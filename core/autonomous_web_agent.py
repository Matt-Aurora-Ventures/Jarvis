"""
Autonomous Web Research Agent

Continuously researches topics, monitors markets, and gathers intelligence.
Uses free/open-source tools: requests, BeautifulSoup, feedparser.

Features:
- Topic queue with priority
- Source rotation (avoid rate limits)
- Knowledge extraction & storage
- Actionable insight detection
- Memory integration
"""

import asyncio
import hashlib
import json
import logging
import re
import time
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Set
from urllib.parse import urlparse

import aiohttp
from aiohttp import ClientTimeout

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
RESEARCH_DB = ROOT / "data" / "research"
KNOWLEDGE_FILE = RESEARCH_DB / "knowledge_base.json"
SOURCES_FILE = RESEARCH_DB / "sources.json"
QUEUE_FILE = RESEARCH_DB / "research_queue.json"


@dataclass
class ResearchTopic:
    """A topic to research."""
    topic: str
    priority: int = 5  # 1-10, higher = more important
    category: str = "general"  # market, crypto, news, tech, trading
    keywords: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    last_researched: Optional[str] = None
    findings_count: int = 0


@dataclass
class KnowledgeEntry:
    """A piece of extracted knowledge."""
    id: str
    topic: str
    title: str
    summary: str
    source_url: str
    source_name: str
    extracted_at: str
    confidence: float
    category: str
    tags: List[str] = field(default_factory=list)
    actionable: bool = False
    action_suggestion: str = ""
    related_entries: List[str] = field(default_factory=list)


@dataclass
class ActionableInsight:
    """An insight that suggests action."""
    insight: str
    source: str
    confidence: float
    suggested_action: str
    urgency: str  # low, medium, high, critical
    expires_at: Optional[str] = None


class ResearchSource:
    """A research data source."""

    def __init__(self, name: str, base_url: str, source_type: str = "web"):
        self.name = name
        self.base_url = base_url
        self.source_type = source_type  # web, api, rss
        self.last_accessed = 0
        self.rate_limit_seconds = 5
        self.enabled = True

    def can_access(self) -> bool:
        return time.time() - self.last_accessed >= self.rate_limit_seconds

    def mark_accessed(self):
        self.last_accessed = time.time()


