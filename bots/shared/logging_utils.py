"""
ClawdBot Logging Utilities.

Provides enhanced structured logging with:
- JSON format for log aggregation
- Colored console output
- Rotating file handlers (10MB max, keep 5)
- Request ID tracking for distributed tracing
- Bot-specific log files at /root/clawdbots/logs/{bot_name}.log

Usage:
    from bots.shared.logging_utils import setup_logger, log_api_call, log_user_message

    logger = setup_logger("my_bot")
    log_api_call(logger, api="telegram", method="sendMessage", latency=0.5, success=True)
"""

import os
import sys
import json
import logging
import threading
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, List, Optional


# Thread-local storage for request ID tracking
_request_context = threading.local()

# Default log directory (can be overridden via CLAWDBOT_LOG_DIR env var)
DEFAULT_LOG_DIR = "/root/clawdbots/logs"

# Message preview length for sanitization
MESSAGE_PREVIEW_LENGTH = 50

# Response preview length
RESPONSE_PREVIEW_LENGTH = 100

# ANSI color codes for console output
COLORS = {
    "DEBUG": "\033[36m",     # Cyan
    "INFO": "\033[32m",      # Green
    "WARNING": "\033[33m",   # Yellow
    "ERROR": "\033[31m",     # Red
    "CRITICAL": "\033[35m",  # Magenta
    "RESET": "\033[0m",      # Reset
}


