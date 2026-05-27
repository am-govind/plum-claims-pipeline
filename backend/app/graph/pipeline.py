"""LangGraph wiring for the multi-agent claims pipeline.

Each node wraps the corresponding agent in a try/except. Non-critical agent
failures are caught: the orchestrator records the failure on the trace,
marks the state as ``degraded``, drops confidence, and continues. Critical
agent failures (intake, document_verification, decision_synthesizer)
propagate. This is what makes TC011 produce a manual-review decision
instead of crashing.

The graph is deliberately linear; we use LangGraph (rather than a plain
chain) so we get state management, native step interception, and an obvious
extension point for parallel branches (e.g. fanning out extraction).
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Callable

from langgraph.graph import END, StateGraph

from app.agents.base import BaseAgent
from app.agents.contradiction_detection import ContradictionDetectionAgent
from app.agents.decision_synthesizer import DecisionSynthesizerAgent
from app.agents.document_verification import DocumentVerificationAgent
from app.agents.extraction import ExtractionAgent
from app.agents.financial_calculation import FinancialCalculationAgent
from app.agents.fraud_detection import FraudDetectionAgent
from app.agents.intake import IntakeAgent
from app.agents.policy_adjudication import PolicyAdjudicationAgent
from app.llm.base import LLMProvider
from app.models.claim import ClaimState
from app.models.trace import TraceStatus
from app.trace.recorder import TraceRecorder


def _wrap(agent: BaseAgent) -> Callable[[ClaimState], Any]:
    """Wrap an agent so non-critical failures never bubble up."""

    async def node(state: ClaimState) -> ClaimState:
        if state.early_stop:
            return state
        rec = TraceRecorder(state)
        start = time.perf_counter()
        try:
            out = await agent.run(state)
            state.cost.add_node(agent.name, int((time.perf_counter() - start) * 1000))
            return out
        except Exception as e:  # noqa: BLE001
            latency_ms = int((time.perf_counter() - start) * 1000)
            state.cost.add_node(agent.name, latency_ms)
            if agent.is_critical:
                rec.record(
                    agent.name,
                    status=TraceStatus.ERROR,
                    summary=f"Critical component failed: {e}",
                    error=e.__class__.__name__,
                    latency_ms=latency_ms,
                    confidence_delta=-0.5,
                )
                raise
            rec.record(
                agent.name,
                status=TraceStatus.ERROR,
                summary=f"{agent.name} failed; pipeline continuing in degraded mode",
                error=f"{e.__class__.__name__}: {e}",
                latency_ms=latency_ms,
                confidence_delta=-0.25,
            )
            state.degraded = True
            if agent.name not in state.failed_components:
                state.failed_components.append(agent.name)
            return state

    node.__name__ = f"{agent.name}_node"
    return node


def _route_after_intake(state: ClaimState) -> str:
    return END if state.early_stop else "document_verification"


def _route_after_verification(state: ClaimState) -> str:
    return END if state.early_stop else "extraction"


# ---------------------------------------------------------------------------
# Deliberation routing
# ---------------------------------------------------------------------------

# Each cycle has a hard iteration cap (1 retry). The counter lives on
# ``state.deliberation_iterations`` so it survives any state copy
# LangGraph does between nodes.

EXTRACTION_LOW_CONF_THRESHOLD = 0.7
RE_EXTRACTION_CAP = 1
POLICY_RECONSIDER_CAP = 1


def _needs_re_extraction(state: ClaimState) -> bool:
    if state.early_stop or not state.extracted:
        return False
    seen = state.deliberation_iterations.get("re_extraction", 0)
    if seen >= RE_EXTRACTION_CAP:
        return False
    low_conf = any(
        d.extraction_confidence < EXTRACTION_LOW_CONF_THRESHOLD for d in state.extracted
    )
    has_issues = any(d.validation_issues for d in state.extracted)
    return low_conf or has_issues


def _route_after_extraction(state: ClaimState) -> str:
    if _needs_re_extraction(state):
        return "re_verification"
    return "contradiction_detection"


def _needs_policy_reconsider(state: ClaimState) -> bool:
    """Trigger policy reconsider when fraud disagrees with policy.

    Specifically: fraud raised signals AND no policy finding failed. We
    treat that as "fraud sees something the rule engine didn't" and ask
    policy to reconsider with the fraud signals in scope.
    """
    seen = state.deliberation_iterations.get("policy_reconsider", 0)
    if seen >= POLICY_RECONSIDER_CAP:
        return False
    has_fraud = bool(state.fraud_signals)
    any_policy_failed = any(not f.passed for f in state.findings)
    return has_fraud and not any_policy_failed


def _route_after_fraud(state: ClaimState) -> str:
    if _needs_policy_reconsider(state):
        return "policy_reconsider"
    return "decision_synthesizer"


async def _re_verification_node(state: ClaimState) -> ClaimState:
    """Lightweight retry: bump the iteration counter and trace it.

    A real implementation would re-run a focused extraction pass (e.g.
    higher-temperature retry, or run a different model). We surface the
    cycle on the trace and continue; the next pass through extraction
    already benefits from the validation feedback recorded above.
    """
    rec = TraceRecorder(state)
    state.deliberation_iterations["re_extraction"] = (
        state.deliberation_iterations.get("re_extraction", 0) + 1
    )
    issues = sum(len(d.validation_issues) for d in state.extracted)
    rec.record(
        "re_verification",
        status=TraceStatus.WARNING,
        summary=(
            f"Deliberation cycle: {issues} extraction validation issue(s) "
            f"and/or low extraction confidence; routing back to extraction "
            f"(iteration {state.deliberation_iterations['re_extraction']}/"
            f"{RE_EXTRACTION_CAP})"
        ),
        evidence={
            "iteration": state.deliberation_iterations["re_extraction"],
            "cap": RE_EXTRACTION_CAP,
            "extraction_issues": issues,
        },
        latency_ms=0,
    )
    return state


async def _policy_reconsider_node(state: ClaimState) -> ClaimState:
    """Mark the case for manual review when fraud + clean policy disagree."""
    rec = TraceRecorder(state)
    state.deliberation_iterations["policy_reconsider"] = (
        state.deliberation_iterations.get("policy_reconsider", 0) + 1
    )
    rec.record(
        "policy_reconsider",
        status=TraceStatus.WARNING,
        summary=(
            f"Deliberation cycle: fraud raised {len(state.fraud_signals)} signal(s) "
            "while all policy checks passed; flagging claim for manual review"
        ),
        evidence={
            "fraud_signals": list(state.fraud_signals),
            "iteration": state.deliberation_iterations["policy_reconsider"],
            "cap": POLICY_RECONSIDER_CAP,
        },
        latency_ms=0,
    )
    return state


def build_graph(*, llm_provider: LLMProvider | None = None):
    """Build (but don't compile yet) the StateGraph."""
    intake = IntakeAgent()
    verify = DocumentVerificationAgent()
    extract = ExtractionAgent(provider=llm_provider)
    contradict = ContradictionDetectionAgent()
    policy = PolicyAdjudicationAgent()
    finance = FinancialCalculationAgent()
    fraud = FraudDetectionAgent()
    synth = DecisionSynthesizerAgent()

    g: StateGraph = StateGraph(ClaimState)
    g.add_node("intake", _wrap(intake))
    g.add_node("document_verification", _wrap(verify))
    g.add_node("extraction", _wrap(extract))
    g.add_node("re_verification", _re_verification_node)
    g.add_node("contradiction_detection", _wrap(contradict))
    g.add_node("policy_adjudication", _wrap(policy))
    g.add_node("financial_calculation", _wrap(finance))
    g.add_node("fraud_detection", _wrap(fraud))
    g.add_node("policy_reconsider", _policy_reconsider_node)
    g.add_node("decision_synthesizer", _wrap(synth))

    g.set_entry_point("intake")
    g.add_conditional_edges("intake", _route_after_intake)
    g.add_conditional_edges("document_verification", _route_after_verification)
    g.add_conditional_edges("extraction", _route_after_extraction)
    g.add_edge("re_verification", "extraction")
    g.add_edge("contradiction_detection", "policy_adjudication")
    g.add_edge("policy_adjudication", "financial_calculation")
    g.add_edge("financial_calculation", "fraud_detection")
    g.add_conditional_edges("fraud_detection", _route_after_fraud)
    g.add_edge("policy_reconsider", "decision_synthesizer")
    g.add_edge("decision_synthesizer", END)
    return g


_compiled_app = None
_compiled_provider_id: int | None = None


def _get_app(llm_provider: LLMProvider | None = None):
    """Compile the graph once per provider instance.

    Tests pass a fresh provider per run so we recompile when the provider
    changes. In production this is called once on startup.
    """
    global _compiled_app, _compiled_provider_id
    pid = id(llm_provider) if llm_provider is not None else 0
    if _compiled_app is None or _compiled_provider_id != pid:
        _compiled_app = build_graph(llm_provider=llm_provider).compile()
        _compiled_provider_id = pid
    return _compiled_app


async def run_pipeline(
    state: ClaimState, *, llm_provider: LLMProvider | None = None
) -> ClaimState:
    """Execute the claim through the LangGraph pipeline."""
    app = _get_app(llm_provider)
    result = await app.ainvoke(state)
    if isinstance(result, ClaimState):
        return result
    return ClaimState.model_validate(result)


def run_pipeline_sync(
    state: ClaimState, *, llm_provider: LLMProvider | None = None
) -> ClaimState:
    return asyncio.run(run_pipeline(state, llm_provider=llm_provider))
