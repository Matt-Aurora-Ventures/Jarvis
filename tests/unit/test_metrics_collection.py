"""
Comprehensive tests for the JARVIS metrics collection system.

Tests cover:
1. Metric collection accuracy (Counter, Gauge, Histogram)
2. Aggregation functions (percentiles, error rates, time windows)
3. Time-series data storage (sliding windows, persistence)
4. Alert thresholds and triggers
5. Memory usage bounds (no unbounded growth)

Modules tested:
- core/monitoring/metrics.py
- core/monitoring/metrics_collector.py
- core/monitoring/business_metrics.py
- core/monitoring/performance_tracker.py
"""

import asyncio
import gc
import json
import os
import sqlite3
import sys
import tempfile
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_metrics_db(temp_data_dir):
    """Create a temporary metrics database path."""
    db_path = temp_data_dir / "metrics.db"
    return str(db_path)


@pytest.fixture
def isolated_registry():
    """Create an isolated metrics registry for testing."""
    from core.monitoring.metrics import MetricsRegistry
    return MetricsRegistry()


@pytest.fixture
def isolated_collector(temp_metrics_db):
    """Create an isolated metrics collector for testing."""
    from core.monitoring.metrics_collector import MetricsCollector
    return MetricsCollector(db_path=temp_metrics_db)


@pytest.fixture
def isolated_business_metrics():
    """Create an isolated business metrics collector for testing."""
    from core.monitoring.business_metrics import BusinessMetricsCollector
    return BusinessMetricsCollector()


@pytest.fixture
def isolated_performance_tracker(temp_data_dir):
    """Create an isolated performance tracker for testing."""
    from core.monitoring.performance_tracker import PerformanceTracker
    return PerformanceTracker(data_dir=str(temp_data_dir))


# =============================================================================
# SECTION 1: METRIC COLLECTION ACCURACY
# =============================================================================

