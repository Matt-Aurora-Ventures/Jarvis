"""
Prometheus Metrics Module - Export metrics for monitoring and alerting.
"""

import time
import logging
from typing import Dict, Optional, Callable
from functools import wraps
from dataclasses import dataclass, field
from collections import defaultdict
import threading

logger = logging.getLogger(__name__)


# === METRIC TYPES ===

@dataclass
class Counter:
    """A counter that only goes up."""
    name: str
    help: str
    labels: Dict[str, str] = field(default_factory=dict)
    _value: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def inc(self, value: float = 1.0):
        """Increment counter."""
        with self._lock:
            self._value += value

    def get(self) -> float:
        """Get current value."""
        with self._lock:
            return self._value


@dataclass
class Gauge:
    """A gauge that can go up or down."""
    name: str
    help: str
    labels: Dict[str, str] = field(default_factory=dict)
    _value: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def set(self, value: float):
        """Set gauge value."""
        with self._lock:
            self._value = value

    def inc(self, value: float = 1.0):
        """Increment gauge."""
        with self._lock:
            self._value += value

    def dec(self, value: float = 1.0):
        """Decrement gauge."""
        with self._lock:
            self._value -= value

    def get(self) -> float:
        """Get current value."""
        with self._lock:
            return self._value


@dataclass
class Histogram:
    """A histogram for tracking distributions."""
    name: str
    help: str
    buckets: tuple = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
    labels: Dict[str, str] = field(default_factory=dict)
    _counts: Dict[float, int] = field(default_factory=dict)
    _sum: float = 0.0
    _count: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self):
        self._counts = {b: 0 for b in self.buckets}
        self._counts[float('inf')] = 0

    def observe(self, value: float):
        """Record an observation."""
        with self._lock:
            self._sum += value
            self._count += 1
            for bucket in self.buckets:
                if value <= bucket:
                    self._counts[bucket] += 1
            self._counts[float('inf')] += 1

    def get_buckets(self) -> Dict[float, int]:
        """Get bucket counts."""
        with self._lock:
            return dict(self._counts)

    def get_sum(self) -> float:
        """Get sum of observations."""
        with self._lock:
            return self._sum

    def get_count(self) -> int:
        """Get count of observations."""
        with self._lock:
            return self._count


# === METRICS REGISTRY ===

class MetricsRegistry:
    """Central registry for all metrics."""

    def __init__(self):
        self._metrics: Dict[str, any] = {}
        self._lock = threading.Lock()

    def counter(self, name: str, help: str, labels: Dict[str, str] = None) -> Counter:
        """Get or create a counter."""
        key = self._make_key(name, labels)
        with self._lock:
            if key not in self._metrics:
                self._metrics[key] = Counter(name, help, labels or {})
            return self._metrics[key]

    def gauge(self, name: str, help: str, labels: Dict[str, str] = None) -> Gauge:
        """Get or create a gauge."""
        key = self._make_key(name, labels)
        with self._lock:
            if key not in self._metrics:
                self._metrics[key] = Gauge(name, help, labels or {})
            return self._metrics[key]

    def histogram(self, name: str, help: str, buckets: tuple = None,
                  labels: Dict[str, str] = None) -> Histogram:
        """Get or create a histogram."""
        key = self._make_key(name, labels)
        with self._lock:
            if key not in self._metrics:
                self._metrics[key] = Histogram(
                    name, help,
                    buckets=buckets or Histogram.buckets,
                    labels=labels or {}
                )
            return self._metrics[key]

    def _make_key(self, name: str, labels: Optional[Dict[str, str]]) -> str:
        """Create a unique key for a metric."""
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def export_prometheus(self) -> str:
        """Export all metrics in Prometheus format."""
        lines = []
        seen_helps = set()

        with self._lock:
            for key, metric in self._metrics.items():
                # Add HELP and TYPE only once per metric name
                if metric.name not in seen_helps:
                    lines.append(f"# HELP {metric.name} {metric.help}")
                    if isinstance(metric, Counter):
                        lines.append(f"# TYPE {metric.name} counter")
                    elif isinstance(metric, Gauge):
                        lines.append(f"# TYPE {metric.name} gauge")
                    elif isinstance(metric, Histogram):
                        lines.append(f"# TYPE {metric.name} histogram")
                    seen_helps.add(metric.name)

                # Format labels
                labels_str = ""
                if metric.labels:
                    labels_str = "{" + ",".join(
                        f'{k}="{v}"' for k, v in metric.labels.items()
                    ) + "}"

                # Export value(s)
                if isinstance(metric, (Counter, Gauge)):
                    lines.append(f"{metric.name}{labels_str} {metric.get()}")
                elif isinstance(metric, Histogram):
                    for bucket, count in metric.get_buckets().items():
                        bucket_labels = labels_str.rstrip("}") if labels_str else "{"
                        if bucket_labels != "{":
                            bucket_labels += ","
                        bucket_labels += f'le="{bucket}"' + "}"
                        lines.append(f"{metric.name}_bucket{bucket_labels} {count}")
                    lines.append(f"{metric.name}_sum{labels_str} {metric.get_sum()}")
                    lines.append(f"{metric.name}_count{labels_str} {metric.get_count()}")

        return "\n".join(lines)


# === GLOBAL REGISTRY ===

_registry: Optional[MetricsRegistry] = None

def get_registry() -> MetricsRegistry:
    """Get the global metrics registry."""
    global _registry
    if _registry is None:
        _registry = MetricsRegistry()
    return _registry


# === PRE-DEFINED METRICS ===

