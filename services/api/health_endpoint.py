"""
Jarvis Health Check API
========================
Simple HTTP endpoint for container health checks and monitoring.

Port: 8080
Endpoints:
  GET /health       - Basic health check (returns 200 if alive)
  GET /health/full  - Detailed status with component health
  GET /metrics      - Prometheus-compatible metrics (optional)

Usage:
    from api.health_endpoint import start_health_server
    await start_health_server(supervisor_state)
"""

import asyncio
import json
import logging
import os
import psutil
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from aiohttp import web

logger = logging.getLogger(__name__)

# Global state reference (set by supervisor)
_supervisor_state: Optional[Dict[str, Any]] = None
_start_time: float = time.time()


def set_supervisor_state(state: Dict[str, Any]) -> None:
    """Set reference to supervisor state for health reporting."""
    global _supervisor_state
    _supervisor_state = state


async def health_check(request: web.Request) -> web.Response:
    """
    Basic health check - returns 200 if service is alive.

    Used by Docker HEALTHCHECK.
    """
    return web.json_response({
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": int(time.time() - _start_time),
    })


async def health_full(request: web.Request) -> web.Response:
    """
    Detailed health check with component status.
    """
    # System metrics
    memory = psutil.virtual_memory()
    cpu_percent = psutil.cpu_percent(interval=0.1)

    # Component status (from supervisor state)
    components = {}
    if _supervisor_state and "components" in _supervisor_state:
        components = _supervisor_state["components"]

    # Determine overall health
    healthy_count = sum(1 for c in components.values() if c.get("status") == "running")
    total_count = len(components) if components else 0

    overall_status = "healthy"
    if total_count > 0 and healthy_count < total_count:
        overall_status = "degraded"
    if healthy_count == 0 and total_count > 0:
        overall_status = "unhealthy"

    response = {
        "status": overall_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": int(time.time() - _start_time),
        "system": {
            "memory_percent": memory.percent,
            "memory_available_mb": memory.available // (1024 * 1024),
            "cpu_percent": cpu_percent,
            "pid": os.getpid(),
        },
        "components": {
            "healthy": healthy_count,
            "total": total_count,
            "details": components,
        },
        "version": os.environ.get("JARVIS_VERSION", "4.6.6"),
    }

    status_code = 200 if overall_status in ("healthy", "degraded") else 503
    return web.json_response(response, status=status_code)


async def metrics(request: web.Request) -> web.Response:
    """
    Prometheus-compatible metrics endpoint.
    """
    memory = psutil.virtual_memory()

    lines = [
        "# HELP jarvis_uptime_seconds Time since service started",
        "# TYPE jarvis_uptime_seconds gauge",
        f"jarvis_uptime_seconds {int(time.time() - _start_time)}",
        "",
        "# HELP jarvis_memory_percent Memory usage percentage",
        "# TYPE jarvis_memory_percent gauge",
        f"jarvis_memory_percent {memory.percent}",
        "",
        "# HELP jarvis_cpu_percent CPU usage percentage",
        "# TYPE jarvis_cpu_percent gauge",
        f"jarvis_cpu_percent {psutil.cpu_percent(interval=0.1)}",
    ]

    # Component metrics
    if _supervisor_state and "components" in _supervisor_state:
        lines.extend([
            "",
            "# HELP jarvis_component_status Component status (1=running, 0=stopped)",
            "# TYPE jarvis_component_status gauge",
        ])
        for name, info in _supervisor_state["components"].items():
            status = 1 if info.get("status") == "running" else 0
            lines.append(f'jarvis_component_status{{component="{name}"}} {status}')

    return web.Response(
        text="\n".join(lines),
        content_type="text/plain",
    )


async def start_health_server(
    supervisor_state: Optional[Dict[str, Any]] = None,
    host: str = "0.0.0.0",
    port: int = 8080,
) -> web.AppRunner:
    """
    Start the health check HTTP server.

    Args:
        supervisor_state: Reference to supervisor state dict for component health
        host: Bind address (default: 0.0.0.0)
        port: Port number (default: 8080)

    Returns:
        AppRunner instance (for cleanup)
    """
    if supervisor_state:
        set_supervisor_state(supervisor_state)

    app = web.Application()
    app.router.add_get("/health", health_check)
    app.router.add_get("/health/full", health_full)
    app.router.add_get("/metrics", metrics)

    # Root redirect to health
    app.router.add_get("/", lambda r: web.HTTPFound("/health"))

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, host, port)
    await site.start()

    logger.info(f"Health server started on http://{host}:{port}")
    return runner


async def stop_health_server(runner: web.AppRunner) -> None:
    """Stop the health check server."""
    await runner.cleanup()
    logger.info("Health server stopped")


# Standalone mode for testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    async def main():
        runner = await start_health_server()
        print("Health server running on http://localhost:8080")
        print("Press Ctrl+C to stop")
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await stop_health_server(runner)

    asyncio.run(main())
