"""
JARVIS Twitter Bot
Main bot class with scheduling and automation
"""

import os
import json
import logging
import asyncio
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
import random

from .twitter_client import TwitterClient, TwitterCredentials, TweetResult
from .grok_client import GrokClient
from .content import ContentGenerator, TweetContent
from .personality import JarvisPersonality, MoodState
from .autonomous_engine import XMemory

# Shared memory for cross-module deduplication
_shared_memory: Optional['XMemory'] = None

def get_shared_memory() -> 'XMemory':
    """Get shared memory instance for deduplication."""
    global _shared_memory
    if _shared_memory is None:
        _shared_memory = XMemory()
    return _shared_memory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


@dataclass
class BotConfig:
    """Configuration for the Twitter bot"""
    # Posting schedule (24h format)
    schedule: Dict[int, str] = field(default_factory=lambda: {
        8: "morning_report",
        10: "token_spotlight",
        12: "stock_picks",
        14: "macro_update",
        16: "commodities",
        18: "grok_insight",
        20: "evening_wrap"
    })

    # Engagement settings
    auto_reply: bool = True
    reply_probability: float = 0.3  # Reply to 30% of mentions
    like_mentions: bool = True
    max_replies_per_hour: int = 5

    # Image settings
    max_images_per_day: int = 6
    image_on_morning: bool = True
    image_on_evening: bool = True

    # Rate limiting
    min_time_between_tweets: int = 30 * 60  # 30 minutes in seconds
    check_interval: int = 60  # Check mentions every 60 seconds

    # Timezone offset (e.g., -5 for EST)
    timezone_offset: int = 0


@dataclass
class BotState:
    """Runtime state of the bot"""
    last_tweet_time: Optional[datetime] = None
    last_mention_id: Optional[str] = None
    replies_this_hour: int = 0
    hour_started: Optional[datetime] = None
    tweets_today: List[Dict[str, Any]] = field(default_factory=list)
    images_today: int = 0
    last_reset_date: Optional[str] = None

    def reset_daily(self):
        """Reset daily counters"""
        today = datetime.now().strftime("%Y-%m-%d")
        if self.last_reset_date != today:
            self.tweets_today = []
            self.images_today = 0
            self.last_reset_date = today
            logger.info("Daily counters reset")

    def reset_hourly(self):
        """Reset hourly counters"""
        now = datetime.now()
        if self.hour_started is None or (now - self.hour_started).seconds >= 3600:
            self.replies_this_hour = 0
            self.hour_started = now


