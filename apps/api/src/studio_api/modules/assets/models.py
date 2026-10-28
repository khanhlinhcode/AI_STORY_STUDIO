from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import JSON, BigInteger, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from studio_api.core.db import Base, UUIDTimestampMixin


class Asset(UUIDTimestampMixin, Base):
    __tablename__ = "assets"
    __table_args__ = (UniqueConstraint("workspace_id", "sha256"),)

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    mime_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    storage_key: Mapped[str] = mapped_column(String(1024), unique=True)
    rights_declaration: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class AssetDependency(UUIDTimestampMixin, Base):
    __tablename__ = "asset_dependencies"
    __table_args__ = (UniqueConstraint("output_asset_id", "input_asset_id", "dependency_type"),)

    output_asset_id: Mapped[UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), index=True
    )
    input_asset_id: Mapped[UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), index=True
    )
    dependency_type: Mapped[str] = mapped_column(String(64))
    transform_run_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
