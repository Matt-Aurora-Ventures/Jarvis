"""
Tests for core/jupiter.py - Jupiter DEX API wrapper

This test suite provides comprehensive coverage for the Jupiter API client
including quote fetching, price lookups, caching, retries, and error handling.
"""

import json
import time
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock
import pytest

# Import module under test
from core import jupiter
from core.jupiter import (
    get_quote,
    get_price,
    get_sol_price_in_usd,
    get_token_price_in_sol,
    get_token_price_in_usd,
    fetch_token_list,
    estimate_swap_impact,
    _backoff_delay,
    _extract_token_list,
    _get_json,
    _cache_path,
    _read_cache,
    _write_cache,
    SOL_MINT,
    USDC_MINT,
    USDT_MINT,
    QUOTE_URL,
    PRICE_URL,
)


class TestBackoffDelay:
    """Test exponential backoff delay calculation."""

    def test_backoff_delay_first_attempt(self):
        """First attempt should return base delay."""
        result = _backoff_delay(0.5, 0)
        assert result == 0.5

    def test_backoff_delay_second_attempt(self):
        """Second attempt should double the base."""
        result = _backoff_delay(0.5, 1)
        assert result == 1.0

    def test_backoff_delay_third_attempt(self):
        """Third attempt should quadruple the base."""
        result = _backoff_delay(0.5, 2)
        assert result == 2.0

    def test_backoff_delay_respects_max(self):
        """Delay should not exceed max_delay."""
        result = _backoff_delay(1.0, 10, max_delay=30.0)
        assert result == 30.0

    def test_backoff_delay_custom_max(self):
        """Custom max_delay should be respected."""
        result = _backoff_delay(1.0, 5, max_delay=10.0)
        assert result == 10.0  # 2^5 = 32, capped at 10


class TestExtractTokenList:
    """Test token list extraction from API responses."""

    def test_extract_from_list(self):
        """Should return list directly if input is a list."""
        tokens = [{"symbol": "SOL"}, {"symbol": "USDC"}]
        result = _extract_token_list(tokens)
        assert result == tokens

    def test_extract_from_dict_with_tokens_key(self):
        """Should extract tokens from dict with 'tokens' key."""
        payload = {"tokens": [{"symbol": "SOL"}, {"symbol": "USDC"}]}
        result = _extract_token_list(payload)
        assert result == [{"symbol": "SOL"}, {"symbol": "USDC"}]

    def test_extract_from_dict_without_tokens_key(self):
        """Should return empty list if dict lacks 'tokens' key."""
        payload = {"data": [{"symbol": "SOL"}]}
        result = _extract_token_list(payload)
        assert result == []

    def test_extract_from_none(self):
        """Should return empty list for None."""
        result = _extract_token_list(None)
        assert result == []

    def test_extract_from_invalid_tokens_value(self):
        """Should return empty list if 'tokens' is not a list."""
        payload = {"tokens": "invalid"}
        result = _extract_token_list(payload)
        assert result == []


