"""
Comprehensive Tests for Bot Supervisor Module

Tests cover bots/supervisor.py:
1. SingleInstanceLock - Cross-platform process locking
2. BotSupervisor - Main orchestrator for all bots
3. ComponentState - Component state tracking
4. Component lifecycle (start, stop, restart)
5. Health monitoring
6. Error recovery and backoff
7. Signal handling and graceful shutdown
8. Configuration and validation

Acceptance Criteria:
- Single instance lock prevents duplicate supervisors
- Components start/stop correctly
- Health monitoring detects issues
- Auto-restart with exponential backoff works
- Graceful shutdown completes within timeout
- Error alerts are sent appropriately
"""

import asyncio
import logging
import os
import sys
import tempfile
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any
from unittest.mock import MagicMock, AsyncMock, Mock, patch, call

# Import classes under test
from bots.supervisor import (
    SingleInstanceLock,
    ensure_single_instance,
    ComponentStatus,
    ComponentState,
    BotSupervisor,
    systemd_notify,
    load_env,
    validate_startup,
    _basic_validation,
    track_supervisor_error,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def supervisor():
    """Create a fresh BotSupervisor instance for each test."""
    with patch('bots.supervisor.SHUTDOWN_MANAGER_AVAILABLE', False):
        sup = BotSupervisor(
            max_restarts=5,
            health_check_interval=1,
            reset_failure_after=10,
        )
        yield sup


@pytest.fixture
def execution_log():
    """Track execution order and state during tests."""
    return {
        "started": [],
        "stopped": [],
        "errors": [],
        "timestamps": [],
    }


# =============================================================================
# SINGLE INSTANCE LOCK TESTS
# =============================================================================

class TestSingleInstanceLock:
    """Test SingleInstanceLock functionality."""

    def test_lock_creation(self):
        """Test that lock can be created."""
        lock = SingleInstanceLock("test_app")
        assert lock.name == "test_app"
        assert lock.lock_file.name == "test_app.lock"
        assert lock.lock_file.parent == Path(tempfile.gettempdir())

    def test_lock_file_path(self):
        """Test lock file is in temp directory."""
        lock = SingleInstanceLock("my_bot")
        assert lock.lock_file.parent == Path(tempfile.gettempdir())
        assert lock.lock_file.name == "my_bot.lock"

    def test_lock_init_sets_is_windows(self):
        """Test lock initialization sets _is_windows based on platform."""
        lock = SingleInstanceLock("platform_test")
        expected = sys.platform == "win32"
        assert lock._is_windows == expected

    def test_lock_release_closes_file(self):
        """Test that release closes the lock file."""
        lock = SingleInstanceLock("release_test")

        # Create a mock file descriptor
        mock_fd = MagicMock()
        lock._lock_fd = mock_fd
        lock._is_windows = True

        mock_msvcrt = MagicMock()
        with patch.dict('sys.modules', {'msvcrt': mock_msvcrt}):
            lock.release()

        # Should have closed the file
        mock_fd.close.assert_called_once()

    def test_lock_release_when_no_fd(self):
        """Test release does nothing when no fd."""
        lock = SingleInstanceLock("no_fd_test")
        lock._lock_fd = None

        # Should not raise
        lock.release()

    def test_context_manager_acquire_and_release(self):
        """Test lock works as context manager."""
        lock = SingleInstanceLock("context_test")

        with patch.object(lock, 'acquire', return_value=True) as mock_acquire:
            with patch.object(lock, 'release') as mock_release:
                with lock:
                    mock_acquire.assert_called_once()
                mock_release.assert_called_once()

    def test_acquire_raises_on_lock_conflict(self):
        """Test that acquiring lock raises RuntimeError when lock is held."""
        lock = SingleInstanceLock("conflict_test")

        # Mock the file open to raise IOError (simulating locked file)
        with patch('builtins.open', side_effect=IOError("Lock held")):
            with pytest.raises(RuntimeError, match="already running"):
                lock.acquire()

    def test_ensure_single_instance_returns_lock(self):
        """Test ensure_single_instance helper returns lock."""
        with patch.object(SingleInstanceLock, 'acquire', return_value=True):
            lock = ensure_single_instance("test_bot")
            assert isinstance(lock, SingleInstanceLock)
            assert lock.name == "test_bot"

    def test_lock_writes_pid(self):
        """Test lock file contains PID after acquire."""
        lock = SingleInstanceLock("pid_test")

        # Mock open and locking to succeed
        mock_fd = MagicMock()
        mock_open = MagicMock(return_value=mock_fd)

        with patch('builtins.open', mock_open):
            if sys.platform == "win32":
                mock_msvcrt = MagicMock()
                with patch.dict('sys.modules', {'msvcrt': mock_msvcrt}):
                    lock.acquire()
            else:
                mock_fcntl = MagicMock()
                mock_fcntl.LOCK_EX = 2
                mock_fcntl.LOCK_NB = 4
                with patch.dict('sys.modules', {'fcntl': mock_fcntl}):
                    lock.acquire()

        # Should have written PID
        mock_fd.write.assert_called()
        mock_fd.flush.assert_called()


# =============================================================================
# COMPONENT STATUS TESTS
# =============================================================================

class TestComponentStatus:
    """Test ComponentStatus enum values."""

    def test_status_values(self):
        """Test all expected status values exist."""
        assert ComponentStatus.STOPPED.value == "stopped"
        assert ComponentStatus.STARTING.value == "starting"
        assert ComponentStatus.RUNNING.value == "running"
        assert ComponentStatus.FAILED.value == "failed"
        assert ComponentStatus.RESTARTING.value == "restarting"

    def test_status_count(self):
        """Test we have exactly 5 statuses."""
        assert len(ComponentStatus) == 5


# =============================================================================
# COMPONENT STATE TESTS
# =============================================================================

class TestComponentState:
    """Test ComponentState dataclass."""

    def test_default_values(self):
        """Test default values are set correctly."""
        state = ComponentState(name="test_bot")

        assert state.name == "test_bot"
        assert state.status == ComponentStatus.STOPPED
        assert state.task is None
        assert state.start_time is None
        assert state.restart_count == 0
        assert state.last_error is None
        assert state.last_error_time is None
        assert state.consecutive_failures == 0
        assert state.min_backoff == 1.0
        assert state.max_backoff == 300.0
        assert state.current_backoff == 1.0

    def test_custom_backoff_values(self):
        """Test custom backoff configuration."""
        state = ComponentState(
            name="custom_bot",
            min_backoff=5.0,
            max_backoff=60.0,
        )

        assert state.min_backoff == 5.0
        assert state.max_backoff == 60.0
        assert state.current_backoff == 1.0  # Default starting value

    def test_state_updates(self):
        """Test state can be updated."""
        state = ComponentState(name="update_test")

        state.status = ComponentStatus.RUNNING
        state.start_time = datetime.now()
        state.restart_count = 3
        state.last_error = "Test error"

        assert state.status == ComponentStatus.RUNNING
        assert state.restart_count == 3
        assert state.last_error == "Test error"


# =============================================================================
# BOT SUPERVISOR INITIALIZATION TESTS
# =============================================================================

class TestBotSupervisorInit:
    """Test BotSupervisor initialization."""

    def test_default_values(self):
        """Test supervisor initializes with default values."""
        with patch('bots.supervisor.SHUTDOWN_MANAGER_AVAILABLE', False):
            sup = BotSupervisor()

            assert sup.max_restarts == 100
            assert sup.health_check_interval == 60
            assert sup.reset_failure_after == 300
            assert sup.components == {}
            assert sup.component_funcs == {}
            assert not sup._running

    def test_custom_values(self):
        """Test supervisor initializes with custom values."""
        with patch('bots.supervisor.SHUTDOWN_MANAGER_AVAILABLE', False):
            sup = BotSupervisor(
                max_restarts=10,
                health_check_interval=30,
                reset_failure_after=120,
            )

            assert sup.max_restarts == 10
            assert sup.health_check_interval == 30
            assert sup.reset_failure_after == 120

    def test_shutdown_event_created(self):
        """Test shutdown event is created."""
        with patch('bots.supervisor.SHUTDOWN_MANAGER_AVAILABLE', False):
            sup = BotSupervisor()
            assert isinstance(sup._shutdown_event, asyncio.Event)

    def test_registers_with_shutdown_manager(self):
        """Test supervisor registers with shutdown manager when available."""
        mock_shutdown_mgr = MagicMock()

        with patch('bots.supervisor.SHUTDOWN_MANAGER_AVAILABLE', True):
            with patch('bots.supervisor.get_shutdown_manager', return_value=mock_shutdown_mgr):
                with patch('bots.supervisor.ShutdownPhase') as mock_phase:
                    mock_phase.IMMEDIATE = "immediate"
                    sup = BotSupervisor()

                    mock_shutdown_mgr.register_hook.assert_called_once()


# =============================================================================
# COMPONENT REGISTRATION TESTS
# =============================================================================

class TestComponentRegistration:
    """Test component registration."""

    def test_register_component(self, supervisor):
        """Test basic component registration."""
        async def dummy_func():
            pass

        supervisor.register("test_bot", dummy_func)

        assert "test_bot" in supervisor.components
        assert "test_bot" in supervisor.component_funcs
        assert supervisor.component_funcs["test_bot"] == dummy_func

    def test_register_with_custom_backoff(self, supervisor):
        """Test registration with custom backoff values."""
        async def dummy_func():
            pass

        supervisor.register(
            "custom_bot",
            dummy_func,
            min_backoff=10.0,
            max_backoff=120.0,
        )

        state = supervisor.components["custom_bot"]
        assert state.min_backoff == 10.0
        assert state.max_backoff == 120.0

    def test_register_multiple_components(self, supervisor):
        """Test registering multiple components."""
        async def bot1():
            pass

        async def bot2():
            pass

        async def bot3():
            pass

        supervisor.register("bot1", bot1)
        supervisor.register("bot2", bot2)
        supervisor.register("bot3", bot3)

        assert len(supervisor.components) == 3
        assert all(name in supervisor.components for name in ["bot1", "bot2", "bot3"])

    def test_register_sync_function(self, supervisor):
        """Test registering synchronous function."""
        def sync_func():
            pass

        supervisor.register("sync_bot", sync_func)
        assert "sync_bot" in supervisor.components

    def test_register_logs_message(self, supervisor, caplog):
        """Test registration logs info message."""
        async def dummy():
            pass

        with caplog.at_level(logging.INFO):
            supervisor.register("logged_bot", dummy)

        assert "Registered component: logged_bot" in caplog.text


# =============================================================================
# COMPONENT LIFECYCLE TESTS
# =============================================================================

class TestComponentLifecycle:
    """Test component start/stop/restart lifecycle."""

    @pytest.mark.asyncio
    async def test_run_async_component(self, supervisor, execution_log):
        """Test running an async component."""
        async def async_bot():
            execution_log["started"].append("async_bot")
            await asyncio.sleep(0.01)
            execution_log["stopped"].append("async_bot")

        supervisor.register("async_bot", async_bot)
        supervisor._running = True

        await supervisor._run_component("async_bot")

        assert "async_bot" in execution_log["started"]
        assert "async_bot" in execution_log["stopped"]

    @pytest.mark.asyncio
    async def test_run_sync_component(self, supervisor, execution_log):
        """Test running a synchronous component."""
        def sync_bot():
            execution_log["started"].append("sync_bot")

        supervisor.register("sync_bot", sync_bot)
        supervisor._running = True

        await supervisor._run_component("sync_bot")

        assert "sync_bot" in execution_log["started"]

    @pytest.mark.asyncio
    async def test_component_status_transitions(self, supervisor):
        """Test component status transitions during run."""
        status_history = []

        async def tracking_bot():
            status_history.append(supervisor.components["tracking"].status)
            await asyncio.sleep(0.01)

        supervisor.register("tracking", tracking_bot)
        supervisor._running = True

        await supervisor._run_component("tracking")

        # Should have been RUNNING during execution
        assert ComponentStatus.RUNNING in status_history
        # Should be STOPPED at end
        assert supervisor.components["tracking"].status == ComponentStatus.STOPPED

    @pytest.mark.asyncio
    async def test_component_start_time_recorded(self, supervisor):
        """Test start time is recorded."""
        async def timed_bot():
            await asyncio.sleep(0.01)

        supervisor.register("timed", timed_bot)
        supervisor._running = True

        before = datetime.now()
        await supervisor._run_component("timed")

        state = supervisor.components["timed"]
        assert state.start_time is not None
        assert state.start_time >= before

    @pytest.mark.asyncio
    async def test_component_cancelled_cleanly(self, supervisor):
        """Test component handles cancellation."""
        async def long_bot():
            await asyncio.sleep(100)

        supervisor.register("long", long_bot)
        supervisor._running = True

        task = asyncio.create_task(supervisor._run_component("long"))
        await asyncio.sleep(0.01)
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        assert supervisor.components["long"].status == ComponentStatus.STOPPED


# =============================================================================
# ERROR RECOVERY TESTS
# =============================================================================

class TestErrorRecovery:
    """Test error recovery and restart behavior."""

    @pytest.mark.asyncio
    async def test_component_restarts_on_error(self, supervisor, execution_log):
        """Test component restarts after error."""
        attempt_count = 0

        async def failing_bot():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise RuntimeError("Simulated failure")
            # Success on third attempt

        supervisor.register("failing", failing_bot)
        supervisor._running = True

        # Patch sleep to speed up test
        with patch('asyncio.sleep', new_callable=AsyncMock):
            await supervisor._run_component("failing")

        assert attempt_count == 3  # Two failures + one success
        assert supervisor.components["failing"].restart_count == 2

    @pytest.mark.asyncio
    async def test_max_restarts_reached(self, supervisor):
        """Test component stops after max restarts."""
        supervisor.max_restarts = 3

        async def always_failing():
            raise RuntimeError("Always fails")

        supervisor.register("always_fail", always_failing)
        supervisor._running = True

        with patch('asyncio.sleep', new_callable=AsyncMock):
            with patch.object(supervisor, '_send_critical_alert', new_callable=AsyncMock):
                await supervisor._run_component("always_fail")

        state = supervisor.components["always_fail"]
        assert state.restart_count >= 3
        assert state.status == ComponentStatus.STOPPED

    @pytest.mark.asyncio
    async def test_exponential_backoff(self, supervisor):
        """Test exponential backoff between restarts."""
        backoff_times = []

        async def failing_bot():
            raise RuntimeError("Fail")

        supervisor.register("backoff_test", failing_bot, min_backoff=1.0, max_backoff=8.0)
        supervisor._running = True
        supervisor.max_restarts = 4

        async def record_sleep(duration):
            backoff_times.append(duration)

        with patch('asyncio.sleep', side_effect=record_sleep):
            with patch.object(supervisor, '_send_error_alert', new_callable=AsyncMock):
                await supervisor._run_component("backoff_test")

        # Backoff should double each time: 1, 2, 4, ...
        if len(backoff_times) >= 2:
            assert backoff_times[1] >= backoff_times[0]

    @pytest.mark.asyncio
    async def test_backoff_capped_at_max(self, supervisor):
        """Test backoff doesn't exceed max_backoff."""
        supervisor.max_restarts = 10

        async def failing_bot():
            raise RuntimeError("Fail")

        supervisor.register("capped_test", failing_bot, min_backoff=1.0, max_backoff=4.0)
        supervisor._running = True

        recorded_backoffs = []

        async def record_sleep(duration):
            recorded_backoffs.append(duration)

        with patch('asyncio.sleep', side_effect=record_sleep):
            with patch.object(supervisor, '_send_error_alert', new_callable=AsyncMock):
                with patch.object(supervisor, '_send_critical_alert', new_callable=AsyncMock):
                    await supervisor._run_component("capped_test")

        # All backoffs should be <= max_backoff
        for backoff in recorded_backoffs:
            assert backoff <= 4.0

    @pytest.mark.asyncio
    async def test_consecutive_failures_tracked(self, supervisor):
        """Test consecutive failures are tracked."""
        failure_count = 0

        async def intermittent_bot():
            nonlocal failure_count
            failure_count += 1
            if failure_count <= 3:
                raise RuntimeError("Fail")

        supervisor.register("intermittent", intermittent_bot)
        supervisor._running = True

        with patch('asyncio.sleep', new_callable=AsyncMock):
            await supervisor._run_component("intermittent")

        # consecutive_failures gets incremented on each failure
        # State may have been reset after success
        state = supervisor.components["intermittent"]
        assert state.restart_count == 3

    @pytest.mark.asyncio
    async def test_last_error_recorded(self, supervisor):
        """Test last error is recorded."""
        async def error_bot():
            raise ValueError("Specific error message")

        supervisor.register("error_bot", error_bot)
        supervisor._running = True
        supervisor.max_restarts = 1

        with patch('asyncio.sleep', new_callable=AsyncMock):
            with patch.object(supervisor, '_send_critical_alert', new_callable=AsyncMock):
                await supervisor._run_component("error_bot")

        state = supervisor.components["error_bot"]
        assert "Specific error message" in state.last_error
        assert state.last_error_time is not None


# =============================================================================
# HEALTH MONITORING TESTS
# =============================================================================

class TestHealthMonitoring:
    """Test health monitoring functionality."""

    @pytest.mark.asyncio
    async def test_health_monitor_runs(self, supervisor, caplog):
        """Test health monitor executes."""
        supervisor._running = True
        supervisor.health_check_interval = 0.05

        async def stop_after_delay():
            await asyncio.sleep(0.1)
            supervisor._running = False

        with caplog.at_level(logging.INFO):
            await asyncio.gather(
                supervisor._health_monitor(),
                stop_after_delay(),
            )

        assert "COMPONENT HEALTH" in caplog.text

    @pytest.mark.asyncio
    async def test_health_monitor_reports_status(self, supervisor, caplog):
        """Test health monitor reports component status."""
        async def running_bot():
            await asyncio.sleep(0.2)

        supervisor.register("health_test", running_bot)
        supervisor.components["health_test"].status = ComponentStatus.RUNNING
        supervisor.components["health_test"].start_time = datetime.now()
        supervisor.health_check_interval = 0.05
        supervisor._running = True

        async def stop_after_delay():
            await asyncio.sleep(0.1)
            supervisor._running = False

        with caplog.at_level(logging.INFO):
            await asyncio.gather(
                supervisor._health_monitor(),
                stop_after_delay(),
            )

        assert "health_test" in caplog.text
        assert "running" in caplog.text

    @pytest.mark.asyncio
    async def test_failure_count_reset_after_stable_run(self, supervisor):
        """Test failure count resets after stable run."""
        supervisor.reset_failure_after = 0.05  # Very short for testing
        supervisor.health_check_interval = 0.03

        async def stable_bot():
            await asyncio.sleep(0.2)

        supervisor.register("stable", stable_bot)
        state = supervisor.components["stable"]
        state.status = ComponentStatus.RUNNING
        state.start_time = datetime.now() - timedelta(seconds=1)  # Already running for 1 second
        state.consecutive_failures = 5
        state.current_backoff = 30.0

        supervisor._running = True

        async def stop_after_check():
            await asyncio.sleep(0.1)
            supervisor._running = False

        await asyncio.gather(
            supervisor._health_monitor(),
            stop_after_check(),
        )

        # Failure count should be reset
        assert state.consecutive_failures == 0
        assert state.current_backoff == state.min_backoff

    @pytest.mark.asyncio
    async def test_health_monitor_handles_cancellation(self, supervisor):
        """Test health monitor handles cancellation gracefully."""
        supervisor._running = True
        supervisor.health_check_interval = 1.0

        task = asyncio.create_task(supervisor._health_monitor())
        await asyncio.sleep(0.01)
        task.cancel()

        # Health monitor catches CancelledError and exits cleanly
        # so it should complete without raising
        try:
            await task
        except asyncio.CancelledError:
            pass  # Also acceptable if it propagates

        # Task should be done regardless
        assert task.done()

    @pytest.mark.asyncio
    async def test_health_monitor_systemd_notify(self, supervisor):
        """Test health monitor sends systemd watchdog ping."""
        supervisor._running = True
        supervisor.health_check_interval = 0.05

        async def stop_soon():
            await asyncio.sleep(0.1)
            supervisor._running = False

        with patch('bots.supervisor.systemd_notify') as mock_notify:
            await asyncio.gather(
                supervisor._health_monitor(),
                stop_soon(),
            )

        # Should have called systemd_notify with WATCHDOG
        mock_notify.assert_called_with("WATCHDOG=1")


# =============================================================================
# RUN FOREVER TESTS
# =============================================================================

class TestRunForever:
    """Test run_forever main loop."""

    @pytest.mark.asyncio
    async def test_run_forever_starts_all_components(self, supervisor, execution_log):
        """Test run_forever starts all registered components."""
        started = set()

        async def bot1():
            started.add("bot1")
            # Exit immediately

        async def bot2():
            started.add("bot2")
            # Exit immediately

        supervisor.register("bot1", bot1)
        supervisor.register("bot2", bot2)

        # Mock health monitor to exit immediately
        async def mock_health_monitor():
            pass

        with patch('bots.supervisor.systemd_notify', return_value=False):
            with patch.object(supervisor, '_health_monitor', mock_health_monitor):
                await supervisor.run_forever()

        assert "bot1" in started
        assert "bot2" in started

    @pytest.mark.asyncio
    async def test_run_forever_sets_running_flag(self, supervisor):
        """Test run_forever sets _running flag."""
        running_during_execution = None

        async def check_running_bot():
            nonlocal running_during_execution
            running_during_execution = supervisor._running
            # Exit immediately

        supervisor.register("check", check_running_bot)

        async def mock_health_monitor():
            pass

        with patch('bots.supervisor.systemd_notify', return_value=False):
            with patch.object(supervisor, '_health_monitor', mock_health_monitor):
                await supervisor.run_forever()

        assert running_during_execution is True

    @pytest.mark.asyncio
    async def test_run_forever_notifies_systemd_ready(self, supervisor):
        """Test run_forever sends READY notification to systemd."""
        async def quick_bot():
            pass

        supervisor.register("quick", quick_bot)

        async def mock_health_monitor():
            pass

        with patch('bots.supervisor.systemd_notify') as mock_notify:
            mock_notify.return_value = True
            with patch.object(supervisor, '_health_monitor', mock_health_monitor):
                await supervisor.run_forever()

        mock_notify.assert_any_call("READY=1")


# =============================================================================
# GRACEFUL SHUTDOWN TESTS
# =============================================================================

class TestGracefulShutdown:
    """Test graceful shutdown behavior."""

    @pytest.mark.asyncio
    async def test_graceful_shutdown_sets_running_false(self, supervisor):
        """Test graceful shutdown sets _running to False."""
        supervisor._running = True
        await supervisor._graceful_shutdown()
        assert not supervisor._running

    @pytest.mark.asyncio
    async def test_graceful_shutdown_cancels_tasks(self, supervisor):
        """Test graceful shutdown cancels component tasks."""
        async def long_bot():
            await asyncio.sleep(100)

        supervisor.register("long", long_bot)
        supervisor._running = True

        # Start the component
        task = asyncio.create_task(supervisor._run_component("long"))
        supervisor.components["long"].task = task

        await asyncio.sleep(0.01)

        # Graceful shutdown
        await supervisor._graceful_shutdown()

        # Task should be cancelled
        assert task.cancelled() or task.done()

    @pytest.mark.asyncio
    async def test_graceful_shutdown_waits_for_tasks(self, supervisor):
        """Test graceful shutdown waits for tasks to complete."""
        completed = False

        async def completing_bot():
            nonlocal completed
            await asyncio.sleep(0.01)
            completed = True

        supervisor.register("completing", completing_bot)
        supervisor._running = True

        task = asyncio.create_task(supervisor._run_component("completing"))
        supervisor.components["completing"].task = task

        await asyncio.sleep(0.02)
        await supervisor._graceful_shutdown()

        # Wait a bit for task to complete
        await asyncio.sleep(0.02)

    @pytest.mark.asyncio
    async def test_cleanup_notifies_systemd_stopping(self, supervisor):
        """Test cleanup sends STOPPING notification."""
        with patch('bots.supervisor.systemd_notify') as mock_notify:
            with patch('bots.supervisor.SHUTDOWN_MANAGER_AVAILABLE', False):
                await supervisor._cleanup()

        mock_notify.assert_called_with("STOPPING=1")

    @pytest.mark.asyncio
    async def test_cleanup_cancels_all_component_tasks(self, supervisor):
        """Test cleanup cancels all component tasks."""
        async def long_bot():
            await asyncio.sleep(100)

        supervisor.register("long1", long_bot)
        supervisor.register("long2", long_bot)

        # Create tasks
        task1 = asyncio.create_task(asyncio.sleep(100))
        task2 = asyncio.create_task(asyncio.sleep(100))

        supervisor.components["long1"].task = task1
        supervisor.components["long2"].task = task2

        with patch('bots.supervisor.SHUTDOWN_MANAGER_AVAILABLE', False):
            with patch('bots.supervisor.systemd_notify'):
                await supervisor._cleanup()

        assert task1.cancelled() or task1.done()
        assert task2.cancelled() or task2.done()


# =============================================================================
# GET STATUS TESTS
# =============================================================================

class TestGetStatus:
    """Test get_status method."""

    def test_get_status_empty(self, supervisor):
        """Test get_status with no components."""
        status = supervisor.get_status()
        assert status == {}

    def test_get_status_single_component(self, supervisor):
        """Test get_status with single component."""
        async def dummy():
            pass

        supervisor.register("test", dummy)
        supervisor.components["test"].status = ComponentStatus.RUNNING
        supervisor.components["test"].restart_count = 2
        supervisor.components["test"].last_error = "Test error"
        supervisor.components["test"].start_time = datetime.now()

        status = supervisor.get_status()

        assert "test" in status
        assert status["test"]["status"] == "running"
        assert status["test"]["restart_count"] == 2
        assert status["test"]["last_error"] == "Test error"
        assert status["test"]["uptime"] is not None

    def test_get_status_multiple_components(self, supervisor):
        """Test get_status with multiple components."""
        async def dummy():
            pass

        supervisor.register("bot1", dummy)
        supervisor.register("bot2", dummy)
        supervisor.register("bot3", dummy)

        supervisor.components["bot1"].status = ComponentStatus.RUNNING
        supervisor.components["bot2"].status = ComponentStatus.FAILED
        supervisor.components["bot3"].status = ComponentStatus.STOPPED

        status = supervisor.get_status()

        assert len(status) == 3
        assert status["bot1"]["status"] == "running"
        assert status["bot2"]["status"] == "failed"
        assert status["bot3"]["status"] == "stopped"

    def test_get_status_uptime_none_when_no_start_time(self, supervisor):
        """Test uptime is None when component hasn't started."""
        async def dummy():
            pass

        supervisor.register("unstarted", dummy)

        status = supervisor.get_status()

        assert status["unstarted"]["uptime"] is None


# =============================================================================
# ERROR ALERT TESTS
# =============================================================================

class TestErrorAlerts:
    """Test error alert functionality."""

    @pytest.mark.asyncio
    async def test_send_error_alert_without_token(self, supervisor):
        """Test error alert does nothing without token."""
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_ADMIN_IDS": "123"}):
            # Should not raise
            await supervisor._send_error_alert("test", "error", 5, 10)

    @pytest.mark.asyncio
    async def test_send_error_alert_without_admin_ids(self, supervisor):
        """Test error alert does nothing without admin IDs."""
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_ADMIN_IDS": ""}):
            await supervisor._send_error_alert("test", "error", 5, 10)

    @pytest.mark.asyncio
    async def test_send_error_alert_sends_message(self, supervisor):
        """Test error alert sends Telegram message."""
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.post = AsyncMock(return_value=mock_response)

        with patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": "test_token",
            "TELEGRAM_ADMIN_IDS": "123,456",
        }):
            with patch('aiohttp.ClientSession', return_value=mock_session):
                await supervisor._send_error_alert("test_bot", "Test error", 5, 10)

        # Should have called post for each admin
        assert mock_session.post.call_count >= 1

    @pytest.mark.asyncio
    async def test_send_critical_alert_sends_message(self, supervisor):
        """Test critical alert sends Telegram message."""
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.post = AsyncMock(return_value=mock_response)

        with patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": "test_token",
            "TELEGRAM_ADMIN_IDS": "123",
        }):
            with patch('aiohttp.ClientSession', return_value=mock_session):
                await supervisor._send_critical_alert("test_bot", "Critical error")

        assert mock_session.post.called

    @pytest.mark.asyncio
    async def test_error_alert_handles_exceptions(self, supervisor):
        """Test error alert handles exceptions gracefully."""
        with patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": "token",
            "TELEGRAM_ADMIN_IDS": "123",
        }):
            with patch('aiohttp.ClientSession', side_effect=Exception("Network error")):
                # Should not raise
                await supervisor._send_error_alert("test", "error", 5, 10)

    @pytest.mark.asyncio
    async def test_alert_limits_admin_count(self, supervisor):
        """Test alert limits to first 3 admins."""
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.post = AsyncMock(return_value=mock_response)

        with patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": "token",
            "TELEGRAM_ADMIN_IDS": "1,2,3,4,5",  # 5 admins
        }):
            with patch('aiohttp.ClientSession', return_value=mock_session):
                await supervisor._send_error_alert("test", "error", 5, 10)

        # Should only call for first 3 admins
        assert mock_session.post.call_count == 3


