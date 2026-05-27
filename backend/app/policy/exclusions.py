"""Diagnosis / treatment exclusions (claim-level, not line-item level)."""

from __future__ import annotations

from app.policy.loader import PolicyTerms

OBESITY_TRIGGERS = {
    "obesity",
    "morbid obesity",
    "bariatric",
    "weight loss",
    "weight-loss",
    "diet program",
    "diet and nutrition",
    "weight management",
}


def diagnosis_excluded_reason(
    policy: PolicyTerms, diagnosis: str | None, treatment: str | None = None
) -> str | None:
    """Return the matching exclusion phrase if the diagnosis or treatment is
    explicitly excluded. Used for TC012 (bariatric / obesity treatment).
    """
    haystack_parts = [p for p in [diagnosis, treatment] if p]
    if not haystack_parts:
        return None
    haystack = " | ".join(haystack_parts).lower()

    for excl in policy.exclusions.get("conditions", []):
        if _phrase_match(excl, haystack):
            return excl

    if any(t in haystack for t in OBESITY_TRIGGERS):
        for excl in policy.exclusions.get("conditions", []):
            if "obesity" in excl.lower() or "bariatric" in excl.lower():
                return excl

    return None


def _phrase_match(excl: str, haystack: str) -> bool:
    """Loose phrase match: split exclusion into words, see if all key tokens
    appear in haystack. Avoids false positives on common stop-words.
    """
    excl_l = excl.lower()
    if excl_l in haystack:
        return True
    stop = {"and", "or", "the", "of", "non-medically", "necessary"}
    tokens = [t for t in excl_l.replace("(", " ").replace(")", " ").split() if t not in stop]
    if not tokens:
        return False
    return all(t in haystack for t in tokens)
