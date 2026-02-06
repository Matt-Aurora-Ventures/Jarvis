"""
Metrics Aggregator Module.

Provides aggregation of metrics across multiple bots with:
- Hourly statistics (HourlyStats)
- Daily statistics (DailyStats)
- Percentile calculations
"""

import statistics
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Dict, List, Tuple, Any, Optional

from core.metrics.bot_metrics import BotMetrics


@dataclass
class HourlyStats:
    """
    Hourly aggregate statistics across all bots.

    Contains totals and averages for the last hour of metrics.
    """

    timestamp: datetime
    total_messages_received: int
    total_messages_sent: int
    total_commands: int
    total_errors: int
    avg_response_time: float
    bot_breakdown: Dict[str, Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "total_messages_received": self.total_messages_received,
            "total_messages_sent": self.total_messages_sent,
            "total_commands": self.total_commands,
            "total_errors": self.total_errors,
            "avg_response_time": self.avg_response_time,
            "bot_breakdown": self.bot_breakdown,
        }


@dataclass
class DailyStats:
    """
    Daily aggregate statistics across all bots.

    Contains totals, averages, and percentiles for the day.
    """

    date: date
    total_messages_received: int
    total_messages_sent: int
    total_commands: int
    total_errors: int
    error_rate: float
    avg_response_time: float
    p50_response_time: float
    p95_response_time: float
    p99_response_time: float
    bot_breakdown: Dict[str, Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "date": self.date.isoformat(),
            "total_messages_received": self.total_messages_received,
            "total_messages_sent": self.total_messages_sent,
            "total_commands": self.total_commands,
            "total_errors": self.total_errors,
            "error_rate": self.error_rate,
            "avg_response_time": self.avg_response_time,
            "p50_response_time": self.p50_response_time,
            "p95_response_time": self.p95_response_time,
            "p99_response_time": self.p99_response_time,
            "bot_breakdown": self.bot_breakdown,
        }


class MetricsAggregator:
    """
    Aggregates metrics across multiple bot sources.

    Provides methods for computing hourly and daily statistics,
    percentile calculations, and per-bot breakdowns.
    """

    def __init__(self, sources: List[BotMetrics]):
        """
        Initialize the aggregator with bot metrics sources.

        Args:
            sources: List of BotMetrics instances to aggregate
        """
        self.sources = sources

    def aggregate_hourly(self) -> HourlyStats:
        """
        Aggregate metrics for the current hour.

        Returns:
            HourlyStats with totals and averages
        """
        total_received = 0
        total_sent = 0
        total_commands = 0
        total_errors = 0
        all_response_times: List[float] = []
        bot_breakdown: Dict[str, Dict[str, Any]] = {}

        for source in self.sources:
            stats = source.get_stats()

            total_received += stats["messages_received"]
            total_sent += stats["messages_sent"]
            total_commands += stats["commands_processed"]
            total_errors += stats["errors_total"]
            all_response_times.extend(source.response_times)

            bot_breakdown[source.bot_name] = {
                "messages_received": stats["messages_received"],
                "messages_sent": stats["messages_sent"],
                "commands_processed": stats["commands_processed"],
                "errors_total": stats["errors_total"],
            }

        avg_response = 0.0
        if all_response_times:
            avg_response = sum(all_response_times) / len(all_response_times)

        return HourlyStats(
            timestamp=datetime.utcnow(),
            total_messages_received=total_received,
            total_messages_sent=total_sent,
            total_commands=total_commands,
            total_errors=total_errors,
            avg_response_time=avg_response,
            bot_breakdown=bot_breakdown,
        )

    def aggregate_daily(self) -> DailyStats:
        """
        Aggregate metrics for the current day.

        Returns:
            DailyStats with totals, averages, and percentiles
        """
        total_received = 0
        total_sent = 0
        total_commands = 0
        total_errors = 0
        all_response_times: List[float] = []
        bot_breakdown: Dict[str, Dict[str, Any]] = {}

        for source in self.sources:
            stats = source.get_stats()

            total_received += stats["messages_received"]
            total_sent += stats["messages_sent"]
            total_commands += stats["commands_processed"]
            total_errors += stats["errors_total"]
            all_response_times.extend(source.response_times)

            bot_breakdown[source.bot_name] = {
                "messages_received": stats["messages_received"],
                "messages_sent": stats["messages_sent"],
                "commands_processed": stats["commands_processed"],
                "errors_total": stats["errors_total"],
            }

        # Calculate error rate
        error_rate = 0.0
        if total_received > 0:
            error_rate = total_errors / total_received

        # Calculate response time statistics
        avg_response = 0.0
        p50 = 0.0
        p95 = 0.0
        p99 = 0.0

        if all_response_times:
            avg_response = sum(all_response_times) / len(all_response_times)
            p50, p95, p99 = self._calculate_percentiles(all_response_times)

        return DailyStats(
            date=datetime.utcnow().date(),
            total_messages_received=total_received,
            total_messages_sent=total_sent,
            total_commands=total_commands,
            total_errors=total_errors,
            error_rate=error_rate,
            avg_response_time=avg_response,
            p50_response_time=p50,
            p95_response_time=p95,
            p99_response_time=p99,
            bot_breakdown=bot_breakdown,
        )

    def get_percentiles(self, metric: str) -> Tuple[float, float, float]:
        """
        Calculate p50, p95, p99 percentiles for a metric.

        Args:
            metric: Name of the metric (currently supports "response_times")

        Returns:
            Tuple of (p50, p95, p99) values
        """
        if metric == "response_times":
            all_times: List[float] = []
            for source in self.sources:
                all_times.extend(source.response_times)

            return self._calculate_percentiles(all_times)

        return (0.0, 0.0, 0.0)

    def _calculate_percentiles(self, data: List[float]) -> Tuple[float, float, float]:
        """
        Calculate p50, p95, p99 percentiles for a list of values.

        Args:
            data: List of numeric values

        Returns:
            Tuple of (p50, p95, p99) values
        """
        if not data:
            return (0.0, 0.0, 0.0)

        if len(data) == 1:
            return (data[0], data[0], data[0])

        sorted_data = sorted(data)
        n = len(sorted_data)

        def percentile(p: float) -> float:
            """Calculate the p-th percentile."""
            k = (n - 1) * p / 100
            f = int(k)
            c = f + 1 if f + 1 < n else f
            d = k - f
            return sorted_data[f] + d * (sorted_data[c] - sorted_data[f])

        p50 = percentile(50)
        p95 = percentile(95)
        p99 = percentile(99)

        return (p50, p95, p99)

    def aggregate_by_bot(self) -> Dict[str, Dict[str, Any]]:
        """
        Get per-bot statistics.

        Returns:
            Dictionary mapping bot names to their statistics
        """
        result: Dict[str, Dict[str, Any]] = {}

        for source in self.sources:
            stats = source.get_stats()
            result[source.bot_name] = {
                "messages_received": stats["messages_received"],
                "messages_sent": stats["messages_sent"],
                "commands_processed": stats["commands_processed"],
                "errors_total": stats["errors_total"],
                "avg_response_time": stats["avg_response_time"],
            }

        return result

    def get_time_series(
        self, metric: str, bucket_minutes: int = 5
    ) -> List[Tuple[datetime, float]]:
        """
        Get time-bucketed data for a metric.

        Note: This requires historical data storage which is not
        implemented in the current simple version. Returns empty list.

        Args:
            metric: Name of the metric
            bucket_minutes: Time bucket size in minutes

        Returns:
            List of (timestamp, value) tuples
        """
        # TODO: Implement with time-series storage (e.g., circular buffer)
        return []
