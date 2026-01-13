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
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.errors import make_error_response

# Performance: Use orjson for faster JSON responses
try:
    from fastapi.responses import ORJSONResponse
    DEFAULT_RESPONSE_CLASS = ORJSONResponse
except ImportError:
    DEFAULT_RESPONSE_CLASS = JSONResponse

# Import new middleware
try:
    from api.middleware.rate_limit import RateLimitMiddleware
    from api.middleware.security_headers import SecurityHeadersMiddleware
    from api.middleware.request_tracing import RequestTracingMiddleware
    from api.middleware.body_limit import BodySizeLimitMiddleware
    HAS_MIDDLEWARE = True
except ImportError:
    HAS_MIDDLEWARE = False

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
            "voice": [],
            "trading": [],
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
        version="4.2.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        default_response_class=DEFAULT_RESPONSE_CLASS,  # Use orjson for 3-10x faster JSON
    )
    
    # OpenTelemetry instrumentation
    try:
        from core.observability import setup_telemetry, instrument_fastapi
        setup_telemetry(service_name="jarvis-api", service_version="4.2.0")
        from core.observability.otel_setup import instrument_fastapi
        instrument_fastapi(app)
    except ImportError:
        pass

    # CORS configuration
    origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add security and performance middleware
    if HAS_MIDDLEWARE:
        # Request tracing (adds X-Request-ID)
        app.add_middleware(RequestTracingMiddleware)
        
        # Security headers (X-Frame-Options, CSP, etc.)
        app.add_middleware(SecurityHeadersMiddleware)
        
        # Rate limiting
        if os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true":
            app.add_middleware(RateLimitMiddleware, enabled=True)
        
        # Request body size limit (10MB default)
        app.add_middleware(BodySizeLimitMiddleware, max_size=10 * 1024 * 1024)
        
        logger.info("Security middleware enabled")

    # GZip compression for responses
    app.add_middleware(GZipMiddleware, minimum_size=1000)

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

    @app.get("/api/metrics")
    async def prometheus_metrics():
        """Prometheus metrics endpoint."""
        from fastapi.responses import PlainTextResponse
        try:
            from core.monitoring.metrics import metrics
            return PlainTextResponse(
                content=metrics.collect_all(),
                media_type="text/plain"
            )
        except ImportError:
            return PlainTextResponse(content="# Metrics not available", media_type="text/plain")

    @app.get("/api/traces")
    async def recent_traces():
        """Get recent distributed traces."""
        try:
            from core.monitoring.tracing import tracer
            return {"traces": tracer.get_recent_traces(limit=50)}
        except ImportError:
            return {"traces": [], "error": "Tracing not available"}

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

    @app.websocket("/ws/voice")
    async def websocket_voice(websocket: WebSocket):
        """WebSocket for real-time voice status updates."""
        await manager.connect(websocket, "voice")
        try:
            # Send initial voice status
            try:
                from core.voice import run_voice_diagnostics
                from core import config
                cfg = config.load_config()
                voice_cfg = cfg.get("voice", {})
                diag = run_voice_diagnostics()
                await websocket.send_json({
                    "type": "voice_status",
                    "data": {
                        "enabled": voice_cfg.get("speak_responses", True),
                        "listening": False,
                        "speaking": False,
                        "processing": False,
                        "tts_available": diag.tts_available,
                        "stt_available": diag.stt_available,
                        "microphone_available": diag.microphone_available,
                        "wake_word_enabled": diag.wake_word_available,
                    }
                })
            except Exception as e:
                await websocket.send_json({
                    "type": "voice_status",
                    "data": {"enabled": False, "error": str(e)}
                })

            while True:
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
                elif data == "status":
                    # Resend current status
                    try:
                        from core import state
                        daemon_state = state.read_state()
                        voice_state = daemon_state.get("voice", {})
                        await websocket.send_json({
                            "type": "voice_status",
                            "data": voice_state
                        })
                    except Exception:
                        pass
        except WebSocketDisconnect:
            manager.disconnect(websocket, "voice")

    @app.websocket("/ws/trading")
    async def websocket_trading(websocket: WebSocket):
        """WebSocket for real-time trading updates (positions, orders, prices)."""
        await manager.connect(websocket, "trading")
        try:
            while True:
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
        except WebSocketDisconnect:
            manager.disconnect(websocket, "trading")


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


async def broadcast_voice_status(data: Dict[str, Any]):
    """Broadcast voice status update (listening, speaking, processing)."""
    await manager.broadcast("voice", {"type": "voice_status", "data": data})


async def broadcast_voice_transcript(text: str, is_final: bool = False):
    """Broadcast voice transcription in real-time."""
    await manager.broadcast("voice", {
        "type": "voice_transcript",
        "data": {"text": text, "is_final": is_final}
    })


async def broadcast_trading_update(update_type: str, data: Dict[str, Any]):
    """Broadcast trading update (position, order, price)."""
    await manager.broadcast("trading", {"type": update_type, "data": data})


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
