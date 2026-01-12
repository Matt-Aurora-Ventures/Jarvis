"""
FastAPI Application for Jarvis.

Main application entry point for all FastAPI-based APIs:
- Staking endpoints
- Credits/billing endpoints
- Treasury/Bags integration endpoints
- Data consent endpoints
- WebSocket real-time updates
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.errors import make_error_response

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("jarvis.api")


# =============================================================================
# WebSocket Connection Manager
# =============================================================================


class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""

    def __init__(self):
        self.active_connections: Dict[str, list[WebSocket]] = {
            "staking": [],
            "credits": [],
            "treasury": [],
        }

    async def connect(self, websocket: WebSocket, channel: str):
        """Accept and register a WebSocket connection."""
        await websocket.accept()
        if channel not in self.active_connections:
            self.active_connections[channel] = []
        self.active_connections[channel].append(websocket)
        logger.info(f"WebSocket connected to channel: {channel}")

    def disconnect(self, websocket: WebSocket, channel: str):
        """Remove a WebSocket connection."""
        if channel in self.active_connections:
            self.active_connections[channel].remove(websocket)
        logger.info(f"WebSocket disconnected from channel: {channel}")

    async def broadcast(self, channel: str, message: Dict[str, Any]):
        """Broadcast a message to all connections in a channel."""
        if channel not in self.active_connections:
            return

        disconnected = []
        for connection in self.active_connections[channel]:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        # Clean up disconnected clients
        for conn in disconnected:
            self.active_connections[channel].remove(conn)


manager = ConnectionManager()


# =============================================================================
# Application Lifecycle
# =============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management."""
    logger.info("Starting Jarvis FastAPI application...")

    # Startup: Initialize services
    try:
        # Initialize treasury-bags integration if enabled
        if os.getenv("ENABLE_BAGS_INTEGRATION", "false").lower() == "true":
            from core.treasury.bags_integration import get_bags_integration
            integration = get_bags_integration()
            integration.start()
            logger.info("Started Bags.fm fee collection")
    except ImportError as e:
        logger.warning(f"Treasury-Bags integration not available: {e}")
    except Exception as e:
        logger.error(f"Error starting Bags integration: {e}")

    yield

    # Shutdown: Cleanup
    logger.info("Shutting down Jarvis FastAPI application...")

    try:
        from core.treasury.bags_integration import get_bags_integration
        integration = get_bags_integration()
        integration.stop()
    except Exception:
        pass


