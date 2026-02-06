"""
Prometheus Exporter Module.

Exports metrics in Prometheus text format for scraping by Prometheus server.

Metrics exported:
- clawdbot_messages_total{bot, direction} - Counter of messages
- clawdbot_response_seconds{bot} - Response time summary
- clawdbot_errors_total{bot, type} - Counter of errors
"""

import time
from typing import List, Optional

from core.metrics.aggregator import MetricsAggregator


class PrometheusExporter:
    """
    Exports metrics in Prometheus text format.

    Follows the Prometheus exposition format:
    https://prometheus.io/docs/instrumenting/exposition_formats/
    """

    def __init__(
        self,
        aggregator: MetricsAggregator,
        include_timestamp: bool = False,
    ):
        """
        Initialize the Prometheus exporter.

        Args:
            aggregator: MetricsAggregator instance to export from
            include_timestamp: Whether to include timestamps on metric lines
        """
        self.aggregator = aggregator
        self.include_timestamp = include_timestamp

    def export(self) -> str:
        """
        Export all metrics in Prometheus text format.

        Returns:
            String containing metrics in Prometheus exposition format
        """
        lines: List[str] = []

        # Get current timestamp in milliseconds
        timestamp_ms = int(time.time() * 1000) if self.include_timestamp else None

        # Export messages_total metric
        lines.extend(self._export_messages_total(timestamp_ms))

        # Export response_seconds metric
        lines.extend(self._export_response_seconds(timestamp_ms))

        # Export errors_total metric
        lines.extend(self._export_errors_total(timestamp_ms))

        return "\n".join(lines) + "\n"

    def _export_messages_total(self, timestamp_ms: Optional[int]) -> List[str]:
        """Export clawdbot_messages_total metric."""
        lines: List[str] = []

        # HELP and TYPE comments
        lines.append("# HELP clawdbot_messages_total Total number of messages processed by bots")
        lines.append("# TYPE clawdbot_messages_total counter")

        for source in self.aggregator.sources:
            bot_name = source.bot_name
            stats = source.get_stats()

            # Received messages
            value = stats["messages_received"]
            metric_line = f'clawdbot_messages_total{{bot="{bot_name}",direction="received"}} {value}'
            if timestamp_ms:
                metric_line += f" {timestamp_ms}"
            lines.append(metric_line)

            # Sent messages
            value = stats["messages_sent"]
            metric_line = f'clawdbot_messages_total{{bot="{bot_name}",direction="sent"}} {value}'
            if timestamp_ms:
                metric_line += f" {timestamp_ms}"
            lines.append(metric_line)

        return lines

    def _export_response_seconds(self, timestamp_ms: Optional[int]) -> List[str]:
        """Export clawdbot_response_seconds metric."""
        lines: List[str] = []

        # HELP and TYPE comments
        lines.append("# HELP clawdbot_response_seconds Response time in seconds")
        lines.append("# TYPE clawdbot_response_seconds summary")

        for source in self.aggregator.sources:
            bot_name = source.bot_name
            response_times = source.response_times

            if not response_times:
                # Export zero values if no data
                sum_value = 0.0
                count_value = 0
            else:
                sum_value = sum(response_times)
                count_value = len(response_times)

            # Sum
            metric_line = f'clawdbot_response_seconds_sum{{bot="{bot_name}"}} {sum_value}'
            if timestamp_ms:
                metric_line += f" {timestamp_ms}"
            lines.append(metric_line)

            # Count
            metric_line = f'clawdbot_response_seconds_count{{bot="{bot_name}"}} {count_value}'
            if timestamp_ms:
                metric_line += f" {timestamp_ms}"
            lines.append(metric_line)

            # Calculate and export quantiles if we have data
            if response_times:
                p50, p95, p99 = self._calculate_quantiles(response_times)

                for quantile, value in [("0.5", p50), ("0.95", p95), ("0.99", p99)]:
                    metric_line = f'clawdbot_response_seconds{{bot="{bot_name}",quantile="{quantile}"}} {value}'
                    if timestamp_ms:
                        metric_line += f" {timestamp_ms}"
                    lines.append(metric_line)

        return lines

    def _export_errors_total(self, timestamp_ms: Optional[int]) -> List[str]:
        """Export clawdbot_errors_total metric."""
        lines: List[str] = []

        # HELP and TYPE comments
        lines.append("# HELP clawdbot_errors_total Total number of errors by bot")
        lines.append("# TYPE clawdbot_errors_total counter")

        for source in self.aggregator.sources:
            bot_name = source.bot_name
            stats = source.get_stats()

            value = stats["errors_total"]
            # For now, use "general" as the error type
            # Could be extended to track specific error types
            metric_line = f'clawdbot_errors_total{{bot="{bot_name}",type="general"}} {value}'
            if timestamp_ms:
                metric_line += f" {timestamp_ms}"
            lines.append(metric_line)

        return lines

    def _calculate_quantiles(self, data: List[float]) -> tuple:
        """
        Calculate quantiles for response times.

        Args:
            data: List of response times

        Returns:
            Tuple of (p50, p95, p99)
        """
        if not data:
            return (0.0, 0.0, 0.0)

        sorted_data = sorted(data)
        n = len(sorted_data)

        def quantile(p: float) -> float:
            """Calculate the p-th quantile (0-1 scale)."""
            if n == 1:
                return sorted_data[0]
            k = (n - 1) * p
            f = int(k)
            c = min(f + 1, n - 1)
            d = k - f
            return sorted_data[f] + d * (sorted_data[c] - sorted_data[f])

        return (quantile(0.5), quantile(0.95), quantile(0.99))
