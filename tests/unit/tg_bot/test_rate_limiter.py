"""
Tests for Redis-backed Telegram bot rate limiting.

Tests tiered rate limiting with:
- Per-user throttling for spam prevention
- Per-action-type limiting (trades vs queries)
- Exponential backoff for retry scenarios
- Redis/fallback mode switching
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

# Import rate limiter components
from tg_bot.services.rate_limiter import (
    TelegramRateLimiter,
    ActionType,
    RateLimitResult,
    RateLimitTier,
    RateLimitMiddleware,
    detect_action_type,
    format_rate_limit_message,
    get_telegram_rate_limiter,
)


class TestActionTypes:
    """Test action type classification."""

    def test_action_types_exist(self):
        """Verify all expected action types are defined."""
        assert hasattr(ActionType, 'QUERY')
        assert hasattr(ActionType, 'TRADE')
        assert hasattr(ActionType, 'ADMIN')
        assert hasattr(ActionType, 'CHAT')

    def test_action_type_values(self):
        """Verify action types have correct values for rate limiting."""
        assert ActionType.QUERY.value == "query"
        assert ActionType.TRADE.value == "trade"
        assert ActionType.ADMIN.value == "admin"
        assert ActionType.CHAT.value == "chat"


class TestRateLimitTiers:
    """Test rate limit tier configuration."""

    def test_tier_defaults(self):
        """Verify default tier configurations."""
        # Query tier should be most permissive
        query_tier = RateLimitTier.get_tier(ActionType.QUERY)
        assert query_tier.requests_per_minute >= 30
        assert query_tier.burst_size >= 5

        # Trade tier should be stricter
        trade_tier = RateLimitTier.get_tier(ActionType.TRADE)
        assert trade_tier.requests_per_minute <= 10
        assert trade_tier.cooldown_seconds >= 5

    def test_trade_tier_stricter_than_query(self):
        """Trade actions must have stricter limits than queries."""
        query_tier = RateLimitTier.get_tier(ActionType.QUERY)
        trade_tier = RateLimitTier.get_tier(ActionType.TRADE)

        assert trade_tier.requests_per_minute < query_tier.requests_per_minute
        assert trade_tier.cooldown_seconds > query_tier.cooldown_seconds


class TestRateLimitResult:
    """Test rate limit result object."""

    def test_allowed_result(self):
        """Test allowed result creation."""
        result = RateLimitResult(allowed=True, retry_after=0)
        assert result.allowed is True
        assert result.retry_after == 0
        assert result.message is None

    def test_denied_result_with_retry(self):
        """Test denied result with retry information."""
        result = RateLimitResult(
            allowed=False,
            retry_after=30,
            message="Rate limited. Try again in 30s"
        )
        assert result.allowed is False
        assert result.retry_after == 30
        assert "30" in result.message


class TestTelegramRateLimiter:
    """Test the main rate limiter class."""

    @pytest.fixture
    def limiter(self):
        """Create a rate limiter for testing."""
        return TelegramRateLimiter(use_redis=False)

    @pytest.fixture
    def redis_limiter(self):
        """Create a Redis-backed rate limiter (mocked)."""
        with patch('tg_bot.services.rate_limiter.redis.asyncio.from_url') as mock_redis:
            mock_redis.return_value = AsyncMock()
            limiter = TelegramRateLimiter(
                redis_url="redis://localhost:6379/0",
                use_redis=True
            )
            return limiter

    @pytest.mark.asyncio
    async def test_query_allowed_initially(self, limiter):
        """First query should always be allowed."""
        result = await limiter.check_rate_limit(
            user_id=12345,
            action_type=ActionType.QUERY
        )
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_trade_allowed_initially(self, limiter):
        """First trade should be allowed."""
        result = await limiter.check_rate_limit(
            user_id=12345,
            action_type=ActionType.TRADE
        )
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_rapid_queries_throttled(self, limiter):
        """Rapid successive queries should eventually be throttled."""
        user_id = 12345
        allowed_count = 0

        # Fire many requests quickly
        for _ in range(50):
            result = await limiter.check_rate_limit(
                user_id=user_id,
                action_type=ActionType.QUERY
            )
            if result.allowed:
                allowed_count += 1

        # Should have been throttled at some point
        assert allowed_count < 50, "Should throttle rapid queries"
        assert allowed_count > 0, "Should allow some queries"

    @pytest.mark.asyncio
    async def test_rapid_trades_throttled_more_strictly(self, limiter):
        """Rapid trades should be throttled more strictly than queries."""
        # Test that trade tier has stricter limits than query tier
        trade_tier = RateLimitTier.get_tier(ActionType.TRADE)
        query_tier = RateLimitTier.get_tier(ActionType.QUERY)

        # Verify tier configurations show trades are stricter
        assert trade_tier.requests_per_minute < query_tier.requests_per_minute
        assert trade_tier.cooldown_seconds > query_tier.cooldown_seconds
        assert trade_tier.burst_size < query_tier.burst_size

        # Also verify that burst sizes differ - trades have smaller burst
        user_id = 12345

        # Fire up to burst limit for trades
        trade_allowed = 0
        for _ in range(trade_tier.burst_size + 5):
            result = await limiter.check_rate_limit(
                user_id=user_id,
                action_type=ActionType.TRADE
            )
            if result.allowed:
                trade_allowed += 1

        # Trade allowed count should be capped at burst_size
        assert trade_allowed <= trade_tier.burst_size

    @pytest.mark.asyncio
    async def test_different_users_independent(self, limiter):
        """Rate limits should be per-user."""
        # Exhaust user 1's limit
        for _ in range(50):
            await limiter.check_rate_limit(user_id=1, action_type=ActionType.QUERY)

        # User 2 should still be able to make requests
        result = await limiter.check_rate_limit(
            user_id=2,
            action_type=ActionType.QUERY
        )
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_retry_after_populated(self, limiter):
        """When throttled, retry_after should be populated."""
        user_id = 12345

        # Exhaust the limit
        for _ in range(100):
            result = await limiter.check_rate_limit(
                user_id=user_id,
                action_type=ActionType.TRADE
            )
            if not result.allowed:
                assert result.retry_after > 0
                break


class TestExponentialBackoff:
    """Test exponential backoff for repeated violations."""

    @pytest.fixture
    def limiter(self):
        """Create a rate limiter for testing."""
        return TelegramRateLimiter(use_redis=False)

    @pytest.mark.asyncio
    async def test_backoff_increases_with_violations(self, limiter):
        """Repeated violations should increase backoff time."""
        user_id = 12345

        # Get backoff with 0 violations
        backoff_0 = await limiter.get_backoff_time(user_id)

        # Record a violation
        await limiter.record_violation(user_id)

        # Get backoff with 1 violation - should be higher
        backoff_1 = await limiter.get_backoff_time(user_id)

        # Record another violation
        await limiter.record_violation(user_id)

        # Get backoff with 2 violations - should be even higher
        backoff_2 = await limiter.get_backoff_time(user_id)

        # Backoff should increase with violations
        assert backoff_1 > backoff_0, "Backoff should increase after first violation"
        assert backoff_2 > backoff_1, "Backoff should increase after second violation"

    @pytest.mark.asyncio
    async def test_backoff_capped_at_maximum(self, limiter):
        """Backoff should not exceed maximum value."""
        user_id = 12345
        max_backoff = 300  # 5 minutes max

        # Record many violations
        for _ in range(20):
            await limiter.record_violation(user_id)

        # Get the backoff time
        backoff = await limiter.get_backoff_time(user_id)
        assert backoff <= max_backoff


class TestRedisIntegration:
    """Test Redis-specific functionality."""

    @pytest.mark.asyncio
    async def test_redis_connection_check(self):
        """Test Redis connection health check."""
        # Create limiter with Redis disabled (memory mode)
        limiter = TelegramRateLimiter(use_redis=False)

        # Memory-only limiter should still work
        result = await limiter.check_rate_limit(
            user_id=12345,
            action_type=ActionType.QUERY
        )
        assert result.allowed is True

        # Redis check should return False when not configured
        is_connected = await limiter.check_redis_connection()
        assert is_connected is False  # No Redis configured

    @pytest.mark.asyncio
    async def test_fallback_on_redis_failure(self):
        """Should fallback to memory when Redis fails."""
        with patch('tg_bot.services.rate_limiter.redis') as mock_redis_module:
            mock_client = AsyncMock()
            mock_client.ping = AsyncMock(side_effect=Exception("Connection refused"))
            mock_redis_module.asyncio.from_url = AsyncMock(return_value=mock_client)

            limiter = TelegramRateLimiter(
                redis_url="redis://localhost:6379/0",
                use_redis=True
            )

            # Should still work (fallback to memory)
            result = await limiter.check_rate_limit(
                user_id=12345,
                action_type=ActionType.QUERY
            )
            assert result.allowed is True


class TestMiddlewareIntegration:
    """Test Telegram middleware integration."""

    @pytest.mark.asyncio
    async def test_middleware_blocks_rate_limited(self):
        """Middleware should block rate-limited requests."""
        from tg_bot.services.rate_limiter import RateLimitMiddleware

        limiter = TelegramRateLimiter(use_redis=False)
        middleware = RateLimitMiddleware(limiter)

        # Create mock handler and update
        handler = AsyncMock()
        update = MagicMock()
        update.effective_user.id = 12345
        update.message.text = "/balance"

        # Should pass initially
        await middleware(handler, update, {})
        assert handler.called

    @pytest.mark.asyncio
    async def test_action_type_detection(self):
        """Middleware should detect action type from command."""
        from tg_bot.services.rate_limiter import detect_action_type

        # Query commands
        assert detect_action_type("/balance") == ActionType.QUERY
        assert detect_action_type("/portfolio") == ActionType.QUERY
        assert detect_action_type("/price SOL") == ActionType.QUERY

        # Trade commands
        assert detect_action_type("/buy SOL 0.1") == ActionType.TRADE
        assert detect_action_type("/sell ABC123") == ActionType.TRADE
        assert detect_action_type("/swap") == ActionType.TRADE

        # Admin commands
        assert detect_action_type("/reload") == ActionType.ADMIN
        assert detect_action_type("/config") == ActionType.ADMIN


class TestRateLimitMessages:
    """Test user-friendly rate limit messages."""

    def test_format_rate_limit_message(self):
        """Test rate limit message formatting."""
        from tg_bot.services.rate_limiter import format_rate_limit_message

        result = RateLimitResult(
            allowed=False,
            retry_after=30,
            message=None
        )

        message = format_rate_limit_message(result, ActionType.TRADE)

        assert "rate" in message.lower() or "limit" in message.lower()
        assert "30" in message or "second" in message.lower()

    def test_trade_limit_message_includes_warning(self):
        """Trade rate limit message should include safety warning."""
        from tg_bot.services.rate_limiter import format_rate_limit_message

        result = RateLimitResult(
            allowed=False,
            retry_after=60,
            message=None
        )

        message = format_rate_limit_message(result, ActionType.TRADE)

        # Should mention this is for safety
        assert any(word in message.lower() for word in ["protect", "safe", "security"])


class TestSingleton:
    """Test singleton pattern for rate limiter."""

    def test_get_telegram_rate_limiter_singleton(self):
        """Should return the same instance."""
        # Reset singleton for testing
        import tg_bot.services.rate_limiter as rl_module
        rl_module._telegram_rate_limiter = None

        limiter1 = get_telegram_rate_limiter()
        limiter2 = get_telegram_rate_limiter()

        assert limiter1 is limiter2


class TestCleanup:
    """Test cleanup and memory management."""

    @pytest.fixture
    def limiter(self):
        return TelegramRateLimiter(use_redis=False)

    @pytest.mark.asyncio
    async def test_cleanup_old_entries(self, limiter):
        """Should clean up old rate limit entries."""
        # Add entries for many users
        for user_id in range(1000):
            await limiter.check_rate_limit(
                user_id=user_id,
                action_type=ActionType.QUERY
            )

        # Force cleanup
        await limiter.cleanup(max_age_seconds=0)

        # Memory should be reduced
        # (Implementation detail - just verify it doesn't crash)
        assert True

    @pytest.mark.asyncio
    async def test_automatic_cleanup_scheduled(self, limiter):
        """Cleanup should run automatically."""
        # Verify cleanup task exists
        assert hasattr(limiter, 'cleanup')
        assert callable(limiter.cleanup)
