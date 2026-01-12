"""
Health Check System - Monitor component status and system health.
"""

import asyncio
import time
import logging
import psutil
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    """Health status of a single component."""
    name: str
    status: HealthStatus = HealthStatus.UNKNOWN
    message: str = ""
    last_check: str = ""
    latency_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemHealth:
    """Overall system health."""
    status: HealthStatus
    version: str
    uptime_seconds: float
    timestamp: str
    components: List[ComponentHealth]
    system_metrics: Dict[str, Any]


class HealthChecker:
    """
    Health check system for monitoring all components.

    Usage:
        checker = HealthChecker()

        # Register components
        checker.register("database", check_database)
        checker.register("redis", check_redis)
        checker.register("jupiter_api", check_jupiter)

        # Run checks
        health = await checker.check_all()
    """

    def __init__(self, version: str = "4.2.0"):
        self.version = version
        self.start_time = time.time()
        self._checks: Dict[str, Callable] = {}
        self._last_results: Dict[str, ComponentHealth] = {}

        # Register default checks
        self._register_default_checks()

    def _register_default_checks(self):
        """Register default health checks."""
        self.register("system", self._check_system)
        self.register("memory", self._check_memory)
        self.register("disk", self._check_disk)

    def register(self, name: str, check_fn: Callable):
        """
        Register a health check function.

        The function should return ComponentHealth or raise exception.
        """
        self._checks[name] = check_fn
        logger.debug(f"Registered health check: {name}")

    def unregister(self, name: str):
        """Unregister a health check."""
        if name in self._checks:
            del self._checks[name]

    async def check_component(self, name: str) -> ComponentHealth:
        """Run health check for a single component."""
        if name not in self._checks:
            return ComponentHealth(
                name=name,
                status=HealthStatus.UNKNOWN,
                message="No health check registered"
            )

        check_fn = self._checks[name]
        start = time.time()

        try:
            # Run check (support both sync and async)
            if asyncio.iscoroutinefunction(check_fn):
                result = await check_fn()
            else:
                result = check_fn()

            latency = (time.time() - start) * 1000

            if isinstance(result, ComponentHealth):
                result.latency_ms = latency
                result.last_check = datetime.now(timezone.utc).isoformat()
                self._last_results[name] = result
                return result

            # If check returned True/False
            if isinstance(result, bool):
                status = HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY
                health = ComponentHealth(
                    name=name,
                    status=status,
                    latency_ms=latency,
                    last_check=datetime.now(timezone.utc).isoformat()
                )
                self._last_results[name] = health
                return health

            # If check returned dict
            if isinstance(result, dict):
                health = ComponentHealth(
                    name=name,
                    status=HealthStatus(result.get("status", "unknown")),
                    message=result.get("message", ""),
                    latency_ms=latency,
                    last_check=datetime.now(timezone.utc).isoformat(),
                    metadata=result.get("metadata", {})
                )
                self._last_results[name] = health
                return health

        except Exception as e:
            logger.error(f"Health check failed for {name}: {e}")
            health = ComponentHealth(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=str(e),
                latency_ms=(time.time() - start) * 1000,
                last_check=datetime.now(timezone.utc).isoformat()
            )
            self._last_results[name] = health
            return health

    async def check_all(self) -> SystemHealth:
        """Run all health checks and return system health."""
        components = []

        # Run all checks concurrently
        tasks = [self.check_component(name) for name in self._checks]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, ComponentHealth):
                components.append(result)
            elif isinstance(result, Exception):
                logger.error(f"Health check error: {result}")

        # Determine overall status
        statuses = [c.status for c in components]

        if all(s == HealthStatus.HEALTHY for s in statuses):
            overall = HealthStatus.HEALTHY
        elif any(s == HealthStatus.UNHEALTHY for s in statuses):
            overall = HealthStatus.UNHEALTHY
        elif any(s == HealthStatus.DEGRADED for s in statuses):
            overall = HealthStatus.DEGRADED
        else:
            overall = HealthStatus.UNKNOWN

        # System metrics
        system_metrics = self._get_system_metrics()

        return SystemHealth(
            status=overall,
            version=self.version,
            uptime_seconds=time.time() - self.start_time,
            timestamp=datetime.now(timezone.utc).isoformat(),
            components=components,
            system_metrics=system_metrics
        )

    def _get_system_metrics(self) -> Dict[str, Any]:
        """Get system resource metrics."""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            return {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_used_mb": memory.used / (1024 * 1024),
                "memory_available_mb": memory.available / (1024 * 1024),
                "disk_percent": disk.percent,
                "disk_free_gb": disk.free / (1024 * 1024 * 1024),
            }
        except Exception as e:
            logger.warning(f"Could not get system metrics: {e}")
            return {}

    # === DEFAULT CHECKS ===

    def _check_system(self) -> ComponentHealth:
        """Check system health."""
        try:
            cpu = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory().percent

            if cpu > 90 or memory > 90:
                status = HealthStatus.UNHEALTHY
                message = f"High resource usage: CPU {cpu}%, Memory {memory}%"
            elif cpu > 70 or memory > 80:
                status = HealthStatus.DEGRADED
                message = f"Elevated resource usage: CPU {cpu}%, Memory {memory}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"CPU {cpu}%, Memory {memory}%"

            return ComponentHealth(
                name="system",
                status=status,
                message=message,
                metadata={"cpu_percent": cpu, "memory_percent": memory}
            )
        except Exception as e:
            return ComponentHealth(
                name="system",
                status=HealthStatus.UNKNOWN,
                message=str(e)
            )

    def _check_memory(self) -> ComponentHealth:
        """Check memory usage."""
        try:
            memory = psutil.virtual_memory()
            used_gb = memory.used / (1024 ** 3)
            total_gb = memory.total / (1024 ** 3)

            if memory.percent > 90:
                status = HealthStatus.UNHEALTHY
            elif memory.percent > 80:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.HEALTHY

            return ComponentHealth(
                name="memory",
                status=status,
                message=f"{used_gb:.1f}GB / {total_gb:.1f}GB ({memory.percent}%)",
                metadata={
                    "used_gb": used_gb,
                    "total_gb": total_gb,
                    "percent": memory.percent
                }
            )
        except Exception as e:
            return ComponentHealth(name="memory", status=HealthStatus.UNKNOWN, message=str(e))

    def _check_disk(self) -> ComponentHealth:
        """Check disk usage."""
        try:
            disk = psutil.disk_usage('/')
            free_gb = disk.free / (1024 ** 3)
            total_gb = disk.total / (1024 ** 3)

            if disk.percent > 95:
                status = HealthStatus.UNHEALTHY
            elif disk.percent > 85:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.HEALTHY

            return ComponentHealth(
                name="disk",
                status=status,
                message=f"{free_gb:.1f}GB free / {total_gb:.1f}GB total ({disk.percent}% used)",
                metadata={
                    "free_gb": free_gb,
                    "total_gb": total_gb,
                    "percent": disk.percent
                }
            )
        except Exception as e:
            return ComponentHealth(name="disk", status=HealthStatus.UNKNOWN, message=str(e))


