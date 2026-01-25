"""
Unit tests for core/command_watchdog.py

Tests cover:
- CommandWatchdog class initialization and attributes
- Command registration (register method)
- Command unregistration (unregister method)
- Watchdog start/stop lifecycle
- Timeout detection and force-killing
- Process tree killing
- Global watchdog singleton functions
- Thread safety with concurrent operations
- Edge cases and error conditions
"""

import pytest
import time
import threading
from unittest.mock import patch, MagicMock, PropertyMock

from core.command_watchdog import (
    CommandWatchdog,
    get_watchdog,
    shutdown_watchdog,
    _watchdog,
)


class TestCommandWatchdogInit:
    """Tests for CommandWatchdog initialization."""

    def test_init_default_check_interval(self):
        """Test CommandWatchdog initializes with default check_interval of 10."""
        wd = CommandWatchdog()
        assert wd.check_interval == 10

    def test_init_custom_check_interval(self):
        """Test CommandWatchdog accepts custom check_interval."""
        wd = CommandWatchdog(check_interval=5)
        assert wd.check_interval == 5

    def test_init_active_commands_empty(self):
        """Test CommandWatchdog starts with empty active_commands dict."""
        wd = CommandWatchdog()
        assert wd.active_commands == {}
        assert isinstance(wd.active_commands, dict)

    def test_init_lock_is_rlock(self):
        """Test CommandWatchdog creates an RLock for thread safety."""
        wd = CommandWatchdog()
        assert isinstance(wd.lock, type(threading.RLock()))

    def test_init_not_running(self):
        """Test CommandWatchdog starts in not running state."""
        wd = CommandWatchdog()
        assert wd._running is False

    def test_init_thread_is_none(self):
        """Test CommandWatchdog starts with no thread."""
        wd = CommandWatchdog()
        assert wd._thread is None

    def test_init_zero_check_interval(self):
        """Test CommandWatchdog accepts zero check_interval."""
        wd = CommandWatchdog(check_interval=0)
        assert wd.check_interval == 0

    def test_init_large_check_interval(self):
        """Test CommandWatchdog accepts large check_interval."""
        wd = CommandWatchdog(check_interval=3600)
        assert wd.check_interval == 3600


class TestCommandWatchdogRegister:
    """Tests for CommandWatchdog.register() method."""

    def test_register_adds_command_to_active_commands(self):
        """Test register adds command info to active_commands dict."""
        wd = CommandWatchdog()
        started = time.time()
        wd.register(pid=1234, command="echo hello", timeout=30, started_at=started)

        assert 1234 in wd.active_commands
        assert wd.active_commands[1234]["command"] == "echo hello"
        assert wd.active_commands[1234]["timeout"] == 30
        assert wd.active_commands[1234]["started_at"] == started
        assert wd.active_commands[1234]["killed"] is False

    def test_register_multiple_commands(self):
        """Test register can track multiple commands."""
        wd = CommandWatchdog()
        started = time.time()

        wd.register(pid=1001, command="cmd1", timeout=10, started_at=started)
        wd.register(pid=1002, command="cmd2", timeout=20, started_at=started)
        wd.register(pid=1003, command="cmd3", timeout=30, started_at=started)

        assert len(wd.active_commands) == 3
        assert 1001 in wd.active_commands
        assert 1002 in wd.active_commands
        assert 1003 in wd.active_commands

    def test_register_overwrites_existing_pid(self):
        """Test register overwrites if same PID is registered again."""
        wd = CommandWatchdog()
        started = time.time()

        wd.register(pid=1234, command="cmd1", timeout=10, started_at=started)
        wd.register(pid=1234, command="cmd2", timeout=20, started_at=started + 5)

        assert len(wd.active_commands) == 1
        assert wd.active_commands[1234]["command"] == "cmd2"
        assert wd.active_commands[1234]["timeout"] == 20

    def test_register_with_long_command(self):
        """Test register handles very long command strings."""
        wd = CommandWatchdog()
        long_cmd = "x" * 10000
        started = time.time()

        wd.register(pid=1234, command=long_cmd, timeout=30, started_at=started)

        assert wd.active_commands[1234]["command"] == long_cmd

    def test_register_with_empty_command(self):
        """Test register handles empty command string."""
        wd = CommandWatchdog()
        started = time.time()

        wd.register(pid=1234, command="", timeout=30, started_at=started)

        assert wd.active_commands[1234]["command"] == ""

    def test_register_with_unicode_command(self):
        """Test register handles unicode in command string."""
        wd = CommandWatchdog()
        started = time.time()

        wd.register(pid=1234, command="echo '\u4e2d\u6587'", timeout=30, started_at=started)

        assert "\u4e2d\u6587" in wd.active_commands[1234]["command"]

    def test_register_stores_killed_as_false(self):
        """Test register always initializes killed flag as False."""
        wd = CommandWatchdog()
        started = time.time()

        wd.register(pid=1234, command="cmd", timeout=30, started_at=started)

        assert wd.active_commands[1234]["killed"] is False

    def test_register_logs_debug_message(self):
        """Test register logs a debug message."""
        wd = CommandWatchdog()
        started = time.time()

        with patch('core.command_watchdog.logger') as mock_logger:
            wd.register(pid=1234, command="echo hello", timeout=30, started_at=started)
            mock_logger.debug.assert_called()
            call_args = mock_logger.debug.call_args[0][0]
            assert "1234" in call_args


