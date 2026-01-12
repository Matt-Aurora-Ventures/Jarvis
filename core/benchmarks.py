"""
Performance Benchmarks - Measure and track system performance.
"""

import asyncio
import time
import logging
import statistics
import psutil
import functools
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from pathlib import Path
from collections import defaultdict
import json

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """Result of a single benchmark run."""
    name: str
    duration_ms: float
    success: bool
    timestamp: str
    memory_mb: float = 0.0
    cpu_percent: float = 0.0
    iterations: int = 1
    error: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkStats:
    """Aggregated statistics for a benchmark."""
    name: str
    total_runs: int
    successful_runs: int
    avg_duration_ms: float
    min_duration_ms: float
    max_duration_ms: float
    std_dev_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    avg_memory_mb: float
    avg_cpu_percent: float


class Benchmark:
    """
    Individual benchmark definition.

    Usage:
        @benchmark("api_response_time")
        async def test_api():
            response = await client.get("/health")
            return response.status_code == 200
    """

    def __init__(
        self,
        name: str,
        func: Callable = None,
        iterations: int = 1,
        warmup_iterations: int = 0,
        timeout_ms: float = 30000
    ):
        self.name = name
        self.func = func
        self.iterations = iterations
        self.warmup_iterations = warmup_iterations
        self.timeout_ms = timeout_ms
        self.results: List[BenchmarkResult] = []

    async def run(self) -> BenchmarkResult:
        """Run the benchmark."""
        if not self.func:
            return BenchmarkResult(
                name=self.name,
                duration_ms=0,
                success=False,
                timestamp=datetime.now(timezone.utc).isoformat(),
                error="No function defined"
            )

        # Warmup
        for _ in range(self.warmup_iterations):
            try:
                if asyncio.iscoroutinefunction(self.func):
                    await asyncio.wait_for(
                        self.func(),
                        timeout=self.timeout_ms / 1000
                    )
                else:
                    self.func()
            except Exception:
                pass

        # Get baseline memory
        process = psutil.Process()
        start_memory = process.memory_info().rss / 1024 / 1024

        # Run benchmark
        durations = []
        success = True
        error = ""

        start_cpu_times = process.cpu_times()

        for _ in range(self.iterations):
            start = time.perf_counter()
            try:
                if asyncio.iscoroutinefunction(self.func):
                    result = await asyncio.wait_for(
                        self.func(),
                        timeout=self.timeout_ms / 1000
                    )
                else:
                    result = self.func()

                if result is not None and isinstance(result, bool):
                    success = success and result

            except asyncio.TimeoutError:
                success = False
                error = "Timeout"
            except Exception as e:
                success = False
                error = str(e)

            end = time.perf_counter()
            durations.append((end - start) * 1000)

        # Calculate metrics
        end_memory = process.memory_info().rss / 1024 / 1024
        end_cpu_times = process.cpu_times()

        cpu_user = end_cpu_times.user - start_cpu_times.user
        cpu_system = end_cpu_times.system - start_cpu_times.system
        total_time = sum(durations) / 1000
        cpu_percent = ((cpu_user + cpu_system) / total_time * 100) if total_time > 0 else 0

        avg_duration = statistics.mean(durations) if durations else 0

        result = BenchmarkResult(
            name=self.name,
            duration_ms=avg_duration,
            success=success,
            timestamp=datetime.now(timezone.utc).isoformat(),
            memory_mb=end_memory - start_memory,
            cpu_percent=cpu_percent,
            iterations=self.iterations,
            error=error
        )

        self.results.append(result)
        return result

    def get_stats(self) -> Optional[BenchmarkStats]:
        """Get aggregated statistics."""
        if not self.results:
            return None

        durations = [r.duration_ms for r in self.results]
        successful = [r for r in self.results if r.success]

        sorted_durations = sorted(durations)
        n = len(sorted_durations)

        return BenchmarkStats(
            name=self.name,
            total_runs=len(self.results),
            successful_runs=len(successful),
            avg_duration_ms=statistics.mean(durations),
            min_duration_ms=min(durations),
            max_duration_ms=max(durations),
            std_dev_ms=statistics.stdev(durations) if len(durations) > 1 else 0,
            p50_ms=sorted_durations[n // 2],
            p95_ms=sorted_durations[int(n * 0.95)] if n > 1 else sorted_durations[0],
            p99_ms=sorted_durations[int(n * 0.99)] if n > 1 else sorted_durations[0],
            avg_memory_mb=statistics.mean([r.memory_mb for r in self.results]),
            avg_cpu_percent=statistics.mean([r.cpu_percent for r in self.results])
        )


class BenchmarkSuite:
    """
    Collection of benchmarks to run together.

    Usage:
        suite = BenchmarkSuite("api_benchmarks")

        @suite.add("health_check")
        async def test_health():
            ...

        @suite.add("token_lookup", iterations=10)
        async def test_lookup():
            ...

        results = await suite.run()
    """

    def __init__(self, name: str):
        self.name = name
        self.benchmarks: Dict[str, Benchmark] = {}

    def add(
        self,
        name: str,
        iterations: int = 1,
        warmup_iterations: int = 0,
        timeout_ms: float = 30000
    ):
        """Decorator to add a benchmark."""
        def decorator(func: Callable):
            self.benchmarks[name] = Benchmark(
                name=name,
                func=func,
                iterations=iterations,
                warmup_iterations=warmup_iterations,
                timeout_ms=timeout_ms
            )
            return func
        return decorator

    def add_benchmark(self, benchmark: Benchmark):
        """Add an existing benchmark."""
        self.benchmarks[benchmark.name] = benchmark

    async def run(self, parallel: bool = False) -> List[BenchmarkResult]:
        """Run all benchmarks in the suite."""
        logger.info(f"Running benchmark suite: {self.name}")

        if parallel:
            tasks = [b.run() for b in self.benchmarks.values()]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return [r for r in results if isinstance(r, BenchmarkResult)]
        else:
            results = []
            for name, benchmark in self.benchmarks.items():
                logger.debug(f"Running benchmark: {name}")
                result = await benchmark.run()
                results.append(result)
            return results

    def get_all_stats(self) -> Dict[str, BenchmarkStats]:
        """Get stats for all benchmarks."""
        return {
            name: b.get_stats()
            for name, b in self.benchmarks.items()
            if b.get_stats() is not None
        }

    def generate_report(self) -> str:
        """Generate a text report."""
        lines = [
            f"Benchmark Suite: {self.name}",
            "=" * 50,
            ""
        ]

        for name, stats in self.get_all_stats().items():
            if stats:
                lines.extend([
                    f"{name}:",
                    f"  Runs: {stats.total_runs} ({stats.successful_runs} successful)",
                    f"  Avg: {stats.avg_duration_ms:.2f}ms",
                    f"  Min/Max: {stats.min_duration_ms:.2f}ms / {stats.max_duration_ms:.2f}ms",
                    f"  P50/P95/P99: {stats.p50_ms:.2f}ms / {stats.p95_ms:.2f}ms / {stats.p99_ms:.2f}ms",
                    f"  Memory: {stats.avg_memory_mb:.2f}MB, CPU: {stats.avg_cpu_percent:.1f}%",
                    ""
                ])

        return "\n".join(lines)


class PerformanceProfiler:
    """
    Profile code performance with context managers.

    Usage:
        profiler = PerformanceProfiler()

        async with profiler.measure("database_query"):
            await db.query(...)

        report = profiler.get_report()
    """

    def __init__(self):
        self.measurements: Dict[str, List[float]] = defaultdict(list)
        self._active: Dict[str, float] = {}

    class _MeasureContext:
        def __init__(self, profiler, name: str):
            self.profiler = profiler
            self.name = name
            self.start = None

        def __enter__(self):
            self.start = time.perf_counter()
            return self

        def __exit__(self, *args):
            duration = (time.perf_counter() - self.start) * 1000
            self.profiler.measurements[self.name].append(duration)

        async def __aenter__(self):
            self.start = time.perf_counter()
            return self

        async def __aexit__(self, *args):
            duration = (time.perf_counter() - self.start) * 1000
            self.profiler.measurements[self.name].append(duration)

    def measure(self, name: str):
        """Context manager for measuring code execution time."""
        return self._MeasureContext(self, name)

    def record(self, name: str, duration_ms: float):
        """Manually record a measurement."""
        self.measurements[name].append(duration_ms)

    def get_stats(self, name: str) -> Optional[Dict]:
        """Get statistics for a specific measurement."""
        if name not in self.measurements or not self.measurements[name]:
            return None

        durations = self.measurements[name]
        sorted_durations = sorted(durations)
        n = len(sorted_durations)

        return {
            'name': name,
            'count': n,
            'avg_ms': statistics.mean(durations),
            'min_ms': min(durations),
            'max_ms': max(durations),
            'std_dev_ms': statistics.stdev(durations) if n > 1 else 0,
            'p50_ms': sorted_durations[n // 2],
            'p95_ms': sorted_durations[int(n * 0.95)] if n > 1 else sorted_durations[0],
            'p99_ms': sorted_durations[int(n * 0.99)] if n > 1 else sorted_durations[0]
        }

    def get_report(self) -> Dict[str, Dict]:
        """Get report for all measurements."""
        return {
            name: self.get_stats(name)
            for name in self.measurements
        }

    def clear(self):
        """Clear all measurements."""
        self.measurements.clear()


# === DECORATOR FOR FUNCTION TIMING ===

def benchmark(name: str = None, threshold_ms: float = None):
    """
    Decorator to benchmark function execution.

    Usage:
        @benchmark("my_function", threshold_ms=100)
        async def slow_function():
            ...
    """
    def decorator(func: Callable):
        benchmark_name = name or func.__name__

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                return await func(*args, **kwargs)
            finally:
                duration = (time.perf_counter() - start) * 1000
                if threshold_ms and duration > threshold_ms:
                    logger.warning(
                        f"{benchmark_name} took {duration:.2f}ms "
                        f"(threshold: {threshold_ms}ms)"
                    )

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                duration = (time.perf_counter() - start) * 1000
                if threshold_ms and duration > threshold_ms:
                    logger.warning(
                        f"{benchmark_name} took {duration:.2f}ms "
                        f"(threshold: {threshold_ms}ms)"
                    )

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# === JARVIS STANDARD BENCHMARKS ===

def create_jarvis_benchmarks() -> BenchmarkSuite:
    """Create standard benchmarks for Jarvis."""
    suite = BenchmarkSuite("jarvis_performance")

    @suite.add("health_check", iterations=5)
    async def benchmark_health():
        """Benchmark health check endpoint."""
        # Simulated - replace with actual health check
        await asyncio.sleep(0.01)
        return True

    @suite.add("memory_usage")
    async def benchmark_memory():
        """Check memory usage."""
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        # Fail if memory exceeds 500MB
        return memory_mb < 500

    @suite.add("cpu_usage")
    async def benchmark_cpu():
        """Check CPU usage."""
        cpu_percent = psutil.cpu_percent(interval=0.5)
        return cpu_percent < 80

    @suite.add("disk_io", iterations=3)
    async def benchmark_disk():
        """Benchmark disk I/O."""
        import tempfile
        data = b"x" * (1024 * 1024)  # 1MB

        with tempfile.NamedTemporaryFile(delete=True) as f:
            f.write(data)
            f.flush()
            f.seek(0)
            _ = f.read()

        return True

    return suite


# Singleton
_profiler: Optional[PerformanceProfiler] = None

def get_profiler() -> PerformanceProfiler:
    """Get singleton profiler."""
    global _profiler
    if _profiler is None:
        _profiler = PerformanceProfiler()
    return _profiler