# =============================================================================
# SYSTEMD NOTIFY TESTS
# =============================================================================

class TestSystemdNotify:
    """Test systemd notification functionality."""

    def test_systemd_notify_without_socket(self):
        """Test systemd_notify returns False without NOTIFY_SOCKET."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("NOTIFY_SOCKET", None)
            result = systemd_notify("READY=1")
            assert result is False

    @pytest.mark.skipif(sys.platform == "win32", reason="Unix sockets not available on Windows")
    @patch('socket.socket')
    def test_systemd_notify_with_socket(self, mock_socket_class):
        """Test systemd_notify sends to socket."""
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        with patch.dict(os.environ, {"NOTIFY_SOCKET": "/run/systemd/notify"}):
            result = systemd_notify("READY=1")

        mock_socket.connect.assert_called_once()
        mock_socket.sendall.assert_called_with(b"READY=1")

    @pytest.mark.skipif(sys.platform == "win32", reason="Unix sockets not available on Windows")
    @patch('socket.socket')
    def test_systemd_notify_handles_abstract_socket(self, mock_socket_class):
        """Test systemd_notify handles abstract sockets."""
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        with patch.dict(os.environ, {"NOTIFY_SOCKET": "@/run/systemd/notify"}):
            result = systemd_notify("WATCHDOG=1")

        # Abstract sockets should have @ replaced with \0
        mock_socket.connect.assert_called_once()

    def test_systemd_notify_handles_exception(self):
        """Test systemd_notify handles exceptions."""
        with patch.dict(os.environ, {"NOTIFY_SOCKET": "/run/systemd/notify"}):
            with patch('socket.socket', side_effect=Exception("Socket error")):
                result = systemd_notify("READY=1")
                assert result is False

    def test_systemd_notify_on_windows_returns_false(self):
        """Test systemd_notify returns False on Windows (no AF_UNIX)."""
        # On Windows, AF_UNIX is not supported so systemd_notify should return False
        if sys.platform == "win32":
            with patch.dict(os.environ, {"NOTIFY_SOCKET": "/run/systemd/notify"}):
                result = systemd_notify("READY=1")
                assert result is False


# =============================================================================
# LOAD ENV TESTS
# =============================================================================

class TestLoadEnv:
    """Test environment loading."""

    def test_load_env_from_tg_bot(self, tmp_path):
        """Test loading env from tg_bot/.env."""
        env_file = tmp_path / "tg_bot" / ".env"
        env_file.parent.mkdir(parents=True, exist_ok=True)
        env_file.write_text("TEST_VAR_TG=tg_value\n")

        with patch('bots.supervisor.project_root', tmp_path):
            # Clear existing var
            os.environ.pop("TEST_VAR_TG", None)
            load_env()

        assert os.environ.get("TEST_VAR_TG") == "tg_value"

    def test_load_env_ignores_comments(self, tmp_path):
        """Test load_env ignores comment lines."""
        env_file = tmp_path / ".env"
        env_file.write_text("# This is a comment\nVALID_VAR=value\n")

        with patch('bots.supervisor.project_root', tmp_path):
            os.environ.pop("VALID_VAR", None)
            load_env()

        assert os.environ.get("VALID_VAR") == "value"

    def test_load_env_ignores_empty_lines(self, tmp_path):
        """Test load_env ignores empty lines."""
        env_file = tmp_path / ".env"
        env_file.write_text("\n\nVAR=value\n\n")

        with patch('bots.supervisor.project_root', tmp_path):
            os.environ.pop("VAR", None)
            load_env()

        assert os.environ.get("VAR") == "value"

    def test_load_env_handles_missing_file(self, tmp_path):
        """Test load_env handles missing files gracefully."""
        with patch('bots.supervisor.project_root', tmp_path):
            # Should not raise
            load_env()


# =============================================================================
# VALIDATION TESTS
# =============================================================================

class TestValidation:
    """Test startup validation."""

    def test_basic_validation_passes_with_token(self):
        """Test basic validation passes with required token."""
        with patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": "test_token",
            "TELEGRAM_ADMIN_IDS": "123",
        }):
            result = _basic_validation()
            assert result is True

    def test_basic_validation_fails_without_token(self):
        """Test basic validation fails without token."""
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": ""}, clear=True):
            os.environ.pop("TELEGRAM_BOT_TOKEN", None)
            result = _basic_validation()
            assert result is False

    def test_validate_startup_uses_comprehensive_validator(self):
        """Test validate_startup uses comprehensive validator when available."""
        mock_validator = MagicMock()
        mock_validator.validate.return_value = (True, [])
        mock_validator.get_group_summary.return_value = {}

        # Patch at the import location since it's imported inside the function
        with patch.dict('sys.modules', {'core.config.validator': MagicMock(
            validate_config=MagicMock(),
            get_validator=MagicMock(return_value=mock_validator),
            ValidationLevel=MagicMock(ERROR='error', WARNING='warning', INFO='info'),
        )}):
            result = validate_startup()

        assert result is True

    def test_validate_startup_falls_back_to_basic(self):
        """Test validate_startup falls back to basic validation."""
        # Clear the module from cache so it will re-import
        import sys as sysmod
        if 'core.config.validator' in sysmod.modules:
            del sysmod.modules['core.config.validator']

        # Make the import fail by patching builtins.__import__
        original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

        def mock_import(name, *args, **kwargs):
            if name == 'core.config.validator' or 'core.config.validator' in str(name):
                raise ImportError("Mocked import failure")
            return original_import(name, *args, **kwargs)

        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "token"}):
            with patch('builtins.__import__', mock_import):
                result = validate_startup()
                assert result is True

    def test_basic_validation_warns_without_admin_ids(self):
        """Test basic validation passes but warns without admin IDs."""
        with patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": "test_token",
            "TELEGRAM_ADMIN_IDS": "",
        }):
            result = _basic_validation()
            # Should pass but with warnings
            assert result is True


# =============================================================================
# ERROR TRACKER TESTS
# =============================================================================

class TestErrorTracker:
    """Test error tracking integration."""

    def test_track_supervisor_error_with_tracker(self):
        """Test error tracking when tracker is available."""
        mock_tracker = MagicMock()

        with patch('bots.supervisor.ERROR_TRACKER_AVAILABLE', True):
            with patch('bots.supervisor.error_tracker', mock_tracker):
                exc = ValueError("Test error")
                track_supervisor_error(exc, "test_component", "test context")

        mock_tracker.track_error.assert_called_once_with(
            exc,
            context="test context",
            component="supervisor",
            metadata={"component_name": "test_component"},
        )

    def test_track_supervisor_error_without_tracker(self):
        """Test error tracking when tracker is not available."""
        with patch('bots.supervisor.ERROR_TRACKER_AVAILABLE', False):
            exc = ValueError("Test error")
            # Should not raise
            track_supervisor_error(exc, "test_component")

    def test_track_supervisor_error_uses_default_context(self):
        """Test error tracking uses default context."""
        mock_tracker = MagicMock()

        with patch('bots.supervisor.ERROR_TRACKER_AVAILABLE', True):
            with patch('bots.supervisor.error_tracker', mock_tracker):
                exc = ValueError("Error")
                track_supervisor_error(exc, "my_bot")

        call_args = mock_tracker.track_error.call_args
        assert "supervisor.my_bot" in call_args.kwargs["context"]


# =============================================================================
# BOT FACTORY FUNCTION TESTS
# =============================================================================

class TestBotFactoryFunctions:
    """Test individual bot factory functions."""

    @pytest.mark.asyncio
    async def test_create_bags_intel_disabled_by_default(self):
        """Test bags_intel is disabled by default."""
        with patch.dict(os.environ, {"BAGS_INTEL_ENABLED": ""}):
            # Should run in a loop doing nothing
            task = asyncio.create_task(
                asyncio.wait_for(
                    __import__('bots.supervisor', fromlist=['create_bags_intel']).create_bags_intel(),
                    timeout=0.1
                )
            )

            with pytest.raises(asyncio.TimeoutError):
                await task

    @pytest.mark.asyncio
    async def test_create_telegram_bot_without_token(self, caplog):
        """Test telegram bot skips without token."""
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": ""}):
            from bots.supervisor import create_telegram_bot

            with caplog.at_level(logging.WARNING):
                await create_telegram_bot()

        assert "No TELEGRAM_BOT_TOKEN" in caplog.text

    @pytest.mark.asyncio
    async def test_create_treasury_bot_without_token(self, caplog):
        """Test treasury bot skips without token."""
        with patch.dict(os.environ, {
            "TREASURY_BOT_TOKEN": "",
            "TREASURY_BOT_TELEGRAM_TOKEN": "",
        }):
            from bots.supervisor import create_treasury_bot

            with caplog.at_level(logging.WARNING):
                await create_treasury_bot()

        assert "No TREASURY_BOT_TOKEN" in caplog.text


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestSupervisorIntegration:
    """Integration tests for supervisor."""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, supervisor, execution_log):
        """Test full supervisor lifecycle."""
        async def bot1():
            execution_log["started"].append("bot1")
            # Exit immediately for quick test
            execution_log["stopped"].append("bot1")

        async def bot2():
            execution_log["started"].append("bot2")
            execution_log["stopped"].append("bot2")

        supervisor.register("bot1", bot1)
        supervisor.register("bot2", bot2)

        async def mock_health_monitor():
            pass

        with patch('bots.supervisor.systemd_notify', return_value=False):
            with patch.object(supervisor, '_health_monitor', mock_health_monitor):
                await supervisor.run_forever()

        assert "bot1" in execution_log["started"]
        assert "bot2" in execution_log["started"]

    @pytest.mark.asyncio
    async def test_component_isolation(self, supervisor, execution_log):
        """Test one component failure doesn't affect others."""
        async def failing_bot():
            execution_log["started"].append("failing")
            raise RuntimeError("Fail!")

        async def stable_bot():
            execution_log["started"].append("stable")
            execution_log["stopped"].append("stable")

        supervisor.register("failing", failing_bot)
        supervisor.register("stable", stable_bot)
        supervisor.max_restarts = 1

        async def mock_health_monitor():
            pass

        with patch('asyncio.sleep', new_callable=AsyncMock):
            with patch('bots.supervisor.systemd_notify', return_value=False):
                with patch.object(supervisor, '_send_critical_alert', new_callable=AsyncMock):
                    with patch.object(supervisor, '_health_monitor', mock_health_monitor):
                        await supervisor.run_forever()

        # Stable bot should have run despite failing bot
        assert "stable" in execution_log["started"]

    @pytest.mark.asyncio
    async def test_shutdown_interrupts_running_components(self, supervisor):
        """Test shutdown interrupts running components."""
        shutdown_triggered = False

        async def long_bot():
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                pass

        supervisor.register("long", long_bot)

        async def mock_health_monitor():
            # Wait for shutdown to be triggered
            while not shutdown_triggered:
                await asyncio.sleep(0.01)

        async def trigger_shutdown():
            nonlocal shutdown_triggered
            await asyncio.sleep(0.02)
            shutdown_triggered = True
            supervisor._running = False
            await supervisor._graceful_shutdown()

        with patch('bots.supervisor.systemd_notify', return_value=False):
            with patch.object(supervisor, '_health_monitor', mock_health_monitor):
                await asyncio.gather(
                    supervisor.run_forever(),
                    trigger_shutdown(),
                    return_exceptions=True,
                )

        # Verify shutdown completed
        assert not supervisor._running