class TestCounterMetric:
    """Tests for Counter metric type accuracy."""

    def test_counter_initialization(self, isolated_registry):
        """Test counter initializes with correct values."""
        counter = isolated_registry.counter(
            "test_counter",
            "Test counter description",
            ["label1", "label2"]
        )

        assert counter.name == "test_counter"
        assert counter.description == "Test counter description"
        assert counter.label_names == ["label1", "label2"]
        assert counter.get(label1="a", label2="b") == 0

    def test_counter_increment_default(self, isolated_registry):
        """Test counter increments by 1 by default."""
        counter = isolated_registry.counter("inc_counter", "Test")

        counter.inc()
        assert counter.get() == 1

        counter.inc()
        assert counter.get() == 2

    def test_counter_increment_custom_value(self, isolated_registry):
        """Test counter increments by custom value."""
        counter = isolated_registry.counter("custom_counter", "Test")

        counter.inc(5)
        assert counter.get() == 5

        counter.inc(10)
        assert counter.get() == 15

    def test_counter_with_labels(self, isolated_registry):
        """Test counter tracks values per label combination."""
        counter = isolated_registry.counter(
            "labeled_counter",
            "Test",
            ["method", "status"]
        )

        counter.inc(1, method="GET", status="200")
        counter.inc(1, method="GET", status="200")
        counter.inc(1, method="POST", status="201")
        counter.inc(1, method="GET", status="500")

        assert counter.get(method="GET", status="200") == 2
        assert counter.get(method="POST", status="201") == 1
        assert counter.get(method="GET", status="500") == 1
        assert counter.get(method="DELETE", status="200") == 0  # Never incremented

    def test_counter_collect(self, isolated_registry):
        """Test counter collects all labeled values."""
        counter = isolated_registry.counter(
            "collect_counter",
            "Test",
            ["type"]
        )

        counter.inc(10, type="success")
        counter.inc(5, type="error")

        collected = counter.collect()

        assert len(collected) == 2
        values = {mv.labels["type"]: mv.value for mv in collected}
        assert values["success"] == 10
        assert values["error"] == 5

    def test_counter_thread_safety(self, isolated_registry):
        """Test counter is thread-safe under concurrent access."""
        counter = isolated_registry.counter("thread_counter", "Test")

        def increment_many():
            for _ in range(1000):
                counter.inc()

        threads = [threading.Thread(target=increment_many) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert counter.get() == 10000


class TestGaugeMetric:
    """Tests for Gauge metric type accuracy."""

    def test_gauge_initialization(self, isolated_registry):
        """Test gauge initializes correctly."""
        gauge = isolated_registry.gauge(
            "test_gauge",
            "Test gauge",
            ["instance"]
        )

        assert gauge.name == "test_gauge"
        assert gauge.get(instance="a") == 0

    def test_gauge_set(self, isolated_registry):
        """Test gauge set operation."""
        gauge = isolated_registry.gauge("set_gauge", "Test")

        gauge.set(100)
        assert gauge.get() == 100

        gauge.set(50)
        assert gauge.get() == 50

    def test_gauge_increment(self, isolated_registry):
        """Test gauge increment operation."""
        gauge = isolated_registry.gauge("inc_gauge", "Test")

        gauge.set(100)
        gauge.inc(10)
        assert gauge.get() == 110

    def test_gauge_decrement(self, isolated_registry):
        """Test gauge decrement operation."""
        gauge = isolated_registry.gauge("dec_gauge", "Test")

        gauge.set(100)
        gauge.dec(30)
        assert gauge.get() == 70

    def test_gauge_with_labels(self, isolated_registry):
        """Test gauge tracks separate values per label."""
        gauge = isolated_registry.gauge(
            "labeled_gauge",
            "Test",
            ["region"]
        )

        gauge.set(100, region="us-east")
        gauge.set(200, region="eu-west")

        assert gauge.get(region="us-east") == 100
        assert gauge.get(region="eu-west") == 200

    def test_gauge_thread_safety(self, isolated_registry):
        """Test gauge is thread-safe."""
        gauge = isolated_registry.gauge("thread_gauge", "Test")
        gauge.set(0)

        def modify():
            for _ in range(100):
                gauge.inc(1)
                gauge.dec(1)

        threads = [threading.Thread(target=modify) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should end at 0 after equal inc/dec
        assert gauge.get() == 0


class TestHistogramMetric:
    """Tests for Histogram metric type accuracy."""

    def test_histogram_initialization(self, isolated_registry):
        """Test histogram initializes with correct buckets."""
        histogram = isolated_registry.histogram(
            "test_histogram",
            "Test",
            buckets=(0.1, 0.5, 1.0, 5.0)
        )

        assert histogram.name == "test_histogram"
        assert histogram.buckets == (0.1, 0.5, 1.0, 5.0)

    def test_histogram_default_buckets(self, isolated_registry):
        """Test histogram uses default buckets when not specified."""
        histogram = isolated_registry.histogram("default_hist", "Test")

        assert histogram.buckets == histogram.DEFAULT_BUCKETS

    def test_histogram_observe(self, isolated_registry):
        """Test histogram observe records values in correct buckets."""
        histogram = isolated_registry.histogram(
            "observe_hist",
            "Test",
            buckets=(0.1, 0.5, 1.0, 5.0)
        )

        histogram.observe(0.05)  # <= 0.1, 0.5, 1.0, 5.0
        histogram.observe(0.3)   # <= 0.5, 1.0, 5.0
        histogram.observe(0.8)   # <= 1.0, 5.0
        histogram.observe(3.0)   # <= 5.0
        histogram.observe(10.0)  # > all buckets

        collected = histogram.collect()

        # Find bucket counts
        bucket_counts = {}
        for mv in collected:
            if "le" in mv.labels:
                bucket_counts[float(mv.labels["le"])] = mv.value

        assert bucket_counts[0.1] == 1  # Only 0.05
        assert bucket_counts[0.5] == 2  # 0.05, 0.3
        assert bucket_counts[1.0] == 3  # 0.05, 0.3, 0.8
        assert bucket_counts[5.0] == 4  # 0.05, 0.3, 0.8, 3.0

    def test_histogram_sum_and_count(self, isolated_registry):
        """Test histogram tracks sum and count correctly."""
        histogram = isolated_registry.histogram(
            "sum_count_hist",
            "Test",
            buckets=(1.0, 5.0)
        )

        histogram.observe(1.5)
        histogram.observe(2.5)
        histogram.observe(3.0)

        collected = histogram.collect()

        sum_value = None
        count_value = None
        for mv in collected:
            if mv.labels.get("type") == "sum":
                sum_value = mv.value
            elif mv.labels.get("type") == "count":
                count_value = mv.value

        assert sum_value == 7.0  # 1.5 + 2.5 + 3.0
        assert count_value == 3

    def test_histogram_time_context_manager(self, isolated_registry):
        """Test histogram time context manager records duration."""
        histogram = isolated_registry.histogram(
            "time_hist",
            "Test",
            buckets=(0.01, 0.1, 1.0)
        )

        with histogram.time():
            time.sleep(0.02)  # Sleep 20ms

        collected = histogram.collect()

        sum_value = None
        for mv in collected:
            if mv.labels.get("type") == "sum":
                sum_value = mv.value

        # Should have recorded approximately 0.02 seconds
        assert sum_value is not None
        assert 0.015 < sum_value < 0.1  # Allow some tolerance


# =============================================================================
# SECTION 2: AGGREGATION FUNCTIONS
# =============================================================================

class TestPercentileCalculator:
    """Tests for percentile calculations."""

    def test_percentile_calculator_init(self):
        """Test percentile calculator initialization."""
        from core.monitoring.metrics_collector import PercentileCalculator

        calc = PercentileCalculator(max_samples=100)
        assert calc.max_samples == 100
        assert calc.count() == 0

    def test_percentile_add_values(self):
        """Test adding values to percentile calculator."""
        from core.monitoring.metrics_collector import PercentileCalculator

        calc = PercentileCalculator()

        for i in range(100):
            calc.add(float(i))

        assert calc.count() == 100
        assert calc.min() == 0.0
        assert calc.max() == 99.0

    def test_percentile_calculation_accuracy(self):
        """Test percentile calculations are accurate."""
        from core.monitoring.metrics_collector import PercentileCalculator

        calc = PercentileCalculator()

        # Add values 1-100
        for i in range(1, 101):
            calc.add(float(i))

        # P50 should be around 50
        assert 49 <= calc.percentile(50) <= 51

        # P90 should be around 90
        assert 89 <= calc.percentile(90) <= 91

        # P99 should be around 99
        assert 98 <= calc.percentile(99) <= 100

    def test_percentile_mean_calculation(self):
        """Test mean calculation."""
        from core.monitoring.metrics_collector import PercentileCalculator

        calc = PercentileCalculator()

        calc.add(10.0)
        calc.add(20.0)
        calc.add(30.0)

        assert calc.mean() == 20.0

    def test_percentile_max_samples_limit(self):
        """Test that calculator respects max_samples limit."""
        from core.monitoring.metrics_collector import PercentileCalculator

        calc = PercentileCalculator(max_samples=10)

        # Add 20 values
        for i in range(20):
            calc.add(float(i))

        # Should only keep 10
        assert calc.count() == 10

    def test_percentile_cleanup_by_window(self):
        """Test cleanup removes old entries."""
        from core.monitoring.metrics_collector import PercentileCalculator

        calc = PercentileCalculator()

        # Add old values
        old_time = time.time() - 400  # 400 seconds ago
        for i in range(10):
            calc.add(float(i), timestamp=old_time)

        # Add recent values
        for i in range(10):
            calc.add(float(i + 100))

        # Cleanup with 300 second window
        calc.cleanup(300)

        # Should only have recent values
        assert calc.count() == 10
        assert calc.min() >= 100


class TestSlidingWindow:
    """Tests for sliding window time-series storage."""

    def test_sliding_window_init(self):
        """Test sliding window initialization."""
        from core.monitoring.metrics_collector import SlidingWindow

        window = SlidingWindow(window_seconds=60)
        assert window.window_seconds == 60
        assert window.count() == 0

    def test_sliding_window_add_and_get(self):
        """Test adding and retrieving from sliding window."""
        from core.monitoring.metrics_collector import SlidingWindow, RequestMetric

        window = SlidingWindow(window_seconds=300)

        metric = RequestMetric(
            timestamp=time.time(),
            component="test",
            endpoint="/api/test",
            latency_ms=100,
            success=True
        )

        window.add(metric)

        assert window.count() == 1
        metrics = window.get_all()
        assert len(metrics) == 1
        assert metrics[0].latency_ms == 100

    def test_sliding_window_expiry(self):
        """Test sliding window removes expired entries."""
        from core.monitoring.metrics_collector import SlidingWindow, RequestMetric

        window = SlidingWindow(window_seconds=1)  # 1 second window

        # Add metric
        metric = RequestMetric(
            timestamp=time.time() - 2,  # 2 seconds ago
            component="test",
            endpoint="/test",
            latency_ms=100,
            success=True
        )
        window._data.append(metric)  # Bypass cleanup

        # Should be cleaned up on get
        assert window.count() == 0


class TestErrorRateCalculation:
    """Tests for error rate aggregation."""

    def test_error_rate_calculation(self, isolated_collector):
        """Test error rate is calculated correctly."""
        # Record 8 successes, 2 failures
        for _ in range(8):
            isolated_collector.record_request(
                component="api",
                endpoint="/test",
                latency_ms=100,
                success=True
            )

        for _ in range(2):
            isolated_collector.record_request(
                component="api",
                endpoint="/test",
                latency_ms=100,
                success=False,
                error_type="ServerError"
            )

        stats = isolated_collector.get_error_rate("api")

        assert stats.total_requests == 10
        assert stats.failed_requests == 2
        assert stats.error_rate == pytest.approx(0.2, rel=0.01)

    def test_error_rate_by_type(self, isolated_collector):
        """Test error rate tracks error types."""
        isolated_collector.record_request(
            component="api",
            endpoint="/test",
            latency_ms=100,
            success=False,
            error_type="ConnectionError"
        )
        isolated_collector.record_request(
            component="api",
            endpoint="/test",
            latency_ms=100,
            success=False,
            error_type="ConnectionError"
        )
        isolated_collector.record_request(
            component="api",
            endpoint="/test",
            latency_ms=100,
            success=False,
            error_type="TimeoutError"
        )

        stats = isolated_collector.get_error_rate("api")

        assert stats.error_types["ConnectionError"] == 2
        assert stats.error_types["TimeoutError"] == 1

    def test_error_rate_empty_component(self, isolated_collector):
        """Test error rate for component with no data."""
        stats = isolated_collector.get_error_rate("nonexistent")

        assert stats.total_requests == 0
        assert stats.error_rate == 0.0


class TestLatencyPercentiles:
    """Tests for latency percentile aggregation."""

    def test_latency_percentiles(self, isolated_collector):
        """Test latency percentiles are calculated correctly."""
        # Record varied latencies
        latencies = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 200, 300, 400, 500]

        for latency in latencies:
            isolated_collector.record_request(
                component="api",
                endpoint="/test",
                latency_ms=float(latency),
                success=True
            )

        stats = isolated_collector.get_latency_percentiles("api")

        assert stats.sample_count == len(latencies)
        assert stats.min_ms == 10.0
        assert stats.max_ms == 500.0

        # P50 should be around median
        assert 50 <= stats.p50_ms <= 100

        # P95 should be high
        assert stats.p95_ms >= 300


# =============================================================================
# SECTION 3: TIME-SERIES DATA STORAGE
# =============================================================================

class TestTimeSeriesStorage:
    """Tests for time-series data persistence."""

    def test_database_initialization(self, temp_metrics_db):
        """Test metrics database is created correctly."""
        from core.monitoring.metrics_collector import MetricsCollector

        collector = MetricsCollector(db_path=temp_metrics_db)

        # Check database exists
        assert os.path.exists(temp_metrics_db)

        # Check tables exist
        conn = sqlite3.connect(temp_metrics_db)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}

        assert "metrics_1m" in tables
        assert "metrics_1h" in tables
        assert "alert_history" in tables

        conn.close()

    @pytest.mark.asyncio
    async def test_aggregation_persistence(self, temp_metrics_db):
        """Test that aggregates are persisted to database."""
        from core.monitoring.metrics_collector import MetricsCollector

        collector = MetricsCollector(db_path=temp_metrics_db)

        # Record some metrics
        for _ in range(10):
            collector.record_request(
                component="test_component",
                endpoint="/test",
                latency_ms=100.0,
                success=True
            )

        # Manually trigger save
        await collector._save_aggregates()

        # Check database has data
        conn = sqlite3.connect(temp_metrics_db)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM metrics_1m WHERE component = 'test_component'")
        count = cursor.fetchone()[0]

        conn.close()

        assert count >= 1

    def test_historical_query(self, temp_metrics_db):
        """Test querying historical metrics."""
        from core.monitoring.metrics_collector import MetricsCollector

        collector = MetricsCollector(db_path=temp_metrics_db)

        # Insert some test data
        conn = sqlite3.connect(temp_metrics_db)
        cursor = conn.cursor()

        now = datetime.now(timezone.utc)
        for i in range(5):
            ts = (now - timedelta(hours=i)).isoformat()
            cursor.execute("""
                INSERT INTO metrics_1m
                (timestamp, component, total_requests, failed_requests, error_rate,
                 latency_p50, latency_p95, latency_p99, latency_min, latency_max, latency_mean)
                VALUES (?, 'test', 100, 5, 0.05, 50, 95, 99, 10, 200, 75)
            """, (ts,))

        conn.commit()
        conn.close()

        # Query historical data
        history = collector.get_historical_metrics("test", hours=24)

        assert len(history) == 5


