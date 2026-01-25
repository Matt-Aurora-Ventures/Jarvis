"""
Tests for core/solana_execution.py - Solana transaction execution helpers.

CRITICAL: This module handles real money movement on Solana blockchain.
All tests use mocks - NO REAL TRANSACTIONS.
"""

import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest


# ==============================================================================
# Test Fixtures
# ==============================================================================

@pytest.fixture
def reset_circuit_breakers():
    """Reset circuit breaker state before and after each test."""
    from core import solana_execution
    solana_execution.reset_circuit_breakers()
    yield
    solana_execution.reset_circuit_breakers()


@pytest.fixture
def mock_rpc_endpoint():
    """Create a mock RPC endpoint."""
    from core.solana_execution import RpcEndpoint
    return RpcEndpoint(
        name="test_endpoint",
        url="https://test-rpc.solana.com",
        timeout_ms=5000,
        rate_limit=100,
    )


@pytest.fixture
def mock_endpoints_list():
    """Create a list of mock RPC endpoints."""
    from core.solana_execution import RpcEndpoint
    return [
        RpcEndpoint(name="primary", url="https://primary-rpc.solana.com", timeout_ms=5000, rate_limit=100),
        RpcEndpoint(name="fallback1", url="https://fallback1-rpc.solana.com", timeout_ms=5000, rate_limit=50),
        RpcEndpoint(name="fallback2", url="https://fallback2-rpc.solana.com", timeout_ms=5000, rate_limit=50),
    ]


@pytest.fixture
def mock_swap_quote():
    """Create a mock Jupiter swap quote."""
    return {
        "inputMint": "So11111111111111111111111111111111111111112",
        "outputMint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        "inAmount": "1000000000",
        "outAmount": "100000000",
        "priceImpactPct": "0.5",
        "routePlan": [{"swapInfo": {"ammKey": "test"}}],
    }


@pytest.fixture
def mock_versioned_transaction():
    """Create a mock VersionedTransaction."""
    mock_tx = MagicMock()
    mock_tx.signatures = [b"test_signature"]
    return mock_tx


# ==============================================================================
# Backoff and Rate Limiting Tests
# ==============================================================================

class TestBackoffDelay:
    """Test exponential backoff delay calculation."""

    def test_backoff_delay_base_case(self):
        """Backoff should return approximately base delay for attempt 0."""
        from core.solana_execution import _backoff_delay

        delay = _backoff_delay(1.0, 0)
        # Base delay + up to 10% jitter
        assert 1.0 <= delay <= 1.1

    def test_backoff_delay_exponential_growth(self):
        """Backoff should grow exponentially with attempts."""
        from core.solana_execution import _backoff_delay

        delay_0 = _backoff_delay(1.0, 0, max_delay=100.0)
        delay_1 = _backoff_delay(1.0, 1, max_delay=100.0)
        delay_2 = _backoff_delay(1.0, 2, max_delay=100.0)

        # Each attempt should roughly double (with jitter)
        assert delay_1 > delay_0
        assert delay_2 > delay_1
        # delay_2 should be approximately 4x base (with jitter)
        assert 4.0 <= delay_2 <= 4.5

    def test_backoff_delay_respects_max_delay(self):
        """Backoff should never exceed max_delay."""
        from core.solana_execution import _backoff_delay

        delay = _backoff_delay(1.0, 100, max_delay=30.0)
        # Max delay + up to 10% jitter
        assert delay <= 33.0

    def test_backoff_delay_includes_jitter(self):
        """Backoff should include random jitter to prevent thundering herd."""
        from core.solana_execution import _backoff_delay

        delays = [_backoff_delay(1.0, 0) for _ in range(10)]
        # Not all delays should be identical due to jitter
        assert len(set(delays)) > 1


class TestRateLimitDetection:
    """Test rate limit status code detection."""

    def test_is_rate_limited_429(self):
        """429 Too Many Requests should be detected as rate limited."""
        from core.solana_execution import _is_rate_limited
        assert _is_rate_limited(429) is True

    def test_is_rate_limited_503(self):
        """503 Service Unavailable should be detected as rate limited."""
        from core.solana_execution import _is_rate_limited
        assert _is_rate_limited(503) is True

    def test_is_rate_limited_502(self):
        """502 Bad Gateway should be detected as rate limited."""
        from core.solana_execution import _is_rate_limited
        assert _is_rate_limited(502) is True

    def test_is_rate_limited_200(self):
        """200 OK should not be detected as rate limited."""
        from core.solana_execution import _is_rate_limited
        assert _is_rate_limited(200) is False

    def test_is_rate_limited_500(self):
        """500 Internal Server Error should not be detected as rate limited."""
        from core.solana_execution import _is_rate_limited
        assert _is_rate_limited(500) is False


# ==============================================================================
# Circuit Breaker Tests
# ==============================================================================

