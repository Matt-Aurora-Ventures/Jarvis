"""
Centralized Error Handling Module for ClawdBots.

Provides uniform error handling, logging, Telegram alerts, retry logic,
and graceful degradation strategies for all ClawdBot instances.

Features:
- Uniform error logging across all bots
- Telegram alerts for critical errors
- Retry logic with exponential backoff for transient failures
- Error pattern tracking for debugging
- Graceful degradation with fallback values
- Rolling error log (max 1000 entries)

Usage:
    from bots.shared.error_handler import (
        handle_error,
        with_retry,
        send_error_alert,
        get_error_stats,
        is_transient_error,
        ErrorContext,
        ErrorSeverity,
    )

    # Handle an error with context
    try:
        await risky_operation()
    except Exception as e:
        result = handle_error(e, ErrorContext(bot_name="clawdjarvis", operation="send_message"))

    # Use retry decorator
    @with_retry(max_retries=3, backoff=True)
    async def api_call():
        return await external_api.fetch()

    # Check error statistics
    stats = get_error_stats()
"""

import asyncio
import functools
import inspect
import json
import logging
import os
import random
import time
import traceback
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union

logger = logging.getLogger(__name__)

# Type variable for generic functions
T = TypeVar('T')


# ==============================================================================
# Error Severity
# ==============================================================================


class ErrorSeverity(Enum):
    """Error severity levels with numeric ordering and alert thresholds."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

    @property
    def level(self) -> int:
        """Get numeric level for comparison."""
        levels = {
            "DEBUG": 10,
            "INFO": 20,
            "WARNING": 30,
            "ERROR": 40,
            "CRITICAL": 50,
        }
        return levels[self.value]

    def should_alert(self) -> bool:
        """Determine if this severity should trigger a Telegram alert."""
        return self.level >= ErrorSeverity.ERROR.level

    def __lt__(self, other: "ErrorSeverity") -> bool:
        return self.level < other.level

    def __le__(self, other: "ErrorSeverity") -> bool:
        return self.level <= other.level

    def __gt__(self, other: "ErrorSeverity") -> bool:
        return self.level > other.level

    def __ge__(self, other: "ErrorSeverity") -> bool:
        return self.level >= other.level


# ==============================================================================
# Error Context
# ==============================================================================


@dataclass
class ErrorContext:
    """Context information for an error.

    Attributes:
        bot_name: Name of the bot where error occurred
        operation: Operation being performed when error occurred
        user_id: Telegram user ID (if applicable)
        chat_id: Telegram chat ID (if applicable)
        message_id: Telegram message ID (if applicable)
        extra: Additional context data
    """

    bot_name: str
    operation: str
    user_id: Optional[int] = None
    chat_id: Optional[int] = None
    message_id: Optional[int] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary."""
        return {
            "bot_name": self.bot_name,
            "operation": self.operation,
            "user_id": self.user_id,
            "chat_id": self.chat_id,
            "message_id": self.message_id,
            "extra": self.extra,
        }


# ==============================================================================
# Error Statistics
# ==============================================================================


@dataclass
class ErrorRecord:
    """Record of a single error occurrence."""

    error_type: str
    error_message: str
    severity: ErrorSeverity
    bot_name: str
    operation: str
    timestamp: datetime
    traceback: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "error_type": self.error_type,
            "error_message": self.error_message,
            "severity": self.severity.value,
            "bot_name": self.bot_name,
            "operation": self.operation,
            "timestamp": self.timestamp.isoformat(),
            "traceback": self.traceback,
            "context": self.context,
        }


