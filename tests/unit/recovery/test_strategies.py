"""
Tests for recovery strategies.

Tests the abstract RecoveryStrategy and concrete implementations:
- RestartStrategy
- RetryStrategy
- FallbackStrategy
- IgnoreStrategy
"""

import pytest
import asyncio
from typing import Any, Optional
from unittest.mock import Mock, AsyncMock, patch, MagicMock


class TestRecoveryStrategyBase:
    """Test the abstract RecoveryStrategy interface."""

    def test_strategy_is_abstract(self):
        """RecoveryStrategy should be abstract and not instantiable directly."""
        from core.recovery.strategies import RecoveryStrategy

        with pytest.raises(TypeError):
            RecoveryStrategy()

    def test_strategy_has_execute_method(self):
        """RecoveryStrategy subclasses must implement execute."""
        from core.recovery.strategies import RecoveryStrategy, RestartStrategy

        # RestartStrategy should have execute
        strategy = RestartStrategy()
        assert hasattr(strategy, "execute")
        assert callable(strategy.execute)

    def test_strategy_has_can_handle_method(self):
        """RecoveryStrategy subclasses should have can_handle method."""
        from core.recovery.strategies import RestartStrategy

        strategy = RestartStrategy()
        assert hasattr(strategy, "can_handle")
        assert callable(strategy.can_handle)


class TestRestartStrategy:
    """Tests for RestartStrategy - restarts a component."""

    def test_init_default(self):
        """RestartStrategy should initialize with defaults."""
        from core.recovery.strategies import RestartStrategy

        strategy = RestartStrategy()
        assert strategy.max_restarts == 3
        assert strategy.cooldown_seconds == 10

    def test_init_custom(self):
        """RestartStrategy should accept custom parameters."""
        from core.recovery.strategies import RestartStrategy

        strategy = RestartStrategy(max_restarts=5, cooldown_seconds=30)
        assert strategy.max_restarts == 5
        assert strategy.cooldown_seconds == 30

    def test_can_handle_always_true(self):
        """RestartStrategy can handle any error."""
        from core.recovery.strategies import RestartStrategy

        strategy = RestartStrategy()
        assert strategy.can_handle(ConnectionError("test")) is True
        assert strategy.can_handle(ValueError("test")) is True

    def test_execute_calls_restart_func(self):
        """execute should call the provided restart function."""
        from core.recovery.strategies import RestartStrategy

        strategy = RestartStrategy()
        restart_func = Mock()

        result = strategy.execute(
            error=ConnectionError("test"),
            component="x_bot",
            restart_func=restart_func
        )

        restart_func.assert_called_once()

    def test_execute_returns_true_on_success(self):
        """execute should return True when restart succeeds."""
        from core.recovery.strategies import RestartStrategy

        strategy = RestartStrategy()
        restart_func = Mock(return_value=True)

        result = strategy.execute(
            error=ConnectionError("test"),
            component="x_bot",
            restart_func=restart_func
        )

        assert result is True

    def test_execute_returns_false_on_failure(self):
        """execute should return False when restart fails."""
        from core.recovery.strategies import RestartStrategy

        strategy = RestartStrategy()
        restart_func = Mock(side_effect=RuntimeError("Restart failed"))

        result = strategy.execute(
            error=ConnectionError("test"),
            component="x_bot",
            restart_func=restart_func
        )

        assert result is False

    def test_execute_respects_max_restarts(self):
        """execute should respect max_restarts limit."""
        from core.recovery.strategies import RestartStrategy

        strategy = RestartStrategy(max_restarts=2)
        restart_func = Mock(return_value=True)

        # First two should succeed
        result1 = strategy.execute(ConnectionError("1"), "bot", restart_func=restart_func)
        result2 = strategy.execute(ConnectionError("2"), "bot", restart_func=restart_func)

        # Third should fail due to limit
        result3 = strategy.execute(ConnectionError("3"), "bot", restart_func=restart_func)

        assert result1 is True
        assert result2 is True
        assert result3 is False


class TestRetryStrategy:
    """Tests for RetryStrategy - retries the operation."""

    def test_init_default(self):
        """RetryStrategy should initialize with defaults."""
        from core.recovery.strategies import RetryStrategy

        strategy = RetryStrategy()
        assert strategy.max_retries == 3
        assert strategy.base_delay == 1.0
        assert strategy.backoff_multiplier == 2.0

    def test_init_custom(self):
        """RetryStrategy should accept custom parameters."""
        from core.recovery.strategies import RetryStrategy

        strategy = RetryStrategy(
            max_retries=5,
            base_delay=0.5,
            backoff_multiplier=3.0
        )
        assert strategy.max_retries == 5
        assert strategy.base_delay == 0.5
        assert strategy.backoff_multiplier == 3.0

    def test_can_handle_retryable_errors(self):
        """RetryStrategy should handle retryable errors."""
        from core.recovery.strategies import RetryStrategy

        strategy = RetryStrategy()
        # Transient errors
        assert strategy.can_handle(ConnectionError("test")) is True
        assert strategy.can_handle(TimeoutError("test")) is True
        assert strategy.can_handle(OSError("test")) is True

    def test_can_handle_non_retryable_errors(self):
        """RetryStrategy should not handle non-retryable errors."""
        from core.recovery.strategies import RetryStrategy

        strategy = RetryStrategy()
        # Programming errors
        assert strategy.can_handle(ValueError("test")) is False
        assert strategy.can_handle(TypeError("test")) is False
        assert strategy.can_handle(KeyError("test")) is False

    def test_execute_retries_operation(self):
        """execute should retry the operation."""
        from core.recovery.strategies import RetryStrategy

        strategy = RetryStrategy(max_retries=3, base_delay=0.01)

        attempts = []
        def operation():
            attempts.append(1)
            if len(attempts) < 2:
                raise ConnectionError("Retrying...")
            return "success"

        result = strategy.execute(
            error=ConnectionError("test"),
            component="x_bot",
            operation=operation
        )

        assert result is True
        assert len(attempts) == 2

    def test_execute_respects_max_retries(self):
        """execute should give up after max_retries."""
        from core.recovery.strategies import RetryStrategy

        strategy = RetryStrategy(max_retries=2, base_delay=0.01)

        attempts = []
        def operation():
            attempts.append(1)
            raise ConnectionError("Always fails")

        result = strategy.execute(
            error=ConnectionError("test"),
            component="x_bot",
            operation=operation
        )

        assert result is False
        assert len(attempts) == 2

    def test_calculate_delay_exponential(self):
        """RetryStrategy should use exponential backoff."""
        from core.recovery.strategies import RetryStrategy

        strategy = RetryStrategy(base_delay=1.0, backoff_multiplier=2.0)

        delay1 = strategy.calculate_delay(1)
        delay2 = strategy.calculate_delay(2)
        delay3 = strategy.calculate_delay(3)

        assert delay1 == 1.0
        assert delay2 == 2.0
        assert delay3 == 4.0


