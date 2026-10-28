from __future__ import annotations

from uuid import UUID

import pytest
from httpx import AsyncClient

from studio_api.core.db import SessionFactory
from studio_api.core.errors import StudioError
from studio_api.core.network import validate_public_url
from studio_api.core.security import hash_password
from studio_api.modules.identity.models import Membership, User


@pytest.mark.asyncio
async def test_cross_workspace_project_is_hidden(
    client: AsyncClient, owner: dict[str, str]
) -> None:
    created = await client.post("/api/v1/projects", headers=owner, json={"title": "Secret series"})
    assert created.status_code == 201, created.text
    project_id = created.json()["id"]

    other = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "other@example.com",
            "password": "another-correct-password",
            "display_name": "Other",
            "workspace_name": "Other Lab",
            "workspace_slug": "other-lab",
        },
    )
    other_headers = {"authorization": f"Bearer {other.json()['access_token']}"}
    denied = await client.get(f"/api/v1/projects/{project_id}", headers=other_headers)
    assert denied.status_code == 404


@pytest.mark.asyncio
async def test_viewer_cannot_create_project(client: AsyncClient, owner: dict[str, str]) -> None:
    async with SessionFactory() as db:
        viewer = User(
            email="viewer@example.com",
            display_name="Viewer",
            hashed_password=hash_password("viewer-password-long"),
        )
        db.add(viewer)
        await db.flush()
        db.add(
            Membership(
                user_id=viewer.id,
                workspace_id=UUID(owner["x-workspace-id"]),
                role="viewer",
            )
        )
        await db.commit()
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "viewer@example.com", "password": "viewer-password-long"},
    )
    headers = {
        "authorization": f"Bearer {login.json()['access_token']}",
        "x-workspace-id": owner["x-workspace-id"],
    }
    denied = await client.post("/api/v1/projects", headers=headers, json={"title": "Nope"})
    assert denied.status_code == 403


def test_ssrf_rejects_loopback() -> None:
    with pytest.raises(StudioError):
        validate_public_url("http://127.0.0.1:8080/internal")
