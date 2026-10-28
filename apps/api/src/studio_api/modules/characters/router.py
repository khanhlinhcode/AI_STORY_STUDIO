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
from studio_api.modules.characters.models import Character, CharacterRevision
from studio_api.modules.characters.service import (
    create_character,
    link_lora_model,
    update_character,
)
from studio_api.modules.projects.models import Project

router = APIRouter(tags=["characters"])


class CharacterCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    bible_data: dict[str, Any]


class CharacterUpdate(BaseModel):
    bible_data: dict[str, Any]


class LinkLoraRequest(BaseModel):
    deployment_id: UUID


class CharacterView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    name: str
    character_bible: dict[str, Any]
    approved_look: dict[str, Any]
    consent_verified: bool
    is_approved: bool
    version: int
    lora_model_id: UUID | None


async def _character_access(
    db: AsyncSession, user_id: UUID, character_id: UUID, role: Role = Role.VIEWER
) -> Character:
    character = await db.get(Character, character_id)
    if character is None:
        raise HTTPException(404, "Character not found")
    project = await db.get_one(Project, character.project_id)
    await assert_workspace_role(db, user_id, project.workspace_id, role)
    return character


@router.get("/projects/{project_id}/characters", response_model=list[CharacterView])
async def list_characters(
    project_id: UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Character]:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "Project not found")
    await assert_workspace_role(db, user.id, project.workspace_id)
    return list(await db.scalars(select(Character).where(Character.project_id == project_id)))


@router.post("/projects/{project_id}/characters", response_model=CharacterView, status_code=201)
async def add_character(
    project_id: UUID,
    payload: CharacterCreate,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Character:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "Project not found")
    await assert_workspace_role(db, user.id, project.workspace_id, Role.EDITOR)
    return await create_character(db, project_id, payload.name, payload.bible_data)


@router.get("/characters/{character_id}", response_model=CharacterView)
async def get_character(
    character_id: UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Character:
    return await _character_access(db, user.id, character_id)


@router.put("/characters/{character_id}", response_model=CharacterView)
async def edit_character(
    character_id: UUID,
    payload: CharacterUpdate,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Character:
    character = await _character_access(db, user.id, character_id, Role.EDITOR)
    return await update_character(db, character, payload.bible_data)


@router.get("/characters/{character_id}/revisions")
async def character_history(
    character_id: UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    await _character_access(db, user.id, character_id)
    rows = list(
        await db.scalars(
            select(CharacterRevision)
            .where(CharacterRevision.character_id == character_id)
            .order_by(CharacterRevision.version)
        )
    )
    return [
        {"id": row.id, "version": row.version, "character_bible": row.character_bible}
        for row in rows
    ]


@router.post("/characters/{character_id}/approve", response_model=CharacterView)
async def approve_character(
    character_id: UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Character:
    character = await _character_access(db, user.id, character_id, Role.PRODUCER)
    character.is_approved = True
    await db.commit()
    await db.refresh(character)
    return character


@router.post("/characters/{character_id}/link-lora", response_model=CharacterView)
async def link_lora(
    character_id: UUID,
    payload: LinkLoraRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Character:
    character = await _character_access(db, user.id, character_id, Role.ML_ENGINEER)
    return await link_lora_model(db, character, payload.deployment_id)
