"""
JARVIS Log Aggregation

Centralized log collection, aggregation, and querying.
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Any, Pattern
from collections import deque, defaultdict
from pathlib import Path
import threading

logger = logging.getLogger(__name__)


class LogLevel(Enum):
    """Log severity levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

    @classmethod
    def from_string(cls, level: str) -> "LogLevel":
        """Parse log level from string."""
        return cls[level.upper()]

    @property
    def severity(self) -> int:
        """Get numeric severity."""
        severities = {
            "DEBUG": 10,
            "INFO": 20,
            "WARNING": 30,
            "ERROR": 40,
            "CRITICAL": 50
        }
        return severities.get(self.value, 0)


@dataclass
class LogEntry:
    """A single log entry."""
    timestamp: datetime
    level: LogLevel
    message: str
    source: str
    logger_name: str = ""
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    user_id: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "message": self.message,
            "source": self.source,
            "logger_name": self.logger_name,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "user_id": self.user_id,
            "extra": self.extra
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LogEntry":
        """Create from dictionary."""
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            level=LogLevel.from_string(data["level"]),
            message=data["message"],
            source=data["source"],
            logger_name=data.get("logger_name", ""),
            trace_id=data.get("trace_id"),
            span_id=data.get("span_id"),
            user_id=data.get("user_id"),
            extra=data.get("extra", {})
        )


@dataclass
class LogQuery:
    """Query parameters for log search."""
    min_level: Optional[LogLevel] = None
    sources: Optional[List[str]] = None
    message_pattern: Optional[str] = None
    trace_id: Optional[str] = None
    user_id: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: int = 100
    offset: int = 0


@dataclass
class LogStats:
    """Aggregated log statistics."""
    total_entries: int
    entries_by_level: Dict[str, int]
    entries_by_source: Dict[str, int]
    error_rate_per_minute: float
    top_errors: List[Dict[str, Any]]
    time_range_start: Optional[datetime]
    time_range_end: Optional[datetime]


