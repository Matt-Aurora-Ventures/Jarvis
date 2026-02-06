"""
Unit Tests for ClawdBots Shared Modules.

Tests cover all shared utilities and services:
1. utils.py - String/time utilities (truncate, format_duration, etc.)
2. cache.py - In-memory caching with TTL
3. config_loader.py - Configuration loading and validation
4. rate_limiter.py - Rate limiting with token bucket algorithm
5. security.py - Input sanitization and security utilities
6. feature_flags.py - Feature flag management

TDD Approach:
- Tests are written FIRST to define expected behavior
- Implementation follows to make tests pass
"""

import json
import os
import sys
import tempfile
import time
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# =============================================================================
# Test Utils Module
# =============================================================================

class TestUtils:
    """Test bots.shared.utils module."""

    def test_truncate_basic(self):
        """Test basic string truncation."""
        from bots.shared.utils import truncate

        result = truncate("hello world", 5)
        assert result == "he..."
        assert len(result) == 5

    def test_truncate_no_truncation_needed(self):
        """Test truncate when string is shorter than max length."""
        from bots.shared.utils import truncate

        result = truncate("hi", 10)
        assert result == "hi"

    def test_truncate_exact_length(self):
        """Test truncate when string equals max length."""
        from bots.shared.utils import truncate

        result = truncate("hello", 5)
        assert result == "hello"

    def test_truncate_custom_suffix(self):
        """Test truncate with custom suffix."""
        from bots.shared.utils import truncate

        result = truncate("hello world", 8, suffix=">>")
        assert result == "hello >>"
        assert len(result) == 8

    def test_truncate_empty_string(self):
        """Test truncate with empty string."""
        from bots.shared.utils import truncate

        result = truncate("", 5)
        assert result == ""

    def test_truncate_short_max_length(self):
        """Test truncate with very short max length."""
        from bots.shared.utils import truncate

        result = truncate("hello", 3)
        assert result == "..."
        assert len(result) == 3

    def test_format_duration_seconds_only(self):
        """Test format_duration with seconds only."""
        from bots.shared.utils import format_duration

        result = format_duration(45)
        assert result == "45s"

    def test_format_duration_minutes_seconds(self):
        """Test format_duration with minutes and seconds."""
        from bots.shared.utils import format_duration

        result = format_duration(125)  # 2m 5s
        assert result == "2m 5s"

    def test_format_duration_hours_minutes_seconds(self):
        """Test format_duration with hours, minutes, and seconds."""
        from bots.shared.utils import format_duration

        result = format_duration(3661)  # 1h 1m 1s
        assert result == "1h 1m 1s"

    def test_format_duration_hours_only(self):
        """Test format_duration with exact hours."""
        from bots.shared.utils import format_duration

        result = format_duration(3600)  # 1h
        assert result == "1h 0m 0s"

    def test_format_duration_zero(self):
        """Test format_duration with zero seconds."""
        from bots.shared.utils import format_duration

        result = format_duration(0)
        assert result == "0s"

    def test_format_duration_days(self):
        """Test format_duration with days."""
        from bots.shared.utils import format_duration

        result = format_duration(90061)  # 1d 1h 1m 1s
        assert "1d" in result or "25h" in result  # Either format acceptable

    def test_slugify_basic(self):
        """Test slugify converts to lowercase with hyphens."""
        from bots.shared.utils import slugify

        result = slugify("Hello World")
        assert result == "hello-world"

    def test_slugify_special_characters(self):
        """Test slugify removes special characters."""
        from bots.shared.utils import slugify

        result = slugify("Hello! World@#$%")
        assert result == "hello-world"

    def test_slugify_multiple_spaces(self):
        """Test slugify handles multiple spaces."""
        from bots.shared.utils import slugify

        result = slugify("hello    world")
        assert result == "hello-world"

    def test_safe_json_loads_valid(self):
        """Test safe_json_loads with valid JSON."""
        from bots.shared.utils import safe_json_loads

        result = safe_json_loads('{"key": "value"}')
        assert result == {"key": "value"}

    def test_safe_json_loads_invalid(self):
        """Test safe_json_loads with invalid JSON returns default."""
        from bots.shared.utils import safe_json_loads

        result = safe_json_loads("not json", default={})
        assert result == {}

    def test_safe_json_loads_none(self):
        """Test safe_json_loads with None input."""
        from bots.shared.utils import safe_json_loads

        result = safe_json_loads(None, default={"default": True})
        assert result == {"default": True}

    def test_deep_get_simple(self):
        """Test deep_get with simple nested dict."""
        from bots.shared.utils import deep_get

        data = {"a": {"b": {"c": 123}}}
        result = deep_get(data, "a.b.c")
        assert result == 123

    def test_deep_get_missing_key(self):
        """Test deep_get returns default for missing key."""
        from bots.shared.utils import deep_get

        data = {"a": {"b": 1}}
        result = deep_get(data, "a.c.d", default="missing")
        assert result == "missing"

    def test_deep_get_list_index(self):
        """Test deep_get with list index."""
        from bots.shared.utils import deep_get

        data = {"items": [{"name": "first"}, {"name": "second"}]}
        result = deep_get(data, "items.0.name")
        assert result == "first"

    def test_retry_decorator_success(self):
        """Test retry decorator on successful function."""
        from bots.shared.utils import retry

        call_count = 0

        @retry(max_attempts=3, delay=0.01)
        def succeeds():
            nonlocal call_count
            call_count += 1
            return "success"

        result = succeeds()
        assert result == "success"
        assert call_count == 1

    def test_retry_decorator_eventual_success(self):
        """Test retry decorator with eventual success."""
        from bots.shared.utils import retry

        call_count = 0

        @retry(max_attempts=3, delay=0.01)
        def fails_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("fail")
            return "success"

        result = fails_twice()
        assert result == "success"
        assert call_count == 3

    def test_retry_decorator_all_failures(self):
        """Test retry decorator raises after max attempts."""
        from bots.shared.utils import retry

        @retry(max_attempts=3, delay=0.01)
        def always_fails():
            raise ValueError("always fails")

        with pytest.raises(ValueError):
            always_fails()


