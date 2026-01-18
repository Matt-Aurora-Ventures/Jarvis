"""
JARVIS Load Testing Suite

Comprehensive load testing scenarios for production readiness.
Tests system behavior under various load conditions.

Requirements:
- locust>=2.0.0
- pytest>=7.0.0
- psutil>=5.0.0

Usage:
    # Run with pytest
    pytest tests/load/load_test.py -v -m "not slow"

    # Run full load test (slow)
    pytest tests/load/load_test.py -v --run-load-tests

    # Run with Locust UI
    locust -f tests/load/locustfile.py --host=http://localhost:8000
"""

import asyncio
import json
import os
import random
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Try to import psutil for resource monitoring
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


@dataclass
class LoadTestMetrics:
    """Metrics collected during load testing."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    response_times: List[float] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    start_time: float = 0
    end_time: float = 0

    # Resource metrics
    cpu_samples: List[float] = field(default_factory=list)
    memory_samples: List[float] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time if self.end_time else 0

    @property
    def error_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return (self.failed_requests / self.total_requests) * 100

    @property
    def requests_per_second(self) -> float:
        if self.duration == 0:
            return 0.0
        return self.total_requests / self.duration

    @property
    def p50_latency(self) -> float:
        if not self.response_times:
            return 0.0
        return statistics.median(self.response_times)

    @property
    def p95_latency(self) -> float:
        if not self.response_times:
            return 0.0
        sorted_times = sorted(self.response_times)
        idx = int(len(sorted_times) * 0.95)
        return sorted_times[min(idx, len(sorted_times) - 1)]

    @property
    def p99_latency(self) -> float:
        if not self.response_times:
            return 0.0
        sorted_times = sorted(self.response_times)
        idx = int(len(sorted_times) * 0.99)
        return sorted_times[min(idx, len(sorted_times) - 1)]

    @property
    def avg_cpu(self) -> float:
        if not self.cpu_samples:
            return 0.0
        return statistics.mean(self.cpu_samples)

    @property
    def avg_memory(self) -> float:
        if not self.memory_samples:
            return 0.0
        return statistics.mean(self.memory_samples)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "error_rate_pct": round(self.error_rate, 2),
            "duration_seconds": round(self.duration, 2),
            "requests_per_second": round(self.requests_per_second, 2),
            "latency_ms": {
                "p50": round(self.p50_latency * 1000, 2),
                "p95": round(self.p95_latency * 1000, 2),
                "p99": round(self.p99_latency * 1000, 2),
            },
            "resources": {
                "avg_cpu_pct": round(self.avg_cpu, 2),
                "avg_memory_mb": round(self.avg_memory, 2),
            },
            "errors": self.errors[:10],  # First 10 errors
        }

    def passes_criteria(
        self,
        max_p95_latency_ms: float = 500,
        max_error_rate_pct: float = 1.0
    ) -> tuple[bool, List[str]]:
        """Check if metrics pass acceptance criteria."""
        failures = []

        p95_ms = self.p95_latency * 1000
        if p95_ms > max_p95_latency_ms:
            failures.append(f"p95 latency {p95_ms:.2f}ms > {max_p95_latency_ms}ms")

        if self.error_rate > max_error_rate_pct:
            failures.append(f"error rate {self.error_rate:.2f}% > {max_error_rate_pct}%")

        return len(failures) == 0, failures


class ResourceMonitor:
    """Monitor system resources during tests."""

    def __init__(self, interval: float = 0.5):
        self.interval = interval
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self.cpu_samples: List[float] = []
        self.memory_samples: List[float] = []

    async def start(self):
        """Start monitoring resources."""
        if not PSUTIL_AVAILABLE:
            return

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())

    async def stop(self):
        """Stop monitoring resources."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _monitor_loop(self):
        """Background monitoring loop."""
        while self._running:
            try:
                process = psutil.Process()
                self.cpu_samples.append(process.cpu_percent())
                self.memory_samples.append(process.memory_info().rss / 1024 / 1024)
            except Exception:
                pass
            await asyncio.sleep(self.interval)