class AutonomousWebAgent:
    """
    Autonomous agent that researches topics and extracts knowledge.

    Workflow:
    1. Maintain priority queue of topics
    2. Fetch content from multiple sources
    3. Extract key information
    4. Detect actionable insights
    5. Store in knowledge base
    6. Suggest actions to user
    """

    # Default sources for different categories
    DEFAULT_SOURCES = {
        'crypto': [
            ('CoinGecko', 'https://api.coingecko.com/api/v3', 'api'),
            ('DexScreener', 'https://api.dexscreener.com', 'api'),
            ('CryptoNews', 'https://cryptonews.com/news/', 'web'),
        ],
        'market': [
            ('Yahoo Finance', 'https://finance.yahoo.com', 'web'),
            ('MarketWatch', 'https://www.marketwatch.com', 'web'),
            ('Fear & Greed', 'https://api.alternative.me/fng/', 'api'),
        ],
        'tech': [
            ('Hacker News', 'https://hacker-news.firebaseio.com/v0', 'api'),
            ('TechCrunch', 'https://techcrunch.com', 'web'),
        ],
        'trading': [
            ('TradingView Ideas', 'https://www.tradingview.com/ideas/', 'web'),
        ],
    }

    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.sources: Dict[str, ResearchSource] = {}
        self.topic_queue: Deque[ResearchTopic] = deque(maxlen=100)
        self.knowledge_base: Dict[str, KnowledgeEntry] = {}
        self.actionable_insights: List[ActionableInsight] = []
        self.seen_urls: Set[str] = set()

        self._running = False
        self._session: Optional[aiohttp.ClientSession] = None

        # Load state
        self._load_state()
        self._init_sources()

    def _init_sources(self):
        """Initialize research sources."""
        for category, sources in self.DEFAULT_SOURCES.items():
            for name, url, source_type in sources:
                key = f"{category}:{name}"
                self.sources[key] = ResearchSource(name, url, source_type)

    def _load_state(self):
        """Load persisted state."""
        RESEARCH_DB.mkdir(parents=True, exist_ok=True)

        # Load knowledge base
        if KNOWLEDGE_FILE.exists():
            try:
                with open(KNOWLEDGE_FILE) as f:
                    data = json.load(f)
                    for entry_data in data.get('entries', []):
                        entry = KnowledgeEntry(**entry_data)
                        self.knowledge_base[entry.id] = entry
            except Exception as e:
                logger.error(f"Failed to load knowledge base: {e}")

        # Load queue
        if QUEUE_FILE.exists():
            try:
                with open(QUEUE_FILE) as f:
                    data = json.load(f)
                    for topic_data in data.get('topics', []):
                        self.topic_queue.append(ResearchTopic(**topic_data))
            except Exception:
                pass

    def _save_state(self):
        """Persist state to disk."""
        # Save knowledge base
        entries = [asdict(e) for e in self.knowledge_base.values()]
        with open(KNOWLEDGE_FILE, 'w') as f:
            json.dump({'entries': entries, 'updated': datetime.now().isoformat()}, f, indent=2)

        # Save queue
        topics = [asdict(t) for t in self.topic_queue]
        with open(QUEUE_FILE, 'w') as f:
            json.dump({'topics': topics}, f, indent=2)

    def add_topic(self, topic: str, priority: int = 5, category: str = "general",
                  keywords: List[str] = None):
        """Add a research topic to the queue."""
        research_topic = ResearchTopic(
            topic=topic,
            priority=priority,
            category=category,
            keywords=keywords or [topic],
        )
        self.topic_queue.append(research_topic)
        self._save_state()
        logger.info(f"Added research topic: {topic} (priority {priority})")

    def get_next_topic(self) -> Optional[ResearchTopic]:
        """Get highest priority topic."""
        if not self.topic_queue:
            return None

        # Sort by priority (descending) and return highest
        topics = list(self.topic_queue)
        topics.sort(key=lambda t: t.priority, reverse=True)
        return topics[0] if topics else None

    async def research_topic(self, topic: ResearchTopic) -> List[KnowledgeEntry]:
        """Research a specific topic."""
        if not self._session:
            # Configure timeouts: 60s total, 30s connect (for web research)
            timeout = ClientTimeout(total=60, connect=30)
            self._session = aiohttp.ClientSession(timeout=timeout)

        findings = []
        category_sources = [
            s for key, s in self.sources.items()
            if key.startswith(topic.category) and s.enabled and s.can_access()
        ]

        for source in category_sources[:3]:  # Limit sources per topic
            try:
                entries = await self._fetch_from_source(source, topic)
                findings.extend(entries)
                source.mark_accessed()
                await asyncio.sleep(1)  # Polite delay
            except Exception as e:
                logger.warning(f"Source {source.name} failed: {e}")

        # Update topic
        topic.last_researched = datetime.now().isoformat()
        topic.findings_count += len(findings)

        # Store findings
        for entry in findings:
            self.knowledge_base[entry.id] = entry

        self._save_state()
        return findings

    async def _fetch_from_source(self, source: ResearchSource, topic: ResearchTopic) -> List[KnowledgeEntry]:
        """Fetch data from a specific source."""
        entries = []

        if source.source_type == 'api':
            entries = await self._fetch_api(source, topic)
        elif source.source_type == 'web':
            entries = await self._fetch_web(source, topic)
        elif source.source_type == 'rss':
            entries = await self._fetch_rss(source, topic)

        return entries

    async def _fetch_api(self, source: ResearchSource, topic: ResearchTopic) -> List[KnowledgeEntry]:
        """Fetch from API source."""
        entries = []

        try:
            # Handle specific APIs
            if 'coingecko' in source.base_url:
                url = f"{source.base_url}/search/trending"
                async with self._session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for coin in data.get('coins', [])[:5]:
                            item = coin.get('item', {})
                            entry = KnowledgeEntry(
                                id=hashlib.md5(f"{item.get('id')}-{time.time()}".encode()).hexdigest()[:12],
                                topic=topic.topic,
                                title=f"Trending: {item.get('name')} ({item.get('symbol')})",
                                summary=f"Market cap rank: {item.get('market_cap_rank')}, Score: {item.get('score')}",
                                source_url=f"https://coingecko.com/coins/{item.get('id')}",
                                source_name=source.name,
                                extracted_at=datetime.now().isoformat(),
                                confidence=0.8,
                                category=topic.category,
                                tags=['trending', 'crypto', item.get('symbol', '')],
                            )
                            entries.append(entry)

            elif 'dexscreener' in source.base_url:
                url = f"{source.base_url}/token-boosts/top/v1"
                async with self._session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for token in data[:5]:
                            if token.get('chainId') == 'solana':
                                entry = KnowledgeEntry(
                                    id=hashlib.md5(f"{token.get('tokenAddress')}-{time.time()}".encode()).hexdigest()[:12],
                                    topic=topic.topic,
                                    title=f"Boosted: {token.get('tokenAddress', '')[:12]}...",
                                    summary=f"Chain: {token.get('chainId')}, Amount: {token.get('amount')}",
                                    source_url=f"https://dexscreener.com/solana/{token.get('tokenAddress')}",
                                    source_name=source.name,
                                    extracted_at=datetime.now().isoformat(),
                                    confidence=0.7,
                                    category=topic.category,
                                    tags=['boosted', 'solana', 'dex'],
                                )
                                entries.append(entry)

            elif 'alternative.me' in source.base_url:
                async with self._session.get(source.base_url, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        fng = data.get('data', [{}])[0]
                        entry = KnowledgeEntry(
                            id=hashlib.md5(f"fng-{fng.get('timestamp')}".encode()).hexdigest()[:12],
                            topic="market sentiment",
                            title=f"Fear & Greed Index: {fng.get('value')}",
                            summary=f"Classification: {fng.get('value_classification')}",
                            source_url="https://alternative.me/crypto/fear-and-greed-index/",
                            source_name=source.name,
                            extracted_at=datetime.now().isoformat(),
                            confidence=0.9,
                            category="market",
                            tags=['sentiment', 'fear-greed', 'indicator'],
                            actionable=int(fng.get('value', 50)) <= 25 or int(fng.get('value', 50)) >= 75,
                            action_suggestion="Extreme fear = potential buy, Extreme greed = potential sell" if int(fng.get('value', 50)) <= 25 or int(fng.get('value', 50)) >= 75 else "",
                        )
                        entries.append(entry)

            elif 'hacker-news' in source.base_url:
                url = f"{source.base_url}/topstories.json"
                async with self._session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        story_ids = await resp.json()
                        for story_id in story_ids[:5]:
                            story_url = f"{source.base_url}/item/{story_id}.json"
                            async with self._session.get(story_url, timeout=5) as story_resp:
                                if story_resp.status == 200:
                                    story = await story_resp.json()
                                    # Check if relevant to topic keywords
                                    title = story.get('title', '').lower()
                                    if any(kw.lower() in title for kw in topic.keywords):
                                        entry = KnowledgeEntry(
                                            id=hashlib.md5(f"hn-{story_id}".encode()).hexdigest()[:12],
                                            topic=topic.topic,
                                            title=story.get('title', ''),
                                            summary=f"Score: {story.get('score')}, Comments: {story.get('descendants', 0)}",
                                            source_url=story.get('url', f"https://news.ycombinator.com/item?id={story_id}"),
                                            source_name=source.name,
                                            extracted_at=datetime.now().isoformat(),
                                            confidence=0.6,
                                            category="tech",
                                            tags=['hackernews', 'tech'],
                                        )
                                        entries.append(entry)

        except Exception as e:
            logger.error(f"API fetch error for {source.name}: {e}")

        return entries

    async def _fetch_web(self, source: ResearchSource, topic: ResearchTopic) -> List[KnowledgeEntry]:
        """Fetch from web source (basic scraping)."""
        # For production, use proper scraping with BeautifulSoup
        # This is a placeholder that returns empty for now
        return []

    async def _fetch_rss(self, source: ResearchSource, topic: ResearchTopic) -> List[KnowledgeEntry]:
        """Fetch from RSS feed."""
        # For production, use feedparser
        return []

    def get_actionable_insights(self) -> List[ActionableInsight]:
        """Get all actionable insights from knowledge base."""
        insights = []

        for entry in self.knowledge_base.values():
            if entry.actionable and entry.action_suggestion:
                insight = ActionableInsight(
                    insight=entry.title,
                    source=entry.source_name,
                    confidence=entry.confidence,
                    suggested_action=entry.action_suggestion,
                    urgency="medium" if entry.confidence > 0.7 else "low",
                )
                insights.append(insight)

        return insights

    def search_knowledge(self, query: str, limit: int = 10) -> List[KnowledgeEntry]:
        """Search the knowledge base."""
        results = []
        query_lower = query.lower()

        for entry in self.knowledge_base.values():
            score = 0
            if query_lower in entry.title.lower():
                score += 3
            if query_lower in entry.summary.lower():
                score += 2
            if any(query_lower in tag.lower() for tag in entry.tags):
                score += 1
            if query_lower in entry.topic.lower():
                score += 2

            if score > 0:
                results.append((score, entry))

        results.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in results[:limit]]

    async def run_research_cycle(self):
        """Run one research cycle."""
        topic = self.get_next_topic()
        if not topic:
            # Add default topics if queue empty
            self.add_topic("crypto market trends", priority=7, category="crypto",
                          keywords=["bitcoin", "solana", "ethereum", "defi"])
            self.add_topic("market sentiment", priority=8, category="market",
                          keywords=["fear", "greed", "sentiment"])
            topic = self.get_next_topic()

        if topic:
            logger.info(f"Researching: {topic.topic}")
            findings = await self.research_topic(topic)
            logger.info(f"Found {len(findings)} entries for {topic.topic}")

            # Remove completed topic (will be re-added if needed)
            try:
                self.topic_queue.remove(topic)
            except ValueError:
                pass

            return findings
        return []

    async def start_continuous(self, interval_seconds: int = 300):
        """Start continuous research loop."""
        self._running = True
        self._session = aiohttp.ClientSession()

        logger.info(f"Starting autonomous research (interval: {interval_seconds}s)")

        while self._running:
            try:
                await self.run_research_cycle()
            except Exception as e:
                logger.error(f"Research cycle error: {e}")

            await asyncio.sleep(interval_seconds)

        await self._session.close()

    def stop(self):
        """Stop the research agent."""
        self._running = False
        self._save_state()


# Singleton instance
_agent: Optional[AutonomousWebAgent] = None


def get_research_agent() -> AutonomousWebAgent:
    """Get singleton research agent."""
    global _agent
    if _agent is None:
        _agent = AutonomousWebAgent()
    return _agent


async def quick_research(topic: str) -> List[KnowledgeEntry]:
    """Quick one-off research on a topic."""
    agent = get_research_agent()
    agent.add_topic(topic, priority=10)
    return await agent.run_research_cycle()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    async def test():
        agent = get_research_agent()
        agent.add_topic("solana memecoins", priority=8, category="crypto",
                       keywords=["solana", "memecoin", "trending"])
        findings = await agent.run_research_cycle()
        print(f"\nFound {len(findings)} entries:")
        for entry in findings:
            print(f"  - {entry.title}")
            if entry.actionable:
                print(f"    ACTION: {entry.action_suggestion}")

    asyncio.run(test())