# === EXTERNAL SERVICE CHECKS ===

async def check_http_endpoint(url: str, timeout: float = 5.0) -> ComponentHealth:
    """Check if an HTTP endpoint is reachable."""
    import aiohttp

    name = url.split("//")[1].split("/")[0] if "//" in url else url

    try:
        async with aiohttp.ClientSession() as session:
            start = time.time()
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                latency = (time.time() - start) * 1000

                if resp.status == 200:
                    return ComponentHealth(
                        name=name,
                        status=HealthStatus.HEALTHY,
                        message=f"HTTP {resp.status}",
                        latency_ms=latency
                    )
                elif resp.status < 500:
                    return ComponentHealth(
                        name=name,
                        status=HealthStatus.DEGRADED,
                        message=f"HTTP {resp.status}",
                        latency_ms=latency
                    )
                else:
                    return ComponentHealth(
                        name=name,
                        status=HealthStatus.UNHEALTHY,
                        message=f"HTTP {resp.status}",
                        latency_ms=latency
                    )

    except asyncio.TimeoutError:
        return ComponentHealth(
            name=name,
            status=HealthStatus.UNHEALTHY,
            message=f"Timeout after {timeout}s"
        )
    except Exception as e:
        return ComponentHealth(
            name=name,
            status=HealthStatus.UNHEALTHY,
            message=str(e)
        )


async def check_database(db_path: str) -> ComponentHealth:
    """Check SQLite database health."""
    import sqlite3

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        conn.close()

        return ComponentHealth(
            name="database",
            status=HealthStatus.HEALTHY,
            message="Connected"
        )
    except Exception as e:
        return ComponentHealth(
            name="database",
            status=HealthStatus.UNHEALTHY,
            message=str(e)
        )


async def check_websocket(url: str, timeout: float = 5.0) -> ComponentHealth:
    """Check if WebSocket endpoint is reachable."""
    import websockets

    name = "websocket:" + url.split("//")[1].split("/")[0]

    try:
        async with websockets.connect(url, close_timeout=timeout) as ws:
            return ComponentHealth(
                name=name,
                status=HealthStatus.HEALTHY,
                message="Connected"
            )
    except asyncio.TimeoutError:
        return ComponentHealth(
            name=name,
            status=HealthStatus.UNHEALTHY,
            message=f"Timeout after {timeout}s"
        )
    except Exception as e:
        return ComponentHealth(
            name=name,
            status=HealthStatus.UNHEALTHY,
            message=str(e)
        )


# === SINGLETON ===

_health_checker: Optional[HealthChecker] = None

def get_health_checker() -> HealthChecker:
    """Get singleton health checker."""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker


# === API HANDLERS ===

async def health_endpoint():
    """FastAPI/aiohttp health endpoint handler."""
    checker = get_health_checker()
    health = await checker.check_all()

    return {
        "status": health.status.value,
        "version": health.version,
        "uptime_seconds": health.uptime_seconds,
        "timestamp": health.timestamp,
        "components": [
            {
                "name": c.name,
                "status": c.status.value,
                "message": c.message,
                "latency_ms": c.latency_ms
            }
            for c in health.components
        ],
        "system": health.system_metrics
    }


def setup_health_routes(app, prefix: str = ""):
    """Setup health check routes for FastAPI."""
    from fastapi import APIRouter

    router = APIRouter()

    @router.get(f"{prefix}/health")
    async def health():
        return await health_endpoint()

    @router.get(f"{prefix}/health/live")
    async def liveness():
        """Kubernetes liveness probe."""
        return {"status": "alive"}

    @router.get(f"{prefix}/health/ready")
    async def readiness():
        """Kubernetes readiness probe."""
        checker = get_health_checker()
        health = await checker.check_all()

        if health.status == HealthStatus.UNHEALTHY:
            from fastapi import HTTPException
            raise HTTPException(status_code=503, detail="Service unhealthy")

        return {"status": "ready"}

    app.include_router(router)
    logger.info("Health check routes configured")
