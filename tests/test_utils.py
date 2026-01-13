"""
Tests for core utilities package.
Tests rate limiter, connection pool, timeout, and decorators.
"""

import pytest
import asyncio
import time


class TestRateLimiter:
    """Tests for rate limiting utilities."""

    def test_import(self):
        """Test module imports correctly."""
        from core.utils.rate_limiter import (
            RateLimiter, MultiRateLimiter, get_rate_limiter, rate_limited
        )
        assert RateLimiter is not None
        assert get_rate_limiter is not None

    def test_singleton(self):
        """Test singleton pattern."""
        from core.utils.rate_limiter import get_rate_limiter
        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()
        assert limiter1 is limiter2

    def test_token_bucket(self):
        """Test token bucket rate limiter."""
        from core.utils.rate_limiter import TokenBucket
        bucket = TokenBucket(rate=10.0, capacity=5)
        
        # Should be able to acquire up to capacity
        for _ in range(5):
            assert bucket.acquire()
        
        # Should fail after capacity exhausted
        assert not bucket.acquire()

    def test_sliding_window(self):
        """Test sliding window rate limiter."""
        from core.utils.rate_limiter import SlidingWindow
        window = SlidingWindow(max_requests=3, window_seconds=1.0)
        
        # Should allow up to max_requests
        for _ in range(3):
            assert window.acquire()
        
        # Should fail after limit
        assert not window.acquire()


class TestConnectionPool:
    """Tests for connection pool utilities."""

    def test_import(self):
        """Test module imports correctly."""
        from core.utils.connection_pool import (
            ConnectionPool, get_connection_pool, get_session
        )
        assert ConnectionPool is not None
        assert get_connection_pool is not None

    def test_singleton(self):
        """Test singleton pattern."""
        from core.utils.connection_pool import get_connection_pool
        pool1 = get_connection_pool()
        pool2 = get_connection_pool()
        assert pool1 is pool2

    def test_stats(self):
        """Test pool stats."""
        from core.utils.connection_pool import get_connection_pool
        pool = get_connection_pool()
        stats = pool.get_stats()
        assert "active_sessions" in stats
        assert "sessions" in stats


class TestTimeout:
    """Tests for timeout utilities."""

    def test_import(self):
        """Test module imports correctly."""
        from core.utils.timeout import (
            with_timeout, timeout, race, retry_with_timeout
        )
        assert with_timeout is not None
        assert timeout is not None

    @pytest.mark.asyncio
    async def test_with_timeout_success(self):
        """Test successful operation within timeout."""
        from core.utils.timeout import with_timeout
        
        async def fast_operation():
            return "success"
        
        result = await with_timeout(fast_operation(), 1.0)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_with_timeout_default(self):
        """Test timeout returning default value."""
        from core.utils.timeout import with_timeout_default
        
        async def slow_operation():
            await asyncio.sleep(10)
            return "done"
        
        result = await with_timeout_default(slow_operation(), 0.1, default="timeout")
        assert result == "timeout"


class TestDecorators:
    """Tests for decorator utilities."""

    def test_import(self):
        """Test module imports correctly."""
        from core.utils.decorators import (
            retry, memoize, singleton, measure_time, log_calls
        )
        assert retry is not None
        assert memoize is not None

    def test_memoize_sync(self):
        """Test memoize decorator for sync functions."""
        from core.utils.decorators import memoize
        
        call_count = 0
        
        @memoize(ttl_seconds=60)
        def expensive_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2
        
        # First call
        result1 = expensive_function(5)
        assert result1 == 10
        assert call_count == 1
        
        # Second call (cached)
        result2 = expensive_function(5)
        assert result2 == 10
        assert call_count == 1  # Should not have called again

    def test_singleton_decorator(self):
        """Test singleton decorator."""
        from core.utils.decorators import singleton
        
        @singleton
        class MyClass:
            def __init__(self):
                self.value = 42
        
        instance1 = MyClass()
        instance2 = MyClass()
        assert instance1 is instance2
        assert instance1.value == 42

    def test_measure_time(self):
        """Test measure_time decorator."""
        from core.utils.decorators import measure_time
        
        @measure_time
        def slow_function():
            time.sleep(0.01)
            return "done"
        
        result = slow_function()
        assert result == "done"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