class ErrorStats:
    """Tracks error statistics and patterns."""

    def __init__(self):
        self.total_errors: int = 0
        self.by_severity: Dict[ErrorSeverity, int] = {}
        self.by_type: Dict[str, int] = {}
        self.by_bot: Dict[str, int] = {}
        self.by_operation: Dict[str, int] = {}
        self.recent_errors: List[ErrorRecord] = []
        self._max_recent = 100

    def record_error(
        self,
        error_type: str,
        severity: ErrorSeverity,
        bot_name: str,
        operation: str = "",
        error_message: str = "",
        traceback_str: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record an error occurrence.

        Args:
            error_type: Type of error (e.g., "ValueError")
            severity: Error severity level
            bot_name: Bot where error occurred
            operation: Operation being performed
            error_message: Error message
            traceback_str: Full traceback string
            context: Additional context
        """
        self.total_errors += 1

        # Update counters
        self.by_severity[severity] = self.by_severity.get(severity, 0) + 1
        self.by_type[error_type] = self.by_type.get(error_type, 0) + 1
        self.by_bot[bot_name] = self.by_bot.get(bot_name, 0) + 1
        if operation:
            self.by_operation[operation] = self.by_operation.get(operation, 0) + 1

        # Add to recent errors
        record = ErrorRecord(
            error_type=error_type,
            error_message=error_message,
            severity=severity,
            bot_name=bot_name,
            operation=operation,
            timestamp=datetime.now(),
            traceback=traceback_str,
            context=context or {},
        )
        self.recent_errors.append(record)

        # Trim recent errors list
        if len(self.recent_errors) > self._max_recent:
            self.recent_errors = self.recent_errors[-self._max_recent:]

    def get_summary(self) -> Dict[str, Any]:
        """Get error statistics summary."""
        return {
            "total_errors": self.total_errors,
            "by_severity": {k.value: v for k, v in self.by_severity.items()},
            "by_type": dict(self.by_type),
            "by_bot": dict(self.by_bot),
            "by_operation": dict(self.by_operation),
            "patterns": self._detect_patterns(),
        }

    def get_recent_errors(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent errors as dictionaries."""
        return [e.to_dict() for e in self.recent_errors[-limit:]]

    def _detect_patterns(self) -> Dict[str, Any]:
        """Detect error patterns (repeated errors, etc.)."""
        patterns = {}

        # Find most common error types
        if self.by_type:
            most_common = max(self.by_type, key=self.by_type.get)
            if self.by_type[most_common] >= 5:
                patterns["most_common_error"] = {
                    "type": most_common,
                    "count": self.by_type[most_common],
                }

        # Find problematic operations
        if self.by_operation:
            problematic = {k: v for k, v in self.by_operation.items() if v >= 3}
            if problematic:
                patterns["problematic_operations"] = problematic

        return patterns


# ==============================================================================
# Transient Error Detection
# ==============================================================================

# Error types that are typically transient (retryable)
TRANSIENT_ERROR_TYPES = (
    ConnectionError,
    ConnectionResetError,
    ConnectionRefusedError,
    ConnectionAbortedError,
    TimeoutError,
    asyncio.TimeoutError,
)

# Error types that are NOT transient (even if they inherit from transient types)
NON_TRANSIENT_ERROR_TYPES = (
    PermissionError,
    FileNotFoundError,
    FileExistsError,
    IsADirectoryError,
    NotADirectoryError,
)

# Message patterns indicating transient errors
TRANSIENT_PATTERNS = [
    "429",  # Rate limit
    "too many requests",
    "rate limit",
    "temporarily",
    "service unavailable",
    "503",
    "502",
    "504",
    "connection reset",
    "connection refused",
    "timed out",
    "timeout",
    "network",
]


def is_transient_error(error: Exception) -> bool:
    """Determine if an error is transient (can be retried).

    Args:
        error: Exception to check

    Returns:
        True if error is likely transient
    """
    # Check for explicitly non-transient types first
    if isinstance(error, NON_TRANSIENT_ERROR_TYPES):
        return False

    # Check by exception type
    if isinstance(error, TRANSIENT_ERROR_TYPES):
        return True

    # Check error message for patterns
    error_str = str(error).lower()
    for pattern in TRANSIENT_PATTERNS:
        if pattern in error_str:
            return True

    return False


# ==============================================================================
# Auto Severity Detection
# ==============================================================================


def auto_detect_severity(error: Exception) -> ErrorSeverity:
    """Auto-detect severity based on error type.

    Args:
        error: Exception to analyze

    Returns:
        Appropriate ErrorSeverity level
    """
    # Critical errors
    if isinstance(error, (MemoryError, SystemError, KeyboardInterrupt)):
        return ErrorSeverity.CRITICAL

    # High severity errors
    if isinstance(error, (PermissionError, ImportError, AttributeError)):
        return ErrorSeverity.ERROR

    # Medium severity (transient)
    if is_transient_error(error):
        return ErrorSeverity.WARNING

    # Default to ERROR
    return ErrorSeverity.ERROR


# ==============================================================================
# Main Error Handler
# ==============================================================================


class ErrorHandler:
    """Centralized error handler for ClawdBots.

    Handles error logging, statistics tracking, Telegram alerts,
    and graceful degradation strategies.
    """

    def __init__(
        self,
        error_log_path: Optional[Path] = None,
        max_log_entries: int = 1000,
        alert_cooldown_seconds: int = 300,
    ):
        """Initialize error handler.

        Args:
            error_log_path: Path to error log JSON file
            max_log_entries: Maximum entries in rolling log
            alert_cooldown_seconds: Minimum seconds between alerts for same error
        """
        # Default log path
        if error_log_path is None:
            default_path = Path("/root/clawdbots/errors.json")
            if default_path.parent.exists():
                error_log_path = default_path
            else:
                error_log_path = Path.home() / ".clawdbots" / "errors.json"

        self.error_log_path = error_log_path
        self.max_log_entries = max_log_entries
        self.alert_cooldown_seconds = alert_cooldown_seconds

        # Statistics
        self.stats = ErrorStats()

        # Log buffer
        self._log_buffer: List[Dict[str, Any]] = []
        self._load_existing_log()

        # Alert state
        self._last_alerts: Dict[str, datetime] = {}

        # Telegram configuration (loaded from environment)
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.alert_chat_id = os.getenv(
            "TELEGRAM_ADMIN_CHAT_ID",
            os.getenv("TELEGRAM_BUY_BOT_CHAT_ID", "")
        )

        # Ensure log directory exists
        if self.error_log_path:
            self.error_log_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_existing_log(self) -> None:
        """Load existing error log if present."""
        if self.error_log_path and self.error_log_path.exists():
            try:
                content = self.error_log_path.read_text()
                self._log_buffer = json.loads(content) if content else []
            except Exception as e:
                logger.warning(f"Could not load existing error log: {e}")
                self._log_buffer = []

    def _log_error(
        self,
        error: Exception,
        context: ErrorContext,
        severity: ErrorSeverity,
    ) -> None:
        """Log error to internal buffer and logger.

        Args:
            error: Exception that occurred
            context: Error context
            severity: Error severity
        """
        error_type = type(error).__name__
        error_message = str(error)

        # Get traceback for ERROR and above
        tb_str = None
        if severity.level >= ErrorSeverity.ERROR.level:
            tb_str = traceback.format_exc()

        # Log to Python logger
        log_message = (
            f"[{context.bot_name}] {error_type}: {error_message} "
            f"(operation={context.operation})"
        )

        if severity == ErrorSeverity.CRITICAL:
            logger.critical(log_message)
        elif severity == ErrorSeverity.ERROR:
            logger.error(log_message)
        elif severity == ErrorSeverity.WARNING:
            logger.warning(log_message)
        elif severity == ErrorSeverity.INFO:
            logger.info(log_message)
        else:
            logger.debug(log_message)

        # Add to buffer
        entry = {
            "timestamp": datetime.now().isoformat(),
            "bot_name": context.bot_name,
            "operation": context.operation,
            "error_type": error_type,
            "error_message": error_message[:500],  # Truncate long messages
            "severity": severity.value,
            "traceback": tb_str[:2000] if tb_str else None,  # Truncate traceback
            "context": context.to_dict(),
        }
        self._log_buffer.append(entry)

        # Trim buffer
        if len(self._log_buffer) > self.max_log_entries:
            self._log_buffer = self._log_buffer[-self.max_log_entries:]

        # Update statistics
        self.stats.record_error(
            error_type=error_type,
            severity=severity,
            bot_name=context.bot_name,
            operation=context.operation,
            error_message=error_message,
            traceback_str=tb_str,
            context=context.to_dict(),
        )

    def _flush_log(self) -> None:
        """Write log buffer to file."""
        if not self.error_log_path:
            return

        try:
            self.error_log_path.write_text(json.dumps(self._log_buffer, indent=2))
        except Exception as e:
            logger.warning(f"Could not flush error log: {e}")

    def _should_send_alert(self, error_key: str) -> bool:
        """Check if alert should be sent based on cooldown.

        Args:
            error_key: Unique key for this error type

        Returns:
            True if alert should be sent
        """
        now = datetime.now()
        last_alert = self._last_alerts.get(error_key)

        if last_alert:
            elapsed = (now - last_alert).total_seconds()
            if elapsed < self.alert_cooldown_seconds:
                return False

        return True

    def _send_telegram_alert(
        self,
        error: Exception,
        context: ErrorContext,
        severity: ErrorSeverity,
    ) -> bool:
        """Send alert via Telegram.

        Args:
            error: Exception that occurred
            context: Error context
            severity: Error severity

        Returns:
            True if sent successfully
        """
        if not self.telegram_token or not self.alert_chat_id:
            logger.debug("Telegram alert not configured")
            return False

        # Check cooldown
        error_key = f"{context.bot_name}:{type(error).__name__}:{context.operation}"
        if not self._should_send_alert(error_key):
            return False

        try:
            # Build message
            severity_emoji = {
                ErrorSeverity.CRITICAL: "",
                ErrorSeverity.ERROR: "",
                ErrorSeverity.WARNING: "",
                ErrorSeverity.INFO: "",
                ErrorSeverity.DEBUG: "",
            }.get(severity, "")

            message = (
                f"{severity_emoji} <b>{severity.value} - {context.bot_name}</b>\n\n"
                f"<b>Operation:</b> {context.operation}\n"
                f"<b>Error:</b> {type(error).__name__}\n"
                f"<b>Message:</b> <code>{str(error)[:200]}</code>\n"
                f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

            # Send via API
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            data = urllib.parse.urlencode({
                "chat_id": self.alert_chat_id,
                "text": message,
                "parse_mode": "HTML",
            }).encode()

            req = urllib.request.Request(url, data=data)
            urllib.request.urlopen(req, timeout=10)

            # Record alert time
            self._last_alerts[error_key] = datetime.now()
            return True

        except Exception as e:
            logger.warning(f"Failed to send Telegram alert: {e}")
            return False

    async def _send_telegram_alert_async(
        self,
        error: Exception,
        context: ErrorContext,
        severity: ErrorSeverity,
    ) -> bool:
        """Async version of send_telegram_alert."""
        # Run sync version in executor to not block
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._send_telegram_alert(error, context, severity)
        )

    def handle_error(
        self,
        error: Exception,
        context: Union[ErrorContext, str],
        bot_name: str = "unknown",
        severity: Optional[ErrorSeverity] = None,
        fallback_value: Any = None,
    ) -> Dict[str, Any]:
        """Handle an error uniformly.

        Args:
            error: Exception that occurred
            context: ErrorContext or string describing operation
            bot_name: Bot name (if context is string)
            severity: Override severity (auto-detected if None)
            fallback_value: Value to return on error (graceful degradation)

        Returns:
            Dict with handling result
        """
        # Normalize context
        if isinstance(context, str):
            context = ErrorContext(bot_name=bot_name, operation=context)

        # Auto-detect severity if not provided
        if severity is None:
            severity = auto_detect_severity(error)

        # Log the error
        self._log_error(error, context, severity)

        # Flush log periodically
        if len(self._log_buffer) % 10 == 0:
            self._flush_log()

        # Send alert if appropriate
        alert_sent = False
        if severity.should_alert():
            alert_sent = self._send_telegram_alert(error, context, severity)

        # Build result
        result = {
            "handled": True,
            "severity": severity.value,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "bot_name": context.bot_name,
            "operation": context.operation,
            "timestamp": datetime.now().isoformat(),
            "alert_sent": alert_sent,
            "fallback_applied": fallback_value is not None,
        }

        if fallback_value is not None:
            result["fallback_value"] = fallback_value

        return result

    async def handle_error_async(
        self,
        error: Exception,
        context: Union[ErrorContext, str],
        bot_name: str = "unknown",
        severity: Optional[ErrorSeverity] = None,
        fallback_value: Any = None,
    ) -> Dict[str, Any]:
        """Async version of handle_error.

        Args:
            error: Exception that occurred
            context: ErrorContext or string describing operation
            bot_name: Bot name (if context is string)
            severity: Override severity (auto-detected if None)
            fallback_value: Value to return on error (graceful degradation)

        Returns:
            Dict with handling result
        """
        # Normalize context
        if isinstance(context, str):
            context = ErrorContext(bot_name=bot_name, operation=context)

        # Auto-detect severity if not provided
        if severity is None:
            severity = auto_detect_severity(error)

        # Log the error
        self._log_error(error, context, severity)

        # Flush log periodically
        if len(self._log_buffer) % 10 == 0:
            self._flush_log()

        # Send alert if appropriate (async)
        alert_sent = False
        if severity.should_alert():
            alert_sent = await self._send_telegram_alert_async(error, context, severity)

        # Build result
        result = {
            "handled": True,
            "severity": severity.value,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "bot_name": context.bot_name,
            "operation": context.operation,
            "timestamp": datetime.now().isoformat(),
            "alert_sent": alert_sent,
            "fallback_applied": fallback_value is not None,
        }

        if fallback_value is not None:
            result["fallback_value"] = fallback_value

        return result

    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics.

        Returns:
            Dict with error statistics
        """
        return self.stats.get_summary()


# ==============================================================================
# Retry Decorator
# ==============================================================================


def with_retry(
    max_retries: int = 3,
    backoff: bool = True,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    only_transient: bool = False,
    on_retry: Optional[Callable[[Exception, int], None]] = None,
):
    """Decorator for retrying functions with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        backoff: Enable exponential backoff
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        only_transient: Only retry transient errors
        on_retry: Callback on each retry (error, attempt)

    Returns:
        Decorated function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        is_async = inspect.iscoroutinefunction(func)

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            last_error = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e

                    # Check if we should retry
                    if attempt >= max_retries:
                        raise

                    if only_transient and not is_transient_error(e):
                        raise

                    # Calculate delay
                    if backoff:
                        delay = min(
                            base_delay * (2 ** attempt),
                            max_delay
                        )
                        # Add jitter
                        delay = delay * (0.5 + random.random())
                    else:
                        delay = base_delay

                    # Log retry
                    logger.warning(
                        f"{func.__name__} attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )

                    # Call retry callback
                    if on_retry:
                        on_retry(e, attempt)

                    await asyncio.sleep(delay)

            raise last_error

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            last_error = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e

                    # Check if we should retry
                    if attempt >= max_retries:
                        raise

                    if only_transient and not is_transient_error(e):
                        raise

                    # Calculate delay
                    if backoff:
                        delay = min(
                            base_delay * (2 ** attempt),
                            max_delay
                        )
                        delay = delay * (0.5 + random.random())
                    else:
                        delay = base_delay

                    # Log retry
                    logger.warning(
                        f"{func.__name__} attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )

                    # Call retry callback
                    if on_retry:
                        on_retry(e, attempt)

                    time.sleep(delay)

            raise last_error

        return async_wrapper if is_async else sync_wrapper

    return decorator


# ==============================================================================
# Singleton Instance
# ==============================================================================

_error_handler: Optional[ErrorHandler] = None


def get_error_handler() -> ErrorHandler:
    """Get singleton error handler instance.

    Returns:
        ErrorHandler singleton
    """
    global _error_handler
    if _error_handler is None:
        _error_handler = ErrorHandler()
    return _error_handler


def reset_error_handler() -> None:
    """Reset error handler singleton (for testing)."""
    global _error_handler
    _error_handler = None


# ==============================================================================
# Convenience Functions
# ==============================================================================


def handle_error(
    error: Exception,
    context: Union[ErrorContext, str],
    bot_name: str = "unknown",
    severity: Optional[ErrorSeverity] = None,
    fallback_value: Any = None,
) -> Dict[str, Any]:
    """Handle an error using the singleton handler.

    Args:
        error: Exception that occurred
        context: ErrorContext or string describing operation
        bot_name: Bot name (if context is string)
        severity: Override severity (auto-detected if None)
        fallback_value: Value to return on error

    Returns:
        Dict with handling result
    """
    handler = get_error_handler()
    return handler.handle_error(error, context, bot_name, severity, fallback_value)


def send_error_alert(
    error: Exception,
    severity: ErrorSeverity,
    context: Optional[ErrorContext] = None,
) -> bool:
    """Send error alert via Telegram.

    Args:
        error: Exception to alert on
        severity: Error severity
        context: Optional error context

    Returns:
        True if alert sent
    """
    if not severity.should_alert():
        return False

    handler = get_error_handler()
    if context is None:
        context = ErrorContext(bot_name="unknown", operation="unknown")

    return handler._send_telegram_alert(error, context, severity)


def get_error_stats() -> Dict[str, Any]:
    """Get error statistics from singleton handler.

    Returns:
        Dict with error statistics
    """
    handler = get_error_handler()
    return handler.get_error_stats()


# ==============================================================================
# Module Exports
# ==============================================================================


__all__ = [
    # Enums
    "ErrorSeverity",
    # Data classes
    "ErrorContext",
    "ErrorStats",
    "ErrorRecord",
    # Main handler
    "ErrorHandler",
    # Decorator
    "with_retry",
    # Functions
    "handle_error",
    "send_error_alert",
    "get_error_stats",
    "is_transient_error",
    "auto_detect_severity",
    # Singleton
    "get_error_handler",
    "reset_error_handler",
]
