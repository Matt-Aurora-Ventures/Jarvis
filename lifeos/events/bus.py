"""
Event Bus

The central event distribution system.

Features:
- Async event emission
- Topic-based subscriptions with wildcards
- Handler priorities
- Event middleware
- History and replay
- Dead letter queue
"""

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import (
    Any,
    Callable,
    Coroutine,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Union,
)

from lifeos.events.event import Event, EventPriority

logger = logging.getLogger(__name__)

# Type for event handlers
EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


@dataclass
class Subscription:
    """A subscription to an event topic."""
    pattern: str
    handler: EventHandler
    priority: int = 0
    once: bool = False
    filter_fn: Optional[Callable[[Event], bool]] = None
    id: str = field(default_factory=lambda: str(id(object())))


@dataclass
class DeadLetter:
    """Record of a failed event handling."""
    event: Event
    handler_id: str
    error: Exception
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    retry_count: int = 0


class EventBus:
    """
    Central event bus for async event distribution.

    Supports:
    - Topic-based subscriptions with wildcards
    - Handler priorities
    - Event middleware
    - Event history
    - Dead letter queue for failed handlers
    """

    def __init__(
        self,
        max_history: int = 1000,
        max_dead_letters: int = 100,
        retry_failed: bool = False,
        max_retries: int = 3,
    ):
        """
        Initialize event bus.

        Args:
            max_history: Maximum events to keep in history
            max_dead_letters: Maximum dead letters to keep
            retry_failed: Whether to retry failed handlers
            max_retries: Maximum retry attempts
        """
        self._subscriptions: Dict[str, List[Subscription]] = defaultdict(list)
        self._middleware: List["EventMiddleware"] = []
        self._history: List[Event] = []
        self._dead_letters: List[DeadLetter] = []
        self._max_history = max_history
        self._max_dead_letters = max_dead_letters
        self._retry_failed = retry_failed
        self._max_retries = max_retries
        self._stats = {
            "events_emitted": 0,
            "events_handled": 0,
            "handlers_failed": 0,
        }
        self._paused = False
        self._pending_events: List[Event] = []

    # =========================================================================
    # Subscription Methods
    # =========================================================================

    def on(
        self,
        pattern: str,
        priority: int = 0,
        once: bool = False,
        filter_fn: Optional[Callable[[Event], bool]] = None,
    ) -> Callable[[EventHandler], EventHandler]:
        """
        Decorator to subscribe a handler to an event pattern.

        Args:
            pattern: Topic pattern to match (supports * and **)
            priority: Handler priority (higher runs first)
            once: If True, handler is removed after first call
            filter_fn: Optional filter function

        Returns:
            Decorator function

        Example:
            @bus.on("user.*")
            async def handle_user_events(event):
                print(event.topic)
        """
        def decorator(handler: EventHandler) -> EventHandler:
            self.subscribe(pattern, handler, priority, once, filter_fn)
            return handler
        return decorator

    def subscribe(
        self,
        pattern: str,
        handler: EventHandler,
        priority: int = 0,
        once: bool = False,
        filter_fn: Optional[Callable[[Event], bool]] = None,
    ) -> str:
        """
        Subscribe a handler to an event pattern.

        Args:
            pattern: Topic pattern to match
            handler: Async handler function
            priority: Handler priority
            once: Remove after first call
            filter_fn: Optional filter

        Returns:
            Subscription ID
        """
        subscription = Subscription(
            pattern=pattern,
            handler=handler,
            priority=priority,
            once=once,
            filter_fn=filter_fn,
        )

        self._subscriptions[pattern].append(subscription)
        self._subscriptions[pattern].sort(key=lambda s: -s.priority)

        logger.debug(f"Subscribed to {pattern} with priority {priority}")
        return subscription.id

    def unsubscribe(self, pattern: str, handler: Optional[EventHandler] = None) -> bool:
        """
        Unsubscribe from a pattern.

        Args:
            pattern: Pattern to unsubscribe from
            handler: Specific handler to remove (all if None)

        Returns:
            True if any subscriptions were removed
        """
        if pattern not in self._subscriptions:
            return False

        if handler is None:
            del self._subscriptions[pattern]
            return True

        original_length = len(self._subscriptions[pattern])
        self._subscriptions[pattern] = [
            s for s in self._subscriptions[pattern]
            if s.handler is not handler
        ]

        return len(self._subscriptions[pattern]) < original_length

    def unsubscribe_by_id(self, subscription_id: str) -> bool:
        """Unsubscribe by subscription ID."""
        for pattern, subs in self._subscriptions.items():
            for sub in subs:
                if sub.id == subscription_id:
                    self._subscriptions[pattern].remove(sub)
                    return True
        return False

    # =========================================================================
    # Emission Methods
    # =========================================================================

    async def emit(
        self,
        topic: str,
        data: Optional[Dict[str, Any]] = None,
        priority: EventPriority = EventPriority.NORMAL,
        source: Optional[str] = None,
        correlation_id: Optional[str] = None,
        wait: bool = True,
    ) -> Event:
        """
        Emit an event.

        Args:
            topic: Event topic
            data: Event data
            priority: Event priority
            source: Event source identifier
            correlation_id: Correlation ID for tracking
            wait: If True, wait for all handlers to complete

        Returns:
            The emitted event
        """
        event = Event(
            topic=topic,
            data=data or {},
            priority=priority,
            source=source,
            correlation_id=correlation_id,
        )

        return await self.emit_event(event, wait=wait)

    async def emit_event(self, event: Event, wait: bool = True) -> Event:
        """
        Emit a pre-constructed event.

        Args:
            event: Event to emit
            wait: If True, wait for handlers

        Returns:
            The event (possibly modified by handlers)
        """
        if self._paused:
            self._pending_events.append(event)
            return event

        self._stats["events_emitted"] += 1

        # Apply middleware (before)
        for middleware in self._middleware:
            event = await middleware.before_emit(event)
            if event is None:
                return event

        # Find matching handlers
        handlers = self._get_matching_handlers(event)

        # Execute handlers
        if wait:
            await self._execute_handlers(event, handlers)
        else:
            asyncio.create_task(self._execute_handlers(event, handlers))

        # Apply middleware (after)
        for middleware in reversed(self._middleware):
            await middleware.after_emit(event)

        # Add to history
        self._add_to_history(event)

        return event

    async def emit_many(
        self,
        events: List[Union[Event, Tuple[str, Dict[str, Any]]]],
        wait: bool = True,
    ) -> List[Event]:
        """
        Emit multiple events.

        Args:
            events: List of events or (topic, data) tuples
            wait: If True, wait for all handlers

        Returns:
            List of emitted events
        """
        results = []

        for item in events:
            if isinstance(item, Event):
                event = await self.emit_event(item, wait=wait)
            else:
                topic, data = item
                event = await self.emit(topic, data, wait=wait)
            results.append(event)

        return results

    def _get_matching_handlers(self, event: Event) -> List[Subscription]:
        """Get all handlers that match this event."""
        matching = []

        for pattern, subscriptions in self._subscriptions.items():
            if event.matches_pattern(pattern):
                for sub in subscriptions:
                    # Check filter
                    if sub.filter_fn and not sub.filter_fn(event):
                        continue
                    matching.append(sub)

        # Sort by priority
        matching.sort(key=lambda s: -s.priority)
        return matching

    async def _execute_handlers(
        self,
        event: Event,
        handlers: List[Subscription],
    ) -> None:
        """Execute handlers for an event."""
        to_remove = []

        for sub in handlers:
            if event.is_propagation_stopped:
                break

            try:
                await sub.handler(event)
                self._stats["events_handled"] += 1
                event.mark_handled()

                if sub.once:
                    to_remove.append(sub)

            except Exception as e:
                logger.error(f"Handler failed for {event.topic}: {e}")
                self._stats["handlers_failed"] += 1
                event.set_error(e)

                self._add_dead_letter(event, sub.id, e)

                if self._retry_failed:
                    await self._retry_handler(event, sub, e)

        # Remove once handlers
        for sub in to_remove:
            self._subscriptions[sub.pattern].remove(sub)

    async def _retry_handler(
        self,
        event: Event,
        sub: Subscription,
        error: Exception,
    ) -> None:
        """Retry a failed handler."""
        for retry in range(self._max_retries):
            try:
                await asyncio.sleep(0.1 * (retry + 1))  # Backoff
                await sub.handler(event)
                logger.info(f"Handler succeeded on retry {retry + 1}")
                return
            except Exception as e:
                error = e

        logger.error(f"Handler failed after {self._max_retries} retries")

    # =========================================================================
    # Middleware
    # =========================================================================

    def use(self, middleware: "EventMiddleware") -> None:
        """Add middleware to the bus."""
        self._middleware.append(middleware)

    def remove_middleware(self, middleware: "EventMiddleware") -> bool:
        """Remove middleware from the bus."""
        if middleware in self._middleware:
            self._middleware.remove(middleware)
            return True
        return False

    # =========================================================================
    # History and Replay
    # =========================================================================

    def _add_to_history(self, event: Event) -> None:
        """Add event to history."""
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history.pop(0)

    def get_history(
        self,
        pattern: Optional[str] = None,
        limit: int = 100,
    ) -> List[Event]:
        """
        Get event history.

        Args:
            pattern: Optional pattern to filter by
            limit: Maximum events to return

        Returns:
            List of events
        """
        if pattern is None:
            return self._history[-limit:]

        matching = [e for e in self._history if e.matches_pattern(pattern)]
        return matching[-limit:]

    async def replay(
        self,
        pattern: Optional[str] = None,
        since: Optional[datetime] = None,
        handler: Optional[EventHandler] = None,
    ) -> int:
        """
        Replay events from history.

        Args:
            pattern: Pattern to filter by
            since: Only replay events after this time
            handler: Specific handler to replay to (all if None)

        Returns:
            Number of events replayed
        """
        events = self.get_history(pattern)

        if since:
            events = [e for e in events if e.timestamp >= since]

        count = 0
        for event in events:
            if handler:
                try:
                    await handler(event)
                    count += 1
                except Exception as e:
                    logger.error(f"Replay handler failed: {e}")
            else:
                await self.emit_event(event)
                count += 1

        return count

    def clear_history(self) -> int:
        """Clear event history."""
        count = len(self._history)
        self._history.clear()
        return count

    # =========================================================================
    # Dead Letter Queue
    # =========================================================================

    def _add_dead_letter(
        self,
        event: Event,
        handler_id: str,
        error: Exception,
    ) -> None:
        """Add failed event to dead letter queue."""
        dead_letter = DeadLetter(
            event=event,
            handler_id=handler_id,
            error=error,
        )
        self._dead_letters.append(dead_letter)

        if len(self._dead_letters) > self._max_dead_letters:
            self._dead_letters.pop(0)

    def get_dead_letters(self, limit: int = 100) -> List[DeadLetter]:
        """Get dead letters."""
        return self._dead_letters[-limit:]

    def clear_dead_letters(self) -> int:
        """Clear dead letter queue."""
        count = len(self._dead_letters)
        self._dead_letters.clear()
        return count

    # =========================================================================
    # Control Methods
    # =========================================================================

    def pause(self) -> None:
        """Pause event processing (events are queued)."""
        self._paused = True

    async def resume(self) -> int:
        """Resume event processing and flush pending events."""
        self._paused = False
        count = len(self._pending_events)

        for event in self._pending_events:
            await self.emit_event(event)

        self._pending_events.clear()
        return count

    @property
    def is_paused(self) -> bool:
        """Check if bus is paused."""
        return self._paused

    # =========================================================================
    # Utilities
    # =========================================================================

    def get_subscriptions(self, pattern: Optional[str] = None) -> Dict[str, int]:
        """Get subscription counts by pattern."""
        if pattern:
            return {pattern: len(self._subscriptions.get(pattern, []))}

        return {p: len(subs) for p, subs in self._subscriptions.items()}

    def get_stats(self) -> Dict[str, Any]:
        """Get bus statistics."""
        return {
            **self._stats,
            "subscription_count": sum(len(s) for s in self._subscriptions.values()),
            "pattern_count": len(self._subscriptions),
            "history_size": len(self._history),
            "dead_letter_count": len(self._dead_letters),
            "pending_events": len(self._pending_events),
            "is_paused": self._paused,
            "middleware_count": len(self._middleware),
        }

    def clear(self) -> None:
        """Clear all subscriptions, history, and dead letters."""
        self._subscriptions.clear()
        self._history.clear()
        self._dead_letters.clear()
        self._pending_events.clear()
        self._stats = {
            "events_emitted": 0,
            "events_handled": 0,
            "handlers_failed": 0,
        }


# Import middleware base class for type hints
from lifeos.events.middleware import EventMiddleware
