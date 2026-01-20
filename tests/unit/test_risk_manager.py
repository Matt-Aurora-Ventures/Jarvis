"""
Tests for Risk Management System
"""

import pytest
import json
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from core.risk import (
    RiskManager,
    RiskLimit,
    RiskViolation,
    RiskAlert,
    RiskMetrics,
    AlertLevel,
    LimitType
)


@pytest.fixture
def temp_risk_dir(tmp_path):
    """Create temporary directory for risk state files."""
    risk_dir = tmp_path / "risk"
    risk_dir.mkdir(parents=True, exist_ok=True)
    return risk_dir


@pytest.fixture
def risk_manager(temp_risk_dir):
    """Create RiskManager instance for testing."""
    return RiskManager(state_dir=temp_risk_dir, enable_alerts=True)


class TestRiskLimits:
    """Test risk limit checking."""

    def test_position_size_within_limit(self, risk_manager):
        """Test position size check passes when within limit."""
        allowed, alert = risk_manager.check_position_size(50.0)  # $50
        assert allowed is True
        assert alert is None  # No alert for normal values

    def test_position_size_warning_threshold(self, risk_manager):
        """Test position size warning at threshold."""
        # Default limit is $100, warning at 80%
        allowed, alert = risk_manager.check_position_size(85.0)
        assert allowed is True
        assert alert is not None
        assert alert.level == AlertLevel.WARNING

    def test_position_size_exceeded(self, risk_manager):
        """Test position size check fails when exceeded."""
        allowed, alert = risk_manager.check_position_size(150.0)  # Exceeds $100
        assert allowed is False
        assert alert is not None
        assert alert.level == AlertLevel.CRITICAL
        assert len(risk_manager.violations) == 1

    def test_daily_loss_within_limit(self, risk_manager):
        """Test daily loss check passes."""
        allowed, alert = risk_manager.check_daily_loss(-50.0)
        assert allowed is True
        assert alert is None

    def test_daily_loss_warning(self, risk_manager):
        """Test daily loss warning at threshold."""
        # Default limit is $200, warning at 75%
        allowed, alert = risk_manager.check_daily_loss(-160.0)
        assert allowed is True
        assert alert is not None
        assert alert.level == AlertLevel.WARNING

    def test_daily_loss_exceeded(self, risk_manager):
        """Test daily loss limit exceeded triggers circuit breaker."""
        allowed, alert = risk_manager.check_daily_loss(-250.0)
        assert allowed is False
        assert alert is not None
        assert alert.level == AlertLevel.EMERGENCY
        assert risk_manager.circuit_breaker_active is True

    def test_concentration_within_limit(self, risk_manager):
        """Test token concentration check passes."""
        allowed, alert = risk_manager.check_concentration(
            token_symbol="SOL",
            token_exposure=100.0,
            total_portfolio=1000.0  # 10% concentration
        )
        assert allowed is True
        assert alert is None

    def test_concentration_exceeded(self, risk_manager):
        """Test token concentration limit exceeded."""
        allowed, alert = risk_manager.check_concentration(
            token_symbol="SHITCOIN",
            token_exposure=400.0,
            total_portfolio=1000.0  # 40% concentration (exceeds 30% limit)
        )
        assert allowed is False
        assert alert is not None
        assert alert.level == AlertLevel.CRITICAL
        assert "SHITCOIN" in alert.message

    def test_portfolio_allocation_exceeded(self, risk_manager):
        """Test portfolio allocation limit."""
        allowed, alert = risk_manager.check_portfolio_allocation(
            deployed_capital=600.0,
            total_portfolio=1000.0  # 60% deployed (exceeds 50% limit)
        )
        assert allowed is False
        assert alert is not None

    def test_trade_frequency_exceeded(self, risk_manager):
        """Test trade frequency limit."""
        allowed, alert = risk_manager.check_trade_frequency(25)  # Exceeds 20 limit
        assert allowed is False
        assert alert is not None
        assert alert.level == AlertLevel.CRITICAL


