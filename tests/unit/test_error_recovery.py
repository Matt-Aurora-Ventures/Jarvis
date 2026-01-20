"""
Comprehensive Error Recovery Tests for JARVIS

Tests for:
- Graceful degradation when services fail
- Retry logic with exponential backoff
- Circuit breaker patterns
- Error logging and classification

Run with: pytest tests/unit/test_error_recovery.py -v
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_logger():
    """Create a mock logger to capture log output."""
    logger = MagicMock(spec=logging.Logger)
    return logger


@pytest.fixture
def call_tracker():
    """Track function calls for testing.

    Usage:
        call_tracker.fail_until = 3  # Fail calls 1, 2 (succeed on 3)

    The should_fail() method returns True when call_count < fail_until.
    Since record() increments call_count BEFORE should_fail() is checked:
        - fail_until=2: call 1 fails (1<2), call 2 succeeds (2<2=False)
        - fail_until=3: calls 1,2 fail, call 3 succeeds
    """
    class CallTracker:
        def __init__(self):
            self.calls: List[Dict[str, Any]] = []
            self.call_count = 0
            self.fail_until = 0

        def record(self, **kwargs):
            self.call_count += 1
            self.calls.append({
                "count": self.call_count,
                "time": time.time(),
                **kwargs
            })

        def should_fail(self) -> bool:
            """Returns True if current call should fail.

            Call this AFTER record() - checks if call_count < fail_until.
            """
            return self.call_count < self.fail_until

        def reset(self):
            self.calls = []
            self.call_count = 0
            self.fail_until = 0

    return CallTracker()


# =============================================================================
# RetryPolicy Tests
# =============================================================================


class TestRetryPolicy:
    """Tests for RetryPolicy configuration and behavior."""

    def test_default_policy_creation(self):
        """RetryPolicy creates with sensible defaults."""
        from core.resilience.retry import RetryPolicy

        policy = RetryPolicy()

        assert policy.max_attempts == 3
        assert policy.base_delay == 1.0
        assert policy.max_delay == 60.0
        assert policy.exponential_base == 2.0
        assert policy.jitter is True

    def test_custom_policy_creation(self):
        """RetryPolicy accepts custom configuration."""
        from core.resilience.retry import RetryPolicy

        policy = RetryPolicy(
            max_attempts=5,
            base_delay=0.5,
            max_delay=30.0,
            exponential_base=3.0,
            jitter=False
        )

        assert policy.max_attempts == 5
        assert policy.base_delay == 0.5
        assert policy.max_delay == 30.0
        assert policy.exponential_base == 3.0
        assert policy.jitter is False

    def test_delay_calculation_exponential(self):
        """get_delay returns exponentially increasing delays."""
        from core.resilience.retry import RetryPolicy

        policy = RetryPolicy(base_delay=1.0, exponential_base=2.0, jitter=False)

        # Attempt 1: 1.0 * 2^0 = 1.0
        assert policy.get_delay(1) == 1.0
        # Attempt 2: 1.0 * 2^1 = 2.0
        assert policy.get_delay(2) == 2.0
        # Attempt 3: 1.0 * 2^2 = 4.0
        assert policy.get_delay(3) == 4.0

    def test_delay_capped_at_max(self):
        """get_delay never exceeds max_delay."""
        from core.resilience.retry import RetryPolicy

        policy = RetryPolicy(base_delay=1.0, max_delay=5.0, jitter=False)

        # Even at attempt 10, should not exceed max
        delay = policy.get_delay(10)
        assert delay <= 5.0

    def test_jitter_adds_randomness(self):
        """Jitter adds randomness to delay."""
        from core.resilience.retry import RetryPolicy

        policy = RetryPolicy(base_delay=1.0, jitter=True, jitter_factor=0.5)

        # Collect multiple delay values
        delays = [policy.get_delay(1) for _ in range(20)]

        # Should have some variation
        unique_delays = len(set(round(d, 3) for d in delays))
        assert unique_delays > 1, "Jitter should produce varying delays"

    def test_should_retry_recognizes_retryable(self):
        """should_retry returns True for retryable exceptions."""
        from core.resilience.retry import RetryPolicy

        policy = RetryPolicy(
            retryable_exceptions=[ConnectionError, TimeoutError]
        )

        assert policy.should_retry(ConnectionError("network down")) is True
        assert policy.should_retry(TimeoutError("timed out")) is True

    def test_should_retry_rejects_non_retryable(self):
        """should_retry returns False for non-retryable exceptions."""
        from core.resilience.retry import RetryPolicy

        policy = RetryPolicy(
            retryable_exceptions=[ConnectionError],
            non_retryable_exceptions=[KeyboardInterrupt, ValueError]
        )

        assert policy.should_retry(KeyboardInterrupt()) is False
        assert policy.should_retry(ValueError("bad value")) is False


# =============================================================================
# Retry Decorator Tests
# =============================================================================


class TestRetryDecorator:
    """Tests for the @retry decorator."""

    @pytest.mark.asyncio
    async def test_succeeds_without_retry(self, call_tracker):
        """Successful functions don't trigger retries."""
        from core.resilience.retry import retry

        @retry(max_attempts=3)
        async def success_func():
            call_tracker.record(status="success")
            return "result"

        result = await success_func()

        assert result == "result"
        assert call_tracker.call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_failure(self, call_tracker):
        """Functions retry on failure until success."""
        from core.resilience.retry import retry

        # fail_until=3 means: call 1 fails (1<3), call 2 fails (2<3), call 3 succeeds (3<3=False)
        call_tracker.fail_until = 3

        @retry(max_attempts=5, base_delay=0.01)
        async def flaky_func():
            call_tracker.record(status="called")
            if call_tracker.should_fail():
                raise ConnectionError("temporary failure")
            return "success"

        result = await flaky_func()

        assert result == "success"
        assert call_tracker.call_count == 3  # 2 failures + 1 success

    @pytest.mark.asyncio
    async def test_raises_after_max_attempts(self, call_tracker):
        """RetryExhausted raised after max attempts."""
        from core.resilience.retry import retry, RetryExhausted

        @retry(max_attempts=3, base_delay=0.01)
        async def always_fails():
            call_tracker.record(status="failed")
            raise ValueError("permanent failure")

        with pytest.raises(RetryExhausted) as exc_info:
            await always_fails()

        assert exc_info.value.attempts == 3
        assert call_tracker.call_count == 3

    @pytest.mark.asyncio
    async def test_non_retryable_exception_not_retried(self, call_tracker):
        """Non-retryable exceptions propagate immediately."""
        from core.resilience.retry import retry

        @retry(max_attempts=3, base_delay=0.01)
        async def raises_keyboard_interrupt():
            call_tracker.record(status="called")
            raise KeyboardInterrupt()

        with pytest.raises(KeyboardInterrupt):
            await raises_keyboard_interrupt()

        assert call_tracker.call_count == 1  # No retries

    @pytest.mark.asyncio
    async def test_on_retry_callback_called(self, call_tracker):
        """on_retry callback is invoked on each retry."""
        from core.resilience.retry import retry, RetryPolicy

        retry_events = []

        def on_retry_handler(attempt, exception, delay):
            retry_events.append({
                "attempt": attempt,
                "error": str(exception),
                "delay": delay
            })

        policy = RetryPolicy(
            max_attempts=3,
            base_delay=0.01,
            on_retry=on_retry_handler
        )

        # fail_until=2 means: call 1 fails (1<2), call 2 succeeds (2<2=False)
        # So only 1 retry event (after first failure)
        call_tracker.fail_until = 2

        @retry(policy=policy)
        async def flaky_func():
            call_tracker.record()
            if call_tracker.should_fail():
                raise ConnectionError("network error")
            return "ok"

        await flaky_func()

        # 1 failure = 1 retry callback
        assert len(retry_events) == 1
        assert retry_events[0]["attempt"] == 1


