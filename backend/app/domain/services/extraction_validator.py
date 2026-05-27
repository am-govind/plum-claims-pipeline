"""Post-extraction deterministic validator.

Given an ``ExtractedDocument`` produced by the LLM, run cheap rule-based
checks that can catch hallucinations or extraction inconsistencies before
they propagate to policy adjudication. Each failed check is appended to
``ExtractedDocument.validation_issues`` and lowers ``extraction_confidence``.

Why not use the LLM to self-check? Two reasons: (1) the LLM is the very
component we're validating, so a separate deterministic layer is more
trustworthy; (2) these checks are cheap and reasoning-free — regex + math.
"""

from __future__ import annotations

import re
from datetime import date as DateType
from datetime import datetime, timedelta

from app.domain.claim import DocumentType, ExtractedDocument

# Indian medical-council registration patterns drawn from
# `sample_documents_guide.md`. These are conservative — we prefer to flag
# odd-looking numbers rather than wave them through, but we never reject
# the whole claim on this signal alone.
DOCTOR_REG_PATTERNS = [
    re.compile(r"^[A-Z]{2}/\d{4,6}/\d{4}$"),
    re.compile(r"^[A-Z]{2,4}-\d{4,6}/\d{4}$"),
    re.compile(r"^[A-Z]{2,4}\d{4,6}$"),
    re.compile(r"^AYUR/[A-Z]{2}/\d{4,6}/\d{4}$"),
]

CONFIDENCE_PENALTY_PER_ISSUE = 0.15


def validate_extraction(doc: ExtractedDocument) -> list[str]:
    """Return a list of human-readable validation issues found on `doc`.

    Mutates the input only via ``validation_issues`` and
    ``extraction_confidence`` (lowered by 0.15 per issue, floored at 0).
    """
    issues: list[str] = []

    # 1. bill total reconciliation: line-item sum within ±1% of total
    if doc.total_amount is not None and doc.line_items:
        line_sum = round(sum(li.amount for li in doc.line_items), 2)
        bill_total = round(doc.total_amount, 2)
        if bill_total > 0 and abs(line_sum - bill_total) / bill_total > 0.01:
            issues.append(
                f"line item sum (₹{line_sum:,.2f}) differs from bill total "
                f"(₹{bill_total:,.2f}) by more than 1%"
            )

    # 2. Document date sanity: present + within last 730 days
    if doc.document_date:
        parsed = _parse_date(doc.document_date)
        if parsed is None:
            issues.append(f"unparseable document_date: {doc.document_date!r}")
        else:
            today = DateType.today()
            if parsed > today + timedelta(days=1):
                issues.append(f"document_date {parsed} is in the future")
            elif parsed < today - timedelta(days=730):
                issues.append(f"document_date {parsed} is older than 2 years")

    # 3. Doctor registration regex: not strictly enforced, but flagged
    if doc.doctor_registration:
        reg = doc.doctor_registration.strip().upper()
        if not any(pat.match(reg) for pat in DOCTOR_REG_PATTERNS):
            issues.append(
                f"doctor_registration '{doc.doctor_registration}' does not match "
                "known Indian medical-council patterns"
            )

    # 4. Negative amount check
    if doc.total_amount is not None and doc.total_amount < 0:
        issues.append(f"total_amount is negative: {doc.total_amount}")
    for li in doc.line_items:
        if li.amount < 0:
            issues.append(f"line item '{li.description}' has negative amount {li.amount}")

    # 5. patient_name presence on documents that always have one
    needs_patient = {
        DocumentType.PRESCRIPTION,
        DocumentType.HOSPITAL_BILL,
        DocumentType.LAB_REPORT,
        DocumentType.DIAGNOSTIC_REPORT,
        DocumentType.PHARMACY_BILL,
        DocumentType.DISCHARGE_SUMMARY,
    }
    if doc.document_type in needs_patient and not doc.patient_name:
        issues.append(
            f"patient_name missing on {doc.document_type.value} (expected on this doc type)"
        )

    if issues:
        doc.validation_issues = issues
        new_conf = doc.extraction_confidence - CONFIDENCE_PENALTY_PER_ISSUE * len(issues)
        doc.extraction_confidence = max(0.0, round(new_conf, 4))
    return issues


def _parse_date(s: str) -> DateType | None:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None
