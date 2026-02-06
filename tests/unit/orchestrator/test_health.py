"""
Tests for OrchestratorHealth.

Tests:
- Health checks for all bots
- Restarting unhealthy bots
- Failure alerting
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta


class TestOrchestratorHealth:
    """Tests for OrchestratorHealth class."""

    @pytest.fixture
    def health_checker(self):
        """Create a fresh health checker for each test."""
        from core.orchestrator.health import OrchestratorHealth
        return OrchestratorHealth()

    @pytest.fixture
    def mock_orchestrator(self):
        """Create a mock orchestrator."""
        orch = MagicMock()
        orch.bots = {}
        orch.restart_bot = AsyncMock()
        orch.get_status = MagicMock(return_value={})
        return orch

    @pytest.fixture
    def healthy_bot(self):
        """Create a healthy mock bot."""
        bot = MagicMock()
        bot.is_running = MagicMock(return_value=True)
        bot.health_check = AsyncMock(return_value={"healthy": True, "latency_ms": 50})
        bot.last_activity = datetime.now()
        return bot

    @pytest.fixture
    def unhealthy_bot(self):
        """Create an unhealthy mock bot."""
        bot = MagicMock()
        bot.is_running = MagicMock(return_value=True)
        bot.health_check = AsyncMock(return_value={"healthy": False, "error": "Connection failed"})
        bot.last_activity = datetime.now() - timedelta(minutes=30)
        return bot

    @pytest.mark.asyncio
    async def test_check_all_bots_healthy(self, health_checker, healthy_bot):
        """Test checking health when all bots are healthy."""
        with patch.object(health_checker, "_get_orchestrator") as mock_get:
            mock_orch = MagicMock()
            mock_orch.bots = {"bot1": healthy_bot, "bot2": healthy_bot}
            mock_get.return_value = mock_orch

            results = await health_checker.check_all_bots()

        assert "bot1" in results
        assert "bot2" in results
        assert results["bot1"]["healthy"] is True
        assert results["bot2"]["healthy"] is True

    @pytest.mark.asyncio
    async def test_check_all_bots_with_unhealthy(self, health_checker, healthy_bot, unhealthy_bot):
        """Test checking health with some unhealthy bots."""
        with patch.object(health_checker, "_get_orchestrator") as mock_get:
            mock_orch = MagicMock()
            mock_orch.bots = {"healthy": healthy_bot, "unhealthy": unhealthy_bot}
            mock_get.return_value = mock_orch

            results = await health_checker.check_all_bots()

        assert results["healthy"]["healthy"] is True
        assert results["unhealthy"]["healthy"] is False
        assert "error" in results["unhealthy"]

    @pytest.mark.asyncio
    async def test_restart_unhealthy(self, health_checker, unhealthy_bot):
        """Test restarting unhealthy bots."""
        mock_orch = MagicMock()
        mock_orch.bots = {"unhealthy": unhealthy_bot}
        mock_orch.restart_bot = AsyncMock()

        with patch.object(health_checker, "_get_orchestrator", return_value=mock_orch):
            with patch.object(health_checker, "check_all_bots", return_value={
                "unhealthy": {"healthy": False, "error": "Test"}
            }):
                restarted = await health_checker.restart_unhealthy()

        assert "unhealthy" in restarted
        mock_orch.restart_bot.assert_called_once_with("unhealthy")

    @pytest.mark.asyncio
    async def test_restart_unhealthy_no_unhealthy(self, health_checker, healthy_bot):
        """Test restart_unhealthy when all bots are healthy."""
        mock_orch = MagicMock()
        mock_orch.bots = {"healthy": healthy_bot}

        with patch.object(health_checker, "_get_orchestrator", return_value=mock_orch):
            with patch.object(health_checker, "check_all_bots", return_value={
                "healthy": {"healthy": True}
            }):
                restarted = await health_checker.restart_unhealthy()

        assert restarted == []

    @pytest.mark.asyncio
    async def test_alert_on_failure(self, health_checker):
        """Test that alerts are sent on bot failure."""
        alert_callback = AsyncMock()
        health_checker.set_alert_callback(alert_callback)

        with patch.object(health_checker, "_get_orchestrator") as mock_get:
            mock_orch = MagicMock()
            unhealthy = MagicMock()
            unhealthy.is_running = MagicMock(return_value=False)
            unhealthy.health_check = AsyncMock(return_value={"healthy": False, "error": "Crashed"})
            mock_orch.bots = {"failing": unhealthy}
            mock_get.return_value = mock_orch

            await health_checker.check_all_bots()

        alert_callback.assert_called_once()
        call_args = alert_callback.call_args[0]
        assert "failing" in call_args[0]  # Bot name in message

    def test_set_alert_callback(self, health_checker):
        """Test setting the alert callback."""
        callback = AsyncMock()

        health_checker.set_alert_callback(callback)

        assert health_checker._alert_callback is callback

    def test_get_health_summary(self, health_checker):
        """Test getting a summary of health status."""
        health_checker._last_check_results = {
            "bot1": {"healthy": True, "latency_ms": 50},
            "bot2": {"healthy": True, "latency_ms": 75},
            "bot3": {"healthy": False, "error": "Connection failed"},
        }

        summary = health_checker.get_health_summary()

        assert summary["total"] == 3
        assert summary["healthy"] == 2
        assert summary["unhealthy"] == 1
        assert summary["health_percentage"] == pytest.approx(66.67, rel=0.1)

    @pytest.mark.asyncio
    async def test_check_bot_timeout(self, health_checker):
        """Test handling of health check timeout."""
        slow_bot = MagicMock()
        slow_bot.is_running = MagicMock(return_value=True)

        async def slow_check():
            await asyncio.sleep(10)  # Simulates timeout
            return {"healthy": True}

        slow_bot.health_check = slow_check

        with patch.object(health_checker, "_get_orchestrator") as mock_get:
            mock_orch = MagicMock()
            mock_orch.bots = {"slow": slow_bot}
            mock_get.return_value = mock_orch

            # Should timeout and mark as unhealthy
            health_checker._check_timeout = 0.1  # 100ms timeout
            results = await health_checker.check_all_bots()

        assert results["slow"]["healthy"] is False
        assert "timeout" in results["slow"].get("error", "").lower()


class TestOrchestratorHealthSingleton:
    """Test singleton pattern for health checker."""

    def test_get_health_checker_returns_singleton(self):
        """Test that get_health_checker returns the same instance."""
        from core.orchestrator.health import get_health_checker

        hc1 = get_health_checker()
        hc2 = get_health_checker()

        assert hc1 is hc2


class TestHealthCheckScheduling:
    """Tests for scheduled health checks."""

    @pytest.fixture
    def health_checker(self):
        from core.orchestrator.health import OrchestratorHealth
        return OrchestratorHealth()

    @pytest.mark.asyncio
    async def test_start_periodic_checks(self, health_checker):
        """Test starting periodic health checks."""
        check_count = 0

        async def mock_check():
            nonlocal check_count
            check_count += 1
            return {"bot1": {"healthy": True}}

        with patch.object(health_checker, "check_all_bots", mock_check):
            # Start with very short interval
            task = await health_checker.start_periodic_checks(interval_seconds=0.1)

            # Wait for a few checks
            await asyncio.sleep(0.35)

            # Stop checks
            await health_checker.stop_periodic_checks()

        # Should have run at least 2-3 times
        assert check_count >= 2

    @pytest.mark.asyncio
    async def test_stop_periodic_checks(self, health_checker):
        """Test stopping periodic health checks."""
        with patch.object(health_checker, "check_all_bots", AsyncMock()):
            await health_checker.start_periodic_checks(interval_seconds=0.1)
            await asyncio.sleep(0.05)

            await health_checker.stop_periodic_checks()

        assert health_checker._check_task is None or health_checker._check_task.done()
