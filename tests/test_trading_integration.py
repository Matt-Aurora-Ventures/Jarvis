"""
Trading Integration Tests - Comprehensive Dry-Run Test Suite
============================================================

Tests all trading flows WITHOUT real transactions.
All tests use paper/simulation modes only.

Run with: pytest tests/test_trading_integration.py -v
"""

import json
import math
from pathlib import Path
from typing import Dict, List, Any

import pytest


# =============================================================================
# Test Fixtures
# =============================================================================

def _build_price_series(
    count: int = 100,
    base: float = 100.0,
    trend: str = "up"
) -> List[float]:
    """Generate synthetic price series for testing."""
    prices = []
    price = base
    for i in range(count):
        if trend == "up":
            price = base + (i * 0.3) + math.sin(i / 5) * 1.5
        elif trend == "down":
            price = base - (i * 0.2) + math.sin(i / 5) * 1.5
        else:  # ranging
            price = base + math.sin(i / 10) * 5
        prices.append(max(price, 0.01))
    return prices


def _build_candles(
    count: int = 100,
    base: float = 100.0,
    trend: str = "up"
) -> List[Dict[str, Any]]:
    """Generate synthetic candle data for backtesting."""
    prices = _build_price_series(count, base, trend)
    candles = []
    for i, price in enumerate(prices):
        candles.append({
            "timestamp": i * 3600000,  # 1 hour intervals
            "open": price * 0.99,
            "high": price * 1.01,
            "low": price * 0.98,
            "close": price,
            "volume": 1000 + (i % 100) * 10,
        })
    return candles


# =============================================================================
# Decision Matrix Tests
# =============================================================================

class TestTradingDecisionMatrix:
    """Tests for the unified decision matrix."""
    
    def test_decision_matrix_initialization(self):
        """Test that decision matrix initializes with all strategies."""
        from core.trading_decision_matrix import get_decision_matrix
        
        matrix = get_decision_matrix()
        strategies = matrix.get_all_strategies()
        
        assert len(strategies) >= 10, f"Expected 10+ strategies, got {len(strategies)}"
    
    def test_strategy_registration_completeness(self):
        """Verify all expected strategies are registered."""
        from core.trading_decision_matrix import get_decision_matrix
        
        matrix = get_decision_matrix()
        expected_names = [
            "TrendFollower",
            "MeanReversion",
            "DCABot",
            "ArbitrageScanner",
            "TriangularArbitrage",
            "GridTrader",
            "BreakoutTrader",
            "MarketMaker",
            "RegimeDetector",
            "SentimentAnalyzer",
        ]
        
        registered_names = [s.name for s in matrix.get_all_strategies()]
        
        for name in expected_names:
            assert name in registered_names, f"Strategy '{name}' not registered"
    
    def test_strategy_selection_trending_regime(self):
        """Test strategy selection for trending market."""
        from core.trading_decision_matrix import get_decision_matrix
        
        matrix = get_decision_matrix()
        strategy = matrix.select_strategy_for_regime("trending")
        
        assert strategy is not None
        assert strategy.matches_regime("trending")
    
    def test_strategy_selection_chopping_regime(self):
        """Test strategy selection for ranging/chopping market."""
        from core.trading_decision_matrix import get_decision_matrix
        
        matrix = get_decision_matrix()
        strategy = matrix.select_strategy_for_regime("chopping")
        
        assert strategy is not None
        assert strategy.matches_regime("chopping")
    
    def test_training_data_export(self):
        """Test training data export contains all required fields."""
        from core.trading_decision_matrix import get_decision_matrix
        
        matrix = get_decision_matrix()
        data = matrix.export_training_data()
        
        assert "strategies" in data
        assert "system_prompt" in data
        assert "decision_flow" in data
        assert "categories" in data
        assert len(data["strategies"]) >= 10
        assert len(data["system_prompt"]) > 100  # Non-trivial prompt
    
    def test_system_prompt_generation(self):
        """Test system prompt contains key information."""
        from core.trading_decision_matrix import get_decision_matrix
        
        matrix = get_decision_matrix()
        prompt = matrix.get_system_prompt()
        
        # Check for key sections
        assert "Strategy" in prompt or "strategy" in prompt
        assert "Safety" in prompt or "CRITICAL" in prompt
        assert "Solana" in prompt
    
    def test_strategy_metadata_completeness(self):
        """Verify each strategy has complete metadata."""
        from core.trading_decision_matrix import get_decision_matrix
        
        matrix = get_decision_matrix()
        
        for strategy in matrix.get_all_strategies():
            assert strategy.id, f"{strategy.name} missing id"
            assert strategy.category, f"{strategy.name} missing category"
            assert strategy.implementation, f"{strategy.name} missing implementation"
            assert len(strategy.regime_fit) > 0, f"{strategy.name} missing regime_fit"
            # These are important for AI understanding
            assert strategy.paper_safe is True, f"{strategy.name} not paper safe"


