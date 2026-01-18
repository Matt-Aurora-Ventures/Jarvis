"""
Tests for backtesting engine, walk-forward analysis, Monte Carlo simulations,
and parameter optimization.

TDD: Write tests first, then implement functionality.
"""

import pytest
import math
import statistics
from datetime import datetime, timedelta
from typing import List, Dict, Any
from unittest.mock import Mock, patch, MagicMock

# Test fixtures and data generation
@pytest.fixture
def sample_price_data() -> List[Dict[str, Any]]:
    """Generate sample OHLCV data for testing."""
    base_price = 100.0
    data = []
    for i in range(252):  # 1 year of daily data
        # Simple random walk with mean reversion
        change = (i % 10 - 5) * 0.01  # Oscillating pattern
        base_price = base_price * (1 + change)

        data.append({
            'timestamp': (datetime(2024, 1, 1) + timedelta(days=i)).isoformat(),
            'open': base_price * 0.995,
            'high': base_price * 1.02,
            'low': base_price * 0.98,
            'close': base_price,
            'volume': 1000000 + i * 10000
        })
    return data


@pytest.fixture
def trending_price_data() -> List[Dict[str, Any]]:
    """Generate trending price data."""
    base_price = 100.0
    data = []
    for i in range(100):
        # Strong uptrend
        base_price = base_price * 1.005
        data.append({
            'timestamp': (datetime(2024, 1, 1) + timedelta(days=i)).isoformat(),
            'open': base_price * 0.998,
            'high': base_price * 1.01,
            'low': base_price * 0.99,
            'close': base_price,
            'volume': 1000000
        })
    return data


@pytest.fixture
def volatile_price_data() -> List[Dict[str, Any]]:
    """Generate highly volatile price data."""
    base_price = 100.0
    data = []
    for i in range(100):
        # High volatility with alternating direction
        change = 0.05 if i % 2 == 0 else -0.04
        base_price = base_price * (1 + change)
        data.append({
            'timestamp': (datetime(2024, 1, 1) + timedelta(days=i)).isoformat(),
            'open': base_price * 0.97,
            'high': base_price * 1.03,
            'low': base_price * 0.95,
            'close': base_price,
            'volume': 2000000
        })
    return data


@pytest.fixture
def mock_trade_history() -> List[Dict[str, Any]]:
    """Generate mock trade history for testing."""
    trades = []
    for i in range(50):
        pnl = 10 if i % 3 != 0 else -15  # 66% win rate
        trades.append({
            'id': f't_{i}',
            'entry_time': (datetime(2024, 1, 1) + timedelta(days=i)).isoformat(),
            'exit_time': (datetime(2024, 1, 1) + timedelta(days=i+1)).isoformat(),
            'entry_price': 100.0 + i,
            'exit_price': 100.0 + i + (pnl / 10),
            'pnl': pnl,
            'pnl_pct': pnl,
            'position_size': 100,
        })
    return trades


# ============================================================================
# BACKTEST ENGINE TESTS
# ============================================================================

