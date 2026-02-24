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

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.gzip import GZipMiddleware

from api.errors import make_error_response
from api.versioning import APIVersionMiddleware, create_version_info_router

# Performance: Use orjson for faster JSON responses
try:
    from fastapi.responses import ORJSONResponse
    DEFAULT_RESPONSE_CLASS = ORJSONResponse
except ImportError:
    DEFAULT_RESPONSE_CLASS = JSONResponse

# Import new middleware
try:
    from api.middleware.rate_limit_headers import RateLimitHeadersMiddleware
    from api.middleware.security_headers import SecurityHeadersMiddleware
    from api.middleware.request_tracing import RequestTracingMiddleware
    from api.middleware.request_logging import RequestLoggingMiddleware
    from api.middleware.body_limit import BodySizeLimitMiddleware
    from api.middleware.compression import CompressionMiddleware
    from api.middleware.timeout import TimeoutMiddleware
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

    # OpenAPI tags for documentation organization
    tags_metadata = [
        {
            "name": "health",
            "description": "System health and status endpoints",
        },
        {
            "name": "staking",
            "description": "Token staking operations and rewards",
        },
        {
            "name": "credits",
            "description": "Credit system and billing operations",
        },
        {
            "name": "treasury",
            "description": "Treasury management and trading operations",
        },
        {
            "name": "trading",
            "description": "Trading execution and order management",
        },
        {
            "name": "voice",
            "description": "Voice command and TTS/STT operations",
        },
        {
            "name": "websocket",
            "description": "Real-time WebSocket connections",
        },
    ]

    app = FastAPI(
        title="JARVIS API",
        description="""
# JARVIS Trading & Automation Platform API

JARVIS is an autonomous AI trading and life automation platform.

## Features

- **Trading**: Execute trades on Solana DEXs (Jupiter, Raydium)
- **Treasury**: Manage treasury wallets and distributions
- **Staking**: Token staking with dynamic APY
- **Credits**: Usage-based billing system
- **Voice**: Voice commands and TTS responses
- **Real-time**: WebSocket feeds for live updates

## Authentication

Most endpoints require authentication via:
- JWT Bearer token in Authorization header
- API key in X-API-Key header

## Rate Limits

| Tier | Requests/min | Requests/hour |
|------|--------------|---------------|
| Free | 10 | 100 |
| Starter | 50 | 500 |
| Pro | 200 | 2000 |
| Whale | 1000 | 10000 |

## WebSocket Channels

- `/ws/trading` - Trade execution updates
- `/ws/staking` - Staking rewards updates
- `/ws/treasury` - Treasury activity
- `/ws/credits` - Credit usage
- `/ws/voice` - Voice command responses
        """,
        version="4.3.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        default_response_class=DEFAULT_RESPONSE_CLASS,
        openapi_tags=tags_metadata,
        contact={
            "name": "JARVIS Support",
            "url": "https://github.com/Matt-Aurora-Ventures/Jarvis",
        },
        license_info={
            "name": "Proprietary",
        },
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
        # Request timeout handling
        if os.getenv("TIMEOUT_ENABLED", "true").lower() == "true":
            app.add_middleware(TimeoutMiddleware, enabled=True)
            logger.info("Request timeout middleware enabled")

        # Request tracing (adds X-Request-ID)
        app.add_middleware(RequestTracingMiddleware)

        # Comprehensive request/response logging
        if os.getenv("REQUEST_LOGGING_ENABLED", "true").lower() == "true":
            log_request_body = os.getenv("LOG_REQUEST_BODY", "false").lower() == "true"
            log_response_body = os.getenv("LOG_RESPONSE_BODY", "false").lower() == "true"
            slow_threshold = float(os.getenv("SLOW_REQUEST_THRESHOLD", "1.0"))
            app.add_middleware(
                RequestLoggingMiddleware,
                log_request_body=log_request_body,
                log_response_body=log_response_body,
                slow_request_threshold=slow_threshold,
            )
            logger.info(f"Request logging enabled (slow threshold: {slow_threshold}s)")

        # Security headers (X-Frame-Options, CSP, etc.)
        app.add_middleware(SecurityHeadersMiddleware)

        # Rate limiting with headers
        if os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true":
            requests_per_minute = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
            requests_per_hour = int(os.getenv("RATE_LIMIT_PER_HOUR", "1000"))
            requests_per_day = int(os.getenv("RATE_LIMIT_PER_DAY", "10000"))
            burst_limit = int(os.getenv("RATE_LIMIT_BURST", "10"))

            app.add_middleware(
                RateLimitHeadersMiddleware,
                requests_per_minute=requests_per_minute,
                requests_per_hour=requests_per_hour,
                requests_per_day=requests_per_day,
                burst_limit=burst_limit,
                enabled=True,
                exclude_paths=["/health", "/metrics", "/docs", "/openapi.json", "/redoc"],
            )
            logger.info(f"Rate limiting enabled: {requests_per_minute}/min, {requests_per_hour}/hour, {requests_per_day}/day, burst={burst_limit}")

        # Request body size limit (10MB default)
        app.add_middleware(BodySizeLimitMiddleware, max_size=10 * 1024 * 1024)

        # Response compression (gzip/brotli) - only compress responses > 1KB
        compression_enabled = os.getenv("COMPRESSION_ENABLED", "true").lower() == "true"
        if compression_enabled:
            compression_threshold = int(os.getenv("COMPRESSION_MIN_SIZE", "1024"))
            compression_level = int(os.getenv("COMPRESSION_LEVEL", "6"))
            app.add_middleware(
                CompressionMiddleware,
                minimum_size=compression_threshold,
                compression_level=compression_level,
            )
            logger.info(f"Response compression enabled (threshold: {compression_threshold} bytes, level: {compression_level})")

        logger.info("Security middleware enabled")

    # API Versioning middleware
    if os.getenv("API_VERSIONING_ENABLED", "true").lower() == "true":
        app.add_middleware(APIVersionMiddleware)
        logger.info("API versioning middleware enabled")

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
        payload = make_error_response(error_code, str(exc.detail))
        payload["detail"] = str(exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content=payload
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

        test_mode = (
            os.getenv("ENVIRONMENT") == "test"
            or os.getenv("TEST_MODE", "").lower() == "true"
            or os.getenv("PYTEST_CURRENT_TEST") is not None
        )

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

        # Check provider availability (skip heavy checks in test mode)
        providers_status = {}
        providers_healthy = True
        if not test_mode:
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

        # Check voice system (skip in test mode to avoid slow/hanging deps)
        voice_status = {"available": False, "tts": False, "stt": False, "microphone": False}
        if not test_mode:
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

    @app.get("/api/ai/control-plane")
    async def ai_control_plane_snapshot():
        """Unified AI control plane snapshot for consensus/context/upgrader/compute."""
        try:
            from core.ai_control_plane import build_ai_control_plane_snapshot

            return build_ai_control_plane_snapshot()
        except Exception as exc:
            logger.warning("AI control plane snapshot unavailable: %s", exc)
            return {
                "status": "degraded",
                "timestamp": None,
                "panels": {},
                "error": str(exc),
            }

    @app.get("/api/roadmap/capabilities")
    async def roadmap_capabilities_snapshot():
        """Capability-driven roadmap status for frontend roadmap rendering."""
        try:
            from core.roadmap_capabilities import build_roadmap_capability_snapshot

            return build_roadmap_capability_snapshot()
        except Exception as exc:
            logger.warning("Roadmap capability snapshot unavailable: %s", exc)
            return {
                "status": "degraded",
                "generated_at": None,
                "summary": {
                    "total_features": 0,
                    "completed_features": 0,
                    "overall_progress_percent": 0,
                    "state_counts": {},
                },
                "phases": [],
                "state_catalog": {},
                "source": "capability_probes_v1",
                "error": str(exc),
            }

    @app.get("/api/runtime/capabilities")
    async def runtime_capabilities_snapshot():
        """Runtime capability report including degraded-mode reasons and fallbacks."""
        try:
            from core.runtime_capabilities import build_runtime_capability_report

            return build_runtime_capability_report()
        except Exception as exc:
            logger.warning("Runtime capability report unavailable: %s", exc)
            return {
                "generated_at": None,
                "components": {},
                "status": "degraded",
                "error": str(exc),
            }

    @app.get("/api/market/depth")
    async def market_depth_snapshot(symbol: str = "SOL", levels: int = 20):
        """Live market-depth snapshot for roadmap trading surfaces."""
        try:
            from core.roadmap_live_data import build_market_depth_snapshot

            return build_market_depth_snapshot(symbol=symbol, levels=levels)
        except Exception as exc:
            logger.warning("Market depth snapshot unavailable: %s", exc)
            return {
                "source": "degraded_fallback",
                "status": "degraded",
                "symbol": symbol.upper(),
                "levels": levels,
                "bids": [],
                "asks": [],
                "error": str(exc),
            }

    @app.get("/api/intel/smart-money")
    async def smart_money_snapshot(limit: int = 8):
        """Smart-money feed backing the roadmap intelligence panel."""
        try:
            from core.roadmap_live_data import build_smart_money_snapshot

            return build_smart_money_snapshot(limit=limit)
        except Exception as exc:
            logger.warning("Smart money snapshot unavailable: %s", exc)
            return {"source": "degraded_fallback", "wallets": [], "error": str(exc)}

    @app.get("/api/intel/sentiment")
    async def sentiment_snapshot(token_limit: int = 8, post_limit: int = 10):
        """Social sentiment feed backing roadmap intelligence panel."""
        try:
            from core.roadmap_live_data import build_social_sentiment_snapshot

            return build_social_sentiment_snapshot(token_limit=token_limit, post_limit=post_limit)
        except Exception as exc:
            logger.warning("Sentiment snapshot unavailable: %s", exc)
            return {
                "source": "degraded_fallback",
                "overall_score": 0,
                "tokens": [],
                "posts": [],
                "error": str(exc),
            }

    @app.get("/api/intel/signal-aggregator")
    async def signal_aggregator_snapshot(limit: int = 10, chain: str = "solana"):
        """Signal-aggregator feed with ranked opportunities and provenance tags."""
        try:
            from core.roadmap_live_data import build_signal_aggregator_snapshot

            return build_signal_aggregator_snapshot(limit=limit, chain=chain)
        except Exception as exc:
            logger.warning("Signal aggregator snapshot unavailable: %s", exc)
            return {
                "source": "degraded_fallback",
                "timestamp": None,
                "chain": chain,
                "summary": {
                    "opportunity_count": 0,
                    "bullish_count": 0,
                    "bearish_count": 0,
                    "avg_signal_score": 0.0,
                },
                "opportunities": [],
                "error": str(exc),
            }

    @app.get("/api/intel/ml-regime")
    async def ml_regime_snapshot(symbol: str = "SOL"):
        """ML-regime status endpoint for strategy adaptation visibility."""
        try:
            from core.roadmap_live_data import build_ml_regime_snapshot

            return build_ml_regime_snapshot(symbol=symbol)
        except Exception as exc:
            logger.warning("ML regime snapshot unavailable: %s", exc)
            return {
                "source": "degraded_fallback",
                "timestamp": None,
                "status": "degraded",
                "symbol": symbol.upper(),
                "regime": "unknown",
                "confidence": 0.0,
                "recommended_strategy": "MeanReversion",
                "classifier": "unavailable",
                "features": {},
                "error": str(exc),
            }

    @app.get("/api/sentinel/status")
    async def sentinel_status_snapshot():
        """Unified Sentinel status (coliseum + approvals + kill-switch)."""
        try:
            from core.roadmap_live_data import build_sentinel_status_snapshot

            return build_sentinel_status_snapshot()
        except Exception as exc:
            logger.warning("Sentinel status unavailable: %s", exc)
            return {
                "source": "degraded_fallback",
                "status": "degraded",
                "approval_gate": {},
                "kill_switch": {},
                "coliseum": {},
                "error": str(exc),
            }

    @app.get("/api/sentinel/coliseum")
    async def sentinel_coliseum_snapshot(limit: int = 10):
        """Coliseum strategy summary and recent strategy outcomes."""
        try:
            from core.roadmap_live_data import build_coliseum_snapshot

            return build_coliseum_snapshot(limit=limit)
        except Exception as exc:
            logger.warning("Coliseum snapshot unavailable: %s", exc)
            return {
                "source": "degraded_fallback",
                "status": "degraded",
                "summary": {},
                "strategies": [],
                "error": str(exc),
            }

    @app.get("/api/lifeos/voice/status")
    async def lifeos_voice_status_snapshot():
        """Voice-system readiness surface for roadmap lifeOS integration."""
        try:
            from core.roadmap_live_data import build_voice_status_snapshot

            return build_voice_status_snapshot()
        except Exception as exc:
            logger.warning("Voice status snapshot unavailable: %s", exc)
            return {
                "source": "degraded_fallback",
                "timestamp": None,
                "status": "degraded",
                "capabilities": {},
                "error": str(exc),
            }

    @app.get("/api/lifeos/knowledge/status")
    async def lifeos_knowledge_status_snapshot():
        """Knowledge/memory readiness surface for roadmap lifeOS integration."""
        try:
            from core.roadmap_live_data import build_knowledge_status_snapshot

            return build_knowledge_status_snapshot()
        except Exception as exc:
            logger.warning("Knowledge status snapshot unavailable: %s", exc)
            return {
                "source": "degraded_fallback",
                "timestamp": None,
                "status": "degraded",
                "capabilities": {},
                "metrics": {},
                "error": str(exc),
            }

    @app.get("/api/lifeos/mirror/status")
    async def lifeos_mirror_status_snapshot():
        """Mirror Test operational status and seven-day trend summary."""
        try:
            from core.roadmap_live_data import build_mirror_test_snapshot

            return build_mirror_test_snapshot()
        except Exception as exc:
            logger.warning("Mirror test snapshot unavailable: %s", exc)
            return {
                "source": "degraded_fallback",
                "status": "degraded",
                "last_run": None,
                "runs_7d": 0,
                "avg_score_7d": 0.0,
                "pending_reviews": 0,
                "error": str(exc),
            }

    @app.get("/api/advanced/mev")
    async def advanced_mev_snapshot(limit: int = 20, chain: str = "solana"):
        """MEV dashboard feed for advanced tooling surfaces."""
        try:
            from core.roadmap_live_data import build_advanced_mev_snapshot

            return build_advanced_mev_snapshot(limit=limit, chain=chain)
        except Exception as exc:
            logger.warning("Advanced MEV snapshot unavailable: %s", exc)
            return {
                "source": "degraded_fallback",
                "timestamp": None,
                "chain": chain,
                "summary": {
                    "event_count": 0,
                    "total_profit_usd": 0.0,
                    "total_victim_loss_usd": 0.0,
                    "high_severity_count": 0,
                    "medium_severity_count": 0,
                    "low_severity_count": 0,
                },
                "events": [],
                "error": str(exc),
            }

    @app.get("/api/advanced/multi-dex")
    async def advanced_multi_dex_snapshot(trading_pair: str = "SOL-USDC", amount_usd: float = 1000.0):
        """Multi-DEX quote comparison endpoint."""
        try:
            from core.roadmap_live_data import build_advanced_multi_dex_snapshot

            return build_advanced_multi_dex_snapshot(trading_pair=trading_pair, amount_usd=amount_usd)
        except Exception as exc:
            logger.warning("Advanced multi-dex snapshot unavailable: %s", exc)
            return {
                "source": "degraded_fallback",
                "timestamp": None,
                "trading_pair": str(trading_pair).upper(),
                "amount_usd": float(amount_usd),
                "quotes": [],
                "best_route": {},
                "error": str(exc),
            }

    @app.get("/api/analytics/portfolio")
    async def analytics_portfolio_snapshot(range: str = "7d"):
        """Portfolio analytics summary endpoint for phase-5 roadmap surfaces."""
        try:
            from core.roadmap_live_data import build_portfolio_analytics_snapshot

            return build_portfolio_analytics_snapshot(range_key=range)
        except Exception as exc:
            logger.warning("Portfolio analytics snapshot unavailable: %s", exc)
            return {
                "source": "degraded_fallback",
                "timestamp": None,
                "range": range,
                "metrics": {},
                "trades": [],
                "holdings": [],
                "pnl_distribution": {},
                "error": str(exc),
            }

    @app.get("/api/advanced/perps/status")
    async def advanced_perps_status_snapshot():
        """Perps production-readiness surface for roadmap and control plane."""
        try:
            from core.roadmap_live_data import build_advanced_perps_status_snapshot

            return build_advanced_perps_status_snapshot()
        except Exception as exc:
            logger.warning("Advanced perps status unavailable: %s", exc)
            return {
                "source": "degraded_fallback",
                "timestamp": None,
                "status": "degraded",
                "capabilities": {},
                "mode": "degraded_fallback",
                "error": str(exc),
            }

    @app.get("/api/polish/themes/status")
    async def polish_theme_status_snapshot():
        """Theme-system readiness status."""
        try:
            from core.roadmap_live_data import build_advanced_theme_status_snapshot

            return build_advanced_theme_status_snapshot()
        except Exception as exc:
            logger.warning("Theme status snapshot unavailable: %s", exc)
            return {
                "source": "degraded_fallback",
                "timestamp": None,
                "status": "degraded",
                "theme_modes": [],
                "capabilities": {},
                "error": str(exc),
            }

    @app.get("/api/polish/onboarding/status")
    async def polish_onboarding_status_snapshot():
        """Onboarding readiness status."""
        try:
            from core.roadmap_live_data import build_advanced_onboarding_status_snapshot

            return build_advanced_onboarding_status_snapshot()
        except Exception as exc:
            logger.warning("Onboarding status snapshot unavailable: %s", exc)
            return {
                "source": "degraded_fallback",
                "timestamp": None,
                "status": "degraded",
                "steps": [],
                "capabilities": {},
                "error": str(exc),
            }

    @app.post("/api/trade")
    async def execute_trade(payload: Dict[str, Any]):
        """Execute paper trade for the primary order-panel surface."""
        try:
            from core.roadmap_live_data import execute_paper_trade

            mint = str(payload.get("mint") or "").strip()
            side = str(payload.get("side") or "buy").strip().lower()
            symbol = str(payload.get("symbol") or "SOL").strip().upper()
            amount_sol = float(payload.get("amount_sol") or 0)
            tp_pct = float(payload.get("tp_pct") or 20)
            sl_pct = float(payload.get("sl_pct") or 10)

            return execute_paper_trade(
                mint=mint,
                side=side,
                amount_sol=amount_sol,
                tp_pct=tp_pct,
                sl_pct=sl_pct,
                symbol=symbol,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.warning("Paper trade endpoint failed: %s", exc)
            return {
                "success": False,
                "status": "error",
                "error": str(exc),
            }

    @app.get("/api/sentinel/approvals/pending")
    async def sentinel_pending_approvals():
        """List pending approval-gate proposals."""
        try:
            from core.approval_gate import get_approval_gate

            pending = [item.to_dict() for item in get_approval_gate().get_pending()]
            return {"count": len(pending), "items": pending}
        except Exception as exc:
            logger.warning("Pending approvals unavailable: %s", exc)
            return {"count": 0, "items": [], "error": str(exc)}

    @app.post("/api/sentinel/approvals/{proposal_id}/approve")
    async def sentinel_approve(proposal_id: str, approved_by: str = "api_user"):
        """Approve a pending trade proposal."""
        try:
            from core.approval_gate import get_approval_gate

            ok = get_approval_gate().approve(proposal_id=proposal_id, approved_by=approved_by)
            return {"ok": bool(ok), "proposal_id": proposal_id}
        except Exception as exc:
            logger.warning("Approval action failed: %s", exc)
            return {"ok": False, "proposal_id": proposal_id, "error": str(exc)}

    @app.post("/api/sentinel/approvals/{proposal_id}/reject")
    async def sentinel_reject(proposal_id: str, reason: str = "Rejected via API"):
        """Reject a pending trade proposal."""
        try:
            from core.approval_gate import get_approval_gate

            ok = get_approval_gate().reject(proposal_id=proposal_id, reason=reason)
            return {"ok": bool(ok), "proposal_id": proposal_id}
        except Exception as exc:
            logger.warning("Reject action failed: %s", exc)
            return {"ok": False, "proposal_id": proposal_id, "error": str(exc)}

    @app.post("/api/sentinel/kill-switch/activate")
    async def sentinel_activate_kill_switch(reason: str = "Manual API activation", activated_by: str = "api_user"):
        """Activate sentinel kill switch through emergency-stop manager."""
        try:
            from core.trading.emergency_stop import get_emergency_stop_manager

            ok, message = get_emergency_stop_manager().activate_kill_switch(
                reason=reason,
                activated_by=activated_by,
            )
            return {"ok": bool(ok), "message": message}
        except Exception as exc:
            logger.warning("Kill-switch activation failed: %s", exc)
            return {"ok": False, "error": str(exc)}

    @app.post("/api/sentinel/kill-switch/reset")
    async def sentinel_reset_kill_switch():
        """Reset emergency stop and approval kill-switch states."""
        response = {"ok": True}
        try:
            from core.trading.emergency_stop import get_emergency_stop_manager

            ok, message = get_emergency_stop_manager().resume_trading(
                resumed_by="api_user",
            )
            response["emergency_stop"] = {"ok": bool(ok), "message": message}
            response["ok"] = response["ok"] and bool(ok)
        except Exception as exc:
            response["emergency_stop"] = {"ok": False, "error": str(exc)}
            response["ok"] = False

        try:
            from core.approval_gate import get_approval_gate

            ok = get_approval_gate().reset_kill_switch(confirm="I_UNDERSTAND_THE_RISK")
            response["approval_gate"] = {"ok": bool(ok)}
            response["ok"] = response["ok"] and bool(ok)
        except Exception as exc:
            response["approval_gate"] = {"ok": False, "error": str(exc)}
            response["ok"] = False

        return response

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

    @app.get("/api/metrics/bags")
    async def get_bags_trading_metrics():
        """Get bags.fm integration metrics and TP/SL trigger statistics."""
        try:
            from core.trading.bags_metrics import get_bags_metrics
            return get_bags_metrics().to_dict()
        except ImportError:
            return {
                "error": "bags.fm metrics not available",
                "bags_trades": 0,
                "jupiter_trades": 0,
                "bags_usage_pct": 0.0,
            }

    @app.get("/api/traces")
    async def recent_traces():
        """Get recent distributed traces."""
        try:
            from core.monitoring.tracing import tracer
            return {"traces": tracer.get_recent_traces(limit=50)}
        except ImportError:
            return {"traces": [], "error": "Tracing not available"}

    @app.get("/api/compression-stats")
    async def compression_stats():
        """Get response compression statistics."""
        if not HAS_MIDDLEWARE:
            return {"error": "Compression middleware not available"}

        # Find CompressionMiddleware instance in the middleware stack
        for middleware in app.user_middleware:
            if hasattr(middleware, 'cls') and middleware.cls.__name__ == 'CompressionMiddleware':
                # Can't easily access instance, return info about config
                return {
                    "enabled": True,
                    "minimum_size": int(os.getenv("COMPRESSION_MIN_SIZE", "1024")),
                    "compression_level": int(os.getenv("COMPRESSION_LEVEL", "6")),
                    "brotli_available": hasattr(middleware.cls, '__module__'),
                }

        return {"enabled": False, "error": "Compression middleware not found"}

    @app.get("/api/timeout-stats")
    async def timeout_stats():
        """Get request timeout statistics."""
        if not HAS_MIDDLEWARE:
            return {"error": "Timeout middleware not available"}

        # Find TimeoutMiddleware instance in the middleware stack
        for middleware in app.user_middleware:
            if hasattr(middleware, 'cls') and middleware.cls.__name__ == 'TimeoutMiddleware':
                # Try to access the instance to get stats
                if hasattr(middleware, 'kwargs') and 'enabled' in middleware.kwargs:
                    return {
                        "enabled": middleware.kwargs['enabled'],
                        "default_timeout": 30.0,
                        "max_client_timeout": 120.0,
                    }
                return {
                    "enabled": True,
                    "default_timeout": 30.0,
                    "max_client_timeout": 120.0,
                }

        return {"enabled": False, "error": "Timeout middleware not found"}

    return app


def _include_routers(app: FastAPI):
    """Include all API routers."""

    # Version info routes (shows available API versions)
    try:
        version_info_router = create_version_info_router()
        app.include_router(version_info_router)
        logger.info("Included API version info routes")
    except Exception as e:
        logger.warning(f"Version info routes not available: {e}")

    # V1 versioned routes (optional - provides /api/v1 prefix)
    if os.getenv("API_VERSIONING_ENABLED", "true").lower() == "true":
        try:
            from api.routes.v1 import create_v1_routers
            v1_routers = create_v1_routers()
            for router in v1_routers:
                app.include_router(router)
            logger.info(f"Included {len(v1_routers)} v1 versioned routes")
        except Exception as e:
            logger.warning(f"V1 versioned routes not available: {e}")

    # Health routes (NEW - enhanced health checks)
    try:
        from api.routes.health import router as health_router
        app.include_router(health_router)
        logger.info("Included enhanced health routes")
    except ImportError as e:
        logger.warning(f"Health routes not available: {e}")

    # Log management routes
    try:
        from api.routes.logs import router as logs_router
        app.include_router(logs_router)
        logger.info("Included log management routes")
    except ImportError as e:
        logger.warning(f"Log management routes not available: {e}")

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

    # Market data WebSocket routes
    try:
        from api.websocket.market_data import create_market_data_router
        market_data_router = create_market_data_router()
        app.include_router(market_data_router)
        logger.info("Included market data WebSocket routes")
    except ImportError as e:
        logger.warning(f"Market data WebSocket routes not available: {e}")


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
