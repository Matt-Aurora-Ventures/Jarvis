"""
Graceful shutdown handler for Telegram bot.

Ensures:
- Pending updates are processed
- Active commands complete
- State is saved
- Bot stops polling cleanly
"""

import asyncio
import logging
from typing import Optional

try:
    from telegram.ext import Application
except ImportError:
    Application = None

try:
    from core.shutdown_manager import get_shutdown_manager, ShutdownPhase
    SHUTDOWN_MANAGER_AVAILABLE = True
except ImportError:
    SHUTDOWN_MANAGER_AVAILABLE = False

logger = logging.getLogger(__name__)


class TelegramBotShutdownHandler:
    """
    Manages graceful shutdown for Telegram bot.

    Usage:
        app = Application.builder().token(token).build()
        shutdown_handler = TelegramBotShutdownHandler(app)
        shutdown_handler.register()
    """

    def __init__(self, application: Optional[Application] = None):
        self.application = application
        self._is_shutting_down = False
        self._pending_updates = 0

    def register(self):
        """Register shutdown hooks with the global shutdown manager."""
        if not SHUTDOWN_MANAGER_AVAILABLE:
            logger.warning("Shutdown manager not available - Telegram bot shutdown may be abrupt")
            return

        if not self.application:
            logger.warning("No Telegram application provided - cannot register shutdown hooks")
            return

        shutdown_mgr = get_shutdown_manager()

        # Phase 1: Stop accepting new updates
        shutdown_mgr.register_hook(
            name="telegram_bot_stop_polling",
            callback=self._stop_polling,
            phase=ShutdownPhase.IMMEDIATE,
            timeout=5.0,
            priority=90,
        )

        # Phase 2: Wait for in-flight updates to complete
        shutdown_mgr.register_hook(
            name="telegram_bot_drain_updates",
            callback=self._drain_updates,
            phase=ShutdownPhase.GRACEFUL,
            timeout=10.0,
        )

        # Phase 3: Save state
        shutdown_mgr.register_hook(
            name="telegram_bot_save_state",
            callback=self._save_state,
            phase=ShutdownPhase.PERSIST,
            timeout=5.0,
        )

        # Phase 4: Final cleanup
        shutdown_mgr.register_hook(
            name="telegram_bot_cleanup",
            callback=self._cleanup,
            phase=ShutdownPhase.CLEANUP,
            timeout=5.0,
        )

        logger.info("Telegram bot shutdown handlers registered")

    async def _stop_polling(self):
        """Stop accepting new updates."""
        if not self.application:
            return

        logger.info("Stopping Telegram bot polling...")
        self._is_shutting_down = True

        try:
            # Stop the updater if it's running
            if self.application.updater and self.application.updater.running:
                await self.application.updater.stop()
                logger.info("Updater stopped")
        except Exception as e:
            logger.error(f"Error stopping updater: {e}")

    async def _drain_updates(self):
        """Wait for in-flight updates to complete."""
        if not self.application:
            return

        logger.info("Draining pending updates...")

        # Wait for update queue to empty (with timeout)
        max_wait = 10
        waited = 0

        while waited < max_wait:
            # Check if there are pending updates
            if hasattr(self.application, 'update_queue'):
                queue_size = self.application.update_queue.qsize()
                if queue_size == 0:
                    logger.info("All updates processed")
                    break

                logger.debug(f"Waiting for {queue_size} updates to complete...")

            await asyncio.sleep(0.5)
            waited += 0.5

        if waited >= max_wait:
            logger.warning(f"Timed out waiting for updates to drain after {max_wait}s")

    async def _save_state(self):
        """Save bot state before shutdown."""
        logger.info("Saving Telegram bot state...")

        # Save persistence data if configured
        if self.application and hasattr(self.application, 'persistence'):
            if self.application.persistence:
                try:
                    await self.application.persistence.flush()
                    logger.info("Persistence data flushed")
                except Exception as e:
                    logger.error(f"Failed to flush persistence: {e}")

        # Save any other state here (e.g., active trades, user sessions)
        # This is a placeholder for application-specific state saving
        try:
            await self._save_application_state()
        except Exception as e:
            logger.error(f"Failed to save application state: {e}")

    async def _save_application_state(self):
        """Save application-specific state. Override this in subclass."""
        # Example: Save active trading positions
        # Example: Save user session data
        # Example: Save pending notifications
        pass

    async def _cleanup(self):
        """Final cleanup."""
        if not self.application:
            return

        logger.info("Telegram bot final cleanup...")

        try:
            # Stop the application
            if self.application.running:
                await self.application.stop()
                logger.info("Application stopped")

            # Shutdown the application
            await self.application.shutdown()
            logger.info("Application shutdown complete")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


def setup_telegram_shutdown(application: Application):
    """
    Convenience function to set up Telegram bot shutdown handling.

    Usage:
        app = Application.builder().token(token).build()
        setup_telegram_shutdown(app)
    """
    handler = TelegramBotShutdownHandler(application)
    handler.register()
    return handler
