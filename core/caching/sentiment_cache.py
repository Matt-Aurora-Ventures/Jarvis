"""
Sentiment Analysis Caching Layer

Provides specialized caching for sentiment analysis results with:
- Token sentiment scores (5-15 min TTL)
- Market regime data (30-60 min TTL)
- Historical data (longer TTL)
- Automatic cache invalidation on new data
- Hit rate metrics

Usage:
    from core.caching.sentiment_cache import SentimentCache

    cache = SentimentCache()

    # Cache token sentiment
    await cache.set_token_sentiment("SOL", sentiment_data, ttl_minutes=10)
    sentiment = await cache.get_token_sentiment("SOL")

    # Cache market data
    await cache.set_market_regime(regime_data)
    regime = await cache.get_market_regime()

    # Invalidate on new data
    cache.invalidate_token("SOL")
    cache.invalidate_all_tokens()
"""

import asyncio
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .cache_manager import MultiLevelCache, get_multi_level_cache

logger = logging.getLogger(__name__)


@dataclass
class SentimentCacheConfig:
    """Configuration for sentiment caching TTLs."""
    # Token-level caching (volatile data)
    token_sentiment_ttl_seconds: int = 600  # 10 minutes
    token_sentiment_min_ttl: int = 300  # 5 minutes
    token_sentiment_max_ttl: int = 900  # 15 minutes

    # Market-level caching (less volatile)
    market_regime_ttl_seconds: int = 1800  # 30 minutes
    market_data_ttl_seconds: int = 3600  # 60 minutes

    # Historical data (stable)
    historical_ttl_seconds: int = 86400  # 24 hours

    # Grok analysis (expensive calls)
    grok_scores_ttl_seconds: int = 900  # 15 minutes
    grok_summary_ttl_seconds: int = 1800  # 30 minutes

    # Traditional markets (slower moving)
    traditional_markets_ttl_seconds: int = 3600  # 60 minutes
    commodity_prices_ttl_seconds: int = 1800  # 30 minutes

    # Macro analysis (changes daily)
    macro_analysis_ttl_seconds: int = 14400  # 4 hours


@dataclass
class CacheMetrics:
    """Metrics for cache performance."""
    token_hits: int = 0
    token_misses: int = 0
    market_hits: int = 0
    market_misses: int = 0
    grok_hits: int = 0
    grok_misses: int = 0
    invalidations: int = 0
    last_reset: float = field(default_factory=time.time)

    @property
    def token_hit_rate(self) -> float:
        total = self.token_hits + self.token_misses
        return self.token_hits / total if total > 0 else 0.0

    @property
    def market_hit_rate(self) -> float:
        total = self.market_hits + self.market_misses
        return self.market_hits / total if total > 0 else 0.0

    @property
    def grok_hit_rate(self) -> float:
        total = self.grok_hits + self.grok_misses
        return self.grok_hits / total if total > 0 else 0.0

    @property
    def overall_hit_rate(self) -> float:
        total_hits = self.token_hits + self.market_hits + self.grok_hits
        total_misses = self.token_misses + self.market_misses + self.grok_misses
        total = total_hits + total_misses
        return total_hits / total if total > 0 else 0.0


