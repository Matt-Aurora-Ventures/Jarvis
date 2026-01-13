"""
JARVIS Health Dashboard API

FastAPI router providing comprehensive health monitoring endpoints:
- Quick health check (/health)
- Liveness probe (/health/live)
- Readiness probe (/health/ready)
- Full dashboard (/health/dashboard)
- Component details (/health/component/{name})
- History (/health/history)
- Uptime stats (/health/uptime)

Usage:
    from core.monitoring.dashboard import create_health_router

    app = FastAPI()
    app.include_router(create_health_router())
"""

import asyncio
import logging
import os
import platform
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

START_TIME = time.time()


def get_system_info() -> Dict[str, Any]:
    """Get static system information."""
    return {
        "hostname": platform.node(),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "architecture": platform.machine(),
        "process_id": os.getpid(),
        "start_time": datetime.fromtimestamp(START_TIME).isoformat(),
        "version": "4.3.0",
    }


def get_resource_usage() -> Dict[str, Any]:
    """Get current resource usage."""
    try:
        import psutil

        process = psutil.Process()
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        return {
            "cpu_percent": round(psutil.cpu_percent(interval=0.1), 1),
            "memory": {
                "percent": round(memory.percent, 1),
                "used_mb": round(memory.used / 1024 / 1024, 1),
                "total_mb": round(memory.total / 1024 / 1024, 1),
            },
            "disk": {
                "percent": round(disk.percent, 1),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 1),
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 1),
            },
            "process": {
                "memory_mb": round(process.memory_info().rss / 1024 / 1024, 1),
                "threads": process.num_threads(),
                "open_files": len(process.open_files()),
            },
        }
    except ImportError:
        return {"error": "psutil not available"}
    except Exception as e:
        return {"error": str(e)}


