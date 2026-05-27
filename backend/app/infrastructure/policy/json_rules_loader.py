"""Read ``policy_rules.json`` into the value objects the domain expects.

Two helpers:

- ``load_rules_data(path)`` returns the raw ``{"rules": [...]}`` dict that
  `DslRuleEngine` evaluates.
- ``load_confidence_config(path)`` extracts the confidence-aggregation
  knobs and returns a `ConfidenceConfig`.

Both are pure functions: open a file, parse JSON, return data. No
module-level caches, no implicit settings lookups.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.domain.services.confidence import (
    DEFAULT_ALPHA,
    DEFAULT_BETA,
    DEFAULT_WEIGHTS,
    ConfidenceConfig,
)


def load_rules_data(path: str | Path) -> dict[str, Any]:
    """Return the full parsed contents of ``policy_rules.json``."""
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_confidence_config(path: str | Path) -> ConfidenceConfig:
    """Build a `ConfidenceConfig` from ``policy_rules.json``.

    Falls back to the documented defaults when the file is missing or the
    relevant keys are absent, so the system still has a sensible formula
    if someone deletes a section.
    """
    p = Path(path)
    if not p.exists():
        return ConfidenceConfig.default()
    with p.open("r", encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
    weights = data.get("confidence_weights") or dict(DEFAULT_WEIGHTS)
    alpha = float(data.get("contradiction_penalty_alpha", DEFAULT_ALPHA))
    beta = float(data.get("degraded_penalty_beta", DEFAULT_BETA))
    return ConfidenceConfig(
        weights={k: float(v) for k, v in weights.items()},
        alpha=alpha,
        beta=beta,
    )