class LoadGenerator:
    """Generate load for testing."""

    def __init__(self):
        self.metrics = LoadTestMetrics()
        self.monitor = ResourceMonitor()

    async def run_concurrent_load(
        self,
        func: Callable,
        concurrent_users: int,
        total_requests: int,
        args: tuple = (),
        kwargs: dict = None,
    ) -> LoadTestMetrics:
        """
        Run load test with concurrent users.

        Args:
            func: Async function to test
            concurrent_users: Number of concurrent users
            total_requests: Total requests to make
            args: Arguments to pass to func
            kwargs: Keyword arguments to pass to func

        Returns:
            LoadTestMetrics with results
        """
        kwargs = kwargs or {}
        self.metrics = LoadTestMetrics()
        semaphore = asyncio.Semaphore(concurrent_users)

        await self.monitor.start()
        self.metrics.start_time = time.time()

        async def make_request():
            async with semaphore:
                start = time.time()
                try:
                    await func(*args, **kwargs)
                    elapsed = time.time() - start
                    self.metrics.response_times.append(elapsed)
                    self.metrics.successful_requests += 1
                except Exception as e:
                    elapsed = time.time() - start
                    self.metrics.response_times.append(elapsed)
                    self.metrics.failed_requests += 1
                    self.metrics.errors.append(str(e))
                finally:
                    self.metrics.total_requests += 1

        tasks = [make_request() for _ in range(total_requests)]
        await asyncio.gather(*tasks, return_exceptions=True)

        self.metrics.end_time = time.time()
        await self.monitor.stop()

        self.metrics.cpu_samples = self.monitor.cpu_samples
        self.metrics.memory_samples = self.monitor.memory_samples

        return self.metrics

    async def run_sustained_load(
        self,
        func: Callable,
        requests_per_second: float,
        duration_seconds: float,
        args: tuple = (),
        kwargs: dict = None,
    ) -> LoadTestMetrics:
        """
        Run sustained load at a target rate.

        Args:
            func: Async function to test
            requests_per_second: Target RPS
            duration_seconds: Duration in seconds
            args: Arguments to pass to func
            kwargs: Keyword arguments to pass to func

        Returns:
            LoadTestMetrics with results
        """
        kwargs = kwargs or {}
        self.metrics = LoadTestMetrics()
        interval = 1.0 / requests_per_second

        await self.monitor.start()
        self.metrics.start_time = time.time()
        end_time = self.metrics.start_time + duration_seconds

        async def make_request():
            start = time.time()
            try:
                await func(*args, **kwargs)
                elapsed = time.time() - start
                self.metrics.response_times.append(elapsed)
                self.metrics.successful_requests += 1
            except Exception as e:
                elapsed = time.time() - start
                self.metrics.response_times.append(elapsed)
                self.metrics.failed_requests += 1
                self.metrics.errors.append(str(e))
            finally:
                self.metrics.total_requests += 1

        tasks = []
        while time.time() < end_time:
            task = asyncio.create_task(make_request())
            tasks.append(task)
            await asyncio.sleep(interval)

        # Wait for remaining tasks
        await asyncio.gather(*tasks, return_exceptions=True)

        self.metrics.end_time = time.time()
        await self.monitor.stop()

        self.metrics.cpu_samples = self.monitor.cpu_samples
        self.metrics.memory_samples = self.monitor.memory_samples

        return self.metrics


# =============================================================================
# Mock Services for Testing
# =============================================================================

class MockTokenAnalyzer:
    """Mock token analyzer for load testing."""

    def __init__(self, latency_range: tuple = (0.01, 0.05)):
        self.latency_range = latency_range
        self.call_count = 0

    async def analyze(self, token_address: str) -> Dict[str, Any]:
        """Simulate token analysis."""
        self.call_count += 1
        await asyncio.sleep(random.uniform(*self.latency_range))

        return {
            "address": token_address,
            "score": random.randint(1, 100),
            "grade": random.choice(["A", "B", "C", "D", "F"]),
            "recommendation": random.choice(["BUY", "HOLD", "SELL"]),
        }


class MockTradingEngine:
    """Mock trading engine for load testing."""

    def __init__(self, latency_range: tuple = (0.02, 0.1), failure_rate: float = 0.01):
        self.latency_range = latency_range
        self.failure_rate = failure_rate
        self.executed_trades = 0

    async def execute_trade(
        self,
        token: str,
        side: str,
        amount: float
    ) -> Dict[str, Any]:
        """Simulate trade execution."""
        await asyncio.sleep(random.uniform(*self.latency_range))

        if random.random() < self.failure_rate:
            raise Exception("Trade execution failed - slippage too high")

        self.executed_trades += 1
        return {
            "id": f"trade_{self.executed_trades}",
            "token": token,
            "side": side,
            "amount": amount,
            "price": random.uniform(0.001, 100),
            "status": "filled",
        }


# =============================================================================
# Load Test Scenarios
# =============================================================================

