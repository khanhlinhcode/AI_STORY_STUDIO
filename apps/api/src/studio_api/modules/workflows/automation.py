from __future__ import annotations

import hashlib
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from studio_api.modules.narrative.service import generate_episode_script
from studio_api.modules.projects.models import Episode, Project
from studio_api.modules.workflows.models import AutomationBatch, ProductionJob
from studio_api.modules.workflows.service import start_production_job


class AutomationLoop:
    async def run_batch(
        self,
        db: AsyncSession,
        topics: list[str],
        project: Project,
        requested_by: UUID | None,
        style: str = "Vietnamese storybook",
    ) -> AutomationBatch:
        batch = AutomationBatch(
            workspace_id=project.workspace_id,
            project_id=project.id,
            topics=topics,
            job_ids=[],
            status="running",
        )
        db.add(batch)
        await db.commit()
        await db.refresh(batch)
        job_ids: list[str] = []
        for topic in topics:
            key = hashlib.sha256(
                f"{project.id}:{topic.casefold()}:{date.today()}".encode()
            ).hexdigest()
            existing = await db.scalar(
                select(ProductionJob).where(
                    ProductionJob.workspace_id == project.workspace_id,
                    ProductionJob.idempotency_key == key,
                )
            )
            if existing:
                job_ids.append(str(existing.id))
                continue
            episode = Episode(
                project_id=project.id,
                title=topic[:200],
                topic=topic,
                execution_mode="automation",
                aspect_ratio="9:16",
            )
            db.add(episode)
            await db.commit()
            await db.refresh(episode)
            await generate_episode_script(db, episode, topic, style)
            job = await start_production_job(db, episode, requested_by, key)
            job_ids.append(str(job.id))
        batch.job_ids = job_ids
        batch.status = "queued" if job_ids else "completed"
        await db.commit()
        await db.refresh(batch)
        return batch

    async def get_batch_status(
        self, db: AsyncSession, batch: AutomationBatch
    ) -> dict[str, int | str]:
        jobs = list(
            await db.scalars(
                select(ProductionJob).where(
                    ProductionJob.id.in_([UUID(value) for value in batch.job_ids])
                )
            )
        )
        counts = {"pending": 0, "running": 0, "completed": 0, "failed": 0, "cancelled": 0}
        for job in jobs:
            if job.status in {"draft", "validated", "queued", "claimed", "waiting_resource"}:
                counts["pending"] += 1
            elif job.status == "running":
                counts["running"] += 1
            elif job.status in counts:
                counts[job.status] += 1
        if batch.status == "cancelled":
            status = "cancelled"
        elif jobs and counts["completed"] == len(jobs):
            status = "completed"
        elif jobs and counts["cancelled"] == len(jobs):
            status = "cancelled"
        elif counts["pending"] == 0 and counts["running"] == 0 and counts["failed"]:
            status = "failed"
        elif counts["running"]:
            status = "running"
        else:
            status = batch.status if batch.status == "cancelled" else "queued"
        if batch.status != status:
            batch.status = status
            await db.commit()
        return {"batch_id": str(batch.id), "status": status, **counts}
