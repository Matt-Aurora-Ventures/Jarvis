"""
Tests for core/admin/actions.py - Admin action implementations.
"""

import os
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest


class TestGetStatus:
    """Tests for get_status function."""

    def test_get_status_returns_dict(self):
        """get_status should return a dictionary with status info."""
        from core.admin.actions import get_status

        status = get_status()

        assert isinstance(status, dict)
        assert "uptime" in status or "system" in status

    def test_get_status_includes_system_info(self):
        """Status should include basic system information."""
        from core.admin.actions import get_status

        status = get_status()

        # Should have some system metrics
        assert any(k in status for k in ["cpu", "memory", "disk", "system"])

    def test_get_status_includes_bot_info(self):
        """Status should include bot component information."""
        from core.admin.actions import get_status

        status = get_status()

        # Should have bots section or components
        assert "bots" in status or "components" in status or "services" in status


class TestGetLogs:
    """Tests for get_logs function."""

    def test_get_logs_returns_string(self):
        """get_logs should return a string with log content."""
        from core.admin.actions import get_logs

        # Create a temp log file
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            log_file.write_text("Line 1\nLine 2\nLine 3\n")

            with patch("core.admin.actions.LOG_DIR", Path(tmpdir)):
                logs = get_logs("test", lines=10)

            assert isinstance(logs, str)
            assert "Line" in logs

    def test_get_logs_respects_line_limit(self):
        """get_logs should only return requested number of lines."""
        from core.admin.actions import get_logs

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            log_file.write_text("\n".join([f"Line {i}" for i in range(100)]))

            with patch("core.admin.actions.LOG_DIR", Path(tmpdir)):
                logs = get_logs("test", lines=5)

            lines = [l for l in logs.strip().split("\n") if l]
            assert len(lines) <= 5

    def test_get_logs_handles_missing_bot(self):
        """get_logs should handle non-existent bot gracefully."""
        from core.admin.actions import get_logs

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("core.admin.actions.LOG_DIR", Path(tmpdir)):
                logs = get_logs("nonexistent_bot", lines=10)

            assert "not found" in logs.lower() or "no logs" in logs.lower() or logs == ""


class TestRestartBot:
    """Tests for restart_bot function."""

    @pytest.mark.asyncio
    async def test_restart_bot_returns_result(self):
        """restart_bot should return a result dict."""
        from core.admin.actions import restart_bot

        # Mock the supervisor
        with patch("core.admin.actions._get_supervisor") as mock_get_supervisor:
            mock_supervisor = MagicMock()
            mock_supervisor.restart_component = AsyncMock(return_value=True)
            mock_get_supervisor.return_value = mock_supervisor

            result = await restart_bot("telegram_bot")

            assert isinstance(result, dict)
            assert "success" in result or "status" in result

    @pytest.mark.asyncio
    async def test_restart_bot_handles_invalid_bot(self):
        """restart_bot should handle invalid bot names."""
        from core.admin.actions import restart_bot

        with patch("core.admin.actions._get_supervisor") as mock_get_supervisor:
            mock_supervisor = MagicMock()
            mock_supervisor.restart_component = AsyncMock(side_effect=KeyError("unknown_bot"))
            mock_get_supervisor.return_value = mock_supervisor

            result = await restart_bot("unknown_bot")

            assert result.get("success") is False or "error" in result


class TestClearCache:
    """Tests for clear_cache function."""

    def test_clear_cache_returns_result(self):
        """clear_cache should return a result dict."""
        from core.admin.actions import clear_cache

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            cache_dir.mkdir()
            (cache_dir / "test.json").write_text("{}")

            with patch("core.admin.actions.CACHE_DIRS", [cache_dir]):
                result = clear_cache()

            assert isinstance(result, dict)
            assert "cleared" in result or "success" in result

    def test_clear_cache_removes_files(self):
        """clear_cache should actually remove cache files."""
        from core.admin.actions import clear_cache

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            cache_dir.mkdir()
            test_file = cache_dir / "test_cache.json"
            test_file.write_text('{"key": "value"}')

            with patch("core.admin.actions.CACHE_DIRS", [cache_dir]):
                clear_cache()

            # Either file is removed or cache_dir is emptied
            files_remaining = list(cache_dir.glob("*")) if cache_dir.exists() else []
            assert len(files_remaining) == 0 or not test_file.exists()


class TestReloadConfig:
    """Tests for reload_config function."""

    def test_reload_config_returns_result(self):
        """reload_config should return a result dict."""
        from core.admin.actions import reload_config

        with patch("core.admin.actions._reload_all_configs") as mock_reload:
            mock_reload.return_value = {"reloaded": ["config1", "config2"]}

            result = reload_config()

            assert isinstance(result, dict)

    def test_reload_config_calls_reload_functions(self):
        """reload_config should trigger config reloads."""
        from core.admin.actions import reload_config

        with patch("core.admin.actions._reload_all_configs") as mock_reload:
            mock_reload.return_value = {"reloaded": []}

            reload_config()

            mock_reload.assert_called_once()


class TestHealthCheck:
    """Tests for health_check function."""

    @pytest.mark.asyncio
    async def test_health_check_returns_dict(self):
        """health_check should return a health status dict."""
        from core.admin.actions import health_check

        result = await health_check()

        assert isinstance(result, dict)
        assert "healthy" in result or "status" in result

    @pytest.mark.asyncio
    async def test_health_check_includes_components(self):
        """health_check should check multiple components."""
        from core.admin.actions import health_check

        with patch("core.admin.actions._check_component_health") as mock_check:
            mock_check.return_value = {"status": "healthy"}

            result = await health_check()

            assert isinstance(result, dict)
            # Should have either overall status or component statuses
            assert len(result) > 0
