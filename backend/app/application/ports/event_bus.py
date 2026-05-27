"""Event-dispatch port.

`EventBus` lets the application layer publish domain events without
caring whether they go to a logger, an outbox table, a Slack webhook,
or a message broker. Concrete adapters live in
`app.infrastructure.events`.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from app.domain.events import DomainEvent


class EventHandler(Protocol):
    """A single subscriber. May read the event; must not mutate it
    (events are frozen) and must not raise to the bus (the bus
    isolates handler exceptions so one bad subscriber can't break
    another)."""

    async def handle(self, event: DomainEvent) -> None: ...


class EventBus(Protocol):
    """Pub/sub for domain events. Subscriptions are process-local."""

    def subscribe(self, handler: EventHandler) -> None: ...

    async def publish(self, event: DomainEvent) -> None: ...

    async def publish_all(self, events: Sequence[DomainEvent]) -> None: ...
