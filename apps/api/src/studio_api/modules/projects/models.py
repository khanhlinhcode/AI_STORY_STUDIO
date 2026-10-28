from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, Boolean, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from studio_api.core.db import Base, UUIDTimestampMixin


class ExecutionMode(StrEnum):
    AUTOMATION = "automation"
    STUDIO = "studio"


class Project(UUIDTimestampMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (Index("ix_projects_workspace_status", "workspace_id", "status"),)

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    locale: Mapped[str] = mapped_column(String(16), default="vi")
    audience: Mapped[str] = mapped_column(String(80), default="children-6-10")
    style_profile: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(24), default="active")
    version: Mapped[int] = mapped_column(Integer, default=1)
    autopilot_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class Episode(UUIDTimestampMixin, Base):
    __tablename__ = "episodes"
    __table_args__ = (Index("ix_episodes_project_status", "project_id", "status"),)

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    topic: Mapped[str] = mapped_column(String(500), default="")
    duration_goal_ms: Mapped[int] = mapped_column(Integer, default=60000)
    aspect_ratio: Mapped[str] = mapped_column(String(8), default="9:16")
    status: Mapped[str] = mapped_column(String(32), default="draft")
    execution_mode: Mapped[str] = mapped_column(String(16), default=ExecutionMode.AUTOMATION.value)
    revision: Mapped[int] = mapped_column(Integer, default=1)

    project: Mapped[Project] = relationship()
