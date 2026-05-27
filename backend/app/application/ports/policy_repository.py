"""Abstract policy-loading port.

The policy is a slow-changing aggregate of insurance terms (coverage,
exclusions, waiting periods, etc). Consumers want a `PolicyTerms` value
object; how it is loaded (JSON file, REST API, database row) is an
infrastructure concern hidden behind this port.
"""

from __future__ import annotations

from typing import Protocol

from app.domain.policy.terms import PolicyTerms


class PolicyRepository(Protocol):
    """Returns the active `PolicyTerms` to consumers in the application layer."""

    def get_terms(self) -> PolicyTerms: ...
