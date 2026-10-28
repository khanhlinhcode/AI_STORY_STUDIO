from __future__ import annotations

import hashlib
import hmac
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Annotated
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from studio_api.core.config import get_settings
from studio_api.core.db import get_db


class Role(StrEnum):
    VIEWER = "viewer"
    REVIEWER = "reviewer"
    EDITOR = "editor"
    ML_ENGINEER = "ml_engineer"
    PRODUCER = "producer"
    OWNER = "owner"


ROLE_RANK = {
    Role.VIEWER: 0,
    Role.REVIEWER: 1,
    Role.EDITOR: 2,
    Role.ML_ENGINEER: 2,
    Role.PRODUCER: 3,
    Role.OWNER: 4,
}


class TokenPayload(BaseModel):
    sub: UUID
    token_type: str
    exp: datetime


password_hasher = PasswordHasher()
bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return password_hasher.verify(hashed, password)
    except VerifyMismatchError:
        return False


def create_token(user_id: UUID, token_type: str = "access") -> str:
    settings = get_settings()
    delta = (
        timedelta(minutes=settings.access_token_minutes)
        if token_type == "access"
        else timedelta(days=settings.refresh_token_days)
    )
    now = datetime.now(UTC)
    return jwt.encode(
        {"sub": str(user_id), "token_type": token_type, "iat": now, "exp": now + delta},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str, expected_type: str = "access") -> TokenPayload:
    settings = get_settings()
    try:
        raw = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        payload = TokenPayload.model_validate(raw)
    except (jwt.PyJWTError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from exc
    if payload.token_type != expected_type:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token type")
    return payload


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from studio_api.modules.identity.models import User

    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    payload = decode_token(credentials.credentials)
    user = await db.get(User, payload.sub)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User is inactive or missing")
    return user


def require_role(min_role: Role) -> Callable[..., object]:
    async def dependency(
        user=Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
        x_workspace_id: Annotated[UUID | None, Header()] = None,
    ):
        from studio_api.modules.identity.models import Membership

        if x_workspace_id is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "X-Workspace-ID is required")
        membership = await db.scalar(
            select(Membership).where(
                Membership.workspace_id == x_workspace_id,
                Membership.user_id == user.id,
                Membership.status == "active",
            )
        )
        if membership is None or ROLE_RANK[Role(membership.role)] < ROLE_RANK[min_role]:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient workspace role")
        return membership

    return dependency


def sign_worker_payload(payload: bytes) -> str:
    return hmac.new(
        get_settings().studio_internal_key.encode(), payload, hashlib.sha256
    ).hexdigest()


def verify_worker_signature(payload: bytes, signature: str) -> bool:
    return hmac.compare_digest(sign_worker_payload(payload), signature)
