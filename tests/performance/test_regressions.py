"""
JARVIS Performance Regression Detection

Establishes baselines and detects performance regressions.

Features:
- Baseline establishment
- Comparison against baseline
- Regression alerts (>10% degradation)
- Performance history tracking

Usage:
    pytest tests/performance/test_regressions.py -v
    pytest tests/performance/test_regressions.py --update-baseline
"""

import asyncio
import json
import os
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import pytest


@dataclass
class PerformanceResult:
    """Result of a performance measurement."""
    name: str
    response_times: List[float]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def mean(self) -> float:
        return statistics.mean(self.response_times) if self.response_times else 0

    @property
    def median(self) -> float:
        return statistics.median(self.response_times) if self.response_times else 0

    @property
    def p95(self) -> float:
        if not self.response_times:
            return 0
        sorted_times = sorted(self.response_times)
        idx = int(len(sorted_times) * 0.95)
        return sorted_times[min(idx, len(sorted_times) - 1)]

    @property
    def p99(self) -> float:
        if not self.response_times:
            return 0
        sorted_times = sorted(self.response_times)
        idx = int(len(sorted_times) * 0.99)
        return sorted_times[min(idx, len(sorted_times) - 1)]

    @property
    def min(self) -> float:
        return min(self.response_times) if self.response_times else 0

    @property
    def max(self) -> float:
        return max(self.response_times) if self.response_times else 0

    @property
    def stddev(self) -> float:
        if len(self.response_times) < 2:
            return 0
        return statistics.stdev(self.response_times)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "timestamp": self.timestamp,
            "samples": len(self.response_times),
            "mean_ms": round(self.mean * 1000, 3),
            "median_ms": round(self.median * 1000, 3),
            "p95_ms": round(self.p95 * 1000, 3),
            "p99_ms": round(self.p99 * 1000, 3),
            "min_ms": round(self.min * 1000, 3),
            "max_ms": round(self.max * 1000, 3),
            "stddev_ms": round(self.stddev * 1000, 3),
        }


@dataclass
class RegressionResult:
    """Result of a regression check."""
    test_name: str
    metric: str
    baseline_value: float
    current_value: float
    change_pct: float
    is_regression: bool
    threshold_pct: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_name": self.test_name,
            "metric": self.metric,
            "baseline_ms": round(self.baseline_value * 1000, 3),
            "current_ms": round(self.current_value * 1000, 3),
            "change_pct": round(self.change_pct, 2),
            "is_regression": self.is_regression,
            "threshold_pct": self.threshold_pct,
        }


