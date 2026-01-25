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


# =============================================================================
# Extended Signal Analysis Tests (Lines 226-399)
# =============================================================================


class TestSentimentSignalThresholds:
    """Extended tests for sentiment signal analysis covering all thresholds."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer with signals disabled (pure sentiment logic)."""
        return SignalAnalyzer(enable_signals=False)

    @pytest.mark.asyncio
    async def test_high_conviction_bullish_a_plus(self, analyzer):
        """Test high conviction bullish signal (A+, score > 0.40)."""
        direction, reason = await analyzer.analyze_sentiment_signal(
            token_mint="SOL_mint",
            sentiment_score=0.45,
            sentiment_grade="A+",
            max_positions=10,
            open_positions_count=3
        )

        assert direction == TradeDirection.LONG
        assert "High conviction bullish" in reason
        assert "A+" in reason
        assert "0.45" in reason

    @pytest.mark.asyncio
    async def test_high_conviction_bullish_a(self, analyzer):
        """Test high conviction bullish signal (A, score > 0.40)."""
        direction, reason = await analyzer.analyze_sentiment_signal(
            token_mint="SOL_mint",
            sentiment_score=0.42,
            sentiment_grade="A",
            max_positions=10,
            open_positions_count=3
        )

        assert direction == TradeDirection.LONG
        assert "High conviction bullish" in reason
        assert "Grade A" in reason

    @pytest.mark.asyncio
    async def test_strong_bullish_a_minus(self, analyzer):
        """Test strong bullish signal (A-, score > 0.35)."""
        direction, reason = await analyzer.analyze_sentiment_signal(
            token_mint="SOL_mint",
            sentiment_score=0.36,
            sentiment_grade="A-",
            max_positions=10,
            open_positions_count=3
        )

        assert direction == TradeDirection.LONG
        assert "Strong bullish signal" in reason
        assert "A-" in reason

    @pytest.mark.asyncio
    async def test_strong_bullish_b_plus(self, analyzer):
        """Test strong bullish signal (B+, score > 0.35)."""
        direction, reason = await analyzer.analyze_sentiment_signal(
            token_mint="SOL_mint",
            sentiment_score=0.37,
            sentiment_grade="B+",
            max_positions=10,
            open_positions_count=3
        )

        assert direction == TradeDirection.LONG
        assert "Strong bullish signal" in reason
        assert "B+" in reason

    @pytest.mark.asyncio
    async def test_moderate_bullish_b(self, analyzer):
        """Test moderate bullish signal (B, score > 0.30)."""
        direction, reason = await analyzer.analyze_sentiment_signal(
            token_mint="SOL_mint",
            sentiment_score=0.32,
            sentiment_grade="B",
            max_positions=10,
            open_positions_count=3
        )

        assert direction == TradeDirection.LONG
        assert "Moderate bullish signal" in reason
        assert "Grade B" in reason

    @pytest.mark.asyncio
    async def test_bearish_signal(self, analyzer):
        """Test bearish signal (score < -0.30)."""
        direction, reason = await analyzer.analyze_sentiment_signal(
            token_mint="SOL_mint",
            sentiment_score=-0.35,
            sentiment_grade="D",
            max_positions=10,
            open_positions_count=3
        )

        assert direction == TradeDirection.SHORT
        assert "Bearish signal" in reason
        assert "-0.35" in reason

    @pytest.mark.asyncio
    async def test_neutral_weak_score(self, analyzer):
        """Test neutral when score not strong enough."""
        direction, reason = await analyzer.analyze_sentiment_signal(
            token_mint="SOL_mint",
            sentiment_score=0.25,  # Below 0.30 threshold for B
            sentiment_grade="B",
            max_positions=10,
            open_positions_count=3
        )

        assert direction == TradeDirection.NEUTRAL
        assert "not strong enough" in reason
        assert "0.25" in reason

    @pytest.mark.asyncio
    async def test_neutral_max_positions_reached(self, analyzer):
        """Test neutral when max positions reached."""
        direction, reason = await analyzer.analyze_sentiment_signal(
            token_mint="SOL_mint",
            sentiment_score=0.50,
            sentiment_grade="A",
            max_positions=10,
            open_positions_count=10  # At max
        )

        assert direction == TradeDirection.NEUTRAL
        assert "Max positions reached" in reason


