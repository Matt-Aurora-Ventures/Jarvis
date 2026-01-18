"""
Integration tests for API fallback chains and circuit breaker behaviors.

Tests:
- Grok -> Claude -> Template fallback chain
- Circuit breaker activation and recovery
- Rate limit handling
- Timeout scenarios
- Degraded operation modes

All external APIs are mocked to enable fast, reliable testing.
"""

import pytest
import asyncio
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from typing import Any, Dict, Optional
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitOpenError,
    get_circuit_breaker,
    circuit_breaker,
)
from core.resilience.backoff import (
    BackoffConfig,
    calculate_backoff_delay,
    retry_with_backoff,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def fresh_circuit_breaker():
    """Create a fresh circuit breaker for each test."""
    return CircuitBreaker(
        name=f"test_circuit_{time.time()}",
        failure_threshold=3,
        success_threshold=2,
        timeout=1.0,  # Short timeout for testing
    )


@pytest.fixture
def mock_grok_client():
    """Create a mock Grok client."""
    client = AsyncMock()
    client.analyze_sentiment = AsyncMock(return_value={
        "score": 0.75,
        "label": "bullish",
        "confidence": 0.85,
    })
    client.is_available = True
    return client


@pytest.fixture
def mock_claude_client():
    """Create a mock Claude client."""
    client = AsyncMock()
    client.analyze = AsyncMock(return_value={
        "score": 0.65,
        "label": "bullish",
        "confidence": 0.80,
    })
    client.is_available = True
    return client


@pytest.fixture
def mock_template_fallback():
    """Create a mock template fallback."""
    def template_analyze(text: str) -> Dict[str, Any]:
        # Simple rule-based fallback
        bullish_words = ["moon", "pump", "bullish", "buy", "up"]
        bearish_words = ["dump", "crash", "bearish", "sell", "down"]

        text_lower = text.lower()
        bullish_count = sum(1 for w in bullish_words if w in text_lower)
        bearish_count = sum(1 for w in bearish_words if w in text_lower)

        if bullish_count > bearish_count:
            return {"score": 0.6, "label": "bullish", "confidence": 0.5}
        elif bearish_count > bullish_count:
            return {"score": -0.6, "label": "bearish", "confidence": 0.5}
        return {"score": 0.0, "label": "neutral", "confidence": 0.3}

    return template_analyze


# =============================================================================
# Circuit Breaker Tests
# =============================================================================

class TestCircuitBreakerBehavior:
    """Tests for circuit breaker state machine."""

    def test_circuit_starts_closed(self, fresh_circuit_breaker):
        """Circuit breaker should start in closed state."""
        cb = fresh_circuit_breaker
        assert cb.state == CircuitState.CLOSED
        assert cb.allow_request() is True

    def test_circuit_opens_after_failures(self, fresh_circuit_breaker):
        """Circuit should open after failure threshold is reached."""
        cb = fresh_circuit_breaker

        # Record failures up to threshold
        for i in range(3):
            cb.record_failure()

        assert cb.state == CircuitState.OPEN
        assert cb.allow_request() is False

    def test_circuit_rejects_when_open(self, fresh_circuit_breaker):
        """Open circuit should reject requests."""
        cb = fresh_circuit_breaker

        # Force open
        cb.force_open()

        assert cb.state == CircuitState.OPEN
        assert cb.allow_request() is False
        assert cb.stats.rejected_calls == 1

    def test_circuit_transitions_to_half_open(self, fresh_circuit_breaker):
        """Circuit should transition to half-open after timeout."""
        cb = fresh_circuit_breaker

        # Open the circuit
        for i in range(3):
            cb.record_failure()

        assert cb.state == CircuitState.OPEN

        # Wait for timeout
        time.sleep(1.2)  # > timeout

        # Accessing state triggers timeout check
        assert cb.state == CircuitState.HALF_OPEN

    def test_circuit_closes_after_successes(self, fresh_circuit_breaker):
        """Circuit should close after success threshold in half-open."""
        cb = fresh_circuit_breaker

        # Open and wait for half-open
        for i in range(3):
            cb.record_failure()
        time.sleep(1.2)

        # Verify half-open
        assert cb.state == CircuitState.HALF_OPEN

        # Record successes
        cb.record_success()
        cb.record_success()

        assert cb.state == CircuitState.CLOSED

    def test_circuit_reopens_on_half_open_failure(self, fresh_circuit_breaker):
        """Circuit should reopen on failure during half-open."""
        cb = fresh_circuit_breaker

        # Open and wait for half-open
        for i in range(3):
            cb.record_failure()
        time.sleep(1.2)

        assert cb.state == CircuitState.HALF_OPEN

        # Failure in half-open
        cb.record_failure()

        assert cb.state == CircuitState.OPEN

    def test_circuit_stats_tracking(self, fresh_circuit_breaker):
        """Circuit should track stats correctly."""
        cb = fresh_circuit_breaker

        # Mix of successes and failures
        cb.record_success()
        cb.record_success()
        cb.record_failure()
        cb.record_success()

        stats = cb.stats
        assert stats.total_calls == 4
        assert stats.successful_calls == 3
        assert stats.failed_calls == 1
        assert stats.failure_rate == 0.25


class TestCircuitBreakerWithExceptions:
    """Tests for circuit breaker with exception handling."""

    def test_excluded_exceptions_not_counted(self):
        """Excluded exceptions should not count toward failures."""
        cb = CircuitBreaker(
            name="test_excluded",
            failure_threshold=2,
            excluded_exceptions=[ValueError],
        )

        # Record excluded exception
        cb.record_failure(ValueError("excluded"))
        cb.record_failure(ValueError("also excluded"))

        # Should still be closed
        assert cb.state == CircuitState.CLOSED

        # Now record non-excluded
        cb.record_failure(TypeError("not excluded"))
        cb.record_failure(TypeError("still not excluded"))

        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_circuit_call_success(self, fresh_circuit_breaker):
        """Successful async call through circuit."""
        cb = fresh_circuit_breaker

        async def success_func():
            return "success"

        result = await cb.call(success_func)
        assert result == "success"
        assert cb.stats.successful_calls == 1

    @pytest.mark.asyncio
    async def test_circuit_call_failure(self, fresh_circuit_breaker):
        """Failed async call through circuit."""
        cb = fresh_circuit_breaker

        async def fail_func():
            raise RuntimeError("test error")

        with pytest.raises(RuntimeError):
            await cb.call(fail_func)

        assert cb.stats.failed_calls == 1


# =============================================================================
# Fallback Chain Tests
# =============================================================================

class TestFallbackChain:
    """Tests for API fallback chains."""

    @pytest.mark.asyncio
    async def test_primary_success_no_fallback(
        self,
        mock_grok_client,
        mock_claude_client,
        mock_template_fallback,
    ):
        """When primary succeeds, no fallback should be used."""
        # Simulate fallback chain
        result = None
        fallback_used = None

        try:
            result = await mock_grok_client.analyze_sentiment("bullish tweet")
            fallback_used = "grok"
        except Exception:
            try:
                result = await mock_claude_client.analyze("bullish tweet")
                fallback_used = "claude"
            except Exception:
                result = mock_template_fallback("bullish tweet")
                fallback_used = "template"

        assert fallback_used == "grok"
        assert result["score"] == 0.75

    @pytest.mark.asyncio
    async def test_fallback_to_claude_on_grok_failure(
        self,
        mock_grok_client,
        mock_claude_client,
        mock_template_fallback,
    ):
        """Should fallback to Claude when Grok fails."""
        # Configure Grok to fail
        mock_grok_client.analyze_sentiment = AsyncMock(
            side_effect=ConnectionError("Grok unavailable")
        )

        result = None
        fallback_used = None

        try:
            result = await mock_grok_client.analyze_sentiment("bullish tweet")
            fallback_used = "grok"
        except Exception:
            try:
                result = await mock_claude_client.analyze("bullish tweet")
                fallback_used = "claude"
            except Exception:
                result = mock_template_fallback("bullish tweet")
                fallback_used = "template"

        assert fallback_used == "claude"
        assert result["score"] == 0.65

    @pytest.mark.asyncio
    async def test_fallback_to_template_on_all_failures(
        self,
        mock_grok_client,
        mock_claude_client,
        mock_template_fallback,
    ):
        """Should fallback to template when both Grok and Claude fail."""
        # Configure both to fail
        mock_grok_client.analyze_sentiment = AsyncMock(
            side_effect=ConnectionError("Grok unavailable")
        )
        mock_claude_client.analyze = AsyncMock(
            side_effect=ConnectionError("Claude unavailable")
        )

        result = None
        fallback_used = None

        try:
            result = await mock_grok_client.analyze_sentiment("bullish moon pump")
            fallback_used = "grok"
        except Exception:
            try:
                result = await mock_claude_client.analyze("bullish moon pump")
                fallback_used = "claude"
            except Exception:
                result = mock_template_fallback("bullish moon pump")
                fallback_used = "template"

        assert fallback_used == "template"
        assert result["label"] == "bullish"
        assert result["confidence"] == 0.5  # Lower confidence for template


# =============================================================================
# Rate Limit Handling Tests
# =============================================================================

class TestRateLimitHandling:
    """Tests for rate limit handling."""

    @pytest.mark.asyncio
    async def test_backoff_delay_calculation(self):
        """Backoff delay should increase exponentially."""
        config = BackoffConfig(
            base_delay=1.0,
            max_delay=30.0,
            exponential_base=2.0,
            jitter=False,
        )

        delays = [calculate_backoff_delay(i, config) for i in range(5)]

        assert delays[0] == 1.0
        assert delays[1] == 2.0
        assert delays[2] == 4.0
        assert delays[3] == 8.0
        assert delays[4] == 16.0

    @pytest.mark.asyncio
    async def test_backoff_respects_max_delay(self):
        """Backoff should not exceed max delay."""
        config = BackoffConfig(
            base_delay=1.0,
            max_delay=10.0,
            exponential_base=2.0,
            jitter=False,
        )

        # After many attempts, delay should cap
        delay = calculate_backoff_delay(10, config)  # 2^10 = 1024
        assert delay == 10.0

    @pytest.mark.asyncio
    async def test_retry_succeeds_after_transient_failure(self):
        """Retry should succeed after transient failures."""
        call_count = 0

        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Transient failure")
            return "success"

        config = BackoffConfig(
            base_delay=0.01,  # Very short for testing
            max_retries=3,
        )

        result = await retry_with_backoff(flaky_func, config=config)

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_exhausts_on_persistent_failure(self):
        """Retry should raise after max retries on persistent failure."""
        call_count = 0

        async def always_fail():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Persistent failure")

        config = BackoffConfig(
            base_delay=0.01,
            max_retries=2,
        )

        with pytest.raises(ConnectionError):
            await retry_with_backoff(always_fail, config=config)

        assert call_count == 3  # Initial + 2 retries


# =============================================================================
# Timeout Scenario Tests
# =============================================================================

class TestTimeoutScenarios:
    """Tests for timeout handling."""

    @pytest.mark.asyncio
    async def test_timeout_triggers_fallback(self):
        """Timeout should trigger fallback behavior."""
        async def slow_func():
            await asyncio.sleep(2.0)  # Slow
            return "slow result"

        try:
            result = await asyncio.wait_for(slow_func(), timeout=0.1)
        except asyncio.TimeoutError:
            result = "fallback result"

        assert result == "fallback result"

    @pytest.mark.asyncio
    async def test_timeout_with_circuit_breaker(self, fresh_circuit_breaker):
        """Timeout should count as circuit breaker failure."""
        cb = fresh_circuit_breaker

        async def slow_func():
            await asyncio.sleep(1.0)
            return "result"

        for i in range(3):
            try:
                result = await asyncio.wait_for(slow_func(), timeout=0.01)
            except asyncio.TimeoutError:
                cb.record_failure()

        assert cb.state == CircuitState.OPEN


# =============================================================================
# Degraded Operation Tests
# =============================================================================

class TestDegradedOperation:
    """Tests for degraded operation modes."""

    @pytest.mark.asyncio
    async def test_degraded_mode_uses_cache(self):
        """Degraded mode should use cached values."""
        cache = {"SOL": {"score": 0.7, "timestamp": datetime.now(timezone.utc)}}

        async def get_sentiment(symbol: str, use_cache: bool = False):
            if use_cache and symbol in cache:
                cached = cache[symbol]
                age = (datetime.now(timezone.utc) - cached["timestamp"]).seconds
                if age < 300:  # 5 minute cache
                    return {"score": cached["score"], "from_cache": True}
            raise ConnectionError("API unavailable")

        # Without cache
        with pytest.raises(ConnectionError):
            await get_sentiment("SOL", use_cache=False)

        # With cache
        result = await get_sentiment("SOL", use_cache=True)
        assert result["from_cache"] is True
        assert result["score"] == 0.7

    @pytest.mark.asyncio
    async def test_degraded_mode_reduces_frequency(self):
        """Degraded mode should reduce request frequency."""
        request_count = 0
        last_request_time = None
        min_interval = 1.0  # Minimum 1 second between requests in degraded mode

        async def rate_limited_request():
            nonlocal request_count, last_request_time
            now = time.time()

            if last_request_time is not None:
                elapsed = now - last_request_time
                if elapsed < min_interval:
                    raise RuntimeError(f"Request too soon: {elapsed:.2f}s")

            last_request_time = now
            request_count += 1
            return "result"

        # First request should succeed
        result1 = await rate_limited_request()
        assert result1 == "result"

        # Immediate second request should fail
        with pytest.raises(RuntimeError, match="Request too soon"):
            await rate_limited_request()

        # After waiting, should succeed
        await asyncio.sleep(1.1)
        result2 = await rate_limited_request()
        assert result2 == "result"


# =============================================================================
# Circuit Breaker Recovery Tests
# =============================================================================

class TestCircuitBreakerRecovery:
    """Tests for circuit breaker recovery behavior."""

    @pytest.mark.asyncio
    async def test_gradual_recovery_in_half_open(self):
        """Recovery should be gradual with limited requests in half-open."""
        cb = CircuitBreaker(
            name="test_recovery",
            failure_threshold=3,
            success_threshold=3,  # Need 3 successes
            timeout=0.1,
        )

        # Open the circuit
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Wait for half-open
        await asyncio.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

        # Partial recovery (2 successes)
        cb.record_success()
        cb.record_success()
        assert cb.state == CircuitState.HALF_OPEN  # Not yet closed

        # Final success
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_reset_restores_clean_state(self, fresh_circuit_breaker):
        """Reset should restore circuit to clean state."""
        cb = fresh_circuit_breaker

        # Accumulate some state
        cb.record_success()
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()

        assert cb.state == CircuitState.OPEN
        assert cb.stats.total_calls == 4

        # Reset
        cb.reset()

        assert cb.state == CircuitState.CLOSED
        assert cb.stats.total_calls == 0
        assert cb.stats.failed_calls == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
