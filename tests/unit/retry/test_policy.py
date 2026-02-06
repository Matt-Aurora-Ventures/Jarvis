"""
Tests for core/retry/policy.py

Tests the RetryPolicy class with various backoff strategies and jitter.
"""

import pytest
from unittest.mock import patch


class TestBackoffStrategy:
    """Tests for backoff strategy enumeration."""

    def test_backoff_strategies_exist(self):
        """All required backoff strategies should be defined."""
        from core.retry.policy import BackoffStrategy

        assert hasattr(BackoffStrategy, 'FIXED')
        assert hasattr(BackoffStrategy, 'LINEAR')
        assert hasattr(BackoffStrategy, 'EXPONENTIAL')

    def test_backoff_strategy_values(self):
        """Backoff strategies should have string values."""
        from core.retry.policy import BackoffStrategy

        assert BackoffStrategy.FIXED.value == "fixed"
        assert BackoffStrategy.LINEAR.value == "linear"
        assert BackoffStrategy.EXPONENTIAL.value == "exponential"


class TestRetryPolicy:
    """Tests for RetryPolicy class."""

    def test_default_initialization(self):
        """Policy should have sensible defaults."""
        from core.retry.policy import RetryPolicy

        policy = RetryPolicy()

        assert policy.max_retries == 3
        assert policy.base_delay == 1.0
        assert policy.max_delay == 60.0
        assert policy.jitter is True

    def test_custom_initialization(self):
        """Policy should accept custom parameters."""
        from core.retry.policy import RetryPolicy, BackoffStrategy

        policy = RetryPolicy(
            max_retries=5,
            base_delay=0.5,
            max_delay=30.0,
            backoff=BackoffStrategy.LINEAR,
            jitter=False
        )

        assert policy.max_retries == 5
        assert policy.base_delay == 0.5
        assert policy.max_delay == 30.0
        assert policy.backoff == BackoffStrategy.LINEAR
        assert policy.jitter is False

    def test_fixed_backoff_delay(self):
        """Fixed backoff should return same delay for all attempts."""
        from core.retry.policy import RetryPolicy, BackoffStrategy

        policy = RetryPolicy(
            base_delay=2.0,
            backoff=BackoffStrategy.FIXED,
            jitter=False
        )

        assert policy.get_delay(1) == 2.0
        assert policy.get_delay(2) == 2.0
        assert policy.get_delay(3) == 2.0
        assert policy.get_delay(10) == 2.0

    def test_linear_backoff_delay(self):
        """Linear backoff should increase delay linearly with attempt number."""
        from core.retry.policy import RetryPolicy, BackoffStrategy

        policy = RetryPolicy(
            base_delay=1.0,
            backoff=BackoffStrategy.LINEAR,
            jitter=False
        )

        assert policy.get_delay(1) == 1.0
        assert policy.get_delay(2) == 2.0
        assert policy.get_delay(3) == 3.0
        assert policy.get_delay(4) == 4.0

    def test_exponential_backoff_delay(self):
        """Exponential backoff should double delay each attempt."""
        from core.retry.policy import RetryPolicy, BackoffStrategy

        policy = RetryPolicy(
            base_delay=1.0,
            backoff=BackoffStrategy.EXPONENTIAL,
            jitter=False
        )

        assert policy.get_delay(1) == 1.0
        assert policy.get_delay(2) == 2.0
        assert policy.get_delay(3) == 4.0
        assert policy.get_delay(4) == 8.0

    def test_max_delay_cap(self):
        """Delay should never exceed max_delay."""
        from core.retry.policy import RetryPolicy, BackoffStrategy

        policy = RetryPolicy(
            base_delay=1.0,
            max_delay=5.0,
            backoff=BackoffStrategy.EXPONENTIAL,
            jitter=False
        )

        assert policy.get_delay(10) == 5.0  # Would be 512 without cap

    def test_jitter_adds_randomness(self):
        """Jitter should add randomness to delay."""
        from core.retry.policy import RetryPolicy, BackoffStrategy

        policy = RetryPolicy(
            base_delay=10.0,
            backoff=BackoffStrategy.FIXED,
            jitter=True,
            jitter_factor=0.5
        )

        # Collect multiple delays - they should vary
        delays = [policy.get_delay(1) for _ in range(20)]

        # With jitter_factor=0.5 and base=10, delay should be in [5, 15]
        assert all(5.0 <= d <= 15.0 for d in delays)
        # They shouldn't all be the same
        assert len(set(delays)) > 1

    def test_jitter_disabled(self):
        """With jitter disabled, delays should be deterministic."""
        from core.retry.policy import RetryPolicy, BackoffStrategy

        policy = RetryPolicy(
            base_delay=10.0,
            backoff=BackoffStrategy.FIXED,
            jitter=False
        )

        delays = [policy.get_delay(1) for _ in range(10)]

        # All should be exactly the same
        assert all(d == 10.0 for d in delays)

    def test_should_retry_default(self):
        """By default, all exceptions should be retryable."""
        from core.retry.policy import RetryPolicy

        policy = RetryPolicy()

        assert policy.should_retry(ValueError("test"))
        assert policy.should_retry(RuntimeError("test"))
        assert policy.should_retry(ConnectionError("test"))

    def test_should_retry_specific_exceptions(self):
        """Should only retry specified exception types when configured."""
        from core.retry.policy import RetryPolicy

        policy = RetryPolicy(
            retryable_exceptions=[ConnectionError, TimeoutError]
        )

        assert policy.should_retry(ConnectionError("test"))
        assert policy.should_retry(TimeoutError("test"))
        assert not policy.should_retry(ValueError("test"))

    def test_non_retryable_exceptions(self):
        """Non-retryable exceptions should never trigger retry."""
        from core.retry.policy import RetryPolicy

        policy = RetryPolicy(
            non_retryable_exceptions=[KeyboardInterrupt, SystemExit, ValueError]
        )

        assert not policy.should_retry(ValueError("test"))
        assert policy.should_retry(RuntimeError("test"))

    def test_non_retryable_takes_precedence(self):
        """Non-retryable should take precedence over retryable."""
        from core.retry.policy import RetryPolicy

        policy = RetryPolicy(
            retryable_exceptions=[Exception],
            non_retryable_exceptions=[ValueError]
        )

        # ValueError is in non-retryable, so should not retry
        assert not policy.should_retry(ValueError("test"))

    def test_policy_immutability(self):
        """Policy should be immutable (dataclass frozen)."""
        from core.retry.policy import RetryPolicy

        policy = RetryPolicy()

        with pytest.raises((AttributeError, TypeError)):
            policy.max_retries = 10

    def test_custom_exponential_base(self):
        """Should support custom exponential base."""
        from core.retry.policy import RetryPolicy, BackoffStrategy

        policy = RetryPolicy(
            base_delay=1.0,
            backoff=BackoffStrategy.EXPONENTIAL,
            exponential_base=3.0,
            jitter=False
        )

        assert policy.get_delay(1) == 1.0
        assert policy.get_delay(2) == 3.0
        assert policy.get_delay(3) == 9.0


class TestPresetPolicies:
    """Tests for preset retry policies."""

    def test_aggressive_retry_policy(self):
        """Aggressive policy should have more retries and shorter delays."""
        from core.retry.policy import AGGRESSIVE_RETRY

        assert AGGRESSIVE_RETRY.max_retries >= 5
        assert AGGRESSIVE_RETRY.base_delay <= 1.0

    def test_conservative_retry_policy(self):
        """Conservative policy should have fewer retries and longer delays."""
        from core.retry.policy import CONSERVATIVE_RETRY

        assert CONSERVATIVE_RETRY.max_retries <= 3
        assert CONSERVATIVE_RETRY.base_delay >= 2.0

    def test_api_retry_policy(self):
        """API policy should be configured for typical HTTP calls."""
        from core.retry.policy import API_RETRY

        assert API_RETRY.max_retries >= 3
        assert ConnectionError in API_RETRY.retryable_exceptions or Exception in API_RETRY.retryable_exceptions

    def test_rpc_retry_policy(self):
        """RPC policy should handle network-level errors."""
        from core.retry.policy import RPC_RETRY

        assert RPC_RETRY.jitter is True  # Prevent thundering herd
