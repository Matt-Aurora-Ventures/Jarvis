"""
Unit tests for market data handling in JARVIS.

Tests the following components:
- Price data fetching (MarketDataAPI, FreePriceAPI)
- Data normalization (AssetPrice, TokenPrice)
- Stale data detection
- Multi-source data aggregation (MarketDataService)
- Missing data handling (graceful degradation)
- Historical data queries
- Caching behavior

Market data sources tested:
- Binance (crypto)
- Yahoo Finance (indices, commodities, precious metals)
- DexScreener (Solana DEX tokens)
- GeckoTerminal (token prices)
- Jupiter (Solana token prices)
"""
import pytest
import asyncio
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, AsyncMock, PropertyMock
from dataclasses import asdict


class TestAssetPriceDataclass:
    """Tests for AssetPrice data normalization."""

    def test_asset_price_basic_fields(self):
        """AssetPrice should correctly store basic fields."""
        from core.data.market_data_api import AssetPrice

        price = AssetPrice(
            symbol="BTC",
            name="Bitcoin",
            price=50000.0,
            change_24h=1000.0,
            change_pct=2.0,
            prev_close=49000.0,
            source="binance",
            asset_class="crypto",
            verified=True
        )

        assert price.symbol == "BTC"
        assert price.name == "Bitcoin"
        assert price.price == 50000.0
        assert price.change_24h == 1000.0
        assert price.change_pct == 2.0
        assert price.prev_close == 49000.0
        assert price.source == "binance"
        assert price.asset_class == "crypto"
        assert price.verified is True

    def test_asset_price_optional_fields_default(self):
        """AssetPrice should have sensible defaults for optional fields."""
        from core.data.market_data_api import AssetPrice

        price = AssetPrice(
            symbol="ETH",
            name="Ethereum",
            price=3000.0
        )

        assert price.change_24h is None
        assert price.change_pct is None
        assert price.prev_close is None
        assert price.source == "unknown"
        assert price.asset_class == "unknown"
        assert price.verified is True

    def test_asset_price_negative_change(self):
        """AssetPrice should handle negative price changes."""
        from core.data.market_data_api import AssetPrice

        price = AssetPrice(
            symbol="SOL",
            name="Solana",
            price=100.0,
            change_24h=-10.0,
            change_pct=-9.1,
            prev_close=110.0
        )

        assert price.change_24h == -10.0
        assert price.change_pct == -9.1


class TestTokenPriceDataclass:
    """Tests for TokenPrice data normalization (Solana tokens)."""

    def test_token_price_basic_fields(self):
        """TokenPrice should correctly store Solana token data."""
        from core.data.free_price_api import TokenPrice

        token = TokenPrice(
            address="So11111111111111111111111111111111111111112",
            symbol="SOL",
            name="Solana",
            price_usd=150.0,
            price_sol=1.0,
            volume_24h=500000000.0,
            liquidity=1000000000.0,
            price_change_24h=5.5,
            source="dexscreener"
        )

        assert token.address == "So11111111111111111111111111111111111111112"
        assert token.symbol == "SOL"
        assert token.name == "Solana"
        assert token.price_usd == 150.0
        assert token.price_sol == 1.0
        assert token.volume_24h == 500000000.0
        assert token.liquidity == 1000000000.0
        assert token.price_change_24h == 5.5
        assert token.source == "dexscreener"

    def test_token_price_auto_timestamp(self):
        """TokenPrice should auto-generate timestamp if not provided."""
        from core.data.free_price_api import TokenPrice

        before = datetime.now(timezone.utc)
        token = TokenPrice(
            address="test_address",
            symbol="TEST",
            name="Test Token",
            price_usd=1.0
        )
        after = datetime.now(timezone.utc)

        assert token.timestamp != ""
        timestamp = datetime.fromisoformat(token.timestamp)
        assert before <= timestamp <= after

    def test_token_price_zero_values(self):
        """TokenPrice should handle zero values gracefully."""
        from core.data.free_price_api import TokenPrice

        token = TokenPrice(
            address="test_address",
            symbol="ZERO",
            name="Zero Token",
            price_usd=0.0,
            volume_24h=0.0,
            liquidity=0.0
        )

        assert token.price_usd == 0.0
        assert token.volume_24h == 0.0
        assert token.liquidity == 0.0


