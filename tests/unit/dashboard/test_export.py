"""
Unit tests for core/dashboard/export.py - Data Export.

Tests the export functions:
- export_json(data) -> str
- export_csv(data) -> str
- export_html(data) -> str
"""

from datetime import datetime, timezone
from typing import Any, Dict

import pytest


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def sample_dashboard_data():
    """Sample dashboard data for export testing."""
    return {
        "timestamp": "2026-02-02T12:00:00Z",
        "bots": {
            "total_bots": 5,
            "running": 4,
            "stopped": 1,
            "bots": {
                "buy_bot": {"status": "running", "uptime_seconds": 86400},
                "telegram_bot": {"status": "running", "uptime_seconds": 3600},
                "twitter_poster": {"status": "stopped", "uptime_seconds": 0},
            }
        },
        "api": {
            "total_requests": 1000,
            "requests_per_minute": 50.5,
            "avg_latency_ms": 125.3,
            "error_rate": 0.02
        },
        "system": {
            "cpu_percent": 45.5,
            "memory_percent": 62.3,
            "memory_mb": 2048,
            "disk_percent": 55.0,
            "uptime_seconds": 86400
        },
        "errors": {
            "total_errors_24h": 42,
            "errors_by_type": {"ValueError": 20, "KeyError": 15, "RuntimeError": 7},
            "recent_errors": [
                {"message": "Connection timeout", "component": "trading"},
                {"message": "Rate limit exceeded", "component": "twitter"},
            ]
        }
    }


@pytest.fixture
def sample_tabular_data():
    """Sample tabular data for CSV export."""
    return [
        {"name": "buy_bot", "status": "running", "uptime_hours": 24.0, "errors": 0},
        {"name": "telegram_bot", "status": "running", "uptime_hours": 1.0, "errors": 2},
        {"name": "twitter_poster", "status": "stopped", "uptime_hours": 0.0, "errors": 5},
    ]


# =============================================================================
# EXPORT FUNCTION TESTS
# =============================================================================

class TestExportJson:
    """Tests for export_json() function."""

    def test_import_export_json(self):
        """Test that export_json can be imported."""
        from core.dashboard.export import export_json
        assert export_json is not None

    def test_export_json_returns_string(self, sample_dashboard_data):
        """Test that export_json returns a string."""
        from core.dashboard.export import export_json

        result = export_json(sample_dashboard_data)
        assert isinstance(result, str)

    def test_export_json_is_valid_json(self, sample_dashboard_data):
        """Test that export_json produces valid JSON."""
        import json
        from core.dashboard.export import export_json

        result = export_json(sample_dashboard_data)
        # Should not raise
        parsed = json.loads(result)
        assert parsed is not None

    def test_export_json_preserves_data(self, sample_dashboard_data):
        """Test that export_json preserves all data."""
        import json
        from core.dashboard.export import export_json

        result = export_json(sample_dashboard_data)
        parsed = json.loads(result)

        assert parsed["timestamp"] == sample_dashboard_data["timestamp"]
        assert parsed["bots"]["total_bots"] == sample_dashboard_data["bots"]["total_bots"]

    def test_export_json_pretty_option(self, sample_dashboard_data):
        """Test that export_json can produce pretty-printed JSON."""
        from core.dashboard.export import export_json

        result = export_json(sample_dashboard_data, pretty=True)
        # Pretty JSON should have newlines
        assert "\n" in result

    def test_export_json_handles_datetime(self):
        """Test that export_json handles datetime objects."""
        from core.dashboard.export import export_json

        data = {"timestamp": datetime.now(timezone.utc)}
        result = export_json(data)
        assert result is not None
        assert len(result) > 0


class TestExportCsv:
    """Tests for export_csv() function."""

    def test_import_export_csv(self):
        """Test that export_csv can be imported."""
        from core.dashboard.export import export_csv
        assert export_csv is not None

    def test_export_csv_returns_string(self, sample_tabular_data):
        """Test that export_csv returns a string."""
        from core.dashboard.export import export_csv

        result = export_csv(sample_tabular_data)
        assert isinstance(result, str)

    def test_export_csv_has_header(self, sample_tabular_data):
        """Test that export_csv includes header row."""
        from core.dashboard.export import export_csv

        result = export_csv(sample_tabular_data)
        lines = result.strip().split("\n")

        # First line should be header
        header = lines[0]
        assert "name" in header
        assert "status" in header

    def test_export_csv_has_data_rows(self, sample_tabular_data):
        """Test that export_csv includes data rows."""
        from core.dashboard.export import export_csv

        result = export_csv(sample_tabular_data)
        lines = result.strip().split("\n")

        # Should have header + 3 data rows
        assert len(lines) == 4

    def test_export_csv_preserves_values(self, sample_tabular_data):
        """Test that export_csv preserves data values."""
        from core.dashboard.export import export_csv

        result = export_csv(sample_tabular_data)

        assert "buy_bot" in result
        assert "running" in result
        assert "stopped" in result

    def test_export_csv_handles_empty_data(self):
        """Test that export_csv handles empty data."""
        from core.dashboard.export import export_csv

        result = export_csv([])
        assert result is not None  # Should not raise

    def test_export_csv_custom_delimiter(self, sample_tabular_data):
        """Test that export_csv supports custom delimiter."""
        from core.dashboard.export import export_csv

        result = export_csv(sample_tabular_data, delimiter=";")
        assert ";" in result

    def test_export_csv_from_dict(self, sample_dashboard_data):
        """Test that export_csv can flatten nested dict."""
        from core.dashboard.export import export_csv

        # Should handle nested dict by flattening or extracting lists
        result = export_csv(sample_dashboard_data)
        assert result is not None


class TestExportHtml:
    """Tests for export_html() function."""

    def test_import_export_html(self):
        """Test that export_html can be imported."""
        from core.dashboard.export import export_html
        assert export_html is not None

    def test_export_html_returns_string(self, sample_dashboard_data):
        """Test that export_html returns a string."""
        from core.dashboard.export import export_html

        result = export_html(sample_dashboard_data)
        assert isinstance(result, str)

    def test_export_html_is_valid_html(self, sample_dashboard_data):
        """Test that export_html produces valid HTML structure."""
        from core.dashboard.export import export_html

        result = export_html(sample_dashboard_data)

        # Should have basic HTML structure
        assert "<html" in result or "<!DOCTYPE" in result or "<table" in result or "<div" in result

    def test_export_html_contains_data(self, sample_dashboard_data):
        """Test that export_html contains the data."""
        from core.dashboard.export import export_html

        result = export_html(sample_dashboard_data)

        # Should contain some of the data values
        assert "1000" in result or "total_requests" in result  # API stats
        assert "running" in result or "buy_bot" in result  # Bot stats

    def test_export_html_with_title(self, sample_dashboard_data):
        """Test that export_html can include a title."""
        from core.dashboard.export import export_html

        result = export_html(sample_dashboard_data, title="Dashboard Report")

        assert "Dashboard Report" in result

    def test_export_html_table_format(self, sample_tabular_data):
        """Test that export_html can produce table format."""
        from core.dashboard.export import export_html

        result = export_html(sample_tabular_data, format="table")

        assert "<table" in result
        assert "<tr" in result
        assert "<td" in result or "<th" in result

    def test_export_html_escapes_special_chars(self):
        """Test that export_html escapes HTML special characters."""
        from core.dashboard.export import export_html

        data = {"message": "<script>alert('xss')</script>"}
        result = export_html(data)

        # Script tag should be escaped
        assert "<script>" not in result


class TestExportUtilities:
    """Tests for export utility functions."""

    def test_get_export_formats(self):
        """Test that we can get list of export formats."""
        from core.dashboard.export import get_export_formats

        formats = get_export_formats()
        assert "json" in formats
        assert "csv" in formats
        assert "html" in formats

    def test_export_with_format(self, sample_dashboard_data):
        """Test generic export function with format parameter."""
        from core.dashboard.export import export

        json_result = export(sample_dashboard_data, format="json")
        assert json_result is not None

        html_result = export(sample_dashboard_data, format="html")
        assert html_result is not None

    def test_export_invalid_format_raises(self, sample_dashboard_data):
        """Test that invalid format raises ValueError."""
        from core.dashboard.export import export

        with pytest.raises(ValueError):
            export(sample_dashboard_data, format="invalid_format")
