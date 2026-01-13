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
def timed_block(name: str, log_level: int = logging.DEBUG):
    """Simple timing context manager."""
    start = time.perf_counter()
    try:
        yield
    finally:
        duration = (time.perf_counter() - start) * 1000
        logger.log(log_level, f"{name}: {duration:.2f}ms")