class TestRetrySync:
    """Tests for synchronous retry behavior."""

    def test_sync_retry_succeeds(self, call_tracker):
        """Sync functions can use retry decorator."""
        from core.resilience.retry import retry

        # fail_until=2 means: call 1 fails (1<2), call 2 succeeds (2<2=False)
        call_tracker.fail_until = 2

        @retry(max_attempts=3, base_delay=0.01)
        def sync_func():
            call_tracker.record()
            if call_tracker.should_fail():
                raise OSError("disk error")
            return "done"

        result = sync_func()

        assert result == "done"
        assert call_tracker.call_count == 2  # 1 failure + 1 success


# =============================================================================
# CircuitBreaker Tests (core/resilience)
# =============================================================================


class TestCircuitBreakerStates:
    """Tests for circuit breaker state machine."""

    def test_initial_state_closed(self):
        """Circuit breaker starts in CLOSED state."""
        from core.resilience.circuit_breaker import CircuitBreaker, CircuitState

        cb = CircuitBreaker("test_initial", failure_threshold=3)

        assert cb.state == CircuitState.CLOSED
        assert cb.allow_request() is True

    @pytest.mark.asyncio
    async def test_opens_after_failures(self):
        """Circuit opens after failure_threshold failures."""
        from core.resilience.circuit_breaker import (
            CircuitBreaker,
            CircuitState,
            CircuitOpenError
        )

        cb = CircuitBreaker("test_opens", failure_threshold=3, timeout=10.0)

        # Record failures
        for i in range(3):
            cb.record_failure(Exception(f"failure {i}"))

        assert cb.state == CircuitState.OPEN
        assert cb.allow_request() is False

        # Subsequent calls should be rejected
        with pytest.raises(CircuitOpenError) as exc_info:
            await cb.call(AsyncMock(return_value="test"))

        assert "test_opens" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_half_open_after_timeout(self):
        """Circuit transitions to HALF_OPEN after timeout."""
        from core.resilience.circuit_breaker import CircuitBreaker, CircuitState

        cb = CircuitBreaker("test_halfopen", failure_threshold=2, timeout=0.1)

        # Open the circuit
        cb.record_failure(Exception("fail 1"))
        cb.record_failure(Exception("fail 2"))

        assert cb.state == CircuitState.OPEN

        # Wait for timeout
        await asyncio.sleep(0.15)

        # Accessing state should trigger half-open
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.allow_request() is True

    @pytest.mark.asyncio
    async def test_closes_after_success_in_half_open(self):
        """Circuit closes after success_threshold successes in HALF_OPEN."""
        from core.resilience.circuit_breaker import CircuitBreaker, CircuitState

        cb = CircuitBreaker(
            "test_close",
            failure_threshold=2,
            success_threshold=2,
            timeout=0.05
        )

        # Open the circuit
        cb.record_failure(Exception("fail"))
        cb.record_failure(Exception("fail"))

        # Wait for half-open
        await asyncio.sleep(0.1)
        _ = cb.state  # Trigger transition

        # Record successes
        cb.record_success()
        cb.record_success()

        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_reopens_on_failure_in_half_open(self):
        """Circuit reopens on failure in HALF_OPEN state."""
        from core.resilience.circuit_breaker import CircuitBreaker, CircuitState

        cb = CircuitBreaker("test_reopen", failure_threshold=2, timeout=0.05)

        # Open the circuit
        cb.record_failure(Exception("fail"))
        cb.record_failure(Exception("fail"))

        # Wait for half-open
        await asyncio.sleep(0.1)
        _ = cb.state  # Trigger transition

        assert cb.state == CircuitState.HALF_OPEN

        # Failure in half-open should reopen
        cb.record_failure(Exception("still failing"))

        assert cb.state == CircuitState.OPEN