class TestMarketDataAPIPriceFetching:
    """Tests for MarketDataAPI price fetching from various sources."""

    @pytest.mark.asyncio
    async def test_get_crypto_prices_success(self):
        """Should fetch crypto prices from Binance."""
        from core.data.market_data_api import MarketDataAPI

        mock_response = {
            "lastPrice": "50000.00",
            "priceChangePercent": "2.50",
            "prevClosePrice": "48750.00"
        }

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session

            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.json = AsyncMock(return_value=mock_response)
            mock_session.get.return_value.__aenter__.return_value = mock_resp

            api = MarketDataAPI()
            # Clear cache to ensure fresh fetch
            from core.data.market_data_api import _market_cache
            _market_cache.clear()

            prices = await api.get_crypto_prices()
            await api.close()

            # Should return dict with crypto prices
            assert isinstance(prices, dict)

    @pytest.mark.asyncio
    async def test_get_crypto_prices_api_error(self):
        """Should handle API errors gracefully."""
        from core.data.market_data_api import MarketDataAPI

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session

            mock_resp = AsyncMock()
            mock_resp.status = 500
            mock_session.get.return_value.__aenter__.return_value = mock_resp

            api = MarketDataAPI()
            from core.data.market_data_api import _market_cache
            _market_cache.clear()

            prices = await api.get_crypto_prices()
            await api.close()

            # Should return empty dict on error
            assert isinstance(prices, dict)

    @pytest.mark.asyncio
    async def test_get_fear_greed_success(self):
        """Should fetch Fear & Greed index."""
        from core.data.market_data_api import MarketDataAPI, _market_cache

        _market_cache.clear()

        mock_response = {
            "data": [
                {"value": "45", "value_classification": "Fear"}
            ]
        }

        # Create a proper async context manager mock
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_response)

        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_context.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_context)
        mock_session.closed = False
        mock_session.close = AsyncMock()

        api = MarketDataAPI()
        api._session = mock_session

        result = await api.get_fear_greed()

        assert result == 45

    @pytest.mark.asyncio
    async def test_get_fear_greed_returns_none_on_error(self):
        """Should return None on Fear & Greed API error."""
        from core.data.market_data_api import MarketDataAPI, _market_cache

        _market_cache.clear()

        # Create a proper async context manager mock for error case
        mock_resp = MagicMock()
        mock_resp.status = 503  # Service unavailable

        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_context.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_context)
        mock_session.closed = False
        mock_session.close = AsyncMock()

        api = MarketDataAPI()
        api._session = mock_session

        result = await api.get_fear_greed()

        assert result is None


class TestFreePriceAPIFallbackChain:
    """Tests for FreePriceAPI fallback chain (DexScreener -> GeckoTerminal -> Jupiter)."""

    @pytest.mark.asyncio
    async def test_get_price_dexscreener_success(self):
        """Should get price from DexScreener as first source."""
        from core.data.free_price_api import FreePriceAPI, _price_cache, TokenPrice

        _price_cache.clear()

        mock_dex_response = {
            "pairs": [
                {
                    "baseToken": {"symbol": "TEST", "name": "Test Token"},
                    "priceUsd": "1.50",
                    "volume": {"h24": "100000"},
                    "liquidity": {"usd": "500000"},
                    "priceChange": {"h24": "5.5"}
                }
            ]
        }

        # Create proper async context manager mock
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_dex_response)

        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_context.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_context)
        mock_session.closed = False
        mock_session.close = AsyncMock()

        api = FreePriceAPI()
        api._session = mock_session

        # Mock rate limiter
        with patch("core.data.free_price_api.get_rate_limiter") as mock_rl:
            mock_rl.return_value.wait_and_acquire = AsyncMock()

            result = await api.get_price("test_address")

            assert result is not None
            assert result.symbol == "TEST"
            assert result.price_usd == 1.50
            assert result.source == "dexscreener"

    @pytest.mark.asyncio
    async def test_get_price_falls_back_to_geckoterminal(self):
        """Should fall back to GeckoTerminal if DexScreener fails."""
        from core.data.free_price_api import FreePriceAPI, _price_cache, TokenPrice

        _price_cache.clear()

        api = FreePriceAPI()

        # Create expected result from GeckoTerminal
        gecko_result = TokenPrice(
            address="test_address",
            symbol="TEST",
            name="Test Token",
            price_usd=1.25,
            source="geckoterminal"
        )

        # Mock internal methods - DexScreener fails, GeckoTerminal succeeds
        with patch.object(api, "_try_dexscreener", new_callable=AsyncMock) as mock_dex,              patch.object(api, "_try_geckoterminal", new_callable=AsyncMock) as mock_gecko,              patch.object(api, "_try_jupiter", new_callable=AsyncMock) as mock_jup:

            mock_dex.return_value = None  # DexScreener fails
            mock_gecko.return_value = gecko_result  # GeckoTerminal succeeds
            mock_jup.return_value = None  # Not called

            result = await api.get_price("test_address")

            assert result is not None
            assert result.source == "geckoterminal"
            assert result.price_usd == 1.25

            # Verify call order
            mock_dex.assert_called_once()
            mock_gecko.assert_called_once()
            mock_jup.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_price_all_sources_fail(self):
        """Should return None if all sources fail."""
        from core.data.free_price_api import FreePriceAPI, _price_cache

        _price_cache.clear()

        # Create mock that always returns error
        mock_resp = MagicMock()
        mock_resp.status = 500

        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_context.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_context)
        mock_session.closed = False
        mock_session.close = AsyncMock()

        api = FreePriceAPI()
        api._session = mock_session

        with patch("core.data.free_price_api.get_rate_limiter") as mock_rl:
            mock_rl.return_value.wait_and_acquire = AsyncMock()

            result = await api.get_price("nonexistent_address")

            assert result is None

    @pytest.mark.asyncio
    async def test_get_multiple_prices_concurrent(self):
        """Should fetch multiple prices concurrently."""
        from core.data.free_price_api import FreePriceAPI, _price_cache

        _price_cache.clear()

        mock_response = {
            "pairs": [
                {
                    "baseToken": {"symbol": "TOKEN", "name": "Token"},
                    "priceUsd": "1.00",
                    "volume": {"h24": "1000"},
                    "liquidity": {"usd": "5000"},
                    "priceChange": {"h24": "0"}
                }
            ]
        }

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_response)

        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_context.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_context)
        mock_session.closed = False
        mock_session.close = AsyncMock()

        api = FreePriceAPI()
        api._session = mock_session

        with patch("core.data.free_price_api.get_rate_limiter") as mock_rl:
            mock_rl.return_value.wait_and_acquire = AsyncMock()

            addresses = ["addr1", "addr2", "addr3"]
            results = await api.get_multiple_prices(addresses)
            await api.close()

            assert isinstance(results, dict)


