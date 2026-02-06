"""
Comprehensive tests for rate limiting algorithms.

Tests cover:
1. TokenBucket - Smooth rate limiting with burst support
2. SlidingWindow - Accurate request counting
3. FixedWindow - Simple, fast rate limiting
4. LeakyBucket - Constant output rate

Target: Full coverage of algorithm implementations
"""

import pytest
import asyncio
import time
import threading
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


# =============================================================================
# TokenBucket Algorithm Tests
# =============================================================================

class TestTokenBucket:
    """Tests for TokenBucket rate limiting algorithm."""

    def test_import(self):
        """Test that TokenBucket can be imported."""
        from core.ratelimit.algorithms import TokenBucket
        assert TokenBucket is not None

    def test_initial_tokens_at_capacity(self):
        """Test bucket starts with tokens at capacity."""
        from core.ratelimit.algorithms import TokenBucket
        bucket = TokenBucket(rate=10.0, capacity=5)
        assert bucket.tokens == 5
        assert bucket.capacity == 5

    def test_acquire_single_token(self):
        """Test acquiring a single token."""
        from core.ratelimit.algorithms import TokenBucket
        bucket = TokenBucket(rate=10.0, capacity=5)

        allowed, wait_time = bucket.acquire(1)

        assert allowed is True
        assert wait_time == 0
        assert bucket.tokens == 4

    def test_acquire_multiple_tokens(self):
        """Test acquiring multiple tokens at once."""
        from core.ratelimit.algorithms import TokenBucket
        bucket = TokenBucket(rate=10.0, capacity=5)

        allowed, wait_time = bucket.acquire(3)

        assert allowed is True
        assert wait_time == 0
        assert bucket.tokens == 2

    def test_acquire_all_tokens(self):
        """Test acquiring all available tokens."""
        from core.ratelimit.algorithms import TokenBucket
        bucket = TokenBucket(rate=10.0, capacity=5)

        allowed, wait_time = bucket.acquire(5)

        assert allowed is True
        assert bucket.tokens == 0

    def test_acquire_more_than_available(self):
        """Test acquiring more tokens than available."""
        from core.ratelimit.algorithms import TokenBucket
        bucket = TokenBucket(rate=10.0, capacity=5)
        bucket.acquire(5)  # Empty the bucket

        allowed, wait_time = bucket.acquire(1)

        assert allowed is False
        assert wait_time > 0
        assert wait_time <= 0.15  # Should be ~0.1 seconds (1 token / 10 rate)

    def test_refill_over_time(self):
        """Test that tokens refill over time."""
        from core.ratelimit.algorithms import TokenBucket
        bucket = TokenBucket(rate=10.0, capacity=5)
        bucket.acquire(5)  # Empty

        # Simulate time passage
        bucket._last_update = time.time() - 0.5  # 0.5 seconds ago
        bucket._refill()

        # Should have refilled 5 tokens (10/sec * 0.5sec)
        assert 4.5 <= bucket.tokens <= 5.5

    def test_refill_does_not_exceed_capacity(self):
        """Test that refill doesn't exceed capacity."""
        from core.ratelimit.algorithms import TokenBucket
        bucket = TokenBucket(rate=10.0, capacity=5)

        # Simulate long time passage
        bucket._last_update = time.time() - 100  # 100 seconds ago
        bucket._refill()

        assert bucket.tokens == bucket.capacity

    def test_wait_time_calculation(self):
        """Test wait time calculation accuracy."""
        from core.ratelimit.algorithms import TokenBucket
        bucket = TokenBucket(rate=10.0, capacity=5)
        bucket.acquire(5)  # Empty

        allowed, wait_time = bucket.acquire(2)

        assert allowed is False
        # Wait time for 2 tokens at rate 10/sec = 0.2 seconds
        assert 0.15 <= wait_time <= 0.25

    def test_thread_safety(self):
        """Test token bucket is thread-safe."""
        from core.ratelimit.algorithms import TokenBucket
        bucket = TokenBucket(rate=100.0, capacity=50)

        results = []
        errors = []

        def acquire_token():
            try:
                allowed, _ = bucket.acquire(1)
                results.append(allowed)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=acquire_token) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 100
        # At least capacity should succeed
        assert sum(results) >= 50

    @pytest.mark.asyncio
    async def test_async_acquire(self):
        """Test async acquire waits for tokens."""
        from core.ratelimit.algorithms import TokenBucket
        bucket = TokenBucket(rate=100.0, capacity=2)
        bucket.acquire(2)  # Empty

        start = time.time()
        result = await bucket.acquire_async(1)
        elapsed = time.time() - start

        assert result is True
        assert elapsed >= 0.005  # Should have waited

    def test_get_tokens(self):
        """Test getting current token count."""
        from core.ratelimit.algorithms import TokenBucket
        bucket = TokenBucket(rate=10.0, capacity=5)

        assert bucket.get_tokens() == 5
        bucket.acquire(2)
        assert bucket.get_tokens() == 3


