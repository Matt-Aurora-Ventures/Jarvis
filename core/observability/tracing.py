"""
Observability - Distributed tracing and correlation for Jarvis bots.

This module provides:
- Trace ID generation and propagation
- Correlation of operations across components (Telegram -> Trade -> X post)
- Structured logging with trace context
- Metrics collection helpers

Usage:
    from core.observability import TraceContext, get_trace_id, traced

    # Start a new trace
    with TraceContext("process_trade") as ctx:
        logger.info(f"Processing trade", extra={"trace_id": ctx.trace_id})
        await execute_trade()

    # Or use decorator
    @traced("execute_trade")
    async def execute_trade():
        ...

    # Get current trace ID anywhere
    trace_id = get_trace_id()
"""

import asyncio
import contextvars
import functools
import logging
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, TypeVar

logger = logging.getLogger(__name__)

# Context variable for trace propagation
_current_trace: contextvars.ContextVar[Optional["TraceContext"]] = contextvars.ContextVar(
    "current_trace", default=None
)

T = TypeVar("T")


def generate_trace_id() -> str:
    """Generate a unique trace ID."""
    return uuid.uuid4().hex[:16]


def generate_span_id() -> str:
    """Generate a unique span ID."""
    return uuid.uuid4().hex[:8]


@dataclass
class Span:
    """A single operation within a trace."""
    span_id: str
    name: str
    trace_id: str
    parent_span_id: Optional[str] = None
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    status: str = "ok"
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def duration_ms(self) -> Optional[float]:
        """Get span duration in milliseconds."""
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return None

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        """Add an event to this span."""
        self.events.append({
            "name": name,
            "timestamp": time.time(),
            "attributes": attributes or {},
        })

    def set_attribute(self, key: str, value: Any) -> None:
        """Set an attribute on this span."""
        self.attributes[key] = value

    def set_error(self, error: Exception) -> None:
        """Mark span as errored."""
        self.status = "error"
        self.attributes["error.type"] = type(error).__name__
        self.attributes["error.message"] = str(error)

    def finish(self) -> None:
        """Mark span as finished."""
        self.end_time = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """Convert span to dictionary for logging/export."""
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
            "end_time": datetime.fromtimestamp(self.end_time).isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "attributes": self.attributes,
            "events": self.events,
        }


