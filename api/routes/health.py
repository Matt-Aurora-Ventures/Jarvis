"""
Enhanced health check endpoints for Jarvis API.

Provides detailed subsystem health monitoring:
- Database connectivity
- External API availability (Birdeye, Jupiter, Grok)
- Bot health status (Telegram, Twitter)
- Cache status
- Queue depths
- LLM provider health
"""

import logging
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/health", tags=["health"])


class HealthStatus(BaseModel):
    """Health status for a single subsystem."""
    healthy: bool
    status: str  # "ok", "degraded", "down"
    message: Optional[str] = None
    latency_ms: Optional[int] = None
    metadata: Dict[str, Any] = {}


class HealthCheckResponse(BaseModel):
    """Overall health check response."""
    status: str  # "healthy", "degraded", "unhealthy"
    timestamp: float
    version: str
    subsystems: Dict[str, HealthStatus]
    summary: Dict[str, Any]


def check_database_health() -> HealthStatus:
    """Check database connectivity and performance."""
    start = time.time()
    try:
        from core import state

        # Try to read state
        state_data = state.read_state()
        latency_ms = int((time.time() - start) * 1000)

        # Check if state is accessible
        if state_data is not None:
            return HealthStatus(
                healthy=True,
                status="ok",
                message="Database operational",
                latency_ms=latency_ms,
                metadata={
                    "state_keys": len(state_data) if isinstance(state_data, dict) else 0,
                }
            )
        else:
            return HealthStatus(
                healthy=False,
                status="degraded",
                message="State read returned None",
                latency_ms=latency_ms
            )
    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        logger.error(f"Database health check failed: {e}")
        return HealthStatus(
            healthy=False,
            status="down",
            message=f"Database error: {str(e)[:100]}",
            latency_ms=latency_ms
        )


def check_birdeye_api() -> HealthStatus:
    """Check Birdeye API availability."""
    start = time.time()
    try:
        from core import birdeye

        # Try a simple API call (get SOL price as a canary)
        result = birdeye.get_token_price("So11111111111111111111111111111111111111112")
        latency_ms = int((time.time() - start) * 1000)

        if result and result.get("success"):
            return HealthStatus(
                healthy=True,
                status="ok",
                message="Birdeye API operational",
                latency_ms=latency_ms,
                metadata={"last_price": result.get("data", {}).get("value")}
            )
        else:
            return HealthStatus(
                healthy=False,
                status="degraded",
                message="Birdeye API returned error",
                latency_ms=latency_ms
            )
    except ImportError:
        return HealthStatus(
            healthy=False,
            status="down",
            message="Birdeye module not available",
            latency_ms=0
        )
    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        logger.error(f"Birdeye health check failed: {e}")
        return HealthStatus(
            healthy=False,
            status="down",
            message=f"Birdeye error: {str(e)[:100]}",
            latency_ms=latency_ms
        )


def check_jupiter_api() -> HealthStatus:
    """Check Jupiter aggregator API availability."""
    start = time.time()
    try:
        import requests

        # Check Jupiter quote API (lightweight health check)
        response = requests.get(
            "https://quote-api.jup.ag/v6/quote",
            params={
                "inputMint": "So11111111111111111111111111111111111111112",  # SOL
                "outputMint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
                "amount": "1000000",  # 0.001 SOL
            },
            timeout=5
        )
        latency_ms = int((time.time() - start) * 1000)

        if response.status_code == 200:
            return HealthStatus(
                healthy=True,
                status="ok",
                message="Jupiter API operational",
                latency_ms=latency_ms
            )
        else:
            return HealthStatus(
                healthy=False,
                status="degraded",
                message=f"Jupiter API returned {response.status_code}",
                latency_ms=latency_ms
            )
    except requests.Timeout:
        return HealthStatus(
            healthy=False,
            status="degraded",
            message="Jupiter API timeout",
            latency_ms=5000
        )
    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        logger.error(f"Jupiter health check failed: {e}")
        return HealthStatus(
            healthy=False,
            status="down",
            message=f"Jupiter error: {str(e)[:100]}",
            latency_ms=latency_ms
        )


