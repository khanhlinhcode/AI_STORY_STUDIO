from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from studio_api.core.access import assert_workspace_role
from studio_api.core.db import get_db
from studio_api.core.security import Role, get_current_user
from studio_api.modules.assets.models import Asset
from studio_api.modules.assets.service import read_asset
from studio_api.modules.exports.models import Export
from studio_api.modules.exports.service import create_export, generate_publish_package
from studio_api.modules.projects.models import Episode, Project

router = APIRouter(tags=["exports"])


class ExportRequest(BaseModel):
    presets: list[str] = Field(default_factory=lambda: ["16:9", "9:16"])


class ExportView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    episode_id: UUID
    episode_revision: int
    status: str
    manifest: dict[str, object]
    validation: dict[str, object]


@router.get("/episodes/{episode_id}/exports", response_model=list[ExportView])
async def list_exports(
    episode_id: UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Export]:
    episode = await db.get(Episode, episode_id)
    if episode is None:
        raise HTTPException(404, "Episode not found")
    project = await db.get_one(Project, episode.project_id)
    await assert_workspace_role(db, user.id, project.workspace_id)
    return list(
        await db.scalars(
            select(Export)
            .where(Export.episode_id == episode_id)
            .order_by(Export.created_at.desc())
            .limit(20)
        )
    )


@router.post("/episodes/{episode_id}/export", response_model=ExportView, status_code=201)
async def export_episode(
    episode_id: UUID,
    payload: ExportRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Export:
    episode = await db.get(Episode, episode_id)
    if episode is None:
        raise HTTPException(404, "Episode not found")
    project = await db.get_one(Project, episode.project_id)
    await assert_workspace_role(db, user.id, project.workspace_id, Role.PRODUCER)
    result = await create_export(db, episode, payload.presets, user.id)
    return result


@router.get("/exports/{export_id}/download")
async def download_export(
    export_id: UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    result = await db.get(Export, export_id)
    if result is None or result.status != "ready":
        raise HTTPException(404, "Export not found")
    episode = await db.get_one(Episode, result.episode_id)
    project = await db.get_one(Project, episode.project_id)
    await assert_workspace_role(db, user.id, project.workspace_id)
    bundle_id = result.manifest.get("bundle_asset_id")
    asset = await db.get(Asset, UUID(bundle_id)) if isinstance(bundle_id, str) else None
    if asset is None or asset.workspace_id != project.workspace_id:
        raise HTTPException(404, "Export bundle not found")
    return Response(
        await read_asset(asset),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="story-{episode.id}.zip"'},
    )


@router.get("/exports/{export_id}/publish-package")
async def publish_package(
    export_id: UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    result = await db.get(Export, export_id)
    if result is None:
        raise HTTPException(404, "Export not found")
    episode = await db.get_one(Episode, result.episode_id)
    project = await db.get_one(Project, episode.project_id)
    await assert_workspace_role(db, user.id, project.workspace_id)
    return generate_publish_package(episode, result)
