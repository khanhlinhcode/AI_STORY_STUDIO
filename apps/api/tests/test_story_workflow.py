from __future__ import annotations

import io
from uuid import UUID

import pytest
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import select

from studio_api.core.db import SessionFactory
from studio_api.modules.assets.service import upload_asset
from studio_api.modules.scenes.models import Scene, SceneRevision
from studio_api.modules.workflows.models import JobStep


async def create_episode(client: AsyncClient, owner: dict[str, str]) -> tuple[str, str]:
    project = await client.post(
        "/api/v1/projects", headers=owner, json={"title": "Mimi Adventures"}
    )
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]
    episode = await client.post(
        f"/api/v1/projects/{project_id}/episodes",
        headers=owner,
        json={"title": "Draft", "execution_mode": "automation"},
    )
    assert episode.status_code == 201, episode.text
    return project_id, episode.json()["id"]


@pytest.mark.asyncio
async def test_fake_script_creates_six_scenes_and_job(
    client: AsyncClient, owner: dict[str, str]
) -> None:
    _, episode_id = await create_episode(client, owner)
    script = await client.post(
        f"/api/v1/episodes/{episode_id}/script/generate",
        headers=owner,
        json={"topic": "chiếc lá biết hát"},
    )
    assert script.status_code == 202, script.text
    assert len(script.json()["structured_json"]["scenes"]) == 6
    scenes = await client.get(f"/api/v1/episodes/{episode_id}/scenes", headers=owner)
    assert scenes.status_code == 200
    assert len(scenes.json()) == 6

    job = await client.post(
        f"/api/v1/episodes/{episode_id}/production/start",
        headers=owner,
        json={},
    )
    assert job.status_code == 202, job.text
    detail = await client.get(f"/api/v1/jobs/{job.json()['id']}", headers=owner)
    assert detail.status_code == 200
    assert detail.json()["status"] == "queued"
    assert len(detail.json()["steps"]) == 14


@pytest.mark.asyncio
async def test_character_updates_keep_history(client: AsyncClient, owner: dict[str, str]) -> None:
    project_id, _ = await create_episode(client, owner)
    bible = {
        "species": "white rabbit",
        "palette": "white and blue",
        "outfit": "blue overalls",
        "eyes": "round brown",
        "style": "2D storybook",
        "rights": "original",
    }
    created = await client.post(
        f"/api/v1/projects/{project_id}/characters",
        headers=owner,
        json={"name": "Mimi", "bible_data": bible},
    )
    assert created.status_code == 201, created.text
    character_id = created.json()["id"]
    updated = await client.put(
        f"/api/v1/characters/{character_id}",
        headers=owner,
        json={"bible_data": {"outfit": "blue overalls with yellow buttons"}},
    )
    assert updated.json()["version"] == 2
    history = await client.get(f"/api/v1/characters/{character_id}/revisions", headers=owner)
    assert [item["version"] for item in history.json()] == [1, 2]


@pytest.mark.asyncio
async def test_asset_upload_deduplicates_by_sha(client: AsyncClient, owner: dict[str, str]) -> None:
    image = Image.new("RGB", (64, 64), "navy")
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    content = buffer.getvalue()
    form = {"rights": '{"source":"original","commercial_use":true}'}
    first = await client.post(
        "/api/v1/assets/upload",
        headers=owner,
        data=form,
        files={"file": ("fixture.png", content, "image/png")},
    )
    second = await client.post(
        "/api/v1/assets/upload",
        headers=owner,
        data=form,
        files={"file": ("fixture.png", content, "image/png")},
    )
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    listed = await client.get("/api/v1/assets?mime_type=image/png", headers=owner)
    assert listed.status_code == 200, listed.text
    assert [asset["id"] for asset in listed.json()] == [first.json()["id"]]


@pytest.mark.asyncio
async def test_scene_variant_requires_render_before_approval_and_keeps_history(
    client: AsyncClient, owner: dict[str, str]
) -> None:
    _, episode_id = await create_episode(client, owner)
    generated = await client.post(
        f"/api/v1/episodes/{episode_id}/script/generate",
        headers=owner,
        json={"topic": "chiếc lá biết hát"},
    )
    assert generated.status_code == 202, generated.text
    scenes = (await client.get(f"/api/v1/episodes/{episode_id}/scenes", headers=owner)).json()
    scene_id = scenes[0]["id"]
    original_revision = scenes[0]["current_revision_id"]
    created = await client.post(
        f"/api/v1/scenes/{scene_id}/generate-image/regenerate",
        headers=owner,
        json={"prompt": "Ánh sáng ban mai dịu nhẹ"},
    )
    assert created.status_code == 202, created.text
    variant_id = created.json()["scene_revision_id"]
    assert variant_id != original_revision
    rejected = await client.post(
        f"/api/v1/scenes/{scene_id}/revisions/{variant_id}/approve", headers=owner
    )
    assert rejected.status_code == 400
    async with SessionFactory() as db:
        step = await db.scalar(
            select(JobStep).where(JobStep.job_id == UUID(created.json()["job_id"]))
        )
        assert step is not None
        image = Image.new("RGB", (32, 32), "teal")
        buffer = io.BytesIO()
        image.save(buffer, "PNG")
        asset = await upload_asset(
            db,
            UUID(owner["x-workspace-id"]),
            buffer.getvalue(),
            "image/png",
            {"source": "test", "commercial_use": True},
        )
        step.status = "completed"
        step.output_manifest_id = asset.id
        await db.commit()
    approved = await client.post(
        f"/api/v1/scenes/{scene_id}/revisions/{variant_id}/approve", headers=owner
    )
    assert approved.status_code == 204, approved.text
    updated = (await client.get(f"/api/v1/episodes/{episode_id}/scenes", headers=owner)).json()
    assert updated[0]["current_revision_id"] == variant_id
    revisions = (await client.get(f"/api/v1/scenes/{scene_id}/revisions", headers=owner)).json()
    assert {item["id"] for item in revisions} == {original_revision, variant_id}
    async with SessionFactory() as db:
        assert await db.get(Scene, UUID(scene_id)) is not None
        assert await db.get(SceneRevision, UUID(original_revision)) is not None
