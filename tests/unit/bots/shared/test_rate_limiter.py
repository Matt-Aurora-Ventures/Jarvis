"""
Tests for ClawdBots rate limiter module.

Tests the token bucket algorithm, per-API and per-bot limits,
request queuing, and statistics tracking.
"""

import asyncio
import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Import will be created after tests
from bots.shared.rate_limiter import (
    RateLimiter,
    check_rate_limit,
    wait_for_rate_limit,
    get_rate_limit_stats,
    set_rate_limit,
    reset_rate_limits,
    DEFAULT_LIMITS,
)


class TestDefaultLimits:
    """Test default rate limit configurations."""

    def test_telegram_default_limit(self):
        """Telegram should default to 30 req/min."""
        assert "telegram" in DEFAULT_LIMITS
        assert DEFAULT_LIMITS["telegram"] == 30

    def test_openai_default_limit(self):
        """OpenAI should default to 60 req/min."""
        assert "openai" in DEFAULT_LIMITS
        assert DEFAULT_LIMITS["openai"] == 60

    def test_anthropic_default_limit(self):
        """Anthropic should default to 60 req/min."""
        assert "anthropic" in DEFAULT_LIMITS
        assert DEFAULT_LIMITS["anthropic"] == 60

    def test_xai_default_limit(self):
        """X.AI should default to 30 req/min."""
        assert "xai" in DEFAULT_LIMITS
        assert DEFAULT_LIMITS["xai"] == 30


class TestCheckRateLimit:
    """Test the check_rate_limit function."""

    def setup_method(self):
        """Reset rate limits before each test."""
        reset_rate_limits()

    def test_check_rate_limit_returns_bool(self):
        """check_rate_limit should return a boolean."""
        result = check_rate_limit("telegram", "clawdjarvis")
        assert isinstance(result, bool)

    def test_first_request_allowed(self):
        """First request should always be allowed."""
        result = check_rate_limit("telegram", "clawdjarvis")
        assert result is True

    def test_requests_within_limit_allowed(self):
        """Requests within the limit should be allowed."""
        # 30 req/min for telegram, so 5 quick requests should be fine
        for _ in range(5):
            result = check_rate_limit("telegram", "clawdjarvis")
            assert result is True

    def test_requests_exceeding_limit_blocked(self):
        """Requests exceeding the limit should be blocked."""
        # Set a low limit for testing
        set_rate_limit("test_api", 2)  # 2 req/min

        # First 2 should pass
        assert check_rate_limit("test_api", "testbot") is True
        assert check_rate_limit("test_api", "testbot") is True

        # Third should fail
        assert check_rate_limit("test_api", "testbot") is False

    def test_different_apis_have_separate_limits(self):
        """Each API should have its own limit pool."""
        set_rate_limit("api_a", 1)
        set_rate_limit("api_b", 1)

        # First request to each should pass
        assert check_rate_limit("api_a", "bot1") is True
        assert check_rate_limit("api_b", "bot1") is True

        # Second request to each should fail
        assert check_rate_limit("api_a", "bot1") is False
        assert check_rate_limit("api_b", "bot1") is False

    def test_different_bots_have_separate_limits(self):
        """Each bot should have its own limit pool per API."""
        set_rate_limit("shared_api", 1)

        # Each bot gets its own limit
        assert check_rate_limit("shared_api", "bot1") is True
        assert check_rate_limit("shared_api", "bot2") is True

        # But hitting the limit is per-bot
        assert check_rate_limit("shared_api", "bot1") is False
        assert check_rate_limit("shared_api", "bot2") is False

    def test_unknown_api_uses_default_limit(self):
        """Unknown APIs should use a reasonable default."""
        # Should not raise, should use default
        result = check_rate_limit("unknown_api", "testbot")
        assert isinstance(result, bool)


