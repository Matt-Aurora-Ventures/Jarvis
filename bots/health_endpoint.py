#!/usr/bin/env python3
"""
JARVIS Health Endpoint - Simple HTTP server for health checks.

Provides a /health endpoint for monitoring tools like uptime monitors,
Kubernetes probes, or external dashboards.

Run alongside the supervisor for complete observability.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from aiohttp import web

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logger = logging.getLogger("jarvis.health")

# Global state - updated by supervisor
_health_state = {
    "status": "unknown",
    "started_at": None,
    "components": {},
    "last_update": None,
}


def update_health(components: dict):
    """Update health state from supervisor."""
    global _health_state
    _health_state["components"] = components
    _health_state["last_update"] = datetime.utcnow().isoformat()

    # Determine overall status
    statuses = [c.get("status", "unknown") for c in components.values()]
    if all(s == "running" for s in statuses):
        _health_state["status"] = "healthy"
    elif any(s == "running" for s in statuses):
        _health_state["status"] = "degraded"
    else:
        _health_state["status"] = "unhealthy"


async def health_handler(request):
    """Handle /health endpoint."""
    status_code = 200 if _health_state["status"] in ("healthy", "degraded") else 503

    response = {
        "status": _health_state["status"],
        "timestamp": datetime.utcnow().isoformat(),
        "uptime": None,
        "components": _health_state["components"],
    }

    if _health_state["started_at"]:
        started = datetime.fromisoformat(_health_state["started_at"])
        uptime = datetime.utcnow() - started
        response["uptime"] = str(uptime)

    return web.json_response(response, status=status_code)


async def ready_handler(request):
    """Handle /ready endpoint (Kubernetes readiness probe)."""
    if _health_state["status"] in ("healthy", "degraded"):
        return web.Response(text="OK", status=200)
    return web.Response(text="NOT READY", status=503)


async def live_handler(request):
    """Handle /live endpoint (Kubernetes liveness probe)."""
    # Always return OK if the server is running
    return web.Response(text="OK", status=200)


async def metrics_handler(request):
    """Handle /metrics endpoint (Prometheus format)."""
    lines = [
        "# HELP jarvis_up Whether JARVIS is up",
        "# TYPE jarvis_up gauge",
        f"jarvis_up {1 if _health_state['status'] in ('healthy', 'degraded') else 0}",
        "",
        "# HELP jarvis_component_status Component status (1=running, 0=stopped)",
        "# TYPE jarvis_component_status gauge",
    ]

    for name, info in _health_state.get("components", {}).items():
        status = 1 if info.get("status") == "running" else 0
        restarts = info.get("restart_count", 0)
        lines.append(f'jarvis_component_status{{component="{name}"}} {status}')
        lines.append(f'jarvis_component_restarts{{component="{name}"}} {restarts}')

    return web.Response(text="\n".join(lines), content_type="text/plain")


async def start_health_server(port: int = 8080):
    """Start the health check HTTP server."""
    global _health_state
    _health_state["started_at"] = datetime.utcnow().isoformat()
    _health_state["status"] = "starting"

    app = web.Application()
    app.router.add_get("/health", health_handler)
    app.router.add_get("/ready", ready_handler)
    app.router.add_get("/live", live_handler)
    app.router.add_get("/metrics", metrics_handler)
    app.router.add_get("/", health_handler)  # Root also returns health

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    logger.info(f"Health server started on http://0.0.0.0:{port}")
    _health_state["status"] = "healthy"

    return runner


async def main():
    """Run standalone health server for testing."""
    logging.basicConfig(level=logging.INFO)

    port = int(os.environ.get("HEALTH_PORT", "8080"))
    runner = await start_health_server(port)

    # Simulate some component data
    update_health({
        "buy_bot": {"status": "running", "restart_count": 0},
        "sentiment": {"status": "running", "restart_count": 0},
        "telegram": {"status": "running", "restart_count": 0},
    })

    print(f"Health server running on http://localhost:{port}")
    print("Endpoints: /health, /ready, /live, /metrics")
    print("Press Ctrl+C to stop")

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
