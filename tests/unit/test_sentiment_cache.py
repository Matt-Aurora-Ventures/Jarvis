"""
Tests for sentiment analysis caching.

Tests:
- Token sentiment caching with TTL
- Market regime caching
- Grok analysis caching (expensive calls)
- Cache invalidation strategies
- Hit rate metrics
- Batch operations
"""

import asyncio
import pytest
import time
from unittest.mock import MagicMock, patch

from core.caching.sentiment_cache import (
    SentimentCache,
    SentimentCacheConfig,
    get_sentiment_cache,
)
from core.caching.cache_manager import MultiLevelCache


@pytest.fixture
def cache_config():
    """Test configuration with short TTLs."""
    return SentimentCacheConfig(
        token_sentiment_ttl_seconds=2,
        token_sentiment_min_ttl=1,  # Allow short TTLs for testing
        token_sentiment_max_ttl=3600,
        market_regime_ttl_seconds=3,
        grok_scores_ttl_seconds=2,
        traditional_markets_ttl_seconds=3,
        macro_analysis_ttl_seconds=5,
    )


@pytest.fixture
def sentiment_cache(cache_config):
    """Create a fresh sentiment cache for each test."""
    # Use in-memory only cache for tests
    multi_cache = MultiLevelCache(enable_file=False)
    cache = SentimentCache(config=cache_config, cache=multi_cache)
    cache.reset_metrics()
    return cache


@pytest.fixture
def sample_token_sentiment():
    """Sample token sentiment data."""
    return {
        "symbol": "SOL",
        "score": 75,
        "verdict": "BULLISH",
        "reason": "Strong fundamentals and momentum",
        "price": 100.50,
        "volume_24h": 1_000_000,
    }


@pytest.fixture
def sample_market_regime():
    """Sample market regime data."""
    return {
        "btc_trend": "BULLISH",
        "sol_trend": "BULLISH",
        "btc_change_24h": 5.2,
        "sol_change_24h": 8.1,
        "risk_level": "NORMAL",
        "regime": "BULL",
    }


# =============================================================================
# TOKEN SENTIMENT TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_token_sentiment_cache_set_get(sentiment_cache, sample_token_sentiment):
    """Test basic token sentiment caching."""
    # Set cache
    result = await sentiment_cache.set_token_sentiment("SOL", sample_token_sentiment)
    assert result is True

    # Get cached value
    cached = await sentiment_cache.get_token_sentiment("SOL")
    assert cached is not None
    assert cached["symbol"] == "SOL"
    assert cached["score"] == 75
    assert "_cached_at" in cached


@pytest.mark.asyncio
async def test_token_sentiment_cache_miss(sentiment_cache):
    """Test cache miss for non-existent token."""
    cached = await sentiment_cache.get_token_sentiment("BONK")
    assert cached is None


@pytest.mark.asyncio
async def test_token_sentiment_ttl_expiration(sentiment_cache, sample_token_sentiment):
    """Test that token sentiment expires after TTL."""
    # Cache with 2 second TTL (from fixture config)
    await sentiment_cache.set_token_sentiment("SOL", sample_token_sentiment)

    # Should be cached immediately
    cached = await sentiment_cache.get_token_sentiment("SOL")
    assert cached is not None

    # Wait for expiration
    await asyncio.sleep(2.5)

    # Should be expired
    cached = await sentiment_cache.get_token_sentiment("SOL")
    assert cached is None


@pytest.mark.asyncio
async def test_token_sentiment_custom_ttl(sentiment_cache, sample_token_sentiment):
    """Test custom TTL for token sentiment."""
    # Set with 1 minute custom TTL
    await sentiment_cache.set_token_sentiment("SOL", sample_token_sentiment, ttl_minutes=1)

    cached = await sentiment_cache.get_token_sentiment("SOL")
    assert cached is not None
    assert cached["_ttl"] == 60  # 1 minute in seconds


@pytest.mark.asyncio
async def test_batch_token_sentiment(sentiment_cache):
    """Test batch operations for token sentiment."""
    sentiments = {
        "SOL": {"symbol": "SOL", "score": 75},
        "BONK": {"symbol": "BONK", "score": 45},
        "WIF": {"symbol": "WIF", "score": -20},
    }

    # Set batch
    await sentiment_cache.set_batch_token_sentiment(sentiments)

    # Get batch
    cached = await sentiment_cache.get_batch_token_sentiment(["SOL", "BONK", "WIF", "MISSING"])

    assert cached["SOL"]["score"] == 75
    assert cached["BONK"]["score"] == 45
    assert cached["WIF"]["score"] == -20
    assert cached["MISSING"] is None