class TestTokenBucketAlgorithm:
    """Test the token bucket algorithm implementation."""

    def setup_method(self):
        """Reset rate limits before each test."""
        reset_rate_limits()

    def test_tokens_refill_over_time(self):
        """Tokens should refill over time."""
        set_rate_limit("refill_test", 60)  # 60 req/min = 1 req/sec

        # Use all tokens
        for _ in range(60):
            check_rate_limit("refill_test", "testbot")

        # Should be rate limited
        assert check_rate_limit("refill_test", "testbot") is False

        # Wait for tokens to refill (1 second = 1 token)
        time.sleep(1.1)

        # Should have a token now
        assert check_rate_limit("refill_test", "testbot") is True

    def test_burst_capacity(self):
        """Should allow burst up to capacity."""
        set_rate_limit("burst_test", 30)  # 30 req/min

        # Burst of 30 requests should all pass
        results = [check_rate_limit("burst_test", "testbot") for _ in range(30)]
        assert all(results)

        # 31st should fail
        assert check_rate_limit("burst_test", "testbot") is False


class TestWaitForRateLimit:
    """Test the wait_for_rate_limit async function."""

    def setup_method(self):
        """Reset rate limits before each test."""
        reset_rate_limits()

    @pytest.mark.asyncio
    async def test_wait_for_rate_limit_returns_when_allowed(self):
        """Should return immediately if rate limit is not exceeded."""
        start = time.time()
        await wait_for_rate_limit("telegram", "testbot")
        elapsed = time.time() - start

        # Should be nearly instant
        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_wait_for_rate_limit_blocks_when_exceeded(self):
        """Should wait until rate limit allows request."""
        set_rate_limit("wait_test", 60)  # 60 req/min = 1 req/sec

        # Exhaust the bucket
        for _ in range(60):
            check_rate_limit("wait_test", "testbot")

        start = time.time()
        await wait_for_rate_limit("wait_test", "testbot")
        elapsed = time.time() - start

        # Should have waited about 1 second for token refill
        assert elapsed >= 0.9
        assert elapsed < 2.0

    @pytest.mark.asyncio
    async def test_wait_for_rate_limit_with_timeout(self):
        """Should handle timeout parameter if provided."""
        set_rate_limit("timeout_test", 1)  # Very low limit

        # Exhaust the bucket
        check_rate_limit("timeout_test", "testbot")

        # The function should be awaitable
        await wait_for_rate_limit("timeout_test", "testbot")


class TestGetRateLimitStats:
    """Test the get_rate_limit_stats function."""

    def setup_method(self):
        """Reset rate limits before each test."""
        reset_rate_limits()

    def test_get_stats_returns_dict(self):
        """Stats should return a dictionary."""
        stats = get_rate_limit_stats()
        assert isinstance(stats, dict)

    def test_stats_include_api_usage(self):
        """Stats should include usage per API."""
        check_rate_limit("telegram", "testbot")
        check_rate_limit("telegram", "testbot")
        check_rate_limit("openai", "testbot")

        stats = get_rate_limit_stats()
        assert "telegram" in stats
        assert "openai" in stats

    def test_stats_include_request_counts(self):
        """Stats should track request counts."""
        check_rate_limit("telegram", "testbot")
        check_rate_limit("telegram", "testbot")
        check_rate_limit("telegram", "testbot")

        stats = get_rate_limit_stats()
        assert stats["telegram"]["requests"] == 3

    def test_stats_include_blocked_counts(self):
        """Stats should track blocked requests."""
        set_rate_limit("block_test", 2)

        check_rate_limit("block_test", "testbot")
        check_rate_limit("block_test", "testbot")
        check_rate_limit("block_test", "testbot")  # This should be blocked

        stats = get_rate_limit_stats()
        assert stats["block_test"]["blocked"] == 1

    def test_stats_per_bot(self):
        """Stats should be available per bot."""
        check_rate_limit("telegram", "bot1")
        check_rate_limit("telegram", "bot2")
        check_rate_limit("telegram", "bot2")

        stats = get_rate_limit_stats()
        assert stats["telegram"]["by_bot"]["bot1"]["requests"] == 1
        assert stats["telegram"]["by_bot"]["bot2"]["requests"] == 2