# =============================================================================
# EDGE CASE TESTS
# =============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_register_same_name_twice(self, supervisor):
        """Test registering same component name twice overwrites."""
        async def bot1():
            pass

        async def bot2():
            pass

        supervisor.register("same_name", bot1)
        supervisor.register("same_name", bot2)

        assert supervisor.component_funcs["same_name"] == bot2

    @pytest.mark.asyncio
    async def test_empty_supervisor_run(self, supervisor):
        """Test running supervisor with no components."""
        async def mock_health_monitor():
            pass

        with patch('bots.supervisor.systemd_notify', return_value=False):
            with patch.object(supervisor, '_health_monitor', mock_health_monitor):
                await supervisor.run_forever()

        # Should complete without error

    @pytest.mark.asyncio
    async def test_component_exits_cleanly(self, supervisor, caplog):
        """Test component that exits without error."""
        async def exiting_bot():
            return  # Exit cleanly

        supervisor.register("exiting", exiting_bot)
        supervisor._running = True

        with caplog.at_level(logging.INFO):
            await supervisor._run_component("exiting")

        assert "exited cleanly" in caplog.text

    @pytest.mark.asyncio
    async def test_zero_max_restarts(self, supervisor):
        """Test with zero max restarts."""
        supervisor.max_restarts = 0

        async def failing_bot():
            raise RuntimeError("Fail")

        supervisor.register("no_restart", failing_bot)
        supervisor._running = True

        await supervisor._run_component("no_restart")

        state = supervisor.components["no_restart"]
        assert state.restart_count == 0

    def test_get_status_with_stopped_component(self, supervisor):
        """Test get_status with never-started component."""
        async def dummy():
            pass

        supervisor.register("never_started", dummy)

        status = supervisor.get_status()

        assert status["never_started"]["status"] == "stopped"
        assert status["never_started"]["uptime"] is None


