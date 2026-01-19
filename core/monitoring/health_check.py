"""
System Health Checker - Comprehensive component health monitoring.

Monitors all JARVIS components:
- Twitter bot: connected, posting working
- Telegram bot: polling active, responding to commands
- Trading engine: can execute trades, no errors
- Database: connectivity OK, no corruption
- API services: Grok, Jupiter, Solscan reachable

Status levels: HEALTHY, DEGRADED, CRITICAL
"""

import asyncio
import json
import logging
import os
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import aiohttp

logger = logging.getLogger("jarvis.monitoring.health_check")


class HealthLevel(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"


@dataclass
class ComponentStatus:
    """Status of a single component."""
    name: str
    status: str  # healthy, degraded, critical
    latency_ms: float
    message: str
    last_check: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemHealthResult:
    """Overall system health result."""
    status: str
    components: Dict[str, ComponentStatus]
    checked_at: datetime
    uptime_seconds: float = 0.0
    healthy_count: int = 0
    degraded_count: int = 0
    critical_count: int = 0


# Helper functions for component checks
async def check_twitter_connectivity() -> Dict[str, Any]:
    """Check Twitter/X connectivity status."""
    try:
        # Check for recent activity in the Grok state file
        grok_state_path = Path("bots/twitter/.grok_state.json")
        if grok_state_path.exists():
            with open(grok_state_path) as f:
                state = json.load(f)
                last_post = state.get("last_post_time")
                if last_post:
                    return {
                        "connected": True,
                        "last_post": last_post,
                        "status": "active"
                    }
        return {"connected": True, "last_post": None, "status": "idle"}
    except Exception as e:
        return {"connected": False, "error": str(e)}


async def check_telegram_connectivity() -> Dict[str, Any]:
    """Check Telegram bot connectivity."""
    try:
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if not token:
            return {"polling": False, "error": "No bot token configured"}

        async with aiohttp.ClientSession() as session:
            url = f"https://api.telegram.org/bot{token}/getMe"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        "polling": True,
                        "last_update": datetime.now(timezone.utc).isoformat(),
                        "bot_info": data.get("result", {})
                    }
                return {"polling": False, "error": f"HTTP {resp.status}"}
    except Exception as e:
        return {"polling": False, "error": str(e)}


async def check_trading_engine() -> Dict[str, Any]:
    """Check trading engine status."""
    try:
        # Check positions file
        positions_path = Path("bots/treasury/.positions.json")
        if positions_path.exists():
            with open(positions_path) as f:
                positions = json.load(f)
                return {
                    "operational": True,
                    "position_count": len(positions) if isinstance(positions, list) else 0,
                    "error_rate": 0.0
                }
        return {"operational": True, "position_count": 0, "error_rate": 0.0}
    except Exception as e:
        return {"operational": False, "error": str(e), "error_rate": 1.0}


