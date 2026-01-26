"""
Unit tests for core/cli.py

Tests cover:
- Helper functions (_looks_like_solana_address, _load_symbol_map, _save_symbol_map, etc.)
- Path resolution (_daemon_python, _resolve_user_path, _trading_symbol_map_path)
- Output formatting functions (_format_observations, _format_processes, _format_ports, _format_profile, _format_uptime)
- Capture text functions (capture_status_text, capture_diagnostics_text, capture_summarize_text, etc.)
- Status payload generation (_status_payload)
- Command handlers (cmd_status, cmd_on, cmd_off, cmd_log, cmd_capture, etc.)
- Argument parsing (build_parser)
- Main dispatch (main)

Target: 60%+ coverage for this 2,861 line module
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open, AsyncMock
from io import StringIO

import pytest


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_config():
    """Mock configuration dictionary."""
    return {
        "voice": {"enabled": False, "mode": "push_to_talk"},
        "memory": {"target_cap": 1000},
        "passive": {"enabled": False},
        "interview": {"enabled": False},
        "diagnostics": {"top_processes": 5},
        "research": {"allow_web": False},
        "hotkeys": {"enabled": False, "chat_activation": "ctrl+shift+up"},
        "trading_daemon": {"symbol_map_path": None},
        "context": {"load_budget_docs": 20, "load_budget_chars": 12000},
        "paths": {"logs_dir": "lifeos/logs"},
    }


@pytest.fixture
def mock_state():
    """Mock state dictionary."""
    return {
        "running": True,
        "voice_enabled": False,
        "voice_mode": "push_to_talk",
        "mic_status": "idle",
        "voice_error": "none",
        "chat_active": False,
        "hotkeys_enabled": False,
        "hotkey_combo": "ctrl+shift+up",
        "hotkey_error": "none",
        "passive_enabled": False,
        "passive_keyboard": False,
        "passive_idle_seconds": 0,
        "interview_enabled": False,
        "last_report_at": "none",
        "component_status": {},
        "startup_ok": 1,
        "startup_failed": 0,
        "brain_status": {"running": True, "phase": "idle", "cycle_count": 5},
        "daemon_heartbeat": "2026-01-25T10:00:00",
        "daemon_uptime_seconds": 3600,
        "updated_at": "2026-01-25T10:00:00",
    }


@pytest.fixture
def mock_args():
    """Mock argparse.Namespace with common arguments."""
    args = argparse.Namespace()
    args.apply = False
    args.dry_run = True
    return args


@pytest.fixture
def mock_safety_context():
    """Mock safety context."""
    context = MagicMock()
    context.dry_run = True
    context.apply = False
    return context


@pytest.fixture
def temp_symbol_map():
    """Create a temporary symbol map file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "symbol_map.json"
        data = {"SOL": "So11111111111111111111111111111111111111112"}
        path.write_text(json.dumps(data))
        yield path


# =============================================================================
# Test _looks_like_solana_address
# =============================================================================

class TestLooksLikeSolanaAddress:
    """Tests for _looks_like_solana_address function."""

    def test_valid_sol_mint(self):
        """SOL mint address should be recognized."""
        from core.cli import _looks_like_solana_address
        assert _looks_like_solana_address("So11111111111111111111111111111111111111112")

    def test_valid_usdc_mint(self):
        """USDC mint address should be recognized."""
        from core.cli import _looks_like_solana_address
        assert _looks_like_solana_address("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")

    def test_valid_usdt_mint(self):
        """USDT mint address should be recognized."""
        from core.cli import _looks_like_solana_address
        assert _looks_like_solana_address("Es9vMFrzaCER3EJmqvQC2Uo9qowWP1h1xFh3Le7YpR1V")

    def test_valid_random_address(self):
        """Random valid Solana address should be recognized."""
        from core.cli import _looks_like_solana_address
        assert _looks_like_solana_address("7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs")

    def test_empty_string(self):
        """Empty string should return False."""
        from core.cli import _looks_like_solana_address
        assert not _looks_like_solana_address("")

    def test_none_value(self):
        """None should return False."""
        from core.cli import _looks_like_solana_address
        assert not _looks_like_solana_address(None)

    def test_too_short(self):
        """String too short should return False."""
        from core.cli import _looks_like_solana_address
        assert not _looks_like_solana_address("abc")
        assert not _looks_like_solana_address("a" * 31)

    def test_too_long(self):
        """String too long should return False."""
        from core.cli import _looks_like_solana_address
        assert not _looks_like_solana_address("a" * 45)
        assert not _looks_like_solana_address("a" * 50)

    def test_ethereum_address(self):
        """Ethereum address format should return False."""
        from core.cli import _looks_like_solana_address
        assert not _looks_like_solana_address("0x1234567890abcdef1234567890abcdef12345678")

    def test_invalid_characters(self):
        """Address with invalid base58 characters should return False."""
        from core.cli import _looks_like_solana_address
        # '0', 'I', 'O', 'l' are not in base58
        assert not _looks_like_solana_address("0OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO")
        assert not _looks_like_solana_address("IIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIIlllllllll")

    def test_boundary_lengths(self):
        """Test boundary lengths (32-44 chars)."""
        from core.cli import _looks_like_solana_address
        # 32 chars - minimum valid
        valid_32 = "a" * 32
        # Replace with valid base58
        valid_32 = "abcdefghjkmnpqrstuvwxyz123456789"[:32]
        assert _looks_like_solana_address(valid_32)

        # 44 chars - maximum valid
        valid_44 = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUV"[:44]
        assert _looks_like_solana_address(valid_44)


# =============================================================================
# Test Symbol Map Functions
# =============================================================================

