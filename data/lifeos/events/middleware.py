"""
Event Middleware

Middleware components that can intercept and modify events
before and after emission.

Built-in middleware:
- LoggingMiddleware: Logs all events
- FilterMiddleware: Filters events by pattern or predicate
- ThrottleMiddleware: Rate limits events
- TransformMiddleware: Transforms event data
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set

from lifeos.events.event import Event

logger = logging.getLogger(__name__)


class EventMiddleware(ABC):
    """
    Base class for event middleware.

    Middleware can intercept events before and after emission
    to add cross-cutting concerns like logging, filtering, etc.
    """

    @abstractmethod
    async def before_emit(self, event: Event) -> Optional[Event]:
        """
        Called before event is emitted.

        Args:
            event: The event about to be emitted

        Returns:
            The event (possibly modified) or None to cancel
        """
        pass

    async def after_emit(self, event: Event) -> None:
        """
        Called after event is emitted.

        Args:
            event: The emitted event
        """
        pass


class LoggingMiddleware(EventMiddleware):
    """Middleware that logs all events."""

    def __init__(
        self,
        log_level: int = logging.DEBUG,
        include_data: bool = False,
        patterns: Optional[List[str]] = None,
    ):
        """
        Initialize logging middleware.

        Args:
            log_level: Log level to use
            include_data: Whether to include event data in log
            patterns: Only log events matching these patterns
        """
        self._log_level = log_level
        self._include_data = include_data
        self._patterns = patterns

    async def before_emit(self, event: Event) -> Optional[Event]:
        """Log event before emission."""
        if self._patterns:
            if not any(event.matches_pattern(p) for p in self._patterns):
                return event

        msg = f"Event: {event.topic} (id={event.id}, priority={event.priority.name})"

        if self._include_data and event.data:
            msg += f" data={event.data}"

        logger.log(self._log_level, msg)
        return event

    async def after_emit(self, event: Event) -> None:
        """Log event after emission."""
        if event.has_error:
            logger.warning(f"Event {event.topic} had error: {event.error}")


class FilterMiddleware(EventMiddleware):
    """Middleware that filters events."""

    def __init__(
        self,
        allow_patterns: Optional[List[str]] = None,
        deny_patterns: Optional[List[str]] = None,
        predicate: Optional[Callable[[Event], bool]] = None,
    ):
        """
        Initialize filter middleware.

        Args:
            allow_patterns: Only allow events matching these
            deny_patterns: Block events matching these
            predicate: Custom filter function
        """
        self._allow = allow_patterns or []
        self._deny = deny_patterns or []
        self._predicate = predicate

    async def before_emit(self, event: Event) -> Optional[Event]:
        """Filter event."""
        # Check deny list first
        for pattern in self._deny:
            if event.matches_pattern(pattern):
                logger.debug(f"Event {event.topic} blocked by deny pattern {pattern}")
                return None

        # Check allow list if specified
        if self._allow:
            allowed = any(event.matches_pattern(p) for p in self._allow)
            if not allowed:
                logger.debug(f"Event {event.topic} not in allow list")
                return None

        # Check predicate
        if self._predicate and not self._predicate(event):
            logger.debug(f"Event {event.topic} blocked by predicate")
            return None

        return event


class ThrottleMiddleware(EventMiddleware):
    """Middleware that rate limits events."""

    def __init__(
        self,
        max_per_second: float = 10.0,
        per_topic: bool = False,
        burst_size: int = 5,
    ):
        """
        Initialize throttle middleware.

        Args:
            max_per_second: Maximum events per second
            per_topic: Whether to throttle per topic
            burst_size: Allow burst of this many events
        """
        self._max_rate = max_per_second
        self._per_topic = per_topic
        self._burst_size = burst_size
        self._tokens: Dict[str, float] = defaultdict(lambda: float(burst_size))
        self._last_update: Dict[str, float] = defaultdict(time.time)

    async def before_emit(self, event: Event) -> Optional[Event]:
        """Throttle event."""
        key = event.topic if self._per_topic else "__global__"
        now = time.time()

        # Refill tokens
        elapsed = now - self._last_update[key]
        self._tokens[key] = min(
            self._burst_size,
            self._tokens[key] + elapsed * self._max_rate
        )
        self._last_update[key] = now

        # Check if we have tokens
        if self._tokens[key] >= 1:
            self._tokens[key] -= 1
            return event

        logger.debug(f"Event {event.topic} throttled")
        return None


class TransformMiddleware(EventMiddleware):
    """Middleware that transforms events."""

    def __init__(
        self,
        transform_fn: Callable[[Event], Event],
        patterns: Optional[List[str]] = None,
    ):
        """
        Initialize transform middleware.

        Args:
            transform_fn: Function to transform events
            patterns: Only transform events matching these
        """
        self._transform = transform_fn
        self._patterns = patterns

    async def before_emit(self, event: Event) -> Optional[Event]:
        """Transform event."""
        if self._patterns:
            if not any(event.matches_pattern(p) for p in self._patterns):
                return event

        return self._transform(event)


class MetricsMiddleware(EventMiddleware):
    """Middleware that collects event metrics."""

    def __init__(self):
        """Initialize metrics middleware."""
        self._counts: Dict[str, int] = defaultdict(int)
        self._latencies: Dict[str, List[float]] = defaultdict(list)
        self._errors: Dict[str, int] = defaultdict(int)
        self._start_times: Dict[str, float] = {}

    async def before_emit(self, event: Event) -> Optional[Event]:
        """Record event start."""
        self._counts[event.topic] += 1
        self._start_times[event.id] = time.time()
        return event

    async def after_emit(self, event: Event) -> None:
        """Record event completion."""
        if event.id in self._start_times:
            latency = time.time() - self._start_times[event.id]
            self._latencies[event.topic].append(latency)
            del self._start_times[event.id]

        if event.has_error:
            self._errors[event.topic] += 1

    def get_metrics(self) -> Dict[str, Any]:
        """Get collected metrics."""
        result = {}

        for topic in self._counts:
            latencies = self._latencies.get(topic, [])
            avg_latency = sum(latencies) / len(latencies) if latencies else 0

            result[topic] = {
                "count": self._counts[topic],
                "errors": self._errors.get(topic, 0),
                "avg_latency_ms": avg_latency * 1000,
                "max_latency_ms": max(latencies) * 1000 if latencies else 0,
            }

        return result

    def reset(self) -> None:
        """Reset all metrics."""
        self._counts.clear()
        self._latencies.clear()
        self._errors.clear()
        self._start_times.clear()


class BufferMiddleware(EventMiddleware):
    """Middleware that buffers events for batch processing."""

    def __init__(
        self,
        buffer_size: int = 100,
        flush_interval: float = 1.0,
        patterns: Optional[List[str]] = None,
    ):
        """
        Initialize buffer middleware.

        Args:
            buffer_size: Max events to buffer before flush
            flush_interval: Seconds between flushes
            patterns: Only buffer events matching these
        """
        self._buffer_size = buffer_size
        self._flush_interval = flush_interval
        self._patterns = patterns
        self._buffer: List[Event] = []
        self._handlers: List[Callable[[List[Event]], None]] = []
        self._last_flush = time.time()
        self._lock = asyncio.Lock()

    def on_flush(self, handler: Callable[[List[Event]], None]) -> None:
        """Register a flush handler."""
        self._handlers.append(handler)

    async def before_emit(self, event: Event) -> Optional[Event]:
        """Buffer event."""
        if self._patterns:
            if not any(event.matches_pattern(p) for p in self._patterns):
                return event

        async with self._lock:
            self._buffer.append(event)

            should_flush = (
                len(self._buffer) >= self._buffer_size or
                time.time() - self._last_flush >= self._flush_interval
            )

            if should_flush:
                await self._flush()

        return event

    async def _flush(self) -> None:
        """Flush the buffer."""
        if not self._buffer:
            return

        events = self._buffer.copy()
        self._buffer.clear()
        self._last_flush = time.time()

        for handler in self._handlers:
            try:
                handler(events)
            except Exception as e:
                logger.error(f"Buffer flush handler failed: {e}")

    async def flush(self) -> int:
        """Manually flush the buffer."""
        async with self._lock:
            count = len(self._buffer)
            await self._flush()
            return count