class TestBacktestEngine:
    """Tests for the main backtesting engine."""

    def test_engine_initialization(self):
        """Test engine can be initialized."""
        from core.backtesting.backtest_engine import AdvancedBacktestEngine
        engine = AdvancedBacktestEngine()
        assert engine is not None

    def test_load_price_data(self, sample_price_data):
        """Test loading historical price data."""
        from core.backtesting.backtest_engine import AdvancedBacktestEngine
        engine = AdvancedBacktestEngine()
        engine.load_data('SOL', sample_price_data)
        assert engine.has_data('SOL')
        assert len(engine.get_data('SOL')) == 252

    def test_run_simple_strategy(self, sample_price_data):
        """Test running a simple buy-and-hold strategy."""
        from core.backtesting.backtest_engine import AdvancedBacktestEngine, BacktestConfig

        engine = AdvancedBacktestEngine()
        engine.load_data('SOL', sample_price_data)

        def buy_and_hold(engine, candle):
            if engine.is_flat():
                engine.buy(1.0, "Buy and hold")

        config = BacktestConfig(
            symbol='SOL',
            start_date='2024-01-01',
            end_date='2024-12-31',
            initial_capital=10000
        )

        result = engine.run(buy_and_hold, config, 'buy_and_hold')

        assert result is not None
        assert result.metrics.total_trades >= 1
        assert result.final_capital > 0

    def test_calculate_sharpe_ratio(self, trending_price_data):
        """Test Sharpe ratio calculation."""
        from core.backtesting.backtest_engine import AdvancedBacktestEngine, BacktestConfig

        engine = AdvancedBacktestEngine()
        engine.load_data('SOL', trending_price_data)

        def trend_follow(engine, candle):
            if engine.is_flat():
                engine.buy(1.0, "Trend follow")

        config = BacktestConfig(
            symbol='SOL',
            start_date='2024-01-01',
            end_date='2024-12-31',
            initial_capital=10000
        )

        result = engine.run(trend_follow, config)

        # Trending market should have positive Sharpe
        assert result.metrics.sharpe_ratio > 0

    def test_calculate_sortino_ratio(self, sample_price_data):
        """Test Sortino ratio calculation."""
        from core.backtesting.backtest_engine import AdvancedBacktestEngine, BacktestConfig

        engine = AdvancedBacktestEngine()
        engine.load_data('SOL', sample_price_data)

        def simple_strategy(engine, candle):
            if engine.is_flat():
                engine.buy(1.0)

        config = BacktestConfig(
            symbol='SOL',
            start_date='2024-01-01',
            end_date='2024-12-31',
            initial_capital=10000
        )

        result = engine.run(simple_strategy, config)

        # Sortino ratio should be calculated
        assert result.metrics.sortino_ratio is not None

    def test_max_drawdown_calculation(self, volatile_price_data):
        """Test max drawdown calculation."""
        from core.backtesting.backtest_engine import AdvancedBacktestEngine, BacktestConfig

        engine = AdvancedBacktestEngine()
        engine.load_data('SOL', volatile_price_data)

        def buy_hold(engine, candle):
            if engine.is_flat():
                engine.buy(1.0)

        config = BacktestConfig(
            symbol='SOL',
            start_date='2024-01-01',
            end_date='2024-12-31',
            initial_capital=10000
        )

        result = engine.run(buy_hold, config)

        # Volatile data should have measurable drawdown
        assert result.metrics.max_drawdown >= 0

    def test_profit_factor_calculation(self, sample_price_data):
        """Test profit factor calculation."""
        from core.backtesting.backtest_engine import AdvancedBacktestEngine, BacktestConfig

        engine = AdvancedBacktestEngine()
        engine.load_data('SOL', sample_price_data)

        # Simple mean reversion strategy
        def mean_reversion(engine, candle):
            if engine.is_flat() and engine.rsi() < 40:
                engine.buy(1.0, "RSI oversold")
            elif engine.is_long() and engine.rsi() > 60:
                engine.sell_all("RSI overbought")

        config = BacktestConfig(
            symbol='SOL',
            start_date='2024-01-01',
            end_date='2024-12-31',
            initial_capital=10000
        )

        result = engine.run(mean_reversion, config)

        # Profit factor should be non-negative
        assert result.metrics.profit_factor >= 0

    def test_recovery_factor_calculation(self, sample_price_data):
        """Test recovery factor calculation."""
        from core.backtesting.backtest_engine import AdvancedBacktestEngine, BacktestConfig

        engine = AdvancedBacktestEngine()
        engine.load_data('SOL', sample_price_data)

        def simple_strategy(engine, candle):
            if engine.is_flat():
                engine.buy(1.0)

        config = BacktestConfig(
            symbol='SOL',
            start_date='2024-01-01',
            end_date='2024-12-31',
            initial_capital=10000
        )

        result = engine.run(simple_strategy, config)

        # Recovery factor should be calculated
        assert hasattr(result.metrics, 'recovery_factor')

    def test_generate_json_report(self, sample_price_data):
        """Test JSON report generation."""
        from core.backtesting.backtest_engine import AdvancedBacktestEngine, BacktestConfig

        engine = AdvancedBacktestEngine()
        engine.load_data('SOL', sample_price_data)

        def simple_strategy(engine, candle):
            if engine.is_flat():
                engine.buy(1.0)

        config = BacktestConfig(
            symbol='SOL',
            start_date='2024-01-01',
            end_date='2024-12-31',
            initial_capital=10000
        )

        result = engine.run(simple_strategy, config)
        report = result.to_json()

        assert 'metrics' in report
        assert 'trades' in report
        assert 'equity_curve' in report

    def test_compare_backtest_vs_live(self, sample_price_data, mock_trade_history):
        """Test comparison of backtest vs live performance."""
        from core.backtesting.backtest_engine import AdvancedBacktestEngine, BacktestConfig

        engine = AdvancedBacktestEngine()
        engine.load_data('SOL', sample_price_data)

        def simple_strategy(engine, candle):
            if engine.is_flat():
                engine.buy(1.0)

        config = BacktestConfig(
            symbol='SOL',
            start_date='2024-01-01',
            end_date='2024-12-31',
            initial_capital=10000
        )

        result = engine.run(simple_strategy, config)
        comparison = engine.compare_with_live(result, mock_trade_history)

        assert 'backtest_return' in comparison
        assert 'live_return' in comparison
        assert 'deviation' in comparison