class TestPerformanceTrackerStorage:
    """Tests for performance tracker data storage."""

    def test_uptime_persistence(self, isolated_performance_tracker, temp_data_dir):
        """Test uptime samples are persisted."""
        tracker = isolated_performance_tracker

        # Record samples
        tracker.record_uptime_sample(is_up=True)
        tracker.record_uptime_sample(is_up=True)
        tracker.record_uptime_sample(is_up=False)

        # Check file exists
        data_file = temp_data_dir / "performance_data.json"
        assert data_file.exists()

        # Create new tracker and load data
        from core.monitoring.performance_tracker import PerformanceTracker
        tracker2 = PerformanceTracker(data_dir=str(temp_data_dir))

        stats = tracker2.get_uptime_stats()
        assert stats["sample_count"] == 3

    def test_api_samples_persistence(self, isolated_performance_tracker, temp_data_dir):
        """Test API availability samples are persisted."""
        tracker = isolated_performance_tracker

        tracker.record_api_sample("grok", is_available=True, latency_ms=100)
        tracker.record_api_sample("grok", is_available=True, latency_ms=150)
        tracker.record_api_sample("helius", is_available=False, latency_ms=0)

        # Reload
        from core.monitoring.performance_tracker import PerformanceTracker
        tracker2 = PerformanceTracker(data_dir=str(temp_data_dir))

        api_stats = tracker2.get_api_availability()

        assert "grok" in api_stats
        assert api_stats["grok"]["sample_count"] == 2

    def test_trade_latency_persistence(self, isolated_performance_tracker, temp_data_dir):
        """Test trade latency samples are persisted."""
        tracker = isolated_performance_tracker

        tracker.record_trade_latency(100.0)
        tracker.record_trade_latency(200.0)
        tracker.record_trade_latency(150.0)

        # Reload
        from core.monitoring.performance_tracker import PerformanceTracker
        tracker2 = PerformanceTracker(data_dir=str(temp_data_dir))

        stats = tracker2.get_trade_latency_stats()

        assert stats["sample_count"] == 3
        assert stats["average_ms"] == 150.0