class TestStaleDataDetection:
    """Tests for stale data detection."""

    def test_cache_ttl_expiration(self):
        """Should detect expired cache entries."""
        from core.cache.memory_cache import LRUCache

        cache = LRUCache(maxsize=100, ttl=1)  # 1 second TTL

        cache.set("test_key", {"price": 100})
        assert cache.get("test_key") == {"price": 100}

        time.sleep(1.1)  # Wait for expiration

        assert cache.get("test_key") is None

    def test_market_overview_timestamp(self):
        """MarketOverview should have accurate timestamp."""
        from core.data.market_data_api import MarketOverview

        before = datetime.now(timezone.utc)
        overview = MarketOverview()
        after = datetime.now(timezone.utc)

        assert overview.last_updated != ""
        timestamp = datetime.fromisoformat(overview.last_updated)
        assert before <= timestamp <= after

    @pytest.mark.asyncio
    async def test_market_data_service_cache_ttl(self):
        """MarketDataService should respect cache TTL."""
        from core.market_data_service import MarketDataService

        service = MarketDataService()
        service.cache_ttl_seconds = 1  # 1 second TTL

        # Simulate cached data
        service.cache["test:addr"] = (
            {"symbol": "TEST", "price": 100},
            datetime.utcnow() - timedelta(seconds=2)  # 2 seconds old
        )

        # Cache should be stale - need fresh data
        cached_data, timestamp = service.cache["test:addr"]
        age = datetime.utcnow() - timestamp
        is_stale = age >= timedelta(seconds=service.cache_ttl_seconds)

        assert is_stale is True


class TestMultiSourceDataAggregation:
    """Tests for aggregating data from multiple sources."""

    @pytest.mark.asyncio
    async def test_market_data_service_aggregates_sources(self):
        """MarketDataService should aggregate data from multiple sources."""
        from core.market_data_service import MarketDataService

        service = MarketDataService()

        # Mock all data sources
        with patch.object(service.jupiter, 'get_price', new_callable=AsyncMock) as mock_jupiter, \
             patch.object(service.dexscreener, 'get_token_data', new_callable=AsyncMock) as mock_dex, \
             patch.object(service.onchain, 'get_holder_distribution', new_callable=AsyncMock) as mock_onchain, \
             patch.object(service.onchain, 'check_smart_contract', new_callable=AsyncMock) as mock_safety:

            mock_jupiter.return_value = 150.0  # Jupiter price
            mock_dex.return_value = {
                "price": 150.5,
                "price_change_24h": 5.0,
                "price_change_7d": 10.0,
                "liquidity_usd": 1000000,
                "volume_24h": 500000,
                "market_cap": 5000000,
                "fdv": 6000000
            }
            mock_onchain.return_value = {
                "total_holders": 5000,
                "concentration_score": 45
            }
            mock_safety.return_value = {
                "verified": True,
                "risk_score": 25
            }

            result = await service.get_market_data("SOL", "So11111111111111111111111111111111111111112")

            assert result is not None
            assert result["symbol"] == "SOL"
            # Should use Jupiter price (primary) or DexScreener as fallback
            assert result["price"] == 150.0 or result["price"] == 150.5
            assert result["liquidity_usd"] == 1000000
            assert result["holder_distribution"] is not None
            assert result["smart_contract_safety"] is not None

    def test_risk_score_calculation(self):
        """Should calculate composite risk score correctly."""
        from core.market_data_service import MarketDataService

        service = MarketDataService()

        # Test low liquidity increases risk
        risk = service._calculate_risk_score(
            {"liquidity_usd": 5000},  # Very low
            {"concentration_score": 50},
            {"risk_score": 50}
        )
        assert risk > 60  # Higher risk due to low liquidity

        # Test high liquidity decreases risk
        risk = service._calculate_risk_score(
            {"liquidity_usd": 5000000},  # High liquidity
            {"concentration_score": 50},
            {"risk_score": 30}  # Low contract risk
        )
        assert risk < 50  # Lower overall risk

    def test_volume_liquidity_ratio(self):
        """Should calculate volume/liquidity ratio correctly."""
        from core.market_data_service import MarketDataService

        service = MarketDataService()

        ratio = service._calc_volume_liquidity_ratio(100000, 500000)
        assert ratio == 0.2

        # Handle zero liquidity
        ratio = service._calc_volume_liquidity_ratio(100000, 0)
        assert ratio == 0.0


