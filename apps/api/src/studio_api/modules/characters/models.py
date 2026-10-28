from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from studio_api.core.db import Base, UUIDTimestampMixin


class Character(UUIDTimestampMixin, Base):
    __tablename__ = "characters"
    __table_args__ = (UniqueConstraint("project_id", "name"),)

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    character_bible: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    voice_profile_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    approved_look: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    lora_model_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("model_deployments.id", ondelete="SET NULL"), nullable=True
    )
    consent_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)


class CharacterRevision(UUIDTimestampMixin, Base):
    __tablename__ = "character_revisions"
    __table_args__ = (UniqueConstraint("character_id", "version"),)

    character_id: Mapped[UUID] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    character_bible: Mapped[dict[str, Any]] = mapped_column(JSON)
    approved_look: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
