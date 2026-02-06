"""
Unified Bot Lifecycle Manager for ClawdBots.

Wraps heartbeat (TelegramHeartbeat) and self-healing (ProcessWatchdog)
into a single lifecycle object that bots can initialize with minimal code.

Usage:
    from bots.shared.bot_lifecycle import BotLifecycle

    lifecycle = BotLifecycle(bot_name="ClawdJarvis", bot_token=BOT_TOKEN)
    lifecycle.start()

    # In message handlers:
    lifecycle.record_message()
    lifecycle.record_api_cost(0.002)

    # On shutdown:
    lifecycle.shutdown()
"""

import logging
from typing import Optional

from bots.shared.heartbeat import TelegramHeartbeat, start_heartbeat_thread
from bots.shared.self_healing import SelfHealingConfig, ProcessWatchdog

logger = logging.getLogger(__name__)


class BotLifecycle:
    """Unified lifecycle for ClawdBot instances.

    Combines heartbeat monitoring and self-healing watchdog into
    a single manager that bots wire up at startup.
    """

    def __init__(
        self,
        bot_name: str,
        bot_token: str,
        admin_chat_id: Optional[int] = None,
        heartbeat_interval_hours: float = 6.0,
        memory_threshold_mb: int = 256,
    ):
        """Initialize lifecycle with heartbeat and self-healing.

        Args:
            bot_name: Display name for the bot
            bot_token: Telegram bot token (for heartbeat messages)
            admin_chat_id: Chat ID for heartbeat/alert messages
            heartbeat_interval_hours: Hours between heartbeat messages
            memory_threshold_mb: Memory threshold for watchdog alerts
        """
        self.bot_name = bot_name
        self.bot_token = bot_token
        self.running = False

        # Create heartbeat
        self.heartbeat = TelegramHeartbeat(
            bot_token=bot_token,
            chat_id=admin_chat_id,
            bot_name=bot_name,
            interval_hours=heartbeat_interval_hours,
        )

        # Create self-healing watchdog
        config = SelfHealingConfig(
            bot_name=bot_name.lower(),
            memory_threshold_mb=memory_threshold_mb,
        )
        self.watchdog = ProcessWatchdog(config)

        # Wire watchdog alerts to heartbeat emergency alerts
        self.watchdog.on_alert(self._on_watchdog_alert)

    def _on_watchdog_alert(self, alert_type: str, details: dict) -> None:
        """Forward watchdog alerts as emergency heartbeat messages."""
        msg = f"[{alert_type}] {details}"
        logger.warning(f"Watchdog alert for {self.bot_name}: {msg}")

    def start(self) -> None:
        """Start heartbeat and watchdog background threads."""
        if self.running:
            return

        self.running = True

        # Start heartbeat thread
        start_heartbeat_thread(self.heartbeat)
        logger.info(f"[{self.bot_name}] Heartbeat started")

        # Start watchdog
        self.watchdog.start()
        logger.info(f"[{self.bot_name}] Watchdog started")

    def shutdown(self) -> None:
        """Gracefully stop heartbeat and watchdog."""
        if not self.running:
            return

        self.running = False

        try:
            self.heartbeat.stop()
        except Exception as e:
            logger.warning(f"Error stopping heartbeat: {e}")

        try:
            self.watchdog.stop()
        except Exception as e:
            logger.warning(f"Error stopping watchdog: {e}")

        logger.info(f"[{self.bot_name}] Lifecycle shutdown complete")

    def record_message(self) -> None:
        """Record a processed message (proxies to heartbeat)."""
        self.heartbeat.record_message()

    def record_api_cost(self, cost_usd: float) -> None:
        """Record API cost (proxies to heartbeat)."""
        self.heartbeat.record_api_cost(cost_usd)
