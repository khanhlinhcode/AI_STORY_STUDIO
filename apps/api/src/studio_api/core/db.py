from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable
from datetime import UTC, datetime
from typing import TypeVar
from uuid import UUID, uuid4

from sqlalchemy import DateTime, MetaData
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from studio_api.core.config import get_settings

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UUIDTimestampMixin:
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


def build_engine(url: str | None = None) -> AsyncEngine:
    database_url = url or get_settings().database_url
    return create_async_engine(database_url, pool_pre_ping=True)


engine = build_engine()
SessionFactory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

ResultT = TypeVar("ResultT")


def run_worker_coroutine(awaitable: Awaitable[ResultT]) -> ResultT:
    """Close pooled async connections before Celery closes this task's event loop."""

    async def execute() -> ResultT:
        try:
            return await awaitable
        finally:
            await engine.dispose()

    return asyncio.run(execute())


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        yield session


async def create_schema(target_engine: AsyncEngine | None = None) -> None:
    selected = target_engine or engine
    import studio_api.models  # noqa: F401

    async with selected.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