class TestCircuitBreaker:
    """Test circuit breaker pattern for RPC endpoints."""

    def test_mark_endpoint_failure_increments_count(self, reset_circuit_breakers):
        """Marking failure should increment the failure count."""
        from core.solana_execution import _mark_endpoint_failure, _endpoint_failures

        url = "https://test.com"
        _mark_endpoint_failure(url)
        assert _endpoint_failures[url] == 1

        _mark_endpoint_failure(url)
        assert _endpoint_failures[url] == 2

    def test_mark_endpoint_success_resets_count(self, reset_circuit_breakers):
        """Marking success should reset the failure count."""
        from core.solana_execution import (
            _mark_endpoint_failure,
            _mark_endpoint_success,
            _endpoint_failures,
        )

        url = "https://test.com"
        _mark_endpoint_failure(url)
        _mark_endpoint_failure(url)
        assert _endpoint_failures[url] == 2

        _mark_endpoint_success(url)
        assert _endpoint_failures[url] == 0

    def test_is_endpoint_available_under_threshold(self, reset_circuit_breakers):
        """Endpoint should be available when under failure threshold."""
        from core.solana_execution import (
            _mark_endpoint_failure,
            _is_endpoint_available,
            CIRCUIT_BREAKER_FAILURE_THRESHOLD,
        )

        url = "https://test.com"
        for _ in range(CIRCUIT_BREAKER_FAILURE_THRESHOLD - 1):
            _mark_endpoint_failure(url)

        assert _is_endpoint_available(url) is True

    def test_is_endpoint_available_at_threshold(self, reset_circuit_breakers):
        """Endpoint should be unavailable when at failure threshold."""
        from core.solana_execution import (
            _mark_endpoint_failure,
            _is_endpoint_available,
            CIRCUIT_BREAKER_FAILURE_THRESHOLD,
        )

        url = "https://test.com"
        for _ in range(CIRCUIT_BREAKER_FAILURE_THRESHOLD):
            _mark_endpoint_failure(url)

        assert _is_endpoint_available(url) is False

    def test_endpoint_recovery_after_timeout(self, reset_circuit_breakers):
        """Endpoint should be available again after recovery period."""
        from core.solana_execution import (
            _mark_endpoint_failure,
            _is_endpoint_available,
            _endpoint_last_failure,
            CIRCUIT_BREAKER_FAILURE_THRESHOLD,
            CIRCUIT_BREAKER_RECOVERY_SECONDS,
        )

        url = "https://test.com"
        for _ in range(CIRCUIT_BREAKER_FAILURE_THRESHOLD):
            _mark_endpoint_failure(url)

        # Simulate recovery period elapsed
        _endpoint_last_failure[url] = time.time() - CIRCUIT_BREAKER_RECOVERY_SECONDS - 1

        assert _is_endpoint_available(url) is True

    def test_reset_circuit_breakers(self, reset_circuit_breakers):
        """reset_circuit_breakers should clear all state."""
        from core.solana_execution import (
            _mark_endpoint_failure,
            _endpoint_failures,
            _endpoint_last_failure,
            _endpoint_health_cache,
            reset_circuit_breakers as reset_fn,
        )

        url = "https://test.com"
        _mark_endpoint_failure(url)
        _endpoint_health_cache[url] = (True, time.time())

        reset_fn()

        assert len(_endpoint_failures) == 0
        assert len(_endpoint_last_failure) == 0
        assert len(_endpoint_health_cache) == 0


# ==============================================================================
# Error Classification Tests
# ==============================================================================

class TestBlockhashExpiredDetection:
    """Test blockhash expiration error detection."""

    def test_is_blockhash_expired_with_blockhash_keyword(self):
        """Should detect 'blockhash' in error message."""
        from core.solana_execution import _is_blockhash_expired

        assert _is_blockhash_expired("Blockhash not found") is True
        assert _is_blockhash_expired("Transaction blockhash expired") is True

    def test_is_blockhash_expired_with_blockhashnotfound(self):
        """Should detect 'blockhashnotfound' in error message."""
        from core.solana_execution import _is_blockhash_expired

        assert _is_blockhash_expired("BlockhashNotFound") is True

    def test_is_blockhash_expired_with_none(self):
        """Should return False for None error."""
        from core.solana_execution import _is_blockhash_expired

        assert _is_blockhash_expired(None) is False

    def test_is_blockhash_expired_unrelated_error(self):
        """Should return False for unrelated errors."""
        from core.solana_execution import _is_blockhash_expired

        assert _is_blockhash_expired("Insufficient funds") is False
        assert _is_blockhash_expired("Connection timeout") is False


class TestSimulationErrorDescription:
    """Test human-readable error description generation."""

    def test_describe_already_processed(self):
        """Should provide hint for AlreadyProcessed errors."""
        from core.solana_execution import describe_simulation_error

        hint = describe_simulation_error("AlreadyProcessed")
        assert hint is not None
        assert "duplicate" in hint.lower() or "replayed" in hint.lower()

    def test_describe_blockhash_error(self):
        """Should provide hint for blockhash errors."""
        from core.solana_execution import describe_simulation_error

        hint = describe_simulation_error("Blockhash expired")
        assert hint is not None
        assert "blockhash" in hint.lower()

    def test_describe_account_in_use(self):
        """Should provide hint for AccountInUse errors."""
        from core.solana_execution import describe_simulation_error

        hint = describe_simulation_error("AccountInUse")
        assert hint is not None
        assert "retry" in hint.lower()

    def test_describe_insufficient_funds(self):
        """Should provide hint for InsufficientFunds errors."""
        from core.solana_execution import describe_simulation_error

        hint = describe_simulation_error("InsufficientFunds")
        assert hint is not None
        assert "funds" in hint.lower()

    def test_describe_invalid_account_data(self):
        """Should provide hint for InvalidAccountData errors."""
        from core.solana_execution import describe_simulation_error

        hint = describe_simulation_error("InvalidAccountData")
        assert hint is not None
        assert "account" in hint.lower()

    def test_describe_uninitialized_account(self):
        """Should provide hint for UninitializedAccount errors."""
        from core.solana_execution import describe_simulation_error

        hint = describe_simulation_error("UninitializedAccount")
        assert hint is not None
        assert "initialize" in hint.lower() or "create" in hint.lower()

    def test_describe_signature_verification_failed(self):
        """Should provide hint for SignatureVerificationFailed errors."""
        from core.solana_execution import describe_simulation_error

        hint = describe_simulation_error("SignatureVerificationFailed")
        assert hint is not None
        assert "signature" in hint.lower()

    def test_describe_custom_program_error(self):
        """Should provide hint for custom program errors."""
        from core.solana_execution import describe_simulation_error

        hint = describe_simulation_error("InstructionErrorCustom(42)")
        assert hint is not None
        assert "42" in hint
        assert "custom" in hint.lower() or "program" in hint.lower()

    def test_describe_none_error(self):
        """Should return None for None error."""
        from core.solana_execution import describe_simulation_error

        assert describe_simulation_error(None) is None

    def test_describe_unknown_error(self):
        """Should return None for unknown errors."""
        from core.solana_execution import describe_simulation_error

        assert describe_simulation_error("SomeUnknownError") is None