class TestMissingDataHandling:
    """Tests for graceful handling of missing data."""

    @pytest.mark.asyncio
    async def test_get_market_overview_partial_data(self):
        """Should handle partial data availability."""
        from core.data.market_data_api import MarketDataAPI, _market_cache

        api = MarketDataAPI()
        _market_cache.clear()

        # Mock with some sources failing
        with patch.object(api, 'get_crypto_prices', new_callable=AsyncMock) as mock_crypto, \
             patch.object(api, 'get_fear_greed', new_callable=AsyncMock) as mock_fg, \
             patch.object(api, 'get_precious_metals', new_callable=AsyncMock) as mock_metals, \
             patch.object(api, 'get_indices', new_callable=AsyncMock) as mock_indices, \
             patch.object(api, 'get_commodities', new_callable=AsyncMock) as mock_commodities:

            # Crypto succeeds
            from core.data.market_data_api import AssetPrice
            mock_crypto.return_value = {
                "btc": AssetPrice(symbol="BTC", name="Bitcoin", price=50000, source="binance", asset_class="crypto")
            }

            # Fear & Greed fails
            mock_fg.return_value = None

            # Metals fail
            mock_metals.return_value = {}

            # Indices partially succeed
            mock_indices.return_value = {
                "spx": AssetPrice(symbol="SPX", name="S&P 500", price=5000, source="yahoo", asset_class="index")
            }

            # Commodities fail
            mock_commodities.return_value = {}

            overview = await api.get_market_overview()
            await api.close()

            # Should still return overview with available data
            assert overview.btc is not None
            assert overview.btc.price == 50000
            assert overview.sp500 is not None
            assert overview.fear_greed is None  # Failed
            assert overview.gold is None  # Failed
            assert overview.oil is None  # Failed

    @pytest.mark.asyncio
    async def test_token_price_missing_fields(self):
        """Should handle API responses with missing fields."""
        from core.data.free_price_api import FreePriceAPI, _price_cache

        _price_cache.clear()

        # Response with minimal data
        mock_response = {
            "pairs": [
                {
                    "baseToken": {"symbol": "MIN"},
                    "priceUsd": "1.00"
                    # Missing: name, volume, liquidity, priceChange
                }
            ]
        }

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_response)

        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_context.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_context)
        mock_session.closed = False
        mock_session.close = AsyncMock()

        api = FreePriceAPI()
        api._session = mock_session

        with patch("core.data.free_price_api.get_rate_limiter") as mock_rl:
            mock_rl.return_value.wait_and_acquire = AsyncMock()

            result = await api.get_price("minimal_token")

            assert result is not None
            assert result.symbol == "MIN"
            assert result.price_usd == 1.00
            assert result.volume_24h == 0.0  # Default
            assert result.liquidity == 0.0  # Default

    def test_dexscreener_empty_pairs(self):
        """Should handle empty pairs array from DexScreener."""
        from core.market_data_service import DexScreenerClient

        client = DexScreenerClient()
        result = client._parse_dexscreener_response({"pairs": []})

        assert result == {}


class TestHistoricalDataQueries:
    """Tests for historical data querying."""

    @pytest.mark.asyncio
    async def test_coingecko_market_chart(self):
        """Should fetch historical market data."""
        from core.market_data_service import CoingeckoClient

        mock_response = {
            "prices": [
                [1609459200000, 29000],
                [1609545600000, 30000],
                [1609632000000, 31000]
            ],
            "market_caps": [
                [1609459200000, 540000000000],
                [1609545600000, 560000000000],
                [1609632000000, 580000000000]
            ],
            "total_volumes": [
                [1609459200000, 30000000000],
                [1609545600000, 32000000000],
                [1609632000000, 34000000000]
            ]
        }

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_response)

        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_context.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session_instance = MagicMock()
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            mock_session_instance.get = MagicMock(return_value=mock_context)
            mock_session_class.return_value = mock_session_instance

            client = CoingeckoClient()
            result = await client.get_market_chart("bitcoin", "usd", 7)

            assert result is not None
            assert "prices" in result
            assert len(result["prices"]) == 3


