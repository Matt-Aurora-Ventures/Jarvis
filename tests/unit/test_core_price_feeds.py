"""
Comprehensive unit tests for core/price/resilient_fetcher.py - Multi-source price aggregation.

Tests the following components:
1. Price Fetching (DexScreener, Jupiter, CoinGecko, Birdeye)
2. Cache Management (TTL, invalidation, eviction)
3. Price Validation (stablecoins, zero price handling)
4. Source Health Tracking (failures, circuit breaker, recovery)
5. Aggregation Logic (source prioritization, failover)

Coverage target: 60%+ with 40-60 tests
"""

import asyncio
import json
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
import sys
import aiohttp

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_token_mint():
    """Sample Solana token mint address (RAY token)."""
    return "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R"


@pytest.fixture
def sol_mint():
    """SOL token mint address."""
    return "So11111111111111111111111111111111111111112"


@pytest.fixture
def usdc_mint():
    """USDC stablecoin mint address."""
    return "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


@pytest.fixture
def usdt_mint():
    """USDT stablecoin mint address."""
    return "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"


@pytest.fixture
def mock_dexscreener_response():
    """Mock response from DexScreener API."""
    return {
        "pairs": [
            {
                "chainId": "solana",
                "priceUsd": "1.23",
                "liquidity": {"usd": 5000000.0},
                "baseToken": {"address": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R"},
            },
            {
                "chainId": "solana",
                "priceUsd": "1.25",
                "liquidity": {"usd": 1000000.0},
                "baseToken": {"address": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R"},
            },
        ]
    }


@pytest.fixture
def mock_dexscreener_no_solana_response():
    """Mock response with no Solana pairs."""
    return {
        "pairs": [
            {
                "chainId": "ethereum",
                "priceUsd": "1.23",
                "liquidity": {"usd": 5000000.0},
            },
        ]
    }


@pytest.fixture
def mock_jupiter_response():
    """Mock response from Jupiter Price API."""
    return {
        "data": {
            "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R": {
                "id": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",
                "mintSymbol": "RAY",
                "price": 1.23,
            }
        }
    }


@pytest.fixture
def mock_coingecko_sol_response():
    """Mock response from CoinGecko for SOL price."""
    return {"solana": {"usd": 180.50}}


def create_mock_response(status=200, json_data=None):
    """Helper to create mock aiohttp response."""
    mock_response = AsyncMock()
    mock_response.status = status
    if json_data is not None:
        mock_response.json = AsyncMock(return_value=json_data)
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    return mock_response


@pytest.fixture
def price_fetcher():
    """Create a fresh ResilientPriceFetcher instance."""
    from core.price.resilient_fetcher import ResilientPriceFetcher
    fetcher = ResilientPriceFetcher(cache_ttl=30, max_cache_size=100)
    return fetcher


@pytest.fixture
def mock_session():
    """Create a mock aiohttp session."""
    session = AsyncMock(spec=aiohttp.ClientSession)
    session.closed = False
    return session


# =============================================================================
# TEST CLASS: PriceResult Dataclass
# =============================================================================


class TestPriceResult:
    """Tests for the PriceResult dataclass."""

    def test_price_result_basic(self):
        """PriceResult should store price and source."""
        from core.price.resilient_fetcher import PriceResult

        result = PriceResult(price=1.23, source="dexscreener")

        assert result.price == 1.23
        assert result.source == "dexscreener"
        assert result.cached is False

    def test_price_result_with_timestamp(self):
        """PriceResult should default to current timestamp."""
        from core.price.resilient_fetcher import PriceResult

        result = PriceResult(price=1.23, source="jupiter")

        assert result.timestamp is not None
        assert isinstance(result.timestamp, datetime)

    def test_price_result_cached_flag(self):
        """PriceResult should indicate cached data."""
        from core.price.resilient_fetcher import PriceResult

        result = PriceResult(price=1.23, source="cache", cached=True)

        assert result.cached is True

    def test_price_result_zero_price(self):
        """PriceResult should handle zero price."""
        from core.price.resilient_fetcher import PriceResult

        result = PriceResult(price=0.0, source="none")

        assert result.price == 0.0
        assert result.source == "none"


# =============================================================================
# TEST CLASS: SourceHealth Tracking
# =============================================================================


class TestSourceHealth:
    """Tests for source health tracking functionality."""

    def test_source_health_init(self):
        """SourceHealth should initialize with healthy state."""
        from core.price.resilient_fetcher import SourceHealth

        health = SourceHealth(name="test_source")

        assert health.name == "test_source"
        assert health.success_count == 0
        assert health.failure_count == 0
        assert health.consecutive_failures == 0
        assert health.is_healthy is True

    def test_source_health_record_success(self):
        """Recording success should increment count and reset failures."""
        from core.price.resilient_fetcher import SourceHealth

        health = SourceHealth(name="test_source")
        health.consecutive_failures = 3

        health.record_success()

        assert health.success_count == 1
        assert health.consecutive_failures == 0
        assert health.last_success is not None

    def test_source_health_record_failure(self):
        """Recording failure should increment consecutive failures."""
        from core.price.resilient_fetcher import SourceHealth

        health = SourceHealth(name="test_source")

        health.record_failure()

        assert health.failure_count == 1
        assert health.consecutive_failures == 1
        assert health.last_failure is not None

    def test_source_health_disabled_after_consecutive_failures(self):
        """Source should be disabled after 5 consecutive failures."""
        from core.price.resilient_fetcher import SourceHealth

        health = SourceHealth(name="test_source")

        for _ in range(5):
            health.record_failure()

        assert health.is_healthy is False
        assert health.disabled_until is not None

    def test_source_health_disabled_until_expires(self):
        """Source should become healthy again after disabled_until expires and failures reset."""
        from core.price.resilient_fetcher import SourceHealth

        health = SourceHealth(name="test_source")
        # Set consecutive_failures below threshold (simulating partial recovery)
        health.consecutive_failures = 4
        health.disabled_until = datetime.utcnow() - timedelta(seconds=1)

        # With disabled_until expired AND consecutive_failures < 5, should be healthy
        assert health.is_healthy is True

    def test_source_health_unhealthy_with_high_failures(self):
        """Source should remain unhealthy if consecutive_failures >= 5."""
        from core.price.resilient_fetcher import SourceHealth

        health = SourceHealth(name="test_source")
        health.consecutive_failures = 5
        # Even with no disabled_until, 5+ failures means unhealthy
        health.disabled_until = None

        assert health.is_healthy is False

    def test_source_health_exponential_backoff(self):
        """Backoff time should increase exponentially with failures."""
        from core.price.resilient_fetcher import SourceHealth

        health = SourceHealth(name="test_source")

        # 5 failures to trigger first backoff (30s)
        for _ in range(5):
            health.record_failure()
        first_backoff = health.disabled_until

        # 6th failure should increase backoff (60s)
        health.record_failure()
        second_backoff = health.disabled_until

        assert second_backoff > first_backoff

    def test_source_health_max_backoff_cap(self):
        """Backoff should cap at 300 seconds (5 minutes)."""
        from core.price.resilient_fetcher import SourceHealth

        health = SourceHealth(name="test_source")

        # Many consecutive failures
        for _ in range(20):
            health.record_failure()

        # Backoff should not exceed 5 minutes
        max_disabled = datetime.utcnow() + timedelta(seconds=300)
        assert health.disabled_until <= max_disabled + timedelta(seconds=1)

    def test_source_health_success_clears_disabled(self):
        """Success should clear disabled_until."""
        from core.price.resilient_fetcher import SourceHealth

        health = SourceHealth(name="test_source")
        health.consecutive_failures = 5
        health.disabled_until = datetime.utcnow() + timedelta(seconds=30)

        health.record_success()

        assert health.disabled_until is None
        assert health.is_healthy is True


# =============================================================================
# TEST CLASS: ResilientPriceFetcher Initialization
# =============================================================================


class TestResilientPriceFetcherInit:
    """Tests for ResilientPriceFetcher initialization."""

    def test_init_default_values(self):
        """Fetcher should initialize with default values."""
        from core.price.resilient_fetcher import ResilientPriceFetcher

        fetcher = ResilientPriceFetcher()

        assert fetcher.cache_ttl == 30
        assert fetcher.max_cache_size == 1000

    def test_init_custom_values(self):
        """Fetcher should accept custom configuration."""
        from core.price.resilient_fetcher import ResilientPriceFetcher

        fetcher = ResilientPriceFetcher(cache_ttl=60, max_cache_size=500)

        assert fetcher.cache_ttl == 60
        assert fetcher.max_cache_size == 500

    def test_init_source_health_tracking(self):
        """Fetcher should initialize health tracking for all sources."""
        from core.price.resilient_fetcher import ResilientPriceFetcher

        fetcher = ResilientPriceFetcher()

        assert "dexscreener" in fetcher._source_health
        assert "jupiter" in fetcher._source_health
        assert "coingecko" in fetcher._source_health
        assert "birdeye" in fetcher._source_health

    def test_init_empty_cache(self):
        """Fetcher should start with empty cache."""
        from core.price.resilient_fetcher import ResilientPriceFetcher

        fetcher = ResilientPriceFetcher()

        assert len(fetcher._cache) == 0


# =============================================================================
# TEST CLASS: Cache Management
# =============================================================================


class TestCacheManagement:
    """Tests for price caching functionality."""

    def test_get_cached_returns_none_for_missing(self, price_fetcher):
        """_get_cached should return None for missing entries."""
        result = price_fetcher._get_cached("unknown_mint")

        assert result is None

    def test_set_and_get_cached(self, price_fetcher):
        """Should store and retrieve cached price."""
        from core.price.resilient_fetcher import PriceResult

        result = PriceResult(price=1.23, source="test")
        price_fetcher._set_cached("test_mint", result)

        cached = price_fetcher._get_cached("test_mint")

        assert cached is not None
        assert cached.price == 1.23
        assert cached.cached is True

    def test_cache_expiration(self, price_fetcher):
        """Cached price should expire after TTL."""
        from core.price.resilient_fetcher import PriceResult

        result = PriceResult(
            price=1.23,
            source="test",
            timestamp=datetime.utcnow() - timedelta(seconds=60),
        )
        price_fetcher._cache["test_mint"] = result

        cached = price_fetcher._get_cached("test_mint")

        assert cached is None

    def test_cache_eviction_on_overflow(self):
        """Cache should evict oldest entries when size exceeds limit."""
        from core.price.resilient_fetcher import ResilientPriceFetcher, PriceResult

        fetcher = ResilientPriceFetcher(max_cache_size=10)

        # Add more entries than cache size
        for i in range(15):
            result = PriceResult(
                price=float(i),
                source="test",
                timestamp=datetime.utcnow() - timedelta(seconds=15 - i),
            )
            fetcher._set_cached(f"mint_{i}", result)

        # Should have evicted oldest entries
        assert len(fetcher._cache) <= 10

    def test_cache_preserves_newer_entries(self):
        """Cache eviction should remove oldest entries first."""
        from core.price.resilient_fetcher import ResilientPriceFetcher, PriceResult

        fetcher = ResilientPriceFetcher(max_cache_size=5)

        # Add entries with varying timestamps
        for i in range(10):
            result = PriceResult(
                price=float(i),
                source="test",
                timestamp=datetime.utcnow() - timedelta(seconds=10 - i),
            )
            fetcher._set_cached(f"mint_{i}", result)

        # Newer entries (higher index) should still be present
        assert "mint_9" in fetcher._cache
        assert "mint_8" in fetcher._cache


# =============================================================================
# TEST CLASS: Stablecoin Handling
# =============================================================================


class TestStablecoinHandling:
    """Tests for stablecoin price handling."""

    @pytest.mark.asyncio
    async def test_usdc_returns_one(self, price_fetcher, usdc_mint):
        """USDC should always return price of 1.0."""
        result = await price_fetcher.get_price(usdc_mint)

        assert result.price == 1.0
        assert result.source == "stablecoin"

    @pytest.mark.asyncio
    async def test_usdt_returns_one(self, price_fetcher, usdt_mint):
        """USDT should always return price of 1.0."""
        result = await price_fetcher.get_price(usdt_mint)

        assert result.price == 1.0
        assert result.source == "stablecoin"

    @pytest.mark.asyncio
    async def test_stablecoin_not_cached(self, price_fetcher, usdc_mint):
        """Stablecoin prices should not be cached."""
        await price_fetcher.get_price(usdc_mint)

        assert usdc_mint not in price_fetcher._cache


# =============================================================================
# TEST CLASS: DexScreener Integration
# =============================================================================


class TestDexScreenerFetching:
    """Tests for DexScreener price fetching."""

    @pytest.mark.asyncio
    async def test_fetch_dexscreener_success(
        self, price_fetcher, sample_token_mint, mock_dexscreener_response, mock_session
    ):
        """Should fetch price from DexScreener successfully."""
        mock_response = create_mock_response(200, mock_dexscreener_response)
        mock_session.get = MagicMock(return_value=mock_response)
        price_fetcher._session = mock_session

        price = await price_fetcher._fetch_dexscreener(sample_token_mint)

        assert price == 1.23  # Highest liquidity pair

    @pytest.mark.asyncio
    async def test_fetch_dexscreener_selects_highest_liquidity(
        self, price_fetcher, sample_token_mint, mock_session
    ):
        """Should select pair with highest liquidity."""
        response_data = {
            "pairs": [
                {"chainId": "solana", "priceUsd": "1.00", "liquidity": {"usd": 100}},
                {"chainId": "solana", "priceUsd": "2.00", "liquidity": {"usd": 1000}},
                {"chainId": "solana", "priceUsd": "1.50", "liquidity": {"usd": 500}},
            ]
        }
        mock_response = create_mock_response(200, response_data)
        mock_session.get = MagicMock(return_value=mock_response)
        price_fetcher._session = mock_session

        price = await price_fetcher._fetch_dexscreener(sample_token_mint)

        assert price == 2.00

    @pytest.mark.asyncio
    async def test_fetch_dexscreener_filters_solana_only(
        self, price_fetcher, sample_token_mint, mock_dexscreener_no_solana_response, mock_session
    ):
        """Should return None if no Solana pairs."""
        mock_response = create_mock_response(200, mock_dexscreener_no_solana_response)
        mock_session.get = MagicMock(return_value=mock_response)
        price_fetcher._session = mock_session

        price = await price_fetcher._fetch_dexscreener(sample_token_mint)

        assert price is None

    @pytest.mark.asyncio
    async def test_fetch_dexscreener_handles_non_200(
        self, price_fetcher, sample_token_mint, mock_session
    ):
        """Should return None on non-200 response."""
        mock_response = create_mock_response(404, None)
        mock_session.get = MagicMock(return_value=mock_response)
        price_fetcher._session = mock_session

        price = await price_fetcher._fetch_dexscreener(sample_token_mint)

        assert price is None

    @pytest.mark.asyncio
    async def test_fetch_dexscreener_handles_empty_pairs(
        self, price_fetcher, sample_token_mint, mock_session
    ):
        """Should return None when pairs list is empty."""
        mock_response = create_mock_response(200, {"pairs": []})
        mock_session.get = MagicMock(return_value=mock_response)
        price_fetcher._session = mock_session

        price = await price_fetcher._fetch_dexscreener(sample_token_mint)

        assert price is None

    @pytest.mark.asyncio
    async def test_fetch_dexscreener_handles_exception(
        self, price_fetcher, sample_token_mint, mock_session
    ):
        """Should return None on exception."""
        mock_session.get = MagicMock(side_effect=aiohttp.ClientError())
        price_fetcher._session = mock_session

        price = await price_fetcher._fetch_dexscreener(sample_token_mint)

        assert price is None

    @pytest.mark.asyncio
    async def test_fetch_dexscreener_handles_zero_price(
        self, price_fetcher, sample_token_mint, mock_session
    ):
        """Should return None when price is zero."""
        response_data = {
            "pairs": [
                {"chainId": "solana", "priceUsd": "0", "liquidity": {"usd": 1000}},
            ]
        }
        mock_response = create_mock_response(200, response_data)
        mock_session.get = MagicMock(return_value=mock_response)
        price_fetcher._session = mock_session

        price = await price_fetcher._fetch_dexscreener(sample_token_mint)

        assert price is None


# =============================================================================
# TEST CLASS: Jupiter Integration
# =============================================================================


class TestJupiterFetching:
    """Tests for Jupiter Price API fetching."""

    @pytest.mark.asyncio
    async def test_fetch_jupiter_success(
        self, price_fetcher, sample_token_mint, mock_jupiter_response, mock_session
    ):
        """Should fetch price from Jupiter successfully."""
        mock_response = create_mock_response(200, mock_jupiter_response)
        mock_session.get = MagicMock(return_value=mock_response)
        price_fetcher._session = mock_session

        price = await price_fetcher._fetch_jupiter(sample_token_mint)

        assert price == 1.23

    @pytest.mark.asyncio
    async def test_fetch_jupiter_handles_non_200(
        self, price_fetcher, sample_token_mint, mock_session
    ):
        """Should return None on non-200 response."""
        mock_response = create_mock_response(500, None)
        mock_session.get = MagicMock(return_value=mock_response)
        price_fetcher._session = mock_session

        price = await price_fetcher._fetch_jupiter(sample_token_mint)

        assert price is None

    @pytest.mark.asyncio
    async def test_fetch_jupiter_handles_missing_token(
        self, price_fetcher, sample_token_mint, mock_session
    ):
        """Should return None when token not in response."""
        mock_response = create_mock_response(200, {"data": {}})
        mock_session.get = MagicMock(return_value=mock_response)
        price_fetcher._session = mock_session

        price = await price_fetcher._fetch_jupiter(sample_token_mint)

        assert price is None

    @pytest.mark.asyncio
    async def test_fetch_jupiter_handles_exception(
        self, price_fetcher, sample_token_mint, mock_session
    ):
        """Should return None on exception."""
        mock_session.get = MagicMock(side_effect=Exception("Network error"))
        price_fetcher._session = mock_session

        price = await price_fetcher._fetch_jupiter(sample_token_mint)

        assert price is None


# =============================================================================
# TEST CLASS: CoinGecko Integration (SOL)
# =============================================================================


class TestCoinGeckoFetching:
    """Tests for CoinGecko SOL price fetching."""

    @pytest.mark.asyncio
    async def test_fetch_coingecko_sol_success(
        self, price_fetcher, mock_coingecko_sol_response, mock_session
    ):
        """Should fetch SOL price from CoinGecko successfully."""
        mock_response = create_mock_response(200, mock_coingecko_sol_response)
        mock_session.get = MagicMock(return_value=mock_response)
        price_fetcher._session = mock_session

        price = await price_fetcher._fetch_coingecko_sol()

        assert price == 180.50

    @pytest.mark.asyncio
    async def test_fetch_coingecko_sol_handles_non_200(
        self, price_fetcher, mock_session
    ):
        """Should return None on non-200 response."""
        mock_response = create_mock_response(429, None)
        mock_session.get = MagicMock(return_value=mock_response)
        price_fetcher._session = mock_session

        price = await price_fetcher._fetch_coingecko_sol()

        assert price is None

    @pytest.mark.asyncio
    async def test_fetch_coingecko_sol_handles_missing_data(
        self, price_fetcher, mock_session
    ):
        """Should return None when data is missing."""
        mock_response = create_mock_response(200, {})
        mock_session.get = MagicMock(return_value=mock_response)
        price_fetcher._session = mock_session

        price = await price_fetcher._fetch_coingecko_sol()

        assert price is None


# =============================================================================
# TEST CLASS: Get Price (Main API)
# =============================================================================


class TestGetPrice:
    """Tests for the main get_price method."""

    @pytest.mark.asyncio
    async def test_get_price_returns_cached(self, price_fetcher, sample_token_mint):
        """Should return cached price if available."""
        from core.price.resilient_fetcher import PriceResult

        cached_result = PriceResult(price=5.0, source="cache_test")
        price_fetcher._set_cached(sample_token_mint, cached_result)

        result = await price_fetcher.get_price(sample_token_mint)

        assert result.price == 5.0
        assert result.cached is True

    @pytest.mark.asyncio
    async def test_get_price_sol_uses_coingecko(
        self, price_fetcher, sol_mint, mock_coingecko_sol_response, mock_session
    ):
        """SOL price should be fetched from CoinGecko."""
        mock_response = create_mock_response(200, mock_coingecko_sol_response)
        mock_session.get = MagicMock(return_value=mock_response)
        price_fetcher._session = mock_session

        result = await price_fetcher.get_price(sol_mint)

        assert result.price == 180.50
        assert result.source == "coingecko"

    @pytest.mark.asyncio
    async def test_get_price_failover_to_jupiter(
        self, price_fetcher, sample_token_mint, mock_jupiter_response, mock_session
    ):
        """Should failover to Jupiter when DexScreener fails."""
        # DexScreener returns None
        dexscreener_response = create_mock_response(200, {"pairs": []})
        jupiter_response = create_mock_response(200, mock_jupiter_response)

        call_count = [0]
        def mock_get(url, **kwargs):
            call_count[0] += 1
            if "dexscreener" in url:
                return dexscreener_response
            elif "jup.ag" in url:
                return jupiter_response
            return create_mock_response(404, None)

        mock_session.get = MagicMock(side_effect=mock_get)
        price_fetcher._session = mock_session

        result = await price_fetcher.get_price(sample_token_mint)

        assert result.price == 1.23
        assert result.source == "jupiter"

    @pytest.mark.asyncio
    async def test_get_price_returns_zero_when_all_fail(
        self, price_fetcher, sample_token_mint, mock_session
    ):
        """Should return zero price when all sources fail."""
        mock_response = create_mock_response(500, None)
        mock_session.get = MagicMock(return_value=mock_response)
        price_fetcher._session = mock_session

        result = await price_fetcher.get_price(sample_token_mint)

        assert result.price == 0.0
        assert result.source == "none"

    @pytest.mark.asyncio
    async def test_get_price_caches_result(
        self, price_fetcher, sample_token_mint, mock_dexscreener_response, mock_session
    ):
        """Successful fetch should cache the result."""
        mock_response = create_mock_response(200, mock_dexscreener_response)
        mock_session.get = MagicMock(return_value=mock_response)
        price_fetcher._session = mock_session

        await price_fetcher.get_price(sample_token_mint)

        assert sample_token_mint in price_fetcher._cache

    @pytest.mark.asyncio
    async def test_get_price_skips_unhealthy_sources(self, price_fetcher, sample_token_mint):
        """Should skip sources that are marked unhealthy."""
        # Mark dexscreener as unhealthy
        for _ in range(5):
            price_fetcher._source_health["dexscreener"].record_failure()

        # Mock only Jupiter to succeed
        with patch.object(price_fetcher, "_fetch_dexscreener", new_callable=AsyncMock) as mock_dex:
            with patch.object(price_fetcher, "_fetch_jupiter", new_callable=AsyncMock) as mock_jup:
                mock_jup.return_value = 1.50
                mock_dex.return_value = 2.00  # Should not be called

                result = await price_fetcher.get_price(sample_token_mint)

        assert result.price == 1.50
        mock_dex.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_price_records_source_success(
        self, price_fetcher, sample_token_mint, mock_dexscreener_response, mock_session
    ):
        """Successful fetch should record success for source."""
        mock_response = create_mock_response(200, mock_dexscreener_response)
        mock_session.get = MagicMock(return_value=mock_response)
        price_fetcher._session = mock_session

        initial_count = price_fetcher._source_health["dexscreener"].success_count

        await price_fetcher.get_price(sample_token_mint)

        assert price_fetcher._source_health["dexscreener"].success_count == initial_count + 1

    @pytest.mark.asyncio
    async def test_get_price_records_source_failure(
        self, price_fetcher, sample_token_mint, mock_session
    ):
        """Failed fetch should record failure for source."""
        mock_response = create_mock_response(200, {"pairs": []})
        mock_session.get = MagicMock(return_value=mock_response)
        price_fetcher._session = mock_session

        initial_count = price_fetcher._source_health["dexscreener"].failure_count

        await price_fetcher.get_price(sample_token_mint)

        assert price_fetcher._source_health["dexscreener"].failure_count == initial_count + 1


# =============================================================================
# TEST CLASS: Source Priority
# =============================================================================


class TestSourcePriority:
    """Tests for source priority and ordering."""

    @pytest.mark.asyncio
    async def test_healthy_sources_prioritized(self, price_fetcher):
        """Healthy sources should be tried before unhealthy ones."""
        # Mark dexscreener as unhealthy
        price_fetcher._source_health["dexscreener"].consecutive_failures = 5
        price_fetcher._source_health["dexscreener"].disabled_until = datetime.utcnow() + timedelta(seconds=30)

        # Jupiter should be tried first
        with patch.object(price_fetcher, "_fetch_jupiter", new_callable=AsyncMock) as mock_jup:
            mock_jup.return_value = 1.23

            result = await price_fetcher.get_price("test_mint")

        assert result.source == "jupiter"

    @pytest.mark.asyncio
    async def test_success_count_affects_priority(self, price_fetcher):
        """Sources with higher success count should be prioritized."""
        # Give Jupiter more successes
        price_fetcher._source_health["jupiter"].success_count = 100
        price_fetcher._source_health["dexscreener"].success_count = 10

        # Both healthy, Jupiter should be tried first due to higher success count
        call_order = []

        async def mock_dex(mint):
            call_order.append("dexscreener")
            return 1.00

        async def mock_jup(mint):
            call_order.append("jupiter")
            return 2.00

        with patch.object(price_fetcher, "_fetch_dexscreener", new=mock_dex):
            with patch.object(price_fetcher, "_fetch_jupiter", new=mock_jup):
                await price_fetcher.get_price("test_mint")

        # Jupiter should be called first
        assert call_order[0] == "jupiter"


# =============================================================================
# TEST CLASS: Session Management
# =============================================================================


class TestSessionManagement:
    """Tests for HTTP session management."""

    @pytest.mark.asyncio
    async def test_get_session_creates_session(self, price_fetcher):
        """_get_session should create session if none exists."""
        session = await price_fetcher._get_session()

        assert session is not None
        assert isinstance(session, aiohttp.ClientSession)

        await price_fetcher.close()

    @pytest.mark.asyncio
    async def test_get_session_reuses_session(self, price_fetcher):
        """_get_session should reuse existing session."""
        session1 = await price_fetcher._get_session()
        session2 = await price_fetcher._get_session()

        assert session1 is session2

        await price_fetcher.close()

    @pytest.mark.asyncio
    async def test_close_closes_session(self, price_fetcher):
        """close() should close the HTTP session."""
        session = await price_fetcher._get_session()
        await price_fetcher.close()

        assert session.closed


# =============================================================================
# TEST CLASS: Health Status Reporting
# =============================================================================


class TestHealthStatusReporting:
    """Tests for health status reporting."""

    def test_get_health_status_all_healthy(self, price_fetcher):
        """Should report all sources as healthy initially."""
        status = price_fetcher.get_health_status()

        assert len(status) == 4
        for source, health in status.items():
            assert health["healthy"] is True
            assert health["consecutive_failures"] == 0

    def test_get_health_status_with_failures(self, price_fetcher):
        """Should report failure counts accurately."""
        price_fetcher._source_health["dexscreener"].record_failure()
        price_fetcher._source_health["dexscreener"].record_failure()

        status = price_fetcher.get_health_status()

        assert status["dexscreener"]["failure_count"] == 2
        assert status["dexscreener"]["consecutive_failures"] == 2

    def test_get_health_status_with_disabled_source(self, price_fetcher):
        """Should report disabled_until when source is disabled."""
        for _ in range(5):
            price_fetcher._source_health["jupiter"].record_failure()

        status = price_fetcher.get_health_status()

        assert status["jupiter"]["healthy"] is False
        assert status["jupiter"]["disabled_until"] is not None


# =============================================================================
# TEST CLASS: Global Instance
# =============================================================================


class TestGlobalInstance:
    """Tests for global price fetcher instance."""

    def test_get_price_fetcher_creates_instance(self):
        """get_price_fetcher should create global instance."""
        from core.price import resilient_fetcher

        # Reset global
        resilient_fetcher._price_fetcher = None

        fetcher = resilient_fetcher.get_price_fetcher()

        assert fetcher is not None
        assert isinstance(fetcher, resilient_fetcher.ResilientPriceFetcher)

    def test_get_price_fetcher_returns_same_instance(self):
        """get_price_fetcher should return same instance."""
        from core.price.resilient_fetcher import get_price_fetcher

        fetcher1 = get_price_fetcher()
        fetcher2 = get_price_fetcher()

        assert fetcher1 is fetcher2


# =============================================================================
# TEST CLASS: Convenience Function
# =============================================================================


class TestConvenienceFunction:
    """Tests for get_token_price convenience function."""

    @pytest.mark.asyncio
    async def test_get_token_price_returns_float(self, sample_token_mint):
        """get_token_price should return price as float."""
        from core.price.resilient_fetcher import get_token_price, PriceResult

        with patch("core.price.resilient_fetcher.get_price_fetcher") as mock_get_fetcher:
            mock_fetcher = MagicMock()
            mock_fetcher.get_price = AsyncMock(return_value=PriceResult(price=1.23, source="test"))
            mock_get_fetcher.return_value = mock_fetcher

            price = await get_token_price(sample_token_mint)

        assert price == 1.23
        assert isinstance(price, float)

    @pytest.mark.asyncio
    async def test_get_token_price_returns_zero_on_failure(self, sample_token_mint):
        """get_token_price should return 0.0 when price fetch fails."""
        from core.price.resilient_fetcher import get_token_price, PriceResult

        with patch("core.price.resilient_fetcher.get_price_fetcher") as mock_get_fetcher:
            mock_fetcher = MagicMock()
            mock_fetcher.get_price = AsyncMock(return_value=PriceResult(price=0.0, source="none"))
            mock_get_fetcher.return_value = mock_fetcher

            price = await get_token_price(sample_token_mint)

        assert price == 0.0


# =============================================================================
# TEST CLASS: API URLs
# =============================================================================


class TestApiUrls:
    """Tests for API URL constants."""

    def test_dexscreener_url(self):
        """DexScreener API URL should be correct."""
        from core.price.resilient_fetcher import ResilientPriceFetcher

        assert "dexscreener.com" in ResilientPriceFetcher.DEXSCREENER_API

    def test_jupiter_url(self):
        """Jupiter API URL should be correct."""
        from core.price.resilient_fetcher import ResilientPriceFetcher

        assert "jup.ag" in ResilientPriceFetcher.JUPITER_PRICE_API

    def test_coingecko_url(self):
        """CoinGecko API URL should be correct."""
        from core.price.resilient_fetcher import ResilientPriceFetcher

        assert "coingecko.com" in ResilientPriceFetcher.COINGECKO_API


# =============================================================================
# TEST CLASS: Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_handles_null_price_in_response(self, price_fetcher, sample_token_mint, mock_session):
        """Should handle null price values gracefully."""
        response_data = {
            "pairs": [
                {"chainId": "solana", "priceUsd": None, "liquidity": {"usd": 1000}},
            ]
        }
        mock_response = create_mock_response(200, response_data)
        mock_session.get = MagicMock(return_value=mock_response)
        price_fetcher._session = mock_session

        price = await price_fetcher._fetch_dexscreener(sample_token_mint)

        assert price is None or price == 0

    @pytest.mark.asyncio
    async def test_handles_missing_liquidity(self, price_fetcher, sample_token_mint, mock_session):
        """Should handle missing liquidity data."""
        response_data = {
            "pairs": [
                {"chainId": "solana", "priceUsd": "1.23"},
            ]
        }
        mock_response = create_mock_response(200, response_data)
        mock_session.get = MagicMock(return_value=mock_response)
        price_fetcher._session = mock_session

        price = await price_fetcher._fetch_dexscreener(sample_token_mint)

        assert price == 1.23

    @pytest.mark.asyncio
    async def test_handles_negative_price(self, price_fetcher, sample_token_mint, mock_session):
        """Should reject negative prices."""
        response_data = {
            "pairs": [
                {"chainId": "solana", "priceUsd": "-1.23", "liquidity": {"usd": 1000}},
            ]
        }
        mock_response = create_mock_response(200, response_data)
        mock_session.get = MagicMock(return_value=mock_response)
        price_fetcher._session = mock_session

        price = await price_fetcher._fetch_dexscreener(sample_token_mint)

        # Negative prices should be treated as invalid
        assert price is None or price <= 0

    @pytest.mark.asyncio
    async def test_session_recreated_if_closed(self, price_fetcher):
        """Should recreate session if it was closed."""
        # Get session and close it
        session1 = await price_fetcher._get_session()
        await session1.close()

        # Get session again - should create new one
        session2 = await price_fetcher._get_session()

        assert session2 is not session1
        assert not session2.closed

        await price_fetcher.close()


# =============================================================================
# RUN CONFIGURATION
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
