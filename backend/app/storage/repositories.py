"""Thin repository layer. Stores ClaimState as JSON so the trace UI can
recover the full execution history without joining many tables."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.models.claim import ClaimState
from app.storage.db import get_session
from app.storage.models import ClaimRecord


def _state_to_json(state: ClaimState) -> dict[str, Any]:
    return json.loads(state.model_dump_json())


class ClaimsRepository:
    @staticmethod
    async def save(state: ClaimState) -> ClaimRecord:
        async with get_session() as session:
            existing = await session.get(ClaimRecord, state.claim_id)
            decision = state.decision
            payload = {
                "claim_id": state.claim_id,
                "member_id": state.input.member_id,
                "policy_id": state.input.policy_id,
                "category": state.input.claim_category.value,
                "status": (decision.status.value if decision else "EARLY_STOP"),
                "submitted_amount": state.input.claimed_amount,
                "approved_amount": (decision.approved_amount if decision else 0.0),
                "confidence": (decision.confidence if decision else state.confidence),
                "state_json": _state_to_json(state),
            }
            if existing:
                for k, v in payload.items():
                    setattr(existing, k, v)
                rec = existing
            else:
                rec = ClaimRecord(
                    **payload, created_at=datetime.now(timezone.utc)
                )
                session.add(rec)
            await session.commit()
            await session.refresh(rec)
            return rec

    @staticmethod
    async def get(claim_id: str) -> ClaimRecord | None:
        async with get_session() as session:
            return await session.get(ClaimRecord, claim_id)

    @staticmethod
    async def list_recent(limit: int = 50) -> list[ClaimRecord]:
        async with get_session() as session:
            result = await session.execute(
                select(ClaimRecord).order_by(ClaimRecord.created_at.desc()).limit(limit)
            )
            return list(result.scalars().all())