# ============================================================================
# WALK-FORWARD ANALYSIS TESTS
# ============================================================================

class TestWalkForwardAnalysis:
    """Tests for walk-forward analysis."""

    def test_walk_forward_initialization(self):
        """Test walk-forward analyzer initialization."""
        from core.backtesting.walk_forward import WalkForwardAnalyzer
        analyzer = WalkForwardAnalyzer()
        assert analyzer is not None

    def test_split_train_test_periods(self, sample_price_data):
        """Test splitting data into train/test periods."""
        from core.backtesting.walk_forward import WalkForwardAnalyzer

        analyzer = WalkForwardAnalyzer()
        splits = analyzer.create_splits(
            data=sample_price_data,
            train_size=0.7,
            test_size=0.3,
            n_splits=3
        )

        assert len(splits) == 3
        for split in splits:
            assert 'train' in split
            assert 'test' in split
            assert len(split['train']) > len(split['test'])

    def test_train_test_walk_forward(self, sample_price_data):
        """Test training on period 1, testing on period 2."""
        from core.backtesting.walk_forward import WalkForwardAnalyzer

        analyzer = WalkForwardAnalyzer()

        def simple_strategy(engine, candle):
            if engine.is_flat() and engine.rsi() < 30:
                engine.buy(1.0)
            elif engine.is_long() and engine.rsi() > 70:
                engine.sell_all()

        result = analyzer.run_walk_forward(
            data=sample_price_data,
            strategy=simple_strategy,
            symbol='SOL',
            train_size=0.7,
            test_size=0.3,
            n_splits=3,
            initial_capital=10000
        )

        assert result is not None
        assert len(result.periods) == 3
        for period in result.periods:
            assert hasattr(period, 'train_performance')
            assert hasattr(period, 'test_performance')

    def test_detect_overfitting(self, sample_price_data):
        """Test detection of overfitting (train >> test performance)."""
        from core.backtesting.walk_forward import WalkForwardAnalyzer

        analyzer = WalkForwardAnalyzer()

        def simple_strategy(engine, candle):
            if engine.is_flat():
                engine.buy(1.0)

        result = analyzer.run_walk_forward(
            data=sample_price_data,
            strategy=simple_strategy,
            symbol='SOL',
            train_size=0.7,
            test_size=0.3,
            n_splits=3,
            initial_capital=10000
        )

        overfitting_score = analyzer.calculate_overfitting_score(result)

        # Score should be between 0 and 1 (or higher for severe overfitting)
        assert overfitting_score >= 0

    def test_walk_forward_curve(self, sample_price_data):
        """Test walk-forward degradation curve output."""
        from core.backtesting.walk_forward import WalkForwardAnalyzer

        analyzer = WalkForwardAnalyzer()

        def simple_strategy(engine, candle):
            if engine.is_flat():
                engine.buy(1.0)

        result = analyzer.run_walk_forward(
            data=sample_price_data,
            strategy=simple_strategy,
            symbol='SOL',
            train_size=0.7,
            test_size=0.3,
            n_splits=3,
            initial_capital=10000
        )

        curve = analyzer.get_degradation_curve(result)

        assert len(curve) > 0
        for point in curve:
            assert 'period' in point
            assert 'train_sharpe' in point
            assert 'test_sharpe' in point

    def test_robustness_ratio(self, sample_price_data):
        """Test robustness ratio calculation."""
        from core.backtesting.walk_forward import WalkForwardAnalyzer

        analyzer = WalkForwardAnalyzer()

        def simple_strategy(engine, candle):
            if engine.is_flat():
                engine.buy(1.0)

        result = analyzer.run_walk_forward(
            data=sample_price_data,
            strategy=simple_strategy,
            symbol='SOL',
            train_size=0.7,
            test_size=0.3,
            n_splits=3,
            initial_capital=10000
        )

        robustness = analyzer.calculate_robustness_ratio(result)

        # Robustness ratio: test_performance / train_performance
        # Should be between 0 and ~1 for non-overfit strategies
        assert robustness >= 0


