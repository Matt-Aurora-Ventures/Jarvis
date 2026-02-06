"""Tests for KaizenEngine - the per-bot self-improvement loop."""

import json
import os
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from bots.shared.kaizen import KaizenEngine, KaizenMetric, KaizenInsight


@pytest.fixture
def tmp_data_dir(tmp_path):
    return str(tmp_path)


@pytest.fixture
def engine(tmp_data_dir):
    return KaizenEngine("testbot", data_dir=tmp_data_dir)


class TestKaizenMetricDataclass:
    def test_create_metric(self):
        m = KaizenMetric(name="error_rate", value=0.05, timestamp="2026-01-01T00:00:00Z", bot="testbot")
        assert m.name == "error_rate"
        assert m.value == 0.05
        assert m.context == ""

    def test_metric_with_context(self):
        m = KaizenMetric(name="latency", value=1.5, timestamp="now", bot="b", context="api call")
        assert m.context == "api call"


class TestKaizenInsightDataclass:
    def test_create_insight(self):
        i = KaizenInsight(category="error_pattern", finding="too many timeouts",
                          recommendation="increase timeout", priority="high")
        assert i.auto_applicable is False
        assert i.applied is False

    def test_auto_applicable(self):
        i = KaizenInsight(category="performance", finding="x", recommendation="y",
                          priority="low", auto_applicable=True)
        assert i.auto_applicable is True


class TestRecordMetric:
    def test_record_and_retrieve(self, engine):
        engine.record_metric("error_rate", 0.1, context="api")
        metrics = json.loads(engine.metrics_file.read_text())
        assert len(metrics) == 1
        assert metrics[0]["name"] == "error_rate"
        assert metrics[0]["value"] == 0.1
        assert metrics[0]["bot"] == "testbot"
        assert metrics[0]["context"] == "api"

    def test_multiple_metrics(self, engine):
        engine.record_metric("a", 1.0)
        engine.record_metric("b", 2.0)
        metrics = json.loads(engine.metrics_file.read_text())
        assert len(metrics) == 2

    def test_creates_data_dir(self, tmp_path):
        sub = str(tmp_path / "nested" / "dir")
        e = KaizenEngine("bot", data_dir=sub)
        e.record_metric("x", 1.0)
        assert Path(sub).exists()


class TestRecordError:
    def test_record_error(self, engine):
        engine.record_error("timeout", "connection to API")
        metrics = json.loads(engine.metrics_file.read_text())
        assert len(metrics) == 1
        assert metrics[0]["name"] == "error"
        assert metrics[0]["context"] == "timeout: connection to API"


class TestRecordResponseQuality:
    def test_record_quality(self, engine):
        engine.record_response_quality(0.85, "chat")
        metrics = json.loads(engine.metrics_file.read_text())
        assert metrics[0]["name"] == "response_quality"
        assert metrics[0]["value"] == 0.85
        assert "chat" in metrics[0]["context"]


class TestAnalyzePeriod:
    def test_empty_analysis(self, engine):
        result = engine.analyze_period(7)
        assert "error_counts" in result
        assert "quality_avg" in result
        assert result["total_metrics"] == 0

    def test_analysis_with_data(self, engine):
        engine.record_metric("error", 1.0, context="timeout: x")
        engine.record_metric("error", 1.0, context="timeout: x")
        engine.record_metric("response_quality", 0.9)
        engine.record_metric("response_quality", 0.7)
        result = engine.analyze_period(7)
        assert result["total_metrics"] == 4
        assert result["error_counts"]["timeout: x"] == 2
        assert 0.79 < result["quality_avg"] < 0.81


class TestDetectErrorPatterns:
    def test_no_errors(self, engine):
        assert engine.detect_error_patterns() == []

    def test_recurring_pattern(self, engine):
        for _ in range(5):
            engine.record_error("timeout", "api call")
        engine.record_error("auth_fail", "login")
        patterns = engine.detect_error_patterns()
        assert len(patterns) >= 1
        assert patterns[0]["error_type"] == "timeout: api call"
        assert patterns[0]["count"] == 5


