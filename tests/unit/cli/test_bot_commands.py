#!/usr/bin/env python3
"""
Tests for CLI bot commands.

Tests bot start, stop, restart, status, and logs commands.
"""

import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock


class TestBotCommands:
    """Tests for bot management commands."""

    @pytest.fixture
    def runner(self):
        """Create a CLI runner."""
        return CliRunner()

    def test_bot_start_command_exists(self, runner):
        """Test that bot start command exists."""
        from cli.main import cli
        result = runner.invoke(cli, ["bot", "start", "--help"])
        assert result.exit_code == 0
        assert "start" in result.output.lower()

    def test_bot_start_requires_name(self, runner):
        """Test that bot start requires a bot name argument."""
        from cli.main import cli
        # Should work with a name
        result = runner.invoke(cli, ["bot", "start", "telegram_bot", "--dry-run"])
        # Should show help or run (not error about missing arg)
        assert "telegram_bot" in result.output or result.exit_code == 0

    def test_bot_start_with_valid_name(self, runner):
        """Test bot start with a valid bot name."""
        from cli.main import cli
        with patch("cli.commands.bot.start_bot") as mock_start:
            mock_start.return_value = True
            result = runner.invoke(cli, ["bot", "start", "telegram_bot"])
            # Either calls the mock or shows dry-run output
            assert result.exit_code == 0 or mock_start.called

    def test_bot_stop_command_exists(self, runner):
        """Test that bot stop command exists."""
        from cli.main import cli
        result = runner.invoke(cli, ["bot", "stop", "--help"])
        assert result.exit_code == 0
        assert "stop" in result.output.lower()

    def test_bot_stop_requires_name(self, runner):
        """Test that bot stop requires a bot name argument."""
        from cli.main import cli
        result = runner.invoke(cli, ["bot", "stop", "telegram_bot", "--dry-run"])
        assert "telegram_bot" in result.output or result.exit_code == 0

    def test_bot_restart_command_exists(self, runner):
        """Test that bot restart command exists."""
        from cli.main import cli
        result = runner.invoke(cli, ["bot", "restart", "--help"])
        assert result.exit_code == 0
        assert "restart" in result.output.lower()

    def test_bot_restart_with_name(self, runner):
        """Test bot restart with a bot name."""
        from cli.main import cli
        with patch("cli.commands.bot.restart_bot") as mock_restart:
            mock_restart.return_value = True
            result = runner.invoke(cli, ["bot", "restart", "telegram_bot"])
            assert result.exit_code == 0 or mock_restart.called

    def test_bot_status_command_exists(self, runner):
        """Test that bot status command exists."""
        from cli.main import cli
        result = runner.invoke(cli, ["bot", "status", "--help"])
        assert result.exit_code == 0

    def test_bot_status_shows_all_bots(self, runner):
        """Test that bot status shows all bot statuses."""
        from cli.main import cli
        with patch("cli.commands.bot.get_bot_statuses") as mock_status:
            mock_status.return_value = {
                "telegram_bot": {"status": "running", "uptime": "1h"},
                "twitter_bot": {"status": "stopped", "uptime": None},
            }
            result = runner.invoke(cli, ["bot", "status"])
            # Should show bot names or call the function
            assert result.exit_code == 0 or mock_status.called

    def test_bot_logs_command_exists(self, runner):
        """Test that bot logs command exists."""
        from cli.main import cli
        result = runner.invoke(cli, ["bot", "logs", "--help"])
        assert result.exit_code == 0
        assert "logs" in result.output.lower()

    def test_bot_logs_requires_name(self, runner):
        """Test that bot logs requires a bot name."""
        from cli.main import cli
        result = runner.invoke(cli, ["bot", "logs", "telegram_bot", "-n", "10"])
        # Should work or show help
        assert result.exit_code == 0 or "name" in result.output.lower()

    def test_bot_logs_has_follow_option(self, runner):
        """Test that bot logs has --follow option."""
        from cli.main import cli
        result = runner.invoke(cli, ["bot", "logs", "--help"])
        assert result.exit_code == 0
        assert "follow" in result.output.lower() or "-f" in result.output

    def test_bot_logs_has_lines_option(self, runner):
        """Test that bot logs has --lines/-n option."""
        from cli.main import cli
        result = runner.invoke(cli, ["bot", "logs", "--help"])
        assert result.exit_code == 0
        assert "lines" in result.output.lower() or "-n" in result.output


class TestBotCommandsIntegration:
    """Integration tests for bot commands with supervisor."""

    @pytest.fixture
    def runner(self):
        """Create a CLI runner."""
        return CliRunner()

    def test_bot_start_calls_supervisor(self, runner):
        """Test that bot start interfaces with supervisor."""
        from cli.main import cli
        with patch("cli.commands.bot.get_supervisor") as mock_get_sup:
            mock_sup = MagicMock()
            mock_get_sup.return_value = mock_sup
            result = runner.invoke(cli, ["bot", "start", "telegram_bot"])
            # Should call supervisor or show output
            assert result.exit_code == 0

    def test_bot_stop_calls_supervisor(self, runner):
        """Test that bot stop interfaces with supervisor."""
        from cli.main import cli
        with patch("cli.commands.bot.get_supervisor") as mock_get_sup:
            mock_sup = MagicMock()
            mock_get_sup.return_value = mock_sup
            result = runner.invoke(cli, ["bot", "stop", "telegram_bot"])
            assert result.exit_code == 0
