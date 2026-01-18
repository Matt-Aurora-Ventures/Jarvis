"""
Data models for structured logging.

Provides:
- LogEntry: Complete log entry with all fields
- LogContext: Reusable context object for correlation
- BusinessEvent: High-level business event wrapper

These models ensure consistent log structure across all Jarvis components.
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class LogEntry:
    """
    Complete structured log entry.

    Schema matches the JSON log format:
    {
      "timestamp": "2026-01-18T14:30:00.123456Z",
      "level": "INFO",
      "logger": "jarvis.trading",
      "message": "Trade executed successfully",
      "service": "trading_engine",
      "correlation_id": "trade-abc123-def456",
      "user_id": "tg_8527130908",
      "active_flags": ["LIVE_TRADING_ENABLED"],
      "context": {"symbol": "SOL", "action": "BUY"},
      "duration_ms": 234.56,
      "error": null,
      "stack_trace": null
    }
    """

    timestamp: datetime
    level: str
    logger: str
    message: str
    service: Optional[str] = None
    correlation_id: Optional[str] = None
    user_id: Optional[str] = None
    active_flags: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    duration_ms: Optional[float] = None
    error: Optional[str] = None
    stack_trace: Optional[str] = None
    location: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with ISO8601 timestamp."""
        data = {}

        # Format timestamp as ISO8601 with Z suffix
        if isinstance(self.timestamp, datetime):
            if self.timestamp.tzinfo is None:
                # Assume UTC if no timezone
                ts = self.timestamp.replace(tzinfo=timezone.utc)
            else:
                ts = self.timestamp.astimezone(timezone.utc)
            data["timestamp"] = ts.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"
        else:
            data["timestamp"] = str(self.timestamp)

        data["level"] = self.level
        data["logger"] = self.logger
        data["message"] = self.message

        # Only include non-None optional fields
        if self.service:
            data["service"] = self.service
        if self.correlation_id:
            data["correlation_id"] = self.correlation_id
        if self.user_id:
            data["user_id"] = self.user_id
        if self.active_flags:
            data["active_flags"] = self.active_flags
        if self.context:
            data["context"] = self.context
        if self.duration_ms is not None:
            data["duration_ms"] = self.duration_ms
        if self.error:
            data["error"] = self.error
        if self.stack_trace:
            data["stack_trace"] = self.stack_trace
        if self.location:
            data["location"] = self.location

        return data

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str)


@dataclass
class LogContext:
    """
    Reusable logging context for correlation tracking.

    Use this to maintain context across related operations:
        ctx = LogContext(service="trading", correlation_id="trade-123")
        logger.set_context(**ctx.to_dict())
    """

    service: Optional[str] = None
    correlation_id: Optional[str] = None
    user_id: Optional[str] = None
    active_flags: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logger context."""
        data = {}
        if self.service:
            data["service"] = self.service
        if self.correlation_id:
            data["correlation_id"] = self.correlation_id
        if self.user_id:
            data["user_id"] = self.user_id
        if self.active_flags:
            data["active_flags"] = self.active_flags
        if self.extra:
            data.update(self.extra)
        return data

    def merge(self, other: "LogContext") -> "LogContext":
        """
        Merge with another context, preferring non-None values from other.

        Returns a new LogContext with combined values.
        """
        return LogContext(
            service=other.service or self.service,
            correlation_id=other.correlation_id or self.correlation_id,
            user_id=other.user_id or self.user_id,
            active_flags=list(set(self.active_flags + other.active_flags)),
            extra={**self.extra, **other.extra},
        )


@dataclass
class BusinessEvent:
    """
    High-level business event wrapper.

    Use for significant business events that should be easily queryable:
        event = BusinessEvent("TRADE_EXECUTED", symbol="SOL", amount=100)
        logger.log_event(event.event_name, **event.data)
    """

    event_name: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)

    def to_log_entry(
        self,
        logger_name: str,
        level: str = "INFO",
        service: Optional[str] = None,
        correlation_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> LogEntry:
        """Convert to a LogEntry for structured logging."""
        return LogEntry(
            timestamp=self.timestamp or datetime.now(timezone.utc),
            level=level,
            logger=logger_name,
            message=f"[EVENT] {self.event_name}",
            service=service,
            correlation_id=correlation_id,
            user_id=user_id,
            context=self.data,
        )


# Common business event types for Jarvis
class EventTypes:
    """Standard event type constants for consistency."""

    # Trading events
    TRADE_SIGNAL_GENERATED = "TRADE_SIGNAL_GENERATED"
    TRADE_EXECUTED = "TRADE_EXECUTED"
    TRADE_FAILED = "TRADE_FAILED"
    POSITION_OPENED = "POSITION_OPENED"
    POSITION_CLOSED = "POSITION_CLOSED"
    STOP_LOSS_TRIGGERED = "STOP_LOSS_TRIGGERED"
    TAKE_PROFIT_TRIGGERED = "TAKE_PROFIT_TRIGGERED"

    # User events
    USER_COMMAND = "USER_COMMAND"
    USER_LOGIN = "USER_LOGIN"
    USER_WALLET_CONNECTED = "USER_WALLET_CONNECTED"

    # System events
    SERVICE_STARTED = "SERVICE_STARTED"
    SERVICE_STOPPED = "SERVICE_STOPPED"
    SERVICE_ERROR = "SERVICE_ERROR"
    COMPONENT_RESTART = "COMPONENT_RESTART"

    # AI/Analysis events
    SENTIMENT_ANALYZED = "SENTIMENT_ANALYZED"
    SIGNAL_AGGREGATED = "SIGNAL_AGGREGATED"
    GROK_QUERY = "GROK_QUERY"