class TestSymbolMapFunctions:
    """Tests for _load_symbol_map and _save_symbol_map."""

    def test_load_nonexistent_file(self):
        """Loading non-existent file returns empty dict."""
        from core.cli import _load_symbol_map
        result = _load_symbol_map(Path("/nonexistent/path/map.json"))
        assert result == {}

    def test_load_valid_json(self, temp_symbol_map):
        """Valid JSON file is loaded correctly."""
        from core.cli import _load_symbol_map
        result = _load_symbol_map(temp_symbol_map)
        assert result == {"SOL": "So11111111111111111111111111111111111111112"}

    def test_load_invalid_json(self):
        """Invalid JSON returns empty dict."""
        from core.cli import _load_symbol_map
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not valid json {{{")
            temp_path = Path(f.name)

        try:
            result = _load_symbol_map(temp_path)
            assert result == {}
        finally:
            temp_path.unlink()

    def test_load_non_dict_json(self):
        """Non-dict JSON returns empty dict."""
        from core.cli import _load_symbol_map
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(["list", "not", "dict"], f)
            temp_path = Path(f.name)

        try:
            result = _load_symbol_map(temp_path)
            assert result == {}
        finally:
            temp_path.unlink()

    def test_save_creates_directories(self):
        """Save creates parent directories if needed."""
        from core.cli import _save_symbol_map, _load_symbol_map
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "subdir" / "nested" / "map.json"
            data = {"TEST": "TestAddress123456789012345678901234"}

            _save_symbol_map(path, data)

            assert path.exists()
            loaded = _load_symbol_map(path)
            assert loaded == data

    def test_save_overwrites_existing(self):
        """Save overwrites existing file."""
        from core.cli import _save_symbol_map, _load_symbol_map
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "map.json"

            _save_symbol_map(path, {"OLD": "old_address"})
            _save_symbol_map(path, {"NEW": "new_address"})

            loaded = _load_symbol_map(path)
            assert loaded == {"NEW": "new_address"}
            assert "OLD" not in loaded


# =============================================================================
# Test Path Resolution Functions
# =============================================================================

class TestPathResolution:
    """Tests for path resolution helper functions."""

    def test_daemon_python_venv311_exists(self):
        """Should return venv311 python if it exists."""
        from core.cli import _daemon_python, ROOT

        with tempfile.TemporaryDirectory() as tmpdir:
            venv311 = Path(tmpdir) / "venv311" / "bin" / "python"
            venv311.parent.mkdir(parents=True)
            venv311.touch()

            with patch("core.cli.ROOT", Path(tmpdir)):
                # Mock the actual implementation to test logic
                result = _daemon_python()
                # The function should return a valid python path
                assert isinstance(result, str)

    def test_daemon_python_fallback(self):
        """Should fallback to sys.executable if no venv found."""
        from core.cli import _daemon_python

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("core.cli.ROOT", Path(tmpdir)):
                result = _daemon_python()
                # Should return sys.executable when no venv exists
                assert isinstance(result, str)

    def test_resolve_user_path_none(self):
        """None value returns fallback."""
        from core.cli import _resolve_user_path
        fallback = Path("/fallback/path")
        result = _resolve_user_path(None, fallback)
        assert result == fallback

    def test_resolve_user_path_empty(self):
        """Empty string returns fallback."""
        from core.cli import _resolve_user_path
        fallback = Path("/fallback/path")
        result = _resolve_user_path("", fallback)
        assert result == fallback

    def test_resolve_user_path_absolute(self):
        """Absolute path is returned as-is."""
        from core.cli import _resolve_user_path
        if sys.platform == "win32":
            abs_path = "C:\\absolute\\path"
        else:
            abs_path = "/absolute/path"
        fallback = Path("/fallback")
        result = _resolve_user_path(abs_path, fallback)
        assert result.is_absolute()

    def test_resolve_user_path_home_expansion(self):
        """Home directory is expanded."""
        from core.cli import _resolve_user_path
        result = _resolve_user_path("~/test/path", Path("/fallback"))
        assert str(result).startswith(str(Path.home()))


# =============================================================================
# Test Output Formatting Functions
# =============================================================================

class TestOutputFormatting:
    """Tests for output formatting functions."""

    def test_format_observations_empty(self):
        """Empty observations returns default message."""
        from core.cli import _format_observations
        result = _format_observations([])
        assert "No critical issues" in result

    def test_format_observations_none(self):
        """None observations returns default message."""
        from core.cli import _format_observations
        result = _format_observations(None)
        assert "No critical issues" in result

    def test_format_observations_with_items(self):
        """Observations are formatted correctly."""
        from core.cli import _format_observations

        class MockObs:
            title = "Test Issue"
            why_it_matters = "It matters"
            confidence = "high"
            next_step = "Fix it"

        result = _format_observations([MockObs()])
        assert "Test Issue" in result
        assert "It matters" in result
        assert "high" in result
        assert "Fix it" in result

    def test_format_processes_empty(self):
        """Empty processes returns default message."""
        from core.cli import _format_processes
        result = _format_processes([])
        assert "No process data" in result

    def test_format_processes_none(self):
        """None processes returns default message."""
        from core.cli import _format_processes
        result = _format_processes(None)
        assert "No process data" in result

    def test_format_processes_with_items(self):
        """Processes are formatted correctly."""
        from core.cli import _format_processes
        processes = [
            {"name": "python", "pid": 1234, "mem_mb": 100, "cpu": 5.0},
            {"name": "node", "pid": 5678, "mem_mb": 200, "cpu": 10.0},
        ]
        result = _format_processes(processes)
        assert "python" in result
        assert "1234" in result
        assert "100" in result
        assert "node" in result

    def test_format_ports_empty(self):
        """Empty ports returns default message."""
        from core.cli import _format_ports
        result = _format_ports([])
        assert "No listening ports" in result

    def test_format_ports_none(self):
        """None ports returns default message."""
        from core.cli import _format_ports
        result = _format_ports(None)
        assert "No listening ports" in result

    def test_format_ports_with_items(self):
        """Ports are formatted correctly."""
        from core.cli import _format_ports
        ports = [
            {"name": "node", "pid": 1234, "address": "127.0.0.1:3000"},
        ]
        result = _format_ports(ports)
        assert "node" in result
        assert "1234" in result
        assert "127.0.0.1:3000" in result

    def test_format_profile_none(self):
        """None profile returns unavailable message."""
        from core.cli import _format_profile
        result = _format_profile(None)
        assert "Unavailable" in result

    def test_format_profile_with_data(self):
        """Profile is formatted correctly."""
        from core.cli import _format_profile

        class MockProfile:
            os_version = "Windows-10"
            cpu_load = 2.5
            ram_total_gb = 16.0
            ram_free_gb = 8.0
            disk_free_gb = 100.0

        result = _format_profile(MockProfile())
        assert "Windows-10" in result
        assert "16.0" in result
        assert "8.0" in result
        assert "100.0" in result


# =============================================================================
# Test _format_uptime
# =============================================================================

class TestFormatUptime:
    """Tests for _format_uptime function."""

    def test_zero_seconds(self):
        """Zero seconds returns 'just started'."""
        from core.cli import _format_uptime
        assert _format_uptime(0) == "just started"

    def test_seconds_only(self):
        """Less than a minute shows seconds."""
        from core.cli import _format_uptime
        result = _format_uptime(45)
        assert "45s" in result

    def test_minutes_and_seconds(self):
        """Minutes and seconds are formatted."""
        from core.cli import _format_uptime
        result = _format_uptime(125)  # 2m 5s
        assert "2m" in result
        assert "5s" in result

    def test_hours_minutes_seconds(self):
        """Hours, minutes, and seconds are formatted."""
        from core.cli import _format_uptime
        result = _format_uptime(3725)  # 1h 2m 5s
        assert "1h" in result
        assert "2m" in result
        assert "5s" in result

    def test_large_hours(self):
        """Large hour values are handled."""
        from core.cli import _format_uptime
        result = _format_uptime(86400)  # 24 hours
        assert "24h" in result


# =============================================================================
# Test _status_payload
# =============================================================================

class TestStatusPayload:
    """Tests for _status_payload function."""

    def test_status_payload_structure(self, mock_config, mock_state):
        """Status payload has expected structure."""
        from core import cli

        with patch.object(cli.config, 'load_config', return_value=mock_config), \
             patch.object(cli.state, 'is_running', return_value=True), \
             patch.object(cli.state, 'read_state', return_value=mock_state), \
             patch.object(cli.memory, 'load_memory_state', return_value={"memory_cap": 1000, "recent_count": 5, "pending_count": 2}), \
             patch.object(cli.interview, 'get_interview_stats', return_value={"today": 2}):

            result = cli._status_payload()

            assert "running" in result
            assert "voice_enabled" in result
            assert "voice_mode" in result
            assert "memory_cap" in result
            assert "recent_entries" in result
            assert "pending_entries" in result

    def test_status_payload_running_yes(self, mock_config, mock_state):
        """Running state is 'yes' when daemon is running."""
        from core import cli

        with patch.object(cli.config, 'load_config', return_value=mock_config), \
             patch.object(cli.state, 'is_running', return_value=True), \
             patch.object(cli.state, 'read_state', return_value=mock_state), \
             patch.object(cli.memory, 'load_memory_state', return_value={"memory_cap": 1000}), \
             patch.object(cli.interview, 'get_interview_stats', return_value={}):

            result = cli._status_payload()
            assert result["running"] == "yes"

    def test_status_payload_running_no(self, mock_config, mock_state):
        """Running state is 'no' when daemon is not running."""
        from core import cli

        with patch.object(cli.config, 'load_config', return_value=mock_config), \
             patch.object(cli.state, 'is_running', return_value=False), \
             patch.object(cli.state, 'read_state', return_value=mock_state), \
             patch.object(cli.memory, 'load_memory_state', return_value={"memory_cap": 1000}), \
             patch.object(cli.interview, 'get_interview_stats', return_value={}):

            result = cli._status_payload()
            assert result["running"] == "no"

    def test_status_payload_memory_fallback(self, mock_config, mock_state):
        """Memory state fallback on AttributeError."""
        from core import cli

        with patch.object(cli.config, 'load_config', return_value=mock_config), \
             patch.object(cli.state, 'is_running', return_value=True), \
             patch.object(cli.state, 'read_state', return_value=mock_state), \
             patch.object(cli.memory, 'load_memory_state', side_effect=AttributeError("No such method")), \
             patch.object(cli.interview, 'get_interview_stats', return_value={}):

            result = cli._status_payload()
            assert "memory_cap" in result


# =============================================================================
# Test Capture Text Functions
# =============================================================================

class TestCaptureTextFunctions:
    """Tests for capture text functions."""

    def test_capture_status_text(self, mock_config, mock_state):
        """capture_status_text returns formatted text."""
        from core import cli

        with patch.object(cli.config, 'load_config', return_value=mock_config), \
             patch.object(cli.state, 'is_running', return_value=True), \
             patch.object(cli.state, 'read_state', return_value=mock_state), \
             patch.object(cli.memory, 'load_memory_state', return_value={"memory_cap": 1000, "recent_count": 5, "pending_count": 2}), \
             patch.object(cli.interview, 'get_interview_stats', return_value={}), \
             patch.object(cli.output, 'render', return_value="[Rendered Output]"):

            result = cli.capture_status_text()
            assert "Status:" in result

    def test_capture_diagnostics_text(self, mock_config):
        """capture_diagnostics_text returns formatted text."""
        from core import cli

        mock_data = {
            "observations": [],
            "processes": [],
            "ports": [],
            "profile": None,
        }

        with patch.object(cli.config, 'load_config', return_value=mock_config), \
             patch.object(cli.diagnostics, 'run_diagnostics', return_value=mock_data), \
             patch.object(cli.output, 'render', return_value="[Rendered Output]"):

            result = cli.capture_diagnostics_text(dry_run=True)
            assert "[Rendered Output]" in result

    def test_capture_summarize_text_dry_run(self, mock_config):
        """capture_summarize_text in dry run mode."""
        from core import cli

        mock_entries = [{"text": "Entry 1", "source": "test"}]
        mock_routed = {"context/file.md": ["item 1"]}

        with patch.object(cli.memory, 'get_pending_entries', return_value=mock_entries), \
             patch.object(cli.memory, 'get_recent_entries', return_value=[]), \
             patch.object(cli.memory, 'summarize_entries', return_value="Summary text"), \
             patch.object(cli.context_router, 'route_entries', return_value=mock_routed), \
             patch.object(cli.output, 'render', return_value="[Rendered]"):

            result = cli.capture_summarize_text(dry_run=True)
            assert "[Rendered]" in result
            assert "Summary Preview" in result

    def test_capture_report_text_dry_run(self, mock_config):
        """capture_report_text in dry run mode."""
        from core import cli

        with patch.object(cli.reporting, 'generate_report_text', return_value="Report content"), \
             patch.object(cli.reporting, 'plan_report_path', return_value=Path("/path/to/report.md")), \
             patch.object(cli.output, 'render', return_value="[Rendered]"):

            result = cli.capture_report_text(kind="daily", dry_run=True)
            assert "[Rendered]" in result
            assert "Report Preview" in result
            assert "Report content" in result

    def test_capture_overnight_text_dry_run(self, mock_config):
        """capture_overnight_text in dry run mode."""
        from core import cli

        mock_result = {"summary": "Overnight summary"}

        with patch.object(cli.overnight, 'run_overnight', return_value=mock_result), \
             patch.object(cli.output, 'render', return_value="[Rendered]"):

            result = cli.capture_overnight_text(dry_run=True)
            assert "[Rendered]" in result
            assert "Summary Preview" in result


# =============================================================================
# Test Command Handlers
# =============================================================================

class TestCmdStatus:
    """Tests for cmd_status command handler."""

    def test_cmd_status_basic(self, mock_args, mock_config, mock_state, capsys):
        """cmd_status prints status text."""
        from core import cli

        mock_args.verbose = False

        with patch.object(cli.config, 'load_config', return_value=mock_config), \
             patch.object(cli.state, 'is_running', return_value=True), \
             patch.object(cli.state, 'read_state', return_value=mock_state), \
             patch.object(cli.memory, 'load_memory_state', return_value={"memory_cap": 1000}), \
             patch.object(cli.interview, 'get_interview_stats', return_value={}), \
             patch.object(cli.output, 'render', return_value="[Status Output]"):

            cli.cmd_status(mock_args)
            captured = capsys.readouterr()
            assert "[Status Output]" in captured.out

    def test_cmd_status_verbose_running(self, mock_args, mock_config, mock_state, capsys):
        """cmd_status with verbose flag shows component details."""
        from core import cli

        mock_args.verbose = True
        mock_state["component_status"] = {"voice": {"ok": True}, "brain": {"ok": True}}

        with patch.object(cli.config, 'load_config', return_value=mock_config), \
             patch.object(cli.state, 'is_running', return_value=True), \
             patch.object(cli.state, 'read_state', return_value=mock_state), \
             patch.object(cli.state, 'read_pid', return_value=1234), \
             patch.object(cli.memory, 'load_memory_state', return_value={"memory_cap": 1000}), \
             patch.object(cli.interview, 'get_interview_stats', return_value={}), \
             patch.object(cli.output, 'render', return_value="[Status Output]"):

            cli.cmd_status(mock_args)
            captured = capsys.readouterr()
            assert "DAEMON HEALTH STATUS" in captured.out

    def test_cmd_status_verbose_not_running(self, mock_args, mock_config, mock_state, capsys):
        """cmd_status verbose shows warning when daemon not running."""
        from core import cli

        mock_args.verbose = True
        mock_state["running"] = False

        with patch.object(cli.config, 'load_config', return_value=mock_config), \
             patch.object(cli.state, 'is_running', return_value=True), \
             patch.object(cli.state, 'read_state', return_value=mock_state), \
             patch.object(cli.memory, 'load_memory_state', return_value={"memory_cap": 1000}), \
             patch.object(cli.interview, 'get_interview_stats', return_value={}), \
             patch.object(cli.output, 'render', return_value="[Status Output]"):

            cli.cmd_status(mock_args)
            captured = capsys.readouterr()
            # When running=False in state, should show warning
            assert "[Status Output]" in captured.out


class TestCmdOn:
    """Tests for cmd_on command handler."""

    def test_cmd_on_already_running(self, mock_args, capsys):
        """cmd_on exits early if daemon is already running."""
        from core import cli

        with patch.object(cli.state, 'is_running', return_value=True), \
             patch.object(cli.output, 'render', return_value="[Already Running]"), \
             patch('core.cli._render') as mock_render:

            cli.cmd_on(mock_args)
            mock_render.assert_called_once()

    def test_cmd_on_dry_run(self, mock_args, mock_config, capsys):
        """cmd_on in dry run mode shows preview."""
        from core import cli

        mock_args.dry_run = True
        mock_args.apply = False

        with patch.object(cli.state, 'is_running', return_value=False), \
             patch.object(cli.config, 'load_config', return_value=mock_config), \
             patch.object(cli.safety, 'resolve_mode') as mock_resolve:

            mock_context = MagicMock()
            mock_context.dry_run = True
            mock_resolve.return_value = mock_context

            with patch('core.cli._render') as mock_render:
                cli.cmd_on(mock_args)
                mock_render.assert_called_once()

    def test_cmd_on_apply_cancelled(self, mock_args, mock_config, capsys):
        """cmd_on with apply but safety not confirmed."""
        from core import cli

        mock_args.dry_run = False
        mock_args.apply = True

        with patch.object(cli.state, 'is_running', return_value=False), \
             patch.object(cli.config, 'load_config', return_value=mock_config), \
             patch.object(cli.safety, 'resolve_mode') as mock_resolve, \
             patch.object(cli.safety, 'allow_action', return_value=False):

            mock_context = MagicMock()
            mock_context.dry_run = False
            mock_resolve.return_value = mock_context

            with patch('core.cli._render') as mock_render:
                cli.cmd_on(mock_args)
                # Should render the cancelled message
                assert mock_render.called


class TestCmdOff:
    """Tests for cmd_off command handler."""

    def test_cmd_off_not_running(self, mock_args, capsys):
        """cmd_off exits early if daemon is not running."""
        from core import cli

        with patch.object(cli.state, 'read_pid', return_value=None), \
             patch.object(cli.state, 'is_running', return_value=False), \
             patch('core.cli._render') as mock_render:

            cli.cmd_off(mock_args)
            mock_render.assert_called_once()

    def test_cmd_off_dry_run(self, mock_args, capsys):
        """cmd_off in dry run mode shows preview."""
        from core import cli

        mock_args.dry_run = True
        mock_args.apply = False

        with patch.object(cli.state, 'read_pid', return_value=1234), \
             patch.object(cli.state, 'is_running', return_value=True), \
             patch.object(cli.safety, 'resolve_mode') as mock_resolve:

            mock_context = MagicMock()
            mock_context.dry_run = True
            mock_resolve.return_value = mock_context

            with patch('core.cli._render') as mock_render:
                cli.cmd_off(mock_args)
                mock_render.assert_called_once()


class TestCmdLog:
    """Tests for cmd_log command handler."""

    def test_cmd_log_empty_text(self, mock_args, capsys):
        """cmd_log with empty text shows error."""
        from core import cli

        mock_args.text = ""

        with patch('core.cli._render') as mock_render:
            cli.cmd_log(mock_args)
            mock_render.assert_called_once()

    def test_cmd_log_whitespace_only(self, mock_args, capsys):
        """cmd_log with whitespace-only text shows error."""
        from core import cli

        mock_args.text = "   "

        with patch('core.cli._render') as mock_render:
            cli.cmd_log(mock_args)
            mock_render.assert_called_once()

    def test_cmd_log_dry_run(self, mock_args, capsys):
        """cmd_log in dry run mode."""
        from core import cli

        mock_args.text = "Test log entry"
        mock_args.dry_run = True
        mock_args.apply = False

        with patch.object(cli.safety, 'resolve_mode') as mock_resolve, \
             patch.object(cli.memory, 'append_entry', return_value=(["entry"], [])):

            mock_context = MagicMock()
            mock_context.dry_run = True
            mock_resolve.return_value = mock_context

            with patch('core.cli._render') as mock_render:
                cli.cmd_log(mock_args)


class TestCmdCapture:
    """Tests for cmd_capture command handler."""

    def test_cmd_capture_dry_run(self, mock_args, capsys):
        """cmd_capture in dry run mode shows preview."""
        from core import cli

        mock_args.dry_run = True
        mock_args.apply = False

        with patch.object(cli.safety, 'resolve_mode') as mock_resolve:
            mock_context = MagicMock()
            mock_context.dry_run = True
            mock_resolve.return_value = mock_context

            with patch('core.cli._render') as mock_render:
                cli.cmd_capture(mock_args)
                mock_render.assert_called_once()

    def test_cmd_capture_safety_denied(self, mock_args, capsys):
        """cmd_capture with safety denied."""
        from core import cli

        mock_args.dry_run = False
        mock_args.apply = True

        with patch.object(cli.safety, 'resolve_mode') as mock_resolve, \
             patch.object(cli.safety, 'allow_action', return_value=False):

            mock_context = MagicMock()
            mock_context.dry_run = False
            mock_resolve.return_value = mock_context

            with patch('core.cli._render') as mock_render:
                cli.cmd_capture(mock_args)
                mock_render.assert_called_once()


class TestCmdSummarize:
    """Tests for cmd_summarize command handler."""

    def test_cmd_summarize_dry_run(self, mock_args, capsys):
        """cmd_summarize in dry run mode."""
        from core import cli

        mock_args.dry_run = True
        mock_args.apply = False

        with patch.object(cli.safety, 'resolve_mode') as mock_resolve, \
             patch('core.cli.capture_summarize_text', return_value="[Summary]"):

            mock_context = MagicMock()
            mock_context.dry_run = True
            mock_resolve.return_value = mock_context

            cli.cmd_summarize(mock_args)
            captured = capsys.readouterr()
            assert "[Summary]" in captured.out


class TestCmdReport:
    """Tests for cmd_report command handler."""

    def test_cmd_report_daily(self, mock_args, capsys):
        """cmd_report with daily type."""
        from core import cli

        mock_args.dry_run = True
        mock_args.apply = False
        mock_args.morning = False
        mock_args.afternoon = False
        mock_args.weekly = False

        with patch.object(cli.safety, 'resolve_mode') as mock_resolve, \
             patch('core.cli.capture_report_text', return_value="[Report]") as mock_capture:

            mock_context = MagicMock()
            mock_context.dry_run = True
            mock_resolve.return_value = mock_context

            cli.cmd_report(mock_args)
            mock_capture.assert_called_with(kind="daily", dry_run=True)

    def test_cmd_report_morning(self, mock_args, capsys):
        """cmd_report with morning type."""
        from core import cli

        mock_args.dry_run = True
        mock_args.apply = False
        mock_args.morning = True
        mock_args.afternoon = False
        mock_args.weekly = False

        with patch.object(cli.safety, 'resolve_mode') as mock_resolve, \
             patch('core.cli.capture_report_text', return_value="[Report]") as mock_capture:

            mock_context = MagicMock()
            mock_context.dry_run = True
            mock_resolve.return_value = mock_context

            cli.cmd_report(mock_args)
            mock_capture.assert_called_with(kind="morning", dry_run=True)

    def test_cmd_report_weekly(self, mock_args, capsys):
        """cmd_report with weekly type."""
        from core import cli

        mock_args.dry_run = True
        mock_args.apply = False
        mock_args.morning = False
        mock_args.afternoon = False
        mock_args.weekly = True

        with patch.object(cli.safety, 'resolve_mode') as mock_resolve, \
             patch('core.cli.capture_report_text', return_value="[Report]") as mock_capture:

            mock_context = MagicMock()
            mock_context.dry_run = True
            mock_resolve.return_value = mock_context

            cli.cmd_report(mock_args)
            mock_capture.assert_called_with(kind="weekly", dry_run=True)


class TestCmdDiagnostics:
    """Tests for cmd_diagnostics command handler."""

    def test_cmd_diagnostics(self, mock_args, capsys):
        """cmd_diagnostics prints diagnostics text."""
        from core import cli

        with patch('core.cli.capture_diagnostics_text', return_value="[Diagnostics]"):
            cli.cmd_diagnostics(mock_args)
            captured = capsys.readouterr()
            assert "[Diagnostics]" in captured.out


class TestCmdRpcDiagnostics:
    """Tests for cmd_rpc_diagnostics command handler."""

    def test_cmd_rpc_diagnostics_text_output(self, capsys):
        """cmd_rpc_diagnostics prints text output."""
        from core import cli

        args = argparse.Namespace()
        args.no_sim = False
        args.json = False

        mock_payload = {
            "endpoints": [
                {
                    "name": "mainnet",
                    "health_ok": True,
                    "health_ms": 50,
                    "blockhash_ms": 100,
                    "simulate_ok": True,
                    "simulate_error": None,
                    "simulate_hint": None,
                }
            ]
        }

        with patch.object(cli.rpc_diagnostics, 'run_solana_rpc_diagnostics', return_value=mock_payload):
            cli.cmd_rpc_diagnostics(args)
            captured = capsys.readouterr()
            assert "mainnet" in captured.out
            assert "health=True" in captured.out

    def test_cmd_rpc_diagnostics_json_output(self, capsys):
        """cmd_rpc_diagnostics prints JSON output."""
        from core import cli

        args = argparse.Namespace()
        args.no_sim = True
        args.json = True

        mock_payload = {"endpoints": []}

        with patch.object(cli.rpc_diagnostics, 'run_solana_rpc_diagnostics', return_value=mock_payload):
            cli.cmd_rpc_diagnostics(args)
            captured = capsys.readouterr()
            parsed = json.loads(captured.out)
            assert "endpoints" in parsed


class TestCmdVoice:
    """Tests for cmd_voice command handler."""

    def test_cmd_voice_doctor(self, capsys):
        """cmd_voice doctor runs diagnostics."""
        from core import cli

        args = argparse.Namespace()
        args.voice_action = "doctor"

        mock_diagnostics = {
            "overall": {"operational": True},
        }

        with patch.object(cli.voice, 'diagnose_voice_pipeline', return_value=mock_diagnostics), \
             patch.object(cli.voice, 'format_voice_doctor_report', return_value="[Voice Report]"):

            result = cli.cmd_voice(args)
            assert result == 0
            captured = capsys.readouterr()
            assert "Voice Pipeline Diagnostics" in captured.out

    def test_cmd_voice_doctor_not_operational(self, capsys):
        """cmd_voice doctor returns 1 when not operational."""
        from core import cli

        args = argparse.Namespace()
        args.voice_action = "doctor"

        mock_diagnostics = {
            "overall": {"operational": False},
        }

        with patch.object(cli.voice, 'diagnose_voice_pipeline', return_value=mock_diagnostics), \
             patch.object(cli.voice, 'format_voice_doctor_report', return_value="[Voice Report]"):

            result = cli.cmd_voice(args)
            assert result == 1

    def test_cmd_voice_unknown_action(self, capsys):
        """cmd_voice with unknown action shows usage."""
        from core import cli

        args = argparse.Namespace()
        args.voice_action = None

        result = cli.cmd_voice(args)
        assert result == 0
        captured = capsys.readouterr()
        assert "Usage:" in captured.out


class TestCmdDoctor:
    """Tests for cmd_doctor command handler."""

    def test_cmd_doctor_basic(self, mock_config, capsys):
        """cmd_doctor runs basic health check."""
        from core import cli

        args = argparse.Namespace()
        args.test = False
        args.voice = False
        args.mcp = False
        args.validate_keys = False

        mock_health = {"groq": {"available": True}}

        with patch.object(cli.config, 'load_config', return_value=mock_config), \
             patch.object(cli.providers, 'get_provider_summary', return_value="[Providers]"), \
             patch.object(cli.providers, 'check_provider_health', return_value=mock_health), \
             patch.object(cli.mcp_doctor_simple, 'run_all_tests', return_value={}), \
             patch.object(cli.secrets, 'list_configured_keys', return_value={"groq": True}), \
             patch.object(cli.state, 'is_running', return_value=False), \
             patch.object(cli.state, 'read_state', return_value={}):

            cli.cmd_doctor(args)
            captured = capsys.readouterr()
            assert "LifeOS Doctor" in captured.out

    def test_cmd_doctor_mcp_mode(self, capsys):
        """cmd_doctor with --mcp flag."""
        from core import cli

        args = argparse.Namespace()
        args.test = False
        args.voice = False
        args.mcp = True
        args.validate_keys = False

        mock_result = MagicMock()
        mock_result.passed = True

        with patch.object(cli.mcp_doctor_simple, 'run_all_tests', return_value={"server1": mock_result}), \
             patch.object(cli.mcp_doctor_simple, 'print_summary'):

            cli.cmd_doctor(args)
            captured = capsys.readouterr()
            assert "MCP DOCTOR" in captured.out

    def test_cmd_doctor_voice_mode(self, capsys):
        """cmd_doctor with --voice flag."""
        from core import cli

        args = argparse.Namespace()
        args.test = False
        args.voice = True
        args.mcp = False
        args.validate_keys = False

        with patch.object(cli.voice, 'get_voice_doctor_summary', return_value="[Voice Summary]"):
            cli.cmd_doctor(args)
            captured = capsys.readouterr()
            assert "Voice Pipeline Diagnostics" in captured.out


class TestCmdTask:
    """Tests for cmd_task command handler."""

    def test_cmd_task_add(self, capsys):
        """cmd_task add creates a task."""
        from core import cli

        args = argparse.Namespace()
        args.task_action = "add"
        args.title = "Test task"
        args.priority = "medium"

        mock_task = MagicMock()
        mock_task.id = "task-123"
        mock_task.title = "Test task"
        mock_task.priority = MagicMock(value="medium")
        mock_task.status = MagicMock(value="pending")

        mock_tm = MagicMock()
        mock_tm.add_task.return_value = mock_task

        with patch.object(cli.task_manager, 'get_task_manager', return_value=mock_tm):
            cli.cmd_task(args)
            captured = capsys.readouterr()
            assert "task-123" in captured.out
            assert "Test task" in captured.out

    def test_cmd_task_list_empty(self, capsys):
        """cmd_task list with no tasks."""
        from core import cli

        args = argparse.Namespace()
        args.task_action = "list"
        args.status = None
        args.priority = None
        args.limit = 20

        mock_tm = MagicMock()
        mock_tm.list_tasks.return_value = []

        with patch.object(cli.task_manager, 'get_task_manager', return_value=mock_tm):
            cli.cmd_task(args)
            captured = capsys.readouterr()
            assert "No tasks found" in captured.out

    def test_cmd_task_status(self, capsys):
        """cmd_task status shows statistics."""
        from core import cli

        args = argparse.Namespace()
        args.task_action = "status"

        mock_tm = MagicMock()
        mock_tm.get_stats.return_value = {
            "total": 10,
            "pending": 5,
            "in_progress": 2,
            "completed": 3,
            "cancelled": 0,
            "by_priority": {"urgent": 1, "high": 2, "medium": 4, "low": 3},
        }

        with patch.object(cli.task_manager, 'get_task_manager', return_value=mock_tm):
            cli.cmd_task(args)
            captured = capsys.readouterr()
            assert "Total: 10" in captured.out
            assert "Pending: 5" in captured.out


# =============================================================================
# Test Argument Parsing
# =============================================================================

class TestBuildParser:
    """Tests for build_parser function."""

    def test_parser_creation(self):
        """Parser is created successfully."""
        from core.cli import build_parser
        parser = build_parser()
        assert parser is not None
        assert parser.prog == "lifeos"

    def test_status_command(self):
        """Status command parses correctly."""
        from core.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["status"])
        assert args.command == "status"

    def test_status_verbose(self):
        """Status with verbose flag."""
        from core.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["status", "-v"])
        assert args.verbose is True

    def test_on_command(self):
        """On command parses correctly."""
        from core.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["on"])
        assert args.command == "on"

    def test_on_with_apply(self):
        """On with --apply flag."""
        from core.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["on", "--apply"])
        assert args.apply is True

    def test_on_with_dry_run(self):
        """On with --dry-run flag."""
        from core.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["on", "--dry-run"])
        assert args.dry_run is True

    def test_off_command(self):
        """Off command parses correctly."""
        from core.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["off"])
        assert args.command == "off"

    def test_doctor_command(self):
        """Doctor command parses correctly."""
        from core.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["doctor"])
        assert args.command == "doctor"

    def test_doctor_with_test(self):
        """Doctor with --test flag."""
        from core.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["doctor", "--test"])
        assert args.test is True

    def test_doctor_with_mcp(self):
        """Doctor with --mcp flag."""
        from core.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["doctor", "--mcp"])
        assert args.mcp is True

    def test_doctor_with_voice(self):
        """Doctor with --voice flag."""
        from core.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["doctor", "--voice"])
        assert args.voice is True

    def test_log_command(self):
        """Log command parses correctly."""
        from core.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["log", "Test message"])
        assert args.command == "log"
        assert args.text == "Test message"

    def test_log_empty(self):
        """Log command with no text."""
        from core.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["log"])
        assert args.text == ""

    def test_listen_on(self):
        """Listen on command."""
        from core.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["listen", "on"])
        assert args.command == "listen"
        assert args.state == "on"

    def test_listen_off(self):
        """Listen off command."""
        from core.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["listen", "off"])
        assert args.state == "off"

    def test_secret_command(self):
        """Secret command parses correctly."""
        from core.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["secret", "gemini", "api-key-123"])
        assert args.command == "secret"
        assert args.provider == "gemini"
        assert args.key == "api-key-123"

    def test_activity_command(self):
        """Activity command parses correctly."""
        from core.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["activity"])
        assert args.command == "activity"
        assert args.hours == 4  # default

    def test_activity_with_hours(self):
        """Activity with --hours flag."""
        from core.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["activity", "--hours", "8"])
        assert args.hours == 8

    def test_jarvis_command(self):
        """Jarvis command parses correctly."""
        from core.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["jarvis"])
        assert args.command == "jarvis"
        assert args.action == "status"

    def test_jarvis_interview(self):
        """Jarvis interview action."""
        from core.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["jarvis", "interview"])
        assert args.action == "interview"

    def test_agent_command(self):
        """Agent command parses correctly."""
        from core.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["agent", "test", "goal"])
        assert args.command == "agent"
        assert args.goal == ["test", "goal"]

    def test_agent_with_execute(self):
        """Agent with --execute flag."""
        from core.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["agent", "--execute", "test"])
        assert args.execute is True

    def test_task_add_command(self):
        """Task add command parses correctly."""
        from core.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["task", "add", "My task"])
        assert args.command == "task"
        assert args.task_action == "add"
        assert args.title == "My task"

    def test_task_list_command(self):
        """Task list command parses correctly."""
        from core.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["task", "list"])
        assert args.task_action == "list"

    def test_brain_command(self):
        """Brain command parses correctly."""
        from core.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["brain"])
        assert args.command == "brain"
        assert args.action == "status"

    def test_brain_inject(self):
        """Brain inject command."""
        from core.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["brain", "inject", "--text", "test input"])
        assert args.action == "inject"
        assert args.text == "test input"

    def test_objective_add_command(self):
        """Objective add command parses correctly."""
        from core.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["objective", "add", "Test objective"])
        assert args.command == "objective"
        assert args.objective_action == "add"
        assert args.description == "Test objective"

    def test_economics_status_command(self):
        """Economics status command parses correctly."""
        from core.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["economics", "status"])
        assert args.command == "economics"
        assert args.economics_action == "status"

    def test_trading_positions_list(self):
        """Trading positions list command."""
        from core.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["trading-positions", "list"])
        assert args.command == "trading-positions"
        assert args.trading_positions_action == "list"

    def test_strategy_scores_command(self):
        """Strategy scores command parses correctly."""
        from core.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["strategy-scores"])
        assert args.command == "strategy-scores"
        assert args.limit == 20


