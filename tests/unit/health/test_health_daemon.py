"""
Unit tests for the health daemon script.

Tests cover:
- Daemon initialization
- Periodic health checking
- Alert triggering
- Auto-restart functionality
"""

import asyncio
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_health_monitor():
    """Create mock HealthMonitor."""
    monitor = AsyncMock()
    monitor.check_all = AsyncMock(return_value={})
    monitor.start_monitoring = AsyncMock()
    monitor.stop_monitoring = AsyncMock()
    monitor._running = False
    return monitor


@pytest.fixture
def mock_health_reporter():
    """Create mock HealthReporter."""
    from core.health.reporter import AlertResult

    reporter = AsyncMock()
    reporter.send_alert = AsyncMock(return_value=AlertResult(sent=True, channels=["telegram"]))
    reporter.send_recovery = AsyncMock(return_value=AlertResult(sent=True, channels=["telegram"]))
    return reporter


# =============================================================================
# DAEMON IMPORT TESTS
# =============================================================================

class TestHealthDaemonImport:
    """Tests for daemon module imports."""

    def test_import_health_daemon(self):
        """Test that HealthDaemon can be imported."""
        from scripts.health_daemon import HealthDaemon
        assert HealthDaemon is not None


# =============================================================================
# DAEMON INIT TESTS
# =============================================================================

class TestHealthDaemonInit:
    """Tests for HealthDaemon initialization."""

    def test_init_default(self):
        """Test default initialization."""
        from scripts.health_daemon import HealthDaemon

        daemon = HealthDaemon()
        assert daemon.check_interval == 60
        assert daemon._running is False

    def test_init_with_custom_interval(self):
        """Test initialization with custom interval."""
        from scripts.health_daemon import HealthDaemon

        daemon = HealthDaemon(check_interval=30)
        assert daemon.check_interval == 30

    def test_init_with_auto_restart(self):
        """Test initialization with auto-restart enabled."""
        from scripts.health_daemon import HealthDaemon

        daemon = HealthDaemon(auto_restart=True)
        assert daemon.auto_restart is True

    def test_init_without_auto_restart(self):
        """Test initialization with auto-restart disabled."""
        from scripts.health_daemon import HealthDaemon

        daemon = HealthDaemon(auto_restart=False)
        assert daemon.auto_restart is False


# =============================================================================
# DAEMON RUN TESTS
# =============================================================================

class TestHealthDaemonRun:
    """Tests for daemon running."""

    @pytest.mark.asyncio
    async def test_run_starts_monitoring(self, mock_health_monitor):
        """Test that run starts the health monitor."""
        from scripts.health_daemon import HealthDaemon

        with patch("scripts.health_daemon.HealthMonitor", return_value=mock_health_monitor):
            daemon = HealthDaemon(check_interval=0.05)

            # Start daemon in background
            task = asyncio.create_task(daemon.run())
            await asyncio.sleep(0.1)

            # Stop daemon
            daemon.stop()
            try:
                await asyncio.wait_for(task, timeout=0.5)
            except asyncio.TimeoutError:
                task.cancel()

            mock_health_monitor.start_monitoring.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_checks_periodically(self):
        """Test that daemon runs checks periodically."""
        from scripts.health_daemon import HealthDaemon

        check_count = 0

        async def mock_check_all():
            nonlocal check_count
            check_count += 1
            return {}

        with patch("scripts.health_daemon.HealthMonitor") as mock_cls:
            mock_monitor = AsyncMock()
            mock_monitor.check_all = mock_check_all
            mock_monitor.start_monitoring = AsyncMock()
            mock_monitor.stop_monitoring = AsyncMock()
            mock_cls.return_value = mock_monitor

            daemon = HealthDaemon(check_interval=0.05)

            task = asyncio.create_task(daemon.run())
            await asyncio.sleep(0.2)
            daemon.stop()

            try:
                await asyncio.wait_for(task, timeout=0.5)
            except asyncio.TimeoutError:
                task.cancel()

            assert check_count >= 3

    @pytest.mark.asyncio
    async def test_stop_stops_daemon(self):
        """Test that stop stops the daemon."""
        from scripts.health_daemon import HealthDaemon

        daemon = HealthDaemon(check_interval=0.05)

        with patch("scripts.health_daemon.HealthMonitor") as mock_cls:
            mock_monitor = AsyncMock()
            mock_monitor.check_all = AsyncMock(return_value={})
            mock_monitor.start_monitoring = AsyncMock()
            mock_monitor.stop_monitoring = AsyncMock()
            mock_cls.return_value = mock_monitor

            task = asyncio.create_task(daemon.run())
            await asyncio.sleep(0.1)

            assert daemon._running is True

            daemon.stop()
            await asyncio.sleep(0.1)

            assert daemon._running is False


# =============================================================================
# ALERT TRIGGER TESTS
# =============================================================================

