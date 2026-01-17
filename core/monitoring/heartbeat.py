"""
External Heartbeat Monitoring - Ping external services for uptime tracking.

Supports:
- Healthchecks.io (recommended, free tier: 20 checks)
- UptimeRobot (webhook endpoint)
- BetterStack (Uptime)
- Custom webhook endpoints

Usage:
    heartbeat = ExternalHeartbeat()
    await heartbeat.start()  # Runs in background

    # Or manual ping
    await heartbeat.ping()
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
import aiohttp

logger = logging.getLogger(__name__)


class ExternalHeartbeat:
    """
    Send periodic heartbeats to external monitoring services.

    Configure via environment variables:
    - HEALTHCHECKS_URL: Healthchecks.io ping URL (e.g., https://hc-ping.com/xxx)
    - BETTERSTACK_URL: BetterStack heartbeat URL
    - HEARTBEAT_WEBHOOK: Custom webhook URL
    - HEARTBEAT_INTERVAL: Ping interval in seconds (default: 60)
    """

    def __init__(
        self,
        interval: int = None,
        healthchecks_url: str = None,
        betterstack_url: str = None,
        custom_webhook: str = None,
    ):
        self.interval = interval or int(os.getenv("HEARTBEAT_INTERVAL", "60"))
        self.healthchecks_url = healthchecks_url or os.getenv("HEALTHCHECKS_URL")
        self.betterstack_url = betterstack_url or os.getenv("BETTERSTACK_URL")
        self.custom_webhook = custom_webhook or os.getenv("HEARTBEAT_WEBHOOK")

        self._session: Optional[aiohttp.ClientSession] = None
        self._task: Optional[asyncio.Task] = None
        self._running = False

        # Stats
        self.ping_count = 0
        self.last_ping: Optional[datetime] = None
        self.failures: List[Dict[str, Any]] = []

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10)
            )
        return self._session

    async def close(self):
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    def has_endpoints(self) -> bool:
        """Check if any heartbeat endpoints are configured."""
        return bool(
            self.healthchecks_url or
            self.betterstack_url or
            self.custom_webhook
        )

    async def ping(self, status: str = "ok", message: str = None) -> Dict[str, bool]:
        """
        Send heartbeat ping to all configured endpoints.

        Args:
            status: "ok" for success, "fail" for failure
            message: Optional status message

        Returns:
            Dict mapping endpoint name to success status
        """
        results = {}
        session = await self._get_session()

        # Healthchecks.io
        if self.healthchecks_url:
            url = self.healthchecks_url
            if status == "fail":
                url = f"{url}/fail"
            try:
                async with session.get(url) as resp:
                    results["healthchecks"] = resp.status == 200
            except Exception as e:
                logger.warning(f"Healthchecks ping failed: {e}")
                results["healthchecks"] = False

        # BetterStack
        if self.betterstack_url:
            try:
                async with session.get(self.betterstack_url) as resp:
                    results["betterstack"] = resp.status == 200
            except Exception as e:
                logger.warning(f"BetterStack ping failed: {e}")
                results["betterstack"] = False

        # Custom webhook (POST with JSON body)
        if self.custom_webhook:
            try:
                payload = {
                    "status": status,
                    "timestamp": datetime.utcnow().isoformat(),
                    "message": message or "Jarvis heartbeat",
                    "ping_count": self.ping_count,
                }
                async with session.post(self.custom_webhook, json=payload) as resp:
                    results["custom"] = resp.status in (200, 201, 204)
            except Exception as e:
                logger.warning(f"Custom webhook ping failed: {e}")
                results["custom"] = False

        # Update stats
        self.ping_count += 1
        self.last_ping = datetime.now()

        if not all(results.values()):
            self.failures.append({
                "timestamp": datetime.now(),
                "results": results,
            })
            # Keep only last 100 failures
            self.failures = self.failures[-100:]

        return results

    async def ping_start(self):
        """Send startup ping (services support /start endpoint)."""
        if self.healthchecks_url:
            try:
                session = await self._get_session()
                async with session.get(f"{self.healthchecks_url}/start") as resp:
                    logger.info(f"Healthchecks start ping: {resp.status}")
            except Exception as e:
                logger.warning(f"Start ping failed: {e}")

    async def _heartbeat_loop(self):
        """Main heartbeat loop."""
        logger.info(f"Heartbeat monitoring started (interval: {self.interval}s)")

        # Send startup ping
        await self.ping_start()

        while self._running:
            try:
                results = await self.ping()
                logger.debug(f"Heartbeat ping: {results}")
                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                await asyncio.sleep(self.interval)

    async def start(self) -> bool:
        """Start background heartbeat task."""
        if not self.has_endpoints():
            logger.info("No heartbeat endpoints configured, skipping")
            return False

        self._running = True
        self._task = asyncio.create_task(self._heartbeat_loop())
        return True

    async def stop(self):
        """Stop heartbeat task."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self.close()

    def get_status(self) -> Dict[str, Any]:
        """Get heartbeat status."""
        return {
            "running": self._running,
            "endpoints_configured": self.has_endpoints(),
            "interval": self.interval,
            "ping_count": self.ping_count,
            "last_ping": self.last_ping.isoformat() if self.last_ping else None,
            "recent_failures": len(self.failures),
        }


# Singleton instance
_heartbeat: Optional[ExternalHeartbeat] = None


def get_heartbeat() -> ExternalHeartbeat:
    """Get singleton heartbeat instance."""
    global _heartbeat
    if _heartbeat is None:
        _heartbeat = ExternalHeartbeat()
    return _heartbeat
