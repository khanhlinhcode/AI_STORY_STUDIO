from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import JSON, Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from studio_api.core.db import Base, UUIDTimestampMixin


class Scene(UUIDTimestampMixin, Base):
    __tablename__ = "scenes"
    __table_args__ = (Index("ix_scenes_episode_order", "episode_id", "order_index"),)

    episode_id: Mapped[UUID] = mapped_column(
        ForeignKey("episodes.id", ondelete="CASCADE"), index=True
    )
    order_index: Mapped[int] = mapped_column(Integer)
    synopsis: Mapped[str] = mapped_column(Text, default="")
    duration_ms: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    current_revision_id: Mapped[UUID | None] = mapped_column(nullable=True)


class SceneRevision(UUIDTimestampMixin, Base):
    __tablename__ = "scene_revisions"

    scene_id: Mapped[UUID] = mapped_column(ForeignKey("scenes.id", ondelete="CASCADE"), index=True)
    script_revision_id: Mapped[UUID] = mapped_column(
        ForeignKey("script_revisions.id", ondelete="RESTRICT"), index=True
    )
    prompt: Mapped[str] = mapped_column(Text)
    negative_prompt: Mapped[str] = mapped_column(Text, default="")
    camera: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    image_desc: Mapped[str] = mapped_column(Text)
    narration: Mapped[str] = mapped_column(Text)
    seed: Mapped[int] = mapped_column(Integer, default=42)
    approval_state: Mapped[str] = mapped_column(String(24), default="pending")
    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("scene_revisions.id", ondelete="SET NULL"), nullable=True
    )
