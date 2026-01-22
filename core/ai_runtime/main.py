"""
AI Runtime Main Entry Point

Can be run standalone or integrated with the supervisor.
"""
import asyncio
import logging
import signal
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    """Main entry point for standalone AI runtime."""
    from .integration import get_ai_runtime_manager

    manager = get_ai_runtime_manager()

    # Setup signal handlers
    loop = asyncio.get_event_loop()

    def signal_handler():
        logger.info("Received shutdown signal")
        asyncio.create_task(manager.stop())

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    # Start runtime
    logger.info("Starting AI Runtime...")
    started = await manager.start()

    if not started:
        logger.info("AI Runtime not started (disabled or unavailable)")
        return

    # Run forever
    try:
        logger.info("AI Runtime running. Press Ctrl+C to stop.")
        while manager.is_running:
            await asyncio.sleep(60)

            # Print status periodically
            supervisor = manager.get_supervisor()
            if supervisor:
                status = supervisor.get_status()
                logger.info(
                    f"Status: {status['insight_count']} insights, "
                    f"{status['pending_actions']} pending actions"
                )

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        await manager.stop()
        logger.info("AI Runtime stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown complete.")
