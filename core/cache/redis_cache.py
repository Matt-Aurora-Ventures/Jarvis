"""Redis caching layer."""
import json
import hashlib
import asyncio
from typing import Any, Optional, Callable
from functools import wraps
import logging

logger = logging.getLogger(__name__)

try:
    import redis.asyncio as aioredis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False


class RedisCache:
    """Redis-based caching with TTL support."""
    
    def __init__(self, url: str = "redis://localhost:6379", prefix: str = "jarvis"):
        self.url = url
        self.prefix = prefix
        self._client = None
    
    async def _get_client(self):
        if not HAS_REDIS:
            return None
        if self._client is None:
            self._client = await aioredis.from_url(self.url, decode_responses=True)
        return self._client
    
    def _make_key(self, key: str) -> str:
        return f"{self.prefix}:{key}"
    
    async def get(self, key: str) -> Optional[Any]:
        client = await self._get_client()
        if not client:
            return None
        try:
            data = await client.get(self._make_key(key))
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        client = await self._get_client()
        if not client:
            return False
        try:
            await client.setex(self._make_key(key), ttl, json.dumps(value, default=str))
            return True
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        client = await self._get_client()
        if not client:
            return False
        try:
            await client.delete(self._make_key(key))
            return True
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        client = await self._get_client()
        if not client:
            return False
        try:
            return await client.exists(self._make_key(key)) > 0
        except Exception:
            return False
    
    async def clear_prefix(self, prefix: str) -> int:
        client = await self._get_client()
        if not client:
            return 0
        try:
            pattern = self._make_key(f"{prefix}:*")
            keys = await client.keys(pattern)
            if keys:
                return await client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Redis clear error: {e}")
            return 0
    
    async def close(self):
        if self._client:
            await self._client.close()
            self._client = None


_cache_instance: Optional[RedisCache] = None


def get_cache() -> RedisCache:
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = RedisCache()
    return _cache_instance


def cache(key_prefix: str, ttl: int = 300):
    """Decorator for caching function results."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_instance = get_cache()
            cache_key = f"{key_prefix}:{hashlib.md5(str(args).encode() + str(kwargs).encode()).hexdigest()[:16]}"
            
            cached = await cache_instance.get(cache_key)
            if cached is not None:
                return cached
            
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            await cache_instance.set(cache_key, result, ttl)
            return result
        return wrapper
    return decorator
