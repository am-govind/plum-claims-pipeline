"""File-backed `PolicyRepository`.

Loads the JSON once at construction time and returns the same
`PolicyTerms` value object on each `get_terms()` call. Cheap to
recreate inside a test (no global cache) but also fine to share for
the lifetime of a process — `PolicyTerms` is effectively immutable.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.domain.policy.terms import PolicyTerms


class JsonPolicyRepository:
    """`PolicyRepository` that reads ``policy_terms.json`` from disk."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        with self._path.open("r", encoding="utf-8") as f:
            self._terms = PolicyTerms(json.load(f))

    def get_terms(self) -> PolicyTerms:
        return self._terms
