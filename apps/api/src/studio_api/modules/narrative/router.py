from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from studio_api.core.access import assert_workspace_role
from studio_api.core.db import get_db
from studio_api.core.security import Role, get_current_user
from studio_api.modules.narrative.models import ScriptRevision
from studio_api.modules.narrative.service import (
    approve_script,
    generate_episode_script,
    get_script_diff,
)
from studio_api.modules.projects.models import Episode, Project

router = APIRouter(tags=["narrative"])


class ScriptGenerateRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=500)
    style: str = Field(default="Vietnamese storybook", max_length=200)


class ScriptView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    episode_id: UUID
    structured_json: dict[str, Any]
    schema_version: str
    parent_id: UUID | None
    is_approved: bool


async def _episode_access(
    db: AsyncSession, user_id: UUID, episode_id: UUID, role: Role = Role.VIEWER
) -> Episode:
    episode = await db.get(Episode, episode_id)
    if episode is None:
        raise HTTPException(404, "Episode not found")
    project = await db.get_one(Project, episode.project_id)
    await assert_workspace_role(db, user_id, project.workspace_id, role)
    return episode


@router.post("/episodes/{episode_id}/script/generate", response_model=ScriptView, status_code=202)
async def generate_script(
    episode_id: UUID,
    payload: ScriptGenerateRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScriptRevision:
    episode = await _episode_access(db, user.id, episode_id, Role.EDITOR)
    return await generate_episode_script(db, episode, payload.topic, payload.style)


@router.get("/episodes/{episode_id}/script/revisions", response_model=list[ScriptView])
async def revisions(
    episode_id: UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ScriptRevision]:
    await _episode_access(db, user.id, episode_id)
    return list(
        await db.scalars(
            select(ScriptRevision)
            .where(ScriptRevision.episode_id == episode_id)
            .order_by(ScriptRevision.created_at.desc())
        )
    )


@router.get("/episodes/{episode_id}/script/diff")
async def diff(
    episode_id: UUID,
    a: UUID,
    b: UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, list[str]]:
    await _episode_access(db, user.id, episode_id)
    first = await db.get(ScriptRevision, a)
    second = await db.get(ScriptRevision, b)
    if (
        first is None
        or second is None
        or first.episode_id != episode_id
        or second.episode_id != episode_id
    ):
        raise HTTPException(404, "Revision not found")
    return {"diff": get_script_diff(first, second)}


@router.post("/script-revisions/{revision_id}/approve", status_code=204)
async def approve(
    revision_id: UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    revision = await db.get(ScriptRevision, revision_id)
    if revision is None:
        raise HTTPException(404, "Revision not found")
    episode = await _episode_access(db, user.id, revision.episode_id, Role.PRODUCER)
    await approve_script(db, revision, episode)
    return Response(status_code=204)
