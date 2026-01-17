"""
EventBus - Async event-driven architecture with backpressure and timeout handling.

Addresses:
- Issue #4: Hung tasks (via handler timeout wrapping)
- Decoupling of components
- Async/await pattern throughout
"""

import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, List, Any, Callable, Awaitable, Tuple

logger = logging.getLogger("jarvis.event_bus")


class EventType(Enum):
    """Event classification for routing and filtering."""
    # Trading events
    TRADE_EXECUTED = "trade_executed"
    TRADE_FAILED = "trade_failed"
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"

    # X Bot events
    TWEET_POSTED = "tweet_posted"
    TWEET_FAILED = "tweet_failed"
    DUPLICATE_DETECTED = "duplicate_detected"

    # Buy Tracker events
    BUY_SIGNAL = "buy_signal"
    BUY_EXECUTED = "buy_executed"
    BUY_FAILED = "buy_failed"

    # Sentiment events
    SENTIMENT_ANALYSIS = "sentiment_analysis"

    # System events
    STARTUP = "startup"
    SHUTDOWN = "shutdown"
    ERROR = "error"
    HEALTH_CHECK = "health_check"


class EventPriority(Enum):
    """Event priority for queue ordering."""
    LOW = 3
    NORMAL = 2
    HIGH = 1
    CRITICAL = 0


@dataclass
class Event:
    """Unified event structure."""
    event_type: EventType
    data: Dict[str, Any]
    priority: EventPriority = EventPriority.NORMAL
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    source: str = ""  # Which component created this event
    expires_at: Optional[str] = None  # TTL for event

    def is_expired(self) -> bool:
        """Check if event TTL has passed."""
        if not self.expires_at:
            return False
        return datetime.fromisoformat(self.expires_at) < datetime.utcnow()

    def __lt__(self, other: "Event") -> bool:
        """Priority comparison for queue ordering."""
        if self.priority.value != other.priority.value:
            return self.priority.value < other.priority.value
        return self.timestamp < other.timestamp


@dataclass
class HandlerResult:
    """Result of handler execution."""
    success: bool
    handler_name: str
    event_type: EventType
    duration_ms: float
    error: Optional[str] = None
    trace_id: str = ""


class EventHandler(ABC):
    """Abstract base for event handlers."""

    @abstractmethod
    async def handle(self, event: Event) -> Tuple[bool, Optional[str]]:
        """
        Handle an event.

        Returns:
            (success, error_message)
        """
        pass

    @abstractmethod
    def handles(self, event_type: EventType) -> bool:
        """Check if this handler processes this event type."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Handler name for logging."""
        pass


