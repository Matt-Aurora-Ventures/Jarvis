"""
JARVIS Metrics Collector

Advanced metrics collection with:
- Error rate tracking and alerts
- Latency percentile tracking (p50, p95, p99)
- Sliding window statistics
- Automatic anomaly detection
- Integration with alerting system

Usage:
    from core.monitoring.metrics_collector import get_metrics_collector

    collector = get_metrics_collector()
    collector.record_request("api", "/endpoint", 150, success=True)

    # Get stats
    stats = collector.get_error_rate("api")
    latency = collector.get_latency_percentiles("api")
"""

import asyncio
import bisect
import logging
import os
import sqlite3
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

logger = logging.getLogger("jarvis.monitoring.metrics")


# =============================================================================
# MODELS
# =============================================================================

@dataclass
class RequestMetric:
    """A single request metric"""
    timestamp: float
    component: str
    endpoint: str
    latency_ms: float
    success: bool
    error_type: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ErrorRateStats:
    """Error rate statistics"""
    component: str
    window_seconds: int
    total_requests: int
    failed_requests: int
    error_rate: float
    error_types: Dict[str, int]
    timestamp: datetime


@dataclass
class LatencyStats:
    """Latency statistics with percentiles"""
    component: str
    window_seconds: int
    sample_count: int
    min_ms: float
    max_ms: float
    mean_ms: float
    p50_ms: float
    p75_ms: float
    p90_ms: float
    p95_ms: float
    p99_ms: float
    timestamp: datetime


@dataclass
class AlertThreshold:
    """Alert threshold configuration"""
    name: str
    component: str
    metric: str  # "error_rate" or "latency_p95"
    threshold: float
    duration_seconds: float = 60.0
    severity: str = "warning"
    callback: Optional[Callable] = None
    triggered: bool = False
    triggered_at: Optional[float] = None


# =============================================================================
# SLIDING WINDOW
# =============================================================================

class SlidingWindow:
    """Efficient sliding window for time-series metrics"""

    def __init__(self, window_seconds: int = 300):
        self.window_seconds = window_seconds
        self._data: Deque[RequestMetric] = deque()

    def add(self, metric: RequestMetric):
        """Add a metric to the window"""
        self._data.append(metric)
        self._cleanup()

    def _cleanup(self):
        """Remove expired entries"""
        cutoff = time.time() - self.window_seconds
        while self._data and self._data[0].timestamp < cutoff:
            self._data.popleft()

    def get_all(self) -> List[RequestMetric]:
        """Get all metrics in window"""
        self._cleanup()
        return list(self._data)

    def count(self) -> int:
        """Get count of metrics"""
        self._cleanup()
        return len(self._data)


# =============================================================================
# PERCENTILE CALCULATOR
# =============================================================================

class PercentileCalculator:
    """
    Efficient percentile calculation using sorted insert.
    Maintains a sorted list for O(1) percentile queries.
    """

    def __init__(self, max_samples: int = 10000):
        self.max_samples = max_samples
        self._values: List[float] = []
        self._times: Deque[Tuple[float, float]] = deque()  # (timestamp, value)

    def add(self, value: float, timestamp: float = None):
        """Add a value"""
        timestamp = timestamp or time.time()

        # Insert in sorted order
        bisect.insort(self._values, value)
        self._times.append((timestamp, value))

        # Trim if too many samples
        if len(self._values) > self.max_samples:
            oldest_time, oldest_value = self._times.popleft()
            idx = bisect.bisect_left(self._values, oldest_value)
            if idx < len(self._values) and self._values[idx] == oldest_value:
                self._values.pop(idx)

    def cleanup(self, window_seconds: int):
        """Remove entries older than window"""
        cutoff = time.time() - window_seconds
        while self._times and self._times[0][0] < cutoff:
            _, value = self._times.popleft()
            idx = bisect.bisect_left(self._values, value)
            if idx < len(self._values) and self._values[idx] == value:
                self._values.pop(idx)

    def percentile(self, p: float) -> float:
        """Get percentile (0-100)"""
        if not self._values:
            return 0.0

        idx = int(len(self._values) * p / 100)
        idx = min(idx, len(self._values) - 1)
        return self._values[idx]

    def min(self) -> float:
        return self._values[0] if self._values else 0.0

    def max(self) -> float:
        return self._values[-1] if self._values else 0.0

    def mean(self) -> float:
        return sum(self._values) / len(self._values) if self._values else 0.0

    def count(self) -> int:
        return len(self._values)


# =============================================================================
# METRICS COLLECTOR
# =============================================================================

