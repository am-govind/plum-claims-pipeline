"""Pytest config — pin policy + test cases to repo root and use MockProvider."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

os.environ.setdefault("POLICY_TERMS_PATH", str(REPO_ROOT / "policy_terms.json"))
os.environ.setdefault("TEST_CASES_PATH", str(REPO_ROOT / "test_cases.json"))
os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_claims.db")


@pytest.fixture(autouse=True)
def _reset_pipeline_cache():
    """Force the LangGraph compile cache to reset between tests."""
    import app.application.pipeline as p

    p._compiled_app = None
    p._compiled_provider_id = None
    yield
