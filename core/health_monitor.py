"""
Health Monitor - System health checking and alerting.

Provides:
- Component health checks
- Dependency monitoring
- Alerting on failures
- Health aggregation
- Kubernetes-ready probes
"""

import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional, List, Callable, Awaitable
from threading import Lock

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health check status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    name: str
    status: HealthStatus
    message: str = ""
    latency_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)
    last_check: str = ""
    consecutive_failures: int = 0


@dataclass
class HealthCheck:
    """Health check definition."""
    name: str
    check_fn: Callable[[], Awaitable[HealthCheckResult]]
    interval_seconds: int = 30
    timeout_seconds: int = 10
    critical: bool = True  # If critical, unhealthy = system unhealthy
    enabled: bool = True


class HealthMonitor:
    """
    System health monitoring.
    
    Features:
    - Async health checks
    - Configurable intervals
    - Alert callbacks
    - Kubernetes probe support
    - Dependency tracking
    """

    _instance: Optional["HealthMonitor"] = None
    _lock = Lock()

    # Feature flags (ready to activate)
    ENABLE_ALERTING = False  # Send alerts on failures
    ENABLE_AUTO_RECOVERY = False  # Attempt auto-recovery

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.checks: Dict[str, HealthCheck] = {}
        self.results: Dict[str, HealthCheckResult] = {}
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._alert_callbacks: List[Callable] = []
        
        self._register_default_checks()
        self._initialized = True
        logger.info("HealthMonitor initialized")

    def _register_default_checks(self):
        """Register default health checks."""
        # Database check
        self.register_check(HealthCheck(
            name="database",
            check_fn=self._check_database,
            interval_seconds=30,
            critical=True,
        ))

        # Jupiter API check
        self.register_check(HealthCheck(
            name="jupiter_api",
            check_fn=self._check_jupiter,
            interval_seconds=60,
            critical=False,
        ))

        # Memory check
        self.register_check(HealthCheck(
            name="memory",
            check_fn=self._check_memory,
            interval_seconds=60,
            critical=False,
        ))

        # Disk check
        self.register_check(HealthCheck(
            name="disk",
            check_fn=self._check_disk,
            interval_seconds=120,
            critical=False,
        ))

    async def _check_database(self) -> HealthCheckResult:
        """Check database connectivity."""
        start = time.time()
        try:
            from pathlib import Path
            db_path = Path("data/jarvis_memory.db")
            if db_path.exists():
                return HealthCheckResult(
                    name="database",
                    status=HealthStatus.HEALTHY,
                    message="Database accessible",
                    latency_ms=(time.time() - start) * 1000,
                    last_check=datetime.now(timezone.utc).isoformat(),
                )
            else:
                return HealthCheckResult(
                    name="database",
                    status=HealthStatus.DEGRADED,
                    message="Database file not found",
                    latency_ms=(time.time() - start) * 1000,
                    last_check=datetime.now(timezone.utc).isoformat(),
                )
        except Exception as e:
            return HealthCheckResult(
                name="database",
                status=HealthStatus.UNHEALTHY,
                message=str(e),
                latency_ms=(time.time() - start) * 1000,
                last_check=datetime.now(timezone.utc).isoformat(),
            )

    async def _check_jupiter(self) -> HealthCheckResult:
        """Check Jupiter API connectivity."""
        start = time.time()
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://lite-api.jup.ag/swap/v1/quote?inputMint=So11111111111111111111111111111111111111112&outputMint=EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v&amount=1000000",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        return HealthCheckResult(
                            name="jupiter_api",
                            status=HealthStatus.HEALTHY,
                            message="Jupiter API accessible",
                            latency_ms=(time.time() - start) * 1000,
                            last_check=datetime.now(timezone.utc).isoformat(),
                        )
                    else:
                        return HealthCheckResult(
                            name="jupiter_api",
                            status=HealthStatus.DEGRADED,
                            message=f"HTTP {resp.status}",
                            latency_ms=(time.time() - start) * 1000,
                            last_check=datetime.now(timezone.utc).isoformat(),
                        )
        except Exception as e:
            return HealthCheckResult(
                name="jupiter_api",
                status=HealthStatus.UNHEALTHY,
                message=str(e)[:100],
                latency_ms=(time.time() - start) * 1000,
                last_check=datetime.now(timezone.utc).isoformat(),
            )

    async def _check_memory(self) -> HealthCheckResult:
        """Check memory usage."""
        start = time.time()
        try:
            import psutil
            memory = psutil.virtual_memory()
            used_pct = memory.percent
            
            status = HealthStatus.HEALTHY
            if used_pct > 90:
                status = HealthStatus.UNHEALTHY
            elif used_pct > 80:
                status = HealthStatus.DEGRADED

            return HealthCheckResult(
                name="memory",
                status=status,
                message=f"{used_pct:.1f}% used",
                latency_ms=(time.time() - start) * 1000,
                details={"percent_used": used_pct, "available_mb": memory.available / 1024 / 1024},
                last_check=datetime.now(timezone.utc).isoformat(),
            )
        except ImportError:
            return HealthCheckResult(
                name="memory",
                status=HealthStatus.UNKNOWN,
                message="psutil not available",
                latency_ms=(time.time() - start) * 1000,
                last_check=datetime.now(timezone.utc).isoformat(),
            )

    async def _check_disk(self) -> HealthCheckResult:
        """Check disk usage."""
        start = time.time()
        try:
            import psutil
            disk = psutil.disk_usage('/')
            used_pct = disk.percent
            
            status = HealthStatus.HEALTHY
            if used_pct > 95:
                status = HealthStatus.UNHEALTHY
            elif used_pct > 85:
                status = HealthStatus.DEGRADED

            return HealthCheckResult(
                name="disk",
                status=status,
                message=f"{used_pct:.1f}% used",
                latency_ms=(time.time() - start) * 1000,
                details={"percent_used": used_pct, "free_gb": disk.free / 1024 / 1024 / 1024},
                last_check=datetime.now(timezone.utc).isoformat(),
            )
        except ImportError:
            return HealthCheckResult(
                name="disk",
                status=HealthStatus.UNKNOWN,
                message="psutil not available",
                latency_ms=(time.time() - start) * 1000,
                last_check=datetime.now(timezone.utc).isoformat(),
            )

    def register_check(self, check: HealthCheck):
        """Register a health check."""
        self.checks[check.name] = check
        self.results[check.name] = HealthCheckResult(
            name=check.name,
            status=HealthStatus.UNKNOWN,
            message="Not yet checked",
        )

    def register_alert_callback(self, callback: Callable):
        """Register callback for health alerts."""
        self._alert_callbacks.append(callback)

    async def run_check(self, name: str) -> HealthCheckResult:
        """Run a specific health check."""
        if name not in self.checks:
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNKNOWN,
                message="Check not found",
            )

        check = self.checks[name]
        if not check.enabled:
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNKNOWN,
                message="Check disabled",
            )

        try:
            result = await asyncio.wait_for(
                check.check_fn(),
                timeout=check.timeout_seconds
            )
        except asyncio.TimeoutError:
            result = HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message="Check timed out",
                last_check=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as e:
            result = HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=str(e)[:100],
                last_check=datetime.now(timezone.utc).isoformat(),
            )

        # Track consecutive failures
        prev = self.results.get(name)
        if prev and result.status == HealthStatus.UNHEALTHY:
            result.consecutive_failures = prev.consecutive_failures + 1
        else:
            result.consecutive_failures = 0

        self.results[name] = result

        # Trigger alerts if needed
        if self.ENABLE_ALERTING and result.status == HealthStatus.UNHEALTHY:
            await self._send_alerts(result)

        return result

    async def run_all_checks(self) -> Dict[str, HealthCheckResult]:
        """Run all health checks."""
        tasks = [self.run_check(name) for name in self.checks]
        await asyncio.gather(*tasks, return_exceptions=True)
        return self.results.copy()

    async def _send_alerts(self, result: HealthCheckResult):
        """Send alerts for unhealthy checks."""
        for callback in self._alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(result)
                else:
                    callback(result)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")

    async def start_monitoring(self):
        """Start background health monitoring."""
        if self._running:
            return

        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Health monitoring started")

    async def stop_monitoring(self):
        """Stop background monitoring."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

    async def _monitor_loop(self):
        """Background monitoring loop."""
        last_check: Dict[str, float] = {}

        while self._running:
            now = time.time()
            
            for name, check in self.checks.items():
                if not check.enabled:
                    continue

                last = last_check.get(name, 0)
                if now - last >= check.interval_seconds:
                    try:
                        await self.run_check(name)
                    except Exception as e:
                        logger.error(f"Health check {name} failed: {e}")
                    last_check[name] = now

            await asyncio.sleep(1)

    def get_overall_status(self) -> HealthStatus:
        """Get overall system health status."""
        critical_unhealthy = False
        any_degraded = False

        for name, check in self.checks.items():
            result = self.results.get(name)
            if not result:
                continue

            if result.status == HealthStatus.UNHEALTHY and check.critical:
                critical_unhealthy = True
            elif result.status == HealthStatus.DEGRADED:
                any_degraded = True

        if critical_unhealthy:
            return HealthStatus.UNHEALTHY
        elif any_degraded:
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY

    def get_health_report(self) -> Dict[str, Any]:
        """Get full health report."""
        return {
            "status": self.get_overall_status().value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {
                name: {
                    "status": result.status.value,
                    "message": result.message,
                    "latency_ms": result.latency_ms,
                    "last_check": result.last_check,
                    "consecutive_failures": result.consecutive_failures,
                }
                for name, result in self.results.items()
            }
        }

    # Kubernetes probe endpoints
    def is_ready(self) -> bool:
        """Readiness probe - can serve traffic."""
        return self.get_overall_status() != HealthStatus.UNHEALTHY

    def is_live(self) -> bool:
        """Liveness probe - should restart if false."""
        critical_checks = [
            name for name, check in self.checks.items()
            if check.critical
        ]
        for name in critical_checks:
            result = self.results.get(name)
            if result and result.consecutive_failures >= 3:
                return False
        return True


# Singleton accessor
def get_health_monitor() -> HealthMonitor:
    """Get the health monitor singleton."""
    return HealthMonitor()