def format_uptime(seconds: float) -> str:
    """Format uptime as human readable string."""
    td = timedelta(seconds=int(seconds))
    days = td.days
    hours, remainder = divmod(td.seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs or not parts:
        parts.append(f"{secs}s")

    return " ".join(parts)


def create_health_router():
    """
    Create FastAPI router for health endpoints.

    Returns:
        APIRouter with health endpoints
    """
    try:
        from fastapi import APIRouter, HTTPException, Query
        from fastapi.responses import JSONResponse
    except ImportError:
        logger.error("FastAPI not available")
        return None

    router = APIRouter(prefix="/health", tags=["health"])

    @router.get("", summary="Health Check", description="Quick health status check")
    @router.get("/", include_in_schema=False)
    async def health_check():
        """
        Quick health check endpoint.

        Returns overall system health status with component summary.
        """
        try:
            from core.monitoring.health import get_health_monitor

            monitor = get_health_monitor()
            health = await monitor.check_health()

            uptime = time.time() - START_TIME

            response = {
                "status": health.status.value,
                "version": health.version,
                "uptime": format_uptime(uptime),
                "uptime_seconds": round(uptime, 1),
                "checked_at": health.checked_at.isoformat(),
                "summary": {
                    "healthy": health.healthy_count,
                    "degraded": health.degraded_count,
                    "unhealthy": health.unhealthy_count,
                    "total": len(health.components),
                },
            }

            status_code = 200 if health.status.value in ["healthy", "degraded"] else 503
            return JSONResponse(content=response, status_code=status_code)

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return JSONResponse(
                content={"status": "error", "message": str(e)},
                status_code=503,
            )

    @router.get("/live", summary="Liveness Probe", description="Kubernetes liveness probe")
    async def liveness():
        """
        Liveness probe for Kubernetes.

        Always returns 200 if the service is running.
        """
        return {
            "status": "alive",
            "uptime_seconds": round(time.time() - START_TIME, 1),
        }

    @router.get("/ready", summary="Readiness Probe", description="Kubernetes readiness probe")
    async def readiness():
        """
        Readiness probe for Kubernetes.

        Returns 200 if the system is ready to accept traffic.
        Returns 503 if any critical component is unhealthy.
        """
        try:
            from core.monitoring.health import get_health_monitor, HealthStatus

            monitor = get_health_monitor()
            health = await monitor.check_health()

            if health.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]:
                return {"status": "ready", "health": health.status.value}

            return JSONResponse(
                content={
                    "status": "not_ready",
                    "health": health.status.value,
                    "unhealthy_components": [
                        name for name, comp in health.components.items()
                        if comp.status == HealthStatus.UNHEALTHY
                    ],
                },
                status_code=503,
            )

        except Exception as e:
            return JSONResponse(
                content={"status": "not_ready", "error": str(e)},
                status_code=503,
            )

    @router.get("/dashboard", summary="Health Dashboard", description="Full system health dashboard")
    async def dashboard():
        """
        Full health dashboard with all component details.

        Includes:
        - Overall status
        - All component health
        - System resources
        - Uptime statistics
        """
        try:
            from core.monitoring.health import get_health_monitor

            monitor = get_health_monitor()
            health = await monitor.check_health()
            uptime_stats = await monitor.get_uptime_stats(days=7)

            uptime = time.time() - START_TIME

            return {
                "status": health.status.value,
                "version": health.version,
                "uptime": format_uptime(uptime),
                "uptime_seconds": round(uptime, 1),
                "checked_at": health.checked_at.isoformat(),
                "components": {
                    name: {
                        "status": comp.status.value,
                        "message": comp.message,
                        "latency_ms": round(comp.latency_ms, 2),
                        "last_check": comp.last_check.isoformat(),
                        "metadata": comp.metadata,
                    }
                    for name, comp in health.components.items()
                },
                "summary": {
                    "healthy": health.healthy_count,
                    "degraded": health.degraded_count,
                    "unhealthy": health.unhealthy_count,
                    "total": len(health.components),
                },
                "uptime_stats": uptime_stats,
                "resources": get_resource_usage(),
                "system": get_system_info(),
            }

        except Exception as e:
            logger.error(f"Dashboard failed: {e}")
            return JSONResponse(
                content={"status": "error", "message": str(e)},
                status_code=500,
            )

    @router.get("/component/{name}", summary="Component Health", description="Check specific component health")
    async def component_health(name: str):
        """
        Check health of a specific component.

        Args:
            name: Component name (e.g., database, solana_rpc, treasury)
        """
        try:
            from core.monitoring.health import get_health_monitor

            monitor = get_health_monitor()
            result = await monitor.check_component(name)

            if result is None:
                raise HTTPException(status_code=404, detail=f"Component '{name}' not found")

            return {
                "name": result.name,
                "status": result.status.value,
                "message": result.message,
                "latency_ms": round(result.latency_ms, 2),
                "last_check": result.last_check.isoformat(),
                "metadata": result.metadata,
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/history", summary="Health History", description="Get health check history")
    async def health_history(
        component: Optional[str] = Query(None, description="Filter by component name"),
        hours: int = Query(24, ge=1, le=168, description="Hours of history (1-168)"),
        limit: int = Query(100, ge=1, le=1000, description="Max records to return"),
    ):
        """
        Get health check history.

        Args:
            component: Optional component name filter
            hours: Hours of history to retrieve (default 24)
            limit: Maximum records to return (default 100)
        """
        try:
            from core.monitoring.health import get_health_monitor

            monitor = get_health_monitor()
            history = await monitor.get_health_history(component=component, hours=hours)

            return {
                "component": component,
                "hours": hours,
                "count": len(history[:limit]),
                "total": len(history),
                "history": history[:limit],
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/uptime", summary="Uptime Statistics", description="Get uptime statistics")
    async def uptime_stats(
        days: int = Query(7, ge=1, le=90, description="Days of uptime to calculate"),
    ):
        """
        Get uptime statistics.

        Args:
            days: Days of history to calculate (default 7)
        """
        try:
            from core.monitoring.health import get_health_monitor

            monitor = get_health_monitor()
            stats = await monitor.get_uptime_stats(days=days)

            uptime = time.time() - START_TIME

            return {
                "current_uptime": format_uptime(uptime),
                "current_uptime_seconds": round(uptime, 1),
                "period_days": days,
                **stats,
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/components", summary="List Components", description="List all monitored components")
    async def list_components():
        """
        List all registered health check components.
        """
        try:
            from core.monitoring.health import get_health_monitor

            monitor = get_health_monitor()

            return {
                "components": [
                    {
                        "name": name,
                        "critical": check.critical,
                        "timeout_seconds": check.timeout_seconds,
                        "interval_seconds": check.interval_seconds,
                    }
                    for name, check in monitor._checks.items()
                ],
                "total": len(monitor._checks),
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/emergency", summary="Emergency Status", description="Check emergency shutdown status")
    async def emergency_status():
        """
        Check if emergency shutdown is active.
        """
        try:
            from core.security.emergency_shutdown import get_emergency_shutdown

            shutdown = get_emergency_shutdown()
            state = shutdown.get_state()

            return {
                "is_shutdown": state.is_shutdown,
                "blocked_operations": state.blocked_operations,
                "event": {
                    "timestamp": state.event.timestamp if state.event else None,
                    "reason": state.event.reason if state.event else None,
                    "category": state.event.category.value if state.event else None,
                    "triggered_by": state.event.triggered_by if state.event else None,
                } if state.event else None,
            }

        except Exception as e:
            return {
                "is_shutdown": False,
                "error": str(e),
            }

    return router


# Convenience function to get router
def get_health_router():
    """Get or create the health router."""
    return create_health_router()


if __name__ == "__main__":
    print("Health Dashboard Module")
    print("=" * 40)
    print(f"System Info: {get_system_info()}")
    print(f"Resources: {get_resource_usage()}")
    print(f"Uptime: {format_uptime(123456)}")
