from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from studio_api.core.db import Base, UUIDTimestampMixin


class ProductionJob(UUIDTimestampMixin, Base):
    __tablename__ = "production_jobs"
    __table_args__ = (
        UniqueConstraint("workspace_id", "idempotency_key"),
        Index("ix_jobs_status_priority_created", "status", "priority", "created_at"),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    episode_id: Mapped[UUID] = mapped_column(
        ForeignKey("episodes.id", ondelete="CASCADE"), index=True
    )
    requested_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), default="draft")
    priority: Mapped[int] = mapped_column(Integer, default=0)
    execution_mode: Mapped[str] = mapped_column(String(16), default="automation")
    job_kind: Mapped[str] = mapped_column(String(24), default="episode")
    idempotency_key: Mapped[str] = mapped_column(String(128))
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot_revision: Mapped[int] = mapped_column(Integer, default=1)


class JobStep(UUIDTimestampMixin, Base):
    __tablename__ = "job_steps"
    __table_args__ = (
        UniqueConstraint("job_id", "scene_revision_id", "kind"),
        Index("ix_job_steps_job_status", "job_id", "status"),
    )

    job_id: Mapped[UUID] = mapped_column(
        ForeignKey("production_jobs.id", ondelete="CASCADE"), index=True
    )
    scene_revision_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("scene_revisions.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(24))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(24), default="pending")
    output_manifest_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("assets.id", ondelete="SET NULL"), nullable=True
    )
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)


class OutboxEvent(UUIDTimestampMixin, Base):
    __tablename__ = "outbox_events"
    __table_args__ = (Index("ix_outbox_status_created", "status", "created_at"),)

    event_type: Mapped[str] = mapped_column(String(120))
    aggregate_id: Mapped[UUID] = mapped_column(index=True)
    schema_version: Mapped[str] = mapped_column(String(16), default="1.0")
    message_id: Mapped[str] = mapped_column(String(64), unique=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)


class AuditEvent(UUIDTimestampMixin, Base):
    __tablename__ = "audit_events"

    workspace_id: Mapped[UUID | None] = mapped_column(index=True, nullable=True)
    actor_id: Mapped[UUID | None] = mapped_column(nullable=True)
    action: Mapped[str] = mapped_column(String(120))
    subject_type: Mapped[str] = mapped_column(String(64))
    subject_id: Mapped[UUID] = mapped_column(index=True)
    before_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    after_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class AutomationBatch(UUIDTimestampMixin, Base):
    __tablename__ = "automation_batches"

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(24), default="pending")
    topics: Mapped[list[str]] = mapped_column(JSON)
    job_ids: Mapped[list[str]] = mapped_column(JSON, default=list)


class SourceStory(UUIDTimestampMixin, Base):
    __tablename__ = "source_stories"
    __table_args__ = (
        UniqueConstraint("project_id", "source_hash", name="uq_source_stories_project_source"),
    )

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    episode_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("episodes.id", ondelete="SET NULL"), nullable=True
    )
    job_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("production_jobs.id", ondelete="SET NULL"), nullable=True
    )
    source_hash: Mapped[str] = mapped_column(String(64))
    source_url: Mapped[str] = mapped_column(String(1000))
    image_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    feed_url: Mapped[str] = mapped_column(String(1000))
    title: Mapped[str] = mapped_column(String(300))
    summary: Mapped[str] = mapped_column(Text)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), default="selected")
    model_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
