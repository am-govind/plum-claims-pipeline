"""Claim submission and retrieval endpoints."""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.application.agents.intake import early_stop_decision
from app.application.pipeline import run_pipeline
from app.domain.claim import ClaimInput, ClaimState
from app.infrastructure.persistence.claims_repository import ClaimsRepository

router = APIRouter(prefix="/api/claims", tags=["claims"])


class ClaimResponse(BaseModel):
    claim_id: str
    state: dict[str, Any]


@router.post("", response_model=ClaimResponse)
async def submit_claim(payload: ClaimInput) -> ClaimResponse:
    claim_id = f"CLM_{uuid.uuid4().hex[:10].upper()}"
    state = ClaimState(claim_id=claim_id, input=payload)
    state = await run_pipeline(state)

    if state.early_stop and state.decision is None:
        state.decision = early_stop_decision(state)

    await ClaimsRepository.save(state)
    return ClaimResponse(claim_id=claim_id, state=json.loads(state.model_dump_json()))


@router.get("/{claim_id}", response_model=ClaimResponse)
async def get_claim(claim_id: str) -> ClaimResponse:
    rec = await ClaimsRepository.get(claim_id)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
    return ClaimResponse(claim_id=claim_id, state=rec.state_json)


@router.get("")
async def list_claims(limit: int = 50) -> list[dict[str, Any]]:
    records = await ClaimsRepository.list_recent(limit=limit)
    return [
        {
            "claim_id": r.claim_id,
            "member_id": r.member_id,
            "category": r.category,
            "status": r.status,
            "submitted_amount": r.submitted_amount,
            "approved_amount": r.approved_amount,
            "confidence": r.confidence,
            "created_at": r.created_at.isoformat(),
        }
        for r in records
    ]
