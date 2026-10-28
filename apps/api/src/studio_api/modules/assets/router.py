from __future__ import annotations

import json
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from studio_api.core.access import assert_workspace_role
from studio_api.core.db import get_db
from studio_api.core.security import Role, get_current_user
from studio_api.modules.assets.models import Asset
from studio_api.modules.assets.service import read_asset, upload_asset

router = APIRouter(tags=["assets"])


class AssetView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    workspace_id: UUID
    sha256: str
    mime_type: str
    size_bytes: int
    storage_key: str
    rights_declaration: dict[str, Any]
    metadata_json: dict[str, Any]


@router.get("/assets", response_model=list[AssetView])
async def list_assets(
    x_workspace_id: Annotated[UUID, Header()],
    mime_type: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Asset]:
    await assert_workspace_role(db, user.id, x_workspace_id)
    statement = select(Asset).where(Asset.workspace_id == x_workspace_id)
    if mime_type:
        statement = statement.where(Asset.mime_type == mime_type)
    ordered = statement.order_by(Asset.created_at.desc()).offset(offset).limit(limit)
    return list(await db.scalars(ordered))


@router.post("/assets/upload", response_model=AssetView, status_code=201)
async def upload(
    x_workspace_id: Annotated[UUID, Header()],
    file: UploadFile = File(),
    rights: str = Form(...),
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Asset:
    await assert_workspace_role(db, user.id, x_workspace_id, Role.EDITOR)
    try:
        declaration = json.loads(rights)
    except json.JSONDecodeError as exc:
        raise HTTPException(422, "rights must be valid JSON") from exc
    content = await file.read(500 * 1024 * 1024 + 1)
    return await upload_asset(db, x_workspace_id, content, file.content_type or "", declaration)


@router.get("/assets/{asset_id}", response_model=AssetView)
async def get_asset(
    asset_id: UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Asset:
    asset = await db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(404, "Asset not found")
    await assert_workspace_role(db, user.id, asset.workspace_id)
    return asset


@router.get("/assets/{asset_id}/download")
async def download_asset(
    asset_id: UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    asset = await get_asset(asset_id, user, db)
    return Response(
        await read_asset(asset),
        media_type=asset.mime_type,
        headers={
            "Content-Disposition": (
                f'inline; filename="{asset.sha256}"'
                if asset.mime_type.startswith("image/") or asset.mime_type == "video/mp4"
                else f'attachment; filename="{asset.sha256}"'
            )
        },
    )
