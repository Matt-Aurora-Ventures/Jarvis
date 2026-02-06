"""
Tests for Watchdog - component health monitoring.

Tests the ability to monitor components, handle timeouts,
and restart failing components with health check integration.
"""

import pytest
import asyncio
import time
from typing import Dict, Any, Callable
from unittest.mock import Mock, AsyncMock, patch, MagicMock


class TestWatchdog:
    """Test suite for Watchdog class."""

    def test_init_default(self):
        """Watchdog should initialize with defaults."""
        from core.recovery.watchdog import Watchdog

        watchdog = Watchdog()

        assert watchdog.default_timeout == 30
        assert watchdog._monitored_components == {}

    def test_init_custom_timeout(self):
        """Watchdog should accept custom default timeout."""
        from core.recovery.watchdog import Watchdog

        watchdog = Watchdog(default_timeout=60)

        assert watchdog.default_timeout == 60

    def test_monitor_registers_component(self):
        """monitor should register a component for monitoring."""
        from core.recovery.watchdog import Watchdog

        watchdog = Watchdog()

        watchdog.monitor("x_bot", timeout=30)

        assert "x_bot" in watchdog._monitored_components
        assert watchdog._monitored_components["x_bot"]["timeout"] == 30

    def test_monitor_with_default_timeout(self):
        """monitor should use default timeout if not specified."""
        from core.recovery.watchdog import Watchdog

        watchdog = Watchdog(default_timeout=45)

        watchdog.monitor("trading")

        assert watchdog._monitored_components["trading"]["timeout"] == 45

    def test_monitor_with_health_check(self):
        """monitor should accept a health check function."""
        from core.recovery.watchdog import Watchdog

        watchdog = Watchdog()
        health_check = Mock(return_value=True)

        watchdog.monitor("x_bot", health_check=health_check)

        assert watchdog._monitored_components["x_bot"]["health_check"] == health_check

    def test_unmonitor_removes_component(self):
        """unmonitor should remove a component from monitoring."""
        from core.recovery.watchdog import Watchdog

        watchdog = Watchdog()
        watchdog.monitor("x_bot")
        watchdog.monitor("trading")

        watchdog.unmonitor("x_bot")

        assert "x_bot" not in watchdog._monitored_components
        assert "trading" in watchdog._monitored_components

    def test_heartbeat_updates_last_seen(self):
        """heartbeat should update last_seen timestamp."""
        from core.recovery.watchdog import Watchdog

        watchdog = Watchdog()
        watchdog.monitor("x_bot")

        initial_time = watchdog._monitored_components["x_bot"].get("last_seen", 0)

        time.sleep(0.01)
        watchdog.heartbeat("x_bot")

        updated_time = watchdog._monitored_components["x_bot"]["last_seen"]
        assert updated_time > initial_time

    def test_heartbeat_unknown_component(self):
        """heartbeat for unknown component should not raise."""
        from core.recovery.watchdog import Watchdog

        watchdog = Watchdog()

        # Should not raise
        watchdog.heartbeat("unknown_component")

    def test_is_healthy_true(self):
        """is_healthy should return True for recently active component."""
        from core.recovery.watchdog import Watchdog

        watchdog = Watchdog(default_timeout=30)
        watchdog.monitor("x_bot")
        watchdog.heartbeat("x_bot")

        assert watchdog.is_healthy("x_bot") is True

    def test_is_healthy_false_timeout(self):
        """is_healthy should return False after timeout."""
        from core.recovery.watchdog import Watchdog

        watchdog = Watchdog(default_timeout=0.01)  # Very short timeout
        watchdog.monitor("x_bot", timeout=0.01)
        watchdog.heartbeat("x_bot")

        time.sleep(0.02)  # Wait for timeout

        assert watchdog.is_healthy("x_bot") is False

    def test_is_healthy_unknown_component(self):
        """is_healthy should return False for unknown component."""
        from core.recovery.watchdog import Watchdog

        watchdog = Watchdog()

        assert watchdog.is_healthy("unknown") is False

    def test_on_timeout_registers_callback(self):
        """on_timeout should register a callback for timeout events."""
        from core.recovery.watchdog import Watchdog

        watchdog = Watchdog()
        callback = Mock()

        watchdog.on_timeout("x_bot", callback)

        assert "x_bot" in watchdog._timeout_callbacks
        assert callback in watchdog._timeout_callbacks["x_bot"]

    def test_on_timeout_callback_invoked(self):
        """on_timeout callback should be invoked when timeout occurs."""
        from core.recovery.watchdog import Watchdog

        watchdog = Watchdog(default_timeout=0.01)
        callback = Mock()

        watchdog.monitor("x_bot", timeout=0.01)
        watchdog.on_timeout("x_bot", callback)
        watchdog.heartbeat("x_bot")

        time.sleep(0.02)

        # Check for timeout
        watchdog.check_timeouts()

        callback.assert_called_once()
        # Callback should receive component name
        callback.assert_called_with("x_bot")

    def test_restart_component_calls_restart_func(self):
        """restart_component should call the registered restart function."""
        from core.recovery.watchdog import Watchdog

        watchdog = Watchdog()
        restart_func = Mock(return_value=True)

        watchdog.monitor("x_bot", restart_func=restart_func)

        result = watchdog.restart_component("x_bot")

        restart_func.assert_called_once()
        assert result is True

    def test_restart_component_no_restart_func(self):
        """restart_component should return False if no restart function."""
        from core.recovery.watchdog import Watchdog

        watchdog = Watchdog()
        watchdog.monitor("x_bot")  # No restart_func

        result = watchdog.restart_component("x_bot")

        assert result is False

    def test_restart_component_unknown(self):
        """restart_component should return False for unknown component."""
        from core.recovery.watchdog import Watchdog

        watchdog = Watchdog()

        result = watchdog.restart_component("unknown")

        assert result is False

    def test_restart_component_handles_exception(self):
        """restart_component should handle exceptions gracefully."""
        from core.recovery.watchdog import Watchdog

        watchdog = Watchdog()
        restart_func = Mock(side_effect=RuntimeError("Restart failed"))

        watchdog.monitor("x_bot", restart_func=restart_func)

        result = watchdog.restart_component("x_bot")

        assert result is False

    def test_get_status_all_components(self):
        """get_status should return status of all monitored components."""
        from core.recovery.watchdog import Watchdog

        watchdog = Watchdog()
        watchdog.monitor("x_bot", timeout=30)
        watchdog.monitor("trading", timeout=60)
        watchdog.heartbeat("x_bot")
        watchdog.heartbeat("trading")

        status = watchdog.get_status()

        assert "x_bot" in status
        assert "trading" in status
        assert "healthy" in status["x_bot"]
        assert "timeout" in status["x_bot"]

    def test_get_status_single_component(self):
        """get_status with component name should return single status."""
        from core.recovery.watchdog import Watchdog

        watchdog = Watchdog()
        watchdog.monitor("x_bot", timeout=30)
        watchdog.heartbeat("x_bot")

        status = watchdog.get_status("x_bot")

        assert status is not None
        assert "healthy" in status
        assert "last_seen" in status


