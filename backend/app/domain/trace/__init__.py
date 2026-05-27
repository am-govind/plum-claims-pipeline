"""Structured trace records.

Every node appends a TraceStep so reviewers can reconstruct exactly what
happened: what was checked, what passed, what failed, and how that affected
the final decision.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TraceStatus(str, Enum):
    OK = "OK"
    WARNING = "WARNING"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED"
    EARLY_STOP = "EARLY_STOP"


class TraceStep(BaseModel):
    """A single observable step in the pipeline.

    `evidence` is structured data that explains the step's output (e.g. which
    rule triggered, which line items were filtered). The frontend renders this
    inline under each step so reviewers can audit decisions field by field.
    """

    step: str
    status: TraceStatus
    summary: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    confidence_delta: float = 0.0
    latency_ms: int = 0
    error: str | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
