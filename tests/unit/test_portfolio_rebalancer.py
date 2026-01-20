"""
Unit tests for Portfolio Rebalancer in core/trading/portfolio_rebalancer.py.

Tests written FIRST following TDD methodology.
These tests define the expected behavior for:
1. Target allocation definitions
2. Drift detection and calculation
3. Rebalancing strategies (threshold, periodic, band)
4. Tax-efficient rebalancing
5. Minimum trade size filters
6. Transaction cost optimization
7. Trade minimization
"""

import pytest
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Any
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# =============================================================================
# TARGET ALLOCATION TESTS
# =============================================================================

class TestTargetAllocation:
    """Tests for target allocation definitions."""

    def test_import_target_allocation(self):
        """Test that TargetAllocation can be imported."""
        from core.trading.portfolio_rebalancer import TargetAllocation
        assert TargetAllocation is not None

    def test_target_allocation_creation(self):
        """Test creating a target allocation."""
        from core.trading.portfolio_rebalancer import TargetAllocation

        alloc = TargetAllocation(
            symbol="SOL",
            target_percent=40.0,
            min_percent=30.0,
            max_percent=50.0,
            drift_threshold=5.0
        )

        assert alloc.symbol == "SOL"
        assert alloc.target_percent == 40.0
        assert alloc.min_percent == 30.0
        assert alloc.max_percent == 50.0
        assert alloc.drift_threshold == 5.0

    def test_target_allocation_defaults(self):
        """Test target allocation default values."""
        from core.trading.portfolio_rebalancer import TargetAllocation

        alloc = TargetAllocation(symbol="ETH", target_percent=30.0)

        assert alloc.min_percent == 0.0
        assert alloc.max_percent == 100.0
        assert alloc.drift_threshold == 5.0

    def test_target_allocation_with_tax_lot(self):
        """Test target allocation with tax lot tracking."""
        from core.trading.portfolio_rebalancer import TargetAllocation

        alloc = TargetAllocation(
            symbol="BTC",
            target_percent=20.0,
            tax_lot_tracking=True,
            short_term_threshold_days=365
        )

        assert alloc.tax_lot_tracking is True
        assert alloc.short_term_threshold_days == 365


# =============================================================================
# PORTFOLIO CONFIGURATION TESTS
# =============================================================================

class TestPortfolioConfig:
    """Tests for portfolio configuration."""

    def test_import_portfolio_config(self):
        """Test that PortfolioConfig can be imported."""
        from core.trading.portfolio_rebalancer import PortfolioConfig
        assert PortfolioConfig is not None

    def test_portfolio_config_creation(self):
        """Test creating a portfolio configuration."""
        from core.trading.portfolio_rebalancer import (
            PortfolioConfig,
            TargetAllocation,
            RebalanceStrategy,
        )

        config = PortfolioConfig(
            name="Main Portfolio",
            target_allocations=[
                TargetAllocation("SOL", 40.0),
                TargetAllocation("ETH", 30.0),
                TargetAllocation("BTC", 20.0),
                TargetAllocation("USDC", 10.0),
            ],
            strategy=RebalanceStrategy.THRESHOLD,
            drift_threshold=5.0,
            min_trade_value=10.0,
        )

        assert config.name == "Main Portfolio"
        assert len(config.target_allocations) == 4
        assert config.strategy == RebalanceStrategy.THRESHOLD
        assert config.drift_threshold == 5.0
        assert config.min_trade_value == 10.0

    def test_portfolio_config_validates_allocations_sum(self):
        """Test that allocations must sum to 100%."""
        from core.trading.portfolio_rebalancer import (
            PortfolioConfig,
            TargetAllocation,
        )

        # This should raise an error - allocations sum to 90%
        with pytest.raises(ValueError, match="must sum to 100"):
            PortfolioConfig(
                name="Invalid",
                target_allocations=[
                    TargetAllocation("SOL", 40.0),
                    TargetAllocation("ETH", 30.0),
                    TargetAllocation("BTC", 20.0),
                    # Missing 10%
                ],
            )

    def test_portfolio_config_with_band_strategy(self):
        """Test portfolio with band rebalancing strategy."""
        from core.trading.portfolio_rebalancer import (
            PortfolioConfig,
            TargetAllocation,
            RebalanceStrategy,
        )

        config = PortfolioConfig(
            name="Band Portfolio",
            target_allocations=[
                TargetAllocation("SOL", 50.0, min_percent=40.0, max_percent=60.0),
                TargetAllocation("USDC", 50.0, min_percent=40.0, max_percent=60.0),
            ],
            strategy=RebalanceStrategy.BAND,
            inner_band_percent=3.0,
            outer_band_percent=5.0,
        )

        assert config.strategy == RebalanceStrategy.BAND
        assert config.inner_band_percent == 3.0
        assert config.outer_band_percent == 5.0


