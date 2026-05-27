"""Integration tests: every test_cases.json case must pass end-to-end via the
mock provider. This is the deterministic eval guarantee for CI."""

from __future__ import annotations

import pytest

from eval.runner import _load_test_cases, run_case


@pytest.mark.asyncio
@pytest.mark.parametrize("case", _load_test_cases(), ids=lambda c: c["case_id"])
async def test_case_passes(case):
    result = await run_case(case)
    if not result["passed"]:
        msg = "; ".join(result["issues"])
        pytest.fail(f"{case['case_id']} ({case['case_name']}) failed: {msg}")
