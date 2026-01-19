"""
Comprehensive tests for Health Monitoring, Alerting, and Dashboard systems.

Tests cover:
- SystemHealthChecker component checks
- Alerter notification system
- Alert rules engine
- Performance tracking
- Budget tracking
- Dashboard data provider
- Alert deduplication
"""

import asyncio
import json
import os
import pytest
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_telegram_notifier():
    """Mock Telegram notification."""
    with patch("aiohttp.ClientSession") as mock:
        session = AsyncMock()
        mock.return_value.__aenter__.return_value = session
        session.post.return_value.__aenter__.return_value.status = 200
        yield session


@pytest.fixture
def sample_alert_rules():
    """Sample alert rules configuration."""
    return {
        "rules": [
            {
                "id": "cpu_high",
                "condition": "cpu_percent > 80",
                "severity": "warning",
                "actions": ["telegram", "log"],
                "cooldown_minutes": 30,
                "message": "CPU usage exceeds 80%"
            },
            {
                "id": "memory_critical",
                "condition": "memory_percent > 90",
                "severity": "critical",
                "actions": ["telegram", "email", "log"],
                "cooldown_minutes": 10,
                "message": "Memory usage exceeds 90%"
            },
            {
                "id": "api_latency_high",
                "condition": "api_latency_p95 > 1000",
                "severity": "warning",
                "actions": ["log"],
                "cooldown_minutes": 15,
                "message": "API latency P95 exceeds 1 second"
            }
        ]
    }


# =============================================================================
# SYSTEM HEALTH CHECKER TESTS
# =============================================================================

class TestSystemHealthChecker:
    """Tests for SystemHealthChecker class."""

    @pytest.mark.asyncio
    async def test_health_checker_initialization(self, temp_data_dir):
        """Test that health checker initializes correctly."""
        from core.monitoring.health_check import SystemHealthChecker

        checker = SystemHealthChecker(data_dir=str(temp_data_dir))
        assert checker is not None
        assert checker.check_interval == 60  # Default 60 seconds

    @pytest.mark.asyncio
    async def test_health_status_levels(self):
        """Test health status levels are defined correctly."""
        from core.monitoring.health_check import HealthLevel

        assert HealthLevel.HEALTHY.value == "healthy"
        assert HealthLevel.DEGRADED.value == "degraded"
        assert HealthLevel.CRITICAL.value == "critical"

    @pytest.mark.asyncio
    async def test_check_twitter_bot_health(self, temp_data_dir):
        """Test Twitter bot health check."""
        from core.monitoring.health_check import SystemHealthChecker

        checker = SystemHealthChecker(data_dir=str(temp_data_dir))

        with patch("core.monitoring.health_check.check_twitter_connectivity") as mock_check:
            mock_check.return_value = {"connected": True, "last_post": datetime.now(timezone.utc).isoformat()}

            result = await checker.check_component("twitter_bot")

            assert result.name == "twitter_bot"
            assert result.status in ["healthy", "degraded", "critical"]

    @pytest.mark.asyncio
    async def test_check_telegram_bot_health(self, temp_data_dir):
        """Test Telegram bot health check."""
        from core.monitoring.health_check import SystemHealthChecker

        checker = SystemHealthChecker(data_dir=str(temp_data_dir))

        with patch("core.monitoring.health_check.check_telegram_connectivity") as mock_check:
            mock_check.return_value = {"polling": True, "last_update": datetime.now(timezone.utc).isoformat()}

            result = await checker.check_component("telegram_bot")

            assert result.name == "telegram_bot"
            assert result.status in ["healthy", "degraded", "critical"]

    @pytest.mark.asyncio
    async def test_check_trading_engine_health(self, temp_data_dir):
        """Test trading engine health check."""
        from core.monitoring.health_check import SystemHealthChecker

        checker = SystemHealthChecker(data_dir=str(temp_data_dir))

        with patch("core.monitoring.health_check.check_trading_engine") as mock_check:
            mock_check.return_value = {"operational": True, "last_trade": None, "error_rate": 0.0}

            result = await checker.check_component("trading_engine")

            assert result.name == "trading_engine"
            assert result.status in ["healthy", "degraded", "critical"]

    @pytest.mark.asyncio
    async def test_check_database_health(self, temp_data_dir):
        """Test database health check."""
        from core.monitoring.health_check import SystemHealthChecker

        checker = SystemHealthChecker(data_dir=str(temp_data_dir))

        result = await checker.check_component("database")

        assert result.name == "database"
        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_check_api_services_health(self, temp_data_dir):
        """Test external API services health check."""
        from core.monitoring.health_check import SystemHealthChecker

        checker = SystemHealthChecker(data_dir=str(temp_data_dir))

        with patch("aiohttp.ClientSession") as mock_session:
            session = AsyncMock()
            mock_session.return_value.__aenter__.return_value = session
            session.get.return_value.__aenter__.return_value.status = 200

            result = await checker.check_component("api_services")

            assert result.name == "api_services"

    @pytest.mark.asyncio
    async def test_full_health_check(self, temp_data_dir):
        """Test full system health check returns all components."""
        from core.monitoring.health_check import SystemHealthChecker

        checker = SystemHealthChecker(data_dir=str(temp_data_dir))

        with patch.object(checker, "check_component") as mock_check:
            mock_check.return_value = MagicMock(
                name="test",
                status="healthy",
                latency_ms=10.0,
                message="OK"
            )

            result = await checker.check_all()

            assert "status" in result
            assert "components" in result
            assert "checked_at" in result

    @pytest.mark.asyncio
    async def test_health_endpoint_json_format(self, temp_data_dir):
        """Test health check returns proper JSON format."""
        from core.monitoring.health_check import SystemHealthChecker

        checker = SystemHealthChecker(data_dir=str(temp_data_dir))

        with patch.object(checker, "check_all") as mock_check:
            mock_check.return_value = {
                "status": "healthy",
                "components": {},
                "checked_at": datetime.now(timezone.utc).isoformat()
            }

            result = await checker.get_health_json()

            # Should be valid JSON
            parsed = json.loads(result)
            assert "status" in parsed


