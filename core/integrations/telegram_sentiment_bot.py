"""
Telegram Sentiment Bot for Jarvis.

Provides automated crypto sentiment analysis via Telegram.
Posts periodic sentiment readings based on configured schedule.

Setup:
    1. Create a bot via @BotFather on Telegram
    2. Set TELEGRAM_BOT_TOKEN in secrets/keys.json
    3. Get your chat_id by messaging @userinfobot
    4. Configure schedule in lifeos/config/telegram_bot.json

Usage:
    from core.integrations import telegram_sentiment_bot

    # Start the bot
    telegram_sentiment_bot.start()

    # Manual sentiment push
    telegram_sentiment_bot.push_sentiment("SOL")
"""

import asyncio
import json
import logging
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Paths
ROOT = Path(__file__).resolve().parents[2]
CONFIG_FILE = ROOT / "lifeos" / "config" / "telegram_bot.json"
SECRETS_FILE = ROOT / "secrets" / "keys.json"

# Default configuration
DEFAULT_CONFIG = {
    "enabled": True,
    "chat_ids": [],  # List of chat IDs to send to
    "schedule": {
        "enabled": True,
        "times": ["09:00", "12:00", "17:00", "21:00"],  # UTC times
        "timezone": "UTC"
    },
    "tokens": ["SOL", "BTC", "ETH"],  # Default tokens to analyze
    "include_trending": True,
    "max_trending": 5,
    "sentiment_threshold": 0.6,  # Only post if confidence > this
    "format": {
        "use_emojis": True,
        "include_chart_link": True,
        "include_price": True
    }
}


@dataclass
class SentimentReading:
    """A sentiment reading for a token."""
    symbol: str
    sentiment: str  # bullish, bearish, neutral
    confidence: float
    price: Optional[float] = None
    change_24h: Optional[float] = None
    key_drivers: Optional[List[str]] = None
    timestamp: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def to_telegram_message(self, use_emojis: bool = True) -> str:
        """Format as Telegram message."""
        emoji_map = {
            "bullish": "🟢" if use_emojis else "[BULLISH]",
            "bearish": "🔴" if use_emojis else "[BEARISH]",
            "neutral": "⚪" if use_emojis else "[NEUTRAL]",
        }

        trend_emoji = {
            "bullish": "📈",
            "bearish": "📉",
            "neutral": "➡️",
        }

        sentiment_icon = emoji_map.get(self.sentiment, "⚪")
        trend_icon = trend_emoji.get(self.sentiment, "➡️") if use_emojis else ""

        lines = [
            f"{sentiment_icon} *{self.symbol}* {trend_icon}",
            f"Sentiment: *{self.sentiment.upper()}* ({self.confidence:.0%} confidence)",
        ]

        if self.price:
            price_str = f"${self.price:,.2f}" if self.price > 1 else f"${self.price:.6f}"
            lines.append(f"Price: {price_str}")

        if self.change_24h is not None:
            change_emoji = "📈" if self.change_24h > 0 else "📉" if self.change_24h < 0 else "➡️"
            change_str = f"{self.change_24h:+.2f}%"
            if use_emojis:
                lines.append(f"24h: {change_emoji} {change_str}")
            else:
                lines.append(f"24h: {change_str}")

        if self.key_drivers:
            drivers = ", ".join(self.key_drivers[:3])
            lines.append(f"Drivers: {drivers}")

        return "\n".join(lines)


