from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import JSON, Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from studio_api.core.db import Base, UUIDTimestampMixin


class ScriptRevision(UUIDTimestampMixin, Base):
    __tablename__ = "script_revisions"

    episode_id: Mapped[UUID] = mapped_column(
        ForeignKey("episodes.id", ondelete="CASCADE"), index=True
    )
    structured_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    schema_version: Mapped[str] = mapped_column(String(16), default="1.0")
    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("script_revisions.id", ondelete="SET NULL"), nullable=True
    )
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False)
