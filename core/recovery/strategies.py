"""
Recovery Strategies - Abstract and concrete recovery strategy implementations.

Provides a strategy pattern for recovery operations:
- RestartStrategy: Restart a component
- RetryStrategy: Retry the operation with backoff
- FallbackStrategy: Use an alternative operation
- IgnoreStrategy: Log and continue

Usage:
    from core.recovery.strategies import RetryStrategy, get_strategy

    # Use a specific strategy
    strategy = RetryStrategy(max_retries=3, base_delay=1.0)
    if strategy.can_handle(error):
        success = strategy.execute(error, component="x_bot", operation=my_func)

    # Get strategy by name
    strategy = get_strategy("retry")
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional, Tuple, Type

logger = logging.getLogger(__name__)


class RecoveryStrategy(ABC):
    """
    Abstract base class for recovery strategies.

    All concrete strategies must implement execute() and can_handle().
    """

    @abstractmethod
    def execute(
        self,
        error: Exception,
        component: str,
        **kwargs: Any,
    ) -> bool:
        """
        Execute the recovery strategy.

        Args:
            error: The exception that triggered recovery
            component: Name of the component being recovered
            **kwargs: Additional strategy-specific arguments

        Returns:
            True if recovery succeeded, False otherwise
        """
        pass

    @abstractmethod
    def can_handle(self, error: Exception) -> bool:
        """
        Check if this strategy can handle the given error.

        Args:
            error: The exception to check

        Returns:
            True if this strategy can handle the error
        """
        pass


class RestartStrategy(RecoveryStrategy):
    """
    Strategy that restarts a component.

    Useful for recovering from state corruption or resource exhaustion.
    """

    def __init__(
        self,
        max_restarts: int = 3,
        cooldown_seconds: float = 10,
    ):
        """
        Initialize restart strategy.

        Args:
            max_restarts: Maximum number of restarts before giving up
            cooldown_seconds: Seconds to wait between restarts
        """
        self.max_restarts = max_restarts
        self.cooldown_seconds = cooldown_seconds
        self._restart_counts: Dict[str, int] = {}

    def can_handle(self, error: Exception) -> bool:
        """RestartStrategy can handle any error."""
        return True

    def execute(
        self,
        error: Exception,
        component: str,
        restart_func: Optional[Callable[[], bool]] = None,
        **kwargs: Any,
    ) -> bool:
        """
        Execute restart recovery.

        Args:
            error: The exception that triggered recovery
            component: Name of the component to restart
            restart_func: Callable that restarts the component

        Returns:
            True if restart succeeded, False otherwise
        """
        # Check restart limit
        current_count = self._restart_counts.get(component, 0)
        if current_count >= self.max_restarts:
            logger.warning(
                f"Max restarts ({self.max_restarts}) reached for {component}"
            )
            return False

        if restart_func is None:
            logger.error(f"No restart function provided for {component}")
            return False

        try:
            # Increment count before attempting
            self._restart_counts[component] = current_count + 1

            logger.info(
                f"Restarting {component} (attempt {current_count + 1}/{self.max_restarts})"
            )

            result = restart_func()

            if result:
                logger.info(f"Successfully restarted {component}")
            else:
                logger.warning(f"Restart of {component} returned False")

            return bool(result)

        except Exception as e:
            logger.error(f"Failed to restart {component}: {e}", exc_info=True)
            return False

    def reset_count(self, component: str) -> None:
        """Reset restart count for a component."""
        if component in self._restart_counts:
            del self._restart_counts[component]


class RetryStrategy(RecoveryStrategy):
    """
    Strategy that retries the operation with exponential backoff.

    Useful for transient errors like network timeouts.
    """

    # Error types that can be retried
    RETRYABLE_ERRORS: Tuple[Type[Exception], ...] = (
        ConnectionError,
        TimeoutError,
        OSError,
    )

    # Error types that should never be retried
    NON_RETRYABLE_ERRORS: Tuple[Type[Exception], ...] = (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
    )

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        backoff_multiplier: float = 2.0,
        max_delay: float = 60.0,
    ):
        """
        Initialize retry strategy.

        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Base delay between retries in seconds
            backoff_multiplier: Multiplier for exponential backoff
            max_delay: Maximum delay between retries
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.backoff_multiplier = backoff_multiplier
        self.max_delay = max_delay

    def can_handle(self, error: Exception) -> bool:
        """
        Check if the error is retryable.

        Returns:
            True for transient errors, False for programming errors
        """
        # Non-retryable errors
        if isinstance(error, self.NON_RETRYABLE_ERRORS):
            return False

        # Explicit retryable errors
        if isinstance(error, self.RETRYABLE_ERRORS):
            return True

        # Check error message for transient patterns
        error_msg = str(error).lower()
        transient_patterns = [
            "connection", "timeout", "temporary", "busy",
            "unavailable", "rate limit", "reset by peer",
            "network", "dns", "socket", "429", "503",
        ]
        return any(p in error_msg for p in transient_patterns)

    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for a given attempt number.

        Args:
            attempt: The attempt number (1-based)

        Returns:
            Delay in seconds
        """
        delay = self.base_delay * (self.backoff_multiplier ** (attempt - 1))
        return min(delay, self.max_delay)

    def execute(
        self,
        error: Exception,
        component: str,
        operation: Optional[Callable[[], Any]] = None,
        **kwargs: Any,
    ) -> bool:
        """
        Execute retry recovery.

        Args:
            error: The exception that triggered recovery
            component: Name of the component
            operation: Callable to retry

        Returns:
            True if retry succeeded, False otherwise
        """
        if operation is None:
            logger.error(f"No operation provided for retry in {component}")
            return False

        for attempt in range(1, self.max_retries + 1):
            try:
                delay = self.calculate_delay(attempt)

                if attempt > 1:
                    logger.info(
                        f"Retrying {component} in {delay:.1f}s "
                        f"(attempt {attempt}/{self.max_retries})"
                    )
                    time.sleep(delay)

                result = operation()
                logger.info(f"Retry succeeded for {component} on attempt {attempt}")
                return True

            except Exception as e:
                logger.warning(f"Retry attempt {attempt} failed: {e}")
                if attempt >= self.max_retries:
                    logger.error(
                        f"All {self.max_retries} retry attempts failed for {component}"
                    )
                    return False

        return False


class FallbackStrategy(RecoveryStrategy):
    """
    Strategy that uses an alternative operation.

    Useful when the primary operation fails but an alternative exists.
    """

    def __init__(
        self,
        fallback_func: Callable[..., Any],
    ):
        """
        Initialize fallback strategy.

        Args:
            fallback_func: Alternative function to execute
        """
        self.fallback_func = fallback_func

    def can_handle(self, error: Exception) -> bool:
        """FallbackStrategy can handle any error."""
        return True

    def execute(
        self,
        error: Exception,
        component: str,
        context: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> bool:
        """
        Execute fallback recovery.

        Args:
            error: The exception that triggered recovery
            component: Name of the component
            context: Optional context to pass to fallback

        Returns:
            True if fallback succeeded, False otherwise
        """
        try:
            logger.info(f"Executing fallback for {component}")

            result = self.fallback_func()

            logger.info(f"Fallback succeeded for {component}")
            return True

        except Exception as e:
            logger.error(f"Fallback failed for {component}: {e}", exc_info=True)
            return False


class IgnoreStrategy(RecoveryStrategy):
    """
    Strategy that logs the error and continues.

    Useful for non-critical errors that shouldn't stop execution.
    """

    def __init__(self, log_level: int = logging.WARNING):
        """
        Initialize ignore strategy.

        Args:
            log_level: Log level for the ignored error
        """
        self.log_level = log_level

    def can_handle(self, error: Exception) -> bool:
        """IgnoreStrategy can handle any error."""
        return True

    def execute(
        self,
        error: Exception,
        component: str,
        **kwargs: Any,
    ) -> bool:
        """
        Log and ignore the error.

        Args:
            error: The exception to ignore
            component: Name of the component

        Returns:
            Always returns True (continue execution)
        """
        if self.log_level == logging.WARNING:
            logger.warning(
                f"Ignoring error in {component}: {type(error).__name__}: {error}"
            )
        elif self.log_level == logging.ERROR:
            logger.error(
                f"Ignoring error in {component}: {type(error).__name__}: {error}"
            )
        elif self.log_level == logging.INFO:
            logger.info(
                f"Ignoring error in {component}: {type(error).__name__}: {error}"
            )
        else:
            logger.log(
                self.log_level,
                f"Ignoring error in {component}: {type(error).__name__}: {error}"
            )

        return True


# Strategy registry
_STRATEGY_REGISTRY: Dict[str, type] = {
    "restart": RestartStrategy,
    "retry": RetryStrategy,
    "fallback": FallbackStrategy,
    "ignore": IgnoreStrategy,
}


def get_strategy(
    name: str,
    **kwargs: Any,
) -> RecoveryStrategy:
    """
    Get a recovery strategy by name.

    Args:
        name: Strategy name ("restart", "retry", "fallback", "ignore")
        **kwargs: Arguments to pass to the strategy constructor

    Returns:
        Instantiated strategy

    Raises:
        ValueError: If strategy name is unknown
    """
    if name not in _STRATEGY_REGISTRY:
        raise ValueError(
            f"Unknown strategy: {name}. "
            f"Available: {list(_STRATEGY_REGISTRY.keys())}"
        )

    return _STRATEGY_REGISTRY[name](**kwargs)


def register_strategy(name: str, strategy_class: type) -> None:
    """
    Register a custom recovery strategy.

    Args:
        name: Name to register the strategy under
        strategy_class: Strategy class (must inherit from RecoveryStrategy)
    """
    if not issubclass(strategy_class, RecoveryStrategy):
        raise TypeError("Strategy class must inherit from RecoveryStrategy")

    _STRATEGY_REGISTRY[name] = strategy_class
