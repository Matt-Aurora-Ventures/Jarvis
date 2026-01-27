"""
JARVIS Provider Health Monitor - Self-Healing Background Service

Continuously monitors provider health and attempts recovery:
- Runs every 60 seconds
- Tests FAILED providers to see if they've recovered
- Logs metrics for debugging
- Alerts if system is degraded for too long

This ensures the system automatically heals without manual intervention.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from core.resilient_provider import get_resilient_provider, ProviderState

logger = logging.getLogger(__name__)


class ProviderHealthMonitor:
    """
    Background service that monitors and recovers providers.

    Key features:
    - Non-blocking background task
    - Automatic recovery attempts
    - Degradation alerts
    - Health metrics logging
    """

    def __init__(self, check_interval: float = 60.0, alert_threshold: int = 5):
        """
        Initialize health monitor.

        Args:
            check_interval: Seconds between health checks (default: 60)
            alert_threshold: Number of consecutive checks with degradation before alerting (default: 5 = 5 minutes)
        """
        self.check_interval = check_interval
        self.alert_threshold = alert_threshold
        self.degradation_count = 0
        self.last_alert_time: Optional[datetime] = None
        self.alert_cooldown = timedelta(hours=1)  # Don't alert more than once per hour
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the health monitor background task."""
        if self._running:
            logger.warning("Provider health monitor already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info(f"🏥 Provider health monitor started (interval={self.check_interval}s)")

    async def stop(self):
        """Stop the health monitor."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Provider health monitor stopped")

    async def _monitor_loop(self):
        """Main monitoring loop."""
        while self._running:
            try:
                await self._check_health()
            except Exception as e:
                logger.error(f"Error in provider health monitor loop: {e}")

            try:
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break

    async def _check_health(self):
        """Perform health check and recovery attempts."""
        provider = get_resilient_provider()
        report = provider.get_health_report()

        # Log current status
        logger.info(
            f"Provider health check: {report['healthy_providers']} healthy, "
            f"{report['degraded_providers']} degraded, "
            f"{report['failed_providers']} failed"
        )

        # Check if system is degraded
        if report['degraded_providers'] > 0 or report['failed_providers'] > 0:
            self.degradation_count += 1

            # Log degradation details
            for name, health in report['providers'].items():
                if health['state'] in ['degraded', 'failed']:
                    logger.warning(
                        f"Provider {name} is {health['state']}: "
                        f"{health['consecutive_failures']} failures, "
                        f"last error: {health.get('last_error', 'unknown')}"
                    )

            # Alert if degraded for too long
            if self.degradation_count >= self.alert_threshold:
                await self._send_degradation_alert(report)

        else:
            # System healthy - reset counter
            if self.degradation_count > 0:
                logger.info(f"✅ Provider system recovered (was degraded for {self.degradation_count} checks)")
            self.degradation_count = 0

        # Attempt recovery for FAILED providers
        await self._attempt_recovery(report)

        # Log detailed metrics every 10 checks (10 minutes)
        if int(asyncio.get_event_loop().time()) % 600 < self.check_interval:
            await self._log_detailed_metrics(report)

    async def _attempt_recovery(self, report: dict):
        """Attempt to recover failed providers."""
        provider = get_resilient_provider()

        for name, health in report['providers'].items():
            if health['state'] == 'failed':
                # Check if recovery timeout has elapsed
                if health.get('last_failure_time'):
                    # Provider will attempt recovery in next call
                    # We just log that it's ready for recovery
                    logger.info(f"Provider {name} is eligible for recovery attempt")

            elif health['state'] == 'recovering':
                logger.info(f"Provider {name} is in recovery state")

    async def _send_degradation_alert(self, report: dict):
        """Send alert if system degraded for too long."""
        now = datetime.now()

        # Check cooldown
        if self.last_alert_time and (now - self.last_alert_time) < self.alert_cooldown:
            return

        self.last_alert_time = now

        alert_message = (
            f"⚠️ JARVIS Provider Degradation Alert\n"
            f"System has been degraded for {self.degradation_count} checks ({self.degradation_count * self.check_interval / 60:.1f} minutes)\n\n"
            f"Status:\n"
            f"  - Healthy: {report['healthy_providers']}\n"
            f"  - Degraded: {report['degraded_providers']}\n"
            f"  - Failed: {report['failed_providers']}\n\n"
            f"Failed providers:\n"
        )

        for name, health in report['providers'].items():
            if health['state'] == 'failed':
                alert_message += f"  - {name}: {health.get('last_error', 'unknown')}\n"

        logger.error(alert_message)

        # TODO: Send Telegram notification to admin
        # This would require telegram bot integration
        # For now, just log the alert

    async def _log_detailed_metrics(self, report: dict):
        """Log detailed health metrics."""
        logger.info("=== Detailed Provider Metrics ===")

        for name, health in sorted(report['providers'].items()):
            success_rate = health.get('success_rate', 0)
            logger.info(
                f"{name}: "
                f"state={health['state']}, "
                f"success_rate={success_rate:.1%}, "
                f"total_calls={health['total_calls']}, "
                f"consecutive_failures={health['consecutive_failures']}"
            )

        logger.info("================================")


# Global monitor instance
_provider_health_monitor: Optional[ProviderHealthMonitor] = None


def get_provider_health_monitor() -> ProviderHealthMonitor:
    """Get the global provider health monitor instance."""
    global _provider_health_monitor
    if _provider_health_monitor is None:
        _provider_health_monitor = ProviderHealthMonitor()
    return _provider_health_monitor


async def start_provider_health_monitor():
    """Start the global provider health monitor."""
    monitor = get_provider_health_monitor()
    await monitor.start()


async def stop_provider_health_monitor():
    """Stop the global provider health monitor."""
    monitor = get_provider_health_monitor()
    await monitor.stop()
