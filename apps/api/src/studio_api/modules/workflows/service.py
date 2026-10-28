from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from studio_api.core.errors import ErrorCode, StudioError
from studio_api.modules.projects.models import Episode, Project
from studio_api.modules.scenes.models import Scene, SceneRevision
from studio_api.modules.workflows.models import JobStep, ProductionJob
from studio_api.modules.workflows.outbox import add_event
from studio_api.modules.workflows.state_machine import JobStatus, StepStatus, transition_job


async def start_production_job(
    db: AsyncSession,
    episode: Episode,
    requested_by: UUID | None,
    idempotency_key: str | None = None,
) -> ProductionJob:
    project = await db.get(Project, episode.project_id)
    if project is None:
        raise StudioError(ErrorCode.NOT_FOUND, "Project not found", status_code=404)
    key = (
        idempotency_key
        or hashlib.sha256(
            f"{episode.id}:{episode.revision}:{episode.execution_mode}".encode()
        ).hexdigest()
    )
    existing = await db.scalar(
        select(ProductionJob).where(
            ProductionJob.workspace_id == project.workspace_id,
            ProductionJob.idempotency_key == key,
        )
    )
    if existing:
        return existing

    scene_revisions = list(
        await db.scalars(
            select(SceneRevision)
            .join(Scene, Scene.current_revision_id == SceneRevision.id)
            .where(Scene.episode_id == episode.id, Scene.is_active.is_(True))
            .order_by(Scene.order_index)
        )
    )
    if not scene_revisions:
        raise StudioError(ErrorCode.POLICY_REJECTED, "Generate a valid script before production")
    job = ProductionJob(
        workspace_id=project.workspace_id,
        episode_id=episode.id,
        requested_by=requested_by,
        status=JobStatus.DRAFT,
        execution_mode=episode.execution_mode,
        job_kind="episode",
        idempotency_key=key,
        snapshot_revision=episode.revision,
    )
    db.add(job)
    await db.flush()
    for revision in scene_revisions:
        db.add(
            JobStep(job_id=job.id, scene_revision_id=revision.id, kind="image", status="pending")
        )
        db.add(
            JobStep(job_id=job.id, scene_revision_id=revision.id, kind="audio", status="pending")
        )
    db.add(JobStep(job_id=job.id, scene_revision_id=None, kind="video", status="pending"))
    db.add(JobStep(job_id=job.id, scene_revision_id=None, kind="export", status="pending"))
    await transition_job(db, job, JobStatus.VALIDATED, actor_id=requested_by)
    await transition_job(db, job, JobStatus.QUEUED, actor_id=requested_by)
    add_event(
        db,
        event_type="production.job.queued.v1",
        aggregate_id=job.id,
        version=1,
        payload={"job_id": job.id, "episode_id": episode.id},
    )
    episode.status = "queued"
    await db.commit()
    await db.refresh(job)
    return job


async def cancel_job(db: AsyncSession, job: ProductionJob, actor_id: UUID) -> None:
    await transition_job(db, job, JobStatus.CANCELLED, actor_id=actor_id)
    steps = list(await db.scalars(select(JobStep).where(JobStep.job_id == job.id)))
    for step in steps:
        if step.status not in {StepStatus.COMPLETED, StepStatus.CANCELLED}:
            step.status = StepStatus.CANCELLED
    add_event(
        db,
        event_type="production.job.cancelled.v1",
        aggregate_id=job.id,
        version=int(datetime.now(UTC).timestamp()),
        payload={"job_id": job.id},
    )
    await db.commit()


async def retry_step(db: AsyncSession, job: ProductionJob, step: JobStep) -> None:
    if step.job_id != job.id or step.status not in {"failed", "retry"}:
        raise StudioError(ErrorCode.INVALID_TRANSITION, "Only a failed step in this job can retry")
    if step.attempts >= step.max_attempts:
        raise StudioError(ErrorCode.INVALID_TRANSITION, "Step has exhausted its retry budget")
    step.status = "retry"
    job.status = "queued"
    await db.commit()
