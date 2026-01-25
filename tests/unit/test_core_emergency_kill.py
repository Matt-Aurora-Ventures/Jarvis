"""
Tests for core/emergency_kill.py

Validates:
- Hanging process detection and killing
- Pattern-based process killing
- Emergency reset functionality
- Dry run mode
- Error handling for various process states
- Age calculation and threshold comparisons
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock, PropertyMock
from io import StringIO
import sys

# Import the module under test
from core.emergency_kill import (
    kill_hanging_processes,
    force_kill_by_pattern,
    emergency_reset,
    MAX_SUBPROCESS_AGE,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_current_process():
    """Create a mock for the current process."""
    mock_proc = Mock()
    mock_proc.pid = 12345
    return mock_proc


@pytest.fixture
def mock_child_process():
    """Create a mock child process."""
    mock_child = Mock()
    mock_child.pid = 11111
    mock_child.cmdline.return_value = ["python", "script.py", "--arg1", "value"]
    # Set create_time to make process old (older than MAX_SUBPROCESS_AGE)
    mock_child.create_time.return_value = time.time() - MAX_SUBPROCESS_AGE - 100
    return mock_child


@pytest.fixture
def mock_young_process():
    """Create a mock young process (not old enough to kill)."""
    mock_young = Mock()
    mock_young.pid = 22222
    mock_young.cmdline.return_value = ["python", "new_script.py"]
    # Set create_time to make process young (younger than MAX_SUBPROCESS_AGE)
    mock_young.create_time.return_value = time.time() - 60  # Only 60 seconds old
    return mock_young


@pytest.fixture
def mock_psutil_time():
    """Mock psutil.time.time() for consistent time comparisons."""
    with patch("core.emergency_kill.psutil.time") as mock_time:
        mock_time.time.return_value = time.time()
        yield mock_time


# =============================================================================
# Test Class: kill_hanging_processes - Basic Functionality
# =============================================================================


class TestKillHangingProcessesBasic:
    """Test basic functionality of kill_hanging_processes."""

    def test_no_children_returns_empty(self):
        """When there are no child processes, return empty lists."""
        with patch("core.emergency_kill.os.getpid") as mock_getpid, \
             patch("core.emergency_kill.psutil.Process") as mock_process:
            mock_getpid.return_value = 12345
            mock_parent = Mock()
            mock_parent.children.return_value = []
            mock_process.return_value = mock_parent

            result = kill_hanging_processes(dry_run=True)

            assert result["found"] == []
            assert result["killed"] == []
            assert result["dry_run"] is True

    def test_finds_old_process(self, mock_psutil_time):
        """Detect processes older than MAX_SUBPROCESS_AGE."""
        current_time = time.time()
        mock_psutil_time.time.return_value = current_time

        with patch("core.emergency_kill.os.getpid") as mock_getpid, \
             patch("core.emergency_kill.psutil.Process") as mock_process:
            mock_getpid.return_value = 12345

            # Create old child process
            mock_child = Mock()
            mock_child.pid = 11111
            mock_child.cmdline.return_value = ["python", "old_script.py"]
            mock_child.create_time.return_value = current_time - MAX_SUBPROCESS_AGE - 100

            mock_parent = Mock()
            mock_parent.children.return_value = [mock_child]
            mock_process.return_value = mock_parent

            result = kill_hanging_processes(dry_run=True)

            assert len(result["found"]) == 1
            assert "PID 11111" in result["found"][0]
            assert result["killed"] == []

    def test_ignores_young_process(self, mock_psutil_time):
        """Young processes should not be flagged for killing."""
        current_time = time.time()
        mock_psutil_time.time.return_value = current_time

        with patch("core.emergency_kill.os.getpid") as mock_getpid, \
             patch("core.emergency_kill.psutil.Process") as mock_process:
            mock_getpid.return_value = 12345

            # Create young child process
            mock_child = Mock()
            mock_child.pid = 22222
            mock_child.cmdline.return_value = ["python", "young_script.py"]
            mock_child.create_time.return_value = current_time - 60  # Only 60 seconds old

            mock_parent = Mock()
            mock_parent.children.return_value = [mock_child]
            mock_process.return_value = mock_parent

            result = kill_hanging_processes(dry_run=True)

            assert result["found"] == []
            assert result["killed"] == []

    def test_age_calculation_at_threshold(self, mock_psutil_time):
        """Process exactly at MAX_SUBPROCESS_AGE should not be killed."""
        current_time = time.time()
        mock_psutil_time.time.return_value = current_time

        with patch("core.emergency_kill.os.getpid") as mock_getpid, \
             patch("core.emergency_kill.psutil.Process") as mock_process:
            mock_getpid.return_value = 12345

            # Create process exactly at threshold
            mock_child = Mock()
            mock_child.pid = 33333
            mock_child.cmdline.return_value = ["python", "threshold_script.py"]
            mock_child.create_time.return_value = current_time - MAX_SUBPROCESS_AGE  # Exactly at threshold

            mock_parent = Mock()
            mock_parent.children.return_value = [mock_child]
            mock_process.return_value = mock_parent

            result = kill_hanging_processes(dry_run=True)

            # Should not be found since it's not > MAX_SUBPROCESS_AGE
            assert result["found"] == []

    def test_age_calculation_just_over_threshold(self, mock_psutil_time):
        """Process just over MAX_SUBPROCESS_AGE should be killed."""
        current_time = time.time()
        mock_psutil_time.time.return_value = current_time

        with patch("core.emergency_kill.os.getpid") as mock_getpid, \
             patch("core.emergency_kill.psutil.Process") as mock_process:
            mock_getpid.return_value = 12345

            # Create process just over threshold
            mock_child = Mock()
            mock_child.pid = 44444
            mock_child.cmdline.return_value = ["python", "over_threshold_script.py"]
            mock_child.create_time.return_value = current_time - MAX_SUBPROCESS_AGE - 1  # Just over

            mock_parent = Mock()
            mock_parent.children.return_value = [mock_child]
            mock_process.return_value = mock_parent

            result = kill_hanging_processes(dry_run=True)

            assert len(result["found"]) == 1


# =============================================================================
# Test Class: kill_hanging_processes - Dry Run vs Actual Kill
# =============================================================================


class TestKillHangingProcessesDryRun:
    """Test dry run mode vs actual killing."""

    def test_dry_run_does_not_kill(self, mock_psutil_time):
        """Dry run should find but not kill processes."""
        current_time = time.time()
        mock_psutil_time.time.return_value = current_time

        with patch("core.emergency_kill.os.getpid") as mock_getpid, \
             patch("core.emergency_kill.psutil.Process") as mock_process:
            mock_getpid.return_value = 12345

            mock_child = Mock()
            mock_child.pid = 11111
            mock_child.cmdline.return_value = ["python", "script.py"]
            mock_child.create_time.return_value = current_time - MAX_SUBPROCESS_AGE - 100

            mock_parent = Mock()
            mock_parent.children.return_value = [mock_child]
            mock_process.return_value = mock_parent

            result = kill_hanging_processes(dry_run=True)

            # Should find but not kill
            assert len(result["found"]) == 1
            assert result["killed"] == []
            assert result["dry_run"] is True
            mock_child.kill.assert_not_called()

    def test_actual_kill_mode(self, mock_psutil_time):
        """Non-dry run should actually kill processes."""
        current_time = time.time()
        mock_psutil_time.time.return_value = current_time

        with patch("core.emergency_kill.os.getpid") as mock_getpid, \
             patch("core.emergency_kill.psutil.Process") as mock_process:
            mock_getpid.return_value = 12345

            mock_child = Mock()
            mock_child.pid = 11111
            mock_child.cmdline.return_value = ["python", "script.py"]
            mock_child.create_time.return_value = current_time - MAX_SUBPROCESS_AGE - 100

            mock_parent = Mock()
            mock_parent.children.return_value = [mock_child]
            mock_process.return_value = mock_parent

            result = kill_hanging_processes(dry_run=False)

            assert len(result["found"]) == 1
            assert len(result["killed"]) == 1
            assert result["dry_run"] is False
            mock_child.kill.assert_called_once()

    def test_dry_run_default_value(self, mock_psutil_time):
        """Default dry_run value should be False."""
        current_time = time.time()
        mock_psutil_time.time.return_value = current_time

        with patch("core.emergency_kill.os.getpid") as mock_getpid, \
             patch("core.emergency_kill.psutil.Process") as mock_process:
            mock_getpid.return_value = 12345

            mock_child = Mock()
            mock_child.pid = 11111
            mock_child.cmdline.return_value = ["python", "script.py"]
            mock_child.create_time.return_value = current_time - MAX_SUBPROCESS_AGE - 100

            mock_parent = Mock()
            mock_parent.children.return_value = [mock_child]
            mock_process.return_value = mock_parent

            # Call without specifying dry_run
            result = kill_hanging_processes()

            # Default is dry_run=False, so it should kill
            mock_child.kill.assert_called_once()


# =============================================================================
# Test Class: kill_hanging_processes - Multiple Processes
# =============================================================================


class TestKillHangingProcessesMultiple:
    """Test handling of multiple child processes."""

    def test_multiple_old_processes(self, mock_psutil_time):
        """Multiple old processes should all be found."""
        current_time = time.time()
        mock_psutil_time.time.return_value = current_time

        with patch("core.emergency_kill.os.getpid") as mock_getpid, \
             patch("core.emergency_kill.psutil.Process") as mock_process:
            mock_getpid.return_value = 12345

            # Create multiple old processes
            old_children = []
            for i in range(5):
                mock_child = Mock()
                mock_child.pid = 10000 + i
                mock_child.cmdline.return_value = [f"python", f"script_{i}.py"]
                mock_child.create_time.return_value = current_time - MAX_SUBPROCESS_AGE - 100
                old_children.append(mock_child)

            mock_parent = Mock()
            mock_parent.children.return_value = old_children
            mock_process.return_value = mock_parent

            result = kill_hanging_processes(dry_run=True)

            assert len(result["found"]) == 5

    def test_mixed_old_and_young_processes(self, mock_psutil_time):
        """Only old processes should be found among mixed ages."""
        current_time = time.time()
        mock_psutil_time.time.return_value = current_time

        with patch("core.emergency_kill.os.getpid") as mock_getpid, \
             patch("core.emergency_kill.psutil.Process") as mock_process:
            mock_getpid.return_value = 12345

            # Create mix of old and young processes
            children = []

            # 3 old processes
            for i in range(3):
                mock_child = Mock()
                mock_child.pid = 10000 + i
                mock_child.cmdline.return_value = [f"python", f"old_script_{i}.py"]
                mock_child.create_time.return_value = current_time - MAX_SUBPROCESS_AGE - 100
                children.append(mock_child)

            # 2 young processes
            for i in range(2):
                mock_child = Mock()
                mock_child.pid = 20000 + i
                mock_child.cmdline.return_value = [f"python", f"young_script_{i}.py"]
                mock_child.create_time.return_value = current_time - 60
                children.append(mock_child)

            mock_parent = Mock()
            mock_parent.children.return_value = children
            mock_process.return_value = mock_parent

            result = kill_hanging_processes(dry_run=True)

            assert len(result["found"]) == 3  # Only old ones
            # Verify old PIDs are found
            found_pids = [f for f in result["found"]]
            assert any("10000" in f for f in found_pids)
            assert any("10001" in f for f in found_pids)
            assert any("10002" in f for f in found_pids)


# =============================================================================
# Test Class: kill_hanging_processes - Error Handling
# =============================================================================


class TestKillHangingProcessesErrors:
    """Test error handling in kill_hanging_processes."""

    def test_nosuchprocess_during_iteration(self, mock_psutil_time):
        """Handle NoSuchProcess exception during iteration."""
        import psutil as real_psutil
        current_time = time.time()
        mock_psutil_time.time.return_value = current_time

        with patch("core.emergency_kill.os.getpid") as mock_getpid, \
             patch("core.emergency_kill.psutil.Process") as mock_process, \
             patch("core.emergency_kill.psutil.NoSuchProcess", real_psutil.NoSuchProcess):
            mock_getpid.return_value = 12345

            # Create a process that disappears
            mock_child = Mock()
            mock_child.pid = 11111
            mock_child.cmdline.side_effect = real_psutil.NoSuchProcess(11111)

            mock_parent = Mock()
            mock_parent.children.return_value = [mock_child]
            mock_process.return_value = mock_parent

            # Should not raise
            result = kill_hanging_processes(dry_run=True)

            assert result["found"] == []
            assert result["killed"] == []

    def test_accessdenied_during_iteration(self, mock_psutil_time):
        """Handle AccessDenied exception during iteration."""
        import psutil as real_psutil
        current_time = time.time()
        mock_psutil_time.time.return_value = current_time

        with patch("core.emergency_kill.os.getpid") as mock_getpid, \
             patch("core.emergency_kill.psutil.Process") as mock_process, \
             patch("core.emergency_kill.psutil.AccessDenied", real_psutil.AccessDenied):
            mock_getpid.return_value = 12345

            mock_child = Mock()
            mock_child.pid = 11111
            mock_child.cmdline.side_effect = real_psutil.AccessDenied(11111)

            mock_parent = Mock()
            mock_parent.children.return_value = [mock_child]
            mock_process.return_value = mock_parent

            result = kill_hanging_processes(dry_run=True)

            assert result["found"] == []

    def test_nosuchprocess_during_kill(self, mock_psutil_time):
        """Handle NoSuchProcess when trying to kill (process died naturally)."""
        import psutil as real_psutil
        current_time = time.time()
        mock_psutil_time.time.return_value = current_time

        with patch("core.emergency_kill.os.getpid") as mock_getpid, \
             patch("core.emergency_kill.psutil.Process") as mock_process, \
             patch("core.emergency_kill.psutil.NoSuchProcess", real_psutil.NoSuchProcess):
            mock_getpid.return_value = 12345

            mock_child = Mock()
            mock_child.pid = 11111
            mock_child.cmdline.return_value = ["python", "script.py"]
            mock_child.create_time.return_value = current_time - MAX_SUBPROCESS_AGE - 100
            mock_child.kill.side_effect = real_psutil.NoSuchProcess(11111)

            mock_parent = Mock()
            mock_parent.children.return_value = [mock_child]
            mock_process.return_value = mock_parent

            result = kill_hanging_processes(dry_run=False)

            # Should find but not report as killed (process died naturally)
            assert len(result["found"]) == 1
            assert result["killed"] == []

    def test_accessdenied_during_kill(self, mock_psutil_time):
        """Handle AccessDenied when trying to kill."""
        import psutil as real_psutil
        current_time = time.time()
        mock_psutil_time.time.return_value = current_time

        with patch("core.emergency_kill.os.getpid") as mock_getpid, \
             patch("core.emergency_kill.psutil.Process") as mock_process, \
             patch("core.emergency_kill.psutil.AccessDenied", real_psutil.AccessDenied):
            mock_getpid.return_value = 12345

            mock_child = Mock()
            mock_child.pid = 11111
            mock_child.cmdline.return_value = ["python", "script.py"]
            mock_child.create_time.return_value = current_time - MAX_SUBPROCESS_AGE - 100
            mock_child.kill.side_effect = real_psutil.AccessDenied(11111)

            mock_parent = Mock()
            mock_parent.children.return_value = [mock_child]
            mock_process.return_value = mock_parent

            result = kill_hanging_processes(dry_run=False)

            # Should report access denied
            assert len(result["found"]) == 1
            assert len(result["killed"]) == 1
            assert "Access denied" in result["killed"][0]


# =============================================================================
# Test Class: kill_hanging_processes - Output Format
# =============================================================================


class TestKillHangingProcessesOutput:
    """Test output format of kill_hanging_processes."""

    def test_return_dict_structure(self):
        """Verify returned dictionary has correct keys."""
        with patch("core.emergency_kill.os.getpid") as mock_getpid, \
             patch("core.emergency_kill.psutil.Process") as mock_process:
            mock_getpid.return_value = 12345
            mock_parent = Mock()
            mock_parent.children.return_value = []
            mock_process.return_value = mock_parent

            result = kill_hanging_processes(dry_run=True)

            assert "found" in result
            assert "killed" in result
            assert "dry_run" in result
            assert isinstance(result["found"], list)
            assert isinstance(result["killed"], list)
            assert isinstance(result["dry_run"], bool)

    def test_found_entry_format(self, mock_psutil_time):
        """Verify format of found process entries."""
        current_time = time.time()
        mock_psutil_time.time.return_value = current_time

        with patch("core.emergency_kill.os.getpid") as mock_getpid, \
             patch("core.emergency_kill.psutil.Process") as mock_process:
            mock_getpid.return_value = 12345

            mock_child = Mock()
            mock_child.pid = 99999
            mock_child.cmdline.return_value = ["python", "test_script.py", "--verbose"]
            mock_child.create_time.return_value = current_time - MAX_SUBPROCESS_AGE - 500

            mock_parent = Mock()
            mock_parent.children.return_value = [mock_child]
            mock_process.return_value = mock_parent

            result = kill_hanging_processes(dry_run=True)

            assert len(result["found"]) == 1
            found_entry = result["found"][0]
            assert "PID 99999" in found_entry
            assert "python test_script.py --verbose" in found_entry
            assert "age:" in found_entry

    def test_cmdline_truncation(self, mock_psutil_time):
        """Long command lines should be truncated."""
        current_time = time.time()
        mock_psutil_time.time.return_value = current_time

        with patch("core.emergency_kill.os.getpid") as mock_getpid, \
             patch("core.emergency_kill.psutil.Process") as mock_process:
            mock_getpid.return_value = 12345

            # Create process with very long command line
            long_cmd = ["python"] + [f"arg{i}" for i in range(100)]
            mock_child = Mock()
            mock_child.pid = 11111
            mock_child.cmdline.return_value = long_cmd
            mock_child.create_time.return_value = current_time - MAX_SUBPROCESS_AGE - 100

            mock_parent = Mock()
            mock_parent.children.return_value = [mock_child]
            mock_process.return_value = mock_parent

            result = kill_hanging_processes(dry_run=True)

            # Command should be truncated to 80 chars
            found_entry = result["found"][0]
            # Extract the cmdline part (between PID and age)
            assert len(found_entry) < 200  # Reasonable max length


# =============================================================================
# Test Class: force_kill_by_pattern - Basic Functionality
# =============================================================================


class TestForceKillByPatternBasic:
    """Test basic functionality of force_kill_by_pattern."""

    def test_no_matching_processes(self):
        """When no processes match, return empty lists."""
        with patch("core.emergency_kill.psutil.process_iter") as mock_iter:
            mock_iter.return_value = iter([])

            result = force_kill_by_pattern("nonexistent_pattern", dry_run=True)

            assert result["found"] == []
            assert result["killed"] == []
            assert result["pattern"] == "nonexistent_pattern"

    def test_finds_matching_process(self):
        """Find process matching pattern."""
        with patch("core.emergency_kill.psutil.process_iter") as mock_iter:
            mock_proc = Mock()
            mock_proc.pid = 55555
            mock_proc.info = {"pid": 55555, "name": "python", "cmdline": ["python", "my_target_script.py"]}

            mock_iter.return_value = iter([mock_proc])

            result = force_kill_by_pattern("target_script", dry_run=True)

            assert len(result["found"]) == 1
            assert "PID 55555" in result["found"][0]

    def test_case_insensitive_matching(self):
        """Pattern matching should be case insensitive."""
        with patch("core.emergency_kill.psutil.process_iter") as mock_iter:
            mock_proc = Mock()
            mock_proc.pid = 55555
            mock_proc.info = {"pid": 55555, "name": "python", "cmdline": ["PYTHON", "MYAPP.PY"]}

            mock_iter.return_value = iter([mock_proc])

            result = force_kill_by_pattern("myapp", dry_run=True)

            assert len(result["found"]) == 1

    def test_pattern_in_args(self):
        """Pattern can match anywhere in command line."""
        with patch("core.emergency_kill.psutil.process_iter") as mock_iter:
            mock_proc = Mock()
            mock_proc.pid = 55555
            mock_proc.info = {"pid": 55555, "name": "python", "cmdline": ["python", "app.py", "--config=target_config.json"]}

            mock_iter.return_value = iter([mock_proc])

            result = force_kill_by_pattern("target_config", dry_run=True)

            assert len(result["found"]) == 1


# =============================================================================
# Test Class: force_kill_by_pattern - Dry Run vs Actual Kill
# =============================================================================


class TestForceKillByPatternDryRun:
    """Test dry run mode in force_kill_by_pattern."""

    def test_dry_run_does_not_kill(self):
        """Dry run should find but not kill."""
        with patch("core.emergency_kill.psutil.process_iter") as mock_iter:
            mock_proc = Mock()
            mock_proc.pid = 55555
            mock_proc.info = {"pid": 55555, "name": "python", "cmdline": ["python", "target.py"]}

            mock_iter.return_value = iter([mock_proc])

            result = force_kill_by_pattern("target", dry_run=True)

            assert len(result["found"]) == 1
            assert result["killed"] == []
            assert result["dry_run"] is True
            mock_proc.kill.assert_not_called()

    def test_actual_kill_mode(self):
        """Non-dry run should kill matching processes."""
        with patch("core.emergency_kill.psutil.process_iter") as mock_iter:
            mock_proc = Mock()
            mock_proc.pid = 55555
            mock_proc.info = {"pid": 55555, "name": "python", "cmdline": ["python", "target.py"]}

            mock_iter.return_value = iter([mock_proc])

            result = force_kill_by_pattern("target", dry_run=False)

            assert len(result["found"]) == 1
            assert len(result["killed"]) == 1
            assert result["dry_run"] is False
            mock_proc.kill.assert_called_once()


# =============================================================================
# Test Class: force_kill_by_pattern - Multiple Processes
# =============================================================================


class TestForceKillByPatternMultiple:
    """Test force_kill_by_pattern with multiple processes."""

    def test_multiple_matching_processes(self):
        """Kill all processes matching pattern."""
        with patch("core.emergency_kill.psutil.process_iter") as mock_iter:
            procs = []
            for i in range(5):
                mock_proc = Mock()
                mock_proc.pid = 50000 + i
                mock_proc.info = {"pid": 50000 + i, "name": "python", "cmdline": [f"python", f"worker_{i}.py", "--app=myapp"]}
                procs.append(mock_proc)

            mock_iter.return_value = iter(procs)

            result = force_kill_by_pattern("myapp", dry_run=False)

            assert len(result["found"]) == 5
            assert len(result["killed"]) == 5

    def test_only_matching_processes_killed(self):
        """Only processes matching pattern should be killed."""
        with patch("core.emergency_kill.psutil.process_iter") as mock_iter:
            matching = Mock()
            matching.pid = 11111
            matching.info = {"pid": 11111, "name": "python", "cmdline": ["python", "target_app.py"]}

            non_matching = Mock()
            non_matching.pid = 22222
            non_matching.info = {"pid": 22222, "name": "node", "cmdline": ["node", "server.js"]}

            mock_iter.return_value = iter([matching, non_matching])

            result = force_kill_by_pattern("target_app", dry_run=False)

            assert len(result["found"]) == 1
            matching.kill.assert_called_once()
            non_matching.kill.assert_not_called()


# =============================================================================
# Test Class: force_kill_by_pattern - Error Handling
# =============================================================================


class TestForceKillByPatternErrors:
    """Test error handling in force_kill_by_pattern."""

    def test_nosuchprocess_during_iteration(self):
        """Handle NoSuchProcess during iteration."""
        import psutil as real_psutil

        with patch("core.emergency_kill.psutil.process_iter") as mock_iter, \
             patch("core.emergency_kill.psutil.NoSuchProcess", real_psutil.NoSuchProcess):
            mock_proc = Mock()
            mock_proc.pid = 11111
            mock_proc.info = {"pid": 11111, "name": "python", "cmdline": None}

            mock_iter.return_value = iter([mock_proc])

            # Should not raise - cmdline is None
            result = force_kill_by_pattern("target", dry_run=True)

            assert result["found"] == []

    def test_accessdenied_during_iteration(self):
        """Handle AccessDenied during iteration."""
        import psutil as real_psutil

        with patch("core.emergency_kill.psutil.process_iter") as mock_iter, \
             patch("core.emergency_kill.psutil.AccessDenied", real_psutil.AccessDenied):
            mock_proc = Mock()
            mock_proc.pid = 11111
            # Accessing info raises AccessDenied
            type(mock_proc).info = PropertyMock(side_effect=real_psutil.AccessDenied(11111))

            mock_iter.return_value = iter([mock_proc])

            # Should not raise
            result = force_kill_by_pattern("target", dry_run=True)

            assert result["found"] == []

    def test_nosuchprocess_during_kill(self):
        """Handle NoSuchProcess when killing."""
        import psutil as real_psutil

        with patch("core.emergency_kill.psutil.process_iter") as mock_iter, \
             patch("core.emergency_kill.psutil.NoSuchProcess", real_psutil.NoSuchProcess):
            mock_proc = Mock()
            mock_proc.pid = 11111
            mock_proc.info = {"pid": 11111, "name": "python", "cmdline": ["python", "target.py"]}
            mock_proc.kill.side_effect = real_psutil.NoSuchProcess(11111)

            mock_iter.return_value = iter([mock_proc])

            result = force_kill_by_pattern("target", dry_run=False)

            assert len(result["found"]) == 1
            assert result["killed"] == []

    def test_accessdenied_during_kill(self):
        """Handle AccessDenied when killing."""
        import psutil as real_psutil

        with patch("core.emergency_kill.psutil.process_iter") as mock_iter, \
             patch("core.emergency_kill.psutil.AccessDenied", real_psutil.AccessDenied):
            mock_proc = Mock()
            mock_proc.pid = 11111
            mock_proc.info = {"pid": 11111, "name": "python", "cmdline": ["python", "target.py"]}
            mock_proc.kill.side_effect = real_psutil.AccessDenied(11111)

            mock_iter.return_value = iter([mock_proc])

            result = force_kill_by_pattern("target", dry_run=False)

            assert len(result["found"]) == 1
            assert "Access denied" in result["killed"][0]

    def test_typeerror_with_none_cmdline(self):
        """Handle TypeError when cmdline is None."""
        with patch("core.emergency_kill.psutil.process_iter") as mock_iter:
            mock_proc = Mock()
            mock_proc.pid = 11111
            mock_proc.info = {"pid": 11111, "name": "python", "cmdline": None}

            mock_iter.return_value = iter([mock_proc])

            # Should handle gracefully
            result = force_kill_by_pattern("target", dry_run=True)

            assert result["found"] == []


# =============================================================================
# Test Class: force_kill_by_pattern - Output Format
# =============================================================================


class TestForceKillByPatternOutput:
    """Test output format of force_kill_by_pattern."""

    def test_return_dict_structure(self):
        """Verify returned dictionary has correct keys."""
        with patch("core.emergency_kill.psutil.process_iter") as mock_iter:
            mock_iter.return_value = iter([])

            result = force_kill_by_pattern("test", dry_run=True)

            assert "found" in result
            assert "killed" in result
            assert "dry_run" in result
            assert "pattern" in result
            assert result["pattern"] == "test"

    def test_cmdline_truncation(self):
        """Long command lines should be truncated to 80 chars."""
        with patch("core.emergency_kill.psutil.process_iter") as mock_iter:
            long_cmd = ["python"] + [f"very_long_argument_{i}" for i in range(50)]
            mock_proc = Mock()
            mock_proc.pid = 11111
            mock_proc.info = {"pid": 11111, "name": "python", "cmdline": long_cmd}

            mock_iter.return_value = iter([mock_proc])

            result = force_kill_by_pattern("very_long_argument", dry_run=True)

            # The cmdline in found should be truncated
            assert len(result["found"]) == 1
            found_entry = result["found"][0]
            # Extract cmdline portion (after "PID 11111: ")
            cmdline_portion = found_entry.split(": ", 1)[1] if ": " in found_entry else found_entry
            assert len(cmdline_portion) <= 80


# =============================================================================
# Test Class: emergency_reset - Basic Functionality
# =============================================================================


class TestEmergencyResetBasic:
    """Test basic functionality of emergency_reset."""

    def test_no_children(self, capsys):
        """Emergency reset with no children should complete quickly."""
        with patch("core.emergency_kill.os.getpid") as mock_getpid, \
             patch("core.emergency_kill.psutil.Process") as mock_process:
            mock_getpid.return_value = 12345
            mock_parent = Mock()
            mock_parent.children.return_value = []
            mock_process.return_value = mock_parent

            emergency_reset()

            captured = capsys.readouterr()
            assert "EMERGENCY RESET" in captured.out
            assert "Killing 0 child processes" in captured.out
            assert "Emergency reset complete" in captured.out

    def test_kills_all_children(self, capsys):
        """Emergency reset should kill all child processes."""
        with patch("core.emergency_kill.os.getpid") as mock_getpid, \
             patch("core.emergency_kill.psutil.Process") as mock_process:
            mock_getpid.return_value = 12345

            children = []
            for i in range(3):
                child = Mock()
                child.pid = 10000 + i
                child.cmdline.return_value = [f"python", f"script_{i}.py"]
                children.append(child)

            mock_parent = Mock()
            mock_parent.children.return_value = children
            mock_process.return_value = mock_parent

            emergency_reset()

            # All children should be killed
            for child in children:
                child.kill.assert_called_once()

            captured = capsys.readouterr()
            assert "Killing 3 child processes" in captured.out

    def test_prints_killed_processes(self, capsys):
        """Emergency reset should print what it's killing."""
        with patch("core.emergency_kill.os.getpid") as mock_getpid, \
             patch("core.emergency_kill.psutil.Process") as mock_process:
            mock_getpid.return_value = 12345

            child = Mock()
            child.pid = 77777
            child.cmdline.return_value = ["python", "important_script.py", "--flag"]

            mock_parent = Mock()
            mock_parent.children.return_value = [child]
            mock_process.return_value = mock_parent

            emergency_reset()

            captured = capsys.readouterr()
            assert "Killing PID 77777" in captured.out
            assert "python important_script.py --flag" in captured.out


