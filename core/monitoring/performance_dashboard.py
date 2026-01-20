"""
JARVIS Performance Monitoring Dashboard

Comprehensive performance monitoring system providing:
- Real-time metrics collection
- Trading performance stats (win/loss ratio, profit per trade)
- System resource monitoring (CPU, memory)
- Historical data aggregation
- Alert thresholds configuration
- Execution latency tracking
- API response time monitoring

Usage:
    from core.monitoring.performance_dashboard import get_performance_dashboard

    dashboard = get_performance_dashboard()
    dashboard.record_trade(trade_data)
    stats = dashboard.get_trading_stats()

Author: JARVIS System
"""

import asyncio
import bisect
import json
import logging
import statistics
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Deque, List, Optional, Tuple

logger = logging.getLogger("jarvis.monitoring.performance_dashboard")


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class TradeRecord:
    """A single trade record for performance tracking."""
    id: str
    symbol: str
    profit_usd: float
    is_win: bool
    timestamp: datetime
    latency_ms: float
    entry_price: float = 0.0
    exit_price: float = 0.0
    amount_usd: float = 0.0
    profit_pct: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LatencySample:
    """A single latency sample."""
    timestamp: float
    latency_ms: float
    operation_type: str


@dataclass
class APISample:
    """A single API response sample."""
    timestamp: float
    endpoint: str
    latency_ms: float
    success: bool


@dataclass
class ResourceSample:
    """A single resource usage sample."""
    timestamp: float
    cpu_percent: float
    memory_mb: float


@dataclass
class AlertThreshold:
    """Alert threshold configuration."""
    name: str
    metric: str
    threshold: float
    comparison: str  # "gt" (greater than), "lt" (less than), "eq" (equal)
    severity: str = "warning"
    triggered: bool = False
    last_triggered: Optional[float] = None
    cooldown_seconds: float = 300.0  # 5 minutes default


# =============================================================================
# PERFORMANCE DASHBOARD
# =============================================================================

