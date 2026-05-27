"""Unit tests for deliberation routing helpers."""

from __future__ import annotations

from datetime import date

from app.graph.pipeline import (
    POLICY_RECONSIDER_CAP,
    RE_EXTRACTION_CAP,
    _needs_policy_reconsider,
    _needs_re_extraction,
)
from app.models.claim import (
    ClaimCategory,
    ClaimInput,
    ClaimState,
    DocumentInput,
    DocumentType,
    ExtractedDocument,
)
from app.models.decision import PolicyFinding


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


def test_re_extraction_triggers_on_low_confidence():
    state = _state()
    state.extracted = [
        ExtractedDocument(
            file_id="F1",
            document_type=DocumentType.PRESCRIPTION,
            extraction_confidence=0.5,
        )
    ]
    assert _needs_re_extraction(state) is True


def test_re_extraction_does_not_trigger_on_high_confidence_and_no_issues():
    state = _state()
    state.extracted = [
        ExtractedDocument(
            file_id="F1",
            document_type=DocumentType.PRESCRIPTION,
            extraction_confidence=0.95,
        )
    ]
    assert _needs_re_extraction(state) is False


def test_re_extraction_caps_at_one_iteration():
    state = _state()
    state.extracted = [
        ExtractedDocument(
            file_id="F1",
            document_type=DocumentType.PRESCRIPTION,
            extraction_confidence=0.4,
        )
    ]
    state.deliberation_iterations["re_extraction"] = RE_EXTRACTION_CAP
    assert _needs_re_extraction(state) is False


def test_policy_reconsider_fires_on_fraud_with_clean_policy():
    state = _state()
    state.fraud_signals = ["Same-day claim count 3 exceeds limit 2"]
    state.findings = [
        PolicyFinding(code="COVERAGE_CHECK", passed=True, message="ok"),
    ]
    assert _needs_policy_reconsider(state) is True


def test_policy_reconsider_does_not_fire_when_policy_already_failed():
    state = _state()
    state.fraud_signals = ["x"]
    state.findings = [
        PolicyFinding(
            code="WAITING_PERIOD", passed=False, message="x", severity="REJECT"
        )
    ]
    assert _needs_policy_reconsider(state) is False


def test_policy_reconsider_caps_at_one():
    state = _state()
    state.fraud_signals = ["x"]
    state.findings = [PolicyFinding(code="OK", passed=True, message="ok")]
    state.deliberation_iterations["policy_reconsider"] = POLICY_RECONSIDER_CAP
    assert _needs_policy_reconsider(state) is False
