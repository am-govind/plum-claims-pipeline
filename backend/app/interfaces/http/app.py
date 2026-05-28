"""FastAPI app entrypoint.

Wires the `Container` (built in the composition root) into FastAPI:

- on startup, build the container and open its database
- on shutdown, close the database
- every router pulls its collaborators from the container via
  `Depends()` providers in `deps.py`, so no router reaches across
  layers for module-level state.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.composition import compose
from app.config import Settings
from app.interfaces.http.routers.claims import router as claims_router
from app.interfaces.http.routers.eval import router as eval_router
from app.interfaces.http.routers.extraction import router as extraction_router
from app.interfaces.http.routers.members import router as members_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    container = compose(Settings())
    app.state.container = container
    await container.database.init()
    try:
        yield
    finally:
        await container.database.close()


def create_app() -> FastAPI:
    settings = Settings()
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
    app.include_router(extraction_router)
    app.include_router(members_router)
    app.include_router(eval_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        provider = app.state.container.settings.llm_provider
        return {"status": "ok", "llm_provider": provider}

    @app.get("/")
    async def root() -> dict[str, str]:
        return {"service": "claims-pipeline", "version": "0.1.0"}

    return app


app = create_app()
