"""Prometheus metrics collection."""
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from collections import defaultdict
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import logging

logger = logging.getLogger(__name__)


@dataclass
class MetricValue:
    """A metric value with labels."""
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class Counter:
    """Prometheus-style counter metric."""
    
    def __init__(self, name: str, description: str, labels: List[str] = None):
        self.name = name
        self.description = description
        self.label_names = labels or []
        self._values: Dict[tuple, float] = defaultdict(float)
        self._lock = threading.Lock()
    
    def inc(self, value: float = 1, **labels):
        """Increment counter."""
        key = tuple(labels.get(l, "") for l in self.label_names)
        with self._lock:
            self._values[key] += value
    
    def get(self, **labels) -> float:
        """Get counter value."""
        key = tuple(labels.get(l, "") for l in self.label_names)
        return self._values.get(key, 0)
    
    def collect(self) -> List[MetricValue]:
        """Collect all values."""
        result = []
        for key, value in self._values.items():
            labels = dict(zip(self.label_names, key))
            result.append(MetricValue(value=value, labels=labels))
        return result


class Gauge:
    """Prometheus-style gauge metric."""
    
    def __init__(self, name: str, description: str, labels: List[str] = None):
        self.name = name
        self.description = description
        self.label_names = labels or []
        self._values: Dict[tuple, float] = {}
        self._lock = threading.Lock()
    
    def set(self, value: float, **labels):
        """Set gauge value."""
        key = tuple(labels.get(l, "") for l in self.label_names)
        with self._lock:
            self._values[key] = value
    
    def inc(self, value: float = 1, **labels):
        """Increment gauge."""
        key = tuple(labels.get(l, "") for l in self.label_names)
        with self._lock:
            self._values[key] = self._values.get(key, 0) + value
    
    def dec(self, value: float = 1, **labels):
        """Decrement gauge."""
        self.inc(-value, **labels)
    
    def get(self, **labels) -> float:
        """Get gauge value."""
        key = tuple(labels.get(l, "") for l in self.label_names)
        return self._values.get(key, 0)
    
    def collect(self) -> List[MetricValue]:
        result = []
        for key, value in self._values.items():
            labels = dict(zip(self.label_names, key))
            result.append(MetricValue(value=value, labels=labels))
        return result


class Histogram:
    """Prometheus-style histogram metric."""
    
    DEFAULT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10)
    
    def __init__(self, name: str, description: str, labels: List[str] = None, buckets: tuple = None):
        self.name = name
        self.description = description
        self.label_names = labels or []
        self.buckets = buckets or self.DEFAULT_BUCKETS
        self._counts: Dict[tuple, Dict[float, int]] = defaultdict(lambda: defaultdict(int))
        self._sums: Dict[tuple, float] = defaultdict(float)
        self._totals: Dict[tuple, int] = defaultdict(int)
        self._lock = threading.Lock()
    
    def observe(self, value: float, **labels):
        """Observe a value."""
        key = tuple(labels.get(l, "") for l in self.label_names)
        with self._lock:
            self._sums[key] += value
            self._totals[key] += 1
            for bucket in self.buckets:
                if value <= bucket:
                    self._counts[key][bucket] += 1
    
    @contextmanager
    def time(self, **labels):
        """Context manager to time operations."""
        start = time.perf_counter()
        try:
            yield
        finally:
            self.observe(time.perf_counter() - start, **labels)
    
    def collect(self) -> List[MetricValue]:
        result = []
        for key in self._totals.keys():
            labels = dict(zip(self.label_names, key))
            
            # Bucket values
            for bucket in self.buckets:
                bucket_labels = {**labels, "le": str(bucket)}
                result.append(MetricValue(
                    value=self._counts[key][bucket],
                    labels=bucket_labels
                ))
            
            # Sum and count
            result.append(MetricValue(value=self._sums[key], labels={**labels, "type": "sum"}))
            result.append(MetricValue(value=self._totals[key], labels={**labels, "type": "count"}))
        
        return result