class TestCommandWatchdogUnregister:
    """Tests for CommandWatchdog.unregister() method."""

    def test_unregister_removes_command_from_active(self):
        """Test unregister removes command from active_commands."""
        wd = CommandWatchdog()
        started = time.time()

        wd.register(pid=1234, command="cmd", timeout=30, started_at=started)
        assert 1234 in wd.active_commands

        wd.unregister(1234)
        assert 1234 not in wd.active_commands

    def test_unregister_nonexistent_pid_no_error(self):
        """Test unregister does not raise error for nonexistent PID."""
        wd = CommandWatchdog()

        # Should not raise
        wd.unregister(9999)
        assert 9999 not in wd.active_commands

    def test_unregister_preserves_other_commands(self):
        """Test unregister only removes specified PID."""
        wd = CommandWatchdog()
        started = time.time()

        wd.register(pid=1001, command="cmd1", timeout=10, started_at=started)
        wd.register(pid=1002, command="cmd2", timeout=20, started_at=started)
        wd.register(pid=1003, command="cmd3", timeout=30, started_at=started)

        wd.unregister(1002)

        assert 1001 in wd.active_commands
        assert 1002 not in wd.active_commands
        assert 1003 in wd.active_commands

    def test_unregister_logs_debug_message(self):
        """Test unregister logs a debug message when PID exists."""
        wd = CommandWatchdog()
        started = time.time()

        wd.register(pid=1234, command="cmd", timeout=30, started_at=started)

        with patch('core.command_watchdog.logger') as mock_logger:
            wd.unregister(1234)
            mock_logger.debug.assert_called()
            call_args = mock_logger.debug.call_args[0][0]
            assert "1234" in call_args

    def test_unregister_no_log_for_nonexistent(self):
        """Test unregister does not log for nonexistent PID."""
        wd = CommandWatchdog()

        with patch('core.command_watchdog.logger') as mock_logger:
            wd.unregister(9999)
            # Should not call debug for stopped tracking since it wasn't tracked
            for call in mock_logger.debug.call_args_list:
                if "stopped tracking" in str(call):
                    pytest.fail("Should not log 'stopped tracking' for nonexistent PID")