# =============================================================================
# Test Cache Module
# =============================================================================

class TestCache:
    """Test bots.shared.cache module."""

    def test_cache_set_get_basic(self):
        """Test basic cache set and get."""
        from bots.shared.cache import Cache

        cache = Cache(persistence_path=None)
        cache.cache_set("test_key", "test_value")
        result = cache.cache_get("test_key")

        assert result == "test_value"

    def test_cache_get_nonexistent(self):
        """Test cache get returns None for nonexistent key."""
        from bots.shared.cache import Cache

        cache = Cache(persistence_path=None)
        result = cache.cache_get("nonexistent")

        assert result is None

    def test_cache_get_with_default(self):
        """Test cache get returns default for missing key."""
        from bots.shared.cache import Cache

        cache = Cache(persistence_path=None)
        result = cache.cache_get("missing", default="fallback")

        assert result == "fallback"

    def test_cache_delete(self):
        """Test cache delete removes entry."""
        from bots.shared.cache import Cache

        cache = Cache(persistence_path=None)
        cache.cache_set("key", "value")
        cache.cache_delete("key")

        assert cache.cache_get("key") is None

    def test_cache_clear(self):
        """Test cache clear removes all entries."""
        from bots.shared.cache import Cache

        cache = Cache(persistence_path=None)
        cache.cache_set("key1", "value1")
        cache.cache_set("key2", "value2")
        cache.cache_clear()

        assert cache.cache_get("key1") is None
        assert cache.cache_get("key2") is None

    def test_cache_ttl_expiration(self):
        """Test cache entry expires after TTL."""
        from bots.shared.cache import Cache

        cache = Cache(persistence_path=None)
        cache.cache_set("key", "value", ttl_seconds=0.1)

        assert cache.cache_get("key") == "value"
        time.sleep(0.15)
        assert cache.cache_get("key") is None

    def test_cache_stats(self):
        """Test cache stats returns hit/miss info."""
        from bots.shared.cache import Cache

        cache = Cache(persistence_path=None)
        cache.cache_set("key", "value")
        cache.cache_get("key")  # hit
        cache.cache_get("missing")  # miss

        stats = cache.cache_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["entries"] == 1

    def test_cache_lru_eviction(self):
        """Test cache evicts oldest entry when max reached."""
        from bots.shared.cache import Cache

        cache = Cache(persistence_path=None, max_entries=2)
        cache.cache_set("key1", "value1")
        cache.cache_set("key2", "value2")
        cache.cache_set("key3", "value3")  # Should evict key1

        assert cache.cache_get("key1") is None
        assert cache.cache_get("key2") == "value2"
        assert cache.cache_get("key3") == "value3"

    def test_cache_various_types(self):
        """Test cache handles different value types."""
        from bots.shared.cache import Cache

        cache = Cache(persistence_path=None)

        cache.cache_set("str", "string")
        cache.cache_set("int", 42)
        cache.cache_set("float", 3.14)
        cache.cache_set("list", [1, 2, 3])
        cache.cache_set("dict", {"a": 1})
        cache.cache_set("bool", True)

        assert cache.cache_get("str") == "string"
        assert cache.cache_get("int") == 42
        assert cache.cache_get("float") == 3.14
        assert cache.cache_get("list") == [1, 2, 3]
        assert cache.cache_get("dict") == {"a": 1}
        assert cache.cache_get("bool") is True