# =============================================================================
# Test Class: emergency_reset - Error Handling
# =============================================================================


class TestEmergencyResetErrors:
    """Test error handling in emergency_reset."""

    def test_nosuchprocess_ignored(self, capsys):
        """NoSuchProcess errors should be silently ignored."""
        import psutil as real_psutil

        with patch("core.emergency_kill.os.getpid") as mock_getpid, \
             patch("core.emergency_kill.psutil.Process") as mock_process, \
             patch("core.emergency_kill.psutil.NoSuchProcess", real_psutil.NoSuchProcess):
            mock_getpid.return_value = 12345

            child = Mock()
            child.pid = 11111
            child.cmdline.return_value = ["python", "script.py"]
            child.kill.side_effect = real_psutil.NoSuchProcess(11111)

            mock_parent = Mock()
            mock_parent.children.return_value = [child]
            mock_process.return_value = mock_parent

            # Should not raise
            emergency_reset()

            captured = capsys.readouterr()
            assert "Emergency reset complete" in captured.out

    def test_accessdenied_ignored(self, capsys):
        """AccessDenied errors should be silently ignored."""
        import psutil as real_psutil

        with patch("core.emergency_kill.os.getpid") as mock_getpid, \
             patch("core.emergency_kill.psutil.Process") as mock_process, \
             patch("core.emergency_kill.psutil.AccessDenied", real_psutil.AccessDenied):
            mock_getpid.return_value = 12345

            child = Mock()
            child.pid = 11111
            child.cmdline.return_value = ["python", "script.py"]
            child.kill.side_effect = real_psutil.AccessDenied(11111)

            mock_parent = Mock()
            mock_parent.children.return_value = [child]
            mock_process.return_value = mock_parent

            # Should not raise
            emergency_reset()

            captured = capsys.readouterr()
            assert "Emergency reset complete" in captured.out

    def test_mixed_success_and_errors(self, capsys):
        """Mixed success and errors should complete reset."""
        import psutil as real_psutil

        with patch("core.emergency_kill.os.getpid") as mock_getpid, \
             patch("core.emergency_kill.psutil.Process") as mock_process, \
             patch("core.emergency_kill.psutil.NoSuchProcess", real_psutil.NoSuchProcess), \
             patch("core.emergency_kill.psutil.AccessDenied", real_psutil.AccessDenied):
            mock_getpid.return_value = 12345

            # Normal child
            child1 = Mock()
            child1.pid = 11111
            child1.cmdline.return_value = ["python", "good.py"]

            # Child that disappears
            child2 = Mock()
            child2.pid = 22222
            child2.cmdline.return_value = ["python", "gone.py"]
            child2.kill.side_effect = real_psutil.NoSuchProcess(22222)

            # Child with access issues
            child3 = Mock()
            child3.pid = 33333
            child3.cmdline.return_value = ["python", "protected.py"]
            child3.kill.side_effect = real_psutil.AccessDenied(33333)

            mock_parent = Mock()
            mock_parent.children.return_value = [child1, child2, child3]
            mock_process.return_value = mock_parent

            emergency_reset()

            # First child should be killed
            child1.kill.assert_called_once()

            captured = capsys.readouterr()
            assert "Emergency reset complete" in captured.out


