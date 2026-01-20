"""
Structured Logging Configuration

Provides:
- Correlation IDs for request tracing
- JSON formatting for machine parsing
- Consistent log levels across codebase
- Contextual data (user_id, trade_id, session_id, etc.)
- Log rotation support
- Performance optimized logging with lazy evaluation
"""

import contextvars
import json
import logging
import logging.handlers
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union
from uuid import uuid4


# Context variables for correlation tracking
correlation_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "correlation_id", default=None
)
user_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "user_id", default=None
)
trade_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "trade_id", default=None
)
session_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "session_id", default=None
)


class CorrelationContext:
    """Context manager for setting correlation context."""

    def __init__(
        self,
        correlation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        trade_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        self.correlation_id = correlation_id or str(uuid4())
        self.user_id = user_id
        self.trade_id = trade_id
        self.session_id = session_id
        self._tokens = []

    def __enter__(self):
        # Store (var, token) pairs to reset correctly
        self._tokens.append((correlation_id_var, correlation_id_var.set(self.correlation_id)))
        if self.user_id:
            self._tokens.append((user_id_var, user_id_var.set(self.user_id)))
        if self.trade_id:
            self._tokens.append((trade_id_var, trade_id_var.set(self.trade_id)))
        if self.session_id:
            self._tokens.append((session_id_var, session_id_var.set(self.session_id)))
        return self

    def __exit__(self, *args):
        for var, token in reversed(self._tokens):
            var.reset(token)


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def __init__(
        self,
        include_traceback: bool = True,
        include_context: bool = True,
        extra_fields: Optional[Dict[str, Any]] = None,
    ):
        super().__init__()
        self.include_traceback = include_traceback
        self.include_context = include_context
        self.extra_fields = extra_fields or {}

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "thread": record.thread,
            "thread_name": record.threadName,
        }

        # Add correlation context if available
        if self.include_context:
            correlation_id = correlation_id_var.get()
            user_id = user_id_var.get()
            trade_id = trade_id_var.get()
            session_id = session_id_var.get()

            if correlation_id:
                log_data["correlation_id"] = correlation_id
            if user_id:
                log_data["user_id"] = user_id
            if trade_id:
                log_data["trade_id"] = trade_id
            if session_id:
                log_data["session_id"] = session_id

        # Add extra fields from configuration
        log_data.update(self.extra_fields)

        # Add exception info
        if record.exc_info and self.include_traceback:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info),
            }

        # Add custom fields from extra
        if hasattr(record, "extra_data"):
            log_data["extra"] = record.extra_data

        return json.dumps(log_data, default=str)


