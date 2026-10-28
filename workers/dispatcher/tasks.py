from __future__ import annotations

from datetime import UTC, datetime, timedelta
import logging
from uuid import UUID

import redis.asyncio as redis
from sqlalchemy import select, update

import studio_api.models  # noqa: F401
from studio_api.core.celery_app import celery_app
from studio_api.core.config import get_settings
from studio_api.core.db import SessionFactory, run_worker_coroutine
from studio_api.modules.projects.models import Project
from studio_api.modules.workflows.autopilot import produce_source_story, reserve_latest_source
from studio_api.modules.workflows.source_feed import fetch_nasa_earth_items
from studio_api.modules.workflows.models import OutboxEvent, ProductionJob, SourceStory
from studio_api.modules.workflows.models import JobStep

logger = logging.getLogger(__name__)


@celery_app.task(name="studio.produce_source_story", acks_late=True)
def produce_discovered_story(source_id: str) -> str:
    return run_worker_coroutine(_produce_discovered_story(UUID(source_id)))


async def _produce_discovered_story(source_id: UUID) -> str:
    async with SessionFactory() as db:
        result = await produce_source_story(db, source_id)
        return str(result.job_id) if result.job_id else ""


@celery_app.task(name="studio.discover_daily", acks_late=True)
def discover_daily() -> int:
    return run_worker_coroutine(_discover_daily())


async def _discover_daily() -> int:
    async with SessionFactory() as db:
        projects = list(
            await db.scalars(
                select(Project).where(Project.status == "active", Project.autopilot_enabled.is_(True))
            )
        )
        if not projects:
            return 0
        items = await fetch_nasa_earth_items()
        queued = 0
        for project in projects:
            try:
                source, created = await reserve_latest_source(db, project, items)
                if created or (
                    source.status == "selected"
                    and source.created_at.replace(tzinfo=UTC)
                    <= datetime.now(UTC) - timedelta(minutes=1)
                ):
                    celery_app.send_task(
                        "studio.produce_source_story", args=[str(source.id)], queue="dispatcher"
                    )
                    queued += 1
            except Exception:
                logger.exception("Daily source discovery failed for project %s", project.id)
        return queued


@celery_app.task(name="studio.dispatch_job", acks_late=True)
def dispatch_job(job_id: str) -> bool:
    return run_worker_coroutine(_dispatch_job(UUID(job_id)))


async def _dispatch_job(job_id: UUID) -> bool:
    async with SessionFactory() as db:
        result = await db.execute(
            update(ProductionJob)
            .where(ProductionJob.id == job_id, ProductionJob.status == "queued")
            .values(
                status="claimed",
                lease_expires_at=datetime.now(UTC) + timedelta(minutes=5),
            )
        )
        await db.commit()
        if result.rowcount == 1:
            celery_app.send_task("studio.run_job", args=[str(job_id)], queue="cpu")
            return True
        return False


@celery_app.task(name="studio.reconcile_expired_leases", acks_late=True)
def reconcile_expired_leases() -> int:
    return run_worker_coroutine(_reconcile_expired_leases())


async def _reconcile_expired_leases() -> int:
    async with SessionFactory() as db:
        now = datetime.now(UTC)
        result = await db.execute(
            update(ProductionJob)
            .where(
                ProductionJob.status.in_(["claimed", "running"]),
                ProductionJob.lease_expires_at < now,
            )
            .values(status="queued", lease_expires_at=None)
        )
        await db.execute(
            update(JobStep)
            .where(
                JobStep.status == "running",
                JobStep.lease_expires_at < now,
            )
            .values(status="retry", lease_expires_at=None)
        )
        abandoned_sources = await db.execute(
            update(SourceStory)
            .where(
                SourceStory.status == "generating",
                SourceStory.updated_at < now - timedelta(minutes=20),
            )
            .values(
                status="failed",
                error_message="Story generation interrupted; retry this source",
            )
        )
        await db.commit()
        queued_ids = list(
            await db.scalars(
                select(ProductionJob.id)
                .where(ProductionJob.status == "queued")
                .limit(100)
            )
        )
        for queued_id in queued_ids:
            celery_app.send_task(
                "studio.dispatch_job", args=[str(queued_id)], queue="dispatcher"
            )
        return result.rowcount + abandoned_sources.rowcount


@celery_app.task(name="studio.dispatch_outbox", acks_late=True)
def dispatch_outbox() -> int:
    return run_worker_coroutine(_dispatch_outbox())


async def _dispatch_outbox() -> int:
    client = redis.from_url(get_settings().redis_url)
    count = 0
    try:
        async with SessionFactory() as db:
            events = list(
                await db.scalars(
                    select(OutboxEvent)
                    .where(OutboxEvent.status == "pending")
                    .order_by(OutboxEvent.created_at)
                    .limit(100)
                    .with_for_update(skip_locked=True)
                )
            )
            for event in events:
                if event.event_type == "production.job.queued.v1":
                    celery_app.send_task(
                        "studio.dispatch_job",
                        args=[str(event.aggregate_id)],
                        queue="dispatcher",
                        task_id=event.message_id,
                    )
                await client.publish(
                    f"studio.events.{event.event_type}",
                    event.model_dump_json()
                    if hasattr(event, "model_dump_json")
                    else str(event.payload),
                )
                event.status = "sent"
                event.attempts += 1
                count += 1
            await db.commit()
    finally:
        await client.aclose()
    return count
