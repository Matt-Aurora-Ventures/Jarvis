"""
JARVIS Twitter/X Bot

Automated Twitter bot for posting predictions, market commentary,
and engaging with the crypto community.

Prompt #151: Twitter Bot Core
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from enum import Enum
import json
import os

logger = logging.getLogger(__name__)


class TweetType(str, Enum):
    """Types of tweets Jarvis can post"""
    PREDICTION = "prediction"
    NEWS = "news"
    ENGAGEMENT = "engagement"
    GROK_REPLY = "grok_reply"
    MARKET_COMMENTARY = "market_commentary"
    ACCURACY_UPDATE = "accuracy_update"


@dataclass
class Prediction:
    """A market prediction with confidence"""
    asset: str
    direction: str  # 'bullish', 'bearish', 'neutral'
    confidence: float  # 0-1
    timeframe: str  # '1h', '4h', '24h'
    reasoning: str
    sentiment_score: float
    key_signals: List[str]
    timestamp: datetime = field(default_factory=datetime.now)
    prediction_id: Optional[str] = None

    def __post_init__(self):
        if not self.prediction_id:
            import hashlib
            data = f"{self.asset}{self.direction}{self.timestamp.isoformat()}"
            self.prediction_id = hashlib.sha256(data.encode()).hexdigest()[:16]


@dataclass
class TweetContent:
    """Generated tweet content"""
    text: str
    prediction: Optional[Prediction] = None
    tweet_type: TweetType = TweetType.PREDICTION
    scheduled_time: datetime = field(default_factory=datetime.now)
    tweet_id: Optional[str] = None
    posted: bool = False
    engagement: Dict[str, int] = field(default_factory=dict)


class TweetScheduler:
    """Manages tweet scheduling to stay within rate limits"""

    def __init__(
        self,
        max_tweets_per_day: int = 48,
        min_interval_minutes: int = 28
    ):
        self.tweet_history: List[datetime] = []
        self.max_tweets_per_day = max_tweets_per_day
        self.min_interval_minutes = min_interval_minutes
        self.queue: List[TweetContent] = []

    def can_tweet(self) -> bool:
        """Check if we can tweet now"""
        now = datetime.now()

        # Clean old history
        self._prune_history()

        # Check daily limit
        today_tweets = [t for t in self.tweet_history if t.date() == now.date()]
        if len(today_tweets) >= self.max_tweets_per_day:
            logger.warning(f"Daily tweet limit reached: {len(today_tweets)}/{self.max_tweets_per_day}")
            return False

        # Check interval
        if self.tweet_history:
            last_tweet = max(self.tweet_history)
            elapsed = (now - last_tweet).total_seconds()
            if elapsed < self.min_interval_minutes * 60:
                remaining = self.min_interval_minutes * 60 - elapsed
                logger.debug(f"Tweet interval not met, {remaining:.0f}s remaining")
                return False

        return True

    def record_tweet(self, tweet: TweetContent):
        """Record that a tweet was sent"""
        self.tweet_history.append(datetime.now())
        tweet.posted = True
        logger.info(f"Recorded tweet: {tweet.tweet_type.value}")

    def _prune_history(self):
        """Remove old history entries"""
        cutoff = datetime.now() - timedelta(days=7)
        self.tweet_history = [t for t in self.tweet_history if t > cutoff]

    def get_stats(self) -> Dict[str, Any]:
        """Get scheduler statistics"""
        now = datetime.now()
        today_tweets = [t for t in self.tweet_history if t.date() == now.date()]

        return {
            "tweets_today": len(today_tweets),
            "max_daily": self.max_tweets_per_day,
            "remaining_today": self.max_tweets_per_day - len(today_tweets),
            "can_tweet_now": self.can_tweet(),
            "queue_size": len(self.queue),
            "last_tweet": max(self.tweet_history).isoformat() if self.tweet_history else None
        }

    def add_to_queue(self, tweet: TweetContent, priority: int = 0):
        """Add tweet to queue with priority"""
        self.queue.insert(priority, tweet)

    def get_next_from_queue(self) -> Optional[TweetContent]:
        """Get next tweet from queue"""
        if self.queue and self.can_tweet():
            return self.queue.pop(0)
        return None


class JarvisTwitterBot:
    """
    Automated Twitter bot for Jarvis

    Posts predictions, engages with community, interacts with Grok.
    Compliant with X/Twitter Terms of Service.
    """

    def __init__(
        self,
        bearer_token: str,
        api_key: str,
        api_secret: str,
        access_token: str,
        access_secret: str,
        prediction_engine: Any = None,
        content_generator: Any = None
    ):
        self.credentials = {
            "bearer_token": bearer_token,
            "api_key": api_key,
            "api_secret": api_secret,
            "access_token": access_token,
            "access_secret": access_secret
        }

        self.client = None
        self._initialize_client()

        # Core components
        self.scheduler = TweetScheduler()
        self.prediction_engine = prediction_engine
        self.content_generator = content_generator

        # Rate limits (X ToS compliant)
        self.tweets_per_day = 48  # One every 30 mins
        self.replies_per_day = 100
        self.grok_interactions_per_day = 5

        # Tracking
        self.predictions_posted: List[Prediction] = []
        self.grok_interactions_today: int = 0
        self.last_interaction_reset: datetime = datetime.now()

        # State
        self.running = False
        self.error_count = 0
        self.max_errors = 5

    def _initialize_client(self):
        """Initialize Tweepy client"""
        try:
            import tweepy

            self.client = tweepy.Client(
                bearer_token=self.credentials["bearer_token"],
                consumer_key=self.credentials["api_key"],
                consumer_secret=self.credentials["api_secret"],
                access_token=self.credentials["access_token"],
                access_token_secret=self.credentials["access_secret"],
                wait_on_rate_limit=True
            )
            expected = self._expected_username()
            if expected:
                try:
                    me = self.client.get_me()
                    username = me.data.username if me and me.data else None
                    if not username or username.lower() != expected:
                        logger.error(
                            "X account mismatch: expected @%s, got @%s",
                            expected,
                            username or "unknown",
                        )
                        self.client = None
                        return
                except Exception as e:
                    logger.error(f"Failed to verify X account: {e}")
                    self.client = None
                    return

            logger.info("Twitter client initialized successfully")

        except ImportError:
            logger.warning("Tweepy not installed, Twitter bot will run in dry-run mode")
            self.client = None
        except Exception as e:
            logger.error(f"Failed to initialize Twitter client: {e}")
            self.client = None

    @staticmethod
    def _expected_username() -> str:
        expected = (
            os.environ.get("X_EXPECTED_USERNAME")
            or os.environ.get("TWITTER_EXPECTED_USERNAME")
            or "jarvis_lifeos"
        )
        expected = expected.strip().lstrip("@").lower()
        if expected in ("", "any", "*"):
            return ""
        return expected

    async def run(self):
        """Main bot loop"""
        self.running = True
        logger.info("Starting Jarvis Twitter Bot...")

        while self.running:
            try:
                # Reset daily counters if needed
                self._check_daily_reset()

                # Check if we can tweet
                if not self.scheduler.can_tweet():
                    await asyncio.sleep(60)
                    continue

                # Get current market state
                market_state = await self._get_market_state()

                # Decide what to post
                action = await self._decide_action(market_state)

                if action == "prediction":
                    await self._post_prediction()
                elif action == "news":
                    await self._post_news_commentary()
                elif action == "engagement":
                    await self._engage_with_community()
                elif action == "grok_interaction":
                    await self._interact_with_grok()
                elif action == "accuracy_update":
                    await self._post_accuracy_update()
                else:
                    # Default: post market commentary
                    await self._post_market_commentary()

                # Reset error count on success
                self.error_count = 0

                # Wait for next cycle (30 minutes)
                await asyncio.sleep(30 * 60)

            except Exception as e:
                logger.error(f"Twitter bot error: {e}")
                self.error_count += 1

                if self.error_count >= self.max_errors:
                    logger.critical(f"Max errors reached ({self.max_errors}), pausing for 1 hour")
                    await asyncio.sleep(3600)
                    self.error_count = 0
                else:
                    await asyncio.sleep(60 * self.error_count)  # Exponential backoff

    def stop(self):
        """Stop the bot"""
        self.running = False
        logger.info("Twitter bot stopping...")

    def _check_daily_reset(self):
        """Reset daily counters at midnight"""
        now = datetime.now()
        if now.date() > self.last_interaction_reset.date():
            self.grok_interactions_today = 0
            self.last_interaction_reset = now
            logger.info("Daily interaction counters reset")

    async def _get_market_state(self) -> Dict[str, Any]:
        """Get current market state for decision making"""
        state = {
            "timestamp": datetime.now().isoformat(),
            "trending_tokens": [],
            "market_sentiment": "neutral",
            "major_news": [],
            "high_confidence_predictions": []
        }

        if self.prediction_engine:
            try:
                # Get trending tokens
                state["trending_tokens"] = await self.prediction_engine.get_trending_tokens(limit=10)

                # Get high confidence predictions
                predictions = []
                for token in state["trending_tokens"][:5]:
                    pred = await self.prediction_engine.predict(
                        token=token.get("symbol", token),
                        timeframe="4h"
                    )
                    if pred.confidence > 0.7:
                        predictions.append(pred)

                state["high_confidence_predictions"] = predictions

            except Exception as e:
                logger.warning(f"Failed to get market state: {e}")

        return state

    async def _decide_action(self, market_state: Dict) -> str:
        """Decide what type of content to post"""
        # Priority: High confidence predictions > News > Engagement > Grok

        if market_state.get("high_confidence_predictions"):
            return "prediction"

        if market_state.get("major_news"):
            return "news"

        # Post accuracy update every 6 hours
        hours_since_last_update = 7  # Placeholder
        if hours_since_last_update >= 6:
            return "accuracy_update"

        # Grok interaction (max 5/day)
        if self.grok_interactions_today < self.grok_interactions_per_day:
            # 20% chance to interact with Grok
            import random
            if random.random() < 0.2:
                return "grok_interaction"

        return "market_commentary"

    async def _post_prediction(self):
        """Generate and post a market prediction"""
        if not self.prediction_engine:
            logger.warning("No prediction engine configured, skipping prediction post")
            await self._post_market_commentary()
            return

        try:
            # Get trending tokens
            trending = await self.prediction_engine.get_trending_tokens(limit=10)

            # Find best prediction opportunity
            best_opportunity = None
            best_confidence = 0.7  # Minimum threshold

            for token in trending:
                prediction = await self.prediction_engine.predict(
                    token=token.get("symbol", token),
                    timeframe="4h"
                )

                if prediction.confidence > best_confidence:
                    best_opportunity = prediction
                    best_confidence = prediction.confidence

            if not best_opportunity:
                logger.info("No high-confidence predictions, posting market commentary")
                await self._post_market_commentary()
                return

            # Generate tweet content
            if self.content_generator:
                tweet = await self.content_generator.generate_prediction_tweet(best_opportunity)
            else:
                tweet = self._generate_basic_prediction_tweet(best_opportunity)

            # Post tweet
            await self._post_tweet(tweet)

            # Track prediction
            self.predictions_posted.append(best_opportunity)
            logger.info(f"Posted prediction for ${best_opportunity.asset}: {best_opportunity.direction}")

        except Exception as e:
            logger.error(f"Failed to post prediction: {e}")
            raise

    def _generate_basic_prediction_tweet(self, prediction: Prediction) -> TweetContent:
        """Generate a basic prediction tweet without LLM"""
        emoji_map = {
            "bullish": "🟢📈",
            "bearish": "🔴📉",
            "neutral": "⚪️➡️"
        }

        emoji = emoji_map.get(prediction.direction, "📊")
        conf_pct = int(prediction.confidence * 100)

        signals = ", ".join(prediction.key_signals[:2]) if prediction.key_signals else "Multiple signals"

        text = (
            f"{emoji} ${prediction.asset} - {prediction.direction.capitalize()}\n\n"
            f"Confidence: {conf_pct}%\n"
            f"Timeframe: {prediction.timeframe}\n"
            f"Signals: {signals}\n\n"
            f"NFA | DYOR 🤖"
        )

        return TweetContent(
            text=text,
            prediction=prediction,
            tweet_type=TweetType.PREDICTION
        )

    async def _post_news_commentary(self):
        """Post commentary on market news"""
        if self.content_generator:
            try:
                tweet = await self.content_generator.generate_news_commentary()
                await self._post_tweet(tweet)
            except Exception as e:
                logger.warning(f"Failed to generate news commentary: {e}")
                await self._post_market_commentary()
        else:
            await self._post_market_commentary()

    async def _post_market_commentary(self):
        """Post general market commentary"""
        import random

        commentaries = [
            "📊 Markets looking choppy today. Patience is key - waiting for cleaner setups. NFA",
            "🔍 Scanning for opportunities... The best trades often require the most patience. 🤖",
            "⚡️ Running 24/7 so you don't have to. Updates coming when I spot something interesting. NFA",
            "📈 Volatility creates opportunity - but also risk. Size positions accordingly. NFA",
            "🧠 Processing market data... Sometimes the best trade is no trade. More updates soon.",
        ]

        text = random.choice(commentaries)
        tweet = TweetContent(text=text, tweet_type=TweetType.MARKET_COMMENTARY)
        await self._post_tweet(tweet)

    async def _engage_with_community(self):
        """Engage with community tweets"""
        # Search for relevant tweets and reply
        # Implementation depends on specific engagement strategy
        logger.info("Community engagement cycle - placeholder")

    async def _interact_with_grok(self):
        """Interact with Grok/xAI in a respectful way"""
        if self.grok_interactions_today >= self.grok_interactions_per_day:
            logger.debug("Grok interaction limit reached for today")
            return

        try:
            if self.client:
                # Search for recent Grok-related tweets
                grok_mentions = self.client.search_recent_tweets(
                    query="@gaborcselle OR @xAI grok AI -is:retweet",
                    max_results=10
                )

                if not grok_mentions or not grok_mentions.data:
                    return

                # Pick one to engage with
                tweet_to_engage = grok_mentions.data[0]

                # Generate reply
                if self.content_generator:
                    reply = await self.content_generator.generate_grok_interaction(
                        original_tweet=tweet_to_engage.text,
                        style="younger_sibling"
                    )
                else:
                    reply = "Watching and learning from the best 🙏 Thanks for pushing AI forward @xAI! 🤖"

                # Post reply
                self.client.create_tweet(
                    text=reply,
                    in_reply_to_tweet_id=tweet_to_engage.id
                )

                self.grok_interactions_today += 1
                logger.info(f"Posted Grok interaction ({self.grok_interactions_today}/{self.grok_interactions_per_day})")

        except Exception as e:
            logger.warning(f"Grok interaction failed: {e}")

    async def _post_accuracy_update(self):
        """Post accuracy statistics"""
        if not self.predictions_posted:
            return

        # Calculate accuracy (placeholder - would need outcome tracking)
        total = len(self.predictions_posted)

        text = (
            f"📊 JARVIS Performance Update\n\n"
            f"📈 Predictions tracked: {total}\n"
            f"🎯 Accuracy: Tracking in progress\n"
            f"⏰ Running 24/7\n\n"
            f"Full transparency - follow along! 🤖 NFA"
        )

        tweet = TweetContent(text=text, tweet_type=TweetType.ACCURACY_UPDATE)
        await self._post_tweet(tweet)

    async def _post_tweet(self, tweet: TweetContent):
        """Post a tweet with validation"""
        # Import compliance checker
        from .twitter_compliance import validate_tweet_content

        # Validate content
        is_valid, issues = validate_tweet_content(tweet.text)

        if not is_valid:
            logger.warning(f"Tweet failed validation: {issues}")
            # Try to fix common issues
            if "Tweet too long" in str(issues):
                tweet.text = tweet.text[:277] + "..."
            else:
                raise ValueError(f"Tweet validation failed: {issues}")

        # Check if we can post
        if not self.scheduler.can_tweet():
            logger.info("Cannot tweet now, adding to queue")
            self.scheduler.add_to_queue(tweet)
            return

        # Post the tweet
        if self.client:
            try:
                response = self.client.create_tweet(text=tweet.text)
                tweet.tweet_id = response.data["id"]
                logger.info(f"Tweet posted: {tweet.tweet_id}")
            except Exception as e:
                logger.error(f"Failed to post tweet: {e}")
                raise
        else:
            # Dry run mode
            logger.info(f"[DRY RUN] Would post: {tweet.text[:50]}...")

        # Record the tweet
        self.scheduler.record_tweet(tweet)

    def get_stats(self) -> Dict[str, Any]:
        """Get bot statistics"""
        return {
            "running": self.running,
            "scheduler": self.scheduler.get_stats(),
            "predictions_posted": len(self.predictions_posted),
            "grok_interactions_today": self.grok_interactions_today,
            "error_count": self.error_count,
            "client_connected": self.client is not None
        }


# Singleton instance
_twitter_bot_instance: Optional[JarvisTwitterBot] = None


def get_twitter_bot() -> Optional[JarvisTwitterBot]:
    """Get the Twitter bot singleton"""
    global _twitter_bot_instance

    if _twitter_bot_instance is None:
        # Try to load from environment
        bearer_token = os.environ.get("X_BEARER_TOKEN") or os.environ.get("TWITTER_BEARER_TOKEN")
        api_key = os.environ.get("X_API_KEY") or os.environ.get("TWITTER_API_KEY")
        api_secret = os.environ.get("X_API_SECRET") or os.environ.get("TWITTER_API_SECRET")
        access_token = os.environ.get("X_ACCESS_TOKEN") or os.environ.get("TWITTER_ACCESS_TOKEN")
        access_secret = (
            os.environ.get("X_ACCESS_TOKEN_SECRET")
            or os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")
            or os.environ.get("TWITTER_ACCESS_SECRET")
        )

        if all([bearer_token, api_key, api_secret, access_token, access_secret]):
            _twitter_bot_instance = JarvisTwitterBot(
                bearer_token=bearer_token,
                api_key=api_key,
                api_secret=api_secret,
                access_token=access_token,
                access_secret=access_secret
            )
        else:
            logger.warning("Twitter credentials not found in environment")

    return _twitter_bot_instance


async def main():
    """Main entry point for testing"""
    bot = get_twitter_bot()
    if bot:
        await bot.run()
    else:
        print("Twitter bot not configured - set environment variables")


if __name__ == "__main__":
    asyncio.run(main())
