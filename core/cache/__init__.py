"""
JARVIS Cache Module

Caching utilities with TTL, LRU eviction, and async support.

Components:
- decorators: General-purpose caching decorators
- api_cache: Specialized API response caching with TTL management
- memory_cache: In-memory LRU cache
- redis_cache: Redis-backed caching (optional)
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

    # Utilities
    get_cache_manager,
    make_cache_key,
)

from .api_cache import (
    # Classes
    APICache,
    DEFAULT_TTLS,

    # Decorators
    cached_api,

    # Functions
    get_api_cache,
    parallel_fetch,
)

from .memory_cache import LRUCache

__all__ = [
    # decorators
    "CacheBackend",
    "CacheEntry",
    "CacheManager",
    "MemoryCache",
    "cached",
    "cache",
    "cache_aside",
    "get_cache_manager",
    "make_cache_key",
    # api_cache
    "APICache",
    "DEFAULT_TTLS",
    "cached_api",
    "get_api_cache",
    "parallel_fetch",
    # memory_cache
    "LRUCache",
]
