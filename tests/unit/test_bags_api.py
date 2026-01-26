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


class TestBagsAPIQuote:
    """Test quote functionality."""

    @pytest.mark.asyncio
    async def test_get_quote_returns_quote_data(self):
        """get_quote() should return quote with amounts and price impact."""
        from core.bags_api import BagsAPI

        api = BagsAPI()

        with patch.object(api, '_client') as mock_client:
            mock_response = AsyncMock()
            mock_response.json = MagicMock(return_value={
                "outputAmount": 1000000000,
                "price": 0.00123,
                "priceImpact": 0.5,
                "fee": 0.001,
            })
            mock_response.raise_for_status = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)

            result = await api.get_quote(
                from_token="SOL",
                to_token="TOKEN123",
                amount_lamports=500000000,
                slippage=0.01,
            )

            assert result is not None
            assert "out_amount" in result
            assert "price_impact" in result

    @pytest.mark.asyncio
    async def test_get_quote_returns_none_on_error(self):
        """get_quote() should return None on API error."""
        from core.bags_api import BagsAPI

        api = BagsAPI()

        with patch.object(api, '_client') as mock_client:
            mock_client.get = AsyncMock(side_effect=Exception("Network error"))

            result = await api.get_quote(
                from_token="SOL",
                to_token="TOKEN123",
                amount_lamports=500000000,
            )

            assert result is None


class TestBagsTradeAdapter:
    """Test trade adapter with Jupiter fallback."""

    @pytest.mark.asyncio
    async def test_adapter_execute_swap_returns_tuple(self):
        """execute_swap() should return (signature, amount_out) tuple."""
        from core.trading.bags_adapter import BagsTradeAdapter

        adapter = BagsTradeAdapter(enable_fallback=False)

        # Mock the bags client
        with patch.object(adapter.bags, 'execute_swap') as mock_swap:
            mock_swap.return_value = MagicMock(
                signature="sig123",
                output_amount=1000000,
                source=MagicMock(value="bags"),
                price_impact=0.5,
                partner_fee_earned=0.001,
            )

            sig, amount = await adapter.execute_swap(
                input_mint="So11111111111111111111111111111111111111112",
                output_mint="TokenMint123",
                amount=100000000,
                slippage=0.5,
            )

            assert sig is not None
            assert isinstance(amount, int)

    @pytest.mark.asyncio
    async def test_adapter_fallback_on_bags_failure(self):
        """Adapter should fall back to Jupiter when Bags fails."""
        from core.trading.bags_adapter import BagsTradeAdapter

        adapter = BagsTradeAdapter(enable_fallback=True)

        # Mock bags to fail, jupiter to succeed
        with patch.object(adapter.bags, 'execute_swap') as mock_bags, \
             patch.object(adapter.jupiter, 'execute_swap') as mock_jupiter:

            mock_bags.side_effect = Exception("Bags.fm unavailable")
            mock_jupiter.return_value = MagicMock(
                signature="jupiter_sig_456",
                output_amount=950000,
                source=MagicMock(value="jupiter"),
                price_impact=0.6,
            )

            sig, amount = await adapter.execute_swap(
                input_mint="So11111111111111111111111111111111111111112",
                output_mint="TokenMint123",
                amount=100000000,
                slippage=0.5,
            )

            assert sig == "jupiter_sig_456"
            mock_jupiter.assert_called_once()

    def test_adapter_get_stats(self):
        """get_stats() should return trading statistics."""
        from core.trading.bags_adapter import BagsTradeAdapter

        adapter = BagsTradeAdapter()
        stats = adapter.get_stats()

        assert "total_trades" in stats
        assert "bags_trades" in stats
        assert "jupiter_trades" in stats
        assert "total_volume_sol" in stats


class TestBagsTradeRouter:
    """Test trade router for fallback behavior."""

    @pytest.mark.asyncio
    async def test_router_tracks_trade_source(self):
        """Router should track which source handled the trade."""
        from core.trading.bags_client import BagsTradeRouter, BagsAPIClient

        bags_client = BagsAPIClient()
        router = BagsTradeRouter(bags_client=bags_client)

        initial_bags_trades = router.bags_trades
        initial_jupiter_trades = router.jupiter_trades

        # After a trade, one of the counters should increment
        stats = router.get_stats()

        assert "bags_trades" in stats
        assert "jupiter_trades" in stats
        assert "total_volume" in stats

    def test_router_has_partner_id(self):
        """Router should have partner ID for attribution."""
        from core.trading.bags_client import BagsTradeRouter

        router = BagsTradeRouter(partner_id="jarvis_demo")

        assert router.partner_id == "jarvis_demo"