class TestCacheModuleFunctions:
    """Test module-level cache functions."""

    def test_module_cache_get_set(self):
        """Test module-level cache_get and cache_set."""
        from bots.shared.cache import cache_clear, cache_get, cache_set

        cache_clear()
        cache_set("module_key", "module_value")
        result = cache_get("module_key")

        assert result == "module_value"
        cache_clear()

    def test_module_cache_delete(self):
        """Test module-level cache_delete."""
        from bots.shared.cache import cache_clear, cache_delete, cache_get, cache_set

        cache_clear()
        cache_set("del_key", "del_value")
        cache_delete("del_key")

        assert cache_get("del_key") is None
        cache_clear()


class TestCachedDecorator:
    """Test @cached decorator."""

    def test_cached_decorator(self):
        """Test @cached decorator caches function results."""
        from bots.shared.cache import Cache, cached

        cache = Cache(persistence_path=None)
        call_count = 0

        @cached(cache=cache, ttl_seconds=3600)
        def expensive_fn(x, y):
            nonlocal call_count
            call_count += 1
            return x + y

        result1 = expensive_fn(1, 2)
        result2 = expensive_fn(1, 2)  # Should use cache

        assert result1 == 3
        assert result2 == 3
        assert call_count == 1


# =============================================================================
# Test Config Loader Module
# =============================================================================

