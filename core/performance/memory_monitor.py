"""Memory monitoring and leak detection."""
import gc
import sys
import tracemalloc
import weakref
from typing import Dict, Any, List, Optional, Set
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


class MemoryMonitor:
    """Monitor memory usage and detect leaks."""
    
    def __init__(self, snapshot_interval: float = 60.0):
        self.snapshot_interval = snapshot_interval
        self.snapshots: List[MemorySnapshot] = []
        self.baseline: Optional[MemorySnapshot] = None
        self._tracking = False
        self._tracked_objects: weakref.WeakSet = weakref.WeakSet()
        self._allocation_sites: Dict[str, int] = defaultdict(int)
    
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
        
        return "\n".join(lines)


# Global monitor instance
memory_monitor = MemoryMonitor()