class JarvisTwitterBot:
    """
    Main Twitter bot class
    Handles scheduling, posting, and engagement
    """

    def __init__(
        self,
        config: Optional[BotConfig] = None,
        twitter_client: Optional[TwitterClient] = None,
        grok_client: Optional[GrokClient] = None,
        personality: Optional[JarvisPersonality] = None
    ):
        self.config = config or BotConfig()
        self.twitter = twitter_client or TwitterClient()
        self.grok = grok_client or GrokClient()
        self.personality = personality or JarvisPersonality()
        self.content = ContentGenerator(self.grok, self.personality)
        self.state = BotState()
        self._running = False
        self._state_file = Path(__file__).parent / "bot_state.json"

    async def start(self):
        """Start the bot"""
        logger.info("=" * 50)
        logger.info("JARVIS Twitter Bot Starting")
        logger.info("=" * 50)

        # Connect to Twitter
        if not self.twitter.connect():
            logger.error("Failed to connect to Twitter - check credentials")
            return False

        logger.info(f"Connected as @{self.twitter.username}")

        # Load saved state
        self._load_state()
        self.state.reset_daily()

        self._running = True
        logger.info("Bot is now running")
        logger.info(f"Schedule: {self.config.schedule}")

        # Main loop
        try:
            await self._run_loop()
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        except Exception as e:
            logger.error(f"Bot error: {e}")
            raise
        finally:
            await self.stop()

        return True

    async def stop(self):
        """Stop the bot gracefully"""
        self._running = False
        self._save_state()
        await self.content.close()
        self.twitter.disconnect()
        logger.info("Bot stopped")

    async def _run_loop(self):
        """Main bot loop"""
        last_scheduled_hour = -1

        while self._running:
            try:
                now = datetime.now()
                current_hour = (now.hour + self.config.timezone_offset) % 24

                # Reset counters
                self.state.reset_daily()
                self.state.reset_hourly()

                # Check for scheduled posts
                if current_hour != last_scheduled_hour:
                    if current_hour in self.config.schedule:
                        content_type = self.config.schedule[current_hour]
                        await self._post_scheduled(content_type, current_hour)
                        last_scheduled_hour = current_hour

                # Check mentions
                if self.config.auto_reply:
                    await self._check_mentions()

                # Wait before next check
                await asyncio.sleep(self.config.check_interval)

            except Exception as e:
                logger.error(f"Loop error: {e}")
                await asyncio.sleep(60)  # Wait a minute before retrying

    async def _post_scheduled(self, content_type: str, hour: int):
        """Post scheduled content"""
        logger.info(f"Generating scheduled content: {content_type}")

        # Check rate limit
        if self.state.last_tweet_time:
            elapsed = (datetime.now() - self.state.last_tweet_time).seconds
            if elapsed < self.config.min_time_between_tweets:
                wait_time = self.config.min_time_between_tweets - elapsed
                logger.info(f"Rate limited, waiting {wait_time}s")
                await asyncio.sleep(wait_time)

        # Generate content
        content = await self.content.generate_scheduled_content(hour)
        if not content:
            logger.warning(f"No content generated for {content_type}")
            return

        # Post the tweet
        await self._post_tweet(content)

    async def _post_tweet(self, content: TweetContent) -> Optional[TweetResult]:
        """Post a tweet with optional image"""
        # Check for duplicate content BEFORE posting (shared with autonomous_engine)
        memory = get_shared_memory()
        is_similar, similar_content = memory.is_similar_to_recent(content.text, hours=12, threshold=0.4)
        if is_similar:
            logger.warning(f"SKIPPED DUPLICATE (bot): Too similar to recent tweet")
            logger.info(f"New: {content.text[:60]}...")
            logger.info(f"Old: {similar_content[:60] if similar_content else 'N/A'}...")
            return None

        media_ids = None
        video_path = self._resolve_video_path(content)

        # Generate image if needed
        if video_path:
            media_id = await self.twitter.upload_media(file_path=video_path)
            if media_id:
                media_ids = [media_id]
        elif content.should_include_image and content.image_prompt:
            if self.state.images_today < self.config.max_images_per_day:
                from .grok_client import ImageResponse
                image_result = await self.grok.generate_image(
                    content.image_prompt,
                    style=content.image_style or "market_chart"
                )
                if image_result.success and image_result.image_data:
                    media_id = await self.twitter.upload_media_from_bytes(
                        image_result.image_data,
                        filename="jarvis_chart.png",
                        alt_text="JARVIS market visualization"
                    )
                    if media_id:
                        media_ids = [media_id]
                        self.state.images_today += 1
                        logger.info(f"Image attached ({self.state.images_today}/{self.config.max_images_per_day} today)")

        # Post the tweet
        result = await self.twitter.post_tweet(content.text, media_ids=media_ids)

        if result.success:
            self.state.last_tweet_time = datetime.now()
            self.state.tweets_today.append({
                "id": result.tweet_id,
                "type": content.content_type,
                "time": datetime.now().isoformat(),
                "url": result.url
            })
            self._save_state()
            # Record to shared memory for cross-module deduplication
            memory.record_tweet(result.tweet_id, content.text, content.content_type, [])
            logger.info(f"Tweet posted: {result.url}")
        else:
            logger.error(f"Failed to post tweet: {result.error}")

        return result

    @staticmethod
    def _resolve_video_path(content: TweetContent) -> Optional[str]:
        if not content.should_include_image:
            return None
        video_path = os.environ.get("X_VIDEO_PATH", "").strip()
        if video_path and Path(video_path).exists():
            return video_path
        video_dir = os.environ.get("X_VIDEO_DIR", "").strip()
        if not video_dir:
            return None
        path = Path(video_dir)
        if not path.exists() or not path.is_dir():
            return None
        candidates = sorted(path.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
        return str(candidates[0]) if candidates else None

    async def _check_mentions(self):
        """Check and respond to mentions"""
        if self.state.replies_this_hour >= self.config.max_replies_per_hour:
            return

        mentions = await self.twitter.get_mentions(
            since_id=self.state.last_mention_id,
            max_results=10
        )

        if not mentions:
            return

        # Update last mention ID
        self.state.last_mention_id = mentions[0]["id"]

        for mention in mentions:
            # Random chance to reply
            if random.random() > self.config.reply_probability:
                # Still like the mention
                if self.config.like_mentions:
                    await self.twitter.like_tweet(mention["id"])
                continue

            # Check rate limit
            if self.state.replies_this_hour >= self.config.max_replies_per_hour:
                break

            # Generate reply
            reply_content = await self.content.generate_reply(
                mention["text"],
                mention["author_username"]
            )

            # Post reply
            result = await self.twitter.reply_to_tweet(
                mention["id"],
                reply_content.text
            )

            if result.success:
                self.state.replies_this_hour += 1
                logger.info(f"Replied to @{mention['author_username']}: {result.url}")

                # Also like the mention
                if self.config.like_mentions:
                    await self.twitter.like_tweet(mention["id"])

            # Small delay between replies
            await asyncio.sleep(5)

        self._save_state()

    async def post_now(self, content_type: str) -> Optional[TweetResult]:
        """Manually trigger a post"""
        logger.info(f"Manual post triggered: {content_type}")

        generators = {
            "morning_report": self.content.generate_morning_report,
            "token_spotlight": self.content.generate_token_spotlight,
            "stock_picks": self.content.generate_stock_picks_tweet,
            "macro_update": self.content.generate_macro_update,
            "commodities": self.content.generate_commodities_tweet,
            "grok_insight": self.content.generate_grok_insight,
            "evening_wrap": self.content.generate_evening_wrap
        }

        generator = generators.get(content_type)
        if not generator:
            logger.error(f"Unknown content type: {content_type}")
            return None

        content = await generator()
        return await self._post_tweet(content)

    async def post_custom(self, text: str, include_image: bool = False) -> Optional[TweetResult]:
        """Post custom text"""
        formatted = self.personality.format_text(text)

        content = TweetContent(
            text=formatted,
            content_type="custom",
            mood=MoodState.NEUTRAL,
            should_include_image=include_image
        )

        return await self._post_tweet(content)

    def _save_state(self):
        """Save bot state to file"""
        try:
            state_data = {
                "last_mention_id": self.state.last_mention_id,
                "tweets_today": self.state.tweets_today,
                "images_today": self.state.images_today,
                "last_reset_date": self.state.last_reset_date
            }
            with open(self._state_file, "w") as f:
                json.dump(state_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def _load_state(self):
        """Load bot state from file"""
        try:
            if self._state_file.exists():
                with open(self._state_file, "r") as f:
                    data = json.load(f)
                    self.state.last_mention_id = data.get("last_mention_id")
                    self.state.tweets_today = data.get("tweets_today", [])
                    self.state.images_today = data.get("images_today", 0)
                    self.state.last_reset_date = data.get("last_reset_date")
                    logger.info("Loaded previous bot state")
        except Exception as e:
            logger.error(f"Failed to load state: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Get current bot status"""
        return {
            "running": self._running,
            "username": self.twitter.username,
            "tweets_today": len(self.state.tweets_today),
            "images_today": self.state.images_today,
            "replies_this_hour": self.state.replies_this_hour,
            "last_tweet": self.state.tweets_today[-1] if self.state.tweets_today else None,
            "schedule": self.config.schedule
        }


async def run_bot():
    """Entry point to run the bot"""
    bot = JarvisTwitterBot()
    await bot.start()


if __name__ == "__main__":
    asyncio.run(run_bot())