def get_log_dir() -> Path:
    """Get the log directory path from environment or default."""
    log_dir = os.environ.get("CLAWDBOT_LOG_DIR", DEFAULT_LOG_DIR)
    path = Path(log_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def set_request_id(request_id: str) -> None:
    """
    Set the request ID for the current thread context.

    This allows tracking a request across multiple log entries for
    distributed tracing and debugging.

    Args:
        request_id: Unique identifier for the current request
    """
    _request_context.request_id = request_id


def get_request_id() -> Optional[str]:
    """Get the current request ID from thread context."""
    return getattr(_request_context, "request_id", None)


def clear_request_id() -> None:
    """Clear the request ID from the current thread context."""
    if hasattr(_request_context, "request_id"):
        delattr(_request_context, "request_id")


class JSONFormatter(logging.Formatter):
    """
    JSON formatter for structured log output.

    Produces JSON lines (one JSON object per line) suitable for
    log aggregation systems like ELK, Datadog, or CloudWatch.
    """

    def __init__(self, bot_name: str):
        super().__init__()
        self.bot_name = bot_name

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "bot_name": self.bot_name,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add request ID if available
        request_id = get_request_id()
        if request_id:
            log_entry["request_id"] = request_id

        # Add any extra fields from the record
        if hasattr(record, "extra_data"):
            log_entry.update(record.extra_data)

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


class ColoredFormatter(logging.Formatter):
    """
    Colored formatter for console output.

    Adds ANSI color codes based on log level for better visual
    distinction in terminal output.
    """

    FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    def __init__(self):
        super().__init__(self.FORMAT, datefmt="%Y-%m-%d %H:%M:%S")

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors."""
        # Get color for this level
        color = COLORS.get(record.levelname, COLORS["RESET"])
        reset = COLORS["RESET"]

        # Color the level name
        original_levelname = record.levelname
        record.levelname = f"{color}{record.levelname}{reset}"

        # Format the message
        result = super().format(record)

        # Restore original level name
        record.levelname = original_levelname

        return result


# Cache of configured loggers to avoid duplicate handlers
_configured_loggers: Dict[str, logging.Logger] = {}


def cleanup_logger(bot_name: str) -> None:
    """
    Clean up a logger by closing all handlers.

    This is important for test cleanup on Windows where file handles
    must be closed before files can be deleted.

    Args:
        bot_name: Name of the bot logger to clean up
    """
    if bot_name in _configured_loggers:
        logger = _configured_loggers[bot_name]

        # Close and remove all handlers
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)

        # Remove from cache
        del _configured_loggers[bot_name]

        # Also clean up the logging module's manager
        if bot_name in logging.Logger.manager.loggerDict:
            del logging.Logger.manager.loggerDict[bot_name]


def setup_logger(
    bot_name: str,
    log_level: int = logging.INFO,
) -> logging.Logger:
    """
    Set up a configured logger for a ClawdBot.

    Creates a logger with both console (colored) and file (JSON) output.
    File output uses rotating file handler (10MB max, keep 5 backups).

    Args:
        bot_name: Name of the bot (used for logger name and log file)
        log_level: Logging level (default: logging.INFO)

    Returns:
        Configured logging.Logger instance

    Example:
        logger = setup_logger("clawdjarvis")
        logger.info("Bot started")
    """
    # Return existing logger if already configured
    if bot_name in _configured_loggers:
        return _configured_loggers[bot_name]

    # Get or create the logger
    logger = logging.getLogger(bot_name)
    logger.setLevel(log_level)

    # Prevent propagation to root logger to avoid duplicate logs
    logger.propagate = False

    # Add console handler with colored output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(ColoredFormatter())
    logger.addHandler(console_handler)

    # Add file handler with JSON output and rotation
    log_dir = get_log_dir()
    log_file = log_dir / f"{bot_name}.log"

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(JSONFormatter(bot_name))
    logger.addHandler(file_handler)

    # Cache the logger
    _configured_loggers[bot_name] = logger

    return logger


def _create_log_record(
    logger: logging.Logger,
    level: int,
    message: str,
    extra_data: Dict[str, Any],
) -> None:
    """Create a log record with extra data attached."""
    # Create a LogRecord manually to attach extra data
    record = logger.makeRecord(
        logger.name,
        level,
        "(logging_utils)",
        0,
        message,
        (),
        None,
    )
    record.extra_data = extra_data
    logger.handle(record)


def log_api_call(
    logger: logging.Logger,
    api: str,
    method: str,
    latency: float,
    success: bool,
    error: Optional[str] = None,
) -> None:
    """
    Log an API call with structured data.

    Args:
        logger: Logger instance from setup_logger
        api: Name of the API (e.g., "telegram", "openai", "anthropic")
        method: API method called (e.g., "sendMessage", "chat.completions")
        latency: Time taken in seconds
        success: Whether the call succeeded
        error: Error message if failed (optional)

    Example:
        log_api_call(logger, api="telegram", method="sendMessage", latency=0.5, success=True)
    """
    extra_data = {
        "log_type": "api_call",
        "api": api,
        "method": method,
        "latency_seconds": latency,
        "success": success,
    }

    if error:
        extra_data["error"] = error

    level = logging.INFO if success else logging.WARNING
    message = f"API call: {api}.{method} ({'OK' if success else 'FAILED'}) in {latency:.3f}s"

    if error:
        message += f" - {error}"

    _create_log_record(logger, level, message, extra_data)


def log_user_message(
    logger: logging.Logger,
    user_id: int,
    message: str,
    platform: str = "telegram",
) -> None:
    """
    Log a user message with privacy protection.

    Messages are truncated to prevent logging sensitive user data.
    Only a preview is logged for debugging purposes.

    Args:
        logger: Logger instance from setup_logger
        user_id: User's ID
        message: The message content (will be truncated)
        platform: Platform the message came from (default: "telegram")

    Example:
        log_user_message(logger, user_id=12345, message="Hello bot!")
    """
    # Truncate message to preview length for privacy
    preview = message[:MESSAGE_PREVIEW_LENGTH]
    if len(message) > MESSAGE_PREVIEW_LENGTH:
        preview += "..."

    extra_data = {
        "log_type": "user_message",
        "user_id": user_id,
        "platform": platform,
        "message_length": len(message),
        "message_preview": preview,
    }

    _create_log_record(
        logger,
        logging.INFO,
        f"User message from {user_id}: {preview}",
        extra_data,
    )


def log_bot_response(
    logger: logging.Logger,
    response: str,
    tokens: int,
    response_time: Optional[float] = None,
) -> None:
    """
    Log a bot response with token count.

    Args:
        logger: Logger instance from setup_logger
        response: The bot's response (preview will be logged)
        tokens: Number of tokens in the response
        response_time: Time to generate response in seconds (optional)

    Example:
        log_bot_response(logger, response="Hello! How can I help?", tokens=10)
    """
    # Create response preview
    preview = response[:RESPONSE_PREVIEW_LENGTH]
    if len(response) > RESPONSE_PREVIEW_LENGTH:
        preview += "..."

    extra_data = {
        "log_type": "bot_response",
        "tokens": tokens,
        "response_length": len(response),
        "response_preview": preview,
    }

    if response_time is not None:
        extra_data["response_time_seconds"] = response_time

    _create_log_record(
        logger,
        logging.INFO,
        f"Bot response: {tokens} tokens, {len(response)} chars",
        extra_data,
    )


def get_recent_logs(
    bot_name: str,
    count: int = 100,
) -> List[Dict[str, Any]]:
    """
    Retrieve recent log entries for a bot.

    Reads the bot's log file and returns the most recent entries
    as parsed JSON dictionaries. Useful for debugging and monitoring.

    Args:
        bot_name: Name of the bot to get logs for
        count: Maximum number of entries to return (default: 100)

    Returns:
        List of log entries as dictionaries, most recent first

    Example:
        logs = get_recent_logs("clawdjarvis", count=10)
        for log in logs:
            print(f"{log['timestamp']}: {log['message']}")
    """
    log_dir = get_log_dir()
    log_file = log_dir / f"{bot_name}.log"

    if not log_file.exists():
        return []

    entries = []
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Parse JSON lines from the end (most recent)
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue

            try:
                entry = json.loads(line)
                entries.append(entry)
                if len(entries) >= count:
                    break
            except json.JSONDecodeError:
                # Skip non-JSON lines
                continue

    except (IOError, OSError) as e:
        # Log read error but don't fail
        pass

    return entries


def log_error(
    logger: logging.Logger,
    error: Exception,
    context: Optional[str] = None,
) -> None:
    """
    Log an error with full traceback.

    Args:
        logger: Logger instance from setup_logger
        error: The exception to log
        context: Additional context about what was happening (optional)

    Example:
        try:
            do_something()
        except Exception as e:
            log_error(logger, e, context="processing user request")
    """
    extra_data = {
        "log_type": "error",
        "error_type": type(error).__name__,
        "error_message": str(error),
    }

    if context:
        extra_data["context"] = context

    message = f"Error: {type(error).__name__}: {error}"
    if context:
        message = f"{context} - {message}"

    logger.exception(message, extra={"extra_data": extra_data})


def log_metrics(
    logger: logging.Logger,
    metrics: Dict[str, Any],
    metric_type: str = "performance",
) -> None:
    """
    Log metrics data for monitoring.

    Args:
        logger: Logger instance from setup_logger
        metrics: Dictionary of metric name -> value
        metric_type: Type of metrics (e.g., "performance", "usage", "health")

    Example:
        log_metrics(logger, {
            "response_time_p99": 0.5,
            "requests_per_minute": 100,
            "error_rate": 0.01,
        }, metric_type="performance")
    """
    extra_data = {
        "log_type": "metrics",
        "metric_type": metric_type,
        "metrics": metrics,
    }

    metrics_summary = ", ".join(f"{k}={v}" for k, v in metrics.items())
    _create_log_record(
        logger,
        logging.INFO,
        f"Metrics ({metric_type}): {metrics_summary}",
        extra_data,
    )


# Export public API
__all__ = [
    "setup_logger",
    "cleanup_logger",
    "log_api_call",
    "log_user_message",
    "log_bot_response",
    "get_recent_logs",
    "set_request_id",
    "get_request_id",
    "clear_request_id",
    "log_error",
    "log_metrics",
    "ColoredFormatter",
    "JSONFormatter",
]