# ============================================================================
# MONTE CARLO SIMULATION TESTS
# ============================================================================

class TestMonteCarloSimulation:
    """Tests for Monte Carlo simulation."""

    def test_monte_carlo_initialization(self):
        """Test Monte Carlo simulator initialization."""
        from core.backtesting.monte_carlo import MonteCarloSimulator
        simulator = MonteCarloSimulator()
        assert simulator is not None

    def test_run_basic_simulation(self, mock_trade_history):
        """Test running basic Monte Carlo simulation."""
        from core.backtesting.monte_carlo import MonteCarloSimulator

        simulator = MonteCarloSimulator()
        result = simulator.run_simulation(
            trades=mock_trade_history,
            n_simulations=1000,
            initial_capital=10000
        )

        assert result is not None
        assert result.n_simulations == 1000

    def test_vary_entry_timing(self, mock_trade_history):
        """Test varying entry timing by +/-5%."""
        from core.backtesting.monte_carlo import MonteCarloSimulator

        simulator = MonteCarloSimulator()
        result = simulator.run_simulation(
            trades=mock_trade_history,
            n_simulations=1000,
            initial_capital=10000,
            entry_timing_variance=0.05  # +/- 5%
        )

        assert result is not None
        # Check that results show variance
        assert result.std_return > 0

    def test_vary_exit_prices(self, mock_trade_history):
        """Test varying exit prices by +/-5%."""
        from core.backtesting.monte_carlo import MonteCarloSimulator

        simulator = MonteCarloSimulator()
        result = simulator.run_simulation(
            trades=mock_trade_history,
            n_simulations=1000,
            initial_capital=10000,
            exit_price_variance=0.05  # +/- 5%
        )

        assert result is not None
        assert result.std_return > 0

    def test_vary_order_size(self, mock_trade_history):
        """Test varying order size by +/-10%."""
        from core.backtesting.monte_carlo import MonteCarloSimulator

        simulator = MonteCarloSimulator()
        result = simulator.run_simulation(
            trades=mock_trade_history,
            n_simulations=1000,
            initial_capital=10000,
            position_size_variance=0.10  # +/- 10%
        )

        assert result is not None
        assert result.std_return > 0

    def test_calculate_percentiles(self, mock_trade_history):
        """Test calculating P10, P50, P90 returns."""
        from core.backtesting.monte_carlo import MonteCarloSimulator

        simulator = MonteCarloSimulator()
        result = simulator.run_simulation(
            trades=mock_trade_history,
            n_simulations=1000,
            initial_capital=10000
        )

        assert result.p10 is not None
        assert result.p50 is not None
        assert result.p90 is not None
        # P10 <= P50 <= P90
        assert result.p10 <= result.p50 <= result.p90

    def test_probability_of_loss(self, mock_trade_history):
        """Test calculating probability of losing more than X%."""
        from core.backtesting.monte_carlo import MonteCarloSimulator

        simulator = MonteCarloSimulator()
        result = simulator.run_simulation(
            trades=mock_trade_history,
            n_simulations=1000,
            initial_capital=10000
        )

        prob_loss_10 = result.probability_of_loss(threshold=0.10)
        prob_loss_25 = result.probability_of_loss(threshold=0.25)

        # Probability should be between 0 and 1
        assert 0 <= prob_loss_10 <= 1
        assert 0 <= prob_loss_25 <= 1
        # Greater loss threshold should have lower probability
        assert prob_loss_25 <= prob_loss_10

    def test_distribution_output(self, mock_trade_history):
        """Test probability distribution curve output."""
        from core.backtesting.monte_carlo import MonteCarloSimulator

        simulator = MonteCarloSimulator()
        result = simulator.run_simulation(
            trades=mock_trade_history,
            n_simulations=1000,
            initial_capital=10000
        )

        distribution = result.get_distribution()

        assert len(distribution) > 0
        assert 'returns' in distribution
        assert len(distribution['returns']) == 1000

    def test_confidence_interval(self, mock_trade_history):
        """Test confidence interval calculation."""
        from core.backtesting.monte_carlo import MonteCarloSimulator

        simulator = MonteCarloSimulator()
        result = simulator.run_simulation(
            trades=mock_trade_history,
            n_simulations=1000,
            initial_capital=10000
        )

        ci_95 = result.confidence_interval(0.95)
        ci_99 = result.confidence_interval(0.99)

        # CI should have lower and upper bounds (lower <= upper)
        assert ci_95['lower'] <= ci_95['upper']
        assert ci_99['lower'] <= ci_99['upper']
        # 99% CI should be at least as wide as 95% CI
        assert (ci_99['upper'] - ci_99['lower']) >= (ci_95['upper'] - ci_95['lower'])

    def test_value_at_risk(self, mock_trade_history):
        """Test Value at Risk calculation."""
        from core.backtesting.monte_carlo import MonteCarloSimulator

        simulator = MonteCarloSimulator()
        result = simulator.run_simulation(
            trades=mock_trade_history,
            n_simulations=1000,
            initial_capital=10000
        )

        var_95 = result.value_at_risk(0.95)
        var_99 = result.value_at_risk(0.99)

        # VaR should be negative (potential loss)
        assert var_99 <= var_95  # 99% VaR should be more negative


