"""
Comprehensive tests for core/metrics.py - Prometheus Metrics Module.

Tests cover:
1. Metric types (Counter, Gauge, Histogram)
2. MetricsRegistry operations
3. Prometheus format export
4. Decorators (track_time, count_calls)
5. Predefined metrics initialization
6. Thread safety
7. Label handling
8. FastAPI/aiohttp integration

Target: 60%+ coverage with 40-60 tests.
"""

import asyncio
import threading
import time
from unittest.mock import MagicMock, patch, AsyncMock

import pytest


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def fresh_registry():
    """Create a fresh MetricsRegistry for isolated testing."""
    from core.metrics import MetricsRegistry
    return MetricsRegistry()


@pytest.fixture
def reset_global_registry():
    """Reset the global registry before and after test."""
    import core.metrics as metrics_module

    original_registry = metrics_module._registry
    original_metrics = metrics_module._metrics

    metrics_module._registry = None
    metrics_module._metrics = None

    yield

    metrics_module._registry = original_registry
    metrics_module._metrics = original_metrics


@pytest.fixture
def sample_counter(fresh_registry):
    """Create a sample counter for testing."""
    return fresh_registry.counter("test_counter", "A test counter")


@pytest.fixture
def sample_gauge(fresh_registry):
    """Create a sample gauge for testing."""
    return fresh_registry.gauge("test_gauge", "A test gauge")


@pytest.fixture
def sample_histogram(fresh_registry):
    """Create a sample histogram for testing."""
    return fresh_registry.histogram("test_histogram", "A test histogram")


# =============================================================================
# SECTION 1: COUNTER METRIC TESTS
# =============================================================================

