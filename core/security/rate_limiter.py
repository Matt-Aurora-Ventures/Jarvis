"""
Rate Limiter

Sliding window rate limiting for API endpoints and trading operations.
Supports Redis for distributed rate limiting.

Prompts #171-180: Security
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List, Tuple, Any
from collections import defaultdict
from enum import Enum

logger = logging.getLogger(__name__)


class RateLimitTier(str, Enum):
    """Rate limit tiers for different user levels"""
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    WHALE = "whale"
    UNLIMITED = "unlimited"


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting"""
    requests_per_minute: int
    requests_per_hour: int
    requests_per_day: int
    burst_size: int = 10


# Default tier limits
TIER_LIMITS = {
    RateLimitTier.FREE: RateLimitConfig(
        requests_per_minute=10,
        requests_per_hour=100,
        requests_per_day=500,
        burst_size=5
    ),
    RateLimitTier.STARTER: RateLimitConfig(
        requests_per_minute=50,
        requests_per_hour=500,
        requests_per_day=5000,
        burst_size=20
    ),
    RateLimitTier.PRO: RateLimitConfig(
        requests_per_minute=100,
        requests_per_hour=2000,
        requests_per_day=20000,
        burst_size=50
    ),
    RateLimitTier.WHALE: RateLimitConfig(
        requests_per_minute=500,
        requests_per_hour=10000,
        requests_per_day=100000,
        burst_size=100
    ),
    RateLimitTier.UNLIMITED: RateLimitConfig(
        requests_per_minute=10000,
        requests_per_hour=100000,
        requests_per_day=1000000,
        burst_size=1000
    )
}


@dataclass
class RateLimitResult:
    """Result of a rate limit check"""
    allowed: bool
    remaining: int
    limit: int
    reset_at: float
    retry_after: Optional[float] = None
    tier: RateLimitTier = RateLimitTier.FREE


class SlidingWindowCounter:
    """
    Sliding window rate limiter

    Uses a sliding window algorithm for smooth rate limiting.
    """

    def __init__(self, window_size_seconds: int, max_requests: int):
        self.window_size = window_size_seconds
        self.max_requests = max_requests
        self.requests: List[float] = []

    def is_allowed(self) -> Tuple[bool, int, float]:
        """
        Check if request is allowed

        Returns: (allowed, remaining, reset_at)
        """
        now = time.time()

        # Remove old requests outside the window
        cutoff = now - self.window_size
        self.requests = [ts for ts in self.requests if ts > cutoff]

        remaining = self.max_requests - len(self.requests)
        reset_at = (self.requests[0] + self.window_size) if self.requests else (now + self.window_size)

        if len(self.requests) >= self.max_requests:
            return False, 0, reset_at

        # Record this request
        self.requests.append(now)
        return True, remaining - 1, reset_at