# =============================================================================
# SECTION 4: ALERT THRESHOLDS
# =============================================================================

class TestAlertThresholds:
    """Tests for alert threshold triggers."""

    def test_add_threshold(self, isolated_collector):
        """Test adding alert threshold."""
        isolated_collector.add_threshold(
            name="high_error_rate",
            component="api",
            metric="error_rate",
            threshold=0.1,
            severity="warning"
        )

        assert "high_error_rate" in isolated_collector._thresholds

    def test_threshold_triggers_on_breach(self, isolated_collector):
        """Test threshold triggers when breached."""
        alert_triggered = []

        def callback(name, value, threshold):
            alert_triggered.append((name, value, threshold))

        isolated_collector.add_threshold(
            name="high_error_rate",
            component="api",
            metric="error_rate",
            threshold=0.1,
            duration_seconds=0,  # Immediate trigger
            callback=callback
        )

        # Record failures to breach threshold
        for _ in range(5):
            isolated_collector.record_request(
                component="api",
                endpoint="/test",
                latency_ms=100,
                success=False,
                error_type="Error"
            )

        # Give time for threshold check
        time.sleep(0.1)

        # Should have triggered
        assert len(alert_triggered) >= 1
        assert alert_triggered[0][0] == "high_error_rate"

    def test_threshold_does_not_trigger_below(self, isolated_collector):
        """Test threshold does not trigger below threshold."""
        alert_triggered = []

        def callback(name, value, threshold):
            alert_triggered.append((name, value, threshold))

        isolated_collector.add_threshold(
            name="high_error_rate",
            component="api",
            metric="error_rate",
            threshold=0.5,  # 50% error rate
            duration_seconds=0,
            callback=callback
        )

        # Record mostly successes (10% error rate)
        for _ in range(9):
            isolated_collector.record_request(
                component="api",
                endpoint="/test",
                latency_ms=100,
                success=True
            )

        isolated_collector.record_request(
            component="api",
            endpoint="/test",
            latency_ms=100,
            success=False,
            error_type="Error"
        )

        # Should not trigger
        assert len(alert_triggered) == 0

    def test_latency_threshold(self, isolated_collector):
        """Test latency-based threshold."""
        alert_triggered = []

        def callback(name, value, threshold):
            alert_triggered.append((name, value, threshold))

        isolated_collector.add_threshold(
            name="high_latency",
            component="api",
            metric="latency_p95",
            threshold=100,  # 100ms
            duration_seconds=0,
            callback=callback
        )

        # Record high latency requests
        for _ in range(10):
            isolated_collector.record_request(
                component="api",
                endpoint="/test",
                latency_ms=500,  # 500ms
                success=True
            )

        # Should trigger
        assert len(alert_triggered) >= 1

    def test_remove_threshold(self, isolated_collector):
        """Test removing threshold."""
        isolated_collector.add_threshold(
            name="test_threshold",
            component="api",
            metric="error_rate",
            threshold=0.1
        )

        assert "test_threshold" in isolated_collector._thresholds

        isolated_collector.remove_threshold("test_threshold")

        assert "test_threshold" not in isolated_collector._thresholds

    def test_alert_history_stored(self, isolated_collector, temp_metrics_db):
        """Test alert history is stored in database."""
        isolated_collector.add_threshold(
            name="stored_alert",
            component="api",
            metric="error_rate",
            threshold=0.1,
            duration_seconds=0
        )

        # Trigger alert
        for _ in range(10):
            isolated_collector.record_request(
                component="api",
                endpoint="/test",
                latency_ms=100,
                success=False,
                error_type="Error"
            )

        # Check database
        conn = sqlite3.connect(temp_metrics_db)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM alert_history WHERE threshold_name = 'stored_alert'")
        count = cursor.fetchone()[0]

        conn.close()

        assert count >= 1