def _get_metrics():
    """Initialize standard metrics."""
    r = get_registry()
    return {
        # Trading metrics
        'trades_total': r.counter('jarvis_trades_total', 'Total number of trades executed'),
        'trades_success': r.counter('jarvis_trades_success_total', 'Successful trades'),
        'trades_failed': r.counter('jarvis_trades_failed_total', 'Failed trades'),
        'trade_amount_sol': r.histogram('jarvis_trade_amount_sol', 'Trade amounts in SOL'),
        'trade_latency': r.histogram('jarvis_trade_latency_seconds', 'Trade execution latency'),

        # Treasury metrics
        'treasury_balance_sol': r.gauge('jarvis_treasury_balance_sol', 'Treasury balance in SOL'),
        'treasury_balance_usd': r.gauge('jarvis_treasury_balance_usd', 'Treasury balance in USD'),
        'treasury_positions': r.gauge('jarvis_treasury_positions', 'Number of open positions'),
        'treasury_daily_pnl': r.gauge('jarvis_treasury_daily_pnl_percent', 'Daily P&L percentage'),

        # Buy tracker metrics
        'buys_detected': r.counter('jarvis_buys_detected_total', 'Total buys detected'),
        'alerts_sent': r.counter('jarvis_alerts_sent_total', 'Alerts sent to Telegram'),
        'alerts_failed': r.counter('jarvis_alerts_failed_total', 'Failed alert sends'),
        'alert_latency': r.histogram('jarvis_alert_latency_seconds', 'Alert send latency'),

        # Sentiment metrics
        'sentiment_reports': r.counter('jarvis_sentiment_reports_total', 'Sentiment reports generated'),
        'predictions_made': r.counter('jarvis_predictions_total', 'Predictions made'),
        'predictions_correct': r.counter('jarvis_predictions_correct_total', 'Correct predictions'),
        'prediction_accuracy': r.gauge('jarvis_prediction_accuracy_percent', 'Current prediction accuracy'),

        # API metrics
        'api_requests': r.counter('jarvis_api_requests_total', 'Total API requests'),
        'api_errors': r.counter('jarvis_api_errors_total', 'API errors'),
        'api_latency': r.histogram('jarvis_api_latency_seconds', 'API request latency'),

        # External API metrics
        'external_api_calls': r.counter('jarvis_external_api_calls_total', 'External API calls'),
        'external_api_errors': r.counter('jarvis_external_api_errors_total', 'External API errors'),
        'grok_api_calls': r.counter('jarvis_grok_api_calls_total', 'Grok API calls'),
        'jupiter_api_calls': r.counter('jarvis_jupiter_api_calls_total', 'Jupiter API calls'),
        'dexscreener_api_calls': r.counter('jarvis_dexscreener_api_calls_total', 'DexScreener API calls'),

        # Twitter metrics
        'tweets_posted': r.counter('jarvis_tweets_posted_total', 'Tweets posted'),
        'tweets_failed': r.counter('jarvis_tweets_failed_total', 'Failed tweet posts'),
        'twitter_rate_limits': r.counter('jarvis_twitter_rate_limits_total', 'Twitter rate limit hits'),

        # Circuit breaker metrics
        'circuit_breaker_opens': r.counter('jarvis_circuit_breaker_opens_total', 'Circuit breaker opens'),
        'circuit_breaker_state': r.gauge('jarvis_circuit_breaker_state', 'Circuit breaker state (0=closed, 1=open, 2=half-open)'),

        # System metrics
        'uptime_seconds': r.gauge('jarvis_uptime_seconds', 'System uptime in seconds'),
        'memory_usage_bytes': r.gauge('jarvis_memory_usage_bytes', 'Memory usage in bytes'),
        'active_websockets': r.gauge('jarvis_active_websockets', 'Active WebSocket connections'),
    }


# Lazy initialization
_metrics: Optional[Dict] = None

def get_metrics() -> Dict:
    """Get all predefined metrics."""
    global _metrics
    if _metrics is None:
        _metrics = _get_metrics()
    return _metrics


# === DECORATORS ===

def track_time(metric_name: str):
    """Decorator to track function execution time."""
    def decorator(func: Callable):
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.time()
            try:
                return func(*args, **kwargs)
            finally:
                duration = time.time() - start
                get_registry().histogram(
                    metric_name, f"Duration of {func.__name__}"
                ).observe(duration)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            try:
                return await func(*args, **kwargs)
            finally:
                duration = time.time() - start
                get_registry().histogram(
                    metric_name, f"Duration of {func.__name__}"
                ).observe(duration)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator


def count_calls(metric_name: str):
    """Decorator to count function calls."""
    def decorator(func: Callable):
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            get_registry().counter(
                metric_name, f"Calls to {func.__name__}"
            ).inc()
            return func(*args, **kwargs)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            get_registry().counter(
                metric_name, f"Calls to {func.__name__}"
            ).inc()
            return await func(*args, **kwargs)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator


# === METRICS ENDPOINT ===

async def metrics_handler(request):
    """HTTP handler for /metrics endpoint."""
    from aiohttp import web
    return web.Response(
        text=get_registry().export_prometheus(),
        content_type="text/plain"
    )


def setup_metrics_endpoint(app, path: str = "/metrics"):
    """Add metrics endpoint to aiohttp app."""
    app.router.add_get(path, metrics_handler)
    logger.info(f"Metrics endpoint enabled at {path}")


# === FASTAPI INTEGRATION ===

def get_fastapi_metrics_router():
    """Get FastAPI router for metrics endpoint."""
    from fastapi import APIRouter
    from fastapi.responses import PlainTextResponse

    router = APIRouter()

    @router.get("/metrics", response_class=PlainTextResponse)
    async def metrics():
        return get_registry().export_prometheus()

    return router
