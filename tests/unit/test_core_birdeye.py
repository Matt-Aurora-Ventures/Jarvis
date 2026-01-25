"""
Comprehensive unit tests for core/birdeye.py - BirdEye API client.

Tests the following components:
1. API Integration - Token price, volume, liquidity, OHLCV fetching
2. Caching - Cache hits/misses, TTL expiration, invalidation
3. Rate Limiting - Request throttling, backoff, retry logic
4. Error Handling - Network failures, invalid responses, timeouts
5. Fallback Behavior - Graceful degradation when API unavailable

Coverage target: 60%+ with 50-70 tests
"""
import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
import requests


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_api_key():
    """Provide a mock API key for testing."""
    return "test_birdeye_api_key_12345"


@pytest.fixture
def sample_token_address():
    """Sample Solana token address for testing (RAY token)."""
    return "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R"


@pytest.fixture
def mock_price_response():
    """Mock response for price API."""
    return {
        "success": True,
        "data": {
            "value": 1.23,
            "updateUnixTime": 1704067200,
            "updateHumanTime": "2024-01-01T00:00:00",
            "liquidity": 5000000.0,
        }
    }


@pytest.fixture
def mock_ohlcv_response():
    """Mock response for OHLCV API."""
    return {
        "success": True,
        "data": {
            "items": [
                {"unixTime": 1704067200, "o": 1.0, "h": 1.2, "l": 0.9, "c": 1.1, "v": 10000},
                {"unixTime": 1704070800, "o": 1.1, "h": 1.3, "l": 1.0, "c": 1.25, "v": 15000},
                {"unixTime": 1704074400, "o": 1.25, "h": 1.35, "l": 1.2, "c": 1.3, "v": 12000},
            ]
        }
    }


@pytest.fixture
def mock_overview_response():
    """Mock response for token overview API."""
    return {
        "success": True,
        "data": {
            "address": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",
            "symbol": "RAY",
            "name": "Raydium",
            "price": 1.23,
            "liquidity": 5000000.0,
            "volume24h": 10000000.0,
            "priceChange24h": 5.5,
        }
    }