# =============================================================================
# Logic Core Integration Tests
# =============================================================================

class TestLogicCoreIntegration:
    """Tests for logic core with decision matrix integration."""
    
    def test_logic_core_cycle_paper_mode(self):
        """Test full logic core cycle in paper mode."""
        from core.logic_core import LogicCore, MarketSnapshot
        
        lc = LogicCore()
        prices = _build_price_series(50, trend="up")
        snapshot = MarketSnapshot(symbol="SOL", prices=prices)
        
        decision = lc.run_cycle(snapshot)
        
        assert decision is not None
        assert decision.strategy in ["Momentum", "MeanReversion", "Arbitrage", "TrendFollower"]
        assert decision.decision in ["EXECUTE", "WAIT"]
        assert decision.gate is not None
    
    def test_logic_core_uses_decision_matrix(self):
        """Verify logic core integrates with decision matrix."""
        from core.logic_core import LogicCore, MarketSnapshot
        from core.trading_decision_matrix import get_decision_matrix
        
        # Ensure matrix is initialized
        matrix = get_decision_matrix()
        assert len(matrix.get_all_strategies()) > 0
        
        lc = LogicCore()
        prices = _build_price_series(50, trend="up")
        snapshot = MarketSnapshot(symbol="SOL", prices=prices)
        
        decision = lc.run_cycle(snapshot)
        
        # Should not crash even if decision matrix has issues
        assert decision is not None
    
    def test_logic_core_regime_detection(self):
        """Test regime detection for different market conditions."""
        from core.logic_core import LogicCore, MarketSnapshot
        
        lc = LogicCore()
        
        # Trending up prices
        up_prices = _build_price_series(50, trend="up")
        up_snapshot = MarketSnapshot(symbol="SOL", prices=up_prices)
        up_decision = lc.run_cycle(up_snapshot)
        
        # Ranging prices
        range_prices = _build_price_series(50, trend="range")
        range_snapshot = MarketSnapshot(symbol="SOL", prices=range_prices)
        range_decision = lc.run_cycle(range_snapshot)
        
        # Both should produce valid decisions
        assert up_decision.decision in ["EXECUTE", "WAIT"]
        assert range_decision.decision in ["EXECUTE", "WAIT"]
    
    def test_logic_core_gate_checks(self):
        """Test that gate checks run properly."""
        from core.logic_core import LogicCore, MarketSnapshot
        
        lc = LogicCore()
        prices = _build_price_series(50)
        snapshot = MarketSnapshot(symbol="SOL", prices=prices)
        
        decision = lc.run_cycle(snapshot)
        
        # Gate should have checks
        assert decision.gate is not None
        assert hasattr(decision.gate, "checks")
        assert isinstance(decision.gate.checks, list)


# =============================================================================
# Trading Pipeline Tests
# =============================================================================