class PerformanceBaseline:
    """Manages performance baselines and regression detection."""

    BASELINE_FILE = Path(__file__).parent / ".performance_baselines.json"
    HISTORY_FILE = Path(__file__).parent / ".performance_history.json"

    def __init__(self, regression_threshold_pct: float = 10.0):
        self.regression_threshold_pct = regression_threshold_pct
        self.baselines: Dict[str, Dict[str, float]] = {}
        self.history: List[Dict[str, Any]] = []
        self._load()

    def _load(self):
        """Load baselines and history from files."""
        if self.BASELINE_FILE.exists():
            try:
                self.baselines = json.loads(self.BASELINE_FILE.read_text())
            except Exception:
                self.baselines = {}

        if self.HISTORY_FILE.exists():
            try:
                self.history = json.loads(self.HISTORY_FILE.read_text())
            except Exception:
                self.history = []

    def _save(self):
        """Save baselines and history to files."""
        self.BASELINE_FILE.write_text(json.dumps(self.baselines, indent=2))
        self.HISTORY_FILE.write_text(json.dumps(self.history[-100:], indent=2))

    def update_baseline(self, result: PerformanceResult):
        """Update baseline for a test."""
        self.baselines[result.name] = {
            "mean": result.mean,
            "median": result.median,
            "p95": result.p95,
            "p99": result.p99,
            "timestamp": result.timestamp,
        }
        self._save()

    def record_result(self, result: PerformanceResult):
        """Record a performance result to history."""
        self.history.append(result.to_dict())
        self._save()

    def get_baseline(self, test_name: str) -> Optional[Dict[str, float]]:
        """Get baseline for a test."""
        return self.baselines.get(test_name)

    def check_regression(
        self,
        result: PerformanceResult,
        metrics: List[str] = None,
    ) -> List[RegressionResult]:
        """
        Check for performance regression against baseline.

        Args:
            result: Current performance result
            metrics: Metrics to check (default: mean, p95)

        Returns:
            List of regression results
        """
        metrics = metrics or ["mean", "p95"]
        baseline = self.get_baseline(result.name)

        if not baseline:
            return []

        results = []
        for metric in metrics:
            baseline_value = baseline.get(metric, 0)
            current_value = getattr(result, metric, 0)

            if baseline_value == 0:
                continue

            change_pct = ((current_value - baseline_value) / baseline_value) * 100
            is_regression = change_pct > self.regression_threshold_pct

            results.append(RegressionResult(
                test_name=result.name,
                metric=metric,
                baseline_value=baseline_value,
                current_value=current_value,
                change_pct=change_pct,
                is_regression=is_regression,
                threshold_pct=self.regression_threshold_pct,
            ))

        return results

    def get_trend(self, test_name: str, metric: str = "mean", last_n: int = 10) -> List[float]:
        """Get performance trend for a test."""
        relevant_history = [
            h for h in self.history
            if h.get("name") == test_name
        ][-last_n:]

        metric_key = f"{metric}_ms"
        return [h.get(metric_key, 0) for h in relevant_history]


class PerformanceBenchmark:
    """Run performance benchmarks."""

    def __init__(self, iterations: int = 100, warmup: int = 5):
        self.iterations = iterations
        self.warmup = warmup

    async def benchmark(
        self,
        name: str,
        func: Callable,
        args: tuple = (),
        kwargs: dict = None,
    ) -> PerformanceResult:
        """
        Run a benchmark.

        Args:
            name: Test name
            func: Function to benchmark
            args: Arguments to pass to function
            kwargs: Keyword arguments to pass to function

        Returns:
            PerformanceResult with timing data
        """
        kwargs = kwargs or {}
        response_times = []

        # Warmup
        for _ in range(self.warmup):
            if asyncio.iscoroutinefunction(func):
                await func(*args, **kwargs)
            else:
                func(*args, **kwargs)

        # Actual benchmark
        for _ in range(self.iterations):
            start = time.perf_counter()
            if asyncio.iscoroutinefunction(func):
                await func(*args, **kwargs)
            else:
                func(*args, **kwargs)
            elapsed = time.perf_counter() - start
            response_times.append(elapsed)

        return PerformanceResult(name=name, response_times=response_times)


# =============================================================================
# Mock Functions for Benchmarking
# =============================================================================

async def mock_token_analysis(token: str) -> Dict[str, Any]:
    """Mock token analysis function."""
    await asyncio.sleep(0.01)  # 10ms simulated work
    return {
        "token": token,
        "score": 85,
        "grade": "B+",
    }


async def mock_trade_execution(amount: float) -> Dict[str, Any]:
    """Mock trade execution function."""
    await asyncio.sleep(0.02)  # 20ms simulated work
    return {
        "id": "trade_123",
        "amount": amount,
        "status": "filled",
    }


def mock_price_calculation(values: List[float]) -> float:
    """Mock price calculation (sync)."""
    time.sleep(0.001)  # 1ms simulated work
    return sum(values) / len(values) if values else 0


async def mock_api_call() -> Dict[str, Any]:
    """Mock API call."""
    await asyncio.sleep(0.015)  # 15ms simulated work
    return {"status": "ok"}


# =============================================================================
# Performance Regression Test Scenarios
# =============================================================================