class TestCircuitBreakerCallbacks:
    """Tests for circuit breaker callbacks."""

    def test_on_open_callback(self):
        """on_open callback is invoked when circuit opens."""
        from core.resilience.circuit_breaker import CircuitBreaker

        opened = []

        cb = CircuitBreaker(
            "test_callback",
            failure_threshold=2,
            on_open=lambda: opened.append("opened")
        )

        cb.record_failure(Exception("fail"))
        cb.record_failure(Exception("fail"))

        assert opened == ["opened"]

    @pytest.mark.asyncio
    async def test_on_close_callback(self):
        """on_close callback is invoked when circuit closes."""
        from core.resilience.circuit_breaker import CircuitBreaker

        closed = []

        cb = CircuitBreaker(
            "test_close_callback",
            failure_threshold=2,
            success_threshold=1,
            timeout=0.05,
            on_close=lambda: closed.append("closed")
        )

        # Open then close
        cb.record_failure(Exception("fail"))
        cb.record_failure(Exception("fail"))

        await asyncio.sleep(0.1)
        _ = cb.state  # Trigger half-open
        cb.record_success()

        assert closed == ["closed"]


class TestCircuitBreakerStatistics:
    """Tests for circuit breaker statistics."""

    @pytest.mark.asyncio
    async def test_stats_track_calls(self):
        """Stats accurately track all call outcomes."""
        from core.resilience.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker("test_stats", failure_threshold=10)

        # Successful calls
        for _ in range(5):
            await cb.call(AsyncMock(return_value="ok"))

        # Failed calls (catch exceptions)
        for _ in range(3):
            try:
                await cb.call(AsyncMock(side_effect=Exception("fail")))
            except Exception:
                pass

        stats = cb.stats
        assert stats.successful_calls == 5
        assert stats.failed_calls == 3
        assert stats.total_calls == 8

    def test_stats_failure_rate(self):
        """Stats correctly calculate failure rate."""
        from core.resilience.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker("test_rate", failure_threshold=100)

        # 3 successes, 2 failures = 40% failure rate
        for _ in range(3):
            cb.record_success()
        for _ in range(2):
            cb.record_failure(Exception("fail"))

        assert cb.stats.failure_rate == 0.4


