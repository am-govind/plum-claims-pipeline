"""Declarative rule engine.

Why a custom evaluator instead of CEL/JsonLogic/Python eval:
- Reviewers can audit every operator in this file.
- We surface ``${policy.path}`` references with the resolved value on every
  ``RuleResult.evidence`` so the trace shows exactly what numbers the rule
  saw.
- We keep the operator surface small and finite — adding an operator is a
  conscious 5-line code change, not an arbitrary expression DSL.

The engine evaluates rules from ``policy_rules.json`` and returns
``RuleResult`` records; the policy adjudication agent converts each into a
``PolicyFinding`` so the synthesizer logic doesn't change. This is what
the plan calls "thin loop" refactor — same outputs, different source.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import timedelta
from string import Template
from typing import Any

from app.domain.claim import ClaimState, DocumentType, ExtractedDocument
from app.domain.evidence import EvidenceLink
from app.domain.policy.exclusions import diagnosis_excluded_reason
from app.domain.policy.terms import PolicyTerms
from app.domain.policy.waiting_periods import _matched_condition  # noqa: F401  (kept for future helpers)

# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class RuleResult:
    rule_id: str
    code: str
    passed: bool
    action: str
    severity: str
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)
    evidence_links: list[EvidenceLink] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Rule engine
# ---------------------------------------------------------------------------


class DslRuleEngine:
    """Evaluator for a tightly-scoped JSON rule DSL.

    Supported operator nodes (each a single-key dict):

    - ``{"all": [..]}``  — all sub-conditions true
    - ``{"any": [..]}``  — any sub-condition true
    - ``{"not": cond}``  — negation
    - ``{"equals": [a, b]}``
    - ``{"in": [needle, haystack]}``
    - ``{"gt": [a, b]}``, ``{"lt": [a, b]}``, ``{"gte": [a, b]}``, ``{"lte": [a, b]}``
    - ``{"matches_diagnosis": ["k1", "k2"]}``  — whole-word match in any extracted diagnosis/treatment
    - ``{"diagnosis_excluded": true}``   — uses the existing excl helper
    - ``{"days_since_join_lt": "${policy.path}"}``
    - ``{"category_in": [..]}``
    - ``{"claimed_amount_gt": <num|${path}>}``
    - ``{"high_value_test_in_doc": "${policy.path}"}``  — substring match
    - ``{"category_requires_prescription": true}`` and ``{"prescription_present": true}``

    The ``${path}`` resolver walks ``policy`` then ``state``.

    Construct with the parsed ``rules_data`` dict and the active
    ``PolicyTerms``; no file IO happens here.
    """

    def __init__(self, *, rules_data: dict[str, Any], policy: PolicyTerms) -> None:
        self.rules_data = rules_data
        self.policy = policy

    # -- public API ----------------------------------------------------------

    def evaluate(self, state: ClaimState) -> list[RuleResult]:
        results: list[RuleResult] = []
        for rule in self.rules_data.get("rules", []):
            scope = rule.get("category_scope", ["*"])
            if "*" not in scope and state.input.claim_category.value not in scope:
                continue
            ctx = _Ctx(policy=self.policy, state=state, rule=rule)
            ctx.template_vars.update(
                {
                    "treatment_date": str(state.input.treatment_date),
                    "claim_category": state.input.claim_category.value,
                    "claimed_amount": f"{state.input.claimed_amount:,.0f}",
                }
            )
            try:
                triggered = _eval_node(rule.get("condition", {}), ctx)
            except Exception as exc:  # pragma: no cover — defensive
                results.append(
                    RuleResult(
                        rule_id=rule["rule_id"],
                        code=rule.get("code", rule["rule_id"]),
                        passed=True,
                        action="SKIP",
                        severity="INFO",
                        message=f"Rule errored and was skipped: {exc}",
                        evidence={"error": str(exc)},
                    )
                )
                continue

            results.append(_make_result(rule, ctx, triggered))
        return results


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


@dataclass
class _Ctx:
    policy: PolicyTerms
    state: ClaimState
    rule: dict[str, Any]
    evidence: dict[str, Any] = field(default_factory=dict)
    evidence_links: list[EvidenceLink] = field(default_factory=list)
    template_vars: dict[str, Any] = field(default_factory=dict)


# Maximum nesting depth for safety; rules in this assignment are flat.
_MAX_DEPTH = 8


def _eval_node(node: Any, ctx: _Ctx, depth: int = 0) -> bool:
    if depth > _MAX_DEPTH:
        raise ValueError("rule nesting too deep")
    if not isinstance(node, dict) or len(node) != 1:
        raise ValueError(f"each operator node must be a single-key dict; got {node!r}")
    op, val = next(iter(node.items()))
    fn = _OPERATORS.get(op)
    if fn is None:
        raise ValueError(f"unknown operator: {op}")
    return fn(val, ctx, depth)


# -- operator implementations -----------------------------------------------


def _op_all(val: Any, ctx: _Ctx, depth: int) -> bool:
    return all(_eval_node(v, ctx, depth + 1) for v in val)


def _op_any(val: Any, ctx: _Ctx, depth: int) -> bool:
    return any(_eval_node(v, ctx, depth + 1) for v in val)


def _op_not(val: Any, ctx: _Ctx, depth: int) -> bool:
    return not _eval_node(val, ctx, depth + 1)


def _op_equals(val: list[Any], ctx: _Ctx, _: int) -> bool:
    a, b = _resolve(val[0], ctx), _resolve(val[1], ctx)
    return a == b


def _op_in(val: list[Any], ctx: _Ctx, _: int) -> bool:
    needle, haystack = _resolve(val[0], ctx), _resolve(val[1], ctx)
    return needle in haystack


def _op_gt(val: list[Any], ctx: _Ctx, _: int) -> bool:
    return _resolve(val[0], ctx) > _resolve(val[1], ctx)


def _op_lt(val: list[Any], ctx: _Ctx, _: int) -> bool:
    return _resolve(val[0], ctx) < _resolve(val[1], ctx)


def _op_gte(val: list[Any], ctx: _Ctx, _: int) -> bool:
    return _resolve(val[0], ctx) >= _resolve(val[1], ctx)


def _op_lte(val: list[Any], ctx: _Ctx, _: int) -> bool:
    return _resolve(val[0], ctx) <= _resolve(val[1], ctx)


def _op_matches_diagnosis(val: list[str], ctx: _Ctx, _: int) -> bool:
    """Whole-word match across all extracted diagnoses and treatments."""
    keywords = [str(_resolve(k, ctx)) for k in val]
    matched = None
    for doc in ctx.state.extracted:
        haystack = " | ".join(p for p in [doc.diagnosis, doc.treatment] if p).lower()
        if not haystack:
            continue
        for kw in keywords:
            pattern = r"\b" + re.escape(kw.lower()) + r"\b"
            if re.search(pattern, haystack):
                matched = (kw, doc)
                break
        if matched:
            break
    if matched:
        kw, doc = matched
        ctx.evidence["matched_keyword"] = kw
        ctx.evidence["matched_diagnosis"] = doc.diagnosis
        ctx.evidence["matched_treatment"] = doc.treatment
        ctx.evidence["file_id"] = doc.file_id
        ctx.evidence_links.append(
            EvidenceLink(
                source_file_id=doc.file_id,
                field_path="extracted.diagnosis",
                snippet=doc.diagnosis or doc.treatment,
            )
        )
        ctx.template_vars["matched_keyword"] = kw
        return True
    return False


def _op_diagnosis_excluded(val: bool, ctx: _Ctx, _: int) -> bool:
    """Use the existing exclusion helper. Surfaces matched phrase as evidence."""
    if not val:
        return False
    for doc in ctx.state.extracted:
        reason = diagnosis_excluded_reason(ctx.policy, doc.diagnosis, doc.treatment)
        if reason:
            ctx.evidence["matched_exclusion"] = reason
            ctx.evidence["diagnosis"] = doc.diagnosis
            ctx.evidence["treatment"] = doc.treatment
            ctx.evidence["file_id"] = doc.file_id
            ctx.evidence_links.append(
                EvidenceLink(
                    source_file_id=doc.file_id,
                    field_path="extracted.diagnosis",
                    snippet=doc.diagnosis or doc.treatment,
                )
            )
            ctx.template_vars["matched_exclusion"] = reason
            return True
    return False


def _op_days_since_join_lt(val: Any, ctx: _Ctx, _: int) -> bool:
    days_required = _resolve(val, ctx)
    if days_required is None:
        return False
    join_date = ctx.policy.member_join_date(ctx.state.input.member_id)
    if join_date is None:
        return False
    days_elapsed = (ctx.state.input.treatment_date - join_date).days
    eligibility = join_date + timedelta(days=int(days_required))
    ctx.evidence.update(
        {
            "join_date": str(join_date),
            "treatment_date": str(ctx.state.input.treatment_date),
            "days_required": int(days_required),
            "days_elapsed": days_elapsed,
            "eligibility_date": str(eligibility),
        }
    )
    ctx.template_vars.update(
        {
            "days_required": int(days_required),
            "days_elapsed": days_elapsed,
            "eligibility_date": str(eligibility),
        }
    )
    return days_elapsed < int(days_required)


def _op_category_in(val: list[str], ctx: _Ctx, _: int) -> bool:
    return ctx.state.input.claim_category.value in val


def _op_category_not_in(val: list[str], ctx: _Ctx, _: int) -> bool:
    return ctx.state.input.claim_category.value not in val


def _op_claimed_amount_gt(val: Any, ctx: _Ctx, _: int) -> bool:
    threshold = _resolve(val, ctx)
    if threshold is None:
        return False
    ctx.evidence["claimed_amount"] = ctx.state.input.claimed_amount
    ctx.evidence["threshold"] = float(threshold)
    return ctx.state.input.claimed_amount > float(threshold)


def _op_high_value_test_in_doc(val: Any, ctx: _Ctx, _: int) -> bool:
    """Detect a high-value test across the extracted docs.

    ``val`` resolves to a list of test names from the policy, e.g.
    ``${policy.opd_categories.diagnostic.high_value_tests_requiring_pre_auth}``.
    """
    tests = _resolve(val, ctx) or []
    blob = _doc_text_blob(ctx.state.extracted)
    for t in tests:
        if t.lower() in blob:
            ctx.evidence["matched_test"] = t.upper()
            ctx.template_vars["matched_test"] = t.upper()
            return True
    return False


def _op_prescription_present(val: bool, ctx: _Ctx, _: int) -> bool:
    has_rx = any(
        d.actual_type == DocumentType.PRESCRIPTION for d in ctx.state.input.documents
    )
    return has_rx == bool(val)


def _op_category_requires_prescription(val: bool, ctx: _Ctx, _: int) -> bool:
    cfg = ctx.policy.opd_categories.get(ctx.state.input.claim_category.value.lower(), {})
    return cfg.get("requires_prescription", False) == bool(val)


def _op_category_covered(val: bool, ctx: _Ctx, _: int) -> bool:
    from app.domain.policy.coverage import is_category_covered

    covered = is_category_covered(ctx.policy, ctx.state.input.claim_category)
    return covered == bool(val)


_OPERATORS: dict[str, Any] = {
    "all": _op_all,
    "any": _op_any,
    "not": _op_not,
    "equals": _op_equals,
    "in": _op_in,
    "gt": _op_gt,
    "lt": _op_lt,
    "gte": _op_gte,
    "lte": _op_lte,
    "matches_diagnosis": _op_matches_diagnosis,
    "diagnosis_excluded": _op_diagnosis_excluded,
    "days_since_join_lt": _op_days_since_join_lt,
    "category_in": _op_category_in,
    "category_not_in": _op_category_not_in,
    "claimed_amount_gt": _op_claimed_amount_gt,
    "high_value_test_in_doc": _op_high_value_test_in_doc,
    "prescription_present": _op_prescription_present,
    "category_requires_prescription": _op_category_requires_prescription,
    "category_covered": _op_category_covered,
}


# -- helpers -----------------------------------------------------------------


_PATH_RE = re.compile(r"^\$\{([a-zA-Z0-9_.]+)\}$")


def _resolve(value: Any, ctx: _Ctx) -> Any:
    """Resolve a literal or ``${policy.path}`` reference."""
    if isinstance(value, str):
        m = _PATH_RE.match(value)
        if m:
            return _walk_path(m.group(1), ctx)
        return value
    if isinstance(value, list):
        return [_resolve(v, ctx) for v in value]
    return value


def _walk_path(path: str, ctx: _Ctx) -> Any:
    parts = path.split(".")
    root_name, *rest = parts
    if root_name == "policy":
        cur: Any = ctx.policy.raw
    elif root_name == "state":
        cur = ctx.state
    else:
        return None
    for p in rest:
        if isinstance(cur, dict):
            cur = cur.get(p)
        else:
            cur = getattr(cur, p, None)
        if cur is None:
            return None
    return cur


def _doc_text_blob(extracted: list[ExtractedDocument]) -> str:
    parts: list[str] = []
    for doc in extracted:
        if doc.diagnosis:
            parts.append(doc.diagnosis)
        if doc.treatment:
            parts.append(doc.treatment)
        parts.extend(doc.tests_ordered)
        for li in doc.line_items:
            parts.append(li.description)
    return " | ".join(parts).lower()


def _make_result(rule: dict[str, Any], ctx: _Ctx, triggered: bool) -> RuleResult:
    """Build a RuleResult from a triggered/not-triggered rule.

    Convention: a "passed" finding is the *good* state for the claim.
    A rule fires (``triggered=True``) when its condition matched, which
    typically means a violation or constraint hit. So ``passed = not triggered``
    when ``action`` is REJECT/MANUAL_REVIEW. For positive rules (e.g. coverage
    confirmed), the rule sets ``inverse_pass`` so triggered → passed.
    """
    action = rule.get("action", "REJECT") if triggered else "PASS"
    inverse = rule.get("inverse_pass", False)
    if inverse:
        passed = triggered
    else:
        passed = not triggered

    severity = (
        rule.get("severity", "REJECT")
        if triggered and not inverse
        else "INFO"
    )

    if triggered:
        template = rule.get("reason_template") or rule.get("reason", rule["rule_id"])
    else:
        template = rule.get("pass_template", f"Rule {rule['rule_id']} passed")

    try:
        message = Template(template).safe_substitute(**ctx.template_vars, **ctx.evidence)
    except Exception:
        message = template

    return RuleResult(
        rule_id=rule["rule_id"],
        code=rule.get("code", rule["rule_id"]),
        passed=passed,
        action=action,
        severity=severity,
        message=message,
        evidence=dict(ctx.evidence),
        evidence_links=list(ctx.evidence_links),
    )


__all__ = ["DslRuleEngine", "RuleResult"]