# =============================================================================
# REBALANCING STRATEGY TESTS
# =============================================================================

class TestRebalanceStrategy:
    """Tests for rebalancing strategies enum."""

    def test_import_rebalance_strategy(self):
        """Test that RebalanceStrategy can be imported."""
        from core.trading.portfolio_rebalancer import RebalanceStrategy
        assert RebalanceStrategy is not None

    def test_threshold_strategy_value(self):
        """Test threshold strategy exists."""
        from core.trading.portfolio_rebalancer import RebalanceStrategy
        assert RebalanceStrategy.THRESHOLD.value == "threshold"

    def test_periodic_strategy_value(self):
        """Test periodic strategy exists."""
        from core.trading.portfolio_rebalancer import RebalanceStrategy
        assert RebalanceStrategy.PERIODIC.value == "periodic"

    def test_band_strategy_value(self):
        """Test band strategy exists."""
        from core.trading.portfolio_rebalancer import RebalanceStrategy
        assert RebalanceStrategy.BAND.value == "band"

    def test_hybrid_strategy_value(self):
        """Test hybrid strategy exists."""
        from core.trading.portfolio_rebalancer import RebalanceStrategy
        assert RebalanceStrategy.HYBRID.value == "hybrid"


# =============================================================================
# PORTFOLIO REBALANCER CLASS TESTS
# =============================================================================

class TestPortfolioRebalancer:
    """Tests for PortfolioRebalancer class."""

    def test_import_portfolio_rebalancer(self):
        """Test that PortfolioRebalancer can be imported."""
        from core.trading.portfolio_rebalancer import PortfolioRebalancer
        assert PortfolioRebalancer is not None

    def test_rebalancer_initialization(self):
        """Test rebalancer initialization."""
        from core.trading.portfolio_rebalancer import PortfolioRebalancer

        rebalancer = PortfolioRebalancer()
        assert rebalancer is not None
        assert rebalancer.portfolios == {}

    def test_rebalancer_with_custom_fee_rate(self):
        """Test rebalancer with custom transaction fee rate."""
        from core.trading.portfolio_rebalancer import PortfolioRebalancer

        rebalancer = PortfolioRebalancer(default_fee_rate=0.003)  # 0.3%
        assert rebalancer.default_fee_rate == 0.003


# =============================================================================
# DRIFT DETECTION TESTS
# =============================================================================

class TestDriftDetection:
    """Tests for drift detection functionality."""

    def test_calculate_drift_basic(self):
        """Test basic drift calculation."""
        from core.trading.portfolio_rebalancer import (
            PortfolioRebalancer,
            PortfolioConfig,
            TargetAllocation,
        )

        rebalancer = PortfolioRebalancer()

        config = PortfolioConfig(
            name="Test",
            target_allocations=[
                TargetAllocation("SOL", 50.0),
                TargetAllocation("USDC", 50.0),
            ],
        )

        # Current holdings: SOL is 60%, USDC is 40%
        current_holdings = {
            "SOL": {"value": 6000.0, "quantity": 100.0, "price": 60.0},
            "USDC": {"value": 4000.0, "quantity": 4000.0, "price": 1.0},
        }

        drift = rebalancer.calculate_drift(config, current_holdings)

        assert drift["SOL"]["target_percent"] == 50.0
        assert drift["SOL"]["current_percent"] == 60.0
        assert drift["SOL"]["drift"] == 10.0
        assert drift["USDC"]["drift"] == -10.0

    def test_calculate_max_drift(self):
        """Test max drift calculation across portfolio."""
        from core.trading.portfolio_rebalancer import (
            PortfolioRebalancer,
            PortfolioConfig,
            TargetAllocation,
        )

        rebalancer = PortfolioRebalancer()

        config = PortfolioConfig(
            name="Test",
            target_allocations=[
                TargetAllocation("SOL", 40.0),
                TargetAllocation("ETH", 30.0),
                TargetAllocation("USDC", 30.0),
            ],
        )

        current_holdings = {
            "SOL": {"value": 5000.0, "quantity": 50.0, "price": 100.0},  # 50%
            "ETH": {"value": 2500.0, "quantity": 1.0, "price": 2500.0},  # 25%
            "USDC": {"value": 2500.0, "quantity": 2500.0, "price": 1.0},  # 25%
        }

        drift = rebalancer.calculate_drift(config, current_holdings)

        assert drift["max_drift"] == 10.0  # SOL is 10% over target
        assert drift["total_drift"] == 20.0  # Sum of absolute drifts

    def test_drift_exceeds_threshold(self):
        """Test drift threshold detection."""
        from core.trading.portfolio_rebalancer import (
            PortfolioRebalancer,
            PortfolioConfig,
            TargetAllocation,
        )

        rebalancer = PortfolioRebalancer()

        config = PortfolioConfig(
            name="Test",
            target_allocations=[
                TargetAllocation("SOL", 50.0, drift_threshold=5.0),
                TargetAllocation("USDC", 50.0, drift_threshold=5.0),
            ],
            drift_threshold=5.0,
        )

        # 8% drift exceeds 5% threshold
        current_holdings = {
            "SOL": {"value": 5800.0, "quantity": 58.0, "price": 100.0},
            "USDC": {"value": 4200.0, "quantity": 4200.0, "price": 1.0},
        }

        drift = rebalancer.calculate_drift(config, current_holdings)

        assert drift["needs_rebalance"] is True
        assert drift["SOL"]["exceeds_threshold"] is True

    def test_drift_within_threshold(self):
        """Test drift within threshold doesn't trigger rebalance."""
        from core.trading.portfolio_rebalancer import (
            PortfolioRebalancer,
            PortfolioConfig,
            TargetAllocation,
        )

        rebalancer = PortfolioRebalancer()

        config = PortfolioConfig(
            name="Test",
            target_allocations=[
                TargetAllocation("SOL", 50.0, drift_threshold=5.0),
                TargetAllocation("USDC", 50.0, drift_threshold=5.0),
            ],
            drift_threshold=5.0,
        )

        # 3% drift is within 5% threshold
        current_holdings = {
            "SOL": {"value": 5300.0, "quantity": 53.0, "price": 100.0},
            "USDC": {"value": 4700.0, "quantity": 4700.0, "price": 1.0},
        }

        drift = rebalancer.calculate_drift(config, current_holdings)

        assert drift["needs_rebalance"] is False