class TestPerformanceTargetAlerts:
    """Tests for performance target breach alerts."""

    def test_uptime_target_breach(self, isolated_performance_tracker):
        """Test alert when uptime falls below target."""
        tracker = isolated_performance_tracker

        # Record mostly down samples
        for _ in range(100):
            tracker.record_uptime_sample(is_up=False)

        alerts = tracker.check_targets()

        assert len(alerts) >= 1
        assert any("uptime" in a["type"].lower() for a in alerts)

    def test_api_availability_breach(self, isolated_performance_tracker):
        """Test alert when API availability falls below target."""
        tracker = isolated_performance_tracker

        # Record many unavailable samples
        for _ in range(100):
            tracker.record_api_sample("test_api", is_available=False, latency_ms=0)

        alerts = tracker.check_targets()

        # Should have API availability alert
        assert any("api_availability" in a["type"].lower() for a in alerts)

    def test_no_alert_when_meeting_targets(self, isolated_performance_tracker):
        """Test no alerts when meeting targets."""
        tracker = isolated_performance_tracker

        # Record all good samples
        for _ in range(100):
            tracker.record_uptime_sample(is_up=True)
            tracker.record_api_sample("test_api", is_available=True, latency_ms=50)

        alerts = tracker.check_targets()

        assert len(alerts) == 0