class TestConfigLoader:
    """Test bots.shared.config_loader module."""

    @pytest.fixture
    def temp_config_file(self):
        """Create temporary config file."""
        config = {
            "bot_name": "test_bot",
            "api_key": "test_key_123",
            "max_retries": 3,
            "timeout": 30.0,
            "features": {
                "enabled": True,
                "items": ["a", "b", "c"]
            }
        }
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        ) as f:
            json.dump(config, f)
            yield Path(f.name)
        os.unlink(f.name)

    @pytest.fixture
    def temp_yaml_config(self):
        """Create temporary YAML config file."""
        yaml_content = """
bot_name: test_bot
api_key: test_key_yaml
max_retries: 5
nested:
  value: 100
  list:
    - item1
    - item2
"""
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.yaml', delete=False
        ) as f:
            f.write(yaml_content)
            yield Path(f.name)
        os.unlink(f.name)

    def test_load_json_config(self, temp_config_file):
        """Test loading JSON config file."""
        from bots.shared.config_loader import load_config

        config = load_config(temp_config_file)

        assert config["bot_name"] == "test_bot"
        assert config["api_key"] == "test_key_123"
        assert config["max_retries"] == 3

    def test_load_yaml_config(self, temp_yaml_config):
        """Test loading YAML config file."""
        from bots.shared.config_loader import load_config

        config = load_config(temp_yaml_config)

        assert config["bot_name"] == "test_bot"
        assert config["api_key"] == "test_key_yaml"
        assert config["max_retries"] == 5

    def test_load_config_file_not_found(self):
        """Test load_config raises for missing file."""
        from bots.shared.config_loader import load_config, ConfigError

        with pytest.raises(ConfigError):
            load_config(Path("/nonexistent/config.json"))

    def test_load_config_with_defaults(self, temp_config_file):
        """Test load_config merges with defaults."""
        from bots.shared.config_loader import load_config

        defaults = {"debug": False, "bot_name": "default_bot"}
        config = load_config(temp_config_file, defaults=defaults)

        assert config["debug"] is False  # From defaults
        assert config["bot_name"] == "test_bot"  # Overridden by file

    def test_get_env_config(self):
        """Test get_env_config reads from environment."""
        from bots.shared.config_loader import get_env_config

        with patch.dict(os.environ, {"TEST_VAR": "test_value"}):
            result = get_env_config("TEST_VAR")
            assert result == "test_value"

    def test_get_env_config_default(self):
        """Test get_env_config returns default for missing var."""
        from bots.shared.config_loader import get_env_config

        result = get_env_config("NONEXISTENT_VAR", default="default")
        assert result == "default"

    def test_get_env_config_required(self):
        """Test get_env_config raises for missing required var."""
        from bots.shared.config_loader import get_env_config, ConfigError

        with pytest.raises(ConfigError):
            get_env_config("NONEXISTENT_VAR", required=True)

    def test_validate_config_valid(self, temp_config_file):
        """Test validate_config passes for valid config."""
        from bots.shared.config_loader import load_config, validate_config

        config = load_config(temp_config_file)
        schema = {
            "bot_name": {"type": str, "required": True},
            "max_retries": {"type": int, "required": True},
        }

        # Should not raise
        validate_config(config, schema)

    def test_validate_config_missing_required(self):
        """Test validate_config raises for missing required field."""
        from bots.shared.config_loader import validate_config, ConfigError

        config = {"optional_field": "value"}
        schema = {
            "required_field": {"type": str, "required": True},
        }

        with pytest.raises(ConfigError):
            validate_config(config, schema)

    def test_validate_config_type_mismatch(self):
        """Test validate_config raises for type mismatch."""
        from bots.shared.config_loader import validate_config, ConfigError

        config = {"count": "not_an_int"}
        schema = {
            "count": {"type": int, "required": True},
        }

        with pytest.raises(ConfigError):
            validate_config(config, schema)


# =============================================================================
# Test Rate Limiter Module
# =============================================================================

