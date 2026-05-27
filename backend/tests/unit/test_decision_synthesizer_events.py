"""Test that the synthesizer maps each Decision branch to the right event.

The branch-selection logic is already covered by the eval suite; this
file pins down the mapping from `DecisionStatus` to `DomainEvent` so a
future refactor of the synthesizer cannot silently change the contract.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.application.agents.decision_synthesizer import _event_for_decision
from app.domain.claim import (
    ClaimCategory,
    ClaimInput,
    ClaimState,
    DocumentInput,
    DocumentType,
)
from app.domain.decision import (
    Decision,
    DecisionStatus,
    LineItemDecision,
    RejectionReason,
)
from app.domain.events import (
    ClaimApproved,
    ClaimPartiallyApproved,
    ClaimRejected,
    ManualReviewRequired,
)


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
    return ClaimState(claim_id="CLM_TEST", input=inp)


def test_approved_maps_to_claim_approved() -> None:
    state = _state()
    state.decision = Decision(
        status=DecisionStatus.APPROVED,
        approved_amount=1350.0,
        submitted_amount=1500.0,
        confidence=0.95,
        summary="Approved",
        user_message="ok",
    )
    event = _event_for_decision(state)
    assert isinstance(event, ClaimApproved)
    assert event.claim_id == "CLM_TEST"
    assert event.member_id == "EMP001"
    assert event.approved_amount == 1350.0
    assert event.confidence == 0.95


def test_partial_maps_to_claim_partially_approved_with_rejected_items() -> None:
    state = _state()
    state.line_decisions = [
        LineItemDecision(
            description="Root Canal",
            submitted_amount=8000,
            approved_amount=8000,
            status=DecisionStatus.APPROVED,
        ),
        LineItemDecision(
            description="Teeth Whitening",
            submitted_amount=4000,
            approved_amount=0,
            status=DecisionStatus.REJECTED,
            reason="Cosmetic exclusion",
        ),
    ]
    state.decision = Decision(
        status=DecisionStatus.PARTIAL,
        approved_amount=8000.0,
        submitted_amount=12000.0,
        confidence=0.9,
        summary="Partial",
        user_message="ok",
        line_items=state.line_decisions,
    )
    event = _event_for_decision(state)
    assert isinstance(event, ClaimPartiallyApproved)
    assert event.rejected_line_items == ("Teeth Whitening",)
    assert event.approved_amount == 8000.0


def test_rejected_maps_to_claim_rejected() -> None:
    state = _state()
    state.decision = Decision(
        status=DecisionStatus.REJECTED,
        approved_amount=0.0,
        submitted_amount=1500.0,
        rejection_reasons=[RejectionReason.WAITING_PERIOD],
        confidence=0.9,
        summary="Within waiting period",
        user_message="ok",
    )
    event = _event_for_decision(state)
    assert isinstance(event, ClaimRejected)
    assert event.rejection_reasons == ("WAITING_PERIOD",)
    assert event.summary == "Within waiting period"


@pytest.mark.parametrize(
    "status",
    [
        DecisionStatus.MANUAL_REVIEW,
        DecisionStatus.FRAUD_INVESTIGATION,
        DecisionStatus.ESCALATED_MEDICAL_REVIEW,
        DecisionStatus.NEEDS_CLARIFICATION,
    ],
)
def test_manual_review_branches_all_map_to_manual_review_required(
    status: DecisionStatus,
) -> None:
    state = _state()
    state.decision = Decision(
        status=status,
        approved_amount=0.0,
        submitted_amount=1500.0,
        confidence=0.5,
        summary=status.value,
        user_message="ok",
        notes=["something to look at"],
    )
    event = _event_for_decision(state)
    assert isinstance(event, ManualReviewRequired)
    assert event.reason == status.value
    assert event.notes == ("something to look at",)