# =============================================================================
# TRADE CALCULATION TESTS
# =============================================================================

class TestTradeCalculation:
    """Tests for rebalancing trade calculations."""

    def test_calculate_trades_basic(self):
        """Test basic trade calculation."""
        from core.trading.portfolio_rebalancer import (
            PortfolioRebalancer,
            PortfolioConfig,
            TargetAllocation,
        )

        rebalancer = PortfolioRebalancer()

        config = PortfolioConfig(
            name="Test",
            target_allocations=[
                TargetAllocation("SOL", 50.0),
                TargetAllocation("USDC", 50.0),
            ],
            min_trade_value=1.0,
        )

        # SOL is 60%, USDC is 40% - need to sell SOL, buy USDC
        current_holdings = {
            "SOL": {"value": 6000.0, "quantity": 60.0, "price": 100.0},
            "USDC": {"value": 4000.0, "quantity": 4000.0, "price": 1.0},
        }

        trades = rebalancer.calculate_trades(config, current_holdings)

        # Should have 2 trades: sell SOL, buy USDC
        assert len(trades) >= 1

        sol_trade = next((t for t in trades if t.symbol == "SOL"), None)
        assert sol_trade is not None
        assert sol_trade.side == "sell"
        assert sol_trade.value == pytest.approx(1000.0, rel=0.01)  # Sell $1000 worth

    def test_calculate_trades_respects_min_trade_size(self):
        """Test that small trades below threshold are filtered."""
        from core.trading.portfolio_rebalancer import (
            PortfolioRebalancer,
            PortfolioConfig,
            TargetAllocation,
        )

        rebalancer = PortfolioRebalancer()

        config = PortfolioConfig(
            name="Test",
            target_allocations=[
                TargetAllocation("SOL", 50.0),
                TargetAllocation("USDC", 50.0),
            ],
            min_trade_value=100.0,  # $100 minimum
        )

        # Very small drift - trades would be < $100
        current_holdings = {
            "SOL": {"value": 5050.0, "quantity": 50.5, "price": 100.0},
            "USDC": {"value": 4950.0, "quantity": 4950.0, "price": 1.0},
        }

        trades = rebalancer.calculate_trades(config, current_holdings)

        # Trades should be empty because value < min_trade_value
        assert len(trades) == 0

    def test_calculate_trades_minimizes_trade_count(self):
        """Test that trades are minimized for efficiency."""
        from core.trading.portfolio_rebalancer import (
            PortfolioRebalancer,
            PortfolioConfig,
            TargetAllocation,
        )

        rebalancer = PortfolioRebalancer()

        config = PortfolioConfig(
            name="Test",
            target_allocations=[
                TargetAllocation("SOL", 40.0),
                TargetAllocation("ETH", 30.0),
                TargetAllocation("BTC", 20.0),
                TargetAllocation("USDC", 10.0),
            ],
            min_trade_value=10.0,
        )

        current_holdings = {
            "SOL": {"value": 5000.0, "quantity": 50.0, "price": 100.0},  # 50% (target 40%)
            "ETH": {"value": 2000.0, "quantity": 1.0, "price": 2000.0},  # 20% (target 30%)
            "BTC": {"value": 2000.0, "quantity": 0.05, "price": 40000.0},  # 20% (target 20%)
            "USDC": {"value": 1000.0, "quantity": 1000.0, "price": 1.0},  # 10% (target 10%)
        }

        trades = rebalancer.calculate_trades(config, current_holdings)

        # Only SOL (sell) and ETH (buy) need rebalancing
        # BTC and USDC are on target
        assert len(trades) == 2

    def test_calculate_trades_considers_transaction_costs(self):
        """Test that transaction costs are factored into trade decisions."""
        from core.trading.portfolio_rebalancer import (
            PortfolioRebalancer,
            PortfolioConfig,
            TargetAllocation,
        )

        rebalancer = PortfolioRebalancer(default_fee_rate=0.01)  # 1% fee

        config = PortfolioConfig(
            name="Test",
            target_allocations=[
                TargetAllocation("SOL", 50.0),
                TargetAllocation("USDC", 50.0),
            ],
            min_trade_value=10.0,
            consider_fees=True,
        )

        current_holdings = {
            "SOL": {"value": 5100.0, "quantity": 51.0, "price": 100.0},
            "USDC": {"value": 4900.0, "quantity": 4900.0, "price": 1.0},
        }

        trades = rebalancer.calculate_trades(config, current_holdings)

        # The $100 trade would cost $1 in fees
        # Trade should include fee estimate
        if len(trades) > 0:
            assert hasattr(trades[0], 'estimated_fee')


