"""
Memory Leak Detection and Tracking
Reliability Audit Item #9: System-wide memory leak detection

Monitors:
- Object counts by type
- Cache sizes across modules
- Memory usage trends
- GC statistics
"""

import gc
import logging
import os
import sys
import time
import tracemalloc
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set
import threading
import weakref

logger = logging.getLogger("jarvis.monitoring.memory")


@dataclass
class MemorySnapshot:
    """Point-in-time memory state"""
    timestamp: datetime
    rss_mb: float
    heap_mb: float
    object_counts: Dict[str, int]
    cache_sizes: Dict[str, int]
    gc_counts: tuple
    top_allocations: List[tuple] = field(default_factory=list)


@dataclass
class MemoryAlert:
    """Memory threshold alert"""
    alert_type: str
    message: str
    current_value: float
    threshold: float
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


class CacheRegistry:
    """Registry for tracking cache objects across the system"""

    def __init__(self):
        self._caches: Dict[str, weakref.ref] = {}
        self._size_funcs: Dict[str, Callable] = {}
        self._lock = threading.Lock()

    def register(
        self,
        name: str,
        cache_obj: Any,
        size_func: Optional[Callable] = None
    ):
        """Register a cache for monitoring"""
        with self._lock:
            self._caches[name] = weakref.ref(cache_obj)
            if size_func:
                self._size_funcs[name] = size_func
            elif hasattr(cache_obj, '__len__'):
                self._size_funcs[name] = lambda c=cache_obj: len(c)
            else:
                self._size_funcs[name] = lambda: 0

    def unregister(self, name: str):
        """Remove cache from monitoring"""
        with self._lock:
            self._caches.pop(name, None)
            self._size_funcs.pop(name, None)

    def get_sizes(self) -> Dict[str, int]:
        """Get current sizes of all registered caches"""
        sizes = {}
        with self._lock:
            for name, ref in list(self._caches.items()):
                obj = ref()
                if obj is None:
                    del self._caches[name]
                    self._size_funcs.pop(name, None)
                    continue
                try:
                    size_func = self._size_funcs.get(name)
                    if size_func:
                        sizes[name] = size_func()
                    elif hasattr(obj, '__len__'):
                        sizes[name] = len(obj)
                except Exception:
                    sizes[name] = -1
        return sizes