class TestSimulationErrorClassification:
    """Test error classification for retry decisions."""

    def test_classify_already_processed_as_permanent(self):
        """AlreadyProcessed should be classified as permanent."""
        from core.solana_execution import classify_simulation_error

        assert classify_simulation_error("AlreadyProcessed") == "permanent"

    def test_classify_blockhash_as_retryable(self):
        """Blockhash errors should be classified as retryable."""
        from core.solana_execution import classify_simulation_error

        assert classify_simulation_error("Blockhash expired") == "retryable"

    def test_classify_account_in_use_as_retryable(self):
        """AccountInUse should be classified as retryable."""
        from core.solana_execution import classify_simulation_error

        assert classify_simulation_error("AccountInUse") == "retryable"

    def test_classify_timeout_as_retryable(self):
        """Timeout errors should be classified as retryable."""
        from core.solana_execution import classify_simulation_error

        assert classify_simulation_error("Connection timed out") == "retryable"
        assert classify_simulation_error("Request timeout") == "retryable"

    def test_classify_network_as_retryable(self):
        """Network errors should be classified as retryable."""
        from core.solana_execution import classify_simulation_error

        assert classify_simulation_error("Network error") == "retryable"
        assert classify_simulation_error("Connection refused") == "retryable"

    def test_classify_rate_limit_as_retryable(self):
        """Rate limit errors should be classified as retryable."""
        from core.solana_execution import classify_simulation_error

        assert classify_simulation_error("rate limited") == "retryable"
        assert classify_simulation_error("HTTP 429") == "retryable"
        assert classify_simulation_error("HTTP 503") == "retryable"

    def test_classify_insufficient_funds_as_permanent(self):
        """InsufficientFunds should be classified as permanent."""
        from core.solana_execution import classify_simulation_error

        assert classify_simulation_error("InsufficientFunds") == "permanent"

    def test_classify_invalid_account_as_permanent(self):
        """InvalidAccountData should be classified as permanent."""
        from core.solana_execution import classify_simulation_error

        assert classify_simulation_error("InvalidAccountData") == "permanent"

    def test_classify_uninitialized_as_permanent(self):
        """UninitializedAccount should be classified as permanent."""
        from core.solana_execution import classify_simulation_error

        assert classify_simulation_error("UninitializedAccount") == "permanent"

    def test_classify_signature_failed_as_permanent(self):
        """SignatureVerificationFailed should be classified as permanent."""
        from core.solana_execution import classify_simulation_error

        assert classify_simulation_error("SignatureVerificationFailed") == "permanent"

    def test_classify_custom_error_as_permanent(self):
        """Custom program errors should be classified as permanent."""
        from core.solana_execution import classify_simulation_error

        assert classify_simulation_error("InstructionErrorCustom(42)") == "permanent"
        assert classify_simulation_error("Custom program error 123") == "permanent"

    def test_classify_none_as_unknown(self):
        """None error should be classified as unknown."""
        from core.solana_execution import classify_simulation_error

        assert classify_simulation_error(None) == "unknown"

    def test_classify_random_error_as_unknown(self):
        """Unknown errors should be classified as unknown."""
        from core.solana_execution import classify_simulation_error

        assert classify_simulation_error("SomeRandomError") == "unknown"


class TestIsRetryableError:
    """Test is_retryable_error helper function."""

    def test_is_retryable_for_retryable_errors(self):
        """Should return True for retryable errors."""
        from core.solana_execution import is_retryable_error

        assert is_retryable_error("Blockhash expired") is True
        assert is_retryable_error("timeout") is True
        assert is_retryable_error("rate limited") is True

    def test_is_retryable_for_permanent_errors(self):
        """Should return False for permanent errors."""
        from core.solana_execution import is_retryable_error

        assert is_retryable_error("InsufficientFunds") is False
        assert is_retryable_error("AlreadyProcessed") is False

    def test_is_retryable_for_unknown_errors(self):
        """Should return False for unknown errors."""
        from core.solana_execution import is_retryable_error

        assert is_retryable_error("SomeUnknownError") is False


# ==============================================================================
# Data Classes Tests
# ==============================================================================

class TestRpcEndpoint:
    """Test RpcEndpoint dataclass."""

    def test_rpc_endpoint_defaults(self):
        """RpcEndpoint should have sensible defaults."""
        from core.solana_execution import RpcEndpoint

        endpoint = RpcEndpoint(name="test", url="https://test.com")

        assert endpoint.timeout_ms == 30000
        assert endpoint.rate_limit == 100

    def test_rpc_endpoint_custom_values(self):
        """RpcEndpoint should accept custom values."""
        from core.solana_execution import RpcEndpoint

        endpoint = RpcEndpoint(
            name="custom",
            url="https://custom.com",
            timeout_ms=10000,
            rate_limit=50,
        )

        assert endpoint.name == "custom"
        assert endpoint.url == "https://custom.com"
        assert endpoint.timeout_ms == 10000
        assert endpoint.rate_limit == 50


class TestSwapExecutionResult:
    """Test SwapExecutionResult dataclass."""

    def test_swap_result_success(self):
        """SwapExecutionResult should represent successful swap."""
        from core.solana_execution import SwapExecutionResult

        result = SwapExecutionResult(
            success=True,
            signature="abc123",
            endpoint="primary",
        )

        assert result.success is True
        assert result.signature == "abc123"
        assert result.error is None

    def test_swap_result_failure(self):
        """SwapExecutionResult should represent failed swap."""
        from core.solana_execution import SwapExecutionResult

        result = SwapExecutionResult(
            success=False,
            error="simulation_failed",
            simulation_error="InsufficientFunds",
            error_hint="Insufficient funds for fee or transfer.",
            retryable=False,
        )

        assert result.success is False
        assert result.error == "simulation_failed"
        assert result.retryable is False

    def test_swap_result_defaults(self):
        """SwapExecutionResult should have sensible defaults."""
        from core.solana_execution import SwapExecutionResult

        result = SwapExecutionResult(success=False)

        assert result.signature is None
        assert result.error is None
        assert result.endpoint is None
        assert result.simulation_error is None
        assert result.error_hint is None
        assert result.retryable is False


# ==============================================================================
# Environment Variable Substitution Tests
# ==============================================================================

class TestEnvSubstitution:
    """Test environment variable substitution in config values."""

    def test_substitute_env_no_placeholder(self):
        """Should return value unchanged if no placeholder."""
        from core.solana_execution import _substitute_env

        assert _substitute_env("https://plain-url.com") == "https://plain-url.com"

    def test_substitute_env_with_valid_env_var(self):
        """Should substitute environment variable placeholder."""
        from core.solana_execution import _substitute_env

        with patch.dict("os.environ", {"TEST_API_KEY": "secret123"}):
            result = _substitute_env("https://api.com?key=${TEST_API_KEY}")
            assert result == "https://api.com?key=secret123"

    def test_substitute_env_with_missing_env_var(self):
        """Should return None if environment variable is not set."""
        from core.solana_execution import _substitute_env

        with patch.dict("os.environ", {}, clear=True):
            result = _substitute_env("https://api.com?key=${MISSING_KEY}")
            assert result is None

    def test_substitute_env_malformed_placeholder(self):
        """Should return value unchanged for malformed placeholders."""
        from core.solana_execution import _substitute_env

        # Missing closing brace
        assert _substitute_env("${INCOMPLETE") == "${INCOMPLETE"


# ==============================================================================
# RPC Config Loading Tests
# ==============================================================================

