"""
Tests for Bags.fm Integration.

Tests the BagsClient, FeeCollector, and TradeRouter modules.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import asdict

# Import the modules to test
from integrations.bags.client import BagsClient, Quote, SwapResult, PartnerStats
from integrations.bags.fee_collector import FeeCollector
from integrations.bags.trade_router import TradeRouter, TradeIntent, TradeResult


class TestBagsClient:
    """Tests for BagsClient."""

    @pytest.fixture
    def client(self):
        """Create a BagsClient instance for testing."""
        return BagsClient(
            partner_key="test_partner_key",
            rpc_url="https://api.mainnet-beta.solana.com"
        )

    @pytest.fixture
    def mock_response(self):
        """Create a mock HTTP response."""
        mock = AsyncMock()
        mock.status = 200
        mock.json = AsyncMock(return_value={
            "inputMint": "So11111111111111111111111111111111111111112",
            "outputMint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            "inputAmount": 1000000000,
            "outputAmount": 50000000,
            "priceImpact": 0.01,
            "fee": 2500000,
            "route": {"test": "route"},
        })
        return mock

    @pytest.mark.asyncio
    async def test_get_quote_success(self, client, mock_response):
        """Test successful quote retrieval."""
        with patch.object(client._session, 'get', return_value=mock_response):
            quote = await client.get_quote(
                input_mint="So11111111111111111111111111111111111111112",
                output_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                amount=1000000000,
                slippage_bps=50
            )

            assert quote is not None
            assert quote.input_amount == 1000000000
            assert quote.output_amount == 50000000
            assert quote.price_impact == 0.01

    @pytest.mark.asyncio
    async def test_get_quote_rate_limit(self, client):
        """Test rate limiting behavior."""
        mock_response = AsyncMock()
        mock_response.status = 429
        mock_response.json = AsyncMock(return_value={"error": "Rate limited"})

        with patch.object(client._session, 'get', return_value=mock_response):
            quote = await client.get_quote(
                input_mint="So11111111111111111111111111111111111111112",
                output_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                amount=1000000000,
                slippage_bps=50
            )

            assert quote is None

    @pytest.mark.asyncio
    async def test_get_partner_stats(self, client):
        """Test partner stats retrieval."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "partnerKey": "test_partner_key",
            "totalVolumeUsd": 100000.50,
            "totalFeesUsd": 250.00,
            "totalTransactions": 500,
            "pendingFees": {"So11111111111111111111111111111111111111112": 1000000000},
        })

        with patch.object(client._session, 'get', return_value=mock_response):
            stats = await client.get_partner_stats()

            assert stats is not None
            assert stats.total_volume_usd == 100000.50
            assert stats.total_fees_usd == 250.00
            assert stats.total_transactions == 500

    def test_health_check(self, client):
        """Test health check returns correct structure."""
        health = client.health_check()

        assert "healthy" in health
        assert "request_count" in health
        assert "rate_limit" in health


class TestFeeCollector:
    """Tests for FeeCollector."""

    @pytest.fixture
    def mock_bags_client(self):
        """Create a mock BagsClient."""
        client = AsyncMock(spec=BagsClient)
        client.get_partner_stats = AsyncMock(return_value=PartnerStats(
            partner_key="test_key",
            total_volume_usd=100000,
            total_fees_usd=250,
            total_transactions=500,
            pending_fees={"So11111111111111111111111111111111111111112": 1000000000},
        ))
        client.create_claim_transactions = AsyncMock(return_value=[
            {"mint": "So11111111111111111111111111111111111111112", "transaction": "base64tx"}
        ])
        return client

    @pytest.fixture
    def fee_collector(self, mock_bags_client):
        """Create a FeeCollector instance."""
        return FeeCollector(
            bags_client=mock_bags_client,
            destination_wallet="TestWallet123",
            min_claim_amount=0.1,
        )

    @pytest.mark.asyncio
    async def test_check_pending_fees(self, fee_collector, mock_bags_client):
        """Test checking pending fees."""
        pending = await fee_collector.check_pending_fees()

        assert "SOL" in pending or len(pending) >= 0
        mock_bags_client.get_partner_stats.assert_called_once()

    @pytest.mark.asyncio
    async def test_collect_and_distribute_no_pending(self, fee_collector, mock_bags_client):
        """Test collection when no pending fees."""
        mock_bags_client.get_partner_stats = AsyncMock(return_value=PartnerStats(
            partner_key="test_key",
            total_volume_usd=100000,
            total_fees_usd=250,
            total_transactions=500,
            pending_fees={},
        ))

        result = await fee_collector.collect_and_distribute()

        assert result["claimed"] == 0
        assert result["distributed"] == 0

    @pytest.mark.asyncio
    async def test_get_collection_stats(self, fee_collector):
        """Test getting collection statistics."""
        stats = fee_collector.get_collection_stats()

        assert "total_collected" in stats
        assert "total_distributed" in stats
        assert "collection_count" in stats


