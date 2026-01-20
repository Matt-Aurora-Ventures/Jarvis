"""
Tests for Instrumented Jupiter Client

Tests:
- Automatic metrics collection on swaps
- Quote time tracking
- Execution metrics recording
- Error handling with metrics
- Integration with metrics tracker
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import tempfile
import os

from bots.treasury.jupiter import SwapQuote, SwapResult
from core.trading.instrumented_jupiter import InstrumentedJupiterClient
from core.trading.execution_metrics import (
    ExecutionMetricsTracker,
    ExecutionStatus
)


@pytest.fixture
def temp_storage():
    """Create temporary storage for metrics"""
    fd, path = tempfile.mkstemp(suffix='.json')
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def metrics_tracker(temp_storage):
    """Create metrics tracker"""
    return ExecutionMetricsTracker(storage_path=temp_storage)


@pytest.fixture
def jupiter_client(metrics_tracker):
    """Create instrumented Jupiter client"""
    return InstrumentedJupiterClient(
        rpc_url="https://api.mainnet-beta.solana.com",
        metrics_tracker=metrics_tracker
    )


@pytest.fixture
def mock_quote():
    """Create mock swap quote"""
    return SwapQuote(
        input_mint="So11111111111111111111111111111111111111112",
        output_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        input_amount=1000000000,  # 1 SOL
        output_amount=200000000,  # 200 USDC
        input_amount_ui=1.0,
        output_amount_ui=200.0,
        price_impact_pct=0.3,
        slippage_bps=50,
        fees_usd=0.25,
        route_plan=[],
        quote_response={}
    )


@pytest.fixture
def mock_wallet():
    """Create mock wallet"""
    wallet = Mock()
    treasury = Mock()
    treasury.address = "mock_treasury_address"
    wallet.get_treasury.return_value = treasury
    wallet.sign_transaction = Mock(return_value=b"signed_tx")
    return wallet


class TestQuoteTracking:
    """Test quote time tracking"""

    @pytest.mark.asyncio
    async def test_get_quote_tracks_time(self, jupiter_client):
        """Test that get_quote tracks retrieval time"""
        with patch.object(jupiter_client, '_get_session') as mock_session:
            # Mock API response
            mock_resp = AsyncMock()
            mock_resp.json.return_value = {
                'data': [{
                    'inAmount': '1000000000',
                    'outAmount': '200000000',
                    'priceImpactPct': 0.3,
                    'marketInfos': [],
                    'routePlan': []
                }]
            }
            mock_resp.__aenter__.return_value = mock_resp
            mock_resp.__aexit__.return_value = None

            mock_session_obj = AsyncMock()
            mock_session_obj.get.return_value = mock_resp
            mock_session.return_value = mock_session_obj

            # Get quote
            quote = await jupiter_client.get_quote(
                input_mint="SOL",
                output_mint="USDC",
                amount=1000000000
            )

            # Should have quote time attached
            assert quote is not None
            assert hasattr(quote, '_metrics_quote_time')
            assert quote._metrics_quote_time > 0


class TestExecutionMetrics:
    """Test execution metrics recording"""

    @pytest.mark.asyncio
    async def test_successful_swap_records_metrics(self, jupiter_client, mock_quote, mock_wallet, metrics_tracker):
        """Test that successful swap records metrics"""
        # Mock parent execute_swap to return success
        with patch('bots.treasury.jupiter.JupiterClient.execute_swap', new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = SwapResult(
                success=True,
                signature="tx_signature_123",
                input_amount=1.0,
                output_amount=199.5,  # Slight slippage
                input_symbol="SOL",
                output_symbol="USDC",
                price_impact=0.3,
                fees_usd=0.25
            )

            # Mock get_token_info
            with patch.object(jupiter_client, 'get_token_info') as mock_token_info:
                mock_token = Mock()
                mock_token.symbol = "USDC"
                mock_token_info.return_value = mock_token

                # Mock get_dynamic_priority_fee
                with patch.object(jupiter_client, 'get_dynamic_priority_fee', return_value=10000):
                    # Execute swap
                    result = await jupiter_client.execute_swap(
                        quote=mock_quote,
                        wallet=mock_wallet,
                        position_id="pos_123",
                        direction="BUY"
                    )

                    # Verify result
                    assert result.success is True

                    # Verify metrics were recorded
                    stats = metrics_tracker.get_stats(hours=24)
                    assert stats.total_executions == 1
                    assert stats.successful_executions == 1
                    assert stats.success_rate_pct == 100.0

                    # Verify slippage was calculated
                    metric = metrics_tracker._metrics[0]
                    assert metric.expected_output == 200.0
                    assert metric.actual_output == 199.5
                    assert abs(metric.slippage_pct - 0.25) < 0.01

    @pytest.mark.asyncio
    async def test_failed_swap_records_metrics(self, jupiter_client, mock_quote, mock_wallet, metrics_tracker):
        """Test that failed swap records metrics"""
        # Mock parent execute_swap to return failure
        with patch('bots.treasury.jupiter.JupiterClient.execute_swap', new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = SwapResult(
                success=False,
                error="Transaction timeout after 30s"
            )

            # Mock get_token_info
            with patch.object(jupiter_client, 'get_token_info') as mock_token_info:
                mock_token = Mock()
                mock_token.symbol = "USDC"
                mock_token_info.return_value = mock_token

                with patch.object(jupiter_client, 'get_dynamic_priority_fee', return_value=10000):
                    # Execute swap
                    result = await jupiter_client.execute_swap(
                        quote=mock_quote,
                        wallet=mock_wallet
                    )

                    # Verify result
                    assert result.success is False

                    # Verify metrics were recorded
                    stats = metrics_tracker.get_stats(hours=24)
                    assert stats.total_executions == 1
                    assert stats.failed_executions == 1
                    assert stats.success_rate_pct == 0.0

                    # Verify error was categorized
                    metric = metrics_tracker._metrics[0]
                    assert metric.status == ExecutionStatus.TIMEOUT
                    assert metric.error_type == "timeout"
                    assert "timeout" in metric.error_message.lower()

    @pytest.mark.asyncio
    async def test_simulation_failure_recorded(self, jupiter_client, mock_quote, mock_wallet, metrics_tracker):
        """Test that simulation failures are recorded"""
        with patch('bots.treasury.jupiter.JupiterClient.execute_swap', new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = SwapResult(
                success=False,
                error="Simulation failed: insufficient balance"
            )

            with patch.object(jupiter_client, 'get_token_info') as mock_token_info:
                mock_token = Mock()
                mock_token.symbol = "USDC"
                mock_token_info.return_value = mock_token

                with patch.object(jupiter_client, 'get_dynamic_priority_fee', return_value=10000):
                    result = await jupiter_client.execute_swap(
                        quote=mock_quote,
                        wallet=mock_wallet
                    )

                    metric = metrics_tracker._metrics[0]
                    assert metric.status == ExecutionStatus.SIMULATED
                    assert metric.error_type == "simulation_failed"

    @pytest.mark.asyncio
    async def test_slippage_error_categorized(self, jupiter_client, mock_quote, mock_wallet, metrics_tracker):
        """Test that slippage errors are categorized correctly"""
        with patch('bots.treasury.jupiter.JupiterClient.execute_swap', new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = SwapResult(
                success=False,
                error="Slippage tolerance exceeded"
            )

            with patch.object(jupiter_client, 'get_token_info') as mock_token_info:
                mock_token = Mock()
                mock_token.symbol = "USDC"
                mock_token_info.return_value = mock_token

                with patch.object(jupiter_client, 'get_dynamic_priority_fee', return_value=10000):
                    result = await jupiter_client.execute_swap(
                        quote=mock_quote,
                        wallet=mock_wallet
                    )

                    metric = metrics_tracker._metrics[0]
                    assert metric.error_type == "slippage_exceeded"


class TestConfirmationTracking:
    """Test transaction confirmation tracking"""

    @pytest.mark.asyncio
    async def test_execute_with_confirmation_tracks_time(self, jupiter_client, mock_quote, mock_wallet, metrics_tracker):
        """Test that execute_with_confirmation tracks confirmation time"""
        with patch('bots.treasury.jupiter.JupiterClient.execute_swap', new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = SwapResult(
                success=True,
                signature="tx_sig_123",
                input_amount=1.0,
                output_amount=200.0,
                input_symbol="SOL",
                output_symbol="USDC",
                price_impact=0.3,
                fees_usd=0.25
            )

            # Mock confirmation check
            with patch.object(jupiter_client, '_wait_for_confirmation', return_value=True):
                with patch.object(jupiter_client, 'get_token_info') as mock_token_info:
                    mock_token = Mock()
                    mock_token.symbol = "USDC"
                    mock_token_info.return_value = mock_token

                    with patch.object(jupiter_client, 'get_dynamic_priority_fee', return_value=10000):
                        result = await jupiter_client.execute_swap_with_confirmation(
                            quote=mock_quote,
                            wallet=mock_wallet,
                            confirm_timeout=30
                        )

                        # Should have confirmation time recorded
                        metric = metrics_tracker._metrics[0]
                        assert metric.confirmation_time > 0


class TestMetricsIntegration:
    """Test integration with metrics tracker"""

    @pytest.mark.asyncio
    async def test_get_metrics_stats(self, jupiter_client, mock_quote, mock_wallet, metrics_tracker):
        """Test getting metrics stats from client"""
        # Execute some swaps
        with patch('bots.treasury.jupiter.JupiterClient.execute_swap', new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = SwapResult(
                success=True,
                signature="tx_sig",
                input_amount=1.0,
                output_amount=200.0,
                input_symbol="SOL",
                output_symbol="USDC",
                price_impact=0.3,
                fees_usd=0.25
            )

            with patch.object(jupiter_client, 'get_token_info') as mock_token_info:
                mock_token = Mock()
                mock_token.symbol = "USDC"
                mock_token_info.return_value = mock_token

                with patch.object(jupiter_client, 'get_dynamic_priority_fee', return_value=10000):
                    for _ in range(3):
                        await jupiter_client.execute_swap(
                            quote=mock_quote,
                            wallet=mock_wallet
                        )

        # Get stats from client
        stats = jupiter_client.get_metrics_stats(hours=24)

        assert stats.total_executions == 3
        assert stats.success_rate_pct == 100.0

    @pytest.mark.asyncio
    async def test_get_optimization_insights(self, jupiter_client, mock_quote, mock_wallet, metrics_tracker):
        """Test getting optimization insights"""
        # Execute swap with high slippage
        with patch('bots.treasury.jupiter.JupiterClient.execute_swap', new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = SwapResult(
                success=True,
                signature="tx_sig",
                input_amount=1.0,
                output_amount=198.0,  # 1% slippage
                input_symbol="SOL",
                output_symbol="USDC",
                price_impact=0.3,
                fees_usd=0.25
            )

            with patch.object(jupiter_client, 'get_token_info') as mock_token_info:
                mock_token = Mock()
                mock_token.symbol = "USDC"
                mock_token_info.return_value = mock_token

                with patch.object(jupiter_client, 'get_dynamic_priority_fee', return_value=10000):
                    await jupiter_client.execute_swap(
                        quote=mock_quote,
                        wallet=mock_wallet
                    )

        # Get insights
        insights = jupiter_client.get_optimization_insights(hours=24)

        assert 'success_rate' in insights
        assert 'latency' in insights
        assert 'slippage' in insights
        assert 'costs' in insights


class TestErrorHandling:
    """Test error handling with metrics"""

    @pytest.mark.asyncio
    async def test_categorizes_blockhash_error(self, jupiter_client, mock_quote, mock_wallet, metrics_tracker):
        """Test blockhash expiration error categorization"""
        with patch('bots.treasury.jupiter.JupiterClient.execute_swap', new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = SwapResult(
                success=False,
                error="Blockhash not found or expired"
            )

            with patch.object(jupiter_client, 'get_token_info') as mock_token_info:
                mock_token = Mock()
                mock_token.symbol = "USDC"
                mock_token_info.return_value = mock_token

                with patch.object(jupiter_client, 'get_dynamic_priority_fee', return_value=10000):
                    await jupiter_client.execute_swap(
                        quote=mock_quote,
                        wallet=mock_wallet
                    )

                    metric = metrics_tracker._metrics[0]
                    assert metric.error_type == "blockhash_expired"

    @pytest.mark.asyncio
    async def test_categorizes_balance_error(self, jupiter_client, mock_quote, mock_wallet, metrics_tracker):
        """Test insufficient balance error categorization"""
        with patch('bots.treasury.jupiter.JupiterClient.execute_swap', new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = SwapResult(
                success=False,
                error="Insufficient balance for transaction"
            )

            with patch.object(jupiter_client, 'get_token_info') as mock_token_info:
                mock_token = Mock()
                mock_token.symbol = "USDC"
                mock_token_info.return_value = mock_token

                with patch.object(jupiter_client, 'get_dynamic_priority_fee', return_value=10000):
                    await jupiter_client.execute_swap(
                        quote=mock_quote,
                        wallet=mock_wallet
                    )

                    metric = metrics_tracker._metrics[0]
                    assert metric.error_type == "insufficient_balance"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
