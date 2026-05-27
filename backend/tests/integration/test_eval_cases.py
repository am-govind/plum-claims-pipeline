"""Integration tests: every test_cases.json case must pass end-to-end via
the mock provider. This is the deterministic eval guarantee for CI.

Uses the same `Container` (built via the composition root) that
production uses, so the assertion is "exactly what the application
does, end to end".
"""

from __future__ import annotations

import pytest

from app.composition import Container
from app.config import Settings
from eval.runner import _load_test_cases, run_case


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    _load_test_cases(Settings().test_cases_path),
    ids=lambda c: c["case_id"],
)
async def test_case_passes(case, container: Container):
    result = await run_case(case, container)
    if not result["passed"]:
        msg = "; ".join(result["issues"])
        pytest.fail(f"{case['case_id']} ({case['case_name']}) failed: {msg}")