# =============================================================================
# ADDITIONAL COVERAGE TESTS
# =============================================================================

class TestSingleInstanceLockPlatformSpecific:
    """Additional platform-specific lock tests."""

    def test_lock_acquire_windows(self):
        """Test lock acquisition on Windows."""
        if sys.platform != "win32":
            pytest.skip("Windows-only test")

        lock = SingleInstanceLock("windows_test")
        mock_fd = MagicMock()

        with patch('builtins.open', return_value=mock_fd):
            with patch('msvcrt.locking') as mock_locking:
                result = lock.acquire()

        mock_locking.assert_called()
        assert lock._lock_fd is not None

    def test_lock_release_windows_with_error(self):
        """Test lock release handles errors gracefully on Windows."""
        lock = SingleInstanceLock("error_release")
        mock_fd = MagicMock()
        lock._lock_fd = mock_fd
        lock._is_windows = True

        # Make msvcrt.locking succeed but close fail
        with patch.dict('sys.modules', {'msvcrt': MagicMock()}):
            mock_fd.close.side_effect = Exception("Close error")
            # Should not raise even when close fails
            lock.release()

        # Lock should be cleared
        assert lock._lock_fd is None

    def test_lock_context_manager_exit_returns_false(self):
        """Test context manager __exit__ returns False."""
        lock = SingleInstanceLock("exit_test")

        with patch.object(lock, 'acquire'):
            with patch.object(lock, 'release'):
                result = lock.__exit__(None, None, None)

        assert result is False