class TestCacheOperations:
    """Test cache file operations."""

    def test_cache_path_creates_directory(self, tmp_path):
        """Cache path should create cache directory if needed."""
        with patch.object(jupiter, 'CACHE_DIR', tmp_path / "test_cache"):
            path = _cache_path("https://api.jup.ag/quote", {"amount": "100"})
            assert path.parent.exists()
            assert path.suffix == ".json"

    def test_cache_path_deterministic(self, tmp_path):
        """Same URL and params should produce same cache path."""
        with patch.object(jupiter, 'CACHE_DIR', tmp_path / "test_cache"):
            path1 = _cache_path("https://api.jup.ag/quote", {"a": "1", "b": "2"})
            path2 = _cache_path("https://api.jup.ag/quote", {"b": "2", "a": "1"})
            assert path1 == path2  # Params are sorted

    def test_cache_path_different_for_different_params(self, tmp_path):
        """Different params should produce different cache paths."""
        with patch.object(jupiter, 'CACHE_DIR', tmp_path / "test_cache"):
            path1 = _cache_path("https://api.jup.ag/quote", {"a": "1"})
            path2 = _cache_path("https://api.jup.ag/quote", {"a": "2"})
            assert path1 != path2

    def test_write_cache(self, tmp_path):
        """Should write cache with timestamp."""
        cache_file = tmp_path / "test.json"
        _write_cache(cache_file, {"foo": "bar"})

        content = json.loads(cache_file.read_text())
        assert "cached_at" in content
        assert content["data"] == {"foo": "bar"}

    def test_read_cache_valid(self, tmp_path):
        """Should read valid cache within TTL."""
        cache_file = tmp_path / "test.json"
        cache_file.write_text(json.dumps({
            "cached_at": time.time(),
            "data": {"foo": "bar"}
        }))

        result = _read_cache(cache_file, ttl_seconds=60)
        assert result == {"foo": "bar"}

    def test_read_cache_expired(self, tmp_path):
        """Should return None for expired cache."""
        cache_file = tmp_path / "test.json"
        cache_file.write_text(json.dumps({
            "cached_at": time.time() - 120,  # 2 minutes ago
            "data": {"foo": "bar"}
        }))

        result = _read_cache(cache_file, ttl_seconds=60)
        assert result is None

    def test_read_cache_missing_file(self, tmp_path):
        """Should return None for missing cache file."""
        cache_file = tmp_path / "nonexistent.json"
        result = _read_cache(cache_file, ttl_seconds=60)
        assert result is None

    def test_read_cache_invalid_json(self, tmp_path):
        """Should return None for invalid JSON in cache."""
        cache_file = tmp_path / "test.json"
        cache_file.write_text("not valid json")

        result = _read_cache(cache_file, ttl_seconds=60)
        assert result is None

    def test_read_cache_missing_cached_at(self, tmp_path):
        """Should return None if cache lacks timestamp."""
        cache_file = tmp_path / "test.json"
        cache_file.write_text(json.dumps({"data": {"foo": "bar"}}))

        result = _read_cache(cache_file, ttl_seconds=60)
        assert result is None