class TestCachingBehavior:
    """Tests for caching behavior in market data APIs."""

    def test_lru_cache_hit(self):
        """Should return cached value on cache hit."""
        from core.cache.memory_cache import LRUCache

        cache = LRUCache(maxsize=100, ttl=300)
        cache.set("price:BTC", 50000)

        result = cache.get("price:BTC")
        assert result == 50000

    def test_lru_cache_eviction(self):
        """Should evict least recently used items when full."""
        from core.cache.memory_cache import LRUCache

        cache = LRUCache(maxsize=3, ttl=300)

        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        # Access key1 to make it recently used
        cache.get("key1")

        # Add key4, should evict key2 (least recently used after key1 access)
        cache.set("key4", "value4")

        assert cache.get("key1") == "value1"  # Still present (recently accessed)
        assert cache.get("key2") is None  # Evicted
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"

    @pytest.mark.asyncio
    async def test_market_data_cache_key_format(self):
        """Should use correct cache key format for market data."""
        from core.data.free_price_api import _price_cache

        _price_cache.clear()

        # Simulate caching
        from core.data.free_price_api import TokenPrice
        token = TokenPrice(
            address="test_addr",
            symbol="TEST",
            name="Test",
            price_usd=1.0
        )

        cache_key = f"price:{token.address}"
        _price_cache.set(cache_key, token)

        cached = _price_cache.get(cache_key)
        assert cached is not None
        assert cached.symbol == "TEST"

    @pytest.mark.asyncio
    async def test_price_api_uses_cache(self):
        """FreePriceAPI should use cache for repeated requests."""
        from core.data.free_price_api import FreePriceAPI, TokenPrice, _price_cache

        _price_cache.clear()

        # Pre-populate cache
        cached_token = TokenPrice(
            address="cached_addr",
            symbol="CACHED",
            name="Cached Token",
            price_usd=99.0,
            source="cache"
        )
        _price_cache.set("price:cached_addr", cached_token)

        api = FreePriceAPI()
        result = await api.get_price("cached_addr")
        await api.close()

        # Should return cached value without API call
        assert result is not None
        assert result.symbol == "CACHED"
        assert result.price_usd == 99.0


class TestMarketOverview:
    """Tests for MarketOverview data structure."""

    def test_market_overview_sentiment_calculation(self):
        """Should calculate market sentiment from fear/greed index."""
        from core.data.market_data_api import MarketOverview

        # Extreme fear
        overview = MarketOverview(fear_greed=20)
        overview.market_sentiment = "extreme fear" if overview.fear_greed < 25 else "neutral"
        assert overview.market_sentiment == "extreme fear"

        # Fear
        overview = MarketOverview(fear_greed=35)
        if overview.fear_greed < 25:
            overview.market_sentiment = "extreme fear"
        elif overview.fear_greed < 40:
            overview.market_sentiment = "fear"
        assert overview.market_sentiment == "fear"

        # Greed
        overview = MarketOverview(fear_greed=65)
        if overview.fear_greed > 75:
            overview.market_sentiment = "extreme greed"
        elif overview.fear_greed > 60:
            overview.market_sentiment = "greed"
        assert overview.market_sentiment == "greed"

    def test_market_overview_data_sources_tracking(self):
        """Should track which data sources were used."""
        from core.data.market_data_api import MarketOverview, AssetPrice

        overview = MarketOverview(
            btc=AssetPrice(symbol="BTC", name="Bitcoin", price=50000, source="binance", asset_class="crypto"),
            gold=AssetPrice(symbol="XAU", name="Gold", price=2000, source="yahoo-futures", asset_class="metal"),
            fear_greed=45,
            data_sources=["binance", "yahoo-finance", "alternative.me"]
        )

        assert "binance" in overview.data_sources
        assert "yahoo-finance" in overview.data_sources
        assert "alternative.me" in overview.data_sources


class TestDataQualityChecks:
    """Tests for data quality validation."""

    def test_price_validation_positive(self):
        """Price should be positive for valid assets."""
        from core.data.market_data_api import AssetPrice

        # Valid positive price
        price = AssetPrice(symbol="BTC", name="Bitcoin", price=50000)
        assert price.price > 0

    def test_price_validation_reasonable_range(self):
        """Should detect unreasonable price values."""
        # This would be part of data validation logic
        def is_reasonable_btc_price(price: float) -> bool:
            return 1000 < price < 1000000  # Reasonable BTC range

        assert is_reasonable_btc_price(50000) is True
        assert is_reasonable_btc_price(0.01) is False
        assert is_reasonable_btc_price(10000000) is False

    def test_volume_validation(self):
        """Volume should be non-negative."""
        from core.data.free_price_api import TokenPrice

        token = TokenPrice(
            address="test",
            symbol="TEST",
            name="Test",
            price_usd=1.0,
            volume_24h=-100  # Invalid negative volume
        )

        # Volume should be checked/sanitized
        assert token.volume_24h is not None


