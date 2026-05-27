"""AgentResult: per-agent confidence input to the formal aggregation formula.

Each agent fills one of these onto `state.agent_results[agent_name]`. The
DecisionSynthesizer reads them and applies the documented weighted formula
defined in `app.decision.confidence`.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AgentResult(BaseModel):
    """Per-agent confidence signal.

    - ``confidence``: the agent's own self-reported confidence (e.g. how
      sure the extraction agent is that it pulled the right diagnosis).
    - ``evidence_strength``: how much corroborating evidence backs the
      agent's output (e.g. matching patient name across 3 docs is stronger
      than 1 doc).
    - ``contradiction_score``: positive when this agent detected an
      inconsistency. Aggregated as a penalty.
    """

    confidence: float = 1.0
    evidence_strength: float = 1.0
    contradiction_score: float = 0.0
    notes: list[str] = Field(default_factory=list)
