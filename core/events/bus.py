"""
Event Bus - Central event dispatcher for JARVIS.

Enables:
- Cross-platform event propagation
- Async event handling
- Event filtering and routing
- Event history and replay
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
import asyncio
import hashlib
import logging
from functools import wraps

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Predefined event types."""
    # Trading events
    TRADE_EXECUTED = "trade.executed"
    TRADE_FAILED = "trade.failed"
    POSITION_OPENED = "position.opened"
    POSITION_CLOSED = "position.closed"
    STOP_LOSS_TRIGGERED = "stoploss.triggered"
    TAKE_PROFIT_TRIGGERED = "takeprofit.triggered"

    # Market events
    PRICE_ALERT = "price.alert"
    WHALE_DETECTED = "whale.detected"
    SIGNAL_GENERATED = "signal.generated"
    MARKET_REGIME_CHANGE = "market.regime_change"

    # Portfolio events
    PORTFOLIO_UPDATED = "portfolio.updated"
    BALANCE_CHANGED = "balance.changed"
    PNL_UPDATED = "pnl.updated"

    # User events
    USER_CONNECTED = "user.connected"
    USER_DISCONNECTED = "user.disconnected"
    USER_PREFERENCE_CHANGED = "user.preference_changed"

    # System events
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    SYSTEM_ERROR = "system.error"
    SYSTEM_HEALTH_CHECK = "system.health_check"

    # Alert events
    ALERT_CREATED = "alert.created"
    ALERT_TRIGGERED = "alert.triggered"
    ALERT_DISMISSED = "alert.dismissed"

    # Staking events
    STAKE_CREATED = "stake.created"
    STAKE_UPDATED = "stake.updated"
    REWARDS_CLAIMED = "rewards.claimed"

    # Custom event
    CUSTOM = "custom"