class MetricsCollector:
    """
    Advanced metrics collector with error rate and latency tracking.

    Features:
    - Per-component metrics
    - Sliding window statistics
    - Percentile calculations
    - Automatic alerting
    - Historical persistence
    """

    DEFAULT_WINDOWS = [60, 300, 900, 3600]  # 1m, 5m, 15m, 1h

    def __init__(
        self,
        db_path: str = None,
        windows: List[int] = None,
    ):
        self.db_path = db_path or os.getenv(
            "METRICS_DB",
            "data/metrics.db"
        )
        self.windows = windows or self.DEFAULT_WINDOWS

        # Per-component data structures
        self._sliding_windows: Dict[str, Dict[int, SlidingWindow]] = {}
        self._latency_calculators: Dict[str, PercentileCalculator] = {}
        self._error_counts: Dict[str, Dict[str, int]] = {}

        # Alert thresholds
        self._thresholds: Dict[str, AlertThreshold] = {}

        # Background task
        self._running = False
        self._task: Optional[asyncio.Task] = None

        self._init_database()

    def _init_database(self):
        """Initialize metrics database"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Minute-level aggregates
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metrics_1m (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                component TEXT NOT NULL,
                total_requests INTEGER,
                failed_requests INTEGER,
                error_rate REAL,
                latency_p50 REAL,
                latency_p95 REAL,
                latency_p99 REAL,
                latency_min REAL,
                latency_max REAL,
                latency_mean REAL,
                UNIQUE(timestamp, component)
            )
        """)

        # Hourly aggregates
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metrics_1h (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                component TEXT NOT NULL,
                total_requests INTEGER,
                failed_requests INTEGER,
                error_rate REAL,
                latency_p50 REAL,
                latency_p95 REAL,
                latency_p99 REAL,
                latency_min REAL,
                latency_max REAL,
                latency_mean REAL,
                UNIQUE(timestamp, component)
            )
        """)

        # Alert history
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alert_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                threshold_name TEXT NOT NULL,
                component TEXT NOT NULL,
                metric TEXT NOT NULL,
                value REAL,
                threshold REAL,
                severity TEXT,
                resolved_at TEXT
            )
        """)

        # Indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_1m_time
            ON metrics_1m(timestamp)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_1h_time
            ON metrics_1h(timestamp)
        """)

        conn.commit()
        conn.close()

    # =========================================================================
    # SETUP
    # =========================================================================

    def _ensure_component(self, component: str):
        """Ensure data structures exist for component"""
        if component not in self._sliding_windows:
            self._sliding_windows[component] = {
                window: SlidingWindow(window)
                for window in self.windows
            }
            self._latency_calculators[component] = PercentileCalculator()
            self._error_counts[component] = {}

    # =========================================================================
    # RECORDING
    # =========================================================================

    def record_request(
        self,
        component: str,
        endpoint: str,
        latency_ms: float,
        success: bool = True,
        error_type: str = None,
        metadata: Dict[str, Any] = None,
    ):
        """
        Record a request metric.

        Args:
            component: Component name (e.g., "api", "bot", "trading")
            endpoint: Endpoint or operation name
            latency_ms: Request latency in milliseconds
            success: Whether request succeeded
            error_type: Error type if failed
            metadata: Additional metadata
        """
        self._ensure_component(component)

        metric = RequestMetric(
            timestamp=time.time(),
            component=component,
            endpoint=endpoint,
            latency_ms=latency_ms,
            success=success,
            error_type=error_type,
            metadata=metadata or {},
        )

        # Add to sliding windows
        for window in self._sliding_windows[component].values():
            window.add(metric)

        # Add latency to calculator
        self._latency_calculators[component].add(latency_ms)

        # Track error types
        if not success and error_type:
            self._error_counts[component][error_type] = (
                self._error_counts[component].get(error_type, 0) + 1
            )

        # Check thresholds
        self._check_thresholds(component)

    def record_error(
        self,
        component: str,
        error_type: str,
        endpoint: str = "unknown",
    ):
        """Record an error without latency"""
        self.record_request(
            component=component,
            endpoint=endpoint,
            latency_ms=0,
            success=False,
            error_type=error_type,
        )

    # =========================================================================
    # ERROR RATE
    # =========================================================================

    def get_error_rate(
        self,
        component: str,
        window_seconds: int = 300,
    ) -> ErrorRateStats:
        """
        Get error rate statistics for a component.

        Args:
            component: Component name
            window_seconds: Window size in seconds

        Returns:
            ErrorRateStats
        """
        self._ensure_component(component)

        # Find closest window
        closest_window = min(self.windows, key=lambda w: abs(w - window_seconds))
        window = self._sliding_windows[component].get(closest_window)

        if not window:
            return ErrorRateStats(
                component=component,
                window_seconds=window_seconds,
                total_requests=0,
                failed_requests=0,
                error_rate=0.0,
                error_types={},
                timestamp=datetime.now(timezone.utc),
            )

        metrics = window.get_all()
        total = len(metrics)
        failed = sum(1 for m in metrics if not m.success)

        # Count error types in window
        error_types: Dict[str, int] = {}
        for m in metrics:
            if not m.success and m.error_type:
                error_types[m.error_type] = error_types.get(m.error_type, 0) + 1

        return ErrorRateStats(
            component=component,
            window_seconds=window_seconds,
            total_requests=total,
            failed_requests=failed,
            error_rate=failed / total if total > 0 else 0.0,
            error_types=error_types,
            timestamp=datetime.now(timezone.utc),
        )

    def get_error_rates_all(
        self,
        window_seconds: int = 300,
    ) -> Dict[str, ErrorRateStats]:
        """Get error rates for all components"""
        return {
            component: self.get_error_rate(component, window_seconds)
            for component in self._sliding_windows.keys()
        }

    # =========================================================================
    # LATENCY PERCENTILES
    # =========================================================================

    def get_latency_percentiles(
        self,
        component: str,
        window_seconds: int = 300,
    ) -> LatencyStats:
        """
        Get latency percentiles for a component.

        Args:
            component: Component name
            window_seconds: Window size in seconds

        Returns:
            LatencyStats
        """
        self._ensure_component(component)

        calc = self._latency_calculators[component]
        calc.cleanup(window_seconds)

        return LatencyStats(
            component=component,
            window_seconds=window_seconds,
            sample_count=calc.count(),
            min_ms=calc.min(),
            max_ms=calc.max(),
            mean_ms=calc.mean(),
            p50_ms=calc.percentile(50),
            p75_ms=calc.percentile(75),
            p90_ms=calc.percentile(90),
            p95_ms=calc.percentile(95),
            p99_ms=calc.percentile(99),
            timestamp=datetime.now(timezone.utc),
        )

    def get_latency_percentiles_all(
        self,
        window_seconds: int = 300,
    ) -> Dict[str, LatencyStats]:
        """Get latency percentiles for all components"""
        return {
            component: self.get_latency_percentiles(component, window_seconds)
            for component in self._latency_calculators.keys()
        }

    # =========================================================================
    # ALERT THRESHOLDS
    # =========================================================================

    def add_threshold(
        self,
        name: str,
        component: str,
        metric: str,
        threshold: float,
        duration_seconds: float = 60.0,
        severity: str = "warning",
        callback: Callable = None,
    ):
        """
        Add an alert threshold.

        Args:
            name: Threshold name
            component: Component to monitor
            metric: "error_rate" or "latency_p95" (or p50, p99)
            threshold: Threshold value
            duration_seconds: How long to exceed before alerting
            severity: Alert severity
            callback: Optional callback function
        """
        self._thresholds[name] = AlertThreshold(
            name=name,
            component=component,
            metric=metric,
            threshold=threshold,
            duration_seconds=duration_seconds,
            severity=severity,
            callback=callback,
        )
        logger.info(f"Added threshold: {name} ({component}.{metric} > {threshold})")

    def remove_threshold(self, name: str):
        """Remove a threshold"""
        if name in self._thresholds:
            del self._thresholds[name]

    def _check_thresholds(self, component: str):
        """Check thresholds for a component"""
        now = time.time()

        for name, threshold in self._thresholds.items():
            if threshold.component != component:
                continue

            # Get current value
            value = self._get_metric_value(component, threshold.metric)

            if value > threshold.threshold:
                if not threshold.triggered:
                    # Start tracking
                    if threshold.triggered_at is None:
                        threshold.triggered_at = now
                    elif now - threshold.triggered_at >= threshold.duration_seconds:
                        # Trigger alert
                        threshold.triggered = True
                        self._trigger_alert(threshold, value)
            else:
                # Reset if below threshold
                if threshold.triggered:
                    self._resolve_alert(threshold)
                threshold.triggered = False
                threshold.triggered_at = None

    def _get_metric_value(self, component: str, metric: str) -> float:
        """Get current value of a metric"""
        if metric == "error_rate":
            stats = self.get_error_rate(component)
            return stats.error_rate

        if metric.startswith("latency_p"):
            percentile = int(metric.replace("latency_p", ""))
            stats = self.get_latency_percentiles(component)

            if percentile == 50:
                return stats.p50_ms
            elif percentile == 75:
                return stats.p75_ms
            elif percentile == 90:
                return stats.p90_ms
            elif percentile == 95:
                return stats.p95_ms
            elif percentile == 99:
                return stats.p99_ms

        return 0.0

    def _trigger_alert(self, threshold: AlertThreshold, value: float):
        """Trigger an alert"""
        logger.warning(
            f"Alert triggered: {threshold.name} - "
            f"{threshold.component}.{threshold.metric}={value:.4f} > {threshold.threshold}"
        )

        # Log to database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO alert_history
            (timestamp, threshold_name, component, metric, value, threshold, severity)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now(timezone.utc).isoformat(),
            threshold.name,
            threshold.component,
            threshold.metric,
            value,
            threshold.threshold,
            threshold.severity,
        ))
        conn.commit()
        conn.close()

        # Call callback
        if threshold.callback:
            try:
                threshold.callback(threshold.name, value, threshold.threshold)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")

    def _resolve_alert(self, threshold: AlertThreshold):
        """Resolve an alert"""
        logger.info(f"Alert resolved: {threshold.name}")

        # Update database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE alert_history
            SET resolved_at = ?
            WHERE threshold_name = ? AND resolved_at IS NULL
        """, (datetime.now(timezone.utc).isoformat(), threshold.name))
        conn.commit()
        conn.close()

    # =========================================================================
    # PERSISTENCE
    # =========================================================================

    async def start_aggregation(self, interval: int = 60):
        """Start background aggregation task"""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._aggregation_loop(interval))
        logger.info("Metrics aggregation started")

    async def stop_aggregation(self):
        """Stop background aggregation"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Metrics aggregation stopped")

    async def _aggregation_loop(self, interval: int):
        """Background aggregation loop"""
        while self._running:
            try:
                await self._save_aggregates()
            except Exception as e:
                logger.error(f"Aggregation error: {e}")

            await asyncio.sleep(interval)

    async def _save_aggregates(self):
        """Save current aggregates to database"""
        timestamp = datetime.now(timezone.utc).replace(second=0, microsecond=0)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for component in self._sliding_windows.keys():
            error_stats = self.get_error_rate(component, window_seconds=60)
            latency_stats = self.get_latency_percentiles(component, window_seconds=60)

            cursor.execute("""
                INSERT OR REPLACE INTO metrics_1m
                (timestamp, component, total_requests, failed_requests, error_rate,
                 latency_p50, latency_p95, latency_p99, latency_min, latency_max, latency_mean)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                timestamp.isoformat(),
                component,
                error_stats.total_requests,
                error_stats.failed_requests,
                error_stats.error_rate,
                latency_stats.p50_ms,
                latency_stats.p95_ms,
                latency_stats.p99_ms,
                latency_stats.min_ms,
                latency_stats.max_ms,
                latency_stats.mean_ms,
            ))

        conn.commit()
        conn.close()

    # =========================================================================
    # HISTORICAL DATA
    # =========================================================================

    def get_historical_metrics(
        self,
        component: str,
        hours: int = 24,
        resolution: str = "1m",
    ) -> List[Dict[str, Any]]:
        """Get historical metrics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        table = "metrics_1m" if resolution == "1m" else "metrics_1h"
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

        cursor.execute(f"""
            SELECT * FROM {table}
            WHERE component = ? AND timestamp >= ?
            ORDER BY timestamp DESC
        """, (component, since))

        columns = [d[0] for d in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]

        conn.close()
        return results

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all metrics"""
        summary = {
            "components": {},
            "thresholds": {},
        }

        for component in self._sliding_windows.keys():
            error_stats = self.get_error_rate(component)
            latency_stats = self.get_latency_percentiles(component)

            summary["components"][component] = {
                "error_rate": round(error_stats.error_rate, 4),
                "total_requests": error_stats.total_requests,
                "latency_p50_ms": round(latency_stats.p50_ms, 2),
                "latency_p95_ms": round(latency_stats.p95_ms, 2),
                "latency_p99_ms": round(latency_stats.p99_ms, 2),
            }

        for name, threshold in self._thresholds.items():
            value = self._get_metric_value(threshold.component, threshold.metric)
            summary["thresholds"][name] = {
                "component": threshold.component,
                "metric": threshold.metric,
                "threshold": threshold.threshold,
                "current_value": round(value, 4),
                "triggered": threshold.triggered,
            }

        return summary


# =============================================================================
# SINGLETON
# =============================================================================

_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get or create the metrics collector singleton"""
    global _collector
    if _collector is None:
        _collector = MetricsCollector()
    return _collector


# =============================================================================
# DECORATOR
# =============================================================================

def track_request(component: str, endpoint: str = None):
    """
    Decorator to track request metrics.

    Usage:
        @track_request("api", "/users")
        async def get_users():
            ...
    """
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            collector = get_metrics_collector()
            start = time.time()
            ep = endpoint or func.__name__

            try:
                result = await func(*args, **kwargs)
                latency = (time.time() - start) * 1000

                collector.record_request(
                    component=component,
                    endpoint=ep,
                    latency_ms=latency,
                    success=True,
                )

                return result

            except Exception as e:
                latency = (time.time() - start) * 1000

                collector.record_request(
                    component=component,
                    endpoint=ep,
                    latency_ms=latency,
                    success=False,
                    error_type=type(e).__name__,
                )

                raise

        return wrapper
    return decorator
