"""
Unit tests for MetricsAggregator class.
Tests hourly/daily aggregation and percentile calculations.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock


class TestMetricsAggregator:
    """Test MetricsAggregator class functionality."""

    def test_init_with_bot_metrics(self):
        """MetricsAggregator should initialize with bot metrics sources."""
        from core.metrics.aggregator import MetricsAggregator
        from core.metrics.bot_metrics import BotMetrics

        metrics1 = BotMetrics(bot_name="bot1")
        metrics2 = BotMetrics(bot_name="bot2")

        aggregator = MetricsAggregator([metrics1, metrics2])

        assert len(aggregator.sources) == 2

    def test_aggregate_hourly_returns_stats(self):
        """aggregate_hourly should return HourlyStats dataclass."""
        from core.metrics.aggregator import MetricsAggregator, HourlyStats
        from core.metrics.bot_metrics import BotMetrics

        metrics = BotMetrics(bot_name="test_bot")
        metrics.increment("messages_received", amount=100)
        metrics.increment("messages_sent", amount=80)
        metrics.increment("commands_processed", amount=50)
        metrics.increment("errors_total", amount=5)
        for i in range(10):
            metrics.record_timing("op", 0.1 * (i + 1))

        aggregator = MetricsAggregator([metrics])
        hourly = aggregator.aggregate_hourly()

        assert isinstance(hourly, HourlyStats)
        assert hourly.total_messages_received == 100
        assert hourly.total_messages_sent == 80
        assert hourly.total_commands == 50
        assert hourly.total_errors == 5
        assert hourly.avg_response_time > 0

    def test_aggregate_hourly_multiple_bots(self):
        """aggregate_hourly should sum metrics across all bots."""
        from core.metrics.aggregator import MetricsAggregator
        from core.metrics.bot_metrics import BotMetrics

        metrics1 = BotMetrics(bot_name="bot1")
        metrics1.increment("messages_received", amount=50)
        metrics1.increment("errors_total", amount=2)

        metrics2 = BotMetrics(bot_name="bot2")
        metrics2.increment("messages_received", amount=30)
        metrics2.increment("errors_total", amount=1)

        aggregator = MetricsAggregator([metrics1, metrics2])
        hourly = aggregator.aggregate_hourly()

        assert hourly.total_messages_received == 80
        assert hourly.total_errors == 3

    def test_aggregate_daily_returns_stats(self):
        """aggregate_daily should return DailyStats dataclass."""
        from core.metrics.aggregator import MetricsAggregator, DailyStats
        from core.metrics.bot_metrics import BotMetrics

        metrics = BotMetrics(bot_name="test_bot")
        metrics.increment("messages_received", amount=1000)
        metrics.increment("messages_sent", amount=800)
        metrics.increment("commands_processed", amount=500)
        metrics.increment("errors_total", amount=10)

        aggregator = MetricsAggregator([metrics])
        daily = aggregator.aggregate_daily()

        assert isinstance(daily, DailyStats)
        assert daily.total_messages_received == 1000
        assert daily.total_messages_sent == 800
        assert daily.total_commands == 500
        assert daily.total_errors == 10
        assert daily.error_rate == 10 / 1000  # errors / messages_received

    def test_aggregate_daily_error_rate_calculation(self):
        """aggregate_daily should calculate error_rate correctly."""
        from core.metrics.aggregator import MetricsAggregator
        from core.metrics.bot_metrics import BotMetrics

        metrics = BotMetrics(bot_name="test_bot")
        metrics.increment("messages_received", amount=200)
        metrics.increment("errors_total", amount=20)

        aggregator = MetricsAggregator([metrics])
        daily = aggregator.aggregate_daily()

        assert daily.error_rate == 0.1  # 20/200

    def test_aggregate_daily_zero_messages(self):
        """aggregate_daily should handle zero messages gracefully."""
        from core.metrics.aggregator import MetricsAggregator
        from core.metrics.bot_metrics import BotMetrics

        metrics = BotMetrics(bot_name="test_bot")

        aggregator = MetricsAggregator([metrics])
        daily = aggregator.aggregate_daily()

        assert daily.total_messages_received == 0
        assert daily.error_rate == 0.0

    def test_get_percentiles(self):
        """get_percentiles should return p50, p95, p99 for a metric."""
        from core.metrics.aggregator import MetricsAggregator
        from core.metrics.bot_metrics import BotMetrics

        metrics = BotMetrics(bot_name="test_bot")
        # Add 100 response times: 0.01, 0.02, ..., 1.0
        for i in range(1, 101):
            metrics.record_timing("op", i * 0.01)

        aggregator = MetricsAggregator([metrics])
        p50, p95, p99 = aggregator.get_percentiles("response_times")

        # p50 should be around 0.5
        assert 0.45 <= p50 <= 0.55
        # p95 should be around 0.95
        assert 0.90 <= p95 <= 1.0
        # p99 should be around 0.99
        assert 0.95 <= p99 <= 1.01

    def test_get_percentiles_empty_data(self):
        """get_percentiles should handle empty data gracefully."""
        from core.metrics.aggregator import MetricsAggregator
        from core.metrics.bot_metrics import BotMetrics

        metrics = BotMetrics(bot_name="test_bot")

        aggregator = MetricsAggregator([metrics])
        p50, p95, p99 = aggregator.get_percentiles("response_times")

        assert p50 == 0.0
        assert p95 == 0.0
        assert p99 == 0.0

    def test_get_percentiles_single_value(self):
        """get_percentiles should handle single value."""
        from core.metrics.aggregator import MetricsAggregator
        from core.metrics.bot_metrics import BotMetrics

        metrics = BotMetrics(bot_name="test_bot")
        metrics.record_timing("op", 0.5)

        aggregator = MetricsAggregator([metrics])
        p50, p95, p99 = aggregator.get_percentiles("response_times")

        assert p50 == 0.5
        assert p95 == 0.5
        assert p99 == 0.5

    def test_aggregate_by_bot(self):
        """aggregate_by_bot should return per-bot statistics."""
        from core.metrics.aggregator import MetricsAggregator
        from core.metrics.bot_metrics import BotMetrics

        metrics1 = BotMetrics(bot_name="clawdmatt")
        metrics1.increment("messages_received", amount=100)

        metrics2 = BotMetrics(bot_name="clawdjarvis")
        metrics2.increment("messages_received", amount=200)

        aggregator = MetricsAggregator([metrics1, metrics2])
        by_bot = aggregator.aggregate_by_bot()

        assert "clawdmatt" in by_bot
        assert "clawdjarvis" in by_bot
        assert by_bot["clawdmatt"]["messages_received"] == 100
        assert by_bot["clawdjarvis"]["messages_received"] == 200

    def test_get_time_series(self):
        """get_time_series should return time-bucketed data."""
        from core.metrics.aggregator import MetricsAggregator
        from core.metrics.bot_metrics import BotMetrics

        metrics = BotMetrics(bot_name="test_bot")
        # This test validates the interface exists
        aggregator = MetricsAggregator([metrics])

        # get_time_series returns list of (timestamp, value) tuples
        series = aggregator.get_time_series("messages_received", bucket_minutes=5)

        assert isinstance(series, list)


class TestHourlyStats:
    """Test HourlyStats dataclass."""

    def test_hourly_stats_creation(self):
        """HourlyStats should be a proper dataclass."""
        from core.metrics.aggregator import HourlyStats

        stats = HourlyStats(
            timestamp=datetime.utcnow(),
            total_messages_received=100,
            total_messages_sent=80,
            total_commands=50,
            total_errors=5,
            avg_response_time=0.5,
            bot_breakdown={"bot1": {"messages": 100}},
        )

        assert stats.total_messages_received == 100
        assert stats.total_messages_sent == 80
        assert stats.total_commands == 50
        assert stats.total_errors == 5
        assert stats.avg_response_time == 0.5

    def test_hourly_stats_to_dict(self):
        """HourlyStats should have to_dict method."""
        from core.metrics.aggregator import HourlyStats

        stats = HourlyStats(
            timestamp=datetime.utcnow(),
            total_messages_received=100,
            total_messages_sent=80,
            total_commands=50,
            total_errors=5,
            avg_response_time=0.5,
            bot_breakdown={},
        )

        d = stats.to_dict()

        assert isinstance(d, dict)
        assert d["total_messages_received"] == 100


class TestDailyStats:
    """Test DailyStats dataclass."""

    def test_daily_stats_creation(self):
        """DailyStats should be a proper dataclass."""
        from core.metrics.aggregator import DailyStats

        stats = DailyStats(
            date=datetime.utcnow().date(),
            total_messages_received=1000,
            total_messages_sent=800,
            total_commands=500,
            total_errors=10,
            error_rate=0.01,
            avg_response_time=0.3,
            p50_response_time=0.25,
            p95_response_time=0.8,
            p99_response_time=1.2,
            bot_breakdown={},
        )

        assert stats.total_messages_received == 1000
        assert stats.error_rate == 0.01
        assert stats.p95_response_time == 0.8

    def test_daily_stats_to_dict(self):
        """DailyStats should have to_dict method."""
        from core.metrics.aggregator import DailyStats

        stats = DailyStats(
            date=datetime.utcnow().date(),
            total_messages_received=1000,
            total_messages_sent=800,
            total_commands=500,
            total_errors=10,
            error_rate=0.01,
            avg_response_time=0.3,
            p50_response_time=0.25,
            p95_response_time=0.8,
            p99_response_time=1.2,
            bot_breakdown={},
        )

        d = stats.to_dict()

        assert isinstance(d, dict)
        assert d["total_messages_received"] == 1000
        assert d["error_rate"] == 0.01
