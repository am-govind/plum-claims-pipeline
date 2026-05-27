"""Pytest config.

Pins policy + test cases paths to the repo root and exposes a ``container``
fixture so integration tests can use the same composition root the real
application uses.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.composition import Container, compose
from app.config import Settings

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

os.environ.setdefault("POLICY_TERMS_PATH", str(REPO_ROOT / "policy_terms.json"))
os.environ.setdefault("TEST_CASES_PATH", str(REPO_ROOT / "test_cases.json"))
os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_claims.db")


@pytest.fixture
def container() -> Container:
    """Fresh `Container` per test. Database is not initialised — the
    integration test only needs the compiled pipeline and the policy."""
    return compose(Settings())
