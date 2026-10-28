"""End-to-end local fixture render without Redis, models, or a public server.

Run with DATABASE_URL=sqlite+aiosqlite:///./local-data/smoke.db and PYTHONPATH=.
This script creates a disposable local test database and outputs a preview manifest.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import UUID

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from studio_api.core.db import SessionFactory, create_schema
from studio_api.main import app
from studio_api.modules.assets.models import Asset
from studio_api.modules.assets.service import read_asset
from studio_api.modules.workflows.models import JobStep, ProductionJob
from workers.cpu_render.pipeline import run_job_async


async def main() -> None:
    Path("local-data").mkdir(exist_ok=True)
    await create_schema()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://local"
    ) as client:
        register = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "smoke@example.com",
                "password": "smoke-test-password-123",
                "display_name": "Smoke Test",
                "workspace_name": "Smoke Studio",
                "workspace_slug": "smoke-studio",
            },
        )
        if register.status_code == 409:
            register = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": "smoke@example.com",
                    "password": "smoke-test-password-123",
                },
            )
        register.raise_for_status()
        auth = register.json()
        headers = {
            "Authorization": f"Bearer {auth['access_token']}",
            "X-Workspace-ID": auth["workspace_id"],
        }
        project = await client.post(
            "/api/v1/projects", headers=headers, json={"title": "Smoke stories"}
        )
        project.raise_for_status()
        episode = await client.post(
            f"/api/v1/projects/{project.json()['id']}/episodes",
            headers=headers,
            json={"title": "Smoke preview", "execution_mode": "automation"},
        )
        episode.raise_for_status()
        episode_id = episode.json()["id"]
        script = await client.post(
            f"/api/v1/episodes/{episode_id}/script/generate",
            headers=headers,
            json={"topic": "chiếc lá biết hát"},
        )
        script.raise_for_status()
        job_response = await client.post(
            f"/api/v1/episodes/{episode_id}/production/start", headers=headers, json={}
        )
        job_response.raise_for_status()
        job_id = UUID(job_response.json()["id"])
    async with SessionFactory() as db:
        job = await db.get_one(ProductionJob, job_id)
        job.status = "claimed"
        await db.commit()
    await run_job_async(job_id)
    async with SessionFactory() as db:
        job = await db.get_one(ProductionJob, job_id)
        video = await db.scalar(
            select(JobStep).where(JobStep.job_id == job_id, JobStep.kind == "video")
        )
        manifest_asset = await db.get_one(Asset, video.output_manifest_id)
        manifest = (await read_asset(manifest_asset)).decode()
        print(f"job={job.id} status={job.status}")
        print(manifest)


if __name__ == "__main__":
    asyncio.run(main())
