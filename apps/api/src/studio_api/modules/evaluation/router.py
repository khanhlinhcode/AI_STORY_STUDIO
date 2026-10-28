from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from studio_api.core.access import assert_workspace_role
from studio_api.core.db import get_db
from studio_api.core.security import Role, get_current_user
from studio_api.modules.evaluation.models import ReviewTask
from studio_api.modules.evaluation.review_service import create_review_task, submit_decision
from studio_api.modules.projects.models import Episode, Project

router = APIRouter(tags=["evaluation"])


class ReviewCreate(BaseModel):
    reviewer_id: UUID


class ReviewDecisionRequest(BaseModel):
    verdict: str = Field(pattern=r"^(approved|rejected)$")
    notes: str = ""
    rubric_scores: dict[str, Any] = Field(default_factory=dict)


class ReviewTaskView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    episode_id: UUID
    reviewer_id: UUID
    episode_revision: int
    status: str


@router.get("/episodes/{episode_id}/reviews", response_model=list[ReviewTaskView])
async def list_reviews(
    episode_id: UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ReviewTask]:
    episode = await db.get(Episode, episode_id)
    if episode is None:
        raise HTTPException(404, "Episode not found")
    project = await db.get_one(Project, episode.project_id)
    await assert_workspace_role(db, user.id, project.workspace_id)
    return list(
        await db.scalars(
            select(ReviewTask)
            .where(ReviewTask.episode_id == episode_id)
            .order_by(ReviewTask.created_at.desc())
            .limit(20)
        )
    )


@router.post("/episodes/{episode_id}/reviews", status_code=201)
async def create_review(
    episode_id: UUID,
    payload: ReviewCreate,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    episode = await db.get(Episode, episode_id)
    if episode is None:
        raise HTTPException(404, "Episode not found")
    project = await db.get_one(Project, episode.project_id)
    await assert_workspace_role(db, user.id, project.workspace_id, Role.PRODUCER)
    await assert_workspace_role(db, payload.reviewer_id, project.workspace_id, Role.REVIEWER)
    task = await create_review_task(db, episode, payload.reviewer_id)
    return {"task_id": task.id, "status": task.status}


@router.post("/reviews/{task_id}/decision", status_code=201)
async def decide(
    task_id: UUID,
    payload: ReviewDecisionRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    task = await db.get(ReviewTask, task_id)
    if task is None:
        raise HTTPException(404, "Review task not found")
    episode = await db.get_one(Episode, task.episode_id)
    project = await db.get_one(Project, episode.project_id)
    await assert_workspace_role(db, user.id, project.workspace_id, Role.REVIEWER)
    decision = await submit_decision(
        db,
        task,
        episode,
        user.id,
        payload.verdict,
        payload.notes,
        payload.rubric_scores,
    )
    return {"decision_id": decision.id, "verdict": decision.verdict}