class TestDetectPerformanceTrends:
    def test_no_data(self, engine):
        assert engine.detect_performance_trends() == []

    def test_declining_quality(self, engine):
        # Record declining quality scores
        now = datetime.now(timezone.utc)
        metrics = []
        for i in range(10):
            ts = (now - timedelta(days=6) + timedelta(hours=i * 12)).isoformat()
            metrics.append({
                "name": "response_quality",
                "value": 0.9 - (i * 0.05),
                "timestamp": ts,
                "bot": "testbot",
                "context": ""
            })
        engine.metrics_file.parent.mkdir(parents=True, exist_ok=True)
        engine.metrics_file.write_text(json.dumps(metrics))
        trends = engine.detect_performance_trends()
        # Should detect declining trend
        assert any(t["direction"] == "declining" for t in trends)


class TestGenerateInsights:
    def test_no_data_returns_empty(self, engine):
        insights = engine.generate_insights()
        assert isinstance(insights, list)

    def test_generates_from_errors(self, engine):
        for _ in range(5):
            engine.record_error("timeout", "flaky endpoint")
        insights = engine.generate_insights()
        assert len(insights) > 0
        assert all(isinstance(i, KaizenInsight) for i in insights)


class TestPrioritizeInsights:
    def test_priority_order(self, engine):
        insights = [
            KaizenInsight("a", "low thing", "do x", "low"),
            KaizenInsight("b", "high thing", "do y", "high"),
            KaizenInsight("c", "med thing", "do z", "medium"),
        ]
        result = engine.prioritize_insights(insights)
        assert result[0].priority == "high"
        assert result[-1].priority == "low"


class TestApplyAutoInsights:
    def test_applies_auto(self, engine):
        insights = [
            KaizenInsight("a", "f", "r", "low", auto_applicable=True),
            KaizenInsight("b", "f2", "r2", "high", auto_applicable=False),
        ]
        applied = engine.apply_auto_insights(insights)
        assert len(applied) == 1
        assert applied[0].applied is True
        # Original non-auto should be unchanged
        assert insights[1].applied is False


class TestFormatReviewReport:
    def test_format_report(self, engine):
        insights = [
            KaizenInsight("error_pattern", "many timeouts", "add retry", "high"),
        ]
        report = engine.format_review_report(insights)
        assert "timeouts" in report
        assert "retry" in report
        assert isinstance(report, str)

    def test_empty_report(self, engine):
        report = engine.format_review_report([])
        assert isinstance(report, str)


class TestRunCycle:
    def test_full_cycle_empty(self, engine):
        report = engine.run_cycle()
        assert isinstance(report, str)

    def test_full_cycle_with_data(self, engine):
        for _ in range(3):
            engine.record_error("timeout", "api")
        engine.record_response_quality(0.8)
        report = engine.run_cycle()
        assert isinstance(report, str)
        # Cycle should be logged
        assert engine.cycle_log.exists()

    def test_cycle_logged(self, engine):
        engine.run_cycle()
        cycles = json.loads(engine.cycle_log.read_text())
        assert len(cycles) == 1
        assert "timestamp" in cycles[0]


class TestGetImprovementHistory:
    def test_empty_history(self, engine):
        history = engine.get_improvement_history()
        assert history == []

    def test_history_after_cycles(self, engine):
        engine.run_cycle()
        engine.run_cycle()
        history = engine.get_improvement_history()
        assert len(history) == 2


class TestThreadSafety:
    def test_concurrent_writes_dont_crash(self, engine):
        """Basic test that rapid writes don't corrupt JSON."""
        for i in range(50):
            engine.record_metric(f"metric_{i}", float(i))
        metrics = json.loads(engine.metrics_file.read_text())
        assert len(metrics) == 50
