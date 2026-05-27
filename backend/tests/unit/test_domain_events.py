"""Unit tests for `ClaimState`'s event API and the immutability of events."""

from __future__ import annotations

import dataclasses
from datetime import date

import pytest

from app.domain.claim import (
    ClaimCategory,
    ClaimInput,
    ClaimState,
    DocumentInput,
    DocumentType,
)
from app.domain.events import ClaimApproved, ClaimRejected


def _state() -> ClaimState:
    inp = ClaimInput(
        member_id="EMP001",
        policy_id="PLUM_GHI_2024",
        claim_category=ClaimCategory.CONSULTATION,
        treatment_date=date(2024, 11, 1),
        claimed_amount=1500,
        documents=[
            DocumentInput(file_id="F1", actual_type=DocumentType.PRESCRIPTION)
        ],
    )
    return ClaimState(claim_id="T", input=inp)


def test_record_and_pull_round_trip() -> None:
    state = _state()
    state.record_event(
        ClaimApproved(claim_id="T", member_id="EMP001", approved_amount=1350.0, confidence=0.95)
    )
    state.record_event(ClaimRejected(claim_id="T", rejection_reasons=("X",), summary="why"))
    events = state.pull_events()
    assert [type(e).__name__ for e in events] == ["ClaimApproved", "ClaimRejected"]


def test_pull_events_is_idempotent_drain() -> None:
    state = _state()
    state.record_event(ClaimApproved(claim_id="T"))
    assert len(state.pull_events()) == 1
    assert state.pull_events() == []
    state.record_event(ClaimApproved(claim_id="T"))
    assert len(state.pull_events()) == 1


def test_events_are_immutable() -> None:
    event = ClaimApproved(claim_id="T", member_id="EMP001", approved_amount=1.0, confidence=1.0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        event.approved_amount = 2.0  # type: ignore[misc]


def test_pending_events_are_excluded_from_serialisation() -> None:
    state = _state()
    state.record_event(ClaimApproved(claim_id="T"))
    dumped = state.model_dump()
    assert "pending_events" not in dumped