class RateLimiter:
    """
    Multi-tier rate limiter with sliding windows

    Supports per-user and per-endpoint rate limiting.
    """

    def __init__(self, redis_client: Any = None):
        self.redis = redis_client
        self.local_limiters: Dict[str, Dict[str, SlidingWindowCounter]] = defaultdict(dict)

    def _get_local_limiter(
        self,
        key: str,
        window: str,
        tier: RateLimitTier
    ) -> SlidingWindowCounter:
        """Get or create a local rate limiter"""
        config = TIER_LIMITS[tier]

        window_configs = {
            "minute": (60, config.requests_per_minute),
            "hour": (3600, config.requests_per_hour),
            "day": (86400, config.requests_per_day)
        }

        window_size, max_requests = window_configs[window]

        limiter_key = f"{key}:{window}"
        if limiter_key not in self.local_limiters:
            self.local_limiters[limiter_key] = {}

        if tier.value not in self.local_limiters[limiter_key]:
            self.local_limiters[limiter_key][tier.value] = SlidingWindowCounter(
                window_size, max_requests
            )

        return self.local_limiters[limiter_key][tier.value]

    async def check_rate_limit(
        self,
        identifier: str,
        tier: RateLimitTier = RateLimitTier.FREE,
        endpoint: str = "default"
    ) -> RateLimitResult:
        """
        Check if request is allowed

        Args:
            identifier: User ID or API key
            tier: Rate limit tier
            endpoint: Endpoint being accessed
        """
        key = f"{identifier}:{endpoint}"

        # Check all windows (minute, hour, day)
        for window in ["minute", "hour", "day"]:
            if self.redis:
                result = await self._check_redis(key, window, tier)
            else:
                result = self._check_local(key, window, tier)

            if not result.allowed:
                return result

        # All windows passed
        config = TIER_LIMITS[tier]
        return RateLimitResult(
            allowed=True,
            remaining=config.requests_per_minute,  # Simplified
            limit=config.requests_per_minute,
            reset_at=time.time() + 60,
            tier=tier
        )

    def _check_local(
        self,
        key: str,
        window: str,
        tier: RateLimitTier
    ) -> RateLimitResult:
        """Check rate limit using local storage"""
        limiter = self._get_local_limiter(key, window, tier)
        allowed, remaining, reset_at = limiter.is_allowed()

        config = TIER_LIMITS[tier]
        limit = {
            "minute": config.requests_per_minute,
            "hour": config.requests_per_hour,
            "day": config.requests_per_day
        }[window]

        return RateLimitResult(
            allowed=allowed,
            remaining=remaining,
            limit=limit,
            reset_at=reset_at,
            retry_after=reset_at - time.time() if not allowed else None,
            tier=tier
        )

    async def _check_redis(
        self,
        key: str,
        window: str,
        tier: RateLimitTier
    ) -> RateLimitResult:
        """Check rate limit using Redis"""
        config = TIER_LIMITS[tier]

        window_configs = {
            "minute": (60, config.requests_per_minute),
            "hour": (3600, config.requests_per_hour),
            "day": (86400, config.requests_per_day)
        }

        window_size, max_requests = window_configs[window]
        now = time.time()
        redis_key = f"ratelimit:{key}:{window}"

        try:
            pipe = self.redis.pipeline()

            # Remove old entries
            pipe.zremrangebyscore(redis_key, 0, now - window_size)

            # Count current entries
            pipe.zcard(redis_key)

            # Add current request
            pipe.zadd(redis_key, {str(now): now})

            # Set expiry
            pipe.expire(redis_key, window_size)

            results = await pipe.execute()
            count = results[1]

            if count >= max_requests:
                # Get oldest entry for reset time
                oldest = await self.redis.zrange(redis_key, 0, 0, withscores=True)
                reset_at = oldest[0][1] + window_size if oldest else now + window_size

                return RateLimitResult(
                    allowed=False,
                    remaining=0,
                    limit=max_requests,
                    reset_at=reset_at,
                    retry_after=reset_at - now,
                    tier=tier
                )

            return RateLimitResult(
                allowed=True,
                remaining=max_requests - count - 1,
                limit=max_requests,
                reset_at=now + window_size,
                tier=tier
            )

        except Exception as e:
            logger.error(f"Redis rate limit check failed: {e}")
            # Fall back to local
            return self._check_local(key, window, tier)

    async def get_usage(
        self,
        identifier: str,
        endpoint: str = "default"
    ) -> Dict[str, Any]:
        """Get current usage statistics"""
        key = f"{identifier}:{endpoint}"

        usage = {}
        for window in ["minute", "hour", "day"]:
            limiter_key = f"{key}:{window}"
            if limiter_key in self.local_limiters:
                for tier, limiter in self.local_limiters[limiter_key].items():
                    usage[f"{window}_{tier}"] = len(limiter.requests)

        return usage

    def reset(self, identifier: str, endpoint: str = "default"):
        """Reset rate limits for an identifier"""
        key = f"{identifier}:{endpoint}"

        for window in ["minute", "hour", "day"]:
            limiter_key = f"{key}:{window}"
            if limiter_key in self.local_limiters:
                self.local_limiters[limiter_key] = {}

        logger.info(f"Reset rate limits for {key}")


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get rate limiter singleton"""
    global _rate_limiter

    if _rate_limiter is None:
        _rate_limiter = RateLimiter()

    return _rate_limiter


async def check_rate_limit(
    identifier: str,
    tier: RateLimitTier = RateLimitTier.FREE,
    endpoint: str = "default"
) -> Tuple[bool, Dict[str, Any]]:
    """
    Convenience function to check rate limit

    Returns: (allowed, info_dict)
    """
    limiter = get_rate_limiter()
    result = await limiter.check_rate_limit(identifier, tier, endpoint)

    return result.allowed, {
        "remaining": result.remaining,
        "limit": result.limit,
        "reset_at": result.reset_at,
        "retry_after": result.retry_after,
        "tier": result.tier.value
    }


# Decorator for rate limiting
def rate_limited(tier: RateLimitTier = RateLimitTier.FREE, endpoint: str = "default"):
    """Decorator to apply rate limiting to async functions"""
    def decorator(func):
        async def wrapper(*args, identifier: str = "anonymous", **kwargs):
            allowed, info = await check_rate_limit(identifier, tier, endpoint)

            if not allowed:
                raise RateLimitExceeded(
                    f"Rate limit exceeded. Retry after {info['retry_after']:.0f} seconds.",
                    retry_after=info["retry_after"]
                )

            return await func(*args, **kwargs)

        return wrapper
    return decorator


class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded"""

    def __init__(self, message: str, retry_after: float = 0):
        super().__init__(message)
        self.retry_after = retry_after


# ============================================================
# Token Bucket Rate Limiter (Enhanced)
# ============================================================

@dataclass
class TokenBucketResult:
    """Result of a token bucket rate limit check."""
    allowed: bool
    remaining: int
    limit: int
    retry_after: Optional[float] = None
    status_code: int = 200

    def __post_init__(self):
        if not self.allowed:
            self.status_code = 429