# ============================================================================
# PARAMETER OPTIMIZATION TESTS
# ============================================================================

class TestParameterOptimization:
    """Tests for parameter optimization."""

    def test_optimizer_initialization(self):
        """Test parameter optimizer initialization."""
        from core.backtesting.parameter_optimizer import ParameterOptimizer
        optimizer = ParameterOptimizer()
        assert optimizer is not None

    def test_define_parameter_space(self):
        """Test defining parameter search space."""
        from core.backtesting.parameter_optimizer import ParameterOptimizer

        optimizer = ParameterOptimizer()
        optimizer.add_parameter('stop_loss', [0.05, 0.10, 0.15, 0.20])
        optimizer.add_parameter('take_profit', [0.20, 0.50, 1.00, 2.00])
        optimizer.add_parameter('position_size', [0.01, 0.02, 0.05, 0.10])

        space = optimizer.get_parameter_space()

        assert len(space['stop_loss']) == 4
        assert len(space['take_profit']) == 4
        assert len(space['position_size']) == 4

    def test_grid_search(self, sample_price_data):
        """Test grid search optimization."""
        from core.backtesting.parameter_optimizer import ParameterOptimizer

        optimizer = ParameterOptimizer()
        optimizer.add_parameter('rsi_oversold', [20, 30, 40])
        optimizer.add_parameter('rsi_overbought', [60, 70, 80])

        def strategy_factory(params):
            def strategy(engine, candle):
                if engine.is_flat() and engine.rsi() < params['rsi_oversold']:
                    engine.buy(1.0)
                elif engine.is_long() and engine.rsi() > params['rsi_overbought']:
                    engine.sell_all()
            return strategy

        result = optimizer.grid_search(
            data=sample_price_data,
            symbol='SOL',
            strategy_factory=strategy_factory,
            initial_capital=10000,
            metric='sharpe_ratio'
        )

        assert result is not None
        assert 'best_params' in result
        assert 'best_score' in result
        assert len(result['all_results']) == 9  # 3x3 grid

    def test_find_optimal_stop_loss(self, sample_price_data):
        """Test finding optimal stop loss."""
        from core.backtesting.parameter_optimizer import ParameterOptimizer

        optimizer = ParameterOptimizer()
        optimizer.add_parameter('stop_loss', [0.05, 0.10, 0.15, 0.20])

        def strategy_factory(params):
            def strategy(engine, candle):
                if engine.is_flat():
                    engine.buy(1.0)
                # Check stop loss
                if engine.is_long():
                    current_pnl = engine.position.unrealized_pnl / (engine.position.entry_price * engine.position.quantity)
                    if current_pnl < -params['stop_loss']:
                        engine.sell_all("Stop loss")
            return strategy

        result = optimizer.grid_search(
            data=sample_price_data,
            symbol='SOL',
            strategy_factory=strategy_factory,
            initial_capital=10000,
            metric='sharpe_ratio'
        )

        assert 'stop_loss' in result['best_params']

    def test_find_optimal_take_profit(self, sample_price_data):
        """Test finding optimal take profit."""
        from core.backtesting.parameter_optimizer import ParameterOptimizer

        optimizer = ParameterOptimizer()
        optimizer.add_parameter('take_profit', [0.20, 0.50, 1.00, 2.00])

        def strategy_factory(params):
            def strategy(engine, candle):
                if engine.is_flat():
                    engine.buy(1.0)
                # Check take profit
                if engine.is_long():
                    current_pnl = engine.position.unrealized_pnl / (engine.position.entry_price * engine.position.quantity)
                    if current_pnl > params['take_profit']:
                        engine.sell_all("Take profit")
            return strategy

        result = optimizer.grid_search(
            data=sample_price_data,
            symbol='SOL',
            strategy_factory=strategy_factory,
            initial_capital=10000,
            metric='total_return_pct'
        )

        assert 'take_profit' in result['best_params']

    def test_find_optimal_position_size(self, sample_price_data):
        """Test finding optimal position size."""
        from core.backtesting.parameter_optimizer import ParameterOptimizer

        optimizer = ParameterOptimizer()
        optimizer.add_parameter('position_size', [0.01, 0.02, 0.05, 0.10])

        def strategy_factory(params):
            def strategy(engine, candle):
                if engine.is_flat():
                    engine.buy(params['position_size'])
                elif engine.is_long() and engine.rsi() > 70:
                    engine.sell_all()
            return strategy

        result = optimizer.grid_search(
            data=sample_price_data,
            symbol='SOL',
            strategy_factory=strategy_factory,
            initial_capital=10000,
            metric='calmar_ratio'
        )

        assert 'position_size' in result['best_params']

    def test_parameter_matrix_output(self, sample_price_data):
        """Test parameter matrix with performance scores."""
        from core.backtesting.parameter_optimizer import ParameterOptimizer

        optimizer = ParameterOptimizer()
        optimizer.add_parameter('param_a', [1, 2, 3])
        optimizer.add_parameter('param_b', [10, 20])

        def strategy_factory(params):
            def strategy(engine, candle):
                if engine.is_flat():
                    engine.buy(1.0)
            return strategy

        result = optimizer.grid_search(
            data=sample_price_data,
            symbol='SOL',
            strategy_factory=strategy_factory,
            initial_capital=10000,
            metric='sharpe_ratio'
        )

        matrix = optimizer.get_parameter_matrix(result)

        assert matrix is not None
        assert len(matrix) == 6  # 3x2 combinations
        for row in matrix:
            assert 'params' in row
            assert 'score' in row

    def test_optimization_with_constraints(self, sample_price_data):
        """Test optimization with parameter constraints."""
        from core.backtesting.parameter_optimizer import ParameterOptimizer

        optimizer = ParameterOptimizer()
        optimizer.add_parameter('stop_loss', [0.05, 0.10, 0.15])
        optimizer.add_parameter('take_profit', [0.20, 0.50, 1.00])

        # Constraint: take_profit must be > 2 * stop_loss
        def constraint(params):
            return params['take_profit'] > 2 * params['stop_loss']

        optimizer.add_constraint(constraint)

        def strategy_factory(params):
            def strategy(engine, candle):
                if engine.is_flat():
                    engine.buy(1.0)
            return strategy

        result = optimizer.grid_search(
            data=sample_price_data,
            symbol='SOL',
            strategy_factory=strategy_factory,
            initial_capital=10000,
            metric='sharpe_ratio'
        )

        # All results should satisfy constraint
        for r in result['all_results']:
            assert r['params']['take_profit'] > 2 * r['params']['stop_loss']


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestBacktestingIntegration:
    """Integration tests for the backtesting system."""

    def test_full_backtesting_pipeline(self, sample_price_data):
        """Test complete backtesting pipeline."""
        from core.backtesting.backtest_engine import AdvancedBacktestEngine, BacktestConfig
        from core.backtesting.walk_forward import WalkForwardAnalyzer
        from core.backtesting.monte_carlo import MonteCarloSimulator
        from core.backtesting.parameter_optimizer import ParameterOptimizer

        # 1. Run backtest
        engine = AdvancedBacktestEngine()
        engine.load_data('SOL', sample_price_data)

        def simple_strategy(engine, candle):
            if engine.is_flat() and engine.rsi() < 30:
                engine.buy(1.0)
            elif engine.is_long() and engine.rsi() > 70:
                engine.sell_all()

        config = BacktestConfig(
            symbol='SOL',
            start_date='2024-01-01',
            end_date='2024-12-31',
            initial_capital=10000
        )

        bt_result = engine.run(simple_strategy, config)
        assert bt_result is not None

        # 2. Walk-forward analysis
        wf_analyzer = WalkForwardAnalyzer()
        wf_result = wf_analyzer.run_walk_forward(
            data=sample_price_data,
            strategy=simple_strategy,
            symbol='SOL',
            train_size=0.7,
            test_size=0.3,
            n_splits=3,
            initial_capital=10000
        )
        assert wf_result is not None

        # 3. Monte Carlo simulation
        if bt_result.trades:
            mc_simulator = MonteCarloSimulator()
            trades_for_mc = [
                {
                    'id': t.id,
                    'entry_time': t.timestamp,
                    'exit_time': t.timestamp,
                    'entry_price': t.price,
                    'exit_price': t.price * (1 + t.pnl / t.value) if t.value else t.price,
                    'pnl': t.pnl,
                    'pnl_pct': (t.pnl / t.value * 100) if t.value else 0,
                    'position_size': t.quantity,
                }
                for t in bt_result.trades
            ]
            mc_result = mc_simulator.run_simulation(
                trades=trades_for_mc,
                n_simulations=100,
                initial_capital=10000
            )
            assert mc_result is not None

    def test_report_generation(self, sample_price_data):
        """Test full report generation."""
        from core.backtesting.backtest_engine import AdvancedBacktestEngine, BacktestConfig

        engine = AdvancedBacktestEngine()
        engine.load_data('SOL', sample_price_data)

        def simple_strategy(engine, candle):
            if engine.is_flat():
                engine.buy(1.0)

        config = BacktestConfig(
            symbol='SOL',
            start_date='2024-01-01',
            end_date='2024-12-31',
            initial_capital=10000
        )

        result = engine.run(simple_strategy, config)

        # Test JSON report
        json_report = result.to_json()
        assert 'metrics' in json_report

        # Test text report
        text_report = result.to_text()
        assert 'Return' in text_report or 'return' in text_report.lower()


