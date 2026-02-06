"""
Comprehensive tests for the main RateLimiter class.

Tests cover:
1. RateLimiter class interface
2. check(key, limit, window) -> bool
3. get_remaining(key) -> int
4. get_reset_time(key) -> datetime
5. wait_if_limited(key) - async wait

Target: Full coverage of limiter API
"""

import pytest
import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


# =============================================================================
# RateLimiter Class Tests
# =============================================================================

class TestRateLimiterBasic:
    """Basic tests for RateLimiter class."""

    def test_import(self):
        """Test that RateLimiter can be imported."""
        from core.ratelimit.limiter import RateLimiter
        assert RateLimiter is not None

    def test_initialization_default(self):
        """Test default initialization."""
        from core.ratelimit.limiter import RateLimiter
        limiter = RateLimiter()
        assert limiter is not None

    def test_initialization_with_storage(self):
        """Test initialization with custom storage."""
        from core.ratelimit.limiter import RateLimiter
        from core.ratelimit.storage import InMemoryStorage

        storage = InMemoryStorage()
        limiter = RateLimiter(storage=storage)

        assert limiter.storage == storage


class TestRateLimiterCheck:
    """Tests for RateLimiter.check() method."""

    def test_check_allows_within_limit(self):
        """Test check allows requests within limit."""
        from core.ratelimit.limiter import RateLimiter
        limiter = RateLimiter()

        # Should allow first request
        result = limiter.check("user:123", limit=10, window=60)
        assert result is True

    def test_check_allows_up_to_limit(self):
        """Test check allows requests up to limit."""
        from core.ratelimit.limiter import RateLimiter
        limiter = RateLimiter()

        # Should allow up to limit
        for i in range(10):
            result = limiter.check("user:456", limit=10, window=60)
            assert result is True

    def test_check_blocks_over_limit(self):
        """Test check blocks requests over limit."""
        from core.ratelimit.limiter import RateLimiter
        limiter = RateLimiter()

        # Fill up the limit
        for _ in range(5):
            limiter.check("user:789", limit=5, window=60)

        # Should block
        result = limiter.check("user:789", limit=5, window=60)
        assert result is False

    def test_check_different_keys_isolated(self):
        """Test different keys have isolated limits."""
        from core.ratelimit.limiter import RateLimiter
        limiter = RateLimiter()

        # Fill user:1 limit
        for _ in range(3):
            limiter.check("user:1", limit=3, window=60)

        # user:1 is blocked
        assert limiter.check("user:1", limit=3, window=60) is False

        # user:2 should still be allowed
        assert limiter.check("user:2", limit=3, window=60) is True

    def test_check_resets_after_window(self):
        """Test that limits reset after window expires."""
        from core.ratelimit.limiter import RateLimiter
        limiter = RateLimiter()

        # Fill the limit
        for _ in range(3):
            limiter.check("user:window", limit=3, window=0.1)

        # Should be blocked
        assert limiter.check("user:window", limit=3, window=0.1) is False

        # Wait for window to expire
        time.sleep(0.15)

        # Should be allowed again
        assert limiter.check("user:window", limit=3, window=0.1) is True


class TestRateLimiterGetRemaining:
    """Tests for RateLimiter.get_remaining() method."""

    def test_get_remaining_full_quota(self):
        """Test get_remaining returns full quota for new key."""
        from core.ratelimit.limiter import RateLimiter
        limiter = RateLimiter()

        remaining = limiter.get_remaining("new:key", limit=10, window=60)
        assert remaining == 10

    def test_get_remaining_after_requests(self):
        """Test get_remaining decreases after requests."""
        from core.ratelimit.limiter import RateLimiter
        limiter = RateLimiter()

        # Make some requests
        for _ in range(3):
            limiter.check("api:endpoint", limit=10, window=60)

        remaining = limiter.get_remaining("api:endpoint", limit=10, window=60)
        assert remaining == 7

    def test_get_remaining_at_limit(self):
        """Test get_remaining returns 0 at limit."""
        from core.ratelimit.limiter import RateLimiter
        limiter = RateLimiter()

        # Fill the limit
        for _ in range(5):
            limiter.check("limited:key", limit=5, window=60)

        remaining = limiter.get_remaining("limited:key", limit=5, window=60)
        assert remaining == 0

    def test_get_remaining_recovers_after_window(self):
        """Test remaining recovers after window expires."""
        from core.ratelimit.limiter import RateLimiter
        limiter = RateLimiter()

        # Use up the quota
        for _ in range(3):
            limiter.check("recover:key", limit=3, window=0.1)

        assert limiter.get_remaining("recover:key", limit=3, window=0.1) == 0

        # Wait for window
        time.sleep(0.15)

        # Should have full quota again
        remaining = limiter.get_remaining("recover:key", limit=3, window=0.1)
        assert remaining == 3


class TestRateLimiterGetResetTime:
    """Tests for RateLimiter.get_reset_time() method."""

    def test_get_reset_time_returns_datetime(self):
        """Test get_reset_time returns a datetime."""
        from core.ratelimit.limiter import RateLimiter
        limiter = RateLimiter()

        limiter.check("reset:key", limit=10, window=60)
        reset_time = limiter.get_reset_time("reset:key")

        assert isinstance(reset_time, datetime)

    def test_get_reset_time_in_future(self):
        """Test reset time is in the future."""
        from core.ratelimit.limiter import RateLimiter
        limiter = RateLimiter()

        limiter.check("future:key", limit=10, window=60)
        reset_time = limiter.get_reset_time("future:key")

        assert reset_time > datetime.now()

    def test_get_reset_time_within_window(self):
        """Test reset time is within the window period."""
        from core.ratelimit.limiter import RateLimiter
        limiter = RateLimiter()

        window_seconds = 60
        limiter.check("window:key", limit=10, window=window_seconds)
        reset_time = limiter.get_reset_time("window:key")

        max_reset = datetime.now() + timedelta(seconds=window_seconds)
        assert reset_time <= max_reset

    def test_get_reset_time_new_key(self):
        """Test reset time for key that hasn't been used."""
        from core.ratelimit.limiter import RateLimiter
        limiter = RateLimiter()

        reset_time = limiter.get_reset_time("unused:key")

        # Should return a reasonable time (now or slightly in the future)
        assert isinstance(reset_time, datetime)


class TestRateLimiterWaitIfLimited:
    """Tests for RateLimiter.wait_if_limited() async method."""

    @pytest.mark.asyncio
    async def test_wait_if_limited_returns_immediately_when_allowed(self):
        """Test wait_if_limited returns immediately when not limited."""
        from core.ratelimit.limiter import RateLimiter
        limiter = RateLimiter()

        start = time.time()
        await limiter.wait_if_limited("allowed:key", limit=10, window=60)
        elapsed = time.time() - start

        assert elapsed < 0.1  # Should be nearly instant

    @pytest.mark.asyncio
    async def test_wait_if_limited_waits_when_over_limit(self):
        """Test wait_if_limited waits when over limit."""
        from core.ratelimit.limiter import RateLimiter
        limiter = RateLimiter()

        # Fill the limit
        for _ in range(3):
            limiter.check("limited:wait", limit=3, window=0.2)

        start = time.time()
        await limiter.wait_if_limited("limited:wait", limit=3, window=0.2)
        elapsed = time.time() - start

        # Should have waited for window to reset
        assert elapsed >= 0.1

    @pytest.mark.asyncio
    async def test_wait_if_limited_allows_after_wait(self):
        """Test that request is allowed after waiting."""
        from core.ratelimit.limiter import RateLimiter
        limiter = RateLimiter()

        # Fill the limit
        for _ in range(2):
            limiter.check("wait:allow", limit=2, window=0.1)

        # Wait and check
        await limiter.wait_if_limited("wait:allow", limit=2, window=0.1)

        # Should now be able to make a request
        result = limiter.check("wait:allow", limit=2, window=0.1)
        assert result is True


# =============================================================================
# RateLimiter with Different Algorithms
# =============================================================================

class TestRateLimiterAlgorithms:
    """Tests for using different algorithms with RateLimiter."""

    def test_use_token_bucket(self):
        """Test using token bucket algorithm."""
        from core.ratelimit.limiter import RateLimiter
        from core.ratelimit.algorithms import AlgorithmType

        limiter = RateLimiter(algorithm=AlgorithmType.TOKEN_BUCKET)

        # Should work with token bucket behavior
        result = limiter.check("bucket:key", limit=5, window=60)
        assert result is True

    def test_use_sliding_window(self):
        """Test using sliding window algorithm."""
        from core.ratelimit.limiter import RateLimiter
        from core.ratelimit.algorithms import AlgorithmType

        limiter = RateLimiter(algorithm=AlgorithmType.SLIDING_WINDOW)

        result = limiter.check("sliding:key", limit=10, window=60)
        assert result is True

    def test_use_fixed_window(self):
        """Test using fixed window algorithm."""
        from core.ratelimit.limiter import RateLimiter
        from core.ratelimit.algorithms import AlgorithmType

        limiter = RateLimiter(algorithm=AlgorithmType.FIXED_WINDOW)

        result = limiter.check("fixed:key", limit=10, window=60)
        assert result is True

    def test_use_leaky_bucket(self):
        """Test using leaky bucket algorithm."""
        from core.ratelimit.limiter import RateLimiter
        from core.ratelimit.algorithms import AlgorithmType

        limiter = RateLimiter(algorithm=AlgorithmType.LEAKY_BUCKET)

        result = limiter.check("leaky:key", limit=5, window=60)
        assert result is True


# =============================================================================
# RateLimiter Specific Rate Limits
# =============================================================================

class TestRateLimiterSpecificLimits:
    """Tests for specific rate limits mentioned in requirements."""

    def test_telegram_30_per_second(self):
        """Test Telegram rate limit of 30 msg/sec per chat."""
        from core.ratelimit.limiter import RateLimiter
        limiter = RateLimiter()

        chat_id = "chat:12345"
        allowed_count = 0

        for _ in range(35):
            if limiter.check(chat_id, limit=30, window=1):
                allowed_count += 1

        assert allowed_count == 30

    def test_user_commands_10_per_minute(self):
        """Test user command rate limit of 10/minute."""
        from core.ratelimit.limiter import RateLimiter
        limiter = RateLimiter()

        user_id = "user:cmd:100"
        allowed_count = 0

        for _ in range(15):
            if limiter.check(user_id, limit=10, window=60):
                allowed_count += 1

        assert allowed_count == 10


# =============================================================================
# Run configuration
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
