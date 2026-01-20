"""Tests for retry logic in external API integrations."""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from aiohttp import ClientError, ClientResponseError
import asyncio

from core.resilience.retry import (
    retry,
    RetryPolicy,
    RetryExhausted,
    JUPITER_QUOTE_RETRY,
    JUPITER_SWAP_RETRY,
    BIRDEYE_API_RETRY,
    TWITTER_API_RETRY,
    SOLANA_RPC_RETRY,
)


class TestRetryPolicies:
    """Test that retry policies are configured correctly."""

    def test_jupiter_quote_retry_policy(self):
        """Jupiter quote retry should be fast and limited."""
        assert JUPITER_QUOTE_RETRY.max_attempts == 3
        assert JUPITER_QUOTE_RETRY.base_delay == 0.5
        assert JUPITER_QUOTE_RETRY.max_delay == 10.0

    def test_jupiter_swap_retry_policy(self):
        """Jupiter swap retry should be more aggressive."""
        assert JUPITER_SWAP_RETRY.max_attempts == 5
        assert JUPITER_SWAP_RETRY.base_delay == 1.0
        assert JUPITER_SWAP_RETRY.max_delay == 30.0
        assert JUPITER_SWAP_RETRY.exponential_base == 2.5

    def test_birdeye_retry_policy(self):
        """Birdeye should have jitter enabled."""
        assert BIRDEYE_API_RETRY.jitter is True
        assert BIRDEYE_API_RETRY.max_attempts == 3

    def test_twitter_retry_policy(self):
        """Twitter should have longer delays."""
        assert TWITTER_API_RETRY.base_delay == 2.0
        assert TWITTER_API_RETRY.max_delay == 30.0

    def test_solana_rpc_retry_policy(self):
        """Solana RPC should have many retries with jitter."""
        assert SOLANA_RPC_RETRY.max_attempts == 5
        assert SOLANA_RPC_RETRY.jitter is True


@pytest.mark.asyncio
class TestRetryDecorator:
    """Test retry decorator behavior."""

    async def test_retry_on_connection_error(self):
        """Should retry on ConnectionError."""
        call_count = 0

        @retry(policy=JUPITER_QUOTE_RETRY)
        async def failing_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Network error")
            return "success"

        result = await failing_function()
        assert result == "success"
        assert call_count == 3

    async def test_retry_exhausted(self):
        """Should raise RetryExhausted after max attempts."""
        call_count = 0

        @retry(policy=RetryPolicy(max_attempts=3, base_delay=0.01))
        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Always fails")

        with pytest.raises(RetryExhausted):
            await always_fails()

        assert call_count == 3

    async def test_no_retry_on_non_retryable_exception(self):
        """Should not retry on non-retryable exceptions."""
        call_count = 0

        @retry(policy=RetryPolicy(
            max_attempts=3,
            retryable_exceptions=[ConnectionError],
            non_retryable_exceptions=[ValueError]
        ))
        async def fails_with_value_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("Not retryable")

        with pytest.raises(ValueError):
            await fails_with_value_error()

        assert call_count == 1  # Should fail immediately

    async def test_exponential_backoff_timing(self):
        """Should use exponential backoff between retries."""
        import time
        call_times = []

        @retry(policy=RetryPolicy(max_attempts=3, base_delay=0.1, exponential_base=2.0, jitter=False))
        async def fails_twice():
            call_times.append(time.time())
            if len(call_times) < 3:
                raise ConnectionError("Fail")
            return "success"

        await fails_twice()

        # Check delays (roughly 0.1s, then 0.2s)
        assert len(call_times) == 3
        delay1 = call_times[1] - call_times[0]
        delay2 = call_times[2] - call_times[1]

        # Allow more tolerance for system delays
        assert 0.08 < delay1 < 0.25
        assert 0.15 < delay2 < 0.35


@pytest.mark.asyncio
class TestJupiterRetryIntegration:
    """Test Jupiter integration with retry logic."""

    async def test_jupiter_has_retry_decorators(self):
        """Jupiter methods should have retry decorators applied."""
        from bots.treasury.jupiter import JupiterClient
        import inspect

        client = JupiterClient()

        # Check that get_quote has retry wrapper
        # The decorator wraps the function, so we check for wrapper attributes
        assert hasattr(client.get_quote, '__wrapped__') or 'retry' in str(type(client.get_quote))

        # Check that get_swap_transaction has retry wrapper
        assert hasattr(client.get_swap_transaction, '__wrapped__') or 'retry' in str(type(client.get_swap_transaction))

    async def test_retry_policy_imports(self):
        """Verify retry policies are importable from jupiter module."""
        # This test verifies that the imports don't fail
        try:
            from bots.treasury.jupiter import retry, JUPITER_QUOTE_RETRY, JUPITER_SWAP_RETRY
            assert JUPITER_QUOTE_RETRY is not None
            assert JUPITER_SWAP_RETRY is not None
            assert retry is not None
        except ImportError as e:
            pytest.fail(f"Failed to import retry from jupiter: {e}")


class TestBirdeyeRetryIntegration:
    """Test Birdeye integration maintains retry on migration."""

    def test_birdeye_has_retry_in_get_json(self):
        """Birdeye _get_json should have retry logic."""
        from core.birdeye import _get_json

        # Check function signature has retries parameter
        import inspect
        sig = inspect.signature(_get_json)
        assert 'retries' in sig.parameters
        assert sig.parameters['retries'].default == 3


class TestRetryStatistics:
    """Test retry statistics and logging."""

    @pytest.mark.asyncio
    async def test_retry_logs_attempts(self, caplog):
        """Should log retry attempts."""
        import logging
        caplog.set_level(logging.WARNING)

        @retry(policy=RetryPolicy(max_attempts=2, base_delay=0.01))
        async def fails_once():
            if not hasattr(fails_once, 'called'):
                fails_once.called = True
                raise ConnectionError("First fail")
            return "success"

        await fails_once()

        # Should have logged the retry
        assert any("Retry 1/2" in record.message for record in caplog.records)


@pytest.mark.asyncio
class TestRetryPolicyConfiguration:
    """Test custom retry policy configuration."""

    async def test_custom_retry_policy(self):
        """Should support custom retry configurations."""
        custom_policy = RetryPolicy(
            max_attempts=5,
            base_delay=0.5,
            max_delay=10.0,
            jitter=True,
            retryable_exceptions=[TimeoutError, ConnectionError]
        )

        call_count = 0

        @retry(policy=custom_policy)
        async def custom_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise TimeoutError("Timeout")
            return "success"

        result = await custom_function()
        assert result == "success"
        assert call_count == 3

    async def test_override_max_attempts(self):
        """Should allow overriding max_attempts."""
        call_count = 0

        @retry(max_attempts=5, base_delay=0.01)
        async def needs_many_retries():
            nonlocal call_count
            call_count += 1
            if call_count < 4:
                raise ConnectionError("Keep failing")
            return "success"

        result = await needs_many_retries()
        assert result == "success"
        assert call_count == 4