class TestCommandWatchdogStartStop:
    """Tests for CommandWatchdog start/stop lifecycle."""

    def test_start_sets_running_true(self):
        """Test start sets _running to True."""
        wd = CommandWatchdog(check_interval=1)

        try:
            wd.start()
            assert wd._running is True
        finally:
            wd.stop()

    def test_start_creates_thread(self):
        """Test start creates a monitoring thread."""
        wd = CommandWatchdog(check_interval=1)

        try:
            wd.start()
            assert wd._thread is not None
            assert isinstance(wd._thread, threading.Thread)
        finally:
            wd.stop()

    def test_start_thread_is_daemon(self):
        """Test start creates a daemon thread."""
        wd = CommandWatchdog(check_interval=1)

        try:
            wd.start()
            assert wd._thread.daemon is True
        finally:
            wd.stop()

    def test_start_thread_is_alive(self):
        """Test started thread is alive."""
        wd = CommandWatchdog(check_interval=1)

        try:
            wd.start()
            assert wd._thread.is_alive()
        finally:
            wd.stop()

    def test_start_when_already_running_no_op(self):
        """Test start does nothing if already running."""
        wd = CommandWatchdog(check_interval=1)

        try:
            wd.start()
            first_thread = wd._thread

            wd.start()  # Second call should be no-op

            assert wd._thread is first_thread
        finally:
            wd.stop()

    def test_stop_sets_running_false(self):
        """Test stop sets _running to False."""
        wd = CommandWatchdog(check_interval=1)

        wd.start()
        wd.stop()

        assert wd._running is False

    def test_stop_when_not_running_no_error(self):
        """Test stop does not raise error when not running."""
        wd = CommandWatchdog()

        # Should not raise
        wd.stop()
        assert wd._running is False

    def test_stop_logs_info_message(self):
        """Test stop logs info message."""
        wd = CommandWatchdog(check_interval=1)

        wd.start()

        with patch('core.command_watchdog.logger') as mock_logger:
            wd.stop()
            mock_logger.info.assert_called()
            call_args = mock_logger.info.call_args[0][0]
            assert "stopped" in call_args.lower()

    def test_start_logs_info_message(self):
        """Test start logs info message."""
        wd = CommandWatchdog(check_interval=1)

        try:
            with patch('core.command_watchdog.logger') as mock_logger:
                wd.start()
                mock_logger.info.assert_called()
                call_args = mock_logger.info.call_args[0][0]
                assert "started" in call_args.lower()
        finally:
            wd.stop()


class TestCommandWatchdogCheckCommands:
    """Tests for CommandWatchdog._check_commands() method."""

    def test_check_commands_does_nothing_for_fresh_commands(self):
        """Test _check_commands does not kill commands within timeout."""
        wd = CommandWatchdog()
        started = time.time()

        wd.register(pid=1234, command="cmd", timeout=30, started_at=started)

        with patch.object(wd, '_force_kill') as mock_kill:
            wd._check_commands()
            mock_kill.assert_not_called()

    def test_check_commands_identifies_timed_out_commands(self):
        """Test _check_commands identifies commands that exceeded timeout + grace."""
        wd = CommandWatchdog()
        # Set started_at to 50 seconds ago, timeout is 30s, grace is 10s = 40s threshold
        started = time.time() - 50

        wd.register(pid=1234, command="hung_cmd", timeout=30, started_at=started)

        with patch.object(wd, '_force_kill') as mock_kill:
            wd._check_commands()
            mock_kill.assert_called_once_with(1234, "hung_cmd")

    def test_check_commands_sets_killed_flag(self):
        """Test _check_commands sets killed flag on timed out command."""
        wd = CommandWatchdog()
        started = time.time() - 50

        wd.register(pid=1234, command="cmd", timeout=30, started_at=started)

        with patch.object(wd, '_force_kill'):
            wd._check_commands()
            assert wd.active_commands[1234]["killed"] is True

    def test_check_commands_does_not_kill_twice(self):
        """Test _check_commands does not kill already killed command."""
        wd = CommandWatchdog()
        started = time.time() - 50

        wd.register(pid=1234, command="cmd", timeout=30, started_at=started)
        wd.active_commands[1234]["killed"] = True  # Already killed

        with patch.object(wd, '_force_kill') as mock_kill:
            wd._check_commands()
            mock_kill.assert_not_called()

    def test_check_commands_respects_grace_period(self):
        """Test _check_commands respects 10 second grace period."""
        wd = CommandWatchdog()
        # 35 seconds ago, timeout 30s, grace 10s = needs 40s, so should NOT kill
        started = time.time() - 35

        wd.register(pid=1234, command="cmd", timeout=30, started_at=started)

        with patch.object(wd, '_force_kill') as mock_kill:
            wd._check_commands()
            mock_kill.assert_not_called()

    def test_check_commands_handles_multiple_timed_out(self):
        """Test _check_commands handles multiple timed out commands."""
        wd = CommandWatchdog()
        started_old = time.time() - 100
        started_fresh = time.time()

        wd.register(pid=1001, command="old1", timeout=30, started_at=started_old)
        wd.register(pid=1002, command="fresh", timeout=30, started_at=started_fresh)
        wd.register(pid=1003, command="old2", timeout=30, started_at=started_old)

        with patch.object(wd, '_force_kill') as mock_kill:
            wd._check_commands()
            assert mock_kill.call_count == 2
            called_pids = [call[0][0] for call in mock_kill.call_args_list]
            assert 1001 in called_pids
            assert 1003 in called_pids
            assert 1002 not in called_pids

    def test_check_commands_logs_warning_for_hung(self):
        """Test _check_commands logs warning for hung commands."""
        wd = CommandWatchdog()
        started = time.time() - 100

        wd.register(pid=1234, command="hung_cmd", timeout=30, started_at=started)

        with patch.object(wd, '_force_kill'):
            with patch('core.command_watchdog.logger') as mock_logger:
                wd._check_commands()
                mock_logger.warning.assert_called()
                call_args = mock_logger.warning.call_args[0][0]
                assert "1234" in call_args
                assert "hung" in call_args.lower()


