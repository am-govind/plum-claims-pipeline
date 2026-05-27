"""Unit tests for the formal confidence formula."""

from __future__ import annotations

from datetime import date

from app.domain.claim import (
    ClaimCategory,
    ClaimInput,
    ClaimState,
    DocumentInput,
    DocumentType,
)
from app.domain.decision import AgentResult
from app.domain.services.confidence import compute_confidence


def _state(*, degraded: bool = False, with_all_agents: bool = True) -> ClaimState:
    inp = ClaimInput(
        member_id="EMP001",
        policy_id="PLUM_GHI_2024",
        claim_category=ClaimCategory.CONSULTATION,
        treatment_date=date(2024, 11, 1),
        claimed_amount=1500,
        documents=[
            DocumentInput(
                file_id="F1",
                actual_type=DocumentType.PRESCRIPTION,
                patient_name_on_doc="A",
            )
        ],
    )
    state = ClaimState(claim_id="T", input=inp)
    state.degraded = degraded
    if with_all_agents:
        for name in (
            "intake",
            "document_verification",
            "extraction",
            "policy_adjudication",
            "financial_calculation",
            "fraud_detection",
            "contradiction_detection",
        ):
            state.agent_results[name] = AgentResult(confidence=1.0)
    return state


def test_perfect_pipeline_yields_confidence_one():
    state = _state()
    out = compute_confidence(state)
    assert abs(out.final - 1.0) < 1e-6
    assert out.weighted_sum > 0.99


def test_degraded_pipeline_lowers_confidence_by_beta():
    s_clean = _state(degraded=False)
    s_deg = _state(degraded=True)
    out_clean = compute_confidence(s_clean)
    out_deg = compute_confidence(s_deg)
    assert out_clean.final - out_deg.final == out_deg.beta


def test_contradiction_score_penalty():
    state = _state()
    state.agent_results["contradiction_detection"] = AgentResult(
        confidence=0.5, contradiction_score=0.8
    )
    out = compute_confidence(state)
    assert out.contradiction_penalty > 0
    assert out.final < 1.0


def test_missing_agents_are_not_fatal():
    state = _state(with_all_agents=False)
    state.agent_results["extraction"] = AgentResult(confidence=1.0)
    out = compute_confidence(state)
    assert 0.0 <= out.final <= 1.0


def test_breakdown_is_serializable():
    state = _state()
    out = compute_confidence(state)
    b = out.to_breakdown()
    assert "final" in b and "per_component" in b and "weights" in b
