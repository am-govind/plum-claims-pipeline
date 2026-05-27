"""Domain events package — typed, immutable facts raised by aggregates."""

from app.domain.events.claim_events import (
    ClaimApproved,
    ClaimHaltedEarly,
    ClaimPartiallyApproved,
    ClaimRejected,
    ComponentDegraded,
    DomainEvent,
    FraudSignalsRaised,
    ManualReviewRequired,
)

__all__ = [
    "ClaimApproved",
    "ClaimHaltedEarly",
    "ClaimPartiallyApproved",
    "ClaimRejected",
    "ComponentDegraded",
    "DomainEvent",
    "FraudSignalsRaised",
    "ManualReviewRequired",
]
