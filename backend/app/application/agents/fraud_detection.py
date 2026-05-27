"""Fraud detection.

Three signals are evaluated:
  1. Same-day claim count vs ``fraud_thresholds.same_day_claims_limit`` (TC009).
  2. Trailing-30-day claim count vs ``monthly_claims_limit``.
  3. High-value claim above ``high_value_claim_threshold`` /
     ``auto_manual_review_above`` -> route to manual review.

Also honours ``simulate_component_failure`` for TC011: when the flag is set,
this agent raises an exception that the orchestrator catches, marking the
component as failed and continuing the pipeline with reduced confidence.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.application.agents.base import BaseAgent
from app.domain.claim import ClaimState
from app.domain.decision import AgentResult, PolicyFinding
from app.domain.events import FraudSignalsRaised
from app.domain.policy.terms import PolicyTerms
from app.domain.trace import TraceStatus


class SimulatedComponentFailure(RuntimeError):
    """Raised when ``simulate_component_failure`` is set; intentionally
    propagates to the orchestrator (which catches it for TC011)."""


class FraudDetectionAgent(BaseAgent):
    name = "fraud_detection"
    is_critical = False

    def __init__(self, *, policy: PolicyTerms) -> None:
        self._policy = policy

    async def run(self, state: ClaimState) -> ClaimState:
        rec = self.recorder(state)
        with rec.time_step(self.name) as ctx:
            if state.input.simulate_component_failure:
                raise SimulatedComponentFailure(
                    "Simulated component failure for graceful-degradation test"
                )

            thresholds = self._policy.fraud_thresholds
            inp = state.input

            signals: list[str] = []
            evidence: dict = {"thresholds": dict(thresholds)}

            same_day_count, monthly_count = self._history_counts(state)
            evidence["same_day_count"] = same_day_count
            evidence["monthly_count"] = monthly_count

            same_day_limit = int(thresholds.get("same_day_claims_limit", 99))
            if same_day_count + 1 > same_day_limit:
                signals.append(
                    f"Same-day claim count {same_day_count + 1} exceeds limit {same_day_limit}"
                )

            monthly_limit = int(thresholds.get("monthly_claims_limit", 99))
            if monthly_count + 1 > monthly_limit:
                signals.append(
                    f"Monthly claim count {monthly_count + 1} exceeds limit {monthly_limit}"
                )

            high_value = float(thresholds.get("high_value_claim_threshold", 1e12))
            auto_mr = float(thresholds.get("auto_manual_review_above", 1e12))
            if inp.claimed_amount >= auto_mr:
                signals.append(
                    f"Claim amount ₹{inp.claimed_amount:,.0f} above auto-MR threshold "
                    f"₹{auto_mr:,.0f}"
                )
            elif inp.claimed_amount >= high_value:
                signals.append(
                    f"High-value claim ₹{inp.claimed_amount:,.0f} (threshold ₹{high_value:,.0f})"
                )

            state.fraud_signals = signals

            if signals:
                state.record_event(
                    FraudSignalsRaised(
                        claim_id=state.claim_id,
                        signals=tuple(signals),
                    )
                )
                state.findings.append(
                    PolicyFinding(
                        code="FRAUD_SIGNALS",
                        passed=False,
                        message=f"{len(signals)} fraud signal(s) raised",
                        evidence={**evidence, "signals": signals},
                        severity="MANUAL_REVIEW",
                    )
                )
                rec.record(
                    self.name,
                    status=TraceStatus.WARNING,
                    summary=f"{len(signals)} fraud signal(s)",
                    evidence={**evidence, "signals": signals},
                    confidence_delta=-0.1,
                    latency_ms=ctx["latency_ms"],
                )
            else:
                rec.record(
                    self.name,
                    status=TraceStatus.OK,
                    summary="No fraud signals raised",
                    evidence=evidence,
                    latency_ms=ctx["latency_ms"],
                )

            state.agent_results[self.name] = AgentResult(
                confidence=1.0 if not signals else 0.7,
                evidence_strength=1.0,
                contradiction_score=0.0,
                notes=signals or ["no_signals"],
            )
        return state

    @staticmethod
    def _history_counts(state: ClaimState) -> tuple[int, int]:
        if not state.input.claims_history:
            return 0, 0
        treatment_dt = state.input.treatment_date
        same_day = sum(
            1
            for h in state.input.claims_history
            if _parse_date(h.date) == treatment_dt
        )
        thirty_days_ago = treatment_dt - timedelta(days=30)
        monthly = sum(
            1
            for h in state.input.claims_history
            if thirty_days_ago <= _parse_date(h.date) <= treatment_dt
        )
        return same_day, monthly


def _parse_date(s: str):
    return datetime.strptime(s, "%Y-%m-%d").date()
