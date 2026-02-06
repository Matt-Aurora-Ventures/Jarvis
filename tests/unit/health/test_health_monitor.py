"""
Unit tests for the HealthMonitor class.

Tests cover:
- Bot registration
- Individual bot health checks
- All-bots health check
- Continuous monitoring with start/stop
- Health status callbacks
"""

import asyncio
import pytest
from datetime import datetime, timezone
from typing import Callable
from unittest.mock import AsyncMock, MagicMock, patch


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_check_fn():
    """Create a mock health check function."""
    async def check():
        return {
            "status": "healthy",
            "latency_ms": 10.5,
            "message": "OK",
        }
    return check


@pytest.fixture
def failing_check_fn():
    """Create a failing health check function."""
    async def check():
        return {
            "status": "unhealthy",
            "latency_ms": 0,
            "message": "Connection failed",
        }
    return check


@pytest.fixture
def slow_check_fn():
    """Create a slow health check function."""
    async def check():
        await asyncio.sleep(0.1)
        return {
            "status": "healthy",
            "latency_ms": 100,
            "message": "OK",
        }
    return check


# =============================================================================
# HEALTH MONITOR TESTS
# =============================================================================

class TestHealthMonitorImport:
    """Tests for module imports."""

    def test_import_health_monitor_module(self):
        """Test that health monitor module can be imported."""
        from core.health.monitor import HealthMonitor
        assert HealthMonitor is not None

    def test_import_health_status(self):
        """Test that HealthStatus can be imported from monitor module."""
        from core.health.monitor import HealthMonitor
        from core.health.status import HealthStatus
        assert HealthStatus is not None


class TestHealthMonitorInit:
    """Tests for HealthMonitor initialization."""

    def test_init_default(self):
        """Test default initialization."""
        from core.health.monitor import HealthMonitor

        monitor = HealthMonitor()
        assert monitor is not None
        assert monitor._bots == {}
        assert monitor._monitoring_task is None
        assert monitor._running is False

    def test_init_with_check_interval(self):
        """Test initialization with custom check interval."""
        from core.health.monitor import HealthMonitor

        monitor = HealthMonitor(check_interval=30)
        assert monitor._check_interval == 30

    def test_init_with_on_status_change_callback(self):
        """Test initialization with status change callback."""
        from core.health.monitor import HealthMonitor

        callback = MagicMock()
        monitor = HealthMonitor(on_status_change=callback)
        assert monitor._on_status_change == callback


class TestBotRegistration:
    """Tests for bot registration."""

    def test_register_bot(self, mock_check_fn):
        """Test registering a bot."""
        from core.health.monitor import HealthMonitor

        monitor = HealthMonitor()
        monitor.register_bot("test_bot", mock_check_fn)

        assert "test_bot" in monitor._bots
        assert monitor._bots["test_bot"]["check_fn"] == mock_check_fn

    def test_register_multiple_bots(self, mock_check_fn):
        """Test registering multiple bots."""
        from core.health.monitor import HealthMonitor

        monitor = HealthMonitor()
        monitor.register_bot("bot1", mock_check_fn)
        monitor.register_bot("bot2", mock_check_fn)

        assert len(monitor._bots) == 2
        assert "bot1" in monitor._bots
        assert "bot2" in monitor._bots

    def test_register_bot_overwrites_existing(self, mock_check_fn, failing_check_fn):
        """Test that re-registering a bot overwrites the check function."""
        from core.health.monitor import HealthMonitor

        monitor = HealthMonitor()
        monitor.register_bot("test_bot", mock_check_fn)
        monitor.register_bot("test_bot", failing_check_fn)

        assert monitor._bots["test_bot"]["check_fn"] == failing_check_fn

    def test_unregister_bot(self, mock_check_fn):
        """Test unregistering a bot."""
        from core.health.monitor import HealthMonitor

        monitor = HealthMonitor()
        monitor.register_bot("test_bot", mock_check_fn)
        monitor.unregister_bot("test_bot")

        assert "test_bot" not in monitor._bots

    def test_unregister_nonexistent_bot(self):
        """Test unregistering a bot that doesn't exist."""
        from core.health.monitor import HealthMonitor

        monitor = HealthMonitor()
        # Should not raise
        monitor.unregister_bot("nonexistent")

    def test_get_registered_bots(self, mock_check_fn):
        """Test getting list of registered bots."""
        from core.health.monitor import HealthMonitor

        monitor = HealthMonitor()
        monitor.register_bot("bot1", mock_check_fn)
        monitor.register_bot("bot2", mock_check_fn)

        bots = monitor.get_registered_bots()
        assert bots == ["bot1", "bot2"]