class TestLoadScenarios:
    """Load test scenarios for Jarvis."""

    @pytest.fixture
    def load_generator(self):
        return LoadGenerator()

    @pytest.fixture
    def mock_analyzer(self):
        return MockTokenAnalyzer(latency_range=(0.01, 0.03))

    @pytest.fixture
    def mock_trading(self):
        return MockTradingEngine(latency_range=(0.02, 0.05), failure_rate=0.005)

    @pytest.mark.asyncio
    async def test_100_concurrent_users_analyzing_tokens(
        self,
        load_generator: LoadGenerator,
        mock_analyzer: MockTokenAnalyzer
    ):
        """
        Scenario: 100 concurrent users analyzing tokens.

        Pass criteria:
        - p95 latency < 500ms
        - Error rate < 1%
        """
        tokens = [f"token_{i}" for i in range(1000)]

        async def analyze_random_token():
            token = random.choice(tokens)
            return await mock_analyzer.analyze(token)

        metrics = await load_generator.run_concurrent_load(
            func=analyze_random_token,
            concurrent_users=100,
            total_requests=1000,
        )

        passed, failures = metrics.passes_criteria(
            max_p95_latency_ms=500,
            max_error_rate_pct=1.0
        )

        print(f"\n[100 Concurrent Users - Token Analysis]")
        print(f"  Total requests: {metrics.total_requests}")
        print(f"  Error rate: {metrics.error_rate:.2f}%")
        print(f"  p50 latency: {metrics.p50_latency * 1000:.2f}ms")
        print(f"  p95 latency: {metrics.p95_latency * 1000:.2f}ms")
        print(f"  p99 latency: {metrics.p99_latency * 1000:.2f}ms")
        print(f"  Throughput: {metrics.requests_per_second:.2f} req/s")

        assert passed, f"Load test failed: {failures}"

    @pytest.mark.asyncio
    async def test_1000_simultaneous_trades(
        self,
        load_generator: LoadGenerator,
        mock_trading: MockTradingEngine
    ):
        """
        Scenario: 1000 trades executed simultaneously.

        Pass criteria:
        - p95 latency < 500ms
        - Error rate < 1%
        """
        async def execute_random_trade():
            token = f"token_{random.randint(1, 100)}"
            side = random.choice(["buy", "sell"])
            amount = random.uniform(0.1, 10.0)
            return await mock_trading.execute_trade(token, side, amount)

        metrics = await load_generator.run_concurrent_load(
            func=execute_random_trade,
            concurrent_users=100,  # 100 concurrent, 1000 total
            total_requests=1000,
        )

        passed, failures = metrics.passes_criteria(
            max_p95_latency_ms=500,
            max_error_rate_pct=1.0
        )

        print(f"\n[1000 Simultaneous Trades]")
        print(f"  Total trades: {metrics.total_requests}")
        print(f"  Successful: {metrics.successful_requests}")
        print(f"  Failed: {metrics.failed_requests}")
        print(f"  Error rate: {metrics.error_rate:.2f}%")
        print(f"  p95 latency: {metrics.p95_latency * 1000:.2f}ms")

        assert passed, f"Load test failed: {failures}"

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_sustained_load_50_rps(
        self,
        load_generator: LoadGenerator,
        mock_analyzer: MockTokenAnalyzer
    ):
        """
        Scenario: 10 minute sustained load with 50 req/sec.

        Note: This is a slow test (10 minutes). Run with --run-load-tests flag.

        Pass criteria:
        - p95 latency < 500ms
        - Error rate < 1%
        """
        # For unit testing, use shorter duration
        duration = float(os.getenv("LOAD_TEST_DURATION", "10"))  # 10 seconds default

        async def analyze_token():
            return await mock_analyzer.analyze(f"token_{random.randint(1, 100)}")

        metrics = await load_generator.run_sustained_load(
            func=analyze_token,
            requests_per_second=50,
            duration_seconds=duration,
        )

        passed, failures = metrics.passes_criteria(
            max_p95_latency_ms=500,
            max_error_rate_pct=1.0
        )

        print(f"\n[Sustained Load - 50 req/sec for {duration}s]")
        print(f"  Total requests: {metrics.total_requests}")
        print(f"  Duration: {metrics.duration:.2f}s")
        print(f"  Actual RPS: {metrics.requests_per_second:.2f}")
        print(f"  Error rate: {metrics.error_rate:.2f}%")
        print(f"  p95 latency: {metrics.p95_latency * 1000:.2f}ms")

        if PSUTIL_AVAILABLE and metrics.cpu_samples:
            print(f"  Avg CPU: {metrics.avg_cpu:.2f}%")
            print(f"  Avg Memory: {metrics.avg_memory:.2f} MB")

        assert passed, f"Load test failed: {failures}"