# =============================================================================
# MARKET REGIME TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_market_regime_cache(sentiment_cache, sample_market_regime):
    """Test market regime caching."""
    # Set cache
    result = await sentiment_cache.set_market_regime(sample_market_regime)
    assert result is True

    # Get cached value
    cached = await sentiment_cache.get_market_regime()
    assert cached is not None
    assert cached["regime"] == "BULL"
    assert cached["btc_trend"] == "BULLISH"
    assert "_cached_at" in cached


@pytest.mark.asyncio
async def test_market_regime_ttl(sentiment_cache, sample_market_regime):
    """Test market regime TTL expiration."""
    # Cache with 3 second TTL
    await sentiment_cache.set_market_regime(sample_market_regime)

    # Should be cached
    cached = await sentiment_cache.get_market_regime()
    assert cached is not None

    # Wait for expiration
    await asyncio.sleep(3.5)

    # Should be expired
    cached = await sentiment_cache.get_market_regime()
    assert cached is None


# =============================================================================
# GROK ANALYSIS TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_grok_scores_cache(sentiment_cache):
    """Test Grok scores caching (expensive calls)."""
    tokens_hash = "abc123def456"
    grok_data = {
        "scores": {"SOL": 75, "BONK": 45},
        "verdicts": {"SOL": "BULLISH", "BONK": "NEUTRAL"},
    }

    # Set cache
    result = await sentiment_cache.set_grok_scores(tokens_hash, grok_data)
    assert result is True

    # Get cached value
    cached = await sentiment_cache.get_grok_scores(tokens_hash)
    assert cached is not None
    assert cached["scores"]["SOL"] == 75
    assert "_cached_at" in cached


@pytest.mark.asyncio
async def test_grok_summary_cache(sentiment_cache):
    """Test Grok summary caching."""
    context_hash = "xyz789abc"
    summary = "Market shows bullish momentum with strong BTC support at $50K."

    # Set cache
    result = await sentiment_cache.set_grok_summary(context_hash, summary)
    assert result is True

    # Get cached value
    cached = await sentiment_cache.get_grok_summary(context_hash)
    assert cached is not None
    assert cached["summary"] == summary


@pytest.mark.asyncio
async def test_grok_cache_different_hashes(sentiment_cache):
    """Test that different token lists get different cache entries."""
    hash1 = "hash1"
    hash2 = "hash2"

    data1 = {"scores": {"SOL": 75}}
    data2 = {"scores": {"BONK": 45}}

    await sentiment_cache.set_grok_scores(hash1, data1)
    await sentiment_cache.set_grok_scores(hash2, data2)

    cached1 = await sentiment_cache.get_grok_scores(hash1)
    cached2 = await sentiment_cache.get_grok_scores(hash2)

    assert cached1["scores"]["SOL"] == 75
    assert cached2["scores"]["BONK"] == 45


# =============================================================================
# TRADITIONAL MARKETS & MACRO TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_traditional_markets_cache(sentiment_cache):
    """Test traditional markets caching."""
    markets_data = {
        "dxy_sentiment": "BULLISH",
        "stocks_sentiment": "NEUTRAL",
        "next_24h": "Expecting consolidation",
    }

    await sentiment_cache.set_traditional_markets(markets_data)
    cached = await sentiment_cache.get_traditional_markets()

    assert cached is not None
    assert cached["dxy_sentiment"] == "BULLISH"


@pytest.mark.asyncio
async def test_macro_analysis_cache(sentiment_cache):
    """Test macro analysis caching."""
    macro_data = {
        "short_term": "Fed meeting tomorrow",
        "medium_term": "CPI data next week",
        "key_events": ["FOMC", "CPI", "NFP"],
    }

    await sentiment_cache.set_macro_analysis(macro_data)
    cached = await sentiment_cache.get_macro_analysis()

    assert cached is not None
    assert "FOMC" in cached["key_events"]


# =============================================================================
# CACHE INVALIDATION TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_invalidate_single_token(sentiment_cache, sample_token_sentiment):
    """Test invalidating a single token."""
    # Cache token
    await sentiment_cache.set_token_sentiment("SOL", sample_token_sentiment)
    assert await sentiment_cache.get_token_sentiment("SOL") is not None

    # Invalidate
    result = sentiment_cache.invalidate_token("SOL")
    assert result is True

    # Should be gone
    cached = await sentiment_cache.get_token_sentiment("SOL")
    assert cached is None


