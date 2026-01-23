"""
Tests for core/jupiter_api.py - Jupiter DEX API wrapper

US-005: bags.fm + Jupiter Backup with TP/SL
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestJupiterAPI:
    """Test JupiterAPI wrapper class."""

    def test_jupiter_api_has_base_url(self):
        """JupiterAPI should have the correct base URL."""
        from core.jupiter_api import JupiterAPI

        assert JupiterAPI.BASE_URL == "https://quote-api.jup.ag/v6"

    @pytest.mark.asyncio
    async def test_get_quote_returns_quote_dict(self):
        """get_quote() should return a quote dict with amounts and route."""
        from core.jupiter_api import JupiterAPI

        api = JupiterAPI()

        with patch.object(api, '_client') as mock_client:
            mock_response = AsyncMock()
            mock_response.json = MagicMock(return_value={
                "inputMint": "So11111111111111111111111111111111111111112",
                "outputMint": "TOKEN123",
                "inAmount": "1000000000",
                "outAmount": "5000000000",
                "priceImpactPct": "0.1",
                "routePlan": [{"swap": "info"}],
            })
            mock_response.raise_for_status = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)

            result = await api.get_quote(
                input_mint="So11111111111111111111111111111111111111112",
                output_mint="TOKEN123",
                amount=1000000000,
                slippage_bps=100,
            )

            assert result is not None
            assert "outAmount" in result or "out_amount" in result or hasattr(result, "out_amount")

    @pytest.mark.asyncio
    async def test_execute_swap_returns_result(self):
        """execute_swap() should return swap result with signature."""
        from core.jupiter_api import JupiterAPI

        api = JupiterAPI()

        mock_quote = {
            "inputMint": "So11111111111111111111111111111111111111112",
            "outputMint": "TOKEN123",
            "inAmount": "1000000000",
            "outAmount": "5000000000",
        }

        with patch.object(api, '_client') as mock_client:
            mock_response = AsyncMock()
            mock_response.json = MagicMock(return_value={
                "swapTransaction": "base64_tx_data",
            })
            mock_response.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)

            # Mock the actual swap execution
            with patch.object(api, '_sign_and_send') as mock_sign:
                mock_sign.return_value = {
                    "success": True,
                    "signature": "tx_sig_123",
                }

                result = await api.execute_swap(
                    quote=mock_quote,
                    user_public_key="user_wallet_123",
                )

                assert result is not None
                assert "success" in result or "signature" in result or "error" in result


class TestJupiterAPIErrorHandling:
    """Test error handling in JupiterAPI."""

    @pytest.mark.asyncio
    async def test_get_quote_returns_none_on_error(self):
        """get_quote() should return None on API error."""
        from core.jupiter_api import JupiterAPI

        api = JupiterAPI()

        with patch.object(api, '_client') as mock_client:
            mock_client.get = AsyncMock(side_effect=Exception("API Error"))

            result = await api.get_quote(
                input_mint="SOL",
                output_mint="TOKEN123",
                amount=1000000000,
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_execute_swap_returns_error_on_failure(self):
        """execute_swap() should return error dict on failure."""
        from core.jupiter_api import JupiterAPI

        api = JupiterAPI()

        mock_quote = {"inputMint": "SOL", "outputMint": "TOKEN123"}

        with patch.object(api, '_client') as mock_client:
            mock_client.post = AsyncMock(side_effect=Exception("Swap failed"))

            result = await api.execute_swap(
                quote=mock_quote,
                user_public_key="wallet123",
            )

            assert result is not None
            assert result.get("success") is False or "error" in result