class TestGetJson:
    """Test the _get_json HTTP request function."""

    @patch("core.jupiter.requests.get")
    def test_get_json_success(self, mock_get, tmp_path):
        """Should return parsed JSON on successful request."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}
        mock_get.return_value = mock_response

        with patch.object(jupiter, 'CACHE_DIR', tmp_path / "cache"):
            result = _get_json("https://api.test.com/data", cache_ttl_seconds=0)

        assert result == {"data": "test"}
        mock_get.assert_called_once()

    @patch("core.jupiter.requests.get")
    def test_get_json_with_params(self, mock_get):
        """Should pass params to request."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "ok"}
        mock_get.return_value = mock_response

        result = _get_json(
            "https://api.test.com/data",
            params={"key": "value"},
            cache_ttl_seconds=0
        )

        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert call_args[1]["params"] == {"key": "value"}

    @patch("core.jupiter.requests.get")
    def test_get_json_uses_cache(self, mock_get, tmp_path):
        """Should use cached response if within TTL."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        with patch.object(jupiter, 'CACHE_DIR', cache_dir):
            # First, populate cache
            cache_path_val = _cache_path("https://api.test.com/data", None)
            _write_cache(cache_path_val, {"cached": True})

            # Should return cached data without making request
            result = _get_json(
                "https://api.test.com/data",
                cache_ttl_seconds=60
            )

        assert result == {"cached": True}
        mock_get.assert_not_called()

    @patch("core.jupiter.requests.get")
    @patch("core.jupiter.time.sleep")
    def test_get_json_retries_on_429(self, mock_sleep, mock_get, tmp_path):
        """Should retry with backoff on rate limit (429)."""
        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429

        mock_response_ok = MagicMock()
        mock_response_ok.status_code = 200
        mock_response_ok.json.return_value = {"success": True}

        mock_get.side_effect = [mock_response_429, mock_response_ok]

        with patch.object(jupiter, 'CACHE_DIR', tmp_path / "cache"):
            result = _get_json(
                "https://api.test.com/data",
                cache_ttl_seconds=0,
                retries=3
            )

        assert result == {"success": True}
        assert mock_get.call_count == 2
        mock_sleep.assert_called()

    @patch("core.jupiter.requests.get")
    @patch("core.jupiter.time.sleep")
    def test_get_json_retries_on_503(self, mock_sleep, mock_get, tmp_path):
        """Should retry with backoff on service unavailable (503)."""
        mock_response_503 = MagicMock()
        mock_response_503.status_code = 503

        mock_response_ok = MagicMock()
        mock_response_ok.status_code = 200
        mock_response_ok.json.return_value = {"success": True}

        mock_get.side_effect = [mock_response_503, mock_response_ok]

        with patch.object(jupiter, 'CACHE_DIR', tmp_path / "cache"):
            result = _get_json(
                "https://api.test.com/data",
                cache_ttl_seconds=0,
                retries=3
            )

        assert result == {"success": True}
        assert mock_get.call_count == 2

    @patch("core.jupiter.requests.get")
    @patch("core.jupiter.time.sleep")
    def test_get_json_returns_none_after_max_retries(self, mock_sleep, mock_get, tmp_path):
        """Should return None after exhausting retries."""
        import requests
        mock_get.side_effect = requests.RequestException("Connection error")

        with patch.object(jupiter, 'CACHE_DIR', tmp_path / "cache"):
            result = _get_json(
                "https://api.test.com/data",
                cache_ttl_seconds=0,
                retries=3
            )

        assert result is None
        assert mock_get.call_count == 3

    @patch("core.jupiter.requests.get")
    def test_get_json_timeout(self, mock_get, tmp_path):
        """Should use specified timeout."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_get.return_value = mock_response

        with patch.object(jupiter, 'CACHE_DIR', tmp_path / "cache"):
            _get_json("https://api.test.com/data", timeout=30, cache_ttl_seconds=0)

        call_args = mock_get.call_args
        assert call_args[1]["timeout"] == 30


class TestGetQuote:
    """Test the get_quote function."""

    @patch("core.jupiter._get_json")
    def test_get_quote_success(self, mock_get_json):
        """Should return quote data on success."""
        mock_get_json.return_value = {
            "inputMint": SOL_MINT,
            "outputMint": USDC_MINT,
            "inAmount": "1000000000",
            "outAmount": "150000000",
            "priceImpactPct": "0.01",
            "routePlan": []
        }

        result = get_quote(SOL_MINT, USDC_MINT, 1_000_000_000)

        assert result is not None
        assert result["outAmount"] == "150000000"
        mock_get_json.assert_called_once()

        # Verify URL is correct
        call_args = mock_get_json.call_args
        assert call_args[0][0] == QUOTE_URL

    @patch("core.jupiter._get_json")
    def test_get_quote_with_slippage(self, mock_get_json):
        """Should pass slippage parameter."""
        mock_get_json.return_value = {"outAmount": "100"}

        get_quote(SOL_MINT, USDC_MINT, 1_000_000_000, slippage_bps=100)

        call_args = mock_get_json.call_args
        params = call_args[1]["params"]
        assert params["slippageBps"] == 100

    @patch("core.jupiter._get_json")
    def test_get_quote_direct_routes_only(self, mock_get_json):
        """Should pass onlyDirectRoutes when specified."""
        mock_get_json.return_value = {"outAmount": "100"}

        get_quote(SOL_MINT, USDC_MINT, 1_000_000_000, only_direct_routes=True)

        call_args = mock_get_json.call_args
        params = call_args[1]["params"]
        assert params["onlyDirectRoutes"] == "true"

    @patch("core.jupiter._get_json")
    def test_get_quote_returns_none_on_failure(self, mock_get_json):
        """Should return None when API fails."""
        mock_get_json.return_value = None

        result = get_quote(SOL_MINT, USDC_MINT, 1_000_000_000)

        assert result is None


