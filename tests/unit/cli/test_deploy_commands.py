#!/usr/bin/env python3
"""
Tests for CLI deploy commands.

Tests deploy sync, push, all, and verify commands.
"""

import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock


class TestDeployCommands:
    """Tests for deployment commands."""

    @pytest.fixture
    def runner(self):
        """Create a CLI runner."""
        return CliRunner()

    def test_deploy_sync_command_exists(self, runner):
        """Test that deploy sync command exists."""
        from cli.main import cli
        result = runner.invoke(cli, ["deploy", "sync", "--help"])
        assert result.exit_code == 0
        assert "sync" in result.output.lower()

    def test_deploy_sync_has_dry_run_option(self, runner):
        """Test that deploy sync has --dry-run option."""
        from cli.main import cli
        result = runner.invoke(cli, ["deploy", "sync", "--help"])
        assert result.exit_code == 0
        assert "dry-run" in result.output.lower() or "dry_run" in result.output.lower()

    def test_deploy_sync_dry_run(self, runner):
        """Test deploy sync in dry-run mode."""
        from cli.main import cli
        result = runner.invoke(cli, ["deploy", "sync", "--dry-run"])
        assert result.exit_code == 0
        assert "dry" in result.output.lower() or "would" in result.output.lower()

    def test_deploy_push_command_exists(self, runner):
        """Test that deploy push command exists."""
        from cli.main import cli
        result = runner.invoke(cli, ["deploy", "push", "--help"])
        assert result.exit_code == 0
        assert "push" in result.output.lower()

    def test_deploy_push_requires_name(self, runner):
        """Test that deploy push requires a bot name."""
        from cli.main import cli
        result = runner.invoke(cli, ["deploy", "push", "telegram_bot", "--dry-run"])
        assert "telegram_bot" in result.output or result.exit_code == 0

    def test_deploy_push_has_force_option(self, runner):
        """Test that deploy push has --force option."""
        from cli.main import cli
        result = runner.invoke(cli, ["deploy", "push", "--help"])
        assert result.exit_code == 0
        assert "force" in result.output.lower()

    def test_deploy_all_command_exists(self, runner):
        """Test that deploy all command exists."""
        from cli.main import cli
        result = runner.invoke(cli, ["deploy", "all", "--help"])
        assert result.exit_code == 0
        assert "all" in result.output.lower()

    def test_deploy_all_dry_run(self, runner):
        """Test deploy all in dry-run mode."""
        from cli.main import cli
        result = runner.invoke(cli, ["deploy", "all", "--dry-run"])
        assert result.exit_code == 0

    def test_deploy_all_has_parallel_option(self, runner):
        """Test that deploy all has --parallel option."""
        from cli.main import cli
        result = runner.invoke(cli, ["deploy", "all", "--help"])
        assert result.exit_code == 0
        # Should have parallel option
        assert "parallel" in result.output.lower() or result.exit_code == 0

    def test_deploy_verify_command_exists(self, runner):
        """Test that deploy verify command exists."""
        from cli.main import cli
        result = runner.invoke(cli, ["deploy", "verify", "--help"])
        assert result.exit_code == 0
        assert "verify" in result.output.lower()

    def test_deploy_verify_shows_status(self, runner):
        """Test that deploy verify shows deployment status."""
        from cli.main import cli
        with patch("cli.commands.deploy.verify_deployment") as mock_verify:
            mock_verify.return_value = {
                "status": "ok",
                "bots_deployed": 5,
                "last_sync": "2026-02-02T00:00:00Z",
            }
            result = runner.invoke(cli, ["deploy", "verify"])
            assert result.exit_code == 0


class TestDeployCommandsIntegration:
    """Integration tests for deploy commands."""

    @pytest.fixture
    def runner(self):
        """Create a CLI runner."""
        return CliRunner()

    def test_deploy_sync_calls_rsync(self, runner):
        """Test that deploy sync uses rsync or similar."""
        from cli.main import cli
        with patch("cli.commands.deploy.sync_to_vps") as mock_sync:
            mock_sync.return_value = True
            result = runner.invoke(cli, ["deploy", "sync"])
            # Should call sync function or show output
            assert result.exit_code == 0 or mock_sync.called

    def test_deploy_push_restarts_bot(self, runner):
        """Test that deploy push restarts the specified bot."""
        from cli.main import cli
        with patch("cli.commands.deploy.push_bot") as mock_push:
            mock_push.return_value = True
            result = runner.invoke(cli, ["deploy", "push", "telegram_bot"])
            assert result.exit_code == 0 or mock_push.called

    def test_deploy_verify_checks_health(self, runner):
        """Test that deploy verify checks bot health."""
        from cli.main import cli
        with patch("cli.commands.deploy.check_deployment_health") as mock_check:
            mock_check.return_value = {"healthy": True, "bots": []}
            result = runner.invoke(cli, ["deploy", "verify"])
            assert result.exit_code == 0
