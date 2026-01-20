"""
Unit tests for the Performance Monitoring Dashboard.

Tests cover:
- Real-time metrics collection
- Trading performance stats (win/loss, profit per trade)
- System resource monitoring (CPU, memory)
- Historical data aggregation
- Alert thresholds
- Execution latency tracking
- API response time tracking
"""

import asyncio
import json
import os
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def temp_data_dir():
    """Create temporary data directory for test data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_trades():
    """Sample trade data for testing."""
    return [
        {
            "id": "trade_001",
            "symbol": "SOL",
            "entry_price": 100.0,
            "exit_price": 110.0,
            "amount_usd": 1000.0,
            "profit_usd": 100.0,
            "profit_pct": 10.0,
            "is_win": True,
            "timestamp": datetime.now(timezone.utc) - timedelta(hours=1),
            "latency_ms": 150.0,
        },
        {
            "id": "trade_002",
            "symbol": "RAY",
            "entry_price": 50.0,
            "exit_price": 45.0,
            "amount_usd": 500.0,
            "profit_usd": -50.0,
            "profit_pct": -10.0,
            "is_win": False,
            "timestamp": datetime.now(timezone.utc) - timedelta(hours=2),
            "latency_ms": 200.0,
        },
        {
            "id": "trade_003",
            "symbol": "JUP",
            "entry_price": 25.0,
            "exit_price": 30.0,
            "amount_usd": 750.0,
            "profit_usd": 150.0,
            "profit_pct": 20.0,
            "is_win": True,
            "timestamp": datetime.now(timezone.utc) - timedelta(minutes=30),
            "latency_ms": 120.0,
        },
    ]


@pytest.fixture
def sample_api_metrics():
    """Sample API response time metrics."""
    return [
        {"endpoint": "jupiter_quote", "latency_ms": 120.0, "success": True},
        {"endpoint": "jupiter_quote", "latency_ms": 150.0, "success": True},
        {"endpoint": "jupiter_swap", "latency_ms": 450.0, "success": True},
        {"endpoint": "jupiter_swap", "latency_ms": 500.0, "success": False},
        {"endpoint": "helius_rpc", "latency_ms": 80.0, "success": True},
    ]


# =============================================================================
# PERFORMANCE DASHBOARD TESTS
# =============================================================================

class TestPerformanceDashboardImport:
    """Tests for module import and initialization."""

    def test_import_module(self):
        """Test that performance dashboard module can be imported."""
        from core.monitoring.performance_dashboard import PerformanceDashboard
        assert PerformanceDashboard is not None

    def test_create_dashboard(self, temp_data_dir):
        """Test creating a dashboard instance."""
        from core.monitoring.performance_dashboard import PerformanceDashboard

        dashboard = PerformanceDashboard(data_dir=str(temp_data_dir))
        assert dashboard is not None
        assert dashboard.data_dir == temp_data_dir


class TestTradingPerformance:
    """Tests for trading performance statistics."""

    def test_win_loss_ratio_calculation(self, temp_data_dir, sample_trades):
        """Test win/loss ratio calculation."""
        from core.monitoring.performance_dashboard import PerformanceDashboard

        dashboard = PerformanceDashboard(data_dir=str(temp_data_dir))

        for trade in sample_trades:
            dashboard.record_trade(trade)

        stats = dashboard.get_trading_stats()

        assert "win_loss_ratio" in stats
        assert "win_rate" in stats
        # 2 wins, 1 loss = 2.0 ratio
        assert stats["win_loss_ratio"] == 2.0
        # Win rate = 2/3 = 66.67%
        assert abs(stats["win_rate"] - 66.67) < 0.1

    def test_average_profit_per_trade(self, temp_data_dir, sample_trades):
        """Test average profit per trade calculation."""
        from core.monitoring.performance_dashboard import PerformanceDashboard

        dashboard = PerformanceDashboard(data_dir=str(temp_data_dir))

        for trade in sample_trades:
            dashboard.record_trade(trade)

        stats = dashboard.get_trading_stats()

        assert "avg_profit_usd" in stats
        assert "total_profit_usd" in stats
        # Total: 100 + (-50) + 150 = 200, Avg = 200/3 = 66.67
        assert abs(stats["total_profit_usd"] - 200.0) < 0.01
        assert abs(stats["avg_profit_usd"] - 66.67) < 0.1

    def test_profit_factor_calculation(self, temp_data_dir, sample_trades):
        """Test profit factor (gross profits / gross losses)."""
        from core.monitoring.performance_dashboard import PerformanceDashboard

        dashboard = PerformanceDashboard(data_dir=str(temp_data_dir))

        for trade in sample_trades:
            dashboard.record_trade(trade)

        stats = dashboard.get_trading_stats()

        assert "profit_factor" in stats
        # Gross profit: 100 + 150 = 250, Gross loss: 50
        # Profit factor = 250 / 50 = 5.0
        assert stats["profit_factor"] == 5.0

    def test_no_trades_returns_safe_defaults(self, temp_data_dir):
        """Test that empty trade list returns safe defaults."""
        from core.monitoring.performance_dashboard import PerformanceDashboard

        dashboard = PerformanceDashboard(data_dir=str(temp_data_dir))
        stats = dashboard.get_trading_stats()

        assert stats["win_loss_ratio"] == 0.0
        assert stats["win_rate"] == 0.0
        assert stats["avg_profit_usd"] == 0.0
        assert stats["profit_factor"] == 0.0
        assert stats["trade_count"] == 0


class TestExecutionLatency:
    """Tests for execution latency tracking."""

    def test_record_execution_latency(self, temp_data_dir):
        """Test recording execution latency."""
        from core.monitoring.performance_dashboard import PerformanceDashboard

        dashboard = PerformanceDashboard(data_dir=str(temp_data_dir))

        dashboard.record_execution_latency(150.0, "trade_execution")
        dashboard.record_execution_latency(200.0, "trade_execution")
        dashboard.record_execution_latency(120.0, "trade_execution")

        stats = dashboard.get_latency_stats("trade_execution")

        assert stats["sample_count"] == 3
        assert "avg_ms" in stats
        assert "p50_ms" in stats
        assert "p95_ms" in stats

    def test_execution_latency_percentiles(self, temp_data_dir):
        """Test latency percentile calculations."""
        from core.monitoring.performance_dashboard import PerformanceDashboard

        dashboard = PerformanceDashboard(data_dir=str(temp_data_dir))

        # Add 100 samples with known distribution
        for i in range(100):
            dashboard.record_execution_latency(float(i + 1), "test")

        stats = dashboard.get_latency_stats("test")

        # p50 should be around 50
        assert 45 <= stats["p50_ms"] <= 55
        # p95 should be around 95
        assert 90 <= stats["p95_ms"] <= 100

    def test_latency_by_operation_type(self, temp_data_dir):
        """Test latency tracking by operation type."""
        from core.monitoring.performance_dashboard import PerformanceDashboard

        dashboard = PerformanceDashboard(data_dir=str(temp_data_dir))

        dashboard.record_execution_latency(100.0, "quote")
        dashboard.record_execution_latency(500.0, "swap")

        quote_stats = dashboard.get_latency_stats("quote")
        swap_stats = dashboard.get_latency_stats("swap")

        assert quote_stats["avg_ms"] == 100.0
        assert swap_stats["avg_ms"] == 500.0


class TestAPIResponseTimes:
    """Tests for API response time tracking."""

    def test_record_api_response(self, temp_data_dir, sample_api_metrics):
        """Test recording API response times."""
        from core.monitoring.performance_dashboard import PerformanceDashboard

        dashboard = PerformanceDashboard(data_dir=str(temp_data_dir))

        for metric in sample_api_metrics:
            dashboard.record_api_response(
                endpoint=metric["endpoint"],
                latency_ms=metric["latency_ms"],
                success=metric["success"]
            )

        stats = dashboard.get_api_stats()

        assert "jupiter_quote" in stats
        assert "jupiter_swap" in stats
        assert "helius_rpc" in stats

    def test_api_success_rate(self, temp_data_dir, sample_api_metrics):
        """Test API success rate calculation."""
        from core.monitoring.performance_dashboard import PerformanceDashboard

        dashboard = PerformanceDashboard(data_dir=str(temp_data_dir))

        for metric in sample_api_metrics:
            dashboard.record_api_response(
                endpoint=metric["endpoint"],
                latency_ms=metric["latency_ms"],
                success=metric["success"]
            )

        stats = dashboard.get_api_stats()

        # jupiter_swap: 1 success, 1 failure = 50%
        assert stats["jupiter_swap"]["success_rate"] == 50.0
        # jupiter_quote: 2 successes = 100%
        assert stats["jupiter_quote"]["success_rate"] == 100.0

    def test_api_latency_average(self, temp_data_dir, sample_api_metrics):
        """Test API latency average calculation."""
        from core.monitoring.performance_dashboard import PerformanceDashboard

        dashboard = PerformanceDashboard(data_dir=str(temp_data_dir))

        for metric in sample_api_metrics:
            dashboard.record_api_response(
                endpoint=metric["endpoint"],
                latency_ms=metric["latency_ms"],
                success=metric["success"]
            )

        stats = dashboard.get_api_stats()

        # jupiter_quote: (120 + 150) / 2 = 135
        assert stats["jupiter_quote"]["avg_latency_ms"] == 135.0


class TestSystemResourceMonitoring:
    """Tests for system resource monitoring."""

    def test_record_cpu_usage(self, temp_data_dir):
        """Test recording CPU usage."""
        from core.monitoring.performance_dashboard import PerformanceDashboard

        dashboard = PerformanceDashboard(data_dir=str(temp_data_dir))

        dashboard.record_resource_usage(cpu_percent=25.5, memory_mb=512.0)
        dashboard.record_resource_usage(cpu_percent=30.0, memory_mb=520.0)

        stats = dashboard.get_resource_stats()

        assert "cpu_percent" in stats
        assert "memory_mb" in stats
        assert stats["cpu_percent"]["current"] == 30.0
        assert stats["cpu_percent"]["avg"] == 27.75

    def test_record_memory_usage(self, temp_data_dir):
        """Test recording memory usage."""
        from core.monitoring.performance_dashboard import PerformanceDashboard

        dashboard = PerformanceDashboard(data_dir=str(temp_data_dir))

        dashboard.record_resource_usage(cpu_percent=20.0, memory_mb=1024.0)
        dashboard.record_resource_usage(cpu_percent=20.0, memory_mb=1100.0)

        stats = dashboard.get_resource_stats()

        assert stats["memory_mb"]["current"] == 1100.0
        assert stats["memory_mb"]["max"] == 1100.0

    @pytest.mark.asyncio
    async def test_collect_system_metrics(self, temp_data_dir):
        """Test automatic system metrics collection."""
        from core.monitoring.performance_dashboard import PerformanceDashboard

        dashboard = PerformanceDashboard(data_dir=str(temp_data_dir))

        with patch('psutil.cpu_percent', return_value=15.5):
            with patch('psutil.Process') as mock_process:
                mock_process.return_value.memory_info.return_value.rss = 500 * 1024 * 1024

                await dashboard.collect_system_metrics()

                stats = dashboard.get_resource_stats()
                assert stats["cpu_percent"]["current"] == 15.5
                assert abs(stats["memory_mb"]["current"] - 500.0) < 1.0


class TestHistoricalDataAggregation:
    """Tests for historical data aggregation."""

    def test_aggregate_hourly_stats(self, temp_data_dir, sample_trades):
        """Test hourly statistics aggregation."""
        from core.monitoring.performance_dashboard import PerformanceDashboard

        dashboard = PerformanceDashboard(data_dir=str(temp_data_dir))

        for trade in sample_trades:
            dashboard.record_trade(trade)

        hourly = dashboard.get_hourly_stats(hours=24)

        assert "hourly_data" in hourly
        assert len(hourly["hourly_data"]) <= 24

    def test_aggregate_daily_stats(self, temp_data_dir, sample_trades):
        """Test daily statistics aggregation."""
        from core.monitoring.performance_dashboard import PerformanceDashboard

        dashboard = PerformanceDashboard(data_dir=str(temp_data_dir))

        for trade in sample_trades:
            dashboard.record_trade(trade)

        daily = dashboard.get_daily_stats(days=7)

        assert "daily_data" in daily
        assert len(daily["daily_data"]) <= 7

    def test_get_historical_trades(self, temp_data_dir, sample_trades):
        """Test retrieving historical trades."""
        from core.monitoring.performance_dashboard import PerformanceDashboard

        dashboard = PerformanceDashboard(data_dir=str(temp_data_dir))

        for trade in sample_trades:
            dashboard.record_trade(trade)

        trades = dashboard.get_historical_trades(hours=24)

        assert len(trades) == 3

    def test_data_retention(self, temp_data_dir):
        """Test old data is cleaned up based on retention policy."""
        from core.monitoring.performance_dashboard import PerformanceDashboard

        dashboard = PerformanceDashboard(
            data_dir=str(temp_data_dir),
            retention_days=7
        )

        # Record some old data (mock old timestamp)
        old_trade = {
            "id": "old_trade",
            "symbol": "OLD",
            "profit_usd": 100.0,
            "is_win": True,
            "timestamp": datetime.now(timezone.utc) - timedelta(days=10),
            "latency_ms": 100.0,
        }
        dashboard.record_trade(old_trade)

        # Run cleanup
        dashboard.cleanup_old_data()

        # Old trade should be removed
        trades = dashboard.get_historical_trades(hours=24 * 30)
        old_found = any(t.get("id") == "old_trade" for t in trades)
        assert not old_found


class TestAlertThresholds:
    """Tests for alert threshold configuration and triggering."""

    def test_configure_alert_threshold(self, temp_data_dir):
        """Test configuring an alert threshold."""
        from core.monitoring.performance_dashboard import PerformanceDashboard

        dashboard = PerformanceDashboard(data_dir=str(temp_data_dir))

        dashboard.add_alert_threshold(
            name="high_latency",
            metric="execution_latency_p95",
            threshold=500.0,
            comparison="gt",  # greater than
            severity="warning"
        )

        thresholds = dashboard.get_alert_thresholds()
        assert len(thresholds) == 1
        assert thresholds[0]["name"] == "high_latency"

    def test_alert_triggered_on_breach(self, temp_data_dir):
        """Test alert is triggered when threshold is breached."""
        from core.monitoring.performance_dashboard import PerformanceDashboard

        dashboard = PerformanceDashboard(data_dir=str(temp_data_dir))

        dashboard.add_alert_threshold(
            name="high_latency",
            metric="execution_latency_p95",
            threshold=500.0,
            comparison="gt",
            severity="warning"
        )

        # Record latencies that will trigger alert
        for _ in range(20):
            dashboard.record_execution_latency(600.0, "trade_execution")

        alerts = dashboard.check_alerts()

        assert len(alerts) > 0
        assert any(a["name"] == "high_latency" for a in alerts)

    def test_no_alert_when_within_threshold(self, temp_data_dir):
        """Test no alert when metrics are within threshold."""
        from core.monitoring.performance_dashboard import PerformanceDashboard

        dashboard = PerformanceDashboard(data_dir=str(temp_data_dir))

        dashboard.add_alert_threshold(
            name="high_latency",
            metric="execution_latency_p95",
            threshold=500.0,
            comparison="gt",
            severity="warning"
        )

        # Record latencies below threshold
        for _ in range(20):
            dashboard.record_execution_latency(100.0, "trade_execution")

        alerts = dashboard.check_alerts()

        high_latency_alerts = [a for a in alerts if a["name"] == "high_latency"]
        assert len(high_latency_alerts) == 0

    def test_win_rate_alert(self, temp_data_dir):
        """Test alert on low win rate."""
        from core.monitoring.performance_dashboard import PerformanceDashboard

        dashboard = PerformanceDashboard(data_dir=str(temp_data_dir))

        dashboard.add_alert_threshold(
            name="low_win_rate",
            metric="win_rate",
            threshold=40.0,
            comparison="lt",  # less than
            severity="critical"
        )

        # Record mostly losing trades
        for i in range(10):
            dashboard.record_trade({
                "id": f"trade_{i}",
                "symbol": "TEST",
                "profit_usd": -10.0 if i < 8 else 10.0,  # 8 losses, 2 wins
                "is_win": i >= 8,
                "timestamp": datetime.now(timezone.utc),
                "latency_ms": 100.0,
            })

        alerts = dashboard.check_alerts()

        low_win_alerts = [a for a in alerts if a["name"] == "low_win_rate"]
        assert len(low_win_alerts) > 0


class TestRealTimeMetrics:
    """Tests for real-time metrics collection."""

    @pytest.mark.asyncio
    async def test_get_realtime_snapshot(self, temp_data_dir, sample_trades):
        """Test getting a real-time metrics snapshot."""
        from core.monitoring.performance_dashboard import PerformanceDashboard

        dashboard = PerformanceDashboard(data_dir=str(temp_data_dir))

        for trade in sample_trades:
            dashboard.record_trade(trade)

        with patch('psutil.cpu_percent', return_value=20.0):
            with patch('psutil.Process') as mock_process:
                mock_process.return_value.memory_info.return_value.rss = 512 * 1024 * 1024

                snapshot = await dashboard.get_realtime_snapshot()

        assert "trading" in snapshot
        assert "system" in snapshot
        assert "timestamp" in snapshot

    def test_metrics_stream_subscription(self, temp_data_dir):
        """Test subscribing to metrics stream."""
        from core.monitoring.performance_dashboard import PerformanceDashboard

        dashboard = PerformanceDashboard(data_dir=str(temp_data_dir))

        received_metrics = []

        def callback(metrics):
            received_metrics.append(metrics)

        dashboard.subscribe_to_metrics(callback)

        # Record some data
        dashboard.record_execution_latency(100.0, "test")

        # Callback should have been called
        assert len(received_metrics) > 0


class TestDataPersistence:
    """Tests for data persistence."""

    def test_save_and_load_data(self, temp_data_dir, sample_trades):
        """Test saving and loading dashboard data."""
        from core.monitoring.performance_dashboard import PerformanceDashboard

        # Create first dashboard and add data
        dashboard1 = PerformanceDashboard(data_dir=str(temp_data_dir))
        for trade in sample_trades:
            dashboard1.record_trade(trade)
        dashboard1.save()

        # Create second dashboard and load data
        dashboard2 = PerformanceDashboard(data_dir=str(temp_data_dir))

        stats = dashboard2.get_trading_stats()
        assert stats["trade_count"] == 3

    def test_export_to_json(self, temp_data_dir, sample_trades):
        """Test exporting dashboard data to JSON."""
        from core.monitoring.performance_dashboard import PerformanceDashboard

        dashboard = PerformanceDashboard(data_dir=str(temp_data_dir))
        for trade in sample_trades:
            dashboard.record_trade(trade)

        export_path = temp_data_dir / "export.json"
        dashboard.export_json(str(export_path))

        assert export_path.exists()

        with open(export_path) as f:
            data = json.load(f)

        assert "trading_stats" in data
        assert "trades" in data


class TestDashboardConfiguration:
    """Tests for dashboard configuration."""

    def test_default_configuration(self, temp_data_dir):
        """Test default configuration values."""
        from core.monitoring.performance_dashboard import PerformanceDashboard

        dashboard = PerformanceDashboard(data_dir=str(temp_data_dir))

        config = dashboard.get_config()

        assert config["retention_days"] == 30
        assert config["sampling_interval_seconds"] == 5

    def test_custom_configuration(self, temp_data_dir):
        """Test custom configuration values."""
        from core.monitoring.performance_dashboard import PerformanceDashboard

        dashboard = PerformanceDashboard(
            data_dir=str(temp_data_dir),
            retention_days=14,
            sampling_interval_seconds=10
        )

        config = dashboard.get_config()

        assert config["retention_days"] == 14
        assert config["sampling_interval_seconds"] == 10


class TestPerformanceMetrics:
    """Tests for dashboard performance itself."""

    def test_dashboard_snapshot_performance(self, temp_data_dir):
        """Test that dashboard operations complete within acceptable time."""
        from core.monitoring.performance_dashboard import PerformanceDashboard

        dashboard = PerformanceDashboard(data_dir=str(temp_data_dir))

        # Add many trades
        for i in range(1000):
            dashboard.record_trade({
                "id": f"trade_{i}",
                "symbol": "SOL",
                "profit_usd": float(i % 100 - 50),
                "is_win": i % 2 == 0,
                "timestamp": datetime.now(timezone.utc),
                "latency_ms": 100.0,
            })

        start = time.time()
        stats = dashboard.get_trading_stats()
        elapsed = (time.time() - start) * 1000

        # Should complete within 100ms
        assert elapsed < 100, f"Stats calculation took {elapsed:.1f}ms"
        assert stats["trade_count"] == 1000


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_dashboard_singleton(self, temp_data_dir):
        """Test getting dashboard singleton instance."""
        from core.monitoring.performance_dashboard import get_performance_dashboard

        with patch('core.monitoring.performance_dashboard._dashboard', None):
            dashboard1 = get_performance_dashboard()
            dashboard2 = get_performance_dashboard()

            assert dashboard1 is dashboard2


# =============================================================================
# EDGE CASES
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_division_by_zero_protection(self, temp_data_dir):
        """Test protection against division by zero."""
        from core.monitoring.performance_dashboard import PerformanceDashboard

        dashboard = PerformanceDashboard(data_dir=str(temp_data_dir))

        # Record only winning trades (no losses)
        dashboard.record_trade({
            "id": "win_only",
            "symbol": "SOL",
            "profit_usd": 100.0,
            "is_win": True,
            "timestamp": datetime.now(timezone.utc),
            "latency_ms": 100.0,
        })

        stats = dashboard.get_trading_stats()

        # Should not raise error, should return infinity or special value
        assert stats["profit_factor"] == float('inf') or stats["profit_factor"] > 0

    def test_empty_latency_stats(self, temp_data_dir):
        """Test getting latency stats with no data."""
        from core.monitoring.performance_dashboard import PerformanceDashboard

        dashboard = PerformanceDashboard(data_dir=str(temp_data_dir))

        stats = dashboard.get_latency_stats("nonexistent")

        assert stats["sample_count"] == 0
        assert stats["avg_ms"] == 0.0

    def test_corrupted_data_file_handling(self, temp_data_dir):
        """Test handling of corrupted data files."""
        from core.monitoring.performance_dashboard import PerformanceDashboard

        # Create a corrupted data file
        data_file = temp_data_dir / "performance_data.json"
        data_file.write_text("invalid json {{{")

        # Should not raise error, should start fresh
        dashboard = PerformanceDashboard(data_dir=str(temp_data_dir))
        stats = dashboard.get_trading_stats()

        assert stats["trade_count"] == 0
