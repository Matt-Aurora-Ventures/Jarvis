"""
Telegram Polling Coordinator

Solves the multi-bot polling conflict by managing a single polling instance
that distributes updates to multiple bot handlers.

Architecture:
- One process polls Telegram API (prevents 409 conflict)
- Updates are distributed to registered handlers via internal queue
- Each bot registers its own handler for specific commands/filters
"""

import asyncio
import logging
from typing import Dict, List, Callable, Optional, Any
from dataclasses import dataclass, field
from telegram.ext import Application, ContextTypes, MessageHandler, CommandHandler, CallbackQueryHandler
from telegram import Update, Bot
import os

logger = logging.getLogger(__name__)


@dataclass
class BotHandlerRegistration:
    """Registration for a bot handler."""
    bot_name: str
    token: str
    command_handlers: Dict[str, Callable] = field(default_factory=dict)
    callback_handlers: List[Callable] = field(default_factory=list)
    message_handlers: List[Callable] = field(default_factory=list)
    initialized: bool = False


class TelegramPollingCoordinator:
    """
    Coordinates Telegram polling for multiple bots sharing the same token.

    Usage:
        coordinator = TelegramPollingCoordinator(token)
        coordinator.register_bot("treasury_bot", treasury_handlers)
        coordinator.register_bot("demo_bot", demo_handlers)
        await coordinator.start()
    """

    def __init__(self, token: str):
        self.token = token
        self.app: Optional[Application] = None
        self.bot: Optional[Bot] = None
        self.registrations: Dict[str, BotHandlerRegistration] = {}
        self._running = False
        self._lock = None

    async def initialize(self) -> bool:
        """Initialize the Telegram application."""
        try:
            # Acquire polling lock
            try:
                from core.utils.instance_lock import acquire_instance_lock, cleanup_stale_lock
                cleanup_stale_lock(self.token, name="telegram_polling")
                self._lock = acquire_instance_lock(
                    self.token,
                    name="telegram_polling",
                    max_wait_seconds=30,
                    validate_pid=True,
                )
                if not self._lock:
                    logger.error("Cannot acquire Telegram polling lock - another instance running")
                    return False
            except Exception as exc:
                logger.warning(f"Polling lock unavailable: {exc}")
                self._lock = None

            # Create application
            self.app = Application.builder().token(self.token).build()
            self.bot = self.app.bot

            # Initialize application
            await self.app.initialize()
            await self.app.start()

            logger.info("Telegram polling coordinator initialized")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize coordinator: {e}", exc_info=True)
            if self._lock:
                self._lock.close()
            return False

    def register_bot(
        self,
        bot_name: str,
        command_handlers: Optional[Dict[str, Callable]] = None,
        callback_handlers: Optional[List[Callable]] = None,
        message_handlers: Optional[List[Callable]] = None,
    ):
        """
        Register a bot's handlers.

        Args:
            bot_name: Unique name for the bot
            command_handlers: Dict of command -> handler function
            callback_handlers: List of callback query handlers
            message_handlers: List of message handlers
        """
        registration = BotHandlerRegistration(
            bot_name=bot_name,
            token=self.token,
            command_handlers=command_handlers or {},
            callback_handlers=callback_handlers or [],
            message_handlers=message_handlers or [],
        )

        self.registrations[bot_name] = registration
        logger.info(f"Registered bot: {bot_name}")

        # If already initialized, install handlers now
        if self.app:
            self._install_bot_handlers(registration)

    def _install_bot_handlers(self, registration: BotHandlerRegistration):
        """Install handlers for a registered bot."""
        if not self.app or registration.initialized:
            return

        try:
            # Add command handlers
            for command, handler in registration.command_handlers.items():
                self.app.add_handler(CommandHandler(command, handler))
                logger.debug(f"[{registration.bot_name}] Registered command: /{command}")

            # Add callback handlers
            for handler in registration.callback_handlers:
                self.app.add_handler(CallbackQueryHandler(handler))
                logger.debug(f"[{registration.bot_name}] Registered callback handler")

            # Add message handlers
            for handler in registration.message_handlers:
                from telegram.ext import filters
                self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handler))
                logger.debug(f"[{registration.bot_name}] Registered message handler")

            registration.initialized = True
            logger.info(f"[{registration.bot_name}] Handlers installed")

        except Exception as e:
            logger.error(f"Failed to install handlers for {registration.bot_name}: {e}")

    async def start(self):
        """Start polling and distribute updates."""
        if not self.app:
            raise RuntimeError("Coordinator not initialized")

        # Install all registered handlers
        for registration in self.registrations.values():
            if not registration.initialized:
                self._install_bot_handlers(registration)

        self._running = True
        logger.info("Starting Telegram polling...")

        try:
            # Start polling
            await self.app.updater.start_polling(drop_pending_updates=True)
            logger.info("✅ Telegram polling started")

            # Keep running
            while self._running:
                await asyncio.sleep(5)

        except Exception as e:
            logger.error(f"Polling error: {e}", exc_info=True)
            raise
        finally:
            await self.stop()

    async def stop(self):
        """Stop polling and cleanup."""
        self._running = False

        if self.app:
            try:
                await self.app.updater.stop()
                await self.app.stop()
                await self.app.shutdown()
            except Exception as e:
                logger.error(f"Error stopping app: {e}")

        if self._lock:
            try:
                self._lock.close()
            except Exception:
                pass

        logger.info("Telegram polling coordinator stopped")


# Global coordinator instance
_coordinator: Optional[TelegramPollingCoordinator] = None


def get_telegram_coordinator(token: Optional[str] = None) -> TelegramPollingCoordinator:
    """
    Get or create the global Telegram polling coordinator.

    Args:
        token: Telegram bot token (required on first call)

    Returns:
        TelegramPollingCoordinator instance
    """
    global _coordinator

    if _coordinator is None:
        if not token:
            token = os.environ.get("TELEGRAM_BOT_TOKEN")
            if not token:
                raise ValueError("No Telegram token provided and TELEGRAM_BOT_TOKEN not set")
        _coordinator = TelegramPollingCoordinator(token)

    return _coordinator
