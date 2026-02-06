#!/usr/bin/env python3
"""
Tests for CLI main module.

Tests the main CLI entry point with global options.
"""

import pytest
from click.testing import CliRunner


class TestCLIMain:
    """Tests for the main CLI entry point."""

    @pytest.fixture
    def runner(self):
        """Create a CLI runner."""
        return CliRunner()

    def test_cli_exists(self):
        """Test that the main CLI entry point exists."""
        from cli.main import cli
        assert cli is not None

    def test_cli_has_version_option(self, runner):
        """Test that --version option works."""
        from cli.main import cli
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "jarvis" in result.output.lower() or "version" in result.output.lower()

    def test_cli_has_help_option(self, runner):
        """Test that --help option works."""
        from cli.main import cli
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.output

    def test_cli_has_verbose_option(self, runner):
        """Test that --verbose option is recognized."""
        from cli.main import cli
        result = runner.invoke(cli, ["--verbose", "--help"])
        assert result.exit_code == 0

    def test_cli_has_config_option(self, runner):
        """Test that --config option is recognized."""
        from cli.main import cli
        result = runner.invoke(cli, ["--config", "custom.yaml", "--help"])
        assert result.exit_code == 0

    def test_cli_has_bot_command_group(self, runner):
        """Test that bot command group exists."""
        from cli.main import cli
        result = runner.invoke(cli, ["bot", "--help"])
        assert result.exit_code == 0
        assert "bot" in result.output.lower()

    def test_cli_has_deploy_command_group(self, runner):
        """Test that deploy command group exists."""
        from cli.main import cli
        result = runner.invoke(cli, ["deploy", "--help"])
        assert result.exit_code == 0
        assert "deploy" in result.output.lower()

    def test_cli_has_health_command_group(self, runner):
        """Test that health command group exists."""
        from cli.main import cli
        result = runner.invoke(cli, ["health", "--help"])
        assert result.exit_code == 0
        assert "health" in result.output.lower()

    def test_cli_invalid_command(self, runner):
        """Test that invalid commands show error."""
        from cli.main import cli
        result = runner.invoke(cli, ["nonexistent"])
        assert result.exit_code != 0
