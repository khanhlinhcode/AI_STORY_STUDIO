from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from studio_api.core.access import assert_workspace_role
from studio_api.core.celery_app import celery_app
from studio_api.core.config import get_settings
from studio_api.core.db import get_db
from studio_api.core.security import Role, get_current_user
from studio_api.modules.projects.models import Project
from studio_api.modules.workflows.automation import AutomationLoop
from studio_api.modules.workflows.autopilot import reserve_latest_source
from studio_api.modules.workflows.models import AutomationBatch, ProductionJob, SourceStory
from studio_api.modules.workflows.service import cancel_job
from studio_api.modules.workflows.source_feed import fetch_nasa_earth_items

router = APIRouter(tags=["automation"])
webhook_router = APIRouter(tags=["webhooks"])


class BatchRequest(BaseModel):
    topics: list[str] = Field(min_length=1, max_length=50)
    project_id: UUID
    style: str = "Vietnamese storybook"


class GenerateWebhook(BaseModel):
    topic: str = Field(min_length=2, max_length=500)
    project_id: UUID
    style: str = "Vietnamese storybook"


class AutopilotSetting(BaseModel):
    enabled: bool


async def _autopilot_project(
    db: AsyncSession, project_id: UUID, user_id: UUID, role: Role = Role.VIEWER
) -> Project:
    project = await db.get(Project, project_id)
    if project is None or project.status != "active":
        raise HTTPException(404, "Project not found")
    await assert_workspace_role(db, user_id, project.workspace_id, role)
    return project


@router.get("/projects/{project_id}/autopilot/preview")
async def autopilot_preview(
    project_id: UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, object]]:
    project = await _autopilot_project(db, project_id, user.id)
    items = await fetch_nasa_earth_items()
    existing = set(
        await db.scalars(
            select(SourceStory.source_hash).where(SourceStory.project_id == project.id)
        )
    )
    return [
        {
            "title": item.title,
            "summary": item.summary,
            "source_url": item.url,
            "image_url": item.image_url,
            "published_at": item.published_at,
            "already_used": item.source_hash in existing,
        }
        for item in items
    ]


@router.get("/projects/{project_id}/autopilot/sources")
async def autopilot_sources(
    project_id: UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, object]]:
    await _autopilot_project(db, project_id, user.id)
    sources = list(
        await db.scalars(
            select(SourceStory)
            .where(SourceStory.project_id == project_id)
            .order_by(SourceStory.created_at.desc())
            .limit(30)
        )
    )
    jobs = {
        source.job_id: await db.get(ProductionJob, source.job_id)
        for source in sources
        if source.job_id
    }
    return [
        {
            "id": source.id,
            "title": source.title,
            "summary": source.summary,
            "source_url": source.source_url,
            "image_url": source.image_url,
            "published_at": source.published_at,
            "status": source.status,
            "error_message": source.error_message,
            "episode_id": source.episode_id,
            "job_id": source.job_id,
            "job_status": getattr(
                jobs.get(source.job_id) if source.job_id is not None else None,
                "status",
                None,
            ),
            "model_snapshot": source.model_snapshot,
        }
        for source in sources
    ]