class TestCheckBot:
    """Tests for individual bot health checks."""

    @pytest.mark.asyncio
    async def test_check_bot_healthy(self, mock_check_fn):
        """Test checking a healthy bot."""
        from core.health.monitor import HealthMonitor
        from core.health.status import HealthStatus

        monitor = HealthMonitor()
        monitor.register_bot("test_bot", mock_check_fn)

        status = await monitor.check_bot("test_bot")

        assert status.status == HealthStatus.HEALTHY
        assert status.name == "test_bot"
        assert status.latency_ms > 0

    @pytest.mark.asyncio
    async def test_check_bot_unhealthy(self, failing_check_fn):
        """Test checking an unhealthy bot."""
        from core.health.monitor import HealthMonitor
        from core.health.status import HealthStatus

        monitor = HealthMonitor()
        monitor.register_bot("test_bot", failing_check_fn)

        status = await monitor.check_bot("test_bot")

        assert status.status == HealthStatus.UNHEALTHY
        assert "Connection failed" in status.message

    @pytest.mark.asyncio
    async def test_check_unregistered_bot(self):
        """Test checking a bot that isn't registered."""
        from core.health.monitor import HealthMonitor
        from core.health.status import HealthStatus

        monitor = HealthMonitor()

        status = await monitor.check_bot("nonexistent")

        assert status.status == HealthStatus.UNKNOWN
        assert "not registered" in status.message.lower()

    @pytest.mark.asyncio
    async def test_check_bot_with_timeout(self):
        """Test that check times out for slow bots."""
        from core.health.monitor import HealthMonitor
        from core.health.status import HealthStatus

        async def very_slow_check():
            await asyncio.sleep(5)  # 5 seconds
            return {"status": "healthy"}

        monitor = HealthMonitor(check_timeout=0.1)
        monitor.register_bot("slow_bot", very_slow_check)

        status = await monitor.check_bot("slow_bot")

        assert status.status == HealthStatus.TIMEOUT
        assert "timed out" in status.message.lower()

    @pytest.mark.asyncio
    async def test_check_bot_exception_handling(self):
        """Test handling exceptions from check function."""
        from core.health.monitor import HealthMonitor
        from core.health.status import HealthStatus

        async def error_check():
            raise RuntimeError("Check failed!")

        monitor = HealthMonitor()
        monitor.register_bot("error_bot", error_check)

        status = await monitor.check_bot("error_bot")

        assert status.status == HealthStatus.ERROR
        assert "Check failed!" in status.message

    @pytest.mark.asyncio
    async def test_check_bot_updates_last_check(self, mock_check_fn):
        """Test that checking a bot updates last_check timestamp."""
        from core.health.monitor import HealthMonitor

        monitor = HealthMonitor()
        monitor.register_bot("test_bot", mock_check_fn)

        assert monitor._bots["test_bot"].get("last_check") is None

        await monitor.check_bot("test_bot")

        assert monitor._bots["test_bot"]["last_check"] is not None
        assert isinstance(monitor._bots["test_bot"]["last_check"], datetime)


class TestCheckAll:
    """Tests for checking all bots."""

    @pytest.mark.asyncio
    async def test_check_all_empty(self):
        """Test check_all with no registered bots."""
        from core.health.monitor import HealthMonitor

        monitor = HealthMonitor()
        results = await monitor.check_all()

        assert results == {}

    @pytest.mark.asyncio
    async def test_check_all_single_bot(self, mock_check_fn):
        """Test check_all with a single bot."""
        from core.health.monitor import HealthMonitor
        from core.health.status import HealthStatus

        monitor = HealthMonitor()
        monitor.register_bot("test_bot", mock_check_fn)

        results = await monitor.check_all()

        assert "test_bot" in results
        assert results["test_bot"].status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_check_all_multiple_bots(self, mock_check_fn, failing_check_fn):
        """Test check_all with multiple bots."""
        from core.health.monitor import HealthMonitor
        from core.health.status import HealthStatus

        monitor = HealthMonitor()
        monitor.register_bot("healthy_bot", mock_check_fn)
        monitor.register_bot("unhealthy_bot", failing_check_fn)

        results = await monitor.check_all()

        assert len(results) == 2
        assert results["healthy_bot"].status == HealthStatus.HEALTHY
        assert results["unhealthy_bot"].status == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_check_all_concurrent(self, slow_check_fn):
        """Test that check_all runs checks concurrently."""
        from core.health.monitor import HealthMonitor
        import time

        monitor = HealthMonitor()
        # Register 5 slow bots (each takes 0.1s)
        for i in range(5):
            monitor.register_bot(f"bot_{i}", slow_check_fn)

        start = time.time()
        results = await monitor.check_all()
        duration = time.time() - start

        # If run concurrently, should take ~0.1s, not ~0.5s
        assert len(results) == 5
        assert duration < 0.3  # Allow some overhead

    @pytest.mark.asyncio
    async def test_check_all_returns_dict_of_bot_status(self, mock_check_fn):
        """Test that check_all returns BotStatus objects."""
        from core.health.monitor import HealthMonitor, BotStatus

        monitor = HealthMonitor()
        monitor.register_bot("test_bot", mock_check_fn)

        results = await monitor.check_all()

        assert isinstance(results["test_bot"], BotStatus)