class TelegramSentimentBot:
    """Telegram bot for automated sentiment analysis."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or CONFIG_FILE
        self.config = self._load_config()
        self.token = self._load_token()
        self._running = False
        self._scheduler_thread: Optional[threading.Thread] = None
        self._bot = None

    def _load_config(self) -> Dict[str, Any]:
        """Load bot configuration."""
        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    config = json.load(f)
                    # Merge with defaults
                    for key, value in DEFAULT_CONFIG.items():
                        if key not in config:
                            config[key] = value
                    return config
            except Exception as e:
                logger.warning(f"Failed to load config: {e}, using defaults")
        return DEFAULT_CONFIG.copy()

    def _save_config(self) -> None:
        """Save current configuration."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)

    def _load_token(self) -> Optional[str]:
        """Load Telegram bot token from secrets."""
        # Check environment first
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if token:
            return token

        # Check secrets file
        if SECRETS_FILE.exists():
            try:
                with open(SECRETS_FILE) as f:
                    secrets = json.load(f)
                    return secrets.get("TELEGRAM_BOT_TOKEN")
            except Exception:
                pass

        return None

    def _get_sentiment_analyzer(self):
        """Get the sentiment analyzer module."""
        try:
            from core.x_sentiment import XSentimentAnalyzer
            return XSentimentAnalyzer()
        except ImportError:
            logger.warning("XSentimentAnalyzer not available")
            return None

    def _get_price_data(self, symbol: str) -> Dict[str, Any]:
        """Get current price data for a token."""
        try:
            from core.birdeye import get_token_price
            return get_token_price(symbol)
        except Exception:
            return {}

    async def analyze_token(self, symbol: str) -> Optional[SentimentReading]:
        """Analyze sentiment for a single token."""
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

            # Get price data
            price_data = self._get_price_data(symbol)

            return SentimentReading(
                symbol=symbol,
                sentiment=result.sentiment,
                confidence=result.confidence,
                price=price_data.get("price"),
                change_24h=price_data.get("change_24h"),
                key_drivers=result.key_topics[:3] if result.key_topics else None,
            )
        except Exception as e:
            logger.error(f"Failed to analyze {symbol}: {e}")
            return None

    async def generate_report(self) -> str:
        """Generate a full sentiment report."""
        tokens = self.config.get("tokens", ["SOL", "BTC", "ETH"])
        readings = []

        for token in tokens:
            reading = await self.analyze_token(token)
            if reading:
                readings.append(reading)

        if not readings:
            return "No sentiment data available at this time."

        use_emojis = self.config.get("format", {}).get("use_emojis", True)

        # Header
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        lines = [
            f"{'🤖' if use_emojis else ''} *Jarvis Sentiment Report*",
            f"_{now}_",
            "",
        ]

        # Add each reading
        for reading in readings:
            lines.append(reading.to_telegram_message(use_emojis))
            lines.append("")

        # Summary
        bullish_count = sum(1 for r in readings if r.sentiment == "bullish")
        bearish_count = sum(1 for r in readings if r.sentiment == "bearish")

        if bullish_count > bearish_count:
            overall = "🟢 Overall: *BULLISH*" if use_emojis else "Overall: BULLISH"
        elif bearish_count > bullish_count:
            overall = "🔴 Overall: *BEARISH*" if use_emojis else "Overall: BEARISH"
        else:
            overall = "⚪ Overall: *NEUTRAL*" if use_emojis else "Overall: NEUTRAL"

        lines.append(overall)

        return "\n".join(lines)

    async def send_message(self, chat_id: int, text: str) -> bool:
        """Send a message to a chat."""
        if not self.token:
            logger.error("No Telegram bot token configured")
            return False

        try:
            import httpx

            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload)
                return response.status_code == 200

        except ImportError:
            # Fallback to requests
            import requests

            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
            }

            response = requests.post(url, json=payload)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False

    async def broadcast_report(self) -> int:
        """Send sentiment report to all configured chats."""
        chat_ids = self.config.get("chat_ids", [])
        if not chat_ids:
            logger.warning("No chat IDs configured")
            return 0

        report = await self.generate_report()
        success_count = 0

        for chat_id in chat_ids:
            if await self.send_message(chat_id, report):
                success_count += 1
                logger.info(f"Sent report to chat {chat_id}")
            else:
                logger.error(f"Failed to send to chat {chat_id}")

        return success_count

    def _should_run_now(self) -> bool:
        """Check if we should run a scheduled report now."""
        schedule = self.config.get("schedule", {})
        if not schedule.get("enabled", False):
            return False

        times = schedule.get("times", [])
        now = datetime.utcnow()
        current_time = now.strftime("%H:%M")

        # Check if current time matches any scheduled time (within 1 minute)
        for scheduled_time in times:
            if current_time == scheduled_time:
                return True

        return False

    def _scheduler_loop(self):
        """Background scheduler loop."""
        last_run_minute = -1

        while self._running:
            now = datetime.utcnow()
            current_minute = now.hour * 60 + now.minute

            # Only check once per minute
            if current_minute != last_run_minute and self._should_run_now():
                last_run_minute = current_minute
                logger.info("Running scheduled sentiment report")

                # Run the broadcast in a new event loop
                try:
                    asyncio.run(self.broadcast_report())
                except Exception as e:
                    logger.error(f"Scheduled broadcast failed: {e}")

            # Sleep for 30 seconds
            time.sleep(30)

    def start_scheduler(self):
        """Start the background scheduler."""
        if self._running:
            return

        self._running = True
        self._scheduler_thread = threading.Thread(
            target=self._scheduler_loop,
            daemon=True,
            name="TelegramSentimentScheduler"
        )
        self._scheduler_thread.start()
        logger.info("Telegram sentiment scheduler started")

    def stop_scheduler(self):
        """Stop the background scheduler."""
        self._running = False
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=5)
            self._scheduler_thread = None
        logger.info("Telegram sentiment scheduler stopped")

    def add_chat_id(self, chat_id: int):
        """Add a chat ID to the broadcast list."""
        if chat_id not in self.config["chat_ids"]:
            self.config["chat_ids"].append(chat_id)
            self._save_config()

    def remove_chat_id(self, chat_id: int):
        """Remove a chat ID from the broadcast list."""
        if chat_id in self.config["chat_ids"]:
            self.config["chat_ids"].remove(chat_id)
            self._save_config()

    def set_schedule(self, times: List[str]):
        """Set the scheduled times (UTC)."""
        self.config["schedule"]["times"] = times
        self._save_config()

    def set_tokens(self, tokens: List[str]):
        """Set the tokens to analyze."""
        self.config["tokens"] = tokens
        self._save_config()