# =============================================================================
# SECTION 5: MEMORY USAGE BOUNDS
# =============================================================================

class TestMemoryBounds:
    """Tests for memory usage and bounds checking."""

    def test_sliding_window_bounded(self, isolated_collector):
        """Test sliding windows don't grow unbounded."""
        # Record many requests
        for _ in range(10000):
            isolated_collector.record_request(
                component="memory_test",
                endpoint="/test",
                latency_ms=100,
                success=True
            )

        # Check window sizes are reasonable
        for component, windows in isolated_collector._sliding_windows.items():
            for window_sec, window in windows.items():
                # Window should not exceed what fits in the time window
                # For 1h window, assuming 1 request per iteration with small time
                # we shouldn't have more than a few thousand entries
                assert window.count() < 50000

    def test_percentile_calculator_bounded(self):
        """Test percentile calculator respects max_samples."""
        from core.monitoring.metrics_collector import PercentileCalculator

        calc = PercentileCalculator(max_samples=1000)

        # Add 10000 values
        for i in range(10000):
            calc.add(float(i))

        # Should be bounded at 1000
        assert calc.count() == 1000

    def test_business_metrics_cleanup(self, isolated_business_metrics):
        """Test business metrics cleanup removes old data."""
        collector = isolated_business_metrics

        # Record many items
        for i in range(1000):
            collector.record_trade(
                symbol="SOL/USDC",
                side="buy",
                volume_usd=100.0
            )
            collector.record_bot_event(
                bot_type="telegram",
                event_type="message"
            )

        # Run cleanup
        removed = collector.cleanup_old_data(days=0)  # Remove everything

        assert removed > 0

        # Should be empty now
        metrics = collector.get_all_metrics()
        assert metrics["trading"]["total_trades"] == 0

    def test_performance_tracker_persistence_limits(self, temp_data_dir):
        """Test performance tracker limits persisted samples to prevent unbounded file growth."""
        from core.monitoring.performance_tracker import PerformanceTracker, UptimeSample

        tracker = PerformanceTracker(data_dir=str(temp_data_dir))

        # Add more samples than the persistence limit (10000)
        for _ in range(15000):
            tracker._uptime_samples.append(
                UptimeSample(timestamp=datetime.now(timezone.utc), is_up=True)
            )

        # Save data
        tracker._save_data()

        # Load the persisted file and check count
        data_file = temp_data_dir / "performance_data.json"
        with open(data_file) as f:
            data = json.load(f)

        # Persisted data should be limited to 10000
        assert len(data.get("uptime_samples", [])) <= 10000

    def test_performance_tracker_retention_cleanup(self, temp_data_dir):
        """Test performance tracker retention-based cleanup removes old data."""
        from core.monitoring.performance_tracker import PerformanceTracker, UptimeSample

        # Create tracker with 1 hour retention
        tracker = PerformanceTracker(
            data_dir=str(temp_data_dir),
            sample_retention_hours=1
        )

        # Add old samples (2 hours ago)
        old_time = datetime.now(timezone.utc) - timedelta(hours=2)
        for _ in range(100):
            tracker._uptime_samples.append(
                UptimeSample(timestamp=old_time, is_up=True)
            )

        # Add recent samples
        for _ in range(50):
            tracker._uptime_samples.append(
                UptimeSample(timestamp=datetime.now(timezone.utc), is_up=True)
            )

        # Trigger cleanup
        tracker._prune_old_samples()

        # Should only have recent samples
        assert len(tracker._uptime_samples) == 50

    def test_no_memory_leak_on_repeated_operations(self, isolated_collector):
        """Test no memory leak on repeated metric recording."""
        import tracemalloc

        tracemalloc.start()

        # Initial memory
        initial = tracemalloc.get_traced_memory()[0]

        # Record many metrics
        for _ in range(1000):
            isolated_collector.record_request(
                component="leak_test",
                endpoint="/test",
                latency_ms=100,
                success=True
            )

        # Force garbage collection
        gc.collect()

        # Check memory
        current = tracemalloc.get_traced_memory()[0]

        tracemalloc.stop()

        # Memory growth should be reasonable (< 50MB for 1000 requests)
        growth_mb = (current - initial) / (1024 * 1024)
        assert growth_mb < 50, f"Memory grew by {growth_mb:.2f}MB"


# =============================================================================
# SECTION 6: BUSINESS METRICS
# =============================================================================

