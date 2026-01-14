"""
JARVIS Bot Rate Limiter

Provides rate limiting for bot commands and messages
to prevent abuse and ensure fair usage.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
from enum import Enum
import asyncio
import logging
import time

logger = logging.getLogger(__name__)


class RateLimitStrategy(Enum):
    """Rate limiting strategies."""
    SLIDING_WINDOW = "sliding_window"
    TOKEN_BUCKET = "token_bucket"
    FIXED_WINDOW = "fixed_window"


@dataclass
class RateLimitConfig:
    """Configuration for a rate limit."""
    requests: int          # Max requests
    window_seconds: int    # Time window
    burst: int = 0         # Burst allowance
    cooldown_seconds: int = 0  # Cooldown after limit hit


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""
    allowed: bool
    remaining: int
    reset_at: datetime
    retry_after: Optional[int] = None
    message: str = ""


# Default limits for different contexts
DEFAULT_LIMITS = {
    "user_message": RateLimitConfig(requests=30, window_seconds=60),
    "user_command": RateLimitConfig(requests=10, window_seconds=60),
    "user_trade": RateLimitConfig(requests=5, window_seconds=60, cooldown_seconds=10),
    "chat_message": RateLimitConfig(requests=100, window_seconds=60),
    "global": RateLimitConfig(requests=1000, window_seconds=60),
}


class SlidingWindowLimiter:
    """
    Sliding window rate limiter.

    Tracks requests in a sliding time window for accurate rate limiting.
    """

    def __init__(self, config: RateLimitConfig):
        self.config = config
        self._requests: Dict[str, List[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def check(self, key: str) -> RateLimitResult:
        """Check if a request is allowed."""
        now = time.time()
        window_start = now - self.config.window_seconds

        async with self._lock:
            # Clean old requests
            self._requests[key] = [
                ts for ts in self._requests[key]
                if ts > window_start
            ]

            current_count = len(self._requests[key])
            allowed = current_count < self.config.requests

            if allowed:
                self._requests[key].append(now)
                remaining = self.config.requests - current_count - 1
            else:
                remaining = 0
                # Calculate retry after
                oldest = min(self._requests[key]) if self._requests[key] else now
                retry_after = int(oldest - window_start) + 1

            reset_at = datetime.utcnow() + timedelta(seconds=self.config.window_seconds)

            return RateLimitResult(
                allowed=allowed,
                remaining=remaining,
                reset_at=reset_at,
                retry_after=None if allowed else retry_after,
                message="" if allowed else f"Rate limit exceeded. Try again in {retry_after}s",
            )


class TokenBucketLimiter:
    """
    Token bucket rate limiter.

    Allows bursts while maintaining a long-term rate limit.
    """

    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.rate = config.requests / config.window_seconds
        self.capacity = config.requests + config.burst
        self._buckets: Dict[str, Tuple[float, float]] = {}  # key -> (tokens, last_update)
        self._lock = asyncio.Lock()

    async def check(self, key: str) -> RateLimitResult:
        """Check if a request is allowed."""
        now = time.time()

        async with self._lock:
            if key not in self._buckets:
                self._buckets[key] = (self.capacity, now)

            tokens, last_update = self._buckets[key]

            # Add tokens based on time passed
            elapsed = now - last_update
            tokens = min(self.capacity, tokens + elapsed * self.rate)

            allowed = tokens >= 1

            if allowed:
                tokens -= 1
                self._buckets[key] = (tokens, now)
                remaining = int(tokens)
            else:
                remaining = 0
                # Time until next token
                retry_after = int((1 - tokens) / self.rate) + 1

            reset_at = datetime.utcnow() + timedelta(seconds=1 / self.rate)

            return RateLimitResult(
                allowed=allowed,
                remaining=remaining,
                reset_at=reset_at,
                retry_after=None if allowed else retry_after,
                message="" if allowed else f"Rate limit exceeded. Try again in {retry_after}s",
            )


class FixedWindowLimiter:
    """
    Fixed window rate limiter.

    Simple counter reset at fixed intervals.
    """

    def __init__(self, config: RateLimitConfig):
        self.config = config
        self._windows: Dict[str, Tuple[int, int]] = {}  # key -> (count, window_id)
        self._lock = asyncio.Lock()

    def _get_window_id(self) -> int:
        """Get current window ID."""
        return int(time.time() / self.config.window_seconds)

    async def check(self, key: str) -> RateLimitResult:
        """Check if a request is allowed."""
        window_id = self._get_window_id()

        async with self._lock:
            if key not in self._windows or self._windows[key][1] != window_id:
                self._windows[key] = (0, window_id)

            count, _ = self._windows[key]
            allowed = count < self.config.requests

            if allowed:
                self._windows[key] = (count + 1, window_id)
                remaining = self.config.requests - count - 1
            else:
                remaining = 0

            # Calculate reset time
            next_window = (window_id + 1) * self.config.window_seconds
            reset_at = datetime.utcfromtimestamp(next_window)
            retry_after = int(next_window - time.time()) + 1

            return RateLimitResult(
                allowed=allowed,
                remaining=remaining,
                reset_at=reset_at,
                retry_after=None if allowed else retry_after,
                message="" if allowed else f"Rate limit exceeded. Try again in {retry_after}s",
            )


class BotRateLimiter:
    """
    Main rate limiter for bot operations.

    Supports multiple limit types and strategies.

    Usage:
        limiter = BotRateLimiter()
        result = await limiter.check_limit("user_123", "command")
        if not result.allowed:
            return f"Rate limited. {result.message}"
    """

    def __init__(
        self,
        limits: Optional[Dict[str, RateLimitConfig]] = None,
        strategy: RateLimitStrategy = RateLimitStrategy.SLIDING_WINDOW
    ):
        self.limits = limits or DEFAULT_LIMITS
        self.strategy = strategy
        self._limiters: Dict[str, object] = {}
        self._cooldowns: Dict[str, float] = {}
        self._lock = asyncio.Lock()

    def _get_limiter(self, limit_type: str):
        """Get or create a limiter for the given type."""
        if limit_type not in self._limiters:
            config = self.limits.get(limit_type, DEFAULT_LIMITS["user_message"])

            if self.strategy == RateLimitStrategy.SLIDING_WINDOW:
                self._limiters[limit_type] = SlidingWindowLimiter(config)
            elif self.strategy == RateLimitStrategy.TOKEN_BUCKET:
                self._limiters[limit_type] = TokenBucketLimiter(config)
            else:
                self._limiters[limit_type] = FixedWindowLimiter(config)

        return self._limiters[limit_type]

    async def check_limit(
        self,
        user_id: str,
        limit_type: str = "user_message",
        chat_id: Optional[str] = None
    ) -> RateLimitResult:
        """Check if a request is within rate limits."""
        # Check cooldown first
        cooldown_key = f"{user_id}:{limit_type}"
        if cooldown_key in self._cooldowns:
            if time.time() < self._cooldowns[cooldown_key]:
                remaining = int(self._cooldowns[cooldown_key] - time.time())
                return RateLimitResult(
                    allowed=False,
                    remaining=0,
                    reset_at=datetime.utcfromtimestamp(self._cooldowns[cooldown_key]),
                    retry_after=remaining,
                    message=f"In cooldown. Wait {remaining}s",
                )
            else:
                del self._cooldowns[cooldown_key]

        limiter = self._get_limiter(limit_type)
        key = f"{user_id}:{limit_type}"

        result = await limiter.check(key)

        # Apply cooldown if limit hit
        if not result.allowed:
            config = self.limits.get(limit_type)
            if config and config.cooldown_seconds > 0:
                self._cooldowns[cooldown_key] = time.time() + config.cooldown_seconds

        # Also check chat limit if applicable
        if chat_id and result.allowed:
            chat_limiter = self._get_limiter("chat_message")
            chat_result = await chat_limiter.check(f"chat:{chat_id}")
            if not chat_result.allowed:
                return chat_result

        return result

    async def get_status(self, user_id: str, limit_type: str = "user_message") -> Dict:
        """Get current rate limit status for a user."""
        limiter = self._get_limiter(limit_type)
        key = f"{user_id}:{limit_type}"

        # Get current count without consuming
        if isinstance(limiter, SlidingWindowLimiter):
            now = time.time()
            window_start = now - limiter.config.window_seconds
            async with limiter._lock:
                requests = [ts for ts in limiter._requests.get(key, []) if ts > window_start]
                count = len(requests)
        elif isinstance(limiter, TokenBucketLimiter):
            async with limiter._lock:
                tokens, _ = limiter._buckets.get(key, (limiter.capacity, time.time()))
                count = limiter.capacity - int(tokens)
        else:
            async with limiter._lock:
                count, _ = limiter._windows.get(key, (0, 0))

        config = self.limits.get(limit_type, DEFAULT_LIMITS["user_message"])

        return {
            "user_id": user_id,
            "limit_type": limit_type,
            "used": count,
            "limit": config.requests,
            "remaining": max(0, config.requests - count),
            "window_seconds": config.window_seconds,
        }


def rate_limit(
    limit_type: str = "user_command",
    on_limit: Optional[str] = None
):
    """
    Decorator for rate limiting bot command handlers.

    Usage:
        @rate_limit("user_command")
        async def handle_command(update, context):
            ...
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract user_id from args (depends on bot framework)
            user_id = None
            for arg in args:
                if hasattr(arg, "effective_user"):
                    user_id = str(arg.effective_user.id)
                    break
                if hasattr(arg, "from_user"):
                    user_id = str(arg.from_user.id)
                    break

            if not user_id:
                # Can't rate limit without user ID
                return await func(*args, **kwargs)

            limiter = get_rate_limiter()
            result = await limiter.check_limit(user_id, limit_type)

            if not result.allowed:
                logger.warning(f"Rate limited user {user_id}: {result.message}")
                if on_limit:
                    return on_limit
                return None

            return await func(*args, **kwargs)

        return wrapper
    return decorator


# Global instance
_rate_limiter: Optional[BotRateLimiter] = None


def get_rate_limiter() -> BotRateLimiter:
    """Get the global rate limiter."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = BotRateLimiter()
    return _rate_limiter


def configure_rate_limits(limits: Dict[str, RateLimitConfig]) -> None:
    """Configure global rate limits."""
    global _rate_limiter
    _rate_limiter = BotRateLimiter(limits=limits)