class TestHealthDaemonAlerts:
    """Tests for daemon alert triggering."""

    @pytest.mark.asyncio
    async def test_sends_alert_on_degradation(self, mock_health_reporter):
        """Test that daemon sends alert when status degrades."""
        from scripts.health_daemon import HealthDaemon
        from core.health.monitor import BotStatus
        from core.health.status import HealthStatus

        unhealthy_status = BotStatus(
            name="test_bot",
            status=HealthStatus.UNHEALTHY,
            message="Connection failed",
            latency_ms=0,
        )

        with patch("scripts.health_daemon.HealthMonitor") as mock_monitor_cls:
            with patch("scripts.health_daemon.HealthReporter", return_value=mock_health_reporter):
                mock_monitor = AsyncMock()
                mock_monitor.check_all = AsyncMock(return_value={"test_bot": unhealthy_status})
                mock_monitor.start_monitoring = AsyncMock()
                mock_monitor.stop_monitoring = AsyncMock()
                mock_monitor_cls.return_value = mock_monitor

                daemon = HealthDaemon(check_interval=0.05)

                task = asyncio.create_task(daemon.run())
                await asyncio.sleep(0.15)
                daemon.stop()

                try:
                    await asyncio.wait_for(task, timeout=0.5)
                except asyncio.TimeoutError:
                    task.cancel()

                mock_health_reporter.send_alert.assert_called()

    @pytest.mark.asyncio
    async def test_sends_recovery_on_improvement(self, mock_health_reporter):
        """Test that daemon sends recovery when status improves."""
        from scripts.health_daemon import HealthDaemon
        from core.health.monitor import BotStatus
        from core.health.status import HealthStatus

        call_count = 0

        async def changing_check_all():
            nonlocal call_count
            call_count += 1

            if call_count <= 2:
                # First 2 calls: unhealthy
                return {
                    "test_bot": BotStatus(
                        name="test_bot",
                        status=HealthStatus.UNHEALTHY,
                        message="Connection failed",
                        latency_ms=0,
                    )
                }
            else:
                # Later calls: healthy
                return {
                    "test_bot": BotStatus(
                        name="test_bot",
                        status=HealthStatus.HEALTHY,
                        message="OK",
                        latency_ms=10,
                    )
                }

        with patch("scripts.health_daemon.HealthMonitor") as mock_monitor_cls:
            with patch("scripts.health_daemon.HealthReporter", return_value=mock_health_reporter):
                mock_monitor = AsyncMock()
                mock_monitor.check_all = changing_check_all
                mock_monitor.start_monitoring = AsyncMock()
                mock_monitor.stop_monitoring = AsyncMock()
                mock_monitor_cls.return_value = mock_monitor

                daemon = HealthDaemon(check_interval=0.05)

                task = asyncio.create_task(daemon.run())
                await asyncio.sleep(0.25)
                daemon.stop()

                try:
                    await asyncio.wait_for(task, timeout=0.5)
                except asyncio.TimeoutError:
                    task.cancel()

                mock_health_reporter.send_recovery.assert_called()


# =============================================================================
# AUTO-RESTART TESTS
# =============================================================================

class TestHealthDaemonAutoRestart:
    """Tests for auto-restart functionality."""

    def test_auto_restart_flag_set(self):
        """Test that auto-restart flag is properly set."""
        from scripts.health_daemon import HealthDaemon

        daemon = HealthDaemon(auto_restart=True)
        assert daemon.auto_restart is True

        daemon2 = HealthDaemon(auto_restart=False)
        assert daemon2.auto_restart is False

    @pytest.mark.asyncio
    async def test_restart_bot_method_exists(self):
        """Test that _restart_bot method exists and can be called."""
        from scripts.health_daemon import HealthDaemon

        daemon = HealthDaemon()

        # Should not raise
        await daemon._restart_bot("test_bot")


# =============================================================================
# SIGNAL HANDLING TESTS
# =============================================================================

class TestHealthDaemonSignals:
    """Tests for signal handling."""

    def test_setup_signal_handlers(self):
        """Test that signal handlers are set up."""
        from scripts.health_daemon import HealthDaemon
        import signal

        daemon = HealthDaemon()

        with patch.object(signal, "signal") as mock_signal:
            daemon.setup_signal_handlers()

            # Should register SIGTERM and SIGINT handlers
            calls = mock_signal.call_args_list
            signals_registered = [call[0][0] for call in calls]

            # On Windows, SIGTERM might not be available
            if hasattr(signal, "SIGTERM"):
                assert signal.SIGTERM in signals_registered or len(calls) > 0


# =============================================================================
# CLI ARGUMENT TESTS
# =============================================================================

class TestHealthDaemonCLI:
    """Tests for CLI argument parsing."""

    def test_parse_args_default(self):
        """Test parsing default arguments."""
        from scripts.health_daemon import parse_args

        args = parse_args([])

        assert args.interval == 60
        assert args.auto_restart is False

    def test_parse_args_custom_interval(self):
        """Test parsing custom interval."""
        from scripts.health_daemon import parse_args

        args = parse_args(["--interval", "30"])

        assert args.interval == 30

    def test_parse_args_auto_restart(self):
        """Test parsing auto-restart flag."""
        from scripts.health_daemon import parse_args

        args = parse_args(["--auto-restart"])

        assert args.auto_restart is True

    def test_parse_args_verbose(self):
        """Test parsing verbose flag."""
        from scripts.health_daemon import parse_args

        args = parse_args(["-v"])

        assert args.verbose is True