class TestBusinessMetrics:
    """Tests for business metrics collection."""

    def test_record_trade(self, isolated_business_metrics):
        """Test recording trade metrics."""
        collector = isolated_business_metrics

        collector.record_trade(
            symbol="SOL/USDC",
            side="buy",
            volume_usd=1000.0,
            fee_usd=2.5,
            success=True,
            profit_loss=50.0
        )

        metrics = collector.get_trading_metrics(hours=1)

        assert metrics.total_trades == 1
        assert metrics.successful_trades == 1
        assert metrics.total_volume_usd == 1000.0
        assert metrics.total_fees_usd == 2.5

    def test_trading_win_rate(self, isolated_business_metrics):
        """Test trading win rate calculation."""
        collector = isolated_business_metrics

        # Record 3 wins, 2 losses
        for _ in range(3):
            collector.record_trade(
                symbol="SOL/USDC",
                side="buy",
                volume_usd=100.0,
                success=True
            )

        for _ in range(2):
            collector.record_trade(
                symbol="SOL/USDC",
                side="buy",
                volume_usd=100.0,
                success=False
            )

        metrics = collector.get_trading_metrics()

        assert metrics.win_rate == pytest.approx(0.6, rel=0.01)

    def test_user_activity_tracking(self, isolated_business_metrics):
        """Test user activity tracking."""
        collector = isolated_business_metrics

        collector.record_user_activity(user_id="user1", activity_type="message")
        collector.record_user_activity(user_id="user1", activity_type="message")
        collector.record_user_activity(user_id="user2", activity_type="command")

        metrics = collector.get_user_metrics()

        assert metrics.total_users == 2
        assert metrics.active_users_24h == 2
        assert metrics.messages_sent_24h == 3

    def test_bot_event_tracking(self, isolated_business_metrics):
        """Test bot event tracking."""
        collector = isolated_business_metrics

        collector.record_bot_event(
            bot_type="telegram",
            event_type="message",
            response_time_ms=150,
            success=True
        )
        collector.record_bot_event(
            bot_type="twitter",
            event_type="mention",
            response_time_ms=200,
            success=True
        )

        metrics = collector.get_bot_metrics()

        assert metrics.telegram_messages_24h == 1
        assert metrics.twitter_mentions_24h == 1
        assert metrics.average_response_time_ms == pytest.approx(175.0, rel=0.01)

    def test_llm_metrics_tracking(self, isolated_business_metrics):
        """Test LLM request metrics."""
        collector = isolated_business_metrics

        collector.record_llm_request(
            provider="grok",
            model="grok-beta",
            tokens=1000,
            cost=0.05,
            latency_ms=500,
            cache_hit=False
        )
        collector.record_llm_request(
            provider="grok",
            model="grok-beta",
            tokens=500,
            cost=0.025,
            latency_ms=300,
            cache_hit=True
        )

        metrics = collector.get_llm_metrics()

        assert metrics.total_requests_24h == 2
        assert metrics.total_tokens_24h == 1500
        assert metrics.total_cost_24h == pytest.approx(0.075, rel=0.01)
        assert metrics.cache_hit_rate == pytest.approx(0.5, rel=0.01)

    def test_prometheus_export_format(self, isolated_business_metrics):
        """Test Prometheus format export."""
        collector = isolated_business_metrics

        collector.record_trade(symbol="SOL", side="buy", volume_usd=100.0, success=True)

        prometheus_output = collector.to_prometheus_format()

        assert "jarvis_trades_total" in prometheus_output
        assert "jarvis_trading_volume_usd" in prometheus_output


# =============================================================================
# SECTION 7: METRICS REGISTRY
# =============================================================================

class TestMetricsRegistry:
    """Tests for the metrics registry."""

    def test_registry_creates_metrics(self, isolated_registry):
        """Test registry creates and stores metrics."""
        counter = isolated_registry.counter("test_counter", "Description")
        gauge = isolated_registry.gauge("test_gauge", "Description")
        histogram = isolated_registry.histogram("test_histogram", "Description")

        assert counter is not None
        assert gauge is not None
        assert histogram is not None

    def test_registry_returns_same_metric(self, isolated_registry):
        """Test registry returns same metric on duplicate registration."""
        counter1 = isolated_registry.counter("same_counter", "Description")
        counter2 = isolated_registry.counter("same_counter", "Description")

        assert counter1 is counter2

    def test_collect_all_prometheus_format(self, isolated_registry):
        """Test collecting all metrics in Prometheus format."""
        counter = isolated_registry.counter("requests", "Total requests", ["method"])
        counter.inc(100, method="GET")
        counter.inc(50, method="POST")

        gauge = isolated_registry.gauge("active_users", "Active users")
        gauge.set(42)

        output = isolated_registry.collect_all()

        assert "# HELP requests Total requests" in output
        assert "# TYPE requests counter" in output
        assert 'requests{method="GET"}' in output
        assert "# HELP active_users Active users" in output
        assert "active_users 42" in output


# =============================================================================
# SECTION 8: INTEGRATION TESTS
# =============================================================================

