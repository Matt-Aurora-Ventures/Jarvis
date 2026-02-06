"""
JARVIS Cache Module

Caching utilities with TTL, LRU eviction, and async support.

Components:
- manager: Central CacheManager for ClawdBots
- backends: Multiple cache backends (InMemoryCache, FileCache, TTLCache, LRUCache)
- decorators: General-purpose caching decorators
- api_cache: Specialized API response caching with TTL management
- memory_cache: In-memory LRU cache
- redis_cache: Redis-backed caching (optional)

Cache location: bots/data/cache/
"""

from .decorators import (
    # Classes
    CacheBackend,
    CacheEntry,
    CacheManager,
    MemoryCache,

    # Decorators
    cached,
    cache,
    cache_aside,
    cache_key,

    # Utilities
    get_cache_manager,
    make_cache_key,
    invalidate_cache,
)

from .api_cache import (
    # Classes
    APICache,
    DEFAULT_TTLS,
    LLMResponseCache,
    LLMCacheStats,

    # Decorators
    cached_api,

    # Functions
    get_api_cache,
    get_llm_cache,
    parallel_fetch,
)

from .memory_cache import LRUCache

# Import new manager and backends
from .manager import (
    CacheManager as ClawdBotCacheManager,
    CacheStats,
    DEFAULT_CACHE_DIR,
    get_cache_manager as get_clawdbot_cache_manager,
)

from .backends import (
    InMemoryCache,
    FileCache,
    TTLCache,
    LRUCache as LRUCacheBackend,
)

__all__ = [
    # decorators
    "CacheBackend",
    "CacheEntry",
    "CacheManager",
    "MemoryCache",
    "cached",
    "cache",
    "cache_aside",
    "cache_key",
    "get_cache_manager",
    "make_cache_key",
    "invalidate_cache",
    # api_cache
    "APICache",
    "DEFAULT_TTLS",
    "LLMResponseCache",
    "LLMCacheStats",
    "cached_api",
    "get_api_cache",
    "get_llm_cache",
    "parallel_fetch",
    # memory_cache
    "LRUCache",
    # manager (ClawdBot specific)
    "ClawdBotCacheManager",
    "CacheStats",
    "DEFAULT_CACHE_DIR",
    "get_clawdbot_cache_manager",
    # backends
    "InMemoryCache",
    "FileCache",
    "TTLCache",
    "LRUCacheBackend",
]
