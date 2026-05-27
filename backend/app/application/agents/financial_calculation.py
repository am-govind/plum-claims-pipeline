"""Financial calculation agent.

Pure deterministic math (no LLM). Delegates to ``app.domain.policy.coverage``
so the order of operations lives in one place and is easy to test against
TC010's expected math: 4500 -> -20% network -> 3600 -> -10% co-pay -> 3240.

If a hard rejection finding already exists (waiting period, exclusion,
pre-auth missing, coverage) we still run the calculation for the trace but
flag that the rejection wins.
"""

from __future__ import annotations

from app.application.agents.base import BaseAgent
from app.domain.claim import ClaimState
from app.domain.decision import AgentResult, PolicyFinding, RejectionReason
from app.domain.policy.coverage import apply_financial_calculation
from app.domain.policy.terms import PolicyTerms
from app.domain.trace import TraceStatus

HARD_REJECT_CODES = {
    RejectionReason.WAITING_PERIOD.value,
    RejectionReason.EXCLUDED_CONDITION.value,
    RejectionReason.PRE_AUTH_MISSING.value,
    RejectionReason.PRESCRIPTION_MISSING.value,
    "COVERAGE_CHECK",
}


class FinancialCalculationAgent(BaseAgent):
    name = "financial_calculation"
    is_critical = False

    def __init__(self, *, policy: PolicyTerms) -> None:
        self._policy = policy

    async def run(self, state: ClaimState) -> ClaimState:
        rec = self.recorder(state)
        with rec.time_step(self.name) as ctx:
            policy = self._policy
            inp = state.input
            result = apply_financial_calculation(
                policy=policy,
                category=inp.claim_category,
                claimed_amount=inp.claimed_amount,
                extracted=state.extracted,
                hospital_name=inp.hospital_name
                or next((d.hospital_name for d in state.extracted if d.hospital_name), None),
                ytd_claims_amount=inp.ytd_claims_amount,
            )

            state.line_decisions = result["line_decisions"]
            breakdown = result["breakdown"]
            state.findings.append(
                PolicyFinding(
                    code="FINANCIAL_CALCULATION",
                    passed=True,
                    message=f"Computed approved amount = ₹{result['final_amount']:,.2f}",
                    evidence=breakdown,
                )
            )

            self._add_cap_findings(state, breakdown)
            self._add_line_item_finding(state, result)

            rec.record(
                self.name,
                status=TraceStatus.OK,
                summary=(
                    f"₹{breakdown['claimed_amount']:,.0f} -> "
                    f"discount {breakdown['network_discount_amount']:,.0f} -> "
                    f"co-pay {breakdown['copay_amount']:,.0f} -> "
                    f"final ₹{result['final_amount']:,.0f}"
                    + (f" (caps hit: {breakdown['caps_hit']})" if breakdown["caps_hit"] else "")
                ),
                evidence=breakdown,
                latency_ms=ctx["latency_ms"],
            )
            state.agent_results[self.name] = AgentResult(
                confidence=1.0,
                evidence_strength=1.0,
                contradiction_score=0.0,
                notes=[f"final={result['final_amount']:.2f}"],
            )
        return state

    def _add_cap_findings(self, state: ClaimState, breakdown: dict) -> None:
        caps = breakdown.get("caps_hit", [])
        if "PER_CLAIM" in caps:
            state.findings.append(
                PolicyFinding(
                    code=RejectionReason.PER_CLAIM_EXCEEDED.value,
                    passed=False,
                    message=(
                        f"Claimed amount ₹{breakdown['claimed_amount']:,.0f} "
                        f"exceeds per-claim limit of ₹{breakdown['per_claim_limit']:,.0f}"
                    ),
                    evidence={
                        "claimed": breakdown["claimed_amount"],
                        "per_claim_limit": breakdown["per_claim_limit"],
                    },
                    severity="REJECT",
                )
            )
        if "SUB_LIMIT" in caps:
            state.findings.append(
                PolicyFinding(
                    code=RejectionReason.SUB_LIMIT_EXCEEDED.value,
                    passed=True,
                    message=(
                        f"Approved amount ₹{breakdown['after_copay']:,.0f} exceeds the "
                        f"category sub-limit of ₹{breakdown['sub_limit']:,.0f} "
                        f"(informational; not enforced as a hard cap)"
                    ),
                    evidence={
                        "sub_limit": breakdown["sub_limit"],
                        "after_copay": breakdown["after_copay"],
                    },
                    severity="WARNING",
                )
            )
        if "YTD" in caps:
            state.findings.append(
                PolicyFinding(
                    code=RejectionReason.YTD_LIMIT_EXCEEDED.value,
                    passed=True,
                    message=(
                        f"Amount capped at YTD remaining of ₹{breakdown['ytd_remaining']:,.0f}"
                    ),
                    evidence={
                        "annual_opd_limit": breakdown["annual_opd_limit"],
                        "ytd_claims_amount": breakdown["ytd_claims_amount"],
                    },
                    severity="WARNING",
                )
            )

    def _add_line_item_finding(self, state: ClaimState, result: dict) -> None:
        if not result["had_excluded_line_items"]:
            return
        state.findings.append(
            PolicyFinding(
                code=RejectionReason.LINE_ITEM_EXCLUDED.value,
                passed=False,
                message="One or more line items rejected as excluded procedures",
                evidence={
                    "line_decisions": [ld.model_dump() for ld in result["line_decisions"]],
                },
                severity="WARNING",
            )
        )