class TestLiquidationSignalAnalysis:
    """Tests for liquidation signal analysis with mocked CoinGlass data."""

    @pytest.fixture
    def analyzer_with_coinglass(self):
        """Create analyzer with mocked CoinGlass."""
        analyzer = SignalAnalyzer(enable_signals=True)

        # Mock CoinGlass
        analyzer._coinglass = AsyncMock()

        # Mock Liquidation Analyzer
        from types import SimpleNamespace
        analyzer._liquidation_analyzer = MagicMock()

        return analyzer

    @pytest.mark.asyncio
    async def test_liquidation_signal_long(self, analyzer_with_coinglass):
        """Test liquidation signal returning LONG direction."""
        # Mock liquidation data
        from types import SimpleNamespace
        liq_data = [
            SimpleNamespace(
                timestamp=1234567890,
                long_liquidations=5_000_000,  # $5M long liquidations
                short_liquidations=500_000,   # $500k short liquidations
            )
        ]
        analyzer_with_coinglass._coinglass.get_liquidations = AsyncMock(return_value=liq_data)

        # Mock analyzer returning LONG signal
        mock_signal = SimpleNamespace(
            direction='long',
            reasoning='High long liquidations signal bottom',
            confidence=0.75
        )
        analyzer_with_coinglass._liquidation_analyzer.analyze = MagicMock(return_value=mock_signal)

        direction, reason, signal = await analyzer_with_coinglass.analyze_liquidation_signal(symbol="BTC")

        assert direction == TradeDirection.LONG
        assert "Liquidation signal" in reason
        assert "75%" in reason
        assert signal == mock_signal

    @pytest.mark.asyncio
    async def test_liquidation_signal_short(self, analyzer_with_coinglass):
        """Test liquidation signal returning SHORT direction."""
        from types import SimpleNamespace
        liq_data = [
            SimpleNamespace(
                timestamp=1234567890,
                long_liquidations=500_000,     # $500k long liquidations
                short_liquidations=5_000_000,  # $5M short liquidations
            )
        ]
        analyzer_with_coinglass._coinglass.get_liquidations = AsyncMock(return_value=liq_data)

        # Mock analyzer returning SHORT signal
        mock_signal = SimpleNamespace(
            direction='short',
            reasoning='High short liquidations signal top',
            confidence=0.65
        )
        analyzer_with_coinglass._liquidation_analyzer.analyze = MagicMock(return_value=mock_signal)

        direction, reason, signal = await analyzer_with_coinglass.analyze_liquidation_signal(symbol="BTC")

        assert direction == TradeDirection.SHORT
        assert "Liquidation signal" in reason
        assert "65%" in reason

    @pytest.mark.asyncio
    async def test_liquidation_signal_neutral(self, analyzer_with_coinglass):
        """Test liquidation signal returning NEUTRAL (no signal)."""
        from types import SimpleNamespace
        liq_data = [
            SimpleNamespace(
                timestamp=1234567890,
                long_liquidations=1_000_000,
                short_liquidations=1_000_000,
            )
        ]
        analyzer_with_coinglass._coinglass.get_liquidations = AsyncMock(return_value=liq_data)

        # Analyzer returns None (no signal)
        analyzer_with_coinglass._liquidation_analyzer.analyze = MagicMock(return_value=None)

        direction, reason, signal = await analyzer_with_coinglass.analyze_liquidation_signal(symbol="BTC")

        assert direction == TradeDirection.NEUTRAL
        assert "No liquidation signal detected" in reason
        assert signal is None

    @pytest.mark.asyncio
    async def test_liquidation_signal_no_data(self, analyzer_with_coinglass):
        """Test liquidation signal when no data available."""
        analyzer_with_coinglass._coinglass.get_liquidations = AsyncMock(return_value=[])

        direction, reason, signal = await analyzer_with_coinglass.analyze_liquidation_signal(symbol="BTC")

        assert direction == TradeDirection.NEUTRAL
        assert "No liquidation data available" in reason
        assert signal is None

    @pytest.mark.asyncio
    async def test_liquidation_signal_error_handling(self, analyzer_with_coinglass):
        """Test liquidation signal handles errors gracefully."""
        analyzer_with_coinglass._coinglass.get_liquidations = AsyncMock(side_effect=Exception("API error"))

        direction, reason, signal = await analyzer_with_coinglass.analyze_liquidation_signal(symbol="BTC")

        assert direction == TradeDirection.NEUTRAL
        assert "error" in reason.lower()
        assert signal is None