class TestCounterMetric:
    """Tests for Counter metric type."""

    def test_counter_initialization(self):
        """Test counter initializes with correct values."""
        from core.metrics import Counter

        counter = Counter(name="test", help="Test counter")

        assert counter.name == "test"
        assert counter.help == "Test counter"
        assert counter.get() == 0.0
        assert counter.labels == {}

    def test_counter_initialization_with_labels(self):
        """Test counter initializes with labels."""
        from core.metrics import Counter

        labels = {"method": "GET", "status": "200"}
        counter = Counter(name="http_requests", help="HTTP requests", labels=labels)

        assert counter.labels == labels

    def test_counter_increment_default(self):
        """Test counter increments by 1 by default."""
        from core.metrics import Counter

        counter = Counter(name="test", help="Test")

        counter.inc()
        assert counter.get() == 1.0

        counter.inc()
        assert counter.get() == 2.0

    def test_counter_increment_custom_value(self):
        """Test counter increments by custom value."""
        from core.metrics import Counter

        counter = Counter(name="test", help="Test")

        counter.inc(5.0)
        assert counter.get() == 5.0

        counter.inc(10.5)
        assert counter.get() == 15.5

    def test_counter_increment_float(self):
        """Test counter accepts float increments."""
        from core.metrics import Counter

        counter = Counter(name="test", help="Test")

        counter.inc(0.5)
        counter.inc(1.5)

        assert counter.get() == 2.0

    def test_counter_thread_safety(self):
        """Test counter is thread-safe under concurrent access."""
        from core.metrics import Counter

        counter = Counter(name="thread_test", help="Thread safety test")

        def increment_many():
            for _ in range(1000):
                counter.inc()

        threads = [threading.Thread(target=increment_many) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert counter.get() == 10000.0

    def test_counter_get_is_atomic(self):
        """Test counter get operation is atomic."""
        from core.metrics import Counter

        counter = Counter(name="atomic_test", help="Atomic test")
        counter.inc(100)

        results = []

        def read_value():
            for _ in range(100):
                results.append(counter.get())

        threads = [threading.Thread(target=read_value) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All reads should return consistent values
        assert all(v >= 100 for v in results)


# =============================================================================
# SECTION 2: GAUGE METRIC TESTS
# =============================================================================

class TestGaugeMetric:
    """Tests for Gauge metric type."""

    def test_gauge_initialization(self):
        """Test gauge initializes with correct values."""
        from core.metrics import Gauge

        gauge = Gauge(name="test", help="Test gauge")

        assert gauge.name == "test"
        assert gauge.help == "Test gauge"
        assert gauge.get() == 0.0

    def test_gauge_initialization_with_labels(self):
        """Test gauge initializes with labels."""
        from core.metrics import Gauge

        labels = {"region": "us-east-1"}
        gauge = Gauge(name="connections", help="Active connections", labels=labels)

        assert gauge.labels == labels

    def test_gauge_set(self):
        """Test gauge set operation."""
        from core.metrics import Gauge

        gauge = Gauge(name="test", help="Test")

        gauge.set(100.0)
        assert gauge.get() == 100.0

        gauge.set(50.0)
        assert gauge.get() == 50.0

        gauge.set(0.0)
        assert gauge.get() == 0.0

    def test_gauge_increment(self):
        """Test gauge increment operation."""
        from core.metrics import Gauge

        gauge = Gauge(name="test", help="Test")

        gauge.set(100.0)
        gauge.inc(10.0)
        assert gauge.get() == 110.0

        gauge.inc()  # Default increment
        assert gauge.get() == 111.0

    def test_gauge_decrement(self):
        """Test gauge decrement operation."""
        from core.metrics import Gauge

        gauge = Gauge(name="test", help="Test")

        gauge.set(100.0)
        gauge.dec(30.0)
        assert gauge.get() == 70.0

        gauge.dec()  # Default decrement
        assert gauge.get() == 69.0

    def test_gauge_negative_values(self):
        """Test gauge handles negative values."""
        from core.metrics import Gauge

        gauge = Gauge(name="test", help="Test")

        gauge.set(-50.0)
        assert gauge.get() == -50.0

        gauge.dec(10.0)
        assert gauge.get() == -60.0

    def test_gauge_thread_safety(self):
        """Test gauge is thread-safe."""
        from core.metrics import Gauge

        gauge = Gauge(name="thread_test", help="Thread safety test")
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

        # Should end at 0 after equal inc/dec operations
        assert gauge.get() == 0.0


# =============================================================================
# SECTION 3: HISTOGRAM METRIC TESTS
# =============================================================================

class TestHistogramMetric:
    """Tests for Histogram metric type."""

    def test_histogram_initialization(self):
        """Test histogram initializes with default buckets."""
        from core.metrics import Histogram

        histogram = Histogram(name="test", help="Test histogram")

        assert histogram.name == "test"
        assert histogram.help == "Test histogram"
        assert histogram.buckets == (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

    def test_histogram_custom_buckets(self):
        """Test histogram with custom buckets."""
        from core.metrics import Histogram

        custom_buckets = (0.1, 0.5, 1.0, 5.0)
        histogram = Histogram(name="test", help="Test", buckets=custom_buckets)

        assert histogram.buckets == custom_buckets

    def test_histogram_initialization_with_labels(self):
        """Test histogram initializes with labels."""
        from core.metrics import Histogram

        labels = {"endpoint": "/api/v1"}
        histogram = Histogram(name="latency", help="Request latency", labels=labels)

        assert histogram.labels == labels

    def test_histogram_observe(self):
        """Test histogram observe operation."""
        from core.metrics import Histogram

        histogram = Histogram(
            name="test",
            help="Test",
            buckets=(0.1, 0.5, 1.0, 5.0)
        )

        histogram.observe(0.05)  # <= 0.1
        histogram.observe(0.3)   # <= 0.5
        histogram.observe(0.8)   # <= 1.0
        histogram.observe(3.0)   # <= 5.0
        histogram.observe(10.0)  # > 5.0, goes to +Inf

        buckets = histogram.get_buckets()

        assert buckets[0.1] == 1
        assert buckets[0.5] == 2
        assert buckets[1.0] == 3
        assert buckets[5.0] == 4
        assert buckets[float('inf')] == 5

    def test_histogram_sum(self):
        """Test histogram tracks sum correctly."""
        from core.metrics import Histogram

        histogram = Histogram(name="test", help="Test", buckets=(1.0, 5.0))

        histogram.observe(1.5)
        histogram.observe(2.5)
        histogram.observe(3.0)

        assert histogram.get_sum() == 7.0

    def test_histogram_count(self):
        """Test histogram tracks count correctly."""
        from core.metrics import Histogram

        histogram = Histogram(name="test", help="Test", buckets=(1.0, 5.0))

        histogram.observe(1.5)
        histogram.observe(2.5)
        histogram.observe(3.0)

        assert histogram.get_count() == 3

    def test_histogram_bucket_cumulative(self):
        """Test histogram buckets are cumulative."""
        from core.metrics import Histogram

        histogram = Histogram(
            name="test",
            help="Test",
            buckets=(0.1, 0.5, 1.0)
        )

        # All values fit in all buckets
        histogram.observe(0.05)  # <= all buckets

        buckets = histogram.get_buckets()

        assert buckets[0.1] == 1
        assert buckets[0.5] == 1
        assert buckets[1.0] == 1
        assert buckets[float('inf')] == 1

    def test_histogram_thread_safety(self):
        """Test histogram is thread-safe."""
        from core.metrics import Histogram

        histogram = Histogram(name="thread_test", help="Test", buckets=(1.0, 5.0, 10.0))

        def observe_many():
            for _ in range(100):
                histogram.observe(1.0)

        threads = [threading.Thread(target=observe_many) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert histogram.get_count() == 1000
        assert histogram.get_sum() == 1000.0


# =============================================================================
# SECTION 4: METRICS REGISTRY TESTS
# =============================================================================

class TestMetricsRegistry:
    """Tests for MetricsRegistry."""

    def test_registry_initialization(self, fresh_registry):
        """Test registry initializes correctly."""
        assert fresh_registry._metrics == {}

    def test_registry_creates_counter(self, fresh_registry):
        """Test registry creates counters."""
        counter = fresh_registry.counter("test_counter", "A test counter")

        assert counter is not None
        assert counter.name == "test_counter"

    def test_registry_creates_gauge(self, fresh_registry):
        """Test registry creates gauges."""
        gauge = fresh_registry.gauge("test_gauge", "A test gauge")

        assert gauge is not None
        assert gauge.name == "test_gauge"

    def test_registry_creates_histogram(self, fresh_registry):
        """Test registry creates histograms."""
        histogram = fresh_registry.histogram("test_histogram", "A test histogram")

        assert histogram is not None
        assert histogram.name == "test_histogram"

    def test_registry_returns_same_metric(self, fresh_registry):
        """Test registry returns same metric on duplicate registration."""
        counter1 = fresh_registry.counter("same_counter", "Test")
        counter2 = fresh_registry.counter("same_counter", "Test")

        assert counter1 is counter2

    def test_registry_different_metrics_same_name(self, fresh_registry):
        """Test registry handles different label combinations."""
        counter1 = fresh_registry.counter("http_requests", "Test", {"method": "GET"})
        counter2 = fresh_registry.counter("http_requests", "Test", {"method": "POST"})

        assert counter1 is not counter2

    def test_registry_make_key_no_labels(self, fresh_registry):
        """Test key generation without labels."""
        key = fresh_registry._make_key("test_metric", None)
        assert key == "test_metric"

    def test_registry_make_key_with_labels(self, fresh_registry):
        """Test key generation with labels."""
        labels = {"method": "GET", "status": "200"}
        key = fresh_registry._make_key("http_requests", labels)

        # Labels should be sorted
        assert key == "http_requests{method=GET,status=200}"

    def test_registry_histogram_custom_buckets(self, fresh_registry):
        """Test registry creates histogram with custom buckets."""
        custom_buckets = (0.1, 1.0, 10.0)
        histogram = fresh_registry.histogram(
            "latency",
            "Request latency",
            buckets=custom_buckets
        )

        assert histogram.buckets == custom_buckets

    def test_registry_histogram_default_buckets(self, fresh_registry):
        """Test registry uses default buckets when not specified."""
        from core.metrics import Histogram

        histogram = fresh_registry.histogram("default_buckets", "Test")

        # Should use class default
        assert histogram.buckets == Histogram.buckets


# =============================================================================
# SECTION 5: PROMETHEUS EXPORT TESTS
# =============================================================================

class TestPrometheusExport:
    """Tests for Prometheus format export."""

    def test_export_empty_registry(self, fresh_registry):
        """Test exporting empty registry."""
        output = fresh_registry.export_prometheus()
        assert output == ""

    def test_export_counter(self, fresh_registry):
        """Test exporting counter in Prometheus format."""
        counter = fresh_registry.counter("test_counter", "A test counter")
        counter.inc(5)

        output = fresh_registry.export_prometheus()

        assert "# HELP test_counter A test counter" in output
        assert "# TYPE test_counter counter" in output
        assert "test_counter 5" in output

    def test_export_gauge(self, fresh_registry):
        """Test exporting gauge in Prometheus format."""
        gauge = fresh_registry.gauge("test_gauge", "A test gauge")
        gauge.set(42.5)

        output = fresh_registry.export_prometheus()

        assert "# HELP test_gauge A test gauge" in output
        assert "# TYPE test_gauge gauge" in output
        assert "test_gauge 42.5" in output

    def test_export_histogram(self, fresh_registry):
        """Test exporting histogram in Prometheus format."""
        histogram = fresh_registry.histogram(
            "test_histogram",
            "A test histogram",
            buckets=(0.1, 1.0)
        )
        histogram.observe(0.5)
        histogram.observe(0.8)

        output = fresh_registry.export_prometheus()

        assert "# HELP test_histogram A test histogram" in output
        assert "# TYPE test_histogram histogram" in output
        assert "test_histogram_bucket" in output
        assert "test_histogram_sum" in output
        assert "test_histogram_count" in output

    def test_export_counter_with_labels(self, fresh_registry):
        """Test exporting counter with labels."""
        counter = fresh_registry.counter(
            "http_requests",
            "HTTP requests",
            {"method": "GET", "status": "200"}
        )
        counter.inc(10)

        output = fresh_registry.export_prometheus()

        assert 'method="GET"' in output
        assert 'status="200"' in output

    def test_export_multiple_metrics_same_name(self, fresh_registry):
        """Test exporting multiple metrics with same name but different labels."""
        counter_get = fresh_registry.counter("requests", "Requests", {"method": "GET"})
        counter_post = fresh_registry.counter("requests", "Requests", {"method": "POST"})

        counter_get.inc(100)
        counter_post.inc(50)

        output = fresh_registry.export_prometheus()

        # HELP and TYPE should appear only once
        assert output.count("# HELP requests") == 1
        assert output.count("# TYPE requests") == 1

        # Both values should be present
        assert 'method="GET"' in output
        assert 'method="POST"' in output

    def test_export_histogram_buckets_format(self, fresh_registry):
        """Test histogram bucket export format."""
        histogram = fresh_registry.histogram(
            "latency",
            "Latency",
            buckets=(0.1, 1.0),
            labels={"endpoint": "/api"}
        )
        histogram.observe(0.5)

        output = fresh_registry.export_prometheus()

        # Check bucket format with le label
        assert 'le="0.1"' in output
        assert 'le="1.0"' in output
        assert 'le="inf"' in output


# =============================================================================
# SECTION 6: DECORATOR TESTS
# =============================================================================

class TestTrackTimeDecorator:
    """Tests for track_time decorator."""

    def test_track_time_sync_function(self, reset_global_registry):
        """Test track_time with synchronous function."""
        from core.metrics import track_time, get_registry

        @track_time("test_duration")
        def slow_function():
            time.sleep(0.01)
            return "done"

        result = slow_function()

        assert result == "done"

        # Check histogram was created
        histogram = get_registry()._metrics.get("test_duration")
        assert histogram is not None
        assert histogram.get_count() == 1
        assert histogram.get_sum() >= 0.01

    @pytest.mark.asyncio
    async def test_track_time_async_function(self, reset_global_registry):
        """Test track_time with asynchronous function."""
        from core.metrics import track_time, get_registry

        @track_time("async_duration")
        async def async_slow_function():
            await asyncio.sleep(0.01)
            return "async done"

        result = await async_slow_function()

        assert result == "async done"

        histogram = get_registry()._metrics.get("async_duration")
        assert histogram is not None
        assert histogram.get_count() == 1

    def test_track_time_preserves_exception(self, reset_global_registry):
        """Test track_time still records time on exception."""
        from core.metrics import track_time, get_registry

        @track_time("error_duration")
        def failing_function():
            time.sleep(0.01)
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            failing_function()

        # Should still have recorded the duration
        histogram = get_registry()._metrics.get("error_duration")
        assert histogram is not None
        assert histogram.get_count() == 1

    def test_track_time_multiple_calls(self, reset_global_registry):
        """Test track_time with multiple function calls."""
        from core.metrics import track_time, get_registry

        @track_time("multi_call_duration")
        def quick_function():
            return "quick"

        for _ in range(5):
            quick_function()

        histogram = get_registry()._metrics.get("multi_call_duration")
        assert histogram.get_count() == 5


class TestCountCallsDecorator:
    """Tests for count_calls decorator."""

    def test_count_calls_sync_function(self, reset_global_registry):
        """Test count_calls with synchronous function."""
        from core.metrics import count_calls, get_registry

        @count_calls("test_calls")
        def simple_function():
            return "called"

        for _ in range(3):
            result = simple_function()
            assert result == "called"

        counter = get_registry()._metrics.get("test_calls")
        assert counter is not None
        assert counter.get() == 3

    @pytest.mark.asyncio
    async def test_count_calls_async_function(self, reset_global_registry):
        """Test count_calls with asynchronous function."""
        from core.metrics import count_calls, get_registry

        @count_calls("async_calls")
        async def async_function():
            return "async called"

        for _ in range(5):
            result = await async_function()
            assert result == "async called"

        counter = get_registry()._metrics.get("async_calls")
        assert counter is not None
        assert counter.get() == 5

    def test_count_calls_preserves_function_metadata(self, reset_global_registry):
        """Test count_calls preserves function name and docstring."""
        from core.metrics import count_calls

        @count_calls("metadata_test")
        def documented_function():
            """This function has documentation."""
            return "documented"

        assert documented_function.__name__ == "documented_function"
        assert "documentation" in documented_function.__doc__


# =============================================================================
# SECTION 7: GLOBAL REGISTRY TESTS
# =============================================================================

class TestGlobalRegistry:
    """Tests for global registry functions."""

    def test_get_registry_returns_singleton(self, reset_global_registry):
        """Test get_registry returns the same instance."""
        from core.metrics import get_registry

        registry1 = get_registry()
        registry2 = get_registry()

        assert registry1 is registry2

    def test_get_registry_creates_on_first_call(self, reset_global_registry):
        """Test get_registry creates registry on first call."""
        import core.metrics as metrics_module

        assert metrics_module._registry is None

        registry = metrics_module.get_registry()

        assert registry is not None
        assert metrics_module._registry is registry


# =============================================================================
# SECTION 8: PREDEFINED METRICS TESTS
# =============================================================================

class TestPredefinedMetrics:
    """Tests for predefined metrics."""

    def test_get_metrics_returns_dict(self, reset_global_registry):
        """Test get_metrics returns a dictionary."""
        from core.metrics import get_metrics

        metrics = get_metrics()

        assert isinstance(metrics, dict)
        assert len(metrics) > 0

    def test_predefined_trading_metrics(self, reset_global_registry):
        """Test trading metrics are predefined."""
        from core.metrics import get_metrics

        metrics = get_metrics()

        assert 'trades_total' in metrics
        assert 'trades_success' in metrics
        assert 'trades_failed' in metrics
        assert 'trade_amount_sol' in metrics
        assert 'trade_latency' in metrics

    def test_predefined_treasury_metrics(self, reset_global_registry):
        """Test treasury metrics are predefined."""
        from core.metrics import get_metrics

        metrics = get_metrics()

        assert 'treasury_balance_sol' in metrics
        assert 'treasury_balance_usd' in metrics
        assert 'treasury_positions' in metrics
        assert 'treasury_daily_pnl' in metrics

    def test_predefined_api_metrics(self, reset_global_registry):
        """Test API metrics are predefined."""
        from core.metrics import get_metrics

        metrics = get_metrics()

        assert 'api_requests' in metrics
        assert 'api_errors' in metrics
        assert 'api_latency' in metrics

    def test_predefined_twitter_metrics(self, reset_global_registry):
        """Test Twitter metrics are predefined."""
        from core.metrics import get_metrics

        metrics = get_metrics()

        assert 'tweets_posted' in metrics
        assert 'tweets_failed' in metrics
        assert 'twitter_rate_limits' in metrics

    def test_predefined_system_metrics(self, reset_global_registry):
        """Test system metrics are predefined."""
        from core.metrics import get_metrics

        metrics = get_metrics()

        assert 'uptime_seconds' in metrics
        assert 'memory_usage_bytes' in metrics
        assert 'active_websockets' in metrics

    def test_get_metrics_singleton(self, reset_global_registry):
        """Test get_metrics returns same instance."""
        from core.metrics import get_metrics

        metrics1 = get_metrics()
        metrics2 = get_metrics()

        assert metrics1 is metrics2

    def test_predefined_metrics_are_usable(self, reset_global_registry):
        """Test predefined metrics can be used."""
        from core.metrics import get_metrics

        metrics = get_metrics()

        # Use a counter
        metrics['trades_total'].inc()
        assert metrics['trades_total'].get() == 1

        # Use a gauge
        metrics['treasury_balance_sol'].set(100.0)
        assert metrics['treasury_balance_sol'].get() == 100.0

        # Use a histogram
        metrics['trade_latency'].observe(0.5)
        assert metrics['trade_latency'].get_count() == 1


# =============================================================================
# SECTION 9: AIOHTTP INTEGRATION TESTS
# =============================================================================

class TestAiohttpIntegration:
    """Tests for aiohttp integration."""

    @pytest.mark.asyncio
    async def test_metrics_handler(self, reset_global_registry):
        """Test metrics HTTP handler."""
        from core.metrics import metrics_handler, get_metrics, get_registry
        from aiohttp import web

        # Setup some metrics
        metrics = get_metrics()
        metrics['trades_total'].inc(5)

        # Mock request
        mock_request = MagicMock()

        # Call the handler
        response = await metrics_handler(mock_request)

        # Verify response is a web.Response
        assert isinstance(response, web.Response)
        assert response.content_type == 'text/plain'
        assert 'jarvis_trades_total' in response.text

    def test_setup_metrics_endpoint(self, reset_global_registry):
        """Test setting up metrics endpoint on aiohttp app."""
        from core.metrics import setup_metrics_endpoint

        mock_app = MagicMock()
        mock_router = MagicMock()
        mock_app.router = mock_router

        setup_metrics_endpoint(mock_app, "/metrics")

        mock_router.add_get.assert_called_once()
        call_args = mock_router.add_get.call_args[0]
        assert call_args[0] == "/metrics"

    def test_setup_metrics_custom_path(self, reset_global_registry):
        """Test setting up metrics endpoint with custom path."""
        from core.metrics import setup_metrics_endpoint

        mock_app = MagicMock()
        mock_router = MagicMock()
        mock_app.router = mock_router

        setup_metrics_endpoint(mock_app, "/custom/metrics")

        call_args = mock_router.add_get.call_args[0]
        assert call_args[0] == "/custom/metrics"


# =============================================================================
# SECTION 10: FASTAPI INTEGRATION TESTS
# =============================================================================

class TestFastAPIIntegration:
    """Tests for FastAPI integration."""

    def test_get_fastapi_metrics_router(self, reset_global_registry):
        """Test getting FastAPI router for metrics."""
        with patch('fastapi.APIRouter') as mock_router_class:
            mock_router = MagicMock()
            mock_router_class.return_value = mock_router

            with patch('fastapi.responses.PlainTextResponse'):
                from core.metrics import get_fastapi_metrics_router

                router = get_fastapi_metrics_router()

                # The function imports and creates a router
                assert router is not None


# =============================================================================
# SECTION 11: EDGE CASES AND ERROR HANDLING
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_counter_large_increment(self):
        """Test counter handles large increments."""
        from core.metrics import Counter

        counter = Counter(name="large", help="Test")

        counter.inc(1_000_000_000)
        assert counter.get() == 1_000_000_000.0

    def test_gauge_rapid_changes(self):
        """Test gauge handles rapid value changes."""
        from core.metrics import Gauge

        gauge = Gauge(name="rapid", help="Test")

        for i in range(1000):
            gauge.set(float(i))

        assert gauge.get() == 999.0

    def test_histogram_zero_observation(self):
        """Test histogram handles zero observation."""
        from core.metrics import Histogram

        histogram = Histogram(name="zero", help="Test", buckets=(0.1, 1.0))

        histogram.observe(0.0)

        buckets = histogram.get_buckets()
        assert buckets[0.1] == 1

    def test_histogram_negative_observation(self):
        """Test histogram handles negative observation."""
        from core.metrics import Histogram

        histogram = Histogram(name="negative", help="Test", buckets=(0.1, 1.0))

        histogram.observe(-0.5)

        # Negative values don't fit in any bucket except +Inf
        buckets = histogram.get_buckets()
        assert buckets[float('inf')] == 1
        assert histogram.get_sum() == -0.5

    def test_registry_empty_labels(self, fresh_registry):
        """Test registry handles empty labels dict."""
        counter = fresh_registry.counter("test", "Test", {})

        assert counter.labels == {}

    def test_registry_special_characters_in_help(self, fresh_registry):
        """Test registry handles special characters in help text."""
        counter = fresh_registry.counter(
            "special",
            "Help with \"quotes\" and newlines\n"
        )

        assert counter.help == "Help with \"quotes\" and newlines\n"


# =============================================================================
# SECTION 12: CONCURRENT ACCESS STRESS TESTS
# =============================================================================

class TestConcurrentAccess:
    """Stress tests for concurrent access."""

    def test_registry_concurrent_metric_creation(self, fresh_registry):
        """Test concurrent metric creation in registry."""
        results = []

        def create_counter(name_suffix):
            counter = fresh_registry.counter(f"concurrent_{name_suffix}", "Test")
            counter.inc()
            results.append(counter.get())

        threads = [
            threading.Thread(target=create_counter, args=(i,))
            for i in range(50)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 50
        assert all(r == 1.0 for r in results)

    def test_export_during_updates(self, fresh_registry):
        """Test Prometheus export during concurrent updates."""
        counter = fresh_registry.counter("export_test", "Test")

        errors = []

        def update_counter():
            for _ in range(100):
                counter.inc()

        def export_metrics():
            for _ in range(100):
                try:
                    output = fresh_registry.export_prometheus()
                    assert "export_test" in output
                except Exception as e:
                    errors.append(e)

        update_thread = threading.Thread(target=update_counter)
        export_thread = threading.Thread(target=export_metrics)

        update_thread.start()
        export_thread.start()

        update_thread.join()
        export_thread.join()

        assert len(errors) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