class TestCircuitBreakerExcludedExceptions:
    """Tests for excluded exceptions feature."""

    def test_excluded_exceptions_dont_trip_breaker(self):
        """Excluded exceptions don't count toward failures."""
        from core.resilience.circuit_breaker import CircuitBreaker, CircuitState

        cb = CircuitBreaker(
            "test_excluded",
            failure_threshold=2,
            excluded_exceptions=[ValueError]
        )

        # ValueError is excluded, shouldn't open circuit
        for _ in range(5):
            cb.record_failure(ValueError("excluded"))

        assert cb.state == CircuitState.CLOSED
        assert cb.stats.consecutive_failures == 0

    def test_non_excluded_exceptions_trip_breaker(self):
        """Non-excluded exceptions do count toward failures."""
        from core.resilience.circuit_breaker import CircuitBreaker, CircuitState

        cb = CircuitBreaker(
            "test_non_excluded",
            failure_threshold=2,
            excluded_exceptions=[ValueError]
        )

        # RuntimeError is not excluded
        cb.record_failure(RuntimeError("not excluded"))
        cb.record_failure(RuntimeError("not excluded"))

        assert cb.state == CircuitState.OPEN


# =============================================================================
# Bot Error Recovery Tests
# =============================================================================


class TestBotErrorClassification:
    """Tests for error classification."""

    def test_classify_timeout_error(self):
        """TimeoutError classified as LOW severity."""
        from core.bot.error_recovery import classify_error, ErrorSeverity

        error = TimeoutError("connection timed out")
        severity = classify_error(error)

        assert severity == ErrorSeverity.LOW

    def test_classify_connection_error(self):
        """ConnectionError classified as MEDIUM severity."""
        from core.bot.error_recovery import classify_error, ErrorSeverity

        error = ConnectionError("network unreachable")
        severity = classify_error(error)

        assert severity == ErrorSeverity.MEDIUM

    def test_classify_permission_error(self):
        """PermissionError classified as HIGH severity."""
        from core.bot.error_recovery import classify_error, ErrorSeverity

        error = PermissionError("access denied")
        severity = classify_error(error)

        assert severity == ErrorSeverity.HIGH

    def test_classify_rate_limit_from_message(self):
        """Rate limit errors detected from message text."""
        from core.bot.error_recovery import classify_error, ErrorSeverity

        error = Exception("Rate limit exceeded. Try again later.")
        severity = classify_error(error)

        assert severity == ErrorSeverity.MEDIUM


