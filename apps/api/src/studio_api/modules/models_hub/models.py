from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from studio_api.core.db import Base, UUIDTimestampMixin


class AIModel(UUIDTimestampMixin, Base):
    __tablename__ = "ai_models"
    __table_args__ = (UniqueConstraint("provider", "checkpoint_hash"),)

    provider: Mapped[str] = mapped_column(String(64))
    model_family: Mapped[str] = mapped_column(String(120))
    variant: Mapped[str] = mapped_column(String(120))
    checkpoint_hash: Mapped[str] = mapped_column(String(128))
    license_id: Mapped[str] = mapped_column(String(120))
    approved: Mapped[bool] = mapped_column(Boolean, default=False)


class ModelDeployment(UUIDTimestampMixin, Base):
    __tablename__ = "model_deployments"
    __table_args__ = (UniqueConstraint("model_id", "alias"),)

    model_id: Mapped[UUID] = mapped_column(
        ForeignKey("ai_models.id", ondelete="CASCADE"), index=True
    )
    alias: Mapped[str] = mapped_column(String(32))
    adapter_id: Mapped[str] = mapped_column(String(120))
    approved_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