# =============================================================================
# REBALANCING STRATEGY-SPECIFIC TESTS
# =============================================================================

class TestThresholdStrategy:
    """Tests for threshold-based rebalancing strategy."""

    def test_threshold_strategy_triggers_on_drift(self):
        """Test threshold strategy triggers when drift exceeds threshold."""
        from core.trading.portfolio_rebalancer import (
            PortfolioRebalancer,
            PortfolioConfig,
            TargetAllocation,
            RebalanceStrategy,
        )

        rebalancer = PortfolioRebalancer()

        config = PortfolioConfig(
            name="Test",
            target_allocations=[
                TargetAllocation("SOL", 50.0),
                TargetAllocation("USDC", 50.0),
            ],
            strategy=RebalanceStrategy.THRESHOLD,
            drift_threshold=5.0,
        )

        # 6% drift exceeds 5% threshold
        current_holdings = {
            "SOL": {"value": 5600.0, "quantity": 56.0, "price": 100.0},
            "USDC": {"value": 4400.0, "quantity": 4400.0, "price": 1.0},
        }

        should_rebalance = rebalancer.should_rebalance(config, current_holdings)
        assert should_rebalance is True

    def test_threshold_strategy_no_trigger_below_threshold(self):
        """Test threshold strategy doesn't trigger below threshold."""
        from core.trading.portfolio_rebalancer import (
            PortfolioRebalancer,
            PortfolioConfig,
            TargetAllocation,
            RebalanceStrategy,
        )

        rebalancer = PortfolioRebalancer()

        config = PortfolioConfig(
            name="Test",
            target_allocations=[
                TargetAllocation("SOL", 50.0),
                TargetAllocation("USDC", 50.0),
            ],
            strategy=RebalanceStrategy.THRESHOLD,
            drift_threshold=5.0,
        )

        # 3% drift is below 5% threshold
        current_holdings = {
            "SOL": {"value": 5300.0, "quantity": 53.0, "price": 100.0},
            "USDC": {"value": 4700.0, "quantity": 4700.0, "price": 1.0},
        }

        should_rebalance = rebalancer.should_rebalance(config, current_holdings)
        assert should_rebalance is False


