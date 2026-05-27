"""Markdown eval report generator.

Walks every case result and writes a human-readable report with the
expected vs actual decision, the user-facing message, and the full trace.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


def _aggregate_metrics_block(results: list[dict[str, Any]]) -> list[str]:
    """Roll up per-case metrics into eval-suite-level numbers.

    Reported:
    - Pipeline latency P50 / P95 (ms)
    - Token / cost totals
    - Extraction confidence histogram (10 buckets, 0.0-1.0)
    - Validation issue count (a hallucination proxy)
    - Rule coverage matrix (which rule_ids fired in which cases)
    """
    lines: list[str] = ["## Aggregate metrics", ""]

    latencies = [r.get("metrics", {}).get("total_latency_ms", 0) for r in results]
    if latencies:
        sorted_l = sorted(latencies)
        p50 = sorted_l[len(sorted_l) // 2]
        p95 = sorted_l[max(0, int(len(sorted_l) * 0.95) - 1)]
        avg = sum(sorted_l) // len(sorted_l)
        lines.append(
            f"- **Latency**: P50 = {p50} ms · P95 = {p95} ms · avg = {avg} ms · "
            f"median = {int(median(sorted_l))} ms"
        )

    tokens_in = sum(r.get("metrics", {}).get("tokens_in", 0) for r in results)
    tokens_out = sum(r.get("metrics", {}).get("tokens_out", 0) for r in results)
    usd = sum(r.get("metrics", {}).get("usd_estimate", 0) for r in results)
    lines.append(
        f"- **Tokens**: {tokens_in:,} in + {tokens_out:,} out = {tokens_in + tokens_out:,} "
        f"total · est. cost ≈ ${usd:.6f}"
    )

    issue_count = sum(
        r.get("metrics", {}).get("validation_issue_count", 0) for r in results
    )
    lines.append(
        f"- **Extraction validation issues** (hallucination proxy): {issue_count} "
        f"across {sum(1 for r in results if r.get('metrics', {}).get('validation_issue_count'))} cases"
    )

    contradictions = sum(
        len(r.get("metrics", {}).get("contradictions", [])) for r in results
    )
    lines.append(f"- **Cross-document contradictions detected**: {contradictions}")

    deliberations = sum(
        sum(r.get("metrics", {}).get("deliberation_iterations", {}).values())
        for r in results
    )
    lines.append(f"- **Deliberation cycles triggered**: {deliberations}")

    confs: list[float] = []
    for r in results:
        confs.extend(r.get("metrics", {}).get("extraction_confidences", []))
    if confs:
        buckets = [0] * 10
        for c in confs:
            idx = min(9, max(0, int(c * 10)))
            buckets[idx] += 1
        lines.append("")
        lines.append("### Extraction confidence histogram")
        lines.append("")
        lines.append("| Bucket | Count |")
        lines.append("| --- | --- |")
        for i, n in enumerate(buckets):
            lo = i / 10
            hi = (i + 1) / 10
            lines.append(f"| [{lo:.1f}, {hi:.1f}) | {'█' * n} {n} |")

    rule_to_cases: dict[str, list[str]] = {}
    for r in results:
        for rid in r.get("metrics", {}).get("fired_rules", []):
            rule_to_cases.setdefault(rid, []).append(r["case_id"])
    if rule_to_cases:
        lines.append("")
        lines.append("### Rule coverage matrix (rules that fired in each case)")
        lines.append("")
        lines.append("| Rule | Fired in | Count |")
        lines.append("| --- | --- | --- |")
        for rid, cases in sorted(rule_to_cases.items()):
            lines.append(f"| `{rid}` | {', '.join(cases)} | {len(cases)} |")
    else:
        lines.append("")
        lines.append("_No policy rules fired in this run._")

    status_counts = Counter(
        (r["decision"] or {}).get("status", "EARLY_STOP") for r in results
    )
    lines.append("")
    lines.append("### Decision status distribution")
    lines.append("")
    for s, n in sorted(status_counts.items()):
        lines.append(f"- {s}: {n}")

    return lines


def _trace_block(trace: list[dict[str, Any]]) -> str:
    lines = []
    for t in trace:
        ev = json.dumps(t.get("evidence", {}), indent=2, default=str)
        err = f"\n  - error: `{t['error']}`" if t.get("error") else ""
        lines.append(
            f"- **{t['step']}** — `{t['status']}` ({t.get('latency_ms', 0)}ms): "
            f"{t['summary']}{err}\n  ```json\n{ev}\n  ```"
        )
    return "\n".join(lines)


def _decision_block(decision: dict[str, Any] | None) -> str:
    if decision is None:
        return "_(no decision; pipeline halted early)_"
    return (
        f"- Status: **{decision['status']}**\n"
        f"- Approved: ₹{decision['approved_amount']:.2f} of ₹{decision['submitted_amount']:.2f}\n"
        f"- Confidence: {decision['confidence']}\n"
        f"- Rejection reasons: {decision.get('rejection_reasons') or '—'}\n"
        f"- Summary: {decision['summary']}\n"
        f"- User message: {decision['user_message']}\n"
        f"- Degraded: {decision.get('degraded', False)}, "
        f"failed components: {decision.get('failed_components') or '—'}\n"
    )


def write_markdown_report(results: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    ts = datetime.now(timezone.utc).isoformat()
    lines = [
        "# Eval Report",
        "",
        f"_Generated: {ts}_",
        "",
        f"**Summary**: {passed}/{total} cases passed.",
        "",
        "| Case | Name | Expected | Got | Approved | Confidence | Latency | Tokens | Result |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in results:
        expected = r["expected"].get("decision") or "EARLY_STOP"
        got = (r["decision"] or {}).get("status") if r["decision"] else "EARLY_STOP"
        approved = (r["decision"] or {}).get("approved_amount", "—") if r["decision"] else "—"
        confidence = (r["decision"] or {}).get("confidence", "—") if r["decision"] else r.get("confidence", "—")
        m = r.get("metrics", {})
        latency = f"{m.get('total_latency_ms', 0)} ms"
        tokens = (m.get("tokens_in", 0) or 0) + (m.get("tokens_out", 0) or 0)
        result = "PASS" if r["passed"] else "FAIL"
        lines.append(
            f"| {r['case_id']} | {r['case_name']} | {expected} | {got} | {approved} | {confidence} | {latency} | {tokens} | {result} |"
        )
    lines.append("")
    lines.extend(_aggregate_metrics_block(results))
    lines.append("")
    for r in results:
        lines.append(f"## {r['case_id']} — {r['case_name']}")
        lines.append("")
        lines.append(f"**Result**: {'PASS' if r['passed'] else 'FAIL'}")
        if r["issues"]:
            lines.append("")
            lines.append("**Mismatches**:")
            for i in r["issues"]:
                lines.append(f"- {i}")
        lines.append("")
        lines.append("**Expected**:")
        lines.append("```json")
        lines.append(json.dumps(r["expected"], indent=2))
        lines.append("```")
        lines.append("")
        lines.append("**Decision (actual)**:")
        lines.append(_decision_block(r["decision"]))
        if r.get("early_stop"):
            lines.append(
                f"**Early stop**: `{r.get('early_stop_reason')}` — "
                f"_{r.get('early_stop_user_message')}_"
            )
            lines.append("")
        lines.append("**system_must checks**:")
        for m in r.get("system_must_results", []):
            mark = "x" if m["satisfied"] else " "
            lines.append(f"- [{mark}] {m['requirement']}")
        lines.append("")
        lines.append("**Trace**:")
        lines.append(_trace_block(r["trace"]))
        lines.append("")
        lines.append("---")
        lines.append("")
    path.write_text("\n".join(lines))
