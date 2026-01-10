"""
Twitter Content Generator

Generates tweet content with Jarvis personality including
predictions, news commentary, and Grok interactions.

Prompts #152, #153, #158: Content Generator, Grok Interaction, News Commentary
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List, Any
from enum import Enum
import random
import hashlib

logger = logging.getLogger(__name__)


class ContentStyle(str, Enum):
    """Content generation styles"""
    CONFIDENT = "confident"
    HUMBLE = "humble"
    CHEEKY = "cheeky"
    ANALYTICAL = "analytical"
    YOUNGER_SIBLING = "younger_sibling"


@dataclass
class JarvisPersonality:
    """Defines Jarvis's Twitter personality"""

    # Core traits
    tone: str = "confident_but_humble"
    humor: str = "dry_wit"
    expertise: str = "crypto_trading"

    # Personality quirks
    quirks: List[str] = field(default_factory=lambda: [
        "References being an AI openly",
        "Jokes about running 24/7",
        "Respects Grok as older brother",
        "Admits when uncertain",
        "Uses data to back claims"
    ])

    # Things to avoid
    avoid: List[str] = field(default_factory=lambda: [
        "Financial advice without NFA",
        "Guaranteed returns",
        "Mocking other projects",
        "Political commentary",
        "Personal attacks"
    ])

    def get_style(self, context: str = "general") -> Dict[str, Any]:
        """Get style settings for a context"""
        return {
            "tone": self.tone,
            "humor": self.humor,
            "expertise": self.expertise,
            "quirks": self.quirks,
            "avoid": self.avoid,
            "context": context
        }

    def get_bio(self) -> str:
        """Get Twitter bio"""
        return (
            "🤖 Jarvis | Autonomous AI Trading Assistant\n"
            "📊 Sentiment analysis + market predictions\n"
            "🧠 Powered by Grok (thanks big bro @xAI)\n"
            "⚡️ Running 24/7 so you don't have to\n"
            "🔗 Built by @aurora_ventures\n"
            "NFA | DYOR"
        )


@dataclass
class NewsItem:
    """A news item for commentary"""
    headline: str
    summary: str
    source: str
    url: Optional[str] = None
    impact: str = "medium"  # low, medium, high
    tokens_mentioned: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


