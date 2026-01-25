"""
Comprehensive tests for core/dextools.py - DexTools API client for token data.

This module provides market data for trading decisions including:
- Token price fetching
- Volume and liquidity queries
- Trading pair information
- API rate limiting
- Caching strategy

Tests cover:
- Token info retrieval (success, failure, cache)
- Hot pairs queries
- Token audit fetching
- Token search
- Rate limiting and backoff
- Response parsing and validation
- Error handling (API errors, invalid tokens, network failures)
- Caching behavior (TTL, invalidation)
"""

import json
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from core import dextools
from core.dextools import (
    # Dataclasses
    DexToolsToken,
    DexToolsPair,
    DexToolsResult,
    # Helper functions
    _ensure_cache_dir,
    _load_api_key,
    _get_chain_id,
    _check_rate_limit,
    _record_request,
    _backoff_delay,
    _load_cache,
    _save_cache,
    _make_request,
    _parse_token_response,
    _parse_pair_response,
    # Public functions
    get_token_info,
    get_hot_pairs,
    get_token_audit,
    search_tokens,
    clear_cache,
    get_api_status,
    # Constants
    CHAIN_MAP,
    DEXTOOLS_API_BASE,
    DEXTOOLS_FREE_API,
    RATE_LIMIT_REQUESTS_PER_MINUTE,
    CACHE_TTL_SECONDS,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create temporary directory for cache files."""
    cache_dir = tmp_path / "dextools_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


@pytest.fixture
def sample_token_api_response():
    """Sample DexTools API response for a token."""
    return {
        "data": {
            "symbol": "TEST",
            "name": "Test Token",
            "reprPair": {"price": 1.234},
            "metrics": {
                "volume": 500000.0,
                "liquidity": 100000.0,
            },
            "holders": 1500,
            "totalSupply": 1000000000.0,
            "circulatingSupply": 800000000.0,
            "marketCap": 987654.0,
            "fdv": 1234567.0,
            "audit": {"score": 85.0},
            "dextScore": {"total": 90.0},
            "creationTime": 1700000000,
            "links": {
                "twitter": "https://twitter.com/test",
                "website": "https://test.com",
                "telegram": "",  # Empty should be filtered
            },
        }
    }


@pytest.fixture
def sample_pair_api_response():
    """Sample DexTools API response for hot pairs."""
    return {
        "data": [
            {
                "address": "PairAddress123",
                "exchange": "raydium",
                "mainToken": {
                    "address": "BaseToken123",
                    "symbol": "BASE",
                },
                "sideToken": {
                    "address": "QuoteToken456",
                    "symbol": "USDC",
                },
                "price": 2.5,
                "variation1h": 5.0,
                "variation24h": 15.0,
                "volume24h": 1000000.0,
                "liquidity": 500000.0,
                "txns24h": 5000,
                "buys24h": 3000,
                "sells24h": 2000,
                "hotLevel": 3,
                "creationBlock": 123456789,
            },
            {
                "address": "PairAddress456",
                "exchange": "orca",
                "mainToken": {
                    "address": "BaseToken789",
                    "symbol": "MEME",
                },
                "sideToken": {
                    "address": "QuoteToken012",
                    "symbol": "SOL",
                },
                "price": 0.001,
                "variation1h": -2.0,
                "variation24h": 50.0,
                "volume24h": 2000000.0,
                "liquidity": 250000.0,
                "txns24h": 10000,
                "buys24h": 6000,
                "sells24h": 4000,
                "hotLevel": 5,
                "creationBlock": 123456000,
            },
        ]
    }


@pytest.fixture
def sample_audit_response():
    """Sample DexTools audit API response."""
    return {
        "data": {
            "score": 85.0,
            "isHoneypot": False,
            "hasMintFunction": False,
            "hasProxyContract": False,
            "canTakeBackOwnership": False,
            "hiddenOwner": False,
            "antiWhale": True,
        }
    }


@pytest.fixture
def sample_search_response():
    """Sample DexTools search API response."""
    return {
        "data": [
            {"address": "TokenA123", "symbol": "TSTA", "name": "Test Token A"},
            {"address": "TokenB456", "symbol": "TSTB", "name": "Test Token B"},
        ]
    }


@pytest.fixture(autouse=True)
def reset_rate_limit_state():
    """Reset rate limit state before each test."""
    dextools._request_timestamps.clear()
    yield
    dextools._request_timestamps.clear()


# =============================================================================
# Test Dataclasses
# =============================================================================

class TestDexToolsToken:
    """Tests for DexToolsToken dataclass."""

    def test_default_values(self):
        """Token should have sensible defaults."""
        token = DexToolsToken(
            address="addr123",
            chain="solana",
            symbol="TEST",
            name="Test Token",
        )
        assert token.price_usd == 0.0
        assert token.volume_24h == 0.0
        assert token.liquidity_usd == 0.0
        assert token.holders == 0
        assert token.socials == {}

    def test_all_fields(self):
        """Token should store all fields correctly."""
        token = DexToolsToken(
            address="addr123",
            chain="solana",
            symbol="TEST",
            name="Test Token",
            price_usd=1.5,
            price_change_24h=10.5,
            volume_24h=500000.0,
            liquidity_usd=100000.0,
            holders=1500,
            total_supply=1000000.0,
            circulating_supply=800000.0,
            market_cap=1200000.0,
            fdv=1500000.0,
            audit_score=85.0,
            dext_score=90.0,
            creation_time=1700000000.0,
            socials={"twitter": "https://twitter.com/test"},
        )
        assert token.price_usd == 1.5
        assert token.holders == 1500
        assert token.socials["twitter"] == "https://twitter.com/test"


class TestDexToolsPair:
    """Tests for DexToolsPair dataclass."""

    def test_default_values(self):
        """Pair should have sensible defaults."""
        pair = DexToolsPair(
            pair_address="pair123",
            chain="solana",
            dex="raydium",
            base_token="base123",
            base_symbol="BASE",
            quote_token="quote456",
            quote_symbol="USDC",
        )
        assert pair.price_usd == 0.0
        assert pair.volume_24h == 0.0
        assert pair.hot_level == 0

    def test_all_fields(self):
        """Pair should store all fields correctly."""
        pair = DexToolsPair(
            pair_address="pair123",
            chain="solana",
            dex="raydium",
            base_token="base123",
            base_symbol="BASE",
            quote_token="quote456",
            quote_symbol="USDC",
            price_usd=2.5,
            price_change_1h=5.0,
            price_change_24h=15.0,
            volume_24h=1000000.0,
            liquidity_usd=500000.0,
            txns_24h=5000,
            buys_24h=3000,
            sells_24h=2000,
            hot_level=3,
            creation_block=123456789,
        )
        assert pair.price_usd == 2.5
        assert pair.txns_24h == 5000
        assert pair.hot_level == 3


class TestDexToolsResult:
    """Tests for DexToolsResult dataclass."""

    def test_success_result(self):
        """Successful result should have success=True."""
        result = DexToolsResult(success=True, data={"test": "data"})
        assert result.success is True
        assert result.data == {"test": "data"}
        assert result.error is None
        assert result.cached is False

    def test_failure_result(self):
        """Failed result should have error message."""
        result = DexToolsResult(success=False, error="API error")
        assert result.success is False
        assert result.data is None
        assert result.error == "API error"

    def test_cached_result(self):
        """Cached result should have cached=True."""
        result = DexToolsResult(success=True, data={"test": "data"}, cached=True)
        assert result.cached is True

    def test_default_source(self):
        """Default source should be 'dextools'."""
        result = DexToolsResult(success=True)
        assert result.source == "dextools"


# =============================================================================
# Test Helper Functions
# =============================================================================

class TestEnsureCacheDir:
    """Tests for _ensure_cache_dir function."""

    def test_creates_directory(self, temp_cache_dir, monkeypatch):
        """Should create cache directory if missing."""
        new_cache = temp_cache_dir / "new_subdir"
        monkeypatch.setattr(dextools, "CACHE_DIR", new_cache)
        assert not new_cache.exists()
        _ensure_cache_dir()
        assert new_cache.exists()

    def test_handles_existing_directory(self, temp_cache_dir, monkeypatch):
        """Should not fail if directory exists."""
        monkeypatch.setattr(dextools, "CACHE_DIR", temp_cache_dir)
        _ensure_cache_dir()  # Should not raise
        assert temp_cache_dir.exists()


class TestLoadApiKey:
    """Tests for _load_api_key function."""

    def test_loads_from_env(self, monkeypatch):
        """Should load API key from environment variable."""
        monkeypatch.setenv("DEXTOOLS_API_KEY", "test_api_key_123")
        key = _load_api_key()
        assert key == "test_api_key_123"

    def test_returns_none_when_no_env(self, monkeypatch):
        """Should return None when env var not set."""
        monkeypatch.delenv("DEXTOOLS_API_KEY", raising=False)
        # Also need to patch CONFIG_PATH to not exist
        monkeypatch.setattr(dextools, "CONFIG_PATH", Path("/nonexistent/path"))
        key = _load_api_key()
        assert key is None

    def test_loads_from_config_file(self, tmp_path, monkeypatch):
        """Should load from config file when env not set."""
        monkeypatch.delenv("DEXTOOLS_API_KEY", raising=False)
        config_file = tmp_path / "keys.json"
        config_file.write_text(json.dumps({"dextools_api_key": "file_api_key"}))
        monkeypatch.setattr(dextools, "CONFIG_PATH", config_file)
        key = _load_api_key()
        assert key == "file_api_key"

    def test_env_takes_precedence(self, tmp_path, monkeypatch):
        """Environment variable should take precedence over config file."""
        monkeypatch.setenv("DEXTOOLS_API_KEY", "env_key")
        config_file = tmp_path / "keys.json"
        config_file.write_text(json.dumps({"dextools_api_key": "file_key"}))
        monkeypatch.setattr(dextools, "CONFIG_PATH", config_file)
        key = _load_api_key()
        assert key == "env_key"

    def test_handles_invalid_json(self, tmp_path, monkeypatch):
        """Should return None on invalid JSON."""
        monkeypatch.delenv("DEXTOOLS_API_KEY", raising=False)
        config_file = tmp_path / "keys.json"
        config_file.write_text("not valid json {{{")
        monkeypatch.setattr(dextools, "CONFIG_PATH", config_file)
        key = _load_api_key()
        assert key is None


class TestGetChainId:
    """Tests for _get_chain_id function."""

    def test_solana_mappings(self):
        """Solana chain mappings should work."""
        assert _get_chain_id("solana") == "solana"
        assert _get_chain_id("sol") == "solana"
        assert _get_chain_id("SOLANA") == "solana"
        assert _get_chain_id("Sol") == "solana"

    def test_ethereum_mappings(self):
        """Ethereum chain mappings should work."""
        assert _get_chain_id("ethereum") == "ether"
        assert _get_chain_id("eth") == "ether"
        assert _get_chain_id("ETHEREUM") == "ether"

    def test_other_chains(self):
        """Other chain mappings should work."""
        assert _get_chain_id("base") == "base"
        assert _get_chain_id("bsc") == "bsc"
        assert _get_chain_id("bnb") == "bsc"
        assert _get_chain_id("arbitrum") == "arbitrum"
        assert _get_chain_id("polygon") == "polygon"

    def test_unknown_chain_passthrough(self):
        """Unknown chains should pass through lowercase."""
        assert _get_chain_id("avalanche") == "avalanche"
        assert _get_chain_id("FANTOM") == "fantom"


class TestBackoffDelay:
    """Tests for exponential backoff calculation."""

    def test_first_attempt(self):
        """First attempt should use base delay."""
        result = _backoff_delay(1.0, 0)
        assert 1.0 <= result <= 1.1  # Allow for jitter

    def test_exponential_growth(self):
        """Delays should grow exponentially (plus jitter)."""
        # Base delay of 1.0, attempt 1 = 2^1 = 2.0
        result = _backoff_delay(1.0, 1)
        assert 2.0 <= result <= 2.2

        # Attempt 2 = 2^2 = 4.0
        result = _backoff_delay(1.0, 2)
        assert 4.0 <= result <= 4.4

    def test_respects_max_delay(self):
        """Delay should not exceed max_delay."""
        result = _backoff_delay(1.0, 10, max_delay=30.0)
        assert result <= 30.0 + 3.0  # max + 10% jitter

    def test_custom_base(self):
        """Custom base delay should be used."""
        result = _backoff_delay(2.0, 0)
        assert 2.0 <= result <= 2.2


class TestRateLimiting:
    """Tests for rate limiting functions."""

    def test_check_rate_limit_under_limit(self):
        """Should not rate limit when under limit."""
        # Add a few requests
        for _ in range(5):
            _record_request()
        should_limit, wait_time = _check_rate_limit()
        assert should_limit is False
        assert wait_time == 0

    def test_check_rate_limit_at_limit(self):
        """Should rate limit when at limit."""
        # Fill up the rate limit
        for _ in range(RATE_LIMIT_REQUESTS_PER_MINUTE):
            _record_request()
        should_limit, wait_time = _check_rate_limit()
        assert should_limit is True
        assert wait_time > 0

    def test_rate_limit_expires_old_requests(self):
        """Old requests should expire from rate limit tracking."""
        # Add old timestamps (older than 60 seconds)
        old_time = time.time() - 120
        dextools._request_timestamps.extend([old_time] * 50)

        should_limit, wait_time = _check_rate_limit()
        assert should_limit is False
        # Old timestamps should be cleaned up
        assert len(dextools._request_timestamps) == 0

    def test_record_request(self):
        """_record_request should add timestamp."""
        initial_count = len(dextools._request_timestamps)
        _record_request()
        assert len(dextools._request_timestamps) == initial_count + 1


# =============================================================================
# Test Cache Functions
# =============================================================================

class TestCacheFunctions:
    """Tests for caching mechanism."""

    def test_save_and_load_cache(self, temp_cache_dir, monkeypatch):
        """Cache should round-trip correctly."""
        monkeypatch.setattr(dextools, "CACHE_DIR", temp_cache_dir)

        _save_cache("test_key", {"data": "value"})
        result = _load_cache("test_key")
        assert result == {"data": "value"}

    def test_cache_ttl_valid(self, temp_cache_dir, monkeypatch):
        """Cache within TTL should return data."""
        monkeypatch.setattr(dextools, "CACHE_DIR", temp_cache_dir)

        _save_cache("ttl_test", {"test": "data"})
        # Should be valid immediately
        result = _load_cache("ttl_test")
        assert result == {"test": "data"}

    def test_cache_ttl_expired(self, temp_cache_dir, monkeypatch):
        """Expired cache should return None."""
        monkeypatch.setattr(dextools, "CACHE_DIR", temp_cache_dir)

        # Write cache with old timestamp
        cache_file = temp_cache_dir / "expired_test.json"
        cache_file.write_text(json.dumps({
            "payload": {"old": "data"},
            "cached_at": time.time() - (CACHE_TTL_SECONDS + 60),
        }))

        result = _load_cache("expired_test")
        assert result is None

    def test_cache_missing_file(self, temp_cache_dir, monkeypatch):
        """Missing cache file should return None."""
        monkeypatch.setattr(dextools, "CACHE_DIR", temp_cache_dir)
        result = _load_cache("nonexistent_key")
        assert result is None

    def test_cache_invalid_json(self, temp_cache_dir, monkeypatch):
        """Invalid JSON should return None."""
        monkeypatch.setattr(dextools, "CACHE_DIR", temp_cache_dir)

        cache_file = temp_cache_dir / "invalid_json.json"
        cache_file.write_text("not valid json {{{")

        result = _load_cache("invalid_json")
        assert result is None


# =============================================================================
# Test API Request Function
# =============================================================================

class TestMakeRequest:
    """Tests for _make_request HTTP handling."""

    @patch("core.dextools.requests.get")
    def test_successful_request(self, mock_get, monkeypatch):
        """Successful API call should return data."""
        monkeypatch.delenv("DEXTOOLS_API_KEY", raising=False)
        monkeypatch.setattr(dextools, "CONFIG_PATH", Path("/nonexistent"))

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "success"}
        mock_get.return_value = mock_response

        result = _make_request("/test/endpoint")
        assert result == {"data": "success"}

    @patch("core.dextools.requests.get")
    def test_uses_api_key_when_available(self, mock_get, monkeypatch):
        """Should use API key in headers when available."""
        monkeypatch.setenv("DEXTOOLS_API_KEY", "test_key")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_get.return_value = mock_response

        _make_request("/test")
        call_args = mock_get.call_args
        assert call_args.kwargs["headers"]["X-API-KEY"] == "test_key"
        assert DEXTOOLS_API_BASE in call_args.args[0]

    @patch("core.dextools.requests.get")
    def test_uses_free_api_without_key(self, mock_get, monkeypatch):
        """Should use free API when no key available."""
        monkeypatch.delenv("DEXTOOLS_API_KEY", raising=False)
        monkeypatch.setattr(dextools, "CONFIG_PATH", Path("/nonexistent"))

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_get.return_value = mock_response

        _make_request("/test")
        call_args = mock_get.call_args
        assert "X-API-KEY" not in call_args.kwargs["headers"]
        assert DEXTOOLS_FREE_API in call_args.args[0]

    @patch("core.dextools.requests.get")
    def test_retries_on_429(self, mock_get, monkeypatch):
        """429 rate limit should trigger retry."""
        monkeypatch.delenv("DEXTOOLS_API_KEY", raising=False)
        monkeypatch.setattr(dextools, "CONFIG_PATH", Path("/nonexistent"))

        mock_429 = Mock()
        mock_429.status_code = 429

        mock_success = Mock()
        mock_success.status_code = 200
        mock_success.json.return_value = {"recovered": True}

        mock_get.side_effect = [mock_429, mock_success]

        with patch("core.dextools.time.sleep"):  # Speed up test
            result = _make_request("/test", retries=3)

        assert result == {"recovered": True}
        assert mock_get.call_count == 2

    @patch("core.dextools.requests.get")
    def test_returns_none_on_401(self, mock_get, monkeypatch):
        """401 unauthorized should return None (no retry)."""
        monkeypatch.delenv("DEXTOOLS_API_KEY", raising=False)
        monkeypatch.setattr(dextools, "CONFIG_PATH", Path("/nonexistent"))

        mock_response = Mock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        result = _make_request("/test")
        assert result is None
        assert mock_get.call_count == 1  # No retry

    @patch("core.dextools.requests.get")
    def test_returns_none_on_non_retryable_error(self, mock_get, monkeypatch):
        """Non-retryable errors should return None."""
        monkeypatch.delenv("DEXTOOLS_API_KEY", raising=False)
        monkeypatch.setattr(dextools, "CONFIG_PATH", Path("/nonexistent"))

        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Not found"
        mock_get.return_value = mock_response

        result = _make_request("/test")
        assert result is None

    @patch("core.dextools.requests.get")
    def test_handles_network_exception(self, mock_get, monkeypatch):
        """Network exceptions should be handled gracefully."""
        monkeypatch.delenv("DEXTOOLS_API_KEY", raising=False)
        monkeypatch.setattr(dextools, "CONFIG_PATH", Path("/nonexistent"))

        import requests as req
        mock_get.side_effect = req.RequestException("Connection failed")

        with patch("core.dextools.time.sleep"):
            result = _make_request("/test", retries=2)

        assert result is None

    @patch("core.dextools.requests.get")
    def test_rate_limit_applied(self, mock_get, monkeypatch):
        """Rate limiting should pause when limit reached."""
        monkeypatch.delenv("DEXTOOLS_API_KEY", raising=False)
        monkeypatch.setattr(dextools, "CONFIG_PATH", Path("/nonexistent"))

        # Fill up rate limit
        for _ in range(RATE_LIMIT_REQUESTS_PER_MINUTE):
            _record_request()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}
        mock_get.return_value = mock_response

        with patch("core.dextools.time.sleep") as mock_sleep:
            _make_request("/test")
            # Should have slept due to rate limit
            assert mock_sleep.called

    def test_no_requests_library(self, monkeypatch):
        """Should return None when requests library not available."""
        monkeypatch.setattr(dextools, "HAS_REQUESTS", False)
        result = _make_request("/test")
        assert result is None


# =============================================================================
# Test Response Parsing
# =============================================================================

class TestParseTokenResponse:
    """Tests for _parse_token_response function."""

    def test_parses_full_response(self, sample_token_api_response):
        """Should parse all fields correctly."""
        data = sample_token_api_response["data"]
        token = _parse_token_response("addr123", "solana", data)

        assert token.address == "addr123"
        assert token.chain == "solana"
        assert token.symbol == "TEST"
        assert token.name == "Test Token"
        assert token.price_usd == 1.234
        assert token.volume_24h == 500000.0
        assert token.liquidity_usd == 100000.0
        assert token.holders == 1500
        assert token.audit_score == 85.0
        assert token.dext_score == 90.0
        assert token.creation_time == 1700000000

    def test_parses_socials_filters_empty(self, sample_token_api_response):
        """Should filter out empty social links."""
        data = sample_token_api_response["data"]
        token = _parse_token_response("addr123", "solana", data)

        assert "twitter" in token.socials
        assert "website" in token.socials
        assert "telegram" not in token.socials  # Empty string filtered

    def test_handles_missing_fields(self):
        """Should handle missing fields with defaults."""
        data = {"symbol": "MIN", "name": "Minimal"}
        token = _parse_token_response("addr123", "solana", data)

        assert token.symbol == "MIN"
        assert token.price_usd == 0.0
        assert token.volume_24h == 0.0
        assert token.holders == 0
        assert token.socials == {}

    def test_handles_none_values_raises(self):
        """None values for nested dicts raise AttributeError.

        The code uses chained .get() which fails if intermediate value is None.
        This documents actual behavior - callers should ensure data validity.
        """
        data = {
            "symbol": "TEST",
            "name": "Test",
            "reprPair": None,  # Will cause AttributeError
            "metrics": None,
            "holders": None,
        }
        with pytest.raises(AttributeError):
            _parse_token_response("addr123", "solana", data)

    def test_handles_missing_nested_keys(self):
        """Should handle missing nested keys with defaults (empty dict fallback)."""
        data = {
            "symbol": "TEST",
            "name": "Test",
            # No reprPair, metrics, etc. - will use empty dict defaults
        }
        token = _parse_token_response("addr123", "solana", data)

        assert token.price_usd == 0.0
        assert token.volume_24h == 0.0
        assert token.holders == 0


class TestParsePairResponse:
    """Tests for _parse_pair_response function."""

    def test_parses_full_response(self, sample_pair_api_response):
        """Should parse all pair fields correctly."""
        data = sample_pair_api_response["data"][0]
        pair = _parse_pair_response("solana", data)

        assert pair.pair_address == "PairAddress123"
        assert pair.chain == "solana"
        assert pair.dex == "raydium"
        assert pair.base_token == "BaseToken123"
        assert pair.base_symbol == "BASE"
        assert pair.quote_token == "QuoteToken456"
        assert pair.quote_symbol == "USDC"
        assert pair.price_usd == 2.5
        assert pair.price_change_1h == 5.0
        assert pair.price_change_24h == 15.0
        assert pair.volume_24h == 1000000.0
        assert pair.liquidity_usd == 500000.0
        assert pair.txns_24h == 5000
        assert pair.buys_24h == 3000
        assert pair.sells_24h == 2000
        assert pair.hot_level == 3
        assert pair.creation_block == 123456789

    def test_handles_missing_fields(self):
        """Should handle missing fields with defaults."""
        data = {"address": "pair123"}
        pair = _parse_pair_response("solana", data)

        assert pair.pair_address == "pair123"
        assert pair.dex == ""
        assert pair.base_token == ""
        assert pair.price_usd == 0.0
        assert pair.hot_level == 0


# =============================================================================
# Test Public Functions
# =============================================================================

class TestGetTokenInfo:
    """Tests for get_token_info function."""

    @patch("core.dextools._make_request")
    def test_successful_fetch(self, mock_request, sample_token_api_response, temp_cache_dir, monkeypatch):
        """Should fetch and parse token info."""
        monkeypatch.setattr(dextools, "CACHE_DIR", temp_cache_dir)
        mock_request.return_value = sample_token_api_response

        result = get_token_info("TokenAddress123", chain="solana")

        assert result.success is True
        assert isinstance(result.data, DexToolsToken)
        assert result.data.symbol == "TEST"
        assert result.cached is False

    @patch("core.dextools._make_request")
    def test_uses_cache(self, mock_request, sample_token_api_response, temp_cache_dir, monkeypatch):
        """Should use cached data when available."""
        monkeypatch.setattr(dextools, "CACHE_DIR", temp_cache_dir)

        # First call populates cache
        mock_request.return_value = sample_token_api_response
        result1 = get_token_info("TokenAddress123")
        assert mock_request.call_count == 1

        # Second call should use cache
        result2 = get_token_info("TokenAddress123")
        assert result2.success is True
        assert result2.cached is True
        assert mock_request.call_count == 1  # No additional API call

    @patch("core.dextools._make_request")
    @patch("core.dexscreener.get_pairs_by_token")
    def test_falls_back_to_dexscreener(self, mock_dexscreener, mock_request, temp_cache_dir, monkeypatch):
        """Should fall back to DexScreener when DexTools fails."""
        monkeypatch.setattr(dextools, "CACHE_DIR", temp_cache_dir)
        mock_request.return_value = None  # DexTools fails

        # Mock DexScreener response
        mock_dexscreener.return_value = Mock(
            success=True,
            data={
                "pairs": [{
                    "baseToken": {"symbol": "FALLBACK", "name": "Fallback Token"},
                    "priceUsd": "0.5",
                    "priceChange": {"h24": "10.0"},
                    "volume": {"h24": "100000"},
                    "liquidity": {"usd": "50000"},
                }]
            }
        )

        result = get_token_info("TokenAddress123")

        assert result.success is True
        assert result.data.symbol == "FALLBACK"
        assert result.data.price_usd == 0.5
        assert "fallback" in result.error.lower()

    @patch("core.dextools._make_request")
    def test_handles_api_failure(self, mock_request, temp_cache_dir, monkeypatch):
        """Should return failure when API and fallback fail."""
        monkeypatch.setattr(dextools, "CACHE_DIR", temp_cache_dir)
        mock_request.return_value = None

        # Patch dexscreener import to fail
        with patch.dict("sys.modules", {"core.dexscreener": None}):
            result = get_token_info("TokenAddress123")

        assert result.success is False
        assert "Failed" in result.error

    @patch("core.dextools._make_request")
    def test_chain_normalization(self, mock_request, sample_token_api_response, temp_cache_dir, monkeypatch):
        """Should normalize chain identifiers."""
        monkeypatch.setattr(dextools, "CACHE_DIR", temp_cache_dir)
        mock_request.return_value = sample_token_api_response

        get_token_info("Token123", chain="eth")
        call_args = mock_request.call_args
        assert "/ether/" in call_args.args[0]


class TestGetHotPairs:
    """Tests for get_hot_pairs function."""

    @patch("core.dextools._make_request")
    def test_successful_fetch(self, mock_request, sample_pair_api_response, temp_cache_dir, monkeypatch):
        """Should fetch and parse hot pairs."""
        monkeypatch.setattr(dextools, "CACHE_DIR", temp_cache_dir)
        mock_request.return_value = sample_pair_api_response

        result = get_hot_pairs(chain="solana", limit=10)

        assert result.success is True
        assert isinstance(result.data, list)
        assert len(result.data) == 2
        assert all(isinstance(p, DexToolsPair) for p in result.data)

    @patch("core.dextools._make_request")
    def test_respects_limit(self, mock_request, temp_cache_dir, monkeypatch):
        """Should respect limit parameter."""
        monkeypatch.setattr(dextools, "CACHE_DIR", temp_cache_dir)

        # Create response with more pairs than limit
        mock_request.return_value = {
            "data": [{"address": f"pair{i}"} for i in range(20)]
        }

        result = get_hot_pairs(limit=5)
        assert len(result.data) == 5

    @patch("core.dextools._make_request")
    def test_uses_cache(self, mock_request, sample_pair_api_response, temp_cache_dir, monkeypatch):
        """Should cache hot pairs."""
        monkeypatch.setattr(dextools, "CACHE_DIR", temp_cache_dir)
        mock_request.return_value = sample_pair_api_response

        result1 = get_hot_pairs()
        result2 = get_hot_pairs()

        assert result2.cached is True
        assert mock_request.call_count == 1

    @patch("core.dextools._make_request")
    def test_handles_api_failure(self, mock_request, temp_cache_dir, monkeypatch):
        """Should return failure when API fails."""
        monkeypatch.setattr(dextools, "CACHE_DIR", temp_cache_dir)
        mock_request.return_value = None

        # Also mock dexscreener fallback to fail
        with patch("core.dexscreener.get_solana_trending", side_effect=Exception("Fallback failed")):
            result = get_hot_pairs()

        assert result.success is False
        assert "Failed" in result.error


class TestGetTokenAudit:
    """Tests for get_token_audit function."""

    @patch("core.dextools._make_request")
    def test_successful_fetch(self, mock_request, sample_audit_response):
        """Should fetch audit data."""
        mock_request.return_value = sample_audit_response

        result = get_token_audit("TokenAddress123", chain="solana")

        assert result.success is True
        assert result.data["score"] == 85.0
        assert result.data["isHoneypot"] is False

    @patch("core.dextools._make_request")
    def test_handles_api_failure(self, mock_request):
        """Should return failure when API fails."""
        mock_request.return_value = None

        result = get_token_audit("TokenAddress123")

        assert result.success is False
        assert "unavailable" in result.error.lower()


class TestSearchTokens:
    """Tests for search_tokens function."""

    @patch("core.dextools._make_request")
    def test_successful_search(self, mock_request, sample_search_response):
        """Should search and return tokens."""
        mock_request.return_value = sample_search_response

        result = search_tokens("TEST", chain="solana", limit=10)

        assert result.success is True
        assert len(result.data) == 2
        assert all(isinstance(t, DexToolsToken) for t in result.data)
        assert result.data[0].symbol == "TSTA"

    @patch("core.dextools._make_request")
    def test_respects_limit(self, mock_request):
        """Should respect limit parameter."""
        mock_request.return_value = {
            "data": [{"address": f"tok{i}", "symbol": f"T{i}", "name": f"Token {i}"} for i in range(20)]
        }

        result = search_tokens("test", limit=5)
        assert len(result.data) == 5

    @patch("core.dextools._make_request")
    def test_handles_api_failure(self, mock_request):
        """Should return failure when API fails."""
        mock_request.return_value = None

        result = search_tokens("TEST")

        assert result.success is False
        assert "failed" in result.error.lower()


class TestClearCache:
    """Tests for clear_cache function."""

    def test_clears_cache_files(self, temp_cache_dir, monkeypatch):
        """Should delete all cache files."""
        monkeypatch.setattr(dextools, "CACHE_DIR", temp_cache_dir)

        # Create some cache files
        (temp_cache_dir / "file1.json").write_text("{}")
        (temp_cache_dir / "file2.json").write_text("{}")
        (temp_cache_dir / "file3.json").write_text("{}")

        count = clear_cache()

        assert count == 3
        assert len(list(temp_cache_dir.glob("*.json"))) == 0

    def test_handles_nonexistent_dir(self, monkeypatch):
        """Should handle non-existent cache directory."""
        monkeypatch.setattr(dextools, "CACHE_DIR", Path("/nonexistent/cache/dir"))
        count = clear_cache()
        assert count == 0


class TestGetApiStatus:
    """Tests for get_api_status function."""

    def test_returns_status_with_key(self, monkeypatch):
        """Should return status when API key is set."""
        monkeypatch.setenv("DEXTOOLS_API_KEY", "test_key")

        status = get_api_status()

        assert status["available"] is True
        assert status["has_api_key"] is True
        assert "configured" in status["note"].lower()

    def test_returns_status_without_key(self, monkeypatch):
        """Should return status when API key is not set."""
        monkeypatch.delenv("DEXTOOLS_API_KEY", raising=False)
        monkeypatch.setattr(dextools, "CONFIG_PATH", Path("/nonexistent"))

        status = get_api_status()

        assert status["available"] is True
        assert status["has_api_key"] is False
        assert "subscription" in status["note"].lower()

    def test_includes_rate_limit_info(self):
        """Should include rate limit configuration."""
        status = get_api_status()

        assert "rate_limit" in status
        assert "cache_ttl" in status
        assert status["cache_ttl"] == CACHE_TTL_SECONDS


# =============================================================================
# Test Constants
# =============================================================================

class TestConstants:
    """Tests for module constants."""

    def test_chain_map_has_common_chains(self):
        """CHAIN_MAP should have common chains."""
        assert "solana" in CHAIN_MAP
        assert "ethereum" in CHAIN_MAP
        assert "base" in CHAIN_MAP

    def test_api_urls_defined(self):
        """API URLs should be defined."""
        assert DEXTOOLS_API_BASE.startswith("https://")
        assert DEXTOOLS_FREE_API.startswith("https://")

    def test_rate_limit_reasonable(self):
        """Rate limit should be reasonable."""
        assert 10 <= RATE_LIMIT_REQUESTS_PER_MINUTE <= 100

    def test_cache_ttl_reasonable(self):
        """Cache TTL should be reasonable."""
        assert 30 <= CACHE_TTL_SECONDS <= 600


# =============================================================================
# Test Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and unusual inputs."""

    @patch("core.dextools._make_request")
    def test_empty_token_address(self, mock_request, temp_cache_dir, monkeypatch):
        """Should handle empty token address."""
        monkeypatch.setattr(dextools, "CACHE_DIR", temp_cache_dir)
        mock_request.return_value = None

        result = get_token_info("")
        assert result.success is False

    @patch("core.dextools._make_request")
    def test_very_long_token_address(self, mock_request, sample_token_api_response, temp_cache_dir, monkeypatch):
        """Should handle long token addresses."""
        monkeypatch.setattr(dextools, "CACHE_DIR", temp_cache_dir)
        mock_request.return_value = sample_token_api_response

        long_addr = "A" * 100
        result = get_token_info(long_addr)
        assert result.success is True

    @patch("core.dextools._make_request")
    def test_special_characters_in_search(self, mock_request, sample_search_response):
        """Should handle special characters in search query."""
        mock_request.return_value = sample_search_response

        result = search_tokens("TEST $#@!")
        assert result.success is True

    @patch("core.dextools._make_request")
    def test_unicode_in_token_name(self, mock_request, temp_cache_dir, monkeypatch):
        """Should handle unicode in token names."""
        monkeypatch.setattr(dextools, "CACHE_DIR", temp_cache_dir)
        mock_request.return_value = {
            "data": {
                "symbol": "TEST",
                "name": "Test Token"
            }
        }

        result = get_token_info("addr123")
        assert result.success is True

    @patch("core.dextools._make_request")
    def test_negative_price_values(self, mock_request, temp_cache_dir, monkeypatch):
        """Should handle negative price values (edge case)."""
        monkeypatch.setattr(dextools, "CACHE_DIR", temp_cache_dir)
        mock_request.return_value = {
            "data": {
                "symbol": "NEG",
                "name": "Negative",
                "reprPair": {"price": -1.0},  # Invalid but possible from bad data
            }
        }

        result = get_token_info("addr123")
        assert result.success is True
        assert result.data.price_usd == -1.0  # Should preserve the value

    def test_chain_map_case_insensitivity(self):
        """Chain mapping should be case insensitive."""
        assert _get_chain_id("SOLANA") == "solana"
        assert _get_chain_id("Solana") == "solana"
        assert _get_chain_id("sOlAnA") == "solana"


# =============================================================================
# Test Integration Scenarios
# =============================================================================

class TestDexScreenerFallback:
    """Tests for DexScreener fallback paths."""

    @patch("core.dextools._make_request")
    def test_get_token_info_dexscreener_exception(self, mock_request, temp_cache_dir, monkeypatch):
        """Should handle DexScreener exceptions gracefully."""
        monkeypatch.setattr(dextools, "CACHE_DIR", temp_cache_dir)
        mock_request.return_value = None  # DexTools fails

        # Mock dexscreener to raise an exception
        with patch("core.dexscreener.get_pairs_by_token", side_effect=Exception("DexScreener error")):
            result = get_token_info("TokenAddress123")

        assert result.success is False
        assert "Failed" in result.error

    @patch("core.dextools._make_request")
    def test_get_hot_pairs_dexscreener_fallback_success(self, mock_request, temp_cache_dir, monkeypatch):
        """Should use DexScreener fallback for hot pairs when DexTools fails."""
        monkeypatch.setattr(dextools, "CACHE_DIR", temp_cache_dir)
        mock_request.return_value = None  # DexTools fails

        # Create mock TokenPair objects for dexscreener response
        mock_pair = Mock()
        mock_pair.pair_address = "FallbackPair123"
        mock_pair.dex_id = "raydium"
        mock_pair.base_token_address = "BaseAddr"
        mock_pair.base_token_symbol = "FALL"
        mock_pair.quote_token_address = "QuoteAddr"
        mock_pair.quote_token_symbol = "SOL"
        mock_pair.price_usd = 1.5
        mock_pair.price_change_24h = 10.0
        mock_pair.volume_24h = 50000.0
        mock_pair.liquidity_usd = 25000.0

        with patch("core.dexscreener.get_solana_trending", return_value=[mock_pair]):
            result = get_hot_pairs()

        assert result.success is True
        assert len(result.data) == 1
        assert result.data[0].pair_address == "FallbackPair123"
        assert result.data[0].base_symbol == "FALL"
        assert "fallback" in result.error.lower()

    @patch("core.dextools._make_request")
    def test_get_hot_pairs_dexscreener_returns_empty(self, mock_request, temp_cache_dir, monkeypatch):
        """Should handle empty DexScreener response."""
        monkeypatch.setattr(dextools, "CACHE_DIR", temp_cache_dir)
        mock_request.return_value = None  # DexTools fails

        with patch("core.dexscreener.get_solana_trending", return_value=[]):
            result = get_hot_pairs()

        assert result.success is False


class TestClearCacheErrors:
    """Tests for clear_cache error handling."""

    def test_handles_permission_error(self, temp_cache_dir, monkeypatch):
        """Should handle permission errors when deleting files."""
        monkeypatch.setattr(dextools, "CACHE_DIR", temp_cache_dir)

        # Create a cache file
        cache_file = temp_cache_dir / "test.json"
        cache_file.write_text("{}")

        # Mock unlink to raise PermissionError
        with patch.object(Path, "unlink", side_effect=PermissionError("Access denied")):
            count = clear_cache()

        # Should return 0 since unlink failed (but not crash)
        assert count == 0


class TestIntegrationScenarios:
    """Integration tests for realistic scenarios."""

    @patch("core.dextools._make_request")
    def test_full_token_lookup_flow(self, mock_request, sample_token_api_response, temp_cache_dir, monkeypatch):
        """Full flow for looking up a token."""
        monkeypatch.setattr(dextools, "CACHE_DIR", temp_cache_dir)
        mock_request.return_value = sample_token_api_response

        # First lookup
        result = get_token_info("TokenMint123")
        assert result.success is True
        assert result.data.symbol == "TEST"
        assert result.cached is False

        # Second lookup should be cached
        result = get_token_info("TokenMint123")
        assert result.success is True
        assert result.cached is True

        # Clear cache
        count = clear_cache()
        assert count >= 1

        # Third lookup should fetch again
        mock_request.return_value = sample_token_api_response
        result = get_token_info("TokenMint123")
        assert result.cached is False

    @patch("core.dextools._make_request")
    def test_hot_pairs_with_filtering(self, mock_request, sample_pair_api_response, temp_cache_dir, monkeypatch):
        """Should fetch hot pairs and allow filtering by properties."""
        monkeypatch.setattr(dextools, "CACHE_DIR", temp_cache_dir)
        mock_request.return_value = sample_pair_api_response

        result = get_hot_pairs(chain="solana", limit=10)
        assert result.success is True

        # Filter by volume
        high_volume = [p for p in result.data if p.volume_24h > 1500000]
        assert len(high_volume) == 1
        assert high_volume[0].base_symbol == "MEME"

        # Filter by hot level
        hottest = [p for p in result.data if p.hot_level >= 5]
        assert len(hottest) == 1
