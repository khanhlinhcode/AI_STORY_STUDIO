from __future__ import annotations

import asyncio
from typing import Any

import redis.asyncio as redis
from sqlalchemy import text

from studio_api.core.config import get_settings
from studio_api.core.db import SessionFactory
from studio_api.modules.models.adapters.registry import get_adapter_registry
from studio_api.modules.models.adapters.types import BaseAdapter


async def service_health() -> dict[str, Any]:
    database = "down"
    cache = "down"
    try:
        async with SessionFactory() as session:
            await asyncio.wait_for(session.execute(text("SELECT 1")), timeout=2)
        database = "ok"
    except Exception:
        database = "down"
    client = redis.from_url(get_settings().redis_url)
    try:
        await asyncio.wait_for(client.ping(), timeout=2)
        cache = "ok"
    except Exception:
        cache = "down"
    finally:
        await client.aclose()
    registry = get_adapter_registry()
    selected: list[BaseAdapter] = [
        registry.get_story_adapter(),
        registry.get_image_adapter(),
        registry.get_tts_adapter(),
    ]

    async def check(adapter: BaseAdapter) -> tuple[str, bool]:
        try:
            report = await asyncio.wait_for(adapter.probe(), timeout=2)
            return report.backend_id, report.available
        except Exception:
            return adapter.backend_id, False

    services = dict(await asyncio.gather(*(check(adapter) for adapter in selected)))
    return {
        "status": "ok" if database == "ok" else "degraded",
        "db": database,
        "redis": cache,
        "ai_services": services,
    }
