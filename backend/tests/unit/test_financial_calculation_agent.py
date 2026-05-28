"""Unit tests for FinancialCalculationAgent.

This agent is the most failure-prone code in the system: every rupee in
the final number is the product of an ordered sequence of operations and
flipping any two of them changes the answer. The eval suite (TC010)
exercises the canonical happy path; these tests pin the *individual*
levers — network discount, co-pay, per-claim cap, line-item exclusions,
YTD cap — independently, so a regression points at the right operation.

Order of operations (matches `apply_financial_calculation` docstring):
  1. Drop excluded line items.
  2. Reject up-front if claimed > per-claim limit.
  3. Network-hospital discount on the remaining gross.
  4. Category co-pay on the discounted amount.
  5. YTD cap on annual_opd_limit minus ytd_claims_amount.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.application.agents.financial_calculation import FinancialCalculationAgent
from app.config import Settings
from app.domain.claim import (
    ClaimCategory,
    ClaimInput,
    ClaimState,
    DocumentQuality,
    DocumentType,
    ExtractedDocument,
    LineItem,
)
from app.domain.decision import RejectionReason
from app.infrastructure.policy.json_policy_repository import JsonPolicyRepository


@pytest.fixture(scope="module")
def agent() -> FinancialCalculationAgent:
    policy = JsonPolicyRepository(Settings().policy_terms_path).get_terms()
    return FinancialCalculationAgent(policy=policy)


def _state(
    *,
    category: ClaimCategory,
    amount: float,
    hospital_name: str | None = None,
    ytd: float = 0.0,
    extracted: list[ExtractedDocument] | None = None,
) -> ClaimState:
    return ClaimState(
        claim_id="T",
        input=ClaimInput(
            member_id="EMP001",
            policy_id="PLUM_GHI_2024",
            claim_category=category,
            treatment_date=date(2024, 11, 1),
            claimed_amount=amount,
            hospital_name=hospital_name,
            ytd_claims_amount=ytd,
        ),
        extracted=extracted or [],
    )


def _bill(
    file_id: str,
    line_items: list[tuple[str, float]],
    *,
    total: float | None = None,
    hospital: str | None = None,
) -> ExtractedDocument:
    return ExtractedDocument(
        file_id=file_id,
        document_type=DocumentType.HOSPITAL_BILL,
        quality=DocumentQuality.GOOD,
        hospital_name=hospital,
        line_items=[LineItem(description=d, amount=a) for d, a in line_items],
        total_amount=total,
    )


@pytest.mark.asyncio
async def test_tc010_network_discount_then_copay_math(agent: FinancialCalculationAgent):
    """TC010 expected math: 4500 -> -20% network -> 3600 -> -10% co-pay -> 3240."""
    state = _state(
        category=ClaimCategory.CONSULTATION,
        amount=4500,
        hospital_name="Apollo Hospitals",
    )

    state = await agent.run(state)

    breakdown = next(
        (f.evidence for f in state.findings if f.code == "FINANCIAL_CALCULATION"),
        {},
    )
    assert breakdown["is_network_hospital"] is True
    assert breakdown["network_discount_amount"] == 900.0
    assert breakdown["after_discount"] == 3600.0
    assert breakdown["copay_amount"] == 360.0
    assert breakdown["final_approved_amount"] == 3240.0


@pytest.mark.asyncio
async def test_non_network_hospital_skips_discount(
    agent: FinancialCalculationAgent,
):
    state = _state(
        category=ClaimCategory.CONSULTATION,
        amount=4500,
        hospital_name="Random Clinic, Bangalore",
    )

    state = await agent.run(state)

    breakdown = next(
        f.evidence for f in state.findings if f.code == "FINANCIAL_CALCULATION"
    )
    assert breakdown["is_network_hospital"] is False
    assert breakdown["network_discount_amount"] == 0.0
    # No discount; co-pay still applies at 10% on 4500 -> 450; final = 4050.
    assert breakdown["copay_amount"] == 450.0
    assert breakdown["final_approved_amount"] == 4050.0


@pytest.mark.asyncio
async def test_per_claim_limit_exceeded_yields_zero_and_finding(
    agent: FinancialCalculationAgent,
):
    """TC008 shape: consultation with claimed 7,500 > per_claim_limit 5,000.

    The sub_limit for consultation is 2,000, so the *effective* per-claim
    cap is max(per_claim_limit, sub_limit) = 5,000. 7,500 exceeds that,
    so PER_CLAIM_EXCEEDED fires and final_approved_amount = 0.
    """
    state = _state(category=ClaimCategory.CONSULTATION, amount=7500)

    state = await agent.run(state)

    breakdown = next(
        f.evidence for f in state.findings if f.code == "FINANCIAL_CALCULATION"
    )
    assert breakdown["per_claim_exceeded"] is True
    assert breakdown["final_approved_amount"] == 0.0
    per_claim_findings = [
        f
        for f in state.findings
        if f.code == RejectionReason.PER_CLAIM_EXCEEDED.value
    ]
    assert len(per_claim_findings) == 1
    assert per_claim_findings[0].passed is False


@pytest.mark.asyncio
async def test_line_item_exclusion_drops_only_the_excluded_item(
    agent: FinancialCalculationAgent,
):
    """TC006 shape: a dental bill mixes a covered procedure with a
    cosmetic-exclusion line. Approved should equal the covered subtotal,
    not the bill total."""
    bill = _bill(
        "F001",
        [("Root Canal Treatment", 8000.0), ("Teeth Whitening", 4000.0)],
        total=12000.0,
    )
    state = _state(category=ClaimCategory.DENTAL, amount=12000, extracted=[bill])

    state = await agent.run(state)

    line_excluded = [
        f
        for f in state.findings
        if f.code == RejectionReason.LINE_ITEM_EXCLUDED.value
    ]
    assert len(line_excluded) == 1
    assert state.line_decisions[0].approved_amount == 8000.0
    assert state.line_decisions[1].approved_amount == 0.0
    breakdown = next(
        f.evidence for f in state.findings if f.code == "FINANCIAL_CALCULATION"
    )
    # Dental has 0% co-pay, no network discount on a non-network bill,
    # so final == accepted_total == 8000.
    assert breakdown["final_approved_amount"] == 8000.0


@pytest.mark.asyncio
async def test_ytd_cap_clips_the_final_amount(agent: FinancialCalculationAgent):
    """Annual OPD limit is 50,000; if ytd_claims_amount has used 49,500
    already, this claim's final amount must be clipped to 500."""
    state = _state(
        category=ClaimCategory.CONSULTATION,
        amount=2000,
        ytd=49500.0,
    )

    state = await agent.run(state)

    breakdown = next(
        f.evidence for f in state.findings if f.code == "FINANCIAL_CALCULATION"
    )
    assert breakdown["ytd_remaining"] == 500.0
    assert breakdown["final_approved_amount"] == 500.0
    assert "YTD" in breakdown["caps_hit"]
