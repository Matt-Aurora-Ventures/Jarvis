"""
RecoveryManager - Error-type based recovery handling.

Provides a mechanism to register handlers for specific error types
and attempt recovery with configurable max attempts.

This complements the RecoveryEngine by providing a more flexible
handler-based approach to error recovery.

Usage:
    from core.recovery.manager import RecoveryManager

    manager = RecoveryManager(max_recovery_attempts=3)

    # Register handlers for specific error types
    manager.register_recovery(ConnectionError, lambda e: reconnect())
    manager.register_recovery(TimeoutError, lambda e: retry_with_backoff())

    # Attempt recovery
    try:
        do_something()
    except Exception as e:
        if manager.attempt_recovery(e):
            # Recovery succeeded
            pass
        else:
            # Recovery failed
            raise
"""

import logging
import threading
from datetime import datetime
from typing import Any, Callable, Dict, Optional, Type

logger = logging.getLogger(__name__)


class RecoveryManager:
    """
    Manages error-type-based recovery with registered handlers.

    Attributes:
        max_recovery_attempts: Maximum recovery attempts before giving up
    """

    def __init__(self, max_recovery_attempts: int = 3):
        """
        Initialize the recovery manager.

        Args:
            max_recovery_attempts: Maximum number of recovery attempts (default: 3)
        """
        self.max_recovery_attempts = max_recovery_attempts
        self._handlers: Dict[Type[Exception], Callable[[Exception], bool]] = {}
        self._attempt_counts: Dict[str, int] = {}  # Error type -> attempt count
        self._stats = {
            "total_attempts": 0,
            "successful_recoveries": 0,
            "failed_recoveries": 0,
        }
        self._lock = threading.Lock()

    def register_recovery(
        self,
        error_type: Type[Exception],
        handler: Callable[[Exception], bool],
    ) -> None:
        """
        Register a recovery handler for an error type.

        Args:
            error_type: The exception type to handle
            handler: A callable that takes the error and returns True if recovery succeeded
        """
        with self._lock:
            self._handlers[error_type] = handler
            logger.debug(f"Registered recovery handler for {error_type.__name__}")

    def attempt_recovery(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Attempt to recover from an error using registered handlers.

        Args:
            error: The exception to recover from
            context: Optional context dictionary for the handler

        Returns:
            True if recovery succeeded, False otherwise
        """
        error_type_name = type(error).__name__

        with self._lock:
            # Check attempt limits
            current_attempts = self._attempt_counts.get(error_type_name, 0)
            if current_attempts >= self.max_recovery_attempts:
                logger.warning(
                    f"Max recovery attempts ({self.max_recovery_attempts}) "
                    f"reached for {error_type_name}"
                )
                return False

            # Find matching handler
            handler = self._find_handler(error)

            if handler is None:
                logger.debug(f"No recovery handler registered for {error_type_name}")
                return False

            # Update attempt count
            self._attempt_counts[error_type_name] = current_attempts + 1
            self._stats["total_attempts"] += 1

        # Execute handler outside lock
        try:
            result = handler(error)

            with self._lock:
                if result:
                    self._stats["successful_recoveries"] += 1
                    logger.info(f"Recovery succeeded for {error_type_name}")
                else:
                    self._stats["failed_recoveries"] += 1
                    logger.warning(f"Recovery failed for {error_type_name}")

            return bool(result)

        except Exception as handler_error:
            logger.error(
                f"Recovery handler raised exception: {handler_error}",
                exc_info=True
            )
            with self._lock:
                self._stats["failed_recoveries"] += 1
            return False

    def _find_handler(
        self,
        error: Exception,
    ) -> Optional[Callable[[Exception], bool]]:
        """
        Find a handler for the given error type.

        Checks for exact match first, then checks for base class matches.

        Args:
            error: The exception to find a handler for

        Returns:
            The handler callable, or None if not found
        """
        error_type = type(error)

        # Check for exact match first
        if error_type in self._handlers:
            return self._handlers[error_type]

        # Check for base class matches
        for registered_type, handler in self._handlers.items():
            if isinstance(error, registered_type):
                return handler

        return None

    def get_recovery_stats(self) -> Dict[str, Any]:
        """
        Get recovery statistics.

        Returns:
            Dictionary with recovery stats including:
            - total_attempts
            - successful_recoveries
            - failed_recoveries
            - handlers_registered
        """
        with self._lock:
            return {
                "total_attempts": self._stats["total_attempts"],
                "successful_recoveries": self._stats["successful_recoveries"],
                "failed_recoveries": self._stats["failed_recoveries"],
                "handlers_registered": len(self._handlers),
                "attempt_counts": dict(self._attempt_counts),
            }

    def reset_attempts(self, error_type: Optional[Type[Exception]] = None) -> None:
        """
        Reset attempt counters.

        Args:
            error_type: Optional specific error type to reset. If None, resets all.
        """
        with self._lock:
            if error_type is not None:
                error_type_name = error_type.__name__
                if error_type_name in self._attempt_counts:
                    del self._attempt_counts[error_type_name]
            else:
                self._attempt_counts.clear()

        logger.debug("Recovery attempt counters reset")

    def unregister_recovery(self, error_type: Type[Exception]) -> bool:
        """
        Unregister a recovery handler.

        Args:
            error_type: The exception type to unregister

        Returns:
            True if handler was found and removed, False otherwise
        """
        with self._lock:
            if error_type in self._handlers:
                del self._handlers[error_type]
                logger.debug(f"Unregistered recovery handler for {error_type.__name__}")
                return True
            return False


# Singleton instance
_recovery_manager: Optional[RecoveryManager] = None


def get_recovery_manager() -> RecoveryManager:
    """Get or create the singleton recovery manager."""
    global _recovery_manager
    if _recovery_manager is None:
        _recovery_manager = RecoveryManager()
    return _recovery_manager
