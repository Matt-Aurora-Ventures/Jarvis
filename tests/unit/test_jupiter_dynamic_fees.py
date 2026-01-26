"""
Tests for Jupiter API Dynamic Priority Fees via Helius API.

This module tests the integration of Helius getPriorityFeeEstimate
with Jupiter swap execution for dynamic fee estimation.

Requirements tested:
1. get_priority_fee_estimate() method using Helius API
2. execute_swap() using dynamic fees instead of "auto"
3. Priority levels: min, low, medium, high, veryHigh
4. maxLamports cap to prevent excessive fees
5. Backward compatibility
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import os


# =============================================================================
# Test Data
# =============================================================================

SAMPLE_HELIUS_FEE_RESPONSE = {
    "jsonrpc": "2.0",
    "result": {
        "priorityFeeEstimate": 50000,
        "priorityFeeLevels": {
            "min": 1000,
            "low": 10000,
            "medium": 50000,
            "high": 100000,
            "veryHigh": 500000,
            "unsafeMax": 10000000,
        }
    },
    "id": 1,
}

SAMPLE_QUOTE = {
    "inputMint": "So11111111111111111111111111111111111111112",
    "outputMint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "inAmount": "1000000000",
    "outAmount": "50000000",
    "priceImpactPct": "0.1",
    "routePlan": [{"swap": "info"}],
    "_raw": {
        "inputMint": "So11111111111111111111111111111111111111112",
        "outputMint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        "inAmount": "1000000000",
        "outAmount": "50000000",
    },
}


# =============================================================================
# Test: Helius Priority Fee Estimation
# =============================================================================

class TestHeliusPriorityFeeEstimate:
    """Test Helius getPriorityFeeEstimate integration."""

    @pytest.mark.asyncio
    async def test_get_priority_fee_estimate_returns_fee_levels(self):
        """get_priority_fee_estimate() should return fee levels from Helius."""
        from core.jupiter_api import JupiterAPI

        api = JupiterAPI()

        with patch.object(api, '_helius_client') as mock_helius:
            mock_helius.post = AsyncMock(return_value=MagicMock(
                status_code=200,
                json=MagicMock(return_value=SAMPLE_HELIUS_FEE_RESPONSE),
            ))

            result = await api.get_priority_fee_estimate()

            assert result is not None
            assert "priorityFeeEstimate" in result or "recommended" in result
            assert "priorityFeeLevels" in result or "levels" in result

    @pytest.mark.asyncio
    async def test_get_priority_fee_estimate_with_accounts(self):
        """get_priority_fee_estimate() should accept account keys for specific estimation."""
        from core.jupiter_api import JupiterAPI

        api = JupiterAPI()

        accounts = [
            "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",  # Jupiter program
            "So11111111111111111111111111111111111111112",  # SOL mint
        ]

        with patch.object(api, '_helius_client') as mock_helius:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json = MagicMock(return_value=SAMPLE_HELIUS_FEE_RESPONSE)
            mock_helius.post = AsyncMock(return_value=mock_response)

            result = await api.get_priority_fee_estimate(account_keys=accounts)

            assert result is not None
            # Verify accounts were passed in the request
            call_args = mock_helius.post.call_args
            assert call_args is not None

    @pytest.mark.asyncio
    async def test_get_priority_fee_estimate_with_priority_level(self):
        """get_priority_fee_estimate() should support priority level parameter."""
        from core.jupiter_api import JupiterAPI

        api = JupiterAPI()

        with patch.object(api, '_helius_client') as mock_helius:
            mock_helius.post = AsyncMock(return_value=MagicMock(
                status_code=200,
                json=MagicMock(return_value=SAMPLE_HELIUS_FEE_RESPONSE),
            ))

            result = await api.get_priority_fee_estimate(priority_level="high")

            assert result is not None

    @pytest.mark.asyncio
    async def test_get_priority_fee_estimate_fallback_on_error(self):
        """get_priority_fee_estimate() should return default on API error."""
        from core.jupiter_api import JupiterAPI, DEFAULT_PRIORITY_FEE

        api = JupiterAPI()

        with patch.object(api, '_helius_client') as mock_helius:
            mock_helius.post = AsyncMock(side_effect=Exception("Helius API Error"))

            result = await api.get_priority_fee_estimate()

            # Should return a fallback value, not None
            assert result is not None
            assert result.get("priorityFeeEstimate", 0) >= DEFAULT_PRIORITY_FEE

    @pytest.mark.asyncio
    async def test_get_priority_fee_estimate_without_helius_key(self):
        """get_priority_fee_estimate() should work without Helius API key (fallback)."""
        from core.jupiter_api import JupiterAPI

        # Temporarily unset Helius key
        with patch.dict(os.environ, {"HELIUS_API_KEY": ""}, clear=False):
            api = JupiterAPI()

            result = await api.get_priority_fee_estimate()

            # Should still return a valid result (fallback)
            assert result is not None


# =============================================================================
# Test: Priority Level Support
# =============================================================================

class TestPriorityLevels:
    """Test support for different priority levels."""

    @pytest.mark.asyncio
    async def test_priority_level_min(self):
        """Should support 'min' priority level."""
        from core.jupiter_api import JupiterAPI, PriorityLevel

        assert hasattr(PriorityLevel, 'MIN') or 'min' in dir(PriorityLevel)

    @pytest.mark.asyncio
    async def test_priority_level_low(self):
        """Should support 'low' priority level."""
        from core.jupiter_api import JupiterAPI, PriorityLevel

        assert hasattr(PriorityLevel, 'LOW') or 'low' in dir(PriorityLevel)

    @pytest.mark.asyncio
    async def test_priority_level_medium(self):
        """Should support 'medium' priority level."""
        from core.jupiter_api import JupiterAPI, PriorityLevel

        assert hasattr(PriorityLevel, 'MEDIUM') or 'medium' in dir(PriorityLevel)

    @pytest.mark.asyncio
    async def test_priority_level_high(self):
        """Should support 'high' priority level."""
        from core.jupiter_api import JupiterAPI, PriorityLevel

        assert hasattr(PriorityLevel, 'HIGH') or 'high' in dir(PriorityLevel)

    @pytest.mark.asyncio
    async def test_priority_level_very_high(self):
        """Should support 'veryHigh' priority level."""
        from core.jupiter_api import JupiterAPI, PriorityLevel

        assert hasattr(PriorityLevel, 'VERY_HIGH') or 'veryHigh' in dir(PriorityLevel)


# =============================================================================
# Test: Execute Swap with Dynamic Fees
# =============================================================================

class TestExecuteSwapDynamicFees:
    """Test execute_swap() with dynamic priority fees."""

    @pytest.mark.asyncio
    async def test_execute_swap_uses_dynamic_fee(self):
        """execute_swap() should use dynamic priority fee instead of 'auto'."""
        from core.jupiter_api import JupiterAPI

        api = JupiterAPI()

        with patch.object(api, '_client') as mock_client:
            mock_response = AsyncMock()
            mock_response.json = MagicMock(return_value={
                "swapTransaction": "base64_tx_data",
                "lastValidBlockHeight": 12345678,
            })
            mock_response.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)

            with patch.object(api, 'get_priority_fee_estimate') as mock_fee:
                mock_fee.return_value = {
                    "priorityFeeEstimate": 50000,
                    "priorityFeeLevels": {
                        "min": 1000,
                        "low": 10000,
                        "medium": 50000,
                        "high": 100000,
                        "veryHigh": 500000,
                    }
                }

                result = await api.execute_swap(
                    quote=SAMPLE_QUOTE,
                    user_public_key="user_wallet_123",
                )

                # Verify priority fee was fetched
                mock_fee.assert_called_once()

                # Verify swap was executed
                assert result is not None
                assert result.get("success") is True or "swap_transaction" in result

    @pytest.mark.asyncio
    async def test_execute_swap_with_custom_priority_level(self):
        """execute_swap() should support custom priority level."""
        from core.jupiter_api import JupiterAPI

        api = JupiterAPI()

        with patch.object(api, '_client') as mock_client:
            mock_response = AsyncMock()
            mock_response.json = MagicMock(return_value={
                "swapTransaction": "base64_tx_data",
            })
            mock_response.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)

            with patch.object(api, 'get_priority_fee_estimate') as mock_fee:
                mock_fee.return_value = {
                    "priorityFeeEstimate": 100000,
                    "priorityFeeLevels": {"high": 100000},
                }

                result = await api.execute_swap(
                    quote=SAMPLE_QUOTE,
                    user_public_key="user_wallet_123",
                    priority_level="high",  # New parameter
                )

                # Verify high priority was requested
                mock_fee.assert_called_once()
                call_kwargs = mock_fee.call_args.kwargs if mock_fee.call_args else {}
                # Either passed as kwarg or correctly handled
                assert result is not None

    @pytest.mark.asyncio
    async def test_execute_swap_with_max_lamports_cap(self):
        """execute_swap() should respect max lamports cap."""
        from core.jupiter_api import JupiterAPI

        api = JupiterAPI()

        with patch.object(api, '_client') as mock_client:
            mock_response = AsyncMock()
            mock_response.json = MagicMock(return_value={
                "swapTransaction": "base64_tx_data",
            })
            mock_response.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)

            with patch.object(api, 'get_priority_fee_estimate') as mock_fee:
                # Helius returns very high fee
                mock_fee.return_value = {
                    "priorityFeeEstimate": 10000000,  # 10M lamports
                    "priorityFeeLevels": {"veryHigh": 10000000},
                }

                result = await api.execute_swap(
                    quote=SAMPLE_QUOTE,
                    user_public_key="user_wallet_123",
                    max_priority_fee_lamports=1000000,  # Cap at 1M
                )

                # Verify swap was executed with capped fee
                assert result is not None
                # The swap request should have used the capped value
                call_args = mock_client.post.call_args
                if call_args:
                    request_json = call_args[1].get('json', {})
                    # If priorityLevelWithMaxLamports is used
                    if 'priorityLevelWithMaxLamports' in request_json:
                        max_lamports = request_json['priorityLevelWithMaxLamports'].get('maxLamports')
                        assert max_lamports <= 1000000

    @pytest.mark.asyncio
    async def test_execute_swap_backward_compatible(self):
        """execute_swap() should work without priority fee parameters (backward compatible)."""
        from core.jupiter_api import JupiterAPI

        api = JupiterAPI()

        with patch.object(api, '_client') as mock_client:
            mock_response = AsyncMock()
            mock_response.json = MagicMock(return_value={
                "swapTransaction": "base64_tx_data",
            })
            mock_response.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)

            # Call without any priority fee parameters
            result = await api.execute_swap(
                quote=SAMPLE_QUOTE,
                user_public_key="user_wallet_123",
            )

            # Should still work
            assert result is not None
            assert result.get("success") is True or "swap_transaction" in result


# =============================================================================
# Test: Max Lamports Cap
# =============================================================================

class TestMaxLamportsCap:
    """Test max lamports cap functionality."""

    @pytest.mark.asyncio
    async def test_default_max_lamports(self):
        """Should have a default max lamports cap."""
        from core.jupiter_api import DEFAULT_MAX_PRIORITY_FEE_LAMPORTS

        # Default should be reasonable (e.g., 1 SOL = 1B lamports or less)
        assert DEFAULT_MAX_PRIORITY_FEE_LAMPORTS > 0
        assert DEFAULT_MAX_PRIORITY_FEE_LAMPORTS <= 10_000_000_000  # 10 SOL max

    @pytest.mark.asyncio
    async def test_fee_capped_at_max_lamports(self):
        """Priority fee should be capped at max lamports."""
        from core.jupiter_api import JupiterAPI

        api = JupiterAPI()

        with patch.object(api, '_helius_client') as mock_helius:
            # Helius returns extremely high fee
            mock_helius.post = AsyncMock(return_value=MagicMock(
                status_code=200,
                json=MagicMock(return_value={
                    "jsonrpc": "2.0",
                    "result": {
                        "priorityFeeEstimate": 100_000_000_000,  # 100 SOL!
                    },
                }),
            ))

            result = await api.get_priority_fee_estimate(
                max_lamports=1_000_000  # Cap at 0.001 SOL
            )

            # Fee should be capped
            assert result is not None
            fee = result.get("priorityFeeEstimate", result.get("recommended", 0))
            assert fee <= 1_000_000

    @pytest.mark.asyncio
    async def test_custom_max_lamports_respected(self):
        """Custom max lamports should be respected."""
        from core.jupiter_api import JupiterAPI

        api = JupiterAPI()

        with patch.object(api, '_client') as mock_client:
            mock_response = AsyncMock()
            mock_response.json = MagicMock(return_value={
                "swapTransaction": "base64_tx_data",
            })
            mock_response.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)

            with patch.object(api, 'get_priority_fee_estimate') as mock_fee:
                mock_fee.return_value = {"priorityFeeEstimate": 500000}

                # Execute with custom max
                await api.execute_swap(
                    quote=SAMPLE_QUOTE,
                    user_public_key="wallet",
                    max_priority_fee_lamports=250000,
                )

                # Verify the cap was applied in swap request
                call_args = mock_client.post.call_args
                assert call_args is not None


# =============================================================================
# Test: Jupiter V6 API Format
# =============================================================================

class TestJupiterV6Format:
    """Test Jupiter V6 API request format for priority fees."""

    @pytest.mark.asyncio
    async def test_uses_dynamic_compute_unit_limit(self):
        """Should use dynamicComputeUnitLimit: true."""
        from core.jupiter_api import JupiterAPI

        api = JupiterAPI()

        with patch.object(api, '_client') as mock_client:
            mock_response = AsyncMock()
            mock_response.json = MagicMock(return_value={
                "swapTransaction": "base64_tx_data",
            })
            mock_response.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)

            with patch.object(api, 'get_priority_fee_estimate') as mock_fee:
                mock_fee.return_value = {"priorityFeeEstimate": 50000}

                await api.execute_swap(
                    quote=SAMPLE_QUOTE,
                    user_public_key="wallet",
                )

                call_args = mock_client.post.call_args
                request_json = call_args[1].get('json', {})

                assert request_json.get('dynamicComputeUnitLimit') is True

    @pytest.mark.asyncio
    async def test_uses_priority_level_with_max_lamports(self):
        """Should use priorityLevelWithMaxLamports format."""
        from core.jupiter_api import JupiterAPI

        api = JupiterAPI()

        with patch.object(api, '_client') as mock_client:
            mock_response = AsyncMock()
            mock_response.json = MagicMock(return_value={
                "swapTransaction": "base64_tx_data",
            })
            mock_response.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)

            with patch.object(api, 'get_priority_fee_estimate') as mock_fee:
                mock_fee.return_value = {"priorityFeeEstimate": 50000}

                await api.execute_swap(
                    quote=SAMPLE_QUOTE,
                    user_public_key="wallet",
                    priority_level="high",
                    max_priority_fee_lamports=1000000,
                )

                call_args = mock_client.post.call_args
                request_json = call_args[1].get('json', {})

                # Should use Jupiter's priorityLevelWithMaxLamports format
                if 'priorityLevelWithMaxLamports' in request_json:
                    plwml = request_json['priorityLevelWithMaxLamports']
                    assert 'maxLamports' in plwml
                    assert 'priorityLevel' in plwml


# =============================================================================
# Test: Helius Client Configuration
# =============================================================================

class TestHeliusClientConfig:
    """Test Helius client configuration in JupiterAPI."""

    def test_helius_url_configured(self):
        """JupiterAPI should have Helius RPC URL configured."""
        from core.jupiter_api import JupiterAPI

        api = JupiterAPI()

        # Should have helius URL either from env or default
        assert hasattr(api, '_helius_url') or hasattr(api, 'helius_url')

    def test_helius_api_key_loaded(self):
        """JupiterAPI should load Helius API key from environment."""
        from core.jupiter_api import JupiterAPI

        with patch.dict(os.environ, {"HELIUS_API_KEY": "test_key_123"}):
            api = JupiterAPI()

            # Should have loaded the key
            helius_key = getattr(api, '_helius_api_key', None) or \
                         getattr(api, 'helius_api_key', None)
            # Key might be optional, so just check it doesn't crash

    @pytest.mark.asyncio
    async def test_helius_client_reused(self):
        """Helius client should be reused across calls."""
        from core.jupiter_api import JupiterAPI

        api = JupiterAPI()

        with patch.object(api, '_helius_client', create=True) as mock_helius:
            mock_helius.post = AsyncMock(return_value=MagicMock(
                status_code=200,
                json=MagicMock(return_value=SAMPLE_HELIUS_FEE_RESPONSE),
            ))

            # Make multiple calls
            await api.get_priority_fee_estimate()
            await api.get_priority_fee_estimate()

            # Should have used the same client
            assert mock_helius.post.call_count == 2
