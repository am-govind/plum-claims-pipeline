"""Process-local `EventBus` implementation.

Sequential async fan-out with per-handler exception isolation: a noisy
or buggy handler logs the failure but never breaks the publish call or
prevents the other handlers from running.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from app.application.ports.event_bus import EventBus, EventHandler
from app.domain.events import DomainEvent

logger = logging.getLogger(__name__)


class InMemoryEventBus(EventBus):
    """`EventBus` adapter that dispatches in-process to subscribed handlers."""

    def __init__(self) -> None:
        self._handlers: list[EventHandler] = []

    def subscribe(self, handler: EventHandler) -> None:
        self._handlers.append(handler)

    async def publish(self, event: DomainEvent) -> None:
        for handler in self._handlers:
            try:
                await handler.handle(event)
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "event handler failed",
                    extra={
                        "handler": handler.__class__.__name__,
                        "event_type": event.__class__.__name__,
                        "claim_id": getattr(event, "claim_id", None),
                        "error": str(exc),
                    },
                )

    async def publish_all(self, events: Sequence[DomainEvent]) -> None:
        for event in events:
            await self.publish(event)
