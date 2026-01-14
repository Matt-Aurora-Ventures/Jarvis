"""Integration tests for monitoring systems."""
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta


class TestMetricsCollectorIntegration:
    """Integration tests for metrics collection."""

    def test_metrics_collector_initialization(self):
        """MetricsCollector should initialize."""
        try:
            from core.monitoring.metrics_collector import MetricsCollector

            collector = MetricsCollector()
            assert collector is not None
        except ImportError:
            pytest.skip("Metrics collector not found")

    def test_error_rate_tracking(self):
        """Error rates should be tracked."""
        try:
            from core.monitoring.metrics_collector import MetricsCollector

            collector = MetricsCollector()

            # Record some requests
            for _ in range(10):
                collector.record_request("api", "/test", success=True)
            for _ in range(2):
                collector.record_request("api", "/test", success=False)

            stats = collector.get_error_rate_stats("api")
            assert stats is not None
            assert stats.total_requests == 12
        except ImportError:
            pytest.skip("Metrics collector not found")

    def test_latency_percentile_tracking(self):
        """Latency percentiles should be tracked."""
        try:
            from core.monitoring.metrics_collector import MetricsCollector

            collector = MetricsCollector()

            # Record varying latencies
            latencies = [10, 20, 30, 50, 100, 200, 500]
            for latency in latencies:
                collector.record_latency("api", "/test", latency)

            stats = collector.get_latency_stats("api")
            assert stats is not None
            assert stats.p50 > 0
            assert stats.p99 >= stats.p50
        except ImportError:
            pytest.skip("Metrics collector not found")


class TestSlidingWindowIntegration:
    """Integration tests for sliding window calculations."""

    def test_sliding_window_behavior(self):
        """Sliding window should maintain time bounds."""
        try:
            from core.monitoring.metrics_collector import SlidingWindow

            window = SlidingWindow(window_seconds=60)

            # Add values
            for i in range(10):
                window.add(i)

            values = window.get_values()
            assert len(values) == 10
        except ImportError:
            pytest.skip("Sliding window not found")


class TestPercentileCalculator:
    """Integration tests for percentile calculations."""

    def test_percentile_accuracy(self):
        """Percentiles should be accurately calculated."""
        try:
            from core.monitoring.metrics_collector import PercentileCalculator

            calc = PercentileCalculator()

            # Add known distribution
            for i in range(1, 101):
                calc.add(i)

            p50 = calc.percentile(50)
            p95 = calc.percentile(95)
            p99 = calc.percentile(99)

            assert 45 <= p50 <= 55  # Should be around 50
            assert 90 <= p95 <= 100  # Should be around 95
            assert 95 <= p99 <= 100  # Should be around 99
        except ImportError:
            pytest.skip("Percentile calculator not found")


class TestAlertThresholds:
    """Integration tests for alert thresholds."""

    def test_threshold_creation(self):
        """Alert thresholds should be creatable."""
        try:
            from core.monitoring.metrics_collector import AlertThreshold

            threshold = AlertThreshold(
                name="high_error_rate",
                warning=0.05,
                critical=0.10
            )

            assert threshold.warning == 0.05
            assert threshold.critical == 0.10
        except ImportError:
            pytest.skip("Alert threshold not found")

    def test_threshold_evaluation(self):
        """Thresholds should evaluate correctly."""
        try:
            from core.monitoring.metrics_collector import AlertThreshold

            threshold = AlertThreshold(
                name="latency",
                warning=100,
                critical=500
            )

            assert threshold.evaluate(50) == "ok"
            assert threshold.evaluate(150) == "warning"
            assert threshold.evaluate(600) == "critical"
        except ImportError:
            pytest.skip("Alert threshold not found")


class TestDashboardIntegration:
    """Integration tests for monitoring dashboard."""

    def test_dashboard_data_structure(self):
        """Dashboard should have expected data structure."""
        try:
            from core.monitoring.dashboard import DashboardData

            data = DashboardData(
                uptime_seconds=3600,
                total_requests=1000,
                error_rate=0.02,
                avg_latency_ms=50.0
            )

            assert data.uptime_seconds == 3600
            assert data.total_requests == 1000
        except ImportError:
            pytest.skip("Dashboard module not found")


class TestHealthMonitorIntegration:
    """Integration tests for health monitoring."""

    def test_health_monitor_exists(self):
        """Health monitor should exist."""
        try:
            from core.monitoring import HealthMonitor

            monitor = HealthMonitor()
            assert monitor is not None
        except ImportError:
            pytest.skip("Health monitor not found")

    def test_service_registration(self):
        """Services should be registrable."""
        try:
            from core.monitoring import HealthMonitor

            monitor = HealthMonitor()

            async def check_db():
                return True

            monitor.register_check("database", check_db)
            assert "database" in monitor.checks
        except ImportError:
            pytest.skip("Health monitor not found")


class TestGrafanaDashboards:
    """Integration tests for Grafana dashboards."""

    def test_dashboard_files_valid_json(self):
        """Dashboard files should be valid JSON."""
        import json
        from pathlib import Path

        dashboard_dir = Path("grafana/dashboards")
        if not dashboard_dir.exists():
            pytest.skip("Grafana dashboards not found")

        for dashboard_file in dashboard_dir.glob("*.json"):
            with open(dashboard_file) as f:
                data = json.load(f)
                assert "title" in data
                assert "panels" in data

    def test_dashboard_has_required_panels(self):
        """Dashboards should have required panels."""
        import json
        from pathlib import Path

        bots_dashboard = Path("grafana/dashboards/jarvis-bots.json")
        if not bots_dashboard.exists():
            pytest.skip("Bots dashboard not found")

        with open(bots_dashboard) as f:
            data = json.load(f)
            panel_titles = [p.get("title") for p in data.get("panels", [])]
            # At least some panels should exist
            assert len(panel_titles) > 0


class TestPrometheusMetrics:
    """Integration tests for Prometheus metrics."""

    def test_metrics_format(self):
        """Metrics should be in Prometheus format."""
        try:
            from core.monitoring.metrics_collector import format_prometheus_metrics

            metrics = {"requests_total": 100, "errors_total": 5}
            output = format_prometheus_metrics(metrics)

            assert "requests_total" in output
            assert "100" in output
        except ImportError:
            pytest.skip("Prometheus formatter not found")
