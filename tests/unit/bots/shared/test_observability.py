"""
Unit tests for bots/shared/observability.py

Tests the ClawdBot observability module for:
- API call tracking (latency, success/failure, tokens)
- Health summary generation
- Daily cost calculation
- Threshold alerting
- JSON persistence
"""

import json
import os
import pytest
import tempfile
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestClawdBotObservability:
    """Test ClawdBotObservability class functionality."""

    @pytest.fixture
    def temp_metrics_file(self, tmp_path):
        """Create a temporary metrics file path."""
        return str(tmp_path / "metrics.json")

    @pytest.fixture
    def observability(self, temp_metrics_file):
        """Create a fresh observability instance with temp file."""
        from bots.shared.observability import ClawdBotObservability
        obs = ClawdBotObservability(metrics_path=temp_metrics_file)
        obs.reset()
        return obs

    def test_initialization_creates_metrics_file(self, temp_metrics_file):
        """Observability should create metrics file on init."""
        from bots.shared.observability import ClawdBotObservability
        obs = ClawdBotObservability(metrics_path=temp_metrics_file)
        assert Path(temp_metrics_file).exists()

    def test_track_api_call_success(self, observability):
        """track_api_call should record successful API calls."""
        observability.track_api_call(
            api_name="telegram",
            latency_ms=150.5,
            success=True,
            tokens_used=0
        )

        summary = observability.get_health_summary()
        assert summary["api_calls"]["total"] >= 1
        assert "telegram" in summary["api_calls"]["by_api"]
        assert summary["api_calls"]["by_api"]["telegram"]["success_count"] >= 1

    def test_track_api_call_failure(self, observability):
        """track_api_call should record failed API calls."""
        observability.track_api_call(
            api_name="openai",
            latency_ms=500.0,
            success=False,
            tokens_used=0
        )

        summary = observability.get_health_summary()
        assert "openai" in summary["api_calls"]["by_api"]
        assert summary["api_calls"]["by_api"]["openai"]["failure_count"] >= 1

    def test_track_api_call_with_tokens(self, observability):
        """track_api_call should track token usage."""
        observability.track_api_call(
            api_name="anthropic",
            latency_ms=200.0,
            success=True,
            tokens_used=1500
        )

        summary = observability.get_health_summary()
        assert summary["api_calls"]["by_api"]["anthropic"]["total_tokens"] >= 1500

    def test_track_api_call_latency_stats(self, observability):
        """track_api_call should calculate latency statistics."""
        for latency in [100, 150, 200, 250, 300]:
            observability.track_api_call(
                api_name="grok",
                latency_ms=latency,
                success=True,
                tokens_used=100
            )

        summary = observability.get_health_summary()
        api_stats = summary["api_calls"]["by_api"]["grok"]

        assert "avg_latency_ms" in api_stats
        assert api_stats["avg_latency_ms"] == pytest.approx(200.0, rel=0.1)
        assert "max_latency_ms" in api_stats
        assert api_stats["max_latency_ms"] == 300

    def test_success_rate_calculation(self, observability):
        """Should calculate success rate correctly."""
        # 7 successes, 3 failures = 70% success rate
        for _ in range(7):
            observability.track_api_call("test_api", 100, True, 0)
        for _ in range(3):
            observability.track_api_call("test_api", 100, False, 0)

        summary = observability.get_health_summary()
        assert summary["api_calls"]["by_api"]["test_api"]["success_rate"] == pytest.approx(0.7, rel=0.01)

    def test_get_health_summary_structure(self, observability):
        """get_health_summary should return complete structure."""
        summary = observability.get_health_summary()

        assert "api_calls" in summary
        assert "uptime_seconds" in summary
        assert "last_updated" in summary
        assert "status" in summary
        assert "errors" in summary

    def test_get_health_summary_status_healthy(self, observability):
        """Status should be healthy when success rate > 90%."""
        for _ in range(10):
            observability.track_api_call("test", 100, True, 0)

        summary = observability.get_health_summary()
        assert summary["status"] == "healthy"

    def test_get_health_summary_status_degraded(self, observability):
        """Status should be degraded when 50% < success rate < 90%."""
        for _ in range(7):
            observability.track_api_call("test", 100, True, 0)
        for _ in range(3):
            observability.track_api_call("test", 100, False, 0)

        summary = observability.get_health_summary()
        assert summary["status"] == "degraded"

    def test_get_health_summary_status_unhealthy(self, observability):
        """Status should be unhealthy when success rate < 50%."""
        for _ in range(3):
            observability.track_api_call("test", 100, True, 0)
        for _ in range(7):
            observability.track_api_call("test", 100, False, 0)

        summary = observability.get_health_summary()
        assert summary["status"] == "unhealthy"

    def test_get_daily_costs_empty(self, observability):
        """get_daily_costs should return zero when no tokens used."""
        costs = observability.get_daily_costs()
        assert costs["total_usd"] == 0.0
        assert costs["by_api"] == {}

    def test_get_daily_costs_calculation(self, observability):
        """get_daily_costs should calculate costs based on tokens."""
        # Track some API calls with tokens
        observability.track_api_call("openai", 100, True, tokens_used=1000)
        observability.track_api_call("anthropic", 100, True, tokens_used=2000)

        costs = observability.get_daily_costs()

        assert costs["total_usd"] > 0
        assert "openai" in costs["by_api"]
        assert "anthropic" in costs["by_api"]
        assert costs["by_api"]["openai"]["tokens"] == 1000
        assert costs["by_api"]["anthropic"]["tokens"] == 2000

    def test_get_daily_costs_with_custom_rates(self, observability):
        """get_daily_costs should use custom token rates if provided."""
        observability.set_token_rates({
            "openai": 0.01,  # $0.01 per 1k tokens
            "anthropic": 0.015  # $0.015 per 1k tokens
        })

        observability.track_api_call("openai", 100, True, tokens_used=1000)
        observability.track_api_call("anthropic", 100, True, tokens_used=1000)

        costs = observability.get_daily_costs()

        assert costs["by_api"]["openai"]["cost_usd"] == pytest.approx(0.01, rel=0.01)
        assert costs["by_api"]["anthropic"]["cost_usd"] == pytest.approx(0.015, rel=0.01)

    def test_alert_if_threshold_exceeded_no_alert(self, observability):
        """alert_if_threshold_exceeded should return None when under threshold."""
        observability.track_api_call("test", 100, True, tokens_used=100)

        alert = observability.alert_if_threshold_exceeded(
            cost_threshold_usd=10.0,
            latency_threshold_ms=1000,
            error_rate_threshold=0.5
        )

        assert alert is None

    def test_alert_if_threshold_exceeded_cost(self, observability):
        """alert_if_threshold_exceeded should alert when cost exceeded."""
        observability.set_token_rates({"expensive_api": 100.0})  # $100 per 1k tokens
        observability.track_api_call("expensive_api", 100, True, tokens_used=1000)

        alert = observability.alert_if_threshold_exceeded(
            cost_threshold_usd=10.0,
            latency_threshold_ms=1000,
            error_rate_threshold=0.5
        )

        assert alert is not None
        assert "cost" in alert["reason"].lower()

    def test_alert_if_threshold_exceeded_latency(self, observability):
        """alert_if_threshold_exceeded should alert when latency exceeded."""
        observability.track_api_call("slow_api", 5000, True, tokens_used=0)

        alert = observability.alert_if_threshold_exceeded(
            cost_threshold_usd=10.0,
            latency_threshold_ms=1000,
            error_rate_threshold=0.5
        )

        assert alert is not None
        assert "latency" in alert["reason"].lower()

    def test_alert_if_threshold_exceeded_error_rate(self, observability):
        """alert_if_threshold_exceeded should alert when error rate exceeded."""
        for _ in range(8):
            observability.track_api_call("failing_api", 100, False, 0)
        for _ in range(2):
            observability.track_api_call("failing_api", 100, True, 0)

        alert = observability.alert_if_threshold_exceeded(
            cost_threshold_usd=100.0,
            latency_threshold_ms=10000,
            error_rate_threshold=0.5
        )

        assert alert is not None
        assert "error" in alert["reason"].lower()

    def test_persistence_save(self, observability, temp_metrics_file):
        """Metrics should be persisted to JSON file."""
        observability.track_api_call("telegram", 100, True, 50)
        observability.save()

        with open(temp_metrics_file, 'r') as f:
            data = json.load(f)

        assert "api_calls" in data
        assert data["api_calls"]["total"] >= 1

    def test_persistence_load(self, temp_metrics_file):
        """Metrics should load from existing JSON file."""
        # Pre-populate the file
        pre_data = {
            "api_calls": {
                "total": 5,
                "by_api": {
                    "telegram": {
                        "success_count": 4,
                        "failure_count": 1,
                        "total_tokens": 500,
                        "latencies": [100, 150, 200, 250, 300]
                    }
                }
            },
            "started_at": datetime.utcnow().isoformat(),
            "errors": []
        }
        with open(temp_metrics_file, 'w') as f:
            json.dump(pre_data, f)

        from bots.shared.observability import ClawdBotObservability
        obs = ClawdBotObservability(metrics_path=temp_metrics_file)

        summary = obs.get_health_summary()
        assert summary["api_calls"]["total"] == 5

    def test_reset_clears_metrics(self, observability):
        """reset should clear all tracked metrics."""
        observability.track_api_call("test", 100, True, 100)
        observability.reset()

        summary = observability.get_health_summary()
        assert summary["api_calls"]["total"] == 0

    def test_track_error(self, observability):
        """Should track error messages."""
        observability.track_error(
            bot_name="clawdmatt",
            error_type="RateLimitError",
            message="Rate limit exceeded"
        )

        summary = observability.get_health_summary()
        assert len(summary["errors"]) >= 1
        assert summary["errors"][0]["bot"] == "clawdmatt"
        assert summary["errors"][0]["type"] == "RateLimitError"


