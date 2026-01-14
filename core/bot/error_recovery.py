"""
JARVIS Bot Error Recovery

Provides error handling, retry logic, and recovery strategies
for Telegram and Twitter bots.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Callable, Awaitable, List, Type
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
import asyncio
import logging
import traceback

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Severity levels for bot errors."""
    LOW = "low"           # Minor issue, retry immediately
    MEDIUM = "medium"     # Temporary issue, retry with backoff
    HIGH = "high"         # Significant issue, notify and retry
    CRITICAL = "critical" # System failure, alert and possibly shutdown


class RecoveryAction(Enum):
    """Possible recovery actions."""
    RETRY = "retry"
    SKIP = "skip"
    NOTIFY_USER = "notify_user"
    NOTIFY_ADMIN = "notify_admin"
    RESTART_SERVICE = "restart_service"
    ESCALATE = "escalate"


@dataclass
class ErrorContext:
    """Context information for an error."""
    error: Exception
    severity: ErrorSeverity
    bot_type: str  # "telegram" or "twitter"
    user_id: Optional[str] = None
    chat_id: Optional[str] = None
    message_text: Optional[str] = None
    command: Optional[str] = None
    attempt: int = 1
    max_attempts: int = 3
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RecoveryResult:
    """Result of a recovery attempt."""
    success: bool
    action: RecoveryAction
    message: str = ""
    should_retry: bool = False
    delay_seconds: float = 0.0


# Error classification
ERROR_CLASSIFICATIONS: Dict[Type[Exception], ErrorSeverity] = {
    TimeoutError: ErrorSeverity.LOW,
    ConnectionError: ErrorSeverity.MEDIUM,
    asyncio.TimeoutError: ErrorSeverity.LOW,
    ValueError: ErrorSeverity.LOW,
    KeyError: ErrorSeverity.LOW,
    PermissionError: ErrorSeverity.HIGH,
    RuntimeError: ErrorSeverity.MEDIUM,
}


def classify_error(error: Exception) -> ErrorSeverity:
    """Classify an error by severity."""
    for error_type, severity in ERROR_CLASSIFICATIONS.items():
        if isinstance(error, error_type):
            return severity

    # Check error message for hints
    error_str = str(error).lower()
    if "rate limit" in error_str or "too many" in error_str:
        return ErrorSeverity.MEDIUM
    if "unauthorized" in error_str or "forbidden" in error_str:
        return ErrorSeverity.HIGH
    if "network" in error_str or "connection" in error_str:
        return ErrorSeverity.MEDIUM

    return ErrorSeverity.MEDIUM


