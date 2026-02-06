"""
Metrics collection and export module.

This module provides:
- BotMetrics: Per-bot metrics collection (messages, commands, errors, response times)
- MetricsAggregator: Aggregate metrics across bots with hourly/daily stats
- PrometheusExporter: Export metrics in Prometheus format
"""

from core.metrics.bot_metrics import BotMetrics, get_bot_metrics, list_all_bots
from core.metrics.aggregator import MetricsAggregator, HourlyStats, DailyStats
from core.metrics.exporter import PrometheusExporter

__all__ = [
    "BotMetrics",
    "get_bot_metrics",
    "list_all_bots",
    "MetricsAggregator",
    "HourlyStats",
    "DailyStats",
    "PrometheusExporter",
]
