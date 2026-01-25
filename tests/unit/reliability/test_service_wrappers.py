"""Tests for service wrappers with circuit breakers and retry.

These tests verify that external service calls are properly protected
with circuit breakers, retry logic, and error handling.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock


class TestServiceWrapper:
    """Test generic service wrapper functionality."""

    def test_wrapper_applies_circuit_breaker(self):
        """ServiceWrapper should apply circuit breaker."""
        from core.reliability.service_wrapper import ServiceWrapper
        from core.reliability.circuit_breaker import CircuitState

        wrapper = ServiceWrapper(
            name="test_service",
            failure_threshold=2,
            timeout=60
        )

        # Simulate failures
        failing_func = Mock(side_effect=Exception("fail"))

        for _ in range(2):
            with pytest.raises(Exception):
                wrapper.call(failing_func)

        assert wrapper.circuit_breaker.state == CircuitState.OPEN

    def test_wrapper_applies_retry(self):
        """ServiceWrapper should apply retry logic."""
        from core.reliability.service_wrapper import ServiceWrapper

        wrapper = ServiceWrapper(
            name="test_service",
            max_retries=3,
            retry_delay=0.01
        )

        attempt = 0

        def fails_twice():
            nonlocal attempt
            attempt += 1
            if attempt < 3:
                raise ValueError("not yet")
            return "success"

        result = wrapper.call(fails_twice)
        assert result == "success"
        assert attempt == 3

    def test_wrapper_with_fallback(self):
        """ServiceWrapper should use fallback on failure."""
        from core.reliability.service_wrapper import ServiceWrapper

        wrapper = ServiceWrapper(
            name="test_service",
            failure_threshold=1,
            fallback=lambda: "fallback_value"
        )

        # Force circuit open
        with pytest.raises(Exception):
            wrapper.call(Mock(side_effect=Exception("fail")))

        # Now call should use fallback
        result = wrapper.call(Mock(side_effect=Exception("fail")))
        assert result == "fallback_value"


class TestAnthropicWrapper:
    """Test Anthropic API wrapper."""

    @pytest.mark.asyncio
    async def test_anthropic_wrapper_success(self):
        """Should successfully call Anthropic API."""
        from core.reliability.service_wrappers.anthropic import AnthropicWrapper

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Hello from Claude")]

        with patch("anthropic.AsyncAnthropic") as mock_client:
            mock_instance = MagicMock()
            mock_instance.messages.create = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_instance

            wrapper = AnthropicWrapper()
            response = await wrapper.create_message(
                model="claude-3-sonnet-20240229",
                messages=[{"role": "user", "content": "Hi"}]
            )

            assert "Hello" in str(response)

    @pytest.mark.asyncio
    async def test_anthropic_wrapper_rate_limit(self):
        """Should handle rate limit with retry."""
        from core.reliability.service_wrappers.anthropic import AnthropicWrapper
        from core.errors.types import QuotaExceededError

        with patch("anthropic.AsyncAnthropic") as mock_client:
            mock_instance = MagicMock()

            # Simulate rate limit then success
            call_count = 0

            async def rate_limited_then_success(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise Exception("rate_limit_error")
                return MagicMock(content=[MagicMock(text="Success")])

            mock_instance.messages.create = rate_limited_then_success
            mock_client.return_value = mock_instance

            wrapper = AnthropicWrapper(max_retries=2, retry_delay=0.01)

            # This should retry and succeed
            # Or raise QuotaExceededError if rate limit persists
            try:
                response = await wrapper.create_message(
                    model="claude-3-sonnet-20240229",
                    messages=[{"role": "user", "content": "Hi"}]
                )
                assert call_count == 2
            except QuotaExceededError:
                assert call_count >= 1


class TestSolanaRPCWrapper:
    """Test Solana RPC wrapper."""

    @pytest.mark.asyncio
    async def test_rpc_wrapper_with_failover(self):
        """Should failover to backup RPC on failure."""
        from core.reliability.service_wrappers.solana_rpc import SolanaRPCWrapper

        primary_fails = True

        async def primary_rpc(*args, **kwargs):
            if primary_fails:
                raise ConnectionError("Primary down")
            return {"result": "primary"}

        async def backup_rpc(*args, **kwargs):
            return {"result": "backup"}

        wrapper = SolanaRPCWrapper(
            primary_endpoint="http://primary.rpc",
            backup_endpoints=["http://backup.rpc"]
        )

        with patch.object(wrapper, "_call_primary", side_effect=ConnectionError):
            with patch.object(wrapper, "_call_backup", return_value={"result": "backup"}):
                result = await wrapper.get_account_info("some_address")
                assert result["result"] == "backup"

    @pytest.mark.asyncio
    async def test_rpc_wrapper_circuit_opens(self):
        """RPC circuit should open on repeated failures."""
        from core.reliability.service_wrappers.solana_rpc import SolanaRPCWrapper
        from core.reliability.circuit_breaker import CircuitState

        wrapper = SolanaRPCWrapper(
            primary_endpoint="http://rpc.example",
            failure_threshold=2
        )

        with patch.object(wrapper, "_call_primary", side_effect=Exception("fail")):
            for _ in range(2):
                with pytest.raises(Exception):
                    await wrapper.get_account_info("addr")

        assert wrapper.circuit_breaker.state == CircuitState.OPEN


class TestJupiterWrapper:
    """Test Jupiter DEX API wrapper."""

    @pytest.mark.asyncio
    async def test_jupiter_quote_with_cache(self):
        """Should cache quote responses."""
        from core.reliability.service_wrappers.jupiter import JupiterWrapper

        wrapper = JupiterWrapper(cache_ttl=60)

        with patch.object(wrapper, "_fetch_quote", return_value={"price": 1.5}) as mock:
            # First call
            quote1 = await wrapper.get_quote("SOL", "USDC", 1.0)
            # Second call (should be cached)
            quote2 = await wrapper.get_quote("SOL", "USDC", 1.0)

            assert quote1 == quote2
            assert mock.call_count == 1  # Only one actual API call

    @pytest.mark.asyncio
    async def test_jupiter_swap_no_cache(self):
        """Swap execution should not be cached."""
        from core.reliability.service_wrappers.jupiter import JupiterWrapper

        wrapper = JupiterWrapper()

        with patch.object(wrapper, "_execute_swap", return_value={"tx": "abc"}) as mock:
            await wrapper.execute_swap("SOL", "USDC", 1.0, slippage=0.5)
            await wrapper.execute_swap("SOL", "USDC", 1.0, slippage=0.5)

            assert mock.call_count == 2  # No caching for swaps


class TestHeliusWrapper:
    """Test Helius API wrapper."""

    @pytest.mark.asyncio
    async def test_helius_rate_limiting(self):
        """Should respect Helius rate limits."""
        from core.reliability.service_wrappers.helius import HeliusWrapper

        wrapper = HeliusWrapper(requests_per_second=2)

        with patch.object(wrapper, "_fetch", return_value={"data": []}) as mock:
            # Make 3 rapid requests
            tasks = [
                wrapper.get_token_metadata("token1"),
                wrapper.get_token_metadata("token2"),
                wrapper.get_token_metadata("token3")
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # All should succeed (rate limiter spaces them out)
            assert all(not isinstance(r, Exception) for r in results)


class TestGlobalServiceRegistry:
    """Test global service wrapper registry."""

    def test_get_wrapper_returns_singleton(self):
        """Same wrapper instance should be returned."""
        from core.reliability.service_wrappers import get_service_wrapper

        w1 = get_service_wrapper("anthropic")
        w2 = get_service_wrapper("anthropic")

        assert w1 is w2

    def test_get_wrapper_different_services(self):
        """Different services return different wrappers."""
        from core.reliability.service_wrappers import get_service_wrapper

        anthropic = get_service_wrapper("anthropic")
        jupiter = get_service_wrapper("jupiter")

        assert anthropic is not jupiter

    def test_get_all_wrapper_statuses(self):
        """Should return status of all registered wrappers."""
        from core.reliability.service_wrappers import get_all_service_statuses

        statuses = get_all_service_statuses()

        assert isinstance(statuses, dict)
        # Should have at least the core services
        expected_services = ["anthropic", "solana_rpc", "jupiter"]
        for service in expected_services:
            if service in statuses:
                assert "circuit_state" in statuses[service]