class TraceContext:
    """
    Context manager for distributed tracing.

    Creates a new trace or continues an existing one.
    Automatically propagates trace context to child operations.
    """

    def __init__(
        self,
        operation_name: str,
        trace_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize trace context.

        Args:
            operation_name: Name of the operation being traced
            trace_id: Existing trace ID to continue, or None for new trace
            parent_span_id: Parent span ID if this is a child span
            attributes: Initial attributes for the span
        """
        self.operation_name = operation_name
        self._token: Optional[contextvars.Token] = None

        # Get parent context if exists
        parent = _current_trace.get()

        if trace_id:
            self.trace_id = trace_id
        elif parent:
            self.trace_id = parent.trace_id
        else:
            self.trace_id = generate_trace_id()

        if parent_span_id:
            self._parent_span_id = parent_span_id
        elif parent:
            self._parent_span_id = parent.current_span.span_id
        else:
            self._parent_span_id = None

        # Create the span
        self.current_span = Span(
            span_id=generate_span_id(),
            name=operation_name,
            trace_id=self.trace_id,
            parent_span_id=self._parent_span_id,
            attributes=attributes or {},
        )

        self.spans: List[Span] = [self.current_span]

    def __enter__(self) -> "TraceContext":
        """Enter trace context."""
        self._token = _current_trace.set(self)
        logger.debug(
            f"[TRACE:{self.trace_id}] Started span: {self.operation_name}",
            extra={"trace_id": self.trace_id, "span_id": self.current_span.span_id}
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit trace context."""
        if exc_val:
            self.current_span.set_error(exc_val)

        self.current_span.finish()

        # Log span completion
        duration = self.current_span.duration_ms
        level = logging.WARNING if self.current_span.status == "error" else logging.DEBUG
        logger.log(
            level,
            f"[TRACE:{self.trace_id}] Finished span: {self.operation_name} "
            f"({duration:.2f}ms) status={self.current_span.status}",
            extra={
                "trace_id": self.trace_id,
                "span_id": self.current_span.span_id,
                "duration_ms": duration,
                "status": self.current_span.status,
            }
        )

        # Restore previous context
        if self._token:
            _current_trace.reset(self._token)

    async def __aenter__(self) -> "TraceContext":
        """Async enter trace context."""
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async exit trace context."""
        return self.__exit__(exc_type, exc_val, exc_tb)

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        """Add an event to the current span."""
        self.current_span.add_event(name, attributes)

    def set_attribute(self, key: str, value: Any) -> None:
        """Set an attribute on the current span."""
        self.current_span.set_attribute(key, value)

    def child_span(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> "TraceContext":
        """Create a child span context."""
        return TraceContext(
            operation_name=name,
            trace_id=self.trace_id,
            parent_span_id=self.current_span.span_id,
            attributes=attributes,
        )


def get_current_trace() -> Optional[TraceContext]:
    """Get the current trace context if any."""
    return _current_trace.get()


def get_trace_id() -> Optional[str]:
    """Get the current trace ID if in a trace context."""
    ctx = _current_trace.get()
    return ctx.trace_id if ctx else None


def get_span_id() -> Optional[str]:
    """Get the current span ID if in a trace context."""
    ctx = _current_trace.get()
    return ctx.current_span.span_id if ctx else None


def traced(name: Optional[str] = None, attributes: Optional[Dict[str, Any]] = None):
    """
    Decorator to automatically trace a function.

    Args:
        name: Operation name (defaults to function name)
        attributes: Static attributes to add to span
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        operation_name = name or func.__name__

        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs) -> T:
                with TraceContext(operation_name, attributes=attributes) as ctx:
                    return await func(*args, **kwargs)
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs) -> T:
                with TraceContext(operation_name, attributes=attributes) as ctx:
                    return func(*args, **kwargs)
            return sync_wrapper

    return decorator


class TracedLogger(logging.LoggerAdapter):
    """
    Logger adapter that automatically includes trace context.

    Usage:
        logger = TracedLogger(logging.getLogger(__name__))
        logger.info("Processing order")  # Automatically includes trace_id
    """

    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        """Add trace context to log record."""
        extra = kwargs.get("extra", {})

        trace_id = get_trace_id()
        span_id = get_span_id()

        if trace_id:
            extra["trace_id"] = trace_id
        if span_id:
            extra["span_id"] = span_id

        kwargs["extra"] = extra
        return msg, kwargs


def get_traced_logger(name: str) -> TracedLogger:
    """Get a logger that automatically includes trace context."""
    return TracedLogger(logging.getLogger(name), {})


# Correlation helpers for cross-component tracing

def create_correlation_context(
    source: str,
    operation: str,
    user_id: Optional[int] = None,
    token_mint: Optional[str] = None,
) -> TraceContext:
    """
    Create a correlation context for cross-component operations.

    This is useful when an operation spans multiple components:
    - Telegram command -> Trade execution -> X post

    Args:
        source: Source component (e.g., "telegram", "api", "scheduler")
        operation: High-level operation (e.g., "buy_token", "close_position")
        user_id: User who initiated the operation
        token_mint: Token being operated on
    """
    attributes = {
        "source": source,
        "operation": operation,
    }
    if user_id:
        attributes["user_id"] = user_id
    if token_mint:
        attributes["token_mint"] = token_mint

    return TraceContext(f"{source}.{operation}", attributes=attributes)


# Export
__all__ = [
    "TraceContext",
    "Span",
    "get_current_trace",
    "get_trace_id",
    "get_span_id",
    "traced",
    "TracedLogger",
    "get_traced_logger",
    "create_correlation_context",
    "generate_trace_id",
]