class TestGetPrice:
    """Test the get_price function."""

    @patch("core.jupiter._get_json")
    def test_get_price_success(self, mock_get_json):
        """Should return price data on success."""
        mock_get_json.return_value = {
            "data": {
                SOL_MINT: {"price": 150.25}
            }
        }

        result = get_price([SOL_MINT])

        assert result is not None
        assert "data" in result
        assert SOL_MINT in result["data"]

    @patch("core.jupiter._get_json")
    def test_get_price_multiple_tokens(self, mock_get_json):
        """Should handle multiple token IDs."""
        mock_get_json.return_value = {
            "data": {
                SOL_MINT: {"price": 150},
                USDC_MINT: {"price": 1}
            }
        }

        result = get_price([SOL_MINT, USDC_MINT])

        call_args = mock_get_json.call_args
        params = call_args[1]["params"]
        assert "," in params["ids"]

    @patch("core.jupiter._get_json")
    def test_get_price_vs_sol(self, mock_get_json):
        """Should use SOL as quote currency when specified."""
        mock_get_json.return_value = {"data": {}}

        get_price([USDC_MINT], vs_currency="sol")

        call_args = mock_get_json.call_args
        params = call_args[1]["params"]
        assert params["vsToken"] == SOL_MINT

    @patch("core.jupiter._get_json")
    def test_get_price_returns_none_on_failure(self, mock_get_json):
        """Should return None when API fails."""
        mock_get_json.return_value = None

        result = get_price([SOL_MINT])

        assert result is None


class TestGetSolPriceInUsd:
    """Test the get_sol_price_in_usd function."""

    @patch("core.jupiter.get_price")
    def test_get_sol_price_success(self, mock_get_price):
        """Should return SOL price in USD."""
        mock_get_price.return_value = {
            "data": {
                SOL_MINT: {"price": 150.75}
            }
        }

        result = get_sol_price_in_usd()

        assert result == 150.75

    @patch("core.jupiter.get_price")
    def test_get_sol_price_returns_none_when_no_data(self, mock_get_price):
        """Should return None when no data available."""
        mock_get_price.return_value = {"data": {}}

        result = get_sol_price_in_usd()

        assert result is None

    @patch("core.jupiter.get_price")
    def test_get_sol_price_returns_none_on_failure(self, mock_get_price):
        """Should return None when API fails."""
        mock_get_price.return_value = None

        result = get_sol_price_in_usd()

        assert result is None


class TestGetTokenPriceInSol:
    """Test the get_token_price_in_sol function."""

    @patch("core.jupiter.get_quote")
    def test_get_token_price_in_sol_success(self, mock_get_quote):
        """Should return token price in SOL."""
        mock_get_quote.return_value = {
            "outAmount": "500000000"  # 0.5 SOL
        }

        result = get_token_price_in_sol("TOKEN_MINT_ADDRESS")

        assert result == 0.5

    @patch("core.jupiter.get_quote")
    def test_get_token_price_in_sol_returns_none_when_no_quote(self, mock_get_quote):
        """Should return None when no quote available."""
        mock_get_quote.return_value = None

        result = get_token_price_in_sol("TOKEN_MINT_ADDRESS")

        assert result is None

    @patch("core.jupiter.get_quote")
    def test_get_token_price_in_sol_returns_none_when_no_out_amount(self, mock_get_quote):
        """Should return None when quote lacks outAmount."""
        mock_get_quote.return_value = {}

        result = get_token_price_in_sol("TOKEN_MINT_ADDRESS")

        assert result is None


