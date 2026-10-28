"""Exercise DB and worker transitions under duplicate delivery and interruption."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import select
from workers.cpu_render import pipeline, render
from workers.dispatcher import tasks as dispatcher

from studio_api.core.db import SessionFactory
from studio_api.core.errors import ErrorCode, StudioError
from studio_api.core.rate_limit import RateLimitMiddleware
from studio_api.main import app
from studio_api.modules.assets.models import Asset
from studio_api.modules.assets.service import upload_asset
from studio_api.modules.projects.models import Episode
from studio_api.modules.scenes.models import Scene, SceneRevision
from studio_api.modules.workflows.models import JobStep, OutboxEvent, ProductionJob


async def _new_job(client: AsyncClient, owner: dict[str, str]) -> tuple[UUID, UUID]:
    middleware = app.middleware_stack
    while middleware is not None:
        if isinstance(middleware, RateLimitMiddleware):
            middleware.windows.clear()
            break
        middleware = getattr(middleware, "app", None)
    project = await client.post("/api/v1/projects", headers=owner, json={"title": "Fault lab"})
    episode = await client.post(
        f"/api/v1/projects/{project.json()['id']}/episodes",
        headers=owner,
        json={"title": "Fault story", "execution_mode": "automation"},
    )
    episode_id = UUID(episode.json()["id"])
    script = await client.post(
        f"/api/v1/episodes/{episode_id}/script/generate",
        headers=owner,
        json={"topic": "thỏ trắng tìm lá"},
    )
    assert script.status_code == 202
    started = await client.post(
        f"/api/v1/episodes/{episode_id}/production/start",
        headers=owner,
        json={"idempotency_key": "fault-key"},
    )
    assert started.status_code == 202
    return episode_id, UUID(started.json()["id"])


@pytest.mark.asyncio
async def test_duplicate_dispatch_and_outbox_are_idempotent(
    client: AsyncClient, owner: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    episode_id, job_id = await _new_job(client, owner)
    again = await client.post(
        f"/api/v1/episodes/{episode_id}/production/start",
        headers=owner,
        json={"idempotency_key": "fault-key"},
    )
    assert UUID(again.json()["id"]) == job_id
    sent: list[str] = []
    monkeypatch.setattr(dispatcher.celery_app, "send_task", lambda name, **_: sent.append(name))
    assert await dispatcher._dispatch_job(job_id) is True
    assert await dispatcher._dispatch_job(job_id) is False
    async with SessionFactory() as db:
        jobs = list(await db.scalars(select(ProductionJob).where(ProductionJob.id == job_id)))
        steps = list(await db.scalars(select(JobStep).where(JobStep.job_id == job_id)))
        outbox = list(
            await db.scalars(
                select(OutboxEvent).where(OutboxEvent.event_type == "production.job.queued.v1")
            )
        )
    assert len(jobs) == 1
    assert len(steps) == 14
    assert len(outbox) == 1
    assert sent == ["studio.run_job"]


@pytest.mark.asyncio
async def test_expired_worker_lease_requeues_step(
    client: AsyncClient, owner: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _, job_id = await _new_job(client, owner)
    expired = datetime.now(UTC) - timedelta(seconds=5)
    async with SessionFactory() as db:
        job = await db.get_one(ProductionJob, job_id)
        step = await db.scalar(select(JobStep).where(JobStep.job_id == job_id))
        assert step is not None
        job.status = "running"
        job.lease_expires_at = expired
        step.status = "running"
        step.lease_expires_at = expired
        step_id = step.id
        await db.commit()
    sent: list[str] = []
    monkeypatch.setattr(dispatcher.celery_app, "send_task", lambda name, **_: sent.append(name))
    assert await dispatcher._reconcile_expired_leases() >= 1
    async with SessionFactory() as db:
        job = await db.get_one(ProductionJob, job_id)
        step = await db.get_one(JobStep, step_id)
        assert job.status == "queued"
        assert step.status == "retry"
        assert step.lease_expires_at is None
    assert "studio.dispatch_job" in sent


@pytest.mark.asyncio
async def test_script_edit_keeps_running_job_on_old_snapshot(
    client: AsyncClient, owner: dict[str, str]
) -> None:
    episode_id, job_id = await _new_job(client, owner)
    async with SessionFactory() as db:
        job = await db.get_one(ProductionJob, job_id)
        job.status = "running"
        old_snapshot = job.snapshot_revision
        old_revisions = set(
            await db.scalars(
                select(JobStep.scene_revision_id).where(
                    JobStep.job_id == job_id, JobStep.kind == "image"
                )
            )
        )
        await db.commit()
    revised = await client.post(
        f"/api/v1/episodes/{episode_id}/script/generate",
        headers=owner,
        json={"topic": "câu chuyện mới về rừng xanh"},
    )
    assert revised.status_code == 202
    async with SessionFactory() as db:
        job = await db.get_one(ProductionJob, job_id)
        episode = await db.get_one(Episode, episode_id)
        current_scenes = list(
            await db.scalars(
                select(Scene).where(Scene.episode_id == episode_id, Scene.is_active.is_(True))
            )
        )
        assert episode.revision > old_snapshot
        assert job.snapshot_revision == old_snapshot
        assert old_revisions.isdisjoint({scene.current_revision_id for scene in current_scenes})
        for revision_id in old_revisions:
            if revision_id is not None:
                assert (await db.get_one(SceneRevision, revision_id)).script_revision_id


@pytest.mark.asyncio
async def test_storage_full_fails_without_temporary_render_files(
    client: AsyncClient,
    owner: dict[str, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, job_id = await _new_job(client, owner)
    monkeypatch.setattr(render.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(render.shutil, "disk_usage", lambda _: SimpleNamespace(free=0))
    async with SessionFactory() as db:
        job = await db.get_one(ProductionJob, job_id)
        with pytest.raises(StudioError) as failure:
            await render.render_job_media(db, job)
    assert failure.value.code == ErrorCode.INSUFFICIENT_STORAGE
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_cancel_during_running_step_does_not_link_late_asset(
    client: AsyncClient, owner: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _, job_id = await _new_job(client, owner)
    async with SessionFactory() as db:
        job = await db.get_one(ProductionJob, job_id)
        job.status = "running"
        step = await db.scalar(
            select(JobStep).where(JobStep.job_id == job_id, JobStep.kind == "image")
        )
        assert step is not None
        step_id = step.id
        await db.commit()
    begun = asyncio.Event()
    resume = asyncio.Event()

    async def slow_image(db, job, step) -> Asset:
        begun.set()
        await resume.wait()
        image = BytesIO()
        Image.new("RGB", (32, 32), "blue").save(image, format="PNG")
        return await upload_asset(
            db,
            job.workspace_id,
            image.getvalue(),
            "image/png",
            {"source": "fixture", "commercial_use": False},
        )

    monkeypatch.setattr(pipeline, "_generate_image", slow_image)
    task = asyncio.create_task(pipeline.execute_step_async(step_id))
    await begun.wait()
    cancelled = await client.post(f"/api/v1/jobs/{job_id}/cancel", headers=owner)
    assert cancelled.status_code == 204
    resume.set()
    await task
    async with SessionFactory() as db:
        job = await db.get_one(ProductionJob, job_id)
        step = await db.get_one(JobStep, step_id)
        assert job.status == "cancelled"
        assert step.status == "cancelled"
        assert step.output_manifest_id is None