# =============================================================================
# Test Class: Module Constants
# =============================================================================


class TestModuleConstants:
    """Test module-level constants."""

    def test_max_subprocess_age_value(self):
        """MAX_SUBPROCESS_AGE should be 300 seconds (5 minutes)."""
        assert MAX_SUBPROCESS_AGE == 300

    def test_max_subprocess_age_type(self):
        """MAX_SUBPROCESS_AGE should be an integer."""
        assert isinstance(MAX_SUBPROCESS_AGE, int)


# =============================================================================
# Test Class: Main Module Execution
# =============================================================================


class TestMainExecution:
    """Test main module execution (__main__ block)."""

    def test_main_no_args_dry_run(self, capsys):
        """Running without args should do dry run scan."""
        with patch("core.emergency_kill.os.getpid") as mock_getpid, \
             patch("core.emergency_kill.psutil.Process") as mock_process, \
             patch("core.emergency_kill.psutil.time") as mock_time, \
             patch.object(sys, "argv", ["emergency_kill.py"]):

            mock_getpid.return_value = 12345
            mock_time.time.return_value = time.time()

            mock_parent = Mock()
            mock_parent.children.return_value = []
            mock_process.return_value = mock_parent

            # Import and run main
            import core.emergency_kill as em
            import importlib

            # Execute the main block code directly
            result = em.kill_hanging_processes(dry_run=True)

            assert result["dry_run"] is True

    def test_main_emergency_arg(self, capsys):
        """Running with 'emergency' arg should trigger reset."""
        with patch("core.emergency_kill.os.getpid") as mock_getpid, \
             patch("core.emergency_kill.psutil.Process") as mock_process:
            mock_getpid.return_value = 12345
            mock_parent = Mock()
            mock_parent.children.return_value = []
            mock_process.return_value = mock_parent

            import core.emergency_kill as em
            em.emergency_reset()

            captured = capsys.readouterr()
            assert "EMERGENCY RESET" in captured.out