# =============================================================================
# Application Factory
# =============================================================================


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(
        title="Jarvis API",
        description="JARVIS Trading & Automation Platform API",
        version="3.7.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # CORS configuration
    origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global exception handlers for standardized error responses
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        error_map = {
            400: "VAL_001",
            401: "AUTH_001",
            403: "AUTH_004",
            404: "SYS_002",
            429: "PROV_002",
            500: "SYS_003",
            503: "SYS_002",
        }
        error_code = error_map.get(exc.status_code, "SYS_003")
        return JSONResponse(
            status_code=exc.status_code,
            content=make_error_response(error_code, str(exc.detail))
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception: {exc}")
        return JSONResponse(
            status_code=500,
            content=make_error_response("SYS_003", "Internal server error")
        )

    # Include routers
    _include_routers(app)

    # WebSocket endpoints
    _setup_websockets(app)

    # Health check
    @app.get("/api/health")
    async def health_check():
        import platform
        import psutil
        import time

        # Get system metrics
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            # Use appropriate path for disk check
            disk_path = "C:\\" if platform.system() == "Windows" else "/"
            disk = psutil.disk_usage(disk_path)
        except Exception:
            cpu_percent = 0
            memory = None
            disk = None

        # Check provider availability
        providers_status = {}
        providers_healthy = True
        try:
            from core import providers
            provider_check = providers.check_providers()
            for name, status in provider_check.items():
                is_available = status.get("available", False)
                providers_status[name] = is_available
                if not is_available:
                    providers_healthy = False
        except Exception:
            providers_healthy = False

        # Check voice system
        voice_status = {"available": False, "tts": False, "stt": False, "microphone": False}
        try:
            from core.voice import run_voice_diagnostics
            diag = run_voice_diagnostics()
            voice_status = {
                "available": diag.microphone_available and diag.tts_available,
                "tts": diag.tts_available,
                "stt": diag.stt_available,
                "microphone": diag.microphone_available,
                "wake_word": diag.wake_word_available,
            }
        except Exception:
            pass

        # Check database
        database_ok = True
        try:
            from core import state
            state.read_state()
        except Exception:
            database_ok = False

        # Determine overall status
        all_healthy = providers_healthy and database_ok
        overall_status = "healthy" if all_healthy else "degraded"
        if not database_ok:
            overall_status = "unhealthy"

        return {
            "status": overall_status,
            "version": "4.1.1",
            "timestamp": time.time(),
            "platform": platform.system(),
            "services": {
                "staking": True,
                "credits": True,
                "treasury": True,
                "voice": voice_status["available"],
                "sentiment": True,
                "database": database_ok,
            },
            "voice": voice_status,
            "providers": providers_status,
            "system": {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent if memory else 0,
                "memory_available_gb": round(memory.available / (1024**3), 2) if memory else 0,
                "disk_percent": disk.percent if disk else 0,
                "disk_free_gb": round(disk.free / (1024**3), 2) if disk else 0,
            },
        }

    @app.get("/api/health/components")
    async def health_components():
        """Detailed component health check."""
        from core import state

        daemon_state = state.read_state()
        component_status = daemon_state.get("component_status", {})

        components = []
        for name, status in component_status.items():
            components.append({
                "name": name,
                "healthy": status.get("ok", False),
                "error": status.get("error"),
            })

        return {
            "components": components,
            "startup_ok": daemon_state.get("startup_ok", 0),
            "startup_failed": daemon_state.get("startup_failed", 0),
        }

    return app


def _include_routers(app: FastAPI):
    """Include all API routers."""

    # Staking routes
    try:
        from api.routes.staking import router as staking_router
        app.include_router(staking_router)
        logger.info("Included staking routes")
    except ImportError as e:
        logger.warning(f"Staking routes not available: {e}")

    # Credits routes
    try:
        from api.routes.credits import router as credits_router
        app.include_router(credits_router)
        logger.info("Included credits routes")
    except ImportError as e:
        logger.warning(f"Credits routes not available: {e}")

    # Treasury-Bags integration routes
    try:
        from core.treasury.bags_integration import create_bags_integration_router
        bags_router = create_bags_integration_router()
        if bags_router:
            app.include_router(bags_router)
            logger.info("Included treasury-bags routes")
    except ImportError as e:
        logger.warning(f"Treasury-Bags routes not available: {e}")

    # Transparency dashboard routes
    try:
        from core.treasury.transparency import create_transparency_router
        transparency_router = create_transparency_router()
        if transparency_router:
            app.include_router(transparency_router)
            logger.info("Included transparency routes")
    except ImportError as e:
        logger.warning(f"Transparency routes not available: {e}")

    # Treasury dashboard routes
    try:
        from core.treasury.dashboard import create_dashboard_router
        dashboard_router = create_dashboard_router()
        if dashboard_router:
            app.include_router(dashboard_router)
            logger.info("Included treasury dashboard routes")
    except ImportError as e:
        logger.warning(f"Treasury dashboard routes not available: {e}")

    # Treasury reports routes
    try:
        from api.routes.treasury_reports import router as reports_router
        app.include_router(reports_router)
        logger.info("Included treasury reports routes")
    except ImportError as e:
        logger.warning(f"Treasury reports routes not available: {e}")

    # Data consent routes
    try:
        from core.data_consent.routes import router as consent_router
        app.include_router(consent_router)
        logger.info("Included data consent routes")
    except ImportError as e:
        logger.warning(f"Data consent routes not available: {e}")


def _setup_websockets(app: FastAPI):
    """Set up WebSocket endpoints."""

    @app.websocket("/ws/staking")
    async def websocket_staking(websocket: WebSocket):
        """WebSocket for real-time staking updates."""
        await manager.connect(websocket, "staking")
        try:
            while True:
                # Keep connection alive, broadcast updates via manager.broadcast()
                data = await websocket.receive_text()
                # Handle client messages if needed
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
        except WebSocketDisconnect:
            manager.disconnect(websocket, "staking")

    @app.websocket("/ws/credits")
    async def websocket_credits(websocket: WebSocket):
        """WebSocket for real-time credit balance updates."""
        await manager.connect(websocket, "credits")
        try:
            while True:
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
        except WebSocketDisconnect:
            manager.disconnect(websocket, "credits")

    @app.websocket("/ws/treasury")
    async def websocket_treasury(websocket: WebSocket):
        """WebSocket for real-time treasury updates."""
        await manager.connect(websocket, "treasury")
        try:
            while True:
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
        except WebSocketDisconnect:
            manager.disconnect(websocket, "treasury")


# =============================================================================
# Broadcast Helpers (for use by services)
# =============================================================================


async def broadcast_staking_update(data: Dict[str, Any]):
    """Broadcast a staking update to all connected clients."""
    await manager.broadcast("staking", {"type": "staking_update", "data": data})


async def broadcast_credits_update(user_id: str, data: Dict[str, Any]):
    """Broadcast a credits update."""
    await manager.broadcast("credits", {"type": "credits_update", "user_id": user_id, "data": data})


async def broadcast_treasury_update(data: Dict[str, Any]):
    """Broadcast a treasury update."""
    await manager.broadcast("treasury", {"type": "treasury_update", "data": data})


# =============================================================================
# Application Instance
# =============================================================================

app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.fastapi_app:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", "8766")),
        reload=os.getenv("API_RELOAD", "true").lower() == "true",
    )
