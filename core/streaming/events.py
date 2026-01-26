"""
Shared event types for the streaming module.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class EventType(Enum):
    """Base event types for streaming."""
    ACCOUNT_UPDATE = "account_update"
    POOL_UPDATE = "pool_update"
    WHALE_ACTIVITY = "whale_activity"
    CONNECTION_STATE = "connection_state"
    ERROR = "error"


@dataclass
class StreamingEvent:
    """Base class for all streaming events."""
    event_type: EventType
    timestamp: float = field(default_factory=time.time)
    data: Dict[str, Any] = field(default_factory=dict)
    source: str = "geyser"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize event to dictionary."""
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "data": self.data,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StreamingEvent":
        """Deserialize event from dictionary."""
        return cls(
            event_type=EventType(data["event_type"]),
            timestamp=data.get("timestamp", time.time()),
            data=data.get("data", {}),
            source=data.get("source", "geyser"),
        )
