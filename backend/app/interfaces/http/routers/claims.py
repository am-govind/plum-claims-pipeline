"""Claim submission and retrieval endpoints."""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.application.agents.intake import early_stop_decision
from app.application.pipeline import CompiledPipeline, run_pipeline
from app.application.ports.claim_repository import ClaimRepository
from app.application.ports.event_bus import EventBus
from app.domain.claim import ClaimInput, ClaimState
from app.interfaces.http.deps import (
    get_claim_repository,
    get_event_bus,
    get_pipeline,
)

router = APIRouter(prefix="/api/claims", tags=["claims"])


class ClaimResponse(BaseModel):
    claim_id: str
    state: dict[str, Any]


def _state_payload(state: ClaimState) -> dict[str, Any]:
    return json.loads(state.model_dump_json())


@router.post("", response_model=ClaimResponse)
async def submit_claim(
    payload: ClaimInput,
    pipeline: CompiledPipeline = Depends(get_pipeline),
    claims: ClaimRepository = Depends(get_claim_repository),
    event_bus: EventBus = Depends(get_event_bus),
) -> ClaimResponse:
    claim_id = f"CLM_{uuid.uuid4().hex[:10].upper()}"
    state = ClaimState(claim_id=claim_id, input=payload)
    state = await run_pipeline(state, pipeline)

    if state.early_stop and state.decision is None:
        state.decision = early_stop_decision(state)

    await claims.save(state)
    await event_bus.publish_all(state.pull_events())
    return ClaimResponse(claim_id=claim_id, state=_state_payload(state))


@router.get("/{claim_id}", response_model=ClaimResponse)
async def get_claim(
    claim_id: str,
    claims: ClaimRepository = Depends(get_claim_repository),
) -> ClaimResponse:
    state = await claims.get(claim_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
    return ClaimResponse(claim_id=claim_id, state=_state_payload(state))


@router.get("")
async def list_claims(
    limit: int = 50,
    claims: ClaimRepository = Depends(get_claim_repository),
) -> list[dict[str, Any]]:
    summaries = await claims.list_recent(limit=limit)
    return [
        {
            "claim_id": s.claim_id,
            "member_id": s.member_id,
            "category": s.category,
            "status": s.status,
            "submitted_amount": s.submitted_amount,
            "approved_amount": s.approved_amount,
            "confidence": s.confidence,
            "created_at": s.created_at.isoformat(),
        }
        for s in summaries
    ]
