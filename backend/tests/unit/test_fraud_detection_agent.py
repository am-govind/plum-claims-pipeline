"""Unit tests for FraudDetectionAgent.

Pins each of the three signal branches independently (same-day, monthly,
high-value), the no-signal happy path, and the `simulate_component_failure`
override that exists so TC011 can exercise graceful degradation.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.application.agents.fraud_detection import (
    FraudDetectionAgent,
    SimulatedComponentFailure,
)
from app.config import Settings
from app.domain.claim import (
    ClaimCategory,
    ClaimInput,
    ClaimState,
    ClaimsHistoryEntry,
)
from app.domain.events import FraudSignalsRaised
from app.infrastructure.policy.json_policy_repository import JsonPolicyRepository


@pytest.fixture(scope="module")
def agent() -> FraudDetectionAgent:
    policy = JsonPolicyRepository(Settings().policy_terms_path).get_terms()
    return FraudDetectionAgent(policy=policy)


def _state(
    *,
    amount: float = 1500.0,
    treatment_date: date = date(2024, 11, 1),
    history: list[ClaimsHistoryEntry] | None = None,
    simulate: bool = False,
) -> ClaimState:
    return ClaimState(
        claim_id="T",
        input=ClaimInput(
            member_id="EMP001",
            policy_id="PLUM_GHI_2024",
            claim_category=ClaimCategory.CONSULTATION,
            treatment_date=treatment_date,
            claimed_amount=amount,
            claims_history=history or [],
            simulate_component_failure=simulate,
        ),
    )


@pytest.mark.asyncio
async def test_no_signals_records_ok(agent: FraudDetectionAgent):
    state = await agent.run(_state())

    assert state.fraud_signals == []
    fraud_step = next(s for s in state.trace if s.step == "fraud_detection")
    assert fraud_step.status.value == "OK"


@pytest.mark.asyncio
async def test_same_day_claims_above_limit_raises_signal(agent: FraudDetectionAgent):
    treatment = date(2024, 11, 1)
    # policy.fraud_thresholds.same_day_claims_limit = 2; we already have
    # 2 same-day claims, so submitting this one makes 3.
    history = [
        ClaimsHistoryEntry(
            claim_id="OLD1", date=str(treatment), amount=500, provider="X"
        ),
        ClaimsHistoryEntry(
            claim_id="OLD2", date=str(treatment), amount=500, provider="Y"
        ),
    ]
    state = await agent.run(_state(history=history, treatment_date=treatment))

    assert any("same-day" in s.lower() for s in state.fraud_signals)
    events = state.pull_events()
    assert any(isinstance(e, FraudSignalsRaised) for e in events)


@pytest.mark.asyncio
async def test_monthly_claims_above_limit_raises_signal(agent: FraudDetectionAgent):
    treatment = date(2024, 11, 30)
    # monthly_claims_limit = 6; 6 prior claims in the 30-day window means
    # this submission makes 7, which exceeds the limit.
    history = [
        ClaimsHistoryEntry(
            claim_id=f"H{i}",
            date=str(date(2024, 11, i + 1)),
            amount=500,
            provider="X",
        )
        for i in range(6)
    ]
    state = await agent.run(_state(history=history, treatment_date=treatment))

    assert any("monthly" in s.lower() for s in state.fraud_signals)


@pytest.mark.asyncio
async def test_auto_manual_review_threshold(agent: FraudDetectionAgent):
    """Claims above auto_manual_review_above (25,000) must raise a signal
    even when no history is present so the synthesizer routes to MANUAL_REVIEW."""
    state = await agent.run(_state(amount=30000.0))

    assert any("auto-MR threshold" in s for s in state.fraud_signals)


@pytest.mark.asyncio
async def test_simulate_component_failure_raises(agent: FraudDetectionAgent):
    """The flag is the lever TC011 uses to verify graceful degradation.
    Fraud must raise (the orchestrator catches it and marks the state
    as degraded); the test asserts the raise itself."""
    with pytest.raises(SimulatedComponentFailure):
        await agent.run(_state(simulate=True))
