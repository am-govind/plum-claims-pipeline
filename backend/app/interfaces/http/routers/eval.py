"""Eval endpoint: runs all 12 cases through the pipeline and returns the
results plus a comparison against the expected outcomes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.composition import Container
from app.interfaces.http.deps import get_container
from eval.runner import run_all_cases

router = APIRouter(prefix="/api/eval", tags=["eval"])


@router.get("/run")
async def run_eval(
    container: Container = Depends(get_container),
) -> dict[str, Any]:
    results = await run_all_cases(container)
    passed = sum(1 for r in results if r["passed"])
    return {
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "results": results,
    }