class TestPeriodicStrategy:
    """Tests for periodic rebalancing strategy."""

    def test_periodic_strategy_due_rebalance(self):
        """Test periodic strategy triggers when period has elapsed."""
        from core.trading.portfolio_rebalancer import (
            PortfolioRebalancer,
            PortfolioConfig,
            TargetAllocation,
            RebalanceStrategy,
        )

        rebalancer = PortfolioRebalancer()

        config = PortfolioConfig(
            name="Test",
            target_allocations=[
                TargetAllocation("SOL", 50.0),
                TargetAllocation("USDC", 50.0),
            ],
            strategy=RebalanceStrategy.PERIODIC,
            rebalance_interval_hours=24,
        )

        current_holdings = {
            "SOL": {"value": 5000.0, "quantity": 50.0, "price": 100.0},
            "USDC": {"value": 5000.0, "quantity": 5000.0, "price": 1.0},
        }

        # Last rebalance was 25 hours ago
        last_rebalance = datetime.now(timezone.utc) - timedelta(hours=25)

        should_rebalance = rebalancer.should_rebalance(
            config, current_holdings, last_rebalance=last_rebalance
        )
        assert should_rebalance is True

    def test_periodic_strategy_not_due(self):
        """Test periodic strategy doesn't trigger before period elapsed."""
        from core.trading.portfolio_rebalancer import (
            PortfolioRebalancer,
            PortfolioConfig,
            TargetAllocation,
            RebalanceStrategy,
        )

        rebalancer = PortfolioRebalancer()

        config = PortfolioConfig(
            name="Test",
            target_allocations=[
                TargetAllocation("SOL", 50.0),
                TargetAllocation("USDC", 50.0),
            ],
            strategy=RebalanceStrategy.PERIODIC,
            rebalance_interval_hours=24,
        )

        current_holdings = {
            "SOL": {"value": 5000.0, "quantity": 50.0, "price": 100.0},
            "USDC": {"value": 5000.0, "quantity": 5000.0, "price": 1.0},
        }

        # Last rebalance was 12 hours ago
        last_rebalance = datetime.now(timezone.utc) - timedelta(hours=12)

        should_rebalance = rebalancer.should_rebalance(
            config, current_holdings, last_rebalance=last_rebalance
        )
        assert should_rebalance is False


class TestBandStrategy:
    """Tests for band rebalancing strategy."""

    def test_band_strategy_triggers_on_outer_band(self):
        """Test band strategy triggers when hitting outer band."""
        from core.trading.portfolio_rebalancer import (
            PortfolioRebalancer,
            PortfolioConfig,
            TargetAllocation,
            RebalanceStrategy,
        )

        rebalancer = PortfolioRebalancer()

        config = PortfolioConfig(
            name="Test",
            target_allocations=[
                TargetAllocation("SOL", 50.0, min_percent=40.0, max_percent=60.0),
                TargetAllocation("USDC", 50.0, min_percent=40.0, max_percent=60.0),
            ],
            strategy=RebalanceStrategy.BAND,
            inner_band_percent=3.0,
            outer_band_percent=10.0,
        )

        # SOL at 62% exceeds outer band (50% + 10% = 60%)
        current_holdings = {
            "SOL": {"value": 6200.0, "quantity": 62.0, "price": 100.0},
            "USDC": {"value": 3800.0, "quantity": 3800.0, "price": 1.0},
        }

        should_rebalance = rebalancer.should_rebalance(config, current_holdings)
        assert should_rebalance is True

    def test_band_strategy_partial_rebalance_to_inner_band(self):
        """Test band strategy only rebalances to inner band, not target."""
        from core.trading.portfolio_rebalancer import (
            PortfolioRebalancer,
            PortfolioConfig,
            TargetAllocation,
            RebalanceStrategy,
        )

        rebalancer = PortfolioRebalancer()

        config = PortfolioConfig(
            name="Test",
            target_allocations=[
                TargetAllocation("SOL", 50.0),
                TargetAllocation("USDC", 50.0),
            ],
            strategy=RebalanceStrategy.BAND,
            inner_band_percent=3.0,
            outer_band_percent=10.0,
        )

        # SOL at 65% - should rebalance to 53% (inner band), not 50%
        current_holdings = {
            "SOL": {"value": 6500.0, "quantity": 65.0, "price": 100.0},
            "USDC": {"value": 3500.0, "quantity": 3500.0, "price": 1.0},
        }

        trades = rebalancer.calculate_trades(config, current_holdings)

        # Should sell SOL to bring it to 53% (inner band)
        sol_trade = next((t for t in trades if t.symbol == "SOL"), None)
        assert sol_trade is not None

        # New SOL value should be 53% of total ($10,000)
        expected_sol_value = 5300.0
        new_sol_value = 6500.0 - sol_trade.value
        assert new_sol_value == pytest.approx(expected_sol_value, rel=0.01)


# =============================================================================
# TAX-EFFICIENT REBALANCING TESTS
# =============================================================================