class PerformanceDashboard:
    """
    Comprehensive performance monitoring dashboard.

    Tracks:
    - Trading performance (win/loss, profit/trade, profit factor)
    - Execution latency by operation type
    - API response times and success rates
    - System resource usage (CPU, memory)
    - Historical data with aggregation

    Provides:
    - Real-time metrics snapshots
    - Alert threshold monitoring
    - Data persistence
    - Metric stream subscriptions
    """

    def __init__(
        self,
        data_dir: str = "data/performance",
        retention_days: int = 30,
        sampling_interval_seconds: int = 5,
    ):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.retention_days = retention_days
        self.sampling_interval_seconds = sampling_interval_seconds

        # Trade storage
        self._trades: List[TradeRecord] = []

        # Latency storage (by operation type)
        self._latency_samples: Dict[str, Deque[LatencySample]] = defaultdict(
            lambda: deque(maxlen=10000)
        )

        # API response storage (by endpoint)
        self._api_samples: Dict[str, Deque[APISample]] = defaultdict(
            lambda: deque(maxlen=5000)
        )

        # Resource usage storage
        self._resource_samples: Deque[ResourceSample] = deque(maxlen=10000)

        # Alert thresholds
        self._alert_thresholds: List[AlertThreshold] = []

        # Metric subscribers
        self._subscribers: List[Callable] = []

        # Load persisted data
        self._load_data()

    # =========================================================================
    # TRADE RECORDING
    # =========================================================================

    def record_trade(self, trade_data: Dict[str, Any]) -> None:
        """
        Record a trade for performance tracking.

        Args:
            trade_data: Dictionary containing trade information:
                - id: Unique trade identifier
                - symbol: Trading symbol
                - profit_usd: Profit/loss in USD
                - is_win: Whether trade was profitable
                - timestamp: Trade timestamp
                - latency_ms: Execution latency
        """
        # Parse timestamp
        timestamp = trade_data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif not isinstance(timestamp, datetime):
            timestamp = datetime.now(timezone.utc)

        record = TradeRecord(
            id=trade_data.get("id", f"trade_{len(self._trades)}"),
            symbol=trade_data.get("symbol", "UNKNOWN"),
            profit_usd=float(trade_data.get("profit_usd", 0.0)),
            is_win=bool(trade_data.get("is_win", trade_data.get("profit_usd", 0) > 0)),
            timestamp=timestamp,
            latency_ms=float(trade_data.get("latency_ms", 0.0)),
            entry_price=float(trade_data.get("entry_price", 0.0)),
            exit_price=float(trade_data.get("exit_price", 0.0)),
            amount_usd=float(trade_data.get("amount_usd", 0.0)),
            profit_pct=float(trade_data.get("profit_pct", 0.0)),
            metadata=trade_data.get("metadata", {}),
        )

        self._trades.append(record)

        # Also record the execution latency
        if record.latency_ms > 0:
            self.record_execution_latency(record.latency_ms, "trade_execution")

        # Notify subscribers
        self._notify_subscribers({"type": "trade", "data": trade_data})

        # Auto-save periodically
        if len(self._trades) % 10 == 0:
            self.save()

    def get_trading_stats(self, hours: int = None) -> Dict[str, Any]:
        """
        Get trading performance statistics.

        Args:
            hours: Optional time window in hours (None = all time)

        Returns:
            Dictionary with trading statistics
        """
        trades = self._get_trades_in_window(hours)

        if not trades:
            return {
                "trade_count": 0,
                "win_count": 0,
                "loss_count": 0,
                "win_rate": 0.0,
                "win_loss_ratio": 0.0,
                "total_profit_usd": 0.0,
                "avg_profit_usd": 0.0,
                "profit_factor": 0.0,
                "gross_profit": 0.0,
                "gross_loss": 0.0,
                "avg_win_usd": 0.0,
                "avg_loss_usd": 0.0,
                "largest_win_usd": 0.0,
                "largest_loss_usd": 0.0,
            }

        wins = [t for t in trades if t.is_win]
        losses = [t for t in trades if not t.is_win]

        win_count = len(wins)
        loss_count = len(losses)
        total_trades = len(trades)

        # Calculate profit metrics
        profits = [t.profit_usd for t in trades]
        total_profit = sum(profits)
        avg_profit = total_profit / total_trades if total_trades > 0 else 0.0

        gross_profit = sum(t.profit_usd for t in wins) if wins else 0.0
        gross_loss = abs(sum(t.profit_usd for t in losses)) if losses else 0.0

        # Win/loss ratio (wins per loss)
        win_loss_ratio = (
            win_count / loss_count if loss_count > 0 else float(win_count)
        )

        # Win rate percentage
        win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0.0

        # Profit factor (gross profit / gross loss)
        if gross_loss > 0:
            profit_factor = gross_profit / gross_loss
        elif gross_profit > 0:
            profit_factor = float('inf')
        else:
            profit_factor = 0.0

        # Average win/loss
        avg_win = gross_profit / win_count if win_count > 0 else 0.0
        avg_loss = gross_loss / loss_count if loss_count > 0 else 0.0

        # Largest win/loss
        largest_win = max([t.profit_usd for t in wins], default=0.0)
        largest_loss = min([t.profit_usd for t in losses], default=0.0)

        return {
            "trade_count": total_trades,
            "win_count": win_count,
            "loss_count": loss_count,
            "win_rate": round(win_rate, 2),
            "win_loss_ratio": round(win_loss_ratio, 2),
            "total_profit_usd": round(total_profit, 2),
            "avg_profit_usd": round(avg_profit, 2),
            "profit_factor": round(profit_factor, 2) if profit_factor != float('inf') else float('inf'),
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "avg_win_usd": round(avg_win, 2),
            "avg_loss_usd": round(avg_loss, 2),
            "largest_win_usd": round(largest_win, 2),
            "largest_loss_usd": round(largest_loss, 2),
        }

    def _get_trades_in_window(self, hours: int = None) -> List[TradeRecord]:
        """Get trades within time window."""
        if hours is None:
            return self._trades.copy()

        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        return [t for t in self._trades if t.timestamp > cutoff]

    # =========================================================================
    # EXECUTION LATENCY
    # =========================================================================

    def record_execution_latency(
        self,
        latency_ms: float,
        operation_type: str = "default"
    ) -> None:
        """
        Record an execution latency sample.

        Args:
            latency_ms: Latency in milliseconds
            operation_type: Type of operation (e.g., "quote", "swap", "trade_execution")
        """
        sample = LatencySample(
            timestamp=time.time(),
            latency_ms=latency_ms,
            operation_type=operation_type
        )
        self._latency_samples[operation_type].append(sample)

        # Notify subscribers
        self._notify_subscribers({
            "type": "latency",
            "operation": operation_type,
            "latency_ms": latency_ms
        })

    def get_latency_stats(
        self,
        operation_type: str = "default",
        window_seconds: int = 300
    ) -> Dict[str, Any]:
        """
        Get latency statistics for an operation type.

        Args:
            operation_type: Type of operation to get stats for
            window_seconds: Time window in seconds

        Returns:
            Dictionary with latency statistics
        """
        samples = self._latency_samples.get(operation_type, deque())

        if not samples:
            return {
                "sample_count": 0,
                "avg_ms": 0.0,
                "min_ms": 0.0,
                "max_ms": 0.0,
                "p50_ms": 0.0,
                "p75_ms": 0.0,
                "p90_ms": 0.0,
                "p95_ms": 0.0,
                "p99_ms": 0.0,
            }

        cutoff = time.time() - window_seconds
        recent = [s.latency_ms for s in samples if s.timestamp > cutoff]

        if not recent:
            return {
                "sample_count": 0,
                "avg_ms": 0.0,
                "min_ms": 0.0,
                "max_ms": 0.0,
                "p50_ms": 0.0,
                "p75_ms": 0.0,
                "p90_ms": 0.0,
                "p95_ms": 0.0,
                "p99_ms": 0.0,
            }

        sorted_latencies = sorted(recent)
        count = len(sorted_latencies)

        def percentile(data: List[float], p: float) -> float:
            """Calculate percentile."""
            idx = int(p / 100 * (len(data) - 1))
            return data[idx]

        return {
            "sample_count": count,
            "avg_ms": round(statistics.mean(recent), 2),
            "min_ms": round(min(recent), 2),
            "max_ms": round(max(recent), 2),
            "p50_ms": round(percentile(sorted_latencies, 50), 2),
            "p75_ms": round(percentile(sorted_latencies, 75), 2),
            "p90_ms": round(percentile(sorted_latencies, 90), 2),
            "p95_ms": round(percentile(sorted_latencies, 95), 2),
            "p99_ms": round(percentile(sorted_latencies, 99), 2),
        }

    # =========================================================================
    # API RESPONSE TRACKING
    # =========================================================================

    def record_api_response(
        self,
        endpoint: str,
        latency_ms: float,
        success: bool
    ) -> None:
        """
        Record an API response.

        Args:
            endpoint: API endpoint name
            latency_ms: Response time in milliseconds
            success: Whether the request was successful
        """
        sample = APISample(
            timestamp=time.time(),
            endpoint=endpoint,
            latency_ms=latency_ms,
            success=success
        )
        self._api_samples[endpoint].append(sample)

        # Notify subscribers
        self._notify_subscribers({
            "type": "api_response",
            "endpoint": endpoint,
            "latency_ms": latency_ms,
            "success": success
        })

    def get_api_stats(self, window_seconds: int = 300) -> Dict[str, Dict[str, Any]]:
        """
        Get API statistics for all endpoints.

        Args:
            window_seconds: Time window in seconds

        Returns:
            Dictionary mapping endpoint to statistics
        """
        cutoff = time.time() - window_seconds
        results = {}

        for endpoint, samples in self._api_samples.items():
            recent = [s for s in samples if s.timestamp > cutoff]

            if not recent:
                results[endpoint] = {
                    "request_count": 0,
                    "success_count": 0,
                    "failure_count": 0,
                    "success_rate": 0.0,
                    "avg_latency_ms": 0.0,
                    "p95_latency_ms": 0.0,
                }
                continue

            success_count = sum(1 for s in recent if s.success)
            failure_count = len(recent) - success_count
            latencies = sorted([s.latency_ms for s in recent])

            results[endpoint] = {
                "request_count": len(recent),
                "success_count": success_count,
                "failure_count": failure_count,
                "success_rate": round(success_count / len(recent) * 100, 2),
                "avg_latency_ms": round(statistics.mean(latencies), 2),
                "p95_latency_ms": round(
                    latencies[int(0.95 * (len(latencies) - 1))] if latencies else 0,
                    2
                ),
            }

        return results

    # =========================================================================
    # SYSTEM RESOURCE MONITORING
    # =========================================================================

    def record_resource_usage(
        self,
        cpu_percent: float,
        memory_mb: float
    ) -> None:
        """
        Record system resource usage.

        Args:
            cpu_percent: CPU usage percentage
            memory_mb: Memory usage in megabytes
        """
        sample = ResourceSample(
            timestamp=time.time(),
            cpu_percent=cpu_percent,
            memory_mb=memory_mb
        )
        self._resource_samples.append(sample)

        # Notify subscribers
        self._notify_subscribers({
            "type": "resource",
            "cpu_percent": cpu_percent,
            "memory_mb": memory_mb
        })

    async def collect_system_metrics(self) -> None:
        """Collect current system metrics using psutil."""
        try:
            import psutil

            cpu = psutil.cpu_percent(interval=0.1)
            process = psutil.Process()
            memory_bytes = process.memory_info().rss
            memory_mb = memory_bytes / (1024 * 1024)

            self.record_resource_usage(cpu, memory_mb)

        except ImportError:
            logger.debug("psutil not available for system metrics")
        except Exception as e:
            logger.warning(f"Failed to collect system metrics: {e}")

    def get_resource_stats(self, window_seconds: int = 300) -> Dict[str, Dict[str, Any]]:
        """
        Get system resource statistics.

        Args:
            window_seconds: Time window in seconds

        Returns:
            Dictionary with CPU and memory statistics
        """
        cutoff = time.time() - window_seconds
        recent = [s for s in self._resource_samples if s.timestamp > cutoff]

        if not recent:
            return {
                "cpu_percent": {
                    "current": 0.0,
                    "avg": 0.0,
                    "min": 0.0,
                    "max": 0.0,
                },
                "memory_mb": {
                    "current": 0.0,
                    "avg": 0.0,
                    "min": 0.0,
                    "max": 0.0,
                },
            }

        cpu_values = [s.cpu_percent for s in recent]
        memory_values = [s.memory_mb for s in recent]

        return {
            "cpu_percent": {
                "current": round(cpu_values[-1], 2),
                "avg": round(statistics.mean(cpu_values), 2),
                "min": round(min(cpu_values), 2),
                "max": round(max(cpu_values), 2),
            },
            "memory_mb": {
                "current": round(memory_values[-1], 2),
                "avg": round(statistics.mean(memory_values), 2),
                "min": round(min(memory_values), 2),
                "max": round(max(memory_values), 2),
            },
        }

    # =========================================================================
    # HISTORICAL DATA AGGREGATION
    # =========================================================================

    def get_hourly_stats(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get hourly aggregated statistics.

        Args:
            hours: Number of hours to include

        Returns:
            Dictionary with hourly data
        """
        now = datetime.now(timezone.utc)
        hourly_data = []

        for i in range(hours):
            start = now - timedelta(hours=i + 1)
            end = now - timedelta(hours=i)

            trades = [
                t for t in self._trades
                if start <= t.timestamp < end
            ]

            if trades:
                profit = sum(t.profit_usd for t in trades)
                wins = sum(1 for t in trades if t.is_win)
                hourly_data.append({
                    "hour": start.isoformat(),
                    "trade_count": len(trades),
                    "win_count": wins,
                    "profit_usd": round(profit, 2),
                })
            else:
                hourly_data.append({
                    "hour": start.isoformat(),
                    "trade_count": 0,
                    "win_count": 0,
                    "profit_usd": 0.0,
                })

        return {"hourly_data": hourly_data}

    def get_daily_stats(self, days: int = 7) -> Dict[str, Any]:
        """
        Get daily aggregated statistics.

        Args:
            days: Number of days to include

        Returns:
            Dictionary with daily data
        """
        now = datetime.now(timezone.utc)
        daily_data = []

        for i in range(days):
            start = (now - timedelta(days=i + 1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            end = (now - timedelta(days=i)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )

            trades = [
                t for t in self._trades
                if start <= t.timestamp < end
            ]

            if trades:
                profit = sum(t.profit_usd for t in trades)
                wins = sum(1 for t in trades if t.is_win)
                daily_data.append({
                    "date": start.date().isoformat(),
                    "trade_count": len(trades),
                    "win_count": wins,
                    "profit_usd": round(profit, 2),
                })
            else:
                daily_data.append({
                    "date": start.date().isoformat(),
                    "trade_count": 0,
                    "win_count": 0,
                    "profit_usd": 0.0,
                })

        return {"daily_data": daily_data}

    def get_historical_trades(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get historical trade records.

        Args:
            hours: Number of hours to look back

        Returns:
            List of trade dictionaries
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        return [
            {
                "id": t.id,
                "symbol": t.symbol,
                "profit_usd": t.profit_usd,
                "is_win": t.is_win,
                "timestamp": t.timestamp.isoformat(),
                "latency_ms": t.latency_ms,
            }
            for t in self._trades
            if t.timestamp > cutoff
        ]

    def cleanup_old_data(self) -> None:
        """Remove data older than retention period."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.retention_days)

        # Clean trades
        self._trades = [t for t in self._trades if t.timestamp > cutoff]

        # Clean samples (time-based)
        time_cutoff = time.time() - (self.retention_days * 24 * 3600)

        for op_type in list(self._latency_samples.keys()):
            self._latency_samples[op_type] = deque(
                [s for s in self._latency_samples[op_type] if s.timestamp > time_cutoff],
                maxlen=10000
            )

        for endpoint in list(self._api_samples.keys()):
            self._api_samples[endpoint] = deque(
                [s for s in self._api_samples[endpoint] if s.timestamp > time_cutoff],
                maxlen=5000
            )

        self._resource_samples = deque(
            [s for s in self._resource_samples if s.timestamp > time_cutoff],
            maxlen=10000
        )

        logger.info(f"Cleaned up old data. Remaining trades: {len(self._trades)}")

    # =========================================================================
    # ALERT THRESHOLDS
    # =========================================================================

    def add_alert_threshold(
        self,
        name: str,
        metric: str,
        threshold: float,
        comparison: str = "gt",
        severity: str = "warning",
        cooldown_seconds: float = 300.0
    ) -> None:
        """
        Add an alert threshold.

        Args:
            name: Unique name for the alert
            metric: Metric to monitor (e.g., "execution_latency_p95", "win_rate")
            threshold: Threshold value
            comparison: "gt" (greater than), "lt" (less than), "eq" (equal)
            severity: Alert severity ("info", "warning", "critical")
            cooldown_seconds: Minimum time between alerts
        """
        # Remove existing threshold with same name
        self._alert_thresholds = [
            t for t in self._alert_thresholds if t.name != name
        ]

        self._alert_thresholds.append(AlertThreshold(
            name=name,
            metric=metric,
            threshold=threshold,
            comparison=comparison,
            severity=severity,
            cooldown_seconds=cooldown_seconds,
        ))

    def get_alert_thresholds(self) -> List[Dict[str, Any]]:
        """Get all configured alert thresholds."""
        return [
            {
                "name": t.name,
                "metric": t.metric,
                "threshold": t.threshold,
                "comparison": t.comparison,
                "severity": t.severity,
                "triggered": t.triggered,
            }
            for t in self._alert_thresholds
        ]

    def check_alerts(self) -> List[Dict[str, Any]]:
        """
        Check all alert thresholds and return triggered alerts.

        Returns:
            List of triggered alerts
        """
        triggered = []
        current_time = time.time()

        for threshold in self._alert_thresholds:
            # Check cooldown
            if (
                threshold.last_triggered and
                current_time - threshold.last_triggered < threshold.cooldown_seconds
            ):
                continue

            # Get current metric value
            value = self._get_metric_value(threshold.metric)

            if value is None:
                continue

            # Check condition
            is_triggered = False
            if threshold.comparison == "gt" and value > threshold.threshold:
                is_triggered = True
            elif threshold.comparison == "lt" and value < threshold.threshold:
                is_triggered = True
            elif threshold.comparison == "eq" and value == threshold.threshold:
                is_triggered = True

            if is_triggered:
                threshold.triggered = True
                threshold.last_triggered = current_time

                triggered.append({
                    "name": threshold.name,
                    "metric": threshold.metric,
                    "threshold": threshold.threshold,
                    "current_value": value,
                    "severity": threshold.severity,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            else:
                threshold.triggered = False

        return triggered

    def _get_metric_value(self, metric: str) -> Optional[float]:
        """Get current value for a metric."""
        if metric == "win_rate":
            stats = self.get_trading_stats()
            return stats["win_rate"]

        elif metric == "profit_factor":
            stats = self.get_trading_stats()
            pf = stats["profit_factor"]
            return pf if pf != float('inf') else 1000.0

        elif metric.startswith("execution_latency_"):
            percentile = metric.split("_")[-1]  # e.g., "p95"
            stats = self.get_latency_stats("trade_execution")
            return stats.get(f"{percentile}_ms", 0.0)

        elif metric.startswith("api_latency_"):
            parts = metric.split("_")
            endpoint = "_".join(parts[2:-1])
            percentile = parts[-1]
            api_stats = self.get_api_stats()
            if endpoint in api_stats:
                return api_stats[endpoint].get(f"{percentile}_latency_ms", 0.0)

        elif metric == "cpu_percent":
            stats = self.get_resource_stats()
            return stats["cpu_percent"]["current"]

        elif metric == "memory_mb":
            stats = self.get_resource_stats()
            return stats["memory_mb"]["current"]

        return None

    # =========================================================================
    # REAL-TIME METRICS
    # =========================================================================

    async def get_realtime_snapshot(self) -> Dict[str, Any]:
        """
        Get a real-time snapshot of all metrics.

        Returns:
            Dictionary with current metrics
        """
        # Collect fresh system metrics
        await self.collect_system_metrics()

        return {
            "trading": self.get_trading_stats(),
            "latency": {
                op: self.get_latency_stats(op)
                for op in self._latency_samples.keys()
            },
            "api": self.get_api_stats(),
            "system": self.get_resource_stats(),
            "alerts": self.check_alerts(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def subscribe_to_metrics(self, callback: Callable[[Dict], None]) -> None:
        """
        Subscribe to real-time metric updates.

        Args:
            callback: Function to call when new metrics arrive
        """
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable) -> None:
        """Unsubscribe from metric updates."""
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def _notify_subscribers(self, data: Dict[str, Any]) -> None:
        """Notify all subscribers of new data."""
        for callback in self._subscribers:
            try:
                callback(data)
            except Exception as e:
                logger.warning(f"Subscriber callback error: {e}")

    # =========================================================================
    # PERSISTENCE
    # =========================================================================

    def save(self) -> None:
        """Save dashboard data to disk."""
        data = {
            "trades": [
                {
                    "id": t.id,
                    "symbol": t.symbol,
                    "profit_usd": t.profit_usd,
                    "is_win": t.is_win,
                    "timestamp": t.timestamp.isoformat(),
                    "latency_ms": t.latency_ms,
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "amount_usd": t.amount_usd,
                    "profit_pct": t.profit_pct,
                    "metadata": t.metadata,
                }
                for t in self._trades[-10000:]  # Keep last 10k
            ],
            "alert_thresholds": [
                {
                    "name": t.name,
                    "metric": t.metric,
                    "threshold": t.threshold,
                    "comparison": t.comparison,
                    "severity": t.severity,
                    "cooldown_seconds": t.cooldown_seconds,
                }
                for t in self._alert_thresholds
            ],
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }

        data_path = self.data_dir / "performance_data.json"
        try:
            with open(data_path, "w") as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved performance data to {data_path}")
        except Exception as e:
            logger.warning(f"Failed to save performance data: {e}")

    def _load_data(self) -> None:
        """Load persisted data from disk."""
        data_path = self.data_dir / "performance_data.json"

        if not data_path.exists():
            return

        try:
            with open(data_path) as f:
                data = json.load(f)

            # Load trades
            for trade in data.get("trades", []):
                timestamp = trade.get("timestamp")
                if isinstance(timestamp, str):
                    timestamp = datetime.fromisoformat(timestamp)

                self._trades.append(TradeRecord(
                    id=trade.get("id", ""),
                    symbol=trade.get("symbol", ""),
                    profit_usd=trade.get("profit_usd", 0.0),
                    is_win=trade.get("is_win", False),
                    timestamp=timestamp,
                    latency_ms=trade.get("latency_ms", 0.0),
                    entry_price=trade.get("entry_price", 0.0),
                    exit_price=trade.get("exit_price", 0.0),
                    amount_usd=trade.get("amount_usd", 0.0),
                    profit_pct=trade.get("profit_pct", 0.0),
                    metadata=trade.get("metadata", {}),
                ))

            # Load alert thresholds
            for threshold in data.get("alert_thresholds", []):
                self._alert_thresholds.append(AlertThreshold(
                    name=threshold.get("name", ""),
                    metric=threshold.get("metric", ""),
                    threshold=threshold.get("threshold", 0.0),
                    comparison=threshold.get("comparison", "gt"),
                    severity=threshold.get("severity", "warning"),
                    cooldown_seconds=threshold.get("cooldown_seconds", 300.0),
                ))

            logger.info(f"Loaded {len(self._trades)} trades from {data_path}")

        except json.JSONDecodeError as e:
            logger.warning(f"Corrupted performance data file, starting fresh: {e}")
        except Exception as e:
            logger.warning(f"Failed to load performance data: {e}")

    def export_json(self, path: str) -> None:
        """
        Export all dashboard data to a JSON file.

        Args:
            path: File path to export to
        """
        data = {
            "trading_stats": self.get_trading_stats(),
            "trades": [
                {
                    "id": t.id,
                    "symbol": t.symbol,
                    "profit_usd": t.profit_usd,
                    "is_win": t.is_win,
                    "timestamp": t.timestamp.isoformat(),
                    "latency_ms": t.latency_ms,
                }
                for t in self._trades
            ],
            "hourly_stats": self.get_hourly_stats(24),
            "daily_stats": self.get_daily_stats(7),
            "api_stats": self.get_api_stats(),
            "resource_stats": self.get_resource_stats(),
            "alert_thresholds": self.get_alert_thresholds(),
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }

        with open(path, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Exported dashboard data to {path}")

    # =========================================================================
    # CONFIGURATION
    # =========================================================================

    def get_config(self) -> Dict[str, Any]:
        """Get current dashboard configuration."""
        return {
            "data_dir": str(self.data_dir),
            "retention_days": self.retention_days,
            "sampling_interval_seconds": self.sampling_interval_seconds,
        }


# =============================================================================
# SINGLETON
# =============================================================================

_dashboard: Optional[PerformanceDashboard] = None


def get_performance_dashboard(data_dir: str = None) -> PerformanceDashboard:
    """
    Get or create the performance dashboard singleton.

    Args:
        data_dir: Optional data directory path

    Returns:
        PerformanceDashboard instance
    """
    global _dashboard

    if _dashboard is None:
        _dashboard = PerformanceDashboard(
            data_dir=data_dir or "data/performance"
        )

    return _dashboard


def reset_dashboard() -> None:
    """Reset the dashboard singleton (useful for testing)."""
    global _dashboard
    _dashboard = None