class TestGetTokenPriceInUsd:
    """Test the get_token_price_in_usd function."""

    @patch("core.jupiter.get_sol_price_in_usd")
    @patch("core.jupiter.get_token_price_in_sol")
    def test_get_token_price_in_usd_success(self, mock_sol_price, mock_token_price):
        """Should calculate USD price from SOL price."""
        mock_sol_price.return_value = 0.5  # Token is 0.5 SOL
        mock_token_price.return_value = 150.0  # SOL is $150
        # Wait, the mocks are reversed. Let me check the function signature

    @patch("core.jupiter.get_token_price_in_sol")
    @patch("core.jupiter.get_sol_price_in_usd")
    def test_get_token_price_in_usd_success_correct(self, mock_sol_usd, mock_token_sol):
        """Should calculate USD price from SOL price."""
        mock_sol_usd.return_value = 150.0  # SOL is $150
        mock_token_sol.return_value = 0.5  # Token is 0.5 SOL

        result = get_token_price_in_usd("TOKEN_MINT_ADDRESS")

        assert result == 75.0  # 0.5 * 150 = 75

    @patch("core.jupiter.get_token_price_in_sol")
    @patch("core.jupiter.get_sol_price_in_usd")
    def test_get_token_price_in_usd_returns_none_when_no_sol_price(self, mock_sol_usd, mock_token_sol):
        """Should return None when SOL price unavailable."""
        mock_sol_usd.return_value = None
        mock_token_sol.return_value = 0.5

        result = get_token_price_in_usd("TOKEN_MINT_ADDRESS")

        assert result is None

    @patch("core.jupiter.get_token_price_in_sol")
    @patch("core.jupiter.get_sol_price_in_usd")
    def test_get_token_price_in_usd_returns_none_when_no_token_price(self, mock_sol_usd, mock_token_sol):
        """Should return None when token price unavailable."""
        mock_sol_usd.return_value = 150.0
        mock_token_sol.return_value = None

        result = get_token_price_in_usd("TOKEN_MINT_ADDRESS")

        assert result is None


class TestFetchTokenList:
    """Test the fetch_token_list function."""

    @patch("core.jupiter._get_json")
    def test_fetch_token_list_success(self, mock_get_json):
        """Should return token list on success."""
        mock_get_json.return_value = [
            {"symbol": "SOL", "address": SOL_MINT},
            {"symbol": "USDC", "address": USDC_MINT}
        ]

        result = fetch_token_list()

        assert len(result) == 2
        assert result[0]["symbol"] == "SOL"

    @patch("core.jupiter._get_json")
    def test_fetch_token_list_uses_fallback(self, mock_get_json):
        """Should use fallback URL when primary fails."""
        mock_get_json.side_effect = [
            None,  # Primary fails
            {"tokens": [{"symbol": "SOL"}]}  # Fallback succeeds
        ]

        result = fetch_token_list()

        assert len(result) == 1
        assert result[0]["symbol"] == "SOL"

    @patch("core.jupiter._get_json")
    def test_fetch_token_list_returns_empty_when_both_fail(self, mock_get_json):
        """Should return empty list when both URLs fail."""
        mock_get_json.return_value = None

        result = fetch_token_list()

        assert result == []