def check_grok_api() -> HealthStatus:
    """Check Grok/X.AI API availability."""
    start = time.time()
    try:
        from core import secrets

        # Check if key is configured
        grok_key = secrets.get_grok_key()
        if not grok_key:
            return HealthStatus(
                healthy=True,  # Not configured is not unhealthy
                status="ok",
                message="Grok not configured (optional)",
                latency_ms=0,
                metadata={"configured": False}
            )

        # Try to initialize client
        from core.providers import _grok_client
        client = _grok_client()

        if client:
            return HealthStatus(
                healthy=True,
                status="ok",
                message="Grok client initialized",
                latency_ms=int((time.time() - start) * 1000),
                metadata={"configured": True}
            )
        else:
            return HealthStatus(
                healthy=False,
                status="degraded",
                message="Grok client failed to initialize",
                latency_ms=int((time.time() - start) * 1000)
            )
    except Exception as e:
        logger.error(f"Grok health check failed: {e}")
        return HealthStatus(
            healthy=False,
            status="down",
            message=f"Grok error: {str(e)[:100]}",
            latency_ms=int((time.time() - start) * 1000)
        )


def check_llm_providers() -> HealthStatus:
    """Check LLM provider health (Groq, OpenRouter, Ollama, etc.)."""
    start = time.time()
    try:
        from core.providers import check_provider_health

        health = check_provider_health()
        latency_ms = int((time.time() - start) * 1000)

        # Count available providers
        available = [name for name, info in health.items() if info["available"]]
        total = len(health)

        if len(available) >= 2:
            status = "ok"
            message = f"{len(available)}/{total} providers available"
            healthy = True
        elif len(available) == 1:
            status = "degraded"
            message = f"Only 1/{total} provider available"
            healthy = True
        else:
            status = "down"
            message = "No LLM providers available"
            healthy = False

        return HealthStatus(
            healthy=healthy,
            status=status,
            message=message,
            latency_ms=latency_ms,
            metadata={
                "available_providers": available,
                "total_providers": total,
                "details": health
            }
        )
    except Exception as e:
        logger.error(f"LLM provider health check failed: {e}")
        return HealthStatus(
            healthy=False,
            status="down",
            message=f"Provider check error: {str(e)[:100]}",
            latency_ms=int((time.time() - start) * 1000)
        )


def check_telegram_bot() -> HealthStatus:
    """Check Telegram bot health."""
    start = time.time()
    try:
        from core import state

        # Read bot state from daemon state
        daemon_state = state.read_state()
        component_status = daemon_state.get("component_status", {})

        # Check for telegram bot component
        tg_status = component_status.get("telegram_bot", {})

        if tg_status.get("ok"):
            return HealthStatus(
                healthy=True,
                status="ok",
                message="Telegram bot running",
                latency_ms=int((time.time() - start) * 1000),
                metadata=tg_status
            )
        elif tg_status.get("error"):
            return HealthStatus(
                healthy=False,
                status="degraded",
                message=f"Telegram bot error: {tg_status.get('error', 'unknown')}",
                latency_ms=int((time.time() - start) * 1000)
            )
        else:
            return HealthStatus(
                healthy=True,  # Not running is not necessarily unhealthy
                status="ok",
                message="Telegram bot not configured",
                latency_ms=int((time.time() - start) * 1000),
                metadata={"configured": False}
            )
    except Exception as e:
        logger.error(f"Telegram bot health check failed: {e}")
        return HealthStatus(
            healthy=False,
            status="down",
            message=f"Check error: {str(e)[:100]}",
            latency_ms=int((time.time() - start) * 1000)
        )


def check_twitter_bot() -> HealthStatus:
    """Check Twitter/X bot health."""
    start = time.time()
    try:
        from core import state
        import os

        # Check if X bot is enabled
        x_enabled = os.getenv("X_BOT_ENABLED", "true").lower() == "true"

        if not x_enabled:
            return HealthStatus(
                healthy=True,
                status="ok",
                message="Twitter bot disabled",
                latency_ms=int((time.time() - start) * 1000),
                metadata={"enabled": False}
            )

        # Read bot state
        daemon_state = state.read_state()
        component_status = daemon_state.get("component_status", {})

        # Check for twitter bot components
        twitter_poster = component_status.get("twitter_poster", {})
        autonomous_x = component_status.get("autonomous_x", {})

        # Consider healthy if either component is OK
        if twitter_poster.get("ok") or autonomous_x.get("ok"):
            return HealthStatus(
                healthy=True,
                status="ok",
                message="Twitter bot running",
                latency_ms=int((time.time() - start) * 1000),
                metadata={
                    "poster": twitter_poster.get("ok", False),
                    "autonomous": autonomous_x.get("ok", False)
                }
            )
        else:
            return HealthStatus(
                healthy=False,
                status="degraded",
                message="Twitter bot components not responding",
                latency_ms=int((time.time() - start) * 1000),
                metadata={
                    "poster_error": twitter_poster.get("error"),
                    "autonomous_error": autonomous_x.get("error")
                }
            )
    except Exception as e:
        logger.error(f"Twitter bot health check failed: {e}")
        return HealthStatus(
            healthy=False,
            status="down",
            message=f"Check error: {str(e)[:100]}",
            latency_ms=int((time.time() - start) * 1000)
        )