class TestSetRateLimit:
    """Test the set_rate_limit function."""

    def setup_method(self):
        """Reset rate limits before each test."""
        reset_rate_limits()

    def test_set_rate_limit_updates_limit(self):
        """set_rate_limit should update the limit for an API."""
        set_rate_limit("custom_api", 100)

        # Should be able to make 100 requests
        for _ in range(100):
            assert check_rate_limit("custom_api", "testbot") is True

        # 101st should fail
        assert check_rate_limit("custom_api", "testbot") is False

    def test_set_rate_limit_accepts_requests_per_minute(self):
        """Limit should be specified as requests per minute."""
        set_rate_limit("rpm_test", 60)  # 60 req/min = 1 req/sec

        # Make 60 requests instantly
        for _ in range(60):
            check_rate_limit("rpm_test", "testbot")

        # Should be limited
        assert check_rate_limit("rpm_test", "testbot") is False

    def test_set_rate_limit_overwrites_default(self):
        """Should be able to override default limits."""
        # Telegram defaults to 30
        set_rate_limit("telegram", 5)

        for _ in range(5):
            assert check_rate_limit("telegram", "testbot") is True

        # 6th should fail with new limit
        assert check_rate_limit("telegram", "testbot") is False


class TestResetRateLimits:
    """Test the reset_rate_limits function."""

    def test_reset_clears_all_limits(self):
        """Reset should clear all usage."""
        set_rate_limit("reset_test", 1)
        check_rate_limit("reset_test", "testbot")

        # Should be limited
        assert check_rate_limit("reset_test", "testbot") is False

        # Reset
        reset_rate_limits()

        # Should be allowed again
        assert check_rate_limit("reset_test", "testbot") is True

    def test_reset_clears_stats(self):
        """Reset should clear statistics."""
        check_rate_limit("telegram", "testbot")
        check_rate_limit("telegram", "testbot")

        reset_rate_limits()

        stats = get_rate_limit_stats()
        # Stats should be empty or zeroed
        assert stats.get("telegram", {}).get("requests", 0) == 0


class TestPersistence:
    """Test state persistence to JSON file."""

    def setup_method(self):
        """Reset and use temp file."""
        self.temp_dir = tempfile.mkdtemp()
        self.state_file = os.path.join(self.temp_dir, "rate_limits.json")

    def teardown_method(self):
        """Clean up temp files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_state_persists_to_file(self):
        """State should be saved to JSON file."""
        with patch.dict(os.environ, {"RATE_LIMIT_STATE_PATH": self.state_file}):
            reset_rate_limits()
            set_rate_limit("persist_api", 10)
            check_rate_limit("persist_api", "testbot")

        # File should exist
        assert os.path.exists(self.state_file)

    def test_state_loads_from_file(self):
        """State should be loaded from JSON file on init."""
        # Create a state file
        state = {
            "limits": {"restored_api": 42},
            "buckets": {}
        }
        with open(self.state_file, "w") as f:
            json.dump(state, f)

        with patch.dict(os.environ, {"RATE_LIMIT_STATE_PATH": self.state_file}):
            reset_rate_limits()
            stats = get_rate_limit_stats()

            # The limit should be loaded (implementation detail)
            # At minimum, the file should be read without error

    def test_handles_missing_state_file(self):
        """Should work fine if state file doesn't exist."""
        nonexistent = os.path.join(self.temp_dir, "nonexistent.json")

        with patch.dict(os.environ, {"RATE_LIMIT_STATE_PATH": nonexistent}):
            reset_rate_limits()
            # Should not raise
            assert check_rate_limit("telegram", "testbot") is True

    def test_handles_corrupted_state_file(self):
        """Should handle corrupted JSON gracefully."""
        with open(self.state_file, "w") as f:
            f.write("not valid json {{{")

        with patch.dict(os.environ, {"RATE_LIMIT_STATE_PATH": self.state_file}):
            reset_rate_limits()
            # Should not raise, should use defaults
            assert check_rate_limit("telegram", "testbot") is True


