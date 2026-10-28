from __future__ import annotations

import hashlib
import secrets
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from studio_api.core.errors import ErrorCode, StudioError
from studio_api.modules.projects.models import Episode, Project
from studio_api.modules.scenes.models import Scene, SceneRevision
from studio_api.modules.workflows.models import JobStep, ProductionJob
from studio_api.modules.workflows.outbox import add_event
from studio_api.modules.workflows.state_machine import JobStatus, transition_job


async def regenerate_scene_image(
    db: AsyncSession,
    scene: Scene,
    prompt: str | None,
    requested_by: UUID,
) -> tuple[SceneRevision, ProductionJob]:
    if scene.current_revision_id is None:
        raise StudioError(ErrorCode.ASSET_STALE, "Scene has no current revision")
    current = await db.get(SceneRevision, scene.current_revision_id)
    episode = await db.get(Episode, scene.episode_id)
    project = await db.get(Project, episode.project_id) if episode else None
    if current is None or episode is None or project is None:
        raise StudioError(ErrorCode.ASSET_STALE, "Scene lineage is incomplete")
    variant = SceneRevision(
        scene_id=scene.id,
        script_revision_id=current.script_revision_id,
        prompt=prompt or current.prompt,
        negative_prompt=current.negative_prompt,
        camera=current.camera,
        image_desc=prompt or current.image_desc,
        narration=current.narration,
        seed=secrets.randbelow(2**31),
        parent_id=current.id,
        approval_state="pending",
    )
    db.add(variant)
    await db.flush()
    job = ProductionJob(
        workspace_id=project.workspace_id,
        episode_id=episode.id,
        requested_by=requested_by,
        execution_mode=episode.execution_mode,
        job_kind="image_variant",
        idempotency_key=hashlib.sha256(f"image_variant:{variant.id}".encode()).hexdigest(),
        snapshot_revision=episode.revision,
        status="draft",
    )
    db.add(job)
    await db.flush()
    db.add(JobStep(job_id=job.id, scene_revision_id=variant.id, kind="image", status="pending"))
    await transition_job(db, job, JobStatus.VALIDATED, actor_id=requested_by)
    await transition_job(db, job, JobStatus.QUEUED, actor_id=requested_by)
    add_event(
        db,
        event_type="production.job.queued.v1",
        aggregate_id=job.id,
        version=1,
        payload={"job_id": job.id, "scene_revision_id": variant.id},
    )
    await db.commit()
    await db.refresh(variant)
    await db.refresh(job)
    return variant, job


async def approve_scene_variant(db: AsyncSession, scene: Scene, variant: SceneRevision) -> None:
    if variant.scene_id != scene.id:
        raise StudioError(ErrorCode.NOT_FOUND, "Variant is not in this scene", status_code=404)
    if variant.approval_state == "rejected":
        raise StudioError(ErrorCode.POLICY_REJECTED, "Rejected variant cannot be approved")
    ready = await db.scalar(
        select(JobStep.id)
        .where(
            JobStep.scene_revision_id == variant.id,
            JobStep.kind == "image",
            JobStep.status == "completed",
            JobStep.output_manifest_id.is_not(None),
        )
        .limit(1)
    )
    if ready is None:
        raise StudioError(ErrorCode.POLICY_REJECTED, "Variant image is not ready")
    scene.current_revision_id = variant.id
    variant.approval_state = "approved"
    episode = await db.get(Episode, scene.episode_id)
    if episode:
        episode.revision += 1
        episode.status = "script_ready"
    await db.commit()
