"""
Example of creating a shutdown-aware service.

This demonstrates best practices for graceful shutdown:
- Database connection cleanup
- Background task cancellation
- State persistence
- Signal handling
"""

import asyncio
import logging
from typing import Optional

from core.shutdown_manager import (
    ShutdownAwareService,
    DatabaseShutdownMixin,
    TaskManagerMixin,
    get_shutdown_manager,
)
from core.db_connection_manager import get_db_manager

logger = logging.getLogger(__name__)


class TradingBotService(DatabaseShutdownMixin, TaskManagerMixin, ShutdownAwareService):
    """
    Example trading bot with graceful shutdown.

    Features:
    - Database connection management
    - Background price monitoring
    - State persistence on shutdown
    - Clean task cancellation
    """

    def __init__(self, db_url: str):
        super().__init__(name="trading_bot")
        self.db_url = db_url
        self.db_connection: Optional[object] = None
        self.positions = {}
        self.price_monitor_task: Optional[asyncio.Task] = None

    async def _startup(self):
        """Initialize resources."""
        logger.info("Starting trading bot...")

        # 1. Connect to database
        await self._connect_database()

        # 2. Load saved state
        await self._load_state()

        # 3. Start background tasks
        self.price_monitor_task = self.create_task(
            self._monitor_prices(),
            name="price_monitor"
        )

        logger.info("Trading bot started successfully")

    async def _shutdown(self):
        """Clean shutdown sequence."""
        logger.info("Shutting down trading bot...")

        # 1. Stop accepting new trades
        logger.info("Stopping new trade acceptance...")

        # 2. Cancel background tasks
        logger.info("Cancelling background tasks...")
        await self._cancel_background_tasks(timeout=5.0)

        # 3. Save current state
        logger.info("Saving state...")
        await self._save_state()

        # 4. Close database connections
        logger.info("Closing database connections...")
        await self._close_db_connections()

        logger.info("Trading bot shutdown complete")

    async def _connect_database(self):
        """Connect to database and register for cleanup."""
        # Example: Create a database connection
        # In real implementation, use asyncpg, aiosqlite, etc.

        class MockConnection:
            async def close(self):
                logger.info("Database connection closed")

            async def execute(self, query: str):
                pass

        self.db_connection = MockConnection()

        # Register with database manager for automatic cleanup
        db_manager = get_db_manager()
        db_manager.register_connection("trading_bot_db", self.db_connection)

        # Also register locally for our own cleanup
        self.register_db_connection(self.db_connection)

        logger.info("Database connected")

    async def _load_state(self):
        """Load saved positions and state from database."""
        if not self.db_connection:
            return

        # Example: Load positions
        # positions = await self.db_connection.fetch("SELECT * FROM positions")
        # self.positions = {p['symbol']: p for p in positions}

        logger.info(f"Loaded {len(self.positions)} positions from database")

    async def _save_state(self):
        """Save current positions and state to database."""
        if not self.db_connection:
            logger.warning("No database connection, cannot save state")
            return

        try:
            # Example: Save positions
            # for symbol, position in self.positions.items():
            #     await self.db_connection.execute(
            #         "INSERT INTO positions (...) VALUES (...)",
            #         position
            #     )

            logger.info(f"Saved {len(self.positions)} positions to database")

        except Exception as e:
            logger.error(f"Failed to save state: {e}", exc_info=True)

    async def _monitor_prices(self):
        """Background task to monitor prices."""
        logger.info("Price monitoring started")

        try:
            while True:
                # Example: Fetch and update prices
                # prices = await fetch_prices(self.positions.keys())
                # await self._update_positions(prices)

                await asyncio.sleep(1.0)

        except asyncio.CancelledError:
            logger.info("Price monitoring cancelled")
            raise

        except Exception as e:
            logger.error(f"Price monitoring error: {e}", exc_info=True)

    async def _update_positions(self, prices: dict):
        """Update positions with new prices."""
        for symbol, price in prices.items():
            if symbol in self.positions:
                self.positions[symbol]['current_price'] = price


async def main():
    """Example usage."""

    # 1. Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # 2. Create service
    bot = TradingBotService(db_url="postgresql://localhost/trading")

    # 3. Start service (registers shutdown hooks automatically)
    await bot.start()

    # 4. Install signal handlers
    shutdown_mgr = get_shutdown_manager()
    shutdown_mgr.install_signal_handlers()

    logger.info("Service running. Press Ctrl+C to shutdown gracefully...")

    # 5. Wait for shutdown signal
    await shutdown_mgr.wait_for_shutdown()

    # 6. Shutdown will happen automatically via hooks
    await shutdown_mgr.shutdown()

    logger.info("Goodbye!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown complete.")