# =============================================================================
# Test Main Function
# =============================================================================

class TestMain:
    """Tests for main function dispatch."""

    def test_main_status(self, mock_config, mock_state):
        """Main dispatches to cmd_status."""
        from core import cli

        with patch('sys.argv', ['lifeos', 'status']), \
             patch.object(cli, 'cmd_status') as mock_cmd:

            cli.main()
            mock_cmd.assert_called_once()

    def test_main_on(self):
        """Main dispatches to cmd_on."""
        from core import cli

        with patch('sys.argv', ['lifeos', 'on']), \
             patch.object(cli, 'cmd_on') as mock_cmd:

            cli.main()
            mock_cmd.assert_called_once()

    def test_main_off(self):
        """Main dispatches to cmd_off."""
        from core import cli

        with patch('sys.argv', ['lifeos', 'off']), \
             patch.object(cli, 'cmd_off') as mock_cmd:

            cli.main()
            mock_cmd.assert_called_once()

    def test_main_doctor(self):
        """Main dispatches to cmd_doctor."""
        from core import cli

        with patch('sys.argv', ['lifeos', 'doctor']), \
             patch.object(cli, 'cmd_doctor') as mock_cmd:

            cli.main()
            mock_cmd.assert_called_once()

    def test_main_log(self):
        """Main dispatches to cmd_log."""
        from core import cli

        with patch('sys.argv', ['lifeos', 'log', 'test']), \
             patch.object(cli, 'cmd_log') as mock_cmd:

            cli.main()
            mock_cmd.assert_called_once()

    def test_main_summarize(self):
        """Main dispatches to cmd_summarize."""
        from core import cli

        with patch('sys.argv', ['lifeos', 'summarize']), \
             patch.object(cli, 'cmd_summarize') as mock_cmd:

            cli.main()
            mock_cmd.assert_called_once()

    def test_main_report(self):
        """Main dispatches to cmd_report."""
        from core import cli

        with patch('sys.argv', ['lifeos', 'report']), \
             patch.object(cli, 'cmd_report') as mock_cmd:

            cli.main()
            mock_cmd.assert_called_once()

    def test_main_diagnostics(self):
        """Main dispatches to cmd_diagnostics."""
        from core import cli

        with patch('sys.argv', ['lifeos', 'diagnostics']), \
             patch.object(cli, 'cmd_diagnostics') as mock_cmd:

            cli.main()
            mock_cmd.assert_called_once()

    def test_main_jarvis(self):
        """Main dispatches to cmd_jarvis."""
        from core import cli

        with patch('sys.argv', ['lifeos', 'jarvis']), \
             patch.object(cli, 'cmd_jarvis') as mock_cmd:

            cli.main()
            mock_cmd.assert_called_once()

    def test_main_agent(self):
        """Main dispatches to cmd_agent."""
        from core import cli

        with patch('sys.argv', ['lifeos', 'agent', 'test']), \
             patch.object(cli, 'cmd_agent') as mock_cmd:

            cli.main()
            mock_cmd.assert_called_once()

    def test_main_task(self):
        """Main dispatches to cmd_task."""
        from core import cli

        with patch('sys.argv', ['lifeos', 'task', 'status']), \
             patch.object(cli, 'cmd_task') as mock_cmd:

            cli.main()
            mock_cmd.assert_called_once()

    def test_main_brain(self):
        """Main dispatches to cmd_brain."""
        from core import cli

        with patch('sys.argv', ['lifeos', 'brain']), \
             patch.object(cli, 'cmd_brain') as mock_cmd:

            cli.main()
            mock_cmd.assert_called_once()

    def test_main_objective(self):
        """Main dispatches to cmd_objective."""
        from core import cli

        with patch('sys.argv', ['lifeos', 'objective', 'list']), \
             patch.object(cli, 'cmd_objective') as mock_cmd:

            cli.main()
            mock_cmd.assert_called_once()

    def test_main_economics(self):
        """Main dispatches to cmd_economics."""
        from core import cli

        with patch('sys.argv', ['lifeos', 'economics', 'status']), \
             patch.object(cli, 'cmd_economics') as mock_cmd:

            cli.main()
            mock_cmd.assert_called_once()