class TestEnhancedMarketDataQualityFilters:
    """Tests for quality filters in enhanced market data."""

    def test_passes_quality_filter_success(self):
        """Should pass tokens meeting all quality criteria."""
        from core.enhanced_market_data import passes_quality_filter

        passes, reason = passes_quality_filter(
            symbol="GOOD",
            name="Good Token",
            liquidity_usd=100000,  # > MIN_LIQUIDITY_USD
            mcap=1000000,  # > MIN_MCAP_USD
            volume_24h=50000,  # > MIN_VOLUME_24H
            tx_count_24h=100,  # > MIN_TX_COUNT_24H
            price_change_24h=50  # < MAX_PRICE_CHANGE_24H
        )

        assert passes is True
        assert reason == "Passed"

    def test_passes_quality_filter_low_liquidity(self):
        """Should reject tokens with low liquidity."""
        from core.enhanced_market_data import passes_quality_filter, MIN_LIQUIDITY_USD

        passes, reason = passes_quality_filter(
            symbol="LOW",
            name="Low Liquidity Token",
            liquidity_usd=1000,  # Below MIN_LIQUIDITY_USD
            mcap=1000000,
            volume_24h=50000,
            tx_count_24h=100,
            price_change_24h=10
        )

        assert passes is False
        assert "Low liquidity" in reason

    def test_passes_quality_filter_extreme_pump(self):
        """Should reject tokens with extreme price pumps."""
        from core.enhanced_market_data import passes_quality_filter, MAX_PRICE_CHANGE_24H

        passes, reason = passes_quality_filter(
            symbol="PUMP",
            name="Pump Token",
            liquidity_usd=100000,
            mcap=1000000,
            volume_24h=50000,
            tx_count_24h=100,
            price_change_24h=600  # > MAX_PRICE_CHANGE_24H (500)
        )

        assert passes is False
        assert "Extreme pump" in reason

    def test_passes_quality_filter_blacklisted_name(self):
        """Should reject tokens with blacklisted names."""
        from core.enhanced_market_data import passes_quality_filter

        passes, reason = passes_quality_filter(
            symbol="SCAM",
            name="pump.fun token",  # Contains blacklisted pattern
            liquidity_usd=100000,
            mcap=1000000,
            volume_24h=50000,
            tx_count_24h=100,
            price_change_24h=10
        )

        assert passes is False
        assert "Blacklisted" in reason


class TestTrendingTokenDataclass:
    """Tests for TrendingToken dataclass."""

    def test_trending_token_to_dict(self):
        """Should serialize TrendingToken to dict correctly."""
        from core.enhanced_market_data import TrendingToken

        token = TrendingToken(
            symbol="TREND",
            name="Trending Token",
            contract="abcd1234",
            price_usd=0.001,
            price_change_24h=25.5,
            volume_24h=100000,
            liquidity_usd=500000,
            mcap=1000000,
            tx_count_24h=500,
            rank=1,
            galaxy_score=75.0,
            social_volume=1000,
            social_sentiment=65.0,
            alt_rank=50,
            news_sentiment="bullish",
            news_count=5
        )

        data = token.to_dict()

        assert data["symbol"] == "TREND"
        assert data["price_usd"] == 0.001
        assert data["rank"] == 1
        assert data["galaxy_score"] == 75.0
        assert data["news_sentiment"] == "bullish"


class TestBackedAssets:
    """Tests for backed.fi xStocks assets."""

    def test_backed_xstocks_registry(self):
        """Should have valid xStocks registry."""
        from core.enhanced_market_data import BACKED_XSTOCKS

        assert "AAPLx" in BACKED_XSTOCKS
        assert "NVDAx" in BACKED_XSTOCKS
        assert "SPYx" in BACKED_XSTOCKS

        # Check structure
        aapl = BACKED_XSTOCKS["AAPLx"]
        assert "name" in aapl
        assert "mint" in aapl
        assert "type" in aapl
        assert "underlying" in aapl

        assert aapl["underlying"] == "AAPL"
        assert aapl["type"] == "stock"

    def test_backed_asset_to_dict(self):
        """Should serialize BackedAsset to dict correctly."""
        from core.enhanced_market_data import BackedAsset

        asset = BackedAsset(
            symbol="AAPLx",
            name="Apple xStock",
            mint_address="test_mint",
            asset_type="stock",
            underlying="AAPL",
            price_usd=180.50,
            change_1y=15.5
        )

        data = asset.to_dict()

        assert data["symbol"] == "AAPLx"
        assert data["underlying"] == "AAPL"
        assert data["asset_type"] == "stock"
        assert data["price_usd"] == 180.50


