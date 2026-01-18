"""
Unit tests for the performance profiling and optimization system.

Tests the following components:
- Enhanced profiler with profile_block context manager
- Metrics collector with persistence and aggregation
- Performance baselines and regression detection
- Output formatting (JSON, CSV, human-readable)
"""
import pytest
import asyncio
import tempfile
import json
import time
import os
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock


class TestProfileBlock:
    """Tests for the profile_block context manager."""

    def test_profile_block_measures_execution_time(self):
        """profile_block should measure execution time in milliseconds."""
        from core.performance.profiler import profile_block, get_profiler_results

        with profile_block("test.operation"):
            time.sleep(0.05)  # Sleep for 50ms

        results = get_profiler_results()
        assert "test.operation" in results
        assert results["test.operation"]["duration_ms"] >= 45  # Allow some tolerance
        assert results["test.operation"]["duration_ms"] < 100

    def test_profile_block_measures_memory(self):
        """profile_block should optionally track memory usage."""
        from core.performance.profiler import profile_block, get_profiler_results

        with profile_block("test.memory_op", track_memory=True):
            # Allocate some memory
            data = [i for i in range(100000)]

        results = get_profiler_results()
        assert "test.memory_op" in results
        assert results["test.memory_op"]["memory_mb"] >= 0

    def test_profile_block_counts_calls(self):
        """profile_block should track number of calls."""
        from core.performance.profiler import profile_block, get_profiler_results, reset_profiler

        reset_profiler()

        for _ in range(5):
            with profile_block("test.repeated"):
                pass

        results = get_profiler_results()
        assert results["test.repeated"]["call_count"] == 5

    def test_profile_block_tracks_exceptions(self):
        """profile_block should count exceptions without swallowing them."""
        from core.performance.profiler import profile_block, get_profiler_results, reset_profiler

        reset_profiler()

        with pytest.raises(ValueError):
            with profile_block("test.error"):
                raise ValueError("test error")

        results = get_profiler_results()
        assert results["test.error"]["exception_count"] == 1

    def test_profile_block_nested_blocks(self):
        """profile_block should support nested profiling."""
        from core.performance.profiler import profile_block, get_profiler_results, reset_profiler

        reset_profiler()

        with profile_block("test.outer"):
            time.sleep(0.01)
            with profile_block("test.inner"):
                time.sleep(0.01)

        results = get_profiler_results()
        assert "test.outer" in results
        assert "test.inner" in results
        # Outer should be >= inner
        assert results["test.outer"]["duration_ms"] >= results["test.inner"]["duration_ms"]


class TestProfilePerformanceDecorator:
    """Tests for the @profile_performance decorator."""

    def test_profile_performance_sync_function(self):
        """@profile_performance should work with sync functions."""
        from core.performance.profiler import profile_performance, get_profiler_results, reset_profiler

        reset_profiler()

        @profile_performance
        def sync_operation():
            time.sleep(0.02)
            return "done"

        result = sync_operation()
        assert result == "done"

        results = get_profiler_results()
        assert "sync_operation" in results
        assert results["sync_operation"]["duration_ms"] >= 15

    @pytest.mark.asyncio
    async def test_profile_performance_async_function(self):
        """@profile_performance should work with async functions."""
        from core.performance.profiler import profile_performance, get_profiler_results, reset_profiler

        reset_profiler()

        @profile_performance
        async def async_operation():
            await asyncio.sleep(0.02)
            return "async done"

        result = await async_operation()
        assert result == "async done"

        results = get_profiler_results()
        assert "async_operation" in results
        assert results["async_operation"]["duration_ms"] >= 15

    def test_profile_performance_custom_name(self):
        """@profile_performance should accept a custom name."""
        from core.performance.profiler import profile_performance, get_profiler_results, reset_profiler

        reset_profiler()

        @profile_performance(name="custom.operation.name")
        def named_operation():
            return True

        named_operation()

        results = get_profiler_results()
        assert "custom.operation.name" in results