class TestPerformanceRegressions:
    """Performance regression test scenarios."""

    @pytest.fixture
    def baseline(self, tmp_path):
        """Create baseline manager with temp files."""
        manager = PerformanceBaseline(regression_threshold_pct=10.0)
        manager.BASELINE_FILE = tmp_path / "baselines.json"
        manager.HISTORY_FILE = tmp_path / "history.json"
        return manager

    @pytest.fixture
    def benchmark(self):
        return PerformanceBenchmark(iterations=50, warmup=5)

    @pytest.mark.asyncio
    async def test_establish_baseline(
        self,
        baseline: PerformanceBaseline,
        benchmark: PerformanceBenchmark
    ):
        """Establish a performance baseline."""
        result = await benchmark.benchmark(
            "token_analysis",
            mock_token_analysis,
            args=("TEST_TOKEN",),
        )

        baseline.update_baseline(result)
        baseline.record_result(result)

        print(f"\n[Baseline Established]")
        print(f"  Test: {result.name}")
        print(f"  Mean: {result.mean * 1000:.3f}ms")
        print(f"  p95: {result.p95 * 1000:.3f}ms")
        print(f"  Samples: {len(result.response_times)}")

        # Verify baseline was saved
        saved = baseline.get_baseline("token_analysis")
        assert saved is not None
        assert saved["mean"] > 0

    @pytest.mark.asyncio
    async def test_no_regression_detected(
        self,
        baseline: PerformanceBaseline,
        benchmark: PerformanceBenchmark
    ):
        """Test when performance is within acceptable range."""
        # Establish baseline
        result1 = await benchmark.benchmark(
            "api_call",
            mock_api_call,
        )
        baseline.update_baseline(result1)

        # Run again with similar performance
        result2 = await benchmark.benchmark(
            "api_call",
            mock_api_call,
        )

        regressions = baseline.check_regression(result2)

        print(f"\n[No Regression Test]")
        print(f"  Baseline mean: {result1.mean * 1000:.3f}ms")
        print(f"  Current mean: {result2.mean * 1000:.3f}ms")

        for r in regressions:
            print(f"  {r.metric}: {r.change_pct:+.2f}% (regression={r.is_regression})")

        # Should not detect regression (same function)
        has_regression = any(r.is_regression for r in regressions)
        assert not has_regression, "False regression detected"

    @pytest.mark.asyncio
    async def test_regression_detected(
        self,
        baseline: PerformanceBaseline,
        benchmark: PerformanceBenchmark
    ):
        """Test detection of actual performance regression."""
        # Establish baseline with fast function
        result1 = await benchmark.benchmark(
            "fast_operation",
            mock_api_call,
        )
        baseline.update_baseline(result1)

        # Simulate slower function (regression)
        async def slow_api_call():
            await asyncio.sleep(0.025)  # 25ms instead of 15ms (66% slower)
            return {"status": "ok"}

        result2 = await benchmark.benchmark(
            "fast_operation",
            slow_api_call,
        )

        regressions = baseline.check_regression(result2)

        print(f"\n[Regression Detection Test]")
        print(f"  Baseline mean: {result1.mean * 1000:.3f}ms")
        print(f"  Current mean: {result2.mean * 1000:.3f}ms")

        for r in regressions:
            print(f"  {r.metric}: {r.change_pct:+.2f}% (regression={r.is_regression})")

        # Should detect regression
        has_regression = any(r.is_regression for r in regressions)
        assert has_regression, "Failed to detect regression"

    @pytest.mark.asyncio
    async def test_performance_improvement(
        self,
        baseline: PerformanceBaseline,
        benchmark: PerformanceBenchmark
    ):
        """Test detection of performance improvement."""
        # Establish baseline with slower function
        async def slow_operation():
            await asyncio.sleep(0.02)
            return {"status": "ok"}

        result1 = await benchmark.benchmark(
            "improving_operation",
            slow_operation,
        )
        baseline.update_baseline(result1)

        # Faster implementation
        async def fast_operation():
            await asyncio.sleep(0.01)
            return {"status": "ok"}

        result2 = await benchmark.benchmark(
            "improving_operation",
            fast_operation,
        )

        regressions = baseline.check_regression(result2)

        print(f"\n[Performance Improvement Test]")
        print(f"  Baseline mean: {result1.mean * 1000:.3f}ms")
        print(f"  Current mean: {result2.mean * 1000:.3f}ms")

        for r in regressions:
            print(f"  {r.metric}: {r.change_pct:+.2f}% (improvement)")

        # Should not be flagged as regression (it's faster)
        has_regression = any(r.is_regression for r in regressions)
        assert not has_regression, "Improvement incorrectly flagged as regression"

    @pytest.mark.asyncio
    async def test_history_tracking(
        self,
        baseline: PerformanceBaseline,
        benchmark: PerformanceBenchmark
    ):
        """Test performance history tracking."""
        # Run multiple benchmarks
        for i in range(5):
            result = await benchmark.benchmark(
                "tracked_operation",
                mock_token_analysis,
                args=(f"TOKEN_{i}",),
            )
            baseline.record_result(result)

        # Get trend
        trend = baseline.get_trend("tracked_operation", "mean")

        print(f"\n[History Tracking Test]")
        print(f"  Recorded runs: {len(baseline.history)}")
        print(f"  Trend values: {[f'{t:.3f}ms' for t in trend]}")

        assert len(trend) == 5

    @pytest.mark.asyncio
    async def test_multiple_metrics(
        self,
        baseline: PerformanceBaseline,
        benchmark: PerformanceBenchmark
    ):
        """Test checking multiple metrics for regression."""
        result1 = await benchmark.benchmark(
            "multi_metric",
            mock_trade_execution,
            args=(100.0,),
        )
        baseline.update_baseline(result1)

        result2 = await benchmark.benchmark(
            "multi_metric",
            mock_trade_execution,
            args=(100.0,),
        )

        # Check multiple metrics
        regressions = baseline.check_regression(
            result2,
            metrics=["mean", "median", "p95", "p99"],
        )

        print(f"\n[Multiple Metrics Test]")
        for r in regressions:
            print(f"  {r.metric}: baseline={r.baseline_value*1000:.3f}ms, "
                  f"current={r.current_value*1000:.3f}ms, change={r.change_pct:+.2f}%")

        assert len(regressions) == 4