class TestBotErrorHandler:
    """Tests for BotErrorHandler."""

    @pytest.fixture
    def handler(self):
        """Create a fresh error handler."""
        from core.bot.error_recovery import BotErrorHandler
        return BotErrorHandler()

    @pytest.mark.asyncio
    async def test_handles_low_severity_with_retry(self, handler):
        """Low severity errors result in retry action."""
        from core.bot.error_recovery import (
            ErrorContext,
            ErrorSeverity,
            RecoveryAction
        )

        context = ErrorContext(
            error=TimeoutError("timed out"),
            severity=ErrorSeverity.LOW,
            bot_type="telegram",
            attempt=1,
            max_attempts=3
        )

        result = await handler.handle_error(context)

        assert result.action == RecoveryAction.RETRY
        assert result.should_retry is True

    @pytest.mark.asyncio
    async def test_handles_medium_severity_with_backoff(self, handler):
        """Medium severity errors use exponential backoff."""
        from core.bot.error_recovery import (
            ErrorContext,
            ErrorSeverity,
            RecoveryAction
        )

        context = ErrorContext(
            error=ConnectionError("network down"),
            severity=ErrorSeverity.MEDIUM,
            bot_type="telegram",
            attempt=1,
            max_attempts=3
        )

        result = await handler.handle_error(context)

        assert result.action == RecoveryAction.RETRY
        assert result.should_retry is True
        assert result.delay_seconds > 0  # Has backoff delay

    @pytest.mark.asyncio
    async def test_stops_retry_at_max_attempts(self, handler):
        """Handler stops retrying at max_attempts."""
        from core.bot.error_recovery import (
            ErrorContext,
            ErrorSeverity,
            RecoveryAction
        )

        context = ErrorContext(
            error=TimeoutError("timed out"),
            severity=ErrorSeverity.LOW,
            bot_type="telegram",
            attempt=3,  # At max
            max_attempts=3
        )

        result = await handler.handle_error(context)

        assert result.should_retry is False
        assert result.action == RecoveryAction.SKIP

    @pytest.mark.asyncio
    async def test_tracks_error_statistics(self, handler):
        """Handler tracks error counts."""
        from core.bot.error_recovery import ErrorContext, ErrorSeverity

        for i in range(3):
            context = ErrorContext(
                error=TimeoutError(f"timeout {i}"),
                severity=ErrorSeverity.LOW,
                bot_type="telegram"
            )
            await handler.handle_error(context)

        stats = handler.get_error_stats()

        assert stats["total_errors"] == 3
        assert "telegram:TimeoutError" in stats["error_counts"]

    @pytest.mark.asyncio
    async def test_notifies_error_listeners(self, handler):
        """Error listeners are notified of errors."""
        from core.bot.error_recovery import ErrorContext, ErrorSeverity

        received_errors = []

        async def listener(context):
            received_errors.append(context)

        handler.add_error_listener(listener)

        context = ErrorContext(
            error=ValueError("test"),
            severity=ErrorSeverity.LOW,
            bot_type="twitter"
        )

        await handler.handle_error(context)

        assert len(received_errors) == 1
        assert received_errors[0].bot_type == "twitter"

    @pytest.mark.asyncio
    async def test_custom_recovery_handler(self, handler):
        """Custom recovery handlers can be registered."""
        from core.bot.error_recovery import (
            ErrorContext,
            ErrorSeverity,
            RecoveryResult,
            RecoveryAction
        )

        async def custom_handler(context):
            return RecoveryResult(
                success=True,
                action=RecoveryAction.NOTIFY_ADMIN,
                message="Custom handling"
            )

        handler.register_recovery_handler(ErrorSeverity.HIGH, custom_handler)

        context = ErrorContext(
            error=PermissionError("access denied"),
            severity=ErrorSeverity.HIGH,
            bot_type="telegram"
        )

        result = await handler.handle_error(context)

        assert result.action == RecoveryAction.NOTIFY_ADMIN
        assert result.message == "Custom handling"


# =============================================================================
# Graceful Degradation Tests
# =============================================================================


