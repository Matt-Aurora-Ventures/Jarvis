"""
Redis-backed Rate Limiter for Telegram Bot.

Provides tiered rate limiting with:
- Per-user throttling for spam prevention
- Per-action-type limiting (trades stricter than queries)
- Exponential backoff for retry scenarios
- Redis for distributed state (with in-memory fallback)
"""

import asyncio
import hashlib
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Try to import redis
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None


class ActionType(Enum):
    """Types of actions with different rate limit tiers."""
    QUERY = "query"       # Balance, portfolio, prices - permissive
    TRADE = "trade"       # Buy, sell, swap - strict
    ADMIN = "admin"       # Admin commands - moderate
    CHAT = "chat"         # General chat messages - permissive


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""
    allowed: bool
    retry_after: float = 0
    message: Optional[str] = None


@dataclass
class TierConfig:
    """Configuration for a rate limit tier."""
    requests_per_minute: int
    burst_size: int
    cooldown_seconds: float
    max_backoff_seconds: float = 300  # 5 minutes max


class RateLimitTier:
    """Rate limit tier configurations."""

    _TIERS: Dict[ActionType, TierConfig] = {
        ActionType.QUERY: TierConfig(
            requests_per_minute=60,     # 1 per second average
            burst_size=10,              # Allow bursts of 10
            cooldown_seconds=1,         # 1 second between requests
            max_backoff_seconds=60,     # Max 1 minute backoff
        ),
        ActionType.TRADE: TierConfig(
            requests_per_minute=6,      # 1 every 10 seconds average
            burst_size=3,               # Allow bursts of 3
            cooldown_seconds=10,        # 10 seconds between trades
            max_backoff_seconds=300,    # Max 5 minute backoff (safety)
        ),
        ActionType.ADMIN: TierConfig(
            requests_per_minute=30,     # 1 every 2 seconds
            burst_size=5,               # Allow bursts of 5
            cooldown_seconds=2,         # 2 seconds between admin ops
            max_backoff_seconds=120,    # Max 2 minute backoff
        ),
        ActionType.CHAT: TierConfig(
            requests_per_minute=30,     # 1 every 2 seconds
            burst_size=5,               # Allow bursts of 5
            cooldown_seconds=2,         # 2 seconds between messages
            max_backoff_seconds=60,     # Max 1 minute backoff
        ),
    }

    @classmethod
    def get_tier(cls, action_type: ActionType) -> TierConfig:
        """Get the tier configuration for an action type."""
        return cls._TIERS.get(action_type, cls._TIERS[ActionType.QUERY])


@dataclass
class UserState:
    """In-memory state for a user."""
    tokens: float = 0
    last_update: float = 0
    violations: int = 0
    last_violation: float = 0

    # Per-action-type tracking
    action_counts: Dict[str, int] = field(default_factory=dict)
    action_times: Dict[str, float] = field(default_factory=dict)


