"""
JARVIS Structured JSON Logging

Provides:
- JSON formatted log output
- Request context tracking
- Performance metrics
- Pretty console output option
- Log aggregation support

Usage:
    from core.logging.structured import get_logger, setup_structured_logging

    logger = get_logger(__name__)
    logger.info("User action", user_id=123, action="login")
"""

import json
import logging
import sys
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

try:
    from api.middleware.request_tracing import get_request_id
except ImportError:
    def get_request_id():
        return ""


# Thread-local context
_context = threading.local()


def get_log_context() -> Dict[str, Any]:
    """Get current thread's log context."""
    if not hasattr(_context, "data"):
        _context.data = {}
    return _context.data


def set_log_context(**kwargs) -> None:
    """Set log context values."""
    ctx = get_log_context()
    ctx.update(kwargs)


def clear_log_context() -> None:
    """Clear log context."""
    _context.data = {}


@contextmanager
def log_context(**kwargs):
    """Context manager for scoped logging context."""
    old = get_log_context().copy()
    set_log_context(**kwargs)
    try:
        yield
    finally:
        _context.data = old


class StructuredFormatter(logging.Formatter):
    """JSON structured log formatter."""

    def __init__(self, include_location: bool = True, extra_fields: Dict[str, Any] = None):
        super().__init__()
        self.include_location = include_location
        self.extra_fields = extra_fields or {}

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Location info
        if self.include_location:
            log_data["location"] = {
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
            }

        # Request ID from tracing
        request_id = get_request_id()
        if request_id:
            log_data["request_id"] = request_id

        # Thread context
        ctx = get_log_context()
        if ctx:
            log_data.update(ctx)

        # Extra fields from record
        if hasattr(record, 'extra_fields'):
            log_data.update(record.extra_fields)

        # Custom extra from init
        log_data.update(self.extra_fields)

        # Exception info
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info),
            }

        return json.dumps(log_data, default=str)


class PrettyFormatter(logging.Formatter):
    """Pretty colored console formatter."""

    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def __init__(self, use_colors: bool = True):
        super().__init__()
        self.use_colors = use_colors and sys.stdout.isatty()

    def format(self, record: logging.LogRecord) -> str:
        time_str = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime("%H:%M:%S.%f")[:-3]

        level = record.levelname
        if self.use_colors:
            color = self.COLORS.get(level, "")
            level_str = f"{color}{level:8}{self.RESET}"
        else:
            level_str = f"{level:8}"

        # Shorten logger name
        name = record.name
        if len(name) > 25:
            parts = name.split(".")
            name = ".".join(p[0] for p in parts[:-1]) + "." + parts[-1]

        message = record.getMessage()

        # Add context
        ctx = get_log_context()
        ctx_str = ""
        if ctx.get("request_id"):
            ctx_str = f" [{ctx['request_id'][:8]}]"

        line = f"{time_str} {level_str} {name:25}{ctx_str} {message}"

        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)

        return line


class ContextLogger(logging.LoggerAdapter):
    """Logger with persistent context."""
    
    def process(self, msg, kwargs):
        extra = kwargs.get('extra', {})
        extra.update(self.extra)
        kwargs['extra'] = extra
        return msg, kwargs


def setup_structured_logging(level: int = logging.INFO, log_file: str = None):
    """Configure structured logging."""
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = []
    
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(StructuredFormatter())
    root.addHandler(console)
    
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(StructuredFormatter())
        root.addHandler(file_handler)
    
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str, **context) -> ContextLogger:
    """Get a logger with context."""
    return ContextLogger(logging.getLogger(name), context)