class TestEstimateSwapImpact:
    """Test the estimate_swap_impact function."""

    @patch("core.jupiter.get_quote")
    @patch("core.jupiter.get_sol_price_in_usd")
    def test_estimate_swap_impact_sol_input(self, mock_sol_price, mock_get_quote):
        """Should estimate impact for SOL input."""
        mock_sol_price.return_value = 150.0
        mock_get_quote.return_value = {
            "outAmount": "100000000",
            "priceImpactPct": "0.5",
            "routePlan": [{"swap": "info"}],
            "otherAmountThreshold": "99000000"
        }

        result = estimate_swap_impact(
            SOL_MINT,
            USDC_MINT,
            amount_usd=100.0
        )

        assert result is not None
        assert result["output_amount"] == 100000000
        assert result["price_impact_pct"] == 0.5
        assert "route_plan" in result

    @patch("core.jupiter.get_quote")
    @patch("core.jupiter.get_sol_price_in_usd")
    def test_estimate_swap_impact_non_sol_input(self, mock_sol_price, mock_get_quote):
        """Should estimate impact for non-SOL input."""
        mock_sol_price.return_value = 150.0
        mock_get_quote.return_value = {
            "outAmount": "500000000",
            "priceImpactPct": "0.1"
        }

        result = estimate_swap_impact(
            USDC_MINT,
            SOL_MINT,
            amount_usd=100.0
        )

        assert result is not None
        assert result["output_amount"] == 500000000

    @patch("core.jupiter.get_sol_price_in_usd")
    def test_estimate_swap_impact_returns_none_when_no_sol_price(self, mock_sol_price):
        """Should return None when SOL price unavailable."""
        mock_sol_price.return_value = None

        result = estimate_swap_impact(SOL_MINT, USDC_MINT, amount_usd=100.0)

        assert result is None

    @patch("core.jupiter.get_quote")
    @patch("core.jupiter.get_sol_price_in_usd")
    def test_estimate_swap_impact_returns_none_when_no_quote(self, mock_sol_price, mock_get_quote):
        """Should return None when quote unavailable."""
        mock_sol_price.return_value = 150.0
        mock_get_quote.return_value = None

        result = estimate_swap_impact(SOL_MINT, USDC_MINT, amount_usd=100.0)

        assert result is None


class TestConstants:
    """Test module constants."""

    def test_sol_mint_constant(self):
        """SOL_MINT should be the correct address."""
        assert SOL_MINT == "So11111111111111111111111111111111111111112"

    def test_usdc_mint_constant(self):
        """USDC_MINT should be the correct address."""
        assert USDC_MINT == "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

    def test_usdt_mint_constant(self):
        """USDT_MINT should be the correct address."""
        assert USDT_MINT == "Es9vMFrzaCER3EJmqvQC2Uo9qowWP1h1xFh3Le7YpR1V"

    def test_quote_url(self):
        """QUOTE_URL should be the Jupiter v6 quote endpoint."""
        assert "quote-api.jup.ag" in QUOTE_URL
        assert "v6" in QUOTE_URL

    def test_price_url(self):
        """PRICE_URL should be the Jupiter price endpoint."""
        assert "price.jup.ag" in PRICE_URL


class TestIntegration:
    """Integration tests with minimal mocking."""

    @patch("core.jupiter.requests.get")
    def test_full_quote_flow(self, mock_get, tmp_path):
        """Test full flow from get_quote to response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "inputMint": SOL_MINT,
            "outputMint": USDC_MINT,
            "inAmount": "1000000000",
            "outAmount": "150000000",
            "priceImpactPct": "0.01",
            "routePlan": [{"swapInfo": {"ammKey": "test"}}]
        }
        mock_get.return_value = mock_response

        with patch.object(jupiter, 'CACHE_DIR', tmp_path / "cache"):
            result = get_quote(
                SOL_MINT,
                USDC_MINT,
                1_000_000_000,
                slippage_bps=50,
                cache_ttl_seconds=0  # Disable cache for test
            )

        assert result is not None
        assert int(result["outAmount"]) == 150000000
        assert float(result["priceImpactPct"]) == 0.01

    @patch("core.jupiter.requests.get")
    def test_cache_workflow(self, mock_get, tmp_path):
        """Test that caching works correctly."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"price": 150}
        mock_get.return_value = mock_response

        with patch.object(jupiter, 'CACHE_DIR', tmp_path / "cache"):
            # First call - should hit API
            result1 = get_price([SOL_MINT], cache_ttl_seconds=60)

            # Second call - should use cache
            result2 = get_price([SOL_MINT], cache_ttl_seconds=60)

        # API should only be called once
        assert mock_get.call_count == 1
        assert result1 == result2


