"""
JARVIS Health Check Probes

Provides Kubernetes-style health probes for liveness,
readiness, and startup checks.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Callable, Awaitable, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import logging

logger = logging.getLogger(__name__)


class ProbeStatus(Enum):
    """Health probe status."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass
class ProbeResult:
    """Result of a health probe check."""
    status: ProbeStatus
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_healthy(self) -> bool:
        return self.status == ProbeStatus.HEALTHY

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ProbeConfig:
    """Configuration for a health probe."""
    initial_delay_seconds: int = 0
    period_seconds: int = 10
    timeout_seconds: int = 5
    success_threshold: int = 1
    failure_threshold: int = 3


HealthCheck = Callable[[], Awaitable[bool]]


class LivenessProbe:
    """
    Liveness probe to determine if the application is running.

    If liveness fails, the container should be restarted.

    Usage:
        probe = LivenessProbe()
        probe.add_check("memory", check_memory_usage)
        result = await probe.check()
    """

    def __init__(self, config: Optional[ProbeConfig] = None):
        self.config = config or ProbeConfig()
        self._checks: Dict[str, HealthCheck] = {}
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self._last_result: Optional[ProbeResult] = None

    def add_check(self, name: str, check: HealthCheck) -> None:
        """Add a liveness check."""
        self._checks[name] = check

    async def check(self) -> ProbeResult:
        """Run all liveness checks."""
        import time
        start = time.monotonic()

        details = {}
        all_healthy = True

        for name, check in self._checks.items():
            try:
                result = await asyncio.wait_for(
                    check(),
                    timeout=self.config.timeout_seconds
                )
                details[name] = {"status": "healthy" if result else "unhealthy"}
                if not result:
                    all_healthy = False
            except asyncio.TimeoutError:
                details[name] = {"status": "timeout"}
                all_healthy = False
            except Exception as e:
                details[name] = {"status": "error", "error": str(e)}
                all_healthy = False

        duration = (time.monotonic() - start) * 1000

        if all_healthy:
            self._consecutive_failures = 0
            self._consecutive_successes += 1
            status = ProbeStatus.HEALTHY
            message = "All liveness checks passed"
        else:
            self._consecutive_successes = 0
            self._consecutive_failures += 1
            status = ProbeStatus.UNHEALTHY
            message = "One or more liveness checks failed"

        self._last_result = ProbeResult(
            status=status,
            message=message,
            details=details,
            duration_ms=duration,
        )

        return self._last_result

    @property
    def is_alive(self) -> bool:
        """Check if the application is considered alive."""
        if self._last_result is None:
            return True  # Assume alive until checked

        if self._consecutive_failures >= self.config.failure_threshold:
            return False

        return True


class ReadinessProbe:
    """
    Readiness probe to determine if the application can serve traffic.

    If readiness fails, traffic should not be sent to this instance.

    Usage:
        probe = ReadinessProbe()
        probe.add_check("database", check_database_connection)
        probe.add_check("cache", check_cache_connection)
        result = await probe.check()
    """

    def __init__(self, config: Optional[ProbeConfig] = None):
        self.config = config or ProbeConfig()
        self._checks: Dict[str, HealthCheck] = {}
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self._last_result: Optional[ProbeResult] = None

    def add_check(self, name: str, check: HealthCheck) -> None:
        """Add a readiness check."""
        self._checks[name] = check

    async def check(self) -> ProbeResult:
        """Run all readiness checks."""
        import time
        start = time.monotonic()

        details = {}
        all_ready = True
        degraded = False

        for name, check in self._checks.items():
            try:
                result = await asyncio.wait_for(
                    check(),
                    timeout=self.config.timeout_seconds
                )
                details[name] = {"status": "ready" if result else "not_ready"}
                if not result:
                    all_ready = False
            except asyncio.TimeoutError:
                details[name] = {"status": "timeout"}
                degraded = True
            except Exception as e:
                details[name] = {"status": "error", "error": str(e)}
                all_ready = False

        duration = (time.monotonic() - start) * 1000

        if all_ready and not degraded:
            self._consecutive_failures = 0
            self._consecutive_successes += 1
            status = ProbeStatus.HEALTHY
            message = "All readiness checks passed"
        elif degraded:
            status = ProbeStatus.DEGRADED
            message = "Some readiness checks degraded"
        else:
            self._consecutive_successes = 0
            self._consecutive_failures += 1
            status = ProbeStatus.UNHEALTHY
            message = "One or more readiness checks failed"

        self._last_result = ProbeResult(
            status=status,
            message=message,
            details=details,
            duration_ms=duration,
        )

        return self._last_result

    @property
    def is_ready(self) -> bool:
        """Check if the application is ready to serve traffic."""
        if self._last_result is None:
            return False  # Not ready until checks pass

        if self._consecutive_failures >= self.config.failure_threshold:
            return False

        if self._consecutive_successes >= self.config.success_threshold:
            return True

        return self._last_result.is_healthy


