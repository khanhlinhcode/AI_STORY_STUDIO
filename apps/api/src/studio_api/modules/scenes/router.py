from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from studio_api.core.access import assert_workspace_role
from studio_api.core.db import get_db
from studio_api.core.security import Role, get_current_user
from studio_api.modules.assets.models import Asset
from studio_api.modules.projects.models import Episode, Project
from studio_api.modules.scenes.models import Scene, SceneRevision
from studio_api.modules.scenes.service import approve_scene_variant, regenerate_scene_image
from studio_api.modules.workflows.models import JobStep

router = APIRouter(tags=["scenes"])


class SceneRevisionView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    scene_id: UUID
    prompt: str
    image_desc: str
    narration: str
    camera: dict[str, object]
    approval_state: str
    seed: int


class SceneView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    episode_id: UUID
    order_index: int
    synopsis: str
    duration_ms: int
    current_revision_id: UUID | None


class SceneOrder(BaseModel):
    scene_ids: list[UUID]


class RegenerateRequest(BaseModel):
    prompt: str | None = Field(default=None, min_length=3, max_length=4000)


@router.get("/episodes/{episode_id}/scenes", response_model=list[SceneView])
async def list_scenes(
    episode_id: UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Scene]:
    episode = await db.get(Episode, episode_id)
    if episode is None:
        raise HTTPException(404, "Episode not found")
    project = await db.get_one(Project, episode.project_id)
    await assert_workspace_role(db, user.id, project.workspace_id)
    return list(
        await db.scalars(
            select(Scene)
            .where(Scene.episode_id == episode_id, Scene.is_active.is_(True))
            .order_by(Scene.order_index)
        )
    )


@router.get("/scenes/{scene_id}/revisions", response_model=list[SceneRevisionView])
async def scene_revisions(
    scene_id: UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SceneRevision]:
    scene = await db.get(Scene, scene_id)
    if scene is None:
        raise HTTPException(404, "Scene not found")
    episode = await db.get_one(Episode, scene.episode_id)
    project = await db.get_one(Project, episode.project_id)
    await assert_workspace_role(db, user.id, project.workspace_id)
    return list(
        await db.scalars(
            select(SceneRevision)
            .where(SceneRevision.scene_id == scene_id)
            .order_by(SceneRevision.created_at.desc())
        )
    )


@router.put("/episodes/{episode_id}/scenes/order", status_code=204)
async def reorder_scenes(
    episode_id: UUID,
    payload: SceneOrder,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    episode = await db.get(Episode, episode_id)
    if episode is None:
        raise HTTPException(404, "Episode not found")
    project = await db.get_one(Project, episode.project_id)
    await assert_workspace_role(db, user.id, project.workspace_id, Role.EDITOR)
    scenes = list(
        await db.scalars(
            select(Scene).where(Scene.episode_id == episode_id, Scene.is_active.is_(True))
        )
    )
    by_id = {scene.id: scene for scene in scenes}
    if set(payload.scene_ids) != set(by_id):
        raise HTTPException(422, "Scene order must contain every scene exactly once")
    for index, scene_id in enumerate(payload.scene_ids):
        by_id[scene_id].order_index = -(index + 1)
    await db.flush()
    for index, scene_id in enumerate(payload.scene_ids):
        by_id[scene_id].order_index = index
    episode.revision += 1
    await db.commit()
    return Response(status_code=204)


@router.get("/scenes/{scene_id}/images")
async def scene_images(
    scene_id: UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, object]]:
    scene = await db.get(Scene, scene_id)
    if scene is None:
        raise HTTPException(404, "Scene not found")
    episode = await db.get_one(Episode, scene.episode_id)
    project = await db.get_one(Project, episode.project_id)
    await assert_workspace_role(db, user.id, project.workspace_id)
    steps = list(
        await db.scalars(
            select(JobStep)
            .join(SceneRevision, SceneRevision.id == JobStep.scene_revision_id)
            .where(
                SceneRevision.scene_id == scene_id,
                JobStep.kind == "image",
                JobStep.status == "completed",
                JobStep.output_manifest_id.is_not(None),
            )
            .order_by(JobStep.created_at.desc())
            .limit(20)
        )
    )
    result: list[dict[str, object]] = []
    for step in steps:
        asset = await db.get(Asset, step.output_manifest_id)
        revision = await db.get(SceneRevision, step.scene_revision_id)
        if asset and revision and asset.workspace_id == project.workspace_id:
            result.append(
                {
                    "asset_id": str(asset.id),
                    "scene_revision_id": str(revision.id),
                    "seed": revision.seed,
                    "approved": revision.id == scene.current_revision_id,
                    "url": f"/api/backend/assets/{asset.id}/download",
                }
            )
    return result


@router.post("/scenes/{scene_id}/generate-image/regenerate", status_code=202)
async def regenerate_image(
    scene_id: UUID,
    payload: RegenerateRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    scene = await db.get(Scene, scene_id)
    if scene is None or not scene.is_active:
        raise HTTPException(404, "Scene not found")
    episode = await db.get_one(Episode, scene.episode_id)
    project = await db.get_one(Project, episode.project_id)
    await assert_workspace_role(db, user.id, project.workspace_id, Role.EDITOR)
    revision, job = await regenerate_scene_image(db, scene, payload.prompt, user.id)
    return {"scene_revision_id": str(revision.id), "job_id": str(job.id)}


@router.post("/scenes/{scene_id}/revisions/{revision_id}/approve", status_code=204)
async def approve_image_variant(
    scene_id: UUID,
    revision_id: UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    scene = await db.get(Scene, scene_id)
    revision = await db.get(SceneRevision, revision_id)
    if scene is None or revision is None:
        raise HTTPException(404, "Scene variant not found")
    episode = await db.get_one(Episode, scene.episode_id)
    project = await db.get_one(Project, episode.project_id)
    await assert_workspace_role(db, user.id, project.workspace_id, Role.PRODUCER)
    await approve_scene_variant(db, scene, revision)
    return Response(status_code=204)
