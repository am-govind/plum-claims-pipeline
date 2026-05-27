"""Build the ``DecisionNode`` causal tree from the synthesised state.

The tree is a structured, expandable view of the decision: which checks
ran, which fired, the calculation steps, and any fraud/contradiction
signals. The frontend renders it as a collapsible tree under "Why was
this decision reached?".
"""

from __future__ import annotations

from typing import Iterable

from app.domain.claim import ClaimState
from app.domain.decision import Decision, DecisionNode, PolicyFinding
from app.domain.evidence import EvidenceLink

# Codes that are treated as policy gates rather than calculation outputs.
_POLICY_CODES = {
    "COVERAGE_CHECK",
    "WAITING_PERIOD",
    "EXCLUDED_CONDITION",
    "PRE_AUTH_MISSING",
    "PRESCRIPTION_MISSING",
    "PRESCRIPTION_PRESENT",
    "PRE_AUTH_CHECK",
    "WAITING_PERIOD_CHECK",
    "EXCLUSION_CHECK",
}


def build_explanation_tree(state: ClaimState, decision: Decision) -> DecisionNode:
    """Compose the tree from findings, calculation breakdown, and signals."""
    root = DecisionNode(
        label=_root_label(decision),
        kind="root",
        status=decision.status.value,
        detail={
            "approved_amount": decision.approved_amount,
            "submitted_amount": decision.submitted_amount,
            "confidence": decision.confidence,
        },
    )

    policy_node = _policy_group(state.findings)
    if policy_node.children:
        root.children.append(policy_node)

    contradictions_node = _contradictions_group(state)
    if contradictions_node.children:
        root.children.append(contradictions_node)

    calc_node = _calculation_group(state, decision)
    if calc_node.children:
        root.children.append(calc_node)

    fraud_node = _fraud_group(state)
    if fraud_node.children:
        root.children.append(fraud_node)

    if decision.degraded:
        root.children.append(
            DecisionNode(
                label="Pipeline ran in degraded mode",
                kind="note",
                status="WARNING",
                detail={"failed_components": decision.failed_components},
            )
        )

    return root


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _root_label(decision: Decision) -> str:
    if decision.approved_amount > 0:
        return f"{decision.status.value} — ₹{decision.approved_amount:,.2f}"
    return decision.status.value


def _policy_group(findings: Iterable[PolicyFinding]) -> DecisionNode:
    group = DecisionNode(label="Policy checks", kind="rule_group")
    for f in findings:
        if f.code not in _POLICY_CODES and not f.code.startswith("WAITING_PERIOD"):
            continue
        group.children.append(
            DecisionNode(
                label=f"{f.rule_id or f.code} — {'PASS' if f.passed else 'FAIL'}",
                kind="rule",
                status="PASS" if f.passed else "FAIL",
                detail={
                    "code": f.code,
                    "rule_id": f.rule_id,
                    "message": f.message,
                    "severity": f.severity,
                },
                evidence=list(f.evidence_links) or _to_links_from_evidence(f.evidence),
            )
        )
    return group


def _contradictions_group(state: ClaimState) -> DecisionNode:
    group = DecisionNode(label="Cross-document contradictions", kind="rule_group")
    for c in state.contradictions:
        group.children.append(
            DecisionNode(
                label=f"{c.kind}",
                kind="signal",
                status=c.severity,
                detail={"description": c.description, "confidence": c.confidence},
                evidence=list(c.evidence),
            )
        )
    return group


def _calculation_group(state: ClaimState, decision: Decision) -> DecisionNode:
    group = DecisionNode(label="Financial calculation", kind="rule_group")
    b = decision.breakdown or {}
    if not b:
        return group

    if "claimed_amount" in b:
        group.children.append(
            DecisionNode(
                label=f"Claimed amount ₹{b['claimed_amount']:,.0f}",
                kind="calc_step",
            )
        )
    if "gross_after_line_items" in b and b.get("gross_after_line_items") != b.get(
        "claimed_amount"
    ):
        group.children.append(
            DecisionNode(
                label=(
                    f"After line-item exclusions: ₹{b['gross_after_line_items']:,.0f}"
                ),
                kind="calc_step",
            )
        )
    if b.get("network_discount_amount", 0) > 0:
        group.children.append(
            DecisionNode(
                label=(
                    f"−{b.get('network_discount_percent', 0)}% network discount → "
                    f"₹{b.get('after_discount', 0):,.0f}"
                ),
                kind="calc_step",
                detail={"amount": b.get("network_discount_amount")},
            )
        )
    if b.get("copay_amount", 0) > 0:
        group.children.append(
            DecisionNode(
                label=(
                    f"−{b.get('copay_percent', 0)}% co-pay → ₹{b.get('after_copay', 0):,.0f}"
                ),
                kind="calc_step",
                detail={"amount": b.get("copay_amount")},
            )
        )
    if b.get("caps_hit"):
        group.children.append(
            DecisionNode(
                label=f"Caps applied: {', '.join(b['caps_hit'])}",
                kind="calc_step",
                detail={"caps": b["caps_hit"]},
            )
        )
    group.children.append(
        DecisionNode(
            label=f"Final approved ₹{decision.approved_amount:,.2f}",
            kind="calc_step",
            status="FINAL",
        )
    )
    return group


def _fraud_group(state: ClaimState) -> DecisionNode:
    group = DecisionNode(label="Fraud signals", kind="rule_group")
    if not state.fraud_signals:
        return group
    for s in state.fraud_signals:
        group.children.append(
            DecisionNode(label=s, kind="signal", status="WARNING")
        )
    return group


def _to_links_from_evidence(ev: dict) -> list[EvidenceLink]:
    fid = ev.get("file_id") if isinstance(ev, dict) else None
    if not fid:
        return []
    snippet = ev.get("matched_keyword") or ev.get("matched_exclusion") or ev.get("diagnosis")
    return [EvidenceLink(source_file_id=fid, snippet=str(snippet) if snippet else None)]
