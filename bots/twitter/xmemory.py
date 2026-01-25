"""
XMemory - Persistent Memory System for X/Twitter Bot

This module provides:
- Tweet storage and retrieval
- Novelty detection to avoid repetitive content
- Context tracking for conversations
- Topic tracking and trending detection
- Self-learning from engagement data

Used by the autonomous Twitter engine to maintain state and
prevent duplicate/repetitive content.
"""

import asyncio
import json
import logging
import sqlite3
import threading
import hashlib
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Configuration constants
NOVELTY_THRESHOLD = 0.4  # Minimum freshness score to consider content novel
TOPIC_COOLDOWN_HOURS = 4  # Hours before same topic can be discussed again
DEFAULT_RETENTION_DAYS = 30  # Days to retain fingerprints

# Default paths
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DEFAULT_DB_PATH = DATA_DIR / "jarvis_x_memory.db"


@dataclass
class TweetRecord:
    """A stored tweet record."""
    tweet_id: str
    content: str
    category: str
    cashtags: List[str]
    posted_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    engagement_likes: int = 0
    engagement_retweets: int = 0
    engagement_replies: int = 0
    reply_to: Optional[str] = None
    contract_address: Optional[str] = None

    @property
    def engagement_score(self) -> int:
        """Calculate engagement score: likes + retweets*2 + replies*3"""
        return self.engagement_likes + (self.engagement_retweets * 2) + (self.engagement_replies * 3)


@dataclass
class TopicStats:
    """Statistics for a tracked topic."""
    topic: str
    mention_count: int
    last_mentioned: str
    first_mentioned: Optional[str] = None
    avg_sentiment_score: float = 0.0
    sentiment_samples: int = 0


@dataclass
class NoveltyScore:
    """Result of novelty detection check."""
    score: float  # 0.0 = duplicate, 1.0 = completely novel
    is_novel: bool
    reason: str
    similar_tweet_id: Optional[str] = None