class TokenBucket:
    """
    Token bucket implementation for rate limiting.

    Tokens are added at a fixed rate and consumed per request.
    Allows for bursting up to bucket capacity.
    """

    def __init__(self, capacity: int, refill_rate: float):
        """
        Initialize token bucket.

        Args:
            capacity: Maximum tokens (bucket size)
            refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = float(capacity)
        self.last_refill = time.time()

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    def consume(self, tokens: int = 1) -> Tuple[bool, float]:
        """
        Attempt to consume tokens.

        Args:
            tokens: Number of tokens to consume

        Returns:
            (success, wait_time) - wait_time is 0 if successful
        """
        self._refill()

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True, 0.0
        else:
            # Calculate wait time
            tokens_needed = tokens - self.tokens
            wait_time = tokens_needed / self.refill_rate
            return False, wait_time

    @property
    def available(self) -> int:
        """Get available tokens."""
        self._refill()
        return int(self.tokens)


class TokenBucketRateLimiter:
    """
    Token bucket rate limiter with support for multiple bucket types.

    Supports rate limiting by:
    - user_id: Per-user limits
    - ip: Per-IP limits
    - endpoint: Per-endpoint limits
    """

    def __init__(
        self,
        max_requests_per_minute: int = 100,
        bucket_type: str = "user_id",
        burst_size: Optional[int] = None
    ):
        """
        Initialize token bucket rate limiter.

        Args:
            max_requests_per_minute: Maximum requests per minute
            bucket_type: Type of bucketing ("user_id", "ip", "endpoint")
            burst_size: Maximum burst size (defaults to requests_per_minute)
        """
        self.max_requests_per_minute = max_requests_per_minute
        self.bucket_type = bucket_type
        self.burst_size = burst_size or max_requests_per_minute

        # Refill rate (tokens per second)
        self.refill_rate = max_requests_per_minute / 60.0

        # Buckets indexed by identifier
        self._buckets: Dict[str, TokenBucket] = {}

    def _get_bucket(self, identifier: str) -> TokenBucket:
        """Get or create bucket for identifier."""
        if identifier not in self._buckets:
            self._buckets[identifier] = TokenBucket(
                capacity=self.burst_size,
                refill_rate=self.refill_rate
            )
        return self._buckets[identifier]

    def check(self, identifier: str, tokens: int = 1) -> TokenBucketResult:
        """
        Check if request is allowed.

        Args:
            identifier: User ID, IP, or endpoint path
            tokens: Number of tokens to consume

        Returns:
            TokenBucketResult with allowed status
        """
        bucket = self._get_bucket(identifier)
        allowed, wait_time = bucket.consume(tokens)

        return TokenBucketResult(
            allowed=allowed,
            remaining=bucket.available,
            limit=self.max_requests_per_minute,
            retry_after=wait_time if not allowed else None
        )

    def reset(self, identifier: str) -> None:
        """Reset bucket for identifier."""
        if identifier in self._buckets:
            del self._buckets[identifier]

    def get_status(self, identifier: str) -> Dict[str, Any]:
        """Get status for identifier."""
        if identifier not in self._buckets:
            return {
                "identifier": identifier,
                "remaining": self.burst_size,
                "limit": self.max_requests_per_minute
            }

        bucket = self._buckets[identifier]
        return {
            "identifier": identifier,
            "remaining": bucket.available,
            "limit": self.max_requests_per_minute,
            "refill_rate": self.refill_rate
        }


# Convenience function for simple rate limiting
def simple_rate_check(
    identifier: str,
    max_per_minute: int = 100
) -> TokenBucketResult:
    """
    Simple rate limit check.

    Args:
        identifier: User/IP/endpoint identifier
        max_per_minute: Maximum requests per minute

    Returns:
        TokenBucketResult
    """
    # Use a module-level cache for the limiter
    global _simple_limiter
    if '_simple_limiter' not in globals() or _simple_limiter.max_requests_per_minute != max_per_minute:
        _simple_limiter = TokenBucketRateLimiter(max_requests_per_minute=max_per_minute)

    return _simple_limiter.check(identifier)


# Testing
if __name__ == "__main__":
    async def test():
        limiter = RateLimiter()

        # Test rate limiting
        print("Testing rate limits...")

        for i in range(15):
            result = await limiter.check_rate_limit(
                identifier="test_user",
                tier=RateLimitTier.FREE,
                endpoint="test"
            )

            status = "✅" if result.allowed else "❌"
            print(f"Request {i+1}: {status} | Remaining: {result.remaining}")

            if not result.allowed:
                print(f"  Retry after: {result.retry_after:.2f}s")

        # Test different tiers
        print("\n\nTesting different tiers...")

        for tier in [RateLimitTier.FREE, RateLimitTier.PRO, RateLimitTier.WHALE]:
            result = await limiter.check_rate_limit(
                identifier=f"user_{tier.value}",
                tier=tier,
                endpoint="test"
            )
            config = TIER_LIMITS[tier]
            print(f"{tier.value}: {config.requests_per_minute}/min, {config.requests_per_hour}/hour")

    asyncio.run(test())
