"""
Tests for core/bags_api.py - Bags.fm API wrapper

US-005: bags.fm + Jupiter Backup with TP/SL
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestBagsAPI:
    """Test BagsAPI wrapper class."""

    def test_bags_api_has_base_url(self):
        """BagsAPI should have the correct base URL."""
        from core.bags_api import BagsAPI

        assert BagsAPI.BASE_URL == "https://api.bags.fm/v1"

    @pytest.mark.asyncio
    async def test_swap_returns_result_dict(self):
        """swap() should return a dict with success, tx_hash, amount_out."""
        from core.bags_api import BagsAPI

        api = BagsAPI()

        # Mock the internal client
        with patch.object(api, '_client') as mock_client:
            mock_response = AsyncMock()
            mock_response.json = MagicMock(return_value={
                "success": True,
                "txHash": "abc123",
                "outputAmount": 1000000,
            })
            mock_response.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)

            result = await api.swap(
                from_token="SOL",
                to_token="TOKEN123",
                amount_lamports=500000000,
                wallet_address="wallet123",
                slippage=0.01,
            )

            assert isinstance(result, dict)
            assert "success" in result
            assert "tx_hash" in result or "error" in result

    @pytest.mark.asyncio
    async def test_get_token_info_returns_token_data(self):
        """get_token_info() should return token metadata."""
        from core.bags_api import BagsAPI

        api = BagsAPI()

        with patch.object(api, '_client') as mock_client:
            mock_response = AsyncMock()
            mock_response.json = MagicMock(return_value={
                "symbol": "TEST",
                "name": "Test Token",
                "decimals": 9,
                "price": 0.001,
            })
            mock_response.raise_for_status = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)

            result = await api.get_token_info("TOKEN_MINT_123")

            assert result is not None
            assert "symbol" in result or hasattr(result, "symbol")

    @pytest.mark.asyncio
    async def test_get_chart_data_returns_price_history(self):
        """get_chart_data() should return price/volume history."""
        from core.bags_api import BagsAPI

        api = BagsAPI()

        with patch.object(api, '_client') as mock_client:
            mock_response = AsyncMock()
            mock_response.json = MagicMock(return_value={
                "candles": [
                    {"timestamp": 1700000000, "open": 1.0, "high": 1.1, "low": 0.9, "close": 1.05},
                ],
            })
            mock_response.raise_for_status = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)

            result = await api.get_chart_data(
                mint="TOKEN_MINT_123",
                interval="1h",
                limit=100,
            )

            assert result is not None
            assert isinstance(result, (list, dict))


class TestBagsAPIErrorHandling:
    """Test error handling in BagsAPI."""

    @pytest.mark.asyncio
    async def test_swap_returns_error_on_failure(self):
        """swap() should return error dict on API failure."""
        from core.bags_api import BagsAPI

        api = BagsAPI()

        with patch.object(api, '_client') as mock_client:
            mock_client.post = AsyncMock(side_effect=Exception("API Error"))

            result = await api.swap(
                from_token="SOL",
                to_token="TOKEN123",
                amount_lamports=500000000,
                wallet_address="wallet123",
            )

            assert result["success"] is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_get_token_info_returns_none_on_404(self):
        """get_token_info() should return None for unknown tokens."""
        from core.bags_api import BagsAPI

        api = BagsAPI()

        with patch.object(api, '_client') as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 404
            mock_response.raise_for_status = MagicMock(
                side_effect=Exception("404 Not Found")
            )
            mock_client.get = AsyncMock(return_value=mock_response)

            result = await api.get_token_info("NONEXISTENT_TOKEN")

            assert result is None