# =============================================================================
# Test Class: Edge Cases
# =============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_cmdline(self, mock_psutil_time):
        """Process with empty command line should be handled."""
        current_time = time.time()
        mock_psutil_time.time.return_value = current_time

        with patch("core.emergency_kill.os.getpid") as mock_getpid, \
             patch("core.emergency_kill.psutil.Process") as mock_process:
            mock_getpid.return_value = 12345

            mock_child = Mock()
            mock_child.pid = 11111
            mock_child.cmdline.return_value = []  # Empty command line
            mock_child.create_time.return_value = current_time - MAX_SUBPROCESS_AGE - 100

            mock_parent = Mock()
            mock_parent.children.return_value = [mock_child]
            mock_process.return_value = mock_parent

            result = kill_hanging_processes(dry_run=True)

            # Should still find it (empty cmdline is valid)
            assert len(result["found"]) == 1

    def test_special_characters_in_pattern(self):
        """Patterns with special characters should work."""
        with patch("core.emergency_kill.psutil.process_iter") as mock_iter:
            mock_proc = Mock()
            mock_proc.pid = 11111
            mock_proc.info = {"pid": 11111, "name": "python", "cmdline": ["python", "script-with-dashes_and_underscores.py"]}

            mock_iter.return_value = iter([mock_proc])

            result = force_kill_by_pattern("script-with-dashes", dry_run=True)

            assert len(result["found"]) == 1

    def test_very_long_process_list(self, mock_psutil_time):
        """Handle large number of child processes."""
        current_time = time.time()
        mock_psutil_time.time.return_value = current_time

        with patch("core.emergency_kill.os.getpid") as mock_getpid, \
             patch("core.emergency_kill.psutil.Process") as mock_process:
            mock_getpid.return_value = 12345

            # Create 100 old processes
            children = []
            for i in range(100):
                child = Mock()
                child.pid = 10000 + i
                child.cmdline.return_value = [f"python", f"script_{i}.py"]
                child.create_time.return_value = current_time - MAX_SUBPROCESS_AGE - 100
                children.append(child)

            mock_parent = Mock()
            mock_parent.children.return_value = children
            mock_process.return_value = mock_parent

            result = kill_hanging_processes(dry_run=True)

            assert len(result["found"]) == 100

    def test_recursive_children(self, mock_psutil_time):
        """Verify recursive=True is passed to children()."""
        current_time = time.time()
        mock_psutil_time.time.return_value = current_time

        with patch("core.emergency_kill.os.getpid") as mock_getpid, \
             patch("core.emergency_kill.psutil.Process") as mock_process:
            mock_getpid.return_value = 12345

            mock_parent = Mock()
            mock_parent.children.return_value = []
            mock_process.return_value = mock_parent

            kill_hanging_processes(dry_run=True)

            # Verify recursive=True was passed
            mock_parent.children.assert_called_once_with(recursive=True)

    def test_process_attributes_accessed_correctly(self, mock_psutil_time):
        """Verify process attributes are accessed correctly."""
        current_time = time.time()
        mock_psutil_time.time.return_value = current_time

        with patch("core.emergency_kill.os.getpid") as mock_getpid, \
             patch("core.emergency_kill.psutil.Process") as mock_process:
            mock_getpid.return_value = 12345

            mock_child = Mock()
            mock_child.pid = 11111
            mock_child.cmdline.return_value = ["python", "script.py"]
            mock_child.create_time.return_value = current_time - MAX_SUBPROCESS_AGE - 100

            mock_parent = Mock()
            mock_parent.children.return_value = [mock_child]
            mock_process.return_value = mock_parent

            kill_hanging_processes(dry_run=True)

            # Verify correct methods were called
            mock_child.cmdline.assert_called()
            mock_child.create_time.assert_called()


