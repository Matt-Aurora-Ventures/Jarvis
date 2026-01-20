"""
Multi-level caching system for Jarvis.

Provides:
- Memory cache (LRU with TTL)
- File cache (SQLite-based persistence)
- Redis cache (optional, for distributed caching)
- Cache decorators
- Statistics tracking
- Specialized sentiment analysis caching
"""

from .cache_manager import (
    MultiLevelCache,
    get_multi_level_cache,
    cached,
    CacheConfig,
    CacheStats,
)
from .sentiment_cache import (
    SentimentCache,
    get_sentiment_cache,
    SentimentCacheConfig,
    CacheMetrics,
)

__all__ = [
    "MultiLevelCache",
    "get_multi_level_cache",
    "cached",
    "CacheConfig",
    "CacheStats",
    "SentimentCache",
    "get_sentiment_cache",
    "SentimentCacheConfig",
    "CacheMetrics",
]