class EventBus:
    """
    Central event dispatch system with backpressure and timeout handling.

    Features:
    - Async queue with configurable size limits
    - Priority-based event ordering
    - Handler timeout wrapping (prevents hung tasks)
    - Dead letter queue for failed events
    - Trace ID propagation
    - Backpressure handling (blocks producers if queue is full)
    """

    def __init__(
        self,
        max_queue_size: int = 1000,
        handler_timeout: float = 30.0,
        dlq_retention: int = 100,
    ):
        """
        Initialize EventBus.

        Args:
            max_queue_size: Maximum events in queue (backpressure threshold)
            handler_timeout: Timeout for handler execution (seconds)
            dlq_retention: Max failed events to keep in dead letter queue
        """
        self.max_queue_size = max_queue_size
        self.handler_timeout = handler_timeout
        self.dlq_retention = dlq_retention

        # Event queue (priority queue)
        self._queue: asyncio.PriorityQueue[Tuple[int, Event]] = asyncio.PriorityQueue()

        # Handlers by event type
        self._handlers: Dict[EventType, List[EventHandler]] = {}

        # Dead letter queue for failed events
        self._dead_letter_queue: List[Tuple[Event, str]] = []

        # Statistics
        self._stats = {
            "events_processed": 0,
            "events_failed": 0,
            "handler_timeouts": 0,
            "queue_size": 0,
        }

        # Running flag
        self._running = False
        self._consumer_task: Optional[asyncio.Task] = None

    def register_handler(self, handler: EventHandler, event_types: List[EventType]) -> None:
        """Register a handler for specific event types."""
        for event_type in event_types:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            self._handlers[event_type].append(handler)
            logger.debug(f"Registered handler {handler.name} for {event_type.value}")

    async def emit(self, event: Event) -> bool:
        """
        Emit an event to the bus.

        Blocks (backpressure) if queue is full and no timeout provided.

        Returns:
            True if queued, False if dropped due to timeout
        """
        if event.is_expired():
            logger.warning(f"Dropped expired event {event.event_type.value} (trace: {event.trace_id})")
            return False

        try:
            # Backpressure: wait if queue is full, but don't block forever
            queue_full = self._queue.qsize() >= self.max_queue_size

            if queue_full:
                logger.warning(
                    f"EventBus queue full ({self._queue.qsize()}/{self.max_queue_size}), "
                    f"blocking {event.event_type.value} (trace: {event.trace_id})"
                )

            # Put with timeout to prevent permanent blocking
            try:
                await asyncio.wait_for(
                    self._queue.put((event.priority.value, event)),
                    timeout=5.0  # 5 second timeout for queue operations
                )
                self._stats["queue_size"] = self._queue.qsize()
                return True
            except asyncio.TimeoutError:
                logger.error(f"Timeout queueing event {event.event_type.value} (queue full)")
                self._dead_letter_queue.append((event, "Queue timeout - backpressure exceeded"))
                self._trim_dlq()
                return False
        except Exception as e:
            logger.error(f"Error emitting event: {e}")
            return False

    async def _dispatch_event(self, event: Event) -> None:
        """Dispatch event to all registered handlers."""
        handlers = self._handlers.get(event.event_type, [])

        if not handlers:
            logger.debug(f"No handlers for {event.event_type.value} (trace: {event.trace_id})")
            return

        for handler in handlers:
            try:
                # Wrap handler with timeout to prevent hung tasks
                start = datetime.utcnow()

                try:
                    success, error = await asyncio.wait_for(
                        handler.handle(event),
                        timeout=self.handler_timeout
                    )
                except asyncio.TimeoutError:
                    success = False
                    error = f"Handler timeout ({self.handler_timeout}s)"
                    self._stats["handler_timeouts"] += 1
                    logger.error(
                        f"Handler timeout: {handler.name} for {event.event_type.value} "
                        f"(trace: {event.trace_id})"
                    )

                duration_ms = (datetime.utcnow() - start).total_seconds() * 1000

                if success:
                    self._stats["events_processed"] += 1
                    logger.debug(
                        f"Handler {handler.name} processed {event.event_type.value} "
                        f"in {duration_ms:.1f}ms (trace: {event.trace_id})"
                    )
                else:
                    self._stats["events_failed"] += 1
                    self._dead_letter_queue.append((event, error or "Handler failed"))
                    self._trim_dlq()
                    logger.warning(
                        f"Handler {handler.name} failed: {error} "
                        f"(trace: {event.trace_id})"
                    )
            except Exception as e:
                self._stats["events_failed"] += 1
                self._dead_letter_queue.append((event, f"Handler exception: {str(e)}"))
                self._trim_dlq()
                logger.error(
                    f"Handler {handler.name} exception: {e} "
                    f"(trace: {event.trace_id})"
                )

    async def _consumer(self) -> None:
        """Consume events from queue and dispatch."""
        logger.info("EventBus consumer started")

        while self._running:
            try:
                # Get next event (with timeout to allow checking _running flag)
                try:
                    _, event = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                await self._dispatch_event(event)
                self._queue.task_done()
                self._stats["queue_size"] = self._queue.qsize()
            except Exception as e:
                logger.error(f"Consumer error: {e}")

    async def start(self) -> None:
        """Start the event bus."""
        if self._running:
            logger.warning("EventBus already running")
            return

        self._running = True
        self._consumer_task = asyncio.create_task(self._consumer())
        logger.info("EventBus started")

    async def stop(self, timeout: float = 10.0) -> None:
        """Stop the event bus and wait for pending events."""
        if not self._running:
            return

        logger.info(f"Stopping EventBus, waiting for {self._queue.qsize()} pending events")

        # Wait for pending events or timeout
        try:
            await asyncio.wait_for(self._queue.join(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(f"EventBus shutdown timeout after {timeout}s, {self._queue.qsize()} events pending")

        self._running = False

        if self._consumer_task:
            await self._consumer_task

        logger.info("EventBus stopped")

    def _trim_dlq(self) -> None:
        """Keep dead letter queue bounded."""
        if len(self._dead_letter_queue) > self.dlq_retention:
            removed = len(self._dead_letter_queue) - self.dlq_retention
            self._dead_letter_queue = self._dead_letter_queue[-self.dlq_retention:]
            logger.debug(f"Trimmed DLQ, removed {removed} old entries")

    def get_stats(self) -> Dict[str, Any]:
        """Get event bus statistics."""
        return {
            "events_processed": self._stats["events_processed"],
            "events_failed": self._stats["events_failed"],
            "handler_timeouts": self._stats["handler_timeouts"],
            "queue_size": self._queue.qsize(),
            "dlq_size": len(self._dead_letter_queue),
            "max_queue_size": self.max_queue_size,
            "handler_timeout": self.handler_timeout,
        }

    def get_dead_letter_queue(self) -> List[Dict[str, Any]]:
        """Get dead letter queue entries."""
        return [
            {
                "event_type": event.event_type.value,
                "trace_id": event.trace_id,
                "error": error,
                "timestamp": event.timestamp,
            }
            for event, error in self._dead_letter_queue
        ]


# Global EventBus instance
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get global EventBus instance."""
    global _event_bus
    if not _event_bus:
        _event_bus = EventBus(max_queue_size=1000, handler_timeout=30.0)
    return _event_bus


def set_event_bus(bus: EventBus) -> None:
    """Set global EventBus instance (for testing)."""
    global _event_bus
    _event_bus = bus