class EventPriority(Enum):
    """Event priority levels."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class Event:
    """Standard event structure."""
    type: str  # Can be EventType value or custom string
    data: Dict[str, Any] = field(default_factory=dict)
    priority: EventPriority = EventPriority.NORMAL
    source: str = "unknown"  # Source platform/component
    user_id: Optional[str] = None
    correlation_id: Optional[str] = None  # For tracking related events
    timestamp: datetime = field(default_factory=datetime.utcnow)
    id: str = field(default="")

    def __post_init__(self):
        if not self.id:
            self.id = self._generate_id()

    def _generate_id(self) -> str:
        """Generate unique event ID."""
        data = f"{self.type}:{self.timestamp.isoformat()}:{id(self)}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "type": self.type,
            "data": self.data,
            "priority": self.priority.value,
            "source": self.source,
            "user_id": self.user_id,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        """Create from dictionary."""
        return cls(
            id=data.get("id", ""),
            type=data["type"],
            data=data.get("data", {}),
            priority=EventPriority(data.get("priority", 1)),
            source=data.get("source", "unknown"),
            user_id=data.get("user_id"),
            correlation_id=data.get("correlation_id"),
            timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else datetime.utcnow(),
        )


@dataclass
class EventHandler:
    """Registered event handler."""
    callback: Callable
    event_types: Set[str]
    priority: EventPriority = EventPriority.NORMAL
    filter_func: Optional[Callable[[Event], bool]] = None
    name: str = ""

    def __post_init__(self):
        if not self.name:
            self.name = self.callback.__name__


class EventBus:
    """
    Central event bus for JARVIS.

    Supports:
    - Async and sync handlers
    - Event filtering
    - Priority-based execution
    - Event history
    """

    def __init__(self, max_history: int = 1000):
        self._handlers: List[EventHandler] = []
        self._history: List[Event] = []
        self._max_history = max_history
        self._paused = False
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._processing = False

    def subscribe(
        self,
        event_types: str | List[str],
        priority: EventPriority = EventPriority.NORMAL,
        filter_func: Optional[Callable[[Event], bool]] = None,
    ) -> Callable:
        """
        Decorator to subscribe a handler to event types.

        Usage:
            @bus.subscribe("trade.executed")
            async def handle_trade(event: Event):
                print(f"Trade: {event.data}")

            @bus.subscribe(["whale.detected", "signal.generated"])
            async def handle_signals(event: Event):
                print(f"Signal: {event.data}")
        """
        if isinstance(event_types, str):
            event_types = [event_types]

        def decorator(func: Callable) -> Callable:
            handler = EventHandler(
                callback=func,
                event_types=set(event_types),
                priority=priority,
                filter_func=filter_func,
            )
            self._handlers.append(handler)

            @wraps(func)
            async def wrapper(*args, **kwargs):
                return await func(*args, **kwargs)

            return wrapper

        return decorator

    def unsubscribe(self, handler_name: str) -> bool:
        """Unsubscribe a handler by name."""
        for i, handler in enumerate(self._handlers):
            if handler.name == handler_name:
                self._handlers.pop(i)
                return True
        return False

    async def publish(self, event: Event) -> int:
        """
        Publish an event to all subscribed handlers.

        Returns number of handlers that received the event.
        """
        if self._paused:
            logger.debug(f"Event bus paused, queueing event: {event.type}")
            await self._event_queue.put(event)
            return 0

        # Add to history
        self._add_to_history(event)

        # Find matching handlers
        matching = []
        for handler in self._handlers:
            if event.type in handler.event_types or "*" in handler.event_types:
                if handler.filter_func is None or handler.filter_func(event):
                    matching.append(handler)

        # Sort by priority (highest first)
        matching.sort(key=lambda h: h.priority.value, reverse=True)

        # Execute handlers
        executed = 0
        for handler in matching:
            try:
                if asyncio.iscoroutinefunction(handler.callback):
                    await handler.callback(event)
                else:
                    handler.callback(event)
                executed += 1
            except Exception as e:
                logger.error(f"Error in event handler {handler.name}: {e}")

        logger.debug(f"Event {event.type} delivered to {executed} handlers")
        return executed

    def publish_sync(self, event: Event) -> None:
        """Synchronously publish an event (creates async task)."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.publish(event))
        except RuntimeError:
            # No running loop, create one
            asyncio.run(self.publish(event))

    async def emit(
        self,
        event_type: str | EventType,
        data: Optional[Dict[str, Any]] = None,
        source: str = "unknown",
        user_id: Optional[str] = None,
        priority: EventPriority = EventPriority.NORMAL,
        correlation_id: Optional[str] = None,
    ) -> int:
        """
        Convenience method to create and publish an event.

        Returns number of handlers that received the event.
        """
        if isinstance(event_type, EventType):
            event_type = event_type.value

        event = Event(
            type=event_type,
            data=data or {},
            source=source,
            user_id=user_id,
            priority=priority,
            correlation_id=correlation_id,
        )

        return await self.publish(event)

    def _add_to_history(self, event: Event) -> None:
        """Add event to history."""
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    def get_history(
        self,
        event_types: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Event]:
        """Get event history with optional filtering."""
        history = self._history

        if event_types:
            history = [e for e in history if e.type in event_types]

        if user_id:
            history = [e for e in history if e.user_id == user_id]

        return history[-limit:]

    def pause(self) -> None:
        """Pause event processing (queue events)."""
        self._paused = True
        logger.info("Event bus paused")

    async def resume(self) -> int:
        """Resume event processing and process queued events."""
        self._paused = False
        processed = 0

        while not self._event_queue.empty():
            event = await self._event_queue.get()
            await self.publish(event)
            processed += 1

        logger.info(f"Event bus resumed, processed {processed} queued events")
        return processed

    def clear_history(self) -> None:
        """Clear event history."""
        self._history = []

    def get_stats(self) -> Dict[str, Any]:
        """Get event bus statistics."""
        event_counts = {}
        for event in self._history:
            event_counts[event.type] = event_counts.get(event.type, 0) + 1

        return {
            "total_handlers": len(self._handlers),
            "handlers": [
                {
                    "name": h.name,
                    "event_types": list(h.event_types),
                    "priority": h.priority.value,
                }
                for h in self._handlers
            ],
            "history_size": len(self._history),
            "event_counts": event_counts,
            "paused": self._paused,
            "queue_size": self._event_queue.qsize(),
        }


# Singleton instance
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus
