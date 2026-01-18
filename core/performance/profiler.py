"""Performance profiling utilities."""
import time
import functools
import asyncio
import tracemalloc
from typing import Callable, Dict, Any, Optional
from dataclasses import dataclass, field
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)


@dataclass
class ProfileResult:
    """Result of a profiling operation."""
    name: str
    duration_ms: float
    memory_peak_mb: float = 0
    memory_current_mb: float = 0
    call_count: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)


class Profiler:
    """Track and report performance metrics."""
    
    def __init__(self, enable_memory: bool = False):
        self.enable_memory = enable_memory
        self.results: Dict[str, ProfileResult] = {}
        self._active = False
    
    def start(self):
        """Start profiling session."""
        self._active = True
        if self.enable_memory:
            tracemalloc.start()
    
    def stop(self) -> Dict[str, ProfileResult]:
        """Stop profiling and return results."""
        self._active = False
        if self.enable_memory:
            tracemalloc.stop()
        return self.results
    
    @contextmanager
    def measure(self, name: str):
        """Context manager to measure a code block."""
        start_time = time.perf_counter()
        memory_start = None
        
        if self.enable_memory and tracemalloc.is_tracing():
            memory_start = tracemalloc.get_traced_memory()
        
        try:
            yield
        finally:
            duration = (time.perf_counter() - start_time) * 1000
            
            memory_peak = 0
            memory_current = 0
            if memory_start and tracemalloc.is_tracing():
                current, peak = tracemalloc.get_traced_memory()
                memory_current = current / 1024 / 1024
                memory_peak = peak / 1024 / 1024
            
            if name in self.results:
                self.results[name].duration_ms += duration
                self.results[name].call_count += 1
                self.results[name].memory_peak_mb = max(self.results[name].memory_peak_mb, memory_peak)
            else:
                self.results[name] = ProfileResult(
                    name=name,
                    duration_ms=duration,
                    memory_peak_mb=memory_peak,
                    memory_current_mb=memory_current
                )
    
    def get_report(self) -> str:
        """Generate a formatted report."""
        lines = ["Performance Report", "=" * 50]
        
        sorted_results = sorted(self.results.values(), key=lambda x: x.duration_ms, reverse=True)
        
        for r in sorted_results:
            avg_ms = r.duration_ms / r.call_count
            lines.append(f"{r.name}:")
            lines.append(f"  Total: {r.duration_ms:.2f}ms ({r.call_count} calls, avg {avg_ms:.2f}ms)")
            if r.memory_peak_mb > 0:
                lines.append(f"  Memory peak: {r.memory_peak_mb:.2f}MB")
        
        return "\n".join(lines)
    
    def reset(self):
        """Clear all results."""
        self.results.clear()


# Global profiler instance
_profiler = Profiler()


def profile(name: str = None):
    """Decorator to profile a function."""
    def decorator(func: Callable) -> Callable:
        profile_name = name or func.__name__
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                duration = (time.perf_counter() - start) * 1000
                logger.debug(f"{profile_name} took {duration:.2f}ms")
        
        return wrapper
    return decorator


def profile_async(name: str = None):
    """Decorator to profile an async function."""
    def decorator(func: Callable) -> Callable:
        profile_name = name or func.__name__
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                return await func(*args, **kwargs)
            finally:
                duration = (time.perf_counter() - start) * 1000
                logger.debug(f"{profile_name} took {duration:.2f}ms")
        
        return wrapper
    return decorator


@contextmanager
def timed_block(name: str, log_level: int = logging.DEBUG, warn_threshold_ms: float = None):
    """Simple timing context manager with optional warning threshold."""
    start = time.perf_counter()
    try:
        yield
    finally:
        duration = (time.perf_counter() - start) * 1000
        if warn_threshold_ms and duration > warn_threshold_ms:
            logger.warning(f"SLOW: {name}: {duration:.2f}ms (threshold: {warn_threshold_ms}ms)")
        else:
            logger.log(log_level, f"{name}: {duration:.2f}ms")


class PerformanceTracker:
    """
    Track performance metrics over time with aggregation.

    Usage:
        tracker = PerformanceTracker()

        with tracker.track("api_call"):
            await make_api_call()

        print(tracker.get_stats("api_call"))
    """

    def __init__(self, max_samples: int = 1000):
        self.max_samples = max_samples
        self._samples: Dict[str, list] = {}
        self._counts: Dict[str, int] = {}

    @contextmanager
    def track(self, name: str):
        """Track a code block's execution time."""
        start = time.perf_counter()
        try:
            yield
        finally:
            duration = (time.perf_counter() - start) * 1000
            self._record(name, duration)

    def _record(self, name: str, duration_ms: float):
        """Record a timing sample."""
        if name not in self._samples:
            self._samples[name] = []
            self._counts[name] = 0

        self._samples[name].append(duration_ms)
        self._counts[name] += 1

        # Limit samples
        if len(self._samples[name]) > self.max_samples:
            self._samples[name] = self._samples[name][-self.max_samples:]

    def get_stats(self, name: str) -> Dict[str, Any]:
        """Get statistics for a tracked operation."""
        if name not in self._samples or not self._samples[name]:
            return {"name": name, "count": 0}

        samples = self._samples[name]
        sorted_samples = sorted(samples)
        count = self._counts[name]

        return {
            "name": name,
            "count": count,
            "min_ms": round(min(samples), 2),
            "max_ms": round(max(samples), 2),
            "avg_ms": round(sum(samples) / len(samples), 2),
            "p50_ms": round(sorted_samples[len(sorted_samples) // 2], 2),
            "p95_ms": round(sorted_samples[int(len(sorted_samples) * 0.95)], 2) if len(sorted_samples) > 20 else None,
            "p99_ms": round(sorted_samples[int(len(sorted_samples) * 0.99)], 2) if len(sorted_samples) > 100 else None,
            "samples": len(samples),
        }

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get stats for all tracked operations."""
        return {name: self.get_stats(name) for name in self._samples}

    def reset(self, name: str = None):
        """Reset tracking for one or all operations."""
        if name:
            self._samples.pop(name, None)
            self._counts.pop(name, None)
        else:
            self._samples.clear()
            self._counts.clear()


# Global performance tracker
_tracker = PerformanceTracker()


def get_performance_tracker() -> PerformanceTracker:
    """Get the global performance tracker."""
    return _tracker


def track_performance(name: str = None, warn_threshold_ms: float = None):
    """
    Decorator to track function performance with optional warning.

    Usage:
        @track_performance(warn_threshold_ms=100)
        async def slow_operation():
            ...
    """
    def decorator(func: Callable) -> Callable:
        op_name = name or func.__name__

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                return await func(*args, **kwargs)
            finally:
                duration = (time.perf_counter() - start) * 1000
                _tracker._record(op_name, duration)
                if warn_threshold_ms and duration > warn_threshold_ms:
                    logger.warning(f"SLOW: {op_name}: {duration:.2f}ms")

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                duration = (time.perf_counter() - start) * 1000
                _tracker._record(op_name, duration)
                if warn_threshold_ms and duration > warn_threshold_ms:
                    logger.warning(f"SLOW: {op_name}: {duration:.2f}ms")

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# =============================================================================
# Enhanced Profile Block System
# =============================================================================

@dataclass
class EnhancedProfileResult:
    """Extended result for profile_block operations."""
    name: str
    duration_ms: float
    memory_mb: float = 0.0
    peak_memory_mb: float = 0.0
    call_count: int = 1
    exception_count: int = 0
    last_exception: Optional[str] = None


class GlobalProfileStore:
    """
    Global store for profile_block results.

    Thread-safe storage for profiling results that can be accessed
    across the application.
    """

    def __init__(self):
        self._results: Dict[str, EnhancedProfileResult] = {}
        self._memory_tracking = False

    def record(
        self,
        name: str,
        duration_ms: float,
        memory_mb: float = 0.0,
        peak_memory_mb: float = 0.0,
        exception: Optional[Exception] = None
    ):
        """Record a profiling result."""
        if name in self._results:
            r = self._results[name]
            r.duration_ms += duration_ms
            r.call_count += 1
            r.memory_mb = max(r.memory_mb, memory_mb)
            r.peak_memory_mb = max(r.peak_memory_mb, peak_memory_mb)
            if exception:
                r.exception_count += 1
                r.last_exception = str(exception)
        else:
            self._results[name] = EnhancedProfileResult(
                name=name,
                duration_ms=duration_ms,
                memory_mb=memory_mb,
                peak_memory_mb=peak_memory_mb,
                call_count=1,
                exception_count=1 if exception else 0,
                last_exception=str(exception) if exception else None
            )

    def get_results(self) -> Dict[str, Dict[str, Any]]:
        """Get all results as a dictionary."""
        return {
            name: {
                "duration_ms": r.duration_ms,
                "memory_mb": r.memory_mb,
                "peak_memory_mb": r.peak_memory_mb,
                "call_count": r.call_count,
                "exception_count": r.exception_count,
                "avg_duration_ms": r.duration_ms / r.call_count if r.call_count > 0 else 0
            }
            for name, r in self._results.items()
        }

    def reset(self):
        """Clear all results."""
        self._results.clear()


# Global profile store
_profile_store = GlobalProfileStore()


@contextmanager
def profile_block(name: str, track_memory: bool = False):
    """
    Context manager for profiling a code block.

    Usage:
        with profile_block("trading.execute_trade"):
            # code here gets profiled

        with profile_block("analysis.sentiment", track_memory=True):
            # code here gets profiled with memory tracking

    Args:
        name: Unique name for this profiled operation (use dotted notation)
        track_memory: Whether to track memory usage (has overhead)
    """
    start_time = time.perf_counter()
    memory_before = 0
    exception_caught = None

    # Start memory tracking if requested
    if track_memory:
        if not tracemalloc.is_tracing():
            tracemalloc.start()
        memory_before, _ = tracemalloc.get_traced_memory()

    try:
        yield
    except Exception as e:
        exception_caught = e
        raise
    finally:
        duration_ms = (time.perf_counter() - start_time) * 1000

        memory_mb = 0.0
        peak_memory_mb = 0.0
        if track_memory and tracemalloc.is_tracing():
            memory_after, peak = tracemalloc.get_traced_memory()
            memory_mb = (memory_after - memory_before) / 1024 / 1024
            peak_memory_mb = peak / 1024 / 1024

        _profile_store.record(
            name=name,
            duration_ms=duration_ms,
            memory_mb=memory_mb,
            peak_memory_mb=peak_memory_mb,
            exception=exception_caught
        )


def get_profiler_results() -> Dict[str, Dict[str, Any]]:
    """Get all profiler results."""
    return _profile_store.get_results()


def reset_profiler():
    """Reset the global profiler."""
    _profile_store.reset()


def profile_performance(func: Callable = None, *, name: str = None):
    """
    Decorator to profile a function's performance.

    Can be used with or without arguments:
        @profile_performance
        def my_func():
            ...

        @profile_performance(name="custom.name")
        async def my_async_func():
            ...

    Args:
        func: The function to decorate (when used without parentheses)
        name: Custom name for the operation (defaults to function name)
    """
    def decorator(fn: Callable) -> Callable:
        op_name = name or fn.__name__

        @functools.wraps(fn)
        async def async_wrapper(*args, **kwargs):
            with profile_block(op_name):
                return await fn(*args, **kwargs)

        @functools.wraps(fn)
        def sync_wrapper(*args, **kwargs):
            with profile_block(op_name):
                return fn(*args, **kwargs)

        if asyncio.iscoroutinefunction(fn):
            return async_wrapper
        return sync_wrapper

    # Handle both @profile_performance and @profile_performance()
    if func is not None:
        return decorator(func)
    return decorator


# =============================================================================
# Output Formatters
# =============================================================================

def export_results_json() -> str:
    """Export profiler results as JSON."""
    import json
    return json.dumps(get_profiler_results(), indent=2)


def export_results_csv() -> str:
    """Export profiler results as CSV."""
    results = get_profiler_results()
    lines = ["name,duration_ms,avg_duration_ms,call_count,exception_count,memory_mb"]

    for name, data in sorted(results.items()):
        lines.append(
            f"{name},{data['duration_ms']:.2f},{data['avg_duration_ms']:.2f},"
            f"{data['call_count']},{data['exception_count']},{data['memory_mb']:.2f}"
        )

    return "\n".join(lines)


def export_results_table() -> str:
    """Export profiler results as a human-readable table."""
    results = get_profiler_results()

    if not results:
        return "No profiling results available."

    # Calculate column widths
    name_width = max(len(name) for name in results.keys())
    name_width = max(name_width, 20)

    lines = [
        "Performance Profiling Results",
        "=" * 70,
        f"{'Name':<{name_width}} {'Time(ms)':>12} {'Avg(ms)':>10} {'Calls':>8} {'Errors':>8}",
        "-" * 70
    ]

    # Sort by duration (slowest first)
    sorted_results = sorted(
        results.items(),
        key=lambda x: x[1]['duration_ms'],
        reverse=True
    )

    for name, data in sorted_results:
        lines.append(
            f"{name:<{name_width}} {data['duration_ms']:>12.2f} "
            f"{data['avg_duration_ms']:>10.2f} {data['call_count']:>8} "
            f"{data['exception_count']:>8}"
        )

    lines.append("-" * 70)

    # Summary
    total_time = sum(d['duration_ms'] for d in results.values())
    total_calls = sum(d['call_count'] for d in results.values())
    total_errors = sum(d['exception_count'] for d in results.values())

    lines.append(f"Total: {total_time:.2f}ms across {total_calls} calls ({total_errors} errors)")

    return "\n".join(lines)


# =============================================================================
# Memory Leak Detection
# =============================================================================

class MemoryLeakDetector:
    """
    Detect potential memory leaks by tracking memory over time.

    Usage:
        detector = MemoryLeakDetector()

        # In your main loop or periodic task
        detector.record_sample(current_memory_mb)

        # Check for leaks
        result = detector.analyze()
        if result["has_potential_leak"]:
            logger.warning(f"Potential memory leak: {result['growth_mb']}MB growth")
    """

    def __init__(self, max_samples: int = 100, leak_threshold_mb: float = 10.0):
        """
        Args:
            max_samples: Maximum number of samples to keep
            leak_threshold_mb: Memory growth threshold to flag as potential leak
        """
        self.max_samples = max_samples
        self.leak_threshold_mb = leak_threshold_mb
        self._samples: list = []

    def record_sample(self, memory_mb: float):
        """Record a memory sample."""
        self._samples.append({
            "timestamp": time.time(),
            "memory_mb": memory_mb
        })

        # Keep only recent samples
        if len(self._samples) > self.max_samples:
            self._samples = self._samples[-self.max_samples:]

    def analyze(self) -> Dict[str, Any]:
        """
        Analyze memory samples for potential leaks.

        Returns:
            Dictionary with analysis results
        """
        if len(self._samples) < 2:
            return {
                "has_potential_leak": False,
                "growth_mb": 0,
                "samples": len(self._samples),
                "message": "Not enough samples"
            }

        first_memory = self._samples[0]["memory_mb"]
        last_memory = self._samples[-1]["memory_mb"]
        growth_mb = last_memory - first_memory

        # Check if there's consistent growth
        increasing_count = 0
        for i in range(1, len(self._samples)):
            if self._samples[i]["memory_mb"] > self._samples[i-1]["memory_mb"]:
                increasing_count += 1

        growth_ratio = increasing_count / (len(self._samples) - 1)

        has_leak = growth_mb > self.leak_threshold_mb and growth_ratio > 0.6

        return {
            "has_potential_leak": has_leak,
            "growth_mb": round(growth_mb, 2),
            "growth_ratio": round(growth_ratio, 2),
            "samples": len(self._samples),
            "first_mb": round(first_memory, 2),
            "last_mb": round(last_memory, 2),
            "message": "Potential leak detected" if has_leak else "Memory stable"
        }

    def reset(self):
        """Clear all samples."""
        self._samples.clear()


# =============================================================================
# Benchmark Runner
# =============================================================================

def run_benchmark(
    func: Callable,
    iterations: int = 100,
    warmup: int = 5
) -> Dict[str, Any]:
    """
    Run a synchronous function multiple times and collect timing statistics.

    Args:
        func: Function to benchmark (no arguments)
        iterations: Number of iterations
        warmup: Number of warmup iterations (not counted)

    Returns:
        Dictionary with timing statistics
    """
    # Warmup
    for _ in range(warmup):
        func()

    # Benchmark
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        func()
        duration = (time.perf_counter() - start) * 1000
        times.append(duration)

    times.sort()

    return {
        "iterations": iterations,
        "min_ms": round(min(times), 3),
        "max_ms": round(max(times), 3),
        "avg_ms": round(sum(times) / len(times), 3),
        "p50_ms": round(times[len(times) // 2], 3),
        "p95_ms": round(times[int(len(times) * 0.95)], 3),
        "p99_ms": round(times[int(len(times) * 0.99)], 3),
        "total_ms": round(sum(times), 3)
    }


async def run_async_benchmark(
    func: Callable,
    iterations: int = 100,
    warmup: int = 5
) -> Dict[str, Any]:
    """
    Run an async function multiple times and collect timing statistics.

    Args:
        func: Async function to benchmark (no arguments)
        iterations: Number of iterations
        warmup: Number of warmup iterations (not counted)

    Returns:
        Dictionary with timing statistics
    """
    # Warmup
    for _ in range(warmup):
        await func()

    # Benchmark
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        await func()
        duration = (time.perf_counter() - start) * 1000
        times.append(duration)

    times.sort()

    return {
        "iterations": iterations,
        "min_ms": round(min(times), 3),
        "max_ms": round(max(times), 3),
        "avg_ms": round(sum(times) / len(times), 3),
        "p50_ms": round(times[len(times) // 2], 3),
        "p95_ms": round(times[int(len(times) * 0.95)], 3) if len(times) >= 20 else None,
        "p99_ms": round(times[int(len(times) * 0.99)], 3) if len(times) >= 100 else None,
        "total_ms": round(sum(times), 3)
    }