def check_cache_status() -> HealthStatus:
    """Check cache system health."""
    start = time.time()
    try:
        from core.cache.api_cache import APICache

        cache = APICache()

        # Get cache stats
        stats = cache.get_stats()
        latency_ms = int((time.time() - start) * 1000)

        # Cache is healthy if it's responding
        return HealthStatus(
            healthy=True,
            status="ok",
            message="Cache operational",
            latency_ms=latency_ms,
            metadata=stats
        )
    except ImportError:
        return HealthStatus(
            healthy=True,
            status="ok",
            message="Cache not configured (optional)",
            latency_ms=0,
            metadata={"configured": False}
        )
    except Exception as e:
        logger.error(f"Cache health check failed: {e}")
        return HealthStatus(
            healthy=False,
            status="degraded",
            message=f"Cache error: {str(e)[:100]}",
            latency_ms=int((time.time() - start) * 1000)
        )


@router.get("/", response_model=HealthCheckResponse)
async def health_check():
    """
    Comprehensive health check for all Jarvis subsystems.

    Returns detailed status for:
    - Database connectivity
    - External APIs (Birdeye, Jupiter, Grok)
    - Bots (Telegram, Twitter)
    - Cache
    - LLM providers
    """
    start = time.time()

    # Run all health checks
    subsystems = {
        "database": check_database_health(),
        "birdeye_api": check_birdeye_api(),
        "jupiter_api": check_jupiter_api(),
        "grok_api": check_grok_api(),
        "llm_providers": check_llm_providers(),
        "telegram_bot": check_telegram_bot(),
        "twitter_bot": check_twitter_bot(),
        "cache": check_cache_status(),
    }

    # Determine overall health
    critical_subsystems = ["database", "llm_providers"]
    critical_healthy = all(
        subsystems[name].healthy for name in critical_subsystems if name in subsystems
    )

    all_healthy = all(s.healthy for s in subsystems.values())

    if critical_healthy and all_healthy:
        overall_status = "healthy"
    elif critical_healthy:
        overall_status = "degraded"
    else:
        overall_status = "unhealthy"

    # Count subsystems
    total_count = len(subsystems)
    healthy_count = sum(1 for s in subsystems.values() if s.healthy)
    degraded_count = sum(1 for s in subsystems.values() if s.status == "degraded")
    down_count = sum(1 for s in subsystems.values() if s.status == "down")

    total_latency_ms = int((time.time() - start) * 1000)

    return HealthCheckResponse(
        status=overall_status,
        timestamp=time.time(),
        version="4.3.0",
        subsystems=subsystems,
        summary={
            "total_subsystems": total_count,
            "healthy_subsystems": healthy_count,
            "degraded_subsystems": degraded_count,
            "down_subsystems": down_count,
            "check_latency_ms": total_latency_ms,
        }
    )


@router.get("/quick")
async def quick_health_check():
    """
    Quick health check for load balancers.

    Returns 200 OK if critical systems are healthy, 503 if not.
    """
    try:
        # Only check critical systems
        db_health = check_database_health()
        llm_health = check_llm_providers()

        if db_health.healthy and llm_health.healthy:
            return {
                "status": "ok",
                "timestamp": time.time()
            }
        else:
            from fastapi import Response
            return Response(
                content='{"status": "unhealthy"}',
                status_code=503,
                media_type="application/json"
            )
    except Exception as e:
        logger.error(f"Quick health check failed: {e}")
        from fastapi import Response
        return Response(
            content='{"status": "error"}',
            status_code=503,
            media_type="application/json"
        )


@router.get("/subsystem/{subsystem_name}")
async def subsystem_health(subsystem_name: str):
    """
    Get health status for a specific subsystem.

    Available subsystems:
    - database
    - birdeye_api
    - jupiter_api
    - grok_api
    - llm_providers
    - telegram_bot
    - twitter_bot
    - cache
    """
    health_checks = {
        "database": check_database_health,
        "birdeye_api": check_birdeye_api,
        "jupiter_api": check_jupiter_api,
        "grok_api": check_grok_api,
        "llm_providers": check_llm_providers,
        "telegram_bot": check_telegram_bot,
        "twitter_bot": check_twitter_bot,
        "cache": check_cache_status,
    }

    if subsystem_name not in health_checks:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=404,
            detail=f"Subsystem '{subsystem_name}' not found. Available: {list(health_checks.keys())}"
        )

    health_status = health_checks[subsystem_name]()

    return {
        "subsystem": subsystem_name,
        "timestamp": time.time(),
        "health": health_status
    }
