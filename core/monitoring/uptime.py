"""
JARVIS Uptime Monitoring

Tracks system uptime, service availability, and provides status pages.
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Any, Awaitable
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """Service health status."""
    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    PARTIAL_OUTAGE = "partial_outage"
    MAJOR_OUTAGE = "major_outage"
    MAINTENANCE = "maintenance"
    UNKNOWN = "unknown"


@dataclass
class HealthCheck:
    """Health check configuration."""
    name: str
    check_fn: Callable[[], Awaitable[bool]]
    interval_seconds: int = 30
    timeout_seconds: int = 10
    critical: bool = True
    description: str = ""


@dataclass
class CheckResult:
    """Result of a health check."""
    name: str
    healthy: bool
    latency_ms: float
    timestamp: datetime
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ServiceUptime:
    """Uptime statistics for a service."""
    service: str
    status: ServiceStatus
    uptime_percent: float
    last_check: datetime
    last_incident: Optional[datetime]
    checks_passed: int
    checks_failed: int
    avg_latency_ms: float
    current_streak_seconds: float


@dataclass
class Incident:
    """Service incident record."""
    id: str
    service: str
    status: ServiceStatus
    title: str
    description: str
    started_at: datetime
    resolved_at: Optional[datetime] = None
    updates: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class UptimeStats:
    """Overall uptime statistics."""
    start_time: datetime
    uptime_seconds: float
    services_operational: int
    services_degraded: int
    services_down: int
    overall_status: ServiceStatus
    incidents_24h: int
    mttr_seconds: Optional[float]  # Mean Time To Recovery


class UptimeMonitor:
    """Monitors system uptime and service health."""

    def __init__(
        self,
        check_interval: int = 30,
        history_retention_hours: int = 24
    ):
        self.check_interval = check_interval
        self.history_retention_hours = history_retention_hours

        self._start_time = datetime.utcnow()
        self._checks: Dict[str, HealthCheck] = {}
        self._results: Dict[str, List[CheckResult]] = defaultdict(list)
        self._incidents: List[Incident] = []
        self._running = False
        self._task: Optional[asyncio.Task] = None

        # Service status tracking
        self._service_status: Dict[str, ServiceStatus] = {}
        self._status_since: Dict[str, datetime] = {}

        # Callbacks
        self._on_status_change: List[Callable[[str, ServiceStatus, ServiceStatus], Awaitable[None]]] = []
        self._on_incident: List[Callable[[Incident], Awaitable[None]]] = []

    def register_check(
        self,
        name: str,
        check_fn: Callable[[], Awaitable[bool]],
        interval_seconds: int = 30,
        timeout_seconds: int = 10,
        critical: bool = True,
        description: str = ""
    ) -> None:
        """Register a health check."""
        self._checks[name] = HealthCheck(
            name=name,
            check_fn=check_fn,
            interval_seconds=interval_seconds,
            timeout_seconds=timeout_seconds,
            critical=critical,
            description=description
        )
        self._service_status[name] = ServiceStatus.UNKNOWN
        self._status_since[name] = datetime.utcnow()
        logger.info(f"Registered health check: {name}")

    def on_status_change(
        self,
        callback: Callable[[str, ServiceStatus, ServiceStatus], Awaitable[None]]
    ) -> None:
        """Register callback for status changes."""
        self._on_status_change.append(callback)

    def on_incident(
        self,
        callback: Callable[[Incident], Awaitable[None]]
    ) -> None:
        """Register callback for incidents."""
        self._on_incident.append(callback)

    async def start(self) -> None:
        """Start the uptime monitor."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Uptime monitor started")

    async def stop(self) -> None:
        """Stop the uptime monitor."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Uptime monitor stopped")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            await self._run_all_checks()
            await self._cleanup_old_results()
            await asyncio.sleep(self.check_interval)

    async def _run_all_checks(self) -> None:
        """Run all registered health checks."""
        tasks = [
            self._run_check(check)
            for check in self._checks.values()
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _run_check(self, check: HealthCheck) -> None:
        """Run a single health check."""
        start_time = time.monotonic()

        try:
            result = await asyncio.wait_for(
                check.check_fn(),
                timeout=check.timeout_seconds
            )
            latency_ms = (time.monotonic() - start_time) * 1000

            check_result = CheckResult(
                name=check.name,
                healthy=result,
                latency_ms=latency_ms,
                timestamp=datetime.utcnow()
            )

        except asyncio.TimeoutError:
            latency_ms = check.timeout_seconds * 1000
            check_result = CheckResult(
                name=check.name,
                healthy=False,
                latency_ms=latency_ms,
                timestamp=datetime.utcnow(),
                error="Timeout"
            )

        except Exception as e:
            latency_ms = (time.monotonic() - start_time) * 1000
            check_result = CheckResult(
                name=check.name,
                healthy=False,
                latency_ms=latency_ms,
                timestamp=datetime.utcnow(),
                error=str(e)
            )

        # Store result
        self._results[check.name].append(check_result)

        # Update status
        await self._update_status(check.name, check_result)

    async def _update_status(self, service: str, result: CheckResult) -> None:
        """Update service status based on check result."""
        old_status = self._service_status.get(service, ServiceStatus.UNKNOWN)

        # Determine new status based on recent checks
        recent_results = self._results[service][-5:]  # Last 5 checks

        if not recent_results:
            new_status = ServiceStatus.UNKNOWN
        else:
            failures = sum(1 for r in recent_results if not r.healthy)

            if failures == 0:
                new_status = ServiceStatus.OPERATIONAL
            elif failures <= 1:
                new_status = ServiceStatus.DEGRADED
            elif failures <= 3:
                new_status = ServiceStatus.PARTIAL_OUTAGE
            else:
                new_status = ServiceStatus.MAJOR_OUTAGE

        # Update if changed
        if new_status != old_status:
            self._service_status[service] = new_status
            self._status_since[service] = datetime.utcnow()

            # Notify callbacks
            for callback in self._on_status_change:
                try:
                    await callback(service, old_status, new_status)
                except Exception as e:
                    logger.error(f"Status change callback error: {e}")

            # Create incident if going from operational to degraded/outage
            if old_status == ServiceStatus.OPERATIONAL and new_status in (
                ServiceStatus.DEGRADED,
                ServiceStatus.PARTIAL_OUTAGE,
                ServiceStatus.MAJOR_OUTAGE
            ):
                await self._create_incident(service, new_status, result)

            # Resolve incident if returning to operational
            elif new_status == ServiceStatus.OPERATIONAL and old_status in (
                ServiceStatus.DEGRADED,
                ServiceStatus.PARTIAL_OUTAGE,
                ServiceStatus.MAJOR_OUTAGE
            ):
                await self._resolve_incident(service)

    async def _create_incident(
        self,
        service: str,
        status: ServiceStatus,
        result: CheckResult
    ) -> None:
        """Create a new incident."""
        incident = Incident(
            id=f"inc_{int(time.time())}_{service}",
            service=service,
            status=status,
            title=f"{service} experiencing issues",
            description=result.error or "Service health check failed",
            started_at=datetime.utcnow()
        )

        self._incidents.append(incident)

        # Notify callbacks
        for callback in self._on_incident:
            try:
                await callback(incident)
            except Exception as e:
                logger.error(f"Incident callback error: {e}")

        logger.warning(f"Incident created: {incident.id} - {incident.title}")

    async def _resolve_incident(self, service: str) -> None:
        """Resolve the latest incident for a service."""
        for incident in reversed(self._incidents):
            if incident.service == service and incident.resolved_at is None:
                incident.resolved_at = datetime.utcnow()
                incident.status = ServiceStatus.OPERATIONAL
                incident.updates.append({
                    "time": datetime.utcnow().isoformat(),
                    "message": "Service has recovered"
                })
                logger.info(f"Incident resolved: {incident.id}")
                break

    async def _cleanup_old_results(self) -> None:
        """Remove results older than retention period."""
        cutoff = datetime.utcnow() - timedelta(hours=self.history_retention_hours)

        for service in self._results:
            self._results[service] = [
                r for r in self._results[service]
                if r.timestamp > cutoff
            ]

    def get_status(self, service: str) -> ServiceStatus:
        """Get current status of a service."""
        return self._service_status.get(service, ServiceStatus.UNKNOWN)

    def get_uptime(self, service: str) -> ServiceUptime:
        """Get uptime statistics for a service."""
        results = self._results.get(service, [])

        if not results:
            return ServiceUptime(
                service=service,
                status=ServiceStatus.UNKNOWN,
                uptime_percent=0.0,
                last_check=datetime.utcnow(),
                last_incident=None,
                checks_passed=0,
                checks_failed=0,
                avg_latency_ms=0.0,
                current_streak_seconds=0.0
            )

        passed = sum(1 for r in results if r.healthy)
        failed = len(results) - passed
        uptime_pct = (passed / len(results)) * 100 if results else 0

        avg_latency = sum(r.latency_ms for r in results) / len(results)

        # Calculate current streak
        streak_seconds = 0.0
        status_since = self._status_since.get(service)
        if status_since and self._service_status.get(service) == ServiceStatus.OPERATIONAL:
            streak_seconds = (datetime.utcnow() - status_since).total_seconds()

        # Find last incident
        last_incident = None
        for incident in reversed(self._incidents):
            if incident.service == service:
                last_incident = incident.started_at
                break

        return ServiceUptime(
            service=service,
            status=self._service_status.get(service, ServiceStatus.UNKNOWN),
            uptime_percent=uptime_pct,
            last_check=results[-1].timestamp,
            last_incident=last_incident,
            checks_passed=passed,
            checks_failed=failed,
            avg_latency_ms=avg_latency,
            current_streak_seconds=streak_seconds
        )

    def get_overall_stats(self) -> UptimeStats:
        """Get overall uptime statistics."""
        now = datetime.utcnow()
        uptime_seconds = (now - self._start_time).total_seconds()

        # Count services by status
        operational = sum(
            1 for s in self._service_status.values()
            if s == ServiceStatus.OPERATIONAL
        )
        degraded = sum(
            1 for s in self._service_status.values()
            if s in (ServiceStatus.DEGRADED, ServiceStatus.PARTIAL_OUTAGE)
        )
        down = sum(
            1 for s in self._service_status.values()
            if s == ServiceStatus.MAJOR_OUTAGE
        )

        # Overall status
        if down > 0:
            overall = ServiceStatus.MAJOR_OUTAGE
        elif degraded > 0:
            overall = ServiceStatus.DEGRADED
        elif operational > 0:
            overall = ServiceStatus.OPERATIONAL
        else:
            overall = ServiceStatus.UNKNOWN

        # Incidents in last 24h
        cutoff = now - timedelta(hours=24)
        incidents_24h = sum(
            1 for i in self._incidents
            if i.started_at > cutoff
        )

        # Calculate MTTR
        mttr = self._calculate_mttr()

        return UptimeStats(
            start_time=self._start_time,
            uptime_seconds=uptime_seconds,
            services_operational=operational,
            services_degraded=degraded,
            services_down=down,
            overall_status=overall,
            incidents_24h=incidents_24h,
            mttr_seconds=mttr
        )

    def _calculate_mttr(self) -> Optional[float]:
        """Calculate Mean Time To Recovery."""
        resolved_incidents = [
            i for i in self._incidents
            if i.resolved_at is not None
        ]

        if not resolved_incidents:
            return None

        total_recovery_time = sum(
            (i.resolved_at - i.started_at).total_seconds()
            for i in resolved_incidents
        )

        return total_recovery_time / len(resolved_incidents)

    def get_incidents(
        self,
        service: Optional[str] = None,
        resolved: Optional[bool] = None,
        limit: int = 10
    ) -> List[Incident]:
        """Get incident history."""
        incidents = self._incidents

        if service:
            incidents = [i for i in incidents if i.service == service]

        if resolved is not None:
            if resolved:
                incidents = [i for i in incidents if i.resolved_at is not None]
            else:
                incidents = [i for i in incidents if i.resolved_at is None]

        return sorted(incidents, key=lambda i: i.started_at, reverse=True)[:limit]

    def get_status_page_data(self) -> Dict[str, Any]:
        """Get data for status page rendering."""
        services = []
        for name in self._checks:
            uptime = self.get_uptime(name)
            services.append({
                "name": name,
                "status": uptime.status.value,
                "uptime_percent": round(uptime.uptime_percent, 2),
                "avg_latency_ms": round(uptime.avg_latency_ms, 1),
                "last_check": uptime.last_check.isoformat()
            })

        overall = self.get_overall_stats()
        active_incidents = self.get_incidents(resolved=False)

        return {
            "overall_status": overall.overall_status.value,
            "uptime_seconds": overall.uptime_seconds,
            "start_time": overall.start_time.isoformat(),
            "services": services,
            "active_incidents": [
                {
                    "id": i.id,
                    "service": i.service,
                    "title": i.title,
                    "status": i.status.value,
                    "started_at": i.started_at.isoformat()
                }
                for i in active_incidents
            ],
            "incidents_24h": overall.incidents_24h,
            "mttr_seconds": overall.mttr_seconds
        }


# Global instance
_uptime_monitor: Optional[UptimeMonitor] = None


def get_uptime_monitor() -> UptimeMonitor:
    """Get the global uptime monitor instance."""
    global _uptime_monitor
    if _uptime_monitor is None:
        _uptime_monitor = UptimeMonitor()
    return _uptime_monitor


# Common health check factories
def http_health_check(url: str, timeout: int = 5) -> Callable[[], Awaitable[bool]]:
    """Create HTTP health check."""
    import httpx

    async def check() -> bool:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=timeout)
            return response.status_code == 200

    return check


def database_health_check(pool: Any) -> Callable[[], Awaitable[bool]]:
    """Create database health check."""
    async def check() -> bool:
        try:
            with pool.get_connection() as conn:
                conn.execute("SELECT 1")
                return True
        except Exception:
            return False

    return check


def redis_health_check(client: Any) -> Callable[[], Awaitable[bool]]:
    """Create Redis health check."""
    async def check() -> bool:
        try:
            await client.ping()
            return True
        except Exception:
            return False

    return check


def custom_health_check(
    check_fn: Callable[[], Any],
    expected_value: Any = True
) -> Callable[[], Awaitable[bool]]:
    """Create custom health check."""
    async def check() -> bool:
        if asyncio.iscoroutinefunction(check_fn):
            result = await check_fn()
        else:
            result = check_fn()
        return result == expected_value

    return check
