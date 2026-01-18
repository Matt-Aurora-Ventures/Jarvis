"""
JSON log formatter for structured logging.

Provides:
- JsonFormatter: Formats log records as JSON
- Automatic context inclusion (service, correlation_id, user_id, active_flags)
- Exception/traceback formatting
- Non-serializable object handling

Usage:
    from core.logging.json_formatter import JsonFormatter

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter(service="trading_engine"))
    logger.addHandler(handler)
"""

import json
import logging
import traceback
from datetime import datetime, timezone, date
from typing import Any, Dict, Optional


class JsonFormatter(logging.Formatter):
    """
    JSON structured log formatter.

    Produces log output in the format:
    {
        "timestamp": "2026-01-18T14:30:00.123456Z",
        "level": "INFO",
        "logger": "jarvis.trading",
        "message": "Trade executed",
        "service": "trading_engine",
        "correlation_id": "trade-abc123",
        "user_id": "tg_123",
        "active_flags": ["LIVE_TRADING_ENABLED"],
        "context": {"symbol": "SOL"},
        "duration_ms": 234.56,
        "function": "execute_trade",
        "line": 42,
        "error": null,
        "stack_trace": null
    }
    """

    def __init__(
        self,
        service: Optional[str] = None,
        include_location: bool = True,
        extra_fields: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the JSON formatter.

        Args:
            service: Default service name to include in all logs
            include_location: Whether to include function/line info
            extra_fields: Additional fields to include in all logs
        """
        super().__init__()
        self.service = service
        self.include_location = include_location
        self.extra_fields = extra_fields or {}

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as JSON."""
        # Build base log data
        log_data: Dict[str, Any] = {
            "timestamp": self._format_timestamp(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add service (from formatter or record)
        service = getattr(record, "service", None) or self.service
        if service:
            log_data["service"] = service

        # Add correlation_id from record
        correlation_id = getattr(record, "correlation_id", None)
        if correlation_id:
            log_data["correlation_id"] = correlation_id

        # Add user_id from record
        user_id = getattr(record, "user_id", None)
        if user_id:
            log_data["user_id"] = user_id

        # Add active_flags from record
        active_flags = getattr(record, "active_flags", None)
        if active_flags:
            log_data["active_flags"] = active_flags

        # Add context from record
        context = getattr(record, "context", None)
        if context:
            log_data["context"] = context

        # Add duration_ms from record
        duration_ms = getattr(record, "duration_ms", None)
        if duration_ms is not None:
            log_data["duration_ms"] = duration_ms

        # Add location info
        if self.include_location:
            log_data["function"] = record.funcName
            log_data["line"] = record.lineno
            if record.pathname:
                log_data["module"] = record.module

        # Add exception info
        if record.exc_info:
            log_data["error"] = self._format_error(record.exc_info)
            log_data["stack_trace"] = self._format_traceback(record.exc_info)

        # Add any extra fields from formatter config
        log_data.update(self.extra_fields)

        # Add any extra fields added via the extra= parameter
        for key, value in record.__dict__.items():
            if key not in (
                "name",
                "msg",
                "args",
                "created",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "stack_info",
                "exc_info",
                "exc_text",
                "thread",
                "threadName",
                "taskName",
                "message",
                "service",
                "correlation_id",
                "user_id",
                "active_flags",
                "context",
                "duration_ms",
            ):
                if not key.startswith("_"):
                    log_data[key] = value

        return json.dumps(log_data, default=self._json_serializer)

    def _format_timestamp(self, record: logging.LogRecord) -> str:
        """Format timestamp as ISO8601 with Z suffix."""
        # Convert record.created (epoch float) to datetime
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"

    def _format_error(self, exc_info) -> Optional[str]:
        """Format exception type and message."""
        if exc_info and exc_info[0]:
            exc_type = exc_info[0].__name__ if exc_info[0] else "Unknown"
            exc_msg = str(exc_info[1]) if exc_info[1] else ""
            return f"{exc_type}: {exc_msg}"
        return None

    def _format_traceback(self, exc_info) -> Optional[str]:
        """Format full traceback."""
        if exc_info:
            return "".join(traceback.format_exception(*exc_info))
        return None

    def _json_serializer(self, obj: Any) -> Any:
        """Custom JSON serializer for non-standard types."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, date):
            return obj.isoformat()
        if isinstance(obj, bytes):
            return obj.decode("utf-8", errors="replace")
        if hasattr(obj, "__dict__"):
            return str(obj)
        return str(obj)


class CompactJsonFormatter(JsonFormatter):
    """
    Compact JSON formatter that omits null values and location info.

    Useful for high-volume logging where space matters.
    """

    def __init__(self, service: Optional[str] = None):
        super().__init__(service=service, include_location=False)

    def format(self, record: logging.LogRecord) -> str:
        """Format with null values omitted."""
        full_json = super().format(record)
        data = json.loads(full_json)

        # Remove null/empty values
        clean_data = {k: v for k, v in data.items() if v is not None and v != [] and v != {}}

        return json.dumps(clean_data, default=self._json_serializer, separators=(",", ":"))