class TestMASignalAnalysis:
    """Tests for moving average signal analysis."""

    @pytest.fixture
    def analyzer_with_ma(self):
        """Create analyzer with mocked MA analyzer."""
        analyzer = SignalAnalyzer(enable_signals=True)
        analyzer._ma_analyzer = MagicMock()
        return analyzer

    @pytest.mark.asyncio
    async def test_ma_signal_long(self, analyzer_with_ma):
        """Test MA signal returning LONG."""
        from types import SimpleNamespace
        mock_signal = SimpleNamespace(
            direction='long',
            reasoning='MA crossover bullish',
            strength=0.80
        )
        analyzer_with_ma._ma_analyzer.analyze = MagicMock(return_value=mock_signal)

        prices = [100.0] * 100  # Need 100+ prices
        direction, reason, signal = await analyzer_with_ma.analyze_ma_signal(prices, symbol="BTC")

        assert direction == TradeDirection.LONG
        assert "MA signal" in reason
        assert "80%" in reason

    @pytest.mark.asyncio
    async def test_ma_signal_short(self, analyzer_with_ma):
        """Test MA signal returning SHORT."""
        from types import SimpleNamespace
        mock_signal = SimpleNamespace(
            direction='short',
            reasoning='MA crossover bearish',
            strength=0.70
        )
        analyzer_with_ma._ma_analyzer.analyze = MagicMock(return_value=mock_signal)

        prices = [100.0] * 100
        direction, reason, signal = await analyzer_with_ma.analyze_ma_signal(prices, symbol="BTC")

        assert direction == TradeDirection.SHORT
        assert "MA signal" in reason
        assert "70%" in reason

    @pytest.mark.asyncio
    async def test_ma_signal_neutral_no_signal(self, analyzer_with_ma):
        """Test MA signal when analyzer returns None."""
        analyzer_with_ma._ma_analyzer.analyze = MagicMock(return_value=None)

        prices = [100.0] * 100
        direction, reason, signal = await analyzer_with_ma.analyze_ma_signal(prices, symbol="BTC")

        assert direction == TradeDirection.NEUTRAL
        assert "No MA signal detected" in reason

    @pytest.mark.asyncio
    async def test_ma_signal_error_handling(self, analyzer_with_ma):
        """Test MA signal handles errors gracefully."""
        analyzer_with_ma._ma_analyzer.analyze = MagicMock(side_effect=Exception("Analysis failed"))

        prices = [100.0] * 100
        direction, reason, signal = await analyzer_with_ma.analyze_ma_signal(prices, symbol="BTC")

        assert direction == TradeDirection.NEUTRAL
        assert "error" in reason.lower()


