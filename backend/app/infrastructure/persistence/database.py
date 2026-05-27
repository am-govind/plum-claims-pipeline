"""SQLAlchemy async engine + sessionmaker wrapped in a `Database` object.

Why a class instead of module globals: the engine is the canonical
example of a long-lived, owned resource — it has a clear lifecycle
(``init`` / ``close``) and we want exactly one per process. Wrapping it
keeps that lifecycle explicit, makes it easy to swap in a test database,
and removes the hidden global state that the old `db.py` carried.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.infrastructure.persistence.db import Base


class Database:
    """Holds the async engine + sessionmaker for one application."""

    def __init__(self, url: str) -> None:
        self.url = url
        self._engine: AsyncEngine | None = None
        self._sessionmaker: async_sessionmaker[AsyncSession] | None = None

    async def init(self) -> None:
        """Create the engine and ensure all tables exist."""
        if self._engine is None:
            self._engine = create_async_engine(self.url, echo=False, future=True)
            self._sessionmaker = async_sessionmaker(
                self._engine, expire_on_commit=False
            )
        from app.infrastructure.persistence import orm as _orm  # noqa: F401  (register tables)

        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._sessionmaker = None

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        if self._sessionmaker is None:
            raise RuntimeError("Database not initialised — call .init() first")
        async with self._sessionmaker() as session:
            yield session