class TestMonitoring:
    """Tests for continuous monitoring."""

    @pytest.mark.asyncio
    async def test_start_monitoring(self, mock_check_fn):
        """Test starting monitoring."""
        from core.health.monitor import HealthMonitor

        monitor = HealthMonitor(check_interval=0.1)
        monitor.register_bot("test_bot", mock_check_fn)

        await monitor.start_monitoring()

        assert monitor._running is True
        assert monitor._monitoring_task is not None

        # Clean up
        await monitor.stop_monitoring()

    @pytest.mark.asyncio
    async def test_stop_monitoring(self, mock_check_fn):
        """Test stopping monitoring."""
        from core.health.monitor import HealthMonitor

        monitor = HealthMonitor(check_interval=0.1)
        monitor.register_bot("test_bot", mock_check_fn)

        await monitor.start_monitoring()
        await monitor.stop_monitoring()

        assert monitor._running is False
        assert monitor._monitoring_task is None

    @pytest.mark.asyncio
    async def test_monitoring_runs_checks_periodically(self, mock_check_fn):
        """Test that monitoring runs checks periodically."""
        from core.health.monitor import HealthMonitor

        check_count = 0
        original_fn = mock_check_fn

        async def counting_check():
            nonlocal check_count
            check_count += 1
            return await original_fn()

        monitor = HealthMonitor(check_interval=0.05)
        monitor.register_bot("test_bot", counting_check)

        await monitor.start_monitoring()
        await asyncio.sleep(0.2)  # Should run ~4 times
        await monitor.stop_monitoring()

        assert check_count >= 3

    @pytest.mark.asyncio
    async def test_start_monitoring_twice_is_safe(self, mock_check_fn):
        """Test that starting monitoring twice doesn't create multiple tasks."""
        from core.health.monitor import HealthMonitor

        monitor = HealthMonitor(check_interval=0.1)
        monitor.register_bot("test_bot", mock_check_fn)

        await monitor.start_monitoring()
        task1 = monitor._monitoring_task

        await monitor.start_monitoring()
        task2 = monitor._monitoring_task

        assert task1 is task2

        await monitor.stop_monitoring()

    @pytest.mark.asyncio
    async def test_stop_monitoring_when_not_running_is_safe(self):
        """Test that stopping when not running doesn't raise."""
        from core.health.monitor import HealthMonitor

        monitor = HealthMonitor()

        # Should not raise
        await monitor.stop_monitoring()

    @pytest.mark.asyncio
    async def test_monitoring_calls_on_status_change(self, mock_check_fn, failing_check_fn):
        """Test that status changes trigger callback."""
        from core.health.monitor import HealthMonitor

        status_changes = []

        def on_change(bot_name, old_status, new_status):
            status_changes.append((bot_name, old_status, new_status))

        monitor = HealthMonitor(check_interval=0.05, on_status_change=on_change)

        # Start healthy
        monitor.register_bot("test_bot", mock_check_fn)

        await monitor.start_monitoring()
        await asyncio.sleep(0.1)

        # Change to unhealthy
        monitor._bots["test_bot"]["check_fn"] = failing_check_fn

        await asyncio.sleep(0.1)
        await monitor.stop_monitoring()

        # Should have recorded the status change
        assert len(status_changes) >= 1


class TestBotStatus:
    """Tests for BotStatus dataclass."""

    def test_bot_status_creation(self):
        """Test creating a BotStatus."""
        from core.health.monitor import BotStatus
        from core.health.status import HealthStatus

        status = BotStatus(
            name="test_bot",
            status=HealthStatus.HEALTHY,
            message="OK",
            latency_ms=10.5,
        )

        assert status.name == "test_bot"
        assert status.status == HealthStatus.HEALTHY
        assert status.message == "OK"
        assert status.latency_ms == 10.5

    def test_bot_status_to_dict(self):
        """Test converting BotStatus to dictionary."""
        from core.health.monitor import BotStatus
        from core.health.status import HealthStatus

        status = BotStatus(
            name="test_bot",
            status=HealthStatus.HEALTHY,
            message="OK",
            latency_ms=10.5,
        )

        d = status.to_dict()

        assert d["name"] == "test_bot"
        assert d["status"] == "healthy"
        assert d["message"] == "OK"
        assert d["latency_ms"] == 10.5

    def test_bot_status_is_ok_property(self):
        """Test is_ok property."""
        from core.health.monitor import BotStatus
        from core.health.status import HealthStatus

        healthy = BotStatus(name="test", status=HealthStatus.HEALTHY, message="", latency_ms=0)
        unhealthy = BotStatus(name="test", status=HealthStatus.UNHEALTHY, message="", latency_ms=0)

        assert healthy.is_ok is True
        assert unhealthy.is_ok is False


class TestHealthMonitorContext:
    """Tests for async context manager support."""

    @pytest.mark.asyncio
    async def test_async_context_manager(self, mock_check_fn):
        """Test using HealthMonitor as async context manager."""
        from core.health.monitor import HealthMonitor

        async with HealthMonitor(check_interval=0.1) as monitor:
            monitor.register_bot("test_bot", mock_check_fn)
            await monitor.start_monitoring()
            await asyncio.sleep(0.05)
            assert monitor._running is True

        # After exiting context, monitoring should be stopped
        assert monitor._running is False