class TestLoadSolanaRpcEndpoints:
    """Test RPC endpoint configuration loading."""

    def test_load_endpoints_missing_config(self, tmp_path):
        """Should return public endpoint when config file is missing."""
        from core.solana_execution import load_solana_rpc_endpoints, RPC_CONFIG

        with patch.object(Path, "exists", return_value=False):
            with patch("core.solana_execution.RPC_CONFIG", tmp_path / "nonexistent.json"):
                endpoints = load_solana_rpc_endpoints()

                assert len(endpoints) >= 1
                assert endpoints[0].name == "public_solana"
                assert "api.mainnet-beta.solana.com" in endpoints[0].url

    def test_load_endpoints_invalid_json(self, tmp_path):
        """Should return public endpoint when config JSON is invalid."""
        from core.solana_execution import load_solana_rpc_endpoints

        config_file = tmp_path / "rpc_providers.json"
        config_file.write_text("not valid json")

        with patch("core.solana_execution.RPC_CONFIG", config_file):
            endpoints = load_solana_rpc_endpoints()

            assert len(endpoints) >= 1
            assert endpoints[0].name == "public_solana"

    def test_load_endpoints_valid_config(self, tmp_path):
        """Should load endpoints from valid config file."""
        from core.solana_execution import load_solana_rpc_endpoints

        config_file = tmp_path / "rpc_providers.json"
        config_data = {
            "solana": {
                "primary": {
                    "name": "helius",
                    "url": "https://helius-rpc.com",
                    "timeout_ms": 10000,
                    "rate_limit": 200,
                },
                "fallback": [
                    {
                        "name": "quicknode",
                        "url": "https://quicknode-rpc.com",
                        "timeout_ms": 15000,
                        "rate_limit": 100,
                    }
                ],
            }
        }
        config_file.write_text(json.dumps(config_data))

        with patch("core.solana_execution.RPC_CONFIG", config_file):
            endpoints = load_solana_rpc_endpoints()

            assert len(endpoints) == 2
            assert endpoints[0].name == "helius"
            assert endpoints[0].url == "https://helius-rpc.com"
            assert endpoints[1].name == "quicknode"

    def test_load_endpoints_with_env_substitution(self, tmp_path):
        """Should substitute environment variables in URLs."""
        from core.solana_execution import load_solana_rpc_endpoints

        config_file = tmp_path / "rpc_providers.json"
        config_data = {
            "solana": {
                "primary": {
                    "name": "helius",
                    "url": "https://rpc.helius.xyz/?api-key=${HELIUS_API_KEY}",
                }
            }
        }
        config_file.write_text(json.dumps(config_data))

        with patch("core.solana_execution.RPC_CONFIG", config_file):
            with patch.dict("os.environ", {"HELIUS_API_KEY": "test-key-123"}):
                endpoints = load_solana_rpc_endpoints()

                assert len(endpoints) >= 1
                assert "test-key-123" in endpoints[0].url

    def test_load_endpoints_empty_config(self, tmp_path):
        """Should return public endpoint when config has no valid endpoints."""
        from core.solana_execution import load_solana_rpc_endpoints

        config_file = tmp_path / "rpc_providers.json"
        config_data = {"solana": {}}
        config_file.write_text(json.dumps(config_data))

        with patch("core.solana_execution.RPC_CONFIG", config_file):
            endpoints = load_solana_rpc_endpoints()

            assert len(endpoints) >= 1
            assert endpoints[0].name == "public_solana"


# ==============================================================================
# HTTP Request Tests
# ==============================================================================

class TestRequestJson:
    """Test HTTP request helper with retry logic."""

    @pytest.mark.asyncio
    async def test_request_json_success_get(self):
        """Should return JSON for successful GET request."""
        from core.solana_execution import _request_json

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"result": "ok"})

        with patch("core.solana_execution.HAS_AIOHTTP", True):
            with patch("aiohttp.ClientSession") as mock_session_cls:
                mock_session = AsyncMock()
                mock_session.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session.__aexit__ = AsyncMock(return_value=None)
                mock_session.get = MagicMock(return_value=AsyncMock(
                    __aenter__=AsyncMock(return_value=mock_response),
                    __aexit__=AsyncMock(return_value=None),
                ))
                mock_session_cls.return_value = mock_session

                result = await _request_json("GET", "https://api.test.com/endpoint")

                assert result == {"result": "ok"}

    @pytest.mark.asyncio
    async def test_request_json_no_aiohttp(self):
        """Should return None when aiohttp is not available."""
        from core.solana_execution import _request_json

        with patch("core.solana_execution.HAS_AIOHTTP", False):
            result = await _request_json("GET", "https://api.test.com")
            assert result is None

    @pytest.mark.asyncio
    async def test_request_json_returns_none_on_all_failures(self):
        """Should return None when all retries fail."""
        from core.solana_execution import _request_json

        with patch("core.solana_execution.HAS_AIOHTTP", True):
            with patch("aiohttp.ClientSession") as mock_session_cls:
                # Mock that raises an exception on creation
                mock_session_cls.side_effect = Exception("Connection failed")

                result = await _request_json(
                    "GET",
                    "https://api.test.com",
                    retries=2,
                    backoff_seconds=0.01,
                )

                # Should return None after failures
                assert result is None


# ==============================================================================
# RPC Health Check Tests
# ==============================================================================

