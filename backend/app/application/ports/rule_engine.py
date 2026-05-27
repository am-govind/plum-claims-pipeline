"""Abstract rule-engine port.

The pipeline only needs ``evaluate(state) -> list[RuleResult]``. The
default implementation is the JSON-DSL `DslRuleEngine` in the domain
policy package, but any other implementation (hand-coded rules, a
remote policy service, a tabular decision engine) can plug in.
"""

from __future__ import annotations

from typing import Protocol

from app.domain.claim import ClaimState
from app.domain.policy.rules import RuleResult


class RuleEngine(Protocol):
    """Evaluate every policy rule against a `ClaimState`."""

    def evaluate(self, state: ClaimState) -> list[RuleResult]: ...
