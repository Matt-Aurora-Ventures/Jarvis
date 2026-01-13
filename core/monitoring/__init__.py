"""
System Health Monitoring Module

Provides health checks, alerts, metrics, and system monitoring.
"""

from core.monitoring.health import HealthMonitor, ComponentHealth, SystemHealth
from core.monitoring.alerts import AlertManager, Alert, AlertSeverity
from core.monitoring.metrics import (
    metrics, Counter, Gauge, Histogram,
    http_requests, http_latency, active_connections,
    provider_calls, provider_latency, trade_executions,
    cache_hits, cache_misses
)
from core.monitoring.tracing import tracer, Span, get_current_trace_id
from core.monitoring.alerting import alert_manager, AlertRule, AlertStatus

__all__ = [
    "HealthMonitor",
    "ComponentHealth",
    "SystemHealth",
    "AlertManager",
    "Alert",
    "AlertSeverity",
    "metrics",
    "Counter",
    "Gauge", 
    "Histogram",
    "http_requests",
    "http_latency",
    "active_connections",
    "provider_calls",
    "provider_latency",
    "trade_executions",
    "cache_hits",
    "cache_misses",
    "tracer",
    "Span",
    "get_current_trace_id",
    "alert_manager",
    "AlertRule",
    "AlertStatus",
]
