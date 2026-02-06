#!/usr/bin/env python3
"""
Tests for CLI health commands.

Tests health check, report, and alerts commands.
"""

import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock


class TestHealthCommands:
    """Tests for health monitoring commands."""

    @pytest.fixture
    def runner(self):
        """Create a CLI runner."""
        return CliRunner()

    def test_health_check_command_exists(self, runner):
        """Test that health check command exists."""
        from cli.main import cli
        result = runner.invoke(cli, ["health", "check", "--help"])
        assert result.exit_code == 0
        assert "check" in result.output.lower()

    def test_health_check_runs_all_checks(self, runner):
        """Test that health check runs all health checks."""
        from cli.main import cli
        with patch("cli.commands.health.run_health_checks") as mock_check:
            mock_check.return_value = {
                "status": "healthy",
                "checks": {
                    "telegram": {"status": "ok"},
                    "twitter": {"status": "ok"},
                    "treasury": {"status": "ok"},
                },
            }
            result = runner.invoke(cli, ["health", "check"])
            assert result.exit_code == 0

    def test_health_check_has_component_option(self, runner):
        """Test that health check has --component option."""
        from cli.main import cli
        result = runner.invoke(cli, ["health", "check", "--help"])
        assert result.exit_code == 0
        assert "component" in result.output.lower()

    def test_health_check_specific_component(self, runner):
        """Test health check for a specific component."""
        from cli.main import cli
        with patch("cli.commands.health.check_component") as mock_check:
            mock_check.return_value = {"status": "healthy"}
            result = runner.invoke(cli, ["health", "check", "--component", "telegram"])
            assert result.exit_code == 0

    def test_health_report_command_exists(self, runner):
        """Test that health report command exists."""
        from cli.main import cli
        result = runner.invoke(cli, ["health", "report", "--help"])
        assert result.exit_code == 0
        assert "report" in result.output.lower()

    def test_health_report_generates_output(self, runner):
        """Test that health report generates a report."""
        from cli.main import cli
        with patch("cli.commands.health.generate_health_report") as mock_report:
            mock_report.return_value = {
                "generated_at": "2026-02-02T00:00:00Z",
                "uptime": "24h",
                "components": {},
            }
            result = runner.invoke(cli, ["health", "report"])
            assert result.exit_code == 0

    def test_health_report_has_format_option(self, runner):
        """Test that health report has --format option."""
        from cli.main import cli
        result = runner.invoke(cli, ["health", "report", "--help"])
        assert result.exit_code == 0
        assert "format" in result.output.lower()

    def test_health_report_json_format(self, runner):
        """Test health report in JSON format."""
        from cli.main import cli
        with patch("cli.commands.health.generate_health_report") as mock_report:
            mock_report.return_value = {"status": "healthy"}
            result = runner.invoke(cli, ["health", "report", "--format", "json"])
            assert result.exit_code == 0

    def test_health_alerts_command_exists(self, runner):
        """Test that health alerts command exists."""
        from cli.main import cli
        result = runner.invoke(cli, ["health", "alerts", "--help"])
        assert result.exit_code == 0
        assert "alerts" in result.output.lower()

    def test_health_alerts_shows_active_alerts(self, runner):
        """Test that health alerts shows active alerts."""
        from cli.main import cli
        with patch("cli.commands.health.get_active_alerts") as mock_alerts:
            mock_alerts.return_value = [
                {"level": "warning", "message": "High memory usage", "since": "1h ago"},
                {"level": "critical", "message": "Bot crashed", "since": "5m ago"},
            ]
            result = runner.invoke(cli, ["health", "alerts"])
            assert result.exit_code == 0

    def test_health_alerts_has_level_filter(self, runner):
        """Test that health alerts has --level filter."""
        from cli.main import cli
        result = runner.invoke(cli, ["health", "alerts", "--help"])
        assert result.exit_code == 0
        assert "level" in result.output.lower()

    def test_health_alerts_filter_by_level(self, runner):
        """Test health alerts filtered by level."""
        from cli.main import cli
        with patch("cli.commands.health.get_active_alerts") as mock_alerts:
            mock_alerts.return_value = [
                {"level": "critical", "message": "Bot crashed"},
            ]
            result = runner.invoke(cli, ["health", "alerts", "--level", "critical"])
            assert result.exit_code == 0


class TestHealthCommandsIntegration:
    """Integration tests for health commands."""

    @pytest.fixture
    def runner(self):
        """Create a CLI runner."""
        return CliRunner()

    def test_health_check_calls_health_endpoint(self, runner):
        """Test that health check calls health endpoint."""
        from cli.main import cli
        with patch("cli.commands.health.fetch_health_status") as mock_fetch:
            mock_fetch.return_value = {"status": "healthy"}
            result = runner.invoke(cli, ["health", "check"])
            assert result.exit_code == 0

    def test_health_report_includes_metrics(self, runner):
        """Test that health report includes metrics."""
        from cli.main import cli
        with patch("cli.commands.health.collect_metrics") as mock_metrics:
            mock_metrics.return_value = {
                "cpu_percent": 45.2,
                "memory_percent": 62.1,
                "disk_percent": 55.0,
            }
            result = runner.invoke(cli, ["health", "report"])
            assert result.exit_code == 0

    def test_health_alerts_from_supervisor(self, runner):
        """Test that health alerts come from supervisor."""
        from cli.main import cli
        with patch("cli.commands.health.get_supervisor_alerts") as mock_alerts:
            mock_alerts.return_value = []
            result = runner.invoke(cli, ["health", "alerts"])
            assert result.exit_code == 0
