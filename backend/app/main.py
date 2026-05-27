"""Backwards-compatible entrypoint.

Preserves the ``uvicorn app.main:app`` import path (used by the Dockerfile,
docker-compose, and the local-dev README commands). The real FastAPI app
construction lives in :mod:`app.interfaces.http.app`.
"""

from app.interfaces.http.app import app, create_app

__all__ = ["app", "create_app"]