class TestMetricsCollector:
    """Tests for the metrics collector."""

    def test_record_api_latency(self):
        """Metrics collector should record API call latencies."""
        from core.performance.metrics_collector import MetricsCollector

        collector = MetricsCollector()

        collector.record_api_latency("jupiter.quote", 125.5)
        collector.record_api_latency("jupiter.quote", 130.2)
        collector.record_api_latency("jupiter.swap", 200.1)

        stats = collector.get_api_stats("jupiter.quote")
        assert stats["count"] == 2
        assert stats["avg_ms"] > 120
        assert stats["avg_ms"] < 135

    def test_record_query_time(self):
        """Metrics collector should record database query times."""
        from core.performance.metrics_collector import MetricsCollector

        collector = MetricsCollector()

        collector.record_query_time("SELECT * FROM positions", 15.3)
        collector.record_query_time("SELECT * FROM positions", 18.7)

        stats = collector.get_query_stats("SELECT * FROM positions")
        assert stats["count"] == 2

    def test_compute_percentiles(self):
        """Metrics collector should compute P50, P95, P99 latencies."""
        from core.performance.metrics_collector import MetricsCollector

        collector = MetricsCollector()

        # Add 100 samples with known distribution
        for i in range(100):
            collector.record_api_latency("test.endpoint", float(i))

        stats = collector.get_api_stats("test.endpoint")
        assert "p50_ms" in stats
        assert "p95_ms" in stats
        assert "p99_ms" in stats

        assert stats["p50_ms"] >= 49 and stats["p50_ms"] <= 50
        assert stats["p95_ms"] >= 94 and stats["p95_ms"] <= 95
        assert stats["p99_ms"] >= 98 and stats["p99_ms"] <= 99

    def test_persistence_jsonl(self):
        """Metrics collector should persist to JSONL format."""
        from core.performance.metrics_collector import MetricsCollector

        with tempfile.TemporaryDirectory() as tmpdir:
            metrics_file = Path(tmpdir) / "metrics.jsonl"
            collector = MetricsCollector(metrics_path=str(metrics_file))

            collector.record_api_latency("test.api", 50.0)
            collector.flush()

            assert metrics_file.exists()
            with open(metrics_file) as f:
                line = f.readline()
                data = json.loads(line)
                assert data["endpoint"] == "test.api"
                assert data["latency_ms"] == 50.0

    def test_retention_policy(self):
        """Metrics collector should enforce 7-day retention."""
        from core.performance.metrics_collector import MetricsCollector

        with tempfile.TemporaryDirectory() as tmpdir:
            metrics_file = Path(tmpdir) / "metrics.jsonl"
            collector = MetricsCollector(
                metrics_path=str(metrics_file),
                retention_days=7
            )

            # Create an old entry (8 days ago)
            old_timestamp = datetime.now() - timedelta(days=8)

            # Write old and new entries
            with open(metrics_file, "w") as f:
                f.write(json.dumps({
                    "timestamp": old_timestamp.isoformat(),
                    "endpoint": "old.api",
                    "latency_ms": 100.0
                }) + "\n")
                f.write(json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "endpoint": "new.api",
                    "latency_ms": 50.0
                }) + "\n")

            # Trigger cleanup
            collector.cleanup_old_metrics()

            # Read back and verify
            with open(metrics_file) as f:
                lines = f.readlines()

            assert len(lines) == 1
            data = json.loads(lines[0])
            assert data["endpoint"] == "new.api"


class TestOutputFormats:
    """Tests for output format generation."""

    def test_json_output(self):
        """Should generate valid JSON output."""
        from core.performance.profiler import profile_block, export_results_json, reset_profiler

        reset_profiler()

        with profile_block("test.json"):
            pass

        output = export_results_json()
        data = json.loads(output)

        assert "test.json" in data
        assert "duration_ms" in data["test.json"]

    def test_csv_output(self):
        """Should generate valid CSV output."""
        from core.performance.profiler import profile_block, export_results_csv, reset_profiler

        reset_profiler()

        with profile_block("test.csv"):
            pass

        output = export_results_csv()
        lines = output.strip().split("\n")

        assert len(lines) >= 2  # Header + at least one data row
        assert "name" in lines[0].lower()
        assert "duration" in lines[0].lower()

    def test_table_output(self):
        """Should generate human-readable table output."""
        from core.performance.profiler import profile_block, export_results_table, reset_profiler

        reset_profiler()

        with profile_block("test.table.operation"):
            pass

        output = export_results_table()

        assert "test.table.operation" in output
        assert "ms" in output.lower() or "time" in output.lower()


class TestPerformanceBaselines:
    """Tests for performance baseline management."""

    def test_load_baselines(self):
        """Should load baselines from JSON config."""
        from core.performance.metrics_collector import PerformanceBaselines

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "baselines.json"
            with open(config_path, 'w') as f:
                json.dump({
                    "signal_detection": {"target_ms": 50},
                    "position_sizing": {"target_ms": 10},
                    "risk_checks": {"target_ms": 5}
                }, f)

            baselines = PerformanceBaselines(str(config_path))

            assert baselines.get_target("signal_detection") == 50
            assert baselines.get_target("position_sizing") == 10

    def test_check_regression(self):
        """Should detect performance regressions (>10% slower)."""
        from core.performance.metrics_collector import PerformanceBaselines

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "baselines.json"
            with open(config_path, 'w') as f:
                json.dump({
                    "test_operation": {"target_ms": 100}
                }, f)

            baselines = PerformanceBaselines(str(config_path))

            # 10% slower = 110ms, should be borderline
            assert not baselines.is_regression("test_operation", 109)
            # 15% slower = 115ms, should be regression
            assert baselines.is_regression("test_operation", 115)
            # Faster is always OK
            assert not baselines.is_regression("test_operation", 80)

    def test_save_new_baseline(self):
        """Should be able to save new baselines."""
        from core.performance.metrics_collector import PerformanceBaselines

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "baselines.json"
            with open(config_path, 'w') as f:
                json.dump({}, f)

            baselines = PerformanceBaselines(str(config_path))
            baselines.set_target("new_operation", 75)
            baselines.save()

            # Reload and verify
            baselines2 = PerformanceBaselines(str(config_path))
            assert baselines2.get_target("new_operation") == 75


