"""
Health Status Module

Provides HealthStatus enum and HealthReport dataclass for health check results.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class HealthStatus(Enum):
    """Health status levels for components and overall system."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    WARNING = "warning"
    CRITICAL = "critical"
    NOT_RUNNING = "not_running"
    NOT_CONFIGURED = "not_configured"
    TIMEOUT = "timeout"
    ERROR = "error"
    AVAILABLE = "available"
    RATE_LIMITED = "rate_limited"

    def __str__(self) -> str:
        return self.value

    @property
    def is_ok(self) -> bool:
        """Check if status indicates healthy/available state."""
        return self in (HealthStatus.HEALTHY, HealthStatus.AVAILABLE)

    @property
    def is_problematic(self) -> bool:
        """Check if status indicates a problem."""
        return self in (
            HealthStatus.UNHEALTHY,
            HealthStatus.CRITICAL,
            HealthStatus.ERROR,
            HealthStatus.NOT_RUNNING,
            HealthStatus.TIMEOUT,
        )


@dataclass
class ComponentHealth:
    """Health status for a single component."""
    name: str
    status: HealthStatus
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "latency_ms": self.latency_ms,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class HealthReport:
    """Comprehensive health report for the system."""
    overall_status: HealthStatus
    components: Dict[str, ComponentHealth] = field(default_factory=dict)
    processes: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    endpoints: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    logs: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    memory: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    api_quotas: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: float = 0.0
    summary: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "overall_status": self.overall_status.value,
            "components": {
                name: comp.to_dict() for name, comp in self.components.items()
            },
            "processes": self.processes,
            "endpoints": self.endpoints,
            "logs": self.logs,
            "memory": self.memory,
            "api_quotas": self.api_quotas,
            "timestamp": self.timestamp.isoformat(),
            "duration_ms": self.duration_ms,
            "summary": self.summary,
        }


def format_report(checks: Dict[str, Any], verbose: bool = False) -> str:
    """
    Format health check results as a human-readable report.

    Args:
        checks: Dictionary of health check results
        verbose: If True, include detailed information

    Returns:
        Formatted string report
    """
    lines = []
    lines.append("=" * 60)
    lines.append("JARVIS HEALTH REPORT")
    lines.append("=" * 60)

    # Overall status
    overall = checks.get("overall_status", "unknown")
    status_icon = {
        "healthy": "[OK]",
        "degraded": "[WARN]",
        "warning": "[WARN]",
        "unhealthy": "[FAIL]",
        "critical": "[CRIT]",
        "unknown": "[???]",
    }.get(overall, "[???]")

    lines.append(f"\nOverall Status: {status_icon} {overall.upper()}")

    # Timestamp
    ts = checks.get("timestamp", "N/A")
    lines.append(f"Checked at: {ts}")

    # Duration
    duration = checks.get("duration_ms", 0)
    lines.append(f"Check duration: {duration:.1f}ms")

    # Summary
    summary = checks.get("summary", {})
    if summary:
        lines.append(f"\nSummary: {summary.get('healthy', 0)} healthy, "
                    f"{summary.get('degraded', 0)} degraded, "
                    f"{summary.get('critical', 0)} critical")

    lines.append("")
    lines.append("-" * 60)

    # Processes
    processes = checks.get("processes", {})
    if processes:
        lines.append("\nPROCESSES:")
        for name, info in processes.items():
            status = info.get("status", "unknown")
            pid = info.get("pid", "N/A")
            icon = "[OK]" if status == "running" else "[--]"
            lines.append(f"  {icon} {name}: {status} (PID: {pid})")

    # Endpoints
    endpoints = checks.get("endpoints", {})
    if endpoints:
        lines.append("\nENDPOINTS:")
        for name, info in endpoints.items():
            status = info.get("status", "unknown")
            latency = info.get("response_time_ms", 0)
            icon = "[OK]" if status == "healthy" else "[--]"
            lines.append(f"  {icon} {name}: {status} ({latency:.0f}ms)")

    # Memory
    memory = checks.get("memory", {})
    if memory:
        lines.append("\nMEMORY:")
        for name, info in memory.items():
            status = info.get("status", "unknown")
            mem_mb = info.get("memory_mb", 0)
            icon = "[OK]" if status == "healthy" else "[WARN]" if status == "warning" else "[--]"
            lines.append(f"  {icon} {name}: {mem_mb}MB ({status})")

    # API Quotas
    api_quotas = checks.get("api_quotas", {})
    if api_quotas:
        lines.append("\nAPI QUOTAS:")
        for name, info in api_quotas.items():
            status = info.get("status", "unknown")
            icon = "[OK]" if status == "available" else "[--]"
            lines.append(f"  {icon} {name}: {status}")

    # Logs
    logs = checks.get("logs", {})
    if logs and verbose:
        lines.append("\nLOG ERRORS:")
        for name, info in logs.items():
            error_count = info.get("error_count", 0)
            warning_count = info.get("warning_count", 0)
            icon = "[OK]" if error_count == 0 else "[WARN]"
            lines.append(f"  {icon} {name}: {error_count} errors, {warning_count} warnings")

    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)


def determine_overall_status(checks: Dict[str, Dict[str, Any]]) -> str:
    """
    Determine overall health status from component checks.

    Args:
        checks: Dictionary of component check results

    Returns:
        Overall status string
    """
    has_critical = False
    has_degraded = False
    has_warning = False

    for name, info in checks.items():
        status = info.get("status", "unknown")

        if status in ("critical", "unhealthy", "error", "not_running"):
            has_critical = True
        elif status == "degraded":
            has_degraded = True
        elif status == "warning":
            has_warning = True

    if has_critical:
        return "critical"
    if has_degraded:
        return "degraded"
    if has_warning:
        return "warning"
    return "healthy"
