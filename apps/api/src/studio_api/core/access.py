from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from studio_api.core.security import ROLE_RANK, Role
from studio_api.modules.identity.models import Membership


async def assert_workspace_role(
    db: AsyncSession,
    user_id: UUID,
    workspace_id: UUID,
    minimum: Role = Role.VIEWER,
) -> Membership:
    membership = await db.scalar(
        select(Membership).where(
            Membership.user_id == user_id,
            Membership.workspace_id == workspace_id,
            Membership.status == "active",
        )
    )
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resource not found")
    if ROLE_RANK[Role(membership.role)] < ROLE_RANK[minimum]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient workspace role")
    return membership