class TestRiskManager:
    """Test RiskManager functionality."""

    def test_initialization(self, risk_manager):
        """Test RiskManager initializes with default limits."""
        assert len(risk_manager.limits) >= 6
        assert LimitType.POSITION_SIZE in risk_manager.limits
        assert LimitType.DAILY_LOSS in risk_manager.limits
        assert LimitType.CONCENTRATION in risk_manager.limits

    def test_update_limit(self, risk_manager):
        """Test updating a limit."""
        risk_manager.update_limit(
            LimitType.POSITION_SIZE,
            hard_limit=200.0,
            warning_threshold=0.9
        )
        limit = risk_manager.limits[LimitType.POSITION_SIZE]
        assert limit.hard_limit == 200.0
        assert limit.warning_threshold == 0.9

    def test_disable_limit(self, risk_manager):
        """Test disabling a limit."""
        risk_manager.update_limit(LimitType.POSITION_SIZE, enabled=False)

        # Should pass even with excessive amount
        allowed, alert = risk_manager.check_position_size(1000.0)
        assert allowed is True
        assert alert is None

    def test_check_all_limits(self, risk_manager):
        """Test checking multiple limits at once."""
        all_passed, alerts = risk_manager.check_all_limits(
            position_size=50.0,
            daily_loss=-50.0,
            token_concentration={'SOL': (100.0, 1000.0)},
            deployed_capital=300.0,
            total_portfolio=1000.0,
            trades_today=5
        )

        assert all_passed is True
        # Should have no critical alerts
        critical_alerts = [a for a in alerts if a.level == AlertLevel.CRITICAL]
        assert len(critical_alerts) == 0

    def test_check_all_limits_with_violations(self, risk_manager):
        """Test checking limits with violations."""
        all_passed, alerts = risk_manager.check_all_limits(
            position_size=150.0,  # Exceeds limit
            daily_loss=-250.0,    # Exceeds limit
            trades_today=25       # Exceeds limit
        )

        assert all_passed is False
        assert len(alerts) >= 3  # At least 3 violations

    def test_violation_persistence(self, risk_manager, temp_risk_dir):
        """Test violations are persisted to disk."""
        # Trigger a violation
        risk_manager.check_position_size(150.0)

        # Create new manager instance
        new_manager = RiskManager(state_dir=temp_risk_dir)

        # Should load previous violations
        assert len(new_manager.violations) == 1

    def test_circuit_breaker_activation(self, risk_manager):
        """Test circuit breaker activates on daily loss."""
        assert risk_manager.circuit_breaker_active is False

        # Trigger circuit breaker
        risk_manager.check_daily_loss(-300.0)

        assert risk_manager.circuit_breaker_active is True
        assert risk_manager.circuit_breaker_triggered_at is not None

    def test_circuit_breaker_reset(self, risk_manager):
        """Test manual circuit breaker reset."""
        risk_manager.check_daily_loss(-300.0)
        assert risk_manager.circuit_breaker_active is True

        risk_manager.reset_circuit_breaker()
        assert risk_manager.circuit_breaker_active is False

    def test_get_recent_violations(self, risk_manager):
        """Test retrieving recent violations."""
        # Trigger violations
        risk_manager.check_position_size(150.0)
        risk_manager.check_trade_frequency(25)

        violations = risk_manager.get_recent_violations(hours=24)
        assert len(violations) == 2

    def test_get_limit_config(self, risk_manager):
        """Test getting limit configuration."""
        config = risk_manager.get_limit_config()

        assert 'POSITION_SIZE' in config
        assert config['POSITION_SIZE']['hard_limit'] == 100.0
        assert 'enabled' in config['POSITION_SIZE']


