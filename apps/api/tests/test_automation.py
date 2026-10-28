from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_automation_batch_idempotency_and_internal_auth(
    client: AsyncClient, owner: dict[str, str]
) -> None:
    project = await client.post(
        "/api/v1/projects", headers=owner, json={"title": "Automation stories"}
    )
    assert project.status_code == 201, project.text
    payload = {
        "project_id": project.json()["id"],
        "topics": ["Lá hát", "Sao nhỏ", "Mèo ngủ"],
    }
    no_key = await client.post("/webhooks/batch", json=payload)
    assert no_key.status_code == 401
    first = await client.post("/api/v1/automation/batch", headers=owner, json=payload)
    second = await client.post("/api/v1/automation/batch", headers=owner, json=payload)
    assert first.status_code == second.status_code == 202
    assert len(first.json()["job_ids"]) == 3
    assert first.json()["job_ids"] == second.json()["job_ids"]
    internal = {"Authorization": "Bearer development-internal-key"}
    status = await client.get(
        f"/webhooks/batches/{first.json()['batch_id']}/status", headers=internal
    )
    assert status.status_code == 200
    assert status.json()["pending"] == 3
    job_status = await client.get(f"/webhooks/jobs/{first.json()['job_ids'][0]}", headers=internal)
    assert job_status.json()["status"] == "queued"
    jobs = await client.get("/webhooks/jobs?status=queued&since=15", headers=internal)
    assert jobs.status_code == 200
    assert len(jobs.json()) == 3
    cancelled = await client.post(
        f"/api/v1/automation/batches/{first.json()['batch_id']}/cancel",
        headers=owner,
    )
    assert cancelled.status_code == 204, cancelled.text
    shared = await client.get(f"/webhooks/jobs/{first.json()['job_ids'][0]}", headers=internal)
    assert shared.json()["status"] == "queued"
