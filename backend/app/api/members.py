"""Read-only endpoints exposing the policy roster and metadata so the
frontend can render dropdowns without duplicating policy_terms.json."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.policy.loader import get_policy

router = APIRouter(prefix="/api", tags=["policy"])


@router.get("/members")
async def list_members() -> list[dict[str, Any]]:
    policy = get_policy()
    return [
        {
            "member_id": m["member_id"],
            "name": m["name"],
            "relationship": m.get("relationship", "SELF"),
            "join_date": m.get("join_date"),
            "primary_member_id": m.get("primary_member_id"),
        }
        for m in policy.raw.get("members", [])
    ]


@router.get("/policy")
async def policy_summary() -> dict[str, Any]:
    p = get_policy()
    return {
        "policy_id": p.policy_id,
        "policy_name": p.raw.get("policy_name"),
        "insurer": p.raw.get("insurer"),
        "categories": list(p.opd_categories.keys()),
        "document_requirements": p.document_requirements,
        "network_hospitals": p.network_hospitals,
        "submission_rules": p.submission_rules,
        "fraud_thresholds": p.fraud_thresholds,
    }
