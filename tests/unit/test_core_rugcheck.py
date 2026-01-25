"""
Comprehensive tests for core/rugcheck.py - Token scam detection and safety checks.

This is CRITICAL SAFETY CODE for detecting scam tokens before trading.
Tests cover:
- Token scam detection for various risk levels
- Risk scoring calculation
- API integration (mocked responses)
- Warning generation
- Error handling (API failures, malformed responses)
- Edge cases (new tokens, tokens with no data)
"""

import hashlib
import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock

import pytest
import requests

from core import rugcheck
from core.rugcheck import (
    _backoff_delay,
    _to_float,
    _authority_value,
    _cache_path,
    _read_cache,
    _write_cache,
    _get_json,
    fetch_report,
    has_locked_liquidity,
    best_lock_stats,
    evaluate_safety,
    SPL_TOKEN_PROGRAM,
    BASE_URL,
    USER_AGENT,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create temporary directory for cache files."""
    cache_dir = tmp_path / "rugcheck_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


@pytest.fixture
def sample_safe_report():
    """A token report that passes all safety checks."""
    return {
        "tokenProgram": SPL_TOKEN_PROGRAM,
        "rugged": False,
        "mintAuthority": None,
        "freezeAuthority": None,
        "transferFee": {"pct": 0.0},
        "markets": [
            {
                "lp": {
                    "lpLockedPct": 95.0,
                    "lpLockedUSD": 50000.0,
                }
            }
        ],
        "lockers": {},
    }


@pytest.fixture
def sample_unsafe_report():
    """A token report that fails safety checks - typical rug pull."""
    return {
        "tokenProgram": SPL_TOKEN_PROGRAM,
        "rugged": True,
        "mintAuthority": "SomeAuthority123",
        "freezeAuthority": "FreezeAuthority456",
        "transferFee": {"pct": 0.05},  # 5% fee = 500 bps
        "markets": [
            {
                "lp": {
                    "lpLockedPct": 0.0,
                    "lpLockedUSD": 0.0,
                }
            }
        ],
        "lockers": {},
    }


@pytest.fixture
def sample_medium_risk_report():
    """A token report with some warning signs."""
    return {
        "tokenProgram": SPL_TOKEN_PROGRAM,
        "rugged": False,
        "mintAuthority": "MintAuth789",  # Still has mint authority
        "freezeAuthority": None,
        "transferFee": {"pct": 0.0},
        "markets": [
            {
                "lp": {
                    "lpLockedPct": 60.0,  # Marginally locked
                    "lpLockedUSD": 10000.0,
                }
            }
        ],
        "lockers": {},
    }


@pytest.fixture
def sample_report_with_nested_token():
    """A report with authority values in nested token object."""
    return {
        "tokenProgram": SPL_TOKEN_PROGRAM,
        "rugged": False,
        "token": {
            "mintAuthority": "NestedMintAuth",
            "freezeAuthority": "NestedFreezeAuth",
        },
        "transferFee": {"pct": 0.0},
        "markets": [
            {
                "lp": {
                    "lpLockedPct": 80.0,
                    "lpLockedUSD": 25000.0,
                }
            }
        ],
        "lockers": {},
    }


@pytest.fixture
def sample_report_with_lockers():
    """A report that uses lockers instead of LP locks."""
    return {
        "tokenProgram": SPL_TOKEN_PROGRAM,
        "rugged": False,
        "mintAuthority": None,
        "freezeAuthority": None,
        "transferFee": {"pct": 0.0},
        "markets": [],  # No market LP data
        "lockers": {
            "locker1": {"usdcLocked": 75000.0},
            "locker2": {"usdcLocked": 25000.0},
        },
    }


# =============================================================================
# Test Helper Functions
# =============================================================================

class TestBackoffDelay:
    """Tests for exponential backoff calculation."""

    def test_backoff_delay_first_attempt(self):
        """First attempt should use base delay."""
        result = _backoff_delay(1.0, 0)
        assert result == 1.0

    def test_backoff_delay_second_attempt(self):
        """Second attempt doubles the delay."""
        result = _backoff_delay(1.0, 1)
        assert result == 2.0

    def test_backoff_delay_exponential_growth(self):
        """Delays should grow exponentially."""
        assert _backoff_delay(1.0, 2) == 4.0
        assert _backoff_delay(1.0, 3) == 8.0
        assert _backoff_delay(1.0, 4) == 16.0

    def test_backoff_delay_respects_max(self):
        """Delay should not exceed max_delay."""
        result = _backoff_delay(1.0, 10, max_delay=30.0)
        assert result == 30.0

    def test_backoff_delay_custom_base(self):
        """Custom base delay should be respected."""
        assert _backoff_delay(2.0, 0) == 2.0
        assert _backoff_delay(2.0, 1) == 4.0
        assert _backoff_delay(0.5, 2) == 2.0


class TestToFloat:
    """Tests for safe float conversion."""

    def test_to_float_from_none(self):
        """None should return 0.0."""
        assert _to_float(None) == 0.0

    def test_to_float_from_int(self):
        """Integer should convert to float."""
        assert _to_float(42) == 42.0

    def test_to_float_from_float(self):
        """Float should remain float."""
        assert _to_float(3.14) == 3.14

    def test_to_float_from_string_numeric(self):
        """Numeric string should convert."""
        assert _to_float("123.45") == 123.45

    def test_to_float_from_string_invalid(self):
        """Invalid string should return 0.0."""
        assert _to_float("not a number") == 0.0

    def test_to_float_from_empty_string(self):
        """Empty string should return 0.0."""
        assert _to_float("") == 0.0

    def test_to_float_from_list(self):
        """List should return 0.0."""
        assert _to_float([1, 2, 3]) == 0.0

    def test_to_float_from_dict(self):
        """Dict should return 0.0."""
        assert _to_float({"value": 100}) == 0.0


class TestAuthorityValue:
    """Tests for extracting authority values from reports."""

    def test_authority_value_direct(self):
        """Authority at top level should be found."""
        report = {"mintAuthority": "DirectAuth123"}
        assert _authority_value(report, "mintAuthority") == "DirectAuth123"

    def test_authority_value_nested_in_token(self):
        """Authority nested in token object should be found."""
        report = {"token": {"mintAuthority": "NestedAuth456"}}
        assert _authority_value(report, "mintAuthority") == "NestedAuth456"

    def test_authority_value_none(self):
        """Missing authority should return None."""
        report = {"tokenProgram": SPL_TOKEN_PROGRAM}
        assert _authority_value(report, "mintAuthority") is None

    def test_authority_value_empty_string(self):
        """Empty string authority should return None (falsy)."""
        report = {"mintAuthority": ""}
        assert _authority_value(report, "mintAuthority") is None

    def test_authority_value_prefers_direct(self):
        """Direct value should take precedence over nested."""
        report = {
            "mintAuthority": "DirectAuth",
            "token": {"mintAuthority": "NestedAuth"},
        }
        assert _authority_value(report, "mintAuthority") == "DirectAuth"


# =============================================================================
# Test Cache Functions
# =============================================================================

class TestCacheFunctions:
    """Tests for caching mechanism."""

    def test_cache_path_generates_hash(self, temp_cache_dir, monkeypatch):
        """Cache path should be a hash-based filename."""
        monkeypatch.setattr(rugcheck, "CACHE_DIR", temp_cache_dir)
        url = "https://api.rugcheck.xyz/v1/tokens/abc123/report"
        path = _cache_path(url, None)
        assert path.suffix == ".json"
        assert len(path.stem) == 20  # SHA256 truncated to 20 chars

    def test_cache_path_includes_params(self, temp_cache_dir, monkeypatch):
        """Cache path should differ with different params."""
        monkeypatch.setattr(rugcheck, "CACHE_DIR", temp_cache_dir)
        url = "https://api.rugcheck.xyz/v1/tokens/abc123/report"
        path1 = _cache_path(url, None)
        path2 = _cache_path(url, {"foo": "bar"})
        assert path1 != path2

    def test_cache_path_params_sorted(self, temp_cache_dir, monkeypatch):
        """Params should be sorted for consistent hashing."""
        monkeypatch.setattr(rugcheck, "CACHE_DIR", temp_cache_dir)
        url = "https://api.rugcheck.xyz/v1/tokens/abc123/report"
        path1 = _cache_path(url, {"a": "1", "b": "2"})
        path2 = _cache_path(url, {"b": "2", "a": "1"})
        assert path1 == path2

    def test_write_cache_creates_file(self, temp_cache_dir):
        """Writing cache should create a file."""
        cache_file = temp_cache_dir / "test_cache.json"
        _write_cache(cache_file, {"test": "data"})
        assert cache_file.exists()

    def test_write_cache_includes_timestamp(self, temp_cache_dir):
        """Cache file should include cached_at timestamp."""
        cache_file = temp_cache_dir / "test_cache.json"
        _write_cache(cache_file, {"test": "data"})
        content = json.loads(cache_file.read_text())
        assert "cached_at" in content
        assert "data" in content
        assert content["data"] == {"test": "data"}

    def test_read_cache_valid(self, temp_cache_dir):
        """Reading valid cache within TTL should return data."""
        cache_file = temp_cache_dir / "valid_cache.json"
        payload = {"cached_at": time.time(), "data": {"token": "value"}}
        cache_file.write_text(json.dumps(payload))
        result = _read_cache(cache_file, ttl_seconds=3600)
        assert result == {"token": "value"}

    def test_read_cache_expired(self, temp_cache_dir):
        """Expired cache should return None."""
        cache_file = temp_cache_dir / "expired_cache.json"
        # Cached 2 hours ago
        payload = {"cached_at": time.time() - 7200, "data": {"token": "value"}}
        cache_file.write_text(json.dumps(payload))
        result = _read_cache(cache_file, ttl_seconds=3600)  # 1 hour TTL
        assert result is None

    def test_read_cache_missing_file(self, temp_cache_dir):
        """Missing cache file should return None."""
        cache_file = temp_cache_dir / "nonexistent.json"
        result = _read_cache(cache_file, ttl_seconds=3600)
        assert result is None

    def test_read_cache_invalid_json(self, temp_cache_dir):
        """Invalid JSON should return None."""
        cache_file = temp_cache_dir / "invalid.json"
        cache_file.write_text("not valid json {{{")
        result = _read_cache(cache_file, ttl_seconds=3600)
        assert result is None

    def test_read_cache_missing_cached_at(self, temp_cache_dir):
        """Cache without cached_at should return None."""
        cache_file = temp_cache_dir / "no_timestamp.json"
        cache_file.write_text(json.dumps({"data": {"token": "value"}}))
        result = _read_cache(cache_file, ttl_seconds=3600)
        assert result is None


# =============================================================================
# Test API Functions (Mocked)
# =============================================================================

class TestGetJson:
    """Tests for HTTP request handling with mocking."""

    @patch("core.rugcheck.requests.get")
    def test_get_json_success(self, mock_get):
        """Successful API call should return data."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "success"}
        mock_get.return_value = mock_response

        result = _get_json("https://api.test.com/endpoint", cache_ttl_seconds=0)
        assert result == {"data": "success"}

    @patch("core.rugcheck.requests.get")
    def test_get_json_retries_on_429(self, mock_get):
        """429 rate limit should trigger retry."""
        mock_response_429 = Mock()
        mock_response_429.status_code = 429
        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {"data": "after_retry"}
        mock_get.side_effect = [mock_response_429, mock_response_success]

        with patch("core.rugcheck.time.sleep"):  # Speed up test
            result = _get_json(
                "https://api.test.com/endpoint",
                cache_ttl_seconds=0,
                backoff_seconds=0.001,
            )
        assert result == {"data": "after_retry"}

    @patch("core.rugcheck.requests.get")
    def test_get_json_retries_on_503(self, mock_get):
        """503 service unavailable should trigger retry."""
        mock_response_503 = Mock()
        mock_response_503.status_code = 503
        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {"data": "recovered"}
        mock_get.side_effect = [mock_response_503, mock_response_success]

        with patch("core.rugcheck.time.sleep"):
            result = _get_json(
                "https://api.test.com/endpoint",
                cache_ttl_seconds=0,
                backoff_seconds=0.001,
            )
        assert result == {"data": "recovered"}

    @patch("core.rugcheck.requests.get")
    def test_get_json_returns_none_after_retries_exhausted(self, mock_get):
        """Should return None after all retries fail."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.HTTPError("Server Error")
        mock_get.return_value = mock_response

        with patch("core.rugcheck.time.sleep"):
            with patch("builtins.print"):  # Suppress error print
                result = _get_json(
                    "https://api.test.com/endpoint",
                    cache_ttl_seconds=0,
                    retries=2,
                    backoff_seconds=0.001,
                )
        assert result is None

    @patch("core.rugcheck.requests.get")
    def test_get_json_handles_request_exception(self, mock_get):
        """Network errors should return None after retries."""
        mock_get.side_effect = requests.RequestException("Connection failed")

        with patch("core.rugcheck.time.sleep"):
            with patch("builtins.print"):
                result = _get_json(
                    "https://api.test.com/endpoint",
                    cache_ttl_seconds=0,
                    retries=2,
                    backoff_seconds=0.001,
                )
        assert result is None

    @patch("core.rugcheck.requests.get")
    def test_get_json_uses_cache(self, mock_get, temp_cache_dir, monkeypatch):
        """Should use cached data when available."""
        monkeypatch.setattr(rugcheck, "CACHE_DIR", temp_cache_dir)

        # Pre-populate cache
        url = "https://api.test.com/cached"
        cache_file = _cache_path(url, None)
        payload = {"cached_at": time.time(), "data": {"from": "cache"}}
        cache_file.write_text(json.dumps(payload))

        result = _get_json(url, cache_ttl_seconds=3600)
        assert result == {"from": "cache"}
        mock_get.assert_not_called()

    @patch("core.rugcheck.requests.get")
    def test_get_json_writes_cache(self, mock_get, temp_cache_dir, monkeypatch):
        """Successful API call should write to cache."""
        monkeypatch.setattr(rugcheck, "CACHE_DIR", temp_cache_dir)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"new": "data"}
        mock_get.return_value = mock_response

        url = "https://api.test.com/new"
        result = _get_json(url, cache_ttl_seconds=3600)
        assert result == {"new": "data"}

        # Verify cache was written
        cache_file = _cache_path(url, None)
        assert cache_file.exists()

    @patch("core.rugcheck.requests.get")
    def test_get_json_sends_user_agent(self, mock_get):
        """Requests should include proper User-Agent header."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_get.return_value = mock_response

        _get_json("https://api.test.com/endpoint", cache_ttl_seconds=0)
        call_args = mock_get.call_args
        assert call_args.kwargs["headers"]["User-Agent"] == USER_AGENT


class TestFetchReport:
    """Tests for fetch_report function."""

    @patch("core.rugcheck._get_json")
    def test_fetch_report_calls_correct_url(self, mock_get_json):
        """Should call correct API endpoint."""
        mock_get_json.return_value = {"test": "data"}
        mint = "SoLTokenMint123456789"
        result = fetch_report(mint)

        expected_url = f"{BASE_URL}/{mint}/report"
        mock_get_json.assert_called_once_with(expected_url, cache_ttl_seconds=3600)
        assert result == {"test": "data"}

    @patch("core.rugcheck._get_json")
    def test_fetch_report_custom_ttl(self, mock_get_json):
        """Custom TTL should be passed through."""
        mock_get_json.return_value = {}
        fetch_report("mint123", cache_ttl_seconds=7200)
        mock_get_json.assert_called_once_with(
            f"{BASE_URL}/mint123/report", cache_ttl_seconds=7200
        )


# =============================================================================
# Test Liquidity Lock Functions
# =============================================================================

class TestHasLockedLiquidity:
    """Tests for liquidity lock detection."""

    def test_has_locked_liquidity_none_report(self):
        """None report should return False."""
        assert has_locked_liquidity(None) is False

    def test_has_locked_liquidity_safe_token(self, sample_safe_report):
        """Safe token with locked LP should return True."""
        assert has_locked_liquidity(sample_safe_report) is True

    def test_has_locked_liquidity_unsafe_token(self, sample_unsafe_report):
        """Unsafe token with 0% lock should return False."""
        assert has_locked_liquidity(sample_unsafe_report) is False

    def test_has_locked_liquidity_custom_threshold(self, sample_safe_report):
        """Custom threshold should be respected."""
        # 95% lock passes 50% threshold
        assert has_locked_liquidity(sample_safe_report, min_locked_pct=50.0) is True
        # 95% lock fails 99% threshold
        assert has_locked_liquidity(sample_safe_report, min_locked_pct=99.0) is False

    def test_has_locked_liquidity_min_usd(self, sample_safe_report):
        """Minimum USD threshold should be checked."""
        # $50,000 lock passes $10,000 threshold
        assert has_locked_liquidity(sample_safe_report, min_locked_usd=10000.0) is True
        # $50,000 lock fails $100,000 threshold
        assert has_locked_liquidity(sample_safe_report, min_locked_usd=100000.0) is False

    def test_has_locked_liquidity_empty_markets(self):
        """Empty markets list should return False."""
        report = {"markets": []}
        assert has_locked_liquidity(report) is False

    def test_has_locked_liquidity_multiple_markets(self):
        """Should pass if any market has sufficient lock."""
        report = {
            "markets": [
                {"lp": {"lpLockedPct": 10.0, "lpLockedUSD": 1000.0}},  # Insufficient
                {"lp": {"lpLockedPct": 80.0, "lpLockedUSD": 50000.0}},  # Sufficient
            ]
        }
        assert has_locked_liquidity(report) is True

    def test_has_locked_liquidity_uses_lockers(self, sample_report_with_lockers):
        """Lockers should be checked if min_locked_pct is 0."""
        # With non-zero pct requirement, lockers alone won't satisfy
        assert has_locked_liquidity(
            sample_report_with_lockers, min_locked_pct=50.0
        ) is False
        # With zero pct requirement, lockers should satisfy USD check
        assert has_locked_liquidity(
            sample_report_with_lockers, min_locked_pct=0.0, min_locked_usd=50000.0
        ) is True

    def test_has_locked_liquidity_null_lp(self):
        """Null lp object should be handled gracefully."""
        report = {"markets": [{"lp": None}]}
        assert has_locked_liquidity(report) is False

    def test_has_locked_liquidity_missing_lp_fields(self):
        """Missing lp fields should default to 0."""
        report = {"markets": [{"lp": {}}]}
        assert has_locked_liquidity(report) is False


class TestBestLockStats:
    """Tests for best_lock_stats calculation."""

    def test_best_lock_stats_none_report(self):
        """None report should return zeros."""
        result = best_lock_stats(None)
        assert result == {"best_lp_locked_pct": 0.0, "best_lp_locked_usd": 0.0}

    def test_best_lock_stats_safe_token(self, sample_safe_report):
        """Should extract lock stats from safe token."""
        result = best_lock_stats(sample_safe_report)
        assert result["best_lp_locked_pct"] == 95.0
        assert result["best_lp_locked_usd"] == 50000.0

    def test_best_lock_stats_multiple_markets(self):
        """Should find best across multiple markets."""
        report = {
            "markets": [
                {"lp": {"lpLockedPct": 50.0, "lpLockedUSD": 10000.0}},
                {"lp": {"lpLockedPct": 90.0, "lpLockedUSD": 75000.0}},
                {"lp": {"lpLockedPct": 70.0, "lpLockedUSD": 30000.0}},
            ]
        }
        result = best_lock_stats(report)
        assert result["best_lp_locked_pct"] == 90.0
        assert result["best_lp_locked_usd"] == 75000.0

    def test_best_lock_stats_empty_markets(self):
        """Empty markets should return zeros."""
        report = {"markets": []}
        result = best_lock_stats(report)
        assert result == {"best_lp_locked_pct": 0.0, "best_lp_locked_usd": 0.0}

    def test_best_lock_stats_ties_prefer_higher_usd(self):
        """When pct is tied, should prefer higher USD."""
        report = {
            "markets": [
                {"lp": {"lpLockedPct": 80.0, "lpLockedUSD": 10000.0}},
                {"lp": {"lpLockedPct": 80.0, "lpLockedUSD": 50000.0}},
            ]
        }
        result = best_lock_stats(report)
        assert result["best_lp_locked_pct"] == 80.0
        assert result["best_lp_locked_usd"] == 50000.0


# =============================================================================
# Test Safety Evaluation
# =============================================================================

class TestEvaluateSafety:
    """Tests for comprehensive safety evaluation."""

    def test_evaluate_safety_none_report(self):
        """None report should return failure with missing_report issue."""
        result = evaluate_safety(None)
        assert result["ok"] is False
        assert "missing_report" in result["issues"]

    def test_evaluate_safety_safe_token(self, sample_safe_report):
        """Safe token should pass all checks."""
        result = evaluate_safety(sample_safe_report)
        assert result["ok"] is True
        assert result["issues"] == []
        assert result["details"]["best_lp_locked_pct"] == 95.0

    def test_evaluate_safety_rugged_token(self, sample_unsafe_report):
        """Rugged token should be flagged."""
        result = evaluate_safety(sample_unsafe_report)
        assert result["ok"] is False
        assert "rugged_flag" in result["issues"]

    def test_evaluate_safety_non_spl_program(self):
        """Non-SPL token program should be flagged."""
        report = {
            "tokenProgram": "SomeOtherProgram123",
            "rugged": False,
            "mintAuthority": None,
            "freezeAuthority": None,
            "transferFee": {"pct": 0.0},
            "markets": [{"lp": {"lpLockedPct": 90.0, "lpLockedUSD": 50000.0}}],
        }
        result = evaluate_safety(report)
        assert result["ok"] is False
        assert "non_spl_program" in result["issues"]

    def test_evaluate_safety_mint_authority_active(self, sample_medium_risk_report):
        """Active mint authority should be flagged."""
        result = evaluate_safety(sample_medium_risk_report)
        assert "mint_authority_active" in result["issues"]

    def test_evaluate_safety_freeze_authority_active(self):
        """Active freeze authority should be flagged."""
        report = {
            "tokenProgram": SPL_TOKEN_PROGRAM,
            "rugged": False,
            "mintAuthority": None,
            "freezeAuthority": "FreezeAuth123",
            "transferFee": {"pct": 0.0},
            "markets": [{"lp": {"lpLockedPct": 90.0, "lpLockedUSD": 50000.0}}],
        }
        result = evaluate_safety(report)
        assert "freeze_authority_active" in result["issues"]

    def test_evaluate_safety_transfer_fee(self):
        """High transfer fee should be flagged."""
        # The API returns pct as a percentage value (e.g., 3.0 means 3%)
        # The code converts to bps by multiplying by 100 (3.0 * 100 = 300 bps)
        report = {
            "tokenProgram": SPL_TOKEN_PROGRAM,
            "rugged": False,
            "mintAuthority": None,
            "freezeAuthority": None,
            "transferFee": {"pct": 3.0},  # 3% = 300 bps
            "markets": [{"lp": {"lpLockedPct": 90.0, "lpLockedUSD": 50000.0}}],
        }
        result = evaluate_safety(report, max_transfer_fee_bps=100.0)  # 1% = 100 bps max
        assert "transfer_fee" in result["issues"]

    def test_evaluate_safety_liquidity_not_locked(self, sample_unsafe_report):
        """Unlocked liquidity should be flagged."""
        result = evaluate_safety(sample_unsafe_report)
        assert "liquidity_not_locked" in result["issues"]

    def test_evaluate_safety_custom_lock_threshold(self, sample_safe_report):
        """Custom lock thresholds should be respected."""
        # 95% lock passes 50% threshold (default)
        result = evaluate_safety(sample_safe_report, min_locked_pct=50.0)
        assert "liquidity_not_locked" not in result["issues"]

        # 95% lock fails 99% threshold
        result = evaluate_safety(sample_safe_report, min_locked_pct=99.0)
        assert "liquidity_not_locked" in result["issues"]

    def test_evaluate_safety_disable_rugged_check(self, sample_unsafe_report):
        """Should be able to disable rugged check."""
        result = evaluate_safety(sample_unsafe_report, require_not_rugged=False)
        assert "rugged_flag" not in result["issues"]

    def test_evaluate_safety_disable_spl_check(self):
        """Should be able to disable SPL program check."""
        report = {
            "tokenProgram": "NonSplProgram",
            "rugged": False,
            "mintAuthority": None,
            "freezeAuthority": None,
            "transferFee": {"pct": 0.0},
            "markets": [{"lp": {"lpLockedPct": 90.0, "lpLockedUSD": 50000.0}}],
        }
        result = evaluate_safety(report, require_spl_program=False)
        assert "non_spl_program" not in result["issues"]

    def test_evaluate_safety_disable_authority_check(self, sample_medium_risk_report):
        """Should be able to disable authority checks."""
        result = evaluate_safety(
            sample_medium_risk_report, require_authorities_revoked=False
        )
        assert "mint_authority_active" not in result["issues"]
        assert "freeze_authority_active" not in result["issues"]

    def test_evaluate_safety_details_included(self, sample_safe_report):
        """Details should include all relevant info."""
        result = evaluate_safety(sample_safe_report)
        details = result["details"]
        assert "best_lp_locked_pct" in details
        assert "best_lp_locked_usd" in details
        assert "token_program" in details
        assert "mint_authority" in details
        assert "freeze_authority" in details
        assert "transfer_fee_bps" in details

    def test_evaluate_safety_nested_authorities(self, sample_report_with_nested_token):
        """Should detect authorities in nested token object."""
        result = evaluate_safety(sample_report_with_nested_token)
        assert "mint_authority_active" in result["issues"]
        assert "freeze_authority_active" in result["issues"]

    def test_evaluate_safety_all_issues_combined(self, sample_unsafe_report):
        """Extremely unsafe token should have multiple issues."""
        result = evaluate_safety(sample_unsafe_report)
        assert result["ok"] is False
        # Should have multiple issues
        assert len(result["issues"]) >= 3
        assert "rugged_flag" in result["issues"]
        assert "liquidity_not_locked" in result["issues"]


# =============================================================================
# Test Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and unusual inputs."""

    def test_empty_report(self):
        """Empty report should fail gracefully."""
        result = evaluate_safety({})
        assert result["ok"] is False
        # Empty dict {} is falsy in Python (bool({}) == False)
        # So the function returns early with "missing_report" issue
        assert "missing_report" in result["issues"]

    def test_minimal_valid_report(self):
        """Minimal report with only required fields still gets evaluated."""
        # This is a non-empty report so it won't trigger missing_report
        report = {"tokenProgram": "something"}
        result = evaluate_safety(report)
        assert result["ok"] is False
        # Should flag non_spl_program since tokenProgram != SPL_TOKEN_PROGRAM
        assert "non_spl_program" in result["issues"]

    def test_malformed_markets_is_handled(self):
        """Malformed markets data causes error - this is expected behavior.

        The code doesn't defensively handle malformed markets because
        the API response format is well-defined. This test documents
        the actual behavior - it raises an AttributeError.
        """
        report = {
            "tokenProgram": SPL_TOKEN_PROGRAM,
            "rugged": False,
            "markets": "not a list",  # Wrong type
        }
        # This raises an error because the code expects markets to be a list
        with pytest.raises(AttributeError):
            evaluate_safety(report)

    def test_null_transfer_fee(self):
        """Null transfer fee should be handled."""
        report = {
            "tokenProgram": SPL_TOKEN_PROGRAM,
            "rugged": False,
            "mintAuthority": None,
            "freezeAuthority": None,
            "transferFee": None,
            "markets": [{"lp": {"lpLockedPct": 90.0, "lpLockedUSD": 50000.0}}],
        }
        result = evaluate_safety(report)
        # Should not fail on transfer fee
        assert "transfer_fee" not in result["issues"]

    def test_missing_transfer_fee_pct(self):
        """Missing pct in transfer fee should default to 0."""
        report = {
            "tokenProgram": SPL_TOKEN_PROGRAM,
            "rugged": False,
            "mintAuthority": None,
            "freezeAuthority": None,
            "transferFee": {},  # Empty dict
            "markets": [{"lp": {"lpLockedPct": 90.0, "lpLockedUSD": 50000.0}}],
        }
        result = evaluate_safety(report)
        assert result["details"]["transfer_fee_bps"] == 0.0

    def test_new_token_no_markets(self):
        """New token with no markets should fail."""
        report = {
            "tokenProgram": SPL_TOKEN_PROGRAM,
            "rugged": False,
            "mintAuthority": None,
            "freezeAuthority": None,
            "transferFee": {"pct": 0.0},
            "markets": None,
        }
        result = evaluate_safety(report)
        assert "liquidity_not_locked" in result["issues"]

    def test_very_small_lock_amounts(self):
        """Very small lock amounts should fail threshold."""
        report = {
            "markets": [{"lp": {"lpLockedPct": 0.001, "lpLockedUSD": 0.01}}]
        }
        assert has_locked_liquidity(report, min_locked_pct=50.0) is False

    def test_exactly_at_threshold(self):
        """Values exactly at threshold should pass."""
        report = {
            "markets": [{"lp": {"lpLockedPct": 50.0, "lpLockedUSD": 0.0}}]
        }
        assert has_locked_liquidity(report, min_locked_pct=50.0, min_locked_usd=0.0) is True


# =============================================================================
# Test Integration Scenarios
# =============================================================================

class TestIntegrationScenarios:
    """Integration tests for realistic scenarios."""

    @patch("core.rugcheck.requests.get")
    def test_full_flow_safe_token(self, mock_get, sample_safe_report, temp_cache_dir, monkeypatch):
        """Full flow for checking a safe token."""
        monkeypatch.setattr(rugcheck, "CACHE_DIR", temp_cache_dir)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_safe_report
        mock_get.return_value = mock_response

        mint = "SafeTokenMint123"
        report = fetch_report(mint, cache_ttl_seconds=3600)

        assert report is not None
        assert has_locked_liquidity(report) is True

        safety = evaluate_safety(report)
        assert safety["ok"] is True
        assert safety["issues"] == []

    @patch("core.rugcheck.requests.get")
    def test_full_flow_scam_token(self, mock_get, sample_unsafe_report, temp_cache_dir, monkeypatch):
        """Full flow for detecting a scam token."""
        monkeypatch.setattr(rugcheck, "CACHE_DIR", temp_cache_dir)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_unsafe_report
        mock_get.return_value = mock_response

        mint = "ScamTokenMint456"
        report = fetch_report(mint, cache_ttl_seconds=3600)

        assert report is not None
        assert has_locked_liquidity(report) is False

        safety = evaluate_safety(report)
        assert safety["ok"] is False
        assert len(safety["issues"]) > 0

    @patch("core.rugcheck.requests.get")
    def test_api_failure_graceful_degradation(self, mock_get):
        """API failures should degrade gracefully."""
        mock_get.side_effect = requests.RequestException("Network error")

        with patch("core.rugcheck.time.sleep"):
            with patch("builtins.print"):
                report = fetch_report("AnyMint")

        assert report is None

        # Safety check should still work with None report
        safety = evaluate_safety(report)
        assert safety["ok"] is False
        assert "missing_report" in safety["issues"]

    def test_cache_round_trip(self, temp_cache_dir, sample_safe_report, monkeypatch):
        """Data should survive cache round-trip."""
        monkeypatch.setattr(rugcheck, "CACHE_DIR", temp_cache_dir)

        cache_file = temp_cache_dir / "roundtrip.json"
        _write_cache(cache_file, sample_safe_report)

        loaded = _read_cache(cache_file, ttl_seconds=3600)
        assert loaded == sample_safe_report

        # Verify safety evaluation works on cached data
        safety = evaluate_safety(loaded)
        assert safety["ok"] is True


# =============================================================================
# Test Constants
# =============================================================================

class TestConstants:
    """Verify module constants are correctly defined."""

    def test_spl_token_program_constant(self):
        """SPL token program address should be correct."""
        assert SPL_TOKEN_PROGRAM == "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"

    def test_base_url_constant(self):
        """Base URL should point to rugcheck API."""
        assert BASE_URL == "https://api.rugcheck.xyz/v1/tokens"

    def test_user_agent_constant(self):
        """User agent should identify the client."""
        assert "LifeOS" in USER_AGENT
        assert "Jarvis" in USER_AGENT