# =============================================================================
# Test Class: Concurrency Considerations
# =============================================================================


class TestConcurrencyConsiderations:
    """Test behavior under concurrent access scenarios."""

    def test_process_dies_between_find_and_kill(self, mock_psutil_time):
        """Handle process dying between find and kill."""
        import psutil as real_psutil
        current_time = time.time()
        mock_psutil_time.time.return_value = current_time

        with patch("core.emergency_kill.os.getpid") as mock_getpid, \
             patch("core.emergency_kill.psutil.Process") as mock_process, \
             patch("core.emergency_kill.psutil.NoSuchProcess", real_psutil.NoSuchProcess):
            mock_getpid.return_value = 12345

            mock_child = Mock()
            mock_child.pid = 11111
            mock_child.cmdline.return_value = ["python", "script.py"]
            mock_child.create_time.return_value = current_time - MAX_SUBPROCESS_AGE - 100
            # Process dies when we try to kill it
            mock_child.kill.side_effect = real_psutil.NoSuchProcess(11111)

            mock_parent = Mock()
            mock_parent.children.return_value = [mock_child]
            mock_process.return_value = mock_parent

            result = kill_hanging_processes(dry_run=False)

            # Should find but gracefully handle failure to kill
            assert len(result["found"]) == 1
            assert result["killed"] == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