class TestGracefulDegradation:
    """Tests for graceful degradation patterns."""

    def test_service_registration(self):
        """Services can be registered."""
        from core.resilience.degradation import GracefulDegradation

        gd = GracefulDegradation()
        gd.register_service("database")
        gd.register_service("cache")
        gd.register_service("api")

        assert "database" in gd.services
        assert "cache" in gd.services
        assert "api" in gd.services

    def test_service_level_full_when_healthy(self):
        """Service level is FULL when all services healthy."""
        from core.resilience.degradation import GracefulDegradation, ServiceLevel

        gd = GracefulDegradation()
        gd.register_service("db")
        gd.register_service("cache")

        gd.report_success("db")
        gd.report_success("cache")

        assert gd.service_level == ServiceLevel.FULL

    def test_service_level_degrades_on_failures(self):
        """Service level degrades when services fail."""
        from core.resilience.degradation import GracefulDegradation, ServiceLevel

        gd = GracefulDegradation()
        gd.register_service("db")
        gd.register_service("cache")

        # Report multiple failures for one service
        for _ in range(5):
            gd.report_failure("cache")

        # Should not be FULL anymore
        assert gd.service_level != ServiceLevel.FULL

    def test_feature_can_be_disabled(self):
        """Features can be manually disabled."""
        from core.resilience.degradation import GracefulDegradation

        gd = GracefulDegradation()

        assert gd.is_feature_available("advanced_search") is True

        gd.disable_feature("advanced_search")

        assert gd.is_feature_available("advanced_search") is False

    def test_feature_can_be_reenabled(self):
        """Disabled features can be re-enabled."""
        from core.resilience.degradation import GracefulDegradation

        gd = GracefulDegradation()
        gd.disable_feature("feature_x")
        gd.enable_feature("feature_x")

        assert gd.is_feature_available("feature_x") is True

    def test_get_status_returns_summary(self):
        """get_status returns complete status summary."""
        from core.resilience.degradation import GracefulDegradation

        gd = GracefulDegradation()
        gd.register_service("db")
        gd.disable_feature("feature_y")

        status = gd.get_status()

        assert "level" in status
        assert "services" in status
        assert "disabled_features" in status
        assert "feature_y" in status["disabled_features"]


# =============================================================================
# Fallback Chain Tests
# =============================================================================


class TestFallbackChain:
    """Tests for fallback chain patterns."""

    @pytest.mark.asyncio
    async def test_uses_primary_on_success(self):
        """Primary function is used when successful."""
        from core.resilience.fallback import FallbackChain

        async def primary():
            return "primary_result"

        async def fallback():
            return "fallback_result"

        chain = FallbackChain(primary, fallback)
        result = await chain.execute()

        assert result == "primary_result"

    @pytest.mark.asyncio
    async def test_uses_fallback_on_failure(self):
        """Fallback function is used when primary fails."""
        from core.resilience.fallback import FallbackChain

        async def primary():
            raise Exception("primary failed")

        async def fallback():
            return "fallback_result"

        chain = FallbackChain(primary, fallback)
        result = await chain.execute()

        assert result == "fallback_result"

    @pytest.mark.asyncio
    async def test_chains_multiple_fallbacks(self):
        """Multiple fallbacks are tried in order."""
        from core.resilience.fallback import FallbackChain

        async def first():
            raise Exception("first failed")

        async def second():
            raise Exception("second failed")

        async def third():
            return "third_result"

        chain = FallbackChain(first, second, third)
        result = await chain.execute()

        assert result == "third_result"


class TestWithFallbackDecorator:
    """Tests for @with_fallback decorator."""

    @pytest.mark.asyncio
    async def test_returns_fallback_value_on_failure(self):
        """Falls back to static value on failure."""
        from core.resilience.fallback import with_fallback

        @with_fallback(fallback_value="default")
        async def failing_func():
            raise Exception("error")

        result = await failing_func()

        assert result == "default"

    @pytest.mark.asyncio
    async def test_returns_result_on_success(self):
        """Returns actual result when successful."""
        from core.resilience.fallback import with_fallback

        @with_fallback(fallback_value="default")
        async def working_func():
            return "actual_result"

        result = await working_func()

        assert result == "actual_result"

    @pytest.mark.asyncio
    async def test_uses_fallback_function(self):
        """Falls back to function when provided."""
        from core.resilience.fallback import with_fallback

        async def get_default():
            return "computed_default"

        @with_fallback(fallback_func=get_default)
        async def failing_func():
            raise Exception("error")

        result = await failing_func()

        assert result == "computed_default"


