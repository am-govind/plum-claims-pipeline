"""Domain events: immutable facts about what happened to a claim.

Each event is a frozen dataclass — once raised it cannot be edited,
because facts about the past don't change. Events are raised by the
aggregate (`ClaimState`) inside the methods that mutate it, then
drained by the application layer after persistence and dispatched to
handlers via the `EventBus` port.

Naming convention: past-tense verb phrases (``ClaimApproved``,
``ManualReviewRequired``). Each event carries only what a downstream
handler genuinely needs — not the whole state — so the contract stays
narrow and the events serialise cheaply.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class DomainEvent:
    """Base type: every event carries the aggregate id and a timestamp."""

    claim_id: str
    occurred_at: datetime = field(default_factory=_now)


@dataclass(frozen=True)
class ClaimApproved(DomainEvent):
    member_id: str = ""
    approved_amount: float = 0.0
    confidence: float = 0.0


@dataclass(frozen=True)
class ClaimPartiallyApproved(DomainEvent):
    member_id: str = ""
    approved_amount: float = 0.0
    rejected_line_items: tuple[str, ...] = ()


@dataclass(frozen=True)
class ClaimRejected(DomainEvent):
    rejection_reasons: tuple[str, ...] = ()
    summary: str = ""


@dataclass(frozen=True)
class ManualReviewRequired(DomainEvent):
    """One event for every non-decision routing path that needs a human.

    The ``reason`` field discriminates between MANUAL_REVIEW,
    FRAUD_INVESTIGATION, ESCALATED_MEDICAL_REVIEW, NEEDS_CLARIFICATION,
    and the degraded-component fallback.
    """

    reason: str = ""
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ClaimHaltedEarly(DomainEvent):
    reason: str = ""
    user_message: str = ""


@dataclass(frozen=True)
class ComponentDegraded(DomainEvent):
    component: str = ""
    error: str = ""


@dataclass(frozen=True)
class FraudSignalsRaised(DomainEvent):
    signals: tuple[str, ...] = ()
