#!/usr/bin/env python
"""
Health Daemon

Background daemon that:
- Periodically checks health of all registered bots
- Sends alerts when status degrades
- Sends recovery notifications when status improves
- Optionally auto-restarts failed bots

Usage:
    python scripts/health_daemon.py
    python scripts/health_daemon.py --interval 30 --auto-restart
    python scripts/health_daemon.py -v --interval 60
"""

import argparse
import asyncio
import logging
import os
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.health.monitor import HealthMonitor, BotStatus
from core.health.reporter import HealthReporter
from core.health.status import HealthStatus
from core.health.checks import ProcessCheck, MemoryCheck, DiskCheck

logger = logging.getLogger("jarvis.health_daemon")


class HealthDaemon:
    """
    Background daemon for health monitoring.

    Features:
    - Periodic health checks
    - Alert on status degradation
    - Recovery notifications
    - Optional auto-restart
    """

    # Default bots to monitor
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
        check_interval: int = 60,
        auto_restart: bool = False,
        bots: Optional[list] = None,
    ):
        """
        Initialize HealthDaemon.

        Args:
            check_interval: Seconds between health checks
            auto_restart: Whether to auto-restart failed bots
            bots: List of bot names to monitor (uses defaults if None)
        """
        self.check_interval = check_interval
        self.auto_restart = auto_restart
        self.bots = bots or self.DEFAULT_BOTS

        self._running = False
        self._monitor: Optional[HealthMonitor] = None
        self._reporter: Optional[HealthReporter] = None

        # Track previous statuses for detecting changes
        self._previous_statuses: Dict[str, HealthStatus] = {}

    async def run(self) -> None:
        """Run the health daemon."""
        self._running = True

        # Initialize monitor and reporter
        self._monitor = HealthMonitor(
            check_interval=self.check_interval,
            on_status_change=self._on_status_change,
        )
        self._reporter = HealthReporter()

        # Register bots
        self._register_bots()

        # Start monitoring
        await self._monitor.start_monitoring()

        logger.info(f"Health daemon started (interval: {self.check_interval}s, auto-restart: {self.auto_restart})")

        # Main loop
        while self._running:
            try:
                # Check all bots
                statuses = await self._monitor.check_all()

                # Process results
                await self._process_statuses(statuses)

            except Exception as e:
                logger.error(f"Error in health daemon loop: {e}")

            # Wait for next check
            try:
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break

        # Cleanup
        await self._monitor.stop_monitoring()
        logger.info("Health daemon stopped")

    def stop(self) -> None:
        """Stop the daemon."""
        self._running = False

    def setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            self.stop()

        # Register handlers
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, signal_handler)
        if hasattr(signal, "SIGINT"):
            signal.signal(signal.SIGINT, signal_handler)

    def _register_bots(self) -> None:
        """Register bots for monitoring."""
        for bot_name in self.bots:
            check = ProcessCheck(bot_name)
            self._monitor.register_bot(bot_name, check.run)
            logger.debug(f"Registered bot: {bot_name}")

        # Also register system checks
        memory_check = MemoryCheck()
        disk_check = DiskCheck()

        self._monitor.register_bot("system_memory", memory_check.run)
        self._monitor.register_bot("system_disk", disk_check.run)

    async def _process_statuses(self, statuses: Dict[str, BotStatus]) -> None:
        """Process health check results."""
        for name, status in statuses.items():
            previous = self._previous_statuses.get(name)

            # Check for degradation
            if status.status.is_problematic:
                # New problem or continuing problem
                if previous is None or not previous.is_problematic:
                    # Status just became problematic
                    await self._reporter.send_alert(status)
                    logger.warning(f"Bot {name} is {status.status.value}: {status.message}")

                    # Auto-restart if configured and bot is not running
                    if self.auto_restart and status.status == HealthStatus.NOT_RUNNING:
                        await self._restart_bot(name)

            # Check for recovery
            elif previous is not None and previous.is_problematic:
                # Status recovered
                await self._reporter.send_recovery(status)
                logger.info(f"Bot {name} recovered: {status.status.value}")

            # Update previous status
            self._previous_statuses[name] = status.status

    def _on_status_change(
        self,
        bot_name: str,
        old_status: Optional[HealthStatus],
        new_status: HealthStatus,
    ) -> None:
        """Handle status change callback."""
        logger.info(
            f"Status change for {bot_name}: "
            f"{old_status.value if old_status else 'None'} -> {new_status.value}"
        )

    async def _restart_bot(self, bot_name: str) -> None:
        """
        Attempt to restart a bot.

        This is a placeholder - actual implementation depends on deployment.
        """
        logger.info(f"Attempting to restart bot: {bot_name}")

        # For systemd-based deployment on VPS
        if os.path.exists("/etc/systemd/system"):
            try:
                service_name = f"{bot_name}.service"
                subprocess.run(
                    ["systemctl", "restart", service_name],
                    check=True,
                    capture_output=True,
                )
                logger.info(f"Restarted systemd service: {service_name}")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to restart {service_name}: {e}")
            except FileNotFoundError:
                logger.warning("systemctl not available")
        else:
            logger.info(f"Auto-restart not implemented for bot: {bot_name}")


def parse_args(args=None) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="JARVIS Health Daemon - Monitor bot health continuously"
    )

    parser.add_argument(
        "--interval", "-i",
        type=int,
        default=60,
        help="Check interval in seconds (default: 60)",
    )

    parser.add_argument(
        "--auto-restart", "-r",
        action="store_true",
        help="Automatically restart failed bots",
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    parser.add_argument(
        "--bots", "-b",
        nargs="+",
        help="Specific bots to monitor (default: all)",
    )

    return parser.parse_args(args)


def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


async def main_async(args: argparse.Namespace) -> None:
    """Async main entry point."""
    daemon = HealthDaemon(
        check_interval=args.interval,
        auto_restart=args.auto_restart,
        bots=args.bots,
    )

    daemon.setup_signal_handlers()
    await daemon.run()


def main() -> None:
    """Main entry point."""
    args = parse_args()
    setup_logging(args.verbose)

    logger.info("Starting JARVIS Health Daemon")
    logger.info(f"  Interval: {args.interval}s")
    logger.info(f"  Auto-restart: {args.auto_restart}")

    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
