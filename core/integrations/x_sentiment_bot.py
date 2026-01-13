"""
X (Twitter) Automated Sentiment Bot for Jarvis.

Posts automated crypto sentiment readings to X.
Uses the sentiment analysis engine to generate market insights.

Setup:
    1. Create X Developer account at developer.twitter.com
    2. Create an App with OAuth 1.0a (read/write permissions)
    3. Set these in secrets/keys.json:
       - X_API_KEY
       - X_API_SECRET
       - X_ACCESS_TOKEN
       - X_ACCESS_TOKEN_SECRET
    4. Configure schedule in lifeos/config/x_bot.json

Usage:
    from core.integrations import x_sentiment_bot

    # Start automated posting
    x_sentiment_bot.start()

    # Manual tweet
    x_sentiment_bot.post_sentiment("SOL")
"""

import asyncio
import hashlib
import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Paths
ROOT = Path(__file__).resolve().parents[2]
CONFIG_FILE = ROOT / "lifeos" / "config" / "x_bot.json"
SECRETS_FILE = ROOT / "secrets" / "keys.json"
POSTED_CACHE = ROOT / "data" / "x_bot" / "posted.json"

# Default configuration
DEFAULT_CONFIG = {
    "enabled": True,
    "schedule": {
        "enabled": True,
        "times": ["08:00", "14:00", "20:00"],  # UTC times - 3x daily
        "timezone": "UTC"
    },
    "tokens": ["SOL", "BTC", "ETH"],
    "post_format": "thread",  # "single" or "thread"
    "include_hashtags": True,
    "include_disclaimer": True,
    "max_chars": 280,
    "dry_run": False,  # Set True to test without posting
    "cooldown_minutes": 60,  # Min time between posts
    "reply_to_mentions": False,
    "mention_keywords": ["sentiment", "bullish", "bearish", "analysis"]
}


@dataclass
class XPost:
    """A post/tweet for X."""
    text: str
    in_reply_to: Optional[str] = None
    media_ids: Optional[List[str]] = None


@dataclass
class SentimentTweet:
    """Formatted sentiment for X posting."""
    symbol: str
    sentiment: str
    confidence: float
    price: Optional[float] = None
    change_24h: Optional[float] = None
    key_insight: Optional[str] = None

    def to_tweet(self, include_hashtags: bool = True, include_disclaimer: bool = True) -> str:
        """Format as X post."""
        # Emoji based on sentiment
        emoji_map = {
            "bullish": "🟢",
            "bearish": "🔴",
            "neutral": "⚪",
        }
        trend_emoji = {
            "bullish": "📈",
            "bearish": "📉",
            "neutral": "➡️",
        }

        sentiment_emoji = emoji_map.get(self.sentiment, "⚪")
        trend = trend_emoji.get(self.sentiment, "")

        # Build tweet
        lines = [
            f"{sentiment_emoji} ${self.symbol} Sentiment: {self.sentiment.upper()} {trend}",
            f"Confidence: {self.confidence:.0%}",
        ]

        if self.price:
            price_str = f"${self.price:,.2f}" if self.price > 1 else f"${self.price:.6f}"
            lines.append(f"Price: {price_str}")

        if self.change_24h is not None:
            change_str = f"{self.change_24h:+.2f}%"
            lines.append(f"24h: {change_str}")

        if self.key_insight:
            lines.append(f"💡 {self.key_insight}")

        if include_hashtags:
            lines.append(f"\n#{self.symbol} #crypto #sentiment")

        if include_disclaimer:
            lines.append("\n⚠️ Not financial advice")

        tweet = "\n".join(lines)

        # Truncate if needed
        if len(tweet) > 280:
            # Remove disclaimer first
            if include_disclaimer:
                tweet = "\n".join(lines[:-1])
            # Still too long? Remove hashtags
            if len(tweet) > 280 and include_hashtags:
                tweet = "\n".join(lines[:-2])
            # Still too long? Truncate
            if len(tweet) > 280:
                tweet = tweet[:277] + "..."

        return tweet


