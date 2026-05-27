"""Formal confidence aggregation.

Documented formula::

    C_final = clip( Σ w_i * C_i  -  α * contradiction_score  -  β * degraded_penalty , 0, 1)

Where:

- ``w_i`` is the weight for agent ``i`` (configured via `ConfidenceConfig`).
- ``C_i`` is the agent's self-reported confidence (``state.agent_results``).
- ``α``, ``β`` are tunable penalty coefficients.
- ``contradiction_score`` = mean of agent contradiction_scores, capped at 1.
- ``degraded_penalty`` = 1 if the pipeline ran in degraded mode, else 0.

We expose the per-component ``w_i * C_i`` terms on
``Decision.confidence_breakdown`` so the UI can show "How was this
calculated?" — every agent's contribution is auditable.

This module is pure domain: it takes a `ConfidenceConfig` and a
`ClaimState`, returns a `ConfidenceComputation`. File IO for the
config lives in `app.infrastructure.policy.json_rules_loader`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.claim import ClaimState

DEFAULT_WEIGHTS: dict[str, float] = {
    "intake": 0.05,
    "document_verification": 0.20,
    "extraction": 0.30,
    "policy_adjudication": 0.15,
    "financial_calculation": 0.10,
    "fraud_detection": 0.10,
    "contradiction_detection": 0.10,
}
DEFAULT_ALPHA = 0.4
DEFAULT_BETA = 0.25


@dataclass(frozen=True)
class ConfidenceConfig:
    """Tunable inputs to the confidence formula.

    Constructed once by the composition root from the rules JSON and
    threaded into `DecisionSynthesizerAgent`. Using a frozen dataclass
    keeps it cheap to copy and impossible to mutate at runtime.
    """

    weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    alpha: float = DEFAULT_ALPHA
    beta: float = DEFAULT_BETA

    @classmethod
    def default(cls) -> "ConfidenceConfig":
        return cls()


@dataclass
class ConfidenceComputation:
    final: float
    weighted_sum: float
    contradiction_penalty: float
    degraded_penalty: float
    per_component: dict[str, dict[str, float]]
    weights: dict[str, float]
    alpha: float
    beta: float

    def to_breakdown(self) -> dict[str, Any]:
        return {
            "final": round(self.final, 4),
            "weighted_sum": round(self.weighted_sum, 4),
            "contradiction_penalty": round(self.contradiction_penalty, 4),
            "degraded_penalty": round(self.degraded_penalty, 4),
            "alpha": self.alpha,
            "beta": self.beta,
            "weights": self.weights,
            "per_component": {
                k: {
                    "weight": round(v["weight"], 4),
                    "confidence": round(v["confidence"], 4),
                    "contribution": round(v["contribution"], 4),
                }
                for k, v in self.per_component.items()
            },
        }


def compute_confidence(
    state: ClaimState, config: ConfidenceConfig
) -> ConfidenceComputation:
    """Apply the weighted formula to ``state`` using ``config``.

    Components without a corresponding ``state.agent_results`` entry
    contribute their weight times 0 — they're effectively missing-data
    penalties without forcing the synthesizer to fabricate values.
    """
    weights = config.weights
    alpha = config.alpha
    beta = config.beta

    per_component: dict[str, dict[str, float]] = {}
    weighted_sum = 0.0
    contradiction_scores: list[float] = []
    for name, w in weights.items():
        ar = state.agent_results.get(name)
        c = ar.confidence if ar else 0.0
        contribution = float(w) * float(c)
        weighted_sum += contribution
        per_component[name] = {
            "weight": float(w),
            "confidence": float(c),
            "contribution": float(contribution),
        }
        if ar:
            contradiction_scores.append(ar.contradiction_score)

    contradiction_score = (
        sum(contradiction_scores) / len(contradiction_scores)
        if contradiction_scores
        else 0.0
    )
    contradiction_score = min(1.0, contradiction_score)
    contradiction_penalty = alpha * contradiction_score
    degraded_penalty = beta * (1.0 if state.degraded else 0.0)

    final = weighted_sum - contradiction_penalty - degraded_penalty
    final = max(0.0, min(1.0, final))

    return ConfidenceComputation(
        final=final,
        weighted_sum=weighted_sum,
        contradiction_penalty=contradiction_penalty,
        degraded_penalty=degraded_penalty,
        per_component=per_component,
        weights={k: float(v) for k, v in weights.items()},
        alpha=alpha,
        beta=beta,
    )
