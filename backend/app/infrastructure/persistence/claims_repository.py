"""SQLAlchemy adapter for `ClaimRepository`.

We persist the full `ClaimState` as JSON so the trace UI can recover
the entire execution history without joining many tables, and we
denormalise a few hot fields (status, amounts, confidence) so the
"recent claims" list is fast.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.application.ports.claim_repository import ClaimRepository
from app.domain.claim import ClaimState
from app.domain.claim.summary import ClaimSummary
from app.infrastructure.persistence.database import Database
from app.infrastructure.persistence.orm import ClaimRecord


def _state_to_json(state: ClaimState) -> dict[str, Any]:
    return json.loads(state.model_dump_json())


class SqlAlchemyClaimRepository(ClaimRepository):
    """Concrete `ClaimRepository` backed by SQLAlchemy + the `Database` wrapper."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def save(self, state: ClaimState) -> None:
        async with self._db.session() as session:
            existing = await session.get(ClaimRecord, state.claim_id)
            decision = state.decision
            payload: dict[str, Any] = {
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
            else:
                session.add(
                    ClaimRecord(**payload, created_at=datetime.now(timezone.utc))
                )
            await session.commit()

    async def get(self, claim_id: str) -> ClaimState | None:
        async with self._db.session() as session:
            rec = await session.get(ClaimRecord, claim_id)
            if rec is None:
                return None
            return ClaimState.model_validate(rec.state_json)

    async def list_recent(self, limit: int = 50) -> list[ClaimSummary]:
        async with self._db.session() as session:
            result = await session.execute(
                select(ClaimRecord).order_by(ClaimRecord.created_at.desc()).limit(limit)
            )
            rows = list(result.scalars().all())
        return [
            ClaimSummary(
                claim_id=r.claim_id,
                member_id=r.member_id,
                policy_id=r.policy_id,
                category=r.category,
                status=r.status,
                submitted_amount=float(r.submitted_amount),
                approved_amount=float(r.approved_amount),
                confidence=float(r.confidence),
                created_at=r.created_at,
            )
            for r in rows
        ]
