from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import JSON, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from studio_api.core.db import Base, UUIDTimestampMixin


class EvalRun(UUIDTimestampMixin, Base):
    __tablename__ = "eval_runs"

    job_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("production_jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    model_ref: Mapped[str] = mapped_column(String(255), default="")
    dataset_ref: Mapped[str] = mapped_column(String(255), default="")
    score: Mapped[float] = mapped_column(Float, default=0)
    passed: Mapped[bool] = mapped_column(default=False)
    report: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ReviewTask(UUIDTimestampMixin, Base):
    __tablename__ = "review_tasks"

    episode_id: Mapped[UUID] = mapped_column(
        ForeignKey("episodes.id", ondelete="CASCADE"), index=True
    )
    reviewer_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    episode_revision: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), default="pending")


class ReviewDecision(UUIDTimestampMixin, Base):
    __tablename__ = "review_decisions"

    task_id: Mapped[UUID] = mapped_column(
        ForeignKey("review_tasks.id", ondelete="CASCADE"), unique=True
    )
    reviewer_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    verdict: Mapped[str] = mapped_column(String(16))
    notes: Mapped[str] = mapped_column(Text, default="")
    rubric_scores: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
