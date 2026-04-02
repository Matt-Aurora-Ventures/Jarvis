"""
Event Bus System

Provides asynchronous, decoupled event-driven communication.

Features:
- Async event emission and handling
- Topic-based subscriptions with wildcards
- Event prioritization
- Event history and replay
- Dead letter queue for failed handlers

Usage:
    from lifeos.events import EventBus, Event

    bus = EventBus()

    @bus.on("user.login")
    async def handle_login(event):
        print(f"User logged in: {event.data['user_id']}")

    await bus.emit("user.login", {"user_id": 123})
"""

from lifeos.events.event import Event, EventPriority
from lifeos.events.bus import EventBus, EventHandler
from lifeos.events.middleware import EventMiddleware, LoggingMiddleware

__all__ = [
    # Core classes
    "Event",
    "EventPriority",
    "EventBus",
    "EventHandler",
    # Middleware
    "EventMiddleware",
    "LoggingMiddleware",
]