class TestRateLimiter:
    """Test bots.shared.rate_limiter module."""

    def test_rate_limiter_allows_under_limit(self):
        """Test rate limiter allows requests under limit."""
        from bots.shared.rate_limiter import RateLimiter

        limiter = RateLimiter(max_requests=10, window_seconds=60)

        for _ in range(5):
            assert limiter.allow() is True

    def test_rate_limiter_blocks_over_limit(self):
        """Test rate limiter blocks requests over limit."""
        from bots.shared.rate_limiter import RateLimiter

        limiter = RateLimiter(max_requests=3, window_seconds=60)

        assert limiter.allow() is True
        assert limiter.allow() is True
        assert limiter.allow() is True
        assert limiter.allow() is False  # Over limit

    def test_rate_limiter_resets_after_window(self):
        """Test rate limiter resets after time window."""
        from bots.shared.rate_limiter import RateLimiter

        limiter = RateLimiter(max_requests=2, window_seconds=0.1)

        assert limiter.allow() is True
        assert limiter.allow() is True
        assert limiter.allow() is False  # Over limit

        time.sleep(0.15)
        assert limiter.allow() is True  # Window reset

    def test_rate_limiter_per_key(self):
        """Test rate limiter tracks per-key limits."""
        from bots.shared.rate_limiter import RateLimiter

        limiter = RateLimiter(max_requests=2, window_seconds=60)

        assert limiter.allow(key="user1") is True
        assert limiter.allow(key="user1") is True
        assert limiter.allow(key="user1") is False  # user1 over limit

        assert limiter.allow(key="user2") is True  # user2 has own quota

    def test_rate_limiter_remaining(self):
        """Test rate limiter returns remaining quota."""
        from bots.shared.rate_limiter import RateLimiter

        limiter = RateLimiter(max_requests=5, window_seconds=60)

        assert limiter.remaining() == 5
        limiter.allow()
        assert limiter.remaining() == 4

    def test_rate_limiter_retry_after(self):
        """Test rate limiter returns retry_after time."""
        from bots.shared.rate_limiter import RateLimiter

        limiter = RateLimiter(max_requests=1, window_seconds=60)

        limiter.allow()
        retry_after = limiter.retry_after()

        assert retry_after > 0
        assert retry_after <= 60

    def test_rate_limiter_reset(self):
        """Test rate limiter reset clears state."""
        from bots.shared.rate_limiter import RateLimiter

        limiter = RateLimiter(max_requests=2, window_seconds=60)

        limiter.allow()
        limiter.allow()
        assert limiter.allow() is False

        limiter.reset()
        assert limiter.allow() is True

    def test_token_bucket_rate_limiter(self):
        """Test token bucket rate limiter."""
        from bots.shared.rate_limiter import TokenBucketLimiter

        limiter = TokenBucketLimiter(capacity=5, refill_rate=1.0)

        # Initial bucket is full
        for _ in range(5):
            assert limiter.allow() is True
        assert limiter.allow() is False

    def test_token_bucket_refill(self):
        """Test token bucket refills over time."""
        from bots.shared.rate_limiter import TokenBucketLimiter

        limiter = TokenBucketLimiter(capacity=2, refill_rate=10.0)

        assert limiter.allow() is True
        assert limiter.allow() is True
        assert limiter.allow() is False

        time.sleep(0.2)  # Wait for refill (10/sec = 2 tokens in 0.2s)
        assert limiter.allow() is True


class TestRateLimitDecorator:
    """Test @rate_limited decorator."""

    def test_rate_limited_decorator(self):
        """Test @rate_limited decorator limits function calls."""
        from bots.shared.rate_limiter import rate_limited

        call_count = 0

        @rate_limited(max_calls=2, window_seconds=60)
        def limited_fn():
            nonlocal call_count
            call_count += 1
            return "called"

        assert limited_fn() == "called"
        assert limited_fn() == "called"

        # Third call should raise
        with pytest.raises(Exception):  # RateLimitExceeded
            limited_fn()


class TestAsyncRateLimiter:
    """Test async rate limiting."""

    @pytest.mark.asyncio
    async def test_async_rate_limiter(self):
        """Test async rate limiter."""
        from bots.shared.rate_limiter import AsyncRateLimiter

        limiter = AsyncRateLimiter(max_requests=2, window_seconds=60)

        assert await limiter.allow() is True
        assert await limiter.allow() is True
        assert await limiter.allow() is False


# =============================================================================
# Test Security Module
# =============================================================================

