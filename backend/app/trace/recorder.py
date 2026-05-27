"""Tiny helper that builds and appends TraceStep records.

Keeping it on its own object means the agents stay focused on their
domain logic and don't sprinkle trace bookkeeping all over.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, Iterator

from app.models.claim import ClaimState
from app.models.trace import TraceStatus, TraceStep


class TraceRecorder:
    def __init__(self, state: ClaimState) -> None:
        self.state = state

    def record(
        self,
        step: str,
        *,
        status: TraceStatus,
        summary: str,
        evidence: dict[str, Any] | None = None,
        confidence_delta: float = 0.0,
        latency_ms: int = 0,
        error: str | None = None,
    ) -> TraceStep:
        ts = TraceStep(
            step=step,
            status=status,
            summary=summary,
            evidence=evidence or {},
            confidence_delta=confidence_delta,
            latency_ms=latency_ms,
            error=error,
        )
        self.state.trace.append(ts)
        self.state.confidence = max(0.0, min(1.0, self.state.confidence + confidence_delta))
        return ts

    @contextmanager
    def time_step(self, step: str) -> Iterator[dict[str, Any]]:
        """Context manager that captures elapsed ms and lets the agent
        finalise the step record from inside the block."""
        ctx: dict[str, Any] = {"latency_ms": 0}
        start = time.perf_counter()
        try:
            yield ctx
        finally:
            ctx["latency_ms"] = int((time.perf_counter() - start) * 1000)