class SentimentCache:
    """
    Specialized cache for sentiment analysis results.

    Provides appropriate TTLs for different types of sentiment data:
    - Token sentiment: 5-15 minutes (volatile)
    - Market regime: 30-60 minutes (less volatile)
    - Historical: 24 hours (stable)
    - Grok analysis: 15-30 minutes (expensive, moderate volatility)

    Features:
    - Automatic invalidation on new data arrival
    - Hit rate tracking per data type
    - Tag-based bulk invalidation
    - Adaptive TTL based on volatility
    """

    def __init__(
        self,
        config: Optional[SentimentCacheConfig] = None,
        cache: Optional[MultiLevelCache] = None
    ):
        self.config = config or SentimentCacheConfig()
        self._cache = cache or get_multi_level_cache()
        self._metrics = CacheMetrics()

        # Namespaces for different data types
        self.NS_TOKEN = "sentiment:token"
        self.NS_MARKET = "sentiment:market"
        self.NS_GROK = "sentiment:grok"
        self.NS_TRADITIONAL = "sentiment:traditional"
        self.NS_MACRO = "sentiment:macro"
        self.NS_HISTORICAL = "sentiment:historical"

    # =============================================================================
    # TOKEN SENTIMENT CACHING
    # =============================================================================

    async def get_token_sentiment(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get cached token sentiment data."""
        key = f"token:{symbol}"
        value = self._cache.get(key, namespace=self.NS_TOKEN)

        if value is not None:
            self._metrics.token_hits += 1
            logger.debug(f"Cache hit for token sentiment: {symbol}")
        else:
            self._metrics.token_misses += 1
            logger.debug(f"Cache miss for token sentiment: {symbol}")

        return value

    async def set_token_sentiment(
        self,
        symbol: str,
        data: Dict[str, Any],
        ttl_minutes: Optional[int] = None,
        clamp_ttl: bool = True
    ) -> bool:
        """
        Cache token sentiment data.

        Args:
            symbol: Token symbol (e.g., "SOL", "BONK")
            data: Sentiment data dictionary
            ttl_minutes: Optional custom TTL in minutes
            clamp_ttl: Whether to clamp TTL to min/max bounds (default True)

        Returns:
            True if cached successfully
        """
        key = f"token:{symbol}"
        ttl_seconds = (ttl_minutes * 60) if ttl_minutes else self.config.token_sentiment_ttl_seconds

        # Clamp TTL to reasonable bounds (only for default TTLs, not custom)
        if clamp_ttl and ttl_minutes is None:
            ttl_seconds = max(
                self.config.token_sentiment_min_ttl,
                min(ttl_seconds, self.config.token_sentiment_max_ttl)
            )

        # Add timestamp to cached data
        cached_data = {
            **data,
            "_cached_at": time.time(),
            "_ttl": ttl_seconds
        }

        tags = [f"token:{symbol}", "sentiment", "volatile"]
        return self._cache.set(key, cached_data, ttl=ttl_seconds, tags=tags, namespace=self.NS_TOKEN)

    async def get_batch_token_sentiment(
        self,
        symbols: List[str]
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """Get multiple token sentiments in one call."""
        results = {}
        for symbol in symbols:
            results[symbol] = await self.get_token_sentiment(symbol)
        return results

    async def set_batch_token_sentiment(
        self,
        sentiments: Dict[str, Dict[str, Any]],
        ttl_minutes: Optional[int] = None
    ):
        """Cache multiple token sentiments."""
        for symbol, data in sentiments.items():
            await self.set_token_sentiment(symbol, data, ttl_minutes)

    # =============================================================================
    # MARKET REGIME CACHING
    # =============================================================================

    async def get_market_regime(self) -> Optional[Dict[str, Any]]:
        """Get cached market regime data."""
        key = "current_regime"
        value = self._cache.get(key, namespace=self.NS_MARKET)

        if value is not None:
            self._metrics.market_hits += 1
            logger.debug("Cache hit for market regime")
        else:
            self._metrics.market_misses += 1
            logger.debug("Cache miss for market regime")

        return value

    async def set_market_regime(
        self,
        data: Dict[str, Any],
        ttl_minutes: Optional[int] = None
    ) -> bool:
        """
        Cache market regime data.

        Args:
            data: Market regime data (btc_trend, sol_trend, risk_level, etc.)
            ttl_minutes: Optional custom TTL in minutes

        Returns:
            True if cached successfully
        """
        key = "current_regime"
        ttl_seconds = (ttl_minutes * 60) if ttl_minutes else self.config.market_regime_ttl_seconds

        cached_data = {
            **data,
            "_cached_at": time.time(),
            "_ttl": ttl_seconds
        }

        tags = ["market_regime", "sentiment"]
        return self._cache.set(key, cached_data, ttl=ttl_seconds, tags=tags, namespace=self.NS_MARKET)

    # =============================================================================
    # GROK ANALYSIS CACHING
    # =============================================================================

    async def get_grok_scores(self, tokens_hash: str) -> Optional[Dict[str, Any]]:
        """
        Get cached Grok token scores.

        Args:
            tokens_hash: Hash of token list to ensure cache validity

        Returns:
            Cached Grok scores or None
        """
        key = f"grok_scores:{tokens_hash}"
        value = self._cache.get(key, namespace=self.NS_GROK)

        if value is not None:
            self._metrics.grok_hits += 1
            logger.debug(f"Cache hit for Grok scores: {tokens_hash[:8]}...")
        else:
            self._metrics.grok_misses += 1
            logger.debug(f"Cache miss for Grok scores: {tokens_hash[:8]}...")

        return value

    async def set_grok_scores(
        self,
        tokens_hash: str,
        data: Dict[str, Any],
        ttl_minutes: Optional[int] = None
    ) -> bool:
        """
        Cache Grok token scores.

        Args:
            tokens_hash: Hash of token list
            data: Grok analysis results
            ttl_minutes: Optional custom TTL in minutes

        Returns:
            True if cached successfully
        """
        key = f"grok_scores:{tokens_hash}"
        ttl_seconds = (ttl_minutes * 60) if ttl_minutes else self.config.grok_scores_ttl_seconds

        cached_data = {
            **data,
            "_cached_at": time.time(),
            "_ttl": ttl_seconds
        }

        tags = ["grok", "sentiment", "expensive"]
        return self._cache.set(key, cached_data, ttl=ttl_seconds, tags=tags, namespace=self.NS_GROK)

    async def get_grok_summary(self, context_hash: str) -> Optional[str]:
        """Get cached Grok summary."""
        key = f"grok_summary:{context_hash}"
        value = self._cache.get(key, namespace=self.NS_GROK)

        if value is not None:
            self._metrics.grok_hits += 1
            logger.debug(f"Cache hit for Grok summary: {context_hash[:8]}...")
        else:
            self._metrics.grok_misses += 1
            logger.debug(f"Cache miss for Grok summary: {context_hash[:8]}...")

        return value

    async def set_grok_summary(
        self,
        context_hash: str,
        summary: str,
        ttl_minutes: Optional[int] = None
    ) -> bool:
        """Cache Grok summary."""
        key = f"grok_summary:{context_hash}"
        ttl_seconds = (ttl_minutes * 60) if ttl_minutes else self.config.grok_summary_ttl_seconds

        cached_data = {
            "summary": summary,
            "_cached_at": time.time(),
            "_ttl": ttl_seconds
        }

        tags = ["grok", "sentiment", "expensive"]
        return self._cache.set(key, cached_data, ttl=ttl_seconds, tags=tags, namespace=self.NS_GROK)

    # =============================================================================
    # TRADITIONAL MARKETS CACHING
    # =============================================================================

    async def get_traditional_markets(self) -> Optional[Dict[str, Any]]:
        """Get cached traditional markets data (DXY, stocks)."""
        key = "traditional_markets"
        value = self._cache.get(key, namespace=self.NS_TRADITIONAL)
        return value

    async def set_traditional_markets(
        self,
        data: Dict[str, Any],
        ttl_minutes: Optional[int] = None
    ) -> bool:
        """Cache traditional markets data."""
        key = "traditional_markets"
        ttl_seconds = (ttl_minutes * 60) if ttl_minutes else self.config.traditional_markets_ttl_seconds

        cached_data = {
            **data,
            "_cached_at": time.time(),
            "_ttl": ttl_seconds
        }

        tags = ["traditional", "markets"]
        return self._cache.set(key, cached_data, ttl=ttl_seconds, tags=tags, namespace=self.NS_TRADITIONAL)

    # =============================================================================
    # MACRO ANALYSIS CACHING
    # =============================================================================

    async def get_macro_analysis(self) -> Optional[Dict[str, Any]]:
        """Get cached macro analysis."""
        key = "macro_analysis"
        value = self._cache.get(key, namespace=self.NS_MACRO)
        return value

    async def set_macro_analysis(
        self,
        data: Dict[str, Any],
        ttl_minutes: Optional[int] = None
    ) -> bool:
        """Cache macro analysis."""
        key = "macro_analysis"
        ttl_seconds = (ttl_minutes * 60) if ttl_minutes else self.config.macro_analysis_ttl_seconds

        cached_data = {
            **data,
            "_cached_at": time.time(),
            "_ttl": ttl_seconds
        }

        tags = ["macro", "sentiment"]
        return self._cache.set(key, cached_data, ttl=ttl_seconds, tags=tags, namespace=self.NS_MACRO)

    # =============================================================================
    # CACHE INVALIDATION
    # =============================================================================

    def invalidate_token(self, symbol: str) -> bool:
        """Invalidate cached sentiment for a specific token."""
        key = f"token:{symbol}"
        result = self._cache.invalidate(key, namespace=self.NS_TOKEN)
        if result:
            self._metrics.invalidations += 1
            logger.debug(f"Invalidated cache for token: {symbol}")
        return result

    def invalidate_all_tokens(self) -> int:
        """Invalidate all token sentiment caches."""
        count = self._cache.invalidate_by_prefix(f"{self.NS_TOKEN}:token:")
        self._metrics.invalidations += count
        logger.info(f"Invalidated {count} token sentiment entries")
        return count

    def invalidate_market_regime(self) -> bool:
        """Invalidate market regime cache."""
        key = "current_regime"
        result = self._cache.invalidate(key, namespace=self.NS_MARKET)
        if result:
            self._metrics.invalidations += 1
            logger.debug("Invalidated market regime cache")
        return result

    def invalidate_grok_data(self) -> int:
        """Invalidate all Grok analysis caches."""
        count = self._cache.invalidate_by_tag("grok")
        self._metrics.invalidations += count
        logger.info(f"Invalidated {count} Grok analysis entries")
        return count

    def invalidate_on_new_data(self, data_type: str = "token"):
        """
        Invalidate appropriate caches when new data arrives.

        Args:
            data_type: Type of new data ("token", "market", "grok", "all")
        """
        if data_type == "token" or data_type == "all":
            self.invalidate_all_tokens()

        if data_type == "market" or data_type == "all":
            self.invalidate_market_regime()

        if data_type == "grok" or data_type == "all":
            self.invalidate_grok_data()

    # =============================================================================
    # METRICS & STATS
    # =============================================================================

    def get_metrics(self) -> Dict[str, Any]:
        """Get cache performance metrics."""
        return {
            "token_sentiment": {
                "hits": self._metrics.token_hits,
                "misses": self._metrics.token_misses,
                "hit_rate": self._metrics.token_hit_rate,
            },
            "market_regime": {
                "hits": self._metrics.market_hits,
                "misses": self._metrics.market_misses,
                "hit_rate": self._metrics.market_hit_rate,
            },
            "grok_analysis": {
                "hits": self._metrics.grok_hits,
                "misses": self._metrics.grok_misses,
                "hit_rate": self._metrics.grok_hit_rate,
            },
            "overall": {
                "hit_rate": self._metrics.overall_hit_rate,
                "invalidations": self._metrics.invalidations,
                "uptime_seconds": time.time() - self._metrics.last_reset,
            }
        }

    def reset_metrics(self):
        """Reset cache metrics."""
        self._metrics = CacheMetrics()
        logger.info("Reset sentiment cache metrics")

    def log_metrics(self):
        """Log current cache performance metrics."""
        metrics = self.get_metrics()
        logger.info(f"Sentiment Cache Metrics:")
        logger.info(f"  Token Hit Rate: {metrics['token_sentiment']['hit_rate']:.2%}")
        logger.info(f"  Market Hit Rate: {metrics['market_regime']['hit_rate']:.2%}")
        logger.info(f"  Grok Hit Rate: {metrics['grok_analysis']['hit_rate']:.2%}")
        logger.info(f"  Overall Hit Rate: {metrics['overall']['hit_rate']:.2%}")
        logger.info(f"  Total Invalidations: {metrics['overall']['invalidations']}")


# Global instance
_sentiment_cache: Optional[SentimentCache] = None


def get_sentiment_cache() -> SentimentCache:
    """Get the global sentiment cache instance."""
    global _sentiment_cache
    if _sentiment_cache is None:
        _sentiment_cache = SentimentCache()
    return _sentiment_cache
