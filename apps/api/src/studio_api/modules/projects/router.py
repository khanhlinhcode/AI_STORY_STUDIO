from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from studio_api.core.access import assert_workspace_role
from studio_api.core.db import get_db
from studio_api.core.errors import ConflictError
from studio_api.core.security import Role, get_current_user
from studio_api.modules.projects.models import Episode, ExecutionMode, Project

router = APIRouter(tags=["projects"])


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    locale: str = "vi"
    audience: str = "children-6-10"
    style_profile: dict[str, Any] = Field(default_factory=dict)


class ProjectView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    workspace_id: UUID
    title: str
    locale: str
    audience: str
    style_profile: dict[str, Any]
    status: str
    version: int
    autopilot_enabled: bool


class EpisodeCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    topic: str = Field(default="", max_length=500)
    duration_goal_ms: int = Field(default=60000, ge=18000, le=600000)
    aspect_ratio: str = Field(default="9:16", pattern=r"^(9:16|16:9)$")
    execution_mode: ExecutionMode = ExecutionMode.AUTOMATION


class EpisodeView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    title: str
    topic: str
    duration_goal_ms: int
    aspect_ratio: str
    execution_mode: str
    status: str
    revision: int


@router.get("/projects", response_model=list[ProjectView])
async def list_projects(
    x_workspace_id: Annotated[UUID, Header()],
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Project]:
    await assert_workspace_role(db, user.id, x_workspace_id)
    return list(
        await db.scalars(
            select(Project)
            .where(Project.workspace_id == x_workspace_id, Project.status != "deleted")
            .order_by(Project.created_at.desc())
        )
    )


@router.post("/projects", response_model=ProjectView, status_code=201)
async def create_project(
    payload: ProjectCreate,
    x_workspace_id: Annotated[UUID, Header()],
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Project:
    await assert_workspace_role(db, user.id, x_workspace_id, Role.EDITOR)
    project = Project(workspace_id=x_workspace_id, **payload.model_dump())
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.get("/projects/{project_id}", response_model=ProjectView)
async def get_project(
    project_id: UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Project:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    await assert_workspace_role(db, user.id, project.workspace_id)
    return project


@router.patch("/projects/{project_id}", response_model=ProjectView)
async def update_project(
    project_id: UUID,
    payload: ProjectCreate,
    expected_version: int,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Project:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    await assert_workspace_role(db, user.id, project.workspace_id, Role.EDITOR)
    result = await db.execute(
        update(Project)
        .where(Project.id == project_id, Project.version == expected_version)
        .values(**payload.model_dump(), version=expected_version + 1)
    )
    if result.rowcount != 1:
        raise ConflictError()
    await db.commit()
    return await db.get_one(Project, project_id)


@router.get("/projects/{project_id}/episodes", response_model=list[EpisodeView])
async def list_episodes(
    project_id: UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Episode]:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    await assert_workspace_role(db, user.id, project.workspace_id)
    return list(
        await db.scalars(
            select(Episode)
            .where(Episode.project_id == project_id)
            .order_by(Episode.created_at.desc())
        )
    )


@router.post("/projects/{project_id}/episodes", response_model=EpisodeView, status_code=201)
async def create_episode(
    project_id: UUID,
    payload: EpisodeCreate,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Episode:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    await assert_workspace_role(db, user.id, project.workspace_id, Role.EDITOR)
    episode = Episode(project_id=project_id, **payload.model_dump(mode="json"))
    db.add(episode)
    await db.commit()
    await db.refresh(episode)
    return episode


@router.get("/episodes/{episode_id}", response_model=EpisodeView)
async def get_episode(
    episode_id: UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Episode:
    episode = await db.get(Episode, episode_id)
    if episode is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Episode not found")
    project = await db.get_one(Project, episode.project_id)
    await assert_workspace_role(db, user.id, project.workspace_id)
    return episode
