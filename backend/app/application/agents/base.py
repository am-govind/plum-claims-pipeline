"""Base class shared by all agents."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.application.recorder import TraceRecorder
from app.domain.claim import ClaimState


class BaseAgent(ABC):
    """All agents take a ClaimState and return the (mutated) ClaimState."""

    name: str = "base"
    is_critical: bool = False
    """If False, the orchestrator may continue when this agent fails (TC011)."""

    @abstractmethod
    async def run(self, state: ClaimState) -> ClaimState: ...

    @staticmethod
    def recorder(state: ClaimState) -> TraceRecorder:
        return TraceRecorder(state)
