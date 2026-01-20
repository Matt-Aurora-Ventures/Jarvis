"""Memory monitoring and leak detection."""
import gc
import sys
import tracemalloc
import weakref
from typing import Dict, Any, List, Optional, Set, Callable
from dataclasses import dataclass
from collections import defaultdict
import threading
import time
import logging

logger = logging.getLogger(__name__)


@dataclass
class MemorySnapshot:
    """Point-in-time memory snapshot."""
    timestamp: float
    rss_mb: float
    heap_mb: float
    gc_counts: tuple
    object_counts: Dict[str, int]
    top_allocations: List[tuple]


@dataclass
class MemoryAlert:
    """Memory alert notification."""
    severity: str  # "warning", "critical"
    message: str
    timestamp: float
    details: Dict[str, Any]


class MemoryMonitor:
    """Monitor memory usage and detect leaks."""

    def __init__(self, snapshot_interval: float = 60.0,
                 warning_threshold_mb: float = 500.0,
                 critical_threshold_mb: float = 1000.0):
        self.snapshot_interval = snapshot_interval
        self.warning_threshold_mb = warning_threshold_mb
        self.critical_threshold_mb = critical_threshold_mb
        self.snapshots: List[MemorySnapshot] = []
        self.baseline: Optional[MemorySnapshot] = None
        self._tracking = False
        self._tracked_objects: weakref.WeakSet = weakref.WeakSet()
        self._allocation_sites: Dict[str, int] = defaultdict(int)
        self._alerts: List[MemoryAlert] = []
        self._alert_callbacks: List[Callable[[MemoryAlert], None]] = []
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_monitoring = threading.Event()
    
    def start_tracking(self):
        """Start memory tracking."""
        if self._tracking:
            return
        
        tracemalloc.start(25)  # 25 frames deep
        self._tracking = True
        self.baseline = self.take_snapshot()
        logger.info("Memory tracking started")
    
    def stop_tracking(self):
        """Stop memory tracking."""
        if not self._tracking:
            return
        
        tracemalloc.stop()
        self._tracking = False
        logger.info("Memory tracking stopped")
    
    def take_snapshot(self) -> MemorySnapshot:
        """Take a memory snapshot."""
        import psutil
        process = psutil.Process()
        
        # Get memory info
        mem_info = process.memory_info()
        rss_mb = mem_info.rss / 1024 / 1024
        
        # Get heap info from tracemalloc
        heap_mb = 0
        top_allocations = []
        if tracemalloc.is_tracing():
            current, peak = tracemalloc.get_traced_memory()
            heap_mb = current / 1024 / 1024
            
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')[:10]
            top_allocations = [
                (str(stat.traceback), stat.size / 1024)
                for stat in top_stats
            ]
        
        # Get object counts by type
        object_counts = defaultdict(int)
        for obj in gc.get_objects():
            object_counts[type(obj).__name__] += 1
        
        # Get top object types
        top_objects = dict(sorted(
            object_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:20])
        
        snapshot = MemorySnapshot(
            timestamp=time.time(),
            rss_mb=rss_mb,
            heap_mb=heap_mb,
            gc_counts=gc.get_count(),
            object_counts=top_objects,
            top_allocations=top_allocations
        )
        
        self.snapshots.append(snapshot)
        
        # Keep only last 100 snapshots
        if len(self.snapshots) > 100:
            self.snapshots = self.snapshots[-100:]
        
        return snapshot
    
    def detect_leaks(self) -> List[Dict[str, Any]]:
        """Detect potential memory leaks by comparing snapshots."""
        if len(self.snapshots) < 2:
            return []
        
        leaks = []
        first = self.snapshots[0]
        last = self.snapshots[-1]
        
        # Check for growing memory
        memory_growth = last.rss_mb - first.rss_mb
        if memory_growth > 100:  # >100MB growth
            leaks.append({
                "type": "memory_growth",
                "severity": "high" if memory_growth > 500 else "medium",
                "details": f"RSS grew by {memory_growth:.1f}MB"
            })
        
        # Check for growing object counts
        for obj_type, count in last.object_counts.items():
            if obj_type in first.object_counts:
                growth = count - first.object_counts[obj_type]
                growth_pct = growth / max(first.object_counts[obj_type], 1) * 100
                
                if growth > 10000 and growth_pct > 50:
                    leaks.append({
                        "type": "object_growth",
                        "severity": "medium",
                        "details": f"{obj_type} grew by {growth} ({growth_pct:.0f}%)"
                    })
        
        return leaks
    
    def force_gc(self) -> Dict[str, int]:
        """Force garbage collection and return stats."""
        before = gc.get_count()
        collected = gc.collect()
        after = gc.get_count()
        
        return {
            "collected": collected,
            "before": before,
            "after": after
        }
    
    def get_object_referrers(self, obj_type: str, limit: int = 5) -> List[str]:
        """Find what's holding references to objects of a type."""
        referrers = []
        
        for obj in gc.get_objects():
            if type(obj).__name__ == obj_type:
                refs = gc.get_referrers(obj)
                for ref in refs[:limit]:
                    ref_info = f"{type(ref).__name__}"
                    if hasattr(ref, '__name__'):
                        ref_info += f" ({ref.__name__})"
                    referrers.append(ref_info)
                break
        
        return referrers[:limit]
    
    def register_alert_callback(self, callback: Callable[[MemoryAlert], None]):
        """Register a callback to be notified of memory alerts."""
        self._alert_callbacks.append(callback)

    def _trigger_alert(self, severity: str, message: str, details: Dict[str, Any]):
        """Trigger a memory alert."""
        alert = MemoryAlert(
            severity=severity,
            message=message,
            timestamp=time.time(),
            details=details
        )
        self._alerts.append(alert)

        # Keep only last 100 alerts
        if len(self._alerts) > 100:
            self._alerts = self._alerts[-100:]

        logger.log(
            logging.WARNING if severity == "warning" else logging.ERROR,
            f"Memory alert [{severity}]: {message}"
        )

        # Notify callbacks
        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")

    def check_thresholds(self):
        """Check if memory usage exceeds thresholds and trigger alerts."""
        if not self.snapshots or not self.baseline:
            return

        latest = self.snapshots[-1]
        growth = latest.rss_mb - self.baseline.rss_mb

        if growth > self.critical_threshold_mb:
            self._trigger_alert(
                severity="critical",
                message=f"Memory growth exceeded {self.critical_threshold_mb}MB",
                details={
                    "current_mb": latest.rss_mb,
                    "baseline_mb": self.baseline.rss_mb,
                    "growth_mb": growth
                }
            )
        elif growth > self.warning_threshold_mb:
            self._trigger_alert(
                severity="warning",
                message=f"Memory growth exceeded {self.warning_threshold_mb}MB",
                details={
                    "current_mb": latest.rss_mb,
                    "baseline_mb": self.baseline.rss_mb,
                    "growth_mb": growth
                }
            )

    def start_background_monitoring(self):
        """Start background monitoring thread."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            logger.warning("Background monitoring already running")
            return

        self._stop_monitoring.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True,
            name="memory-monitor"
        )
        self._monitor_thread.start()
        logger.info("Background memory monitoring started")

    def stop_background_monitoring(self):
        """Stop background monitoring thread."""
        if not self._monitor_thread:
            return

        self._stop_monitoring.set()
        self._monitor_thread.join(timeout=5.0)
        logger.info("Background memory monitoring stopped")

    def _monitoring_loop(self):
        """Background monitoring loop."""
        while not self._stop_monitoring.is_set():
            try:
                snapshot = self.take_snapshot()
                self.check_thresholds()
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")

            self._stop_monitoring.wait(self.snapshot_interval)

    def get_alerts(self, since: Optional[float] = None, severity: Optional[str] = None) -> List[MemoryAlert]:
        """Get recent alerts."""
        alerts = self._alerts

        if since is not None:
            alerts = [a for a in alerts if a.timestamp >= since]

        if severity is not None:
            alerts = [a for a in alerts if a.severity == severity]

        return alerts

    def clear_alerts(self):
        """Clear all alerts."""
        self._alerts.clear()

    def get_memory_trend(self, window_minutes: int = 60) -> Dict[str, Any]:
        """Get memory trend over time window."""
        if not self.snapshots:
            return {"trend": "unknown", "samples": 0}

        cutoff = time.time() - (window_minutes * 60)
        recent = [s for s in self.snapshots if s.timestamp >= cutoff]

        if len(recent) < 2:
            return {"trend": "insufficient_data", "samples": len(recent)}

        first = recent[0]
        last = recent[-1]
        growth_mb = last.rss_mb - first.rss_mb
        growth_rate_mb_per_min = growth_mb / window_minutes

        trend = "stable"
        if growth_rate_mb_per_min > 1.0:
            trend = "increasing"
        elif growth_rate_mb_per_min < -1.0:
            trend = "decreasing"

        return {
            "trend": trend,
            "samples": len(recent),
            "window_minutes": window_minutes,
            "first_mb": first.rss_mb,
            "last_mb": last.rss_mb,
            "growth_mb": growth_mb,
            "growth_rate_mb_per_min": growth_rate_mb_per_min
        }

    def get_report(self) -> str:
        """Generate memory report."""
        if not self.snapshots:
            return "No snapshots available"

        latest = self.snapshots[-1]
        lines = [
            "Memory Report",
            "=" * 50,
            f"RSS: {latest.rss_mb:.1f}MB",
            f"Heap: {latest.heap_mb:.1f}MB",
            f"GC counts: {latest.gc_counts}",
            "",
            "Top Object Types:",
        ]

        for obj_type, count in list(latest.object_counts.items())[:10]:
            lines.append(f"  {obj_type}: {count:,}")

        if latest.top_allocations:
            lines.extend(["", "Top Allocations:"])
            for trace, size_kb in latest.top_allocations[:5]:
                lines.append(f"  {size_kb:.1f}KB: {trace[:80]}")

        leaks = self.detect_leaks()
        if leaks:
            lines.extend(["", "Potential Leaks:"])
            for leak in leaks:
                lines.append(f"  [{leak['severity']}] {leak['details']}")

        # Add trend
        trend = self.get_memory_trend()
        if trend["trend"] != "unknown":
            lines.extend(["", f"Trend (60min): {trend['trend']} ({trend['growth_rate_mb_per_min']:.2f} MB/min)"])

        # Add alerts
        recent_alerts = self.get_alerts(since=time.time() - 3600)
        if recent_alerts:
            lines.extend(["", "Recent Alerts (1h):"])
            for alert in recent_alerts[-5:]:
                lines.append(f"  [{alert.severity}] {alert.message}")

        return "\n".join(lines)


# Global monitor instance
memory_monitor = MemoryMonitor()