# Module-level singleton
_bot: Optional[TelegramSentimentBot] = None


def get_bot() -> TelegramSentimentBot:
    """Get the singleton bot instance."""
    global _bot
    if _bot is None:
        _bot = TelegramSentimentBot()
    return _bot


def start():
    """Start the Telegram sentiment bot."""
    bot = get_bot()
    bot.start_scheduler()


def stop():
    """Stop the Telegram sentiment bot."""
    bot = get_bot()
    bot.stop_scheduler()


def push_sentiment(symbol: str, chat_id: Optional[int] = None):
    """Push a single token sentiment reading."""
    bot = get_bot()

    async def _push():
        reading = await bot.analyze_token(symbol)
        if reading:
            if chat_id:
                await bot.send_message(chat_id, reading.to_telegram_message())
            else:
                # Send to all configured chats
                for cid in bot.config.get("chat_ids", []):
                    await bot.send_message(cid, reading.to_telegram_message())

    asyncio.run(_push())


def push_report():
    """Push a full sentiment report."""
    bot = get_bot()
    asyncio.run(bot.broadcast_report())


if __name__ == "__main__":
    # Test mode
    logging.basicConfig(level=logging.INFO)
    print("Telegram Sentiment Bot Test")
    print("=" * 40)

    bot = get_bot()

    if not bot.token:
        print("No TELEGRAM_BOT_TOKEN configured!")
        print("Set it in secrets/keys.json or as environment variable")
    else:
        print(f"Token configured: {bot.token[:10]}...")
        print(f"Chat IDs: {bot.config.get('chat_ids', [])}")
        print(f"Schedule: {bot.config.get('schedule', {}).get('times', [])}")
        print(f"Tokens: {bot.config.get('tokens', [])}")
