from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from studio_api.core.errors import ErrorCode, StudioError
from studio_api.modules.evaluation.models import ReviewDecision, ReviewTask
from studio_api.modules.projects.models import Episode
from studio_api.modules.workflows.outbox import add_event


async def create_review_task(db: AsyncSession, episode: Episode, reviewer_id: UUID) -> ReviewTask:
    if episode.execution_mode != "studio":
        raise StudioError(
            ErrorCode.POLICY_REJECTED, "Human review tasks are only used in Studio mode"
        )
    task = ReviewTask(
        episode_id=episode.id,
        reviewer_id=reviewer_id,
        episode_revision=episode.revision,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def submit_decision(
    db: AsyncSession,
    task: ReviewTask,
    episode: Episode,
    reviewer_id: UUID,
    verdict: str,
    notes: str,
    rubric_scores: dict[str, Any],
) -> ReviewDecision:
    if task.episode_revision != episode.revision:
        raise StudioError(
            ErrorCode.ASSET_STALE, "Review task references an old episode revision", status_code=409
        )
    if task.reviewer_id != reviewer_id:
        raise StudioError(ErrorCode.POLICY_REJECTED, "Review task belongs to another reviewer")
    if task.status != "pending":
        raise StudioError(ErrorCode.POLICY_REJECTED, "Review task has already been decided")
    if verdict not in {"approved", "rejected"}:
        raise StudioError(ErrorCode.POLICY_REJECTED, "Invalid review verdict")
    decision = ReviewDecision(
        task_id=task.id,
        reviewer_id=reviewer_id,
        verdict=verdict,
        notes=notes,
        rubric_scores=rubric_scores,
    )
    db.add(decision)
    task.status = verdict
    add_event(
        db,
        event_type="review.decision.v1",
        aggregate_id=task.id,
        version=episode.revision,
        payload={"episode_id": episode.id, "verdict": verdict},
    )
    await db.commit()
    await db.refresh(decision)
    return decision
