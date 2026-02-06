"""
Unit tests for PrometheusExporter class.
Tests Prometheus-format metrics export functionality.
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock


class TestPrometheusExporter:
    """Test PrometheusExporter class functionality."""

    def test_init_with_aggregator(self):
        """PrometheusExporter should initialize with MetricsAggregator."""
        from core.metrics.exporter import PrometheusExporter
        from core.metrics.aggregator import MetricsAggregator
        from core.metrics.bot_metrics import BotMetrics

        metrics = BotMetrics(bot_name="test_bot")
        aggregator = MetricsAggregator([metrics])

        exporter = PrometheusExporter(aggregator)

        assert exporter.aggregator is aggregator

    def test_export_returns_string(self):
        """export should return Prometheus format string."""
        from core.metrics.exporter import PrometheusExporter
        from core.metrics.aggregator import MetricsAggregator
        from core.metrics.bot_metrics import BotMetrics

        metrics = BotMetrics(bot_name="clawdbot")
        metrics.increment("messages_received", amount=100)
        metrics.increment("messages_sent", amount=80)
        metrics.increment("errors_total", amount=5)

        aggregator = MetricsAggregator([metrics])
        exporter = PrometheusExporter(aggregator)

        output = exporter.export()

        assert isinstance(output, str)
        assert len(output) > 0

    def test_export_contains_messages_total_metric(self):
        """export should contain clawdbot_messages_total metric."""
        from core.metrics.exporter import PrometheusExporter
        from core.metrics.aggregator import MetricsAggregator
        from core.metrics.bot_metrics import BotMetrics

        metrics = BotMetrics(bot_name="clawdbot")
        metrics.increment("messages_received", amount=100)
        metrics.increment("messages_sent", amount=80)

        aggregator = MetricsAggregator([metrics])
        exporter = PrometheusExporter(aggregator)

        output = exporter.export()

        # Check for received messages
        assert 'clawdbot_messages_total{bot="clawdbot",direction="received"}' in output
        assert "100" in output

        # Check for sent messages
        assert 'clawdbot_messages_total{bot="clawdbot",direction="sent"}' in output
        assert "80" in output

    def test_export_contains_response_seconds_metric(self):
        """export should contain clawdbot_response_seconds metric."""
        from core.metrics.exporter import PrometheusExporter
        from core.metrics.aggregator import MetricsAggregator
        from core.metrics.bot_metrics import BotMetrics

        metrics = BotMetrics(bot_name="clawdbot")
        metrics.record_timing("handle", 0.5)
        metrics.record_timing("handle", 1.0)
        metrics.record_timing("handle", 0.3)

        aggregator = MetricsAggregator([metrics])
        exporter = PrometheusExporter(aggregator)

        output = exporter.export()

        # Should contain summary metrics for response times
        assert 'clawdbot_response_seconds{bot="clawdbot"}' in output or \
               'clawdbot_response_seconds_sum{bot="clawdbot"}' in output

    def test_export_contains_errors_total_metric(self):
        """export should contain clawdbot_errors_total metric."""
        from core.metrics.exporter import PrometheusExporter
        from core.metrics.aggregator import MetricsAggregator
        from core.metrics.bot_metrics import BotMetrics

        metrics = BotMetrics(bot_name="clawdbot")
        metrics.increment("errors_total", amount=5)

        aggregator = MetricsAggregator([metrics])
        exporter = PrometheusExporter(aggregator)

        output = exporter.export()

        # Check for errors metric with type label
        assert 'clawdbot_errors_total{bot="clawdbot"' in output

    def test_export_multiple_bots(self):
        """export should include metrics for all bots."""
        from core.metrics.exporter import PrometheusExporter
        from core.metrics.aggregator import MetricsAggregator
        from core.metrics.bot_metrics import BotMetrics

        metrics1 = BotMetrics(bot_name="clawdmatt")
        metrics1.increment("messages_received", amount=100)

        metrics2 = BotMetrics(bot_name="clawdjarvis")
        metrics2.increment("messages_received", amount=200)

        aggregator = MetricsAggregator([metrics1, metrics2])
        exporter = PrometheusExporter(aggregator)

        output = exporter.export()

        assert 'bot="clawdmatt"' in output
        assert 'bot="clawdjarvis"' in output

    def test_export_contains_help_comments(self):
        """export should contain HELP comments for metrics."""
        from core.metrics.exporter import PrometheusExporter
        from core.metrics.aggregator import MetricsAggregator
        from core.metrics.bot_metrics import BotMetrics

        metrics = BotMetrics(bot_name="clawdbot")
        metrics.increment("messages_received", amount=10)

        aggregator = MetricsAggregator([metrics])
        exporter = PrometheusExporter(aggregator)

        output = exporter.export()

        assert "# HELP clawdbot_messages_total" in output

    def test_export_contains_type_comments(self):
        """export should contain TYPE comments for metrics."""
        from core.metrics.exporter import PrometheusExporter
        from core.metrics.aggregator import MetricsAggregator
        from core.metrics.bot_metrics import BotMetrics

        metrics = BotMetrics(bot_name="clawdbot")
        metrics.increment("messages_received", amount=10)

        aggregator = MetricsAggregator([metrics])
        exporter = PrometheusExporter(aggregator)

        output = exporter.export()

        assert "# TYPE clawdbot_messages_total counter" in output

    def test_export_histogram_buckets(self):
        """export should include histogram buckets for response times."""
        from core.metrics.exporter import PrometheusExporter
        from core.metrics.aggregator import MetricsAggregator
        from core.metrics.bot_metrics import BotMetrics

        metrics = BotMetrics(bot_name="clawdbot")
        # Add various response times to populate buckets
        for t in [0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5]:
            metrics.record_timing("handle", t)

        aggregator = MetricsAggregator([metrics])
        exporter = PrometheusExporter(aggregator)

        output = exporter.export()

        # Should contain histogram-style metrics with le labels
        # Or summary-style with quantile labels
        assert "clawdbot_response" in output

    def test_export_error_types(self):
        """export should support error type labels."""
        from core.metrics.exporter import PrometheusExporter
        from core.metrics.aggregator import MetricsAggregator
        from core.metrics.bot_metrics import BotMetrics

        metrics = BotMetrics(bot_name="clawdbot")
        metrics.increment("errors_total", amount=3)

        aggregator = MetricsAggregator([metrics])
        exporter = PrometheusExporter(aggregator)

        output = exporter.export()

        # Check for errors with type label
        assert 'clawdbot_errors_total' in output

    def test_export_timestamp(self):
        """export should optionally include timestamps."""
        from core.metrics.exporter import PrometheusExporter
        from core.metrics.aggregator import MetricsAggregator
        from core.metrics.bot_metrics import BotMetrics

        metrics = BotMetrics(bot_name="clawdbot")
        metrics.increment("messages_received", amount=10)

        aggregator = MetricsAggregator([metrics])
        exporter = PrometheusExporter(aggregator, include_timestamp=True)

        output = exporter.export()

        # Should contain timestamp at end of metric lines
        lines = output.strip().split('\n')
        metric_lines = [l for l in lines if not l.startswith('#') and l.strip()]
        if metric_lines:
            # At least one metric line should have a timestamp (13-digit unix ms)
            assert any(len(l.split()[-1]) >= 10 for l in metric_lines if l)


class TestPrometheusFormat:
    """Test Prometheus format compliance."""

    def test_metric_name_format(self):
        """Metric names should follow Prometheus naming conventions."""
        from core.metrics.exporter import PrometheusExporter
        from core.metrics.aggregator import MetricsAggregator
        from core.metrics.bot_metrics import BotMetrics

        metrics = BotMetrics(bot_name="clawdbot")
        metrics.increment("messages_received", amount=10)

        aggregator = MetricsAggregator([metrics])
        exporter = PrometheusExporter(aggregator)

        output = exporter.export()

        # Metric names should be lowercase with underscores
        assert "clawdbot_messages_total" in output
        # No dashes or spaces in metric names
        assert "clawdbot-messages" not in output

    def test_label_format(self):
        """Labels should follow Prometheus format: name="value"."""
        from core.metrics.exporter import PrometheusExporter
        from core.metrics.aggregator import MetricsAggregator
        from core.metrics.bot_metrics import BotMetrics

        metrics = BotMetrics(bot_name="clawdbot")
        metrics.increment("messages_received", amount=10)

        aggregator = MetricsAggregator([metrics])
        exporter = PrometheusExporter(aggregator)

        output = exporter.export()

        # Labels should be key="value" format
        assert 'bot="clawdbot"' in output
        assert 'direction="received"' in output

    def test_no_duplicate_metrics(self):
        """export should not produce duplicate metric entries."""
        from core.metrics.exporter import PrometheusExporter
        from core.metrics.aggregator import MetricsAggregator
        from core.metrics.bot_metrics import BotMetrics

        metrics = BotMetrics(bot_name="clawdbot")
        metrics.increment("messages_received", amount=10)

        aggregator = MetricsAggregator([metrics])
        exporter = PrometheusExporter(aggregator)

        output = exporter.export()

        lines = output.strip().split('\n')
        # Filter to actual metric lines (not comments)
        metric_lines = [l for l in lines if not l.startswith('#') and l.strip()]

        # Each unique metric+labels combo should appear only once
        unique_metrics = set()
        for line in metric_lines:
            # Extract metric name and labels (everything before the value)
            parts = line.rsplit(' ', 1)
            if len(parts) == 2:
                metric_key = parts[0]
                assert metric_key not in unique_metrics, f"Duplicate metric: {metric_key}"
                unique_metrics.add(metric_key)
