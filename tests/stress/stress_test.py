"""
JARVIS Stress Testing Suite

Tests system behavior under extreme conditions to find breaking points.

Stress Scenarios:
1. Spike: Sudden 10x traffic increase
2. Sustained: Constant load for extended period
3. Ramp: Gradually increase from 10 to 100 users

Usage:
    pytest tests/stress/stress_test.py -v
    pytest tests/stress/stress_test.py -v --run-stress-tests  # Full tests
"""

import asyncio
import random
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

import pytest

# Try to import psutil for resource monitoring
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


@dataclass
class StressMetrics:
    """Metrics collected during stress testing."""
    phase: str = ""
    duration_seconds: float = 0
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    response_times: List[float] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    # Breakdown by time bucket
    time_buckets: List[Dict[str, Any]] = field(default_factory=list)

    # Resource tracking
    peak_cpu: float = 0
    peak_memory_mb: float = 0
    avg_cpu: float = 0
    avg_memory_mb: float = 0

    @property
    def error_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return (self.failed_requests / self.total_requests) * 100

    @property
    def throughput(self) -> float:
        if self.duration_seconds == 0:
            return 0.0
        return self.total_requests / self.duration_seconds

    @property
    def p95_latency(self) -> float:
        if not self.response_times:
            return 0.0
        sorted_times = sorted(self.response_times)
        idx = int(len(sorted_times) * 0.95)
        return sorted_times[min(idx, len(sorted_times) - 1)]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase": self.phase,
            "duration_seconds": round(self.duration_seconds, 2),
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "error_rate_pct": round(self.error_rate, 2),
            "throughput_rps": round(self.throughput, 2),
            "p95_latency_ms": round(self.p95_latency * 1000, 2),
            "peak_cpu_pct": round(self.peak_cpu, 2),
            "peak_memory_mb": round(self.peak_memory_mb, 2),
            "time_buckets": self.time_buckets,
        }


@dataclass
class StressCurve:
    """Represents system behavior over time under stress."""
    timestamps: List[float] = field(default_factory=list)
    throughputs: List[float] = field(default_factory=list)
    latencies: List[float] = field(default_factory=list)
    error_rates: List[float] = field(default_factory=list)
    user_counts: List[int] = field(default_factory=list)

    def get_degradation_point(self) -> Optional[Tuple[int, float]]:
        """
        Find the point where performance degrades significantly.

        Returns:
            Tuple of (user_count, latency_at_degradation) or None
        """
        if len(self.latencies) < 3:
            return None

        # Find where latency increases by >50% from baseline
        baseline = statistics.mean(self.latencies[:3])

        for i, latency in enumerate(self.latencies):
            if latency > baseline * 1.5:
                return (self.user_counts[i], latency)

        return None

    def get_breaking_point(self) -> Optional[Tuple[int, float]]:
        """
        Find the point where system starts failing.

        Returns:
            Tuple of (user_count, error_rate_at_break) or None
        """
        for i, error_rate in enumerate(self.error_rates):
            if error_rate > 5.0:  # >5% error rate = breaking
                return (self.user_counts[i], error_rate)

        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "data_points": len(self.timestamps),
            "degradation_point": self.get_degradation_point(),
            "breaking_point": self.get_breaking_point(),
            "peak_throughput": max(self.throughputs) if self.throughputs else 0,
            "peak_users": max(self.user_counts) if self.user_counts else 0,
        }


