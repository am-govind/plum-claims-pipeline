"""Unit tests for the JSON rule engine.

Constructs `DslRuleEngine` explicitly with the rules + policy loaded via
the infrastructure adapters, exactly as production does in the
composition root.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.config import Settings
from app.domain.claim import (
    ClaimCategory,
    ClaimInput,
    ClaimState,
    DocumentInput,
    DocumentType,
    ExtractedDocument,
)
from app.domain.policy.rules import DslRuleEngine
from app.infrastructure.policy.json_policy_repository import JsonPolicyRepository
from app.infrastructure.policy.json_rules_loader import load_rules_data


@pytest.fixture(scope="module")
def rule_engine() -> DslRuleEngine:
    settings = Settings()
    policy = JsonPolicyRepository(settings.policy_terms_path).get_terms()
    rules_data = load_rules_data(settings.policy_rules_path)
    return DslRuleEngine(rules_data=rules_data, policy=policy)


def _state(*, category=ClaimCategory.CONSULTATION, diagnosis=None, member_id="EMP001"):
    inp = ClaimInput(
        member_id=member_id,
        policy_id="PLUM_GHI_2024",
        claim_category=category,
        treatment_date=date(2024, 11, 1),
        claimed_amount=1500,
        documents=[
            DocumentInput(
                file_id="F001",
                actual_type=DocumentType.PRESCRIPTION,
                patient_name_on_doc="Test Patient",
            )
        ],
    )
    state = ClaimState(claim_id="TEST", input=inp)
    if diagnosis:
        state.extracted = [
            ExtractedDocument(
                file_id="F001",
                document_type=DocumentType.PRESCRIPTION,
                diagnosis=diagnosis,
                patient_name="Test Patient",
            )
        ]
    return state


def test_engine_loads_rules_and_evaluates_clean_state(rule_engine: DslRuleEngine) -> None:
    state = _state(diagnosis="Common Cold")
    results = rule_engine.evaluate(state)
    assert results, "engine should produce at least one rule result"
    coverage = next(r for r in results if r.rule_id == "COVERAGE_CHECK")
    assert coverage.passed


def test_engine_fires_diabetes_waiting_period_for_recent_member(
    rule_engine: DslRuleEngine,
) -> None:
    state = _state(diagnosis="Type 2 Diabetes Mellitus", member_id="EMP005")
    results = rule_engine.evaluate(state)
    diabetes = next(
        (r for r in results if r.rule_id == "WAITING_PERIOD_DIABETES"), None
    )
    assert diabetes is not None
    assert diabetes.passed is False
    assert "diabetes" in diabetes.message.lower()
    assert "eligible" in diabetes.message.lower()


def test_engine_skips_obesity_when_diagnosis_is_unrelated(
    rule_engine: DslRuleEngine,
) -> None:
    state = _state(diagnosis="Common cold")
    results = rule_engine.evaluate(state)
    obesity = next(r for r in results if r.rule_id == "WAITING_PERIOD_OBESITY")
    assert obesity.passed is True


def test_engine_does_not_match_hernia_inside_herniation(
    rule_engine: DslRuleEngine,
) -> None:
    """`Lumbar Disc Herniation` must not trigger a hernia waiting period."""
    state = _state(
        diagnosis="Suspected Lumbar Disc Herniation", member_id="EMP007"
    )
    results = rule_engine.evaluate(state)
    hernia = next(r for r in results if r.rule_id == "WAITING_PERIOD_HERNIA")
    assert hernia.passed is True
