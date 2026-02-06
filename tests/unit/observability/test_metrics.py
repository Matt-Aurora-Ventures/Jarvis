"""
Unit tests for core/observability/metrics.py

Tests the BotMetrics class for tracking:
- API calls (provider, latency, success)
- Messages (bot, direction, size)
- Errors (bot, error_type, message)
- Stats retrieval
- Prometheus export
"""

import pytest
import time
from unittest.mock import patch


class TestBotMetrics:
    """Test BotMetrics class functionality."""

    def test_bot_metrics_singleton(self):
        """BotMetrics should be a singleton or provide get_instance."""
        from core.observability.metrics import BotMetrics

        m1 = BotMetrics.get_instance()
        m2 = BotMetrics.get_instance()
        assert m1 is m2

    def test_track_api_call_success(self):
        """track_api_call should record successful API calls."""
        from core.observability.metrics import BotMetrics

        metrics = BotMetrics.get_instance()
        metrics.reset()  # Clear any previous state

        metrics.track_api_call(provider="openai", latency_ms=150.5, success=True)

        stats = metrics.get_stats()
        assert stats["api_calls"]["total"] >= 1
        assert "openai" in stats["api_calls"]["by_provider"]
        assert stats["api_calls"]["by_provider"]["openai"]["success"] >= 1

    def test_track_api_call_failure(self):
        """track_api_call should record failed API calls."""
        from core.observability.metrics import BotMetrics

        metrics = BotMetrics.get_instance()
        metrics.reset()

        metrics.track_api_call(provider="anthropic", latency_ms=500.0, success=False)

        stats = metrics.get_stats()
        assert "anthropic" in stats["api_calls"]["by_provider"]
        assert stats["api_calls"]["by_provider"]["anthropic"]["failure"] >= 1

    def test_track_api_call_latency_percentiles(self):
        """track_api_call should track latency for percentile calculations."""
        from core.observability.metrics import BotMetrics

        metrics = BotMetrics.get_instance()
        metrics.reset()

        # Track multiple calls with varying latencies
        for latency in [100, 150, 200, 250, 300]:
            metrics.track_api_call(provider="grok", latency_ms=latency, success=True)

        stats = metrics.get_stats()
        provider_stats = stats["api_calls"]["by_provider"]["grok"]

        assert "avg_latency_ms" in provider_stats
        assert provider_stats["avg_latency_ms"] == pytest.approx(200.0, rel=0.1)

    def test_track_message_inbound(self):
        """track_message should record inbound messages."""
        from core.observability.metrics import BotMetrics

        metrics = BotMetrics.get_instance()
        metrics.reset()

        metrics.track_message(bot="jarvis", direction="inbound", size_bytes=256)

        stats = metrics.get_stats()
        assert stats["messages"]["total"] >= 1
        assert "jarvis" in stats["messages"]["by_bot"]
        assert stats["messages"]["by_bot"]["jarvis"]["inbound"]["count"] >= 1
        assert stats["messages"]["by_bot"]["jarvis"]["inbound"]["bytes"] >= 256

    def test_track_message_outbound(self):
        """track_message should record outbound messages."""
        from core.observability.metrics import BotMetrics

        metrics = BotMetrics.get_instance()
        metrics.reset()

        metrics.track_message(bot="matt", direction="outbound", size_bytes=512)

        stats = metrics.get_stats()
        assert "matt" in stats["messages"]["by_bot"]
        assert stats["messages"]["by_bot"]["matt"]["outbound"]["count"] >= 1

    def test_track_error(self):
        """track_error should record errors by bot and type."""
        from core.observability.metrics import BotMetrics

        metrics = BotMetrics.get_instance()
        metrics.reset()

        metrics.track_error(
            bot="friday",
            error_type="RateLimitError",
            message="Rate limit exceeded for API"
        )

        stats = metrics.get_stats()
        assert stats["errors"]["total"] >= 1
        assert "friday" in stats["errors"]["by_bot"]
        assert "RateLimitError" in stats["errors"]["by_bot"]["friday"]["by_type"]

    def test_track_error_stores_recent_messages(self):
        """track_error should store recent error messages."""
        from core.observability.metrics import BotMetrics

        metrics = BotMetrics.get_instance()
        metrics.reset()

        metrics.track_error(
            bot="jarvis",
            error_type="ConnectionError",
            message="Failed to connect to RPC"
        )

        stats = metrics.get_stats()
        recent = stats["errors"]["by_bot"]["jarvis"]["recent"]
        assert len(recent) >= 1
        assert any("Failed to connect" in err["message"] for err in recent)

    def test_get_stats_returns_complete_structure(self):
        """get_stats should return a complete metrics dictionary."""
        from core.observability.metrics import BotMetrics

        metrics = BotMetrics.get_instance()
        metrics.reset()

        stats = metrics.get_stats()

        assert "api_calls" in stats
        assert "messages" in stats
        assert "errors" in stats
        assert "uptime_seconds" in stats
        assert "last_updated" in stats

    def test_export_prometheus_format(self):
        """export_prometheus should return valid Prometheus format."""
        from core.observability.metrics import BotMetrics

        metrics = BotMetrics.get_instance()
        metrics.reset()

        # Add some test data
        metrics.track_api_call(provider="openai", latency_ms=100, success=True)
        metrics.track_message(bot="jarvis", direction="inbound", size_bytes=100)
        metrics.track_error(bot="jarvis", error_type="TestError", message="test")

        prom_output = metrics.export_prometheus()

        # Should be valid Prometheus text format
        assert isinstance(prom_output, str)
        assert "# HELP" in prom_output
        assert "# TYPE" in prom_output
        assert "jarvis_api_calls_total" in prom_output
        assert "jarvis_messages_total" in prom_output
        assert "jarvis_errors_total" in prom_output

    def test_export_prometheus_labels(self):
        """export_prometheus should include proper labels."""
        from core.observability.metrics import BotMetrics

        metrics = BotMetrics.get_instance()
        metrics.reset()

        metrics.track_api_call(provider="anthropic", latency_ms=200, success=True)

        prom_output = metrics.export_prometheus()

        # Should have provider label
        assert 'provider="anthropic"' in prom_output

    def test_reset_clears_all_metrics(self):
        """reset should clear all tracked metrics."""
        from core.observability.metrics import BotMetrics

        metrics = BotMetrics.get_instance()

        # Add some data
        metrics.track_api_call(provider="test", latency_ms=100, success=True)
        metrics.track_message(bot="test", direction="inbound", size_bytes=100)
        metrics.track_error(bot="test", error_type="TestError", message="test")

        # Reset
        metrics.reset()

        stats = metrics.get_stats()
        assert stats["api_calls"]["total"] == 0
        assert stats["messages"]["total"] == 0
        assert stats["errors"]["total"] == 0


class TestBotMetricsThreadSafety:
    """Test thread safety of BotMetrics."""

    def test_concurrent_api_calls(self):
        """BotMetrics should handle concurrent track_api_call calls."""
        import threading
        from core.observability.metrics import BotMetrics

        metrics = BotMetrics.get_instance()
        metrics.reset()

        def track_calls():
            for _ in range(100):
                metrics.track_api_call(provider="test", latency_ms=10, success=True)

        threads = [threading.Thread(target=track_calls) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        stats = metrics.get_stats()
        assert stats["api_calls"]["total"] == 500

    def test_concurrent_message_tracking(self):
        """BotMetrics should handle concurrent track_message calls."""
        import threading
        from core.observability.metrics import BotMetrics

        metrics = BotMetrics.get_instance()
        metrics.reset()

        def track_messages():
            for _ in range(100):
                metrics.track_message(bot="test", direction="inbound", size_bytes=10)

        threads = [threading.Thread(target=track_messages) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        stats = metrics.get_stats()
        assert stats["messages"]["total"] == 500
