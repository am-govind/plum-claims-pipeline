"""Unit tests for IntakeAgent.

The integration eval (`tests/integration/test_eval_cases.py`) exercises the
happy path. These tests pin the fail-fast branches: member not found, policy
mismatch, below-minimum claim. Each branch must (1) halt the pipeline early
or stage a finding, (2) record a trace step, and (3) emit a ClaimHaltedEarly
event when it halts so the notification stub can react downstream.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.application.agents.intake import IntakeAgent
from app.config import Settings
from app.domain.claim import ClaimCategory, ClaimInput, ClaimState
from app.domain.decision import RejectionReason
from app.domain.events import ClaimHaltedEarly
from app.infrastructure.policy.json_policy_repository import JsonPolicyRepository


@pytest.fixture(scope="module")
def agent() -> IntakeAgent:
    policy = JsonPolicyRepository(Settings().policy_terms_path).get_terms()
    return IntakeAgent(policy=policy)


def _state(
    *,
    member_id: str = "EMP001",
    policy_id: str = "PLUM_GHI_2024",
    amount: float = 1500.0,
) -> ClaimState:
    return ClaimState(
        claim_id="T",
        input=ClaimInput(
            member_id=member_id,
            policy_id=policy_id,
            claim_category=ClaimCategory.CONSULTATION,
            treatment_date=date(2024, 11, 1),
            claimed_amount=amount,
        ),
    )


@pytest.mark.asyncio
async def test_happy_path_records_intake_ok(agent: IntakeAgent):
    state = await agent.run(_state())
    assert not state.early_stop
    assert any(s.step == "intake" for s in state.trace)
    assert "intake" in state.agent_results
    assert "intake_ok" in state.agent_results["intake"].notes


@pytest.mark.asyncio
async def test_member_not_found_halts_early(agent: IntakeAgent):
    state = await agent.run(_state(member_id="DOES_NOT_EXIST"))

    assert state.early_stop is True
    assert state.early_stop_reason == "MEMBER_NOT_FOUND"
    assert state.early_stop_user_message is not None
    assert "DOES_NOT_EXIST" in state.early_stop_user_message

    events = state.pull_events()
    assert any(
        isinstance(e, ClaimHaltedEarly) and e.reason == "MEMBER_NOT_FOUND"
        for e in events
    ), "MEMBER_NOT_FOUND must publish a ClaimHaltedEarly event"


@pytest.mark.asyncio
async def test_policy_mismatch_halts_early(agent: IntakeAgent):
    state = await agent.run(_state(policy_id="SOME_OTHER_POLICY"))

    assert state.early_stop is True
    assert state.early_stop_reason == "POLICY_MISMATCH"
    assert "SOME_OTHER_POLICY" in (state.early_stop_user_message or "")


@pytest.mark.asyncio
async def test_below_minimum_claim_stages_finding_but_continues(
    agent: IntakeAgent,
):
    """Below-minimum claim shouldn't early-stop — the pipeline continues
    so the synthesizer can render the BELOW_MIN_CLAIM rejection with the
    full breakdown. Intake just stages the finding.
    """
    state = await agent.run(_state(amount=100.0))

    assert state.early_stop is False
    below_min = [
        f for f in state.findings if f.code == RejectionReason.BELOW_MIN_CLAIM.value
    ]
    assert len(below_min) == 1
    assert below_min[0].passed is False
    assert "minimum" in below_min[0].message.lower()