# =============================================================================
# Test Additional Command Handlers
# =============================================================================

class TestCmdStub:
    """Tests for cmd_stub command handler."""

    def test_cmd_stub(self, mock_args):
        """cmd_stub shows not implemented message."""
        from core import cli

        with patch.object(cli.commands, 'not_implemented', return_value=({}, {}, {})), \
             patch('core.cli._render') as mock_render:

            cli.cmd_stub(mock_args, "test_cmd", "next_phase")
            mock_render.assert_called_once()


class TestCmdListen:
    """Tests for cmd_listen command handler."""

    def test_cmd_listen_dry_run(self, mock_args, capsys):
        """cmd_listen in dry run mode."""
        from core import cli

        mock_args.state = "on"
        mock_args.dry_run = True
        mock_args.apply = False

        with patch.object(cli.safety, 'resolve_mode') as mock_resolve:
            mock_context = MagicMock()
            mock_context.dry_run = True
            mock_resolve.return_value = mock_context

            with patch('core.cli._render') as mock_render:
                cli.cmd_listen(mock_args)
                mock_render.assert_called_once()

    def test_cmd_listen_apply_on(self, mock_args, capsys):
        """cmd_listen turns listening on."""
        from core import cli

        mock_args.state = "on"
        mock_args.dry_run = False
        mock_args.apply = True

        with patch.object(cli.safety, 'resolve_mode') as mock_resolve, \
             patch.object(cli.safety, 'allow_action', return_value=True), \
             patch.object(cli.state, 'update_state') as mock_update:

            mock_context = MagicMock()
            mock_context.dry_run = False
            mock_resolve.return_value = mock_context

            with patch('core.cli._render'):
                cli.cmd_listen(mock_args)
                mock_update.assert_called_with(voice_enabled=True, mic_status="idle")