class TestWatchdogAsync:
    """Async tests for Watchdog."""

    @pytest.mark.asyncio
    async def test_start_monitoring_loop(self):
        """start should begin the monitoring loop."""
        from core.recovery.watchdog import Watchdog

        watchdog = Watchdog(check_interval=0.01)
        watchdog.monitor("x_bot", timeout=1)

        # Start monitoring in background
        task = asyncio.create_task(watchdog.start())

        # Let it run briefly
        await asyncio.sleep(0.05)

        # Stop monitoring
        await watchdog.stop()
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_monitoring_detects_timeout(self):
        """Monitoring loop should detect component timeouts."""
        from core.recovery.watchdog import Watchdog

        watchdog = Watchdog(check_interval=0.01, default_timeout=0.02)
        callback = Mock()

        watchdog.monitor("x_bot", timeout=0.02)
        watchdog.on_timeout("x_bot", callback)
        watchdog.heartbeat("x_bot")

        # Start monitoring
        task = asyncio.create_task(watchdog.start())

        # Wait for timeout detection
        await asyncio.sleep(0.1)

        await watchdog.stop()
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

        # Callback should have been called
        assert callback.called

    @pytest.mark.asyncio
    async def test_async_health_check(self):
        """Watchdog should support async health check functions."""
        from core.recovery.watchdog import Watchdog

        async def async_health_check():
            await asyncio.sleep(0.001)
            return True

        watchdog = Watchdog()
        watchdog.monitor("x_bot", health_check=async_health_check)
        watchdog.heartbeat("x_bot")

        # Run health check
        result = await watchdog.run_health_check("x_bot")

        assert result is True


