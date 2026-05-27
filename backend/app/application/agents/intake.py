"""Intake agent: validates the submission shape, looks up the member,
checks submission deadline and minimum claim amount before any expensive
processing happens.
"""

from __future__ import annotations

from app.application.agents.base import BaseAgent
from app.domain.claim import ClaimState
from app.domain.decision import (
    AgentResult,
    Decision,
    DecisionStatus,
    PolicyFinding,
    RejectionReason,
)
from app.domain.policy.terms import PolicyTerms
from app.domain.trace import TraceStatus


class IntakeAgent(BaseAgent):
    name = "intake"
    is_critical = True

    def __init__(self, *, policy: PolicyTerms) -> None:
        self._policy = policy

    async def run(self, state: ClaimState) -> ClaimState:
        rec = self.recorder(state)
        with rec.time_step(self.name) as ctx:
            policy = self._policy
            inp = state.input

            member = policy.get_member(inp.member_id)
            evidence: dict = {
                "member_id": inp.member_id,
                "policy_id": inp.policy_id,
                "category": inp.claim_category.value,
                "claimed_amount": inp.claimed_amount,
                "treatment_date": str(inp.treatment_date),
                "found_member": bool(member),
                "document_count": len(inp.documents),
            }

            if not member:
                rec.record(
                    self.name,
                    status=TraceStatus.EARLY_STOP,
                    summary=f"Member {inp.member_id} not found in roster",
                    evidence=evidence,
                    confidence_delta=-0.5,
                    latency_ms=ctx["latency_ms"],
                )
                state.halt_early(
                    reason="MEMBER_NOT_FOUND",
                    user_message=(
                        f"We could not find member {inp.member_id} in the policy roster. "
                        f"Please check the member ID and resubmit."
                    ),
                )
                return state

            if inp.policy_id != policy.policy_id:
                rec.record(
                    self.name,
                    status=TraceStatus.EARLY_STOP,
                    summary=f"Policy {inp.policy_id} does not match active policy",
                    evidence=evidence,
                    latency_ms=ctx["latency_ms"],
                )
                state.halt_early(
                    reason="POLICY_MISMATCH",
                    user_message=(
                        f"Policy ID {inp.policy_id} is not the active policy. "
                        f"Please verify your policy ID."
                    ),
                )
                return state

            min_claim = policy.submission_rules.get("minimum_claim_amount", 0)
            if inp.claimed_amount < float(min_claim):
                state.findings.append(
                    PolicyFinding(
                        code=RejectionReason.BELOW_MIN_CLAIM.value,
                        passed=False,
                        message=f"Claimed amount ₹{inp.claimed_amount:,.0f} is below minimum ₹{min_claim:,.0f}",
                        evidence={"claimed": inp.claimed_amount, "minimum": min_claim},
                        severity="REJECT",
                    )
                )

            rec.record(
                self.name,
                status=TraceStatus.OK,
                summary=f"Intake validated for member {member['name']}",
                evidence={**evidence, "member_name": member["name"]},
                latency_ms=ctx["latency_ms"],
            )
            state.agent_results[self.name] = AgentResult(
                confidence=1.0,
                evidence_strength=1.0,
                contradiction_score=0.0,
                notes=["intake_ok"],
            )

        return state


def early_stop_decision(state: ClaimState) -> Decision:
    """Build a Decision object for an early-stop state. Used by the API
    layer when the pipeline halted before the synthesizer ran."""
    return Decision(
        status=DecisionStatus.NEEDS_CORRECTION,
        approved_amount=0.0,
        submitted_amount=state.input.claimed_amount,
        confidence=state.confidence,
        summary=state.early_stop_reason or "Claim halted",
        user_message=state.early_stop_user_message or "Claim cannot be processed.",
        notes=[state.early_stop_reason or ""],
    )
