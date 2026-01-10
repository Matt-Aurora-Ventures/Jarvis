"""
Redis-based Rate Limiter.

Provides distributed rate limiting for API endpoints:
- Sliding window algorithm
- Per-user and per-IP limits
- Tier-based rate limits
- Redis-backed for distributed deployments
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("jarvis.payments.rate_limiter")


# =============================================================================
# Configuration
# =============================================================================


class UserTier(Enum):
    """User tier for rate limiting."""
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    WHALE = "whale"


@dataclass
class RateLimitConfig:
    """Configuration for rate limiter."""

    # Redis connection
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    # Default limits (requests per minute)
    default_limit: int = 10

    # Tier limits
    tier_limits: Dict[str, int] = None

    # Window size in seconds
    window_seconds: int = 60

    # Key prefix
    key_prefix: str = "jarvis:ratelimit:"

    def __post_init__(self):
        if self.tier_limits is None:
            self.tier_limits = {
                UserTier.FREE.value: 10,
                UserTier.STARTER.value: 50,
                UserTier.PRO.value: 100,
                UserTier.WHALE.value: 500,
            }


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""

    allowed: bool
    limit: int
    remaining: int
    reset_at: int
    retry_after: Optional[int] = None

    def to_headers(self) -> Dict[str, str]:
        """Generate rate limit headers."""
        headers = {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(max(0, self.remaining)),
            "X-RateLimit-Reset": str(self.reset_at),
        }
        if self.retry_after is not None:
            headers["Retry-After"] = str(self.retry_after)
        return headers


# =============================================================================
# Redis Rate Limiter
# =============================================================================


class RedisRateLimiter:
    """
    Distributed rate limiter using Redis.

    Uses sliding window algorithm for smooth rate limiting.
    """

    def __init__(self, config: RateLimitConfig = None):
        self.config = config or RateLimitConfig()
        self._redis = None
        self._connected = False

    async def connect(self):
        """Connect to Redis."""
        if self._connected:
            return

        try:
            import redis.asyncio as redis
            self._redis = redis.from_url(
                self.config.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            await self._redis.ping()
            self._connected = True
            logger.info("Connected to Redis for rate limiting")
        except ImportError:
            logger.warning("redis package not installed, using in-memory fallback")
            self._redis = InMemoryRedis()
            self._connected = True
        except Exception as e:
            logger.warning(f"Redis connection failed, using in-memory fallback: {e}")
            self._redis = InMemoryRedis()
            self._connected = True

    async def close(self):
        """Close Redis connection."""
        if self._redis and hasattr(self._redis, "close"):
            await self._redis.close()
        self._connected = False

    async def check_rate_limit(
        self,
        identifier: str,
        tier: str = None,
        endpoint: str = None,
    ) -> RateLimitResult:
        """
        Check if a request is within rate limits.

        Args:
            identifier: User ID or IP address
            tier: User tier (for determining limit)
            endpoint: Optional endpoint for per-endpoint limits

        Returns:
            RateLimitResult with limit status
        """
        if not self._connected:
            await self.connect()

        # Determine limit based on tier
        limit = self.config.tier_limits.get(tier, self.config.default_limit)

        # Generate key
        key_parts = [self.config.key_prefix, identifier]
        if endpoint:
            key_parts.append(endpoint.replace("/", "_"))
        key = ":".join(key_parts)

        # Current time
        now = int(time.time())
        window_start = now - self.config.window_seconds

        try:
            # Use Redis sorted set for sliding window
            pipe = self._redis.pipeline()

            # Remove old entries
            pipe.zremrangebyscore(key, 0, window_start)

            # Count current window entries
            pipe.zcard(key)

            # Add current request
            pipe.zadd(key, {str(now): now})

            # Set expiry
            pipe.expire(key, self.config.window_seconds * 2)

            results = await pipe.execute()
            current_count = results[1]

            # Calculate remaining
            remaining = limit - current_count - 1
            reset_at = now + self.config.window_seconds

            if current_count >= limit:
                # Rate limited
                return RateLimitResult(
                    allowed=False,
                    limit=limit,
                    remaining=0,
                    reset_at=reset_at,
                    retry_after=self.config.window_seconds,
                )

            return RateLimitResult(
                allowed=True,
                limit=limit,
                remaining=max(0, remaining),
                reset_at=reset_at,
            )

        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            # Fail open - allow request if Redis fails
            return RateLimitResult(
                allowed=True,
                limit=limit,
                remaining=limit,
                reset_at=now + self.config.window_seconds,
            )

    async def get_usage(self, identifier: str) -> Dict[str, Any]:
        """Get current usage statistics for an identifier."""
        if not self._connected:
            await self.connect()

        key = f"{self.config.key_prefix}{identifier}"
        now = int(time.time())
        window_start = now - self.config.window_seconds

        try:
            count = await self._redis.zcount(key, window_start, now)
            return {
                "identifier": identifier,
                "requests_in_window": count,
                "window_seconds": self.config.window_seconds,
            }
        except Exception as e:
            logger.error(f"Failed to get usage: {e}")
            return {"error": str(e)}

    async def reset(self, identifier: str):
        """Reset rate limit for an identifier."""
        if not self._connected:
            await self.connect()

        key = f"{self.config.key_prefix}{identifier}"
        try:
            await self._redis.delete(key)
            logger.info(f"Reset rate limit for {identifier}")
        except Exception as e:
            logger.error(f"Failed to reset rate limit: {e}")


# =============================================================================
# In-Memory Fallback
# =============================================================================


class InMemoryRedis:
    """In-memory fallback when Redis is unavailable."""

    def __init__(self):
        self._data: Dict[str, Dict[str, float]] = {}
        self._expiry: Dict[str, float] = {}

    def pipeline(self):
        return InMemoryPipeline(self)

    async def zcount(self, key: str, min_score: float, max_score: float) -> int:
        self._cleanup_expired()
        if key not in self._data:
            return 0
        return sum(1 for score in self._data[key].values()
                   if min_score <= score <= max_score)

    async def delete(self, key: str):
        self._data.pop(key, None)
        self._expiry.pop(key, None)

    def _cleanup_expired(self):
        now = time.time()
        expired = [k for k, exp in self._expiry.items() if exp < now]
        for k in expired:
            self._data.pop(k, None)
            self._expiry.pop(k, None)


class InMemoryPipeline:
    """Pipeline implementation for in-memory fallback."""

    def __init__(self, redis: InMemoryRedis):
        self._redis = redis
        self._commands = []

    def zremrangebyscore(self, key: str, min_score: float, max_score: float):
        self._commands.append(("zremrangebyscore", key, min_score, max_score))
        return self

    def zcard(self, key: str):
        self._commands.append(("zcard", key))
        return self

    def zadd(self, key: str, mapping: Dict[str, float]):
        self._commands.append(("zadd", key, mapping))
        return self

    def expire(self, key: str, seconds: int):
        self._commands.append(("expire", key, seconds))
        return self

    async def execute(self):
        results = []
        for cmd in self._commands:
            if cmd[0] == "zremrangebyscore":
                key, min_s, max_s = cmd[1], cmd[2], cmd[3]
                if key in self._redis._data:
                    to_remove = [m for m, s in self._redis._data[key].items()
                                 if min_s <= s <= max_s]
                    for m in to_remove:
                        del self._redis._data[key][m]
                results.append(0)

            elif cmd[0] == "zcard":
                key = cmd[1]
                count = len(self._redis._data.get(key, {}))
                results.append(count)

            elif cmd[0] == "zadd":
                key, mapping = cmd[1], cmd[2]
                if key not in self._redis._data:
                    self._redis._data[key] = {}
                self._redis._data[key].update(mapping)
                results.append(len(mapping))

            elif cmd[0] == "expire":
                key, seconds = cmd[1], cmd[2]
                self._redis._expiry[key] = time.time() + seconds
                results.append(True)

        return results


# =============================================================================
# FastAPI Middleware
# =============================================================================


def create_rate_limit_middleware(config: RateLimitConfig = None):
    """Create FastAPI middleware for rate limiting."""
    try:
        from fastapi import Request, Response
        from starlette.middleware.base import BaseHTTPMiddleware
    except ImportError:
        logger.warning("FastAPI not installed, middleware unavailable")
        return None

    limiter = RedisRateLimiter(config)

    class RateLimitMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            # Skip health checks
            if request.url.path in ["/health", "/metrics"]:
                return await call_next(request)

            # Get identifier (user ID or IP)
            user_id = getattr(request.state, "user_id", None)
            identifier = user_id or request.client.host

            # Get tier
            tier = getattr(request.state, "user_tier", "free")

            # Check rate limit
            result = await limiter.check_rate_limit(
                identifier=identifier,
                tier=tier,
                endpoint=request.url.path,
            )

            if not result.allowed:
                return Response(
                    content='{"error": "Rate limit exceeded"}',
                    status_code=429,
                    headers=result.to_headers(),
                    media_type="application/json",
                )

            # Process request
            response = await call_next(request)

            # Add rate limit headers
            for key, value in result.to_headers().items():
                response.headers[key] = value

            return response

    return RateLimitMiddleware


# =============================================================================
# Dependency for FastAPI
# =============================================================================


_limiter: Optional[RedisRateLimiter] = None


async def get_rate_limiter() -> RedisRateLimiter:
    """Get singleton rate limiter."""
    global _limiter
    if _limiter is None:
        _limiter = RedisRateLimiter()
        await _limiter.connect()
    return _limiter


def create_rate_limit_dependency(
    limit: int = None,
    window_seconds: int = 60,
):
    """Create a rate limit dependency for specific endpoints."""
    try:
        from fastapi import Depends, HTTPException, Request
    except ImportError:
        return None

    async def rate_limit_check(
        request: Request,
        limiter: RedisRateLimiter = Depends(get_rate_limiter),
    ):
        user_id = getattr(request.state, "user_id", None)
        identifier = user_id or request.client.host
        tier = getattr(request.state, "user_tier", "free")

        result = await limiter.check_rate_limit(
            identifier=identifier,
            tier=tier,
            endpoint=request.url.path,
        )

        if not result.allowed:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers=result.to_headers(),
            )

        return result

    return rate_limit_check