@router.post("/projects/{project_id}/autopilot/run", status_code=202)
async def autopilot_run(
    project_id: UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    project = await _autopilot_project(db, project_id, user.id, Role.PRODUCER)
    items = await fetch_nasa_earth_items()
    source, created = await reserve_latest_source(db, project, items)
    if created or (
        source.status == "selected"
        and source.created_at.replace(tzinfo=UTC) <= datetime.now(UTC) - timedelta(minutes=1)
    ):
        celery_app.send_task(
            "studio.produce_source_story", args=[str(source.id)], queue="dispatcher"
        )
    return {
        "source_id": source.id,
        "title": source.title,
        "status": source.status,
        "created": created,
        "job_id": source.job_id,
    }


@router.post("/projects/{project_id}/autopilot/retry/{source_id}", status_code=202)
async def autopilot_retry(
    project_id: UUID,
    source_id: UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    await _autopilot_project(db, project_id, user.id, Role.PRODUCER)
    source = await db.get(SourceStory, source_id)
    if source is None or source.project_id != project_id:
        raise HTTPException(404, "Source story not found")
    if source.status != "failed":
        raise HTTPException(409, "Only a failed source story can be retried")
    source.status = "selected"
    source.job_id = None
    source.error_message = None
    await db.commit()
    celery_app.send_task("studio.produce_source_story", args=[str(source.id)], queue="dispatcher")
    return {"source_id": source.id, "status": source.status}


@router.patch("/projects/{project_id}/autopilot")
async def autopilot_setting(
    project_id: UUID,
    payload: AutopilotSetting,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    project = await _autopilot_project(db, project_id, user.id, Role.PRODUCER)
    project.autopilot_enabled = payload.enabled
    project.version += 1
    await db.commit()
    return {"project_id": project.id, "enabled": project.autopilot_enabled}


async def _run_batch(
    payload: BatchRequest, db: AsyncSession, user_id: UUID | None
) -> AutomationBatch:
    project = await db.get(Project, payload.project_id)
    if project is None:
        raise HTTPException(404, "Project not found")
    if user_id:
        await assert_workspace_role(db, user_id, project.workspace_id, Role.PRODUCER)
    return await AutomationLoop().run_batch(db, payload.topics, project, user_id, payload.style)


@router.post("/automation/batch", status_code=202)
async def batch(
    payload: BatchRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    result = await _run_batch(payload, db, user.id)
    return {"batch_id": result.id, "job_ids": result.job_ids}


@router.get("/automation/batches/{batch_id}/status")
async def batch_status(
    batch_id: UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, int | str]:
    found = await db.get(AutomationBatch, batch_id)
    if found is None:
        raise HTTPException(404, "Batch not found")
    await assert_workspace_role(db, user.id, found.workspace_id)
    return await AutomationLoop().get_batch_status(db, found)


@router.post("/automation/batches/{batch_id}/cancel", status_code=204)
async def cancel_batch(
    batch_id: UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    found = await db.get(AutomationBatch, batch_id)
    if found is None:
        raise HTTPException(404, "Batch not found")
    await assert_workspace_role(db, user.id, found.workspace_id, Role.PRODUCER)
    other_batches = list(
        await db.scalars(
            select(AutomationBatch).where(
                AutomationBatch.workspace_id == found.workspace_id,
                AutomationBatch.id != found.id,
                AutomationBatch.status.notin_(["completed", "failed", "cancelled"]),
            )
        )
    )
    shared_job_ids = {job_id for batch in other_batches for job_id in batch.job_ids}
    for job_id in found.job_ids:
        if job_id in shared_job_ids:
            continue
        job = await db.get(ProductionJob, UUID(job_id))
        if job and job.status not in {"completed", "cancelled"}:
            await cancel_job(db, job, user.id)
    found.status = "cancelled"
    await db.commit()
    return Response(status_code=204)


def _verify_internal_key(authorization: Annotated[str | None, Header()] = None) -> None:
    expected = f"Bearer {get_settings().studio_internal_key}"
    if authorization != expected:
        raise HTTPException(401, "Invalid internal key")


@webhook_router.post(
    "/webhooks/generate", status_code=202, dependencies=[Depends(_verify_internal_key)]
)
async def webhook_generate(
    payload: GenerateWebhook,
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    result = await _run_batch(
        BatchRequest(topics=[payload.topic], project_id=payload.project_id, style=payload.style),
        db,
        None,
    )
    return {"batch_id": result.id, "job_id": result.job_ids[0]}


@webhook_router.post(
    "/webhooks/batch", status_code=202, dependencies=[Depends(_verify_internal_key)]
)
async def webhook_batch(
    payload: BatchRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    result = await _run_batch(payload, db, None)
    return {"batch_id": result.id, "job_ids": result.job_ids}


@webhook_router.get(
    "/webhooks/batches/{batch_id}/status", dependencies=[Depends(_verify_internal_key)]
)
async def webhook_batch_status(
    batch_id: UUID, db: AsyncSession = Depends(get_db)
) -> dict[str, int | str]:
    found = await db.get(AutomationBatch, batch_id)
    if found is None:
        raise HTTPException(404, "Batch not found")
    return await AutomationLoop().get_batch_status(db, found)


@webhook_router.get("/webhooks/jobs/{job_id}", dependencies=[Depends(_verify_internal_key)])
async def webhook_job_status(
    job_id: UUID, db: AsyncSession = Depends(get_db)
) -> dict[str, str | None]:
    job = await db.get(ProductionJob, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    return {"job_id": str(job.id), "status": job.status, "error_code": job.error_code}


@webhook_router.get("/webhooks/jobs", dependencies=[Depends(_verify_internal_key)])
async def webhook_jobs(
    status: str | None = None,
    since: int = Query(default=15, ge=1, le=1440),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, str | None]]:
    statement = select(ProductionJob).where(
        ProductionJob.updated_at >= datetime.now(UTC) - timedelta(minutes=since)
    )
    if status:
        statement = statement.where(ProductionJob.status == status.lower())
    jobs = list(await db.scalars(statement.order_by(ProductionJob.created_at.desc()).limit(100)))
    return [
        {"job_id": str(job.id), "status": job.status, "error_code": job.error_code} for job in jobs
    ]