class StartupProbe:
    """
    Startup probe to determine if the application has started.

    Startup probe runs during initialization and once it passes,
    liveness and readiness probes take over.

    Usage:
        probe = StartupProbe()
        probe.add_check("migrations", check_migrations_complete)
        probe.add_check("warmup", check_cache_warmup)
        result = await probe.check()
    """

    def __init__(self, config: Optional[ProbeConfig] = None):
        self.config = config or ProbeConfig(
            initial_delay_seconds=5,
            period_seconds=5,
            timeout_seconds=30,
            failure_threshold=30,  # 30 failures = 2.5 minutes
        )
        self._checks: Dict[str, HealthCheck] = {}
        self._started = False
        self._start_time: Optional[datetime] = None
        self._last_result: Optional[ProbeResult] = None

    def add_check(self, name: str, check: HealthCheck) -> None:
        """Add a startup check."""
        self._checks[name] = check

    async def check(self) -> ProbeResult:
        """Run all startup checks."""
        if self._start_time is None:
            self._start_time = datetime.utcnow()

        import time
        start = time.monotonic()

        details = {}
        all_started = True

        for name, check in self._checks.items():
            try:
                result = await asyncio.wait_for(
                    check(),
                    timeout=self.config.timeout_seconds
                )
                details[name] = {"status": "started" if result else "pending"}
                if not result:
                    all_started = False
            except asyncio.TimeoutError:
                details[name] = {"status": "timeout"}
                all_started = False
            except Exception as e:
                details[name] = {"status": "error", "error": str(e)}
                all_started = False

        duration = (time.monotonic() - start) * 1000

        if all_started:
            self._started = True
            status = ProbeStatus.HEALTHY
            message = "Application started successfully"
        else:
            status = ProbeStatus.UNHEALTHY
            message = "Application still starting"

        self._last_result = ProbeResult(
            status=status,
            message=message,
            details=details,
            duration_ms=duration,
        )

        return self._last_result

    @property
    def is_started(self) -> bool:
        """Check if the application has completed startup."""
        return self._started


class HealthProbeManager:
    """
    Manages all health probes for the application.

    Usage:
        manager = HealthProbeManager()

        # Add checks
        manager.liveness.add_check("heartbeat", lambda: True)
        manager.readiness.add_check("database", check_db)
        manager.startup.add_check("migrations", check_migrations)

        # Run probes
        status = await manager.check_all()
    """

    def __init__(self):
        self.liveness = LivenessProbe()
        self.readiness = ReadinessProbe()
        self.startup = StartupProbe()

    async def check_liveness(self) -> ProbeResult:
        """Run liveness probe."""
        return await self.liveness.check()

    async def check_readiness(self) -> ProbeResult:
        """Run readiness probe."""
        return await self.readiness.check()

    async def check_startup(self) -> ProbeResult:
        """Run startup probe."""
        return await self.startup.check()

    async def check_all(self) -> Dict[str, ProbeResult]:
        """Run all probes."""
        return {
            "startup": await self.check_startup(),
            "liveness": await self.check_liveness(),
            "readiness": await self.check_readiness(),
        }

    def get_status(self) -> Dict[str, Any]:
        """Get current status of all probes."""
        return {
            "started": self.startup.is_started,
            "alive": self.liveness.is_alive,
            "ready": self.readiness.is_ready,
        }


# ============================================================================
# Common Health Checks
# ============================================================================

async def check_database_connection(db_session) -> bool:
    """Check if database is accessible."""
    try:
        await db_session.execute("SELECT 1")
        return True
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")
        return False


async def check_redis_connection(redis_client) -> bool:
    """Check if Redis is accessible."""
    try:
        await redis_client.ping()
        return True
    except Exception as e:
        logger.warning(f"Redis health check failed: {e}")
        return False


async def check_memory_usage(threshold_mb: float = 1000) -> bool:
    """Check if memory usage is below threshold."""
    try:
        import psutil
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        return memory_mb < threshold_mb
    except ImportError:
        return True  # Can't check without psutil


async def check_disk_space(path: str = "/", threshold_percent: float = 90) -> bool:
    """Check if disk space is available."""
    try:
        import psutil
        usage = psutil.disk_usage(path)
        return usage.percent < threshold_percent
    except ImportError:
        return True  # Can't check without psutil


async def check_cpu_usage(threshold_percent: float = 90) -> bool:
    """Check if CPU usage is below threshold."""
    try:
        import psutil
        cpu_percent = psutil.cpu_percent(interval=0.1)
        return cpu_percent < threshold_percent
    except ImportError:
        return True  # Can't check without psutil


# Global instance
_manager: Optional[HealthProbeManager] = None


def get_probe_manager() -> HealthProbeManager:
    """Get the global health probe manager."""
    global _manager
    if _manager is None:
        _manager = HealthProbeManager()
    return _manager


def setup_default_probes() -> HealthProbeManager:
    """Set up probes with default checks."""
    manager = get_probe_manager()

    # Liveness checks
    manager.liveness.add_check("memory", lambda: check_memory_usage(2000))
    manager.liveness.add_check("cpu", lambda: check_cpu_usage(95))

    # Readiness checks are added by the application

    logger.info("Health probes initialized with default checks")
    return manager
