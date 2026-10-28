from __future__ import annotations

import io
import json
import zipfile
from uuid import UUID

import pytest
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import select

from studio_api.core.db import SessionFactory
from studio_api.modules.assets.service import upload_asset
from studio_api.modules.evaluation.models import EvalRun
from studio_api.modules.projects.models import Episode
from studio_api.modules.workflows.models import JobStep, ProductionJob


@pytest.mark.asyncio
async def test_export_requires_qc_and_downloads_real_bundle(
    client: AsyncClient, owner: dict[str, str]
) -> None:
    project = await client.post(
        "/api/v1/projects", headers=owner, json={"title": "Export test"}
    )
    project_id = project.json()["id"]
    episode = await client.post(
        f"/api/v1/projects/{project_id}/episodes",
        headers=owner,
        json={"title": "Chuyện về Mimi", "execution_mode": "automation"},
    )
    episode_id = episode.json()["id"]
    generated = await client.post(
        f"/api/v1/episodes/{episode_id}/script/generate",
        headers=owner,
        json={"topic": "Mimi tìm bạn"},
    )
    assert generated.status_code == 202
    started = await client.post(
        f"/api/v1/episodes/{episode_id}/production/start", headers=owner, json={}
    )
    job_id = UUID(started.json()["id"])
    blocked = await client.post(
        f"/api/v1/episodes/{episode_id}/export", headers=owner, json={}
    )
    assert blocked.status_code == 400

    async with SessionFactory() as db:
        job = await db.get_one(ProductionJob, job_id)
        job.status = "completed"
        workspace_id = UUID(owner["x-workspace-id"])
        image = Image.new("RGB", (1280, 720), "teal")
        buffer = io.BytesIO()
        image.save(buffer, "JPEG")
        thumbnail = await upload_asset(db, workspace_id, buffer.getvalue(), "image/jpeg", {})
        horizontal = await upload_asset(
            db, workspace_id, b"\x00\x00\x00\x18ftypisomhorizontal", "video/mp4", {}
        )
        vertical = await upload_asset(
            db, workspace_id, b"\x00\x00\x00\x18ftypisomvertical", "video/mp4", {}
        )
        srt = await upload_asset(
            db, workspace_id, b"1\n00:00:00,000 --> 00:00:01,000\nMimi\n", "text/plain", {}
        )
        manifest = await upload_asset(
            db,
            workspace_id,
            json.dumps(
                {
                    "job_id": str(job_id),
                    "episode_revision": job.snapshot_revision,
                    "fixture_only": False,
                    "videos": {"16x9": str(horizontal.id), "9x16": str(vertical.id)},
                    "srt": str(srt.id),
                    "thumbnail": str(thumbnail.id),
                }
            ).encode(),
            "application/json",
            {},
        )
        video_step = await db.scalar(
            select(JobStep).where(JobStep.job_id == job_id, JobStep.kind == "video")
        )
        assert video_step is not None
        video_step.output_manifest_id = manifest.id
        db.add(
            EvalRun(
                job_id=job_id,
                passed=True,
                score=100,
                report={"blocking": False, "technical_checks": ["h264"], "blocking_issues": []},
            )
        )
        await db.commit()

    invalid = await client.post(
        f"/api/v1/episodes/{episode_id}/export",
        headers=owner,
        json={"presets": ["unknown"]},
    )
    assert invalid.status_code == 400
    created = await client.post(
        f"/api/v1/episodes/{episode_id}/export", headers=owner, json={}
    )
    assert created.status_code == 201, created.text
    export_id = created.json()["id"]
    assert created.json()["manifest"]["bundle_asset_id"]
    listed = await client.get(f"/api/v1/episodes/{episode_id}/exports", headers=owner)
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == export_id
    package = await client.get(
        f"/api/v1/exports/{export_id}/publish-package", headers=owner
    )
    assert package.json()["youtube"]["made_for_kids"] is True
    download = await client.get(f"/api/v1/exports/{export_id}/download", headers=owner)
    assert download.status_code == 200
    with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
        assert set(archive.namelist()) == {
            "horizontal.mp4", "vertical.mp4", "captions.srt", "thumbnail.jpg", "metadata.json"
        }
        metadata = json.loads(archive.read("metadata.json"))
        assert metadata["export_id"] == export_id
        assert metadata["files"]["horizontal.mp4"]["sha256"] == horizontal.sha256
    unauthenticated = await client.get(f"/api/v1/exports/{export_id}/download")
    assert unauthenticated.status_code == 401

    async with SessionFactory() as db:
        episode_row = await db.get_one(Episode, UUID(episode_id))
        episode_row.revision += 1
        await db.commit()
    stale = await client.post(
        f"/api/v1/episodes/{episode_id}/export", headers=owner, json={}
    )
    assert stale.status_code == 409


@pytest.mark.asyncio
async def test_studio_review_decision_is_single_use(
    client: AsyncClient, owner: dict[str, str]
) -> None:
    person = await client.get("/api/v1/auth/me", headers=owner)
    assert person.status_code == 200
    reviewer_id = person.json()["id"]
    project = await client.post(
        "/api/v1/projects", headers=owner, json={"title": "Review test"}
    )
    episode = await client.post(
        f"/api/v1/projects/{project.json()['id']}/episodes",
        headers=owner,
        json={"title": "Studio review", "execution_mode": "studio"},
    )
    episode_id = episode.json()["id"]
    script = await client.post(
        f"/api/v1/episodes/{episode_id}/script/generate",
        headers=owner,
        json={"topic": "Mimi giúp bạn"},
    )
    approved = await client.post(
        f"/api/v1/script-revisions/{script.json()['id']}/approve", headers=owner
    )
    assert approved.status_code == 204
    created = await client.post(
        f"/api/v1/episodes/{episode_id}/reviews",
        headers=owner,
        json={"reviewer_id": reviewer_id},
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["task_id"]
    listed = await client.get(f"/api/v1/episodes/{episode_id}/reviews", headers=owner)
    assert listed.json()[0]["id"] == task_id
    decision = await client.post(
        f"/api/v1/reviews/{task_id}/decision",
        headers=owner,
        json={"verdict": "approved", "notes": "Đã xem cả sáu cảnh", "rubric_scores": {}},
    )
    assert decision.status_code == 201, decision.text
    duplicate = await client.post(
        f"/api/v1/reviews/{task_id}/decision",
        headers=owner,
        json={"verdict": "rejected"},
    )
    assert duplicate.status_code == 400
