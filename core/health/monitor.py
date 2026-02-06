"""
Health Monitor Module

Provides the HealthMonitor class for monitoring bot health with:
- Bot registration
- Individual and bulk health checks
- Continuous monitoring with configurable intervals
- Status change callbacks
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, List, Optional

from .status import HealthStatus

logger = logging.getLogger("jarvis.health.monitor")


@dataclass
class BotStatus:
    """Status of a single bot."""
    name: str
    status: HealthStatus
    message: str = ""
    latency_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_ok(self) -> bool:
        """Check if status indicates healthy state."""
        return self.status in (HealthStatus.HEALTHY, HealthStatus.AVAILABLE)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "latency_ms": self.latency_ms,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


# Type alias for health check functions
HealthCheckFn = Callable[[], Coroutine[Any, Any, Dict[str, Any]]]

# Type alias for status change callbacks
StatusChangeCallback = Callable[[str, Optional[HealthStatus], HealthStatus], None]


class HealthMonitor:
    """
    Monitor health of registered bots.

    Provides:
    - Bot registration with custom health check functions
    - Individual bot health checking
    - Bulk health checking (all bots)
    - Continuous monitoring with configurable interval
    - Optional status change callbacks

    Usage:
        monitor = HealthMonitor(check_interval=60)

        async def check_telegram():
            # Your check logic
            return {"status": "healthy", "latency_ms": 10}

        monitor.register_bot("telegram_bot", check_telegram)
        await monitor.start_monitoring()
    """

    def __init__(
        self,
        check_interval: int = 60,
        check_timeout: float = 30.0,
        on_status_change: Optional[StatusChangeCallback] = None,
    ):
        """
        Initialize HealthMonitor.

        Args:
            check_interval: Seconds between health checks (default 60)
            check_timeout: Timeout for individual health checks in seconds (default 30)
            on_status_change: Optional callback when bot status changes
        """
        self._check_interval = check_interval
        self._check_timeout = check_timeout
        self._on_status_change = on_status_change

        self._bots: Dict[str, Dict[str, Any]] = {}
        self._monitoring_task: Optional[asyncio.Task] = None
        self._running = False

    def register_bot(self, name: str, check_fn: HealthCheckFn) -> None:
        """
        Register a bot for health monitoring.

        Args:
            name: Unique name for the bot
            check_fn: Async function that returns health check result dict
                      Expected keys: status, message (optional), latency_ms (optional)
        """
        self._bots[name] = {
            "check_fn": check_fn,
            "last_check": None,
            "last_status": None,
        }
        logger.debug(f"Registered bot for health monitoring: {name}")

    def unregister_bot(self, name: str) -> None:
        """
        Unregister a bot from health monitoring.

        Args:
            name: Name of the bot to unregister
        """
        if name in self._bots:
            del self._bots[name]
            logger.debug(f"Unregistered bot from health monitoring: {name}")

    def get_registered_bots(self) -> List[str]:
        """
        Get list of registered bot names.

        Returns:
            List of bot names
        """
        return list(self._bots.keys())

    async def check_bot(self, name: str) -> BotStatus:
        """
        Check health of a specific bot.

        Args:
            name: Name of the bot to check

        Returns:
            BotStatus with health information
        """
        if name not in self._bots:
            return BotStatus(
                name=name,
                status=HealthStatus.UNKNOWN,
                message=f"Bot '{name}' not registered",
            )

        bot_info = self._bots[name]
        check_fn = bot_info["check_fn"]
        start_time = time.monotonic()

        try:
            # Run check with timeout
            result = await asyncio.wait_for(
                check_fn(),
                timeout=self._check_timeout
            )

            latency_ms = (time.monotonic() - start_time) * 1000

            # Parse result
            status_str = result.get("status", "unknown")
            status = self._parse_status(status_str)
            message = result.get("message", "")
            details = {k: v for k, v in result.items() if k not in ("status", "message", "latency_ms")}

            # Use provided latency if available
            if "latency_ms" in result:
                latency_ms = result["latency_ms"]

            bot_status = BotStatus(
                name=name,
                status=status,
                message=message,
                latency_ms=latency_ms,
                details=details,
            )

        except asyncio.TimeoutError:
            latency_ms = self._check_timeout * 1000
            bot_status = BotStatus(
                name=name,
                status=HealthStatus.TIMEOUT,
                message=f"Health check timed out after {self._check_timeout}s",
                latency_ms=latency_ms,
            )
            logger.warning(f"Health check timeout for {name}")

        except Exception as e:
            latency_ms = (time.monotonic() - start_time) * 1000
            bot_status = BotStatus(
                name=name,
                status=HealthStatus.ERROR,
                message=str(e),
                latency_ms=latency_ms,
            )
            logger.error(f"Health check error for {name}: {e}")

        # Update state
        old_status = bot_info.get("last_status")
        bot_info["last_check"] = datetime.now(timezone.utc)
        bot_info["last_status"] = bot_status.status

        # Trigger callback if status changed
        if self._on_status_change and old_status != bot_status.status:
            try:
                self._on_status_change(name, old_status, bot_status.status)
            except Exception as e:
                logger.error(f"Status change callback error: {e}")

        return bot_status

    async def check_all(self) -> Dict[str, BotStatus]:
        """
        Check health of all registered bots concurrently.

        Returns:
            Dictionary mapping bot names to BotStatus
        """
        if not self._bots:
            return {}

        # Run all checks concurrently
        tasks = {
            name: asyncio.create_task(self.check_bot(name))
            for name in self._bots
        }

        results = {}
        for name, task in tasks.items():
            try:
                results[name] = await task
            except Exception as e:
                logger.error(f"Error checking {name}: {e}")
                results[name] = BotStatus(
                    name=name,
                    status=HealthStatus.ERROR,
                    message=str(e),
                )

        return results

    async def start_monitoring(self, interval: Optional[int] = None) -> None:
        """
        Start continuous health monitoring.

        Args:
            interval: Optional override for check interval
        """
        if self._running:
            logger.debug("Monitoring already running")
            return

        self._running = True
        check_interval = interval or self._check_interval

        logger.info(f"Starting health monitoring (interval: {check_interval}s)")

        self._monitoring_task = asyncio.create_task(
            self._monitoring_loop(check_interval)
        )

    async def stop_monitoring(self) -> None:
        """Stop continuous health monitoring."""
        if not self._running:
            return

        self._running = False

        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None

        logger.info("Health monitoring stopped")

    async def _monitoring_loop(self, interval: int) -> None:
        """Internal monitoring loop."""
        while self._running:
            try:
                await self.check_all()
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")

            try:
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break

    def _parse_status(self, status_str: str) -> HealthStatus:
        """Parse status string to HealthStatus enum."""
        status_map = {
            "healthy": HealthStatus.HEALTHY,
            "available": HealthStatus.AVAILABLE,
            "degraded": HealthStatus.DEGRADED,
            "unhealthy": HealthStatus.UNHEALTHY,
            "warning": HealthStatus.WARNING,
            "critical": HealthStatus.CRITICAL,
            "error": HealthStatus.ERROR,
            "timeout": HealthStatus.TIMEOUT,
            "not_running": HealthStatus.NOT_RUNNING,
            "not_configured": HealthStatus.NOT_CONFIGURED,
            "rate_limited": HealthStatus.RATE_LIMITED,
        }
        return status_map.get(status_str.lower(), HealthStatus.UNKNOWN)

    # Async context manager support
    async def __aenter__(self) -> "HealthMonitor":
        """Enter async context."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context, stopping monitoring."""
        await self.stop_monitoring()