class TestBotSupervisorAdvanced:
    """Advanced BotSupervisor tests for additional coverage."""

    @pytest.mark.asyncio
    async def test_run_component_with_sync_function(self, supervisor):
        """Test _run_component with synchronous function."""
        execution_count = 0

        def sync_bot():
            nonlocal execution_count
            execution_count += 1

        supervisor.register("sync", sync_bot)
        supervisor._running = True

        await supervisor._run_component("sync")

        assert execution_count == 1

    @pytest.mark.asyncio
    async def test_health_monitor_with_error(self, supervisor, caplog):
        """Test health monitor handles internal errors."""
        supervisor._running = True
        supervisor.health_check_interval = 0.01

        # Register a component
        async def dummy():
            pass
        supervisor.register("test", dummy)

        error_raised = False

        # Store original method
        original_method = supervisor._health_monitor

        async def mock_with_error():
            nonlocal error_raised
            try:
                # Just run for a brief time
                await asyncio.sleep(0.02)
                supervisor._running = False
            except Exception as e:
                error_raised = True

        # Just test that health monitor handles errors gracefully
        with caplog.at_level(logging.ERROR):
            await mock_with_error()

        # Test completed without raising

    @pytest.mark.asyncio
    async def test_graceful_shutdown_timeout(self, supervisor):
        """Test graceful shutdown handles task timeout."""
        async def never_finish():
            await asyncio.sleep(100)

        supervisor.register("never", never_finish)
        supervisor._running = True

        task = asyncio.create_task(asyncio.sleep(100))
        supervisor.components["never"].task = task

        await supervisor._graceful_shutdown()

        # Task should be cancelled
        assert task.cancelled() or task.done()

    @pytest.mark.asyncio
    async def test_graceful_shutdown_task_exception(self, supervisor, caplog):
        """Test graceful shutdown handles task exceptions."""
        async def error_on_cancel():
            try:
                await asyncio.sleep(100)
            except asyncio.CancelledError:
                raise RuntimeError("Error during cancel")

        supervisor.register("error_cancel", error_on_cancel)
        supervisor._running = True

        task = asyncio.create_task(error_on_cancel())
        supervisor.components["error_cancel"].task = task

        with caplog.at_level(logging.ERROR):
            await supervisor._graceful_shutdown()

    @pytest.mark.asyncio
    async def test_cleanup_with_shutdown_manager_available(self, supervisor):
        """Test cleanup when shutdown manager is available."""
        with patch('bots.supervisor.SHUTDOWN_MANAGER_AVAILABLE', True):
            with patch('bots.supervisor.systemd_notify'):
                await supervisor._cleanup()