class TestCombinedSignalDecisionMatrix:
    """Tests for combined signal with decision matrix enabled."""

    @pytest.fixture
    def analyzer_with_decision_matrix(self):
        """Create analyzer with all components mocked."""
        analyzer = SignalAnalyzer(enable_signals=True)

        # Mock decision matrix
        from types import SimpleNamespace
        analyzer._decision_matrix = MagicMock()

        # Mock all analyzers
        analyzer._coinglass = AsyncMock()
        analyzer._liquidation_analyzer = MagicMock()
        analyzer._ma_analyzer = MagicMock()

        return analyzer

    @pytest.mark.asyncio
    async def test_combined_signal_all_long(self, analyzer_with_decision_matrix):
        """Test combined signal when all signals agree LONG."""
        analyzer = analyzer_with_decision_matrix

        # Mock liquidation signal: LONG
        from types import SimpleNamespace
        liq_data = [SimpleNamespace(timestamp=123, long_liquidations=5_000_000, short_liquidations=500_000)]
        analyzer._coinglass.get_liquidations = AsyncMock(return_value=liq_data)
        liq_signal = SimpleNamespace(direction='long', reasoning='Liq: long', confidence=0.75)
        analyzer._liquidation_analyzer.analyze = MagicMock(return_value=liq_signal)

        # Mock MA signal: LONG
        ma_signal = SimpleNamespace(direction='long', reasoning='MA: long', strength=0.80)
        analyzer._ma_analyzer.analyze = MagicMock(return_value=ma_signal)

        direction, reason, confidence = await analyzer.get_combined_signal(
            token_mint="SOL_mint",
            symbol="BTC",
            sentiment_score=0.50,  # Sentiment will be LONG too
            sentiment_grade="A",
            max_positions=10,
            open_positions_count=3,
            prices=[100.0] * 100
        )

        # All 3 signals are LONG
        assert direction == TradeDirection.LONG
        assert confidence > 0.0
        assert "High conviction bullish" in reason or "Liquidation signal" in reason

    @pytest.mark.asyncio
    async def test_combined_signal_mixed_signals(self, analyzer_with_decision_matrix):
        """Test combined signal with mixed directions."""
        analyzer = analyzer_with_decision_matrix

        # Sentiment: LONG
        # Liquidation: SHORT
        # MA: LONG
        from types import SimpleNamespace
        liq_data = [SimpleNamespace(timestamp=123, long_liquidations=500_000, short_liquidations=5_000_000)]
        analyzer._coinglass.get_liquidations = AsyncMock(return_value=liq_data)
        liq_signal = SimpleNamespace(direction='short', reasoning='Liq: short', confidence=0.60)
        analyzer._liquidation_analyzer.analyze = MagicMock(return_value=liq_signal)

        ma_signal = SimpleNamespace(direction='long', reasoning='MA: long', strength=0.70)
        analyzer._ma_analyzer.analyze = MagicMock(return_value=ma_signal)

        direction, reason, confidence = await analyzer.get_combined_signal(
            token_mint="SOL_mint",
            symbol="BTC",
            sentiment_score=0.50,
            sentiment_grade="A",
            max_positions=10,
            open_positions_count=3,
            prices=[100.0] * 100
        )

        # 2 LONG (sentiment + MA) vs 1 SHORT (liquidation)
        # Weighted score: long_score = 0.5 + 0.7 = 1.2, short_score = 0.6
        assert direction == TradeDirection.LONG
        assert confidence > 0.0

    @pytest.mark.asyncio
    async def test_combined_signal_no_signals(self, analyzer_with_decision_matrix):
        """Test combined signal when no signals detected."""
        analyzer = analyzer_with_decision_matrix

        # All signals return NEUTRAL
        analyzer._coinglass.get_liquidations = AsyncMock(return_value=[])
        analyzer._ma_analyzer.analyze = MagicMock(return_value=None)

        direction, reason, confidence = await analyzer.get_combined_signal(
            token_mint="SOL_mint",
            symbol="BTC",
            sentiment_score=0.20,  # Below threshold
            sentiment_grade="C",
            max_positions=10,
            open_positions_count=3,
            prices=[100.0] * 100
        )

        assert direction == TradeDirection.NEUTRAL
        assert "No signals detected" in reason
        assert confidence == 0.0

    @pytest.mark.asyncio
    async def test_combined_signal_weak_confidence(self, analyzer_with_decision_matrix):
        """Test combined signal when confidence is too low."""
        analyzer = analyzer_with_decision_matrix

        # Single weak signal
        from types import SimpleNamespace
        liq_data = [SimpleNamespace(timestamp=123, long_liquidations=1_000_000, short_liquidations=500_000)]
        analyzer._coinglass.get_liquidations = AsyncMock(return_value=liq_data)
        liq_signal = SimpleNamespace(direction='long', reasoning='Liq: weak', confidence=0.30)
        analyzer._liquidation_analyzer.analyze = MagicMock(return_value=liq_signal)

        analyzer._ma_analyzer.analyze = MagicMock(return_value=None)

        direction, reason, confidence = await analyzer.get_combined_signal(
            token_mint="SOL_mint",
            symbol="BTC",
            sentiment_score=0.20,  # Neutral sentiment
            sentiment_grade="C",
            max_positions=10,
            open_positions_count=3,
            prices=[100.0] * 100
        )

        # Only 1 weak signal (0.30 confidence) - below 0.6 threshold
        assert direction == TradeDirection.NEUTRAL
        assert confidence == 0.0