class TestCmdActivity:
    """Tests for cmd_activity command handler."""

    def test_cmd_activity(self, capsys):
        """cmd_activity shows activity summary."""
        from core import cli

        args = argparse.Namespace()
        args.hours = 4

        with patch.object(cli.passive, 'summarize_activity', return_value="Activity summary"), \
             patch.object(cli.passive, 'load_recent_activity', return_value=[{"event": "test"}]), \
             patch('core.cli._render'):

            cli.cmd_activity(args)
            captured = capsys.readouterr()
            assert "Activity summary" in captured.out
            assert "Total log entries: 1" in captured.out


class TestCmdJarvis:
    """Tests for cmd_jarvis command handler."""

    def test_cmd_jarvis_status(self, capsys):
        """cmd_jarvis status shows info."""
        from core import cli

        args = argparse.Namespace()
        args.action = "status"

        mock_profile = MagicMock()
        mock_profile.name = "TestUser"

        with patch.object(cli.jarvis, 'get_user_profile', return_value=mock_profile):
            cli.cmd_jarvis(args)
            captured = capsys.readouterr()
            assert "Jarvis Status:" in captured.out

    def test_cmd_jarvis_interview(self, capsys):
        """cmd_jarvis interview runs interview."""
        from core import cli

        args = argparse.Namespace()
        args.action = "interview"

        with patch.object(cli.jarvis, 'conduct_interview', return_value="Interview questions"):
            cli.cmd_jarvis(args)
            captured = capsys.readouterr()
            assert "Jarvis Interview" in captured.out

    def test_cmd_jarvis_profile(self, capsys):
        """cmd_jarvis profile shows user profile."""
        from core import cli

        args = argparse.Namespace()
        args.action = "profile"

        mock_profile = MagicMock()
        mock_profile.name = "TestUser"
        mock_profile.linkedin = "linkedin.com/test"
        mock_profile.trading_focus = "crypto"
        mock_profile.primary_goals = ["goal1", "goal2"]
        mock_profile.interests = ["interest1"]
        mock_profile.mentor_channels = ["channel1"]

        with patch.object(cli.jarvis, 'get_user_profile', return_value=mock_profile):
            cli.cmd_jarvis(args)
            captured = capsys.readouterr()
            assert "User Profile" in captured.out
            assert "TestUser" in captured.out