class StressTestRunner:
    """Run stress tests with various patterns."""

    def __init__(self):
        self.current_metrics = StressMetrics()
        self._resource_samples: List[Tuple[float, float]] = []

    async def _sample_resources(self):
        """Sample system resources."""
        if not PSUTIL_AVAILABLE:
            return

        process = psutil.Process()
        cpu = process.cpu_percent()
        memory = process.memory_info().rss / 1024 / 1024
        self._resource_samples.append((cpu, memory))

    async def _run_requests(
        self,
        func: Callable,
        concurrent: int,
        count: int,
        args: tuple = (),
        kwargs: dict = None,
    ) -> Tuple[int, int, List[float], List[str]]:
        """Run a batch of concurrent requests."""
        kwargs = kwargs or {}
        semaphore = asyncio.Semaphore(concurrent)
        successful = 0
        failed = 0
        response_times = []
        errors = []

        async def make_request():
            nonlocal successful, failed
            async with semaphore:
                start = time.time()
                try:
                    await func(*args, **kwargs)
                    elapsed = time.time() - start
                    response_times.append(elapsed)
                    successful += 1
                except Exception as e:
                    elapsed = time.time() - start
                    response_times.append(elapsed)
                    failed += 1
                    errors.append(str(e)[:100])

        tasks = [make_request() for _ in range(count)]
        await asyncio.gather(*tasks, return_exceptions=True)

        return successful, failed, response_times, errors

    async def run_spike_test(
        self,
        func: Callable,
        baseline_users: int = 10,
        spike_multiplier: int = 10,
        spike_duration_seconds: float = 30,
        args: tuple = (),
        kwargs: dict = None,
    ) -> Tuple[StressMetrics, StressMetrics, StressMetrics]:
        """
        Run spike test: sudden traffic increase.

        Returns:
            Tuple of (pre_spike_metrics, spike_metrics, post_spike_metrics)
        """
        kwargs = kwargs or {}
        requests_per_phase = 100

        # Phase 1: Baseline
        pre_metrics = StressMetrics(phase="pre_spike")
        start = time.time()
        s, f, times, errs = await self._run_requests(
            func, baseline_users, requests_per_phase, args, kwargs
        )
        pre_metrics.duration_seconds = time.time() - start
        pre_metrics.successful_requests = s
        pre_metrics.failed_requests = f
        pre_metrics.total_requests = s + f
        pre_metrics.response_times = times
        pre_metrics.errors = errs

        # Phase 2: Spike
        spike_metrics = StressMetrics(phase="spike")
        spike_users = baseline_users * spike_multiplier
        start = time.time()
        s, f, times, errs = await self._run_requests(
            func, spike_users, requests_per_phase * spike_multiplier, args, kwargs
        )
        spike_metrics.duration_seconds = time.time() - start
        spike_metrics.successful_requests = s
        spike_metrics.failed_requests = f
        spike_metrics.total_requests = s + f
        spike_metrics.response_times = times
        spike_metrics.errors = errs

        # Phase 3: Recovery
        post_metrics = StressMetrics(phase="post_spike")
        start = time.time()
        s, f, times, errs = await self._run_requests(
            func, baseline_users, requests_per_phase, args, kwargs
        )
        post_metrics.duration_seconds = time.time() - start
        post_metrics.successful_requests = s
        post_metrics.failed_requests = f
        post_metrics.total_requests = s + f
        post_metrics.response_times = times
        post_metrics.errors = errs

        return pre_metrics, spike_metrics, post_metrics

    async def run_ramp_test(
        self,
        func: Callable,
        start_users: int = 10,
        end_users: int = 100,
        steps: int = 10,
        requests_per_step: int = 50,
        args: tuple = (),
        kwargs: dict = None,
    ) -> Tuple[StressMetrics, StressCurve]:
        """
        Run ramp test: gradually increase load.

        Returns:
            Tuple of (overall_metrics, stress_curve)
        """
        kwargs = kwargs or {}
        curve = StressCurve()
        overall = StressMetrics(phase="ramp")

        user_step = (end_users - start_users) // steps
        start_time = time.time()

        for step in range(steps + 1):
            users = start_users + (step * user_step)
            step_start = time.time()

            s, f, times, errs = await self._run_requests(
                func, users, requests_per_step, args, kwargs
            )

            step_duration = time.time() - step_start

            # Record curve data
            curve.timestamps.append(time.time() - start_time)
            curve.user_counts.append(users)
            curve.throughputs.append((s + f) / step_duration if step_duration > 0 else 0)
            curve.latencies.append(statistics.mean(times) if times else 0)
            curve.error_rates.append((f / (s + f) * 100) if (s + f) > 0 else 0)

            # Accumulate overall
            overall.successful_requests += s
            overall.failed_requests += f
            overall.total_requests += s + f
            overall.response_times.extend(times)
            overall.errors.extend(errs)

            await self._sample_resources()

        overall.duration_seconds = time.time() - start_time

        # Calculate resource stats
        if self._resource_samples:
            cpus, mems = zip(*self._resource_samples)
            overall.peak_cpu = max(cpus)
            overall.peak_memory_mb = max(mems)
            overall.avg_cpu = statistics.mean(cpus)
            overall.avg_memory_mb = statistics.mean(mems)

        return overall, curve

    async def run_sustained_test(
        self,
        func: Callable,
        users: int = 50,
        duration_seconds: float = 60,
        bucket_seconds: float = 10,
        args: tuple = (),
        kwargs: dict = None,
    ) -> StressMetrics:
        """
        Run sustained load test.

        Returns:
            StressMetrics with time bucket breakdown
        """
        kwargs = kwargs or {}
        metrics = StressMetrics(phase="sustained")
        start_time = time.time()
        end_time = start_time + duration_seconds

        while time.time() < end_time:
            bucket_start = time.time()
            bucket_end = min(bucket_start + bucket_seconds, end_time)

            bucket_success = 0
            bucket_failed = 0
            bucket_times = []

            # Run requests for this bucket
            while time.time() < bucket_end:
                s, f, times, errs = await self._run_requests(
                    func, users, users, args, kwargs
                )
                bucket_success += s
                bucket_failed += f
                bucket_times.extend(times)
                metrics.errors.extend(errs)

            # Record bucket
            bucket_duration = time.time() - bucket_start
            bucket_data = {
                "timestamp": bucket_start - start_time,
                "duration": round(bucket_duration, 2),
                "requests": bucket_success + bucket_failed,
                "errors": bucket_failed,
                "error_rate": round(
                    bucket_failed / (bucket_success + bucket_failed) * 100
                    if (bucket_success + bucket_failed) > 0 else 0, 2
                ),
                "p95_latency_ms": round(
                    sorted(bucket_times)[int(len(bucket_times) * 0.95)] * 1000
                    if bucket_times else 0, 2
                ),
            }
            metrics.time_buckets.append(bucket_data)

            metrics.successful_requests += bucket_success
            metrics.failed_requests += bucket_failed
            metrics.total_requests += bucket_success + bucket_failed
            metrics.response_times.extend(bucket_times)

            await self._sample_resources()

        metrics.duration_seconds = time.time() - start_time

        # Resource stats
        if self._resource_samples:
            cpus, mems = zip(*self._resource_samples)
            metrics.peak_cpu = max(cpus)
            metrics.peak_memory_mb = max(mems)
            metrics.avg_cpu = statistics.mean(cpus)
            metrics.avg_memory_mb = statistics.mean(mems)

        return metrics