class XSentimentBot:
    """X bot for automated sentiment posting."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or CONFIG_FILE
        self.config = self._load_config()
        self.credentials = self._load_credentials()
        self._running = False
        self._scheduler_thread: Optional[threading.Thread] = None
        self._last_post_time = 0.0
        self._posted_hashes: set = self._load_posted_cache()

    def _load_config(self) -> Dict[str, Any]:
        """Load bot configuration."""
        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    config = json.load(f)
                    for key, value in DEFAULT_CONFIG.items():
                        if key not in config:
                            config[key] = value
                    return config
            except Exception as e:
                logger.warning(f"Failed to load config: {e}")
        return DEFAULT_CONFIG.copy()

    def _save_config(self) -> None:
        """Save current configuration."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)

    def _load_credentials(self) -> Dict[str, str]:
        """Load X API credentials."""
        creds = {}

        # Environment variables first
        creds["api_key"] = os.environ.get("X_API_KEY", "")
        creds["api_secret"] = os.environ.get("X_API_SECRET", "")
        creds["access_token"] = os.environ.get("X_ACCESS_TOKEN", "")
        creds["access_token_secret"] = os.environ.get("X_ACCESS_TOKEN_SECRET", "")

        # Fall back to secrets file
        if not all(creds.values()) and SECRETS_FILE.exists():
            try:
                with open(SECRETS_FILE) as f:
                    secrets = json.load(f)
                    creds["api_key"] = creds["api_key"] or secrets.get("X_API_KEY", "")
                    creds["api_secret"] = creds["api_secret"] or secrets.get("X_API_SECRET", "")
                    creds["access_token"] = creds["access_token"] or secrets.get("X_ACCESS_TOKEN", "")
                    creds["access_token_secret"] = creds["access_token_secret"] or secrets.get("X_ACCESS_TOKEN_SECRET", "")
            except Exception:
                pass

        return creds

    def _load_posted_cache(self) -> set:
        """Load cache of posted tweet hashes."""
        if POSTED_CACHE.exists():
            try:
                with open(POSTED_CACHE) as f:
                    data = json.load(f)
                    return set(data.get("hashes", []))
            except Exception:
                pass
        return set()

    def _save_posted_cache(self) -> None:
        """Save posted tweet hashes."""
        POSTED_CACHE.parent.mkdir(parents=True, exist_ok=True)
        with open(POSTED_CACHE, 'w') as f:
            json.dump({"hashes": list(self._posted_hashes)[-1000:]}, f)

    def _expected_username(self) -> str:
        expected = (
            os.environ.get("X_EXPECTED_USERNAME")
            or os.environ.get("TWITTER_EXPECTED_USERNAME")
            or "jarvis_lifeos"
        )
        expected = expected.strip().lstrip("@").lower()
        if expected in ("", "*", "any"):
            return ""
        return expected

    def _hash_tweet(self, text: str) -> str:
        """Generate hash for deduplication."""
        return hashlib.md5(text.encode()).hexdigest()[:12]

    def is_configured(self) -> bool:
        """Check if credentials are configured."""
        return all([
            self.credentials.get("api_key"),
            self.credentials.get("api_secret"),
            self.credentials.get("access_token"),
            self.credentials.get("access_token_secret"),
        ])

    def _get_tweepy_client(self):
        """Get authenticated Tweepy client."""
        try:
            import tweepy

            client = tweepy.Client(
                consumer_key=self.credentials["api_key"],
                consumer_secret=self.credentials["api_secret"],
                access_token=self.credentials["access_token"],
                access_token_secret=self.credentials["access_token_secret"],
            )
            expected = self._expected_username()
            if expected:
                try:
                    me = client.get_me()
                    username = me.data.username if me and me.data else None
                    if not username or username.lower() != expected:
                        logger.error(
                            "X account mismatch: expected @%s, got @%s",
                            expected,
                            username or "unknown",
                        )
                        return None
                except Exception as e:
                    logger.error(f"Failed to verify X account: {e}")
                    return None
            return client
        except ImportError:
            logger.error("tweepy not installed. Run: pip install tweepy")
            return None

    def _get_sentiment_analyzer(self):
        """Get sentiment analyzer."""
        try:
            from core.x_sentiment import XSentimentAnalyzer
            return XSentimentAnalyzer()
        except ImportError:
            return None

    def _get_price_data(self, symbol: str) -> Dict[str, Any]:
        """Get price data for a token."""
        try:
            from core.birdeye import get_token_price
            return get_token_price(symbol)
        except Exception:
            return {}

    async def analyze_token(self, symbol: str) -> Optional[SentimentTweet]:
        """Analyze sentiment for a token."""
        analyzer = self._get_sentiment_analyzer()
        if not analyzer:
            return None

        try:
            result = await asyncio.to_thread(
                analyzer.analyze_crypto_sentiment,
                symbol,
                sample_size=20
            )

            if not result:
                return None

            price_data = self._get_price_data(symbol)

            key_insight = None
            if result.key_topics:
                key_insight = result.key_topics[0]

            return SentimentTweet(
                symbol=symbol,
                sentiment=result.sentiment,
                confidence=result.confidence,
                price=price_data.get("price"),
                change_24h=price_data.get("change_24h"),
                key_insight=key_insight,
            )
        except Exception as e:
            logger.error(f"Failed to analyze {symbol}: {e}")
            return None

    def post_tweet(self, text: str) -> Optional[str]:
        """Post a tweet. Returns tweet ID or None."""
        if self.config.get("dry_run", False):
            logger.info(f"[DRY RUN] Would post: {text}")
            return "dry_run_id"

        # Check cooldown
        cooldown = self.config.get("cooldown_minutes", 60) * 60
        if time.time() - self._last_post_time < cooldown:
            logger.warning("Cooldown active, skipping post")
            return None

        # Check for duplicate
        tweet_hash = self._hash_tweet(text)
        if tweet_hash in self._posted_hashes:
            logger.warning("Duplicate tweet, skipping")
            return None

        if not self.is_configured():
            logger.error("X credentials not configured")
            return None

        client = self._get_tweepy_client()
        if not client:
            return None

        try:
            response = client.create_tweet(text=text)
            tweet_id = response.data["id"]

            # Update caches
            self._last_post_time = time.time()
            self._posted_hashes.add(tweet_hash)
            self._save_posted_cache()

            logger.info(f"Posted tweet: {tweet_id}")
            return tweet_id
        except Exception as e:
            logger.error(f"Failed to post tweet: {e}")
            return None

    async def post_sentiment(self, symbol: str) -> Optional[str]:
        """Analyze and post sentiment for a token."""
        tweet = await self.analyze_token(symbol)
        if not tweet:
            return None

        text = tweet.to_tweet(
            include_hashtags=self.config.get("include_hashtags", True),
            include_disclaimer=self.config.get("include_disclaimer", True),
        )

        return self.post_tweet(text)

    async def post_report(self) -> List[str]:
        """Post sentiment for all configured tokens."""
        tokens = self.config.get("tokens", ["SOL"])
        posted_ids = []

        if self.config.get("post_format") == "thread":
            # Post as a thread
            first_tweet_id = None
            for i, symbol in enumerate(tokens):
                tweet = await self.analyze_token(symbol)
                if not tweet:
                    continue

                text = tweet.to_tweet(
                    include_hashtags=(i == len(tokens) - 1),  # Only on last tweet
                    include_disclaimer=(i == len(tokens) - 1),
                )

                # TODO: Implement reply threading
                tweet_id = self.post_tweet(text)
                if tweet_id:
                    posted_ids.append(tweet_id)
                    if first_tweet_id is None:
                        first_tweet_id = tweet_id

                # Small delay between thread posts
                await asyncio.sleep(2)
        else:
            # Post individually
            for symbol in tokens:
                tweet_id = await self.post_sentiment(symbol)
                if tweet_id:
                    posted_ids.append(tweet_id)
                await asyncio.sleep(60)  # 1 minute between individual posts

        return posted_ids

    def _should_run_now(self) -> bool:
        """Check if scheduled run is due."""
        schedule = self.config.get("schedule", {})
        if not schedule.get("enabled", False):
            return False

        times = schedule.get("times", [])
        now = datetime.now(timezone.utc)
        current_time = now.strftime("%H:%M")

        return current_time in times

    def _scheduler_loop(self):
        """Background scheduler."""
        last_run_minute = -1

        while self._running:
            now = datetime.now(timezone.utc)
            current_minute = now.hour * 60 + now.minute

            if current_minute != last_run_minute and self._should_run_now():
                last_run_minute = current_minute
                logger.info("Running scheduled X sentiment post")

                try:
                    asyncio.run(self.post_report())
                except Exception as e:
                    logger.error(f"Scheduled post failed: {e}")

            time.sleep(30)

    def start_scheduler(self):
        """Start background scheduler."""
        if self._running:
            return

        self._running = True
        self._scheduler_thread = threading.Thread(
            target=self._scheduler_loop,
            daemon=True,
            name="XSentimentScheduler"
        )
        self._scheduler_thread.start()
        logger.info("X sentiment scheduler started")

    def stop_scheduler(self):
        """Stop background scheduler."""
        self._running = False
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=5)
            self._scheduler_thread = None


