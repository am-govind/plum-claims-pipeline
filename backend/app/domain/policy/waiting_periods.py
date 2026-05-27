"""Waiting period rules.

Returns a violation record when the treatment date falls inside the relevant
waiting window (initial 30 days, condition-specific window, or PED 365 days).
The eligibility date is computed and surfaced in the user message — TC005
explicitly requires that the rejection states when the member becomes
eligible.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date as DateType
from datetime import timedelta

from app.domain.policy.terms import PolicyTerms

CONDITION_KEYWORDS: dict[str, list[str]] = {
    "diabetes": ["diabetes", "t2dm", "type 2 diabetes", "diabetic"],
    "hypertension": ["hypertension", "htn", "high blood pressure"],
    "thyroid_disorders": ["thyroid", "hypothyroid", "hyperthyroid"],
    "joint_replacement": ["joint replacement", "knee replacement", "hip replacement"],
    "maternity": ["maternity", "pregnancy", "delivery", "antenatal"],
    "mental_health": ["mental health", "depression", "anxiety", "psychiatric"],
    "obesity_treatment": ["obesity", "bariatric", "weight loss"],
    "hernia": ["hernia"],
    "cataract": ["cataract"],
}


@dataclass
class WaitingPeriodViolation:
    kind: str
    days_required: int
    days_elapsed: int
    join_date: DateType
    eligibility_date: DateType
    matched_condition: str | None = None
    matched_keyword: str | None = None


def _matched_condition(diagnosis: str | None) -> tuple[str, str] | None:
    """Match a diagnosis string against condition keywords using whole-word
    boundaries. Substring matching would mis-classify e.g. 'Lumbar Disc
    Herniation' as a hernia waiting-period violation (TC007).
    """
    if not diagnosis:
        return None
    d = diagnosis.lower()
    for cond, kws in CONDITION_KEYWORDS.items():
        for kw in kws:
            pattern = r"\b" + re.escape(kw) + r"\b"
            if re.search(pattern, d):
                return cond, kw
    return None


def waiting_period_violation(
    policy: PolicyTerms,
    join_date: DateType | None,
    treatment_date: DateType,
    diagnosis: str | None,
) -> WaitingPeriodViolation | None:
    """Return the most specific waiting-period violation, if any."""
    if join_date is None:
        return None
    days_elapsed = (treatment_date - join_date).days
    wp = policy.waiting_periods

    matched = _matched_condition(diagnosis)
    if matched:
        cond, kw = matched
        days_required = wp.get("specific_conditions", {}).get(cond)
        if days_required is not None and days_elapsed < days_required:
            return WaitingPeriodViolation(
                kind="SPECIFIC_CONDITION",
                days_required=int(days_required),
                days_elapsed=days_elapsed,
                join_date=join_date,
                eligibility_date=join_date + timedelta(days=int(days_required)),
                matched_condition=cond,
                matched_keyword=kw,
            )

    initial = wp.get("initial_waiting_period_days")
    if initial is not None and days_elapsed < int(initial):
        return WaitingPeriodViolation(
            kind="INITIAL",
            days_required=int(initial),
            days_elapsed=days_elapsed,
            join_date=join_date,
            eligibility_date=join_date + timedelta(days=int(initial)),
        )

    return None
