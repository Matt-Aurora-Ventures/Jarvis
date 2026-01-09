"""
Event Definition

Defines the Event class and related types.

Events are the core message type in the event bus system.
They carry data from emitters to handlers.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from typing import Any, Dict, Optional


class EventPriority(IntEnum):
    """Priority levels for events."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class Event:
    """
    An event that can be emitted and handled.

    Attributes:
        topic: The event topic (e.g., "user.login", "trade.executed")
        data: Payload data for the event
        priority: Event priority level
        source: Identifier of the event source
        correlation_id: ID for tracking related events
        timestamp: When the event was created
        id: Unique event identifier
        metadata: Additional metadata
    """
    topic: str
    data: Dict[str, Any] = field(default_factory=dict)
    priority: EventPriority = EventPriority.NORMAL
    source: Optional[str] = None
    correlation_id: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Processing state
    _handled: bool = field(default=False, repr=False)
    _propagation_stopped: bool = field(default=False, repr=False)
    _error: Optional[Exception] = field(default=None, repr=False)

    def stop_propagation(self) -> None:
        """Stop the event from being handled by subsequent handlers."""
        self._propagation_stopped = True

    @property
    def is_propagation_stopped(self) -> bool:
        """Check if propagation is stopped."""
        return self._propagation_stopped

    def mark_handled(self) -> None:
        """Mark the event as handled."""
        self._handled = True

    @property
    def is_handled(self) -> bool:
        """Check if event was handled."""
        return self._handled

    def set_error(self, error: Exception) -> None:
        """Set an error that occurred during handling."""
        self._error = error

    @property
    def error(self) -> Optional[Exception]:
        """Get any error that occurred."""
        return self._error

    @property
    def has_error(self) -> bool:
        """Check if an error occurred."""
        return self._error is not None

    def matches_pattern(self, pattern: str) -> bool:
        """
        Check if this event's topic matches a pattern.

        Supports wildcards:
        - * matches a single segment
        - ** matches multiple segments

        Args:
            pattern: Pattern to match against

        Returns:
            True if topic matches pattern
        """
        if pattern == self.topic:
            return True

        if pattern == "**":
            return True

        pattern_parts = pattern.split(".")
        topic_parts = self.topic.split(".")

        return self._match_parts(pattern_parts, topic_parts)

    def _match_parts(self, pattern: list, topic: list) -> bool:
        """Recursively match pattern parts against topic parts."""
        if not pattern and not topic:
            return True

        if not pattern:
            return False

        if pattern[0] == "**":
            # ** can match zero or more segments
            if len(pattern) == 1:
                return True
            # Try matching remaining pattern at each position
            for i in range(len(topic) + 1):
                if self._match_parts(pattern[1:], topic[i:]):
                    return True
            return False

        if not topic:
            return False

        if pattern[0] == "*" or pattern[0] == topic[0]:
            return self._match_parts(pattern[1:], topic[1:])

        return False

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "id": self.id,
            "topic": self.topic,
            "data": self.data,
            "priority": self.priority.value,
            "source": self.source,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        """Create event from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            topic=data["topic"],
            data=data.get("data", {}),
            priority=EventPriority(data.get("priority", EventPriority.NORMAL)),
            source=data.get("source"),
            correlation_id=data.get("correlation_id"),
            timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else datetime.now(timezone.utc),
            metadata=data.get("metadata", {}),
        )

    def create_reply(
        self,
        topic: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> "Event":
        """Create a reply event with same correlation ID."""
        return Event(
            topic=topic,
            data=data or {},
            source=self.topic,
            correlation_id=self.correlation_id or self.id,
            priority=self.priority,
        )

    def create_derived(
        self,
        topic: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> "Event":
        """Create a derived event that inherits metadata."""
        return Event(
            topic=topic,
            data=data or self.data.copy(),
            source=self.topic,
            correlation_id=self.correlation_id or self.id,
            priority=self.priority,
            metadata={**self.metadata, "parent_event_id": self.id},
        )