class TestMetricsIntegration:
    """Integration tests for the complete metrics system."""

    @pytest.mark.asyncio
    async def test_full_metrics_flow(self, temp_metrics_db, temp_data_dir):
        """Test complete metrics collection and reporting flow."""
        from core.monitoring.metrics_collector import MetricsCollector
        from core.monitoring.business_metrics import BusinessMetricsCollector
        from core.monitoring.performance_tracker import PerformanceTracker

        # Initialize all collectors
        metrics_collector = MetricsCollector(db_path=temp_metrics_db)
        business_metrics = BusinessMetricsCollector()
        performance_tracker = PerformanceTracker(data_dir=str(temp_data_dir))

        # Record various metrics
        for i in range(10):
            metrics_collector.record_request(
                component="api",
                endpoint=f"/endpoint/{i}",
                latency_ms=float(100 + i * 10),
                success=i % 3 != 0
            )

            business_metrics.record_trade(
                symbol="SOL/USDC",
                side="buy" if i % 2 == 0 else "sell",
                volume_usd=float(1000 + i * 100),
                success=True
            )

            performance_tracker.record_uptime_sample(is_up=True)
            performance_tracker.record_trade_latency(latency_ms=float(150 + i * 5))

        # Get summaries
        collector_summary = metrics_collector.get_summary()
        business_all = business_metrics.get_all_metrics()
        perf_all = performance_tracker.get_all_stats()

        # Verify data flows through correctly
        assert "api" in collector_summary["components"]
        assert business_all["trading"]["total_trades"] == 10
        assert perf_all["uptime"]["sample_count"] == 10

    def test_metrics_thread_safety_integration(self, temp_metrics_db):
        """Test metrics collection is thread-safe in integration."""
        from core.monitoring.metrics_collector import MetricsCollector

        collector = MetricsCollector(db_path=temp_metrics_db)

        def record_requests(component_name):
            for _ in range(100):
                collector.record_request(
                    component=component_name,
                    endpoint="/test",
                    latency_ms=100,
                    success=True
                )

        threads = [
            threading.Thread(target=record_requests, args=(f"component_{i}",))
            for i in range(5)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Each component should have 100 requests
        for i in range(5):
            stats = collector.get_error_rate(f"component_{i}")
            assert stats.total_requests == 100


# =============================================================================
# SECTION 9: PREDEFINED METRICS
# =============================================================================

class TestPredefinedMetrics:
    """Tests for predefined global metrics."""

    def test_http_requests_counter_exists(self):
        """Test HTTP requests counter is predefined."""
        from core.monitoring.metrics import http_requests

        assert http_requests is not None
        assert http_requests.name == "http_requests_total"

    def test_http_latency_histogram_exists(self):
        """Test HTTP latency histogram is predefined."""
        from core.monitoring.metrics import http_latency

        assert http_latency is not None
        assert http_latency.name == "http_request_duration_seconds"

    def test_active_connections_gauge_exists(self):
        """Test active connections gauge is predefined."""
        from core.monitoring.metrics import active_connections

        assert active_connections is not None
        assert active_connections.name == "active_connections"

    def test_provider_metrics_exist(self):
        """Test provider metrics are predefined."""
        from core.monitoring.metrics import provider_calls, provider_latency

        assert provider_calls is not None
        assert provider_latency is not None

    def test_jarvis_specific_metrics_exist(self):
        """Test JARVIS-specific metrics are predefined."""
        from core.monitoring.metrics import (
            TWEETS_POSTED,
            TWEET_LATENCY,
            API_CALLS,
            API_LATENCY,
            ACTIVE_POSITIONS
        )

        assert TWEETS_POSTED is not None
        assert TWEET_LATENCY is not None
        assert API_CALLS is not None
        assert API_LATENCY is not None
        assert ACTIVE_POSITIONS is not None


# =============================================================================
# SECTION 10: DECORATOR TESTS
# =============================================================================

class TestTrackRequestDecorator:
    """Tests for the track_request decorator."""

    @pytest.mark.asyncio
    async def test_decorator_tracks_success(self, temp_metrics_db):
        """Test decorator tracks successful requests."""
        from core.monitoring.metrics_collector import track_request, MetricsCollector

        # Reset singleton for test isolation
        import core.monitoring.metrics_collector as module
        original = module._collector
        module._collector = MetricsCollector(db_path=temp_metrics_db)

        try:
            @track_request("test_component", "/test_endpoint")
            async def test_function():
                return "success"

            result = await test_function()

            assert result == "success"

            # Check metrics were recorded
            stats = module._collector.get_error_rate("test_component")
            assert stats.total_requests == 1
            assert stats.failed_requests == 0
        finally:
            module._collector = original

    @pytest.mark.asyncio
    async def test_decorator_tracks_failure(self, temp_metrics_db):
        """Test decorator tracks failed requests."""
        from core.monitoring.metrics_collector import track_request, MetricsCollector

        import core.monitoring.metrics_collector as module
        original = module._collector
        module._collector = MetricsCollector(db_path=temp_metrics_db)

        try:
            @track_request("test_component", "/failing_endpoint")
            async def failing_function():
                raise ValueError("Test error")

            with pytest.raises(ValueError):
                await failing_function()

            # Check error was recorded
            stats = module._collector.get_error_rate("test_component")
            assert stats.total_requests == 1
            assert stats.failed_requests == 1
            assert "ValueError" in stats.error_types
        finally:
            module._collector = original