class BotErrorHandler:
    """
    Handles errors and coordinates recovery for bot operations.

    Usage:
        handler = BotErrorHandler()
        result = await handler.handle_error(error_context)
    """

    def __init__(self):
        self._error_counts: Dict[str, int] = {}
        self._last_errors: Dict[str, datetime] = {}
        self._recovery_handlers: Dict[ErrorSeverity, Callable] = {}
        self._error_listeners: List[Callable] = []

    def register_recovery_handler(
        self,
        severity: ErrorSeverity,
        handler: Callable[[ErrorContext], Awaitable[RecoveryResult]]
    ) -> None:
        """Register a custom recovery handler for a severity level."""
        self._recovery_handlers[severity] = handler

    def add_error_listener(
        self,
        listener: Callable[[ErrorContext], Awaitable[None]]
    ) -> None:
        """Add a listener that gets notified of all errors."""
        self._error_listeners.append(listener)

    async def handle_error(self, context: ErrorContext) -> RecoveryResult:
        """Handle an error and determine recovery action."""
        # Track error
        error_key = f"{context.bot_type}:{type(context.error).__name__}"
        self._error_counts[error_key] = self._error_counts.get(error_key, 0) + 1
        self._last_errors[error_key] = context.timestamp

        # Log the error
        self._log_error(context)

        # Notify listeners
        for listener in self._error_listeners:
            try:
                await listener(context)
            except Exception as e:
                logger.error(f"Error in error listener: {e}")

        # Use custom handler if available
        if context.severity in self._recovery_handlers:
            return await self._recovery_handlers[context.severity](context)

        # Default recovery logic
        return await self._default_recovery(context)

    async def _default_recovery(self, context: ErrorContext) -> RecoveryResult:
        """Default recovery strategy based on severity."""
        if context.severity == ErrorSeverity.LOW:
            # Immediate retry for low severity
            if context.attempt < context.max_attempts:
                return RecoveryResult(
                    success=True,
                    action=RecoveryAction.RETRY,
                    message="Retrying immediately",
                    should_retry=True,
                    delay_seconds=0.5,
                )
            return RecoveryResult(
                success=False,
                action=RecoveryAction.SKIP,
                message="Max retries reached, skipping",
            )

        elif context.severity == ErrorSeverity.MEDIUM:
            # Exponential backoff for medium severity
            if context.attempt < context.max_attempts:
                delay = 2 ** context.attempt
                return RecoveryResult(
                    success=True,
                    action=RecoveryAction.RETRY,
                    message=f"Retrying after {delay}s backoff",
                    should_retry=True,
                    delay_seconds=delay,
                )
            return RecoveryResult(
                success=False,
                action=RecoveryAction.NOTIFY_USER,
                message="Operation failed, user notified",
            )

        elif context.severity == ErrorSeverity.HIGH:
            # Notify and maybe retry for high severity
            if context.attempt < 2:  # Only one retry for high severity
                return RecoveryResult(
                    success=True,
                    action=RecoveryAction.RETRY,
                    message="Retrying with caution",
                    should_retry=True,
                    delay_seconds=5.0,
                )
            return RecoveryResult(
                success=False,
                action=RecoveryAction.NOTIFY_ADMIN,
                message="High severity error, admin notified",
            )

        else:  # CRITICAL
            return RecoveryResult(
                success=False,
                action=RecoveryAction.ESCALATE,
                message="Critical error, escalating",
            )

    def _log_error(self, context: ErrorContext) -> None:
        """Log error with appropriate level."""
        error_info = {
            "bot_type": context.bot_type,
            "error_type": type(context.error).__name__,
            "severity": context.severity.value,
            "attempt": context.attempt,
            "user_id": context.user_id,
        }

        if context.severity == ErrorSeverity.CRITICAL:
            logger.critical(f"Critical bot error: {context.error}", extra=error_info)
        elif context.severity == ErrorSeverity.HIGH:
            logger.error(f"High severity bot error: {context.error}", extra=error_info)
        elif context.severity == ErrorSeverity.MEDIUM:
            logger.warning(f"Medium severity bot error: {context.error}", extra=error_info)
        else:
            logger.info(f"Low severity bot error: {context.error}", extra=error_info)

    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics."""
        return {
            "error_counts": dict(self._error_counts),
            "last_errors": {
                k: v.isoformat() for k, v in self._last_errors.items()
            },
            "total_errors": sum(self._error_counts.values()),
        }


def with_error_recovery(
    bot_type: str,
    max_attempts: int = 3,
    notify_on_failure: bool = True
):
    """
    Decorator for bot command handlers with automatic error recovery.

    Usage:
        @with_error_recovery("telegram", max_attempts=3)
        async def handle_command(update, context):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            handler = get_error_handler()
            attempt = 0

            while attempt < max_attempts:
                attempt += 1
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    context = ErrorContext(
                        error=e,
                        severity=classify_error(e),
                        bot_type=bot_type,
                        attempt=attempt,
                        max_attempts=max_attempts,
                    )

                    result = await handler.handle_error(context)

                    if result.should_retry:
                        if result.delay_seconds > 0:
                            await asyncio.sleep(result.delay_seconds)
                        continue

                    # No more retries
                    if notify_on_failure:
                        # Could send error message to user here
                        pass

                    raise

            raise RuntimeError(f"Max attempts ({max_attempts}) exceeded")

        return wrapper
    return decorator


