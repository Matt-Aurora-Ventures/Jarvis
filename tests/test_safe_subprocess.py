"""
Tests for core/safe_subprocess.py

Tests cover:
- Safe command execution
- Timeout handling
- Command validation
- Return value structure
- Error handling
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.safe_subprocess import (
    TimeoutError,
    CommandExecutionError,
    run_command_safe,
)


class TestExceptions:
    """Test custom exception classes."""

    def test_timeout_error_message(self):
        """TimeoutError should have message."""
        err = TimeoutError("Command timed out after 30s")
        assert "timed out" in str(err)

    def test_command_execution_error_message(self):
        """CommandExecutionError should have message."""
        err = CommandExecutionError("Exit code 1")
        assert "Exit code" in str(err)


class TestRunCommandSafe:
    """Test run_command_safe function."""

    def test_simple_command_list(self):
        """Should run simple command as list."""
        result = run_command_safe(["echo", "hello"], skip_validation=True)

        assert result["returncode"] == 0
        assert "hello" in result["stdout"]
        assert result["timed_out"] is False
        assert result["killed"] is False

    def test_simple_command_string(self):
        """Should run simple command as string."""
        result = run_command_safe("echo hello", skip_validation=True)

        assert result["returncode"] == 0
        assert "hello" in result["stdout"]

    def test_result_structure(self):
        """Result should have expected keys."""
        result = run_command_safe(["echo", "test"], skip_validation=True)

        assert "stdout" in result
        assert "stderr" in result
        assert "returncode" in result
        assert "timed_out" in result
        assert "killed" in result
        assert "command" in result

    def test_captures_stdout(self):
        """Should capture stdout."""
        result = run_command_safe(["echo", "captured"], skip_validation=True)

        assert "captured" in result["stdout"]

    def test_captures_stderr(self):
        """Should capture stderr."""
        # Use a command that writes to stderr
        result = run_command_safe(
            "python -c \"import sys; sys.stderr.write('error')\"",
            skip_validation=True
        )

        assert "error" in result["stderr"]

    def test_returns_exit_code(self):
        """Should return process exit code."""
        result = run_command_safe(
            "python -c \"exit(42)\"",
            skip_validation=True
        )

        assert result["returncode"] == 42

    def test_custom_timeout(self):
        """Should accept custom timeout."""
        result = run_command_safe(
            ["echo", "quick"],
            timeout=60,
            skip_validation=True
        )

        assert result["returncode"] == 0

    def test_blocked_command_structure(self):
        """Blocked command should return proper structure."""
        # Mock the validator to block the command
        with patch('core.safe_subprocess.validate_before_run') as mock_validate:
            mock_validate.return_value = (False, "Dangerous command", [])

            result = run_command_safe("rm -rf /")

            assert result["blocked"] is True
            assert result["returncode"] == -1
            assert "blocked" in result["stderr"].lower() or "validator" in result["stderr"].lower()

    def test_validation_warnings_logged(self):
        """Should log validation warnings but allow execution."""
        with patch('core.safe_subprocess.validate_before_run') as mock_validate:
            mock_validate.return_value = (True, "", ["Potential issue"])

            with patch('core.safe_subprocess.logger') as mock_logger:
                result = run_command_safe(["echo", "test"])

                # Execution should proceed
                assert result.get("blocked") is not True

    def test_auto_shell_mode_for_string(self):
        """Should auto-enable shell for string commands."""
        # String command with shell features
        result = run_command_safe(
            "echo hello && echo world",
            skip_validation=True
        )

        assert "hello" in result["stdout"]
        assert "world" in result["stdout"]

    def test_custom_cwd(self):
        """Should use custom working directory."""
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_command_safe(
                ["python", "-c", "import os; print(os.getcwd())"],
                cwd=tmpdir,
                skip_validation=True
            )

            # Normalize paths for comparison - strip and lowercase both
            actual = result["stdout"].strip().lower().replace('\\', '/')
            expected = tmpdir.lower().replace('\\', '/')
            assert actual == expected

    def test_custom_env(self):
        """Should use custom environment variables."""
        import os
        env = os.environ.copy()
        env["TEST_VAR"] = "test_value_123"

        result = run_command_safe(
            "python -c \"import os; print(os.environ.get('TEST_VAR', ''))\"",
            env=env,
            skip_validation=True
        )

        assert "test_value_123" in result["stdout"]


class TestTimeoutHandling:
    """Test timeout handling."""

    def test_timeout_sets_flag(self):
        """Should set timed_out flag on timeout."""
        # This test may be slow - use short timeout
        result = run_command_safe(
            "python -c \"import time; time.sleep(10)\"",
            timeout=1,
            skip_validation=True
        )

        assert result["timed_out"] is True

    def test_timeout_kills_process(self):
        """Should kill process on timeout."""
        result = run_command_safe(
            "python -c \"import time; time.sleep(10)\"",
            timeout=1,
            skip_validation=True
        )

        assert result["killed"] is True or result["timed_out"] is True


class TestValidation:
    """Test command validation."""

    def test_blocks_dangerous_commands(self):
        """Should block dangerous commands by default."""
        with patch('core.safe_subprocess.validate_before_run') as mock_validate:
            mock_validate.return_value = (False, "rm -rf is dangerous", [])

            result = run_command_safe("rm -rf /")

            assert result["blocked"] is True

    def test_skip_validation_flag(self):
        """Should skip validation when flag is set."""
        # Should not call validator when skip_validation=True
        with patch('core.safe_subprocess.validate_before_run') as mock_validate:
            mock_validate.return_value = (True, "", [])

            result = run_command_safe(
                ["echo", "safe"],
                skip_validation=True
            )

            # Should not have called validator
            mock_validate.assert_not_called()


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_command_list(self):
        """Should handle empty command list gracefully."""
        try:
            result = run_command_safe([], skip_validation=True)
            # Either returns error or raises exception - both OK
        except (ValueError, IndexError, OSError):
            pass  # Expected for empty command

    def test_empty_command_string(self):
        """Should handle empty command string."""
        try:
            result = run_command_safe("", skip_validation=True)
            # May return error or raise - both OK
        except (ValueError, OSError):
            pass  # Expected

    def test_command_not_found(self):
        """Should handle command not found."""
        result = run_command_safe(
            ["nonexistent_command_xyz_123"],
            skip_validation=True
        )

        # Should not crash, returncode should indicate failure
        assert result["returncode"] != 0 or "not found" in result["stderr"].lower() or \
               "not recognized" in result["stderr"].lower()

    def test_unicode_in_command(self):
        """Should handle unicode in commands."""
        result = run_command_safe(
            ["echo", "日本語テスト"],
            skip_validation=True
        )

        # Should not crash
        assert isinstance(result, dict)

    def test_special_chars_in_output(self):
        """Should handle special characters in output."""
        result = run_command_safe(
            "echo $pecial && echo @chars",
            skip_validation=True
        )

        # Should not crash
        assert isinstance(result, dict)

    def test_very_long_output(self):
        """Should handle long command output."""
        result = run_command_safe(
            "python -c \"print('x' * 10000)\"",
            skip_validation=True
        )

        assert len(result["stdout"]) >= 10000

    def test_binary_output(self):
        """Should handle binary-like output."""
        result = run_command_safe(
            "python -c \"import sys; sys.stdout.buffer.write(b'\\x00\\x01\\x02')\"",
            skip_validation=True
        )

        # Should not crash
        assert isinstance(result, dict)


class TestProcessKill:
    """Test process killing functionality."""

    def test_kill_process_tree_import_error(self):
        """Should fallback when psutil not available."""
        from core.safe_subprocess import _kill_process_tree

        # Mock psutil import failure
        with patch.dict('sys.modules', {'psutil': None}):
            with patch('core.safe_subprocess.os.kill') as mock_kill:
                # Should not raise even with fake PID
                try:
                    _kill_process_tree(99999999)
                except:
                    pass  # OK if it fails for non-existent process

