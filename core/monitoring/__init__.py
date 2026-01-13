"""
System Health Monitoring Module

Provides health checks, alerts, metrics, and system monitoring.
"""

from core.monitoring.health import HealthMonitor, ComponentHealth, SystemHealth
from core.monitoring.alerts import AlertManager, Alert, AlertSeverity
from core.monitoring.dashboard import create_health_router, get_health_router
from core.monitoring.metrics import (
    metrics, Counter, Gauge, Histogram,
    http_requests, http_latency, active_connections,
    provider_calls, provider_latency, trade_executions,
    cache_hits, cache_misses
)
from core.monitoring.tracing import tracer, Span, get_current_trace_id
from core.monitoring.alerting import alert_manager, AlertRule, AlertStatus
from core.monitoring.bot_health import (
    BotHealthChecker,
    BotHealth,
    BotMetrics,
    BotType,
    get_bot_health_checker,
    register_bot_checks,
    track_bot_activity,
    track_command,
)

__all__ = [
    "HealthMonitor",
    "ComponentHealth",
    "SystemHealth",
    "AlertManager",
    "Alert",
    "AlertSeverity",
    "create_health_router",
    "get_health_router",
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
    # Bot health
    "BotHealthChecker",
    "BotHealth",
    "BotMetrics",
    "BotType",
    "get_bot_health_checker",
    "register_bot_checks",
    "track_bot_activity",
    "track_command",
]
