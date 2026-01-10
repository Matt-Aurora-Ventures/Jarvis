"""
Analytics Module.

Provides event tracking and metrics aggregation.
"""

from .events import (
    Event,
    EventType,
    EventTracker,
    MetricsAggregator,
    SQLiteEventSink,
    get_event_tracker,
    init_event_tracker,
    create_events_router,
)

__all__ = [
    "Event",
    "EventType",
    "EventTracker",
    "MetricsAggregator",
    "SQLiteEventSink",
    "get_event_tracker",
    "init_event_tracker",
    "create_events_router",
]