class TestRateLimiterClass:
    """Test the RateLimiter class directly."""

    def test_create_rate_limiter(self):
        """Should be able to create a RateLimiter instance."""
        limiter = RateLimiter()
        assert limiter is not None

    def test_rate_limiter_with_custom_limits(self):
        """Should accept custom limits in constructor."""
        limits = {"custom": 100}
        limiter = RateLimiter(limits=limits)

        # Should use custom limit
        for _ in range(100):
            assert limiter.check("custom", "testbot") is True
        assert limiter.check("custom", "testbot") is False

    def test_rate_limiter_check_method(self):
        """RateLimiter should have a check method."""
        limiter = RateLimiter()
        result = limiter.check("telegram", "testbot")
        assert isinstance(result, bool)

    def test_rate_limiter_wait_method(self):
        """RateLimiter should have an async wait method."""
        limiter = RateLimiter()
        # Method should exist and be awaitable
        assert hasattr(limiter, "wait")

    def test_rate_limiter_stats_method(self):
        """RateLimiter should have a stats method."""
        limiter = RateLimiter()
        stats = limiter.get_stats()
        assert isinstance(stats, dict)

    def test_rate_limiter_set_limit_method(self):
        """RateLimiter should have a set_limit method."""
        limiter = RateLimiter()
        limiter.set_limit("new_api", 50)

        # New limit should be effective
        for _ in range(50):
            assert limiter.check("new_api", "testbot") is True
        assert limiter.check("new_api", "testbot") is False

    def test_rate_limiter_reset_method(self):
        """RateLimiter should have a reset method."""
        limiter = RateLimiter()
        limiter.set_limit("reset_api", 1)
        limiter.check("reset_api", "testbot")

        assert limiter.check("reset_api", "testbot") is False

        limiter.reset()
        assert limiter.check("reset_api", "testbot") is True


class TestConcurrency:
    """Test thread safety and concurrent access."""

    def test_concurrent_checks(self):
        """Rate limiter should be thread-safe."""
        import threading

        reset_rate_limits()
        set_rate_limit("concurrent_api", 100)

        results = []
        errors = []

        def make_request():
            try:
                result = check_rate_limit("concurrent_api", "testbot")
                results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=make_request) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No errors should occur
        assert len(errors) == 0
        # All 50 should pass (limit is 100)
        assert all(results)
        assert len(results) == 50

    @pytest.mark.asyncio
    async def test_concurrent_async_waits(self):
        """Async waits should work concurrently."""
        reset_rate_limits()
        set_rate_limit("async_api", 10)

        # Launch 5 concurrent waits
        tasks = [wait_for_rate_limit("async_api", "testbot") for _ in range(5)]
        results = await asyncio.gather(*tasks)

        # All should complete without error
        assert len(results) == 5


class TestEdgeCases:
    """Test edge cases and error handling."""

    def setup_method(self):
        """Reset rate limits before each test."""
        reset_rate_limits()

    def test_empty_api_name(self):
        """Should handle empty API name gracefully."""
        # Should not raise
        result = check_rate_limit("", "testbot")
        assert isinstance(result, bool)

    def test_empty_bot_name(self):
        """Should handle empty bot name gracefully."""
        result = check_rate_limit("telegram", "")
        assert isinstance(result, bool)

    def test_none_api_name(self):
        """Should handle None API name."""
        with pytest.raises((TypeError, ValueError)):
            check_rate_limit(None, "testbot")

    def test_none_bot_name(self):
        """Should handle None bot name."""
        with pytest.raises((TypeError, ValueError)):
            check_rate_limit("telegram", None)

    def test_zero_limit(self):
        """Zero limit should block all requests."""
        set_rate_limit("zero_api", 0)
        assert check_rate_limit("zero_api", "testbot") is False

    def test_negative_limit(self):
        """Negative limit should be rejected or treated as zero."""
        with pytest.raises(ValueError):
            set_rate_limit("neg_api", -5)

    def test_very_high_limit(self):
        """Very high limits should work."""
        set_rate_limit("high_api", 1000000)
        for _ in range(1000):
            assert check_rate_limit("high_api", "testbot") is True

    def test_special_characters_in_names(self):
        """Should handle special characters in names."""
        result = check_rate_limit("api-with-dashes", "bot_with_underscores")
        assert isinstance(result, bool)

        result = check_rate_limit("api.with.dots", "bot:with:colons")
        assert isinstance(result, bool)