class TelegramRateLimiter:
    """
    Redis-backed rate limiter for Telegram bot.

    Features:
    - Per-user rate limiting
    - Per-action-type tiers (trades stricter than queries)
    - Exponential backoff for violations
    - Redis backend with in-memory fallback
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        use_redis: bool = True,
        key_prefix: str = "tg_ratelimit:"
    ):
        """
        Initialize the rate limiter.

        Args:
            redis_url: Redis connection URL (e.g., "redis://localhost:6379/0")
            use_redis: Whether to attempt Redis connection
            key_prefix: Prefix for Redis keys
        """
        self.redis_url = redis_url or "redis://localhost:6379/0"
        self.use_redis = use_redis and REDIS_AVAILABLE
        self.key_prefix = key_prefix

        # Redis client (lazy initialized)
        self._redis: Optional[Any] = None
        self._redis_connected = False

        # In-memory fallback state
        self._memory_state: Dict[int, UserState] = defaultdict(UserState)
        self._lock = asyncio.Lock()

        logger.info(
            f"TelegramRateLimiter initialized (redis={self.use_redis}, "
            f"available={REDIS_AVAILABLE})"
        )

    async def _get_redis(self) -> Optional[Any]:
        """Get Redis client, initializing if needed."""
        if not self.use_redis:
            return None

        if self._redis is None:
            try:
                self._redis = redis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True
                )
                # Test connection
                await self._redis.ping()
                self._redis_connected = True
                logger.info("Redis connection established")
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}, using memory fallback")
                self._redis_connected = False
                self._redis = None

        return self._redis if self._redis_connected else None

    async def check_redis_connection(self) -> bool:
        """Check if Redis is connected and healthy."""
        try:
            redis_client = await self._get_redis()
            if redis_client:
                await redis_client.ping()
                return True
        except Exception as e:
            logger.warning(f"Redis health check failed: {e}")
        return False

    def _get_user_key(self, user_id: int, action_type: ActionType) -> str:
        """Generate Redis key for user rate limit."""
        return f"{self.key_prefix}{user_id}:{action_type.value}"

    def _get_violation_key(self, user_id: int) -> str:
        """Generate Redis key for user violations."""
        return f"{self.key_prefix}violations:{user_id}"

    async def check_rate_limit(
        self,
        user_id: int,
        action_type: ActionType
    ) -> RateLimitResult:
        """
        Check if a user action should be allowed.

        Args:
            user_id: Telegram user ID
            action_type: Type of action being performed

        Returns:
            RateLimitResult with allowed status and retry info
        """
        tier = RateLimitTier.get_tier(action_type)

        # Try Redis first
        redis_client = await self._get_redis()
        if redis_client:
            return await self._check_redis(user_id, action_type, tier, redis_client)

        # Fallback to memory
        return await self._check_memory(user_id, action_type, tier)

    async def _check_redis(
        self,
        user_id: int,
        action_type: ActionType,
        tier: TierConfig,
        redis_client: Any
    ) -> RateLimitResult:
        """Check rate limit using Redis."""
        key = self._get_user_key(user_id, action_type)
        violation_key = self._get_violation_key(user_id)
        now = time.time()

        try:
            # Use Redis sorted set for sliding window
            window_seconds = 60  # 1 minute window

            # Remove old entries
            await redis_client.zremrangebyscore(key, 0, now - window_seconds)

            # Count requests in window
            request_count = await redis_client.zcard(key)

            # Check if over limit
            if request_count >= tier.requests_per_minute:
                # Get violations for backoff
                violations = int(await redis_client.get(violation_key) or 0)
                backoff = self._calculate_backoff(violations, tier)

                return RateLimitResult(
                    allowed=False,
                    retry_after=backoff,
                    message=f"Rate limited. Try again in {int(backoff)}s"
                )

            # Check burst (requests in last cooldown_seconds)
            burst_count = await redis_client.zcount(
                key, now - tier.cooldown_seconds, now
            )
            if burst_count >= tier.burst_size:
                return RateLimitResult(
                    allowed=False,
                    retry_after=tier.cooldown_seconds,
                    message=f"Please wait {tier.cooldown_seconds}s between requests"
                )

            # Allow request - add to window
            await redis_client.zadd(key, {str(now): now})
            await redis_client.expire(key, window_seconds + 10)

            return RateLimitResult(allowed=True)

        except Exception as e:
            # During shutdown, event loop may be closed - this is expected
            if "Event loop is closed" in str(e):
                logger.debug(f"Redis unavailable (shutdown): {e}, using memory")
            else:
                logger.warning(f"Redis rate limit error: {e}, falling back to memory")
            return await self._check_memory(user_id, action_type, tier)

    async def _check_memory(
        self,
        user_id: int,
        action_type: ActionType,
        tier: TierConfig
    ) -> RateLimitResult:
        """Check rate limit using in-memory state (fallback)."""
        now = time.time()

        async with self._lock:
            state = self._memory_state[user_id]

            # Initialize tokens if first request
            if state.last_update == 0:
                state.tokens = tier.burst_size
                state.last_update = now

            # Refill tokens based on elapsed time
            elapsed = now - state.last_update
            refill_rate = tier.requests_per_minute / 60.0  # tokens per second
            state.tokens = min(
                tier.burst_size,
                state.tokens + elapsed * refill_rate
            )
            state.last_update = now

            # Check per-action cooldown
            action_key = action_type.value
            last_action = state.action_times.get(action_key, 0)
            time_since_last = now - last_action

            if time_since_last < tier.cooldown_seconds and last_action > 0:
                return RateLimitResult(
                    allowed=False,
                    retry_after=tier.cooldown_seconds - time_since_last,
                    message=f"Please wait {tier.cooldown_seconds - time_since_last:.0f}s"
                )

            # Check tokens
            if state.tokens < 1:
                backoff = self._calculate_backoff(state.violations, tier)
                return RateLimitResult(
                    allowed=False,
                    retry_after=backoff,
                    message=f"Rate limited. Try again in {int(backoff)}s"
                )

            # Allow - consume token and record action
            state.tokens -= 1
            state.action_times[action_key] = now
            state.action_counts[action_key] = state.action_counts.get(action_key, 0) + 1

            return RateLimitResult(allowed=True)

    def _calculate_backoff(self, violations: int, tier: TierConfig) -> float:
        """Calculate exponential backoff based on violations."""
        # Base backoff is the cooldown
        base = tier.cooldown_seconds

        # Exponential increase: base * 2^violations
        backoff = base * (2 ** min(violations, 6))  # Cap exponential growth

        # Cap at max
        return min(backoff, tier.max_backoff_seconds)

    async def record_violation(self, user_id: int) -> None:
        """Record a rate limit violation for a user (increases backoff)."""
        redis_client = await self._get_redis()

        if redis_client:
            try:
                key = self._get_violation_key(user_id)
                await redis_client.incr(key)
                await redis_client.expire(key, 3600)  # Expire violations after 1 hour
                return
            except Exception as e:
                logger.warning(f"Failed to record violation in Redis: {e}")

        # Fallback to memory
        async with self._lock:
            state = self._memory_state[user_id]
            state.violations += 1
            state.last_violation = time.time()

    async def get_backoff_time(self, user_id: int) -> float:
        """Get current backoff time for a user."""
        redis_client = await self._get_redis()

        if redis_client:
            try:
                key = self._get_violation_key(user_id)
                violations = int(await redis_client.get(key) or 0)
                return self._calculate_backoff(
                    violations,
                    RateLimitTier.get_tier(ActionType.TRADE)
                )
            except Exception as e:
                logger.warning(f"Failed to get backoff from Redis: {e}")

        # Fallback to memory
        async with self._lock:
            state = self._memory_state[user_id]
            return self._calculate_backoff(
                state.violations,
                RateLimitTier.get_tier(ActionType.TRADE)
            )

    async def cleanup(self, max_age_seconds: int = 3600) -> int:
        """
        Clean up old rate limit entries.

        Args:
            max_age_seconds: Remove entries older than this

        Returns:
            Number of entries cleaned up
        """
        cleaned = 0
        now = time.time()

        # Clean memory state
        async with self._lock:
            to_remove = []
            for user_id, state in self._memory_state.items():
                if now - state.last_update > max_age_seconds:
                    to_remove.append(user_id)

            for user_id in to_remove:
                del self._memory_state[user_id]
                cleaned += 1

        logger.info(f"Cleaned up {cleaned} rate limit entries")
        return cleaned


def detect_action_type(text: str) -> ActionType:
    """
    Detect the action type from a command or message.

    Args:
        text: Command text (e.g., "/buy SOL 0.1")

    Returns:
        ActionType for rate limiting
    """
    if not text:
        return ActionType.CHAT

    text_lower = text.lower().strip()

    # Trade commands (strict)
    trade_commands = [
        "/buy", "/sell", "/swap", "/trade", "/execute",
        "/ape", "/simbuy", "/simsell", "/quickbuy", "/quicksell",
        "/limit", "/stop", "/tp", "/sl",
    ]
    if any(text_lower.startswith(cmd) for cmd in trade_commands):
        return ActionType.TRADE

    # Admin commands (moderate)
    admin_commands = [
        "/reload", "/config", "/logs", "/system", "/errors",
        "/away", "/back", "/memory", "/sysmem", "/metrics",
        "/addscam", "/trust", "/unspam", "/warn", "/unban",
        "/togglemedia", "/xbot", "/flag",
    ]
    if any(text_lower.startswith(cmd) for cmd in admin_commands):
        return ActionType.ADMIN

    # Query commands (permissive)
    query_commands = [
        "/balance", "/portfolio", "/positions", "/price",
        "/analyze", "/trending", "/sentiment", "/digest",
        "/help", "/start", "/status", "/about", "/commands",
        "/watchlist", "/search", "/chart", "/score",
        "/treasury", "/pnl", "/dashboard", "/wallet",
        "/gainers", "/losers", "/stocks", "/solprice",
        "/mcap", "/volume", "/liquidity", "/age", "/summary",
        "/signals", "/keystatus", "/health", "/flags",
        "/audit", "/ratelimits", "/orders", "/calibrate",
        "/sector", "/settings", "/compare", "/watch", "/unwatch",
        "/searchp", "/export", "/exportpos", "/exporttrades",
        "/quick", "/analytics", "/perfstats", "/performers",
        "/tokenperf", "/trustscore", "/sim", "/simpos",
        "/demo", "/paper", "/dev", "/report", "/picks",
        "/costs", "/brain", "/code", "/vibe", "/console",
        "/remember", "/modstats", "/upgrades", "/uptime",
        "/clistats", "/stats", "/queue", "/newpairs",
    ]
    if any(text_lower.startswith(cmd) for cmd in query_commands):
        return ActionType.QUERY

    # Default to chat for non-commands
    if not text_lower.startswith("/"):
        return ActionType.CHAT

    # Unknown command - treat as query
    return ActionType.QUERY


class RateLimitMiddleware:
    """
    Middleware for Telegram bot rate limiting.

    Usage:
        limiter = TelegramRateLimiter()
        middleware = RateLimitMiddleware(limiter)

        # In handler
        async def my_handler(update, context):
            result = await middleware.check(update)
            if not result.allowed:
                await update.message.reply_text(result.message)
                return
            # ... handle normally
    """

    def __init__(self, limiter: TelegramRateLimiter):
        self.limiter = limiter

    async def __call__(
        self,
        handler: Callable,
        update: Any,
        context: Any
    ) -> Any:
        """Process update through rate limiting."""
        # Get user ID
        user_id = None
        if hasattr(update, 'effective_user') and update.effective_user:
            user_id = update.effective_user.id

        if user_id is None:
            # Can't rate limit without user ID
            return await handler(update, context)

        # Get command text
        text = ""
        if hasattr(update, 'message') and update.message:
            text = update.message.text or ""
        elif hasattr(update, 'callback_query') and update.callback_query:
            text = update.callback_query.data or ""

        # Detect action type
        action_type = detect_action_type(text)

        # Check rate limit
        result = await self.limiter.check_rate_limit(user_id, action_type)

        if not result.allowed:
            # Send rate limit message
            message = format_rate_limit_message(result, action_type)

            if hasattr(update, 'message') and update.message:
                await update.message.reply_text(message)
            elif hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.answer(message[:200], show_alert=True)

            # Record violation for backoff
            await self.limiter.record_violation(user_id)
            return None

        # Proceed with handler
        return await handler(update, context)


def format_rate_limit_message(result: RateLimitResult, action_type: ActionType) -> str:
    """
    Format a user-friendly rate limit message.

    Args:
        result: The rate limit result
        action_type: Type of action that was limited

    Returns:
        Formatted message string
    """
    retry_str = f"{int(result.retry_after)}" if result.retry_after else "a moment"

    if action_type == ActionType.TRADE:
        return (
            f"Slow down there, partner! Trade commands have stricter limits "
            f"to protect your funds.\n\n"
            f"Please wait {retry_str} seconds before trying again.\n\n"
            f"This is a security feature to prevent accidental rapid trades."
        )
    elif action_type == ActionType.ADMIN:
        return (
            f"Admin command rate limited.\n"
            f"Please wait {retry_str} seconds before trying again."
        )
    else:
        return (
            f"You're sending requests too quickly!\n"
            f"Please wait {retry_str} seconds before trying again."
        )


# Singleton instance
_telegram_rate_limiter: Optional[TelegramRateLimiter] = None


def get_telegram_rate_limiter(
    redis_url: Optional[str] = None,
    use_redis: bool = True
) -> TelegramRateLimiter:
    """
    Get the singleton Telegram rate limiter.

    Args:
        redis_url: Redis URL (only used on first call)
        use_redis: Whether to use Redis (only used on first call)

    Returns:
        TelegramRateLimiter instance
    """
    global _telegram_rate_limiter

    if _telegram_rate_limiter is None:
        import os
        # Try to get Redis URL from environment
        url = redis_url or os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        _telegram_rate_limiter = TelegramRateLimiter(
            redis_url=url,
            use_redis=use_redis
        )

    return _telegram_rate_limiter
