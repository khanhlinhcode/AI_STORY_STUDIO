from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from studio_api.core.access import assert_workspace_role
from studio_api.core.db import SessionFactory, get_db
from studio_api.core.security import Role, get_current_user
from studio_api.modules.assets.models import Asset
from studio_api.modules.assets.service import read_asset
from studio_api.modules.evaluation.models import EvalRun
from studio_api.modules.projects.models import Episode, Project
from studio_api.modules.workflows.models import JobStep, ProductionJob
from studio_api.modules.workflows.service import cancel_job, retry_step, start_production_job

router = APIRouter(tags=["workflows"])


class JobView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    workspace_id: UUID
    episode_id: UUID
    status: str
    priority: int
    execution_mode: str
    job_kind: str
    error_code: str | None
    error_message: str | None
    snapshot_revision: int


class StepView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    job_id: UUID
    scene_revision_id: UUID | None
    kind: str
    attempts: int
    max_attempts: int
    status: str
    error_code: str | None


class JobDetail(JobView):
    steps: list[StepView]


class ProductionStart(BaseModel):
    idempotency_key: str | None = None


async def _job_access(
    db: AsyncSession, user_id: UUID, job_id: UUID, role: Role = Role.VIEWER
) -> ProductionJob:
    job = await db.get(ProductionJob, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    await assert_workspace_role(db, user_id, job.workspace_id, role)
    return job


@router.post("/episodes/{episode_id}/production/start", response_model=JobView, status_code=202)
async def start(
    episode_id: UUID,
    payload: ProductionStart,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProductionJob:
    episode = await db.get(Episode, episode_id)
    if episode is None:
        raise HTTPException(404, "Episode not found")
    project = await db.get_one(Project, episode.project_id)
    await assert_workspace_role(db, user.id, project.workspace_id, Role.PRODUCER)
    return await start_production_job(db, episode, user.id, payload.idempotency_key)


@router.get("/jobs", response_model=list[JobView])
async def jobs(
    status_filter: str | None = Query(default=None, alias="status"),
    since_minutes: int | None = Query(default=None, alias="since"),
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProductionJob]:
    from studio_api.modules.identity.models import Membership

    workspace_ids = select(Membership.workspace_id).where(
        Membership.user_id == user.id, Membership.status == "active"
    )
    statement = select(ProductionJob).where(ProductionJob.workspace_id.in_(workspace_ids))
    if status_filter:
        statement = statement.where(ProductionJob.status == status_filter.lower())
    if since_minutes:
        statement = statement.where(
            ProductionJob.updated_at >= datetime.now(UTC) - timedelta(minutes=since_minutes)
        )
    return list(await db.scalars(statement.order_by(ProductionJob.created_at.desc()).limit(200)))


@router.get("/jobs/{job_id}", response_model=JobDetail)
async def job_detail(
    job_id: UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobDetail:
    job = await _job_access(db, user.id, job_id)
    steps = list(
        await db.scalars(
            select(JobStep).where(JobStep.job_id == job.id).order_by(JobStep.created_at)
        )
    )
    return JobDetail(
        **JobView.model_validate(job).model_dump(),
        steps=[StepView.model_validate(step) for step in steps],
    )


@router.get("/jobs/{job_id}/artifacts")
async def job_artifacts(
    job_id: UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    job = await _job_access(db, user.id, job_id)
    video_step = await db.scalar(
        select(JobStep).where(JobStep.job_id == job_id, JobStep.kind == "video")
    )
    if video_step is None or video_step.output_manifest_id is None:
        raise HTTPException(404, "Rendered artifacts are not ready")
    asset = await db.get(Asset, video_step.output_manifest_id)
    if asset is None or asset.workspace_id != job.workspace_id:
        raise HTTPException(404, "Artifact manifest not found")
    manifest = json.loads(await read_asset(asset))
    qc = await db.scalar(
        select(EvalRun).where(EvalRun.job_id == job_id).order_by(EvalRun.created_at.desc()).limit(1)
    )
    return {"manifest": manifest, "qc": qc.report if qc else None}


@router.get("/jobs/{job_id}/events")
async def job_events(
    job_id: UUID,
    request: Request,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EventSourceResponse:
    await _job_access(db, user.id, job_id)

    async def stream() -> AsyncGenerator[dict[str, str], None]:
        previous = ""
        while not await request.is_disconnected():
            async with SessionFactory() as session:
                job = await session.get(ProductionJob, job_id)
                if job is None:
                    yield {"event": "error", "data": json.dumps({"message": "job removed"})}
                    return
                steps = list(await session.scalars(select(JobStep).where(JobStep.job_id == job_id)))
                payload = json.dumps(
                    {
                        "job_id": str(job.id),
                        "status": job.status,
                        "steps": [
                            {"id": str(step.id), "kind": step.kind, "status": step.status}
                            for step in steps
                        ],
                    },
                    sort_keys=True,
                )
                if payload != previous:
                    yield {"event": "job.updated", "data": payload}
                    previous = payload
                if job.status in {"completed", "failed", "cancelled"}:
                    return
            await asyncio.sleep(2)

    return EventSourceResponse(stream(), ping=15)


@router.post("/jobs/{job_id}/cancel", status_code=204)
async def cancel(
    job_id: UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    job = await _job_access(db, user.id, job_id, Role.PRODUCER)
    await cancel_job(db, job, user.id)
    return Response(status_code=204)


@router.post("/jobs/{job_id}/retry-step/{step_id}", response_model=StepView)
async def retry(
    job_id: UUID,
    step_id: UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobStep:
    job = await _job_access(db, user.id, job_id, Role.PRODUCER)
    step = await db.get(JobStep, step_id)
    if step is None:
        raise HTTPException(404, "Step not found")
    await retry_step(db, job, step)
    await db.refresh(step)
    return step