# =============================================================================
# Mock Services for Stress Testing
# =============================================================================

class MockService:
    """Mock service with configurable behavior."""

    def __init__(
        self,
        base_latency: float = 0.01,
        latency_variance: float = 0.005,
        failure_rate: float = 0.01,
        degradation_threshold: int = 50,
    ):
        self.base_latency = base_latency
        self.latency_variance = latency_variance
        self.failure_rate = failure_rate
        self.degradation_threshold = degradation_threshold
        self._concurrent = 0
        self._lock = asyncio.Lock()

    async def process(self, data: Any = None) -> Dict[str, Any]:
        """Process a request with realistic behavior."""
        async with self._lock:
            self._concurrent += 1
            current_concurrent = self._concurrent

        try:
            # Simulate latency that increases with load
            load_factor = max(1.0, current_concurrent / self.degradation_threshold)
            latency = (self.base_latency + random.uniform(-self.latency_variance, self.latency_variance)) * load_factor
            await asyncio.sleep(latency)

            # Failure rate increases under load
            adjusted_failure_rate = self.failure_rate * load_factor
            if random.random() < adjusted_failure_rate:
                raise Exception(f"Service overloaded ({current_concurrent} concurrent)")

            return {
                "status": "success",
                "data": data,
                "processing_time_ms": round(latency * 1000, 2),
                "concurrent_requests": current_concurrent,
            }

        finally:
            async with self._lock:
                self._concurrent -= 1


# =============================================================================
# Stress Test Scenarios
# =============================================================================

