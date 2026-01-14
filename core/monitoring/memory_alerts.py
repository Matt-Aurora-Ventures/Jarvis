"""
JARVIS Memory Usage Alerts

Monitors system and process memory usage with configurable alerts.
"""

import asyncio
import os
import gc
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Any, Awaitable
from collections import deque

logger = logging.getLogger(__name__)

# Try to import psutil for system metrics
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    logger.warning("psutil not installed, memory monitoring will be limited")


class MemoryAlertLevel(Enum):
    """Memory alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class MemorySnapshot:
    """Point-in-time memory usage snapshot."""
    timestamp: datetime
    process_rss_mb: float  # Resident Set Size
    process_vms_mb: float  # Virtual Memory Size
    system_used_mb: float
    system_available_mb: float
    system_percent: float
    gc_objects: int


@dataclass
class MemoryAlert:
    """Memory usage alert."""
    level: MemoryAlertLevel
    message: str
    timestamp: datetime
    process_rss_mb: float
    system_percent: float
    threshold_value: float
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryThresholds:
    """Configurable memory thresholds."""
    process_rss_warning_mb: float = 500.0
    process_rss_critical_mb: float = 1000.0
    process_rss_emergency_mb: float = 2000.0
    system_percent_warning: float = 70.0
    system_percent_critical: float = 85.0
    system_percent_emergency: float = 95.0
    growth_rate_warning_mb_per_hour: float = 100.0
    gc_objects_warning: int = 1_000_000


@dataclass
class MemoryStats:
    """Memory usage statistics over a period."""
    current: MemorySnapshot
    avg_rss_mb: float
    max_rss_mb: float
    min_rss_mb: float
    growth_rate_mb_per_hour: float
    gc_collections: Dict[int, int]
    alert_count: int


class MemoryMonitor:
    """Monitors memory usage and generates alerts."""

    def __init__(
        self,
        thresholds: Optional[MemoryThresholds] = None,
        check_interval_seconds: int = 60,
        history_size: int = 60,  # 1 hour of history at 1-minute intervals
    ):
        self.thresholds = thresholds or MemoryThresholds()
        self.check_interval = check_interval_seconds
        self.history_size = history_size

        self._history: deque[MemorySnapshot] = deque(maxlen=history_size)
        self._alerts: List[MemoryAlert] = []
        self._running = False
        self._task: Optional[asyncio.Task] = None

        # Callbacks
        self._alert_callbacks: List[Callable[[MemoryAlert], Awaitable[None]]] = []

        # GC tracking
        self._last_gc_stats: Dict[int, int] = {0: 0, 1: 0, 2: 0}

        # Get process for monitoring
        if HAS_PSUTIL:
            self._process = psutil.Process(os.getpid())
        else:
            self._process = None

    def on_alert(
        self,
        callback: Callable[[MemoryAlert], Awaitable[None]]
    ) -> None:
        """Register callback for memory alerts."""
        self._alert_callbacks.append(callback)

    async def start(self) -> None:
        """Start the memory monitor."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Memory monitor started")

    async def stop(self) -> None:
        """Stop the memory monitor."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Memory monitor stopped")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                snapshot = self._take_snapshot()
                self._history.append(snapshot)
                await self._check_alerts(snapshot)
            except Exception as e:
                logger.error(f"Memory monitoring error: {e}")

            await asyncio.sleep(self.check_interval)

    def _take_snapshot(self) -> MemorySnapshot:
        """Take a memory usage snapshot."""
        now = datetime.utcnow()

        if HAS_PSUTIL and self._process:
            # Process memory
            mem_info = self._process.memory_info()
            process_rss = mem_info.rss / (1024 * 1024)  # MB
            process_vms = mem_info.vms / (1024 * 1024)  # MB

            # System memory
            sys_mem = psutil.virtual_memory()
            system_used = sys_mem.used / (1024 * 1024)
            system_available = sys_mem.available / (1024 * 1024)
            system_percent = sys_mem.percent
        else:
            # Fallback without psutil
            import sys
            # Rough estimate using gc
            process_rss = 0.0
            process_vms = 0.0
            system_used = 0.0
            system_available = 0.0
            system_percent = 0.0

        return MemorySnapshot(
            timestamp=now,
            process_rss_mb=process_rss,
            process_vms_mb=process_vms,
            system_used_mb=system_used,
            system_available_mb=system_available,
            system_percent=system_percent,
            gc_objects=len(gc.get_objects())
        )

    async def _check_alerts(self, snapshot: MemorySnapshot) -> None:
        """Check thresholds and generate alerts."""
        alerts = []

        # Process RSS alerts
        if snapshot.process_rss_mb >= self.thresholds.process_rss_emergency_mb:
            alerts.append(MemoryAlert(
                level=MemoryAlertLevel.EMERGENCY,
                message=f"EMERGENCY: Process memory at {snapshot.process_rss_mb:.1f}MB",
                timestamp=snapshot.timestamp,
                process_rss_mb=snapshot.process_rss_mb,
                system_percent=snapshot.system_percent,
                threshold_value=self.thresholds.process_rss_emergency_mb
            ))
        elif snapshot.process_rss_mb >= self.thresholds.process_rss_critical_mb:
            alerts.append(MemoryAlert(
                level=MemoryAlertLevel.CRITICAL,
                message=f"CRITICAL: Process memory at {snapshot.process_rss_mb:.1f}MB",
                timestamp=snapshot.timestamp,
                process_rss_mb=snapshot.process_rss_mb,
                system_percent=snapshot.system_percent,
                threshold_value=self.thresholds.process_rss_critical_mb
            ))
        elif snapshot.process_rss_mb >= self.thresholds.process_rss_warning_mb:
            alerts.append(MemoryAlert(
                level=MemoryAlertLevel.WARNING,
                message=f"WARNING: Process memory at {snapshot.process_rss_mb:.1f}MB",
                timestamp=snapshot.timestamp,
                process_rss_mb=snapshot.process_rss_mb,
                system_percent=snapshot.system_percent,
                threshold_value=self.thresholds.process_rss_warning_mb
            ))

        # System memory alerts
        if snapshot.system_percent >= self.thresholds.system_percent_emergency:
            alerts.append(MemoryAlert(
                level=MemoryAlertLevel.EMERGENCY,
                message=f"EMERGENCY: System memory at {snapshot.system_percent:.1f}%",
                timestamp=snapshot.timestamp,
                process_rss_mb=snapshot.process_rss_mb,
                system_percent=snapshot.system_percent,
                threshold_value=self.thresholds.system_percent_emergency
            ))
        elif snapshot.system_percent >= self.thresholds.system_percent_critical:
            alerts.append(MemoryAlert(
                level=MemoryAlertLevel.CRITICAL,
                message=f"CRITICAL: System memory at {snapshot.system_percent:.1f}%",
                timestamp=snapshot.timestamp,
                process_rss_mb=snapshot.process_rss_mb,
                system_percent=snapshot.system_percent,
                threshold_value=self.thresholds.system_percent_critical
            ))
        elif snapshot.system_percent >= self.thresholds.system_percent_warning:
            alerts.append(MemoryAlert(
                level=MemoryAlertLevel.WARNING,
                message=f"WARNING: System memory at {snapshot.system_percent:.1f}%",
                timestamp=snapshot.timestamp,
                process_rss_mb=snapshot.process_rss_mb,
                system_percent=snapshot.system_percent,
                threshold_value=self.thresholds.system_percent_warning
            ))

        # Growth rate alert
        growth_rate = self._calculate_growth_rate()
        if growth_rate >= self.thresholds.growth_rate_warning_mb_per_hour:
            alerts.append(MemoryAlert(
                level=MemoryAlertLevel.WARNING,
                message=f"Memory growing at {growth_rate:.1f}MB/hour",
                timestamp=snapshot.timestamp,
                process_rss_mb=snapshot.process_rss_mb,
                system_percent=snapshot.system_percent,
                threshold_value=self.thresholds.growth_rate_warning_mb_per_hour,
                details={"growth_rate_mb_per_hour": growth_rate}
            ))

        # GC objects alert
        if snapshot.gc_objects >= self.thresholds.gc_objects_warning:
            alerts.append(MemoryAlert(
                level=MemoryAlertLevel.INFO,
                message=f"High GC object count: {snapshot.gc_objects:,}",
                timestamp=snapshot.timestamp,
                process_rss_mb=snapshot.process_rss_mb,
                system_percent=snapshot.system_percent,
                threshold_value=self.thresholds.gc_objects_warning,
                details={"gc_objects": snapshot.gc_objects}
            ))

        # Process alerts
        for alert in alerts:
            self._alerts.append(alert)
            logger.log(
                logging.CRITICAL if alert.level == MemoryAlertLevel.EMERGENCY
                else logging.ERROR if alert.level == MemoryAlertLevel.CRITICAL
                else logging.WARNING if alert.level == MemoryAlertLevel.WARNING
                else logging.INFO,
                alert.message
            )

            # Notify callbacks
            for callback in self._alert_callbacks:
                try:
                    await callback(alert)
                except Exception as e:
                    logger.error(f"Alert callback error: {e}")

    def _calculate_growth_rate(self) -> float:
        """Calculate memory growth rate in MB per hour."""
        if len(self._history) < 2:
            return 0.0

        oldest = self._history[0]
        newest = self._history[-1]

        time_diff_hours = (newest.timestamp - oldest.timestamp).total_seconds() / 3600
        if time_diff_hours < 0.01:  # Less than 36 seconds
            return 0.0

        memory_diff = newest.process_rss_mb - oldest.process_rss_mb
        return memory_diff / time_diff_hours

    def get_current_snapshot(self) -> MemorySnapshot:
        """Get current memory snapshot."""
        return self._take_snapshot()

    def get_stats(self) -> MemoryStats:
        """Get memory statistics."""
        current = self.get_current_snapshot()

        if not self._history:
            return MemoryStats(
                current=current,
                avg_rss_mb=current.process_rss_mb,
                max_rss_mb=current.process_rss_mb,
                min_rss_mb=current.process_rss_mb,
                growth_rate_mb_per_hour=0.0,
                gc_collections=self._get_gc_stats(),
                alert_count=len(self._alerts)
            )

        rss_values = [s.process_rss_mb for s in self._history]

        return MemoryStats(
            current=current,
            avg_rss_mb=sum(rss_values) / len(rss_values),
            max_rss_mb=max(rss_values),
            min_rss_mb=min(rss_values),
            growth_rate_mb_per_hour=self._calculate_growth_rate(),
            gc_collections=self._get_gc_stats(),
            alert_count=len(self._alerts)
        )

    def _get_gc_stats(self) -> Dict[int, int]:
        """Get garbage collection statistics."""
        stats = gc.get_stats()
        return {
            i: stats[i]["collections"]
            for i in range(len(stats))
        }

    def get_alerts(
        self,
        level: Optional[MemoryAlertLevel] = None,
        since: Optional[datetime] = None,
        limit: int = 50
    ) -> List[MemoryAlert]:
        """Get memory alerts."""
        alerts = self._alerts

        if level:
            alerts = [a for a in alerts if a.level == level]

        if since:
            alerts = [a for a in alerts if a.timestamp >= since]

        return sorted(alerts, key=lambda a: a.timestamp, reverse=True)[:limit]

    def force_gc(self) -> Dict[str, Any]:
        """Force garbage collection and return stats."""
        before = self.get_current_snapshot()

        # Force full collection
        gc.collect(0)
        gc.collect(1)
        gc.collect(2)

        after = self.get_current_snapshot()

        return {
            "before_rss_mb": before.process_rss_mb,
            "after_rss_mb": after.process_rss_mb,
            "freed_mb": before.process_rss_mb - after.process_rss_mb,
            "before_gc_objects": before.gc_objects,
            "after_gc_objects": after.gc_objects,
            "objects_freed": before.gc_objects - after.gc_objects
        }

    def get_top_memory_objects(self, top_n: int = 10) -> List[Dict[str, Any]]:
        """Get types using the most memory."""
        import sys
        from collections import Counter

        type_counts: Counter = Counter()
        type_sizes: Dict[str, int] = {}

        for obj in gc.get_objects():
            obj_type = type(obj).__name__
            type_counts[obj_type] += 1
            try:
                size = sys.getsizeof(obj)
                type_sizes[obj_type] = type_sizes.get(obj_type, 0) + size
            except TypeError:
                pass

        # Sort by total size
        sorted_types = sorted(
            type_sizes.items(),
            key=lambda x: x[1],
            reverse=True
        )[:top_n]

        return [
            {
                "type": name,
                "count": type_counts[name],
                "total_size_mb": size / (1024 * 1024)
            }
            for name, size in sorted_types
        ]


# Global instance
_memory_monitor: Optional[MemoryMonitor] = None


def get_memory_monitor() -> MemoryMonitor:
    """Get the global memory monitor instance."""
    global _memory_monitor
    if _memory_monitor is None:
        _memory_monitor = MemoryMonitor()
    return _memory_monitor


# Decorator for memory-sensitive operations
def memory_check(
    max_rss_mb: float = 1000.0,
    raise_on_exceed: bool = False
):
    """Decorator to check memory before/after operations."""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            monitor = get_memory_monitor()
            before = monitor.get_current_snapshot()

            if before.process_rss_mb > max_rss_mb:
                if raise_on_exceed:
                    raise MemoryError(
                        f"Memory usage ({before.process_rss_mb:.1f}MB) "
                        f"exceeds limit ({max_rss_mb:.1f}MB)"
                    )
                logger.warning(
                    f"High memory before {func.__name__}: {before.process_rss_mb:.1f}MB"
                )

            result = await func(*args, **kwargs)

            after = monitor.get_current_snapshot()
            growth = after.process_rss_mb - before.process_rss_mb
            if growth > 50:  # More than 50MB growth
                logger.warning(
                    f"{func.__name__} increased memory by {growth:.1f}MB"
                )

            return result

        def sync_wrapper(*args, **kwargs):
            monitor = get_memory_monitor()
            before = monitor.get_current_snapshot()

            if before.process_rss_mb > max_rss_mb:
                if raise_on_exceed:
                    raise MemoryError(
                        f"Memory usage ({before.process_rss_mb:.1f}MB) "
                        f"exceeds limit ({max_rss_mb:.1f}MB)"
                    )
                logger.warning(
                    f"High memory before {func.__name__}: {before.process_rss_mb:.1f}MB"
                )

            result = func(*args, **kwargs)

            after = monitor.get_current_snapshot()
            growth = after.process_rss_mb - before.process_rss_mb
            if growth > 50:
                logger.warning(
                    f"{func.__name__} increased memory by {growth:.1f}MB"
                )

            return result

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
