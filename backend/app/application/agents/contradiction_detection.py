"""Cross-Document Contradiction Detection.

Runs after extraction, before policy adjudication. Checks for
inconsistencies *across* documents that any single doc can't catch:

1. patient name consistency (fuzzy)
2. treatment date sanity (all extracted dates within ±7 days of submitted)
3. hospital name consistency (when ≥2 docs name a hospital)
4. amount reconciliation (sum of line items vs bill total vs claimed)
5. diagnosis ↔ treatment compatibility (lightweight allowlist)

Each contradiction lowers confidence and is recorded onto
``state.contradictions``. None of the 12 fixture cases trigger these
(intentional contradictions in TC003 are caught upstream by document
verification), so this agent stays silent on the standard eval.
"""

from __future__ import annotations

from datetime import datetime
from datetime import date as DateType

from rapidfuzz import fuzz

from app.application.agents.base import BaseAgent
from app.domain.claim import ClaimState
from app.domain.decision import AgentResult
from app.domain.evidence import Contradiction, EvidenceLink
from app.domain.trace import TraceStatus

PATIENT_NAME_THRESHOLD = 80
HOSPITAL_NAME_THRESHOLD = 75
DATE_TOLERANCE_DAYS = 7
AMOUNT_TOLERANCE_PCT = 0.05  # 5%

DIAG_TX_ALLOWLIST: dict[str, list[str]] = {
    "fever": ["paracetamol", "azithromycin", "consultation", "blood test"],
    "diabetes": ["metformin", "glimepiride", "insulin", "hba1c", "glucose"],
    "hypertension": ["amlodipine", "telmisartan", "blood pressure"],
    "cardiac": ["ecg", "stent", "cardiac", "atorvastatin", "ecg report"],
    "fracture": ["x-ray", "cast", "orthopaedic", "physiotherapy"],
    "consultation": ["consultation", "consult"],
    "hernia": ["hernia"],
    "obesity": ["bariatric", "diet", "obesity"],
    "lumbar": ["mri", "ct scan", "spine"],
    "viral": ["paracetamol", "consult"],
    "infection": ["antibiotic", "azithromycin", "amoxicillin"],
}


class ContradictionDetectionAgent(BaseAgent):
    name = "contradiction_detection"
    is_critical = False

    async def run(self, state: ClaimState) -> ClaimState:
        rec = self.recorder(state)
        with rec.time_step(self.name) as ctx:
            contradictions: list[Contradiction] = []
            contradictions += _check_patient_names(state)
            contradictions += _check_dates(state)
            contradictions += _check_hospital_names(state)
            contradictions += _check_amounts(state)
            contradictions += _check_diagnosis_treatment(state)

            state.contradictions.extend(contradictions)

            n = len(contradictions)
            if n == 0:
                rec.record(
                    self.name,
                    status=TraceStatus.OK,
                    summary="No cross-document contradictions detected",
                    evidence={
                        "patient_names": list(_unique_patient_names(state)),
                        "hospital_names": list(_unique_hospital_names(state)),
                    },
                    latency_ms=ctx["latency_ms"],
                )
            else:
                rec.record(
                    self.name,
                    status=TraceStatus.WARNING,
                    summary=f"{n} cross-document contradiction(s) detected",
                    evidence={
                        "contradictions": [
                            {"kind": c.kind, "description": c.description}
                            for c in contradictions
                        ],
                    },
                    latency_ms=ctx["latency_ms"],
                )

            score = min(1.0, n * 0.25)
            state.agent_results[self.name] = AgentResult(
                confidence=max(0.0, 1.0 - score),
                evidence_strength=1.0,
                contradiction_score=score,
                notes=[c.kind for c in contradictions],
            )
        return state


# ---------------------------------------------------------------------------
# checks
# ---------------------------------------------------------------------------


def _check_patient_names(state: ClaimState) -> list[Contradiction]:
    names = [
        (d.file_id, d.patient_name) for d in state.extracted if d.patient_name
    ]
    if len(names) < 2:
        return []
    base_id, base_name = names[0]
    for fid, n in names[1:]:
        if fuzz.token_sort_ratio(base_name.lower(), n.lower()) < PATIENT_NAME_THRESHOLD:
            return [
                Contradiction(
                    kind="PATIENT_NAME_INCONSISTENT",
                    description=(
                        f"Patient name varies across documents: '{base_name}' "
                        f"({base_id}) vs '{n}' ({fid})"
                    ),
                    severity="REJECT",
                    evidence=[
                        EvidenceLink(source_file_id=base_id, snippet=base_name),
                        EvidenceLink(source_file_id=fid, snippet=n),
                    ],
                )
            ]
    return []