class TestFallbackStrategy:
    """Tests for FallbackStrategy - uses an alternative operation."""

    def test_init_with_fallback_func(self):
        """FallbackStrategy should require a fallback function."""
        from core.recovery.strategies import FallbackStrategy

        fallback = Mock(return_value="fallback_result")
        strategy = FallbackStrategy(fallback_func=fallback)

        assert strategy.fallback_func == fallback

    def test_can_handle_always_true(self):
        """FallbackStrategy can handle any error."""
        from core.recovery.strategies import FallbackStrategy

        fallback = Mock()
        strategy = FallbackStrategy(fallback_func=fallback)

        assert strategy.can_handle(ConnectionError("test")) is True
        assert strategy.can_handle(ValueError("test")) is True

    def test_execute_calls_fallback(self):
        """execute should call the fallback function."""
        from core.recovery.strategies import FallbackStrategy

        fallback = Mock(return_value="fallback_result")
        strategy = FallbackStrategy(fallback_func=fallback)

        result = strategy.execute(
            error=ConnectionError("test"),
            component="x_bot"
        )

        assert result is True
        fallback.assert_called_once()

    def test_execute_passes_context_to_fallback(self):
        """execute should pass error context to fallback."""
        from core.recovery.strategies import FallbackStrategy

        fallback = Mock(return_value="fallback_result")
        strategy = FallbackStrategy(fallback_func=fallback)

        error = ConnectionError("test")
        strategy.execute(error=error, component="x_bot", context={"key": "value"})

        # Fallback should receive error and context
        fallback.assert_called_once()

    def test_execute_returns_false_on_fallback_failure(self):
        """execute should return False if fallback fails."""
        from core.recovery.strategies import FallbackStrategy

        fallback = Mock(side_effect=RuntimeError("Fallback failed"))
        strategy = FallbackStrategy(fallback_func=fallback)

        result = strategy.execute(
            error=ConnectionError("test"),
            component="x_bot"
        )

        assert result is False


class TestIgnoreStrategy:
    """Tests for IgnoreStrategy - logs and continues."""

    def test_init_default(self):
        """IgnoreStrategy should initialize with defaults."""
        from core.recovery.strategies import IgnoreStrategy

        strategy = IgnoreStrategy()
        assert hasattr(strategy, "log_level")

    def test_init_custom_log_level(self):
        """IgnoreStrategy should accept custom log level."""
        from core.recovery.strategies import IgnoreStrategy
        import logging

        strategy = IgnoreStrategy(log_level=logging.ERROR)
        assert strategy.log_level == logging.ERROR

    def test_can_handle_always_true(self):
        """IgnoreStrategy can handle any error."""
        from core.recovery.strategies import IgnoreStrategy

        strategy = IgnoreStrategy()
        assert strategy.can_handle(ConnectionError("test")) is True
        assert strategy.can_handle(ValueError("test")) is True

    def test_execute_always_returns_true(self):
        """execute should always return True (ignore and continue)."""
        from core.recovery.strategies import IgnoreStrategy

        strategy = IgnoreStrategy()

        result = strategy.execute(
            error=ConnectionError("test"),
            component="x_bot"
        )

        assert result is True

    def test_execute_logs_error(self):
        """execute should log the error."""
        from core.recovery.strategies import IgnoreStrategy
        import logging

        strategy = IgnoreStrategy(log_level=logging.WARNING)

        with patch("core.recovery.strategies.logger") as mock_logger:
            strategy.execute(
                error=ConnectionError("test error"),
                component="x_bot"
            )

            mock_logger.warning.assert_called()


class TestStrategyRegistry:
    """Tests for strategy registration and lookup."""

    def test_get_strategy_by_name(self):
        """Should be able to get strategy by name."""
        from core.recovery.strategies import get_strategy

        restart = get_strategy("restart")
        retry = get_strategy("retry")
        fallback = get_strategy("fallback", fallback_func=Mock())
        ignore = get_strategy("ignore")

        from core.recovery.strategies import (
            RestartStrategy, RetryStrategy, FallbackStrategy, IgnoreStrategy
        )

        assert isinstance(restart, RestartStrategy)
        assert isinstance(retry, RetryStrategy)
        assert isinstance(fallback, FallbackStrategy)
        assert isinstance(ignore, IgnoreStrategy)

    def test_get_strategy_unknown(self):
        """get_strategy should raise for unknown strategies."""
        from core.recovery.strategies import get_strategy

        with pytest.raises(ValueError):
            get_strategy("unknown_strategy")