# =============================================================================
# ALERTER TESTS
# =============================================================================

class TestAlerter:
    """Tests for the Alerter notification system."""

    @pytest.mark.asyncio
    async def test_alerter_initialization(self, temp_data_dir):
        """Test alerter initializes with channels."""
        from core.monitoring.alerter import Alerter

        alerter = Alerter(data_dir=str(temp_data_dir))
        assert alerter is not None
        assert "telegram" in alerter.channels
        assert "log" in alerter.channels

    @pytest.mark.asyncio
    async def test_alert_types_defined(self):
        """Test alert types are properly defined."""
        from core.monitoring.alerter import AlertType

        assert AlertType.CRITICAL.value == "critical"
        assert AlertType.WARNING.value == "warning"
        assert AlertType.INFO.value == "info"

    @pytest.mark.asyncio
    async def test_send_telegram_alert(self, temp_data_dir, mock_telegram_notifier):
        """Test sending alert to Telegram."""
        from core.monitoring.alerter import Alerter, AlertType

        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test_token", "TELEGRAM_ADMIN_IDS": "123456"}):
            alerter = Alerter(data_dir=str(temp_data_dir))

            result = await alerter.send_alert(
                alert_type=AlertType.WARNING,
                message="Test alert message",
                channels=["telegram"]
            )

            assert result.sent is True

    @pytest.mark.asyncio
    async def test_send_log_alert(self, temp_data_dir):
        """Test sending alert to logs."""
        from core.monitoring.alerter import Alerter, AlertType

        alerter = Alerter(data_dir=str(temp_data_dir))

        with patch("logging.Logger.warning") as mock_log:
            result = await alerter.send_alert(
                alert_type=AlertType.WARNING,
                message="Test log alert",
                channels=["log"]
            )

            assert result.sent is True

    @pytest.mark.asyncio
    async def test_alert_deduplication(self, temp_data_dir):
        """Test that same alert is not sent twice within cooldown period."""
        from core.monitoring.alerter import Alerter, AlertType

        alerter = Alerter(data_dir=str(temp_data_dir), dedup_window_hours=1)

        # First alert should send
        result1 = await alerter.send_alert(
            alert_type=AlertType.WARNING,
            message="Test dedup",
            channels=["log"],
            alert_id="test_dedup_001"
        )
        assert result1.sent is True

        # Same alert within 1 hour should be deduplicated
        result2 = await alerter.send_alert(
            alert_type=AlertType.WARNING,
            message="Test dedup",
            channels=["log"],
            alert_id="test_dedup_001"
        )
        assert result2.sent is False
        assert result2.reason == "deduplicated"

    @pytest.mark.asyncio
    async def test_alert_history_stored(self, temp_data_dir):
        """Test that alerts are stored in history."""
        from core.monitoring.alerter import Alerter, AlertType

        alerter = Alerter(data_dir=str(temp_data_dir))

        await alerter.send_alert(
            alert_type=AlertType.INFO,
            message="Test history",
            channels=["log"]
        )

        history = alerter.get_alert_history(limit=10)
        assert len(history) >= 1
        assert history[0]["message"] == "Test history"


