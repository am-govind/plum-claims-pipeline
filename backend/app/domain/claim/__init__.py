"""Domain models for the claim being processed.

`ClaimState` is the single object that flows through the LangGraph pipeline.
Each agent reads what it needs and appends to the same state object so the
final trace is a complete record of how the decision was reached.
"""

from __future__ import annotations

from datetime import date as DateType
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ClaimCategory(str, Enum):
    CONSULTATION = "CONSULTATION"
    DIAGNOSTIC = "DIAGNOSTIC"
    PHARMACY = "PHARMACY"
    DENTAL = "DENTAL"
    VISION = "VISION"
    ALTERNATIVE_MEDICINE = "ALTERNATIVE_MEDICINE"


class DocumentType(str, Enum):
    PRESCRIPTION = "PRESCRIPTION"
    HOSPITAL_BILL = "HOSPITAL_BILL"
    PHARMACY_BILL = "PHARMACY_BILL"
    LAB_REPORT = "LAB_REPORT"
    DIAGNOSTIC_REPORT = "DIAGNOSTIC_REPORT"
    DISCHARGE_SUMMARY = "DISCHARGE_SUMMARY"
    DENTAL_REPORT = "DENTAL_REPORT"
    UNKNOWN = "UNKNOWN"


class DocumentQuality(str, Enum):
    GOOD = "GOOD"
    ACCEPTABLE = "ACCEPTABLE"
    POOR = "POOR"
    UNREADABLE = "UNREADABLE"


class LineItem(BaseModel):
    description: str
    amount: float


MAX_BYTES_B64_LEN = 14_000_000
"""Roughly 10 MB of decoded payload (base64 inflates by ~33%). Bigger than
any real phone photo, small enough that a runaway upload can't OOM the
extraction provider before it even reaches Gemini."""


class DocumentInput(BaseModel):
    """A document as submitted by the member or a test fixture.

    `actual_type`, `quality`, `patient_name_on_doc`, and pre-extracted `content`
    can be supplied directly by tests; in production these are derived by the
    extraction agent. Either way, the verification agent reads them off the
    same object.
    """

    model_config = ConfigDict(extra="allow")

    file_id: str
    file_name: str | None = None
    actual_type: DocumentType = DocumentType.UNKNOWN
    quality: DocumentQuality = DocumentQuality.GOOD
    patient_name_on_doc: str | None = None
    content: dict[str, Any] | None = None
    bytes_b64: str | None = None
    mime_type: str | None = None

    @field_validator("bytes_b64")
    @classmethod
    def _bytes_b64_within_limit(cls, v: str | None) -> str | None:
        if v is not None and len(v) > MAX_BYTES_B64_LEN:
            raise ValueError(
                f"bytes_b64 too large: {len(v)} chars (max {MAX_BYTES_B64_LEN}, "
                "~10 MB decoded). Compress the image client-side or split the PDF."
            )
        return v


class ExtractedDocument(BaseModel):
    """The structured payload produced by the extraction agent."""

    file_id: str
    document_type: DocumentType
    quality: DocumentQuality = DocumentQuality.GOOD
    patient_name: str | None = None
    doctor_name: str | None = None
    doctor_registration: str | None = None
    diagnosis: str | None = None
    treatment: str | None = None
    medicines: list[str] = Field(default_factory=list)
    tests_ordered: list[str] = Field(default_factory=list)
    hospital_name: str | None = None
    bill_number: str | None = None
    document_date: str | None = None
    line_items: list[LineItem] = Field(default_factory=list)
    total_amount: float | None = None
    extraction_confidence: float = 1.0
    raw: dict[str, Any] = Field(default_factory=dict)
    validation_issues: list[str] = Field(default_factory=list)


class ClaimsHistoryEntry(BaseModel):
    claim_id: str
    date: str
    amount: float
    provider: str | None = None


class ClaimInput(BaseModel):
    """The submission payload."""

    member_id: str
    policy_id: str
    claim_category: ClaimCategory
    treatment_date: DateType
    claimed_amount: float
    hospital_name: str | None = None
    ytd_claims_amount: float = 0.0
    claims_history: list[ClaimsHistoryEntry] = Field(default_factory=list)
    documents: list[DocumentInput] = Field(default_factory=list)
    simulate_component_failure: bool = False


class ClaimState(BaseModel):
    """The single mutable object passed through the LangGraph pipeline."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    claim_id: str
    input: ClaimInput
    extracted: list[ExtractedDocument] = Field(default_factory=list)
    findings: list["PolicyFinding"] = Field(default_factory=list)
    line_decisions: list["LineItemDecision"] = Field(default_factory=list)
    fraud_signals: list[str] = Field(default_factory=list)
    contradictions: list["Contradiction"] = Field(default_factory=list)
    agent_results: dict[str, "AgentResult"] = Field(default_factory=dict)
    cost: "CostBreakdown" = Field(default_factory=lambda: _new_cost())
    trace: list["TraceStep"] = Field(default_factory=list)
    degraded: bool = False
    failed_components: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    early_stop: bool = False
    early_stop_reason: str | None = None
    early_stop_user_message: str | None = None
    deliberation_iterations: dict[str, int] = Field(default_factory=dict)
    decision: Optional["Decision"] = None
    pending_events: list["DomainEvent"] = Field(default_factory=list, exclude=True)
    """Domain events recorded during this run. Excluded from serialisation
    so the persisted JSON stays clean; drained via :meth:`pull_events`
    after the pipeline completes."""

    def record_event(self, event: "DomainEvent") -> None:
        """Buffer a domain event for the application layer to dispatch."""
        self.pending_events.append(event)

    def pull_events(self) -> list["DomainEvent"]:
        """Return all recorded events and clear the buffer (idempotent)."""
        events = list(self.pending_events)
        self.pending_events.clear()
        return events

    def halt_early(self, reason: str, user_message: str) -> None:
        """Mark this claim as halted before the synthesizer runs.

        Sets the three early-stop fields and records a `ClaimHaltedEarly`
        domain event in one atomic step. Agents must use this instead of
        poking the fields directly so the event can never be forgotten
        and the field set can never drift apart.
        """
        from app.domain.events import ClaimHaltedEarly

        self.early_stop = True
        self.early_stop_reason = reason
        self.early_stop_user_message = user_message
        self.record_event(
            ClaimHaltedEarly(
                claim_id=self.claim_id,
                reason=reason,
                user_message=user_message,
            )
        )


def _new_cost() -> "CostBreakdown":
    from app.domain.cost import CostBreakdown

    return CostBreakdown()


from app.domain.cost import CostBreakdown
from app.domain.decision import AgentResult, Decision, LineItemDecision, PolicyFinding
from app.domain.events import DomainEvent
from app.domain.evidence import Contradiction
from app.domain.trace import TraceStep

ClaimState.model_rebuild()

from app.domain.claim.summary import ClaimSummary  # noqa: E402,F401  (re-export)
