"""Placeholder notification handler.

Demonstrates the multi-handler dispatch pattern without taking on a
real integration. Reacts only to events that would prompt an outbound
member-facing message; logs what would have been sent. Swap the body
of :meth:`handle` for a real email / SMS / webhook call.
"""

from __future__ import annotations

import structlog

from app.domain.events import (
    ClaimHaltedEarly,
    ClaimRejected,
    DomainEvent,
    ManualReviewRequired,
)

logger = structlog.get_logger("notifications")


class NotificationStubHandler:
    """Reacts to member-facing events (rejected / manual review / early stop)."""

    async def handle(self, event: DomainEvent) -> None:
        if isinstance(event, ClaimRejected):
            self._log(event.claim_id, "rejection", event.summary)
        elif isinstance(event, ManualReviewRequired):
            self._log(
                event.claim_id,
                "manual_review",
                f"reason={event.reason}",
            )
        elif isinstance(event, ClaimHaltedEarly):
            self._log(event.claim_id, "halted_early", event.reason)

    @staticmethod
    def _log(claim_id: str, channel: str, detail: str) -> None:
        logger.info(
            "would_notify_member",
            claim_id=claim_id,
            channel=channel,
            detail=detail,
        )