class TestPerformanceResult:
    """Unit tests for PerformanceResult."""

    def test_statistics_calculation(self):
        """Test that statistics are calculated correctly."""
        result = PerformanceResult(
            name="test",
            response_times=[0.01, 0.02, 0.015, 0.025, 0.01, 0.03, 0.02, 0.015, 0.025, 0.02],
        )

        assert result.mean > 0
        assert result.median > 0
        assert result.p95 > 0
        assert result.p99 > 0
        assert result.min == 0.01
        assert result.max == 0.03
        assert result.stddev > 0

    def test_empty_result(self):
        """Test handling of empty results."""
        result = PerformanceResult(name="empty", response_times=[])

        assert result.mean == 0
        assert result.median == 0
        assert result.p95 == 0

    def test_to_dict(self):
        """Test serialization to dictionary."""
        result = PerformanceResult(
            name="test",
            response_times=[0.01, 0.02],
        )

        data = result.to_dict()

        assert "name" in data
        assert "mean_ms" in data
        assert "p95_ms" in data
        assert data["samples"] == 2


class TestRegressionResult:
    """Unit tests for RegressionResult."""

    def test_regression_detection(self):
        """Test regression detection logic."""
        # Regression case
        result = RegressionResult(
            test_name="test",
            metric="mean",
            baseline_value=0.01,
            current_value=0.015,  # 50% worse
            change_pct=50.0,
            is_regression=True,
            threshold_pct=10.0,
        )

        assert result.is_regression

    def test_to_dict(self):
        """Test serialization."""
        result = RegressionResult(
            test_name="test",
            metric="p95",
            baseline_value=0.01,
            current_value=0.011,
            change_pct=10.0,
            is_regression=False,
            threshold_pct=10.0,
        )

        data = result.to_dict()

        assert data["test_name"] == "test"
        assert data["metric"] == "p95"
        assert not data["is_regression"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
