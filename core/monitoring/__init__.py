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
from core.monitoring.metrics_collector import (
    MetricsCollector,
    ErrorRateStats,
    LatencyStats,
    AlertThreshold,
    get_metrics_collector,
    track_request,
)
from core.monitoring.uptime import (
    UptimeMonitor,
    ServiceStatus,
    ServiceUptime,
    HealthCheck,
    CheckResult,
    Incident,
    UptimeStats,
    get_uptime_monitor,
    http_health_check,
    database_health_check,
    redis_health_check,
    custom_health_check,
)
from core.monitoring.memory_alerts import (
    MemoryMonitor,
    MemorySnapshot,
    MemoryAlert,
    MemoryAlertLevel,
    MemoryThresholds,
    MemoryStats,
    get_memory_monitor,
    memory_check,
)
from core.monitoring.log_aggregator import (
    LogAggregator,
    LogEntry,
    LogLevel,
    LogQuery,
    LogStats,
    LogContext,
    AggregatingHandler,
    get_log_aggregator,
    setup_log_aggregation,
)
# New comprehensive monitoring modules
from core.monitoring.health_check import (
    SystemHealthChecker,
    HealthLevel,
    ComponentStatus,
    get_system_health_checker,
)
from core.monitoring.alerter import (
    Alerter,
    AlertType,
    AlertResult,
    get_alerter,
)
from core.monitoring.alert_rules import (
    AlertRulesEngine,
    get_alert_rules_engine,
)
from core.monitoring.performance_tracker import (
    PerformanceTracker,
    get_performance_tracker,
)
from core.monitoring.budget_tracker import (
    BudgetTracker,
    get_budget_tracker,
)
from core.monitoring.dashboard_data import (
    DashboardDataProvider,
    create_dashboard_router,
    get_dashboard_provider,
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
    # Metrics collector
    "MetricsCollector",
    "ErrorRateStats",
    "LatencyStats",
    "AlertThreshold",
    "get_metrics_collector",
    "track_request",
    # Uptime monitoring
    "UptimeMonitor",
    "ServiceStatus",
    "ServiceUptime",
    "HealthCheck",
    "CheckResult",
    "Incident",
    "UptimeStats",
    "get_uptime_monitor",
    "http_health_check",
    "database_health_check",
    "redis_health_check",
    "custom_health_check",
    # Memory monitoring
    "MemoryMonitor",
    "MemorySnapshot",
    "MemoryAlert",
    "MemoryAlertLevel",
    "MemoryThresholds",
    "MemoryStats",
    "get_memory_monitor",
    "memory_check",
    # Log aggregation
    "LogAggregator",
    "LogEntry",
    "LogLevel",
    "LogQuery",
    "LogStats",
    "LogContext",
    "AggregatingHandler",
    "get_log_aggregator",
    "setup_log_aggregation",
    # System health checker
    "SystemHealthChecker",
    "HealthLevel",
    "ComponentStatus",
    "get_system_health_checker",
    # Alerter
    "Alerter",
    "AlertType",
    "AlertResult",
    "get_alerter",
    # Alert rules
    "AlertRulesEngine",
    "get_alert_rules_engine",
    # Performance tracker
    "PerformanceTracker",
    "get_performance_tracker",
    # Budget tracker
    "BudgetTracker",
    "get_budget_tracker",
    # Dashboard data
    "DashboardDataProvider",
    "create_dashboard_router",
    "get_dashboard_provider",
]