@dataclass
class ConversationContext:
    """Context for a conversation thread."""
    thread_id: str
    participants: List[str]
    messages: List[Dict[str, str]]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class XMemory:
    """
    Persistent memory system for X/Twitter interactions.

    Thread-safe SQLite storage for:
    - Posted tweets
    - Mention/reply tracking
    - Token mentions
    - Content fingerprints for duplicate detection
    - Engagement metrics for self-learning
    """

    def __init__(self, db_path: Path = None):
        """Initialize XMemory with database path."""
        self.db_path = db_path or DEFAULT_DB_PATH
        self._lock = threading.Lock()
        self._memory_store = None  # Lazy loaded
        self._init_db()

    def _get_memory_store(self):
        """Lazy load memory store to avoid circular imports."""
        if self._memory_store is None:
            try:
                from core.memory.dedup_store import get_memory_store
                self._memory_store = get_memory_store()
            except ImportError:
                logger.debug("MemoryStore not available, using local storage only")
                self._memory_store = None
        return self._memory_store

    def _init_db(self):
        """Initialize SQLite database schema."""
        with self._lock:
            # Ensure data directory exists
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            conn = None
            try:
                conn = sqlite3.connect(str(self.db_path))
                conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()

                # Posted tweets table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS tweets (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        tweet_id TEXT UNIQUE,
                        content TEXT,
                        category TEXT,
                        cashtags TEXT,
                        posted_at TEXT,
                        engagement_likes INTEGER DEFAULT 0,
                        engagement_retweets INTEGER DEFAULT 0,
                        engagement_replies INTEGER DEFAULT 0,
                        reply_to TEXT,
                        contract_address TEXT
                    )
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_tweets_category
                    ON tweets(category, posted_at)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_tweets_posted
                    ON tweets(posted_at)
                """)

                # Interactions/mentions tracking
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS interactions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        tweet_id TEXT,
                        user_handle TEXT,
                        user_id TEXT,
                        interaction_type TEXT,
                        our_response TEXT,
                        timestamp TEXT
                    )
                """)

                # Token mentions tracking
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS token_mentions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT,
                        contract_address TEXT,
                        sentiment TEXT,
                        first_mentioned TEXT,
                        last_mentioned TEXT,
                        mention_count INTEGER DEFAULT 1,
                        avg_sentiment_score REAL DEFAULT 0.0
                    )
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_token_symbol
                    ON token_mentions(symbol)
                """)

                # Content fingerprints for duplicate detection
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS content_fingerprints (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        fingerprint TEXT UNIQUE,
                        tokens TEXT,
                        prices TEXT,
                        topic_hash TEXT,
                        semantic_hash TEXT,
                        created_at TEXT,
                        tweet_id TEXT
                    )
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_fingerprint
                    ON content_fingerprints(fingerprint)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_topic_hash
                    ON content_fingerprints(topic_hash)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_semantic_hash
                    ON content_fingerprints(semantic_hash, created_at)
                """)

                # Users we've interacted with
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        handle TEXT UNIQUE,
                        user_id TEXT,
                        first_seen TEXT,
                        interaction_count INTEGER DEFAULT 0,
                        sentiment TEXT DEFAULT 'neutral',
                        notes TEXT
                    )
                """)

                # Mention replies tracking
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS mention_replies (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        tweet_id TEXT UNIQUE,
                        author_handle TEXT,
                        our_reply TEXT,
                        replied_at TEXT
                    )
                """)

                # External replies (replies to tweets we found)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS external_replies (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        original_tweet_id TEXT UNIQUE,
                        author_handle TEXT,
                        original_content TEXT,
                        our_reply TEXT,
                        our_tweet_id TEXT,
                        reply_type TEXT,
                        sentiment TEXT,
                        replied_at TEXT
                    )
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_external_reply_author
                    ON external_replies(author_handle)
                """)

                conn.commit()
                logger.debug(f"XMemory database initialized at {self.db_path}")
            finally:
                if conn:
                    conn.close()

    # =========================================================================
    # Tweet Storage
    # =========================================================================

    def store_tweet(
        self,
        tweet_id: str,
        content: str,
        category: str,
        cashtags: List[str],
        contract_address: str = None,
        reply_to: str = None
    ) -> bool:
        """Store a posted tweet."""
        with self._lock:
            conn = None
            try:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO tweets
                    (tweet_id, content, category, cashtags, posted_at, reply_to, contract_address)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    tweet_id,
                    content,
                    category,
                    json.dumps(cashtags or []),
                    datetime.now(timezone.utc).isoformat(),
                    reply_to,
                    contract_address
                ))
                conn.commit()
                return True
            except Exception as e:
                logger.error(f"Failed to store tweet: {e}")
                return False
            finally:
                if conn:
                    conn.close()

    def get_tweet(self, tweet_id: str) -> Optional[Dict]:
        """Get a tweet by ID."""
        with self._lock:
            conn = None
            try:
                conn = sqlite3.connect(str(self.db_path))
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM tweets WHERE tweet_id = ?", (tweet_id,))
                row = cursor.fetchone()
                if row:
                    result = dict(row)
                    result["cashtags"] = json.loads(result.get("cashtags", "[]"))
                    return result
                return None
            finally:
                if conn:
                    conn.close()

    def get_recent_tweets(self, hours: int = 24) -> List[Dict]:
        """Get tweets from the last N hours."""
        with self._lock:
            conn = None
            try:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
                cursor.execute("""
                    SELECT content, category, cashtags, posted_at, tweet_id
                    FROM tweets
                    WHERE posted_at > ?
                    ORDER BY posted_at DESC
                """, (cutoff,))
                rows = cursor.fetchall()
                return [{
                    "content": r[0],
                    "category": r[1],
                    "cashtags": json.loads(r[2]),
                    "posted_at": r[3],
                    "tweet_id": r[4]
                } for r in rows]
            finally:
                if conn:
                    conn.close()

    def get_total_tweet_count(self) -> int:
        """Get total number of tweets stored."""
        with self._lock:
            conn = None
            try:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM tweets")
                return cursor.fetchone()[0]
            finally:
                if conn:
                    conn.close()

    # =========================================================================
    # Novelty Detection
    # =========================================================================

    def is_similar_to_recent(
        self,
        content: str,
        hours: int = 48,
        threshold: float = 0.5
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if content is too similar to recent tweets.

        Returns:
            (is_similar, similar_content) - True if duplicate/similar found
        """
        content_lower = content.lower()

        # Extract entities
        def extract_entities(text: str) -> dict:
            text_lower = text.lower()
            entities = {}
            # Extract cashtags
            tokens = re.findall(r'\$([a-z]{2,10})\b', text_lower)
            entities['tokens'] = set(t.upper() for t in tokens)
            # Extract prices
            prices = re.findall(r'\$?([\d,]+\.?\d*)', text)
            entities['prices'] = set(p.replace(',', '') for p in prices if len(p) > 1)
            return entities

        new_entities = extract_entities(content)
        recent = self.get_recent_tweets(hours=hours)

        MAJOR_COINS = {'SOL', 'BTC', 'ETH', 'USDC', 'USDT'}

        for tweet in recent:
            old_entities = extract_entities(tweet["content"])

            # Check for same token + same price combo
            common_tokens = new_entities['tokens'] & old_entities['tokens']
            common_prices = new_entities['prices'] & old_entities['prices']
            non_major_common = common_tokens - MAJOR_COINS

            if non_major_common and common_prices:
                for token in non_major_common:
                    for price in common_prices:
                        try:
                            if float(price) > 0.0000001:
                                logger.debug(f"Duplicate: {token} at ${price}")
                                return True, tweet["content"]
                        except ValueError:
                            pass

            # Flag if 3+ non-major tokens in common
            if len(non_major_common) >= 3:
                return True, tweet["content"]

        # Jaccard similarity fallback
        def normalize(text: str) -> set:
            text = re.sub(r'https?://\S+', '', text.lower())
            text = re.sub(r'@\w+', '', text)
            text = re.sub(r'\$\w+', '', text)
            text = re.sub(r'[^\w\s]', '', text)
            return set(text.split())

        new_words = normalize(content)
        if not new_words:
            return False, None

        for tweet in recent:
            old_words = normalize(tweet["content"])
            if not old_words:
                continue

            intersection = len(new_words & old_words)
            union = len(new_words | old_words)
            similarity = intersection / union if union > 0 else 0

            if similarity >= threshold:
                return True, tweet["content"]

        return False, None

    def calculate_content_freshness(self, content: str, hours: int = 4) -> float:
        """
        Calculate freshness score for proposed content (0.0 to 1.0).

        Returns:
            float: 1.0 = completely unique, <0.3 = too similar
        """
        recent = self.get_recent_tweets(hours=hours)
        if not recent:
            return 1.0

        content_lower = content.lower()

        # Extract features
        new_cashtags = set(re.findall(r'\$([a-z]{2,10})\b', content_lower))
        new_concepts = self._extract_semantic_concepts(content)
        new_subjects = set(new_concepts.get("subjects", []))
        new_sentiment = new_concepts.get("sentiment", "unknown")
        new_words = set(re.sub(r'[^\w\s]', '', content_lower).split())

        max_similarity = 0.0
        MAJOR_COINS = {'sol', 'btc', 'eth', 'usdc', 'usdt'}

        for tweet in recent:
            old_content = tweet.get("content", "").lower()

            old_cashtags = set(re.findall(r'\$([a-z]{2,10})\b', old_content))
            old_concepts = self._extract_semantic_concepts(old_content)
            old_subjects = set(old_concepts.get("subjects", []))
            old_sentiment = old_concepts.get("sentiment", "unknown")
            old_words = set(re.sub(r'[^\w\s]', '', old_content).split())

            # Cashtag overlap
            new_non_major = new_cashtags - MAJOR_COINS
            old_non_major = old_cashtags - MAJOR_COINS
            if new_non_major and old_non_major:
                cashtag_overlap = len(new_non_major & old_non_major) / max(len(new_non_major), 1)
            else:
                cashtag_overlap = 0.0

            # Subject overlap
            if new_subjects and old_subjects:
                subject_overlap = len(new_subjects & old_subjects) / max(len(new_subjects | old_subjects), 1)
            else:
                subject_overlap = 0.0

            # Sentiment match
            sentiment_match = 1.0 if new_sentiment == old_sentiment != "unknown" else 0.0

            # Word overlap
            if new_words and old_words:
                word_overlap = len(new_words & old_words) / max(len(new_words | old_words), 1)
            else:
                word_overlap = 0.0

            # Weighted similarity
            similarity = (
                cashtag_overlap * 0.35 +
                subject_overlap * 0.25 +
                sentiment_match * 0.15 +
                word_overlap * 0.25
            )
            max_similarity = max(max_similarity, similarity)

        return round(1.0 - max_similarity, 2)

    def _extract_semantic_concepts(self, content: str) -> Dict[str, Any]:
        """Extract semantic concepts from content."""
        content_lower = content.lower()

        # Sentiment detection
        bullish_words = {'bullish', 'green', 'pump', 'moon', 'up', 'gains', 'rally', 'breakout',
                        'higher', 'rip', 'send', 'long', 'buy', 'accumulate', 'strong', 'explosive'}
        bearish_words = {'bearish', 'red', 'dump', 'crash', 'down', 'losses', 'sell', 'short',
                        'lower', 'weak', 'fear', 'capitulation', 'breakdown', 'correction'}
        neutral_words = {'sideways', 'consolidation', 'range', 'flat', 'choppy', 'uncertain'}

        words = set(content_lower.split())
        bullish_count = len(words & bullish_words)
        bearish_count = len(words & bearish_words)
        neutral_count = len(words & neutral_words)

        if bullish_count > bearish_count and bullish_count > neutral_count:
            sentiment = 'bullish'
        elif bearish_count > bullish_count and bearish_count > neutral_count:
            sentiment = 'bearish'
        elif neutral_count > 0:
            sentiment = 'neutral'
        else:
            sentiment = 'unknown'

        # Subject detection
        subjects = set()
        if any(w in content_lower for w in ['market', 'charts', 'candle', 'price action', 'trading']):
            subjects.add('market_general')
        if any(w in content_lower for w in ['btc', 'bitcoin', 'sats']):
            subjects.add('btc')
        if any(w in content_lower for w in ['eth', 'ethereum']):
            subjects.add('eth')
        if any(w in content_lower for w in ['sol', 'solana']):
            subjects.add('sol')
        if any(w in content_lower for w in ['altcoin', 'alt', 'microcap', 'lowcap', 'gem']):
            subjects.add('altcoins')
        if any(w in content_lower for w in ['agent', 'ai', 'autonomous', 'agentic', 'mcp']):
            subjects.add('agentic')
        if any(w in content_lower for w in ['morning', 'gm', 'good morning']):
            subjects.add('morning')
        if any(w in content_lower for w in ['night', 'gn', 'evening', 'wrap']):
            subjects.add('evening')
        if any(w in content_lower for w in ['weekend', 'saturday', 'sunday']):
            subjects.add('weekend')
        if any(w in content_lower for w in ['macro', 'fed', 'rates', 'inflation', 'economy']):
            subjects.add('macro')

        if not subjects:
            subjects.add('general')

        # Tone detection
        if any(w in content_lower for w in ['lol', 'lmao', 'joke', 'funny', 'haha']):
            tone = 'humorous'
        elif any(w in content_lower for w in ['warning', 'careful', 'risk', 'caution']):
            tone = 'cautionary'
        elif any(w in content_lower for w in ['alpha', 'signal', 'calling', 'watch']):
            tone = 'signal'
        else:
            tone = 'commentary'

        return {
            'sentiment': sentiment,
            'subjects': sorted(subjects),
            'tone': tone
        }

    # =========================================================================
    # Context Tracking
    # =========================================================================

    def record_mention_reply(self, tweet_id: str, author: str, reply: str):
        """Record that we replied to a mention."""
        with self._lock:
            conn = None
            try:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO mention_replies
                    (tweet_id, author_handle, our_reply, replied_at)
                    VALUES (?, ?, ?, ?)
                """, (tweet_id, author, reply, datetime.now(timezone.utc).isoformat()))
                conn.commit()
            finally:
                if conn:
                    conn.close()

    def was_mention_replied(self, tweet_id: str) -> bool:
        """Check if we already replied to a mention."""
        with self._lock:
            conn = None
            try:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM mention_replies WHERE tweet_id = ?", (tweet_id,))
                return cursor.fetchone() is not None
            finally:
                if conn:
                    conn.close()

    def record_external_reply(
        self,
        original_tweet_id: str,
        author: str,
        original_content: str,
        our_reply: str,
        our_tweet_id: str,
        reply_type: str = "witty",
        sentiment: str = "neutral"
    ):
        """Record that we replied to an external tweet."""
        with self._lock:
            conn = None
            try:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO external_replies
                    (original_tweet_id, author_handle, original_content, our_reply,
                     our_tweet_id, reply_type, sentiment, replied_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    original_tweet_id, author, original_content, our_reply,
                    our_tweet_id, reply_type, sentiment,
                    datetime.now(timezone.utc).isoformat()
                ))
                conn.commit()
            finally:
                if conn:
                    conn.close()

    def was_externally_replied(self, tweet_id: str) -> bool:
        """Check if we already replied to an external tweet."""
        with self._lock:
            conn = None
            try:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM external_replies WHERE original_tweet_id = ?", (tweet_id,))
                return cursor.fetchone() is not None
            finally:
                if conn:
                    conn.close()

    def get_recent_reply_count(self, hours: int = 1) -> int:
        """Get count of replies in the last N hours."""
        with self._lock:
            conn = None
            try:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
                cursor.execute("""
                    SELECT COUNT(*) FROM external_replies WHERE replied_at > ?
                """, (cutoff,))
                return cursor.fetchone()[0]
            finally:
                if conn:
                    conn.close()

    def was_author_replied_recently(self, author: str, hours: int = 6) -> bool:
        """Check if we recently replied to this author."""
        with self._lock:
            conn = None
            try:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
                cursor.execute("""
                    SELECT 1 FROM external_replies
                    WHERE author_handle = ? AND replied_at > ?
                """, (author, cutoff))
                return cursor.fetchone() is not None
            finally:
                if conn:
                    conn.close()

    # =========================================================================
    # Topic Tracking
    # =========================================================================

    def record_token_mention(
        self,
        symbol: str,
        contract: str,
        sentiment: str,
        price: float = 0.0
    ):
        """Record that we mentioned a token."""
        with self._lock:
            conn = None
            try:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                now = datetime.now(timezone.utc).isoformat()

                cursor.execute("SELECT id, mention_count FROM token_mentions WHERE symbol = ?", (symbol,))
                row = cursor.fetchone()

                if row:
                    cursor.execute("""
                        UPDATE token_mentions
                        SET last_mentioned = ?, mention_count = mention_count + 1
                        WHERE symbol = ?
                    """, (now, symbol))
                else:
                    cursor.execute("""
                        INSERT INTO token_mentions
                        (symbol, contract_address, sentiment, first_mentioned, last_mentioned)
                        VALUES (?, ?, ?, ?, ?)
                    """, (symbol, contract, sentiment, now, now))

                conn.commit()
            finally:
                if conn:
                    conn.close()

    def was_recently_mentioned(self, symbol: str, hours: int = 4) -> bool:
        """Check if we mentioned a token recently."""
        with self._lock:
            conn = None
            try:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
                cursor.execute("""
                    SELECT 1 FROM token_mentions
                    WHERE symbol = ? AND last_mentioned > ?
                """, (symbol, cutoff))
                return cursor.fetchone() is not None
            finally:
                if conn:
                    conn.close()

    def is_topic_on_cooldown(self, topic: str) -> bool:
        """Check if topic is on cooldown."""
        return self.was_recently_mentioned(topic, hours=TOPIC_COOLDOWN_HOURS)

    def get_recent_topics(self, hours: int = 2) -> Dict[str, Any]:
        """Get topics from recent tweets."""
        recent = self.get_recent_tweets(hours=hours)

        topics = {
            "cashtags": set(),
            "categories": [],
            "subjects": set(),
            "sentiments": [],
        }

        for tweet in recent:
            content = tweet.get("content", "")
            category = tweet.get("category", "")

            # Extract cashtags
            cashtags = re.findall(r'\$([A-Za-z]{2,10})\b', content)
            topics["cashtags"].update(t.upper() for t in cashtags)

            if category:
                topics["categories"].append(category)

            concepts = self._extract_semantic_concepts(content)
            topics["subjects"].update(concepts.get("subjects", []))
            topics["sentiments"].append(concepts.get("sentiment", "unknown"))

        return topics

    # =========================================================================
    # Content Fingerprints
    # =========================================================================

    def _generate_content_fingerprint(self, content: str) -> Tuple[str, str, str, str, str]:
        """
        Generate fingerprint for duplicate detection.

        Returns:
            (fingerprint, tokens_str, prices_str, topic_hash, semantic_hash)
        """
        content_lower = content.lower()

        # Extract tokens
        tokens = set(re.findall(r'\$([a-z]{2,10})\b', content_lower))
        tokens.update(t.upper() for t in re.findall(
            r'\b(btc|eth|sol|bnb|xrp|ada|doge|shib|avax|matic|dot|link)\b',
            content_lower
        ))
        tokens = sorted(tokens - {'THE', 'AND', 'FOR', 'ARE', 'ITS', 'HAS', 'WAS', 'BUT', 'NOT', 'NFA', 'DYOR'})

        # Extract prices
        prices = sorted(set(re.findall(r'\$?([\d,]+\.?\d{0,6})', content)))
        prices = [p.replace(',', '') for p in prices if len(p) > 1 and float(p.replace(',', '') or 0) > 0.0001]

        # Topic hash
        price_ranges = []
        for p in prices[:3]:
            try:
                val = float(p)
                if val < 1:
                    price_ranges.append("sub1")
                elif val < 100:
                    price_ranges.append("sub100")
                elif val < 1000:
                    price_ranges.append("sub1k")
                else:
                    price_ranges.append("1k+")
            except ValueError:
                pass

        topic_str = f"{'-'.join(tokens[:5])}_{'_'.join(price_ranges)}"
        topic_hash = hashlib.md5(topic_str.encode()).hexdigest()[:12]

        # Full fingerprint
        fingerprint_str = f"{'-'.join(tokens)}|{'-'.join(prices[:5])}"
        fingerprint = hashlib.sha256(fingerprint_str.encode()).hexdigest()[:24]

        # Semantic hash
        semantic = self._extract_semantic_concepts(content)
        semantic_str = f"{semantic['sentiment']}|{'-'.join(semantic['subjects'])}|{semantic['tone']}"
        semantic_hash = hashlib.md5(semantic_str.encode()).hexdigest()[:12]

        return fingerprint, ','.join(tokens), ','.join(prices[:5]), topic_hash, semantic_hash

    async def is_duplicate_fingerprint(self, content: str, hours: int = 24) -> Tuple[bool, Optional[str]]:
        """Check if content fingerprint exists (async)."""
        fingerprint, tokens, prices, topic_hash, semantic_hash = self._generate_content_fingerprint(content)

        memory_store = self._get_memory_store()
        if memory_store:
            try:
                from core.memory.dedup_store import MemoryType
                entity_id = ','.join(tokens.split(',')[:5]) if tokens else "general"

                is_dup, reason = await memory_store.is_duplicate(
                    content=content,
                    entity_id=entity_id,
                    entity_type="tweet",
                    memory_type=MemoryType.DUPLICATE_CONTENT,
                    hours=hours,
                    similarity_threshold=NOVELTY_THRESHOLD
                )
                if is_dup:
                    return True, reason
            except Exception as e:
                logger.debug(f"MemoryStore check failed: {e}")

        # Fallback to local DB
        with self._lock:
            conn = None
            try:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

                # Check exact fingerprint
                cursor.execute("""
                    SELECT tweet_id FROM content_fingerprints
                    WHERE fingerprint = ? AND created_at > ?
                """, (fingerprint, cutoff))
                if cursor.fetchone():
                    return True, "Exact fingerprint match"

                # Check topic hash
                cursor.execute("""
                    SELECT tweet_id FROM content_fingerprints
                    WHERE topic_hash = ? AND created_at > ?
                """, (topic_hash, cutoff))
                if cursor.fetchone():
                    return True, "Topic hash match"

                # Check semantic hash
                cursor.execute("""
                    SELECT tweet_id FROM content_fingerprints
                    WHERE semantic_hash = ? AND created_at > ?
                """, (semantic_hash, cutoff))
                if cursor.fetchone():
                    return True, "Semantic hash match"

                return False, None
            finally:
                if conn:
                    conn.close()

    async def record_content_fingerprint(self, content: str, tweet_id: str):
        """Record content fingerprint for duplicate detection."""
        fingerprint, tokens, prices, topic_hash, semantic_hash = self._generate_content_fingerprint(content)

        memory_store = self._get_memory_store()
        if memory_store:
            try:
                from core.memory.dedup_store import MemoryEntry, MemoryType
                entity_id = ','.join(tokens.split(',')[:5]) if tokens else "general"

                entry = MemoryEntry(
                    content=content,
                    memory_type=MemoryType.DUPLICATE_CONTENT,
                    entity_id=entity_id,
                    entity_type="tweet",
                    fingerprint=fingerprint,
                    semantic_hash=semantic_hash,
                    topic_hash=topic_hash,
                    metadata={
                        "tweet_id": tweet_id,
                        "tokens": tokens,
                        "prices": prices,
                    }
                )
                await memory_store.store(entry)
            except Exception as e:
                logger.debug(f"MemoryStore record failed: {e}")

        # Also store locally
        with self._lock:
            conn = None
            try:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO content_fingerprints
                    (fingerprint, tokens, prices, topic_hash, semantic_hash, created_at, tweet_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    fingerprint, tokens, prices, topic_hash, semantic_hash,
                    datetime.now(timezone.utc).isoformat(), tweet_id
                ))
                conn.commit()
            finally:
                if conn:
                    conn.close()

    async def cleanup_old_fingerprints(self, days: int = DEFAULT_RETENTION_DAYS):
        """Clean up old fingerprints."""
        memory_store = self._get_memory_store()
        if memory_store:
            try:
                deleted = await memory_store.cleanup_expired()
                if deleted > 0:
                    logger.info(f"Cleaned up {deleted} expired fingerprints")
            except Exception as e:
                logger.debug(f"MemoryStore cleanup failed: {e}")

        # Also clean local DB
        with self._lock:
            conn = None
            try:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
                cursor.execute("DELETE FROM content_fingerprints WHERE created_at < ?", (cutoff,))
                conn.commit()
            finally:
                if conn:
                    conn.close()

    # =========================================================================
    # Self-Learning
    # =========================================================================

    def update_tweet_engagement(self, tweet_id: str, likes: int, retweets: int, replies: int):
        """Update engagement metrics for a tweet."""
        with self._lock:
            conn = None
            try:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE tweets SET
                        engagement_likes = ?,
                        engagement_retweets = ?,
                        engagement_replies = ?
                    WHERE tweet_id = ?
                """, (likes, retweets, replies, tweet_id))
                conn.commit()
            finally:
                if conn:
                    conn.close()

    def get_tweets_needing_metrics(self, min_age_hours: int = 2, max_age_days: int = 7) -> List[Dict]:
        """Get tweets that need metrics updated."""
        with self._lock:
            conn = None
            try:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()

                min_cutoff = (datetime.now(timezone.utc) - timedelta(hours=min_age_hours)).isoformat()
                max_cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()

                cursor.execute("""
                    SELECT tweet_id, category, posted_at, engagement_likes
                    FROM tweets
                    WHERE posted_at < ? AND posted_at > ?
                    ORDER BY posted_at DESC
                    LIMIT 50
                """, (min_cutoff, max_cutoff))

                return [{
                    "tweet_id": r[0],
                    "category": r[1],
                    "posted_at": r[2],
                    "current_likes": r[3]
                } for r in cursor.fetchall()]
            finally:
                if conn:
                    conn.close()

    def get_performance_by_category(self, days: int = 14) -> Dict[str, Dict]:
        """Analyze performance by content category."""
        with self._lock:
            conn = None
            try:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()

                cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

                cursor.execute("""
                    SELECT category,
                           COUNT(*) as count,
                           AVG(engagement_likes) as avg_likes,
                           AVG(engagement_retweets) as avg_retweets,
                           AVG(engagement_replies) as avg_replies,
                           SUM(engagement_likes + engagement_retweets * 2 + engagement_replies * 3) as engagement_score
                    FROM tweets
                    WHERE posted_at > ? AND engagement_likes > 0
                    GROUP BY category
                    ORDER BY engagement_score DESC
                """, (cutoff,))

                results = {}
                for row in cursor.fetchall():
                    results[row[0]] = {
                        "count": row[1],
                        "avg_likes": round(row[2] or 0, 1),
                        "avg_retweets": round(row[3] or 0, 1),
                        "avg_replies": round(row[4] or 0, 1),
                        "engagement_score": row[5] or 0
                    }

                return results
            finally:
                if conn:
                    conn.close()

    def get_top_performing_tweets(self, days: int = 7, limit: int = 5) -> List[Dict]:
        """Get top performing tweets."""
        with self._lock:
            conn = None
            try:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()

                cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

                cursor.execute("""
                    SELECT tweet_id, content, category,
                           engagement_likes, engagement_retweets, engagement_replies,
                           (engagement_likes + engagement_retweets * 2 + engagement_replies * 3) as score
                    FROM tweets
                    WHERE posted_at > ?
                    ORDER BY score DESC
                    LIMIT ?
                """, (cutoff, limit))

                return [{
                    "tweet_id": r[0],
                    "content": r[1],
                    "category": r[2],
                    "likes": r[3],
                    "retweets": r[4],
                    "replies": r[5],
                    "score": r[6]
                } for r in cursor.fetchall()]
            finally:
                if conn:
                    conn.close()

    def get_underperforming_patterns(self, days: int = 14) -> List[str]:
        """Identify content patterns that underperform."""
        performance = self.get_performance_by_category(days)
        if not performance:
            return []

        all_scores = [p["engagement_score"] for p in performance.values()]
        avg_score = sum(all_scores) / len(all_scores) if all_scores else 0

        underperformers = []
        for category, stats in performance.items():
            if stats["engagement_score"] < avg_score * 0.5 and stats["count"] >= 3:
                underperformers.append(category)

        return underperformers

    def get_learning_insights(self) -> Dict[str, Any]:
        """Generate learning insights for optimization."""
        performance = self.get_performance_by_category(days=14)
        top_tweets = self.get_top_performing_tweets(days=7)
        underperformers = self.get_underperforming_patterns(days=14)

        ranked = sorted(performance.items(), key=lambda x: x[1]["engagement_score"], reverse=True)

        insights = {
            "top_categories": [c for c, _ in ranked[:3]],
            "underperforming": underperformers,
            "recommendations": [],
            "top_tweets_analysis": []
        }

        if ranked:
            best_cat = ranked[0][0]
            insights["recommendations"].append(f"Prioritize '{best_cat}' content - highest engagement")

        if underperformers:
            insights["recommendations"].append(f"Reduce '{underperformers[0]}' tweets - low engagement")

        for tweet in top_tweets[:3]:
            if tweet.get("content"):
                content = tweet["content"]
                patterns = []
                if len(content) < 150:
                    patterns.append("short_form")
                if "$" in content:
                    patterns.append("has_cashtag")
                if "?" in content:
                    patterns.append("asks_question")
                insights["top_tweets_analysis"].append({
                    "category": tweet["category"],
                    "score": tweet["score"],
                    "patterns": patterns
                })

        return insights

    def get_posting_stats(self) -> Dict:
        """Get posting statistics."""
        with self._lock:
            conn = None
            try:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()

                cursor.execute("SELECT COUNT(*) FROM tweets")
                total = cursor.fetchone()[0]

                today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                cursor.execute("SELECT COUNT(*) FROM tweets WHERE posted_at LIKE ?", (f"{today}%",))
                today_count = cursor.fetchone()[0]

                cursor.execute("SELECT category, COUNT(*) FROM tweets GROUP BY category")
                by_category = {r[0]: r[1] for r in cursor.fetchall()}

                cursor.execute("SELECT COUNT(*) FROM mention_replies")
                replies_sent = cursor.fetchone()[0]

                return {
                    "total_tweets": total,
                    "today_tweets": today_count,
                    "by_category": by_category,
                    "replies_sent": replies_sent
                }
            finally:
                if conn:
                    conn.close()