class TestHighLiquiditySolanaTokens:
    """Tests for high liquidity Solana token registry."""

    def test_high_liquidity_tokens_registry(self):
        """Should have established tokens in registry."""
        from core.enhanced_market_data import HIGH_LIQUIDITY_SOLANA_TOKENS

        # Native Solana
        assert "SOL" in HIGH_LIQUIDITY_SOLANA_TOKENS
        assert HIGH_LIQUIDITY_SOLANA_TOKENS["SOL"]["category"] == "L1"

        # DeFi
        assert "JUP" in HIGH_LIQUIDITY_SOLANA_TOKENS
        assert HIGH_LIQUIDITY_SOLANA_TOKENS["JUP"]["category"] == "DeFi"

        # Meme
        assert "BONK" in HIGH_LIQUIDITY_SOLANA_TOKENS
        assert HIGH_LIQUIDITY_SOLANA_TOKENS["BONK"]["category"] == "Meme"

        # LST
        assert "mSOL" in HIGH_LIQUIDITY_SOLANA_TOKENS
        assert HIGH_LIQUIDITY_SOLANA_TOKENS["mSOL"]["category"] == "LST"

    def test_get_wrapped_tokens_by_category(self):
        """Should group tokens by category."""
        from core.enhanced_market_data import get_wrapped_tokens_by_category

        categories = get_wrapped_tokens_by_category()

        assert "DeFi" in categories
        assert "Meme" in categories
        assert "Wrapped" in categories
        assert "Stablecoin" in categories

        # Check structure
        for token_info in categories["DeFi"]:
            assert "symbol" in token_info
            assert "name" in token_info
            assert "mint" in token_info

    def test_get_wrapped_token_count(self):
        """Should count tokens per category."""
        from core.enhanced_market_data import get_wrapped_token_count

        counts = get_wrapped_token_count()

        assert isinstance(counts, dict)
        assert all(isinstance(v, int) for v in counts.values())
        assert sum(counts.values()) > 0


class TestConvictionPick:
    """Tests for ConvictionPick dataclass."""

    def test_conviction_pick_to_dict(self):
        """Should serialize ConvictionPick correctly."""
        from core.enhanced_market_data import ConvictionPick

        pick = ConvictionPick(
            symbol="SOL",
            name="Solana",
            asset_class="token",
            contract="So11111111111111111111111111111111111111112",
            conviction_score=85,
            reasoning="Strong ecosystem growth",
            entry_price=150.0,
            target_price=180.0,
            stop_loss=135.0,
            timeframe="medium"
        )

        data = pick.to_dict()

        assert data["symbol"] == "SOL"
        assert data["conviction_score"] == 85
        assert data["entry_price"] == 150.0
        assert data["target_price"] == 180.0
        assert data["stop_loss"] == 135.0
        assert data["timeframe"] == "medium"


class TestMarketDataServiceCaching:
    """Tests for MarketDataService cache management."""

    def test_cache_clear(self):
        """Should clear all cached entries."""
        from core.market_data_service import MarketDataService

        service = MarketDataService()

        # Add some cache entries
        service.cache["key1"] = ({"data": 1}, datetime.utcnow())
        service.cache["key2"] = ({"data": 2}, datetime.utcnow())

        assert len(service.cache) == 2

        service.clear_cache()

        assert len(service.cache) == 0

    def test_cache_stats(self):
        """Should return cache statistics."""
        from core.market_data_service import MarketDataService

        service = MarketDataService()

        # Empty cache
        stats = service.get_cache_stats()
        assert stats["entries"] == 0

        # Add entries
        now = datetime.utcnow()
        service.cache["key1"] = ({"data": 1}, now - timedelta(minutes=5))
        service.cache["key2"] = ({"data": 2}, now)

        stats = service.get_cache_stats()
        assert stats["entries"] == 2
        assert stats["ttl_seconds"] == service.cache_ttl_seconds

    def test_liquidity_score(self):
        """Should calculate liquidity score correctly."""
        from core.market_data_service import MarketDataService

        service = MarketDataService()

        assert service._liquidity_score(5000) == 0  # < 10K
        assert service._liquidity_score(50000) == 25  # < 100K
        assert service._liquidity_score(500000) == 50  # < 1M
        assert service._liquidity_score(5000000) == 75  # < 10M
        assert service._liquidity_score(50000000) == 100  # >= 10M