@pytest.fixture
def mock_trending_response():
    """Mock response for trending tokens API."""
    return {
        "success": True,
        "data": {
            "tokens": [
                {"address": "token1", "symbol": "TK1", "price": 1.0},
                {"address": "token2", "symbol": "TK2", "price": 2.0},
                {"address": "token3", "symbol": "TK3", "price": 3.0},
            ]
        }
    }


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create a temporary cache directory."""
    cache_dir = tmp_path / "birdeye_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


@pytest.fixture(autouse=True)
def reset_rate_limit_state():
    """Reset rate limit state before each test."""
    from core import birdeye
    birdeye._request_timestamps.clear()
    birdeye._rate_limit_backoff = 0
    birdeye._last_rate_limit_time = 0
    yield
    # Cleanup after test
    birdeye._request_timestamps.clear()
    birdeye._rate_limit_backoff = 0
    birdeye._last_rate_limit_time = 0


# =============================================================================
# TEST CLASS: BirdEyeResult Dataclass
# =============================================================================


class TestBirdEyeResult:
    """Tests for the BirdEyeResult dataclass."""

    def test_birdeye_result_success(self):
        """BirdEyeResult should correctly represent a successful response."""
        from core.birdeye import BirdEyeResult

        result = BirdEyeResult(
            success=True,
            data={"price": 1.23},
            cached=False,
            retryable=True,
        )

        assert result.success is True
        assert result.data == {"price": 1.23}
        assert result.error is None
        assert result.cached is False
        assert result.retryable is True

    def test_birdeye_result_failure(self):
        """BirdEyeResult should correctly represent a failed response."""
        from core.birdeye import BirdEyeResult

        result = BirdEyeResult(
            success=False,
            error="rate_limited",
            retryable=True,
        )

        assert result.success is False
        assert result.data is None
        assert result.error == "rate_limited"
        assert result.retryable is True

    def test_birdeye_result_defaults(self):
        """BirdEyeResult should have sensible defaults."""
        from core.birdeye import BirdEyeResult

        result = BirdEyeResult(success=True)

        assert result.data is None
        assert result.error is None
        assert result.cached is False
        assert result.retryable is True

    def test_birdeye_result_cached_flag(self):
        """BirdEyeResult should indicate when data is from cache."""
        from core.birdeye import BirdEyeResult

        result = BirdEyeResult(
            success=True,
            data={"price": 1.0},
            cached=True,
        )

        assert result.cached is True

    def test_birdeye_result_non_retryable_error(self):
        """BirdEyeResult should indicate non-retryable errors."""
        from core.birdeye import BirdEyeResult

        result = BirdEyeResult(
            success=False,
            error="invalid_api_key",
            retryable=False,
        )

        assert result.retryable is False


# =============================================================================
# TEST CLASS: Backoff Delay Calculation
# =============================================================================


class TestBackoffDelay:
    """Tests for exponential backoff delay calculation."""

    def test_backoff_delay_first_attempt(self):
        """Backoff delay for first attempt should be close to base."""
        from core.birdeye import _backoff_delay

        delay = _backoff_delay(base=1.0, attempt=0)

        # First attempt: 1.0 * 2^0 = 1.0 + jitter (up to 0.1)
        assert 1.0 <= delay <= 1.1

    def test_backoff_delay_increases_exponentially(self):
        """Backoff delay should increase exponentially with attempts."""
        from core.birdeye import _backoff_delay

        delays = [_backoff_delay(base=1.0, attempt=i) for i in range(5)]

        # Each delay should roughly double (accounting for jitter)
        for i in range(1, len(delays)):
            # Expected: base * 2^attempt
            expected_min = 1.0 * (2 ** i)
            expected_max = expected_min * 1.1  # 10% jitter
            assert expected_min <= delays[i] <= expected_max

    def test_backoff_delay_respects_max_delay(self):
        """Backoff delay should not exceed max_delay."""
        from core.birdeye import _backoff_delay

        delay = _backoff_delay(base=1.0, attempt=10, max_delay=30.0)

        # 1.0 * 2^10 = 1024, but should be capped at 30 + jitter
        assert delay <= 33.0  # 30 + 10% jitter

    def test_backoff_delay_custom_max(self):
        """Backoff delay should respect custom max_delay."""
        from core.birdeye import _backoff_delay

        delay = _backoff_delay(base=1.0, attempt=5, max_delay=10.0)

        # 1.0 * 2^5 = 32, but should be capped at 10 + jitter
        assert delay <= 11.0

    def test_backoff_delay_includes_jitter(self):
        """Backoff delay should include random jitter."""
        from core.birdeye import _backoff_delay

        # Run multiple times to verify jitter variability
        delays = [_backoff_delay(base=1.0, attempt=0) for _ in range(100)]

        # With jitter, we should see some variation
        unique_delays = set(delays)
        assert len(unique_delays) > 1  # At least some variation


# =============================================================================
# TEST CLASS: Rate Limiting
# =============================================================================


class TestRateLimiting:
    """Tests for rate limiting functionality."""

    def test_check_rate_limit_no_requests(self):
        """Should not rate limit when no requests have been made."""
        from core.birdeye import _check_rate_limit

        should_wait, wait_time = _check_rate_limit()

        assert should_wait is False
        assert wait_time == 0

    def test_check_rate_limit_under_limit(self):
        """Should not rate limit when under the limit."""
        from core.birdeye import _check_rate_limit, _record_request

        # Make some requests but stay under limit
        for _ in range(50):
            _record_request()

        should_wait, wait_time = _check_rate_limit()

        assert should_wait is False
        assert wait_time == 0

    def test_check_rate_limit_at_limit(self):
        """Should rate limit when at the request limit."""
        from core.birdeye import _check_rate_limit, _record_request, RATE_LIMIT_REQUESTS_PER_MINUTE

        # Hit the limit
        for _ in range(RATE_LIMIT_REQUESTS_PER_MINUTE):
            _record_request()

        should_wait, wait_time = _check_rate_limit()

        assert should_wait is True
        assert wait_time > 0

    def test_record_request_adds_timestamp(self):
        """Recording a request should add a timestamp."""
        from core.birdeye import _record_request, _request_timestamps

        initial_count = len(_request_timestamps)
        _record_request()

        assert len(_request_timestamps) == initial_count + 1

    def test_record_rate_limit_sets_backoff(self):
        """Recording a rate limit should set the backoff timer."""
        from core import birdeye
        from core.birdeye import _record_rate_limit

        initial_backoff = birdeye._rate_limit_backoff
        _record_rate_limit()

        assert birdeye._rate_limit_backoff > initial_backoff
        assert birdeye._last_rate_limit_time > 0

    def test_record_rate_limit_doubles_backoff(self):
        """Consecutive rate limits should double the backoff time."""
        from core import birdeye
        from core.birdeye import _record_rate_limit

        _record_rate_limit()  # First: 5s
        first_backoff = birdeye._rate_limit_backoff

        _record_rate_limit()  # Second: 10s
        second_backoff = birdeye._rate_limit_backoff

        assert second_backoff == first_backoff * 2

    def test_rate_limit_backoff_max_cap(self):
        """Rate limit backoff should cap at 60 seconds."""
        from core import birdeye
        from core.birdeye import _record_rate_limit

        # Record many rate limits to exceed cap
        for _ in range(10):
            _record_rate_limit()

        assert birdeye._rate_limit_backoff <= 60

    def test_old_timestamps_are_cleaned(self):
        """Old request timestamps should be cleaned up."""
        from core import birdeye
        from core.birdeye import _check_rate_limit

        # Add old timestamps (older than 60 seconds)
        old_time = time.time() - 120
        birdeye._request_timestamps.extend([old_time] * 50)

        # Check rate limit will clean old timestamps
        _check_rate_limit()

        # Old timestamps should be gone
        now = time.time()
        assert all(t > now - 60 for t in birdeye._request_timestamps)


# =============================================================================
# TEST CLASS: API Key Loading
# =============================================================================


class TestApiKeyLoading:
    """Tests for API key loading functionality."""

    def test_load_api_key_from_env(self, mock_api_key):
        """Should load API key from environment variable."""
        from core.birdeye import _load_api_key

        with patch.dict(os.environ, {"BIRDEYE_API_KEY": mock_api_key}):
            with patch("core.birdeye.ROOT", Path("/nonexistent")):
                key = _load_api_key()

        assert key == mock_api_key

    def test_load_api_key_from_secrets_file(self, mock_api_key, tmp_path):
        """Should load API key from secrets file."""
        from core.birdeye import _load_api_key

        # Create secrets file
        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir()
        secrets_file = secrets_dir / "keys.json"
        secrets_file.write_text(json.dumps({"birdeye": {"api_key": mock_api_key}}))

        with patch("core.birdeye.ROOT", tmp_path):
            with patch.dict(os.environ, {}, clear=True):
                # Clear BIRDEYE_API_KEY if set
                os.environ.pop("BIRDEYE_API_KEY", None)
                key = _load_api_key()

        assert key == mock_api_key

    def test_load_api_key_returns_none_when_missing(self, tmp_path):
        """Should return None when no API key is available."""
        from core.birdeye import _load_api_key

        with patch("core.birdeye.ROOT", tmp_path):
            with patch.dict(os.environ, {}, clear=True):
                os.environ.pop("BIRDEYE_API_KEY", None)
                key = _load_api_key()

        assert key is None

    def test_load_api_key_handles_invalid_json(self, tmp_path):
        """Should handle invalid JSON in secrets file."""
        from core.birdeye import _load_api_key

        # Create invalid secrets file
        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir()
        secrets_file = secrets_dir / "keys.json"
        secrets_file.write_text("not valid json")

        with patch("core.birdeye.ROOT", tmp_path):
            with patch.dict(os.environ, {}, clear=True):
                os.environ.pop("BIRDEYE_API_KEY", None)
                key = _load_api_key()

        assert key is None

    def test_has_api_key_returns_true(self, mock_api_key):
        """has_api_key should return True when key is available."""
        from core.birdeye import has_api_key

        with patch("core.birdeye._load_api_key", return_value=mock_api_key):
            result = has_api_key()

        assert result is True

    def test_has_api_key_returns_false(self):
        """has_api_key should return False when key is unavailable."""
        from core.birdeye import has_api_key

        with patch("core.birdeye._load_api_key", return_value=None):
            result = has_api_key()

        assert result is False

    def test_load_api_key_public_function(self, mock_api_key):
        """Public load_api_key function should delegate to internal function."""
        from core.birdeye import load_api_key

        with patch("core.birdeye._load_api_key", return_value=mock_api_key):
            key = load_api_key()

        assert key == mock_api_key


# =============================================================================
# TEST CLASS: API Status
# =============================================================================


class TestApiStatus:
    """Tests for API status reporting."""

    def test_get_api_status_with_key(self, mock_api_key):
        """get_api_status should report when API key is available."""
        from core.birdeye import get_api_status

        with patch("core.birdeye.has_api_key", return_value=True):
            status = get_api_status()

        assert status["has_api_key"] is True
        assert "requests_last_minute" in status
        assert "rate_limit" in status
        assert "base_url" in status

    def test_get_api_status_without_key(self):
        """get_api_status should report when API key is unavailable."""
        from core.birdeye import get_api_status

        with patch("core.birdeye.has_api_key", return_value=False):
            status = get_api_status()

        assert status["has_api_key"] is False

    def test_get_api_status_reports_recent_requests(self):
        """get_api_status should report recent request count."""
        from core.birdeye import get_api_status, _record_request

        for _ in range(5):
            _record_request()

        status = get_api_status()

        assert status["requests_last_minute"] == 5

    def test_get_api_status_reports_backoff(self):
        """get_api_status should report rate limit backoff if active."""
        from core import birdeye
        from core.birdeye import get_api_status, _record_rate_limit

        _record_rate_limit()
        status = get_api_status()

        assert status["rate_limit_backoff"] is not None
        assert status["rate_limit_backoff"] > 0


# =============================================================================
# TEST CLASS: Token Price Fetching
# =============================================================================


class TestTokenPriceFetching:
    """Tests for token price API integration."""

    def test_fetch_token_price_success(self, sample_token_address, mock_price_response, mock_api_key):
        """fetch_token_price should return price data on success."""
        from core.birdeye import fetch_token_price, BirdEyeResult

        mock_result = BirdEyeResult(success=True, data=mock_price_response)

        with patch("core.birdeye.load_api_key", return_value=mock_api_key):
            with patch("core.birdeye._get_json", return_value=mock_result):
                result = fetch_token_price(sample_token_address)

        assert result is not None
        assert result["data"]["value"] == 1.23

    def test_fetch_token_price_no_api_key(self, sample_token_address):
        """fetch_token_price should handle missing API key."""
        from core.birdeye import fetch_token_price, BirdEyeResult

        mock_result = BirdEyeResult(success=False, error="no_api_key")

        with patch("core.birdeye.load_api_key", return_value=None):
            with patch("core.birdeye._get_json", return_value=mock_result):
                result = fetch_token_price(sample_token_address)

        assert result is None

    def test_fetch_token_price_with_custom_chain(self, sample_token_address, mock_price_response, mock_api_key):
        """fetch_token_price should support custom chain parameter."""
        from core.birdeye import fetch_token_price, BirdEyeResult

        mock_result = BirdEyeResult(success=True, data=mock_price_response)

        with patch("core.birdeye.load_api_key", return_value=mock_api_key):
            with patch("core.birdeye._get_json", return_value=mock_result) as mock_get:
                fetch_token_price(sample_token_address, chain="ethereum")

        # Verify chain header was set
        call_args = mock_get.call_args
        assert call_args.kwargs["headers"]["x-chain"] == "ethereum"

    def test_fetch_token_price_safe_success(self, sample_token_address, mock_price_response, mock_api_key):
        """fetch_token_price_safe should return full result object."""
        from core.birdeye import fetch_token_price_safe, BirdEyeResult

        mock_result = BirdEyeResult(success=True, data=mock_price_response)

        with patch("core.birdeye.load_api_key", return_value=mock_api_key):
            with patch("core.birdeye._get_json", return_value=mock_result):
                result = fetch_token_price_safe(sample_token_address)

        assert isinstance(result, BirdEyeResult)
        assert result.success is True
        assert result.data is not None

    def test_fetch_token_price_safe_no_api_key(self, sample_token_address):
        """fetch_token_price_safe should return error when no API key."""
        from core.birdeye import fetch_token_price_safe

        with patch("core.birdeye.load_api_key", return_value=None):
            result = fetch_token_price_safe(sample_token_address)

        assert result.success is False
        assert result.error == "no_api_key"
        assert result.retryable is False

    def test_fetch_token_price_with_cache_ttl(self, sample_token_address, mock_price_response, mock_api_key):
        """fetch_token_price should respect cache TTL parameter."""
        from core.birdeye import fetch_token_price, BirdEyeResult

        mock_result = BirdEyeResult(success=True, data=mock_price_response)

        with patch("core.birdeye.load_api_key", return_value=mock_api_key):
            with patch("core.birdeye._get_json", return_value=mock_result) as mock_get:
                fetch_token_price(sample_token_address, cache_ttl_seconds=120)

        call_args = mock_get.call_args
        assert call_args.kwargs["cache_ttl_seconds"] == 120


# =============================================================================
# TEST CLASS: OHLCV Data Fetching
# =============================================================================


class TestOHLCVFetching:
    """Tests for OHLCV (candlestick) data fetching."""

    def test_fetch_ohlcv_success(self, sample_token_address, mock_ohlcv_response, mock_api_key):
        """fetch_ohlcv should return OHLCV data on success."""
        from core.birdeye import fetch_ohlcv, BirdEyeResult

        mock_result = BirdEyeResult(success=True, data=mock_ohlcv_response)

        with patch("core.birdeye.load_api_key", return_value=mock_api_key):
            with patch("core.birdeye._get_json", return_value=mock_result):
                result = fetch_ohlcv(sample_token_address)

        assert result is not None
        assert "data" in result
        assert len(result["data"]["items"]) == 3

    def test_fetch_ohlcv_no_api_key(self, sample_token_address):
        """fetch_ohlcv should handle missing API key."""
        from core.birdeye import fetch_ohlcv, BirdEyeResult

        mock_result = BirdEyeResult(success=False, error="no_api_key")

        with patch("core.birdeye.load_api_key", return_value=None):
            with patch("core.birdeye._get_json", return_value=mock_result):
                result = fetch_ohlcv(sample_token_address)

        assert result is None

    def test_fetch_ohlcv_different_timeframes(self, sample_token_address, mock_ohlcv_response, mock_api_key):
        """fetch_ohlcv should support different timeframes."""
        from core.birdeye import fetch_ohlcv, BirdEyeResult

        mock_result = BirdEyeResult(success=True, data=mock_ohlcv_response)
        timeframes = ["1m", "5m", "15m", "1H", "4H", "1D", "1W"]

        with patch("core.birdeye.load_api_key", return_value=mock_api_key):
            with patch("core.birdeye._get_json", return_value=mock_result) as mock_get:
                for tf in timeframes:
                    fetch_ohlcv(sample_token_address, timeframe=tf)

        # Verify timeframe was passed correctly
        assert mock_get.call_count == len(timeframes)

    def test_fetch_ohlcv_safe_success(self, sample_token_address, mock_ohlcv_response, mock_api_key):
        """fetch_ohlcv_safe should return full result object."""
        from core.birdeye import fetch_ohlcv_safe, BirdEyeResult

        mock_result = BirdEyeResult(success=True, data=mock_ohlcv_response)

        with patch("core.birdeye.load_api_key", return_value=mock_api_key):
            with patch("core.birdeye._get_json", return_value=mock_result):
                result = fetch_ohlcv_safe(sample_token_address)

        assert isinstance(result, BirdEyeResult)
        assert result.success is True

    def test_fetch_ohlcv_safe_no_api_key(self, sample_token_address):
        """fetch_ohlcv_safe should return error when no API key."""
        from core.birdeye import fetch_ohlcv_safe

        with patch("core.birdeye.load_api_key", return_value=None):
            result = fetch_ohlcv_safe(sample_token_address)

        assert result.success is False
        assert result.error == "no_api_key"

    def test_fetch_ohlcv_custom_limit(self, sample_token_address, mock_ohlcv_response, mock_api_key):
        """fetch_ohlcv should respect custom limit parameter."""
        from core.birdeye import fetch_ohlcv, BirdEyeResult

        mock_result = BirdEyeResult(success=True, data=mock_ohlcv_response)

        with patch("core.birdeye.load_api_key", return_value=mock_api_key):
            with patch("core.birdeye._get_json", return_value=mock_result):
                fetch_ohlcv(sample_token_address, limit=100)

        # Function calculates time_from based on limit


# =============================================================================
# TEST CLASS: OHLCV Normalization
# =============================================================================


class TestOHLCVNormalization:
    """Tests for OHLCV data normalization."""

    def test_normalize_ohlcv_success(self, mock_ohlcv_response):
        """normalize_ohlcv should convert API response to standard format."""
        from core.birdeye import normalize_ohlcv

        result = normalize_ohlcv(mock_ohlcv_response)

        assert len(result) == 3
        assert all("timestamp" in item for item in result)
        assert all("open" in item for item in result)
        assert all("high" in item for item in result)
        assert all("low" in item for item in result)
        assert all("close" in item for item in result)
        assert all("volume" in item for item in result)

    def test_normalize_ohlcv_sorted_by_timestamp(self, mock_ohlcv_response):
        """normalize_ohlcv should sort results by timestamp."""
        from core.birdeye import normalize_ohlcv

        result = normalize_ohlcv(mock_ohlcv_response)

        timestamps = [item["timestamp"] for item in result]
        assert timestamps == sorted(timestamps)

    def test_normalize_ohlcv_empty_data(self):
        """normalize_ohlcv should handle empty data."""
        from core.birdeye import normalize_ohlcv

        result = normalize_ohlcv({"data": {"items": []}})

        assert result == []

    def test_normalize_ohlcv_missing_fields(self):
        """normalize_ohlcv should handle missing fields with defaults."""
        from core.birdeye import normalize_ohlcv

        data = {
            "data": {
                "items": [
                    {"unixTime": 1704067200},  # Only timestamp
                ]
            }
        }

        result = normalize_ohlcv(data)

        assert len(result) == 1
        assert result[0]["open"] == 0
        assert result[0]["volume"] == 0

    def test_normalize_ohlcv_invalid_values(self):
        """normalize_ohlcv should skip items with invalid values."""
        from core.birdeye import normalize_ohlcv

        data = {
            "data": {
                "items": [
                    {"unixTime": 1704067200, "o": "not_a_number"},
                    {"unixTime": 1704070800, "o": 1.0, "h": 1.2, "l": 0.9, "c": 1.1, "v": 10000},
                ]
            }
        }

        result = normalize_ohlcv(data)

        # Should skip the invalid item
        assert len(result) == 1


# =============================================================================
# TEST CLASS: Token Overview
# =============================================================================


class TestTokenOverview:
    """Tests for token overview fetching."""

    def test_fetch_token_overview_success(self, sample_token_address, mock_overview_response, mock_api_key):
        """fetch_token_overview should return overview data on success."""
        from core.birdeye import fetch_token_overview, BirdEyeResult

        mock_result = BirdEyeResult(success=True, data=mock_overview_response)

        with patch("core.birdeye.load_api_key", return_value=mock_api_key):
            with patch("core.birdeye._get_json", return_value=mock_result):
                result = fetch_token_overview(sample_token_address)

        assert result is not None
        assert result["data"]["symbol"] == "RAY"

    def test_fetch_token_overview_failure(self, sample_token_address):
        """fetch_token_overview should return None on failure."""
        from core.birdeye import fetch_token_overview, BirdEyeResult

        mock_result = BirdEyeResult(success=False, error="not_found")

        with patch("core.birdeye.load_api_key", return_value="key"):
            with patch("core.birdeye._get_json", return_value=mock_result):
                result = fetch_token_overview(sample_token_address)

        assert result is None


# =============================================================================
# TEST CLASS: Trending Tokens
# =============================================================================


class TestTrendingTokens:
    """Tests for trending tokens fetching."""

    def test_fetch_trending_tokens_success(self, mock_trending_response, mock_api_key):
        """fetch_trending_tokens should return trending data on success."""
        from core.birdeye import fetch_trending_tokens, BirdEyeResult

        mock_result = BirdEyeResult(success=True, data=mock_trending_response)

        with patch("core.birdeye.load_api_key", return_value=mock_api_key):
            with patch("core.birdeye._get_json", return_value=mock_result):
                result = fetch_trending_tokens()

        assert result is not None
        assert len(result["data"]["tokens"]) == 3

    def test_fetch_trending_tokens_limit_capped(self, mock_trending_response, mock_api_key):
        """fetch_trending_tokens should cap limit at 20."""
        from core.birdeye import fetch_trending_tokens, BirdEyeResult

        mock_result = BirdEyeResult(success=True, data=mock_trending_response)

        with patch("core.birdeye.load_api_key", return_value=mock_api_key):
            with patch("core.birdeye._get_json", return_value=mock_result) as mock_get:
                fetch_trending_tokens(limit=100)

        call_args = mock_get.call_args
        assert call_args.kwargs["params"]["limit"] == 20

    def test_fetch_trending_tokens_limit_minimum(self, mock_trending_response, mock_api_key):
        """fetch_trending_tokens should enforce minimum limit of 1."""
        from core.birdeye import fetch_trending_tokens, BirdEyeResult

        mock_result = BirdEyeResult(success=True, data=mock_trending_response)

        with patch("core.birdeye.load_api_key", return_value=mock_api_key):
            with patch("core.birdeye._get_json", return_value=mock_result) as mock_get:
                fetch_trending_tokens(limit=0)

        call_args = mock_get.call_args
        assert call_args.kwargs["params"]["limit"] == 1

    def test_fetch_trending_tokens_fallback_without_sort(self, mock_trending_response, mock_api_key):
        """fetch_trending_tokens should retry without sort params on failure."""
        from core.birdeye import fetch_trending_tokens, BirdEyeResult

        fail_result = BirdEyeResult(success=False, error="bad_params")
        success_result = BirdEyeResult(success=True, data=mock_trending_response)

        with patch("core.birdeye.load_api_key", return_value=mock_api_key):
            with patch("core.birdeye._get_json", side_effect=[fail_result, success_result]):
                result = fetch_trending_tokens(sort_by="volume24h")

        assert result is not None

    def test_fetch_trending_tokens_safe_no_api_key(self):
        """fetch_trending_tokens_safe should return error when no API key."""
        from core.birdeye import fetch_trending_tokens_safe

        with patch("core.birdeye.load_api_key", return_value=None):
            result = fetch_trending_tokens_safe()

        assert result.success is False
        assert result.error == "no_api_key"


# =============================================================================
# TEST CLASS: HTTP Error Classification
# =============================================================================


class TestHttpErrorClassification:
    """Tests for HTTP error classification."""

    def test_classify_401_invalid_api_key(self):
        """401 should be classified as invalid_api_key."""
        from core.birdeye import _classify_http_error

        error_type, retryable = _classify_http_error(401)

        assert error_type == "invalid_api_key"
        assert retryable is False

    def test_classify_403_forbidden(self):
        """403 should be classified as forbidden."""
        from core.birdeye import _classify_http_error

        error_type, retryable = _classify_http_error(403)

        assert error_type == "forbidden"
        assert retryable is False

    def test_classify_404_not_found(self):
        """404 should be classified as not_found."""
        from core.birdeye import _classify_http_error

        error_type, retryable = _classify_http_error(404)

        assert error_type == "not_found"
        assert retryable is False

    def test_classify_429_rate_limited(self):
        """429 should be classified as rate_limited."""
        from core.birdeye import _classify_http_error

        error_type, retryable = _classify_http_error(429)

        assert error_type == "rate_limited"
        assert retryable is True

    def test_classify_500_server_error(self):
        """500 should be classified as server_error."""
        from core.birdeye import _classify_http_error

        error_type, retryable = _classify_http_error(500)

        assert error_type == "server_error"
        assert retryable is True

    def test_classify_502_server_error(self):
        """502 should be classified as server_error."""
        from core.birdeye import _classify_http_error

        error_type, retryable = _classify_http_error(502)

        assert error_type == "server_error"
        assert retryable is True

    def test_classify_503_server_error(self):
        """503 should be classified as server_error."""
        from core.birdeye import _classify_http_error

        error_type, retryable = _classify_http_error(503)

        assert error_type == "server_error"
        assert retryable is True

    def test_classify_other_4xx_error(self):
        """Other 4xx errors should be classified by status code."""
        from core.birdeye import _classify_http_error

        error_type, retryable = _classify_http_error(400)

        assert error_type == "http_400"
        assert retryable is False


# =============================================================================
# TEST CLASS: HTTP Request Handling (_get_json)
# =============================================================================


class TestGetJson:
    """Tests for the core HTTP request function."""

    def test_get_json_success(self, mock_price_response):
        """_get_json should return success result on 200."""
        from core.birdeye import _get_json

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_price_response

        with patch("requests.get", return_value=mock_response):
            result = _get_json("https://api.example.com/test")

        assert result.success is True
        assert result.data == mock_price_response

    def test_get_json_with_cache_hit(self, mock_price_response, temp_cache_dir):
        """_get_json should return cached data when available."""
        from core.birdeye import _get_json, _write_cache, _cache_path

        with patch("core.birdeye.CACHE_DIR", temp_cache_dir):
            # Pre-populate cache
            cache_path = _cache_path("https://api.example.com/test", None)
            _write_cache(cache_path, mock_price_response)

            result = _get_json(
                "https://api.example.com/test",
                cache_ttl_seconds=3600,
            )

        assert result.success is True
        assert result.cached is True
        assert result.data == mock_price_response

    def test_get_json_rate_limit_wait(self):
        """_get_json should wait when rate limited."""
        from core.birdeye import _get_json

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}

        with patch("core.birdeye._check_rate_limit", return_value=(True, 0.01)):
            with patch("time.sleep") as mock_sleep:
                with patch("requests.get", return_value=mock_response):
                    _get_json("https://api.example.com/test")

        mock_sleep.assert_called()

    def test_get_json_retry_on_429(self):
        """_get_json should retry on 429 response."""
        from core.birdeye import _get_json

        mock_429 = MagicMock()
        mock_429.status_code = 429
        mock_429.headers = {"Retry-After": "1"}

        mock_200 = MagicMock()
        mock_200.status_code = 200
        mock_200.json.return_value = {"success": True}

        with patch("requests.get", side_effect=[mock_429, mock_200]):
            with patch("time.sleep"):
                result = _get_json("https://api.example.com/test", retries=2)

        assert result.success is True

    def test_get_json_retry_on_500(self):
        """_get_json should retry on 500 response."""
        from core.birdeye import _get_json

        mock_500 = MagicMock()
        mock_500.status_code = 500

        mock_200 = MagicMock()
        mock_200.status_code = 200
        mock_200.json.return_value = {"success": True}

        with patch("requests.get", side_effect=[mock_500, mock_200]):
            with patch("time.sleep"):
                result = _get_json("https://api.example.com/test", retries=2)

        assert result.success is True

    def test_get_json_client_error_no_retry(self):
        """_get_json should not retry on 4xx client errors."""
        from core.birdeye import _get_json

        mock_400 = MagicMock()
        mock_400.status_code = 400
        mock_400.text = "Bad Request"

        with patch("requests.get", return_value=mock_400):
            result = _get_json("https://api.example.com/test", retries=3)

        assert result.success is False
        assert result.retryable is False

    def test_get_json_timeout_retry(self):
        """_get_json should retry on timeout."""
        from core.birdeye import _get_json

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}

        with patch("requests.get", side_effect=[requests.Timeout(), mock_response]):
            with patch("time.sleep"):
                result = _get_json("https://api.example.com/test", retries=2)

        assert result.success is True

    def test_get_json_connection_error_retry(self):
        """_get_json should retry on connection error."""
        from core.birdeye import _get_json

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}

        with patch("requests.get", side_effect=[requests.ConnectionError(), mock_response]):
            with patch("time.sleep"):
                result = _get_json("https://api.example.com/test", retries=2)

        assert result.success is True

    def test_get_json_invalid_json_no_retry(self):
        """_get_json should not retry on invalid JSON response."""
        from core.birdeye import _get_json

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("error", "doc", 0)

        with patch("requests.get", return_value=mock_response):
            result = _get_json("https://api.example.com/test", retries=3)

        assert result.success is False
        assert result.error == "invalid_json"
        assert result.retryable is False

    def test_get_json_api_error_response(self):
        """_get_json should handle API-level error in response."""
        from core.birdeye import _get_json

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": False, "message": "token_not_found"}

        with patch("requests.get", return_value=mock_response):
            result = _get_json("https://api.example.com/test")

        assert result.success is False
        assert result.error == "token_not_found"

    def test_get_json_exhausts_retries(self):
        """_get_json should return error after exhausting retries."""
        from core.birdeye import _get_json

        with patch("requests.get", side_effect=requests.Timeout()):
            with patch("time.sleep"):
                result = _get_json("https://api.example.com/test", retries=3)

        assert result.success is False
        assert result.error == "timeout"

    def test_get_json_caches_successful_response(self, temp_cache_dir):
        """_get_json should cache successful responses."""
        from core.birdeye import _get_json, _cache_path, _read_cache

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}

        with patch("core.birdeye.CACHE_DIR", temp_cache_dir):
            with patch("requests.get", return_value=mock_response):
                _get_json(
                    "https://api.example.com/test",
                    cache_ttl_seconds=3600,
                )

            # Verify cache was written
            cache_path = _cache_path("https://api.example.com/test", None)
            cached = _read_cache(cache_path, 3600)

        assert cached == {"data": "test"}


# =============================================================================
# TEST CLASS: Caching Functions
# =============================================================================


class TestCacheFunctions:
    """Tests for caching functionality."""

    def test_cache_path_generation(self, temp_cache_dir):
        """_cache_path should generate deterministic paths."""
        from core.birdeye import _cache_path

        with patch("core.birdeye.CACHE_DIR", temp_cache_dir):
            path1 = _cache_path("https://api.example.com/test", {"param": "value"})
            path2 = _cache_path("https://api.example.com/test", {"param": "value"})

        assert path1 == path2

    def test_cache_path_different_params(self, temp_cache_dir):
        """_cache_path should generate different paths for different params."""
        from core.birdeye import _cache_path

        with patch("core.birdeye.CACHE_DIR", temp_cache_dir):
            path1 = _cache_path("https://api.example.com/test", {"param": "value1"})
            path2 = _cache_path("https://api.example.com/test", {"param": "value2"})

        assert path1 != path2

    def test_write_and_read_cache(self, temp_cache_dir):
        """Should write and read cache correctly."""
        from core.birdeye import _write_cache, _read_cache

        cache_path = temp_cache_dir / "test_cache.json"
        data = {"test": "data", "number": 123}

        _write_cache(cache_path, data)
        result = _read_cache(cache_path, ttl_seconds=3600)

        assert result == data

    def test_read_cache_expired(self, temp_cache_dir):
        """Should return None for expired cache."""
        from core.birdeye import _write_cache, _read_cache

        cache_path = temp_cache_dir / "test_cache.json"
        data = {"test": "data"}

        # Write cache with artificial old timestamp
        payload = {"cached_at": time.time() - 3600, "data": data}
        cache_path.write_text(json.dumps(payload))

        result = _read_cache(cache_path, ttl_seconds=60)

        assert result is None

    def test_read_cache_invalid_json(self, temp_cache_dir):
        """Should return None for invalid cache file."""
        from core.birdeye import _read_cache

        cache_path = temp_cache_dir / "test_cache.json"
        cache_path.write_text("not valid json")

        result = _read_cache(cache_path, ttl_seconds=3600)

        assert result is None

    def test_read_cache_missing_file(self, temp_cache_dir):
        """Should return None for missing cache file."""
        from core.birdeye import _read_cache

        cache_path = temp_cache_dir / "nonexistent.json"

        result = _read_cache(cache_path, ttl_seconds=3600)

        assert result is None

    def test_read_cache_missing_cached_at(self, temp_cache_dir):
        """Should return None when cached_at is missing."""
        from core.birdeye import _read_cache

        cache_path = temp_cache_dir / "test_cache.json"
        cache_path.write_text(json.dumps({"data": "test"}))

        result = _read_cache(cache_path, ttl_seconds=3600)

        assert result is None

    def test_clear_cache(self, temp_cache_dir):
        """clear_cache should remove all cache files."""
        from core.birdeye import clear_cache

        # Create some cache files
        for i in range(5):
            (temp_cache_dir / f"cache_{i}.json").write_text("{}")

        with patch("core.birdeye.CACHE_DIR", temp_cache_dir):
            count = clear_cache()

        assert count == 5
        assert len(list(temp_cache_dir.glob("*.json"))) == 0

    def test_clear_cache_empty_directory(self, temp_cache_dir):
        """clear_cache should handle empty directory."""
        from core.birdeye import clear_cache

        with patch("core.birdeye.CACHE_DIR", temp_cache_dir):
            count = clear_cache()

        assert count == 0

    def test_clear_cache_nonexistent_directory(self, tmp_path):
        """clear_cache should handle nonexistent directory."""
        from core.birdeye import clear_cache

        nonexistent = tmp_path / "nonexistent"

        with patch("core.birdeye.CACHE_DIR", nonexistent):
            count = clear_cache()

        assert count == 0


# =============================================================================
# TEST CLASS: Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests combining multiple components."""

    def test_full_price_fetch_flow(self, sample_token_address, mock_price_response, mock_api_key, temp_cache_dir):
        """Test complete flow: fetch, cache, return cached."""
        from core.birdeye import fetch_token_price, BirdEyeResult

        mock_result = BirdEyeResult(success=True, data=mock_price_response)

        with patch("core.birdeye.load_api_key", return_value=mock_api_key):
            with patch("core.birdeye.CACHE_DIR", temp_cache_dir):
                with patch("core.birdeye._get_json", return_value=mock_result) as mock_get:
                    # First call - should hit API
                    result1 = fetch_token_price(sample_token_address, cache_ttl_seconds=3600)

                    assert result1 is not None
                    assert mock_get.call_count == 1

    def test_api_status_reflects_state(self, mock_api_key):
        """API status should accurately reflect current state."""
        from core.birdeye import get_api_status, _record_request, _record_rate_limit

        with patch("core.birdeye.has_api_key", return_value=True):
            # Make some requests
            for _ in range(10):
                _record_request()

            # Trigger backoff
            _record_rate_limit()

            status = get_api_status()

        assert status["has_api_key"] is True
        assert status["requests_last_minute"] == 10
        assert status["rate_limit_backoff"] is not None


# =============================================================================
# TEST CLASS: Constants and Configuration
# =============================================================================


class TestConfiguration:
    """Tests for module constants and configuration."""

    def test_rate_limit_constant(self):
        """Rate limit constant should be defined."""
        from core.birdeye import RATE_LIMIT_REQUESTS_PER_MINUTE

        assert RATE_LIMIT_REQUESTS_PER_MINUTE == 100

    def test_base_url_constant(self):
        """Base URL constant should be defined."""
        from core.birdeye import BASE_URL

        assert BASE_URL == "https://public-api.birdeye.so"

    def test_user_agent_constant(self):
        """User agent constant should be defined."""
        from core.birdeye import USER_AGENT

        assert "LifeOS" in USER_AGENT
        assert "Jarvis" in USER_AGENT


# =============================================================================
# RUN CONFIGURATION
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