class TestRpcHealth:
    """Test RPC endpoint health checking."""

    @pytest.mark.asyncio
    async def test_rpc_health_returns_true_when_healthy(self, mock_rpc_endpoint, reset_circuit_breakers):
        """Should return True for healthy endpoint."""
        from core.solana_execution import _rpc_health

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"result": "ok"})

        with patch("core.solana_execution.HAS_AIOHTTP", True):
            with patch("aiohttp.ClientSession") as mock_session_cls:
                mock_session = AsyncMock()
                mock_session.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session.__aexit__ = AsyncMock(return_value=None)
                mock_session.post = MagicMock(return_value=AsyncMock(
                    __aenter__=AsyncMock(return_value=mock_response),
                    __aexit__=AsyncMock(return_value=None),
                ))
                mock_session_cls.return_value = mock_session

                result = await _rpc_health(mock_rpc_endpoint)

                assert result is True

    @pytest.mark.asyncio
    async def test_rpc_health_returns_false_on_error(self, mock_rpc_endpoint, reset_circuit_breakers):
        """Should return False when health check fails."""
        from core.solana_execution import _rpc_health

        with patch("core.solana_execution.HAS_AIOHTTP", True):
            with patch("aiohttp.ClientSession") as mock_session_cls:
                mock_session = AsyncMock()
                mock_session.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session.__aexit__ = AsyncMock(return_value=None)
                mock_session.post = MagicMock(side_effect=Exception("Connection refused"))
                mock_session_cls.return_value = mock_session

                result = await _rpc_health(mock_rpc_endpoint)

                assert result is False

    @pytest.mark.asyncio
    async def test_rpc_health_uses_cache(self, mock_rpc_endpoint, reset_circuit_breakers):
        """Should use cached health check result."""
        from core.solana_execution import _rpc_health, _endpoint_health_cache

        # Pre-populate cache
        _endpoint_health_cache[mock_rpc_endpoint.url] = (True, time.time())

        with patch("core.solana_execution.HAS_AIOHTTP", True):
            # Should not make actual request due to cache
            result = await _rpc_health(mock_rpc_endpoint)

            assert result is True

    @pytest.mark.asyncio
    async def test_rpc_health_respects_circuit_breaker(self, mock_rpc_endpoint, reset_circuit_breakers):
        """Should return False when endpoint is circuit-broken."""
        from core.solana_execution import (
            _rpc_health,
            _mark_endpoint_failure,
            CIRCUIT_BREAKER_FAILURE_THRESHOLD,
        )

        # Trip circuit breaker
        for _ in range(CIRCUIT_BREAKER_FAILURE_THRESHOLD):
            _mark_endpoint_failure(mock_rpc_endpoint.url)

        with patch("core.solana_execution.HAS_AIOHTTP", True):
            result = await _rpc_health(mock_rpc_endpoint)

            assert result is False


class TestGetHealthyEndpoints:
    """Test parallel health checking of endpoints."""

    @pytest.mark.asyncio
    async def test_get_healthy_endpoints_filters_unhealthy(self, mock_endpoints_list, reset_circuit_breakers):
        """Should filter out unhealthy endpoints."""
        from core.solana_execution import get_healthy_endpoints

        # Mock _rpc_health to return different results
        health_results = {
            mock_endpoints_list[0].url: True,
            mock_endpoints_list[1].url: False,
            mock_endpoints_list[2].url: True,
        }

        async def mock_health(endpoint):
            return health_results.get(endpoint.url, False)

        with patch("core.solana_execution._rpc_health", side_effect=mock_health):
            healthy = await get_healthy_endpoints(mock_endpoints_list)

            assert len(healthy) == 2
            assert mock_endpoints_list[0] in healthy
            assert mock_endpoints_list[2] in healthy

    @pytest.mark.asyncio
    async def test_get_healthy_endpoints_returns_all_when_none_healthy(self, mock_endpoints_list, reset_circuit_breakers):
        """Should return all available endpoints when none are healthy."""
        from core.solana_execution import get_healthy_endpoints

        async def mock_health(endpoint):
            return False

        with patch("core.solana_execution._rpc_health", side_effect=mock_health):
            healthy = await get_healthy_endpoints(mock_endpoints_list)

            # Should return all available as fallback
            assert len(healthy) == len(mock_endpoints_list)


# ==============================================================================
# Jupiter API Tests
# ==============================================================================

