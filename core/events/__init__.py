"""
Event Bus and Market Event Engine.

This module provides:
- EventBus: Central event dispatcher
- Event: Standard event structure
- MarketEvent: Classified market events (primary alpha source)
- TradingPipeline: Event -> Cost Check -> Strategy -> Sizing -> Exit
"""

from .bus import (
    EventBus,
    Event,
    EventType,
    EventPriority,
    EventHandler,
    get_event_bus,
)

from .market_events import (
    MarketEvent,
    MarketEventType,
    EventUrgency,
    VolumeTracker,
    precheck_cost,
    classify_stream_event,
)

from .trading_pipeline import (
    TradingPipeline,
    PipelineAction,
    PipelineResult,
    RejectionReason,
    ExitPlan,
)

__all__ = [
    # Bus
    "EventBus",
    "Event",
    "EventType",
    "EventPriority",
    "EventHandler",
    "get_event_bus",
    # Market events
    "MarketEvent",
    "MarketEventType",
    "EventUrgency",
    "VolumeTracker",
    "precheck_cost",
    "classify_stream_event",
    # Trading pipeline
    "TradingPipeline",
    "PipelineAction",
    "PipelineResult",
    "RejectionReason",
    "ExitPlan",
]
