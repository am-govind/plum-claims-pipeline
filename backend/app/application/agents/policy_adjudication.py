"""Policy adjudication via the declarative rule engine.

Reads ``policy_rules.json`` and evaluates each rule against the current
ClaimState. The agent itself is a thin loop — all of the policy logic
lives in the rule file plus the operator implementations in
``app.domain.policy.rules``. This makes audit easy: every rejection
traces back to a named rule with the resolved policy values it saw.

The rules emit ``RuleResult`` records; the agent maps them onto the
existing ``PolicyFinding`` shape so downstream agents (synthesizer, eval)
do not need to change.
"""

from __future__ import annotations

from app.application.agents.base import BaseAgent
from app.domain.claim import ClaimState
from app.domain.decision import AgentResult, PolicyFinding
from app.domain.policy.rules import RuleResult, get_rule_engine
from app.domain.trace import TraceStatus


class PolicyAdjudicationAgent(BaseAgent):
    name = "policy_adjudication"
    is_critical = False

    async def run(self, state: ClaimState) -> ClaimState:
        rec = self.recorder(state)
        with rec.time_step(self.name) as ctx:
            engine = get_rule_engine()
            results: list[RuleResult] = engine.evaluate(state)

            findings: list[PolicyFinding] = [
                PolicyFinding(
                    code=r.code,
                    passed=r.passed,
                    message=r.message,
                    evidence=r.evidence,
                    evidence_links=r.evidence_links,
                    severity=r.severity if not r.passed else "INFO",
                    rule_id=r.rule_id,
                )
                for r in results
            ]
            state.findings.extend(findings)

            failed = [f for f in findings if not f.passed]
            rec.record(
                self.name,
                status=TraceStatus.OK if not failed else TraceStatus.WARNING,
                summary=(
                    f"{len(findings)} policy rule(s) evaluated; "
                    f"{len(failed)} failed"
                    + (
                        ": " + ", ".join(f.rule_id or f.code for f in failed)
                        if failed
                        else ""
                    )
                ),
                evidence={
                    "rules_evaluated": [
                        {
                            "rule_id": f.rule_id,
                            "code": f.code,
                            "passed": f.passed,
                            "severity": f.severity,
                        }
                        for f in findings
                    ],
                },
                latency_ms=ctx["latency_ms"],
            )

            state.agent_results[self.name] = AgentResult(
                confidence=1.0 if not failed else 0.95,
                evidence_strength=1.0,
                contradiction_score=0.0,
                notes=[f"{f.rule_id}={f.passed}" for f in findings],
            )
        return state