def _check_dates(state: ClaimState) -> list[Contradiction]:
    submitted = state.input.treatment_date
    out: list[Contradiction] = []
    for doc in state.extracted:
        if not doc.document_date:
            continue
        try:
            d = _parse_loose_date(doc.document_date)
        except ValueError:
            continue
        delta = abs((d - submitted).days)
        if delta > DATE_TOLERANCE_DAYS:
            out.append(
                Contradiction(
                    kind="DATE_DISCREPANCY",
                    description=(
                        f"Document {doc.file_id} dated {doc.document_date} "
                        f"is {delta} days from submitted treatment date {submitted}"
                    ),
                    severity="WARNING",
                    evidence=[
                        EvidenceLink(
                            source_file_id=doc.file_id,
                            field_path="document_date",
                            snippet=doc.document_date,
                        )
                    ],
                )
            )
    return out


def _check_hospital_names(state: ClaimState) -> list[Contradiction]:
    names = [
        (d.file_id, d.hospital_name) for d in state.extracted if d.hospital_name
    ]
    if len(names) < 2:
        return []
    base_id, base_name = names[0]
    for fid, n in names[1:]:
        if fuzz.token_set_ratio(base_name.lower(), n.lower()) < HOSPITAL_NAME_THRESHOLD:
            return [
                Contradiction(
                    kind="HOSPITAL_NAME_INCONSISTENT",
                    description=(
                        f"Hospital name varies across documents: '{base_name}' "
                        f"({base_id}) vs '{n}' ({fid})"
                    ),
                    severity="WARNING",
                    evidence=[
                        EvidenceLink(source_file_id=base_id, snippet=base_name),
                        EvidenceLink(source_file_id=fid, snippet=n),
                    ],
                )
            ]
    return []


def _check_amounts(state: ClaimState) -> list[Contradiction]:
    out: list[Contradiction] = []
    for doc in state.extracted:
        if doc.total_amount is None or not doc.line_items:
            continue
        line_sum = round(sum(li.amount for li in doc.line_items), 2)
        bill_total = round(doc.total_amount, 2)
        if bill_total <= 0:
            continue
        diff = abs(line_sum - bill_total) / bill_total
        if diff > AMOUNT_TOLERANCE_PCT:
            out.append(
                Contradiction(
                    kind="AMOUNT_RECONCILIATION_FAILED",
                    description=(
                        f"Document {doc.file_id}: line items sum to ₹{line_sum:,.2f} "
                        f"but bill total is ₹{bill_total:,.2f}"
                    ),
                    severity="REJECT",
                    evidence=[
                        EvidenceLink(
                            source_file_id=doc.file_id,
                            field_path="line_items",
                            snippet=f"sum={line_sum} vs total={bill_total}",
                        )
                    ],
                )
            )

    claimed = state.input.claimed_amount
    bill_totals = [d.total_amount for d in state.extracted if d.total_amount is not None]
    if bill_totals and claimed > 0:
        max_bill = max(bill_totals)
        if claimed > max_bill * (1 + AMOUNT_TOLERANCE_PCT):
            out.append(
                Contradiction(
                    kind="CLAIMED_EXCEEDS_BILLS",
                    description=(
                        f"Claimed ₹{claimed:,.2f} exceeds the highest bill total "
                        f"of ₹{max_bill:,.2f} found across documents"
                    ),
                    severity="WARNING",
                )
            )
    return out


def _check_diagnosis_treatment(state: ClaimState) -> list[Contradiction]:
    diag_blob = " ".join(
        (d.diagnosis or "") + " " + (d.treatment or "") for d in state.extracted
    ).lower()
    rx_or_tests: list[str] = []
    for d in state.extracted:
        rx_or_tests.extend(d.medicines)
        rx_or_tests.extend(d.tests_ordered)
        for li in d.line_items:
            rx_or_tests.append(li.description)
    rx_blob = " ".join(rx_or_tests).lower()

    if not diag_blob.strip() or not rx_blob.strip():
        return []

    matched = False
    for diag_kw, allowed in DIAG_TX_ALLOWLIST.items():
        if diag_kw in diag_blob:
            if any(t in rx_blob for t in allowed):
                matched = True
            break
    else:
        return []

    if matched:
        return []
    return [
        Contradiction(
            kind="DIAGNOSIS_TREATMENT_MISMATCH",
            description=(
                "Diagnosis does not appear consistent with prescribed "
                "medicines/tests/line items based on standard clinical patterns"
            ),
            severity="WARNING",
            confidence=0.6,
        )
    ]


def _unique_patient_names(state: ClaimState) -> set[str]:
    return {d.patient_name for d in state.extracted if d.patient_name}


def _unique_hospital_names(state: ClaimState) -> set[str]:
    return {d.hospital_name for d in state.extracted if d.hospital_name}


def _parse_loose_date(s: str) -> DateType:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unparseable date: {s}")