# =============================================================================
# ALERT RULES ENGINE TESTS
# =============================================================================

class TestAlertRulesEngine:
    """Tests for the alert rules engine."""

    @pytest.mark.asyncio
    async def test_rules_engine_initialization(self, temp_data_dir, sample_alert_rules):
        """Test rules engine loads from config."""
        from core.monitoring.alert_rules import AlertRulesEngine

        rules_path = temp_data_dir / "alert_rules.json"
        with open(rules_path, "w") as f:
            json.dump(sample_alert_rules, f)

        engine = AlertRulesEngine(rules_path=str(rules_path))

        assert len(engine.rules) == 3

    @pytest.mark.asyncio
    async def test_cpu_rule_evaluation(self, temp_data_dir, sample_alert_rules):
        """Test CPU usage rule triggers correctly."""
        from core.monitoring.alert_rules import AlertRulesEngine

        rules_path = temp_data_dir / "alert_rules.json"
        with open(rules_path, "w") as f:
            json.dump(sample_alert_rules, f)

        engine = AlertRulesEngine(rules_path=str(rules_path))

        # Simulate high CPU
        metrics = {"cpu_percent": 85}
        triggered = engine.evaluate(metrics)

        assert any(r["id"] == "cpu_high" for r in triggered)

    @pytest.mark.asyncio
    async def test_memory_critical_rule(self, temp_data_dir, sample_alert_rules):
        """Test memory critical rule triggers."""
        from core.monitoring.alert_rules import AlertRulesEngine

        rules_path = temp_data_dir / "alert_rules.json"
        with open(rules_path, "w") as f:
            json.dump(sample_alert_rules, f)

        engine = AlertRulesEngine(rules_path=str(rules_path))

        # Simulate critical memory
        metrics = {"memory_percent": 95}
        triggered = engine.evaluate(metrics)

        assert any(r["id"] == "memory_critical" for r in triggered)

    @pytest.mark.asyncio
    async def test_rule_cooldown(self, temp_data_dir, sample_alert_rules):
        """Test that rules respect cooldown period."""
        from core.monitoring.alert_rules import AlertRulesEngine

        rules_path = temp_data_dir / "alert_rules.json"
        with open(rules_path, "w") as f:
            json.dump(sample_alert_rules, f)

        engine = AlertRulesEngine(rules_path=str(rules_path))

        metrics = {"cpu_percent": 85}

        # First evaluation should trigger
        triggered1 = engine.evaluate(metrics)
        assert len(triggered1) > 0

        # Immediate second evaluation should be in cooldown
        triggered2 = engine.evaluate(metrics)
        assert len(triggered2) == 0  # Cooldown active

    @pytest.mark.asyncio
    async def test_add_custom_rule(self, temp_data_dir):
        """Test adding custom rules at runtime."""
        from core.monitoring.alert_rules import AlertRulesEngine

        engine = AlertRulesEngine()

        engine.add_rule({
            "id": "custom_rule",
            "condition": "custom_metric > 100",
            "severity": "warning",
            "actions": ["log"],
            "cooldown_minutes": 5,
            "message": "Custom metric exceeded"
        })

        assert "custom_rule" in [r["id"] for r in engine.rules]


