"""
Telegram Plugin for LifeOS.

Wraps the telegram_sentiment_bot integration as a plugin with:
- PAE Providers: Message history, bot status
- PAE Actions: Send message, broadcast report, add/remove chat
- Event integration for notifications
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from lifeos.plugins.base import Plugin

logger = logging.getLogger(__name__)


class SendMessageAction:
    """Action to send a Telegram message."""

    name = "telegram.send_message"
    description = "Send a message to a Telegram chat"
    requires_confirmation = False

    def __init__(self, plugin_id: str, config: Dict[str, Any]):
        self._plugin_id = plugin_id
        self._config = config
        self._bot = None

    def set_bot(self, bot) -> None:
        """Set the bot instance."""
        self._bot = bot

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the send message action."""
        chat_id = params.get("chat_id")
        message = params.get("message")

        if not message:
            raise ValueError("message is required")

        if not self._bot:
            return {
                "success": False,
                "error": "Bot not initialized",
            }

        # If no chat_id, broadcast to all configured chats
        if chat_id:
            success = await self._bot.send_message(chat_id, message)
            return {
                "success": success,
                "chat_id": chat_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        else:
            # Broadcast to all
            chat_ids = self._bot.config.get("chat_ids", [])
            sent = 0
            for cid in chat_ids:
                if await self._bot.send_message(cid, message):
                    sent += 1
            return {
                "success": sent > 0,
                "sent_count": sent,
                "total_chats": len(chat_ids),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }


class BroadcastReportAction:
    """Action to broadcast a sentiment report."""

    name = "telegram.broadcast_report"
    description = "Broadcast sentiment report to all configured chats"
    requires_confirmation = False

    def __init__(self, plugin_id: str, config: Dict[str, Any]):
        self._plugin_id = plugin_id
        self._config = config
        self._bot = None

    def set_bot(self, bot) -> None:
        """Set the bot instance."""
        self._bot = bot

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the broadcast action."""
        if not self._bot:
            return {
                "success": False,
                "error": "Bot not initialized",
            }

        try:
            count = await self._bot.broadcast_report()
            return {
                "success": count > 0,
                "sent_count": count,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }


class ManageChatAction:
    """Action to add/remove chat IDs."""

    name = "telegram.manage_chat"
    description = "Add or remove chat IDs from broadcast list"
    requires_confirmation = True

    def __init__(self, plugin_id: str, config: Dict[str, Any]):
        self._plugin_id = plugin_id
        self._config = config
        self._bot = None

    def set_bot(self, bot) -> None:
        """Set the bot instance."""
        self._bot = bot

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute chat management action."""
        action = params.get("action")  # "add" or "remove"
        chat_id = params.get("chat_id")

        if not action or not chat_id:
            raise ValueError("action and chat_id are required")

        if not self._bot:
            return {
                "success": False,
                "error": "Bot not initialized",
            }

        if action == "add":
            self._bot.add_chat_id(int(chat_id))
            return {
                "success": True,
                "action": "added",
                "chat_id": chat_id,
            }
        elif action == "remove":
            self._bot.remove_chat_id(int(chat_id))
            return {
                "success": True,
                "action": "removed",
                "chat_id": chat_id,
            }
        else:
            raise ValueError(f"Unknown action: {action}")


class BotStatusProvider:
    """Provider for bot status information."""

    name = "telegram.status"
    description = "Get Telegram bot status"

    def __init__(self, plugin_id: str, config: Dict[str, Any]):
        self._plugin_id = plugin_id
        self._config = config
        self._bot = None

    def set_bot(self, bot) -> None:
        """Set the bot instance."""
        self._bot = bot

    async def provide(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """Provide bot status."""
        if not self._bot:
            return {
                "initialized": False,
                "error": "Bot not initialized",
            }

        return {
            "initialized": True,
            "has_token": self._bot.token is not None,
            "chat_count": len(self._bot.config.get("chat_ids", [])),
            "scheduler_running": self._bot._running,
            "schedule_enabled": self._bot.config.get("schedule", {}).get("enabled", False),
            "schedule_times": self._bot.config.get("schedule", {}).get("times", []),
            "tokens": self._bot.config.get("tokens", []),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


class TelegramPlugin(Plugin):
    """
    Telegram integration plugin.

    Provides:
    - Automated sentiment reports via Telegram
    - Manual message sending
    - Chat management
    - Event-driven notifications
    """

    def __init__(self, context, manifest):
        super().__init__(context, manifest)
        self._bot = None
        self._actions: List[Any] = []
        self._providers: List[Any] = []
        self._event_subscriptions: List[str] = []

    async def on_load(self) -> None:
        """Initialize the plugin."""
        logger.info("Loading Telegram plugin")

        # Try to import the existing bot
        try:
            from core.integrations.telegram_sentiment_bot import TelegramSentimentBot
            self._bot = TelegramSentimentBot()
            logger.info("Telegram bot initialized")
        except ImportError:
            logger.warning("telegram_sentiment_bot not available, using mock mode")
            self._bot = None

        # Get plugin config
        config = self._context.config if self._context else {}

        # Create PAE components
        self._actions = [
            SendMessageAction(self._manifest.name, config),
            BroadcastReportAction(self._manifest.name, config),
            ManageChatAction(self._manifest.name, config),
        ]

        self._providers = [
            BotStatusProvider(self._manifest.name, config),
        ]

        # Set bot instance on all components
        for action in self._actions:
            action.set_bot(self._bot)
        for provider in self._providers:
            provider.set_bot(self._bot)

        # Register with PAE if available
        if self._context and "jarvis" in self._context.services:
            jarvis = self._context.services["jarvis"]
            if hasattr(jarvis, "pae"):
                for action in self._actions:
                    jarvis.pae.register_action(action)
                for provider in self._providers:
                    jarvis.pae.register_provider(provider)
                logger.info("Registered Telegram PAE components")

    async def on_enable(self) -> None:
        """Enable the plugin and start scheduler."""
        logger.info("Enabling Telegram plugin")

        # Start scheduler if bot is available and schedule is enabled
        if self._bot:
            schedule_enabled = self._bot.config.get("schedule", {}).get("enabled", False)
            if schedule_enabled:
                self._bot.start_scheduler()
                logger.info("Telegram scheduler started")

        # Subscribe to notification events
        if self._context and "event_bus" in self._context.services:
            event_bus = self._context.services["event_bus"]

            # Subscribe to notification events
            @event_bus.on("notification.telegram")
            async def handle_notification(event):
                if self._bot:
                    message = event.data.get("message", "")
                    chat_id = event.data.get("chat_id")
                    if message:
                        if chat_id:
                            await self._bot.send_message(chat_id, message)
                        else:
                            for cid in self._bot.config.get("chat_ids", []):
                                await self._bot.send_message(cid, message)

            self._event_subscriptions.append("notification.telegram")

            # Emit enabled event
            await event_bus.emit("telegram.enabled", {
                "has_token": self._bot.token is not None if self._bot else False,
            })

    async def on_disable(self) -> None:
        """Disable the plugin and stop scheduler."""
        logger.info("Disabling Telegram plugin")

        if self._bot:
            self._bot.stop_scheduler()

        # Emit disabled event
        if self._context and "event_bus" in self._context.services:
            await self._context.services["event_bus"].emit("telegram.disabled")

    async def on_unload(self) -> None:
        """Clean up plugin resources."""
        logger.info("Unloading Telegram plugin")

        # Stop scheduler if running
        if self._bot and self._bot._running:
            self._bot.stop_scheduler()

        self._bot = None
        self._actions.clear()
        self._providers.clear()

    # Public API methods

    async def send_message(self, chat_id: int, message: str) -> bool:
        """Send a message to a specific chat."""
        if not self._bot:
            return False
        return await self._bot.send_message(chat_id, message)

    async def broadcast(self, message: str) -> int:
        """Broadcast a message to all configured chats."""
        if not self._bot:
            return 0

        count = 0
        for chat_id in self._bot.config.get("chat_ids", []):
            if await self._bot.send_message(chat_id, message):
                count += 1
        return count

    async def send_report(self) -> int:
        """Send sentiment report to all chats."""
        if not self._bot:
            return 0
        return await self._bot.broadcast_report()

    def add_chat(self, chat_id: int) -> None:
        """Add a chat ID to broadcasts."""
        if self._bot:
            self._bot.add_chat_id(chat_id)

    def remove_chat(self, chat_id: int) -> None:
        """Remove a chat ID from broadcasts."""
        if self._bot:
            self._bot.remove_chat_id(chat_id)

    def get_status(self) -> Dict[str, Any]:
        """Get current bot status."""
        if not self._bot:
            return {"initialized": False}

        return {
            "initialized": True,
            "has_token": self._bot.token is not None,
            "chat_count": len(self._bot.config.get("chat_ids", [])),
            "scheduler_running": self._bot._running,
        }
