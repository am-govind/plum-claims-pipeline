"""End-to-end check that the right domain events fire for representative cases.

We subscribe a `RecordingHandler` to the live event bus on the
fixture-built `Container`, run a handful of `test_cases.json` cases
through the pipeline, and assert that the right event types fire with
the right ``claim_id``. The eval suite already verifies the decisions
themselves; this file just verifies the event side-channel.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.composition import Container
from app.config import Settings
from app.domain.events import (
    ClaimApproved,
    ClaimHaltedEarly,
    ClaimRejected,
    ComponentDegraded,
    DomainEvent,
    FraudSignalsRaised,
    ManualReviewRequired,
)
from eval.runner import _load_test_cases, run_case


class _RecordingHandler:
    def __init__(self) -> None:
        self.events: list[DomainEvent] = []

    async def handle(self, event: DomainEvent) -> None:
        self.events.append(event)


def _case(case_id: str) -> dict[str, Any]:
    for c in _load_test_cases(Settings().test_cases_path):
        if c["case_id"] == case_id:
            return c
    raise KeyError(case_id)


def _types(events: list[DomainEvent]) -> list[str]:
    return [e.__class__.__name__ for e in events]


@pytest.mark.asyncio
async def test_tc004_approved_fires_claim_approved(container: Container) -> None:
    sink = _RecordingHandler()
    container.event_bus.subscribe(sink)

    await run_case(_case("TC004"), container)

    types = _types(sink.events)
    assert "ClaimApproved" in types
    approved = next(e for e in sink.events if isinstance(e, ClaimApproved))
    assert approved.claim_id == "TC004"
    assert approved.approved_amount > 0


@pytest.mark.asyncio
async def test_tc005_waiting_period_fires_claim_rejected(container: Container) -> None:
    sink = _RecordingHandler()
    container.event_bus.subscribe(sink)

    await run_case(_case("TC005"), container)

    rejected = [e for e in sink.events if isinstance(e, ClaimRejected)]
    assert rejected, "TC005 should emit ClaimRejected"
    assert rejected[0].claim_id == "TC005"
    assert "WAITING_PERIOD" in rejected[0].rejection_reasons


@pytest.mark.asyncio
async def test_tc001_wrong_document_fires_claim_halted_early(
    container: Container,
) -> None:
    sink = _RecordingHandler()
    container.event_bus.subscribe(sink)

    await run_case(_case("TC001"), container)

    halted = [e for e in sink.events if isinstance(e, ClaimHaltedEarly)]
    assert halted, "TC001 should emit ClaimHaltedEarly"
    assert halted[0].claim_id == "TC001"
    assert halted[0].reason == "DOCUMENT_TYPE_MISMATCH"


@pytest.mark.asyncio
async def test_tc009_fraud_fires_signals_and_manual_review(
    container: Container,
) -> None:
    sink = _RecordingHandler()
    container.event_bus.subscribe(sink)

    await run_case(_case("TC009"), container)

    types = _types(sink.events)
    assert "FraudSignalsRaised" in types
    assert "ManualReviewRequired" in types
    fraud = next(e for e in sink.events if isinstance(e, FraudSignalsRaised))
    assert fraud.signals  # at least one signal


@pytest.mark.asyncio
async def test_tc011_component_failure_fires_component_degraded(
    container: Container,
) -> None:
    sink = _RecordingHandler()
    container.event_bus.subscribe(sink)

    await run_case(_case("TC011"), container)

    degraded = [e for e in sink.events if isinstance(e, ComponentDegraded)]
    assert degraded, "TC011 should emit ComponentDegraded"
    assert degraded[0].component == "fraud_detection"
    # TC011 still ends approved, so a ClaimApproved should also be present.
    assert any(isinstance(e, ClaimApproved) for e in sink.events)


@pytest.mark.asyncio
async def test_events_are_drained_after_publish(container: Container) -> None:
    """A handler should see events exactly once per claim, not twice."""
    sink = _RecordingHandler()
    container.event_bus.subscribe(sink)

    await run_case(_case("TC004"), container)
    first = len(sink.events)
    # Same case again with a fresh state -- handler count should grow but
    # the previous run's events should not be re-emitted.
    await run_case(_case("TC004"), container)
    second = len(sink.events)

    assert second > first
    # ClaimApproved expected exactly once per run.
    approved = [e for e in sink.events if isinstance(e, ClaimApproved)]
    assert len(approved) == 2


@pytest.mark.parametrize(
    "case_id, decision_event",
    [
        ("TC006", "ClaimPartiallyApproved"),
        ("TC012", "ClaimRejected"),
        ("TC009", "ManualReviewRequired"),
    ],
)
@pytest.mark.asyncio
async def test_decision_events_cover_remaining_branches(
    container: Container, case_id: str, decision_event: str
) -> None:
    sink = _RecordingHandler()
    container.event_bus.subscribe(sink)

    await run_case(_case(case_id), container)

    assert decision_event in _types(sink.events)
    # Manual-review used here so we know ManualReviewRequired isn't aliased.
    if decision_event == "ManualReviewRequired":
        assert isinstance(
            next(e for e in sink.events if isinstance(e, ManualReviewRequired)),
            ManualReviewRequired,
        )
