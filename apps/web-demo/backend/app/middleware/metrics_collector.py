"""
Performance Metrics Collector
Tracks API performance, error rates, and system health metrics.
"""
import time
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
from threading import Lock

logger = logging.getLogger(__name__)


@dataclass
class RequestMetric:
    """Single request metric"""
    endpoint: str
    method: str
    status_code: int
    duration_ms: float
    timestamp: datetime
    error: Optional[str] = None


@dataclass
class EndpointStats:
    """Statistics for a specific endpoint"""
    total_requests: int = 0
    total_errors: int = 0
    total_duration_ms: float = 0.0
    min_duration_ms: float = float('inf')
    max_duration_ms: float = 0.0
    last_request: Optional[datetime] = None

    @property
    def avg_duration_ms(self) -> float:
        """Average request duration"""
        return self.total_duration_ms / self.total_requests if self.total_requests > 0 else 0.0

    @property
    def error_rate(self) -> float:
        """Error rate as percentage"""
        return (self.total_errors / self.total_requests * 100) if self.total_requests > 0 else 0.0


class MetricsCollector:
    """
    Collects and aggregates application metrics.

    Features:
    - Request duration tracking
    - Error rate monitoring
    - Endpoint-specific statistics
    - Time-window metrics (last 1min, 5min, 15min)
    - Prometheus-compatible export
    """

    def __init__(self, max_history: int = 10000):
        """
        Initialize metrics collector.

        Args:
            max_history: Maximum number of recent requests to keep
        """
        self.max_history = max_history
        self.recent_requests: deque[RequestMetric] = deque(maxlen=max_history)
        self.endpoint_stats: Dict[str, EndpointStats] = defaultdict(EndpointStats)
        self.lock = Lock()

        # System-wide counters
        self.total_requests = 0
        self.total_errors = 0
        self.start_time = datetime.utcnow()

    def record_request(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        duration_ms: float,
        error: Optional[str] = None
    ):
        """
        Record a request metric.

        Args:
            endpoint: API endpoint path
            method: HTTP method
            status_code: Response status code
            duration_ms: Request duration in milliseconds
            error: Optional error message
        """
        with self.lock:
            # Create metric
            metric = RequestMetric(
                endpoint=endpoint,
                method=method,
                status_code=status_code,
                duration_ms=duration_ms,
                timestamp=datetime.utcnow(),
                error=error
            )

            # Add to recent history
            self.recent_requests.append(metric)

            # Update endpoint stats
            stats = self.endpoint_stats[endpoint]
            stats.total_requests += 1
            stats.total_duration_ms += duration_ms
            stats.min_duration_ms = min(stats.min_duration_ms, duration_ms)
            stats.max_duration_ms = max(stats.max_duration_ms, duration_ms)
            stats.last_request = metric.timestamp

            if status_code >= 400:
                stats.total_errors += 1

            # Update global counters
            self.total_requests += 1
            if status_code >= 400:
                self.total_errors += 1

    def get_stats(self, time_window_minutes: Optional[int] = None) -> Dict:
        """
        Get aggregated statistics.

        Args:
            time_window_minutes: Optional time window to filter metrics

        Returns:
            Dictionary with aggregated stats
        """
        with self.lock:
            if time_window_minutes:
                cutoff = datetime.utcnow() - timedelta(minutes=time_window_minutes)
                requests = [r for r in self.recent_requests if r.timestamp >= cutoff]
            else:
                requests = list(self.recent_requests)

            if not requests:
                return {
                    "total_requests": 0,
                    "total_errors": 0,
                    "error_rate": 0.0,
                    "avg_duration_ms": 0.0,
                    "min_duration_ms": 0.0,
                    "max_duration_ms": 0.0,
                    "requests_per_minute": 0.0
                }

            total_requests = len(requests)
            total_errors = sum(1 for r in requests if r.status_code >= 400)
            durations = [r.duration_ms for r in requests]

            # Calculate requests per minute
            if time_window_minutes:
                rpm = total_requests / time_window_minutes
            else:
                uptime_minutes = (datetime.utcnow() - self.start_time).total_seconds() / 60
                rpm = total_requests / uptime_minutes if uptime_minutes > 0 else 0

            return {
                "total_requests": total_requests,
                "total_errors": total_errors,
                "error_rate": (total_errors / total_requests * 100) if total_requests > 0 else 0.0,
                "avg_duration_ms": sum(durations) / len(durations),
                "min_duration_ms": min(durations),
                "max_duration_ms": max(durations),
                "requests_per_minute": round(rpm, 2)
            }

    def get_endpoint_stats(self) -> Dict[str, Dict]:
        """
        Get per-endpoint statistics.

        Returns:
            Dictionary mapping endpoints to their stats
        """
        with self.lock:
            return {
                endpoint: {
                    "total_requests": stats.total_requests,
                    "total_errors": stats.total_errors,
                    "error_rate": round(stats.error_rate, 2),
                    "avg_duration_ms": round(stats.avg_duration_ms, 2),
                    "min_duration_ms": round(stats.min_duration_ms, 2),
                    "max_duration_ms": round(stats.max_duration_ms, 2),
                    "last_request": stats.last_request.isoformat() if stats.last_request else None
                }
                for endpoint, stats in self.endpoint_stats.items()
            }

    def get_metrics_summary(self) -> Dict:
        """
        Get comprehensive metrics summary.

        Returns:
            Dictionary with all metrics including time windows
        """
        with self.lock:
            uptime_seconds = (datetime.utcnow() - self.start_time).total_seconds()

            return {
                "uptime_seconds": round(uptime_seconds, 2),
                "uptime_hours": round(uptime_seconds / 3600, 2),
                "total_requests": self.total_requests,
                "total_errors": self.total_errors,
                "global_error_rate": round(
                    (self.total_errors / self.total_requests * 100) if self.total_requests > 0 else 0.0,
                    2
                ),
                "last_1_minute": self.get_stats(1),
                "last_5_minutes": self.get_stats(5),
                "last_15_minutes": self.get_stats(15),
                "all_time": self.get_stats(),
                "endpoints": self.get_endpoint_stats()
            }

    def to_prometheus(self) -> str:
        """
        Export metrics in Prometheus format.

        Returns:
            Prometheus-formatted metrics string
        """
        with self.lock:
            lines = []

            # Help and type declarations
            lines.append("# HELP jarvis_requests_total Total number of requests")
            lines.append("# TYPE jarvis_requests_total counter")
            lines.append(f"jarvis_requests_total {self.total_requests}")

            lines.append("# HELP jarvis_errors_total Total number of errors")
            lines.append("# TYPE jarvis_errors_total counter")
            lines.append(f"jarvis_errors_total {self.total_errors}")

            # Per-endpoint metrics
            lines.append("# HELP jarvis_endpoint_requests_total Requests per endpoint")
            lines.append("# TYPE jarvis_endpoint_requests_total counter")
            for endpoint, stats in self.endpoint_stats.items():
                safe_endpoint = endpoint.replace("/", "_").replace("{", "").replace("}", "")
                lines.append(f'jarvis_endpoint_requests_total{{endpoint="{endpoint}"}} {stats.total_requests}')

            lines.append("# HELP jarvis_endpoint_duration_seconds Request duration per endpoint")
            lines.append("# TYPE jarvis_endpoint_duration_seconds histogram")
            for endpoint, stats in self.endpoint_stats.items():
                if stats.total_requests > 0:
                    safe_endpoint = endpoint.replace("/", "_").replace("{", "").replace("}", "")
                    avg_sec = stats.avg_duration_ms / 1000
                    lines.append(f'jarvis_endpoint_duration_seconds_sum{{endpoint="{endpoint}"}} {stats.total_duration_ms / 1000}')
                    lines.append(f'jarvis_endpoint_duration_seconds_count{{endpoint="{endpoint}"}} {stats.total_requests}')

            return "\n".join(lines)

    def reset(self):
        """Reset all metrics (use with caution)"""
        with self.lock:
            self.recent_requests.clear()
            self.endpoint_stats.clear()
            self.total_requests = 0
            self.total_errors = 0
            self.start_time = datetime.utcnow()
            logger.info("Metrics collector reset")


# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector
