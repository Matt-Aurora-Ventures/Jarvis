"""
Unit tests for core/dashboard/data.py - Dashboard Data Layer.

Tests the DashboardData class and its methods:
- get_bot_stats()
- get_api_stats()
- get_system_stats()
- get_error_summary()
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict
from unittest.mock import MagicMock, patch, AsyncMock

import pytest


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def dashboard_data():
    """Create a DashboardData instance for testing."""
    from core.dashboard.data import DashboardData
    return DashboardData()


@pytest.fixture
def mock_supervisor_status():
    """Mock supervisor component status."""
    return {
        "buy_bot": {
            "status": "running",
            "restart_count": 0,
            "uptime_seconds": 86400,
            "last_error": None,
        },
        "telegram_bot": {
            "status": "running",
            "restart_count": 1,
            "uptime_seconds": 3600,
            "last_error": None,
        },
        "twitter_poster": {
            "status": "stopped",
            "restart_count": 5,
            "uptime_seconds": 0,
            "last_error": "OAuth token expired",
        },
    }


# =============================================================================
# DashboardData CLASS TESTS
# =============================================================================

class TestDashboardDataImport:
    """Tests for module imports."""

    def test_import_dashboard_data_module(self):
        """Test that DashboardData can be imported."""
        from core.dashboard.data import DashboardData
        assert DashboardData is not None

    def test_dashboard_data_instantiation(self):
        """Test that DashboardData can be instantiated."""
        from core.dashboard.data import DashboardData
        data = DashboardData()
        assert data is not None


class TestGetBotStats:
    """Tests for get_bot_stats() method."""

    def test_get_bot_stats_returns_dict(self, dashboard_data):
        """Test that get_bot_stats returns a dictionary."""
        result = dashboard_data.get_bot_stats()
        assert isinstance(result, dict)

    def test_get_bot_stats_has_required_keys(self, dashboard_data):
        """Test that get_bot_stats has required keys."""
        result = dashboard_data.get_bot_stats()
        assert "total_bots" in result
        assert "running" in result
        assert "stopped" in result
        assert "errored" in result
        assert "bots" in result

    def test_get_bot_stats_with_mock_supervisor(self, dashboard_data, mock_supervisor_status):
        """Test bot stats with mocked supervisor."""
        with patch.object(dashboard_data, '_get_supervisor_status', return_value=mock_supervisor_status):
            result = dashboard_data.get_bot_stats()

            assert result["total_bots"] == 3
            assert result["running"] == 2
            assert result["stopped"] == 1

    def test_get_bot_stats_handles_empty_supervisor(self, dashboard_data):
        """Test bot stats when supervisor returns empty."""
        with patch.object(dashboard_data, '_get_supervisor_status', return_value={}):
            result = dashboard_data.get_bot_stats()

            assert result["total_bots"] == 0
            assert result["running"] == 0

    def test_get_bot_stats_individual_bot_info(self, dashboard_data, mock_supervisor_status):
        """Test that individual bot info is included."""
        with patch.object(dashboard_data, '_get_supervisor_status', return_value=mock_supervisor_status):
            result = dashboard_data.get_bot_stats()

            assert "buy_bot" in result["bots"]
            assert result["bots"]["buy_bot"]["status"] == "running"
            assert "uptime_seconds" in result["bots"]["buy_bot"]


class TestGetApiStats:
    """Tests for get_api_stats() method."""

    def test_get_api_stats_returns_dict(self, dashboard_data):
        """Test that get_api_stats returns a dictionary."""
        result = dashboard_data.get_api_stats()
        assert isinstance(result, dict)

    def test_get_api_stats_has_required_keys(self, dashboard_data):
        """Test that get_api_stats has required keys."""
        result = dashboard_data.get_api_stats()
        assert "total_requests" in result
        assert "requests_per_minute" in result
        assert "avg_latency_ms" in result
        assert "error_rate" in result
        assert "endpoints" in result

    def test_get_api_stats_with_mock_metrics(self, dashboard_data):
        """Test API stats with mocked metrics collector."""
        mock_metrics = MagicMock()
        mock_metrics.get_request_count.return_value = 1000
        mock_metrics.get_requests_per_minute.return_value = 50.5
        mock_metrics.get_avg_latency_ms.return_value = 125.3
        mock_metrics.get_error_rate.return_value = 0.02
        mock_metrics.get_endpoint_stats.return_value = {
            "/api/v1/health": {"count": 500, "avg_latency_ms": 50.0},
            "/api/v1/trades": {"count": 300, "avg_latency_ms": 200.0},
        }

        with patch.object(dashboard_data, '_get_metrics_collector', return_value=mock_metrics):
            result = dashboard_data.get_api_stats()

            assert result["total_requests"] == 1000
            assert result["requests_per_minute"] == 50.5
            assert result["avg_latency_ms"] == 125.3
            assert result["error_rate"] == 0.02

    def test_get_api_stats_handles_no_metrics(self, dashboard_data):
        """Test API stats when metrics collector is unavailable."""
        with patch.object(dashboard_data, '_get_metrics_collector', return_value=None):
            result = dashboard_data.get_api_stats()

            # Should return zeros/defaults
            assert result["total_requests"] == 0
            assert result["error_rate"] == 0.0


class TestGetSystemStats:
    """Tests for get_system_stats() method."""

    def test_get_system_stats_returns_dict(self, dashboard_data):
        """Test that get_system_stats returns a dictionary."""
        result = dashboard_data.get_system_stats()
        assert isinstance(result, dict)

    def test_get_system_stats_has_required_keys(self, dashboard_data):
        """Test that get_system_stats has required keys."""
        result = dashboard_data.get_system_stats()
        assert "cpu_percent" in result
        assert "memory_percent" in result
        assert "memory_mb" in result
        assert "disk_percent" in result
        assert "uptime_seconds" in result

    def test_get_system_stats_has_valid_cpu_percent(self, dashboard_data):
        """Test that CPU percent is in valid range."""
        result = dashboard_data.get_system_stats()
        assert 0 <= result["cpu_percent"] <= 100

    def test_get_system_stats_has_valid_memory_percent(self, dashboard_data):
        """Test that memory percent is in valid range."""
        result = dashboard_data.get_system_stats()
        assert 0 <= result["memory_percent"] <= 100

    def test_get_system_stats_has_positive_memory_mb(self, dashboard_data):
        """Test that memory MB is positive."""
        result = dashboard_data.get_system_stats()
        assert result["memory_mb"] >= 0


class TestGetErrorSummary:
    """Tests for get_error_summary() method."""

    def test_get_error_summary_returns_dict(self, dashboard_data):
        """Test that get_error_summary returns a dictionary."""
        result = dashboard_data.get_error_summary()
        assert isinstance(result, dict)

    def test_get_error_summary_has_required_keys(self, dashboard_data):
        """Test that get_error_summary has required keys."""
        result = dashboard_data.get_error_summary()
        assert "total_errors_24h" in result
        assert "errors_by_type" in result
        assert "errors_by_component" in result
        assert "recent_errors" in result

    def test_get_error_summary_with_mock_errors(self, dashboard_data):
        """Test error summary with mocked error data."""
        mock_log_aggregator = MagicMock()
        mock_log_aggregator.get_error_count.return_value = 42
        mock_log_aggregator.get_errors_by_type.return_value = {
            "ValueError": 20,
            "KeyError": 15,
            "RuntimeError": 7,
        }
        mock_log_aggregator.get_errors_by_component.return_value = {
            "trading": 25,
            "telegram": 10,
            "twitter": 7,
        }
        mock_log_aggregator.get_recent_errors.return_value = [
            {"message": "Connection timeout", "component": "trading", "timestamp": "2026-02-02T12:00:00Z"},
            {"message": "Rate limit exceeded", "component": "twitter", "timestamp": "2026-02-02T11:55:00Z"},
        ]

        with patch.object(dashboard_data, '_get_log_aggregator', return_value=mock_log_aggregator):
            result = dashboard_data.get_error_summary()

            assert result["total_errors_24h"] == 42
            assert result["errors_by_type"]["ValueError"] == 20
            assert len(result["recent_errors"]) == 2

    def test_get_error_summary_handles_no_log_aggregator(self, dashboard_data):
        """Test error summary when log aggregator is unavailable."""
        with patch.object(dashboard_data, '_get_log_aggregator', return_value=None):
            result = dashboard_data.get_error_summary()

            assert result["total_errors_24h"] == 0
            assert result["errors_by_type"] == {}
            assert result["recent_errors"] == []


class TestGetAllStats:
    """Tests for get_all_stats() method."""

    def test_get_all_stats_returns_dict(self, dashboard_data):
        """Test that get_all_stats returns a dictionary."""
        result = dashboard_data.get_all_stats()
        assert isinstance(result, dict)

    def test_get_all_stats_has_all_sections(self, dashboard_data):
        """Test that get_all_stats has all stat sections."""
        result = dashboard_data.get_all_stats()

        assert "bots" in result
        assert "api" in result
        assert "system" in result
        assert "errors" in result
        assert "timestamp" in result

    def test_get_all_stats_timestamp_is_recent(self, dashboard_data):
        """Test that timestamp is recent (within last minute)."""
        result = dashboard_data.get_all_stats()

        # Parse timestamp
        ts = datetime.fromisoformat(result["timestamp"].replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = (now - ts).total_seconds()

        assert abs(delta) < 60  # Within last minute