class MemoryLeakTracker:
    """
    System-wide memory leak detection.

    Features:
    - Periodic memory snapshots
    - Object count tracking by type
    - Cache size monitoring
    - Growth rate detection
    - Alerting on thresholds
    """

    def __init__(
        self,
        snapshot_interval_sec: float = 300,  # 5 minutes
        rss_threshold_mb: float = 1024,  # 1GB
        growth_rate_threshold: float = 0.1,  # 10% per interval
        max_snapshots: int = 288,  # 24 hours at 5min intervals
    ):
        self.snapshot_interval = snapshot_interval_sec
        self.rss_threshold_mb = rss_threshold_mb
        self.growth_rate_threshold = growth_rate_threshold
        self.max_snapshots = max_snapshots

        self._snapshots: List[MemorySnapshot] = []
        self._alerts: List[MemoryAlert] = []
        self._alert_callbacks: List[Callable[[MemoryAlert], None]] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        self.cache_registry = CacheRegistry()
        self._tracked_types: Set[str] = {
            'dict', 'list', 'set', 'tuple',
            'function', 'method', 'frame',
            'asyncio.Task', 'coroutine',
        }

        # Enable tracemalloc for detailed tracking
        if not tracemalloc.is_tracing():
            tracemalloc.start(10)  # Store 10 frames

    def start(self):
        """Start background monitoring"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="MemoryLeakTracker"
        )
        self._thread.start()
        logger.info("Memory leak tracker started")

    def stop(self):
        """Stop background monitoring"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Memory leak tracker stopped")

    def _monitor_loop(self):
        """Background monitoring loop"""
        while self._running:
            try:
                snapshot = self.take_snapshot()
                self._check_thresholds(snapshot)
                self._check_growth_rate()
            except Exception as e:
                logger.error(f"Memory monitoring error: {e}")

            time.sleep(self.snapshot_interval)

    def take_snapshot(self) -> MemorySnapshot:
        """Take a memory snapshot"""
        import psutil

        process = psutil.Process()
        mem_info = process.memory_info()

        # Get object counts
        gc.collect()
        object_counts = self._get_object_counts()

        # Get cache sizes
        cache_sizes = self.cache_registry.get_sizes()

        # Get top allocations from tracemalloc
        top_allocs = []
        if tracemalloc.is_tracing():
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')[:10]
            top_allocs = [
                (str(stat.traceback), stat.size)
                for stat in top_stats
            ]

        snapshot = MemorySnapshot(
            timestamp=datetime.now(timezone.utc),
            rss_mb=mem_info.rss / (1024 * 1024),
            heap_mb=mem_info.vms / (1024 * 1024),
            object_counts=object_counts,
            cache_sizes=cache_sizes,
            gc_counts=gc.get_count(),
            top_allocations=top_allocs,
        )

        with self._lock:
            self._snapshots.append(snapshot)
            if len(self._snapshots) > self.max_snapshots:
                self._snapshots.pop(0)

        return snapshot

    def _get_object_counts(self) -> Dict[str, int]:
        """Count objects by type"""
        counts: Dict[str, int] = {}

        for obj in gc.get_objects():
            type_name = type(obj).__name__
            if type_name in self._tracked_types or len(counts) < 50:
                counts[type_name] = counts.get(type_name, 0) + 1

        return dict(sorted(counts.items(), key=lambda x: -x[1])[:20])

    def _check_thresholds(self, snapshot: MemorySnapshot):
        """Check memory thresholds and create alerts"""
        # RSS threshold
        if snapshot.rss_mb > self.rss_threshold_mb:
            alert = MemoryAlert(
                alert_type="rss_exceeded",
                message=f"RSS memory {snapshot.rss_mb:.1f}MB exceeds threshold {self.rss_threshold_mb}MB",
                current_value=snapshot.rss_mb,
                threshold=self.rss_threshold_mb,
                timestamp=snapshot.timestamp,
            )
            self._emit_alert(alert)

        # Check for large cache sizes
        for cache_name, size in snapshot.cache_sizes.items():
            if size > 10000:  # Arbitrary large cache threshold
                alert = MemoryAlert(
                    alert_type="large_cache",
                    message=f"Cache '{cache_name}' has {size} entries",
                    current_value=size,
                    threshold=10000,
                    timestamp=snapshot.timestamp,
                    metadata={"cache_name": cache_name},
                )
                self._emit_alert(alert)

    def _check_growth_rate(self):
        """Check for suspicious memory growth"""
        with self._lock:
            if len(self._snapshots) < 2:
                return

            recent = self._snapshots[-1]
            previous = self._snapshots[-2]

        if previous.rss_mb > 0:
            growth_rate = (recent.rss_mb - previous.rss_mb) / previous.rss_mb

            if growth_rate > self.growth_rate_threshold:
                alert = MemoryAlert(
                    alert_type="rapid_growth",
                    message=f"Memory grew {growth_rate*100:.1f}% in {self.snapshot_interval}s",
                    current_value=growth_rate,
                    threshold=self.growth_rate_threshold,
                    timestamp=recent.timestamp,
                    metadata={
                        "previous_mb": previous.rss_mb,
                        "current_mb": recent.rss_mb,
                    },
                )
                self._emit_alert(alert)

    def _emit_alert(self, alert: MemoryAlert):
        """Store and emit alert"""
        with self._lock:
            self._alerts.append(alert)
            if len(self._alerts) > 1000:
                self._alerts.pop(0)

        logger.warning(f"Memory alert: {alert.message}")

        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")

    def on_alert(self, callback: Callable[[MemoryAlert], None]):
        """Register alert callback"""
        self._alert_callbacks.append(callback)

    def get_recent_snapshots(self, count: int = 10) -> List[MemorySnapshot]:
        """Get recent snapshots"""
        with self._lock:
            return self._snapshots[-count:]

    def get_alerts(self, since: Optional[datetime] = None) -> List[MemoryAlert]:
        """Get alerts, optionally filtered by time"""
        with self._lock:
            if since is None:
                return self._alerts.copy()
            return [a for a in self._alerts if a.timestamp >= since]

    def get_memory_trend(self) -> Dict[str, Any]:
        """Analyze memory trend over available snapshots"""
        with self._lock:
            if len(self._snapshots) < 2:
                return {"status": "insufficient_data"}

            rss_values = [s.rss_mb for s in self._snapshots]

        min_rss = min(rss_values)
        max_rss = max(rss_values)
        avg_rss = sum(rss_values) / len(rss_values)

        # Simple trend detection
        first_half_avg = sum(rss_values[:len(rss_values)//2]) / (len(rss_values)//2)
        second_half_avg = sum(rss_values[len(rss_values)//2:]) / (len(rss_values) - len(rss_values)//2)

        if second_half_avg > first_half_avg * 1.2:
            trend = "increasing"
        elif second_half_avg < first_half_avg * 0.8:
            trend = "decreasing"
        else:
            trend = "stable"

        return {
            "status": "ok",
            "trend": trend,
            "min_mb": min_rss,
            "max_mb": max_rss,
            "avg_mb": avg_rss,
            "current_mb": rss_values[-1],
            "samples": len(rss_values),
            "span_hours": (
                self._snapshots[-1].timestamp - self._snapshots[0].timestamp
            ).total_seconds() / 3600,
        }

    def force_gc(self) -> Dict[str, int]:
        """Force garbage collection and return stats"""
        before = gc.get_count()
        collected = gc.collect()
        after = gc.get_count()

        return {
            "collected": collected,
            "before_gen0": before[0],
            "before_gen1": before[1],
            "before_gen2": before[2],
            "after_gen0": after[0],
            "after_gen1": after[1],
            "after_gen2": after[2],
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get summary for health dashboard"""
        with self._lock:
            latest = self._snapshots[-1] if self._snapshots else None
            alert_count = len(self._alerts)

        if latest is None:
            return {
                "status": "no_data",
                "message": "No memory snapshots available",
            }

        trend = self.get_memory_trend()

        return {
            "status": "ok" if alert_count == 0 else "warning",
            "current_rss_mb": latest.rss_mb,
            "trend": trend.get("trend", "unknown"),
            "gc_counts": latest.gc_counts,
            "object_counts": latest.object_counts,
            "cache_sizes": latest.cache_sizes,
            "alert_count": alert_count,
            "snapshot_count": len(self._snapshots),
        }


# =============================================================================
# SINGLETON
# =============================================================================

_tracker: Optional[MemoryLeakTracker] = None


def get_memory_tracker() -> MemoryLeakTracker:
    """Get or create the memory tracker singleton"""
    global _tracker
    if _tracker is None:
        _tracker = MemoryLeakTracker()
    return _tracker


def start_memory_tracking():
    """Start background memory tracking"""
    tracker = get_memory_tracker()
    tracker.start()
    return tracker


def register_cache(name: str, cache_obj: Any, size_func: Optional[Callable] = None):
    """Register a cache for monitoring"""
    tracker = get_memory_tracker()
    tracker.cache_registry.register(name, cache_obj, size_func)