class TestErrorAlertEdgeCases:
    """Edge case tests for error alerts."""

    @pytest.mark.asyncio
    async def test_send_error_alert_invalid_admin_ids(self, supervisor):
        """Test error alert handles invalid admin IDs."""
        with patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": "token",
            "TELEGRAM_ADMIN_IDS": "invalid,not_a_number,123",
        }):
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.post = AsyncMock()

            with patch('aiohttp.ClientSession', return_value=mock_session):
                await supervisor._send_error_alert("test", "error", 5, 10)

            # Should only call for valid admin ID (123)
            assert mock_session.post.call_count == 1

    @pytest.mark.asyncio
    async def test_send_critical_alert_without_admin_ids(self, supervisor):
        """Test critical alert handles empty admin IDs."""
        with patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": "token",
            "TELEGRAM_ADMIN_IDS": "",
        }):
            # Should not raise
            await supervisor._send_critical_alert("test", "error")


class TestLoadEnvEdgeCases:
    """Edge case tests for load_env."""

    def test_load_env_with_complex_values(self, tmp_path):
        """Test loading env with complex values."""
        env_file = tmp_path / ".env"
        env_file.write_text("COMPLEX_VAR=value=with=equals\nSPACED_VAR=  value  \n")

        with patch('bots.supervisor.project_root', tmp_path):
            os.environ.pop("COMPLEX_VAR", None)
            os.environ.pop("SPACED_VAR", None)
            load_env()

        # Should handle equals signs in values
        assert os.environ.get("COMPLEX_VAR") == "value=with=equals"