class TestWatchdogHealthCheckIntegration:
    """Tests for health check integration."""

    def test_health_check_integration_sync(self):
        """Watchdog should integrate with sync health checks."""
        from core.recovery.watchdog import Watchdog

        health_check = Mock(return_value={"status": "healthy", "uptime": 100})

        watchdog = Watchdog()
        watchdog.monitor("x_bot", health_check=health_check)

        # Run sync health check
        result = watchdog.check_health("x_bot")

        health_check.assert_called_once()
        assert result["status"] == "healthy"

    def test_health_check_failure_triggers_restart(self):
        """Failed health check should trigger restart if configured."""
        from core.recovery.watchdog import Watchdog

        health_check = Mock(return_value=False)
        restart_func = Mock(return_value=True)

        watchdog = Watchdog()
        watchdog.monitor(
            "x_bot",
            health_check=health_check,
            restart_func=restart_func,
            auto_restart=True
        )

        # Trigger health check
        watchdog.check_health("x_bot")

        # Should have restarted
        restart_func.assert_called_once()

    def test_health_check_exception_handling(self):
        """Watchdog should handle exceptions in health checks."""
        from core.recovery.watchdog import Watchdog

        health_check = Mock(side_effect=RuntimeError("Health check failed"))

        watchdog = Watchdog()
        watchdog.monitor("x_bot", health_check=health_check)

        # Should not raise
        result = watchdog.check_health("x_bot")

        # Should indicate unhealthy
        assert result is None or result is False or (isinstance(result, dict) and not result.get("healthy", True))


class TestWatchdogRestartLimits:
    """Tests for restart rate limiting."""

    def test_max_restarts_enforced(self):
        """Watchdog should respect max_restarts limit."""
        from core.recovery.watchdog import Watchdog

        watchdog = Watchdog()
        restart_func = Mock(return_value=True)

        watchdog.monitor("x_bot", restart_func=restart_func, max_restarts=2)

        # First two restarts should succeed
        assert watchdog.restart_component("x_bot") is True
        assert watchdog.restart_component("x_bot") is True

        # Third should fail due to limit
        assert watchdog.restart_component("x_bot") is False

    def test_restart_count_resets_after_cooldown(self):
        """Restart count should reset after cooldown period."""
        from core.recovery.watchdog import Watchdog

        watchdog = Watchdog()
        restart_func = Mock(return_value=True)

        watchdog.monitor(
            "x_bot",
            restart_func=restart_func,
            max_restarts=1,
            restart_cooldown=0.01
        )

        # First restart
        assert watchdog.restart_component("x_bot") is True

        # Second should fail
        assert watchdog.restart_component("x_bot") is False

        # Wait for cooldown
        time.sleep(0.02)

        # Reset and try again
        watchdog.reset_restart_count("x_bot")

        # Should succeed again
        assert watchdog.restart_component("x_bot") is True
