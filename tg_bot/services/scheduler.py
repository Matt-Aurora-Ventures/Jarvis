"""
Scheduler for hourly sentiment digests.

Pushes to:
1. Broadcast chat (main group) if configured
2. All individual subscribers
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Callable, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from tg_bot.services.claude_client import ClaudeClient
from tg_bot.services.token_data import TokenDataService
from tg_bot.models.subscriber import SubscriberDB

logger = logging.getLogger(__name__)


class DigestScheduler:
    """Scheduler for sending hourly digests to subscribers and broadcast chat."""

    def __init__(
        self,
        claude: ClaudeClient,
        token_service: TokenDataService,
        subscriber_db: SubscriberDB,
        send_message: Callable,
        hour: int = 14,
        minute: int = 0,
        broadcast_chat_id: Optional[int] = None,
    ):
        self.claude = claude
        self.token_service = token_service
        self.subscriber_db = subscriber_db
        self.send_message = send_message  # Async function to send telegram message
        self.hour = hour
        self.minute = minute
        self.scheduler: Optional[AsyncIOScheduler] = None

        # Broadcast chat - main group to push digests to
        self.broadcast_chat_id = broadcast_chat_id
        if not self.broadcast_chat_id:
            # Try to load from environment
            chat_id_str = os.getenv("TELEGRAM_BROADCAST_CHAT_ID") or os.getenv("TELEGRAM_BUY_BOT_CHAT_ID")
            if chat_id_str:
                try:
                    self.broadcast_chat_id = int(chat_id_str.strip())
                except ValueError:
                    pass

        if self.broadcast_chat_id:
            logger.info(f"Broadcast chat configured: {self.broadcast_chat_id}")

    def start(self):
        """Start the scheduler."""
        self.scheduler = AsyncIOScheduler()
        self.scheduler.add_job(
            self._send_digest,
            CronTrigger(hour=self.hour, minute=self.minute),
            id="hourly_digest",
            replace_existing=True,
        )
        self.scheduler.start()
        logger.info(f"Digest scheduler started (runs at {self.hour:02d}:{self.minute:02d} UTC)")

    def stop(self):
        """Stop the scheduler."""
        if self.scheduler:
            self.scheduler.shutdown()
            logger.info("Digest scheduler stopped")

    async def _send_digest(self):
        """Generate and send digest to all subscribers."""
        logger.info("Generating hourly digest...")

        try:
            # Get trending tokens
            tokens = await self.token_service.get_trending(limit=10)

            # Analyze sentiment for each
            analyzed = []
            for token in tokens:
                sentiment = await self.claude.analyze_sentiment(
                    token.symbol, token.to_dict()
                )
                analyzed.append((token, sentiment))

            # Sort by sentiment score
            analyzed.sort(key=lambda x: x[1].score, reverse=True)

            # Build digest message
            now = datetime.now(timezone.utc)
            message = f"""
*Jarvis Hourly Digest*
{now.strftime('%B %d, %Y')} | {now.strftime('%H:%M')} UTC

*Most Bullish:*
"""
            # Top 3 bullish
            for token, sentiment in analyzed[:3]:
                change = f"+{token.price_change_24h:.1f}" if token.price_change_24h >= 0 else f"{token.price_change_24h:.1f}"
                message += f"  {token.symbol} | {sentiment.score:.2f} | {change}%\n"

            message += "\n*Most Bearish:*\n"
            # Top 2 bearish
            for token, sentiment in analyzed[-2:]:
                change = f"+{token.price_change_24h:.1f}" if token.price_change_24h >= 0 else f"{token.price_change_24h:.1f}"
                message += f"  {token.symbol} | {sentiment.score:.2f} | {change}%\n"

            message += "\n_Reply /sentiment <token> for details._"

            # Send to broadcast chat FIRST (main group)
            if self.broadcast_chat_id:
                try:
                    await self.send_message(self.broadcast_chat_id, message, parse_mode="Markdown")
                    logger.info(f"Digest sent to broadcast chat {self.broadcast_chat_id}")
                except Exception as e:
                    logger.warning(f"Failed to send digest to broadcast chat: {e}")

            # Send to all subscribers
            subscribers = self.subscriber_db.get_active_subscribers()
            logger.info(f"Sending digest to {len(subscribers)} subscribers")

            for sub in subscribers:
                # Skip if this is the broadcast chat (avoid duplicate)
                if self.broadcast_chat_id and sub.chat_id == self.broadcast_chat_id:
                    continue
                try:
                    await self.send_message(sub.chat_id, message, parse_mode="Markdown")
                except Exception as e:
                    logger.warning(f"Failed to send digest to {sub.user_id}: {e}")

            logger.info("Hourly digest sent successfully")

        except Exception as e:
            logger.error(f"Failed to generate digest: {e}")

    async def send_test_digest(self, chat_id: int):
        """Send a test digest to a specific chat."""
        await self._send_digest()
        # Could send to specific chat for testing