class TestCommandWatchdogForceKill:
    """Tests for CommandWatchdog._force_kill() method."""

    def test_force_kill_kills_process(self):
        """Test _force_kill calls kill on the process."""
        wd = CommandWatchdog()

        mock_proc = MagicMock()
        mock_proc.children.return_value = []

        with patch('psutil.Process', return_value=mock_proc):
            wd._force_kill(1234, "test_cmd")
            mock_proc.kill.assert_called_once()

    def test_force_kill_kills_children_first(self):
        """Test _force_kill kills children before parent."""
        wd = CommandWatchdog()

        mock_child1 = MagicMock()
        mock_child2 = MagicMock()
        mock_proc = MagicMock()
        mock_proc.children.return_value = [mock_child1, mock_child2]

        call_order = []
        mock_child1.kill.side_effect = lambda: call_order.append('child1')
        mock_child2.kill.side_effect = lambda: call_order.append('child2')
        mock_proc.kill.side_effect = lambda: call_order.append('parent')

        with patch('psutil.Process', return_value=mock_proc):
            wd._force_kill(1234, "test_cmd")

        assert call_order.index('child1') < call_order.index('parent')
        assert call_order.index('child2') < call_order.index('parent')

    def test_force_kill_handles_no_such_process(self):
        """Test _force_kill handles NoSuchProcess exception."""
        wd = CommandWatchdog()

        import psutil
        with patch('psutil.Process', side_effect=psutil.NoSuchProcess(1234)):
            # Should not raise
            wd._force_kill(1234, "test_cmd")

    def test_force_kill_handles_child_no_such_process(self):
        """Test _force_kill handles NoSuchProcess for child."""
        wd = CommandWatchdog()

        import psutil
        mock_child = MagicMock()
        mock_child.kill.side_effect = psutil.NoSuchProcess(1111)
        mock_proc = MagicMock()
        mock_proc.children.return_value = [mock_child]

        with patch('psutil.Process', return_value=mock_proc):
            # Should not raise
            wd._force_kill(1234, "test_cmd")

    def test_force_kill_handles_access_denied(self):
        """Test _force_kill handles AccessDenied exception."""
        wd = CommandWatchdog()

        import psutil
        mock_proc = MagicMock()
        mock_proc.children.return_value = []
        mock_proc.kill.side_effect = psutil.AccessDenied(1234)

        with patch('psutil.Process', return_value=mock_proc):
            # Should not raise
            wd._force_kill(1234, "test_cmd")

    def test_force_kill_handles_generic_exception(self):
        """Test _force_kill handles generic exceptions."""
        wd = CommandWatchdog()

        with patch('psutil.Process', side_effect=RuntimeError("Something failed")):
            # Should not raise, but should log error
            with patch('core.command_watchdog.logger') as mock_logger:
                wd._force_kill(1234, "test_cmd")
                mock_logger.error.assert_called()

    def test_force_kill_logs_error_message(self):
        """Test _force_kill logs error message about killing."""
        wd = CommandWatchdog()

        mock_proc = MagicMock()
        mock_proc.children.return_value = []

        with patch('psutil.Process', return_value=mock_proc):
            with patch('core.command_watchdog.logger') as mock_logger:
                wd._force_kill(1234, "test_cmd")
                mock_logger.error.assert_called()
                call_args = mock_logger.error.call_args[0][0]
                assert "FORCE KILLING" in call_args
                assert "1234" in call_args

    def test_force_kill_logs_debug_for_already_terminated(self):
        """Test _force_kill logs debug for already terminated process."""
        wd = CommandWatchdog()

        import psutil
        with patch('psutil.Process', side_effect=psutil.NoSuchProcess(1234)):
            with patch('core.command_watchdog.logger') as mock_logger:
                wd._force_kill(1234, "test_cmd")
                mock_logger.debug.assert_called()
                call_args = mock_logger.debug.call_args[0][0]
                assert "terminated" in call_args.lower()