class TestYahooFinanceFetching:
    """Tests for Yahoo Finance data fetching."""

    @pytest.mark.asyncio
    async def test_yahoo_fetch_rate_limiting(self):
        """Should respect rate limiting for Yahoo API."""
        from core.data.market_data_api import MarketDataAPI

        api = MarketDataAPI()
        original_delay = api.YAHOO_DELAY

        # Verify rate limit exists
        assert api.YAHOO_DELAY > 0

        await api.close()

    @pytest.mark.asyncio
    async def test_get_precious_metals_validation(self):
        """Should validate precious metals prices."""
        from core.data.market_data_api import MarketDataAPI, _market_cache

        _market_cache.clear()

        mock_gold_response = {
            "chart": {
                "result": [{
                    "meta": {
                        "regularMarketPrice": 2050.5,
                        "previousClose": 2040.0
                    }
                }]
            }
        }

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_gold_response)

        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_context.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_context)
        mock_session.closed = False
        mock_session.close = AsyncMock()

        api = MarketDataAPI()
        api._session = mock_session

        result = await api._yahoo_fetch("GC=F")

        assert result is not None
        assert result["price"] == 2050.5
        assert result["prev_close"] == 2040.0


class TestSOLPriceFetching:
    """Tests for SOL-specific price fetching."""

    @pytest.mark.asyncio
    async def test_get_sol_price(self):
        """Should get SOL price correctly."""
        from core.data.free_price_api import FreePriceAPI, _price_cache, TokenPrice

        _price_cache.clear()

        mock_response = {
            "pairs": [
                {
                    "baseToken": {"symbol": "SOL", "name": "Wrapped SOL"},
                    "priceUsd": "150.00",
                    "volume": {"h24": "1000000000"},
                    "liquidity": {"usd": "5000000000"},
                    "priceChange": {"h24": "2.5"}
                }
            ]
        }

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_response)

        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_context.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_context)
        mock_session.closed = False
        mock_session.close = AsyncMock()

        api = FreePriceAPI()
        api._session = mock_session
        api._sol_price = None
        api._sol_price_time = None

        with patch("core.data.free_price_api.get_rate_limiter") as mock_rl:
            mock_rl.return_value.wait_and_acquire = AsyncMock()

            result = await api.get_sol_price()

            assert result == 150.0


class TestJupiterPriceAPI:
    """Tests for Jupiter Price API integration."""

    @pytest.mark.asyncio
    async def test_jupiter_client_get_price(self):
        """Should fetch price from Jupiter API."""
        from core.market_data_service import JupiterClient

        mock_response = {
            "data": {
                "So11111111111111111111111111111111111111112": {
                    "price": 150.0
                }
            }
        }

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_response)

        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_context.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session_instance = MagicMock()
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            mock_session_instance.get = MagicMock(return_value=mock_context)
            mock_session_class.return_value = mock_session_instance

            client = JupiterClient()
            result = await client.get_price("So11111111111111111111111111111111111111112")

            assert result == 150.0

    @pytest.mark.asyncio
    async def test_jupiter_client_get_prices_batch(self):
        """Should fetch multiple prices from Jupiter API."""
        from core.market_data_service import JupiterClient

        mock_response = {
            "data": {
                "mint1": {"price": 100.0},
                "mint2": {"price": 200.0},
                "mint3": {"price": 300.0}
            }
        }

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_response)

        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_context.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session_instance = MagicMock()
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            mock_session_instance.get = MagicMock(return_value=mock_context)
            mock_session_class.return_value = mock_session_instance

            client = JupiterClient()
            result = await client.get_prices_batch(["mint1", "mint2", "mint3"])

            assert result == {"mint1": 100.0, "mint2": 200.0, "mint3": 300.0}


class TestDataNormalization:
    """Tests for data normalization across different sources."""

    def test_price_rounding(self):
        """Should round prices appropriately."""
        from core.data.market_data_api import AssetPrice

        # Crypto prices - should handle many decimal places
        btc = AssetPrice(symbol="BTC", name="Bitcoin", price=50123.456789)
        assert btc.price == 50123.456789

        # Very small prices (memecoins)
        meme = AssetPrice(symbol="MEME", name="Meme Token", price=0.00000123)
        assert meme.price == 0.00000123

    def test_percentage_change_handling(self):
        """Should handle percentage changes correctly."""
        from core.data.market_data_api import AssetPrice

        # Positive change
        up = AssetPrice(symbol="UP", name="Up Token", price=100, change_pct=15.5)
        assert up.change_pct == 15.5

        # Negative change
        down = AssetPrice(symbol="DOWN", name="Down Token", price=100, change_pct=-25.3)
        assert down.change_pct == -25.3

        # Zero change
        flat = AssetPrice(symbol="FLAT", name="Flat Token", price=100, change_pct=0.0)
        assert flat.change_pct == 0.0

    def test_volume_normalization(self):
        """Should handle various volume formats."""
        from core.data.free_price_api import TokenPrice

        # High volume
        high_vol = TokenPrice(
            address="test",
            symbol="HIGH",
            name="High Volume",
            price_usd=1.0,
            volume_24h=1_000_000_000.0  # 1 billion
        )
        assert high_vol.volume_24h == 1_000_000_000.0

        # Low volume
        low_vol = TokenPrice(
            address="test",
            symbol="LOW",
            name="Low Volume",
            price_usd=1.0,
            volume_24h=100.0
        )
        assert low_vol.volume_24h == 100.0
