"""
Telegram Sync for JARVIS Twitter Posts

Automatically pushes tweets to Telegram when JARVIS posts on X.
"""

import os
import logging
import asyncio
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Load environment variables
try:
    from dotenv import load_dotenv
    # Try twitter .env first, then tg_bot .env
    twitter_env = Path(__file__).parent / ".env"
    tg_env = Path(__file__).parent.parent.parent / "tg_bot" / ".env"

    if twitter_env.exists():
        load_dotenv(twitter_env, override=False)
    if tg_env.exists():
        load_dotenv(tg_env, override=False)
except ImportError:
    pass


class TelegramSync:
    """Syncs JARVIS tweets to Telegram channel."""

    def __init__(
        self,
        bot_token: Optional[str] = None,
        channel_id: Optional[str] = None
    ):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.channel_id = channel_id or os.getenv("TELEGRAM_ANNOUNCEMENTS_CHANNEL") or os.getenv("TELEGRAM_BUY_BOT_CHAT_ID")
        self._enabled = bool(self.bot_token and self.channel_id)

        if not self._enabled:
            logger.warning("Telegram sync disabled - missing TELEGRAM_BOT_TOKEN or channel ID")

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def push_tweet(
        self,
        tweet_text: str,
        tweet_url: str,
        username: str = "Jarvis_lifeos"
    ) -> bool:
        """
        Push a tweet to Telegram channel.

        Args:
            tweet_text: The tweet content
            tweet_url: URL to the tweet
            username: Twitter username

        Returns:
            True if sent successfully
        """
        if not self._enabled:
            logger.debug("Telegram sync disabled, skipping push")
            return False

        try:
            import aiohttp

            # Format message for Telegram
            message = self._format_message(tweet_text, tweet_url, username)

            # Send via Telegram Bot API
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.channel_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": False
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        logger.info(f"Tweet synced to Telegram: {tweet_url}")
                        return True
                    else:
                        error = await resp.text()
                        logger.error(f"Telegram sync failed ({resp.status}): {error}")
                        return False

        except ImportError:
            # Fallback to requests if aiohttp not available
            try:
                import requests
                message = self._format_message(tweet_text, tweet_url, username)
                url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
                payload = {
                    "chat_id": self.channel_id,
                    "text": message,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": False
                }
                resp = requests.post(url, json=payload)
                if resp.status_code == 200:
                    logger.info(f"Tweet synced to Telegram: {tweet_url}")
                    return True
                else:
                    logger.error(f"Telegram sync failed: {resp.text}")
                    return False
            except Exception as e:
                logger.error(f"Telegram sync error: {e}")
                return False
        except Exception as e:
            logger.error(f"Telegram sync error: {e}")
            return False

    def _format_message(self, tweet_text: str, tweet_url: str, username: str) -> str:
        """Format tweet for Telegram."""
        return f"""<b>🐦 New Post from @{username}</b>

{tweet_text}

<a href="{tweet_url}">View on X →</a>"""

    def push_tweet_sync(
        self,
        tweet_text: str,
        tweet_url: str,
        username: str = "Jarvis_lifeos"
    ) -> bool:
        """Synchronous version of push_tweet."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're already in an async context, create a task
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run,
                        self.push_tweet(tweet_text, tweet_url, username)
                    )
                    return future.result(timeout=10)
            else:
                return loop.run_until_complete(
                    self.push_tweet(tweet_text, tweet_url, username)
                )
        except Exception as e:
            logger.error(f"Sync push failed: {e}")
            return False


# Singleton instance
_telegram_sync: Optional[TelegramSync] = None


def get_telegram_sync() -> TelegramSync:
    """Get singleton TelegramSync instance."""
    global _telegram_sync
    if _telegram_sync is None:
        _telegram_sync = TelegramSync()
    return _telegram_sync


async def sync_tweet_to_telegram(
    tweet_text: str,
    tweet_url: str,
    username: str = "Jarvis_lifeos"
) -> bool:
    """Convenience function to sync a tweet to Telegram."""
    sync = get_telegram_sync()
    return await sync.push_tweet(tweet_text, tweet_url, username)
