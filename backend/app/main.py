"""FastAPI app entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.claims import router as claims_router
from app.api.eval import router as eval_router
from app.api.members import router as members_router
from app.config import get_settings
from app.policy.loader import load_policy
from app.storage.db import close_engine, init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    load_policy()
    await init_db()
    yield
    await close_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Plum Claims Pipeline",
        version="0.1.0",
        description="Multi-agent health insurance claims processing pipeline.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(claims_router)
    app.include_router(members_router)
    app.include_router(eval_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "llm_provider": settings.llm_provider}

    @app.get("/")
    async def root() -> dict[str, str]:
        return {"service": "claims-pipeline", "version": "0.1.0"}

    return app


app = create_app()
