"""
Tests for Price Alert Triggering

Tests:
- Price threshold alerts (above/below)
- Percentage change alerts (up/down)
- Alert persistence (survives restarts)
- Alert cooldown (prevents spam)
- User alert management (add/remove/list)
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import json

from core.alerts import AlertEngine, AlertType, DeliveryChannel
from core.alerts.price_monitor import PriceAlertMonitor, PriceBaseline


class TestPriceThresholdAlerts:
    """Test price threshold alert creation and triggering"""

    @pytest.fixture
    def engine(self):
        """Create alert engine with temp storage"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = AlertEngine(storage_path=tmpdir)
            yield engine

    @pytest.mark.asyncio
    async def test_add_price_alert_above(self, engine):
        """Test adding a price alert for 'above' threshold"""
        alert_id = await engine.add_price_alert(
            user_id="user123",
            token="SOL",
            threshold_price=150.0,
            direction="above",
        )

        assert alert_id.startswith("PRICE-")
        assert len(alert_id) == 12 + 6  # PRICE- + 12 hex chars

        # Check subscription was created
        alerts = await engine.get_user_alerts("user123")
        assert len(alerts) == 1
        assert alerts[0]["token"] == "SOL"
        assert alerts[0]["threshold"] == 150.0
        assert alerts[0]["direction"] == "above"

    @pytest.mark.asyncio
    async def test_add_price_alert_below(self, engine):
        """Test adding a price alert for 'below' threshold"""
        alert_id = await engine.add_price_alert(
            user_id="user123",
            token="SOL",
            threshold_price=100.0,
            direction="below",
        )

        alerts = await engine.get_user_alerts("user123")
        assert len(alerts) == 1
        assert alerts[0]["direction"] == "below"

    @pytest.mark.asyncio
    async def test_trigger_price_alert_above(self, engine):
        """Test triggering price alert when threshold is crossed (above)"""
        # Add alert
        await engine.add_price_alert(
            user_id="user123",
            token="SOL",
            threshold_price=150.0,
            direction="above",
        )

        # Trigger alert
        await engine.trigger_price_alert(
            token="SOL",
            current_price=155.0,
            threshold_price=150.0,
            direction="above",
        )

        # Check alert was created
        recent = await engine.get_recent_alerts()
        assert len(recent) > 0
        assert recent[-1].token == "SOL"
        assert "above" in recent[-1].message.lower()

    @pytest.mark.asyncio
    async def test_trigger_price_alert_below(self, engine):
        """Test triggering price alert when threshold is crossed (below)"""
        await engine.add_price_alert(
            user_id="user123",
            token="SOL",
            threshold_price=100.0,
            direction="below",
        )

        await engine.trigger_price_alert(
            token="SOL",
            current_price=95.0,
            threshold_price=100.0,
            direction="below",
        )

        recent = await engine.get_recent_alerts()
        assert len(recent) > 0
        assert "below" in recent[-1].message.lower()