class TestTradingPipeline:
    """Tests for the trading pipeline backtesting."""
    
    def test_backtest_sma_cross(self):
        """Test SMA cross backtest runs without errors."""
        from core import trading_pipeline
        
        candles = _build_candles(80)
        strategy = trading_pipeline.StrategyConfig(
            kind="sma_cross",
            params={"fast": 5, "slow": 15},
            capital_usd=1000.0,
        )
        
        result = trading_pipeline.run_backtest(candles, "SOL", "1h", strategy)
        
        assert result.error is None
        assert isinstance(result.sharpe_ratio, float)
        assert isinstance(result.roi, float)
    
    def test_backtest_rsi_strategy(self):
        """Test RSI strategy backtest."""
        from core import trading_pipeline
        
        candles = _build_candles(80)
        strategy = trading_pipeline.StrategyConfig(
            kind="rsi",
            params={"period": 14, "lower": 30, "upper": 70},
            capital_usd=1000.0,
        )
        
        result = trading_pipeline.run_backtest(candles, "SOL", "1h", strategy)
        
        assert result.error is None
    
    def test_walk_forward_backtest(self):
        """Test walk-forward validation runs."""
        from core import trading_pipeline
        
        candles = _build_candles(200)  # Need more data for walk-forward
        strategy = trading_pipeline.StrategyConfig(
            kind="sma_cross",
            params={"fast": 5, "slow": 15},
            capital_usd=1000.0,
        )
        
        results = trading_pipeline.walk_forward_backtest(
            candles, "SOL", "1h", strategy,
            n_splits=3,  # Fewer splits for test speed
        )
        
        assert len(results) > 0
        for result in results:
            assert result.error is None


# =============================================================================
# Strategy Tests (Paper Mode)
# =============================================================================

class TestTradingStrategies:
    """Tests for individual trading strategies."""
    
    def test_trend_follower_signal(self):
        """Test TrendFollower generates valid signals."""
        from core.trading_strategies import TrendFollower
        
        strategy = TrendFollower(short_period=5, long_period=15)
        prices = _build_price_series(50, trend="up")
        
        signal = strategy.analyze(prices, "SOL")
        
        assert signal is not None
        assert signal.action in ["BUY", "SELL", "HOLD"]
        assert 0 <= signal.confidence <= 1
    
    def test_mean_reversion_signal(self):
        """Test MeanReversion generates valid signals."""
        from core.trading_strategies import MeanReversion
        
        strategy = MeanReversion()
        prices = _build_price_series(50, trend="range")
        
        signal = strategy.analyze(prices, "SOL")
        
        assert signal is not None
        assert signal.action in ["BUY", "SELL", "HOLD"]
    
    def test_dca_bot_signal(self):
        """Test DCABot generates buy signals."""
        from core.trading_strategies import DCABot
        
        strategy = DCABot(interval_hours=0.001)  # Very short for testing
        prices = _build_price_series(50)
        
        signal = strategy.analyze(prices, "SOL")
        
        assert signal is not None
        # DCA always tends to buy


# =============================================================================
# Solana Execution Tests (Simulation Only)
# =============================================================================

class TestSolanaExecution:
    """Tests for Solana execution - simulation mode only."""
    
    def test_simulation_error_classification(self):
        """Test error classification for Solana simulation errors."""
        from core.solana_execution import classify_simulation_error
        
        # Test known error patterns
        assert classify_simulation_error("blockhash not found") == "blockhash_expired"
        assert classify_simulation_error("InstructionError: [0, Custom(6001)]") == "custom_program_error"
        assert classify_simulation_error("insufficient funds") == "insufficient_funds"
        assert classify_simulation_error("unknown error") == "unknown"
    
    def test_simulation_error_description(self):
        """Test human-readable error descriptions."""
        from core.solana_execution import describe_simulation_error
        
        desc = describe_simulation_error("blockhash not found")
        assert desc is not None
        assert "blockhash" in desc.lower() or "stale" in desc.lower()


# =============================================================================
# Jupiter API Tests (Read-Only)
# =============================================================================

class TestJupiterAPI:
    """Tests for Jupiter API - read-only operations."""
    
    @pytest.mark.skipif(True, reason="Requires network access")
    def test_get_sol_price(self):
        """Test SOL price retrieval from Jupiter."""
        from core.jupiter import get_sol_price_in_usd
        
        price = get_sol_price_in_usd()
        
        if price is not None:
            assert price > 0
            assert price < 10000  # Sanity check