class TestCommandWatchdogMonitorLoop:
    """Tests for CommandWatchdog._monitor_loop() method."""

    def test_monitor_loop_calls_check_commands(self):
        """Test _monitor_loop calls _check_commands."""
        wd = CommandWatchdog(check_interval=0)
        wd._running = True

        call_count = 0

        def mock_check():
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                wd._running = False

        with patch.object(wd, '_check_commands', side_effect=mock_check):
            wd._monitor_loop()

        assert call_count >= 2

    def test_monitor_loop_handles_exceptions(self):
        """Test _monitor_loop handles exceptions without crashing."""
        wd = CommandWatchdog(check_interval=0)
        wd._running = True

        call_count = 0

        def mock_check():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Test error")
            if call_count >= 2:
                wd._running = False

        with patch.object(wd, '_check_commands', side_effect=mock_check):
            with patch('core.command_watchdog.logger') as mock_logger:
                wd._monitor_loop()
                mock_logger.error.assert_called()

    def test_monitor_loop_stops_when_not_running(self):
        """Test _monitor_loop stops when _running is False."""
        wd = CommandWatchdog(check_interval=0)
        wd._running = False

        with patch.object(wd, '_check_commands') as mock_check:
            wd._monitor_loop()
            mock_check.assert_not_called()


class TestGlobalWatchdogFunctions:
    """Tests for global watchdog singleton functions."""

    def test_get_watchdog_creates_instance(self):
        """Test get_watchdog creates a watchdog instance."""
        import core.command_watchdog as cw
        original = cw._watchdog

        try:
            cw._watchdog = None
            wd = get_watchdog()

            assert wd is not None
            assert isinstance(wd, CommandWatchdog)
        finally:
            if cw._watchdog:
                cw._watchdog.stop()
            cw._watchdog = original

    def test_get_watchdog_returns_same_instance(self):
        """Test get_watchdog returns the same instance on multiple calls."""
        import core.command_watchdog as cw
        original = cw._watchdog

        try:
            cw._watchdog = None
            wd1 = get_watchdog()
            wd2 = get_watchdog()

            assert wd1 is wd2
        finally:
            if cw._watchdog:
                cw._watchdog.stop()
            cw._watchdog = original

    def test_get_watchdog_starts_watchdog(self):
        """Test get_watchdog starts the watchdog automatically."""
        import core.command_watchdog as cw
        original = cw._watchdog

        try:
            cw._watchdog = None
            wd = get_watchdog()

            assert wd._running is True
        finally:
            if cw._watchdog:
                cw._watchdog.stop()
            cw._watchdog = original

    def test_shutdown_watchdog_stops_instance(self):
        """Test shutdown_watchdog stops the watchdog."""
        import core.command_watchdog as cw
        original = cw._watchdog

        try:
            cw._watchdog = None
            wd = get_watchdog()
            assert wd._running is True

            shutdown_watchdog()
            assert cw._watchdog is None
        finally:
            cw._watchdog = original

    def test_shutdown_watchdog_when_none_no_error(self):
        """Test shutdown_watchdog does not error when no instance exists."""
        import core.command_watchdog as cw
        original = cw._watchdog

        try:
            cw._watchdog = None

            # Should not raise
            shutdown_watchdog()
            assert cw._watchdog is None
        finally:
            cw._watchdog = original


