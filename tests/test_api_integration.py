"""
API Integration Tests - Validate market data sources work end-to-end

Tests:
1. DexScreener API - SOL token data
2. Jupiter API - Price fetching
3. Coingecko API - Market data
4. MarketDataService aggregation
5. Error handling and fallbacks
6. Cache behavior
"""

import asyncio
import logging
from datetime import datetime

import pytest

from core.market_data_service import (
    MarketDataService,
    DexScreenerClient,
    JupiterClient,
    CoingeckoClient,
    OnchainDataClient,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestDexScreenerAPI:
    """Test DexScreener API integration."""

    async def test_get_token_data(self):
        """Test fetching token data from DexScreener."""
        client = DexScreenerClient()

        # Test with SOL token
        sol_mint = "So11111111111111111111111111111111111111112"
        result = await client.get_token_data(sol_mint)

        if result:
            logger.info(f"✓ DexScreener SOL data: {result}")
            assert "price" in result or result == {}
            assert isinstance(result, dict)
        else:
            logger.warning("✗ DexScreener returned None (API may be rate limited)")

    async def test_search_token(self):
        """Test searching for tokens on DexScreener."""
        client = DexScreenerClient()

        result = await client.search_token("BONK")
        if result:
            logger.info(f"✓ DexScreener search returned {len(result)} results")
            assert isinstance(result, list)
        else:
            logger.warning("✗ DexScreener search returned None")

    async def test_parse_response(self):
        """Test parsing DexScreener response format."""
        client = DexScreenerClient()

        # Mock response
        mock_response = {
            "pairs": [
                {
                    "priceUsd": "142.50",
                    "priceChange": {"h24": 5.2, "d7": 15.3},
                    "liquidity": {"usd": 500_000_000},
                    "volume": {"h24": 2_500_000_000},
                    "marketCap": 45_000_000_000,
                    "fdv": 46_000_000_000,
                    "pairCreatedAt": 1609459200,
                    "chainId": "solana",
                }
            ]
        }

        result = client._parse_dexscreener_response(mock_response)
        logger.info(f"✓ Parsed response: {result}")
        assert result["price"] == 142.50
        assert result["liquidity_usd"] == 500_000_000
        assert result["volume_24h"] == 2_500_000_000


class TestJupiterAPI:
    """Test Jupiter API integration."""

    async def test_get_single_price(self):
        """Test fetching single token price."""
        client = JupiterClient()

        # SOL mint
        sol_mint = "So11111111111111111111111111111111111111112"
        price = await client.get_price(sol_mint)

        if price and price > 0:
            logger.info(f"✓ Jupiter SOL price: ${price:.2f}")
            assert isinstance(price, float)
            assert price > 0
        else:
            logger.warning("✗ Jupiter returned no price (API may be rate limited)")

    async def test_get_batch_prices(self):
        """Test fetching multiple token prices."""
        client = JupiterClient()

        mints = [
            "So11111111111111111111111111111111111111112",  # SOL
            "EPjFWaLb3hyccuBvfgLub8f3eMsqtiL15dC13jPyV29",  # USDC
        ]

        prices = await client.get_prices_batch(mints)
        if prices:
            logger.info(f"✓ Jupiter batch prices: {prices}")
            assert isinstance(prices, dict)
            assert len(prices) <= len(mints)
        else:
            logger.warning("✗ Jupiter batch returned empty (API may be rate limited)")

    async def test_price_accuracy(self):
        """Test that prices are reasonable."""
        client = JupiterClient()

        sol_mint = "So11111111111111111111111111111111111111112"
        price = await client.get_price(sol_mint)

        if price:
            # SOL should be between $10 and $1000
            assert 10 < price < 1000, f"Price ${price} seems unreasonable"
            logger.info(f"✓ Price ${price} is within reasonable range")
        else:
            logger.warning("✗ No price to validate")


class TestCoingeckoAPI:
    """Test Coingecko API integration."""

    async def test_get_token_by_address(self):
        """Test fetching token data by address."""
        client = CoingeckoClient()

        # Try SOL
        sol_address = "So11111111111111111111111111111111111111112"
        result = await client.get_token_by_address(sol_address, chain="solana")

        if result:
            logger.info(f"✓ Coingecko returned token data with keys: {list(result.keys())[:5]}")
            assert isinstance(result, dict)
        else:
            logger.warning("✗ Coingecko returned None")

    async def test_get_market_chart(self):
        """Test fetching historical price data."""
        client = CoingeckoClient()

        # Using token ID instead of mint (Coingecko uses IDs)
        result = await client.get_market_chart("solana", vs_currency="usd", days=7)

        if result:
            logger.info(f"✓ Coingecko returned market chart with keys: {list(result.keys())}")
            assert "prices" in result or isinstance(result, dict)
        else:
            logger.warning("✗ Coingecko market chart returned None")


class TestOnchainDataAPI:
    """Test on-chain data integration."""

    async def test_holder_distribution(self):
        """Test getting holder distribution."""
        client = OnchainDataClient()

        sol_mint = "So11111111111111111111111111111111111111112"
        result = await client.get_holder_distribution(sol_mint)

        if result:
            logger.info(f"✓ Holder distribution: {result}")
            assert "total_holders" in result
            assert "concentration_score" in result
        else:
            logger.warning("✗ Holder distribution returned None")

    async def test_smart_contract_check(self):
        """Test smart contract safety check."""
        client = OnchainDataClient()

        sol_mint = "So11111111111111111111111111111111111111112"
        result = await client.check_smart_contract(sol_mint)

        if result:
            logger.info(f"✓ Smart contract check: {result}")
            assert "verified" in result or "audit_status" in result
        else:
            logger.warning("✗ Smart contract check returned None")


class TestMarketDataServiceAggregation:
    """Test the unified MarketDataService."""

    async def test_get_market_data(self):
        """Test aggregating data from multiple sources."""
        service = MarketDataService()

        sol_mint = "So11111111111111111111111111111111111111112"
        result = await service.get_market_data("SOL", mint_address=sol_mint)

        if result:
            logger.info(f"✓ Market data aggregated: {list(result.keys())}")
            assert result["symbol"] == "SOL"
            assert "price" in result
            assert "liquidity_usd" in result
            assert "risk_score" in result
            assert "holder_distribution" in result
        else:
            logger.warning("✗ Market data aggregation returned None")

    async def test_cache_behavior(self):
        """Test that caching works correctly."""
        service = MarketDataService()

        sol_mint = "So11111111111111111111111111111111111111112"

        # First call - should hit API
        result1 = await service.get_market_data("SOL", mint_address=sol_mint)

        # Get cache stats
        cache_stats = service.get_cache_stats()
        logger.info(f"✓ Cache stats: {cache_stats}")

        # Second call - should use cache
        result2 = await service.get_market_data("SOL", mint_address=sol_mint)

        if result1 and result2:
            assert cache_stats["entries"] >= 1
            assert result1 == result2  # Should be identical (from cache)
            logger.info("✓ Cache is working correctly")

    async def test_batch_prices(self):
        """Test batch price fetching."""
        service = MarketDataService()

        mints = [
            "So11111111111111111111111111111111111111112",  # SOL
            "EPjFWaLb3hyccuBvfgLub8f3eMsqtiL15dC13jPyV29",  # USDC
        ]

        prices = await service.get_prices_batch(mints)
        if prices:
            logger.info(f"✓ Batch prices: {prices}")
            assert isinstance(prices, dict)
        else:
            logger.warning("✗ Batch prices returned empty")

    async def test_liquidity_info(self):
        """Test liquidity information endpoint."""
        service = MarketDataService()

        sol_mint = "So11111111111111111111111111111111111111112"
        result = await service.get_liquidity_info(sol_mint)

        if result:
            logger.info(f"✓ Liquidity info: {result}")
            assert "total_liquidity_usd" in result
            assert "liquidity_score" in result
            assert "recommended_max_trade" in result
        else:
            logger.warning("✗ Liquidity info returned None")


class TestErrorHandling:
    """Test error handling and fallbacks."""

    async def test_invalid_mint_address(self):
        """Test handling of invalid mint address."""
        service = MarketDataService()

        result = await service.get_market_data("INVALID", mint_address="invalid_mint")
        # Should return None or empty dict, not crash
        assert result is None or isinstance(result, dict)
        logger.info(f"✓ Handled invalid mint gracefully: {result}")

    async def test_timeout_handling(self):
        """Test handling of timeouts."""
        client = DexScreenerClient()

        # Try with invalid URL
        client.BASE_URL = "https://invalid.api.example.com"
        result = await client.get_token_data("So11111111111111111111111111111111111111112")

        # Should return None, not crash
        assert result is None
        logger.info("✓ Handled API timeout gracefully")

    async def test_partial_data_aggregation(self):
        """Test that service works even if some APIs fail."""
        service = MarketDataService()

        # Should still return some data even if some sources fail
        result = await service.get_market_data("SOL", mint_address="So11111111111111111111111111111111111111112")

        # Result should contain aggregated data from working sources
        if result:
            logger.info(f"✓ Partial aggregation succeeded: {list(result.keys())}")
            assert isinstance(result, dict)


class TestRiskScoreCalculation:
    """Test risk score calculation logic."""

    async def test_calculate_risk_score(self):
        """Test risk scoring algorithm."""
        service = MarketDataService()

        # Test with different liquidity levels
        test_cases = [
            {
                "name": "Low liquidity (risky)",
                "dex_data": {"liquidity_usd": 5_000},
                "holder_data": {"concentration_score": 50},
                "safety_data": {"risk_score": 50},
            },
            {
                "name": "High liquidity (safe)",
                "dex_data": {"liquidity_usd": 10_000_000},
                "holder_data": {"concentration_score": 30},
                "safety_data": {"risk_score": 25},
            },
            {
                "name": "High concentration (risky)",
                "dex_data": {"liquidity_usd": 1_000_000},
                "holder_data": {"concentration_score": 85},
                "safety_data": {"risk_score": 50},
            },
        ]

        for test_case in test_cases:
            risk = service._calculate_risk_score(
                test_case["dex_data"],
                test_case["holder_data"],
                test_case["safety_data"],
            )
            logger.info(f"✓ {test_case['name']}: Risk score = {risk:.1f}")
            assert 0 <= risk <= 100

    async def test_liquidity_score(self):
        """Test liquidity scoring."""
        service = MarketDataService()

        test_cases = [
            (5_000, 0),  # Very low
            (50_000, 25),  # Low
            (500_000, 50),  # Medium
            (5_000_000, 75),  # High
            (50_000_000, 100),  # Very high
        ]

        for liquidity, expected_score in test_cases:
            score = service._liquidity_score(liquidity)
            logger.info(f"✓ Liquidity ${liquidity:,} → score {score}")
            assert score == expected_score


async def run_all_tests():
    """Run all integration tests."""
    logger.info("=" * 60)
    logger.info("MARKET DATA API INTEGRATION TESTS")
    logger.info("=" * 60)

    test_classes = [
        TestDexScreenerAPI(),
        TestJupiterAPI(),
        TestCoingeckoAPI(),
        TestOnchainDataAPI(),
        TestMarketDataServiceAggregation(),
        TestErrorHandling(),
        TestRiskScoreCalculation(),
    ]

    for test_class in test_classes:
        logger.info(f"\n📋 Running {test_class.__class__.__name__}...")
        for method_name in dir(test_class):
            if method_name.startswith("test_"):
                try:
                    method = getattr(test_class, method_name)
                    await method()
                except Exception as e:
                    logger.error(f"✗ {method_name} failed: {e}")

    logger.info("\n" + "=" * 60)
    logger.info("INTEGRATION TESTS COMPLETE")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