class TestClawdBotObservabilityThreadSafety:
    """Test thread safety of ClawdBotObservability."""

    @pytest.fixture
    def temp_metrics_file(self, tmp_path):
        """Create a temporary metrics file path."""
        return str(tmp_path / "metrics.json")

    @pytest.fixture
    def observability(self, temp_metrics_file):
        """Create a fresh observability instance with temp file."""
        from bots.shared.observability import ClawdBotObservability
        obs = ClawdBotObservability(metrics_path=temp_metrics_file)
        obs.reset()
        return obs

    def test_concurrent_api_calls(self, observability):
        """Should handle concurrent track_api_call calls."""
        def track_calls():
            for _ in range(100):
                observability.track_api_call("test", 10, True, 10)

        threads = [threading.Thread(target=track_calls) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        summary = observability.get_health_summary()
        assert summary["api_calls"]["total"] == 500

    def test_concurrent_read_write(self, observability):
        """Should handle concurrent reads and writes."""
        results = []
        errors = []

        def write_calls():
            for _ in range(50):
                observability.track_api_call("test", 10, True, 10)
                time.sleep(0.001)

        def read_calls():
            for _ in range(50):
                try:
                    summary = observability.get_health_summary()
                    results.append(summary)
                except Exception as e:
                    errors.append(e)
                time.sleep(0.001)

        threads = [
            threading.Thread(target=write_calls),
            threading.Thread(target=write_calls),
            threading.Thread(target=read_calls),
            threading.Thread(target=read_calls),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 100


class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    @pytest.fixture
    def temp_metrics_file(self, tmp_path):
        """Create a temporary metrics file path."""
        return str(tmp_path / "metrics.json")

    def test_track_api_call_function(self, temp_metrics_file):
        """Module-level track_api_call should work."""
        from bots.shared import observability

        with patch.object(observability, '_default_instance', None):
            with patch.object(observability, 'DEFAULT_METRICS_PATH', temp_metrics_file):
                observability.track_api_call("telegram", 100, True, 50)
                summary = observability.get_health_summary()
                assert summary["api_calls"]["total"] >= 1

    def test_get_health_summary_function(self, temp_metrics_file):
        """Module-level get_health_summary should work."""
        from bots.shared import observability

        with patch.object(observability, '_default_instance', None):
            with patch.object(observability, 'DEFAULT_METRICS_PATH', temp_metrics_file):
                summary = observability.get_health_summary()
                assert "status" in summary

    def test_get_daily_costs_function(self, temp_metrics_file):
        """Module-level get_daily_costs should work."""
        from bots.shared import observability

        with patch.object(observability, '_default_instance', None):
            with patch.object(observability, 'DEFAULT_METRICS_PATH', temp_metrics_file):
                costs = observability.get_daily_costs()
                assert "total_usd" in costs

    def test_alert_if_threshold_exceeded_function(self, temp_metrics_file):
        """Module-level alert_if_threshold_exceeded should work."""
        from bots.shared import observability

        with patch.object(observability, '_default_instance', None):
            with patch.object(observability, 'DEFAULT_METRICS_PATH', temp_metrics_file):
                alert = observability.alert_if_threshold_exceeded()
                # Should return None when under thresholds
                assert alert is None