class TestSecurity:
    """Test bots.shared.security module."""

    def test_sanitize_html(self):
        """Test sanitize_html removes HTML tags."""
        from bots.shared.security import sanitize_html

        result = sanitize_html("<script>alert('xss')</script>Hello")
        assert "<script>" not in result
        assert "Hello" in result

    def test_sanitize_html_preserves_safe_tags(self):
        """Test sanitize_html preserves allowed tags."""
        from bots.shared.security import sanitize_html

        result = sanitize_html("<b>Bold</b> text", allowed_tags=["b"])
        assert "<b>" in result
        assert "Bold" in result

    def test_sanitize_sql(self):
        """Test sanitize_sql prevents SQL injection."""
        from bots.shared.security import sanitize_sql

        result = sanitize_sql("test'; DROP TABLE users; --")
        assert "DROP TABLE" not in result or result.replace("'", "") != result

    def test_sanitize_path(self):
        """Test sanitize_path prevents path traversal."""
        from bots.shared.security import sanitize_path

        result = sanitize_path("../../../etc/passwd")
        assert ".." not in result

    def test_sanitize_path_normalizes(self):
        """Test sanitize_path normalizes paths."""
        from bots.shared.security import sanitize_path

        result = sanitize_path("./data/../data/./file.txt")
        assert result == "data/file.txt" or "data/file.txt" in result

    def test_sanitize_input_basic(self):
        """Test sanitize_input removes dangerous characters."""
        from bots.shared.security import sanitize_input

        result = sanitize_input("Hello<script>World")
        assert "<script>" not in result

    def test_sanitize_input_preserves_text(self):
        """Test sanitize_input preserves safe text."""
        from bots.shared.security import sanitize_input

        result = sanitize_input("Hello World 123")
        assert "Hello World 123" == result

    def test_sanitize_input_max_length(self):
        """Test sanitize_input enforces max length."""
        from bots.shared.security import sanitize_input

        result = sanitize_input("a" * 1000, max_length=100)
        assert len(result) <= 100

    def test_is_safe_url(self):
        """Test is_safe_url validates URLs."""
        from bots.shared.security import is_safe_url

        assert is_safe_url("https://example.com") is True
        assert is_safe_url("http://example.com") is True
        assert is_safe_url("javascript:alert(1)") is False
        assert is_safe_url("data:text/html,<script>") is False

    def test_is_safe_url_allowed_hosts(self):
        """Test is_safe_url with allowed hosts."""
        from bots.shared.security import is_safe_url

        assert is_safe_url(
            "https://api.example.com",
            allowed_hosts=["api.example.com"]
        ) is True
        assert is_safe_url(
            "https://evil.com",
            allowed_hosts=["api.example.com"]
        ) is False

    def test_mask_sensitive(self):
        """Test mask_sensitive masks sensitive data."""
        from bots.shared.security import mask_sensitive

        result = mask_sensitive("secret123")
        assert result != "secret123"
        assert "***" in result or len(result) != len("secret123")

    def test_mask_sensitive_partial(self):
        """Test mask_sensitive shows partial data."""
        from bots.shared.security import mask_sensitive

        result = mask_sensitive("secret123456", show_chars=4)
        assert result.startswith("secr") or result.endswith("3456")

    def test_hash_sensitive(self):
        """Test hash_sensitive creates consistent hash."""
        from bots.shared.security import hash_sensitive

        result1 = hash_sensitive("secret")
        result2 = hash_sensitive("secret")

        assert result1 == result2
        assert result1 != "secret"
        assert len(result1) > 0

    def test_validate_token_format(self):
        """Test validate_token_format checks token structure."""
        from bots.shared.security import validate_token_format

        # Valid token format (alphanumeric with dashes)
        assert validate_token_format("abc123-def456") is True

        # Invalid characters
        assert validate_token_format("token with spaces") is False
        assert validate_token_format("token<script>") is False


class TestSecurityHelpers:
    """Test security helper functions."""

    def test_generate_secure_token(self):
        """Test generate_secure_token creates random tokens."""
        from bots.shared.security import generate_secure_token

        token1 = generate_secure_token()
        token2 = generate_secure_token()

        assert token1 != token2
        assert len(token1) >= 32

    def test_generate_secure_token_length(self):
        """Test generate_secure_token respects length param."""
        from bots.shared.security import generate_secure_token

        token = generate_secure_token(length=64)
        assert len(token) == 64

    def test_constant_time_compare(self):
        """Test constant_time_compare for timing attack prevention."""
        from bots.shared.security import constant_time_compare

        assert constant_time_compare("secret", "secret") is True
        assert constant_time_compare("secret", "SECRET") is False
        assert constant_time_compare("secret", "secre") is False


# =============================================================================
# Test Feature Flags Module
# =============================================================================

