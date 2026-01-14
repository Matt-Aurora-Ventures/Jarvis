"""
News Event Detector
Monitors crypto news for trading-relevant events and triggers alerts.

Integrates with:
- CryptoPanic API for news aggregation
- LunarCrush for social sentiment spikes
- Alpha detector for correlation
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class NewsEventType(Enum):
    """Types of news events that can trigger action."""
    REGULATORY = "regulatory"  # SEC, legal, government
    EXCHANGE = "exchange"  # Listings, delistings
    PARTNERSHIP = "partnership"  # Major partnerships
    TECHNICAL = "technical"  # Upgrades, hacks, bugs
    WHALE = "whale"  # Large wallet movements
    SOCIAL_SPIKE = "social_spike"  # Sudden social volume
    BREAKING = "breaking"  # Major breaking news
    SENTIMENT_SHIFT = "sentiment_shift"  # Market mood change


class EventPriority(Enum):
    """Priority levels for news events."""
    CRITICAL = 3  # Immediate action needed
    HIGH = 2  # Act within minutes
    MEDIUM = 1  # Monitor closely
    LOW = 0  # Informational only


@dataclass
class NewsEvent:
    """A detected news event."""
    event_id: str
    event_type: NewsEventType
    priority: EventPriority
    title: str
    summary: str
    tokens: List[str]  # Affected tokens
    source: str
    url: Optional[str]
    detected_at: datetime
    sentiment: str  # bullish, bearish, neutral
    confidence: float  # 0-100
    raw_data: Dict[str, Any] = field(default_factory=dict)
    actioned: bool = False


# Keyword patterns for event classification
EVENT_PATTERNS = {
    NewsEventType.REGULATORY: [
        "sec", "cftc", "regulation", "lawsuit", "legal", "court", "ban",
        "investigation", "subpoena", "congressional", "senate", "bill",
        "compliance", "license", "enforcement"
    ],
    NewsEventType.EXCHANGE: [
        "listing", "delist", "coinbase", "binance", "kraken", "bybit",
        "ftx", "gemini", "trading pair", "spot trading", "futures"
    ],
    NewsEventType.PARTNERSHIP: [
        "partnership", "collaboration", "integration", "launches with",
        "joins", "teams up", "alliance", "acquisition", "merger"
    ],
    NewsEventType.TECHNICAL: [
        "upgrade", "fork", "hack", "exploit", "vulnerability", "bug",
        "mainnet", "testnet", "release", "v2", "v3", "migration"
    ],
    NewsEventType.WHALE: [
        "whale", "large transfer", "million moved", "billion",
        "wallet", "accumulation", "distribution"
    ],
    NewsEventType.BREAKING: [
        "breaking", "just in", "alert", "urgent", "emergency",
        "flash crash", "pump", "dump", "rug"
    ],
}

# Keywords that boost priority
HIGH_PRIORITY_KEYWORDS = [
    "breaking", "urgent", "emergency", "hack", "exploit", "crash",
    "sec", "lawsuit", "ban", "delisting", "rug"
]


class NewsEventDetector:
    """
    Detect and categorize crypto news events.
    Monitors multiple sources and triggers alerts.
    """

    def __init__(self):
        self.events: List[NewsEvent] = []
        self.last_scan = None
        self.scan_interval = 180  # 3 minutes
        self._cryptopanic = None
        self._lunarcrush = None
        self._telegram_notifier = None

        # Track seen headlines to avoid duplicates
        self._seen_headlines: set = set()

        # Alert thresholds
        self.min_confidence = 60.0
        self.sentiment_spike_threshold = 0.3  # 30% shift

    def _get_cryptopanic(self):
        """Lazy load CryptoPanic API."""
        if self._cryptopanic is None:
            try:
                from core.data.cryptopanic_api import get_cryptopanic
                self._cryptopanic = get_cryptopanic()
            except Exception as e:
                logger.debug(f"CryptoPanic not available: {e}")
        return self._cryptopanic

    def _get_lunarcrush(self):
        """Lazy load LunarCrush API."""
        if self._lunarcrush is None:
            try:
                from core.data.lunarcrush_api import get_lunarcrush
                self._lunarcrush = get_lunarcrush()
            except Exception as e:
                logger.debug(f"LunarCrush not available: {e}")
        return self._lunarcrush

    def _get_telegram(self):
        """Lazy load Telegram notifier."""
        if self._telegram_notifier is None:
            try:
                from tg_bot.services.notifier import get_notifier
                self._telegram_notifier = get_notifier()
            except Exception:
                pass
        return self._telegram_notifier

    def _generate_event_id(self, title: str) -> str:
        """Generate unique event ID."""
        import hashlib
        content = f"{title}:{datetime.utcnow().strftime('%Y%m%d%H')}"
        return hashlib.md5(content.encode()).hexdigest()[:12]

    def _classify_event(self, title: str, content: str = "") -> Optional[NewsEventType]:
        """Classify event type based on keywords."""
        text = f"{title} {content}".lower()

        for event_type, keywords in EVENT_PATTERNS.items():
            if any(kw in text for kw in keywords):
                return event_type

        return None

    def _calculate_priority(self, title: str, sentiment: str, event_type: Optional[NewsEventType]) -> EventPriority:
        """Calculate event priority."""
        title_lower = title.lower()

        # Check for high priority keywords
        if any(kw in title_lower for kw in HIGH_PRIORITY_KEYWORDS):
            return EventPriority.CRITICAL

        # Breaking news is always high priority
        if event_type == NewsEventType.BREAKING:
            return EventPriority.CRITICAL

        # Regulatory and exchange news are high priority
        if event_type in (NewsEventType.REGULATORY, NewsEventType.EXCHANGE):
            return EventPriority.HIGH

        # Strong sentiment signals
        if sentiment in ("bullish", "bearish"):
            return EventPriority.MEDIUM

        return EventPriority.LOW

    def _calculate_confidence(self, article: Dict[str, Any]) -> float:
        """Calculate confidence score for an article."""
        confidence = 50.0

        # Votes boost confidence
        positive = article.get("votes_positive", 0)
        negative = article.get("votes_negative", 0)
        total_votes = positive + negative

        if total_votes > 10:
            confidence += min(20, total_votes / 2)

        # Hot articles are more relevant
        if article.get("is_hot"):
            confidence += 15

        # Known reputable sources
        reputable_sources = ["coindesk", "cointelegraph", "decrypt", "theblock"]
        source = article.get("source", "").lower()
        if any(s in source for s in reputable_sources):
            confidence += 10

        return min(100, confidence)

    async def scan_news(self) -> List[NewsEvent]:
        """Scan all news sources for events."""
        events = []

        # Scan CryptoPanic
        crypto_events = await self._scan_cryptopanic()
        events.extend(crypto_events)

        # Scan for social sentiment spikes
        social_events = await self._scan_social_spikes()
        events.extend(social_events)

        # Update state
        self.events = events
        self.last_scan = datetime.utcnow()

        logger.info(f"News scan found {len(events)} events")
        return events

    async def _scan_cryptopanic(self) -> List[NewsEvent]:
        """Scan CryptoPanic for news events."""
        events = []
        cryptopanic = self._get_cryptopanic()

        if not cryptopanic:
            return events

        try:
            # Get hot news
            hot_news = await cryptopanic.get_news(filter_type="hot", limit=20)

            # Get important/breaking news
            important = await cryptopanic.get_important_news(limit=10)

            # Get bullish/bearish news
            bullish = await cryptopanic.get_bullish_news(limit=5)
            bearish = await cryptopanic.get_bearish_news(limit=5)

            # Combine and dedupe
            all_articles = []
            seen_titles = set()
            for article in hot_news + important + bullish + bearish:
                title = article.get("title", "")
                if title and title not in seen_titles:
                    seen_titles.add(title)
                    all_articles.append(article)

            # Process each article
            for article in all_articles:
                title = article.get("title", "")

                # Skip if we've already seen this
                if title in self._seen_headlines:
                    continue

                self._seen_headlines.add(title)

                # Classify and create event
                event_type = self._classify_event(title)
                if not event_type:
                    event_type = NewsEventType.BREAKING if article.get("is_hot") else None

                if event_type:
                    sentiment = article.get("sentiment", "neutral")
                    priority = self._calculate_priority(title, sentiment, event_type)
                    confidence = self._calculate_confidence(article)

                    event = NewsEvent(
                        event_id=self._generate_event_id(title),
                        event_type=event_type,
                        priority=priority,
                        title=title,
                        summary=title[:200],
                        tokens=article.get("currencies", []),
                        source=article.get("source", "CryptoPanic"),
                        url=article.get("url"),
                        detected_at=datetime.utcnow(),
                        sentiment=sentiment,
                        confidence=confidence,
                        raw_data=article
                    )
                    events.append(event)

        except Exception as e:
            logger.error(f"CryptoPanic scan error: {e}")

        return events

    async def _scan_social_spikes(self) -> List[NewsEvent]:
        """Detect social sentiment spikes."""
        events = []
        lunarcrush = self._get_lunarcrush()

        if not lunarcrush:
            return events

        try:
            # Get trending coins
            trending = await lunarcrush.get_trending_coins(20)

            for coin in trending:
                # High galaxy score with strong sentiment = notable event
                galaxy_score = coin.get("galaxy_score", 0)
                sentiment = coin.get("sentiment", 50)
                social_volume = coin.get("social_volume", 0)

                # Detect significant social activity
                if galaxy_score > 80 or (social_volume > 10000 and abs(sentiment - 50) > 15):
                    symbol = coin.get("symbol", "")

                    event = NewsEvent(
                        event_id=self._generate_event_id(f"social_spike_{symbol}"),
                        event_type=NewsEventType.SOCIAL_SPIKE,
                        priority=EventPriority.MEDIUM if galaxy_score > 90 else EventPriority.LOW,
                        title=f"Social spike detected: ${symbol}",
                        summary=f"Galaxy score: {galaxy_score}, Sentiment: {sentiment}",
                        tokens=[symbol],
                        source="LunarCrush",
                        url=None,
                        detected_at=datetime.utcnow(),
                        sentiment="bullish" if sentiment > 55 else "bearish" if sentiment < 45 else "neutral",
                        confidence=min(100, galaxy_score),
                        raw_data=coin
                    )
                    events.append(event)

        except Exception as e:
            logger.error(f"Social spike scan error: {e}")

        return events

    def get_high_priority_events(self) -> List[NewsEvent]:
        """Get events that need immediate attention."""
        return [
            e for e in self.events
            if e.priority.value >= EventPriority.HIGH.value
            and not e.actioned
            and e.confidence >= self.min_confidence
        ]

    def get_events_for_token(self, symbol: str) -> List[NewsEvent]:
        """Get events related to a specific token."""
        symbol_upper = symbol.upper()
        return [
            e for e in self.events
            if symbol_upper in e.tokens or symbol_upper in e.title.upper()
        ]

    async def send_alert(self, event: NewsEvent) -> bool:
        """Send alert for a news event."""
        telegram = self._get_telegram()
        if not telegram:
            return False

        try:
            # Format alert message
            priority_emoji = {
                EventPriority.CRITICAL: "🚨",
                EventPriority.HIGH: "⚠️",
                EventPriority.MEDIUM: "📢",
                EventPriority.LOW: "ℹ️"
            }

            sentiment_emoji = {
                "bullish": "🟢",
                "bearish": "🔴",
                "neutral": "⚪"
            }

            msg = (
                f"{priority_emoji.get(event.priority, '📰')} **NEWS ALERT**\n\n"
                f"{event.title}\n\n"
                f"Type: {event.event_type.value}\n"
                f"Sentiment: {sentiment_emoji.get(event.sentiment, '⚪')} {event.sentiment}\n"
                f"Confidence: {event.confidence:.0f}%\n"
                f"Tokens: {', '.join(event.tokens) if event.tokens else 'General'}\n"
            )

            if event.url:
                msg += f"\n🔗 {event.url}"

            await telegram.send_message(msg)
            event.actioned = True
            return True

        except Exception as e:
            logger.error(f"Alert send error: {e}")
            return False

    async def process_alerts(self):
        """Process and send alerts for high priority events."""
        high_priority = self.get_high_priority_events()

        for event in high_priority:
            await self.send_alert(event)
            await asyncio.sleep(1)  # Rate limit

    def get_content_from_events(self) -> List[Dict[str, Any]]:
        """Generate tweet content suggestions from events."""
        suggestions = []

        for event in self.events:
            if event.actioned or event.confidence < self.min_confidence:
                continue

            if event.event_type == NewsEventType.REGULATORY:
                suggestions.append({
                    "type": "news_commentary",
                    "topic": "regulatory news",
                    "event": event,
                    "prompt": f"Brief take on: {event.title}"
                })
            elif event.event_type == NewsEventType.EXCHANGE:
                suggestions.append({
                    "type": "exchange_news",
                    "topic": event.title,
                    "event": event,
                    "prompt": f"Listing/exchange news: {event.title}"
                })
            elif event.event_type == NewsEventType.SOCIAL_SPIKE:
                tokens = ", ".join(event.tokens) if event.tokens else "crypto"
                suggestions.append({
                    "type": "social_alpha",
                    "topic": f"Social buzz on {tokens}",
                    "event": event,
                    "prompt": f"Social activity spike on {tokens}. {event.summary}"
                })

        return suggestions[:3]

    def mark_actioned(self, event_id: str):
        """Mark an event as actioned."""
        for event in self.events:
            if event.event_id == event_id:
                event.actioned = True
                break

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of current news state."""
        if not self.events:
            return {"status": "no_data", "last_scan": self.last_scan}

        critical = len([e for e in self.events if e.priority == EventPriority.CRITICAL])
        high = len([e for e in self.events if e.priority == EventPriority.HIGH])
        bullish = len([e for e in self.events if e.sentiment == "bullish"])
        bearish = len([e for e in self.events if e.sentiment == "bearish"])

        return {
            "total_events": len(self.events),
            "critical_count": critical,
            "high_priority_count": high,
            "bullish_count": bullish,
            "bearish_count": bearish,
            "sentiment_ratio": bullish / max(bearish, 1),
            "market_mood": "bullish" if bullish > bearish * 1.5 else "bearish" if bearish > bullish * 1.5 else "mixed",
            "last_scan": self.last_scan,
            "top_events": [
                {"title": e.title, "type": e.event_type.value, "priority": e.priority.name}
                for e in sorted(self.events, key=lambda x: x.priority.value, reverse=True)[:5]
            ]
        }


# Singleton
_detector: Optional[NewsEventDetector] = None


def get_news_detector() -> NewsEventDetector:
    """Get singleton NewsEventDetector instance."""
    global _detector
    if _detector is None:
        _detector = NewsEventDetector()
    return _detector