# =============================================================================
# Error Logging Tests
# =============================================================================


class TestErrorLogging:
    """Tests for error logging and capture."""

    def test_error_record_creation(self):
        """ErrorRecord correctly captures error details."""
        from core.error_recovery import ErrorRecord, ErrorSeverity

        error = ValueError("test error")
        record = ErrorRecord(
            error=error,
            context={"user_id": "123"},
            severity=ErrorSeverity.MEDIUM
        )

        assert record.error == error
        assert record.context["user_id"] == "123"
        assert record.severity == ErrorSeverity.MEDIUM
        assert record.error_id.startswith("err_")

    def test_error_record_to_dict(self):
        """ErrorRecord serializes to dictionary."""
        from core.error_recovery import ErrorRecord, ErrorSeverity

        error = TypeError("bad type")
        record = ErrorRecord(
            error=error,
            context={"key": "value"},
            severity=ErrorSeverity.LOW
        )

        data = record.to_dict()

        assert data["type"] == "TypeError"
        assert data["severity"] == "low"
        assert "stack_trace" in data
        assert data["context"]["key"] == "value"

    def test_transient_error_detection(self):
        """Transient errors are correctly identified."""
        from core.error_recovery import _is_transient_error

        # Transient errors
        assert _is_transient_error(TimeoutError("timed out")) is True
        assert _is_transient_error(ConnectionError("network down")) is True
        assert _is_transient_error(Exception("rate limit exceeded")) is True
        assert _is_transient_error(Exception("socket error")) is True

        # Non-transient errors
        assert _is_transient_error(ValueError("bad value")) is False
        assert _is_transient_error(KeyError("missing key")) is False


# =============================================================================
# Integration Tests
# =============================================================================


class TestErrorRecoveryIntegration:
    """Integration tests combining multiple error recovery patterns."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_prevents_cascade(self):
        """Circuit breaker prevents cascading failures."""
        from core.resilience.circuit_breaker import CircuitBreaker, CircuitState, CircuitOpenError

        cb = CircuitBreaker("cascade_test", failure_threshold=3, timeout=1.0)

        # Simulate 3 failures to open circuit
        for _ in range(3):
            cb.record_failure(ConnectionError("service down"))

        assert cb.state == CircuitState.OPEN

        # Verify circuit is open and rejecting requests
        assert cb.allow_request() is False

        # Check that rejected calls don't increase failure count
        initial_failures = cb.stats.failed_calls
        cb.allow_request()  # This should not count as failure
        assert cb.stats.failed_calls == initial_failures

    @pytest.mark.asyncio
    async def test_retry_exhaustion_with_circuit_breaker(self):
        """Retries exhaust then circuit breaker kicks in."""
        from core.resilience.retry import retry, RetryExhausted
        from core.resilience.circuit_breaker import CircuitBreaker, CircuitState

        cb = CircuitBreaker("exhaustion_test", failure_threshold=5, timeout=1.0)

        @retry(max_attempts=3, base_delay=0.01)
        async def failing_operation():
            cb.record_failure(ConnectionError("fail"))
            raise ConnectionError("service unavailable")

        # First round of retries
        with pytest.raises(RetryExhausted):
            await failing_operation()

        # Circuit should have recorded 3 failures
        assert cb.stats.failed_calls == 3

        # Second round pushes over threshold
        with pytest.raises(RetryExhausted):
            await failing_operation()

        # Now circuit should be open (6 failures > 5 threshold)
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_fallback_with_degradation(self):
        """Fallback chain integrates with degradation."""
        from core.resilience.fallback import FallbackChain
        from core.resilience.degradation import GracefulDegradation, ServiceLevel

        gd = GracefulDegradation()
        gd.register_service("primary_api")
        gd.register_service("backup_api")

        async def primary():
            gd.report_failure("primary_api")
            raise Exception("primary down")

        async def backup():
            gd.report_success("backup_api")
            return "backup_result"

        chain = FallbackChain(primary, backup)
        result = await chain.execute()

        assert result == "backup_result"
        # Primary should be marked as unhealthy after multiple failures
        # But single failure won't mark it unhealthy (threshold = 3)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
