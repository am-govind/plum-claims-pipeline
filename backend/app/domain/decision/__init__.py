"""Decision and finding models."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.domain.cost import CostBreakdown
from app.domain.decision.agent_result import AgentResult
from app.domain.decision.explanation import DecisionNode
from app.domain.evidence import EvidenceLink


class DecisionStatus(str, Enum):
    APPROVED = "APPROVED"
    PARTIAL = "PARTIAL"
    REJECTED = "REJECTED"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    NEEDS_REUPLOAD = "NEEDS_REUPLOAD"
    NEEDS_CORRECTION = "NEEDS_CORRECTION"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    ESCALATED_MEDICAL_REVIEW = "ESCALATED_MEDICAL_REVIEW"
    FRAUD_INVESTIGATION = "FRAUD_INVESTIGATION"


class RejectionReason(str, Enum):
    WAITING_PERIOD = "WAITING_PERIOD"
    EXCLUDED_CONDITION = "EXCLUDED_CONDITION"
    PRE_AUTH_MISSING = "PRE_AUTH_MISSING"
    PER_CLAIM_EXCEEDED = "PER_CLAIM_EXCEEDED"
    SUB_LIMIT_EXCEEDED = "SUB_LIMIT_EXCEEDED"
    YTD_LIMIT_EXCEEDED = "YTD_LIMIT_EXCEEDED"
    SUBMISSION_DEADLINE = "SUBMISSION_DEADLINE"
    BELOW_MIN_CLAIM = "BELOW_MIN_CLAIM"
    CATEGORY_NOT_COVERED = "CATEGORY_NOT_COVERED"
    LINE_ITEM_EXCLUDED = "LINE_ITEM_EXCLUDED"
    PRESCRIPTION_MISSING = "PRESCRIPTION_MISSING"
    GENERIC_DRUG_VIOLATION = "GENERIC_DRUG_VIOLATION"


class PolicyFinding(BaseModel):
    """A single rule outcome from policy adjudication.

    `passed=False` does not by itself reject a claim — the synthesizer
    aggregates findings into a final decision so multiple findings can be
    surfaced together.
    """

    code: str
    passed: bool
    message: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    evidence_links: list[EvidenceLink] = Field(default_factory=list)
    severity: str = "INFO"
    rule_id: str | None = None


class LineItemDecision(BaseModel):
    description: str
    submitted_amount: float
    approved_amount: float
    status: DecisionStatus
    reason: str | None = None
    rejection_code: RejectionReason | None = None


class Decision(BaseModel):
    """Final decision record returned by the synthesizer."""

    status: DecisionStatus
    approved_amount: float = 0.0
    submitted_amount: float = 0.0
    rejection_reasons: list[RejectionReason] = Field(default_factory=list)
    confidence: float = 1.0
    summary: str
    user_message: str
    notes: list[str] = Field(default_factory=list)
    breakdown: dict[str, Any] = Field(default_factory=dict)
    line_items: list[LineItemDecision] = Field(default_factory=list)
    requires_manual_review: bool = False
    degraded: bool = False
    failed_components: list[str] = Field(default_factory=list)
    explanation_tree: DecisionNode | None = None
    cost: CostBreakdown | None = None
    evidence_links: list[EvidenceLink] = Field(default_factory=list)
    confidence_breakdown: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "AgentResult",
    "Decision",
    "DecisionNode",
    "DecisionStatus",
    "LineItemDecision",
    "PolicyFinding",
    "RejectionReason",
]