class AggregatingHandler(logging.Handler):
    """Logging handler that sends logs to the aggregator."""

    def __init__(self, aggregator: "LogAggregator", source: str = "app"):
        super().__init__()
        self.aggregator = aggregator
        self.source = source

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record to the aggregator."""
        try:
            entry = LogEntry(
                timestamp=datetime.fromtimestamp(record.created),
                level=LogLevel.from_string(record.levelname),
                message=record.getMessage(),
                source=self.source,
                logger_name=record.name,
                trace_id=getattr(record, 'trace_id', None),
                span_id=getattr(record, 'span_id', None),
                user_id=getattr(record, 'user_id', None),
                extra={
                    "filename": record.filename,
                    "lineno": record.lineno,
                    "funcName": record.funcName,
                    "pathname": record.pathname,
                }
            )
            self.aggregator.add_entry(entry)
        except Exception:
            self.handleError(record)


class LogAggregator:
    """Centralized log aggregation."""

    def __init__(
        self,
        max_entries: int = 100_000,
        flush_interval_seconds: int = 60,
        persist_path: Optional[Path] = None
    ):
        self.max_entries = max_entries
        self.flush_interval = flush_interval_seconds
        self.persist_path = persist_path

        self._entries: deque[LogEntry] = deque(maxlen=max_entries)
        self._lock = threading.Lock()
        self._running = False
        self._flush_task: Optional[asyncio.Task] = None

        # Indexes for fast lookup
        self._by_level: Dict[LogLevel, List[int]] = defaultdict(list)
        self._by_source: Dict[str, List[int]] = defaultdict(list)
        self._by_trace: Dict[str, List[int]] = defaultdict(list)

        # Error patterns for aggregation
        self._error_patterns: Dict[str, int] = defaultdict(int)

        # Callbacks
        self._on_error: List[Callable[[LogEntry], None]] = []

    def add_entry(self, entry: LogEntry) -> None:
        """Add a log entry."""
        with self._lock:
            idx = len(self._entries)
            self._entries.append(entry)

            # Update indexes
            self._by_level[entry.level].append(idx)
            self._by_source[entry.source].append(idx)
            if entry.trace_id:
                self._by_trace[entry.trace_id].append(idx)

            # Track error patterns
            if entry.level in (LogLevel.ERROR, LogLevel.CRITICAL):
                pattern = self._extract_error_pattern(entry.message)
                self._error_patterns[pattern] += 1

                # Notify error callbacks
                for callback in self._on_error:
                    try:
                        callback(entry)
                    except Exception:
                        pass

    def _extract_error_pattern(self, message: str) -> str:
        """Extract a normalized error pattern from a message."""
        # Remove numbers, UUIDs, timestamps
        pattern = re.sub(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', '<UUID>', message)
        pattern = re.sub(r'\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}', '<TIMESTAMP>', pattern)
        pattern = re.sub(r'\b\d+\b', '<NUM>', pattern)
        pattern = re.sub(r'\b0x[0-9a-fA-F]+\b', '<HEX>', pattern)
        return pattern[:200]  # Limit length

    def query(self, query: LogQuery) -> List[LogEntry]:
        """Query log entries."""
        with self._lock:
            results = []
            entries = list(self._entries)

            # Apply filters
            for entry in reversed(entries):  # Most recent first
                if query.min_level and entry.level.severity < query.min_level.severity:
                    continue

                if query.sources and entry.source not in query.sources:
                    continue

                if query.message_pattern:
                    if not re.search(query.message_pattern, entry.message, re.IGNORECASE):
                        continue

                if query.trace_id and entry.trace_id != query.trace_id:
                    continue

                if query.user_id and entry.user_id != query.user_id:
                    continue

                if query.start_time and entry.timestamp < query.start_time:
                    continue

                if query.end_time and entry.timestamp > query.end_time:
                    continue

                results.append(entry)

                if len(results) >= query.limit + query.offset:
                    break

            return results[query.offset:query.offset + query.limit]

    def get_stats(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> LogStats:
        """Get aggregated statistics."""
        with self._lock:
            entries = list(self._entries)

            # Filter by time range
            if start_time or end_time:
                entries = [
                    e for e in entries
                    if (not start_time or e.timestamp >= start_time)
                    and (not end_time or e.timestamp <= end_time)
                ]

            # Count by level
            by_level: Dict[str, int] = defaultdict(int)
            for entry in entries:
                by_level[entry.level.value] += 1

            # Count by source
            by_source: Dict[str, int] = defaultdict(int)
            for entry in entries:
                by_source[entry.source] += 1

            # Calculate error rate
            error_count = by_level.get("ERROR", 0) + by_level.get("CRITICAL", 0)
            if entries:
                time_range = (entries[-1].timestamp - entries[0].timestamp).total_seconds()
                minutes = max(time_range / 60, 1)
                error_rate = error_count / minutes
            else:
                error_rate = 0.0

            # Top error patterns
            top_errors = sorted(
                self._error_patterns.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]

            return LogStats(
                total_entries=len(entries),
                entries_by_level=dict(by_level),
                entries_by_source=dict(by_source),
                error_rate_per_minute=error_rate,
                top_errors=[{"pattern": p, "count": c} for p, c in top_errors],
                time_range_start=entries[0].timestamp if entries else None,
                time_range_end=entries[-1].timestamp if entries else None
            )

    def get_trace(self, trace_id: str) -> List[LogEntry]:
        """Get all log entries for a trace."""
        query = LogQuery(trace_id=trace_id, limit=1000)
        return self.query(query)

    def on_error(self, callback: Callable[[LogEntry], None]) -> None:
        """Register callback for error logs."""
        self._on_error.append(callback)

    def create_handler(self, source: str = "app") -> AggregatingHandler:
        """Create a logging handler for this aggregator."""
        return AggregatingHandler(self, source)

    def attach_to_logger(
        self,
        logger_name: str = "",
        source: str = "app",
        level: int = logging.DEBUG
    ) -> None:
        """Attach aggregator to a logger."""
        log = logging.getLogger(logger_name)
        handler = self.create_handler(source)
        handler.setLevel(level)
        log.addHandler(handler)

    async def start_persistence(self) -> None:
        """Start background persistence."""
        if not self.persist_path:
            return

        self._running = True
        self._flush_task = asyncio.create_task(self._persistence_loop())
        logger.info("Log persistence started")

    async def stop_persistence(self) -> None:
        """Stop background persistence."""
        self._running = False
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

        # Final flush
        if self.persist_path:
            self._flush_to_disk()

    async def _persistence_loop(self) -> None:
        """Background persistence loop."""
        while self._running:
            await asyncio.sleep(self.flush_interval)
            self._flush_to_disk()

    def _flush_to_disk(self) -> None:
        """Flush logs to disk."""
        if not self.persist_path:
            return

        try:
            self.persist_path.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            log_file = self.persist_path / f"logs_{timestamp}.jsonl"

            with self._lock:
                entries = list(self._entries)

            with open(log_file, 'w') as f:
                for entry in entries:
                    f.write(json.dumps(entry.to_dict()) + "\n")

            logger.debug(f"Flushed {len(entries)} logs to {log_file}")

        except Exception as e:
            logger.error(f"Failed to flush logs: {e}")

    def load_from_disk(self, log_file: Path) -> int:
        """Load logs from a disk file."""
        count = 0
        try:
            with open(log_file, 'r') as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        entry = LogEntry.from_dict(data)
                        self.add_entry(entry)
                        count += 1
                    except Exception:
                        continue
        except Exception as e:
            logger.error(f"Failed to load logs from {log_file}: {e}")

        return count

    def clear(self) -> int:
        """Clear all logs and return count."""
        with self._lock:
            count = len(self._entries)
            self._entries.clear()
            self._by_level.clear()
            self._by_source.clear()
            self._by_trace.clear()
            self._error_patterns.clear()
            return count

    def export_json(self, path: Path) -> int:
        """Export all logs to JSON file."""
        with self._lock:
            entries = list(self._entries)

        with open(path, 'w') as f:
            json.dump([e.to_dict() for e in entries], f, indent=2)

        return len(entries)


# Global instance
_log_aggregator: Optional[LogAggregator] = None


def get_log_aggregator() -> LogAggregator:
    """Get the global log aggregator instance."""
    global _log_aggregator
    if _log_aggregator is None:
        _log_aggregator = LogAggregator()
    return _log_aggregator


def setup_log_aggregation(
    sources: Optional[List[str]] = None,
    persist_path: Optional[Path] = None
) -> LogAggregator:
    """Set up log aggregation for the application."""
    global _log_aggregator

    _log_aggregator = LogAggregator(persist_path=persist_path)

    # Default sources to aggregate
    default_sources = sources or [
        "",  # Root logger
        "core",
        "api",
        "bots",
        "integrations"
    ]

    for source in default_sources:
        _log_aggregator.attach_to_logger(source, source or "root")

    return _log_aggregator


# Context manager for trace-aware logging
class LogContext:
    """Context manager for adding trace context to logs."""

    _local = threading.local()

    def __init__(
        self,
        trace_id: Optional[str] = None,
        span_id: Optional[str] = None,
        user_id: Optional[str] = None
    ):
        self.trace_id = trace_id
        self.span_id = span_id
        self.user_id = user_id
        self._old_factory = None

    def __enter__(self):
        # Store old factory
        self._old_factory = logging.getLogRecordFactory()

        # Create new factory that adds context
        old_factory = self._old_factory
        context = self

        def record_factory(*args, **kwargs):
            record = old_factory(*args, **kwargs)
            record.trace_id = context.trace_id
            record.span_id = context.span_id
            record.user_id = context.user_id
            return record

        logging.setLogRecordFactory(record_factory)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore old factory
        if self._old_factory:
            logging.setLogRecordFactory(self._old_factory)
        return False
