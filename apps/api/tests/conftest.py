from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["ENVIRONMENT"] = "test"
os.environ["AI_ADAPTER_MODE"] = "fake"
os.environ["REDIS_URL"] = "redis://127.0.0.1:1/0"
os.environ["JWT_SECRET"] = "test-secret-with-at-least-thirty-two-characters"

from studio_api.core.db import Base, engine  # noqa: E402
from studio_api.main import app  # noqa: E402


@pytest_asyncio.fixture(autouse=True)
async def database() -> AsyncIterator[None]:
    import studio_api.models  # noqa: F401

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as test_client:
        yield test_client


@pytest_asyncio.fixture
async def owner(client: AsyncClient) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "owner@example.com",
            "password": "correct-horse-battery-staple",
            "display_name": "Owner",
            "workspace_name": "Story Lab",
            "workspace_slug": "story-lab",
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    return {
        "authorization": f"Bearer {payload['access_token']}",
        "x-workspace-id": payload["workspace_id"],
    }