class TestErrorHandling:
    """Test error handling scenarios."""

    @patch("core.jupiter.requests.get")
    @patch("core.jupiter.time.sleep")
    def test_handles_connection_error(self, mock_sleep, mock_get, tmp_path):
        """Should handle connection errors gracefully."""
        import requests
        mock_get.side_effect = requests.ConnectionError("Network unreachable")

        with patch.object(jupiter, 'CACHE_DIR', tmp_path / "cache"):
            result = _get_json(
                "https://api.test.com/data",
                retries=2,
                cache_ttl_seconds=0
            )

        assert result is None

    @patch("core.jupiter.requests.get")
    @patch("core.jupiter.time.sleep")
    def test_handles_timeout_error(self, mock_sleep, mock_get, tmp_path):
        """Should handle timeout errors gracefully."""
        import requests
        mock_get.side_effect = requests.Timeout("Request timed out")

        with patch.object(jupiter, 'CACHE_DIR', tmp_path / "cache"):
            result = _get_json(
                "https://api.test.com/data",
                retries=2,
                cache_ttl_seconds=0
            )

        assert result is None

    @patch("core.jupiter.requests.get")
    def test_handles_http_error(self, mock_get, tmp_path):
        """Should handle HTTP errors gracefully."""
        import requests
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.HTTPError("Server error")
        mock_get.return_value = mock_response

        with patch.object(jupiter, 'CACHE_DIR', tmp_path / "cache"):
            with patch("core.jupiter.time.sleep"):
                result = _get_json(
                    "https://api.test.com/data",
                    retries=1,
                    cache_ttl_seconds=0
                )

        assert result is None


class TestSlippageHandling:
    """Test slippage-related functionality."""

    @patch("core.jupiter._get_json")
    def test_default_slippage(self, mock_get_json):
        """Should use default slippage of 50 bps."""
        mock_get_json.return_value = {"outAmount": "100"}

        get_quote(SOL_MINT, USDC_MINT, 1_000_000_000)

        call_args = mock_get_json.call_args
        params = call_args[1]["params"]
        assert params["slippageBps"] == 50

    @patch("core.jupiter._get_json")
    def test_custom_slippage(self, mock_get_json):
        """Should use custom slippage when specified."""
        mock_get_json.return_value = {"outAmount": "100"}

        get_quote(SOL_MINT, USDC_MINT, 1_000_000_000, slippage_bps=200)

        call_args = mock_get_json.call_args
        params = call_args[1]["params"]
        assert params["slippageBps"] == 200


class TestPriceImpact:
    """Test price impact handling."""

    @patch("core.jupiter.get_quote")
    @patch("core.jupiter.get_sol_price_in_usd")
    def test_price_impact_extracted_correctly(self, mock_sol_price, mock_get_quote):
        """Should extract price impact from quote."""
        mock_sol_price.return_value = 150.0
        mock_get_quote.return_value = {
            "outAmount": "100000000",
            "priceImpactPct": "2.5",
            "routePlan": []
        }

        result = estimate_swap_impact(SOL_MINT, USDC_MINT, amount_usd=1000.0)

        assert result["price_impact_pct"] == 2.5

    @patch("core.jupiter.get_quote")
    @patch("core.jupiter.get_sol_price_in_usd")
    def test_price_impact_zero_when_missing(self, mock_sol_price, mock_get_quote):
        """Should default to 0 when price impact missing."""
        mock_sol_price.return_value = 150.0
        mock_get_quote.return_value = {
            "outAmount": "100000000"
        }

        result = estimate_swap_impact(SOL_MINT, USDC_MINT, amount_usd=100.0)

        assert result["price_impact_pct"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
