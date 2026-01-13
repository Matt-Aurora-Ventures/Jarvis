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