class TestPercentageChangeAlerts:
    """Test percentage change alert functionality"""

    @pytest.fixture
    def engine(self):
        """Create alert engine with temp storage"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = AlertEngine(storage_path=tmpdir)
            yield engine

    @pytest.mark.asyncio
    async def test_add_percentage_alert_up(self, engine):
        """Test adding percentage change alert (upward)"""
        alert_id = await engine.add_percentage_alert(
            user_id="user123",
            token="SOL",
            percentage_change=5.0,
            direction="up",
        )

        assert alert_id.startswith("PCT-")

        alerts = await engine.get_user_alerts("user123")
        assert len(alerts) == 1
        assert alerts[0]["type"] == "percentage"
        assert alerts[0]["percentage"] == 5.0
        assert alerts[0]["direction"] == "up"

    @pytest.mark.asyncio
    async def test_add_percentage_alert_down(self, engine):
        """Test adding percentage change alert (downward)"""
        alert_id = await engine.add_percentage_alert(
            user_id="user123",
            token="SOL",
            percentage_change=10.0,
            direction="down",
        )

        alerts = await engine.get_user_alerts("user123")
        assert alerts[0]["direction"] == "down"
        assert alerts[0]["percentage"] == 10.0

    @pytest.mark.asyncio
    async def test_trigger_percentage_alert_up(self, engine):
        """Test triggering percentage alert (upward movement)"""
        await engine.add_percentage_alert(
            user_id="user123",
            token="SOL",
            percentage_change=5.0,
            direction="up",
        )

        # Trigger 5% up from baseline
        await engine.trigger_percentage_alert(
            token="SOL",
            current_price=105.0,
            baseline_price=100.0,
            percentage_change=5.0,
            direction="up",
        )

        recent = await engine.get_recent_alerts()
        assert len(recent) > 0
        assert "5.0%" in recent[-1].title or "5.0%" in recent[-1].message

    @pytest.mark.asyncio
    async def test_trigger_percentage_alert_down(self, engine):
        """Test triggering percentage alert (downward movement)"""
        await engine.add_percentage_alert(
            user_id="user123",
            token="SOL",
            percentage_change=10.0,
            direction="down",
        )

        await engine.trigger_percentage_alert(
            token="SOL",
            current_price=90.0,
            baseline_price=100.0,
            percentage_change=-10.0,
            direction="down",
        )

        recent = await engine.get_recent_alerts()
        assert len(recent) > 0
        assert "down" in recent[-1].title.lower() or "down" in recent[-1].message.lower()


class TestAlertPersistence:
    """Test alert persistence across restarts"""

    @pytest.mark.asyncio
    async def test_alerts_survive_restart(self):
        """Test that alerts persist after engine restart"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create engine and add alerts
            engine1 = AlertEngine(storage_path=tmpdir)
            await engine1.add_price_alert(
                user_id="user123",
                token="SOL",
                threshold_price=150.0,
                direction="above",
            )
            await engine1.add_percentage_alert(
                user_id="user123",
                token="BONK",
                percentage_change=5.0,
                direction="up",
            )

            alerts1 = await engine1.get_user_alerts("user123")
            assert len(alerts1) == 2

            # Create new engine instance (simulating restart)
            engine2 = AlertEngine(storage_path=tmpdir)
            alerts2 = await engine2.get_user_alerts("user123")

            # Alerts should still exist
            assert len(alerts2) == 2
            assert any(a["token"] == "SOL" for a in alerts2)
            assert any(a["token"] == "BONK" for a in alerts2)

    @pytest.mark.asyncio
    async def test_storage_file_format(self):
        """Test that storage file is valid JSON"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = AlertEngine(storage_path=tmpdir)
            await engine.add_price_alert(
                user_id="user123",
                token="SOL",
                threshold_price=150.0,
                direction="above",
            )

            # Check storage file exists and is valid JSON
            storage_file = Path(tmpdir) / "subscriptions.json"
            assert storage_file.exists()

            with open(storage_file) as f:
                data = json.load(f)

            assert "subscriptions" in data
            assert "user123" in data["subscriptions"]


class TestAlertManagement:
    """Test user alert management operations"""

    @pytest.fixture
    def engine(self):
        """Create alert engine"""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = AlertEngine(storage_path=tmpdir)
            yield engine

    @pytest.mark.asyncio
    async def test_remove_specific_alert(self, engine):
        """Test removing a specific alert by ID"""
        # Add multiple alerts
        alert_id1 = await engine.add_price_alert(
            user_id="user123",
            token="SOL",
            threshold_price=150.0,
            direction="above",
        )
        alert_id2 = await engine.add_price_alert(
            user_id="user123",
            token="BONK",
            threshold_price=0.00001,
            direction="below",
        )

        # Remove one alert
        removed = await engine.remove_alert("user123", alert_id1)
        assert removed is True

        # Check only one alert remains
        alerts = await engine.get_user_alerts("user123")
        assert len(alerts) == 1
        assert alerts[0]["token"] == "BONK"

    @pytest.mark.asyncio
    async def test_remove_nonexistent_alert(self, engine):
        """Test removing an alert that doesn't exist"""
        removed = await engine.remove_alert("user123", "FAKE-ALERT-ID")
        assert removed is False

    @pytest.mark.asyncio
    async def test_list_empty_alerts(self, engine):
        """Test listing alerts when user has none"""
        alerts = await engine.get_user_alerts("user123")
        assert alerts == []

    @pytest.mark.asyncio
    async def test_list_multiple_alerts(self, engine):
        """Test listing multiple alerts"""
        await engine.add_price_alert(
            user_id="user123",
            token="SOL",
            threshold_price=150.0,
            direction="above",
        )
        await engine.add_percentage_alert(
            user_id="user123",
            token="BONK",
            percentage_change=5.0,
            direction="up",
        )
        await engine.add_price_alert(
            user_id="user123",
            token="JUP",
            threshold_price=1.0,
            direction="below",
        )

        alerts = await engine.get_user_alerts("user123")
        assert len(alerts) == 3

        # Check different types
        price_alerts = [a for a in alerts if a["type"] == "price"]
        pct_alerts = [a for a in alerts if a["type"] == "percentage"]

        assert len(price_alerts) == 2
        assert len(pct_alerts) == 1