# =============================================================================
# PERFORMANCE TRACKER TESTS
# =============================================================================

class TestPerformanceTracker:
    """Tests for performance tracking."""

    @pytest.mark.asyncio
    async def test_tracker_initialization(self, temp_data_dir):
        """Test performance tracker initializes correctly."""
        from core.monitoring.performance_tracker import PerformanceTracker

        tracker = PerformanceTracker(data_dir=str(temp_data_dir))
        assert tracker is not None
        assert tracker.uptime_target == 99.5
        assert tracker.api_availability_target == 99.9

    @pytest.mark.asyncio
    async def test_track_uptime(self, temp_data_dir):
        """Test uptime tracking."""
        from core.monitoring.performance_tracker import PerformanceTracker

        tracker = PerformanceTracker(data_dir=str(temp_data_dir))

        # Record uptime samples
        tracker.record_uptime_sample(is_up=True)
        tracker.record_uptime_sample(is_up=True)
        tracker.record_uptime_sample(is_up=False)

        stats = tracker.get_uptime_stats()

        assert stats["uptime_percent"] == pytest.approx(66.67, rel=0.01)

    @pytest.mark.asyncio
    async def test_track_api_availability(self, temp_data_dir):
        """Test API availability tracking."""
        from core.monitoring.performance_tracker import PerformanceTracker

        tracker = PerformanceTracker(data_dir=str(temp_data_dir))

        # Record API samples
        tracker.record_api_sample(service="grok", is_available=True, latency_ms=50)
        tracker.record_api_sample(service="grok", is_available=True, latency_ms=100)
        tracker.record_api_sample(service="jupiter", is_available=False, latency_ms=0)

        stats = tracker.get_api_availability()

        assert "grok" in stats
        assert stats["grok"]["availability_percent"] == 100.0

    @pytest.mark.asyncio
    async def test_track_trade_latency(self, temp_data_dir):
        """Test trade latency tracking."""
        from core.monitoring.performance_tracker import PerformanceTracker

        tracker = PerformanceTracker(data_dir=str(temp_data_dir))

        tracker.record_trade_latency(latency_ms=150)
        tracker.record_trade_latency(latency_ms=200)
        tracker.record_trade_latency(latency_ms=100)

        stats = tracker.get_trade_latency_stats()

        assert stats["average_ms"] == 150.0
        assert stats["min_ms"] == 100
        assert stats["max_ms"] == 200

    @pytest.mark.asyncio
    async def test_alert_on_target_breach(self, temp_data_dir):
        """Test alert triggered when target breached."""
        from core.monitoring.performance_tracker import PerformanceTracker

        tracker = PerformanceTracker(
            data_dir=str(temp_data_dir),
            uptime_target=99.5
        )

        # Record mostly down samples
        for _ in range(100):
            tracker.record_uptime_sample(is_up=False)

        alerts = tracker.check_targets()

        assert len(alerts) > 0
        assert any("uptime" in a["message"].lower() for a in alerts)


# =============================================================================
# BUDGET TRACKER TESTS
# =============================================================================