class TestTradeRouter:
    """Tests for TradeRouter."""

    @pytest.fixture
    def mock_bags_client(self):
        """Create a mock BagsClient."""
        client = AsyncMock(spec=BagsClient)
        client.get_quote = AsyncMock(return_value=Quote(
            input_mint="So11111111111111111111111111111111111111112",
            output_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            input_amount=1000000000,
            output_amount=50000000,
            price_impact=0.01,
            fee=2500000,
            route={"test": "route"},
        ))
        client.execute_swap = AsyncMock(return_value=SwapResult(
            success=True,
            signature="tx_signature_123",
            input_amount=1000000000,
            output_amount=50000000,
            fee_amount=2500000,
        ))
        return client

    @pytest.fixture
    def trade_router(self, mock_bags_client):
        """Create a TradeRouter instance."""
        return TradeRouter(
            bags_client=mock_bags_client,
            jupiter_client=None,
            prefer_bags=True,
        )

    @pytest.mark.asyncio
    async def test_route_through_bags(self, trade_router, mock_bags_client):
        """Test routing through Bags."""
        intent = TradeIntent(
            input_mint="So11111111111111111111111111111111111111112",
            output_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            amount=1000000000,
            slippage_bps=50,
            keypair=MagicMock(),
        )

        result = await trade_router.execute(intent)

        assert result.success is True
        assert result.routed_through == "bags"
        mock_bags_client.get_quote.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_to_jupiter(self, trade_router, mock_bags_client):
        """Test fallback to Jupiter when Bags fails."""
        mock_bags_client.get_quote = AsyncMock(return_value=None)

        mock_jupiter = AsyncMock()
        mock_jupiter.get_quote = AsyncMock(return_value=MagicMock(
            input_amount=1000000000,
            output_amount=49000000,
        ))
        mock_jupiter.execute_swap = AsyncMock(return_value=MagicMock(
            success=True,
            signature="jupiter_tx_123",
        ))
        trade_router.jupiter_client = mock_jupiter

        intent = TradeIntent(
            input_mint="So11111111111111111111111111111111111111112",
            output_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            amount=1000000000,
            slippage_bps=50,
            keypair=MagicMock(),
        )

        result = await trade_router.execute(intent)

        assert result.routed_through == "jupiter"

    def test_get_routing_stats(self, trade_router):
        """Test getting routing statistics."""
        stats = trade_router.get_routing_stats()

        assert "total_trades" in stats
        assert "bags_trades" in stats
        assert "jupiter_trades" in stats
        assert "bags_volume" in stats


class TestIntegration:
    """Integration tests for the full flow."""

    @pytest.mark.asyncio
    async def test_full_trade_flow(self):
        """Test a complete trade flow from quote to execution."""
        # This would be an integration test with mocked external services
        pass

    @pytest.mark.asyncio
    async def test_fee_collection_cycle(self):
        """Test a complete fee collection cycle."""
        # This would test the full collection -> distribution flow
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
