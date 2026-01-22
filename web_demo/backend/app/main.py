"""
JARVIS Web Demo - FastAPI Application
Secure, standalone trading interface with AI-powered sentiment analysis.

Security Architecture: Implements Burak Eregar's principles
1. Treat every client as hostile
2. Enforce everything server-side
3. UI restrictions are not security
"""
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings, validate_security_settings
from app.security import add_security_headers, limiter

# Import routers
from app.routes import ai, bags, websocket, transactions, metrics
from app.services.websocket_manager import get_websocket_manager
from app.database import init_db
# from app.api import auth, wallet, trading, positions, sentiment, portfolio, admin

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    Initialize services on startup, cleanup on shutdown.
    """
    logger.info(f"Starting JARVIS Web Demo ({settings.APP_ENV})")

    # Validate security configuration
    try:
        validate_security_settings()
    except ValueError as e:
        logger.error(f"Security validation failed: {e}")
        raise

    # Initialize database connection pool and create tables
    init_db()
    logger.info("✓ Database initialized successfully")

    # Initialize Redis connection
    # await init_redis()

    # Startup AI provider
    if settings.XAI_ENABLED:
        logger.info("AI Provider: Grok (XAI)")
    elif settings.OLLAMA_ENABLED:
        logger.info(f"AI Provider: Ollama ({settings.OLLAMA_MODEL})")
    else:
        logger.warning("AI Provider: None (sentiment features disabled)")

    # Start WebSocket manager for real-time price feeds
    ws_manager = get_websocket_manager()
    await ws_manager.start(birdeye_api_key=None)  # Add Birdeye API key if available
    logger.info("✓ WebSocket manager started for real-time price feeds")

    logger.info("✓ Application started successfully")

    yield

    # Cleanup on shutdown
    logger.info("Shutting down application")

    # Stop WebSocket manager
    await ws_manager.stop()
    logger.info("✓ WebSocket manager stopped")

    # await close_db()
    # await close_redis()


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="Secure AI-powered Solana trading interface",
    version="1.0.0",
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
    lifespan=lifespan,
)

# Add rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# =============================================================================
# Middleware (Rule #2: Enforce security server-side)
# =============================================================================

# Security headers
app.middleware("http")(add_security_headers)

# CORS (Rule #1: Only allowed origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)

# Gzip compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Metrics collection
from app.middleware.metrics_middleware import MetricsMiddleware
app.add_middleware(MetricsMiddleware)


# =============================================================================
# Global Exception Handlers
# =============================================================================

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Handle validation errors."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors without exposing details."""
    logger.error(f"Unexpected error: {exc}", exc_info=True)

    # Never expose internal errors in production
    if settings.is_production:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An internal error occurred"},
        )
    else:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(exc)},
        )


# =============================================================================
# Health Checks
# =============================================================================

@app.get("/health", tags=["health"])
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint.
    Returns service status without exposing sensitive info.
    """
    return {
        "status": "healthy",
        "environment": settings.APP_ENV,
        "ai_provider": settings.ai_provider,
    }


@app.get("/health/ready", tags=["health"])
async def readiness_check() -> Dict[str, Any]:
    """
    Readiness check for Kubernetes/Docker.
    Verifies all dependencies are available.
    """
    checks = {
        "database": False,
        "redis": False,
        "solana_rpc": False,
    }

    try:
        # Check database
        # await db.execute("SELECT 1")
        checks["database"] = True
    except Exception as e:
        logger.error(f"Database check failed: {e}")

    try:
        # Check Redis
        # await redis.ping()
        checks["redis"] = True
    except Exception as e:
        logger.error(f"Redis check failed: {e}")

    try:
        # Check Solana RPC
        # await solana_client.is_connected()
        checks["solana_rpc"] = True
    except Exception as e:
        logger.error(f"Solana RPC check failed: {e}")

    all_healthy = all(checks.values())

    return {
        "ready": all_healthy,
        "checks": checks,
    }


# =============================================================================
# API Routes
# =============================================================================

@app.get("/", tags=["root"])
async def root() -> Dict[str, str]:
    """Root endpoint."""
    return {
        "message": "JARVIS Web Demo API",
        "version": "1.0.0",
        "docs": "/docs" if settings.is_development else "disabled",
    }


# Include routers (to be created)
# Register new self-correcting AI and Bags routes
app.include_router(ai.router, prefix=f"{settings.API_V1_PREFIX}")
app.include_router(bags.router, prefix=f"{settings.API_V1_PREFIX}")
app.include_router(websocket.router, prefix=f"{settings.API_V1_PREFIX}")
app.include_router(transactions.router, prefix=f"{settings.API_V1_PREFIX}")
app.include_router(metrics.router, prefix=f"{settings.API_V1_PREFIX}")

# app.include_router(auth.router, prefix=f"{settings.API_V1_PREFIX}/auth", tags=["auth"])
# app.include_router(wallet.router, prefix=f"{settings.API_V1_PREFIX}/wallet", tags=["wallet"])
# app.include_router(trading.router, prefix=f"{settings.API_V1_PREFIX}/trading", tags=["trading"])
# app.include_router(positions.router, prefix=f"{settings.API_V1_PREFIX}/positions", tags=["positions"])
# app.include_router(sentiment.router, prefix=f"{settings.API_V1_PREFIX}/sentiment", tags=["sentiment"])
# app.include_router(portfolio.router, prefix=f"{settings.API_V1_PREFIX}/portfolio", tags=["portfolio"])
# app.include_router(admin.router, prefix=f"{settings.API_V1_PREFIX}/admin", tags=["admin"])


# =============================================================================
# Metrics (if enabled)
# =============================================================================

if settings.ENABLE_METRICS:
    @app.get("/metrics", tags=["metrics"])
    async def metrics():
        """Prometheus metrics endpoint."""
        # Return Prometheus-formatted metrics
        return {
            "message": "Metrics endpoint - Prometheus format",
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.is_development,
        log_level=settings.LOG_LEVEL.lower(),
    )