class TestGetSwapQuote:
    """Test Jupiter swap quote retrieval."""

    @pytest.mark.asyncio
    async def test_get_swap_quote_success(self, mock_swap_quote):
        """Should return quote on success."""
        from core.solana_execution import get_swap_quote

        with patch("core.solana_execution._request_json") as mock_request:
            mock_request.return_value = mock_swap_quote

            result = await get_swap_quote(
                input_mint="So11111111111111111111111111111111111111112",
                output_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                amount=1000000000,
            )

            assert result is not None
            assert result["inputMint"] == "So11111111111111111111111111111111111111112"

    @pytest.mark.asyncio
    async def test_get_swap_quote_no_aiohttp(self):
        """Should return None when aiohttp is not available."""
        from core.solana_execution import get_swap_quote

        with patch("core.solana_execution.HAS_AIOHTTP", False):
            result = await get_swap_quote(
                input_mint="So11111111111111111111111111111111111111112",
                output_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                amount=1000000000,
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_get_swap_quote_failure(self):
        """Should return None on request failure."""
        from core.solana_execution import get_swap_quote

        with patch("core.solana_execution._request_json") as mock_request:
            mock_request.return_value = None

            result = await get_swap_quote(
                input_mint="So11111111111111111111111111111111111111112",
                output_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                amount=1000000000,
            )

            assert result is None


class TestGetSwapTransaction:
    """Test Jupiter swap transaction retrieval."""

    @pytest.mark.asyncio
    async def test_get_swap_transaction_success(self, mock_swap_quote):
        """Should return transaction on success."""
        from core.solana_execution import get_swap_transaction

        with patch("core.solana_execution._request_json") as mock_request:
            mock_request.return_value = {"swapTransaction": "base64_encoded_tx"}

            result = await get_swap_transaction(
                quote=mock_swap_quote,
                user_public_key="TestWalletAddress123",
            )

            assert result == "base64_encoded_tx"

    @pytest.mark.asyncio
    async def test_get_swap_transaction_no_aiohttp(self, mock_swap_quote):
        """Should return None when aiohttp is not available."""
        from core.solana_execution import get_swap_transaction

        with patch("core.solana_execution.HAS_AIOHTTP", False):
            result = await get_swap_transaction(
                quote=mock_swap_quote,
                user_public_key="TestWalletAddress123",
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_get_swap_transaction_failure(self, mock_swap_quote):
        """Should return None on request failure."""
        from core.solana_execution import get_swap_transaction

        with patch("core.solana_execution._request_json") as mock_request:
            mock_request.return_value = None

            result = await get_swap_transaction(
                quote=mock_swap_quote,
                user_public_key="TestWalletAddress123",
            )

            assert result is None


# ==============================================================================
# Transaction Confirmation Tests
# ==============================================================================

class TestConfirmSignature:
    """Test transaction signature confirmation."""

    @pytest.mark.asyncio
    async def test_confirm_signature_success(self):
        """Should return True when transaction is confirmed."""
        from core.solana_execution import _confirm_signature

        mock_client = AsyncMock()
        mock_value = MagicMock()
        mock_value.err = None
        mock_value.confirmation_status = "confirmed"
        mock_client.get_signature_statuses = AsyncMock(return_value=MagicMock(value=[mock_value]))

        success, error = await _confirm_signature(
            mock_client,
            "test_signature_123",
            timeout_seconds=1,
        )

        assert success is True
        assert error is None

    @pytest.mark.asyncio
    async def test_confirm_signature_finalized(self):
        """Should return True when transaction is finalized."""
        from core.solana_execution import _confirm_signature

        mock_client = AsyncMock()
        mock_value = MagicMock()
        mock_value.err = None
        mock_value.confirmation_status = "finalized"
        mock_client.get_signature_statuses = AsyncMock(return_value=MagicMock(value=[mock_value]))

        success, error = await _confirm_signature(
            mock_client,
            "test_signature_123",
            timeout_seconds=1,
        )

        assert success is True
        assert error is None

    @pytest.mark.asyncio
    async def test_confirm_signature_with_error(self):
        """Should return False with error when transaction fails."""
        from core.solana_execution import _confirm_signature

        mock_client = AsyncMock()
        mock_value = MagicMock()
        mock_value.err = "InsufficientFunds"
        mock_value.confirmation_status = None
        mock_client.get_signature_statuses = AsyncMock(return_value=MagicMock(value=[mock_value]))

        success, error = await _confirm_signature(
            mock_client,
            "test_signature_123",
            timeout_seconds=1,
        )

        assert success is False
        assert error is not None

    @pytest.mark.asyncio
    async def test_confirm_signature_timeout(self):
        """Should return False on timeout."""
        from core.solana_execution import _confirm_signature

        mock_client = AsyncMock()
        # Return pending status (no confirmation)
        mock_value = MagicMock()
        mock_value.err = None
        mock_value.confirmation_status = "processed"  # Not yet confirmed
        mock_client.get_signature_statuses = AsyncMock(return_value=MagicMock(value=[mock_value]))

        success, error = await _confirm_signature(
            mock_client,
            "test_signature_123",
            commitment="confirmed",
            timeout_seconds=0.1,  # Very short timeout
            poll_interval=0.05,
        )

        assert success is False
        assert error == "confirmation_timeout"


# ==============================================================================
# Get Recent Blockhash Tests
# ==============================================================================

class TestGetRecentBlockhash:
    """Test recent blockhash retrieval."""

    @pytest.mark.asyncio
    async def test_get_recent_blockhash_success(self, mock_endpoints_list, reset_circuit_breakers):
        """Should return blockhash and last valid block height."""
        from core.solana_execution import get_recent_blockhash

        mock_blockhash = MagicMock()
        mock_blockhash.blockhash = "TestBlockhash123456789"
        mock_blockhash.last_valid_block_height = 12345678

        mock_client = AsyncMock()
        mock_client.get_latest_blockhash = AsyncMock(return_value=MagicMock(value=mock_blockhash))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("core.solana_execution.HAS_SOLANA", True):
            with patch("core.solana_execution.get_healthy_endpoints") as mock_healthy:
                mock_healthy.return_value = mock_endpoints_list
                with patch("core.solana_execution.AsyncClient") as mock_async_client:
                    mock_async_client.return_value = mock_client

                    result = await get_recent_blockhash(mock_endpoints_list)

                    assert result is not None
                    blockhash, last_valid = result
                    assert blockhash == "TestBlockhash123456789"
                    assert last_valid == 12345678

    @pytest.mark.asyncio
    async def test_get_recent_blockhash_no_solana(self, mock_endpoints_list):
        """Should return None when solana SDK is not available."""
        from core.solana_execution import get_recent_blockhash

        with patch("core.solana_execution.HAS_SOLANA", False):
            result = await get_recent_blockhash(mock_endpoints_list)
            assert result is None

    @pytest.mark.asyncio
    async def test_get_recent_blockhash_all_fail(self, mock_endpoints_list, reset_circuit_breakers):
        """Should return None when all endpoints fail."""
        from core.solana_execution import get_recent_blockhash

        mock_client = AsyncMock()
        mock_client.get_latest_blockhash = AsyncMock(side_effect=Exception("RPC Error"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("core.solana_execution.HAS_SOLANA", True):
            with patch("core.solana_execution.get_healthy_endpoints") as mock_healthy:
                mock_healthy.return_value = mock_endpoints_list
                with patch("core.solana_execution.AsyncClient") as mock_async_client:
                    mock_async_client.return_value = mock_client

                    result = await get_recent_blockhash(mock_endpoints_list)

                    assert result is None


# ==============================================================================
# Execute Swap Transaction Tests
# ==============================================================================

class TestExecuteSwapTransaction:
    """Test swap transaction execution with failover."""

    @pytest.mark.asyncio
    async def test_execute_swap_no_solana_sdk(self, mock_versioned_transaction, mock_endpoints_list):
        """Should return error when Solana SDK is not available."""
        from core.solana_execution import execute_swap_transaction

        with patch("core.solana_execution.HAS_SOLANA", False):
            result = await execute_swap_transaction(
                mock_versioned_transaction,
                mock_endpoints_list,
            )

            assert result.success is False
            assert result.error == "solana_sdk_missing"
            assert result.retryable is False

    @pytest.mark.asyncio
    async def test_execute_swap_gnosis_safe_check_fails(self, mock_versioned_transaction, mock_endpoints_list):
        """Should return error when Gnosis Safe check fails."""
        from core.solana_execution import execute_swap_transaction

        with patch("core.solana_execution.HAS_SOLANA", True):
            with patch("core.solana_execution.require_poly_gnosis_safe") as mock_gnosis:
                mock_gnosis.return_value = (False, "gnosis_safe_missing")

                result = await execute_swap_transaction(
                    mock_versioned_transaction,
                    mock_endpoints_list,
                )

                assert result.success is False
                assert "gnosis_safe_missing" in result.error
                assert result.retryable is False

    @pytest.mark.asyncio
    async def test_execute_swap_no_healthy_endpoints(self, mock_versioned_transaction, mock_endpoints_list, reset_circuit_breakers):
        """Should return error when no healthy endpoints available."""
        from core.solana_execution import execute_swap_transaction

        with patch("core.solana_execution.HAS_SOLANA", True):
            with patch("core.solana_execution.require_poly_gnosis_safe") as mock_gnosis:
                mock_gnosis.return_value = (True, None)
                with patch("core.solana_execution.get_healthy_endpoints") as mock_healthy:
                    mock_healthy.return_value = []

                    result = await execute_swap_transaction(
                        mock_versioned_transaction,
                        mock_endpoints_list,
                    )

                    assert result.success is False
                    assert result.error == "no_healthy_endpoints"
                    assert result.retryable is True

    @pytest.mark.asyncio
    async def test_execute_swap_success(self, mock_versioned_transaction, mock_endpoints_list, reset_circuit_breakers):
        """Should return success when transaction confirms."""
        from core.solana_execution import execute_swap_transaction

        mock_sim = MagicMock()
        mock_sim.value = MagicMock()
        mock_sim.value.err = None

        mock_send = MagicMock()
        mock_send.value = "tx_signature_123"

        mock_client = AsyncMock()
        mock_client.simulate_transaction = AsyncMock(return_value=mock_sim)
        mock_client.send_transaction = AsyncMock(return_value=mock_send)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        # Create a mock context manager for AsyncClient
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        with patch("core.solana_execution.HAS_SOLANA", True):
            with patch("core.solana_execution.require_poly_gnosis_safe") as mock_gnosis:
                mock_gnosis.return_value = (True, None)
                with patch("core.solana_execution.get_healthy_endpoints") as mock_healthy:
                    mock_healthy.return_value = mock_endpoints_list[:1]
                    with patch("core.solana_execution.AsyncClient") as mock_async_client:
                        mock_async_client.return_value = mock_cm
                        with patch("core.solana_execution.TxOpts") as mock_tx_opts:
                            mock_tx_opts.return_value = MagicMock()
                            with patch("core.solana_execution._confirm_signature") as mock_confirm:
                                mock_confirm.return_value = (True, None)

                                result = await execute_swap_transaction(
                                    mock_versioned_transaction,
                                    mock_endpoints_list,
                                )

                                assert result.success is True
                                assert result.signature == "tx_signature_123"

    @pytest.mark.asyncio
    async def test_execute_swap_simulation_permanent_error(self, mock_versioned_transaction, mock_endpoints_list, reset_circuit_breakers):
        """Should return permanent error without retrying."""
        from core.solana_execution import execute_swap_transaction

        mock_sim = MagicMock()
        mock_sim.value = MagicMock()
        mock_sim.value.err = "InsufficientFunds"

        mock_client = AsyncMock()
        mock_client.simulate_transaction = AsyncMock(return_value=mock_sim)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        # Create a mock context manager for AsyncClient
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        with patch("core.solana_execution.HAS_SOLANA", True):
            with patch("core.solana_execution.require_poly_gnosis_safe") as mock_gnosis:
                mock_gnosis.return_value = (True, None)
                with patch("core.solana_execution.get_healthy_endpoints") as mock_healthy:
                    mock_healthy.return_value = mock_endpoints_list[:1]
                    with patch("core.solana_execution.AsyncClient") as mock_async_client:
                        mock_async_client.return_value = mock_cm

                        result = await execute_swap_transaction(
                            mock_versioned_transaction,
                            mock_endpoints_list,
                        )

                        assert result.success is False
                        assert result.error == "simulation_failed"
                        assert result.retryable is False

    @pytest.mark.asyncio
    async def test_execute_swap_blockhash_refresh(self, mock_versioned_transaction, mock_endpoints_list, reset_circuit_breakers):
        """Should refresh blockhash on expiry error."""
        from core.solana_execution import execute_swap_transaction

        call_count = 0

        mock_sim_fail = MagicMock()
        mock_sim_fail.value = MagicMock()
        mock_sim_fail.value.err = "BlockhashNotFound"

        mock_sim_ok = MagicMock()
        mock_sim_ok.value = MagicMock()
        mock_sim_ok.value.err = None

        mock_send = MagicMock()
        mock_send.value = "tx_signature_123"

        async def mock_simulate(tx):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_sim_fail
            return mock_sim_ok

        mock_client = AsyncMock()
        mock_client.simulate_transaction = mock_simulate
        mock_client.send_transaction = AsyncMock(return_value=mock_send)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        # Create a mock context manager for AsyncClient
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        refreshed_tx = MagicMock()
        refresh_fn = MagicMock(return_value=refreshed_tx)

        with patch("core.solana_execution.HAS_SOLANA", True):
            with patch("core.solana_execution.require_poly_gnosis_safe") as mock_gnosis:
                mock_gnosis.return_value = (True, None)
                with patch("core.solana_execution.get_healthy_endpoints") as mock_healthy:
                    mock_healthy.return_value = mock_endpoints_list[:1]
                    with patch("core.solana_execution.AsyncClient") as mock_async_client:
                        mock_async_client.return_value = mock_cm
                        with patch("core.solana_execution.TxOpts") as mock_tx_opts:
                            mock_tx_opts.return_value = MagicMock()
                            with patch("core.solana_execution._confirm_signature") as mock_confirm:
                                mock_confirm.return_value = (True, None)

                                result = await execute_swap_transaction(
                                    mock_versioned_transaction,
                                    mock_endpoints_list,
                                    refresh_signed_tx=refresh_fn,
                                )

                                # Refresh function should have been called
                                refresh_fn.assert_called()
                                assert result.success is True


# ==============================================================================
# Simulate Transaction Tests
# ==============================================================================

class TestSimulateTransaction:
    """Test transaction simulation."""

    @pytest.mark.asyncio
    async def test_simulate_transaction_no_solana(self, mock_versioned_transaction, mock_endpoints_list):
        """Should return error when Solana SDK is not available."""
        from core.solana_execution import simulate_transaction

        with patch("core.solana_execution.HAS_SOLANA", False):
            result = await simulate_transaction(
                mock_versioned_transaction,
                mock_endpoints_list,
            )

            assert result.success is False
            assert result.error == "solana_sdk_missing"

    @pytest.mark.asyncio
    async def test_simulate_transaction_success(self, mock_versioned_transaction, mock_endpoints_list, reset_circuit_breakers):
        """Should return success for successful simulation."""
        from core.solana_execution import simulate_transaction

        mock_sim = MagicMock()
        mock_sim.value = MagicMock()
        mock_sim.value.err = None

        mock_client = AsyncMock()
        mock_client.simulate_transaction = AsyncMock(return_value=mock_sim)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        # Create a mock context manager for AsyncClient
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        with patch("core.solana_execution.HAS_SOLANA", True):
            with patch("core.solana_execution.get_healthy_endpoints") as mock_healthy:
                mock_healthy.return_value = mock_endpoints_list[:1]
                with patch("core.solana_execution.AsyncClient") as mock_async_client:
                    mock_async_client.return_value = mock_cm

                    result = await simulate_transaction(
                        mock_versioned_transaction,
                        mock_endpoints_list,
                    )

                    assert result.success is True

    @pytest.mark.asyncio
    async def test_simulate_transaction_failure(self, mock_versioned_transaction, mock_endpoints_list, reset_circuit_breakers):
        """Should return error for failed simulation."""
        from core.solana_execution import simulate_transaction

        mock_sim = MagicMock()
        mock_sim.value = MagicMock()
        mock_sim.value.err = "InvalidAccountData"

        mock_client = AsyncMock()
        mock_client.simulate_transaction = AsyncMock(return_value=mock_sim)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        # Create a mock context manager for AsyncClient
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        with patch("core.solana_execution.HAS_SOLANA", True):
            with patch("core.solana_execution.get_healthy_endpoints") as mock_healthy:
                mock_healthy.return_value = mock_endpoints_list[:1]
                with patch("core.solana_execution.AsyncClient") as mock_async_client:
                    mock_async_client.return_value = mock_cm

                    result = await simulate_transaction(
                        mock_versioned_transaction,
                        mock_endpoints_list,
                    )

                    assert result.success is False
                    assert result.error == "simulation_failed"
                    assert result.simulation_error == "InvalidAccountData"


# ==============================================================================
# Endpoint Status Tests
# ==============================================================================

class TestGetEndpointStatus:
    """Test endpoint status reporting."""

    @pytest.mark.asyncio
    async def test_get_endpoint_status_returns_status_dict(self, reset_circuit_breakers):
        """Should return status dictionary with all endpoints."""
        from core.solana_execution import get_endpoint_status, RpcEndpoint

        mock_endpoints = [
            RpcEndpoint(name="primary", url="https://primary.com", rate_limit=100),
            RpcEndpoint(name="fallback", url="https://fallback.com", rate_limit=50),
        ]

        with patch("core.solana_execution.load_solana_rpc_endpoints") as mock_load:
            mock_load.return_value = mock_endpoints
            with patch("core.solana_execution._rpc_health") as mock_health:
                mock_health.side_effect = [True, False]

                status = await get_endpoint_status()

                assert "endpoints" in status
                assert "total" in status
                assert "healthy" in status
                assert "available" in status
                assert status["total"] == 2
                assert status["healthy"] == 1

    @pytest.mark.asyncio
    async def test_get_endpoint_status_includes_failure_counts(self, reset_circuit_breakers):
        """Should include failure counts in status."""
        from core.solana_execution import (
            get_endpoint_status,
            RpcEndpoint,
            _mark_endpoint_failure,
        )

        mock_endpoints = [
            RpcEndpoint(name="primary", url="https://primary.com", rate_limit=100),
        ]

        _mark_endpoint_failure(mock_endpoints[0].url)
        _mark_endpoint_failure(mock_endpoints[0].url)

        with patch("core.solana_execution.load_solana_rpc_endpoints") as mock_load:
            mock_load.return_value = mock_endpoints
            with patch("core.solana_execution._rpc_health") as mock_health:
                mock_health.return_value = True

                status = await get_endpoint_status()

                assert status["endpoints"][0]["failures"] == 2


# ==============================================================================
# Edge Cases and Error Handling Tests
# ==============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_describe_simulation_error_case_insensitive(self):
        """Error description should be case-insensitive."""
        from core.solana_execution import describe_simulation_error

        assert describe_simulation_error("INSUFFICIENTFUNDS") is not None
        assert describe_simulation_error("insufficientfunds") is not None
        assert describe_simulation_error("InsufficientFunds") is not None

    def test_classify_simulation_error_case_insensitive(self):
        """Error classification should be case-insensitive."""
        from core.solana_execution import classify_simulation_error

        assert classify_simulation_error("BLOCKHASH") == "retryable"
        assert classify_simulation_error("blockhash") == "retryable"
        assert classify_simulation_error("Blockhash") == "retryable"

    def test_empty_string_error(self):
        """Should handle empty string errors gracefully."""
        from core.solana_execution import (
            describe_simulation_error,
            classify_simulation_error,
            _is_blockhash_expired,
        )

        # Empty strings should be treated as no error
        assert describe_simulation_error("") is None
        assert classify_simulation_error("") == "unknown"
        assert _is_blockhash_expired("") is False

    @pytest.mark.asyncio
    async def test_execute_swap_handles_timeout(self, mock_versioned_transaction, mock_endpoints_list, reset_circuit_breakers):
        """Should handle timeout errors gracefully."""
        from core.solana_execution import execute_swap_transaction

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_client.__aexit__ = AsyncMock(return_value=None)

        # Create a mock context manager for AsyncClient that raises TimeoutError
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        with patch("core.solana_execution.HAS_SOLANA", True):
            with patch("core.solana_execution.require_poly_gnosis_safe") as mock_gnosis:
                mock_gnosis.return_value = (True, None)
                with patch("core.solana_execution.get_healthy_endpoints") as mock_healthy:
                    mock_healthy.return_value = mock_endpoints_list[:1]
                    with patch("core.solana_execution.AsyncClient") as mock_async_client:
                        mock_async_client.return_value = mock_cm

                        result = await execute_swap_transaction(
                            mock_versioned_transaction,
                            mock_endpoints_list,
                            max_retries=1,
                            retry_delay=0.01,
                        )

                        assert result.success is False
                        assert result.error == "timeout"


class TestConstants:
    """Test module constants are properly defined."""

    def test_jupiter_api_endpoints(self):
        """Jupiter API endpoints should be properly defined."""
        from core.solana_execution import JUPITER_QUOTE_API, JUPITER_SWAP_API

        assert "jupiterapi.com" in JUPITER_QUOTE_API or "jup.ag" in JUPITER_QUOTE_API
        assert "quote" in JUPITER_QUOTE_API
        assert "swap" in JUPITER_SWAP_API

    def test_solana_mints(self):
        """SOL and USDC mint addresses should be valid."""
        from core.solana_execution import SOL_MINT, USDC_MINT

        # SOL wrapped token address
        assert SOL_MINT == "So11111111111111111111111111111111111111112"
        # USDC on Solana
        assert USDC_MINT == "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

    def test_circuit_breaker_constants(self):
        """Circuit breaker constants should have sensible values."""
        from core.solana_execution import (
            CIRCUIT_BREAKER_FAILURE_THRESHOLD,
            CIRCUIT_BREAKER_RECOVERY_SECONDS,
            RPC_HEALTH_CACHE_SECONDS,
        )

        assert CIRCUIT_BREAKER_FAILURE_THRESHOLD >= 1
        assert CIRCUIT_BREAKER_RECOVERY_SECONDS >= 10
        assert RPC_HEALTH_CACHE_SECONDS >= 1