class StructuredFormatter(logging.Formatter):
    """Human-readable structured formatter for console output."""

    def __init__(self, use_color: bool = True):
        super().__init__()
        self.use_color = use_color
        self.colors = {
            "DEBUG": "\033[36m",  # Cyan
            "INFO": "\033[32m",  # Green
            "WARNING": "\033[33m",  # Yellow
            "ERROR": "\033[31m",  # Red
            "CRITICAL": "\033[35m",  # Magenta
            "RESET": "\033[0m",
        }

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with structure and color."""
        timestamp = datetime.utcfromtimestamp(record.created).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        # Color level name if enabled
        level = record.levelname
        if self.use_color and sys.stdout.isatty():
            color = self.colors.get(level, "")
            reset = self.colors["RESET"]
            level = f"{color}{level}{reset}"

        # Build base message
        parts = [
            f"[{timestamp}]",
            f"[{level}]",
            f"[{record.name}]",
            record.getMessage(),
        ]

        # Add correlation context
        correlation_id = correlation_id_var.get()
        user_id = user_id_var.get()
        trade_id = trade_id_var.get()

        context_parts = []
        if correlation_id:
            context_parts.append(f"correlation_id={correlation_id[:8]}")
        if user_id:
            context_parts.append(f"user_id={user_id}")
        if trade_id:
            context_parts.append(f"trade_id={trade_id}")

        if context_parts:
            parts.append(f"[{', '.join(context_parts)}]")

        # Add exception if present
        if record.exc_info:
            exc_text = "\n".join(traceback.format_exception(*record.exc_info))
            parts.append(f"\n{exc_text}")

        return " ".join(parts)


class StructuredLogger:
    """Enhanced logger with structured logging capabilities."""

    def __init__(self, logger: logging.Logger):
        self._logger = logger

    def _log_with_extra(
        self, level: int, msg: str, extra_data: Optional[Dict[str, Any]] = None, **kwargs
    ):
        """Log with structured extra data."""
        if extra_data:
            # Create a new LogRecord with extra_data attached
            kwargs.setdefault("extra", {})["extra_data"] = extra_data
        self._logger.log(level, msg, **kwargs)

    def debug(self, msg: str, **extra_data):
        """Log debug message with structured data."""
        self._log_with_extra(logging.DEBUG, msg, extra_data or None)

    def info(self, msg: str, **extra_data):
        """Log info message with structured data."""
        self._log_with_extra(logging.INFO, msg, extra_data or None)

    def warning(self, msg: str, **extra_data):
        """Log warning message with structured data."""
        self._log_with_extra(logging.WARNING, msg, extra_data or None)

    def error(self, msg: str, exc_info: bool = False, **extra_data):
        """Log error message with structured data."""
        self._log_with_extra(logging.ERROR, msg, extra_data or None, exc_info=exc_info)

    def critical(self, msg: str, exc_info: bool = False, **extra_data):
        """Log critical message with structured data."""
        self._log_with_extra(logging.CRITICAL, msg, extra_data or None, exc_info=exc_info)

    def exception(self, msg: str, **extra_data):
        """Log exception with traceback and structured data."""
        self._log_with_extra(logging.ERROR, msg, extra_data or None, exc_info=True)


def setup_logging(
    log_dir: Union[str, Path] = "logs",
    log_file: str = "jarvis.log",
    level: Union[str, int] = logging.INFO,
    json_format: bool = True,
    console_output: bool = True,
    max_bytes: int = 100 * 1024 * 1024,  # 100MB
    backup_count: int = 10,
    extra_fields: Optional[Dict[str, Any]] = None,
) -> logging.Logger:
    """
    Configure structured logging for the application.

    Args:
        log_dir: Directory for log files
        log_file: Name of the log file
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: Use JSON formatting for file logs
        console_output: Enable console output
        max_bytes: Max size of log file before rotation
        backup_count: Number of backup files to keep
        extra_fields: Additional fields to include in all logs

    Returns:
        Configured root logger
    """
    # Convert level string to int if needed
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    # Create log directory
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        log_path / log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(level)

    # Use JSON formatter for files
    if json_format:
        file_formatter = JSONFormatter(
            include_traceback=True,
            include_context=True,
            extra_fields=extra_fields,
        )
    else:
        file_formatter = StructuredFormatter(use_color=False)

    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # Console handler (human-readable)
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_formatter = StructuredFormatter(use_color=True)
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

    return root_logger


def get_logger(name: str) -> StructuredLogger:
    """
    Get a structured logger for a module.

    Args:
        name: Logger name (usually __name__)

    Returns:
        StructuredLogger instance
    """
    return StructuredLogger(logging.getLogger(name))


def set_correlation_id(correlation_id: Optional[str] = None) -> str:
    """
    Set correlation ID for current context.

    Args:
        correlation_id: Optional correlation ID (generates one if not provided)

    Returns:
        The correlation ID that was set
    """
    cid = correlation_id or str(uuid4())
    correlation_id_var.set(cid)
    return cid


def get_correlation_id() -> Optional[str]:
    """Get current correlation ID."""
    return correlation_id_var.get()


def set_user_context(
    user_id: Optional[str] = None,
    trade_id: Optional[str] = None,
    session_id: Optional[str] = None,
):
    """Set user context for logging."""
    if user_id:
        user_id_var.set(user_id)
    if trade_id:
        trade_id_var.set(trade_id)
    if session_id:
        session_id_var.set(session_id)


# Example usage and testing
if __name__ == "__main__":
    # Setup logging
    setup_logging(
        log_dir="test_logs",
        log_file="test.log",
        level="DEBUG",
        json_format=True,
        console_output=True,
        extra_fields={"service": "jarvis", "environment": "development"},
    )

    # Get logger
    logger = get_logger(__name__)

    # Basic logging
    logger.info("Application started")

    # With correlation context
    with CorrelationContext(user_id="user_123", trade_id="trade_456"):
        logger.info("Processing trade", amount=100.50, symbol="SOL")
        logger.warning("Low liquidity detected", pool_size=5000)

        try:
            raise ValueError("Example error")
        except Exception:
            logger.exception("Trade failed", trade_type="buy")

    # Without context
    logger.debug("Debug message", extra_field="value")
    logger.error("Error message", error_code=500)

    print("\nCheck test_logs/test.log for JSON formatted output")
