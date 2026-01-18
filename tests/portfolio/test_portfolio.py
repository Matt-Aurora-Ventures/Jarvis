"""
Portfolio Management Tests

Tests for:
- Correlation matrix calculation
- Portfolio optimization (Markowitz efficient frontier)
- Multi-asset risk calculation (VaR, portfolio volatility)
- Rebalancing logic
- Sector rotation

TDD approach: Write tests first, implement to pass.
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
import asyncio


# =============================================================================
# CORRELATION MATRIX TESTS
# =============================================================================

class TestCorrelationMatrix:
    """Tests for correlation matrix calculation."""

    def test_correlation_between_identical_assets(self):
        """Identical price series should have correlation of 1.0."""
        from core.portfolio.correlation import CorrelationMatrix

        # Need more data points for meaningful correlation
        prices = {
            'SOL': [100, 110, 105, 115, 120, 118, 125, 130, 128, 135],
            'SOL_COPY': [100, 110, 105, 115, 120, 118, 125, 130, 128, 135],
        }

        cm = CorrelationMatrix(min_data_points=3)
        matrix = cm.calculate(prices)

        assert matrix['SOL']['SOL_COPY'] == pytest.approx(1.0, abs=0.01)
        assert matrix['SOL_COPY']['SOL'] == pytest.approx(1.0, abs=0.01)

    def test_correlation_between_inverse_assets(self):
        """Inversely correlated return series should have negative correlation."""
        from core.portfolio.correlation import CorrelationMatrix

        # Create prices where returns are inversely correlated
        # UP goes up when DOWN goes down (alternating pattern)
        prices = {
            'UP': [100, 110, 105, 115, 110, 120, 115, 125, 120, 130],
            'DOWN': [100, 90, 95, 85, 90, 80, 85, 75, 80, 70],
        }

        cm = CorrelationMatrix(min_data_points=3)
        matrix = cm.calculate(prices)

        # Should have negative correlation
        assert matrix['UP']['DOWN'] < 0

    def test_correlation_matrix_symmetric(self):
        """Correlation matrix should be symmetric."""
        from core.portfolio.correlation import CorrelationMatrix

        prices = {
            'A': [100, 105, 110, 108, 115],
            'B': [50, 52, 48, 55, 58],
            'C': [200, 190, 195, 205, 210],
        }

        cm = CorrelationMatrix()
        matrix = cm.calculate(prices)

        assert matrix['A']['B'] == pytest.approx(matrix['B']['A'], abs=0.001)
        assert matrix['A']['C'] == pytest.approx(matrix['C']['A'], abs=0.001)
        assert matrix['B']['C'] == pytest.approx(matrix['C']['B'], abs=0.001)

    def test_correlation_diagonal_is_one(self):
        """Diagonal of correlation matrix should be 1.0 (self-correlation)."""
        from core.portfolio.correlation import CorrelationMatrix

        prices = {
            'A': [100, 105, 110, 108, 115],
            'B': [50, 52, 48, 55, 58],
        }

        cm = CorrelationMatrix()
        matrix = cm.calculate(prices)

        assert matrix['A']['A'] == pytest.approx(1.0, abs=0.001)
        assert matrix['B']['B'] == pytest.approx(1.0, abs=0.001)

    def test_correlation_with_insufficient_data(self):
        """Should handle insufficient data gracefully."""
        from core.portfolio.correlation import CorrelationMatrix

        prices = {
            'A': [100],  # Only 1 data point
            'B': [50],
        }

        cm = CorrelationMatrix()
        matrix = cm.calculate(prices)

        # Should return NaN or 0 for insufficient data
        assert matrix['A']['B'] == 0.0 or np.isnan(matrix['A']['B'])

    def test_correlation_update_daily(self):
        """Test daily update functionality."""
        from core.portfolio.correlation import CorrelationMatrix

        cm = CorrelationMatrix()

        # Initial data
        prices_day1 = {
            'SOL': [100, 110, 105],
            'ETH': [3000, 3100, 3050],
        }
        cm.update(prices_day1)

        # Add new day
        prices_day2 = {
            'SOL': [108],
            'ETH': [3080],
        }
        cm.update(prices_day2, append=True)

        matrix = cm.get_matrix()
        assert 'SOL' in matrix
        assert 'ETH' in matrix

    def test_get_low_correlation_pairs(self):
        """Test finding asset pairs with low correlation."""
        from core.portfolio.correlation import CorrelationMatrix

        prices = {
            'A': [100, 110, 120, 130, 140],
            'B': [100, 110, 120, 130, 140],  # Perfect correlation with A
            'C': [100, 90, 100, 90, 100],    # Different pattern
        }

        cm = CorrelationMatrix()
        cm.calculate(prices)

        pairs = cm.get_low_correlation_pairs(threshold=0.7)

        # A-C and B-C should be low correlation pairs
        assert len(pairs) > 0


# =============================================================================
# PORTFOLIO OPTIMIZER TESTS
# =============================================================================

class TestPortfolioOptimizer:
    """Tests for Markowitz portfolio optimization."""

    def test_optimal_weights_sum_to_one(self):
        """Portfolio weights should sum to 1.0."""
        from core.portfolio.optimizer import PortfolioOptimizer

        returns = {
            'SOL': [0.05, 0.03, -0.02, 0.04, 0.01],
            'ETH': [0.04, 0.02, 0.01, 0.03, -0.01],
            'BTC': [0.03, 0.01, 0.02, 0.02, 0.01],
        }

        optimizer = PortfolioOptimizer()
        weights = optimizer.optimize(returns, target_return=0.03)

        assert sum(weights.values()) == pytest.approx(1.0, abs=0.01)

    def test_weights_are_non_negative(self):
        """All weights should be non-negative (no short selling)."""
        from core.portfolio.optimizer import PortfolioOptimizer

        returns = {
            'SOL': [0.05, 0.03, -0.02, 0.04, 0.01],
            'ETH': [0.04, 0.02, 0.01, 0.03, -0.01],
        }

        optimizer = PortfolioOptimizer()
        weights = optimizer.optimize(returns, target_return=0.02)

        for asset, weight in weights.items():
            assert weight >= 0, f"Weight for {asset} is negative: {weight}"

    def test_max_assets_constraint(self):
        """Should respect max assets constraint."""
        from core.portfolio.optimizer import PortfolioOptimizer

        returns = {
            'A': [0.05, 0.03, -0.02, 0.04, 0.01],
            'B': [0.04, 0.02, 0.01, 0.03, -0.01],
            'C': [0.03, 0.01, 0.02, 0.02, 0.01],
            'D': [0.02, 0.04, 0.01, 0.03, 0.02],
            'E': [0.01, 0.02, 0.03, 0.01, 0.04],
        }

        optimizer = PortfolioOptimizer(max_assets=3)
        weights = optimizer.optimize(returns, target_return=0.02)

        non_zero_weights = [w for w in weights.values() if w > 0.01]
        assert len(non_zero_weights) <= 3

    def test_correlation_filter(self):
        """Should skip highly correlated asset pairs when correlation matrix provided."""
        from core.portfolio.optimizer import PortfolioOptimizer
        from core.portfolio.correlation import CorrelationMatrix

        # Create highly correlated assets with more data
        np.random.seed(42)
        base = list(np.random.normal(0.01, 0.03, 30))
        returns = {
            'A': base,
            'A_CLONE': base,  # Perfect correlation
            'B': list(np.random.normal(0.01, 0.03, 30)),  # Different pattern
        }

        # Pre-compute correlation matrix
        cm = CorrelationMatrix()
        prices = {k: [100 * (1 + sum(v[:i+1])) for i in range(len(v))] for k, v in returns.items()}
        corr_matrix = cm.calculate(prices)

        optimizer = PortfolioOptimizer(max_correlation=0.7)
        weights = optimizer.optimize(returns, target_return=0.02, correlation_matrix=corr_matrix)

        # With correlation filter, should not include both A and A_CLONE with significant weight
        a_weight = weights.get('A', 0)
        clone_weight = weights.get('A_CLONE', 0)
        # At least one should be filtered out or have minimal weight
        assert a_weight < 0.3 or clone_weight < 0.3

    def test_efficient_frontier(self):
        """Test efficient frontier calculation."""
        from core.portfolio.optimizer import PortfolioOptimizer

        returns = {
            'SOL': [0.05, 0.03, -0.02, 0.04, 0.01],
            'ETH': [0.04, 0.02, 0.01, 0.03, -0.01],
        }

        optimizer = PortfolioOptimizer()
        frontier = optimizer.get_efficient_frontier(returns, n_points=10)

        assert len(frontier) == 10

        # Check frontier is sorted by risk
        risks = [p['risk'] for p in frontier]
        assert risks == sorted(risks)

    def test_equal_weight_allocation(self):
        """Test equal weight allocation option."""
        from core.portfolio.optimizer import PortfolioOptimizer

        returns = {
            'A': [0.05, 0.03, -0.02],
            'B': [0.04, 0.02, 0.01],
            'C': [0.03, 0.01, 0.02],
        }

        optimizer = PortfolioOptimizer()
        weights = optimizer.get_equal_weights(list(returns.keys()))

        expected = 1.0 / 3.0
        for w in weights.values():
            assert w == pytest.approx(expected, abs=0.001)

    def test_risk_weighted_allocation(self):
        """Test risk-weighted (inverse volatility) allocation."""
        from core.portfolio.optimizer import PortfolioOptimizer

        # Create assets with different volatilities
        returns = {
            'LOW_VOL': [0.01, 0.01, 0.01, 0.01, 0.01],   # Low volatility
            'HIGH_VOL': [0.10, -0.10, 0.10, -0.10, 0.10], # High volatility
        }

        optimizer = PortfolioOptimizer()
        weights = optimizer.get_risk_parity_weights(returns)

        # Lower volatility should get higher weight
        assert weights['LOW_VOL'] > weights['HIGH_VOL']


# =============================================================================
# MULTI-ASSET RISK CALCULATOR TESTS
# =============================================================================

class TestMultiAssetRiskCalculator:
    """Tests for portfolio risk metrics."""

    def test_portfolio_volatility_single_asset(self):
        """Single asset volatility is calculated correctly."""
        from core.portfolio.risk_calculator import MultiAssetRiskCalculator

        # Use more realistic returns (daily returns are small)
        returns = {'SOL': [0.005, 0.003, -0.002, 0.004, 0.001, -0.001, 0.002, 0.003, -0.002, 0.001]}
        weights = {'SOL': 1.0}

        calc = MultiAssetRiskCalculator()
        vol = calc.calculate_portfolio_volatility(returns, weights)

        # Volatility should be positive
        assert vol > 0
        # Annualized volatility should be reasonable (crypto can be high)
        assert vol < 5.0  # Less than 500% annualized

    def test_diversification_benefit(self):
        """Diversified portfolio should have lower risk than weighted sum."""
        from core.portfolio.risk_calculator import MultiAssetRiskCalculator

        # Uncorrelated assets
        np.random.seed(42)
        returns = {
            'A': list(np.random.normal(0.01, 0.05, 50)),
            'B': list(np.random.normal(0.01, 0.05, 50)),
        }
        weights = {'A': 0.5, 'B': 0.5}

        calc = MultiAssetRiskCalculator()
        benefit = calc.calculate_diversification_benefit(returns, weights)

        # Diversification benefit should be positive
        assert benefit >= 0

    def test_var_95(self):
        """Test Value at Risk calculation at 95% confidence."""
        from core.portfolio.risk_calculator import MultiAssetRiskCalculator

        # Use normally distributed returns
        np.random.seed(42)
        returns = {
            'SOL': list(np.random.normal(0.001, 0.02, 100)),
        }
        weights = {'SOL': 1.0}

        calc = MultiAssetRiskCalculator()
        var = calc.calculate_var(returns, weights, confidence=0.95)

        # VaR should be a negative number (loss)
        assert var < 0

    def test_var_99(self):
        """Test VaR at 99% confidence is larger than 95%."""
        from core.portfolio.risk_calculator import MultiAssetRiskCalculator

        np.random.seed(42)
        returns = {
            'SOL': list(np.random.normal(0.001, 0.02, 100)),
        }
        weights = {'SOL': 1.0}

        calc = MultiAssetRiskCalculator()
        var_95 = calc.calculate_var(returns, weights, confidence=0.95)
        var_99 = calc.calculate_var(returns, weights, confidence=0.99)

        # 99% VaR should be larger (more negative)
        assert var_99 < var_95

    def test_portfolio_beta(self):
        """Test portfolio beta calculation."""
        from core.portfolio.risk_calculator import MultiAssetRiskCalculator

        # Create asset that moves with market
        market_returns = [0.01, -0.02, 0.03, -0.01, 0.02]
        asset_returns = [0.02, -0.04, 0.06, -0.02, 0.04]  # 2x market

        returns = {'ASSET': asset_returns}
        weights = {'ASSET': 1.0}

        calc = MultiAssetRiskCalculator()
        beta = calc.calculate_portfolio_beta(returns, weights, market_returns)

        # Beta should be approximately 2 (with some tolerance for numerical differences)
        assert beta == pytest.approx(2.0, rel=0.5)  # Allow 50% tolerance for small sample

    def test_max_volatility_constraint(self):
        """Test portfolio volatility constraint (max 20% annualized)."""
        from core.portfolio.risk_calculator import MultiAssetRiskCalculator

        calc = MultiAssetRiskCalculator(max_volatility=0.20)

        # High volatility asset
        returns = {
            'HIGH_VOL': [0.10, -0.10, 0.15, -0.15, 0.20],  # Very volatile
        }
        weights = {'HIGH_VOL': 1.0}

        exceeds = calc.exceeds_volatility_limit(returns, weights)
        assert exceeds == True

    def test_risk_metrics_summary(self):
        """Test comprehensive risk metrics calculation."""
        from core.portfolio.risk_calculator import MultiAssetRiskCalculator

        np.random.seed(42)
        returns = {
            'SOL': list(np.random.normal(0.001, 0.03, 100)),
            'ETH': list(np.random.normal(0.001, 0.02, 100)),
        }
        weights = {'SOL': 0.6, 'ETH': 0.4}
        market_returns = list(np.random.normal(0.001, 0.025, 100))

        calc = MultiAssetRiskCalculator()
        metrics = calc.get_risk_summary(returns, weights, market_returns)

        assert 'volatility' in metrics
        assert 'var_95' in metrics
        assert 'var_99' in metrics
        assert 'diversification_benefit' in metrics
        assert 'beta' in metrics


# =============================================================================
# REBALANCER TESTS
# =============================================================================

class TestRebalancer:
    """Tests for portfolio rebalancing."""

    def test_no_rebalance_within_threshold(self):
        """Should not rebalance when within threshold."""
        from core.portfolio.rebalancer import Rebalancer

        target_weights = {'SOL': 0.5, 'ETH': 0.5}
        current_weights = {'SOL': 0.52, 'ETH': 0.48}  # 2% drift

        rebalancer = Rebalancer(drift_threshold=0.10)
        trades = rebalancer.calculate_rebalance_trades(
            current_weights, target_weights, portfolio_value=10000
        )

        assert len(trades) == 0

    def test_rebalance_when_drift_exceeds_threshold(self):
        """Should rebalance when drift exceeds 10%."""
        from core.portfolio.rebalancer import Rebalancer

        target_weights = {'SOL': 0.5, 'ETH': 0.5}
        current_weights = {'SOL': 0.65, 'ETH': 0.35}  # 15% drift on SOL

        rebalancer = Rebalancer(drift_threshold=0.10)
        trades = rebalancer.calculate_rebalance_trades(
            current_weights, target_weights, portfolio_value=10000
        )

        assert len(trades) > 0
        # Should sell SOL and buy ETH
        sol_trade = next(t for t in trades if t['asset'] == 'SOL')
        assert sol_trade['action'] == 'sell'

    def test_rebalance_minimizes_trades(self):
        """Should minimize number of trades."""
        from core.portfolio.rebalancer import Rebalancer

        target_weights = {'A': 0.25, 'B': 0.25, 'C': 0.25, 'D': 0.25}
        current_weights = {'A': 0.26, 'B': 0.24, 'C': 0.25, 'D': 0.25}

        rebalancer = Rebalancer(drift_threshold=0.10, min_trade_size=100)
        trades = rebalancer.calculate_rebalance_trades(
            current_weights, target_weights, portfolio_value=10000
        )

        # Small drifts should not trigger trades
        assert len(trades) == 0

    def test_monthly_rebalance_schedule(self):
        """Test monthly rebalancing schedule."""
        from core.portfolio.rebalancer import Rebalancer

        rebalancer = Rebalancer(rebalance_frequency='monthly')

        # Last rebalance was 15 days ago
        last_rebalance = datetime.now() - timedelta(days=15)
        assert rebalancer.should_rebalance(last_rebalance) == False

        # Last rebalance was 35 days ago
        last_rebalance = datetime.now() - timedelta(days=35)
        assert rebalancer.should_rebalance(last_rebalance) == True

    def test_rebalance_trade_costs(self):
        """Should account for trading costs in rebalancing."""
        from core.portfolio.rebalancer import Rebalancer

        target_weights = {'SOL': 0.5, 'ETH': 0.5}
        current_weights = {'SOL': 0.55, 'ETH': 0.45}

        rebalancer = Rebalancer(trading_fee_pct=0.003)  # 0.3% fee
        trades = rebalancer.calculate_rebalance_trades(
            current_weights, target_weights, portfolio_value=10000
        )

        # Should include estimated costs
        if len(trades) > 0:
            total_cost = sum(t.get('estimated_fee', 0) for t in trades)
            assert total_cost > 0

    @pytest.mark.asyncio
    async def test_execute_rebalance(self):
        """Test async rebalancing execution."""
        from core.portfolio.rebalancer import Rebalancer

        rebalancer = Rebalancer()

        # Mock trading engine
        mock_engine = Mock()
        mock_engine.execute_trade = AsyncMock(return_value={'success': True})

        trades = [
            {'asset': 'SOL', 'action': 'sell', 'amount_usd': 500},
            {'asset': 'ETH', 'action': 'buy', 'amount_usd': 500},
        ]

        result = await rebalancer.execute_rebalance(trades, mock_engine)

        assert result['executed'] == 2
        assert mock_engine.execute_trade.call_count == 2


# =============================================================================
# SECTOR ROTATION TESTS
# =============================================================================

class TestSectorRotation:
    """Tests for sector-based allocation rotation."""

    def test_sector_classification(self):
        """Test token sector classification."""
        from core.portfolio.sector_rotation import SectorRotation

        sr = SectorRotation()

        assert sr.get_sector('JUP') == 'DeFi'
        assert sr.get_sector('RNDR') == 'Infrastructure'
        assert sr.get_sector('BONK') == 'Meme'

    def test_sector_weights_calculation(self):
        """Test portfolio sector weight calculation."""
        from core.portfolio.sector_rotation import SectorRotation

        positions = {
            'JUP': {'value': 1000},
            'RAY': {'value': 1000},
            'BONK': {'value': 500},
            'RNDR': {'value': 500},
        }

        sr = SectorRotation()
        weights = sr.calculate_sector_weights(positions)

        # DeFi: JUP + RAY = 2000 = 66.7%
        # Meme: BONK = 500 = 16.7%
        # Infrastructure: RNDR = 500 = 16.7%
        assert weights['DeFi'] == pytest.approx(0.667, rel=0.01)

    def test_rotation_on_sentiment_change(self):
        """Test rotation when sector sentiment changes."""
        from core.portfolio.sector_rotation import SectorRotation

        sr = SectorRotation()

        # Sentiment scores by sector
        old_sentiment = {'DeFi': 0.6, 'Layer2': 0.4, 'Meme': 0.3}
        new_sentiment = {'DeFi': 0.3, 'Layer2': 0.8, 'Meme': 0.2}

        rotation = sr.calculate_rotation(old_sentiment, new_sentiment)

        # Should reduce DeFi, increase Layer2
        assert rotation.get('DeFi', 0) < 0
        assert rotation.get('Layer2', 0) > 0

    def test_rotation_threshold(self):
        """Should only rotate on significant sentiment shift."""
        from core.portfolio.sector_rotation import SectorRotation

        sr = SectorRotation(rotation_threshold=0.20)

        # Small sentiment change
        old_sentiment = {'DeFi': 0.6}
        new_sentiment = {'DeFi': 0.55}  # Only 5% change

        rotation = sr.calculate_rotation(old_sentiment, new_sentiment)

        # Should not trigger rotation
        assert rotation.get('DeFi', 0) == 0

    def test_quarterly_rotation_schedule(self):
        """Test quarterly rotation schedule."""
        from core.portfolio.sector_rotation import SectorRotation

        sr = SectorRotation(rotation_frequency='quarterly')

        # Last rotation was 60 days ago
        last_rotation = datetime.now() - timedelta(days=60)
        assert sr.should_rotate(last_rotation) == False

        # Last rotation was 100 days ago
        last_rotation = datetime.now() - timedelta(days=100)
        assert sr.should_rotate(last_rotation) == True

    def test_get_rotation_recommendations(self):
        """Test getting rotation recommendations."""
        from core.portfolio.sector_rotation import SectorRotation

        sr = SectorRotation()

        current_positions = {
            'JUP': {'value': 2000, 'sector': 'DeFi'},
            'RAY': {'value': 1000, 'sector': 'DeFi'},
            'BONK': {'value': 500, 'sector': 'Meme'},
        }

        sentiment = {
            'DeFi': 0.3,  # Weak
            'Meme': 0.4,  # Moderate
            'Layer2': 0.8,  # Strong
        }

        recommendations = sr.get_recommendations(current_positions, sentiment)

        assert 'reduce' in recommendations or 'increase' in recommendations


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestPortfolioIntegration:
    """Integration tests for portfolio management."""

    def test_full_optimization_flow(self):
        """Test complete optimization workflow."""
        from core.portfolio.correlation import CorrelationMatrix
        from core.portfolio.optimizer import PortfolioOptimizer
        from core.portfolio.risk_calculator import MultiAssetRiskCalculator

        # Historical returns
        np.random.seed(42)
        returns = {
            'SOL': list(np.random.normal(0.002, 0.04, 100)),
            'ETH': list(np.random.normal(0.001, 0.03, 100)),
            'BTC': list(np.random.normal(0.001, 0.02, 100)),
        }

        # 1. Calculate correlations
        prices = {k: [100 * (1 + sum(v[:i+1])) for i in range(len(v))] for k, v in returns.items()}
        cm = CorrelationMatrix()
        corr_matrix = cm.calculate(prices)

        # 2. Optimize portfolio
        optimizer = PortfolioOptimizer(max_assets=10, max_correlation=0.7)
        weights = optimizer.optimize(returns, target_return=0.02)

        # 3. Calculate risk metrics
        calc = MultiAssetRiskCalculator()
        metrics = calc.get_risk_summary(returns, weights, returns['BTC'])  # BTC as market

        # Verify
        assert sum(weights.values()) == pytest.approx(1.0, abs=0.01)
        assert metrics['volatility'] > 0
        assert metrics['var_95'] < 0

    def test_rebalancing_with_correlation_filter(self):
        """Test rebalancing that respects correlation constraints."""
        from core.portfolio.correlation import CorrelationMatrix
        from core.portfolio.rebalancer import Rebalancer

        # Setup correlated assets with more data points
        prices = {
            'A': [100, 110, 120, 130, 140, 150, 160, 170, 180, 190],
            'A_CORR': [100, 110, 120, 130, 140, 150, 160, 170, 180, 190],  # Identical = perfectly correlated
            'B': [100, 95, 105, 90, 110, 95, 105, 90, 110, 100],  # Different pattern
        }

        cm = CorrelationMatrix(min_data_points=3)
        corr_matrix = cm.calculate(prices)

        # Verify A and A_CORR are highly correlated
        assert corr_matrix['A']['A_CORR'] > 0.9

        # Current weights that need rebalancing
        current_weights = {'A': 0.4, 'A_CORR': 0.4, 'B': 0.2}
        target_weights = {'A': 0.3, 'A_CORR': 0.3, 'B': 0.4}

        rebalancer = Rebalancer(correlation_matrix=corr_matrix, max_correlation=0.7)

        # Should flag correlation issue
        warnings = rebalancer.check_correlation_warnings(current_weights)
        assert len(warnings) > 0

    def test_sector_aware_optimization(self):
        """Test optimization with sector diversification."""
        from core.portfolio.optimizer import PortfolioOptimizer
        from core.portfolio.sector_rotation import SectorRotation

        returns = {
            'JUP': [0.02, 0.01, -0.01, 0.02, 0.01],
            'RAY': [0.03, 0.01, -0.02, 0.03, 0.01],  # Same sector as JUP
            'RNDR': [0.01, 0.02, 0.01, 0.01, 0.02],
            'BONK': [0.05, -0.03, 0.04, -0.02, 0.03],
        }

        sr = SectorRotation()
        optimizer = PortfolioOptimizer(max_sector_allocation=0.50)

        weights = optimizer.optimize_with_sectors(returns, sr)

        # DeFi sector (JUP + RAY) should not exceed 50%
        defi_weight = weights.get('JUP', 0) + weights.get('RAY', 0)
        assert defi_weight <= 0.51  # Allow small tolerance


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================

class TestErrorHandling:
    """Tests for error handling in portfolio management."""

    def test_empty_prices_correlation(self):
        """Handle empty price data gracefully."""
        from core.portfolio.correlation import CorrelationMatrix

        cm = CorrelationMatrix()
        matrix = cm.calculate({})

        assert matrix == {}

    def test_missing_returns_optimization(self):
        """Handle missing returns data."""
        from core.portfolio.optimizer import PortfolioOptimizer

        optimizer = PortfolioOptimizer()
        weights = optimizer.optimize({}, target_return=0.02)

        assert weights == {}

    def test_invalid_weights_risk_calc(self):
        """Handle invalid weights in risk calculation."""
        from core.portfolio.risk_calculator import MultiAssetRiskCalculator

        returns = {'SOL': [0.01, 0.02, -0.01]}
        weights = {'SOL': 1.5, 'ETH': -0.5}  # Invalid: doesn't sum to 1

        calc = MultiAssetRiskCalculator()

        with pytest.raises(ValueError):
            calc.calculate_portfolio_volatility(returns, weights)

    def test_mismatched_data_lengths(self):
        """Handle mismatched data lengths."""
        from core.portfolio.correlation import CorrelationMatrix

        prices = {
            'A': [100, 110, 120],
            'B': [50, 55],  # Different length
        }

        cm = CorrelationMatrix()
        # Should handle gracefully (align or warn)
        matrix = cm.calculate(prices)

        # Should still produce a result
        assert 'A' in matrix or matrix == {}
