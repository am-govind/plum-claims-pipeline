"""Event-bus adapters and concrete handlers."""

from app.infrastructure.events.in_memory_bus import InMemoryEventBus
from app.infrastructure.events.notification_stub_handler import NotificationStubHandler
from app.infrastructure.events.structlog_handler import StructlogEventHandler

__all__ = [
    "InMemoryEventBus",
    "NotificationStubHandler",
    "StructlogEventHandler",
]