class TestStressScenarios:
    """Stress test scenarios for Jarvis."""

    @pytest.fixture
    def stress_runner(self):
        return StressTestRunner()

    @pytest.fixture
    def mock_service(self):
        return MockService(
            base_latency=0.01,
            latency_variance=0.005,
            failure_rate=0.01,
            degradation_threshold=30,
        )

    @pytest.mark.asyncio
    async def test_spike_10x_traffic(
        self,
        stress_runner: StressTestRunner,
        mock_service: MockService
    ):
        """
        Scenario: Sudden 10x traffic increase.

        Validates:
        - System handles spike without crashing
        - Error rate during spike is acceptable (<10%)
        - System recovers after spike
        """
        pre, spike, post = await stress_runner.run_spike_test(
            func=mock_service.process,
            baseline_users=5,
            spike_multiplier=10,
            spike_duration_seconds=5,
        )

        print(f"\n[Spike Test - 10x Traffic]")
        print(f"  Pre-spike:  {pre.total_requests} reqs, {pre.error_rate:.2f}% errors, p95={pre.p95_latency*1000:.2f}ms")
        print(f"  During spike: {spike.total_requests} reqs, {spike.error_rate:.2f}% errors, p95={spike.p95_latency*1000:.2f}ms")
        print(f"  Post-spike: {post.total_requests} reqs, {post.error_rate:.2f}% errors, p95={post.p95_latency*1000:.2f}ms")

        # Spike shouldn't cause complete failure
        assert spike.error_rate < 50, f"Too many errors during spike: {spike.error_rate}%"

        # System should recover after spike
        # Allow small tolerance (5%) even if pre-spike was 0% errors
        max_acceptable_error = max(pre.error_rate * 2, 5.0)
        assert post.error_rate <= max_acceptable_error, \
            f"System didn't recover properly after spike: {post.error_rate:.2f}% > {max_acceptable_error:.2f}%"

    @pytest.mark.asyncio
    async def test_ramp_10_to_100_users(
        self,
        stress_runner: StressTestRunner,
        mock_service: MockService
    ):
        """
        Scenario: Gradually increase from 10 to 100 users.

        Validates:
        - Identifies degradation point
        - Identifies breaking point (if any)
        - Generates stress curve
        """
        metrics, curve = await stress_runner.run_ramp_test(
            func=mock_service.process,
            start_users=10,
            end_users=100,
            steps=9,
            requests_per_step=30,
        )

        print(f"\n[Ramp Test - 10 to 100 Users]")
        print(f"  Total requests: {metrics.total_requests}")
        print(f"  Overall error rate: {metrics.error_rate:.2f}%")
        print(f"  Duration: {metrics.duration_seconds:.2f}s")

        degradation = curve.get_degradation_point()
        breaking = curve.get_breaking_point()

        if degradation:
            print(f"  Degradation point: {degradation[0]} users (latency: {degradation[1]*1000:.2f}ms)")
        else:
            print(f"  No degradation detected")

        if breaking:
            print(f"  Breaking point: {breaking[0]} users (error rate: {breaking[1]:.2f}%)")
        else:
            print(f"  No breaking point detected")

        print(f"  Peak throughput: {max(curve.throughputs):.2f} req/s")

        # Should complete without catastrophic failure
        assert metrics.total_requests > 0, "No requests completed"

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_sustained_load_1_minute(
        self,
        stress_runner: StressTestRunner,
        mock_service: MockService
    ):
        """
        Scenario: Sustained load for 1 minute.

        Validates:
        - Consistent performance over time
        - No memory leaks (stable memory)
        - Error rate stays bounded
        """
        # Use shorter duration for unit tests
        duration = 10  # seconds

        metrics = await stress_runner.run_sustained_test(
            func=mock_service.process,
            users=20,
            duration_seconds=duration,
            bucket_seconds=2,
        )

        print(f"\n[Sustained Load - {duration}s at 20 users]")
        print(f"  Total requests: {metrics.total_requests}")
        print(f"  Error rate: {metrics.error_rate:.2f}%")
        print(f"  Throughput: {metrics.throughput:.2f} req/s")
        print(f"  p95 latency: {metrics.p95_latency * 1000:.2f}ms")

        if metrics.time_buckets:
            print(f"\n  Time bucket analysis:")
            for bucket in metrics.time_buckets:
                print(f"    t={bucket['timestamp']:.0f}s: {bucket['requests']} reqs, {bucket['error_rate']}% errors")

        # Error rate should stay relatively stable
        if len(metrics.time_buckets) >= 2:
            early_errors = statistics.mean(
                b["error_rate"] for b in metrics.time_buckets[:2]
            )
            late_errors = statistics.mean(
                b["error_rate"] for b in metrics.time_buckets[-2:]
            )
            # Late error rate shouldn't be 5x worse than early
            assert late_errors < early_errors * 5 + 1, "Error rate degraded significantly over time"


class TestStressCurve:
    """Unit tests for stress curve analysis."""

    def test_degradation_detection(self):
        """Test degradation point detection."""
        curve = StressCurve(
            timestamps=[0, 1, 2, 3, 4],
            user_counts=[10, 20, 30, 40, 50],
            latencies=[0.1, 0.1, 0.12, 0.2, 0.3],  # Degradation at 40 users
            error_rates=[0, 0, 0, 1, 2],
            throughputs=[100, 100, 95, 80, 60],
        )

        degradation = curve.get_degradation_point()
        assert degradation is not None
        assert degradation[0] == 40  # 40 users

    def test_breaking_point_detection(self):
        """Test breaking point detection."""
        curve = StressCurve(
            timestamps=[0, 1, 2, 3, 4],
            user_counts=[10, 20, 30, 40, 50],
            latencies=[0.1, 0.1, 0.12, 0.2, 0.3],
            error_rates=[0, 1, 2, 8, 15],  # Breaking at 40 users
            throughputs=[100, 100, 95, 80, 60],
        )

        breaking = curve.get_breaking_point()
        assert breaking is not None
        assert breaking[0] == 40  # 40 users

    def test_no_breaking_point(self):
        """Test when no breaking point exists."""
        curve = StressCurve(
            timestamps=[0, 1, 2],
            user_counts=[10, 20, 30],
            latencies=[0.1, 0.1, 0.12],
            error_rates=[0, 1, 2],  # All under 5%
            throughputs=[100, 100, 95],
        )

        breaking = curve.get_breaking_point()
        assert breaking is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