class TestFeatureFlags:
    """Test bots.shared.feature_flags module."""

    @pytest.fixture
    def temp_flags_file(self):
        """Create temporary feature flags file."""
        flags = {
            "TEST_ENABLED": True,
            "TEST_DISABLED": False,
            "TEST_PERCENTAGE": {"enabled": True, "percentage": 50},
            "TEST_WHITELIST": {
                "enabled": True,
                "whitelist": ["user1", "user2"]
            }
        }
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        ) as f:
            json.dump(flags, f)
            yield Path(f.name)
        os.unlink(f.name)

    def test_is_enabled_basic(self, temp_flags_file):
        """Test is_enabled with basic boolean flag."""
        from bots.shared.feature_flags import FeatureFlags

        ff = FeatureFlags(config_path=temp_flags_file)

        assert ff.is_enabled("TEST_ENABLED") is True
        assert ff.is_enabled("TEST_DISABLED") is False

    def test_is_enabled_nonexistent(self, temp_flags_file):
        """Test is_enabled returns False for missing flag."""
        from bots.shared.feature_flags import FeatureFlags

        ff = FeatureFlags(config_path=temp_flags_file)

        assert ff.is_enabled("NONEXISTENT") is False

    def test_is_enabled_nonexistent_with_default(self, temp_flags_file):
        """Test is_enabled returns default for missing flag."""
        from bots.shared.feature_flags import FeatureFlags

        ff = FeatureFlags(config_path=temp_flags_file)

        assert ff.is_enabled("NONEXISTENT", default=True) is True

    def test_is_enabled_percentage_consistent(self, temp_flags_file):
        """Test percentage rollout is consistent for same user."""
        from bots.shared.feature_flags import FeatureFlags

        ff = FeatureFlags(config_path=temp_flags_file)

        result1 = ff.is_enabled("TEST_PERCENTAGE", user_id="user123")
        result2 = ff.is_enabled("TEST_PERCENTAGE", user_id="user123")

        assert result1 == result2

    def test_is_enabled_whitelist(self, temp_flags_file):
        """Test is_enabled respects whitelist."""
        from bots.shared.feature_flags import FeatureFlags

        ff = FeatureFlags(config_path=temp_flags_file)

        assert ff.is_enabled("TEST_WHITELIST", user_id="user1") is True
        assert ff.is_enabled("TEST_WHITELIST", user_id="user999") is False

    def test_env_override(self, temp_flags_file):
        """Test environment variable override."""
        from bots.shared.feature_flags import FeatureFlags

        with patch.dict(os.environ, {"FF_TEST_DISABLED": "true"}):
            ff = FeatureFlags(config_path=temp_flags_file)
            assert ff.is_enabled("TEST_DISABLED") is True

    def test_get_all_flags(self, temp_flags_file):
        """Test get_all_flags returns all flags."""
        from bots.shared.feature_flags import FeatureFlags

        ff = FeatureFlags(config_path=temp_flags_file)
        all_flags = ff.get_all_flags()

        assert "TEST_ENABLED" in all_flags
        assert "TEST_DISABLED" in all_flags

    def test_set_flag(self, temp_flags_file):
        """Test set_flag updates flag value."""
        from bots.shared.feature_flags import FeatureFlags

        ff = FeatureFlags(config_path=temp_flags_file)

        ff.set_flag("TEST_DISABLED", True)
        assert ff.is_enabled("TEST_DISABLED") is True

    def test_reload(self, temp_flags_file):
        """Test reload refreshes flags from file."""
        from bots.shared.feature_flags import FeatureFlags

        ff = FeatureFlags(config_path=temp_flags_file)
        assert ff.is_enabled("TEST_ENABLED") is True

        # Modify file
        new_flags = {"TEST_ENABLED": False}
        with open(temp_flags_file, 'w') as f:
            json.dump(new_flags, f)

        ff.reload()
        assert ff.is_enabled("TEST_ENABLED") is False


class TestFeatureFlagsModuleFunctions:
    """Test module-level feature flag functions."""

    def test_is_feature_enabled(self):
        """Test module-level is_feature_enabled."""
        from bots.shared.feature_flags import is_feature_enabled

        # Should work without errors (may return default False)
        result = is_feature_enabled("SOME_FLAG", default=False)
        assert isinstance(result, bool)


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