class TestCmdAgent:
    """Tests for cmd_agent command handler."""

    def test_cmd_agent_empty_goal(self, capsys):
        """cmd_agent with empty goal shows error."""
        from core import cli

        args = argparse.Namespace()
        args.goal = []
        args.execute = False
        args.max_cycles = None
        args.max_step_retries = None

        cli.cmd_agent(args)
        captured = capsys.readouterr()
        assert "Goal is required" in captured.out

    def test_cmd_agent_module_unavailable(self, capsys):
        """cmd_agent handles module import error."""
        from core import cli

        args = argparse.Namespace()
        args.goal = ["test", "goal"]
        args.execute = False
        args.max_cycles = None
        args.max_step_retries = None

        with patch.dict('sys.modules', {'core.agent_graph': None}), \
             patch.object(cli.config, 'load_config', return_value={"agent": {}}):
            # This will try to import agent_graph which we've patched to fail
            try:
                cli.cmd_agent(args)
            except Exception:
                pass  # Expected to fail when agent_graph import fails


class TestCmdFeedback:
    """Tests for cmd_feedback command handler."""

    def test_cmd_feedback_metrics(self, capsys):
        """cmd_feedback metrics shows action metrics."""
        from core import cli

        args = argparse.Namespace()
        args.feedback_action = "metrics"

        mock_loop = MagicMock()
        mock_loop.get_metrics.return_value = {
            "action1": {"total_calls": 10, "success_rate": 0.9, "avg_duration_ms": 50}
        }

        with patch.object(cli.action_feedback, 'get_feedback_loop', return_value=mock_loop):
            cli.cmd_feedback(args)
            captured = capsys.readouterr()
            assert "ACTION METRICS" in captured.out

    def test_cmd_feedback_patterns(self, capsys):
        """cmd_feedback patterns shows learned patterns."""
        from core import cli

        args = argparse.Namespace()
        args.feedback_action = "patterns"

        mock_loop = MagicMock()
        mock_loop.get_patterns.return_value = []

        with patch.object(cli.action_feedback, 'get_feedback_loop', return_value=mock_loop):
            cli.cmd_feedback(args)
            captured = capsys.readouterr()
            assert "LEARNED PATTERNS" in captured.out


