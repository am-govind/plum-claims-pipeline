"""Compact projection of a stored claim used by the list endpoint.

Keeping this in `domain/claim/` (and returned from the repository port)
means the application and interface layers never depend on the SQLAlchemy
ORM type. The persistence adapter is the only thing that knows how to
turn a `ClaimRecord` row into a `ClaimSummary`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ClaimSummary:
    claim_id: str
    member_id: str
    policy_id: str
    category: str
    status: str
    submitted_amount: float
    approved_amount: float
    confidence: float
    created_at: datetime