@pytest.mark.asyncio
async def test_invalidate_all_tokens(sentiment_cache):
    """Test invalidating all token caches."""
    # Cache multiple tokens
    await sentiment_cache.set_token_sentiment("SOL", {"score": 75})
    await sentiment_cache.set_token_sentiment("BONK", {"score": 45})
    await sentiment_cache.set_token_sentiment("WIF", {"score": -20})

    # Invalidate all
    count = sentiment_cache.invalidate_all_tokens()
    assert count >= 3  # At least our 3 tokens


@pytest.mark.asyncio
async def test_invalidate_market_regime(sentiment_cache, sample_market_regime):
    """Test invalidating market regime."""
    await sentiment_cache.set_market_regime(sample_market_regime)
    assert await sentiment_cache.get_market_regime() is not None

    result = sentiment_cache.invalidate_market_regime()
    assert result is True

    cached = await sentiment_cache.get_market_regime()
    assert cached is None


@pytest.mark.asyncio
async def test_invalidate_grok_data(sentiment_cache):
    """Test invalidating Grok analysis data."""
    await sentiment_cache.set_grok_scores("hash1", {"scores": {}})
    await sentiment_cache.set_grok_summary("hash2", "summary")

    count = sentiment_cache.invalidate_grok_data()
    assert count >= 2


@pytest.mark.asyncio
async def test_invalidate_on_new_data(sentiment_cache, sample_token_sentiment, sample_market_regime):
    """Test invalidation when new data arrives."""
    # Cache various data
    await sentiment_cache.set_token_sentiment("SOL", sample_token_sentiment)
    await sentiment_cache.set_market_regime(sample_market_regime)
    await sentiment_cache.set_grok_scores("hash", {"scores": {}})

    # Invalidate tokens only
    sentiment_cache.invalidate_on_new_data("token")
    assert await sentiment_cache.get_token_sentiment("SOL") is None
    assert await sentiment_cache.get_market_regime() is not None  # Should still be cached

    # Invalidate all
    sentiment_cache.invalidate_on_new_data("all")
    assert await sentiment_cache.get_market_regime() is None


# =============================================================================
# METRICS TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_hit_rate_tracking(sentiment_cache, sample_token_sentiment):
    """Test cache hit rate metrics."""
    # Initial state
    metrics = sentiment_cache.get_metrics()
    assert metrics["token_sentiment"]["hit_rate"] == 0.0

    # Cache a token
    await sentiment_cache.set_token_sentiment("SOL", sample_token_sentiment)

    # Generate hits
    await sentiment_cache.get_token_sentiment("SOL")  # Hit
    await sentiment_cache.get_token_sentiment("SOL")  # Hit
    await sentiment_cache.get_token_sentiment("BONK")  # Miss

    metrics = sentiment_cache.get_metrics()
    assert metrics["token_sentiment"]["hits"] == 2
    assert metrics["token_sentiment"]["misses"] == 1
    assert metrics["token_sentiment"]["hit_rate"] == pytest.approx(2/3)


@pytest.mark.asyncio
async def test_market_hit_rate(sentiment_cache, sample_market_regime):
    """Test market regime hit rate tracking."""
    await sentiment_cache.set_market_regime(sample_market_regime)

    # Generate hits
    await sentiment_cache.get_market_regime()  # Hit
    await sentiment_cache.get_market_regime()  # Hit

    metrics = sentiment_cache.get_metrics()
    assert metrics["market_regime"]["hits"] == 2
    assert metrics["market_regime"]["misses"] == 0
    assert metrics["market_regime"]["hit_rate"] == 1.0


@pytest.mark.asyncio
async def test_grok_hit_rate(sentiment_cache):
    """Test Grok analysis hit rate tracking."""
    await sentiment_cache.set_grok_scores("hash1", {"scores": {}})

    # Generate hits and misses
    await sentiment_cache.get_grok_scores("hash1")  # Hit
    await sentiment_cache.get_grok_scores("hash2")  # Miss

    metrics = sentiment_cache.get_metrics()
    assert metrics["grok_analysis"]["hits"] == 1
    assert metrics["grok_analysis"]["misses"] == 1
    assert metrics["grok_analysis"]["hit_rate"] == 0.5


