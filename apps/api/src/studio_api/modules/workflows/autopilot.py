from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from studio_api.core.config import get_settings
from studio_api.core.errors import ErrorCode, StudioError
from studio_api.modules.narrative.service import generate_episode_script
from studio_api.modules.projects.models import Episode, Project
from studio_api.modules.workflows.models import SourceStory
from studio_api.modules.workflows.service import start_production_job
from studio_api.modules.workflows.source_feed import SourceItem


async def reserve_latest_source(
    db: AsyncSession, project: Project, items: list[SourceItem]
) -> tuple[SourceStory, bool]:
    await db.execute(select(Project.id).where(Project.id == project.id).with_for_update())
    now = datetime.now(UTC)
    await db.execute(
        update(SourceStory)
        .where(
            SourceStory.project_id == project.id,
            SourceStory.status == "generating",
            SourceStory.updated_at < now - timedelta(minutes=20),
        )
        .values(status="failed", error_message="Story generation interrupted; retry this source")
    )
    recent = await db.scalar(
        select(SourceStory)
        .where(
            SourceStory.project_id == project.id,
            SourceStory.created_at >= now - timedelta(hours=24),
            SourceStory.status.in_(["selected", "generating", "queued"]),
        )
        .order_by(SourceStory.created_at.desc())
        .limit(1)
    )
    if recent is not None:
        return recent, False
    used = set(
        await db.scalars(
            select(SourceStory.source_hash).where(SourceStory.project_id == project.id)
        )
    )
    selected = next((item for item in items if item.source_hash not in used), None)
    if selected is None:
        raise StudioError(
            ErrorCode.NOT_FOUND, "No fresh, unused child-friendly NASA article is available",
            status_code=404,
        )
    settings = get_settings()
    source = SourceStory(
        project_id=project.id,
        source_hash=selected.source_hash,
        source_url=selected.url,
        image_url=selected.image_url,
        feed_url=selected.feed_url,
        title=selected.title,
        summary=selected.summary,
        published_at=selected.published_at,
        status="selected",
        model_snapshot={
            "story_backend": settings.ai_story_mode,
            "story_model": (
                settings.ollama_model if settings.ai_story_mode == "ollama" else "fixture"
            ),
            "media_backend": settings.ai_adapter_mode,
            "lora_name": settings.active_lora_name or None,
        },
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return source, True


async def produce_source_story(db: AsyncSession, source_id: UUID) -> SourceStory:
    claimed = await db.execute(
        update(SourceStory)
        .where(SourceStory.id == source_id, SourceStory.status == "selected")
        .values(status="generating")
    )
    await db.commit()
    source = await db.get(SourceStory, source_id)
    if source is None:
        raise StudioError(ErrorCode.NOT_FOUND, "Source story not found", status_code=404)
    if claimed.rowcount != 1:
        return source
    project = await db.get(Project, source.project_id)
    if project is None or project.status != "active":
        source.status = "failed"
        source.error_message = "Project is unavailable"
        await db.commit()
        return source
    try:
        settings = get_settings()
        source.model_snapshot = {
            "story_backend": settings.ai_story_mode,
            "story_model": (
                settings.ollama_model if settings.ai_story_mode == "ollama" else "fixture"
            ),
            "media_backend": settings.ai_adapter_mode,
            "voice_backend": settings.ai_voice_mode,
            "lora_name": settings.active_lora_name or None,
        }
        await db.commit()
        episode = await db.get(Episode, source.episode_id) if source.episode_id else None
        if episode is None:
            episode = Episode(
                project_id=project.id,
                title=source.title[:200],
                topic=source.title,
                execution_mode="automation",
                aspect_ratio="9:16",
            )
            db.add(episode)
            await db.commit()
            await db.refresh(episode)
            source.episode_id = episode.id
            await db.commit()
        await generate_episode_script(
            db,
            episode,
            source.title,
            "Vietnamese illustrated science story for children ages 6–10",
            source_context={
                "title": source.title,
                "summary": source.summary,
                "published_at": source.published_at.isoformat(),
                "source_url": source.source_url,
            },
        )
        key = hashlib.sha256(
            f"source:{project.id}:{source.source_hash}:{episode.revision}".encode()
        ).hexdigest()
        job = await start_production_job(db, episode, None, key)
        source.job_id = job.id
        source.status = "queued"
        source.error_message = None
        await db.commit()
        await db.refresh(source)
        return source
    except Exception as exc:
        await db.rollback()
        source = await db.get_one(SourceStory, source_id)
        source.status = "failed"
        source.error_message = str(exc)[:500]
        await db.commit()
        raise