# =============================================================================
# SlidingWindow Algorithm Tests
# =============================================================================

class TestSlidingWindow:
    """Tests for SlidingWindow rate limiting algorithm."""

    def test_import(self):
        """Test that SlidingWindow can be imported."""
        from core.ratelimit.algorithms import SlidingWindow
        assert SlidingWindow is not None

    def test_initial_state_empty(self):
        """Test sliding window starts empty."""
        from core.ratelimit.algorithms import SlidingWindow
        window = SlidingWindow(limit=10, window_seconds=60.0)

        assert window.get_count() == 0

    def test_acquire_within_limit(self):
        """Test acquiring within the limit."""
        from core.ratelimit.algorithms import SlidingWindow
        window = SlidingWindow(limit=10, window_seconds=60.0)

        allowed, wait_time = window.acquire()

        assert allowed is True
        assert wait_time == 0
        assert window.get_count() == 1

    def test_acquire_multiple_within_limit(self):
        """Test multiple acquires within limit."""
        from core.ratelimit.algorithms import SlidingWindow
        window = SlidingWindow(limit=10, window_seconds=60.0)

        for i in range(10):
            allowed, wait_time = window.acquire()
            assert allowed is True

        assert window.get_count() == 10

    def test_acquire_exceeds_limit(self):
        """Test acquiring when limit exceeded."""
        from core.ratelimit.algorithms import SlidingWindow
        window = SlidingWindow(limit=5, window_seconds=60.0)

        for _ in range(5):
            window.acquire()

        allowed, wait_time = window.acquire()

        assert allowed is False
        assert wait_time > 0

    def test_old_requests_cleaned_up(self):
        """Test old requests are removed from window."""
        from core.ratelimit.algorithms import SlidingWindow
        window = SlidingWindow(limit=10, window_seconds=0.1)

        for _ in range(5):
            window.acquire()

        assert window.get_count() == 5

        # Wait for window to expire
        time.sleep(0.15)
        window._cleanup()

        assert window.get_count() == 0

    def test_wait_time_until_slot_available(self):
        """Test wait time calculation."""
        from core.ratelimit.algorithms import SlidingWindow
        window = SlidingWindow(limit=3, window_seconds=1.0)

        for _ in range(3):
            window.acquire()

        allowed, wait_time = window.acquire()

        assert allowed is False
        assert 0 < wait_time <= 1.0

    def test_get_remaining(self):
        """Test getting remaining slots."""
        from core.ratelimit.algorithms import SlidingWindow
        window = SlidingWindow(limit=10, window_seconds=60.0)

        assert window.get_remaining() == 10

        for _ in range(3):
            window.acquire()

        assert window.get_remaining() == 7

    def test_thread_safety(self):
        """Test sliding window is thread-safe."""
        from core.ratelimit.algorithms import SlidingWindow
        window = SlidingWindow(limit=50, window_seconds=60.0)

        results = []

        def acquire_slot():
            allowed, _ = window.acquire()
            results.append(allowed)

        threads = [threading.Thread(target=acquire_slot) for _ in range(75)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert sum(results) == 50  # Only limit should succeed


# =============================================================================
# FixedWindow Algorithm Tests
# =============================================================================

class TestFixedWindow:
    """Tests for FixedWindow rate limiting algorithm."""

    def test_import(self):
        """Test that FixedWindow can be imported."""
        from core.ratelimit.algorithms import FixedWindow
        assert FixedWindow is not None

    def test_initial_state(self):
        """Test fixed window starts with zero count."""
        from core.ratelimit.algorithms import FixedWindow
        window = FixedWindow(limit=10, window_seconds=60.0)

        assert window.get_count() == 0

    def test_acquire_within_limit(self):
        """Test acquiring within the limit."""
        from core.ratelimit.algorithms import FixedWindow
        window = FixedWindow(limit=10, window_seconds=60.0)

        allowed, wait_time = window.acquire()

        assert allowed is True
        assert wait_time == 0

    def test_acquire_at_limit(self):
        """Test acquiring at the limit."""
        from core.ratelimit.algorithms import FixedWindow
        window = FixedWindow(limit=5, window_seconds=60.0)

        for _ in range(5):
            allowed, _ = window.acquire()
            assert allowed is True

        allowed, wait_time = window.acquire()
        assert allowed is False
        assert wait_time > 0

    def test_window_resets_after_period(self):
        """Test that window resets after time period."""
        from core.ratelimit.algorithms import FixedWindow
        window = FixedWindow(limit=3, window_seconds=0.1)

        for _ in range(3):
            window.acquire()

        allowed, _ = window.acquire()
        assert allowed is False

        # Wait for window to reset
        time.sleep(0.15)

        allowed, _ = window.acquire()
        assert allowed is True

    def test_get_reset_time(self):
        """Test getting reset time."""
        from core.ratelimit.algorithms import FixedWindow
        window = FixedWindow(limit=10, window_seconds=60.0)

        reset_time = window.get_reset_time()

        assert isinstance(reset_time, datetime)
        assert reset_time > datetime.now()

    def test_get_remaining(self):
        """Test getting remaining requests."""
        from core.ratelimit.algorithms import FixedWindow
        window = FixedWindow(limit=10, window_seconds=60.0)

        assert window.get_remaining() == 10

        for _ in range(4):
            window.acquire()

        assert window.get_remaining() == 6


# =============================================================================
# LeakyBucket Algorithm Tests
# =============================================================================

class TestLeakyBucket:
    """Tests for LeakyBucket rate limiting algorithm."""

    def test_import(self):
        """Test that LeakyBucket can be imported."""
        from core.ratelimit.algorithms import LeakyBucket
        assert LeakyBucket is not None

    def test_initial_state_empty(self):
        """Test leaky bucket starts empty."""
        from core.ratelimit.algorithms import LeakyBucket
        bucket = LeakyBucket(rate=10.0, capacity=5)

        assert bucket.get_level() == 0

    def test_acquire_adds_to_bucket(self):
        """Test acquiring adds water to bucket."""
        from core.ratelimit.algorithms import LeakyBucket
        bucket = LeakyBucket(rate=10.0, capacity=5)

        allowed, wait_time = bucket.acquire(1)

        assert allowed is True
        assert wait_time == 0
        assert bucket.get_level() == 1

    def test_acquire_until_full(self):
        """Test bucket fills up to capacity."""
        from core.ratelimit.algorithms import LeakyBucket
        bucket = LeakyBucket(rate=10.0, capacity=5)

        for i in range(5):
            allowed, _ = bucket.acquire(1)
            assert allowed is True

        # Bucket is now full
        allowed, wait_time = bucket.acquire(1)
        assert allowed is False
        assert wait_time > 0

    def test_bucket_leaks_over_time(self):
        """Test that bucket leaks over time."""
        from core.ratelimit.algorithms import LeakyBucket
        bucket = LeakyBucket(rate=100.0, capacity=10)

        # Fill the bucket
        for _ in range(10):
            bucket.acquire(1)

        assert bucket.get_level() == 10

        # Wait for some leakage
        time.sleep(0.05)  # 0.05 sec * 100 rate = 5 leaked
        bucket._leak()

        assert bucket.get_level() < 10

    def test_constant_output_rate(self):
        """Test that output rate is constant."""
        from core.ratelimit.algorithms import LeakyBucket
        bucket = LeakyBucket(rate=10.0, capacity=5)

        # Add items to bucket
        for _ in range(5):
            bucket.acquire(1)

        # The leak rate should be constant at 10/second
        assert bucket.rate == 10.0

    def test_wait_time_for_full_bucket(self):
        """Test wait time calculation when bucket is full."""
        from core.ratelimit.algorithms import LeakyBucket
        bucket = LeakyBucket(rate=10.0, capacity=5)

        # Fill the bucket
        for _ in range(5):
            bucket.acquire(1)

        allowed, wait_time = bucket.acquire(1)

        assert allowed is False
        # Wait time should be 1/rate = 0.1 seconds for 1 slot to free
        assert 0.05 <= wait_time <= 0.15

    @pytest.mark.asyncio
    async def test_async_acquire(self):
        """Test async acquire waits for leak."""
        from core.ratelimit.algorithms import LeakyBucket
        bucket = LeakyBucket(rate=100.0, capacity=2)

        # Fill the bucket
        bucket.acquire(2)

        start = time.time()
        result = await bucket.acquire_async(1)
        elapsed = time.time() - start

        assert result is True
        assert elapsed >= 0.005  # Should have waited for leak


# =============================================================================
# Run configuration
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