class TestBudgetTracker:
    """Tests for API cost/budget tracking."""

    @pytest.mark.asyncio
    async def test_budget_tracker_initialization(self, temp_data_dir):
        """Test budget tracker initializes."""
        from core.monitoring.budget_tracker import BudgetTracker

        tracker = BudgetTracker(data_dir=str(temp_data_dir))
        assert tracker is not None

    @pytest.mark.asyncio
    async def test_track_grok_spend(self, temp_data_dir):
        """Test tracking Grok API spend."""
        from core.monitoring.budget_tracker import BudgetTracker

        tracker = BudgetTracker(data_dir=str(temp_data_dir))

        tracker.record_api_cost("grok", cost_usd=0.05)
        tracker.record_api_cost("grok", cost_usd=0.10)

        spend = tracker.get_daily_spend("grok")

        assert spend == pytest.approx(0.15, rel=0.01)

    @pytest.mark.asyncio
    async def test_track_helius_usage(self, temp_data_dir):
        """Test tracking Helius RPC usage."""
        from core.monitoring.budget_tracker import BudgetTracker

        tracker = BudgetTracker(data_dir=str(temp_data_dir))

        tracker.record_api_cost("helius", cost_usd=0.001, calls=10)

        usage = tracker.get_service_usage("helius")

        assert usage["calls"] == 10
        assert usage["cost_usd"] == pytest.approx(0.001)

    @pytest.mark.asyncio
    async def test_monthly_projection(self, temp_data_dir):
        """Test monthly cost projection."""
        from core.monitoring.budget_tracker import BudgetTracker

        tracker = BudgetTracker(data_dir=str(temp_data_dir))

        # Record daily spend
        tracker.record_api_cost("grok", cost_usd=5.00)

        projection = tracker.get_monthly_projection("grok")

        # Should project ~$150/month ($5 * 30 days)
        assert projection >= 100  # At least $100 projected

    @pytest.mark.asyncio
    async def test_budget_alert_50_percent(self, temp_data_dir):
        """Test alert when daily spend > 50% of monthly budget."""
        from core.monitoring.budget_tracker import BudgetTracker

        tracker = BudgetTracker(
            data_dir=str(temp_data_dir),
            monthly_budgets={"grok": 10.0}  # $10/month budget
        )

        # Spend 60% of budget in one day
        tracker.record_api_cost("grok", cost_usd=6.00)

        alerts = tracker.check_budgets()

        assert len(alerts) > 0
        assert any("warning" in a["severity"].lower() for a in alerts)

    @pytest.mark.asyncio
    async def test_budget_alert_100_percent(self, temp_data_dir):
        """Test critical alert when daily spend > 100% of monthly budget."""
        from core.monitoring.budget_tracker import BudgetTracker

        tracker = BudgetTracker(
            data_dir=str(temp_data_dir),
            monthly_budgets={"grok": 10.0}
        )

        # Overspend in one day
        tracker.record_api_cost("grok", cost_usd=15.00)

        alerts = tracker.check_budgets()

        assert len(alerts) > 0
        assert any("critical" in a["severity"].lower() for a in alerts)

    @pytest.mark.asyncio
    async def test_total_spend_across_services(self, temp_data_dir):
        """Test total spend calculation across all services."""
        from core.monitoring.budget_tracker import BudgetTracker

        tracker = BudgetTracker(data_dir=str(temp_data_dir))

        tracker.record_api_cost("grok", cost_usd=1.00)
        tracker.record_api_cost("helius", cost_usd=0.50)
        tracker.record_api_cost("anthropic", cost_usd=2.00)

        total = tracker.get_total_daily_spend()

        assert total == pytest.approx(3.50)


# =============================================================================
# DASHBOARD DATA PROVIDER TESTS
# =============================================================================

