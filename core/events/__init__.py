"""
Event Bus - Unified event system for cross-app communication.

This module provides:
- EventBus: Central event dispatcher
- Event: Standard event structure
- Decorators for event subscription
"""

from .bus import (
    EventBus,
    Event,
    EventType,
    EventPriority,
    EventHandler,
    get_event_bus,
)

__all__ = [
    "EventBus",
    "Event",
    "EventType",
    "EventPriority",
    "EventHandler",
    "get_event_bus",
]