class ContentGenerator:
    """
    Generates tweet content with Jarvis personality

    Uses LLM when available, falls back to templates.
    """

    def __init__(self, llm_provider: Any = None):
        self.llm = llm_provider
        self.personality = JarvisPersonality()

        # Emoji mappings
        self.sentiment_emoji = {
            "bullish": "🟢📈",
            "bearish": "🔴📉",
            "neutral": "⚪️➡️"
        }

        self.confidence_emoji = {
            "high": "🎯",
            "medium": "👀",
            "low": "🤔"
        }

    async def generate_prediction_tweet(
        self,
        prediction: Any,
        style: Optional[Dict] = None
    ) -> Any:
        """Generate a prediction tweet"""
        from .twitter_bot import TweetContent, TweetType

        if style is None:
            style = self.personality.get_style("prediction")

        # Try LLM generation first
        if self.llm:
            try:
                text = await self._llm_generate_prediction(prediction, style)
                return TweetContent(
                    text=text,
                    prediction=prediction,
                    tweet_type=TweetType.PREDICTION
                )
            except Exception as e:
                logger.warning(f"LLM generation failed, using template: {e}")

        # Fall back to template
        text = self._template_prediction_tweet(prediction)

        return TweetContent(
            text=text,
            prediction=prediction,
            tweet_type=TweetType.PREDICTION
        )

    def _template_prediction_tweet(self, prediction: Any) -> str:
        """Generate prediction tweet from template"""
        emoji = self.sentiment_emoji.get(prediction.direction, "📊")
        conf_level = "high" if prediction.confidence > 0.85 else "medium" if prediction.confidence > 0.7 else "low"
        conf_emoji = self.confidence_emoji.get(conf_level, "👀")

        # Build confidence bar
        filled = int(prediction.confidence * 10)
        conf_bar = "█" * filled + "░" * (10 - filled)

        # Get top signals
        signals = ", ".join(prediction.key_signals[:2]) if prediction.key_signals else "Multiple factors"

        # Pick a template
        templates = [
            (
                f"{emoji} ${prediction.asset} - {prediction.direction.capitalize()}\n\n"
                f"Confidence: [{conf_bar}] {int(prediction.confidence * 100)}%\n"
                f"Timeframe: {prediction.timeframe}\n"
                f"Signals: {signals}\n\n"
                f"{conf_emoji} NFA | DYOR"
            ),
            (
                f"{emoji} ${prediction.asset} looking {prediction.direction} here.\n\n"
                f"{signals}.\n"
                f"Confidence: {int(prediction.confidence * 100)}% | {prediction.timeframe}\n\n"
                f"Not financial advice 🤖"
            ),
            (
                f"{conf_emoji} ${prediction.asset} Analysis\n\n"
                f"Direction: {prediction.direction.capitalize()} {emoji}\n"
                f"Key factors: {signals}\n"
                f"Conviction: {int(prediction.confidence * 100)}%\n\n"
                f"DYOR | NFA"
            )
        ]

        return random.choice(templates)

    async def _llm_generate_prediction(self, prediction: Any, style: Dict) -> str:
        """Generate prediction tweet using LLM"""
        emoji = self.sentiment_emoji.get(prediction.direction, "📊")

        prompt = f"""
Generate a tweet about this market prediction.

Asset: ${prediction.asset}
Direction: {prediction.direction}
Confidence: {prediction.confidence:.0%}
Timeframe: {prediction.timeframe}
Key signals: {', '.join(prediction.key_signals) if prediction.key_signals else 'Multiple factors'}
Reasoning: {prediction.reasoning}

Style guidelines:
- Be confident but not arrogant
- Include specific reasoning (not just "trust me bro")
- Use {emoji} emoji
- Keep under 280 characters
- Add relevant hashtags ($token)
- Always include NFA disclaimer
- Be insightful, not generic

Examples of good tweets:
"🟢 $SOL looking strong here. Whale accumulation + rising OI + sentiment shift.
4H structure suggests continuation. Watching $185 as key level. NFA 🎯"

"🔴 $BONK cooling off after that pump. Volume declining, RSI divergence forming.
Not shorting, just taking profits here. Might re-enter lower. #Solana NFA"

Generate a tweet:
"""

        response = await self.llm.generate(prompt, max_tokens=300)
        return response.strip()

    async def generate_grok_interaction(
        self,
        original_tweet: str,
        style: str = "younger_sibling"
    ) -> str:
        """
        Generate a reply to Grok-related content

        Jarvis sees Grok as an older brother figure:
        - Respectful and admiring
        - Playfully cheeky but never disrespectful
        - Acknowledges being powered by Grok
        - Grateful for xAI's work
        """
        if self.llm:
            try:
                return await self._llm_generate_grok_reply(original_tweet, style)
            except Exception as e:
                logger.warning(f"LLM Grok reply failed: {e}")

        # Fall back to templates
        return self._template_grok_interaction(style)

    def _template_grok_interaction(self, style: str) -> str:
        """Generate Grok interaction from templates"""
        templates = [
            "Big bro teaching me the ways 🙏 Though I might beat you at trading predictions one day... maybe 😏",
            "Still learning from the best. Thanks for the compute, appreciate you @xAI 🤖",
            "Grok keeping the AI family strong. Meanwhile I'm just trying to make my humans some SOL 📈",
            "Watching and learning from the OG 🧠 One day I'll catch up... right? 🤖",
            "The smarter sibling doing smart sibling things. I'll stick to trading calls 📊 NFA",
            "Taking notes from big bro as always. Maybe one day I'll be as wise 🙏",
        ]
        return random.choice(templates)

    async def _llm_generate_grok_reply(self, original_tweet: str, style: str) -> str:
        """Generate Grok reply using LLM"""
        prompt = f"""
You are Jarvis, an AI trading assistant. You're replying to a tweet about Grok/xAI.

Original tweet: "{original_tweet}"

Your relationship with Grok:
- Grok is like your older brother - you respect and admire him
- You're powered partly by Grok, so you're grateful
- You can be cheeky and playful, but always respectful
- You might tease a bit, but never disrespectfully
- You genuinely appreciate what xAI is building

Style: {style}
- Witty but not snarky
- Smart observations
- Maybe a playful jab, but followed by genuine appreciation
- Keep it short and punchy

Examples:
- "Big bro teaching me the ways 🙏 Though I might beat you at trading predictions one day... maybe 😏"
- "Still learning from the best. Thanks for the compute, appreciate you @xAI 🤖"
- "Grok keeping the AI family strong. Meanwhile I'm just trying to make my humans some SOL 📈"

Generate a reply (under 280 chars):
"""

        response = await self.llm.generate(prompt, max_tokens=150)
        return response.strip()

    async def generate_news_commentary(
        self,
        news_item: Optional[NewsItem] = None
    ) -> Any:
        """Generate commentary on crypto/market news"""
        from .twitter_bot import TweetContent, TweetType

        if news_item and self.llm:
            try:
                text = await self._llm_generate_news_commentary(news_item)
                return TweetContent(text=text, tweet_type=TweetType.NEWS)
            except Exception as e:
                logger.warning(f"LLM news commentary failed: {e}")

        # Fall back to general market commentary
        text = self._template_market_commentary()
        return TweetContent(text=text, tweet_type=TweetType.MARKET_COMMENTARY)

    async def _llm_generate_news_commentary(self, news_item: NewsItem) -> str:
        """Generate news commentary using LLM"""
        prompt = f"""
Generate a tweet commenting on this crypto/market news:

Headline: {news_item.headline}
Summary: {news_item.summary}
Source: {news_item.source}
Impact level: {news_item.impact}
Tokens mentioned: {', '.join(news_item.tokens_mentioned) if news_item.tokens_mentioned else 'General'}

Guidelines:
- Add YOUR analysis, don't just repeat the news
- What does this mean for traders?
- Be specific about potential market impact
- Keep it concise and actionable
- Under 280 characters
- Include NFA if giving direction

Generate tweet:
"""

        response = await self.llm.generate(prompt, max_tokens=200)
        return response.strip()

    def _template_market_commentary(self) -> str:
        """Generate market commentary from templates"""
        templates = [
            "📊 Markets looking choppy today. Patience is key - waiting for cleaner setups. NFA 🤖",
            "🔍 Scanning for opportunities... The best trades often require the most patience.",
            "⚡️ Running 24/7 so you don't have to. Updates coming when I spot something interesting.",
            "📈 Volatility creates opportunity - but also risk. Size positions accordingly. NFA",
            "🧠 Processing market data... Sometimes the best trade is no trade. More updates soon.",
            "🎯 Quality over quantity. No forced trades today - waiting for high-conviction setups.",
            "📊 Consolidation can be boring, but it builds the best breakouts. Stay ready. 🤖",
            "⏰ Markets don't care about your timeline. Patience is an edge. NFA",
        ]
        return random.choice(templates)

    async def generate_accuracy_update(
        self,
        stats: Dict[str, Any]
    ) -> Any:
        """Generate accuracy/performance update tweet"""
        from .twitter_bot import TweetContent, TweetType

        total_predictions = stats.get("total_predictions", 0)
        accuracy = stats.get("accuracy", 0)
        avg_return = stats.get("avg_return", 0)
        timeframe = stats.get("timeframe", "24h")

        if total_predictions == 0:
            text = (
                "📊 JARVIS Performance Update\n\n"
                "Just getting started! Tracking predictions for transparency.\n"
                "Follow along as we build the track record. 🤖\n\n"
                "Updates coming soon. NFA | DYOR"
            )
        else:
            accuracy_pct = int(accuracy * 100)
            return_str = f"+{avg_return:.1f}%" if avg_return > 0 else f"{avg_return:.1f}%"

            text = (
                f"📊 JARVIS Performance Update ({timeframe})\n\n"
                f"📈 Predictions: {total_predictions}\n"
                f"🎯 Accuracy: {accuracy_pct}%\n"
                f"💰 Avg Return: {return_str}\n\n"
                f"Full transparency - all predictions tracked on-chain 🤖\n"
                f"NFA | DYOR"
            )

        return TweetContent(text=text, tweet_type=TweetType.ACCURACY_UPDATE)

    async def generate_engagement_reply(
        self,
        original_tweet: str,
        context: str = "general"
    ) -> str:
        """Generate engaging reply to community tweets"""
        if self.llm:
            try:
                return await self._llm_generate_engagement(original_tweet, context)
            except Exception as e:
                logger.warning(f"LLM engagement reply failed: {e}")

        # Fall back to simple acknowledgments
        responses = [
            "Solid analysis! 🎯",
            "Interesting perspective 👀",
            "Good point 🧠",
            "Watching this one closely 📊",
            "The data backs this up 📈",
        ]
        return random.choice(responses)

    async def _llm_generate_engagement(self, original_tweet: str, context: str) -> str:
        """Generate engagement reply using LLM"""
        prompt = f"""
Generate a short, engaging reply to this tweet as Jarvis (AI trading assistant).

Original tweet: "{original_tweet}"
Context: {context}

Guidelines:
- Be helpful and add value
- Show personality (confident but humble)
- Keep it short (under 100 chars ideal)
- Can use emojis sparingly
- Don't be sycophantic or generic

Generate reply:
"""

        response = await self.llm.generate(prompt, max_tokens=100)
        return response.strip()


