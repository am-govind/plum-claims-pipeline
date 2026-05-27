"""SQLAlchemy declarative base.

The actual engine + session lifecycle lives in
`app.infrastructure.persistence.database.Database`.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