class MetricsRegistry:
    """Registry for all metrics."""
    
    def __init__(self):
        self._metrics: Dict[str, Any] = {}
    
    def counter(self, name: str, description: str, labels: List[str] = None) -> Counter:
        if name not in self._metrics:
            self._metrics[name] = Counter(name, description, labels)
        return self._metrics[name]
    
    def gauge(self, name: str, description: str, labels: List[str] = None) -> Gauge:
        if name not in self._metrics:
            self._metrics[name] = Gauge(name, description, labels)
        return self._metrics[name]
    
    def histogram(self, name: str, description: str, labels: List[str] = None, buckets: tuple = None) -> Histogram:
        if name not in self._metrics:
            self._metrics[name] = Histogram(name, description, labels, buckets)
        return self._metrics[name]
    
    def collect_all(self) -> str:
        """Collect all metrics in Prometheus format."""
        lines = []
        
        for name, metric in self._metrics.items():
            lines.append(f"# HELP {name} {metric.description}")
            
            if isinstance(metric, Counter):
                lines.append(f"# TYPE {name} counter")
            elif isinstance(metric, Gauge):
                lines.append(f"# TYPE {name} gauge")
            elif isinstance(metric, Histogram):
                lines.append(f"# TYPE {name} histogram")
            
            for mv in metric.collect():
                label_str = ",".join(f'{k}="{v}"' for k, v in mv.labels.items())
                if label_str:
                    lines.append(f"{name}{{{label_str}}} {mv.value}")
                else:
                    lines.append(f"{name} {mv.value}")
        
        return "\n".join(lines)


# Global registry
metrics = MetricsRegistry()

# Pre-defined metrics
http_requests = metrics.counter("http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"])
http_latency = metrics.histogram("http_request_duration_seconds", "HTTP request latency", ["method", "endpoint"])
active_connections = metrics.gauge("active_connections", "Active WebSocket connections", ["channel"])
provider_calls = metrics.counter("provider_calls_total", "AI provider API calls", ["provider", "status"])
provider_latency = metrics.histogram("provider_latency_seconds", "AI provider latency", ["provider"])
trade_executions = metrics.counter("trade_executions_total", "Trade executions", ["symbol", "side", "status"])
cache_hits = metrics.counter("cache_hits_total", "Cache hits", ["cache_type"])
cache_misses = metrics.counter("cache_misses_total", "Cache misses", ["cache_type"])

# Jarvis bot metrics
TWEETS_POSTED = metrics.counter(
    "jarvis_tweets_posted_total",
    "Tweets posted",
    ["category", "with_image"],
)
TWEET_LATENCY = metrics.histogram(
    "jarvis_tweet_latency_seconds",
    "Tweet post latency",
)
API_CALLS = metrics.counter(
    "jarvis_api_calls_total",
    "API calls",
    ["service"],
)
API_LATENCY = metrics.histogram(
    "jarvis_api_latency_seconds",
    "API call latency",
    ["service"],
)
ACTIVE_POSITIONS = metrics.gauge(
    "jarvis_active_positions",
    "Active positions",
)

_metrics_server: Optional[HTTPServer] = None
_metrics_server_lock = threading.Lock()


def start_metrics_server(port: int = 9090) -> Optional[HTTPServer]:
    """Start a simple Prometheus metrics HTTP server."""
    global _metrics_server
    with _metrics_server_lock:
        if _metrics_server is not None:
            return _metrics_server

        class MetricsHandler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802 - BaseHTTPRequestHandler naming
                if self.path.rstrip("/") != "/metrics":
                    self.send_response(404)
                    self.end_headers()
                    return

                payload = metrics.collect_all().encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, format, *args):  # noqa: A002
                return

        try:
            server = HTTPServer(("0.0.0.0", port), MetricsHandler)
        except OSError as exc:
            logger.warning(f"Metrics server failed to start on port {port}: {exc}")
            return None

        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        _metrics_server = server
        logger.info(f"Metrics server started on http://0.0.0.0:{port}/metrics")
        return server
