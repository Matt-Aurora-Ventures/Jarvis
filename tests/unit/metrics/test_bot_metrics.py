"""
Unit tests for BotMetrics class.
Tests the core bot metrics collection functionality.
"""

import pytest
import time
from unittest.mock import patch, MagicMock


class TestBotMetrics:
    """Test BotMetrics class functionality."""

    def test_init_creates_zero_counters(self):
        """BotMetrics should initialize with zero counters."""
        from core.metrics.bot_metrics import BotMetrics

        metrics = BotMetrics(bot_name="test_bot")

        assert metrics.bot_name == "test_bot"
        assert metrics.messages_received == 0
        assert metrics.messages_sent == 0
        assert metrics.commands_processed == 0
        assert metrics.errors_total == 0
        assert metrics.response_times == []

    def test_increment_messages_received(self):
        """increment should increase messages_received counter."""
        from core.metrics.bot_metrics import BotMetrics

        metrics = BotMetrics(bot_name="test_bot")
        metrics.increment("messages_received")

        assert metrics.messages_received == 1

        metrics.increment("messages_received")
        metrics.increment("messages_received")

        assert metrics.messages_received == 3

    def test_increment_messages_sent(self):
        """increment should increase messages_sent counter."""
        from core.metrics.bot_metrics import BotMetrics

        metrics = BotMetrics(bot_name="test_bot")
        metrics.increment("messages_sent")
        metrics.increment("messages_sent")

        assert metrics.messages_sent == 2

    def test_increment_commands_processed(self):
        """increment should increase commands_processed counter."""
        from core.metrics.bot_metrics import BotMetrics

        metrics = BotMetrics(bot_name="test_bot")
        metrics.increment("commands_processed")

        assert metrics.commands_processed == 1

    def test_increment_errors_total(self):
        """increment should increase errors_total counter."""
        from core.metrics.bot_metrics import BotMetrics

        metrics = BotMetrics(bot_name="test_bot")
        metrics.increment("errors_total")
        metrics.increment("errors_total")

        assert metrics.errors_total == 2

    def test_increment_invalid_metric_raises(self):
        """increment with invalid metric name should raise ValueError."""
        from core.metrics.bot_metrics import BotMetrics

        metrics = BotMetrics(bot_name="test_bot")

        with pytest.raises(ValueError, match="Unknown metric"):
            metrics.increment("invalid_metric")

    def test_increment_with_amount(self):
        """increment should support custom amount."""
        from core.metrics.bot_metrics import BotMetrics

        metrics = BotMetrics(bot_name="test_bot")
        metrics.increment("messages_received", amount=5)

        assert metrics.messages_received == 5

    def test_record_timing(self):
        """record_timing should add duration to response_times list."""
        from core.metrics.bot_metrics import BotMetrics

        metrics = BotMetrics(bot_name="test_bot")
        metrics.record_timing("handle_message", 0.5)
        metrics.record_timing("handle_message", 1.2)
        metrics.record_timing("process_command", 0.3)

        assert len(metrics.response_times) == 3
        assert 0.5 in metrics.response_times
        assert 1.2 in metrics.response_times
        assert 0.3 in metrics.response_times

    def test_record_timing_with_operation_tracking(self):
        """record_timing should track operations separately if operation_times dict exists."""
        from core.metrics.bot_metrics import BotMetrics

        metrics = BotMetrics(bot_name="test_bot")
        metrics.record_timing("handle_message", 0.5)
        metrics.record_timing("handle_message", 0.8)
        metrics.record_timing("process_command", 0.3)

        # Should store all times in response_times
        assert len(metrics.response_times) == 3

    def test_get_stats_returns_summary(self):
        """get_stats should return summary statistics."""
        from core.metrics.bot_metrics import BotMetrics

        metrics = BotMetrics(bot_name="test_bot")
        metrics.increment("messages_received", amount=10)
        metrics.increment("messages_sent", amount=8)
        metrics.increment("commands_processed", amount=5)
        metrics.increment("errors_total", amount=2)
        metrics.record_timing("test", 0.5)
        metrics.record_timing("test", 1.0)
        metrics.record_timing("test", 1.5)

        stats = metrics.get_stats()

        assert stats["bot_name"] == "test_bot"
        assert stats["messages_received"] == 10
        assert stats["messages_sent"] == 8
        assert stats["commands_processed"] == 5
        assert stats["errors_total"] == 2
        assert stats["response_times_count"] == 3
        assert stats["avg_response_time"] == 1.0

    def test_get_stats_empty_response_times(self):
        """get_stats should handle empty response_times gracefully."""
        from core.metrics.bot_metrics import BotMetrics

        metrics = BotMetrics(bot_name="test_bot")
        stats = metrics.get_stats()

        assert stats["response_times_count"] == 0
        assert stats["avg_response_time"] == 0.0

    def test_reset_clears_all_metrics(self):
        """reset should clear all metrics to initial state."""
        from core.metrics.bot_metrics import BotMetrics

        metrics = BotMetrics(bot_name="test_bot")
        metrics.increment("messages_received", amount=10)
        metrics.increment("errors_total", amount=5)
        metrics.record_timing("test", 1.0)

        metrics.reset()

        assert metrics.messages_received == 0
        assert metrics.messages_sent == 0
        assert metrics.commands_processed == 0
        assert metrics.errors_total == 0
        assert metrics.response_times == []

    def test_thread_safety_context_manager(self):
        """BotMetrics should be thread-safe using internal lock."""
        from core.metrics.bot_metrics import BotMetrics
        import threading

        metrics = BotMetrics(bot_name="test_bot")

        def increment_many():
            for _ in range(100):
                metrics.increment("messages_received")

        threads = [threading.Thread(target=increment_many) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert metrics.messages_received == 1000


class TestBotMetricsRegistry:
    """Test the global bot metrics registry."""

    def test_get_or_create_returns_same_instance(self):
        """get_or_create should return same instance for same bot name."""
        from core.metrics.bot_metrics import get_bot_metrics

        metrics1 = get_bot_metrics("clawdbot")
        metrics2 = get_bot_metrics("clawdbot")

        assert metrics1 is metrics2

    def test_get_or_create_different_bots(self):
        """get_or_create should return different instances for different bots."""
        from core.metrics.bot_metrics import get_bot_metrics

        metrics1 = get_bot_metrics("clawdbot_a")
        metrics2 = get_bot_metrics("clawdbot_b")

        assert metrics1 is not metrics2
        assert metrics1.bot_name == "clawdbot_a"
        assert metrics2.bot_name == "clawdbot_b"

    def test_list_all_bots(self):
        """list_all_bots should return all registered bot names."""
        from core.metrics.bot_metrics import get_bot_metrics, list_all_bots, _reset_registry

        # Reset to clean state
        _reset_registry()

        get_bot_metrics("bot_alpha")
        get_bot_metrics("bot_beta")
        get_bot_metrics("bot_gamma")

        bots = list_all_bots()

        assert "bot_alpha" in bots
        assert "bot_beta" in bots
        assert "bot_gamma" in bots