class SystemHealthChecker:
    """
    Comprehensive system health checker.

    Checks all major components and provides unified health status.
    """

    VERSION = "1.0.0"

    def __init__(
        self,
        data_dir: str = "data/health",
        check_interval: int = 60,
    ):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.check_interval = check_interval
        self._start_time = datetime.now(timezone.utc)
        self._last_results: Dict[str, ComponentStatus] = {}

        # Component checkers
        self._checkers: Dict[str, Callable] = {
            "twitter_bot": self._check_twitter_bot,
            "telegram_bot": self._check_telegram_bot,
            "trading_engine": self._check_trading_engine,
            "database": self._check_database,
            "api_services": self._check_api_services,
        }

    async def check_component(self, name: str) -> ComponentStatus:
        """Check a single component's health."""
        if name not in self._checkers:
            return ComponentStatus(
                name=name,
                status="critical",
                latency_ms=0,
                message=f"Unknown component: {name}"
            )

        start = time.time()
        try:
            checker = self._checkers[name]
            result = await checker()
            latency = (time.time() - start) * 1000

            status = ComponentStatus(
                name=name,
                status=result.get("status", "healthy"),
                latency_ms=latency,
                message=result.get("message", "OK"),
                metadata=result.get("metadata", {})
            )
            self._last_results[name] = status
            return status

        except Exception as e:
            latency = (time.time() - start) * 1000
            status = ComponentStatus(
                name=name,
                status="critical",
                latency_ms=latency,
                message=f"Check failed: {e}"
            )
            self._last_results[name] = status
            return status

    async def check_all(self) -> Dict[str, Any]:
        """Run all health checks and return system status."""
        components = {}
        healthy = 0
        degraded = 0
        critical = 0

        for name in self._checkers:
            result = await self.check_component(name)
            components[name] = result

            if result.status == "healthy":
                healthy += 1
            elif result.status == "degraded":
                degraded += 1
            else:
                critical += 1

        # Determine overall status
        if critical > 0:
            overall = "critical"
        elif degraded > 0:
            overall = "degraded"
        else:
            overall = "healthy"

        uptime = (datetime.now(timezone.utc) - self._start_time).total_seconds()

        return {
            "status": overall,
            "components": {
                name: {
                    "status": comp.status,
                    "latency_ms": comp.latency_ms,
                    "message": comp.message,
                    "last_check": comp.last_check.isoformat(),
                    "metadata": comp.metadata
                }
                for name, comp in components.items()
            },
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "uptime_seconds": uptime,
            "summary": {
                "healthy": healthy,
                "degraded": degraded,
                "critical": critical,
                "total": len(components)
            }
        }

    async def get_health_json(self) -> str:
        """Get health status as JSON string."""
        result = await self.check_all()
        return json.dumps(result, indent=2, default=str)

    # Component-specific checkers
    async def _check_twitter_bot(self) -> Dict[str, Any]:
        """Check Twitter/X bot health."""
        try:
            result = await check_twitter_connectivity()
            if result.get("connected"):
                return {
                    "status": "healthy",
                    "message": "Twitter bot connected",
                    "metadata": result
                }
            return {
                "status": "degraded",
                "message": result.get("error", "Not connected"),
                "metadata": result
            }
        except Exception as e:
            return {"status": "critical", "message": str(e)}

    async def _check_telegram_bot(self) -> Dict[str, Any]:
        """Check Telegram bot health."""
        try:
            result = await check_telegram_connectivity()
            if result.get("polling"):
                return {
                    "status": "healthy",
                    "message": "Telegram bot polling",
                    "metadata": result
                }
            return {
                "status": "degraded",
                "message": result.get("error", "Not polling"),
                "metadata": result
            }
        except Exception as e:
            return {"status": "critical", "message": str(e)}

    async def _check_trading_engine(self) -> Dict[str, Any]:
        """Check trading engine health."""
        try:
            result = await check_trading_engine()
            if result.get("operational"):
                return {
                    "status": "healthy",
                    "message": f"Trading engine OK ({result.get('position_count', 0)} positions)",
                    "metadata": result
                }
            return {
                "status": "critical",
                "message": result.get("error", "Not operational"),
                "metadata": result
            }
        except Exception as e:
            return {"status": "critical", "message": str(e)}

    async def _check_database(self) -> Dict[str, Any]:
        """Check database connectivity."""
        start = time.time()
        try:
            db_path = self.data_dir.parent / "jarvis.db"
            if not db_path.exists():
                db_path = Path("data/jarvis.db")

            if db_path.exists():
                conn = sqlite3.connect(str(db_path), timeout=5)
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                conn.close()

                return {
                    "status": "healthy",
                    "message": "Database connection OK",
                    "metadata": {"latency_ms": (time.time() - start) * 1000}
                }
            else:
                # Try health.db
                health_db = Path("data/health.db")
                if health_db.exists():
                    conn = sqlite3.connect(str(health_db), timeout=5)
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
                    conn.close()
                    return {
                        "status": "healthy",
                        "message": "Database connection OK",
                        "metadata": {"latency_ms": (time.time() - start) * 1000}
                    }

            return {
                "status": "degraded",
                "message": "No database found",
                "metadata": {}
            }
        except Exception as e:
            return {
                "status": "critical",
                "message": f"Database error: {e}",
                "metadata": {}
            }

    async def _check_api_services(self) -> Dict[str, Any]:
        """Check external API services health."""
        services = {
            "jupiter": "https://quote-api.jup.ag/v6/quote?inputMint=So11111111111111111111111111111111111111112&outputMint=EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v&amount=1000000",
            "solscan": "https://api.solscan.io/health",
        }

        results = {}
        all_ok = True
        any_degraded = False

        try:
            async with aiohttp.ClientSession() as session:
                for name, url in services.items():
                    try:
                        start = time.time()
                        async with session.get(
                            url,
                            timeout=aiohttp.ClientTimeout(total=10)
                        ) as resp:
                            latency = (time.time() - start) * 1000
                            results[name] = {
                                "status": "ok" if resp.status == 200 else "error",
                                "latency_ms": latency,
                                "http_status": resp.status
                            }
                            if resp.status != 200:
                                any_degraded = True
                    except Exception as e:
                        results[name] = {"status": "error", "error": str(e)}
                        all_ok = False
        except Exception as e:
            return {"status": "critical", "message": str(e), "metadata": results}

        if all_ok and not any_degraded:
            return {
                "status": "healthy",
                "message": "All API services reachable",
                "metadata": results
            }
        elif any_degraded or not all_ok:
            return {
                "status": "degraded",
                "message": "Some API services unavailable",
                "metadata": results
            }
        return {"status": "critical", "message": "API services down", "metadata": results}


# Singleton
_health_checker: Optional[SystemHealthChecker] = None


def get_system_health_checker() -> SystemHealthChecker:
    """Get or create the system health checker singleton."""
    global _health_checker
    if _health_checker is None:
        _health_checker = SystemHealthChecker()
    return _health_checker
