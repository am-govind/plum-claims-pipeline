"""FastAPI `Depends()` providers that hand out collaborators from the
container attached to ``app.state``.

Each provider returns a port (`ClaimRepository`, `PolicyRepository`,
…) rather than a concrete adapter — routers stay decoupled from any
particular persistence or LLM implementation.
"""

from __future__ import annotations

from fastapi import Request

from app.application.pipeline import CompiledPipeline
from app.application.ports.claim_repository import ClaimRepository
from app.application.ports.event_bus import EventBus
from app.application.ports.policy_repository import PolicyRepository
from app.composition import Container


def get_container(request: Request) -> Container:
    return request.app.state.container


def get_claim_repository(request: Request) -> ClaimRepository:
    return get_container(request).claim_repository


def get_policy_repository(request: Request) -> PolicyRepository:
    return get_container(request).policy_repository


def get_pipeline(request: Request) -> CompiledPipeline:
    return get_container(request).pipeline


def get_event_bus(request: Request) -> EventBus:
    return get_container(request).event_bus
