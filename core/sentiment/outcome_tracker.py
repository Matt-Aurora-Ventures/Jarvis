"""
Outcome Tracker - Background service that records prediction outcomes.

Runs continuously to:
1. Find predictions that are 24+ hours old without outcomes
2. Fetch current price data for those assets
3. Calculate actual price change
4. Record outcome in the sentiment database
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict
import logging
from pathlib import Path
import json

from .self_tuning import SelfTuningSentimentEngine

logger = logging.getLogger(__name__)


class OutcomeTracker:
    """Background service for tracking and recording prediction outcomes."""

    def __init__(self, sentiment_db: str = None, polling_interval: int = 300):
        """
        Initialize outcome tracker.

        Args:
            sentiment_db: Path to sentiment database
            polling_interval: Seconds between checks for pending outcomes
        """
        self.engine = SelfTuningSentimentEngine(sentiment_db)
        self.polling_interval = polling_interval
        self.is_running = False

    async def run(self):
        """Run outcome tracking loop indefinitely."""
        self.is_running = True
        logger.info("🚀 Outcome Tracker started")

        while self.is_running:
            try:
                await self._check_and_record_outcomes()
            except Exception as e:
                logger.error(f"Error in outcome tracking loop: {e}")

            # Wait before next check
            await asyncio.sleep(self.polling_interval)

    async def _check_and_record_outcomes(self):
        """Check for pending outcomes and record them."""
        pending = self.engine.get_pending_outcomes()

        if not pending:
            return

        logger.info(f"📊 Found {len(pending)} predictions awaiting outcomes")

        for prediction in pending:
            try:
                # Get current price for symbol
                current_price = await self._get_current_price(prediction.symbol)

                if current_price is None:
                    logger.warning(f"Could not fetch current price for {prediction.symbol}")
                    continue

                # Calculate actual price change
                entry_price = prediction.components.price_momentum  # Placeholder
                if entry_price > 0:
                    price_change_pct = ((current_price - entry_price) / entry_price) * 100
                else:
                    price_change_pct = 0

                # Record outcome
                self.engine.record_outcome(prediction.id, price_change_pct)

                outcome_str = "✅ WIN" if price_change_pct > 0 else "❌ LOSS" if price_change_pct < 0 else "⚪ NEUTRAL"
                logger.info(
                    f"{outcome_str} | {prediction.symbol}: {price_change_pct:+.2f}% | "
                    f"Grade: {prediction.sentiment_grade}"
                )

            except Exception as e:
                logger.error(f"Error recording outcome for {prediction.symbol}: {e}")

    async def _get_current_price(self, symbol: str) -> Optional[float]:
        """
        Fetch current price for a symbol.

        TODO: Integrate with actual price source (CoinGecko, Jupiter DEX, etc.)
        """
        # Placeholder - integrate with actual data source
        logger.debug(f"Fetching current price for {symbol}")
        return None

    def stop(self):
        """Stop the outcome tracking loop."""
        self.is_running = False
        logger.info("🛑 Outcome Tracker stopped")


async def run_outcome_tracker(
    sentiment_db: str = "./data/sentiment.db",
    polling_interval: int = 300,
):
    """
    Convenience function to run outcome tracker.

    Args:
        sentiment_db: Path to sentiment database
        polling_interval: Seconds between polls
    """
    tracker = OutcomeTracker(sentiment_db, polling_interval)
    try:
        await tracker.run()
    except KeyboardInterrupt:
        tracker.stop()


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Run tracker
    import sys
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(run_outcome_tracker())
