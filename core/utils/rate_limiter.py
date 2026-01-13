"""
Rate Limiter - Lightweight rate limiting for API calls.
No external dependencies, thread-safe, supports multiple strategies.
"""

import time
import asyncio
from typing import Dict, Optional, Callable, Any
from dataclasses import dataclass
from threading import Lock
from collections import deque
import logging

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    requests_per_second: float = 10.0
    requests_per_minute: float = 300.0
    burst_size: int = 10
    retry_after_seconds: float = 1.0


class TokenBucket:
    """Token bucket rate limiter - allows bursts up to bucket size."""
    
    def __init__(self, rate: float, capacity: int):
        """
        Args:
            rate: Tokens added per second
            capacity: Maximum tokens in bucket
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = float(capacity)
        self.last_update = time.time()
        self._lock = Lock()
    
    def acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens. Returns True if successful."""
        with self._lock:
            now = time.time()
            elapsed = now - self.last_update
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_update = now
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False
    
    def wait_time(self, tokens: int = 1) -> float:
        """Calculate wait time to acquire tokens."""
        with self._lock:
            if self.tokens >= tokens:
                return 0.0
            needed = tokens - self.tokens
            return needed / self.rate


class SlidingWindow:
    """Sliding window rate limiter - strict limit over time window."""
    
    def __init__(self, max_requests: int, window_seconds: float):
        """
        Args:
            max_requests: Maximum requests allowed in window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: deque = deque()
        self._lock = Lock()
    
    def acquire(self) -> bool:
        """Try to make a request. Returns True if allowed."""
        with self._lock:
            now = time.time()
            cutoff = now - self.window_seconds
            
            # Remove old requests
            while self.requests and self.requests[0] < cutoff:
                self.requests.popleft()
            
            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return True
            return False
    
    def wait_time(self) -> float:
        """Calculate wait time until a request can be made."""
        with self._lock:
            if len(self.requests) < self.max_requests:
                return 0.0
            
            oldest = self.requests[0]
            return max(0, oldest + self.window_seconds - time.time())


class RateLimiter:
    """
    Combined rate limiter with token bucket and sliding window.
    Provides both burst allowance and strict limits.
    """
    
    def __init__(self, config: RateLimitConfig = None):
        config = config or RateLimitConfig()
        
        # Token bucket for burst control
        self.bucket = TokenBucket(
            rate=config.requests_per_second,
            capacity=config.burst_size
        )
        
        # Sliding window for per-minute limit
        self.window = SlidingWindow(
            max_requests=int(config.requests_per_minute),
            window_seconds=60.0
        )
        
        self.retry_after = config.retry_after_seconds
    
    def acquire(self) -> bool:
        """Try to acquire permission for a request."""
        return self.bucket.acquire() and self.window.acquire()
    
    def wait_time(self) -> float:
        """Get time to wait before next request."""
        return max(self.bucket.wait_time(), self.window.wait_time())
    
    async def wait_and_acquire(self) -> bool:
        """Wait if necessary and then acquire."""
        wait = self.wait_time()
        if wait > 0:
            await asyncio.sleep(wait)
        return self.acquire()


class MultiRateLimiter:
    """Rate limiter for multiple endpoints/APIs."""
    
    def __init__(self):
        self._limiters: Dict[str, RateLimiter] = {}
        self._lock = Lock()
        self._default_config = RateLimitConfig()
    
    def configure(self, key: str, config: RateLimitConfig):
        """Configure rate limit for a specific key (e.g., API name)."""
        with self._lock:
            self._limiters[key] = RateLimiter(config)
    
    def get(self, key: str) -> RateLimiter:
        """Get rate limiter for a key, creating default if needed."""
        with self._lock:
            if key not in self._limiters:
                self._limiters[key] = RateLimiter(self._default_config)
            return self._limiters[key]
    
    def acquire(self, key: str) -> bool:
        """Acquire permission for a specific key."""
        return self.get(key).acquire()
    
    async def wait_and_acquire(self, key: str) -> bool:
        """Wait and acquire for a specific key."""
        return await self.get(key).wait_and_acquire()
    
    def get_stats(self) -> dict:
        """Get stats for all configured rate limiters."""
        with self._lock:
            stats = {}
            for key, limiter in self._limiters.items():
                bucket = limiter._bucket
                window = limiter._window
                stats[key] = {
                    "tokens_available": round(bucket.tokens, 2),
                    "bucket_capacity": bucket.capacity,
                    "rate_per_sec": bucket.rate,
                    "window_requests": len(window.requests),
                    "window_max": window.max_requests,
                    "window_seconds": window.window_seconds
                }
            return stats


# Singleton instance
_instance: Optional[MultiRateLimiter] = None


def get_rate_limiter() -> MultiRateLimiter:
    """Get singleton rate limiter."""
    global _instance
    if _instance is None:
        _instance = MultiRateLimiter()
        
        # Configure known APIs with their limits
        # DexScreener: 300/min
        _instance.configure("dexscreener", RateLimitConfig(
            requests_per_second=5.0,
            requests_per_minute=300.0,
            burst_size=10
        ))
        
        # GeckoTerminal: 30/min for free tier
        _instance.configure("geckoterminal", RateLimitConfig(
            requests_per_second=0.5,
            requests_per_minute=30.0,
            burst_size=5
        ))
        
        # Jupiter: Generally liberal
        _instance.configure("jupiter", RateLimitConfig(
            requests_per_second=10.0,
            requests_per_minute=600.0,
            burst_size=20
        ))
        
        # Helius: Depends on tier
        _instance.configure("helius", RateLimitConfig(
            requests_per_second=5.0,
            requests_per_minute=100.0,
            burst_size=10
        ))
        
        # Default for unknown
        _instance.configure("default", RateLimitConfig(
            requests_per_second=2.0,
            requests_per_minute=60.0,
            burst_size=5
        ))
    
    return _instance


def rate_limited(api_key: str = "default"):
    """Decorator to rate limit a function."""
    def decorator(func: Callable) -> Callable:
        async def async_wrapper(*args, **kwargs) -> Any:
            limiter = get_rate_limiter()
            await limiter.wait_and_acquire(api_key)
            return await func(*args, **kwargs)
        
        def sync_wrapper(*args, **kwargs) -> Any:
            limiter = get_rate_limiter()
            if not limiter.acquire(api_key):
                time.sleep(limiter.get(api_key).wait_time())
                limiter.acquire(api_key)
            return func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator
