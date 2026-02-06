"""
Comprehensive tests for rate limiting decorators.

Tests cover:
1. @rate_limit(calls=10, period=60) - Generic rate limit decorator
2. @rate_limit_user(calls=5, period=60) - User-based rate limiting
3. @rate_limit_api(provider, calls, period) - API provider rate limiting

Target: Full coverage of decorator implementations
"""

import pytest
import asyncio
import time
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


# =============================================================================
# @rate_limit Decorator Tests
# =============================================================================

class TestRateLimitDecorator:
    """Tests for @rate_limit decorator."""

    def test_import(self):
        """Test that rate_limit decorator can be imported."""
        from core.ratelimit.decorators import rate_limit
        assert rate_limit is not None

    def test_sync_function_allowed(self):
        """Test sync function is allowed within limit."""
        from core.ratelimit.decorators import rate_limit

        call_count = 0

        @rate_limit(calls=5, period=60)
        def limited_func():
            nonlocal call_count
            call_count += 1
            return "success"

        # Should allow up to limit
        for _ in range(5):
            result = limited_func()
            assert result == "success"

        assert call_count == 5

    def test_sync_function_blocked_over_limit(self):
        """Test sync function is blocked over limit."""
        from core.ratelimit.decorators import rate_limit
        from core.ratelimit.exceptions import RateLimitExceeded

        call_count = 0

        @rate_limit(calls=3, period=60, key="blocked_func")
        def blocked_func():
            nonlocal call_count
            call_count += 1
            return "success"

        # Use up the limit
        for _ in range(3):
            blocked_func()

        # Should raise exception on next call
        with pytest.raises(RateLimitExceeded):
            blocked_func()

        assert call_count == 3

    @pytest.mark.asyncio
    async def test_async_function_allowed(self):
        """Test async function is allowed within limit."""
        from core.ratelimit.decorators import rate_limit

        call_count = 0

        @rate_limit(calls=5, period=60)
        async def async_limited():
            nonlocal call_count
            call_count += 1
            return "async success"

        for _ in range(5):
            result = await async_limited()
            assert result == "async success"

        assert call_count == 5

    @pytest.mark.asyncio
    async def test_async_function_blocked(self):
        """Test async function is blocked over limit."""
        from core.ratelimit.decorators import rate_limit
        from core.ratelimit.exceptions import RateLimitExceeded

        @rate_limit(calls=2, period=60, key="async_blocked")
        async def async_blocked():
            return "result"

        # Use up the limit
        await async_blocked()
        await async_blocked()

        # Should raise exception
        with pytest.raises(RateLimitExceeded):
            await async_blocked()

    def test_custom_key(self):
        """Test decorator with custom key."""
        from core.ratelimit.decorators import rate_limit

        @rate_limit(calls=3, period=60, key="custom:key:123")
        def custom_key_func():
            return "success"

        for _ in range(3):
            custom_key_func()

        # Should work (limit is 3)
        from core.ratelimit.exceptions import RateLimitExceeded
        with pytest.raises(RateLimitExceeded):
            custom_key_func()

    def test_reset_after_period(self):
        """Test rate limit resets after period."""
        from core.ratelimit.decorators import rate_limit

        @rate_limit(calls=2, period=0.1, key="reset_period")
        def reset_func():
            return "success"

        # Use up the limit
        reset_func()
        reset_func()

        from core.ratelimit.exceptions import RateLimitExceeded
        with pytest.raises(RateLimitExceeded):
            reset_func()

        # Wait for period to reset
        time.sleep(0.15)

        # Should be allowed again
        result = reset_func()
        assert result == "success"

    def test_on_limited_callback(self):
        """Test on_limited callback is called when rate limited."""
        from core.ratelimit.decorators import rate_limit

        callback_called = False

        def on_limited(key, remaining):
            nonlocal callback_called
            callback_called = True

        @rate_limit(calls=1, period=60, key="callback_test", on_limited=on_limited)
        def callback_func():
            return "success"

        callback_func()

        # This should trigger the callback
        from core.ratelimit.exceptions import RateLimitExceeded
        with pytest.raises(RateLimitExceeded):
            callback_func()

        assert callback_called is True


# =============================================================================
# @rate_limit_user Decorator Tests
# =============================================================================

class TestRateLimitUserDecorator:
    """Tests for @rate_limit_user decorator."""

    def test_import(self):
        """Test that rate_limit_user decorator can be imported."""
        from core.ratelimit.decorators import rate_limit_user
        assert rate_limit_user is not None

    def test_extracts_user_from_positional_arg(self):
        """Test decorator extracts user_id from positional argument."""
        from core.ratelimit.decorators import rate_limit_user

        @rate_limit_user(calls=3, period=60)
        def user_func(user_id: int, message: str):
            return f"User {user_id}: {message}"

        # User 1 makes 3 calls
        for _ in range(3):
            result = user_func(1, "hello")
            assert "User 1" in result

        # User 1 is now limited
        from core.ratelimit.exceptions import RateLimitExceeded
        with pytest.raises(RateLimitExceeded):
            user_func(1, "blocked")

        # User 2 should still be allowed
        result = user_func(2, "different user")
        assert "User 2" in result

    def test_extracts_user_from_kwarg(self):
        """Test decorator extracts user_id from keyword argument."""
        from core.ratelimit.decorators import rate_limit_user

        @rate_limit_user(calls=2, period=60, user_param="uid")
        def kwarg_func(uid: int, data: dict):
            return f"Processed for {uid}"

        # Use keyword argument
        kwarg_func(uid=100, data={})
        kwarg_func(uid=100, data={})

        from core.ratelimit.exceptions import RateLimitExceeded
        with pytest.raises(RateLimitExceeded):
            kwarg_func(uid=100, data={})

    def test_isolates_different_users(self):
        """Test that different users have isolated limits."""
        from core.ratelimit.decorators import rate_limit_user

        @rate_limit_user(calls=2, period=60)
        def isolated_func(user_id: int):
            return user_id

        # User A uses their quota
        isolated_func(100)
        isolated_func(100)

        # User B has separate quota
        assert isolated_func(200) == 200
        assert isolated_func(200) == 200

        # Both should be limited for their own quota
        from core.ratelimit.exceptions import RateLimitExceeded
        with pytest.raises(RateLimitExceeded):
            isolated_func(100)
        with pytest.raises(RateLimitExceeded):
            isolated_func(200)

    @pytest.mark.asyncio
    async def test_async_user_function(self):
        """Test rate_limit_user with async function."""
        from core.ratelimit.decorators import rate_limit_user

        @rate_limit_user(calls=2, period=60)
        async def async_user_func(user_id: int):
            await asyncio.sleep(0.01)
            return f"async:{user_id}"

        result = await async_user_func(500)
        assert result == "async:500"


# =============================================================================
# @rate_limit_api Decorator Tests
# =============================================================================

class TestRateLimitApiDecorator:
    """Tests for @rate_limit_api decorator."""

    def test_import(self):
        """Test that rate_limit_api decorator can be imported."""
        from core.ratelimit.decorators import rate_limit_api
        assert rate_limit_api is not None

    def test_limits_by_provider(self):
        """Test API calls are limited by provider."""
        from core.ratelimit.decorators import rate_limit_api

        @rate_limit_api(provider="grok", calls=3, period=60)
        def call_grok_api():
            return "grok response"

        for _ in range(3):
            call_grok_api()

        from core.ratelimit.exceptions import RateLimitExceeded
        with pytest.raises(RateLimitExceeded):
            call_grok_api()

    def test_different_providers_isolated(self):
        """Test different API providers have isolated limits."""
        from core.ratelimit.decorators import rate_limit_api

        @rate_limit_api(provider="provider_a", calls=2, period=60)
        def call_provider_a():
            return "a"

        @rate_limit_api(provider="provider_b", calls=2, period=60)
        def call_provider_b():
            return "b"

        # Use up provider A
        call_provider_a()
        call_provider_a()

        # Provider B should still work
        assert call_provider_b() == "b"

    def test_daily_budget_limit(self):
        """Test API rate limiting with daily budget concept."""
        from core.ratelimit.decorators import rate_limit_api

        # Grok has $10 daily limit - represent as 10 calls
        @rate_limit_api(provider="grok_budget", calls=10, period=86400)  # 24 hours
        def call_grok_with_budget():
            return "grok call"

        for _ in range(10):
            call_grok_with_budget()

        from core.ratelimit.exceptions import RateLimitExceeded
        with pytest.raises(RateLimitExceeded):
            call_grok_with_budget()

    @pytest.mark.asyncio
    async def test_async_api_function(self):
        """Test rate_limit_api with async function."""
        from core.ratelimit.decorators import rate_limit_api

        @rate_limit_api(provider="async_api", calls=5, period=60)
        async def async_api_call():
            await asyncio.sleep(0.01)
            return "async api response"

        result = await async_api_call()
        assert result == "async api response"

    def test_retry_after_info(self):
        """Test that retry_after info is available in exception."""
        from core.ratelimit.decorators import rate_limit_api
        from core.ratelimit.exceptions import RateLimitExceeded

        @rate_limit_api(provider="retry_test", calls=1, period=60)
        def retry_func():
            return "ok"

        retry_func()

        with pytest.raises(RateLimitExceeded) as exc_info:
            retry_func()

        assert exc_info.value.retry_after > 0


# =============================================================================
# Decorator Configuration Tests
# =============================================================================

class TestDecoratorConfiguration:
    """Tests for decorator configuration options."""

    def test_raise_on_limit_true(self):
        """Test raise_on_limit=True raises exception."""
        from core.ratelimit.decorators import rate_limit
        from core.ratelimit.exceptions import RateLimitExceeded

        @rate_limit(calls=1, period=60, key="raise_true", raise_on_limit=True)
        def raise_func():
            return "ok"

        raise_func()

        with pytest.raises(RateLimitExceeded):
            raise_func()

    def test_raise_on_limit_false_returns_none(self):
        """Test raise_on_limit=False returns None when limited."""
        from core.ratelimit.decorators import rate_limit

        @rate_limit(calls=1, period=60, key="raise_false", raise_on_limit=False)
        def no_raise_func():
            return "ok"

        assert no_raise_func() == "ok"
        assert no_raise_func() is None  # Returns None when limited

    def test_wait_on_limit_true(self):
        """Test wait_on_limit=True waits until allowed."""
        from core.ratelimit.decorators import rate_limit

        @rate_limit(calls=1, period=0.1, key="wait_true", wait_on_limit=True)
        def wait_func():
            return "waited"

        assert wait_func() == "waited"

        start = time.time()
        result = wait_func()
        elapsed = time.time() - start

        assert result == "waited"
        assert elapsed >= 0.05  # Should have waited


# =============================================================================
# Exception Tests
# =============================================================================

class TestRateLimitExceeded:
    """Tests for RateLimitExceeded exception."""

    def test_import(self):
        """Test that RateLimitExceeded can be imported."""
        from core.ratelimit.exceptions import RateLimitExceeded
        assert RateLimitExceeded is not None

    def test_exception_attributes(self):
        """Test exception has required attributes."""
        from core.ratelimit.exceptions import RateLimitExceeded

        exc = RateLimitExceeded(
            key="test:key",
            limit=10,
            window=60,
            retry_after=30.5
        )

        assert exc.key == "test:key"
        assert exc.limit == 10
        assert exc.window == 60
        assert exc.retry_after == 30.5

    def test_exception_message(self):
        """Test exception has informative message."""
        from core.ratelimit.exceptions import RateLimitExceeded

        exc = RateLimitExceeded(
            key="user:123",
            limit=5,
            window=60,
            retry_after=45.0
        )

        message = str(exc)
        assert "user:123" in message or "Rate limit" in message


# =============================================================================
# Run configuration
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