class TestThreadSafety:
    """Tests for thread safety of CommandWatchdog."""

    def test_concurrent_register_unregister(self):
        """Test concurrent register and unregister operations."""
        wd = CommandWatchdog()
        started = time.time()
        errors = []

        def register_loop():
            try:
                for i in range(100):
                    wd.register(pid=i, command=f"cmd{i}", timeout=30, started_at=started)
            except Exception as e:
                errors.append(e)

        def unregister_loop():
            try:
                for i in range(100):
                    wd.unregister(i)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=register_loop),
            threading.Thread(target=unregister_loop),
            threading.Thread(target=register_loop),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_register_during_check_commands(self):
        """Test registering new commands during _check_commands."""
        wd = CommandWatchdog()
        started = time.time()

        wd.register(pid=1, command="cmd1", timeout=30, started_at=started)

        original_check = wd._check_commands

        def modified_check():
            # Register new command during check
            wd.register(pid=2, command="cmd2", timeout=30, started_at=started)
            original_check()

        with patch.object(wd, '_check_commands', modified_check):
            wd._check_commands()

        assert 1 in wd.active_commands
        assert 2 in wd.active_commands


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_register_with_zero_timeout(self):
        """Test register with zero timeout."""
        wd = CommandWatchdog()
        started = time.time()

        wd.register(pid=1234, command="cmd", timeout=0, started_at=started)

        assert wd.active_commands[1234]["timeout"] == 0

    def test_register_with_negative_timeout(self):
        """Test register with negative timeout (boundary case)."""
        wd = CommandWatchdog()
        started = time.time()

        wd.register(pid=1234, command="cmd", timeout=-1, started_at=started)

        assert wd.active_commands[1234]["timeout"] == -1

    def test_register_with_future_started_at(self):
        """Test register with future started_at time."""
        wd = CommandWatchdog()
        future_time = time.time() + 1000

        wd.register(pid=1234, command="cmd", timeout=30, started_at=future_time)

        with patch.object(wd, '_force_kill') as mock_kill:
            wd._check_commands()
            mock_kill.assert_not_called()

    def test_check_commands_with_empty_active(self):
        """Test _check_commands with no active commands."""
        wd = CommandWatchdog()

        with patch.object(wd, '_force_kill') as mock_kill:
            wd._check_commands()
            mock_kill.assert_not_called()

    def test_force_kill_with_truncated_command_in_log(self):
        """Test _force_kill truncates long commands in log."""
        wd = CommandWatchdog()
        long_cmd = "x" * 200

        mock_proc = MagicMock()
        mock_proc.children.return_value = []

        with patch('psutil.Process', return_value=mock_proc):
            with patch('core.command_watchdog.logger') as mock_logger:
                wd._force_kill(1234, long_cmd)
                call_args = mock_logger.error.call_args[0][0]
                # Should be truncated to 80 chars
                assert len(call_args) < len(long_cmd) + 100

    def test_check_commands_truncates_warning(self):
        """Test _check_commands truncates long commands in warning."""
        wd = CommandWatchdog()
        long_cmd = "y" * 200
        started = time.time() - 100

        wd.register(pid=1234, command=long_cmd, timeout=30, started_at=started)

        with patch.object(wd, '_force_kill'):
            with patch('core.command_watchdog.logger') as mock_logger:
                wd._check_commands()
                call_args = mock_logger.warning.call_args[0][0]
                assert len(call_args) < len(long_cmd) + 100


class TestPsutilIntegration:
    """Tests for psutil integration in _force_kill."""

    def test_force_kill_uses_recursive_children(self):
        """Test _force_kill gets children recursively."""
        wd = CommandWatchdog()

        mock_proc = MagicMock()

        with patch('psutil.Process', return_value=mock_proc):
            wd._force_kill(1234, "cmd")
            mock_proc.children.assert_called_once_with(recursive=True)

    def test_force_kill_handles_access_denied_for_child(self):
        """Test _force_kill handles AccessDenied for child process."""
        wd = CommandWatchdog()

        import psutil
        mock_child = MagicMock()
        mock_child.kill.side_effect = psutil.AccessDenied(1111)
        mock_proc = MagicMock()
        mock_proc.children.return_value = [mock_child]

        with patch('psutil.Process', return_value=mock_proc):
            # Should not raise, and should still try to kill parent
            wd._force_kill(1234, "cmd")
            mock_proc.kill.assert_called_once()

    def test_force_kill_handles_parent_access_denied(self):
        """Test _force_kill handles AccessDenied for parent process."""
        wd = CommandWatchdog()

        import psutil
        mock_proc = MagicMock()
        mock_proc.children.return_value = []
        mock_proc.kill.side_effect = psutil.AccessDenied(1234)

        with patch('psutil.Process', return_value=mock_proc):
            # Should not raise
            wd._force_kill(1234, "cmd")