class TestDashboardDataProvider:
    """Tests for the dashboard data provider."""

    @pytest.mark.asyncio
    async def test_dashboard_provider_initialization(self, temp_data_dir):
        """Test dashboard provider initializes."""
        from core.monitoring.dashboard_data import DashboardDataProvider

        provider = DashboardDataProvider(data_dir=str(temp_data_dir))
        assert provider is not None

    @pytest.mark.asyncio
    async def test_get_health_status(self, temp_data_dir):
        """Test getting current health status."""
        from core.monitoring.dashboard_data import DashboardDataProvider

        provider = DashboardDataProvider(data_dir=str(temp_data_dir))

        with patch.object(provider, "_get_health_checker") as mock_health:
            mock_health.return_value.check_all = AsyncMock(return_value={
                "status": "healthy",
                "components": {"db": {"status": "healthy"}}
            })

            data = await provider.get_dashboard_data()

            assert "health" in data
            assert data["health"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_get_performance_metrics(self, temp_data_dir):
        """Test getting performance metrics."""
        from core.monitoring.dashboard_data import DashboardDataProvider

        provider = DashboardDataProvider(data_dir=str(temp_data_dir))

        data = await provider.get_dashboard_data()

        assert "performance" in data

    @pytest.mark.asyncio
    async def test_get_budget_usage(self, temp_data_dir):
        """Test getting budget usage data."""
        from core.monitoring.dashboard_data import DashboardDataProvider

        provider = DashboardDataProvider(data_dir=str(temp_data_dir))

        data = await provider.get_dashboard_data()

        assert "budget" in data

    @pytest.mark.asyncio
    async def test_get_trading_stats(self, temp_data_dir):
        """Test getting trading statistics."""
        from core.monitoring.dashboard_data import DashboardDataProvider

        provider = DashboardDataProvider(data_dir=str(temp_data_dir))

        data = await provider.get_dashboard_data()

        assert "trading" in data

    @pytest.mark.asyncio
    async def test_get_recent_alerts(self, temp_data_dir):
        """Test getting recent alerts."""
        from core.monitoring.dashboard_data import DashboardDataProvider

        provider = DashboardDataProvider(data_dir=str(temp_data_dir))

        data = await provider.get_dashboard_data()

        assert "alerts" in data
        assert isinstance(data["alerts"], list)

    @pytest.mark.asyncio
    async def test_dashboard_json_format(self, temp_data_dir):
        """Test dashboard returns valid JSON."""
        from core.monitoring.dashboard_data import DashboardDataProvider

        provider = DashboardDataProvider(data_dir=str(temp_data_dir))

        json_str = await provider.get_dashboard_json()

        # Should be valid JSON
        parsed = json.loads(json_str)
        assert "health" in parsed
        assert "timestamp" in parsed


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestHealthMonitoringIntegration:
    """Integration tests for the full monitoring system."""

    @pytest.mark.asyncio
    async def test_full_monitoring_cycle(self, temp_data_dir):
        """Test a full monitoring check -> alert cycle."""
        from core.monitoring.health_check import SystemHealthChecker
        from core.monitoring.alerter import Alerter, AlertType
        from core.monitoring.alert_rules import AlertRulesEngine

        # Setup
        checker = SystemHealthChecker(data_dir=str(temp_data_dir))
        alerter = Alerter(data_dir=str(temp_data_dir))

        rules = AlertRulesEngine()
        rules.add_rule({
            "id": "test_rule",
            "condition": "test_metric > 0",
            "severity": "info",
            "actions": ["log"],
            "cooldown_minutes": 0,
            "message": "Test triggered"
        })

        # Simulate metrics
        metrics = {"test_metric": 1}
        triggered = rules.evaluate(metrics)

        # Send alerts for triggered rules
        for rule in triggered:
            await alerter.send_alert(
                alert_type=AlertType.INFO,
                message=rule["message"],
                channels=rule["actions"]
            )

        history = alerter.get_alert_history(limit=10)
        assert len(history) >= 1

    @pytest.mark.asyncio
    async def test_metrics_flow_to_dashboard(self, temp_data_dir):
        """Test metrics flow from collection to dashboard."""
        from core.monitoring.performance_tracker import PerformanceTracker
        from core.monitoring.dashboard_data import DashboardDataProvider

        # Record some metrics
        tracker = PerformanceTracker(data_dir=str(temp_data_dir))
        tracker.record_uptime_sample(is_up=True)
        tracker.record_trade_latency(latency_ms=100)

        # Get dashboard data
        provider = DashboardDataProvider(data_dir=str(temp_data_dir))
        data = await provider.get_dashboard_data()

        assert "performance" in data
