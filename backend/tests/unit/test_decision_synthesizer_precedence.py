"""Unit tests for DecisionSynthesizerAgent decision precedence.

`test_decision_synthesizer_events.py` only covers event emission. These
tests pin the *ordering* of decision branches — especially the
hard-rejection priority that drives the user-facing message when more
than one rejection rule fires on the same claim (TC012 was the
motivating bug: a permanent exclusion was being shadowed by a
waiting-period message that misled the member into resubmitting).
"""

from __future__ import annotations

from datetime import date

import pytest

from app.application.agents.decision_synthesizer import DecisionSynthesizerAgent
from app.domain.claim import ClaimCategory, ClaimInput, ClaimState
from app.domain.decision import (
    DecisionStatus,
    PolicyFinding,
    RejectionReason,
)
from app.domain.services.confidence import ConfidenceConfig


@pytest.fixture(scope="module")
def agent() -> DecisionSynthesizerAgent:
    return DecisionSynthesizerAgent(confidence_config=ConfidenceConfig())


def _state(
    *,
    findings: list[PolicyFinding] | None = None,
    final_amount: float = 1000.0,
    claimed: float = 1000.0,
) -> ClaimState:
    state = ClaimState(
        claim_id="T",
        input=ClaimInput(
            member_id="EMP001",
            policy_id="PLUM_GHI_2024",
            claim_category=ClaimCategory.CONSULTATION,
            treatment_date=date(2024, 11, 1),
            claimed_amount=claimed,
        ),
    )
    state.findings = list(findings or [])
    # The synthesizer reads breakdown from the FINANCIAL_CALCULATION
    # finding's evidence; include one so the messaging paths have data
    # to substitute into the user-facing template.
    state.findings.append(
        PolicyFinding(
            code="FINANCIAL_CALCULATION",
            passed=True,
            message="calculated",
            evidence={
                "claimed_amount": claimed,
                "final_approved_amount": final_amount,
                "per_claim_limit": 5000,
                "network_discount_amount": 0,
                "copay_amount": 0,
            },
        )
    )
    return state


def _excluded_finding() -> PolicyFinding:
    return PolicyFinding(
        code=RejectionReason.EXCLUDED_CONDITION.value,
        passed=False,
        rule_id="EXCLUDED_CONDITION_DIAGNOSIS",
        message="Diagnosis matches exclusion 'Obesity and weight loss programs'",
        evidence={
            "diagnosis": "Morbid Obesity — BMI 37",
            "matched_exclusion": "Obesity and weight loss programs",
        },
        severity="REJECT",
    )


def _obesity_waiting_finding() -> PolicyFinding:
    return PolicyFinding(
        code=RejectionReason.WAITING_PERIOD.value,
        passed=False,
        rule_id="WAITING_PERIOD_OBESITY",
        message="Waiting period applies",
        evidence={
            "days_required": 365,
            "eligibility_date": "2025-04-01",
            "condition_label": "obesity-related treatment",
        },
        severity="REJECT",
    )


def _per_claim_finding() -> PolicyFinding:
    return PolicyFinding(
        code=RejectionReason.PER_CLAIM_EXCEEDED.value,
        passed=False,
        message="per-claim exceeded",
        evidence={"claimed": 7500, "per_claim_limit": 5000},
        severity="REJECT",
    )


@pytest.mark.asyncio
async def test_tc012_exclusion_wins_over_waiting_period(
    agent: DecisionSynthesizerAgent,
):
    """When EXCLUDED_CONDITION and WAITING_PERIOD both fire (TC012):

    1. Decision status must be REJECTED.
    2. The primary user message must reference the exclusion, not
       'you can resubmit in N days'.
    3. EXCLUDED_CONDITION must come *first* in rejection_reasons so an
       API consumer who only reads the first reason still gets the
       correct one.
    4. All other hard rejections must still be present in the list so
       the audit log is complete.
    """
    state = _state(
        findings=[
            _obesity_waiting_finding(),
            _excluded_finding(),
            _per_claim_finding(),
        ],
        final_amount=0.0,
    )

    state = await agent.run(state)

    assert state.decision is not None
    assert state.decision.status is DecisionStatus.REJECTED
    assert state.decision.rejection_reasons[0] is RejectionReason.EXCLUDED_CONDITION
    assert set(state.decision.rejection_reasons) == {
        RejectionReason.EXCLUDED_CONDITION,
        RejectionReason.WAITING_PERIOD,
        RejectionReason.PER_CLAIM_EXCEEDED,
    }
    assert "excluded under this policy" in state.decision.user_message
    assert "resubmit on or after" not in state.decision.user_message.lower()


@pytest.mark.asyncio
async def test_pre_auth_message_uses_matched_test_not_none(
    agent: DecisionSynthesizerAgent,
):
    """Regression for TC007: the synthesizer must read `matched_test` from
    rule evidence (the key the JSON rule engine actually emits). Reading
    `test_name` produced the literal word 'None' in the user message."""
    pre_auth = PolicyFinding(
        code=RejectionReason.PRE_AUTH_MISSING.value,
        passed=False,
        rule_id="PRE_AUTH_DIAGNOSTIC_HIGH_VALUE",
        message="pre-auth required",
        evidence={"matched_test": "MRI", "threshold": 10000.0},
        severity="REJECT",
    )
    state = _state(findings=[pre_auth], final_amount=0.0, claimed=15000)

    state = await agent.run(state)

    msg = state.decision.user_message
    assert "for MRI" in msg
    assert "₹10,000" in msg
    assert "None" not in msg
    assert msg.rstrip() == msg, "trailing whitespace from missing next_steps fixed"


@pytest.mark.asyncio
async def test_waiting_period_message_names_the_condition(
    agent: DecisionSynthesizerAgent,
):
    """Regression for TC005: the message must name the condition
    ('diabetes', 'obesity-related treatment', …) rather than referring to
    it as 'this type of claim'."""
    state = _state(findings=[_obesity_waiting_finding()], final_amount=0.0)

    state = await agent.run(state)

    assert "obesity-related treatment" in state.decision.user_message


@pytest.mark.asyncio
async def test_degraded_with_no_extracted_routes_to_manual_review(
    agent: DecisionSynthesizerAgent,
):
    """TC011 shape: extraction failed entirely. With no extracted docs
    and final_amount = 0, the synthesizer must MANUAL_REVIEW the claim
    rather than reject it outright."""
    state = _state(findings=[], final_amount=0.0)
    state.degraded = True
    state.failed_components = ["fraud_detection"]
    # No state.extracted, so the degraded-no-extraction branch fires.

    state = await agent.run(state)

    assert state.decision.status is DecisionStatus.MANUAL_REVIEW
    assert state.decision.requires_manual_review is True


@pytest.mark.asyncio
async def test_clean_approval(agent: DecisionSynthesizerAgent):
    state = _state(findings=[], final_amount=3240.0, claimed=4500)

    state = await agent.run(state)

    assert state.decision.status is DecisionStatus.APPROVED
    assert state.decision.approved_amount == 3240.0
    assert state.decision.rejection_reasons == []
