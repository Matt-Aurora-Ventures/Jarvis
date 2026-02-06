"""
Health Checker Module

Provides HealthChecker class for comprehensive system health monitoring.
"""

import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import aiohttp

from .status import (
    HealthStatus,
    ComponentHealth,
    HealthReport,
    determine_overall_status,
)

logger = logging.getLogger("jarvis.health.checker")


class HealthChecker:
    """
    Comprehensive health checker for JARVIS system components.

    Checks:
    - Bot processes (running, PID, uptime)
    - Bot API responses (health endpoints)
    - Log errors (recent error count)
    - Memory usage (per process)
    - API quotas (Telegram, Twitter, etc.)
    - Database connectivity
    - Disk space
    """

    DEFAULT_BOTS = [
        "supervisor",
        "buy_bot",
        "sentiment_reporter",
        "twitter_poster",
        "telegram_bot",
        "autonomous_x",
        "treasury_bot",
        "clawdmatt",
        "clawdjarvis",
        "clawdfriday",
    ]

    def __init__(
        self,
        bot_names: Optional[List[str]] = None,
        log_dir: Optional[str] = None,
        vps_mode: bool = False,
    ):
        """
        Initialize HealthChecker.

        Args:
            bot_names: List of bot names to check (uses defaults if None)
            log_dir: Directory containing log files
            vps_mode: If True, use VPS-specific paths and settings
        """
        self.bot_names = bot_names or self.DEFAULT_BOTS
        self.vps_mode = vps_mode or os.getenv("VPS_MODE", "false").lower() in ("true", "1", "yes")

        # Determine log directory
        if log_dir:
            self.log_dir = Path(log_dir)
        elif self.vps_mode:
            self.log_dir = Path("/root/clawdbots/logs")
        else:
            self.log_dir = Path("logs")

        # API endpoints to check
        self._api_endpoints = {
            "telegram": "https://api.telegram.org/bot{token}/getMe",
            "twitter": "https://api.twitter.com/2/tweets",
            "jupiter": "https://quote-api.jup.ag/v6/health",
            "helius": "https://mainnet.helius-rpc.com",
        }

    async def check_bot(self, bot_name: str) -> HealthStatus:
        """
        Check health of a specific bot.

        Args:
            bot_name: Name of the bot to check

        Returns:
            HealthStatus enum value
        """
        from scripts.health_check import check_bot_process

        result = check_bot_process(bot_name)
        status = result.get("status", "unknown")

        if status == "running":
            return HealthStatus.HEALTHY
        elif status == "not_running":
            return HealthStatus.NOT_RUNNING
        else:
            return HealthStatus.UNKNOWN

    async def check_api(self, provider: str) -> HealthStatus:
        """
        Check health of an external API provider.

        Args:
            provider: API provider name (telegram, twitter, jupiter, etc.)

        Returns:
            HealthStatus enum value
        """
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                if provider == "telegram":
                    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
                    if not token:
                        return HealthStatus.NOT_CONFIGURED
                    url = f"https://api.telegram.org/bot{token}/getMe"
                elif provider == "jupiter":
                    url = "https://quote-api.jup.ag/v6/health"
                elif provider == "helius":
                    key = os.getenv("HELIUS_API_KEY", "")
                    url = f"https://mainnet.helius-rpc.com/?api-key={key}" if key else "https://mainnet.helius-rpc.com"
                else:
                    return HealthStatus.UNKNOWN

                async with session.get(url) as response:
                    if response.status == 200:
                        return HealthStatus.HEALTHY
                    elif response.status == 429:
                        return HealthStatus.RATE_LIMITED
                    else:
                        return HealthStatus.DEGRADED

        except asyncio.TimeoutError:
            return HealthStatus.TIMEOUT
        except Exception as e:
            logger.warning(f"API check failed for {provider}: {e}")
            return HealthStatus.ERROR

    async def check_database(self) -> HealthStatus:
        """
        Check database connectivity.

        Returns:
            HealthStatus enum value
        """
        try:
            import sqlite3

            # Check common database locations
            db_paths = [
                Path("data/jarvis.db"),
                Path("data/health.db"),
                Path("/root/clawdbots/data/jarvis.db"),
            ]

            for db_path in db_paths:
                if db_path.exists():
                    conn = sqlite3.connect(str(db_path), timeout=5)
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
                    conn.close()
                    return HealthStatus.HEALTHY

            return HealthStatus.DEGRADED

        except Exception as e:
            logger.warning(f"Database check failed: {e}")
            return HealthStatus.ERROR

    async def check_disk(self) -> HealthStatus:
        """
        Check disk space availability.

        Returns:
            HealthStatus enum value
        """
        try:
            import psutil

            usage = psutil.disk_usage("/")
            percent_used = usage.percent
            free_gb = usage.free / (1024 ** 3)

            if free_gb < 1.0:  # Less than 1GB free
                return HealthStatus.CRITICAL
            elif percent_used > 90:
                return HealthStatus.WARNING
            elif percent_used > 80:
                return HealthStatus.DEGRADED
            else:
                return HealthStatus.HEALTHY

        except ImportError:
            return HealthStatus.UNKNOWN
        except Exception as e:
            logger.warning(f"Disk check failed: {e}")
            return HealthStatus.ERROR

    async def check_memory(self) -> HealthStatus:
        """
        Check system memory availability.

        Returns:
            HealthStatus enum value
        """
        try:
            import psutil

            mem = psutil.virtual_memory()
            free_mb = mem.available / (1024 ** 2)
            percent_used = mem.percent

            if free_mb < 500:  # Less than 500MB free
                return HealthStatus.CRITICAL
            elif percent_used > 90:
                return HealthStatus.WARNING
            elif percent_used > 80:
                return HealthStatus.DEGRADED
            else:
                return HealthStatus.HEALTHY

        except ImportError:
            return HealthStatus.UNKNOWN
        except Exception as e:
            logger.warning(f"Memory check failed: {e}")
            return HealthStatus.ERROR

    async def run_all_checks(self) -> Dict[str, HealthStatus]:
        """
        Run all health checks.

        Returns:
            Dictionary mapping check names to HealthStatus
        """
        results = {}

        # Check each bot
        for bot_name in self.bot_names:
            results[f"bot_{bot_name}"] = await self.check_bot(bot_name)

        # Check APIs
        for provider in ["telegram", "jupiter"]:
            results[f"api_{provider}"] = await self.check_api(provider)

        # System checks
        results["database"] = await self.check_database()
        results["disk"] = await self.check_disk()
        results["memory"] = await self.check_memory()

        return results

    async def run(self) -> Dict[str, Any]:
        """
        Run comprehensive health check and return results.

        Returns:
            Dictionary with all check results
        """
        start_time = time.time()

        # Run individual check groups
        processes = await self._check_processes()
        endpoints = await self._check_endpoints()
        logs = await self._check_logs()
        memory = await self._check_memory()
        apis = await self._check_apis()

        duration_ms = (time.time() - start_time) * 1000

        # Determine overall status
        all_checks = {
            **processes,
            **endpoints,
            **logs,
            **memory,
            **apis,
        }
        overall_status = determine_overall_status(all_checks)

        # Calculate summary
        summary = {"healthy": 0, "degraded": 0, "critical": 0, "total": 0}
        for info in all_checks.values():
            status = info.get("status", "unknown")
            summary["total"] += 1
            if status in ("healthy", "running", "available"):
                summary["healthy"] += 1
            elif status in ("degraded", "warning"):
                summary["degraded"] += 1
            elif status in ("critical", "unhealthy", "error", "not_running"):
                summary["critical"] += 1

        return {
            "overall_status": overall_status,
            "processes": processes,
            "endpoints": endpoints,
            "logs": logs,
            "memory": memory,
            "api_quotas": apis,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "duration_ms": duration_ms,
            "summary": summary,
        }

    async def _check_processes(self) -> Dict[str, Dict[str, Any]]:
        """Check all bot processes."""
        from scripts.health_check import check_bot_process

        results = {}
        for bot_name in self.bot_names:
            results[bot_name] = check_bot_process(bot_name)
        return results

    async def _check_endpoints(self) -> Dict[str, Dict[str, Any]]:
        """Check health endpoints."""
        from scripts.health_check import check_bot_response

        results = {}
        # Add any health endpoints to check
        endpoints = {
            "api_server": "http://localhost:8765/api/stats",
        }

        for name, url in endpoints.items():
            try:
                results[name] = await check_bot_response(name, url)
            except Exception as e:
                results[name] = {"status": "error", "error": str(e)}

        return results

    async def _check_logs(self) -> Dict[str, Dict[str, Any]]:
        """Check log files for errors."""
        from scripts.health_check import check_log_errors

        results = {}
        for bot_name in self.bot_names:
            results[bot_name] = check_log_errors(
                bot_name,
                log_dir=str(self.log_dir),
                minutes=60
            )
        return results

    async def _check_memory(self) -> Dict[str, Dict[str, Any]]:
        """Check memory usage."""
        from scripts.health_check import check_memory_usage

        results = {}
        for bot_name in self.bot_names:
            results[bot_name] = check_memory_usage(bot_name)
        return results

    async def _check_apis(self) -> Dict[str, Dict[str, Any]]:
        """Check API quotas."""
        from scripts.health_check import check_api_quotas

        return await check_api_quotas()
