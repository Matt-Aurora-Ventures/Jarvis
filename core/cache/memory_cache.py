"""In-memory caching with LRU eviction."""
import time
from typing import Any, Optional, Dict
from collections import OrderedDict
from threading import Lock
from functools import wraps


class LRUCache:
    """Thread-safe LRU cache."""
    
    def __init__(self, maxsize: int = 1000, ttl: int = 300):
        self.maxsize = maxsize
        self.ttl = ttl
        self._cache: OrderedDict = OrderedDict()
        self._timestamps: Dict[str, float] = {}
        self._lock = Lock()
    
    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key not in self._cache:
                return None
            if self._is_expired(key):
                self._remove(key)
                return None
            self._cache.move_to_end(key)
            return self._cache[key]
    
    def set(self, key: str, value: Any, ttl: int = None):
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            else:
                if len(self._cache) >= self.maxsize:
                    oldest = next(iter(self._cache))
                    self._remove(oldest)
            self._cache[key] = value
            self._timestamps[key] = time.time() + (ttl or self.ttl)
    
    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._cache:
                self._remove(key)
                return True
            return False
    
    def clear(self):
        with self._lock:
            self._cache.clear()
            self._timestamps.clear()
    
    def _is_expired(self, key: str) -> bool:
        return time.time() > self._timestamps.get(key, 0)
    
    def _remove(self, key: str):
        self._cache.pop(key, None)
        self._timestamps.pop(key, None)
    
    def __len__(self):
        return len(self._cache)
    
    def __contains__(self, key: str):
        return self.get(key) is not None


class MemoryCache:
    """Simple in-memory cache with namespaces."""
    
    def __init__(self, default_ttl: int = 300):
        self.default_ttl = default_ttl
        self._caches: Dict[str, LRUCache] = {}
        self._lock = Lock()
    
    def _get_cache(self, namespace: str) -> LRUCache:
        if namespace not in self._caches:
            with self._lock:
                if namespace not in self._caches:
                    self._caches[namespace] = LRUCache(ttl=self.default_ttl)
        return self._caches[namespace]
    
    def get(self, key: str, namespace: str = "default") -> Optional[Any]:
        return self._get_cache(namespace).get(key)
    
    def set(self, key: str, value: Any, namespace: str = "default", ttl: int = None):
        self._get_cache(namespace).set(key, value, ttl)
    
    def delete(self, key: str, namespace: str = "default") -> bool:
        return self._get_cache(namespace).delete(key)
    
    def clear_namespace(self, namespace: str):
        if namespace in self._caches:
            self._caches[namespace].clear()
    
    def clear_all(self):
        for cache in self._caches.values():
            cache.clear()


_memory_cache = MemoryCache()


def memoize(ttl: int = 300, namespace: str = "memoize"):
    """Decorator for memoizing function results."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = f"{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"
            cached = _memory_cache.get(key, namespace)
            if cached is not None:
                return cached
            result = func(*args, **kwargs)
            _memory_cache.set(key, result, namespace, ttl)
            return result
        return wrapper
    return decorator