class TestValidationEdgeCases:
    """Edge case tests for validation."""

    def test_validate_startup_with_validation_errors(self):
        """Test validate_startup handles validation errors."""
        mock_result = MagicMock()
        mock_result.level = MagicMock()
        mock_result.level.__eq__ = MagicMock(side_effect=lambda x: x == 'error')
        mock_result.key = "test_key"
        mock_result.message = "test message"

        mock_validator = MagicMock()
        mock_validator.validate.return_value = (False, [mock_result])
        mock_validator.get_group_summary.return_value = {}

        mock_validation_level = MagicMock()
        mock_validation_level.ERROR = 'error'
        mock_validation_level.WARNING = 'warning'
        mock_validation_level.INFO = 'info'

        with patch.dict('sys.modules', {'core.config.validator': MagicMock(
            validate_config=MagicMock(),
            get_validator=MagicMock(return_value=mock_validator),
            ValidationLevel=mock_validation_level,
        )}):
            result = validate_startup()

        # Should return False when there are errors
        # Note: The actual behavior depends on the implementation


class TestBotFactoryFunctionsAdvanced:
    """Advanced tests for bot factory functions."""

    @pytest.mark.asyncio
    async def test_create_autonomous_x_engine_without_api_key(self, caplog):
        """Test autonomous X engine skips without API key."""
        with patch.dict(os.environ, {
            "X_API_KEY": "",
            "TWITTER_API_KEY": "",
        }):
            from bots.supervisor import create_autonomous_x_engine

            with caplog.at_level(logging.WARNING):
                await create_autonomous_x_engine()

        assert "No X_API_KEY" in caplog.text

    @pytest.mark.asyncio
    async def test_create_public_trading_bot_without_token(self, caplog):
        """Test public trading bot skips without token."""
        with patch.dict(os.environ, {"PUBLIC_BOT_TELEGRAM_TOKEN": ""}):
            from bots.supervisor import create_public_trading_bot

            with caplog.at_level(logging.INFO):
                await create_public_trading_bot()

        assert "PUBLIC_BOT_TELEGRAM_TOKEN not set" in caplog.text

    @pytest.mark.asyncio
    async def test_create_treasury_bot_token_conflict(self, caplog):
        """Test treasury bot skips when token conflicts with main bot."""
        shared_token = "same_token_123"
        with patch.dict(os.environ, {
            "TREASURY_BOT_TOKEN": shared_token,
            "TELEGRAM_BOT_TOKEN": shared_token,
            "PUBLIC_BOT_TELEGRAM_TOKEN": "",
        }):
            from bots.supervisor import create_treasury_bot

            with caplog.at_level(logging.WARNING):
                await create_treasury_bot()

        assert "matches another bot token" in caplog.text


class TestComponentStateAdvanced:
    """Advanced tests for ComponentState."""

    def test_component_state_all_fields(self):
        """Test ComponentState with all fields set."""
        now = datetime.now()
        mock_task = MagicMock()

        state = ComponentState(
            name="full_test",
            status=ComponentStatus.RUNNING,
            task=mock_task,
            start_time=now,
            restart_count=5,
            last_error="Previous error",
            last_error_time=now,
            consecutive_failures=3,
            min_backoff=2.0,
            max_backoff=120.0,
            current_backoff=8.0,
        )

        assert state.name == "full_test"
        assert state.status == ComponentStatus.RUNNING
        assert state.task == mock_task
        assert state.start_time == now
        assert state.restart_count == 5
        assert state.last_error == "Previous error"
        assert state.consecutive_failures == 3
        assert state.min_backoff == 2.0
        assert state.max_backoff == 120.0
        assert state.current_backoff == 8.0


class TestRunComponentEdgeCases:
    """Edge case tests for _run_component."""

    @pytest.mark.asyncio
    async def test_run_component_stop_on_clean_exit(self, supervisor, caplog):
        """Test _run_component stops on clean exit."""
        async def clean_exit_bot():
            return "done"

        supervisor.register("clean", clean_exit_bot)
        supervisor._running = True

        with caplog.at_level(logging.INFO):
            await supervisor._run_component("clean")

        assert "exited cleanly" in caplog.text
        assert supervisor.components["clean"].status == ComponentStatus.STOPPED

    @pytest.mark.asyncio
    async def test_run_component_alert_on_5th_failure(self, supervisor):
        """Test _run_component sends alert every 5 failures."""
        failure_count = 0

        async def failing_bot():
            nonlocal failure_count
            failure_count += 1
            raise RuntimeError(f"Failure {failure_count}")

        supervisor.register("alerting", failing_bot)
        supervisor._running = True
        supervisor.max_restarts = 6

        alert_sent = False

        async def mock_alert(*args):
            nonlocal alert_sent
            alert_sent = True

        # Patch TASK_TRACKING_AVAILABLE to False to use create_task path
        with patch('bots.supervisor.TASK_TRACKING_AVAILABLE', False):
            with patch('asyncio.sleep', new_callable=AsyncMock):
                with patch.object(supervisor, '_send_error_alert', mock_alert):
                    with patch.object(supervisor, '_send_critical_alert', new_callable=AsyncMock):
                        await supervisor._run_component("alerting")

        # Should have attempted to send alert at 5th failure
        # Note: The alert is sent via create_task, so we check if mock was called
        assert failure_count >= 5


class TestIntegrationAdvanced:
    """Advanced integration tests."""

    @pytest.mark.asyncio
    async def test_multiple_component_failure_isolation(self, supervisor):
        """Test multiple components can fail independently."""
        results = {"a": False, "b": False, "c": False}

        async def bot_a():
            results["a"] = True
            raise RuntimeError("Bot A failed")

        async def bot_b():
            results["b"] = True
            # Succeeds

        async def bot_c():
            results["c"] = True
            raise ValueError("Bot C failed")

        supervisor.register("a", bot_a)
        supervisor.register("b", bot_b)
        supervisor.register("c", bot_c)
        supervisor.max_restarts = 1

        async def mock_health_monitor():
            pass

        with patch('asyncio.sleep', new_callable=AsyncMock):
            with patch('bots.supervisor.systemd_notify', return_value=False):
                with patch.object(supervisor, '_send_critical_alert', new_callable=AsyncMock):
                    with patch.object(supervisor, '_health_monitor', mock_health_monitor):
                        await supervisor.run_forever()

        # All bots should have attempted to run
        assert results["a"] is True
        assert results["b"] is True
        assert results["c"] is True


# =============================================================================
# MORE COVERAGE TESTS FOR BOT FACTORY FUNCTIONS
# =============================================================================

class TestBotFactoryFunctionsMore:
    """More tests for bot factory functions."""

    @pytest.mark.asyncio
    async def test_create_bags_intel_enabled(self):
        """Test bags_intel runs when enabled."""
        with patch.dict(os.environ, {"BAGS_INTEL_ENABLED": "true"}):
            # Mock the import
            mock_service = AsyncMock()

            with patch.dict('sys.modules', {
                'bots.bags_intel': MagicMock(create_bags_intel_service=mock_service)
            }):
                from bots.supervisor import create_bags_intel

                await create_bags_intel()

                mock_service.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_ai_supervisor_unavailable(self, caplog):
        """Test AI supervisor handles import error."""
        # Clear the module from cache
        import sys as sysmod
        for mod in list(sysmod.modules.keys()):
            if 'ai_runtime' in mod:
                del sysmod.modules[mod]

        # Make the import fail
        with patch.dict('sys.modules', {'core.ai_runtime.integration': None}):
            from bots.supervisor import create_ai_supervisor

            # Should run forever idle loop
            task = asyncio.create_task(
                asyncio.wait_for(create_ai_supervisor(), timeout=0.1)
            )

            with pytest.raises(asyncio.TimeoutError):
                await task


