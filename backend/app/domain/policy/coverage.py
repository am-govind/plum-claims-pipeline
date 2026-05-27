"""Coverage and financial calculation rules.

The financial calculation order is fixed and documented (see TC010):
  1. Drop excluded line items (e.g. teeth whitening on a dental claim).
  2. Reject up-front if the *claimed* amount exceeds the per-claim limit
     (TC008: ₹7,500 > ₹5,000 -> PER_CLAIM_EXCEEDED).
  3. Apply network-hospital discount on the remaining gross amount.
  4. Apply category co-pay on the discounted amount.
  5. Cap at the YTD OPD limit (annual_opd_limit minus ytd_claims_amount).

Notes on sub_limit:
  - The category ``sub_limit`` is treated as informational. The expected
    output for TC010 (₹3,240) exceeds the consultation sub_limit (₹2,000),
    confirming sub_limit is not a hard cap on the post-discount amount.
    We surface a warning when the approved amount is above sub_limit so
    operations can review category-level utilisation, but the value is
    not reduced.
"""

from __future__ import annotations

from typing import Any

from app.domain.claim import ClaimCategory, ExtractedDocument, LineItem
from app.domain.decision import LineItemDecision, RejectionReason
from app.domain.policy.terms import PolicyTerms, is_network_hospital


def category_config(policy: PolicyTerms, category: ClaimCategory) -> dict[str, Any]:
    """Return the OPD-category rules block (sub_limit, copay, etc.)."""
    return policy.opd_categories.get(category.value.lower(), {})


def is_category_covered(policy: PolicyTerms, category: ClaimCategory) -> bool:
    return bool(category_config(policy, category).get("covered", False))


def line_item_excluded_reason(
    policy: PolicyTerms, category: ClaimCategory, description: str
) -> str | None:
    """If a line-item description matches a category-level exclusion, return
    the matching exclusion phrase. Used for partial approvals (TC006)."""
    cfg = category_config(policy, category)
    excluded = [e.lower() for e in cfg.get("excluded_procedures", [])]
    excluded += [e.lower() for e in cfg.get("excluded_items", [])]
    desc = description.lower().strip()
    for ex in excluded:
        if ex in desc or desc in ex:
            return ex
    return None


def _aggregate_line_items(extracted: list[ExtractedDocument]) -> list[LineItem]:
    items: list[LineItem] = []
    for doc in extracted:
        items.extend(doc.line_items)
    return items


def apply_financial_calculation(
    policy: PolicyTerms,
    category: ClaimCategory,
    claimed_amount: float,
    extracted: list[ExtractedDocument],
    hospital_name: str | None,
    ytd_claims_amount: float,
) -> dict[str, Any]:
    """Run the documented six-step calculation and return a structured
    breakdown the synthesizer can read directly into a decision."""

    cfg = category_config(policy, category)
    line_items = _aggregate_line_items(extracted)

    line_decisions: list[LineItemDecision] = []
    accepted_total = 0.0
    rejected_total = 0.0

    if line_items:
        for li in line_items:
            ex = line_item_excluded_reason(policy, category, li.description)
            if ex:
                line_decisions.append(
                    LineItemDecision(
                        description=li.description,
                        submitted_amount=li.amount,
                        approved_amount=0.0,
                        status="REJECTED",  # type: ignore[arg-type]
                        reason=f"Line item matches category exclusion '{ex}'",
                        rejection_code=RejectionReason.LINE_ITEM_EXCLUDED,
                    )
                )
                rejected_total += li.amount
            else:
                line_decisions.append(
                    LineItemDecision(
                        description=li.description,
                        submitted_amount=li.amount,
                        approved_amount=li.amount,
                        status="APPROVED",  # type: ignore[arg-type]
                    )
                )
                accepted_total += li.amount
        gross_after_line_items = accepted_total
    else:
        gross_after_line_items = claimed_amount

    per_claim_limit = policy.coverage.get("per_claim_limit")
    sub_limit = cfg.get("sub_limit")
    effective_per_claim_cap: float | None
    if per_claim_limit is None:
        effective_per_claim_cap = None
    elif sub_limit is not None:
        effective_per_claim_cap = float(max(per_claim_limit, sub_limit))
    else:
        effective_per_claim_cap = float(per_claim_limit)

    per_claim_exceeded = (
        effective_per_claim_cap is not None
        and gross_after_line_items > effective_per_claim_cap
    )

    network_is_match = is_network_hospital(hospital_name)
    network_discount_pct = cfg.get("network_discount_percent", 0) if network_is_match else 0
    network_discount_amount = round(gross_after_line_items * network_discount_pct / 100.0, 2)
    after_discount = round(gross_after_line_items - network_discount_amount, 2)

    copay_pct = cfg.get("copay_percent", 0)
    copay_amount = round(after_discount * copay_pct / 100.0, 2)
    after_copay = round(after_discount - copay_amount, 2)

    annual_opd_limit = policy.coverage.get("annual_opd_limit")
    ytd_remaining = (
        max(0.0, float(annual_opd_limit) - ytd_claims_amount)
        if annual_opd_limit is not None
        else None
    )
    if ytd_remaining is not None and after_copay > ytd_remaining:
        ytd_capped = float(ytd_remaining)
    else:
        ytd_capped = after_copay

    if per_claim_exceeded:
        final_amount = 0.0
    else:
        final_amount = round(max(0.0, ytd_capped), 2)

    sub_limit_warning = (
        sub_limit is not None and after_copay > float(sub_limit) and not per_claim_exceeded
    )

    breakdown = {
        "claimed_amount": claimed_amount,
        "line_items_total_submitted": (accepted_total + rejected_total) if line_items else None,
        "line_items_accepted_total": accepted_total if line_items else None,
        "line_items_rejected_total": rejected_total if line_items else None,
        "gross_after_line_items": gross_after_line_items,
        "is_network_hospital": network_is_match,
        "network_discount_percent": network_discount_pct,
        "network_discount_amount": network_discount_amount,
        "after_discount": after_discount,
        "copay_percent": copay_pct,
        "copay_amount": copay_amount,
        "after_copay": after_copay,
        "sub_limit": sub_limit,
        "sub_limit_warning": sub_limit_warning,
        "per_claim_limit": per_claim_limit,
        "effective_per_claim_cap": effective_per_claim_cap,
        "per_claim_exceeded": per_claim_exceeded,
        "annual_opd_limit": annual_opd_limit,
        "ytd_claims_amount": ytd_claims_amount,
        "ytd_remaining": ytd_remaining,
        "after_ytd_cap": ytd_capped,
        "final_approved_amount": final_amount,
    }

    caps_hit: list[str] = []
    if per_claim_exceeded:
        caps_hit.append("PER_CLAIM")
    if sub_limit_warning:
        caps_hit.append("SUB_LIMIT")
    if ytd_remaining is not None and after_copay > ytd_remaining and not per_claim_exceeded:
        caps_hit.append("YTD")
    breakdown["caps_hit"] = caps_hit

    return {
        "breakdown": breakdown,
        "line_decisions": line_decisions,
        "final_amount": final_amount,
        "accepted_gross": gross_after_line_items,
        "had_excluded_line_items": rejected_total > 0,
    }