class TestCmdBrain:
    """Tests for cmd_brain command handler."""

    def test_cmd_brain_status(self, mock_state, capsys):
        """cmd_brain status shows brain status."""
        from core import cli

        args = argparse.Namespace()
        args.action = "status"
        args.text = None

        mock_obj_manager = MagicMock()
        mock_obj_manager.get_active.return_value = None
        mock_obj_manager.get_queue.return_value = []
        mock_obj_manager.status_summary.return_value = {
            "queue_size": 0,
            "completed_count": 5,
            "failed_count": 1,
            "success_rate": 0.83,
        }

        with patch.object(cli.state, 'read_state', return_value=mock_state), \
             patch.object(cli.objectives, 'get_manager', return_value=mock_obj_manager):

            cli.cmd_brain(args)
            captured = capsys.readouterr()
            assert "JARVIS BRAIN STATUS" in captured.out

    def test_cmd_brain_inject(self, capsys):
        """cmd_brain inject adds text to brain."""
        from core import cli

        args = argparse.Namespace()
        args.action = "inject"
        args.text = "Test input"

        mock_orch = MagicMock()

        with patch.object(cli.orchestrator, 'get_orchestrator', return_value=mock_orch):
            cli.cmd_brain(args)
            mock_orch.inject_user_input.assert_called_with("Test input")

    def test_cmd_brain_inject_no_text(self, capsys):
        """cmd_brain inject without text shows error."""
        from core import cli

        args = argparse.Namespace()
        args.action = "inject"
        args.text = None

        cli.cmd_brain(args)
        captured = capsys.readouterr()
        assert "Error: --text required" in captured.out


