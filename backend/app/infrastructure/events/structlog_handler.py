"""`EventHandler` that emits one structured log line per domain event.

The simplest possible subscriber: useful for audit, debugging, and as
a low-cost destination for analytics pipelines that tail JSON logs.
"""

from __future__ import annotations

from dataclasses import asdict

import structlog

from app.domain.events import DomainEvent

logger = structlog.get_logger("domain_events")


class StructlogEventHandler:
    """Emit ``logger.info("domain_event", ...)`` per event."""

    async def handle(self, event: DomainEvent) -> None:
        payload = asdict(event)
        event_type = event.__class__.__name__
        occurred_at = payload.pop("occurred_at", None)
        logger.info(
            "domain_event",
            event_type=event_type,
            occurred_at=occurred_at.isoformat() if occurred_at else None,
            **payload,
        )