class TestRiskMetrics:
    """Test risk metrics calculation."""

    def test_calculate_risk_metrics(self, risk_manager):
        """Test risk metrics calculation."""
        # Mock positions
        class MockPosition:
            def __init__(self, symbol, amount_usd, opened_at):
                self.token_symbol = symbol
                self.amount_usd = amount_usd
                self.opened_at = opened_at

        now = datetime.utcnow().isoformat()
        positions = [
            MockPosition("SOL", 50.0, now),
            MockPosition("BTC", 75.0, now),
            MockPosition("SOL", 25.0, now),  # Duplicate token
        ]

        metrics = risk_manager.get_risk_metrics(
            positions=positions,
            daily_pnl=-20.0,
            portfolio_peak=1000.0,
            current_portfolio=950.0
        )

        assert metrics.total_positions == 3
        assert metrics.total_exposure_usd == 150.0
        assert metrics.daily_pnl == -20.0
        assert metrics.daily_loss == 20.0
        assert metrics.max_position_size == 75.0
        assert metrics.max_concentration > 0  # SOL has 75.0 total
        assert metrics.drawdown_from_peak == 5.0  # 5% drawdown

    def test_metrics_limit_utilization(self, risk_manager):
        """Test limit utilization calculation in metrics."""
        class MockPosition:
            def __init__(self, symbol, amount_usd, opened_at):
                self.token_symbol = symbol
                self.amount_usd = amount_usd
                self.opened_at = opened_at

        now = datetime.utcnow().isoformat()
        positions = [MockPosition("SOL", 80.0, now)]  # 80% of $100 limit

        metrics = risk_manager.get_risk_metrics(
            positions=positions,
            daily_pnl=-150.0,  # 75% of $200 limit
            portfolio_peak=1000.0,
            current_portfolio=1000.0
        )

        assert metrics.position_limit_usage == 80.0
        assert metrics.daily_loss_limit_usage == 75.0


class TestRiskAlert:
    """Test risk alert functionality."""

    def test_alert_creation(self):
        """Test creating a risk alert."""
        alert = RiskAlert(
            timestamp=datetime.utcnow().isoformat(),
            level=AlertLevel.WARNING,
            limit_type=LimitType.POSITION_SIZE,
            message="Position size approaching limit",
            current_value=85.0,
            limit_value=100.0,
            action_required="Monitor position"
        )

        assert alert.level == AlertLevel.WARNING
        assert alert.current_value == 85.0

    def test_alert_telegram_message(self):
        """Test formatting alert for Telegram."""
        alert = RiskAlert(
            timestamp=datetime.utcnow().isoformat(),
            level=AlertLevel.CRITICAL,
            limit_type=LimitType.DAILY_LOSS,
            message="Daily loss limit exceeded",
            current_value=250.0,
            limit_value=200.0,
            action_required="Stop trading immediately"
        )

        msg = alert.to_telegram_message()

        assert "CRITICAL" in msg
        assert "DAILY_LOSS" in msg
        assert "250.00" in msg
        assert "200.00" in msg
        assert "Stop trading immediately" in msg


class TestLimitPersistence:
    """Test limit configuration persistence."""

    def test_save_and_load_limits(self, temp_risk_dir):
        """Test limits are saved and loaded correctly."""
        manager1 = RiskManager(state_dir=temp_risk_dir)

        # Update a limit
        manager1.update_limit(LimitType.POSITION_SIZE, hard_limit=250.0)

        # Create new manager instance
        manager2 = RiskManager(state_dir=temp_risk_dir)

        # Should have loaded updated limit
        limit = manager2.limits[LimitType.POSITION_SIZE]
        assert limit.hard_limit == 250.0

    def test_custom_limit_creation(self, temp_risk_dir):
        """Test creating custom limits."""
        manager = RiskManager(state_dir=temp_risk_dir)

        # Add custom limit manually
        manager.limits[LimitType.CORRELATION] = RiskLimit(
            limit_type=LimitType.CORRELATION,
            hard_limit=0.7,
            warning_threshold=0.8,
            description="Max correlation between positions"
        )

        manager._save_limits()

        # Reload
        manager2 = RiskManager(state_dir=temp_risk_dir)
        assert LimitType.CORRELATION in manager2.limits


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_zero_portfolio_concentration(self, risk_manager):
        """Test concentration check with zero portfolio."""
        allowed, alert = risk_manager.check_concentration(
            token_symbol="SOL",
            token_exposure=100.0,
            total_portfolio=0.0
        )
        # Should allow when portfolio is zero (avoids division by zero)
        assert allowed is True

    def test_negative_values(self, risk_manager):
        """Test handling of negative values."""
        # Daily loss should handle negative input correctly
        allowed, _ = risk_manager.check_daily_loss(-100.0)
        assert allowed is True  # abs(-100) < 200 limit

    def test_empty_positions(self, risk_manager):
        """Test metrics calculation with no positions."""
        metrics = risk_manager.get_risk_metrics(
            positions=[],
            daily_pnl=0.0,
            portfolio_peak=1000.0,
            current_portfolio=1000.0
        )

        assert metrics.total_positions == 0
        assert metrics.total_exposure_usd == 0.0
        assert metrics.max_position_size == 0.0