# Singleton
_bot: Optional[XSentimentBot] = None


def get_bot() -> XSentimentBot:
    """Get singleton instance."""
    global _bot
    if _bot is None:
        _bot = XSentimentBot()
    return _bot


def start():
    """Start X sentiment bot."""
    get_bot().start_scheduler()


def stop():
    """Stop X sentiment bot."""
    get_bot().stop_scheduler()


def post_sentiment(symbol: str) -> Optional[str]:
    """Post sentiment for a token."""
    return asyncio.run(get_bot().post_sentiment(symbol))


def post_report() -> List[str]:
    """Post full sentiment report."""
    return asyncio.run(get_bot().post_report())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("X Sentiment Bot Test")
    print("=" * 40)

    bot = get_bot()

    if not bot.is_configured():
        print("X credentials not configured!")
        print("Required in secrets/keys.json:")
        print("  - X_API_KEY")
        print("  - X_API_SECRET")
        print("  - X_ACCESS_TOKEN")
        print("  - X_ACCESS_TOKEN_SECRET")
    else:
        print("Credentials configured ✓")
        print(f"Schedule: {bot.config.get('schedule', {}).get('times', [])}")
        print(f"Tokens: {bot.config.get('tokens', [])}")
        print(f"Dry run: {bot.config.get('dry_run', False)}")
