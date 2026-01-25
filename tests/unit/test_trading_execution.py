"""
Unit tests for trading_execution.py

Tests cover:
- SwapExecutor with Bags.fm → Jupiter fallback
- Circuit breaker enforcement
- Signal analysis (sentiment, liquidation, MA)
- Combined signal generation
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Any

from bots.treasury.trading.trading_execution import SwapExecutor, SignalAnalyzer
from bots.treasury.trading.types import TradeDirection


# Mock types for Jupiter (avoid import errors)
class MockSwapQuote:
    def __init__(self, input_mint, output_mint, in_amount, out_amount, slippage_bps=50, price=1.0):
        self.input_mint = input_mint
        self.output_mint = output_mint
        self.in_amount = in_amount
        self.out_amount = out_amount
        self.slippage_bps = slippage_bps
        self.price = price


class MockSwapResult:
    def __init__(self, success, signature=None, input_mint=None, output_mint=None,
                 in_amount=None, out_amount=None, price=0.0, error=None):
        self.success = success
        self.signature = signature
        self.input_mint = input_mint
        self.output_mint = output_mint
        self.in_amount = in_amount
        self.out_amount = out_amount
        self.price = price
        self.error = error


@pytest.fixture
def mock_jupiter():
    """Create mock Jupiter client."""
    jupiter = AsyncMock()
    jupiter.execute_swap = AsyncMock(return_value=MockSwapResult(
        success=True,
        signature="jupiter_tx_123",
        input_mint="SOL",
        output_mint="USDC",
        in_amount=100,
        out_amount=9500,
        price=95.0
    ))
    return jupiter


@pytest.fixture
def mock_wallet():
    """Create mock wallet."""
    wallet = MagicMock()
    wallet.public_key = "wallet_public_key_123"
    return wallet


@pytest.fixture
def mock_bags_adapter():
    """Create mock Bags.fm adapter."""
    bags = AsyncMock()
    bags.execute_swap = AsyncMock(return_value=("bags_tx_123", 9600))
    return bags


@pytest.fixture
def swap_executor(mock_jupiter, mock_wallet):
    """Create SwapExecutor without Bags adapter."""
    return SwapExecutor(mock_jupiter, mock_wallet, bags_adapter=None)


@pytest.fixture
def swap_executor_with_bags(mock_jupiter, mock_wallet, mock_bags_adapter):
    """Create SwapExecutor with Bags adapter."""
    return SwapExecutor(mock_jupiter, mock_wallet, bags_adapter=mock_bags_adapter)


class TestSwapExecutor:
    """Tests for SwapExecutor class."""

    @pytest.mark.asyncio
    async def test_execute_swap_jupiter_only(self, swap_executor):
        """Test swap execution via Jupiter when Bags not configured."""
        quote = MockSwapQuote(
            input_mint="So11111111111111111111111111111111111111112",
            output_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            in_amount=100_000_000,  # 0.1 SOL
            out_amount=9_500_000,   # 9.5 USDC
        )

        result = await swap_executor.execute_swap(quote)

        assert result.success is True
        assert result.signature == "jupiter_tx_123"
        swap_executor.jupiter.execute_swap.assert_called_once_with(quote, swap_executor.wallet)

    @pytest.mark.asyncio
    @patch('bots.treasury.trading.trading_execution.SwapResult', MockSwapResult)
    async def test_execute_swap_bags_success(self, swap_executor_with_bags, mock_bags_adapter):
        """Test successful swap via Bags.fm."""
        quote = MockSwapQuote(
            input_mint="SOL_mint",
            output_mint="USDC_mint",
            in_amount=100_000_000,
            out_amount=9_500_000,
            slippage_bps=50,
            price=95.0,
        )

        result = await swap_executor_with_bags.execute_swap(quote)

        assert result.success is True
        assert result.signature == "bags_tx_123"
        assert result.out_amount == 9600
        mock_bags_adapter.execute_swap.assert_called_once_with(
            input_mint="SOL_mint",
            output_mint="USDC_mint",
            amount=100_000_000,
            slippage=0.5,  # slippage_bps / 100
        )

        # Jupiter should NOT be called if Bags succeeds
        swap_executor_with_bags.jupiter.execute_swap.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_swap_bags_fails_jupiter_fallback(self, swap_executor_with_bags, mock_bags_adapter):
        """Test Bags.fm failure triggers Jupiter fallback."""
        mock_bags_adapter.execute_swap = AsyncMock(
            side_effect=Exception("Bags API down")
        )

        quote = MockSwapQuote(
            input_mint="SOL_mint",
            output_mint="USDC_mint",
            in_amount=100_000_000,
            out_amount=9_500_000,
        )

        result = await swap_executor_with_bags.execute_swap(quote)

        assert result.success is True
        assert result.signature == "jupiter_tx_123"
        mock_bags_adapter.execute_swap.assert_called_once()
        swap_executor_with_bags.jupiter.execute_swap.assert_called_once()

    @pytest.mark.asyncio
    @patch('core.recovery.adapters.TradingAdapter')
    async def test_execute_swap_circuit_breaker_open(self, mock_trading_adapter_class, swap_executor):
        """Test that circuit breaker blocks trades."""
        mock_adapter = MagicMock()
        mock_adapter.can_execute.return_value = False
        mock_adapter.get_status.return_value = {
            'consecutive_failures': 5,
            'circuit_open_until': '2026-01-24T12:00:00'
        }
        mock_trading_adapter_class.return_value = mock_adapter

        quote = MockSwapQuote(
            input_mint="SOL_mint",
            output_mint="USDC_mint",
            in_amount=100_000_000,
            out_amount=9_500_000,
        )

        result = await swap_executor.execute_swap(quote)

        assert result.success is False
        assert "circuit breaker" in result.error.lower()
        swap_executor.jupiter.execute_swap.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_swap_extracts_mints_from_quote(self, swap_executor):
        """Test that input/output mints are extracted from quote if not provided."""
        quote = MockSwapQuote(
            input_mint="extracted_input_mint",
            output_mint="extracted_output_mint",
            in_amount=100,
            out_amount=95,
        )

        # Call without explicit mints
        result = await swap_executor.execute_swap(quote)

        assert result.success is True
        swap_executor.jupiter.execute_swap.assert_called_once_with(quote, swap_executor.wallet)

    @pytest.mark.asyncio
    async def test_execute_swap_jupiter_failure(self, swap_executor):
        """Test handling of Jupiter swap failure."""
        swap_executor.jupiter.execute_swap = AsyncMock(return_value=MockSwapResult(
            success=False,
            error="Slippage exceeded"
        ))

        quote = MockSwapQuote(
            input_mint="SOL_mint",
            output_mint="USDC_mint",
            in_amount=100,
            out_amount=95,
        )

        result = await swap_executor.execute_swap(quote)

        assert result.success is False
        assert result.error == "Slippage exceeded"


class TestSignalAnalyzer:
    """Tests for SignalAnalyzer class."""

    @pytest.fixture
    def signal_analyzer(self):
        """Create SignalAnalyzer instance."""
        return SignalAnalyzer(enable_signals=True)

    @pytest.fixture
    def signal_analyzer_disabled(self):
        """Create SignalAnalyzer with signals disabled."""
        return SignalAnalyzer(enable_signals=False)

    @pytest.mark.asyncio
    async def test_close(self, signal_analyzer):
        """Test closing the signal analyzer."""
        # Should not raise exception
        await signal_analyzer.close()

    @pytest.mark.asyncio
    async def test_analyze_sentiment_signal(self, signal_analyzer_disabled):
        """Test sentiment analysis with correct parameters."""
        direction, reason = await signal_analyzer_disabled.analyze_sentiment_signal(
            token_mint="SOL",
            sentiment_score=0.5,
            sentiment_grade="A",
            max_positions=10,
            open_positions_count=5
        )

        assert direction == TradeDirection.LONG
        assert "High conviction bullish" in reason

    @pytest.mark.asyncio
    async def test_analyze_liquidation_signal_when_disabled(self, signal_analyzer_disabled):
        """Test liquidation analysis when signals are disabled."""
        direction, reason, signal = await signal_analyzer_disabled.analyze_liquidation_signal(symbol="BTC")

        assert direction == TradeDirection.NEUTRAL
        assert "not available" in reason
        assert signal is None

    @pytest.mark.asyncio
    async def test_analyze_ma_signal(self, signal_analyzer_disabled):
        """Test MA analysis when signals are disabled."""
        direction, reason, signal = await signal_analyzer_disabled.analyze_ma_signal(
            prices=[100.0, 101.0, 102.0],
            symbol="BTC"
        )

        assert direction == TradeDirection.NEUTRAL
        assert "not available" in reason or "No signal" in reason
        assert signal is None

    @pytest.mark.asyncio
    async def test_get_combined_signal(self, signal_analyzer_disabled):
        """Test combined signal when decision matrix not available."""
        direction, reason, confidence = await signal_analyzer_disabled.get_combined_signal(
            token_mint="SOL",
            symbol="BTC",
            sentiment_score=0.5,
            sentiment_grade="A",
            max_positions=10,
            open_positions_count=5,
            prices=None
        )

        assert direction == TradeDirection.LONG
        assert "High conviction bullish" in reason
        assert confidence == 0.5

    @pytest.mark.asyncio
    async def test_get_liquidation_summary_when_coinglass_unavailable(self, signal_analyzer_disabled):
        """Test liquidation summary when CoinGlass is not available."""
        result = await signal_analyzer_disabled.get_liquidation_summary(symbol="BTC")

        assert "error" in result
        assert "not available" in result["error"]


class TestSwapExecutorRecoveryAdapter:
    """Tests for SwapExecutor recovery adapter integration."""

    @pytest.mark.asyncio
    @patch('core.recovery.adapters.TradingAdapter')
    async def test_recovery_adapter_records_success(self, mock_trading_adapter_class, swap_executor):
        """Test that recovery adapter records success."""
        mock_adapter = MagicMock()
        mock_adapter.can_execute.return_value = True
        mock_adapter.record_success = MagicMock()
        mock_trading_adapter_class.return_value = mock_adapter

        quote = MockSwapQuote(
            input_mint="SOL_mint",
            output_mint="USDC_mint",
            in_amount=100,
            out_amount=95,
        )

        await swap_executor.execute_swap(quote)

        mock_adapter.record_success.assert_called_once_with("execute_swap_jupiter")

    @pytest.mark.asyncio
    @patch('core.recovery.adapters.TradingAdapter')
    async def test_recovery_adapter_records_failure(self, mock_trading_adapter_class, swap_executor):
        """Test that recovery adapter records failure."""
        mock_adapter = MagicMock()
        mock_adapter.can_execute.return_value = True
        mock_adapter.record_failure = MagicMock()
        mock_trading_adapter_class.return_value = mock_adapter

        swap_executor.jupiter.execute_swap = AsyncMock(return_value=MockSwapResult(
            success=False,
            error="Transaction failed"
        ))

        quote = MockSwapQuote(
            input_mint="SOL_mint",
            output_mint="USDC_mint",
            in_amount=100,
            out_amount=95,
        )

        await swap_executor.execute_swap(quote)

        mock_adapter.record_failure.assert_called_once_with("execute_swap_jupiter", "Transaction failed")

    @pytest.mark.asyncio
    @patch('bots.treasury.trading.trading_execution.SwapResult', MockSwapResult)
    @patch('core.recovery.adapters.TradingAdapter')
    async def test_recovery_adapter_bags_success(self, mock_trading_adapter_class, swap_executor_with_bags):
        """Test that recovery adapter records Bags.fm success."""
        mock_adapter = MagicMock()
        mock_adapter.can_execute.return_value = True
        mock_adapter.record_success = MagicMock()
        mock_trading_adapter_class.return_value = mock_adapter

        quote = MockSwapQuote(
            input_mint="SOL_mint",
            output_mint="USDC_mint",
            in_amount=100,
            out_amount=95,
        )

        await swap_executor_with_bags.execute_swap(quote)

        mock_adapter.record_success.assert_called_once_with("execute_swap_bags")

    @pytest.mark.asyncio
    @patch('core.recovery.adapters.TradingAdapter')
    async def test_recovery_adapter_bags_failure_jupiter_fallback(self, mock_trading_adapter_class, swap_executor_with_bags, mock_bags_adapter):
        """Test that recovery adapter records Bags failure and Jupiter fallback."""
        mock_adapter = MagicMock()
        mock_adapter.can_execute.return_value = True
        mock_adapter.record_failure = MagicMock()
        mock_adapter.record_success = MagicMock()
        mock_trading_adapter_class.return_value = mock_adapter

        mock_bags_adapter.execute_swap = AsyncMock(
            side_effect=Exception("Bags API error")
        )

        quote = MockSwapQuote(
            input_mint="SOL_mint",
            output_mint="USDC_mint",
            in_amount=100,
            out_amount=95,
        )

        await swap_executor_with_bags.execute_swap(quote)

        # Bags failure should be recorded
        mock_adapter.record_failure.assert_called_once_with("execute_swap_bags", "Bags API error")
        # Jupiter fallback success should be recorded
        mock_adapter.record_success.assert_called_once_with("execute_swap_jupiter")

    @pytest.mark.asyncio
    @patch('core.recovery.adapters.TradingAdapter')
    async def test_recovery_adapter_import_error_ignored(self, mock_trading_adapter_class, swap_executor):
        """Test that recovery adapter import errors are gracefully handled."""
        # Simulate ImportError
        mock_trading_adapter_class.side_effect = ImportError("Module not found")

        quote = MockSwapQuote(
            input_mint="SOL_mint",
            output_mint="USDC_mint",
            in_amount=100,
            out_amount=95,
        )

        # Should not raise, just log and continue
        result = await swap_executor.execute_swap(quote)

        assert result.success is True

    @pytest.mark.asyncio
    @patch('core.recovery.adapters.TradingAdapter')
    async def test_recovery_adapter_runtime_error_ignored(self, mock_trading_adapter_class, swap_executor):
        """Test that recovery adapter runtime errors are gracefully handled."""
        # Simulate runtime error in adapter
        mock_adapter = MagicMock()
        mock_adapter.can_execute.side_effect = RuntimeError("Adapter crashed")
        mock_trading_adapter_class.return_value = mock_adapter

        quote = MockSwapQuote(
            input_mint="SOL_mint",
            output_mint="USDC_mint",
            in_amount=100,
            out_amount=95,
        )

        # Should not raise, just log and continue
        result = await swap_executor.execute_swap(quote)

        assert result.success is True