class TestTaxEfficientRebalancing:
    """Tests for tax-efficient rebalancing."""

    def test_tax_lot_selection_fifo(self):
        """Test FIFO tax lot selection."""
        from core.trading.portfolio_rebalancer import (
            PortfolioRebalancer,
            PortfolioConfig,
            TargetAllocation,
            TaxLot,
        )

        rebalancer = PortfolioRebalancer()

        config = PortfolioConfig(
            name="Test",
            target_allocations=[
                TargetAllocation("SOL", 50.0, tax_lot_tracking=True),
                TargetAllocation("USDC", 50.0),
            ],
            tax_lot_method="FIFO",
        )

        tax_lots = [
            TaxLot(symbol="SOL", quantity=10.0, cost_basis=50.0, acquired_date=datetime(2023, 1, 1)),
            TaxLot(symbol="SOL", quantity=10.0, cost_basis=100.0, acquired_date=datetime(2024, 1, 1)),
        ]

        current_holdings = {
            "SOL": {"value": 3000.0, "quantity": 20.0, "price": 150.0, "tax_lots": tax_lots},
            "USDC": {"value": 3000.0, "quantity": 3000.0, "price": 1.0},
        }

        # Need to sell 5 SOL
        trades = rebalancer.calculate_trades(config, current_holdings, tax_optimize=True)

        sol_trade = next((t for t in trades if t.symbol == "SOL"), None)
        if sol_trade:
            # FIFO: should sell from oldest lot first (lower cost basis)
            assert sol_trade.tax_lots_used[0].cost_basis == 50.0

    def test_tax_lot_selection_tax_loss_harvesting(self):
        """Test tax-loss harvesting prefers losing positions."""
        from core.trading.portfolio_rebalancer import (
            PortfolioRebalancer,
            PortfolioConfig,
            TargetAllocation,
            TaxLot,
        )

        rebalancer = PortfolioRebalancer()

        config = PortfolioConfig(
            name="Test",
            target_allocations=[
                TargetAllocation("SOL", 50.0, tax_lot_tracking=True),
                TargetAllocation("USDC", 50.0),
            ],
            tax_loss_harvesting=True,
        )

        # Current price is $80, lot 1 has loss, lot 2 has gain
        tax_lots = [
            TaxLot(symbol="SOL", quantity=10.0, cost_basis=100.0, acquired_date=datetime(2023, 1, 1)),  # Loss
            TaxLot(symbol="SOL", quantity=10.0, cost_basis=50.0, acquired_date=datetime(2024, 1, 1)),  # Gain
        ]

        current_holdings = {
            "SOL": {"value": 1600.0, "quantity": 20.0, "price": 80.0, "tax_lots": tax_lots},
            "USDC": {"value": 2400.0, "quantity": 2400.0, "price": 1.0},
        }

        trades = rebalancer.calculate_trades(config, current_holdings, tax_optimize=True)

        sol_trade = next((t for t in trades if t.symbol == "SOL"), None)
        if sol_trade and sol_trade.side == "sell":
            # Tax loss harvesting: should sell from lot with loss first (cost basis $100)
            assert sol_trade.tax_lots_used[0].cost_basis == 100.0

    def test_avoids_wash_sales(self):
        """Test wash sale avoidance."""
        from core.trading.portfolio_rebalancer import (
            PortfolioRebalancer,
            PortfolioConfig,
            TargetAllocation,
        )

        rebalancer = PortfolioRebalancer()

        config = PortfolioConfig(
            name="Test",
            target_allocations=[
                TargetAllocation("SOL", 50.0),
                TargetAllocation("USDC", 50.0),
            ],
            avoid_wash_sales=True,
            wash_sale_window_days=30,
        )

        current_holdings = {
            "SOL": {"value": 6000.0, "quantity": 60.0, "price": 100.0},
            "USDC": {"value": 4000.0, "quantity": 4000.0, "price": 1.0},
        }

        # Recent sell of SOL within 30 days
        recent_sells = [
            {"symbol": "SOL", "date": datetime.now(timezone.utc) - timedelta(days=15), "loss": True}
        ]

        trades = rebalancer.calculate_trades(
            config, current_holdings, recent_sells=recent_sells
        )

        # Should not suggest buying SOL back if recently sold at a loss
        sol_buy = next((t for t in trades if t.symbol == "SOL" and t.side == "buy"), None)
        assert sol_buy is None or sol_buy.wash_sale_warning is True


# =============================================================================
# TRADE EXECUTION TESTS
# =============================================================================

