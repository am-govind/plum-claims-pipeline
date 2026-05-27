"""Evidence linking.

Every finding, contradiction, and decision-tree node should be able to
point back to the document, field, or snippet that justifies it. This is
how the trace UI answers "show me where you got that".
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class EvidenceLink(BaseModel):
    """A pointer from a decision/finding to its source.

    `source_file_id` is the uploaded document; `field_path` is a JSONPath-
    like reference (e.g. `extracted[0].diagnosis`) so reviewers can
    navigate to the exact field. `snippet` is the textual fragment that
    triggered the rule. `page` and `bbox` are populated when the OCR
    layer is available; for the mock provider they're left None.
    """

    source_file_id: str | None = None
    field_path: str | None = None
    snippet: str | None = None
    page: int | None = None
    bbox: tuple[float, float, float, float] | None = None
    confidence: float = 1.0


class Contradiction(BaseModel):
    """A cross-document inconsistency detected by the contradiction agent."""

    kind: str
    description: str
    severity: str = "WARNING"
    evidence: list[EvidenceLink] = Field(default_factory=list)
    confidence: float = 1.0
