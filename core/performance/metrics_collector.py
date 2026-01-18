"""
Metrics collection and analysis for performance monitoring.

Collects and aggregates metrics for:
- API call latencies (by endpoint)
- Database query times
- Trading decision times
- Sentiment analysis times
- Signal generation times

Supports persistence to JSONL format with configurable retention.
"""
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class MetricSample:
    """A single metric sample."""
    timestamp: datetime
    value: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class MetricsCollector:
    """
    Collect and aggregate performance metrics.

    Usage:
        collector = MetricsCollector()

        # Record API latencies
        collector.record_api_latency("jupiter.quote", 125.5)

        # Record query times
        collector.record_query_time("SELECT * FROM positions", 15.3)

        # Get statistics
        stats = collector.get_api_stats("jupiter.quote")
        print(f"P95 latency: {stats['p95_ms']}ms")
    """

    def __init__(
        self,
        metrics_path: Optional[str] = None,
        retention_days: int = 7,
        max_samples: int = 10000
    ):
        """
        Args:
            metrics_path: Path to JSONL file for persistence
            retention_days: Number of days to retain metrics
            max_samples: Maximum samples to keep in memory per metric
        """
        self.metrics_path = metrics_path or "data/performance/metrics.jsonl"
        self.retention_days = retention_days
        self.max_samples = max_samples

        # In-memory storage
        self._api_samples: Dict[str, List[float]] = defaultdict(list)
        self._query_samples: Dict[str, List[float]] = defaultdict(list)
        self._trading_samples: Dict[str, List[float]] = defaultdict(list)
        self._signal_samples: Dict[str, List[float]] = defaultdict(list)

        # Pending writes for batching
        self._pending_writes: List[Dict[str, Any]] = []

        # Ensure directory exists
        Path(self.metrics_path).parent.mkdir(parents=True, exist_ok=True)

    def record_api_latency(self, endpoint: str, latency_ms: float, metadata: Optional[Dict] = None):
        """
        Record an API call latency.

        Args:
            endpoint: API endpoint identifier (e.g., "jupiter.quote")
            latency_ms: Latency in milliseconds
            metadata: Optional additional metadata
        """
        self._api_samples[endpoint].append(latency_ms)
        self._trim_samples(self._api_samples[endpoint])

        self._pending_writes.append({
            "type": "api_latency",
            "timestamp": datetime.now().isoformat(),
            "endpoint": endpoint,
            "latency_ms": latency_ms,
            "metadata": metadata or {}
        })

    def record_query_time(self, query: str, duration_ms: float, metadata: Optional[Dict] = None):
        """
        Record a database query execution time.

        Args:
            query: The SQL query (or normalized version)
            duration_ms: Execution time in milliseconds
            metadata: Optional additional metadata
        """
        # Normalize query for grouping
        normalized = self._normalize_query(query)
        self._query_samples[normalized].append(duration_ms)
        self._trim_samples(self._query_samples[normalized])

        self._pending_writes.append({
            "type": "query_time",
            "timestamp": datetime.now().isoformat(),
            "query": normalized,
            "duration_ms": duration_ms,
            "metadata": metadata or {}
        })

    def record_trading_decision(self, phase: str, duration_ms: float, metadata: Optional[Dict] = None):
        """
        Record a trading decision phase duration.

        Args:
            phase: Trading phase (e.g., "signal_detection", "position_sizing")
            duration_ms: Duration in milliseconds
            metadata: Optional additional metadata
        """
        self._trading_samples[phase].append(duration_ms)
        self._trim_samples(self._trading_samples[phase])

        self._pending_writes.append({
            "type": "trading_decision",
            "timestamp": datetime.now().isoformat(),
            "phase": phase,
            "duration_ms": duration_ms,
            "metadata": metadata or {}
        })

    def record_signal_generation(self, signal_type: str, duration_ms: float, metadata: Optional[Dict] = None):
        """
        Record signal generation time.

        Args:
            signal_type: Type of signal (e.g., "liquidation", "dual_ma")
            duration_ms: Duration in milliseconds
            metadata: Optional additional metadata
        """
        self._signal_samples[signal_type].append(duration_ms)
        self._trim_samples(self._signal_samples[signal_type])

        self._pending_writes.append({
            "type": "signal_generation",
            "timestamp": datetime.now().isoformat(),
            "signal_type": signal_type,
            "duration_ms": duration_ms,
            "metadata": metadata or {}
        })

    def get_api_stats(self, endpoint: str) -> Dict[str, Any]:
        """Get statistics for an API endpoint."""
        return self._compute_stats(self._api_samples.get(endpoint, []), endpoint)

    def get_query_stats(self, query: str) -> Dict[str, Any]:
        """Get statistics for a query."""
        normalized = self._normalize_query(query)
        return self._compute_stats(self._query_samples.get(normalized, []), normalized)

    def get_trading_stats(self, phase: str) -> Dict[str, Any]:
        """Get statistics for a trading phase."""
        return self._compute_stats(self._trading_samples.get(phase, []), phase)

    def get_signal_stats(self, signal_type: str) -> Dict[str, Any]:
        """Get statistics for a signal type."""
        return self._compute_stats(self._signal_samples.get(signal_type, []), signal_type)

    def get_all_api_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all API endpoints."""
        return {endpoint: self.get_api_stats(endpoint) for endpoint in self._api_samples}

    def get_all_query_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all queries."""
        return {query: self._compute_stats(samples, query) for query, samples in self._query_samples.items()}

    def _compute_stats(self, samples: List[float], name: str) -> Dict[str, Any]:
        """Compute statistics for a list of samples."""
        if not samples:
            return {"name": name, "count": 0}

        sorted_samples = sorted(samples)
        count = len(sorted_samples)

        stats = {
            "name": name,
            "count": count,
            "min_ms": round(min(sorted_samples), 2),
            "max_ms": round(max(sorted_samples), 2),
            "avg_ms": round(sum(sorted_samples) / count, 2),
            "p50_ms": round(sorted_samples[count // 2], 2),
        }

        # Only compute higher percentiles with enough samples
        if count >= 20:
            stats["p95_ms"] = round(sorted_samples[int(count * 0.95)], 2)
        if count >= 100:
            stats["p99_ms"] = round(sorted_samples[int(count * 0.99)], 2)

        return stats

    def _trim_samples(self, samples: List[float]):
        """Trim samples to max_samples limit."""
        if len(samples) > self.max_samples:
            del samples[:-self.max_samples]

    def _normalize_query(self, query: str) -> str:
        """Normalize a query for grouping."""
        import re
        # Replace string literals
        normalized = re.sub(r"'[^']*'", "'?'", query)
        # Replace numbers
        normalized = re.sub(r"\b\d+\b", "?", normalized)
        # Normalize whitespace
        return " ".join(normalized.split())

    def flush(self):
        """Flush pending writes to disk."""
        if not self._pending_writes:
            return

        try:
            with open(self.metrics_path, "a") as f:
                for entry in self._pending_writes:
                    f.write(json.dumps(entry) + "\n")
            self._pending_writes.clear()
        except Exception as e:
            logger.error(f"Failed to flush metrics: {e}")

    def cleanup_old_metrics(self):
        """Remove metrics older than retention_days."""
        if not os.path.exists(self.metrics_path):
            return

        cutoff = datetime.now() - timedelta(days=self.retention_days)
        kept_lines = []

        try:
            with open(self.metrics_path, "r") as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        entry_time = datetime.fromisoformat(entry["timestamp"])
                        if entry_time >= cutoff:
                            kept_lines.append(line)
                    except (json.JSONDecodeError, KeyError, ValueError):
                        continue

            with open(self.metrics_path, "w") as f:
                f.writelines(kept_lines)

            logger.info(f"Cleaned up metrics, kept {len(kept_lines)} entries")
        except Exception as e:
            logger.error(f"Failed to cleanup metrics: {e}")

    def reset(self):
        """Reset all in-memory metrics."""
        self._api_samples.clear()
        self._query_samples.clear()
        self._trading_samples.clear()
        self._signal_samples.clear()
        self._pending_writes.clear()


# =============================================================================
# Performance Baselines
# =============================================================================

class PerformanceBaselines:
    """
    Manage performance baselines and detect regressions.

    Usage:
        baselines = PerformanceBaselines("config/performance_baselines.json")

        # Check if current performance is a regression
        if baselines.is_regression("signal_detection", current_time_ms):
            logger.warning("Performance regression detected!")

        # Update baseline
        baselines.set_target("new_operation", 50)
        baselines.save()
    """

    def __init__(self, config_path: str):
        """
        Args:
            config_path: Path to JSON file with baseline configurations
        """
        self.config_path = config_path
        self._baselines: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self):
        """Load baselines from config file."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    self._baselines = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Failed to load baselines: {e}")
                self._baselines = {}

    def get_target(self, operation: str) -> Optional[float]:
        """Get the target time for an operation in milliseconds."""
        if operation in self._baselines:
            return self._baselines[operation].get("target_ms")
        return None

    def set_target(self, operation: str, target_ms: float, metadata: Optional[Dict] = None):
        """Set a target time for an operation."""
        self._baselines[operation] = {
            "target_ms": target_ms,
            "updated_at": datetime.now().isoformat(),
            **(metadata or {})
        }

    def is_regression(self, operation: str, actual_ms: float, threshold_pct: float = 10.0) -> bool:
        """
        Check if actual time represents a regression.

        Args:
            operation: Operation name
            actual_ms: Actual execution time in milliseconds
            threshold_pct: Percentage threshold for regression (default 10%)

        Returns:
            True if this is a regression (>threshold% slower than baseline)
        """
        target = self.get_target(operation)
        if target is None:
            return False

        # Calculate threshold
        threshold = target * (1 + threshold_pct / 100)
        return actual_ms > threshold

    def get_all_baselines(self) -> Dict[str, Dict[str, Any]]:
        """Get all baselines."""
        return self._baselines.copy()

    def save(self):
        """Save baselines to config file."""
        try:
            Path(self.config_path).parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w") as f:
                json.dump(self._baselines, f, indent=2)
        except IOError as e:
            logger.error(f"Failed to save baselines: {e}")


# =============================================================================
# Regression Report Generation
# =============================================================================

def generate_regression_report(
    baselines: Dict[str, Dict[str, Any]],
    actual: Dict[str, Dict[str, Any]],
    threshold_pct: float = 10.0
) -> Dict[str, Any]:
    """
    Generate a regression report comparing actual performance to baselines.

    Args:
        baselines: Dictionary of operation -> {"target_ms": float}
        actual: Dictionary of operation -> {"avg_ms": float}
        threshold_pct: Percentage threshold for regression detection

    Returns:
        Report dictionary with regressions, improvements, and summary
    """
    regressions = {}
    improvements = {}
    unchanged = {}

    for operation, baseline_data in baselines.items():
        target_ms = baseline_data.get("target_ms")
        if target_ms is None:
            continue

        if operation not in actual:
            continue

        actual_ms = actual[operation].get("avg_ms")
        if actual_ms is None:
            continue

        diff_pct = ((actual_ms - target_ms) / target_ms) * 100

        if diff_pct > threshold_pct:
            regressions[operation] = {
                "target_ms": target_ms,
                "actual_ms": actual_ms,
                "diff_pct": round(diff_pct, 1)
            }
        elif diff_pct < -threshold_pct:
            improvements[operation] = {
                "target_ms": target_ms,
                "actual_ms": actual_ms,
                "diff_pct": round(diff_pct, 1)
            }
        else:
            unchanged[operation] = {
                "target_ms": target_ms,
                "actual_ms": actual_ms,
                "diff_pct": round(diff_pct, 1)
            }

    return {
        "has_regressions": len(regressions) > 0,
        "regressions": regressions,
        "improvements": improvements,
        "unchanged": unchanged,
        "summary": {
            "total_operations": len(baselines),
            "regression_count": len(regressions),
            "improvement_count": len(improvements),
            "unchanged_count": len(unchanged)
        }
    }


# =============================================================================
# Global Metrics Collector Instance
# =============================================================================

_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def record_metric(metric_type: str, name: str, value: float, metadata: Optional[Dict] = None):
    """
    Convenience function to record a metric.

    Args:
        metric_type: Type of metric ("api", "query", "trading", "signal")
        name: Name/identifier for the metric
        value: The metric value (typically milliseconds)
        metadata: Optional additional metadata
    """
    collector = get_metrics_collector()

    if metric_type == "api":
        collector.record_api_latency(name, value, metadata)
    elif metric_type == "query":
        collector.record_query_time(name, value, metadata)
    elif metric_type == "trading":
        collector.record_trading_decision(name, value, metadata)
    elif metric_type == "signal":
        collector.record_signal_generation(name, value, metadata)
    else:
        logger.warning(f"Unknown metric type: {metric_type}")
