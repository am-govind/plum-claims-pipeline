"""SQLAlchemy async setup. SQLite for the demo; Postgres just by changing
the URL — the repository layer doesn't change."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    pass


_engine = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def _get_engine():
    global _engine
    if _engine is None:
        s = get_settings()
        _engine = create_async_engine(s.database_url, echo=False, future=True)
    return _engine


def _get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(_get_engine(), expire_on_commit=False)
    return _sessionmaker


async def init_db() -> None:
    from app.storage import models as _models  # noqa: F401  (register tables)

    async with _get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_engine() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _sessionmaker = None


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    sm = _get_sessionmaker()
    async with sm() as session:
        yield session
