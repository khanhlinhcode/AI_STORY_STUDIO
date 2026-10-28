"""Exercise the running Compose stack through the web session proxy.

Requires `make up`. Supports fixture and sourced Autopilot verification.
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from time import monotonic
from uuid import uuid4

import httpx


async def main(base_url: str) -> None:
    identity = uuid4().hex[:12]
    async with httpx.AsyncClient(base_url=base_url, timeout=360) as client:
        response = await client.post(
            "/api/session/register",
            json={
                "email": f"stack-{identity}@example.com",
                "password": "local-stack-test-password-123",
                "display_name": "Stack Test",
                "workspace_name": f"Stack Studio {identity}",
                "workspace_slug": f"stack-studio-{identity}",
            },
        )
        response.raise_for_status()
        assert client.cookies.get("studio_access")
        project = await client.post(
            "/api/backend/projects", json={"title": "Live stack verification"}
        )
        project.raise_for_status()
        episode = await client.post(
            f"/api/backend/projects/{project.json()['id']}/episodes",
            json={"title": "Stack preview", "execution_mode": "automation"},
        )
        episode.raise_for_status()
        episode_id = episode.json()["id"]
        script = await client.post(
            f"/api/backend/episodes/{episode_id}/script/generate",
            json={"topic": "chiếc lá biết hát"},
        )
        script.raise_for_status()
        scenes = await client.get(f"/api/backend/episodes/{episode_id}/scenes")
        scenes.raise_for_status()
        assert len(scenes.json()) >= 6
        job = await client.post(
            f"/api/backend/episodes/{episode_id}/production/start", json={}
        )
        job.raise_for_status()
        job_id = job.json()["id"]
        await wait_for_job(client, job_id)
        artifacts = await client.get(f"/api/backend/jobs/{job_id}/artifacts")
        artifacts.raise_for_status()
        manifest = artifacts.json()["manifest"]
        assert manifest["fixture_only"] is True
        assert set(manifest["videos"]) == {"16x9", "9x16"}
        assert artifacts.json()["qc"]["blocking"] is True
        video = await client.get(
            f"/api/backend/assets/{manifest['videos']['16x9']}/download"
        )
        video.raise_for_status()
        assert video.headers["content-type"].startswith("video/mp4")
        assert video.content[4:8] == b"ftyp"
        images = await client.get(
            f"/api/backend/scenes/{scenes.json()[0]['id']}/images"
        )
        images.raise_for_status()
        assert images.json()
        scene_id = scenes.json()[0]["id"]
        old_revision = scenes.json()[0]["current_revision_id"]
        variant = await client.post(
            f"/api/backend/scenes/{scene_id}/generate-image/regenerate",
            json={"prompt": "Soft morning light in a Vietnamese storybook garden"},
        )
        variant.raise_for_status()
        await wait_for_job(client, variant.json()["job_id"])
        variants = await client.get(f"/api/backend/scenes/{scene_id}/images")
        variants.raise_for_status()
        assert len(variants.json()) >= 2
        approval = await client.post(
            f"/api/backend/scenes/{scene_id}/revisions/{variant.json()['scene_revision_id']}/approve",
            json={},
        )
        approval.raise_for_status()
        updated = await client.get(f"/api/backend/episodes/{episode_id}/scenes")
        updated.raise_for_status()
        assert (
            updated.json()[0]["current_revision_id"]
            == variant.json()["scene_revision_id"]
        )
        assert updated.json()[0]["current_revision_id"] != old_revision
        print(
            f"Live stack OK: job={job_id}, MP4={len(video.content)} bytes, variant approved"
        )


async def verify_autopilot(base_url: str, output_dir: Path | None = None) -> None:
    identity = uuid4().hex[:12]
    async with httpx.AsyncClient(base_url=base_url, timeout=40) as client:
        registration = await client.post(
            "/api/session/register",
            json={
                "email": f"autopilot-stack-{identity}@example.com",
                "password": "local-stack-test-password-123",
                "display_name": "Autopilot Stack Test",
                "workspace_name": f"Autopilot Stack {identity}",
                "workspace_slug": f"autopilot-stack-{identity}",
            },
        )
        registration.raise_for_status()
        project = await client.post(
            "/api/backend/projects", json={"title": "Science and nature verification"}
        )
        project.raise_for_status()
        project_id = project.json()["id"]
        enabled = await client.patch(
            f"/api/backend/projects/{project_id}/autopilot", json={"enabled": True}
        )
        enabled.raise_for_status()
        started = await client.post(f"/api/backend/projects/{project_id}/autopilot/run")
        started.raise_for_status()
        source_id = started.json()["source_id"]
        # The sourced script may require three Ollama attempts, each with a
        # 300-second request timeout, before the render job is queued.
        deadline = monotonic() + 960
        source = None
        while monotonic() < deadline:
            try:
                response = await client.get(
                    f"/api/backend/projects/{project_id}/autopilot/sources"
                )
            except httpx.RequestError:
                await asyncio.sleep(3)
                continue
            if response.status_code >= 500:
                await asyncio.sleep(3)
                continue
            response.raise_for_status()
            source = next(
                (row for row in response.json() if row["id"] == source_id), None
            )
            if source and source["job_id"]:
                break
            if source and source["status"] == "failed":
                raise RuntimeError(
                    f"Autopilot script failed: {source['error_message']}"
                )
            await asyncio.sleep(3)
        if not source or not source["job_id"]:
            raise TimeoutError("Autopilot did not queue a job within 960 seconds")
        assert source["source_url"].startswith(
            "https://science.nasa.gov/earth/earth-observatory/"
        )
        assert source["image_url"].startswith("https://assets.science.nasa.gov/")
        assert source["model_snapshot"]["story_backend"] == "ollama"
        job_id = source["job_id"]
        await wait_for_job(client, job_id, timeout_seconds=600)
        artifacts = await client.get(f"/api/backend/jobs/{job_id}/artifacts")
        artifacts.raise_for_status()
        manifest = artifacts.json()["manifest"]
        assert manifest["source_url"] == source["source_url"]
        assert manifest["fixture_only"] is False
        assert set(manifest["videos"]) == {"16x9", "9x16"}
        assert artifacts.json()["qc"]["blocking"] is True
        sizes: dict[str, int] = {}
        for preset, filename in [("9x16", "portrait"), ("16x9", "landscape")]:
            video = await client.get(
                f"/api/backend/assets/{manifest['videos'][preset]}/download",
                timeout=120,
            )
            video.raise_for_status()
            assert video.headers["content-type"].startswith("video/mp4")
            assert video.content[4:8] == b"ftyp"
            sizes[preset] = len(video.content)
            if output_dir is not None:
                output_dir.mkdir(parents=True, exist_ok=True)
                (output_dir / f"autopilot-{filename}.mp4").write_bytes(video.content)
        print(f"Autopilot OK: source={source['source_url']}, job={job_id}, MP4={sizes}")


async def wait_for_job(
    client: httpx.AsyncClient, job_id: str, timeout_seconds: int = 600
) -> None:
    deadline = monotonic() + timeout_seconds
    while monotonic() < deadline:
        try:
            detail = await client.get(f"/api/backend/jobs/{job_id}")
        except httpx.RequestError:
            await asyncio.sleep(3)
            continue
        if detail.status_code >= 500:
            await asyncio.sleep(3)
            continue
        detail.raise_for_status()
        state = detail.json()["status"]
        if state in {"completed", "failed", "cancelled"}:
            assert state == "completed", detail.json()
            return
        await asyncio.sleep(3)
    raise TimeoutError(f"Job {job_id} did not finish within {timeout_seconds} seconds")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:3000")
    parser.add_argument("--autopilot", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    asyncio.run(
        verify_autopilot(args.base_url, args.output_dir)
        if args.autopilot
        else main(args.base_url)
    )