class TestWatchdogLogging:
    """Tests for watchdog logging behavior."""

    def test_register_logs_truncated_command(self):
        """Test register truncates command in debug log."""
        wd = CommandWatchdog()
        long_cmd = "z" * 100
        started = time.time()

        with patch('core.command_watchdog.logger') as mock_logger:
            wd.register(pid=1234, command=long_cmd, timeout=30, started_at=started)
            call_args = mock_logger.debug.call_args[0][0]
            # Should truncate to 50 chars
            assert len(call_args) < len(long_cmd) + 50

    def test_start_stop_logging_sequence(self):
        """Test start and stop log in correct sequence."""
        wd = CommandWatchdog(check_interval=1)

        log_calls = []

        def mock_info(msg):
            log_calls.append(msg)

        with patch('core.command_watchdog.logger') as mock_logger:
            mock_logger.info = mock_info

            wd.start()
            wd.stop()

        assert len(log_calls) == 2
        assert "started" in log_calls[0].lower()
        assert "stopped" in log_calls[1].lower()


class TestTimeBasedBehavior:
    """Tests for time-based behavior in watchdog."""

    def test_check_commands_uses_current_time(self):
        """Test _check_commands uses current time for age calculation."""
        wd = CommandWatchdog()

        # Register command "just now" but mock time to make it appear old
        real_started = time.time()
        wd.register(pid=1234, command="cmd", timeout=30, started_at=real_started)

        # Mock time.time() to return a value 100 seconds in the future
        with patch('time.time', return_value=real_started + 100):
            with patch.object(wd, '_force_kill') as mock_kill:
                wd._check_commands()
                mock_kill.assert_called_once()

    def test_grace_period_is_ten_seconds(self):
        """Test the grace period is exactly 10 seconds beyond timeout."""
        wd = CommandWatchdog()

        # timeout=30, grace=10, so kill after 40 seconds
        real_started = time.time()
        wd.register(pid=1234, command="cmd", timeout=30, started_at=real_started)

        # At 39 seconds - should NOT kill
        with patch('time.time', return_value=real_started + 39):
            with patch.object(wd, '_force_kill') as mock_kill:
                wd._check_commands()
                mock_kill.assert_not_called()

        # Reset killed flag for next test
        wd.active_commands[1234]["killed"] = False

        # At 41 seconds - should kill
        with patch('time.time', return_value=real_started + 41):
            with patch.object(wd, '_force_kill') as mock_kill:
                wd._check_commands()
                mock_kill.assert_called_once()


class TestStartStopIdempotency:
    """Tests for start/stop idempotency."""

    def test_multiple_starts_single_thread(self):
        """Test multiple start calls create only one thread."""
        wd = CommandWatchdog(check_interval=1)

        try:
            wd.start()
            thread1 = wd._thread

            wd.start()
            thread2 = wd._thread

            wd.start()
            thread3 = wd._thread

            assert thread1 is thread2 is thread3
        finally:
            wd.stop()

    def test_multiple_stops_no_error(self):
        """Test multiple stop calls do not cause error."""
        wd = CommandWatchdog(check_interval=1)

        wd.start()
        wd.stop()
        wd.stop()
        wd.stop()

        assert wd._running is False

    def test_start_after_stop(self):
        """Test watchdog can be restarted after being stopped."""
        wd = CommandWatchdog(check_interval=1)

        wd.start()
        assert wd._running is True
        old_thread = wd._thread

        wd.stop()
        assert wd._running is False

        wd.start()
        assert wd._running is True
        assert wd._thread is not old_thread  # New thread created


class TestCommandInfoStructure:
    """Tests for command info dictionary structure."""

    def test_registered_command_has_all_fields(self):
        """Test registered command has all required fields."""
        wd = CommandWatchdog()
        started = time.time()

        wd.register(pid=1234, command="test", timeout=60, started_at=started)

        info = wd.active_commands[1234]

        assert "command" in info
        assert "timeout" in info
        assert "started_at" in info
        assert "killed" in info

    def test_registered_command_field_types(self):
        """Test registered command fields have correct types."""
        wd = CommandWatchdog()
        started = time.time()

        wd.register(pid=1234, command="test", timeout=60, started_at=started)

        info = wd.active_commands[1234]

        assert isinstance(info["command"], str)
        assert isinstance(info["timeout"], (int, float))
        assert isinstance(info["started_at"], float)
        assert isinstance(info["killed"], bool)