class TestMemoryLeakDetection:
    """Tests for memory leak detection capabilities."""

    def test_detect_memory_growth(self):
        """Should detect sustained memory growth."""
        from core.performance.profiler import MemoryLeakDetector

        detector = MemoryLeakDetector()

        # Simulate memory readings
        detector.record_sample(100)  # 100 MB
        detector.record_sample(110)  # 110 MB
        detector.record_sample(120)  # 120 MB
        detector.record_sample(130)  # 130 MB
        detector.record_sample(140)  # 140 MB

        result = detector.analyze()
        assert result["has_potential_leak"] == True
        assert result["growth_mb"] == 40

    def test_no_leak_for_stable_memory(self):
        """Should not flag stable memory usage."""
        from core.performance.profiler import MemoryLeakDetector

        detector = MemoryLeakDetector()

        # Simulate stable memory
        detector.record_sample(100)
        detector.record_sample(102)
        detector.record_sample(99)
        detector.record_sample(101)
        detector.record_sample(100)

        result = detector.analyze()
        assert result["has_potential_leak"] == False


class TestIntegrationWithTrading:
    """Tests for integration with trading components."""

    @pytest.mark.asyncio
    async def test_profile_trading_decision_flow(self):
        """Should profile the complete trading decision flow."""
        from core.performance.profiler import profile_block, get_profiler_results, reset_profiler

        reset_profiler()

        async def mock_signal_detection():
            with profile_block("trading.signal_detection"):
                await asyncio.sleep(0.01)
                with profile_block("trading.signal_detection.liquidation"):
                    await asyncio.sleep(0.005)
                with profile_block("trading.signal_detection.ma_analysis"):
                    await asyncio.sleep(0.005)

        async def mock_position_sizing():
            with profile_block("trading.position_sizing"):
                await asyncio.sleep(0.005)

        async def mock_risk_check():
            with profile_block("trading.risk_check"):
                await asyncio.sleep(0.002)

        # Simulate full flow
        await mock_signal_detection()
        await mock_position_sizing()
        await mock_risk_check()

        results = get_profiler_results()

        assert "trading.signal_detection" in results
        assert "trading.position_sizing" in results
        assert "trading.risk_check" in results

        # Verify hierarchical timing
        assert results["trading.signal_detection"]["duration_ms"] >= \
               results["trading.signal_detection.liquidation"]["duration_ms"]


class TestBenchmarkRunner:
    """Tests for the benchmark running capabilities."""

    def test_run_benchmark_function(self):
        """Should run a function multiple times and collect stats."""
        from core.performance.profiler import run_benchmark

        call_count = 0

        def operation():
            nonlocal call_count
            call_count += 1
            time.sleep(0.01)
            return call_count

        stats = run_benchmark(operation, iterations=10, warmup=5)

        # Total calls = iterations + warmup
        assert call_count == 15
        assert stats["iterations"] == 10
        assert stats["avg_ms"] >= 8
        assert stats["min_ms"] >= 8
        assert stats["max_ms"] >= 8
        assert "p50_ms" in stats

    @pytest.mark.asyncio
    async def test_run_async_benchmark(self):
        """Should run an async function multiple times and collect stats."""
        from core.performance.profiler import run_async_benchmark

        call_count = 0

        async def async_operation():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            return call_count

        stats = await run_async_benchmark(async_operation, iterations=5, warmup=5)

        # Total calls = iterations + warmup
        assert call_count == 10
        assert stats["iterations"] == 5
        assert stats["avg_ms"] >= 8


class TestRegressionTests:
    """Tests specifically for regression detection."""

    def test_baseline_comparison_report(self):
        """Should generate a comparison report against baselines."""
        from core.performance.metrics_collector import generate_regression_report

        baselines = {
            "signal_detection": {"target_ms": 50},
            "position_sizing": {"target_ms": 10}
        }

        actual = {
            "signal_detection": {"avg_ms": 45},  # OK - faster
            "position_sizing": {"avg_ms": 15}    # REGRESSION - 50% slower
        }

        report = generate_regression_report(baselines, actual)

        assert "position_sizing" in report["regressions"]
        assert "signal_detection" not in report["regressions"]
        assert report["has_regressions"] == True