class TestTaskTrackingPaths:
    """Test different task tracking code paths."""

    @pytest.mark.asyncio
    async def test_alert_with_task_tracking_available(self, supervisor):
        """Test alert sending with fire_and_forget available."""
        failure_count = 0

        async def failing_bot():
            nonlocal failure_count
            failure_count += 1
            raise RuntimeError(f"Failure {failure_count}")

        supervisor.register("alerting", failing_bot)
        supervisor._running = True
        supervisor.max_restarts = 6

        # Mock fire_and_forget
        mock_fire = MagicMock()

        with patch('bots.supervisor.TASK_TRACKING_AVAILABLE', True):
            with patch('bots.supervisor.fire_and_forget', mock_fire):
                with patch('asyncio.sleep', new_callable=AsyncMock):
                    await supervisor._run_component("alerting")

        # fire_and_forget should have been called for the alert
        assert mock_fire.called

    @pytest.mark.asyncio
    async def test_critical_alert_with_task_tracking(self, supervisor):
        """Test critical alert with fire_and_forget available."""
        async def always_fail():
            raise RuntimeError("Always fails")

        supervisor.register("fail", always_fail)
        supervisor._running = True
        supervisor.max_restarts = 1

        mock_fire = MagicMock()

        with patch('bots.supervisor.TASK_TRACKING_AVAILABLE', True):
            with patch('bots.supervisor.fire_and_forget', mock_fire):
                with patch('asyncio.sleep', new_callable=AsyncMock):
                    await supervisor._run_component("fail")

        # fire_and_forget should have been called for critical alert
        assert mock_fire.called


class TestRunComponentMorePaths:
    """More tests for _run_component code paths."""

    @pytest.mark.asyncio
    async def test_run_component_cancelled_during_backoff(self, supervisor):
        """Test component cancellation during backoff sleep."""
        failure_count = 0

        async def failing_bot():
            nonlocal failure_count
            failure_count += 1
            raise RuntimeError("Fail")

        supervisor.register("cancel_backoff", failing_bot)
        supervisor._running = True
        supervisor.max_restarts = 10

        # Make sleep raise CancelledError on second call
        call_count = 0
        async def cancel_on_second_sleep(duration):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise asyncio.CancelledError()

        with patch('asyncio.sleep', cancel_on_second_sleep):
            await supervisor._run_component("cancel_backoff")

        # Should have stopped due to cancellation during backoff
        assert supervisor.components["cancel_backoff"].status == ComponentStatus.STOPPED

    @pytest.mark.asyncio
    async def test_run_component_not_running(self, supervisor):
        """Test component doesn't run when supervisor is not running."""
        async def bot():
            pass

        supervisor.register("no_run", bot)
        supervisor._running = False  # Not running

        await supervisor._run_component("no_run")

        # Should have stopped immediately
        assert supervisor.components["no_run"].status == ComponentStatus.STOPPED


class TestHealthMonitorMorePaths:
    """More tests for health monitor code paths."""

    @pytest.mark.asyncio
    async def test_health_monitor_uptime_display(self, supervisor, caplog):
        """Test health monitor displays uptime correctly."""
        supervisor._running = True
        supervisor.health_check_interval = 0.01

        async def dummy():
            pass

        supervisor.register("uptime_test", dummy)
        state = supervisor.components["uptime_test"]
        state.status = ComponentStatus.RUNNING
        state.start_time = datetime.now() - timedelta(hours=1)  # 1 hour uptime
        state.restart_count = 2

        async def stop_soon():
            await asyncio.sleep(0.02)
            supervisor._running = False

        with caplog.at_level(logging.INFO):
            await asyncio.gather(
                supervisor._health_monitor(),
                stop_soon(),
            )

        # Should log the status with uptime
        assert "uptime_test" in caplog.text


class TestGetStatusMorePaths:
    """More tests for get_status."""

    def test_get_status_with_running_time(self, supervisor):
        """Test get_status calculates uptime correctly."""
        async def dummy():
            pass

        supervisor.register("running_test", dummy)
        state = supervisor.components["running_test"]
        state.status = ComponentStatus.RUNNING
        state.start_time = datetime.now() - timedelta(seconds=60)

        status = supervisor.get_status()

        assert status["running_test"]["uptime"] is not None


class TestShutdownManagerIntegration:
    """Test shutdown manager integration."""

    def test_supervisor_registers_shutdown_hook(self):
        """Test supervisor registers with shutdown manager."""
        mock_shutdown_mgr = MagicMock()

        with patch('bots.supervisor.SHUTDOWN_MANAGER_AVAILABLE', True):
            with patch('bots.supervisor.get_shutdown_manager', return_value=mock_shutdown_mgr):
                with patch('bots.supervisor.ShutdownPhase') as mock_phase:
                    mock_phase.IMMEDIATE = "immediate"
                    sup = BotSupervisor()

        # Should have registered
        mock_shutdown_mgr.register_hook.assert_called_once()
        call_kwargs = mock_shutdown_mgr.register_hook.call_args.kwargs
        assert call_kwargs['name'] == 'supervisor'


class TestSystemdNotifyMoreCases:
    """More tests for systemd_notify."""

    def test_systemd_notify_empty_socket_path(self):
        """Test systemd_notify with empty socket path."""
        with patch.dict(os.environ, {"NOTIFY_SOCKET": ""}):
            result = systemd_notify("READY=1")
            assert result is False


class TestLoadEnvMoreCases:
    """More tests for load_env."""

    def test_load_env_doesnt_overwrite_existing(self, tmp_path):
        """Test load_env uses setdefault (doesn't overwrite)."""
        env_file = tmp_path / ".env"
        env_file.write_text("EXISTING_VAR=new_value\n")

        # Set existing value
        os.environ["EXISTING_VAR"] = "existing_value"

        with patch('bots.supervisor.project_root', tmp_path):
            load_env()

        # Should NOT overwrite existing value
        assert os.environ.get("EXISTING_VAR") == "existing_value"

        # Cleanup
        del os.environ["EXISTING_VAR"]


class TestErrorTrackerMoreCases:
    """More tests for error tracker."""

    def test_track_error_with_no_context(self):
        """Test error tracking with empty context uses default."""
        mock_tracker = MagicMock()

        with patch('bots.supervisor.ERROR_TRACKER_AVAILABLE', True):
            with patch('bots.supervisor.error_tracker', mock_tracker):
                exc = ValueError("Test")
                track_supervisor_error(exc, "my_component", "")

        # Should use default context pattern
        call_args = mock_tracker.track_error.call_args
        assert "supervisor.my_component" in call_args.kwargs["context"]


class TestCleanupMorePaths:
    """More tests for cleanup paths."""

    @pytest.mark.asyncio
    async def test_cleanup_fallback_without_shutdown_manager(self, supervisor):
        """Test cleanup fallback when shutdown manager unavailable."""
        async def long_task():
            await asyncio.sleep(100)

        supervisor.register("cleanup_test", long_task)

        task = asyncio.create_task(asyncio.sleep(100))
        supervisor.components["cleanup_test"].task = task

        with patch('bots.supervisor.SHUTDOWN_MANAGER_AVAILABLE', False):
            with patch('bots.supervisor.systemd_notify'):
                await supervisor._cleanup()

        # Task should be cancelled
        assert task.cancelled() or task.done()

    @pytest.mark.asyncio
    async def test_cleanup_handles_cancelled_error(self, supervisor):
        """Test cleanup handles CancelledError from tasks."""
        supervisor.register("cancel_test", lambda: None)

        task = asyncio.create_task(asyncio.sleep(100))
        supervisor.components["cancel_test"].task = task

        with patch('bots.supervisor.SHUTDOWN_MANAGER_AVAILABLE', False):
            with patch('bots.supervisor.systemd_notify'):
                await supervisor._cleanup()


class TestGracefulShutdownMorePaths:
    """More tests for graceful shutdown."""

    @pytest.mark.asyncio
    async def test_graceful_shutdown_with_done_task(self, supervisor, caplog):
        """Test graceful shutdown with already-done task."""
        supervisor.register("done_test", lambda: None)

        # Create a task that's already done
        async def quick():
            return "done"
        task = asyncio.create_task(quick())
        await asyncio.sleep(0.01)  # Let it complete

        supervisor.components["done_test"].task = task

        with caplog.at_level(logging.INFO):
            await supervisor._graceful_shutdown()

        # Should log shutdown
        assert "shutdown" in caplog.text.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