class TestSuccessFeeManager:
    """Test success fee calculation and collection."""

    def test_calculate_fee_on_winning_trade(self):
        """Should calculate 0.5% fee on profitable trades."""
        from core.trading.bags_client import SuccessFeeManager

        manager = SuccessFeeManager()

        fee_details = manager.calculate_success_fee(
            entry_price=1.0,
            exit_price=1.5,  # 50% profit
            amount_sol=1.0,
            token_symbol="TEST",
        )

        assert fee_details["applies"] is True
        assert fee_details["fee_percent"] == 0.5
        assert fee_details["pnl_percent"] == 50.0

    def test_no_fee_on_losing_trade(self):
        """Should not charge fee on losing trades."""
        from core.trading.bags_client import SuccessFeeManager

        manager = SuccessFeeManager()

        fee_details = manager.calculate_success_fee(
            entry_price=1.0,
            exit_price=0.8,  # 20% loss
            amount_sol=1.0,
            token_symbol="TEST",
        )

        assert fee_details["applies"] is False
        assert fee_details["fee_amount"] == 0

    def test_fee_stats_tracking(self):
        """Should track fee collection statistics."""
        from core.trading.bags_client import SuccessFeeManager

        manager = SuccessFeeManager()
        stats = manager.get_fee_stats()

        assert "fee_percent" in stats
        assert "total_collected" in stats
        assert "transaction_count" in stats


class TestBagsAPIClient:
    """Test full-featured BagsAPIClient."""

    def test_client_has_rate_limiting(self):
        """Client should have rate limiting configuration."""
        from core.trading.bags_client import BagsAPIClient

        client = BagsAPIClient()

        assert hasattr(client, 'requests_per_minute')
        assert client.requests_per_minute > 0

    @pytest.mark.asyncio
    async def test_client_get_quote_endpoint(self):
        """get_quote() should call correct API endpoint."""
        from core.trading.bags_client import BagsAPIClient

        client = BagsAPIClient()

        with patch.object(client, 'client') as mock_http:
            mock_response = AsyncMock()
            mock_response.json = MagicMock(return_value={
                "success": True,
                "response": {
                    "outAmount": "1000000",
                    "priceImpactPct": 0.5,
                    "routePlan": [],
                    "requestId": "req123",
                }
            })
            mock_response.raise_for_status = MagicMock()
            mock_http.get = AsyncMock(return_value=mock_response)

            quote = await client.get_quote(
                from_token="So11111111111111111111111111111111111111112",
                to_token="TokenMint123",
                amount=0.5,
                slippage_bps=100,
            )

            assert quote is not None
            mock_http.get.assert_called_once()

    def test_client_stats_tracking(self):
        """Client should track swap statistics."""
        from core.trading.bags_client import BagsAPIClient

        client = BagsAPIClient()
        stats = client.get_client_stats()

        assert "total_volume" in stats
        assert "successful_swaps" in stats
        assert "failed_swaps" in stats
        assert "success_rate" in stats


class TestFactoryFunctions:
    """Test singleton factory functions."""

    def test_get_bags_api_returns_singleton(self):
        """get_bags_api() should return singleton BagsAPI."""
        from core.bags_api import get_bags_api

        api1 = get_bags_api()
        api2 = get_bags_api()

        assert api1 is api2

    def test_get_bags_client_returns_singleton(self):
        """get_bags_client() should return singleton BagsAPIClient."""
        from core.trading.bags_client import get_bags_client

        client1 = get_bags_client()
        client2 = get_bags_client()

        assert client1 is client2

    def test_get_bags_client_supports_profiles(self):
        """get_bags_client() should support different profiles."""
        from core.trading.bags_client import get_bags_client

        default_client = get_bags_client()
        demo_client = get_bags_client(profile="demo")

        # Different profiles can be different instances
        # (unless they resolve to same config)
        assert default_client is not None
        assert demo_client is not None
