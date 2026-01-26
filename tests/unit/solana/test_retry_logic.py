"""
Unit tests for Solana Transaction Retry Logic.

Tests cover:
1. Blockhash caching and smart refresh timing
2. Exponential backoff with jitter
3. Error classification (retryable vs non-retryable)
4. Retry strategy (immediate, 1s+jitter, 2s+jitter, 4s+jitter)
5. Metrics tracking for retry counts
6. Integration with existing transaction operations
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


# =============================================================================
# Test: Error Classification
# =============================================================================

class TestErrorClassification:
    """Test error classification for retry decisions."""

    def test_blockhash_expired_is_retryable(self):
        """Blockhash expired errors should be retryable."""
        from core.solana.retry_logic import classify_error, ErrorCategory

        errors = [
            "BlockhashNotFound",
            "blockhash not found",
            "Blockhash expired",
            "Transaction's blockhash has expired",
        ]

        for error in errors:
            category = classify_error(error)
            assert category == ErrorCategory.RETRYABLE_BLOCKHASH, f"Expected RETRYABLE_BLOCKHASH for: {error}"

    def test_rpc_timeout_is_retryable(self):
        """RPC timeout errors should be retryable."""
        from core.solana.retry_logic import classify_error, ErrorCategory

        errors = [
            "timeout",
            "Request timed out",
            "Connection timeout",
        ]

        for error in errors:
            category = classify_error(error)
            assert category == ErrorCategory.RETRYABLE_NETWORK, f"Expected RETRYABLE_NETWORK for: {error}"

    def test_rate_limit_is_retryable(self):
        """Rate limit errors should be retryable."""
        from core.solana.retry_logic import classify_error, ErrorCategory

        errors = [
            "429 Too Many Requests",
            "Rate limit exceeded",
            "503 Service Unavailable",
        ]

        for error in errors:
            category = classify_error(error)
            assert category == ErrorCategory.RETRYABLE_NETWORK, f"Expected RETRYABLE_NETWORK for: {error}"

    def test_insufficient_funds_is_permanent(self):
        """Insufficient funds errors should be permanent."""
        from core.solana.retry_logic import classify_error, ErrorCategory

        errors = [
            "InsufficientFunds",
            "insufficient funds for fee",
            "Insufficient balance",
        ]

        for error in errors:
            category = classify_error(error)
            assert category == ErrorCategory.PERMANENT, f"Expected PERMANENT for: {error}"

    def test_invalid_signature_is_permanent(self):
        """Invalid signature errors should be permanent."""
        from core.solana.retry_logic import classify_error, ErrorCategory

        errors = [
            "SignatureVerificationFailed",
            "Invalid signature",
            "Signature verification failed",
        ]

        for error in errors:
            category = classify_error(error)
            assert category == ErrorCategory.PERMANENT, f"Expected PERMANENT for: {error}"

    def test_already_processed_is_permanent(self):
        """Already processed transaction should be permanent."""
        from core.solana.retry_logic import classify_error, ErrorCategory

        category = classify_error("AlreadyProcessed")
        assert category == ErrorCategory.PERMANENT

    def test_unknown_error_is_unknown(self):
        """Unknown errors should be classified as unknown."""
        from core.solana.retry_logic import classify_error, ErrorCategory

        category = classify_error("Some random error")
        assert category == ErrorCategory.UNKNOWN


# =============================================================================
# Test: Blockhash Cache
# =============================================================================

class TestBlockhashCache:
    """Test smart blockhash caching and refresh timing."""

    @pytest.fixture
    def mock_rpc_client(self):
        """Create a mock RPC client for blockhash fetching."""
        client = AsyncMock()
        mock_response = MagicMock()
        mock_response.value = MagicMock()
        mock_response.value.blockhash = "TestBlockhash123456789"
        mock_response.value.last_valid_block_height = 200000000
        client.get_latest_blockhash.return_value = mock_response
        return client

    @pytest.mark.asyncio
    async def test_blockhash_cache_stores_blockhash(self, mock_rpc_client):
        """Test that blockhash cache stores fetched blockhash."""
        from core.solana.retry_logic import BlockhashCache

        cache = BlockhashCache(rpc_client=mock_rpc_client)
        blockhash, last_valid = await cache.get_blockhash()

        assert blockhash == "TestBlockhash123456789"
        assert last_valid == 200000000

    @pytest.mark.asyncio
    async def test_blockhash_cache_returns_cached_if_valid(self, mock_rpc_client):
        """Test that cache returns cached blockhash if still valid (>75%)."""
        from core.solana.retry_logic import BlockhashCache

        cache = BlockhashCache(rpc_client=mock_rpc_client, validity_threshold=0.75)

        # First call fetches from RPC
        await cache.get_blockhash()
        mock_rpc_client.get_latest_blockhash.assert_called_once()

        # Second call should use cache (blockhash still >75% valid)
        await cache.get_blockhash()
        assert mock_rpc_client.get_latest_blockhash.call_count == 1

    @pytest.mark.asyncio
    async def test_blockhash_cache_refreshes_when_expired(self, mock_rpc_client):
        """Test that cache refreshes blockhash when validity drops below threshold."""
        from core.solana.retry_logic import BlockhashCache

        cache = BlockhashCache(rpc_client=mock_rpc_client, validity_threshold=0.75)

        # First call
        await cache.get_blockhash()

        # Simulate blockhash aging past threshold
        cache._fetch_time = time.time() - 200  # Old enough to be < 75% valid

        # Should fetch new blockhash
        await cache.get_blockhash()
        assert mock_rpc_client.get_latest_blockhash.call_count == 2

    @pytest.mark.asyncio
    async def test_blockhash_validity_percentage(self, mock_rpc_client):
        """Test calculating blockhash validity percentage."""
        from core.solana.retry_logic import BlockhashCache

        cache = BlockhashCache(rpc_client=mock_rpc_client)
        await cache.get_blockhash()

        # Immediately after fetch, should be ~100% valid
        validity = cache.get_validity_percentage()
        assert validity >= 0.95  # Allow some time for test execution

    @pytest.mark.asyncio
    async def test_force_refresh_bypasses_cache(self, mock_rpc_client):
        """Test that force_refresh bypasses the cache."""
        from core.solana.retry_logic import BlockhashCache

        cache = BlockhashCache(rpc_client=mock_rpc_client)

        await cache.get_blockhash()
        await cache.get_blockhash(force_refresh=True)

        assert mock_rpc_client.get_latest_blockhash.call_count == 2


# =============================================================================
# Test: Exponential Backoff
# =============================================================================

class TestExponentialBackoff:
    """Test exponential backoff with jitter."""

    def test_immediate_first_attempt(self):
        """First attempt should be immediate (0 delay)."""
        from core.solana.retry_logic import calculate_backoff

        delay = calculate_backoff(attempt=0)
        assert delay == 0.0

    def test_second_attempt_has_delay(self):
        """Second attempt should have ~1s base delay."""
        from core.solana.retry_logic import calculate_backoff

        # Multiple runs to account for jitter
        delays = [calculate_backoff(attempt=1) for _ in range(100)]

        # Should be around 1s +/- jitter
        avg_delay = sum(delays) / len(delays)
        assert 0.8 <= avg_delay <= 1.5

    def test_third_attempt_has_increased_delay(self):
        """Third attempt should have ~2s base delay."""
        from core.solana.retry_logic import calculate_backoff

        delays = [calculate_backoff(attempt=2) for _ in range(100)]
        avg_delay = sum(delays) / len(delays)
        assert 1.5 <= avg_delay <= 3.0

    def test_fourth_attempt_has_maximum_delay(self):
        """Fourth attempt should have ~4s base delay."""
        from core.solana.retry_logic import calculate_backoff

        delays = [calculate_backoff(attempt=3) for _ in range(100)]
        avg_delay = sum(delays) / len(delays)
        assert 3.0 <= avg_delay <= 5.5

    def test_jitter_adds_randomness(self):
        """Jitter should add randomness to delays."""
        from core.solana.retry_logic import calculate_backoff

        delays = [calculate_backoff(attempt=2) for _ in range(100)]

        # Should have variance (not all the same)
        unique_delays = set(delays)
        assert len(unique_delays) > 1

    def test_max_delay_cap(self):
        """Delay should be capped at max_delay."""
        from core.solana.retry_logic import calculate_backoff

        delay = calculate_backoff(attempt=10, max_delay=5.0)
        assert delay <= 5.5  # Jitter can add up to 10%


# =============================================================================
# Test: Retry Strategy
# =============================================================================

class TestRetryStrategy:
    """Test the retry strategy configuration."""

    def test_max_retries_default(self):
        """Default max retries should be 3."""
        from core.solana.retry_logic import RetryStrategy

        strategy = RetryStrategy()
        assert strategy.max_retries == 3

    def test_retry_strategy_for_blockhash_error(self):
        """Blockhash errors should allow retries with refresh."""
        from core.solana.retry_logic import RetryStrategy, ErrorCategory

        strategy = RetryStrategy()
        should_retry, refresh_blockhash = strategy.should_retry(
            attempt=1,
            error_category=ErrorCategory.RETRYABLE_BLOCKHASH
        )

        assert should_retry is True
        assert refresh_blockhash is True

    def test_retry_strategy_for_network_error(self):
        """Network errors should allow retries without blockhash refresh."""
        from core.solana.retry_logic import RetryStrategy, ErrorCategory

        strategy = RetryStrategy()
        should_retry, refresh_blockhash = strategy.should_retry(
            attempt=1,
            error_category=ErrorCategory.RETRYABLE_NETWORK
        )

        assert should_retry is True
        assert refresh_blockhash is False

    def test_retry_strategy_for_permanent_error(self):
        """Permanent errors should not allow retries."""
        from core.solana.retry_logic import RetryStrategy, ErrorCategory

        strategy = RetryStrategy()
        should_retry, _ = strategy.should_retry(
            attempt=0,
            error_category=ErrorCategory.PERMANENT
        )

        assert should_retry is False

    def test_retry_strategy_respects_max_retries(self):
        """Should not retry beyond max attempts."""
        from core.solana.retry_logic import RetryStrategy, ErrorCategory

        strategy = RetryStrategy(max_retries=3)

        # Attempt 3 (0-indexed) should be the last attempt
        should_retry, _ = strategy.should_retry(
            attempt=3,
            error_category=ErrorCategory.RETRYABLE_NETWORK
        )

        assert should_retry is False


# =============================================================================
# Test: Retry Metrics
# =============================================================================

class TestRetryMetrics:
    """Test retry metrics tracking."""

    def test_metrics_initialized_to_zero(self):
        """Metrics should be initialized to zero."""
        from core.solana.retry_logic import RetryMetrics

        metrics = RetryMetrics()

        assert metrics.total_attempts == 0
        assert metrics.successful_attempts == 0
        assert metrics.blockhash_refreshes == 0
        assert metrics.permanent_failures == 0

    def test_metrics_record_attempt(self):
        """Test recording a retry attempt."""
        from core.solana.retry_logic import RetryMetrics

        metrics = RetryMetrics()
        metrics.record_attempt(success=False)

        assert metrics.total_attempts == 1
        assert metrics.successful_attempts == 0

    def test_metrics_record_success(self):
        """Test recording a successful attempt."""
        from core.solana.retry_logic import RetryMetrics

        metrics = RetryMetrics()
        metrics.record_attempt(success=True)

        assert metrics.total_attempts == 1
        assert metrics.successful_attempts == 1

    def test_metrics_record_blockhash_refresh(self):
        """Test recording blockhash refresh."""
        from core.solana.retry_logic import RetryMetrics

        metrics = RetryMetrics()
        metrics.record_blockhash_refresh()

        assert metrics.blockhash_refreshes == 1

    def test_metrics_success_rate(self):
        """Test calculating success rate."""
        from core.solana.retry_logic import RetryMetrics

        metrics = RetryMetrics()
        metrics.record_attempt(success=True)
        metrics.record_attempt(success=True)
        metrics.record_attempt(success=False)

        assert metrics.success_rate == pytest.approx(2/3, rel=0.01)

    def test_metrics_to_dict(self):
        """Test exporting metrics to dict."""
        from core.solana.retry_logic import RetryMetrics

        metrics = RetryMetrics()
        metrics.record_attempt(success=True)

        d = metrics.to_dict()

        assert "total_attempts" in d
        assert "successful_attempts" in d
        assert "blockhash_refreshes" in d
        assert "success_rate" in d


# =============================================================================
# Test: TransactionRetryExecutor
# =============================================================================

class TestTransactionRetryExecutor:
    """Test the main retry executor."""

    @pytest.fixture
    def mock_rpc_client(self):
        """Create a mock RPC client."""
        client = AsyncMock()
        # Mock blockhash
        blockhash_response = MagicMock()
        blockhash_response.value = MagicMock()
        blockhash_response.value.blockhash = "TestBlockhash123"
        blockhash_response.value.last_valid_block_height = 200000000
        client.get_latest_blockhash.return_value = blockhash_response
        return client

    @pytest.mark.asyncio
    async def test_executor_succeeds_on_first_attempt(self, mock_rpc_client):
        """Test executor succeeds on first attempt."""
        from core.solana.retry_logic import TransactionRetryExecutor

        # Mock successful send
        send_response = MagicMock()
        send_response.value = "signature123"
        mock_rpc_client.send_transaction.return_value = send_response

        executor = TransactionRetryExecutor(rpc_client=mock_rpc_client)
        mock_tx = MagicMock()

        result = await executor.execute_with_retry(mock_tx)

        assert result.success is True
        assert result.signature == "signature123"
        assert result.attempts == 1

    @pytest.mark.asyncio
    async def test_executor_retries_on_blockhash_error(self, mock_rpc_client):
        """Test executor retries on blockhash expired error."""
        from core.solana.retry_logic import TransactionRetryExecutor

        # First call fails with blockhash error, second succeeds
        send_response = MagicMock()
        send_response.value = "signature123"
        mock_rpc_client.send_transaction.side_effect = [
            Exception("BlockhashNotFound"),
            send_response,
        ]

        executor = TransactionRetryExecutor(rpc_client=mock_rpc_client)
        mock_tx = MagicMock()

        result = await executor.execute_with_retry(mock_tx)

        assert result.success is True
        assert result.attempts == 2

    @pytest.mark.asyncio
    async def test_executor_stops_on_permanent_error(self, mock_rpc_client):
        """Test executor stops immediately on permanent error."""
        from core.solana.retry_logic import TransactionRetryExecutor

        mock_rpc_client.send_transaction.side_effect = Exception("InsufficientFunds")

        executor = TransactionRetryExecutor(rpc_client=mock_rpc_client)
        mock_tx = MagicMock()

        result = await executor.execute_with_retry(mock_tx)

        assert result.success is False
        assert result.attempts == 1
        assert "InsufficientFunds" in result.error

    @pytest.mark.asyncio
    async def test_executor_respects_max_retries(self, mock_rpc_client):
        """Test executor respects maximum retry count."""
        from core.solana.retry_logic import TransactionRetryExecutor, RetryStrategy

        mock_rpc_client.send_transaction.side_effect = Exception("timeout")

        strategy = RetryStrategy(max_retries=2)
        executor = TransactionRetryExecutor(
            rpc_client=mock_rpc_client,
            retry_strategy=strategy
        )
        mock_tx = MagicMock()

        result = await executor.execute_with_retry(mock_tx)

        assert result.success is False
        assert result.attempts <= 3  # Initial + 2 retries

    @pytest.mark.asyncio
    async def test_executor_tracks_metrics(self, mock_rpc_client):
        """Test executor tracks retry metrics."""
        from core.solana.retry_logic import TransactionRetryExecutor

        send_response = MagicMock()
        send_response.value = "signature123"
        mock_rpc_client.send_transaction.return_value = send_response

        executor = TransactionRetryExecutor(rpc_client=mock_rpc_client)
        mock_tx = MagicMock()

        await executor.execute_with_retry(mock_tx)

        metrics = executor.get_metrics()
        assert metrics.total_attempts >= 1


# =============================================================================
# Test: RetryResult Dataclass
# =============================================================================

class TestRetryResult:
    """Test the RetryResult dataclass."""

    def test_retry_result_success(self):
        """Test creating a successful retry result."""
        from core.solana.retry_logic import RetryResult

        result = RetryResult(
            success=True,
            signature="sig123",
            attempts=1,
        )

        assert result.success is True
        assert result.signature == "sig123"
        assert result.error is None

    def test_retry_result_failure(self):
        """Test creating a failed retry result."""
        from core.solana.retry_logic import RetryResult

        result = RetryResult(
            success=False,
            error="InsufficientFunds",
            attempts=1,
            retryable=False,
        )

        assert result.success is False
        assert result.error == "InsufficientFunds"
        assert result.retryable is False

    def test_retry_result_to_dict(self):
        """Test converting retry result to dict."""
        from core.solana.retry_logic import RetryResult

        result = RetryResult(
            success=True,
            signature="sig123",
            attempts=2,
        )

        d = result.to_dict()

        assert d["success"] is True
        assert d["signature"] == "sig123"
        assert d["attempts"] == 2


# =============================================================================
# Test: Integration with Existing Code
# =============================================================================

class TestIntegrationWithExisting:
    """Test integration with existing solana_execution module."""

    def test_retry_logic_exports_expected_symbols(self):
        """Test that retry_logic exports expected symbols."""
        from core.solana import retry_logic

        # Core classes
        assert hasattr(retry_logic, 'TransactionRetryExecutor')
        assert hasattr(retry_logic, 'BlockhashCache')
        assert hasattr(retry_logic, 'RetryStrategy')
        assert hasattr(retry_logic, 'RetryMetrics')

        # Enums
        assert hasattr(retry_logic, 'ErrorCategory')

        # Functions
        assert hasattr(retry_logic, 'classify_error')
        assert hasattr(retry_logic, 'calculate_backoff')

        # Result types
        assert hasattr(retry_logic, 'RetryResult')

    def test_error_category_enum_values(self):
        """Test ErrorCategory enum has expected values."""
        from core.solana.retry_logic import ErrorCategory

        assert hasattr(ErrorCategory, 'RETRYABLE_BLOCKHASH')
        assert hasattr(ErrorCategory, 'RETRYABLE_NETWORK')
        assert hasattr(ErrorCategory, 'PERMANENT')
        assert hasattr(ErrorCategory, 'UNKNOWN')
