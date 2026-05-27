"""Decision Explanation Tree.

The synthesizer builds a recursive ``DecisionNode`` so the UI can render
the causal structure of any decision, not just a flat list of reasons.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.domain.evidence import EvidenceLink

NodeKind = Literal["root", "rule_group", "rule", "calc_step", "signal", "note"]


class DecisionNode(BaseModel):
    """A node in the decision causal tree.

    The root carries the final status; children describe each
    contributing factor. Each node can carry evidence links and structured
    detail (numbers, codes) that the UI renders inline.
    """

    label: str
    kind: NodeKind = "rule"
    status: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)
    evidence: list[EvidenceLink] = Field(default_factory=list)
    children: list["DecisionNode"] = Field(default_factory=list)


DecisionNode.model_rebuild()
