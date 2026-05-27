"""Unit tests for `InMemoryEventBus` fan-out and handler isolation."""

from __future__ import annotations

import pytest

from app.domain.events import ClaimApproved, DomainEvent
from app.infrastructure.events.in_memory_bus import InMemoryEventBus


class _RecordingHandler:
    def __init__(self) -> None:
        self.events: list[DomainEvent] = []

    async def handle(self, event: DomainEvent) -> None:
        self.events.append(event)


class _RaisingHandler:
    async def handle(self, event: DomainEvent) -> None:  # noqa: ARG002
        raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_publish_fans_out_to_every_subscriber() -> None:
    bus = InMemoryEventBus()
    a, b = _RecordingHandler(), _RecordingHandler()
    bus.subscribe(a)
    bus.subscribe(b)

    await bus.publish(ClaimApproved(claim_id="T"))

    assert len(a.events) == 1
    assert len(b.events) == 1


@pytest.mark.asyncio
async def test_handler_exceptions_are_isolated() -> None:
    bus = InMemoryEventBus()
    healthy = _RecordingHandler()
    bus.subscribe(_RaisingHandler())
    bus.subscribe(healthy)

    await bus.publish(ClaimApproved(claim_id="T"))

    assert len(healthy.events) == 1


@pytest.mark.asyncio
async def test_publish_all_preserves_order() -> None:
    bus = InMemoryEventBus()
    sink = _RecordingHandler()
    bus.subscribe(sink)

    events = [
        ClaimApproved(claim_id="A"),
        ClaimApproved(claim_id="B"),
        ClaimApproved(claim_id="C"),
    ]
    await bus.publish_all(events)

    assert [e.claim_id for e in sink.events] == ["A", "B", "C"]
