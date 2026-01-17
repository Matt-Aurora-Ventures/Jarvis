"""
Event Bus System - Async event-driven architecture with backpressure handling.

Provides:
- EventBus: Central event dispatch system
- Event types: Structured events for different systems
- Handler registration and execution
- Backpressure handling (queue limits, blocking producers)
- Timeout wrapping (prevents hung tasks)
- Dead letter queue (failed events capture)
- Trace ID propagation (debugging)
"""

from core.event_bus.event_bus import (
    EventBus,
    Event,
    EventType,
    EventPriority,
    HandlerResult,
    get_event_bus,
)

__all__ = [
    "EventBus",
    "Event",
    "EventType",
    "EventPriority",
    "HandlerResult",
    "get_event_bus",
]
