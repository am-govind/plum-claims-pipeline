"""Pre-authorization rules.

TC007: an MRI for ₹15,000 with no pre-auth must be rejected. Pre-auth is
required for high-value tests (MRI/CT/PET) above the threshold and for major
surgical procedures. The simulation has no claims database for prior
pre-auth, so the absence is detected from the submission shape (a flag could
be wired in later).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.claim import ClaimCategory, ExtractedDocument
from app.policy.loader import PolicyTerms


@dataclass
class PreAuthViolation:
    test_name: str
    threshold: float | None
    claimed_amount: float
    rule: str


def _category_high_value_tests(policy: PolicyTerms, category: ClaimCategory) -> list[str]:
    cfg = policy.opd_categories.get(category.value.lower(), {})
    return [t.lower() for t in cfg.get("high_value_tests_requiring_pre_auth", [])]


def _category_threshold(policy: PolicyTerms, category: ClaimCategory) -> float | None:
    cfg = policy.opd_categories.get(category.value.lower(), {})
    th = cfg.get("pre_auth_threshold")
    return float(th) if th is not None else None


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


def pre_auth_violation(
    policy: PolicyTerms,
    category: ClaimCategory,
    claimed_amount: float,
    extracted: list[ExtractedDocument],
    pre_auth_obtained: bool = False,
) -> PreAuthViolation | None:
    """Detect a missing pre-auth for high-value diagnostic tests or surgeries.

    The simulation defaults `pre_auth_obtained=False` because none of the test
    cases include a pre-auth record; in production we'd look it up.
    """
    if pre_auth_obtained:
        return None

    threshold = _category_threshold(policy, category)
    high_value = _category_high_value_tests(policy, category)
    if not high_value or threshold is None:
        return None

    blob = _doc_text_blob(extracted)
    matched = next((t for t in high_value if t in blob), None)
    if matched and claimed_amount > threshold:
        return PreAuthViolation(
            test_name=matched.upper(),
            threshold=threshold,
            claimed_amount=claimed_amount,
            rule=f"Pre-authorization required for {matched.upper()} above ₹{threshold:,.0f}",
        )
    return None
