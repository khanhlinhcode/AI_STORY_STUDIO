from __future__ import annotations

import re
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from studio_api.core.db import get_db
from studio_api.core.security import (
    create_token,
    decode_token,
    get_current_user,
    hash_password,
    verify_password,
)
from studio_api.modules.identity.models import Membership, User, Workspace

router = APIRouter(tags=["identity"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    display_name: str = Field(min_length=1, max_length=120)
    workspace_name: str = Field(min_length=2, max_length=160)
    workspace_slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,78}[a-z0-9]$")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    workspace_id: UUID | None = None


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,78}[a-z0-9]$")


class WorkspaceView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    status: str


class UserView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    display_name: str


@router.get("/auth/me", response_model=UserView)
async def current_user(user=Depends(get_current_user)) -> User:
    return user


@router.post("/auth/register", response_model=TokenResponse, status_code=201)
async def register(
    payload: RegisterRequest, db: Annotated[AsyncSession, Depends(get_db)]
) -> TokenResponse:
    existing = await db.scalar(select(User).where(User.email == payload.email.lower()))
    slug_used = await db.scalar(select(Workspace).where(Workspace.slug == payload.workspace_slug))
    if existing or slug_used:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email or workspace slug already exists")
    user = User(
        email=payload.email.lower(),
        hashed_password=hash_password(payload.password),
        display_name=payload.display_name,
    )
    db.add(user)
    await db.flush()
    workspace = Workspace(
        name=payload.workspace_name, slug=payload.workspace_slug, owner_id=user.id
    )
    db.add(workspace)
    await db.flush()
    db.add(Membership(user_id=user.id, workspace_id=workspace.id, role="owner", status="active"))
    await db.commit()
    return TokenResponse(
        access_token=create_token(user.id),
        refresh_token=create_token(user.id, "refresh"),
        workspace_id=workspace.id,
    )


@router.post("/auth/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest, db: Annotated[AsyncSession, Depends(get_db)]
) -> TokenResponse:
    user = await db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    workspace_id = await db.scalar(
        select(Membership.workspace_id)
        .where(Membership.user_id == user.id, Membership.status == "active")
        .limit(1)
    )
    return TokenResponse(
        access_token=create_token(user.id),
        refresh_token=create_token(user.id, "refresh"),
        workspace_id=workspace_id,
    )


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest) -> TokenResponse:
    token = decode_token(payload.refresh_token, "refresh")
    return TokenResponse(
        access_token=create_token(token.sub),
        refresh_token=create_token(token.sub, "refresh"),
    )


@router.get("/workspaces", response_model=list[WorkspaceView])
async def list_workspaces(
    user=Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[Workspace]:
    return list(
        await db.scalars(
            select(Workspace)
            .join(Membership, Membership.workspace_id == Workspace.id)
            .where(Membership.user_id == user.id, Membership.status == "active")
            .order_by(Workspace.name)
        )
    )


@router.post("/workspaces", response_model=WorkspaceView, status_code=201)
async def create_workspace(
    payload: WorkspaceCreate,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Workspace:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,78}[a-z0-9]", payload.slug):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid slug")
    workspace = Workspace(name=payload.name, slug=payload.slug, owner_id=user.id)
    db.add(workspace)
    await db.flush()
    db.add(Membership(user_id=user.id, workspace_id=workspace.id, role="owner"))
    await db.commit()
    await db.refresh(workspace)
    return workspace