class TestTradeExecution:
    """Tests for trade execution."""

    @pytest.mark.asyncio
    async def test_execute_rebalance_dry_run(self):
        """Test dry run execution doesn't make real trades."""
        from core.trading.portfolio_rebalancer import (
            PortfolioRebalancer,
            PortfolioConfig,
            TargetAllocation,
        )

        rebalancer = PortfolioRebalancer()

        config = PortfolioConfig(
            name="Test",
            target_allocations=[
                TargetAllocation("SOL", 50.0),
                TargetAllocation("USDC", 50.0),
            ],
        )

        current_holdings = {
            "SOL": {"value": 6000.0, "quantity": 60.0, "price": 100.0},
            "USDC": {"value": 4000.0, "quantity": 4000.0, "price": 1.0},
        }

        result = await rebalancer.execute_rebalance(
            config, current_holdings, dry_run=True
        )

        assert result.dry_run is True
        assert result.trades_executed == 0
        assert len(result.planned_trades) > 0

    @pytest.mark.asyncio
    async def test_execute_rebalance_with_callback(self):
        """Test execution with trade callback."""
        from core.trading.portfolio_rebalancer import (
            PortfolioRebalancer,
            PortfolioConfig,
            TargetAllocation,
        )

        executed_trades = []

        async def mock_execute(trade):
            executed_trades.append(trade)
            return {"success": True, "tx_hash": "abc123"}

        rebalancer = PortfolioRebalancer()
        rebalancer.set_execution_callback(mock_execute)

        config = PortfolioConfig(
            name="Test",
            target_allocations=[
                TargetAllocation("SOL", 50.0),
                TargetAllocation("USDC", 50.0),
            ],
            min_trade_value=1.0,
        )

        current_holdings = {
            "SOL": {"value": 6000.0, "quantity": 60.0, "price": 100.0},
            "USDC": {"value": 4000.0, "quantity": 4000.0, "price": 1.0},
        }

        result = await rebalancer.execute_rebalance(config, current_holdings)

        assert len(executed_trades) > 0
        assert result.trades_executed > 0


# =============================================================================
# REBALANCE RESULT TESTS
# =============================================================================

class TestRebalanceResult:
    """Tests for rebalance result tracking."""

    def test_import_rebalance_result(self):
        """Test that RebalanceResult can be imported."""
        from core.trading.portfolio_rebalancer import RebalanceResult
        assert RebalanceResult is not None

    def test_rebalance_result_fields(self):
        """Test RebalanceResult has required fields."""
        from core.trading.portfolio_rebalancer import RebalanceResult, RebalanceStatus

        result = RebalanceResult(
            id="test123",
            timestamp=datetime.now(timezone.utc).isoformat(),
            portfolio_value_before=10000.0,
            portfolio_value_after=10000.0,
            trades_planned=2,
            trades_executed=2,
            total_traded_value=1000.0,
            fees_paid=5.0,
            drift_before=10.0,
            drift_after=0.5,
            status=RebalanceStatus.COMPLETED,
        )

        assert result.id == "test123"
        assert result.trades_planned == 2
        assert result.trades_executed == 2
        assert result.status == RebalanceStatus.COMPLETED