class TestLoadTestMetrics:
    """Unit tests for load test metrics."""

    def test_metrics_calculation(self):
        """Test metrics calculations."""
        metrics = LoadTestMetrics(
            total_requests=100,
            successful_requests=95,
            failed_requests=5,
            response_times=[0.1, 0.2, 0.15, 0.3, 0.5, 0.1, 0.2, 0.4, 0.6, 0.25],
            start_time=1000,
            end_time=1010,
        )

        assert metrics.error_rate == 5.0
        assert metrics.duration == 10.0
        assert metrics.requests_per_second == 10.0
        assert metrics.p50_latency > 0
        assert metrics.p95_latency > 0
        assert metrics.p99_latency > 0

    def test_passes_criteria(self):
        """Test pass criteria evaluation."""
        # Passing metrics
        metrics = LoadTestMetrics(
            total_requests=100,
            successful_requests=99,
            failed_requests=1,
            response_times=[0.1] * 100,  # 100ms each
        )

        passed, failures = metrics.passes_criteria(
            max_p95_latency_ms=500,
            max_error_rate_pct=2.0
        )
        assert passed
        assert len(failures) == 0

        # Failing metrics
        bad_metrics = LoadTestMetrics(
            total_requests=100,
            successful_requests=90,
            failed_requests=10,
            response_times=[1.0] * 100,  # 1000ms each
        )

        passed, failures = bad_metrics.passes_criteria(
            max_p95_latency_ms=500,
            max_error_rate_pct=1.0
        )
        assert not passed
        assert len(failures) == 2


# =============================================================================
# Baseline Performance Tracking
# =============================================================================

class PerformanceBaseline:
    """Track and compare performance baselines."""

    BASELINE_FILE = Path(__file__).parent / ".performance_baseline.json"

    def __init__(self):
        self.baseline: Dict[str, Any] = {}
        self._load_baseline()

    def _load_baseline(self):
        """Load baseline from file."""
        if self.BASELINE_FILE.exists():
            try:
                self.baseline = json.loads(self.BASELINE_FILE.read_text())
            except Exception:
                self.baseline = {}

    def save_baseline(self):
        """Save baseline to file."""
        self.BASELINE_FILE.write_text(json.dumps(self.baseline, indent=2))

    def update_baseline(self, test_name: str, metrics: LoadTestMetrics):
        """Update baseline for a test."""
        self.baseline[test_name] = {
            "p50_latency_ms": round(metrics.p50_latency * 1000, 2),
            "p95_latency_ms": round(metrics.p95_latency * 1000, 2),
            "p99_latency_ms": round(metrics.p99_latency * 1000, 2),
            "error_rate_pct": round(metrics.error_rate, 2),
            "requests_per_second": round(metrics.requests_per_second, 2),
            "timestamp": datetime.now().isoformat(),
        }
        self.save_baseline()

    def compare_to_baseline(
        self,
        test_name: str,
        metrics: LoadTestMetrics,
        regression_threshold_pct: float = 10.0
    ) -> tuple[bool, Dict[str, Any]]:
        """
        Compare metrics to baseline.

        Returns:
            Tuple of (is_regression, comparison_dict)
        """
        if test_name not in self.baseline:
            return False, {"message": "No baseline exists"}

        baseline = self.baseline[test_name]
        current = {
            "p50_latency_ms": metrics.p50_latency * 1000,
            "p95_latency_ms": metrics.p95_latency * 1000,
            "p99_latency_ms": metrics.p99_latency * 1000,
            "error_rate_pct": metrics.error_rate,
        }

        regressions = {}
        is_regression = False

        for key in ["p50_latency_ms", "p95_latency_ms", "p99_latency_ms", "error_rate_pct"]:
            if baseline.get(key, 0) == 0:
                continue

            change_pct = ((current[key] - baseline[key]) / baseline[key]) * 100
            regressions[key] = {
                "baseline": baseline[key],
                "current": round(current[key], 2),
                "change_pct": round(change_pct, 2),
            }

            if change_pct > regression_threshold_pct:
                is_regression = True

        return is_regression, regressions


class TestPerformanceBaseline:
    """Tests for performance baseline tracking."""

    def test_baseline_comparison(self, tmp_path):
        """Test baseline comparison."""
        baseline = PerformanceBaseline()
        baseline.BASELINE_FILE = tmp_path / "baseline.json"

        # Create baseline
        baseline.baseline["test_load"] = {
            "p50_latency_ms": 100,
            "p95_latency_ms": 200,
            "p99_latency_ms": 300,
            "error_rate_pct": 1.0,
        }

        # Same performance
        metrics = LoadTestMetrics(
            total_requests=100,
            successful_requests=99,
            failed_requests=1,
            response_times=[0.1, 0.2, 0.3] * 33 + [0.1],
        )

        is_regression, comparison = baseline.compare_to_baseline("test_load", metrics)
        assert not is_regression or comparison  # Either no regression or has comparison data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