# =============================================================================
# Exit Intent Tests (Paper Mode)
# =============================================================================

class TestExitIntents:
    """Tests for exit intent lifecycle - paper mode only."""
    
    def test_create_spot_intent(self):
        """Test creating a spot exit intent."""
        from core.exit_intents import create_spot_intent
        
        intent = create_spot_intent(
            position_id="test-001",
            token_mint="So11111111111111111111111111111111111111112",
            symbol="SOL",
            entry_price=100.0,
            quantity=1.0,
            is_paper=True,  # Always paper mode
        )
        
        assert intent is not None
        assert intent.is_paper is True
        assert len(intent.take_profits) == 3
        assert intent.stop_loss is not None
    
    def test_exit_intent_to_dict(self):
        """Test exit intent serialization."""
        from core.exit_intents import create_spot_intent
        
        intent = create_spot_intent(
            position_id="test-002",
            token_mint="So11111111111111111111111111111111111111112",
            symbol="SOL",
            entry_price=100.0,
            quantity=1.0,
            is_paper=True,
        )
        
        data = intent.to_dict()
        
        assert "position_id" in data
        assert "take_profits" in data
        assert "stop_loss" in data
        assert data["is_paper"] is True


# =============================================================================
# Risk Manager Tests
# =============================================================================

class TestRiskManager:
    """Tests for risk management."""
    
    def test_position_sizer_calculation(self):
        """Test position sizing calculation."""
        from core.risk_manager import PositionSizer, RiskLimits
        
        sizer = PositionSizer(RiskLimits(max_position_pct=2.0))
        
        result = sizer.calculate_position(
            capital=10000.0,
            entry_price=100.0,
            stop_loss_price=95.0,
        )
        
        assert "position_size" in result
        assert "quantity" in result
        assert result["position_size"] <= 10000.0 * 0.02  # Max 2%
    
    def test_stop_take_calculation(self):
        """Test stop-loss/take-profit calculation."""
        from core.risk_manager import PositionSizer
        
        sizer = PositionSizer()
        
        result = sizer.calculate_stop_take(
            entry_price=100.0,
            direction="LONG",
        )
        
        assert "stop_loss" in result
        assert "take_profit" in result
        assert result["stop_loss"] < 100.0  # Below entry for long
        assert result["take_profit"] > 100.0  # Above entry for long


# =============================================================================
# Full Integration Flow Test
# =============================================================================

class TestFullIntegrationFlow:
    """End-to-end integration test for trading flow."""
    
    def test_complete_paper_trading_flow(self):
        """
        Test complete trading flow from strategy selection to exit intent.
        All in paper mode - NO REAL TRANSACTIONS.
        """
        from core.trading_decision_matrix import get_decision_matrix
        from core.logic_core import LogicCore, MarketSnapshot
        from core.exit_intents import create_spot_intent
        from core.risk_manager import PositionSizer
        
        # 1. Get decision matrix
        matrix = get_decision_matrix()
        assert len(matrix.get_all_strategies()) >= 10
        
        # 2. Create market snapshot
        prices = _build_price_series(50, trend="up")
        snapshot = MarketSnapshot(symbol="SOL", prices=prices)
        
        # 3. Run logic core decision
        lc = LogicCore()
        decision = lc.run_cycle(snapshot)
        assert decision is not None
        
        # 4. If execute, create position sizing
        if decision.decision == "EXECUTE" and decision.plan:
            sizer = PositionSizer()
            position = sizer.calculate_position(
                capital=1000.0,
                entry_price=decision.plan.entry,
                stop_loss_price=decision.plan.stop,
            )
            assert position["position_size"] > 0
            
            # 5. Create exit intent (paper mode)
            intent = create_spot_intent(
                position_id="integration-test",
                token_mint="So11111111111111111111111111111111111111112",
                symbol="SOL",
                entry_price=decision.plan.entry,
                quantity=position["quantity"],
                is_paper=True,
            )
            assert intent.is_paper is True
            assert len(intent.take_profits) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