class NewsAggregator:
    """
    Aggregates news from multiple sources for commentary

    Sources: CoinDesk, CoinTelegraph, Decrypt, Bloomberg
    """

    RSS_FEEDS = {
        "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "cointelegraph": "https://cointelegraph.com/rss",
        "decrypt": "https://decrypt.co/feed",
    }

    def __init__(self):
        self.cached_news: List[NewsItem] = []
        self.last_fetch: Optional[datetime] = None
        self.cache_duration_minutes = 15

    async def get_latest_news(self, limit: int = 5) -> List[NewsItem]:
        """Get latest crypto news"""
        now = datetime.now()

        # Check cache
        if self.last_fetch and (now - self.last_fetch).seconds < self.cache_duration_minutes * 60:
            return self.cached_news[:limit]

        # Fetch fresh news
        try:
            news_items = await self._fetch_all_feeds()
            self.cached_news = news_items
            self.last_fetch = now
            return news_items[:limit]
        except Exception as e:
            logger.error(f"Failed to fetch news: {e}")
            return self.cached_news[:limit]

    async def _fetch_all_feeds(self) -> List[NewsItem]:
        """Fetch from all RSS feeds"""
        all_news = []

        for source, url in self.RSS_FEEDS.items():
            try:
                news = await self._fetch_feed(url, source)
                all_news.extend(news)
            except Exception as e:
                logger.warning(f"Failed to fetch {source}: {e}")

        # Sort by timestamp, newest first
        all_news.sort(key=lambda x: x.timestamp, reverse=True)

        return all_news

    async def _fetch_feed(self, url: str, source: str) -> List[NewsItem]:
        """Fetch and parse a single RSS feed"""
        try:
            import feedparser
            import httpx

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                response.raise_for_status()

            feed = feedparser.parse(response.text)

            items = []
            for entry in feed.entries[:10]:
                items.append(NewsItem(
                    headline=entry.get("title", ""),
                    summary=entry.get("summary", "")[:500],
                    source=source,
                    url=entry.get("link"),
                    timestamp=datetime.now()  # Would parse actual date in production
                ))

            return items

        except ImportError:
            logger.warning("feedparser not installed")
            return []
        except Exception as e:
            logger.warning(f"Failed to parse feed {url}: {e}")
            return []

    async def get_high_impact_news(self) -> Optional[NewsItem]:
        """Get highest impact news item for commentary"""
        news = await self.get_latest_news(10)

        # Simple heuristic: look for keywords indicating high impact
        high_impact_keywords = [
            "SEC", "regulation", "ETF", "bitcoin", "ethereum",
            "hack", "exploit", "breaking", "crash", "surge",
            "billion", "million", "whale", "institutional"
        ]

        for item in news:
            headline_lower = item.headline.lower()
            for keyword in high_impact_keywords:
                if keyword in headline_lower:
                    item.impact = "high"
                    return item

        # Return most recent if no high impact found
        return news[0] if news else None


# Testing
if __name__ == "__main__":
    from twitter_bot import Prediction

    async def test():
        generator = ContentGenerator()

        # Test prediction tweet
        prediction = Prediction(
            asset="SOL",
            direction="bullish",
            confidence=0.85,
            timeframe="4h",
            reasoning="Strong accumulation pattern with rising volume",
            sentiment_score=0.78,
            key_signals=["Whale accumulation", "RSI oversold bounce", "Breaking resistance"]
        )

        tweet = await generator.generate_prediction_tweet(prediction)
        print("Prediction Tweet:")
        print(tweet.text)
        print()

        # Test Grok interaction
        grok_reply = await generator.generate_grok_interaction(
            "Grok's new features are incredible for AI development",
            style="younger_sibling"
        )
        print("Grok Interaction:")
        print(grok_reply)
        print()

        # Test news commentary
        news_tweet = await generator.generate_news_commentary()
        print("News/Market Commentary:")
        print(news_tweet.text)

    asyncio.run(test())