@pytest.mark.asyncio
async def test_overall_hit_rate(sentiment_cache, sample_token_sentiment, sample_market_regime):
    """Test overall cache hit rate across all types."""
    # Cache data
    await sentiment_cache.set_token_sentiment("SOL", sample_token_sentiment)
    await sentiment_cache.set_market_regime(sample_market_regime)
    await sentiment_cache.set_grok_scores("hash", {"scores": {}})

    # Generate mixed hits/misses
    await sentiment_cache.get_token_sentiment("SOL")  # Hit
    await sentiment_cache.get_token_sentiment("BONK")  # Miss
    await sentiment_cache.get_market_regime()  # Hit
    await sentiment_cache.get_grok_scores("hash")  # Hit
    await sentiment_cache.get_grok_scores("missing")  # Miss

    metrics = sentiment_cache.get_metrics()
    # 3 hits, 2 misses = 60% hit rate
    assert metrics["overall"]["hit_rate"] == pytest.approx(0.6)


@pytest.mark.asyncio
async def test_invalidation_tracking(sentiment_cache, sample_token_sentiment):
    """Test invalidation count tracking."""
    await sentiment_cache.set_token_sentiment("SOL", sample_token_sentiment)
    await sentiment_cache.set_token_sentiment("BONK", {"score": 45})

    metrics_before = sentiment_cache.get_metrics()
    initial_invalidations = metrics_before["overall"]["invalidations"]

    # Invalidate tokens
    sentiment_cache.invalidate_token("SOL")
    sentiment_cache.invalidate_token("BONK")

    metrics_after = sentiment_cache.get_metrics()
    assert metrics_after["overall"]["invalidations"] >= initial_invalidations + 2


@pytest.mark.asyncio
async def test_reset_metrics(sentiment_cache, sample_token_sentiment):
    """Test metrics reset."""
    # Generate some activity
    await sentiment_cache.set_token_sentiment("SOL", sample_token_sentiment)
    await sentiment_cache.get_token_sentiment("SOL")
    await sentiment_cache.get_token_sentiment("BONK")

    metrics = sentiment_cache.get_metrics()
    assert metrics["token_sentiment"]["hits"] > 0

    # Reset
    sentiment_cache.reset_metrics()

    metrics = sentiment_cache.get_metrics()
    assert metrics["token_sentiment"]["hits"] == 0
    assert metrics["token_sentiment"]["misses"] == 0


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_global_instance():
    """Test global sentiment cache instance."""
    cache1 = get_sentiment_cache()
    cache2 = get_sentiment_cache()

    # Should be same instance
    assert cache1 is cache2


@pytest.mark.asyncio
async def test_ttl_bounds_clamping(sentiment_cache, sample_token_sentiment):
    """Test that default TTL is clamped to configured bounds, but custom TTL is not."""
    # Test 1: Default TTL should be clamped (no custom ttl_minutes provided)
    # This uses token_sentiment_ttl_seconds=2 from config
    await sentiment_cache.set_token_sentiment("DEFAULT", sample_token_sentiment)
    cached = await sentiment_cache.get_token_sentiment("DEFAULT")
    # Should respect min bound
    assert cached["_ttl"] >= sentiment_cache.config.token_sentiment_min_ttl

    # Test 2: Custom TTL should NOT be clamped
    await sentiment_cache.set_token_sentiment("SOL", sample_token_sentiment, ttl_minutes=1000)
    cached = await sentiment_cache.get_token_sentiment("SOL")
    # Custom TTL of 1000 minutes = 60000 seconds, should be preserved
    assert cached["_ttl"] == 60000

    # Test 3: Very short custom TTL should also be preserved
    await sentiment_cache.set_token_sentiment("BONK", sample_token_sentiment, ttl_minutes=0.01)
    cached = await sentiment_cache.get_token_sentiment("BONK")
    # Custom TTL of 0.01 minutes = 0.6 seconds, should be preserved
    assert cached["_ttl"] == pytest.approx(0.6, rel=0.1)


@pytest.mark.asyncio
async def test_cache_metrics_logging(sentiment_cache, sample_token_sentiment, caplog):
    """Test that metrics can be logged."""
    import logging
    caplog.set_level(logging.INFO)

    await sentiment_cache.set_token_sentiment("SOL", sample_token_sentiment)
    await sentiment_cache.get_token_sentiment("SOL")

    sentiment_cache.log_metrics()

    # Check that log contains metric information
    assert "Sentiment Cache Metrics" in caplog.text
    assert "Hit Rate" in caplog.text