# =============================================================================
# EDGE CASES AND ERROR HANDLING
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_portfolio(self):
        """Test handling empty portfolio."""
        from core.trading.portfolio_rebalancer import (
            PortfolioRebalancer,
            PortfolioConfig,
            TargetAllocation,
        )

        rebalancer = PortfolioRebalancer()

        config = PortfolioConfig(
            name="Test",
            target_allocations=[
                TargetAllocation("SOL", 50.0),
                TargetAllocation("USDC", 50.0),
            ],
        )

        current_holdings = {}  # Empty portfolio

        drift = rebalancer.calculate_drift(config, current_holdings)

        assert drift["total_value"] == 0.0
        assert drift["needs_rebalance"] is False

    def test_missing_asset_in_holdings(self):
        """Test handling missing asset in holdings."""
        from core.trading.portfolio_rebalancer import (
            PortfolioRebalancer,
            PortfolioConfig,
            TargetAllocation,
        )

        rebalancer = PortfolioRebalancer()

        config = PortfolioConfig(
            name="Test",
            target_allocations=[
                TargetAllocation("SOL", 50.0),
                TargetAllocation("ETH", 30.0),
                TargetAllocation("USDC", 20.0),
            ],
        )

        # ETH is missing from holdings
        current_holdings = {
            "SOL": {"value": 7000.0, "quantity": 70.0, "price": 100.0},
            "USDC": {"value": 3000.0, "quantity": 3000.0, "price": 1.0},
        }

        drift = rebalancer.calculate_drift(config, current_holdings)

        assert drift["ETH"]["current_percent"] == 0.0
        assert drift["ETH"]["drift"] == -30.0  # 0% - 30% target

    def test_zero_price_handling(self):
        """Test handling zero price assets."""
        from core.trading.portfolio_rebalancer import (
            PortfolioRebalancer,
            PortfolioConfig,
            TargetAllocation,
        )

        rebalancer = PortfolioRebalancer()

        config = PortfolioConfig(
            name="Test",
            target_allocations=[
                TargetAllocation("SOL", 50.0),
                TargetAllocation("USDC", 50.0),
            ],
        )

        current_holdings = {
            "SOL": {"value": 0.0, "quantity": 50.0, "price": 0.0},  # Zero price
            "USDC": {"value": 5000.0, "quantity": 5000.0, "price": 1.0},
        }

        # Should not raise an error
        drift = rebalancer.calculate_drift(config, current_holdings)
        assert "SOL" in drift

    def test_very_small_allocations(self):
        """Test handling very small allocation percentages."""
        from core.trading.portfolio_rebalancer import (
            PortfolioRebalancer,
            PortfolioConfig,
            TargetAllocation,
        )

        rebalancer = PortfolioRebalancer()

        config = PortfolioConfig(
            name="Test",
            target_allocations=[
                TargetAllocation("SOL", 99.0),
                TargetAllocation("USDC", 1.0),  # Very small allocation
            ],
            min_trade_value=10.0,
        )

        current_holdings = {
            "SOL": {"value": 9900.0, "quantity": 99.0, "price": 100.0},
            "USDC": {"value": 100.0, "quantity": 100.0, "price": 1.0},
        }

        drift = rebalancer.calculate_drift(config, current_holdings)
        trades = rebalancer.calculate_trades(config, current_holdings)

        # Should handle small allocations correctly
        assert drift["USDC"]["current_percent"] == 1.0


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestIntegration:
    """Integration tests for portfolio rebalancer."""

    @pytest.mark.asyncio
    async def test_full_rebalance_workflow(self):
        """Test complete rebalancing workflow."""
        from core.trading.portfolio_rebalancer import (
            PortfolioRebalancer,
            PortfolioConfig,
            TargetAllocation,
            RebalanceStrategy,
            RebalanceStatus,
        )

        rebalancer = PortfolioRebalancer()

        # Setup portfolio
        config = PortfolioConfig(
            name="Integration Test Portfolio",
            target_allocations=[
                TargetAllocation("SOL", 40.0, drift_threshold=5.0),
                TargetAllocation("ETH", 30.0, drift_threshold=5.0),
                TargetAllocation("BTC", 20.0, drift_threshold=5.0),
                TargetAllocation("USDC", 10.0, drift_threshold=5.0),
            ],
            strategy=RebalanceStrategy.THRESHOLD,
            drift_threshold=5.0,
            min_trade_value=10.0,
        )

        # Current holdings are drifted
        current_holdings = {
            "SOL": {"value": 5000.0, "quantity": 50.0, "price": 100.0},  # 50% (target 40%)
            "ETH": {"value": 2000.0, "quantity": 1.0, "price": 2000.0},  # 20% (target 30%)
            "BTC": {"value": 2000.0, "quantity": 0.05, "price": 40000.0},  # 20% (target 20%)
            "USDC": {"value": 1000.0, "quantity": 1000.0, "price": 1.0},  # 10% (target 10%)
        }

        # Check if rebalance needed
        should_rebalance = rebalancer.should_rebalance(config, current_holdings)
        assert should_rebalance is True

        # Calculate drift
        drift = rebalancer.calculate_drift(config, current_holdings)
        assert drift["max_drift"] == 10.0  # SOL is 10% over

        # Calculate trades
        trades = rebalancer.calculate_trades(config, current_holdings)
        assert len(trades) >= 2  # At least SOL sell and ETH buy

        # Execute rebalance (dry run)
        result = await rebalancer.execute_rebalance(config, current_holdings, dry_run=True)
        assert result.status == RebalanceStatus.COMPLETED
        assert result.dry_run is True

    def test_multiple_strategies_comparison(self):
        """Test comparing different rebalancing strategies."""
        from core.trading.portfolio_rebalancer import (
            PortfolioRebalancer,
            PortfolioConfig,
            TargetAllocation,
            RebalanceStrategy,
        )

        rebalancer = PortfolioRebalancer()

        base_allocations = [
            TargetAllocation("SOL", 50.0),
            TargetAllocation("USDC", 50.0),
        ]

        current_holdings = {
            "SOL": {"value": 5500.0, "quantity": 55.0, "price": 100.0},  # 55%
            "USDC": {"value": 4500.0, "quantity": 4500.0, "price": 1.0},  # 45%
        }

        # Threshold strategy with 5% threshold - should NOT rebalance
        threshold_config = PortfolioConfig(
            name="Threshold",
            target_allocations=base_allocations,
            strategy=RebalanceStrategy.THRESHOLD,
            drift_threshold=5.0,
        )
        assert rebalancer.should_rebalance(threshold_config, current_holdings) is False

        # Threshold strategy with 3% threshold - should rebalance
        tight_threshold_config = PortfolioConfig(
            name="Tight Threshold",
            target_allocations=base_allocations,
            strategy=RebalanceStrategy.THRESHOLD,
            drift_threshold=3.0,
        )
        assert rebalancer.should_rebalance(tight_threshold_config, current_holdings) is True