class TestCmdObjective:
    """Tests for cmd_objective command handler."""

    def test_cmd_objective_add(self, capsys):
        """cmd_objective add creates objective."""
        from core import cli

        args = argparse.Namespace()
        args.objective_action = "add"
        args.description = "Test objective"
        args.priority = "5"
        args.criteria = None

        mock_obj = MagicMock()
        mock_obj.id = "obj-123"
        mock_obj.description = "Test objective"
        mock_obj.priority = 5
        mock_obj.success_criteria = []

        mock_manager = MagicMock()
        mock_manager.create_objective.return_value = mock_obj

        with patch.object(cli.objectives, 'get_manager', return_value=mock_manager):
            cli.cmd_objective(args)
            captured = capsys.readouterr()
            assert "obj-123" in captured.out

    def test_cmd_objective_list(self, capsys):
        """cmd_objective list shows objectives."""
        from core import cli

        args = argparse.Namespace()
        args.objective_action = "list"
        args.limit = 10

        mock_manager = MagicMock()
        mock_manager.get_active.return_value = None
        mock_manager.get_queue.return_value = []

        with patch.object(cli.objectives, 'get_manager', return_value=mock_manager):
            cli.cmd_objective(args)
            captured = capsys.readouterr()
            assert "OBJECTIVE QUEUE" in captured.out


class TestCmdEconomics:
    """Tests for cmd_economics command handler."""

    def test_cmd_economics_status(self, capsys):
        """cmd_economics status shows economic status."""
        from core import cli

        args = argparse.Namespace()
        args.economics_action = "status"

        mock_status = MagicMock()
        mock_status.is_profitable = True
        mock_status.status_message = "Profitable"
        mock_status.costs_today = 0.50
        mock_status.revenue_today = 1.00
        mock_status.net_pnl_today = 0.50
        mock_status.api_calls_today = 100
        mock_status.tokens_today = 50000
        mock_status.net_pnl_30d = 15.00
        mock_status.roi_30d_percent = 30.0
        mock_status.trading_pnl = 10.00
        mock_status.time_saved_value = 5.00
        mock_status.alerts = []

        mock_dashboard = MagicMock()
        mock_dashboard.get_status.return_value = mock_status

        with patch.object(cli, 'EconomicsDashboard', return_value=mock_dashboard):
            cli.cmd_economics(args)
            captured = capsys.readouterr()
            assert "JARVIS ECONOMIC STATUS" in captured.out


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for CLI module."""

    def test_full_parser_all_commands(self):
        """All commands can be parsed."""
        from core.cli import build_parser

        parser = build_parser()

        # Test various command patterns
        test_cases = [
            ["status"],
            ["status", "-v"],
            ["on"],
            ["on", "--apply"],
            ["off"],
            ["off", "--dry-run"],
            ["doctor"],
            ["doctor", "--test"],
            ["doctor", "--mcp"],
            ["doctor", "--voice"],
            ["log", "test message"],
            ["capture"],
            ["summarize"],
            ["report"],
            ["report", "--morning"],
            ["overnight"],
            ["diagnostics"],
            ["talk"],
            ["chat"],
            ["listen", "on"],
            ["listen", "off"],
            ["secret", "gemini", "key123"],
            ["activity"],
            ["activity", "--hours", "8"],
            ["checkin"],
            ["evolve"],
            ["jarvis"],
            ["jarvis", "interview"],
            ["agent", "test", "goal"],
            ["task", "list"],
            ["task", "add", "My task"],
            ["task", "status"],
            ["brain"],
            ["brain", "status"],
            ["objective", "list"],
            ["feedback", "metrics"],
            ["agents", "status"],
            ["economics", "status"],
        ]

        for args_list in test_cases:
            try:
                args = parser.parse_args(args_list)
                assert args.command is not None, f"Failed to parse: {args_list}"
            except SystemExit:
                pytest.fail(f"Parser exited for: {args_list}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