# ============================================================================
# EDGE CASE TESTS
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_data(self):
        """Test handling of empty data."""
        from core.backtesting.backtest_engine import AdvancedBacktestEngine, BacktestConfig

        engine = AdvancedBacktestEngine()

        with pytest.raises(ValueError):
            config = BacktestConfig(
                symbol='SOL',
                start_date='2024-01-01',
                end_date='2024-12-31',
                initial_capital=10000
            )
            engine.run(lambda e, c: None, config)

    def test_no_trades(self, sample_price_data):
        """Test handling when strategy generates no trades."""
        from core.backtesting.backtest_engine import AdvancedBacktestEngine, BacktestConfig

        engine = AdvancedBacktestEngine()
        engine.load_data('SOL', sample_price_data)

        def no_trade_strategy(engine, candle):
            pass  # Never trades

        config = BacktestConfig(
            symbol='SOL',
            start_date='2024-01-01',
            end_date='2024-12-31',
            initial_capital=10000
        )

        result = engine.run(no_trade_strategy, config)

        assert result.metrics.total_trades == 0
        assert result.final_capital == config.initial_capital

    def test_single_trade(self, sample_price_data):
        """Test handling of single trade."""
        from core.backtesting.backtest_engine import AdvancedBacktestEngine, BacktestConfig

        engine = AdvancedBacktestEngine()
        engine.load_data('SOL', sample_price_data)

        traded = [False]
        def single_trade_strategy(engine, candle):
            if not traded[0] and engine.is_flat():
                engine.buy(1.0)
                traded[0] = True

        config = BacktestConfig(
            symbol='SOL',
            start_date='2024-01-01',
            end_date='2024-12-31',
            initial_capital=10000
        )

        result = engine.run(single_trade_strategy, config)

        # Should have at least the buy trade (and auto-close at end)
        assert result.metrics.total_trades >= 1

    def test_monte_carlo_empty_trades(self):
        """Test Monte Carlo with empty trade list."""
        from core.backtesting.monte_carlo import MonteCarloSimulator

        simulator = MonteCarloSimulator()

        with pytest.raises(ValueError):
            simulator.run_simulation(
                trades=[],
                n_simulations=1000,
                initial_capital=10000
            )

    def test_walk_forward_insufficient_data(self):
        """Test walk-forward with insufficient data."""
        from core.backtesting.walk_forward import WalkForwardAnalyzer

        analyzer = WalkForwardAnalyzer()

        # Very short data
        short_data = [
            {'timestamp': '2024-01-01', 'open': 100, 'high': 101, 'low': 99, 'close': 100, 'volume': 1000}
        ]

        with pytest.raises(ValueError):
            analyzer.run_walk_forward(
                data=short_data,
                strategy=lambda e, c: None,
                symbol='SOL',
                train_size=0.7,
                test_size=0.3,
                n_splits=5,
                initial_capital=10000
            )