class TestPriceMonitor:
    """Test price monitoring and alert triggering"""

    @pytest.fixture
    def engine(self):
        """Create alert engine"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield AlertEngine(storage_path=tmpdir)

    async def mock_price_fetcher(self, token: str):
        """Mock price fetcher"""
        prices = {
            "SOL": {"price_usd": 155.0},
            "BONK": {"price_usd": 0.00001},
        }
        return prices.get(token, {"price_usd": 0})

    @pytest.mark.asyncio
    async def test_monitor_initialization(self, engine):
        """Test price monitor initialization"""
        monitor = PriceAlertMonitor(
            alert_engine=engine,
            price_fetcher_func=self.mock_price_fetcher,
            check_interval_seconds=10,
        )

        assert monitor.running is False
        assert monitor.check_interval == 10

    @pytest.mark.asyncio
    async def test_baseline_tracking(self, engine):
        """Test baseline price tracking for percentage alerts"""
        monitor = PriceAlertMonitor(
            alert_engine=engine,
            price_fetcher_func=self.mock_price_fetcher,
        )

        # Set baseline
        monitor.set_baseline("SOL", 100.0)

        assert "SOL" in monitor.baselines
        assert monitor.baselines["SOL"].price == 100.0
        assert not monitor.baselines["SOL"].is_stale()

    @pytest.mark.asyncio
    async def test_baseline_staleness(self, engine):
        """Test baseline staleness detection"""
        monitor = PriceAlertMonitor(
            alert_engine=engine,
            price_fetcher_func=self.mock_price_fetcher,
        )

        # Create stale baseline
        baseline = PriceBaseline(
            token="SOL",
            price=100.0,
            timestamp=datetime.now() - timedelta(hours=25),
        )
        monitor.baselines["SOL"] = baseline

        assert baseline.is_stale(max_age_hours=24)

    @pytest.mark.asyncio
    async def test_alert_cooldown(self, engine):
        """Test alert cooldown prevents spam"""
        monitor = PriceAlertMonitor(
            alert_engine=engine,
            price_fetcher_func=self.mock_price_fetcher,
            alert_cooldown_seconds=300,
        )

        alert_key = "user123:SOL:price:150:above"

        # First alert should be allowed
        assert monitor._can_send_alert(alert_key) is True

        # Mark as sent
        monitor.last_alerts[alert_key] = datetime.now()

        # Second alert should be blocked (within cooldown)
        assert monitor._can_send_alert(alert_key) is False

        # Simulate time passing
        monitor.last_alerts[alert_key] = datetime.now() - timedelta(seconds=301)

        # Should be allowed again
        assert monitor._can_send_alert(alert_key) is True


class TestVolumeAlerts:
    """Test volume spike alert functionality"""

    @pytest.fixture
    def engine(self):
        """Create alert engine"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield AlertEngine(storage_path=tmpdir)

    @pytest.mark.asyncio
    async def test_trigger_volume_alert(self, engine):
        """Test triggering volume spike alert"""
        await engine.trigger_volume_alert(
            token="SOL",
            current_volume=10_000_000,
            average_volume=2_000_000,
            multiplier=5.0,
        )

        recent = await engine.get_recent_alerts()
        assert len(recent) > 0
        assert "Volume Spike" in recent[-1].title
        assert "5.0x" in recent[-1].message


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