class CircuitBreaker:
    """
    Circuit breaker for bot operations.

    Prevents repeated failures from overwhelming the system.

    Usage:
        breaker = CircuitBreaker(failure_threshold=5)

        if breaker.is_open:
            return "Service temporarily unavailable"

        try:
            result = await operation()
            breaker.record_success()
        except Exception as e:
            breaker.record_failure()
            raise
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_requests: int = 1
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_requests = half_open_requests

        self._failures = 0
        self._successes = 0
        self._state = "closed"  # closed, open, half-open
        self._last_failure: Optional[datetime] = None
        self._half_open_count = 0

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (blocking requests)."""
        if self._state == "open":
            # Check if we should transition to half-open
            if self._last_failure:
                elapsed = (datetime.utcnow() - self._last_failure).total_seconds()
                if elapsed >= self.recovery_timeout:
                    self._state = "half-open"
                    self._half_open_count = 0
                    return False
            return True
        return False

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (allowing requests)."""
        return self._state == "closed"

    def record_success(self) -> None:
        """Record a successful operation."""
        self._successes += 1

        if self._state == "half-open":
            self._half_open_count += 1
            if self._half_open_count >= self.half_open_requests:
                # Recovered, close the circuit
                self._state = "closed"
                self._failures = 0
                logger.info("Circuit breaker closed after successful recovery")

    def record_failure(self) -> None:
        """Record a failed operation."""
        self._failures += 1
        self._last_failure = datetime.utcnow()

        if self._state == "half-open":
            # Failure during recovery, reopen
            self._state = "open"
            logger.warning("Circuit breaker reopened due to failure in half-open state")
        elif self._failures >= self.failure_threshold:
            # Too many failures, open the circuit
            self._state = "open"
            logger.warning(f"Circuit breaker opened after {self._failures} failures")

    def reset(self) -> None:
        """Reset the circuit breaker."""
        self._failures = 0
        self._successes = 0
        self._state = "closed"
        self._last_failure = None
        self._half_open_count = 0

    def get_state(self) -> Dict[str, Any]:
        """Get circuit breaker state."""
        return {
            "state": self._state,
            "failures": self._failures,
            "successes": self._successes,
            "last_failure": self._last_failure.isoformat() if self._last_failure else None,
        }


class UserErrorNotifier:
    """Formats and sends error messages to users."""

    ERROR_MESSAGES = {
        ErrorSeverity.LOW: "Oops! Something went wrong. Please try again.",
        ErrorSeverity.MEDIUM: "We're experiencing some issues. Please try again in a moment.",
        ErrorSeverity.HIGH: "We're having technical difficulties. Our team has been notified.",
        ErrorSeverity.CRITICAL: "Service is temporarily unavailable. Please try again later.",
    }

    @classmethod
    def get_user_message(
        cls,
        severity: ErrorSeverity,
        include_retry_hint: bool = True
    ) -> str:
        """Get a user-friendly error message."""
        message = cls.ERROR_MESSAGES.get(severity, cls.ERROR_MESSAGES[ErrorSeverity.MEDIUM])

        if include_retry_hint and severity in (ErrorSeverity.LOW, ErrorSeverity.MEDIUM):
            message += " If the problem persists, try again in a few minutes."

        return message


# Global instances
_error_handler: Optional[BotErrorHandler] = None
_circuit_breakers: Dict[str, CircuitBreaker] = {}


def get_error_handler() -> BotErrorHandler:
    """Get the global error handler."""
    global _error_handler
    if _error_handler is None:
        _error_handler = BotErrorHandler()
    return _error_handler


def get_circuit_breaker(name: str) -> CircuitBreaker:
    """Get or create a circuit breaker by name."""
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker()
    return _circuit_breakers[name]
