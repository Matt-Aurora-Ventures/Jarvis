"""
JARVIS Health Module

Provides health check functionality including:
- Kubernetes-style liveness, readiness, and startup probes
- Comprehensive health checking (HealthChecker)
- Health status enums and reports
- Bot health monitoring (HealthMonitor)
- Health check classes (ProcessCheck, MemoryCheck, etc.)
- Health reporting with Telegram alerts (HealthReporter)
"""

from .probes import (
    ProbeStatus,
    ProbeResult,
    ProbeConfig,
    LivenessProbe,
    ReadinessProbe,
    StartupProbe,
    HealthProbeManager,
    get_probe_manager,
    setup_default_probes,
    check_database_connection,
    check_redis_connection,
    check_memory_usage,
    check_disk_space,
    check_cpu_usage,
)

from .status import (
    HealthStatus,
    ComponentHealth,
    HealthReport,
    format_report,
    determine_overall_status,
)

from .checker import HealthChecker

from .monitor import (
    HealthMonitor,
    BotStatus,
)

from .checks import (
    CheckResult,
    ProcessCheck,
    MemoryCheck,
    ResponseCheck,
    APICheck,
    DiskCheck,
)

from .reporter import (
    HealthReporter,
    AlertResult,
)

__all__ = [
    # Probes
    'ProbeStatus',
    'ProbeResult',
    'ProbeConfig',
    'LivenessProbe',
    'ReadinessProbe',
    'StartupProbe',
    'HealthProbeManager',
    'get_probe_manager',
    'setup_default_probes',
    'check_database_connection',
    'check_redis_connection',
    'check_memory_usage',
    'check_disk_space',
    'check_cpu_usage',
    # Status
    'HealthStatus',
    'ComponentHealth',
    'HealthReport',
    'format_report',
    'determine_overall_status',
    # Checker
    'HealthChecker',
    # Monitor
    'HealthMonitor',
    'BotStatus',
    # Checks
    'CheckResult',
    'ProcessCheck',
    'MemoryCheck',
    'ResponseCheck',
    'APICheck',
    'DiskCheck',
    # Reporter
    'HealthReporter',
    'AlertResult',
]
