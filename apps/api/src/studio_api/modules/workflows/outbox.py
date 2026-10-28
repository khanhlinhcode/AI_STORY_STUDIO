from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from studio_api.modules.workflows.models import OutboxEvent


def message_id(event_type: str, aggregate_id: UUID, version: int | str) -> str:
    source = f"{event_type}:{aggregate_id}:{version}".encode()
    return hashlib.sha256(source).hexdigest()


def add_event(
    db: AsyncSession,
    *,
    event_type: str,
    aggregate_id: UUID,
    version: int | str,
    payload: dict[str, Any],
) -> OutboxEvent:
    event = OutboxEvent(
        event_type=event_type,
        aggregate_id=aggregate_id,
        schema_version="1.0",
        message_id=message_id(event_type, aggregate_id, version),
        payload=json.loads(json.dumps(payload, default=str)),
        status="pending",
    )
    db.add(event)
    return event
