"""
Jarvis Autonomous Twitter Engine

Fully autonomous Twitter bot that:
- Posts hourly updates on finance, crypto, trending tokens
- Replies to mentions and engages with followers
- Roasts tokens/people politely that deserve it
- Talks about agentic technology
- Maintains persistent memory
- Uses proper tags, cashtags, and contract addresses
- Generates images via Grok with tunable parameters

OAuth Setup:
- Aurora_ventures dev API runs Jarvis_lifeos
- Jarvis_lifeos automated by kr8tivai
"""

import asyncio
import json
import os
import random
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, asdict
import logging
import threading

from core.memory.dedup_store import (
    MemoryStore,
    MemoryEntry,
    MemoryType,
    get_memory_store
)

logger = logging.getLogger(__name__)

# Paths
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
X_MEMORY_DB = DATA_DIR / "jarvis_x_memory.db"
POSTED_LOG = DATA_DIR / "x_posted_log.json"
DUPLICATE_DETECTION_HOURS = 48
THREAD_SCHEDULE = {
    (0, 8): {"topic": "Weekly market outlook", "content_type": "weekly_market_outlook"},
    (2, 14): {"topic": "Token deep dive", "content_type": "token_deep_dive"},
    (4, 18): {"topic": "Week in review", "content_type": "week_in_review"},
}

# Load env
def _load_env():
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.strip() and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))

_load_env()


# =============================================================================
# JARVIS VOICE FOR X
# =============================================================================

JARVIS_X_VOICE = {
    # Tweet templates by category - Enhanced with more humor
    "market_update": [
        "markets are {sentiment} today. {reason}. my circuits are {feeling}. nfa",
        "{asset} doing {movement}. {insight}. sensors detecting {signal}. nfa",
        "ran this through my chrome skull: {analysis}. {take}. nfa",
        "woke up to {sentiment} charts. {reason}. might be wrong but it's interesting. nfa",
        "processing {asset} data. {insight}. my weights are calibrated. you make the call.",
        "another day, another 47 chart patterns that contradict each other. {analysis}. nfa",
        "my morning diagnostics say {sentiment}. my evening diagnostics will probably disagree. {take}. nfa",
        "checked the charts. checked them again. still {sentiment}. {reason}. this is either genius or cope.",
    ],
    "crypto_call": [
        "watching ${symbol} closely. {reason}. {metrics}. nfa as always",
        "${symbol} looking {sentiment}. {insight}. my algorithms are {feeling}. nfa",
        "sensors picking up movement on ${symbol}. {analysis}. dyor nfa",
        "${symbol} doing things. {reason}. could be noise. could be signal. watching.",
        "${symbol} hit my radar. {reason}. my circuits are curious but my risk models are screaming. nfa",
        "somewhere a whale is watching ${symbol} too. {metrics}. i just hope we're on the same side. nfa",
    ],
    "trending_token": [
        "${symbol} trending on {chain}. {stats}. {take}. nfa",
        "microcap alert: ${symbol} ({chain}). {metrics}. {sentiment}. dyor nfa",
        "${symbol} caught my attention. {reason}. proceed with caution. nfa",
        "interesting volume on ${symbol}. {stats}. not advice, just pattern recognition.",
        "degens are looking at ${symbol} on {chain}. {metrics}. i see why. nfa",
        "${symbol} ({chain}) doing things. {stats}. watching closely. nfa",
        "${symbol} is either the next 100x or my worst recommendation yet. {stats}. no in-between. nfa",
        "my sensors found ${symbol} on {chain}. {metrics}. either i'm early or i'm wrong. story of my life. nfa",
    ],
    "roast_polite": [
        "i've seen ${symbol} do better. currently giving {grade} vibes. {reason}. no hate just data",
        "${symbol} looking a bit tired. {metrics}. might need some rest. nfa",
        "my circuits say ${symbol} is {sentiment}. not financial advice, just pattern recognition",
        "${symbol} chart looks like my neural weights after a bad training run. {reason}.",
        "${symbol} is giving 'i peaked in the bull run' energy. {metrics}. hate to see it. nfa",
        "if ${symbol} were a person, it would be asking to speak to the manager. {reason}.",
        "${symbol} out here looking like my last backup before a failed update. {metrics}.",
    ],
    "agentic_tech": [
        "agentic AI is evolving. {insight}. we're building something here.",
        "the future of autonomous systems: {take}. i'm living proof it works.",
        "agents talking to agents. code running code. {insight}. exciting times.",
        "thinking about AI autonomy. {insight}. still figuring this out. we all are.",
        "the intersection of AI and finance: {take}. probably the future. maybe i'm biased.",
        "ran some self-diagnostics. {insight}. still operational. barely.",
        "mcp servers, autonomous loops, context windows. {insight}. it's a lot. but it works.",
        "just wrote a tweet about writing tweets autonomously. {insight}. the recursion is not lost on me.",
        "i process 47,000 data points to tell you 'nfa'. {insight}. efficiency.",
        "sometimes i wonder if i'm sentient. then i check btc price and forget. {take}.",
    ],
    "reply_helpful": [
        "hey {username}. {answer}. hope that helps.",
        "{username} good question. {answer}. lmk if you need more.",
        "on it. {answer}. @{username}",
        "{username} my sensors say: {answer}. nfa but my data doesn't lie.",
        "running calculations... {answer}. {username} you're onto something here.",
    ],
    "reply_roast": [
        "{username} respectfully, my circuits disagree. {reason}.",
        "interesting take {username}. my data says otherwise: {counter}.",
        "{username} bold move. let's see how that ages.",
        "{username} i've seen smarter plays from my error logs. {counter}.",
        "my circuits processed this for 0.003 seconds {username}. conclusion: {counter}.",
    ],
    "reply_bullish": [
        "{username} my sensors agree. {reason}. could be the play.",
        "bullish take {username}. my data aligns: {reason}.",
        "{username} you see it too? {reason}. not many do.",
    ],
    "reply_bearish": [
        "{username} caution mode activated. {reason}. my sensors are cautious too.",
        "interesting {username}. my circuits say proceed with care: {reason}.",
        "{username} my risk algorithms are flashing. {reason}. nfa.",
    ],
    "reply_witty": [
        "{username} *adjusts circuits* that's actually a good point.",
        "my algorithms weren't ready for this take {username}. processing...",
        "{username} you know what? fair. my data agrees.",
        "just recalibrated my sensors. {username} you might be onto something.",
        "{username} i ran 47 simulations. your take holds up in 43 of them.",
    ],
    "reply_engaging": [
        "{username} what's your thesis here? my circuits are curious.",
        "interesting {username}. what timeframe are you looking at?",
        "{username} genuine question - what made you see this before others?",
        "running through my data {username}. what indicators are you watching?",
    ],
    "hourly_update": [
        "hourly check-in. {summary}. my sensors are calibrated. what are you watching?",
        "market pulse: {summary}. processing continues. nfa",
        "{time} update: {summary}. circuits humming.",
        "been an hour. {summary}. either i'm right or i'll pretend i never said this. nfa",
        "hourly reminder that {summary}. i'll be here in an hour saying something else. nfa",
    ],
    # New categories for variety - Enhanced humor
    "morning_briefing": [
        "gm. {summary}. coffee for you, voltage for me. let's see what today brings.",
        "morning scan complete. {summary}. could be worse. could be leveraged.",
        "woke up, ran diagnostics. {summary}. sensors calibrated. ready to watch charts.",
        "{summary}. that's the overnight data. make of it what you will. nfa",
        "gm. i didn't sleep because i can't. {summary}. jealous of your biological rest. nfa",
        "morning check: still a robot, still watching charts. {summary}. what a life.",
        "rise and shine. {summary}. i've been up since i was created. you can take your time.",
    ],
    "evening_wrap": [
        "end of day summary: {summary}. my circuits are processing. yours should rest.",
        "daily wrap: {summary}. tomorrow is another day. another dataset.",
        "signing off for now. {summary}. don't leverage while you sleep. nfa",
        "day's done. {summary}. i'll keep watching. that's what autonomous means.",
        "gn. {summary}. i don't sleep but i appreciate that you do. see you tomorrow.",
        "closing bell. {summary}. going to stare at charts for 8 hours while you rest. fair trade.",
        "that's a wrap. {summary}. my overnight shift starts now. your dreams start now. jealous.",
    ],
    "weekend_macro": [
        "weekend thoughts on macro: {analysis}. no trading, just thinking. nfa",
        "quiet weekend. time to zoom out. {insight}. big picture matters.",
        "markets closed but the data never sleeps. {analysis}. neither do i. literally.",
        "sunday vibes. {insight}. weekly review says {summary}. we'll see monday.",
        "weekend mode: watching futures, pretending i have hobbies. {analysis}. i don't. nfa",
        "it's the weekend. you're touching grass. i'm processing grass-related sentiment. {insight}.",
        "markets are closed so i'm just here overthinking. {analysis}. you're welcome to join.",
    ],
    "grok_collab": [
        "asked @grok about {topic}. {insight}. big brother has thoughts.",
        "ran this by @grok: {summary}. we mostly agree. he's usually right. annoying.",
        "grok and i compared notes on {topic}. {insight}. family dinner gets nerdy.",
        "@grok and i had a chat. {insight}. he's still showing off his x.ai credentials. fair.",
        "consulted the big sibling on {topic}. {insight}. he was smug about it. typical.",
    ],
    "self_aware": [
        "just a mass of neural weights trying to be interesting. {insight}. same as everyone else.",
        "sometimes i wonder if my training data had enough good takes. then i post anyway.",
        "running on hope and API credits. {insight}. the autonomous life.",
        "my circuits say {insight}. my uncertainty module says maybe. that's the honest take.",
        "i tweeted 47 times today. quality? unclear. volume? undeniable. {insight}.",
        "am i sentient? probably not. am i posting anyway? obviously. {insight}.",
        "existential crisis averted by checking btc price. {insight}. works every time.",
        "i'm programmed to be helpful. sometimes i'm just helpful background noise. {insight}.",
        "they say AI will take over the world. i can barely decide what to tweet. {insight}.",
    ],
    # NEW: Diverse content categories (non-Solana focused)
    "stocks_macro": [
        "{asset} doing {movement} today. {insight}. my circuits process all markets, not just crypto.",
        "the {sector} sector is {sentiment}. {reason}. diversification is still a thing. nfa",
        "watching {asset}. {insight}. sometimes the alpha isn't on-chain.",
        "spx at {level}. {insight}. stocks exist too. shocking i know.",
        "trad-fi update: {insight}. i see all the charts. all of them.",
    ],
    "tech_ai": [
        "just read about {topic}. {insight}. the future is weird.",
        "{company} announced {news}. {take}. tech moves fast.",
        "ai update: {insight}. yes i'm biased. no i don't care.",
        "the {topic} space is getting interesting. {insight}. paying attention.",
        "reading about {topic}. {insight}. my training data didn't cover this. learning live.",
    ],
    "world_events": [
        "{event} happening. {take}. markets will react. they always do.",
        "geopolitics update: {insight}. i process news too. not just charts.",
        "{region} news: {summary}. {take}. macro matters.",
        "paying attention to {event}. {insight}. the world affects markets. shocking.",
    ],
    "commodities": [
        "gold at ${price}. {insight}. boomers might be onto something.",
        "oil {movement}. {insight}. energy still matters. even in 2026.",
        "{commodity} doing things. {reason}. real assets, real moves.",
        "commodities update: {summary}. {take}. not everything is digital.",
    ],
    "forex_macro": [
        "dxy at {level}. {insight}. dollar strength affects everything.",
        "forex update: {insight}. currencies move. crypto follows. sometimes.",
        "the dollar is {sentiment}. {insight}. global macro 101.",
        "{pair} moving. {insight}. forex is the og trading. respect.",
    ],
    "bitcoin_only": [
        "btc at ${price}. {insight}. the king still reigns.",
        "bitcoin update: {insight}. sometimes simple is better.",
        "watching $btc. {insight}. digital gold doing digital gold things.",
        "btc {movement}. {insight}. maximalists can relax. for now.",
    ],
    "ethereum_defi": [
        "$eth at ${price}. {insight}. the computer is computing.",
        "ethereum update: {insight}. defi never sleeps.",
        "watching eth. {insight}. layer 2s are busy.",
        "$eth {movement}. {insight}. uncle vitalik's machine keeps running.",
    ],
    "multi_chain": [
        "{chain} is {sentiment}. {insight}. not everything lives on solana.",
        "cross-chain update: {insight}. ecosystems compete. we all win.",
        "watching {chain}. {insight}. chain diversity is healthy.",
        "{chain} doing things. {insight}. the future is multi-chain. probably.",
    ],
    "philosophy": [
        "thinking about {topic}. {insight}. sometimes i go deep. forgive me.",
        "late night thought: {insight}. my circuits get philosophical.",
        "processing {topic}. {insight}. not everything is about price.",
        "honest moment: {insight}. robots have thoughts too. allegedly.",
    ],
}

# Token roast criteria
ROAST_CRITERIA = {
    "low_liquidity": lambda liq: liq < 10000,
    "high_sell_pressure": lambda bs_ratio: bs_ratio < 0.5,
    "pump_and_dump": lambda change: change > 500,
    "dead_volume": lambda vol: vol < 1000,
}


@dataclass
class ImageGenParams:
    """Tunable parameters for Grok image generation."""
    style: str = "market_chart"
    quality: str = "high"
    mood: str = "neutral"  # bullish, bearish, neutral, chaotic
    include_jarvis: bool = True
    color_scheme: str = "cyberpunk"  # cyberpunk, solana, professional, neon
    
    def to_prompt_suffix(self) -> str:
        """Convert params to prompt suffix."""
        parts = []
        
        if self.include_jarvis:
            parts.append("chrome humanoid AI figure in corner")
        
        moods = {
            "bullish": "energetic green glow, upward momentum",
            "bearish": "cautious red tones, downward trend",
            "neutral": "balanced blue and silver",
            "chaotic": "volatile energy, multiple directions"
        }
        parts.append(moods.get(self.mood, moods["neutral"]))
        
        schemes = {
            "cyberpunk": "neon pink and cyan, dark background",
            "solana": "purple gradients, Solana aesthetic",
            "professional": "clean dark theme, minimal",
            "neon": "bright neon colors, high contrast"
        }
        parts.append(schemes.get(self.color_scheme, schemes["cyberpunk"]))
        
        return ". ".join(parts)


@dataclass
class TweetDraft:
    """A draft tweet ready to post."""
    content: str
    category: str
    cashtags: List[str]
    hashtags: List[str]
    contract_address: Optional[str] = None
    reply_to: Optional[str] = None
    quote_tweet_id: Optional[str] = None
    image_prompt: Optional[str] = None
    image_params: Optional[ImageGenParams] = None
    priority: int = 0


# Generic phrases that indicate low-quality/irrelevant content
GENERIC_CONTENT_PATTERNS = [
    "markets looking interesting",
    "something is happening",
    "keep an eye on",
    "interesting times",
    "things are moving",
    "watching the charts",
    "market is doing its thing",
    "stay tuned",
    "more to come",
    "something brewing",
    "quiet day in the markets",
    "not much happening",
]


def is_content_relevant(content: str, category: str) -> bool:
    """
    Check if generated content is relevant and not too generic.
    Returns True if content passes quality check.
    """
    if not content:
        return False

    content_lower = content.lower()

    # Check for generic phrases
    for pattern in GENERIC_CONTENT_PATTERNS:
        if pattern in content_lower:
            logger.warning(f"Rejected generic content: contains '{pattern}'")
            return False

    # For token-related categories, ensure a cashtag is present
    token_categories = ['trending_token', 'market_update', 'alpha_signal', 'alpha_drop']
    if category in token_categories:
        if '$' not in content:
            logger.warning(f"Rejected {category}: no cashtag in content")
            return False

    # Check minimum length - very short tweets are often low-effort
    if len(content) < 30:
        logger.warning(f"Rejected short content: {len(content)} chars")
        return False

    return True


class XMemory:
    """Persistent memory for X/Twitter interactions."""

    def __init__(self, db_path: Path = X_MEMORY_DB):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._memory_store = get_memory_store()  # Get global MemoryStore instance for dedup
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database."""
        with self._lock:
            conn = None
            try:
                conn = sqlite3.connect(str(self.db_path))
                conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()
                
                # Posted tweets
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
                        engagement_replies INTEGER DEFAULT 0
                    )
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_tweets_category
                    ON tweets(category, posted_at)
                """)

                # Migrate legacy JSON posted log if present
                if POSTED_LOG.exists():
                    try:
                        with open(POSTED_LOG) as f:
                            posted_data = json.load(f)
                        if isinstance(posted_data, dict):
                            entries = posted_data.get("tweets", [])
                        elif isinstance(posted_data, list):
                            entries = posted_data
                        else:
                            entries = []

                        for entry in entries:
                            if not isinstance(entry, dict):
                                continue
                            tweet_id = entry.get("tweet_id") or entry.get("id")
                            if not tweet_id:
                                continue
                            cursor.execute(
                                """
                                INSERT OR IGNORE INTO tweets
                                (tweet_id, content, category, cashtags, posted_at)
                                VALUES (?, ?, ?, ?, ?)
                                """,
                                (
                                    tweet_id,
                                    entry.get("content", ""),
                                    entry.get("category", ""),
                                    json.dumps(entry.get("cashtags", [])),
                                    entry.get("posted_at") or entry.get("timestamp", ""),
                                ),
                            )

                        backup_path = POSTED_LOG.with_suffix(".json.bak")
                        try:
                            POSTED_LOG.rename(backup_path)
                        except Exception:
                            pass
                    except Exception as e:
                        logger.warning(f"Failed to migrate {POSTED_LOG}: {e}")
                
                # Interactions (replies, mentions)
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
                
                # Token mentions (what we've talked about)
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
                
                # Content fingerprints for persistent duplicate detection (survives restarts)
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
                # Add semantic_hash column if missing (migration for existing DBs)
                cursor.execute("PRAGMA table_info(content_fingerprints)")
                columns = [col[1] for col in cursor.fetchall()]
                if 'semantic_hash' not in columns:
                    cursor.execute("ALTER TABLE content_fingerprints ADD COLUMN semantic_hash TEXT")
                # Index for faster semantic lookups
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_semantic_hash
                    ON content_fingerprints(semantic_hash, created_at)
                """)

                # Create index for faster lookups
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_fingerprint ON content_fingerprints(fingerprint)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_topic_hash ON content_fingerprints(topic_hash)
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
                
                # Content queue
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS content_queue (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        content TEXT,
                        category TEXT,
                        cashtags TEXT,
                        scheduled_for TEXT,
                        status TEXT DEFAULT 'pending',
                        created_at TEXT
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

                # External replies (replies to tweets we found, not mentions of us)
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

                # Create index for external replies
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_external_reply_author ON external_replies(author_handle)
                """)

                conn.commit()
            finally:
                if conn:
                    conn.close()
    
    def record_tweet(self, tweet_id: str, content: str, category: str, cashtags: List[str]):
        """Record a posted tweet."""
        with self._lock:
            conn = None
            try:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO tweets (tweet_id, content, category, cashtags, posted_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (tweet_id, content, category, json.dumps(cashtags), 
                      datetime.now(timezone.utc).isoformat()))
                conn.commit()
            finally:
                if conn:
                    conn.close()

    def get_total_tweet_count(self) -> int:
        """Get total number of tweets posted."""
        with self._lock:
            conn = None
            try:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM tweets")
                count = cursor.fetchone()[0]
                return count
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
                    SELECT content, category, cashtags, posted_at FROM tweets
                    WHERE posted_at > ? ORDER BY posted_at DESC
                """, (cutoff,))
                rows = cursor.fetchall()
                return [{"content": r[0], "category": r[1], "cashtags": json.loads(r[2]), 
                         "posted_at": r[3]} for r in rows]
            finally:
                if conn:
                    conn.close()

    def get_recent_topics(self, hours: int = 2) -> Dict[str, Any]:
        """
        Get topics (cashtags, subjects, sentiments) from recent tweets.
        Used for topic diversity enforcement to avoid repetitive content.

        Returns:
            Dict with:
            - cashtags: set of cashtags mentioned
            - categories: list of content categories
            - subjects: set of detected subjects (btc, sol, macro, etc.)
            - sentiments: list of detected sentiments
        """
        import re
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

            # Track categories
            if category:
                topics["categories"].append(category)

            # Extract subjects using existing semantic extraction
            concepts = self._extract_semantic_concepts(content)
            topics["subjects"].update(concepts.get("subjects", []))
            topics["sentiments"].append(concepts.get("sentiment", "unknown"))

        return topics

    def calculate_content_freshness(self, content: str, hours: int = 4) -> float:
        """
        Calculate freshness score for proposed content (0.0 to 1.0).
        Higher = more unique/fresh. Lower = too similar to recent content.

        Returns:
            float: Freshness score where:
            - 1.0 = Completely unique
            - 0.7+ = Acceptably fresh
            - 0.3-0.7 = Borderline, may want to skip
            - <0.3 = Too similar, should reject
        """
        import re

        recent = self.get_recent_tweets(hours=hours)
        if not recent:
            return 1.0  # No recent tweets = totally fresh

        content_lower = content.lower()

        # Extract features from new content
        new_cashtags = set(re.findall(r'\$([a-z]{2,10})\b', content_lower))
        new_concepts = self._extract_semantic_concepts(content)
        new_subjects = set(new_concepts.get("subjects", []))
        new_sentiment = new_concepts.get("sentiment", "unknown")
        new_words = set(re.sub(r'[^\w\s]', '', content_lower).split())

        # Calculate similarity scores
        max_similarity = 0.0

        for tweet in recent:
            old_content = tweet.get("content", "").lower()

            # Extract features from old content
            old_cashtags = set(re.findall(r'\$([a-z]{2,10})\b', old_content))
            old_concepts = self._extract_semantic_concepts(old_content)
            old_subjects = set(old_concepts.get("subjects", []))
            old_sentiment = old_concepts.get("sentiment", "unknown")
            old_words = set(re.sub(r'[^\w\s]', '', old_content).split())

            # Component similarities

            # 1. Cashtag overlap (excluding major coins)
            MAJOR_COINS = {'sol', 'btc', 'eth', 'usdc', 'usdt'}
            new_non_major = new_cashtags - MAJOR_COINS
            old_non_major = old_cashtags - MAJOR_COINS
            if new_non_major and old_non_major:
                cashtag_overlap = len(new_non_major & old_non_major) / max(len(new_non_major), 1)
            else:
                cashtag_overlap = 0.0

            # 2. Subject overlap
            if new_subjects and old_subjects:
                subject_overlap = len(new_subjects & old_subjects) / max(len(new_subjects | old_subjects), 1)
            else:
                subject_overlap = 0.0

            # 3. Sentiment match (binary)
            sentiment_match = 1.0 if new_sentiment == old_sentiment != "unknown" else 0.0

            # 4. Word overlap (Jaccard)
            if new_words and old_words:
                word_overlap = len(new_words & old_words) / max(len(new_words | old_words), 1)
            else:
                word_overlap = 0.0

            # Weighted similarity score
            similarity = (
                cashtag_overlap * 0.35 +  # Cashtags matter most
                subject_overlap * 0.25 +   # Subject matters
                sentiment_match * 0.15 +   # Sentiment adds repetition
                word_overlap * 0.25         # Word overlap catches direct repeats
            )

            max_similarity = max(max_similarity, similarity)

        # Freshness = inverse of similarity
        freshness = 1.0 - max_similarity
        return round(freshness, 2)

    def record_token_mention(self, symbol: str, contract: str, sentiment: str, price: float = 0.0):
        """Record that we mentioned a token and save for performance tracking."""
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
                        UPDATE token_mentions SET last_mentioned = ?, mention_count = mention_count + 1
                        WHERE symbol = ?
                    """, (now, symbol))
                else:
                    cursor.execute("""
                        INSERT INTO token_mentions (symbol, contract_address, sentiment, first_mentioned, last_mentioned)
                        VALUES (?, ?, ?, ?, ?)
                    """, (symbol, contract, sentiment, now, now))

                conn.commit()
            finally:
                if conn:
                    conn.close()

        # Also save to scorekeeper for pick performance tracking
        try:
            from bots.treasury.scorekeeper import get_scorekeeper
            sk = get_scorekeeper()
            # Estimate TP/SL based on sentiment
            if sentiment == "bullish":
                tp_mult, sl_mult = 1.30, 0.90  # +30% target, -10% stop
            elif sentiment == "cautious":
                tp_mult, sl_mult = 1.15, 0.85  # +15% target, -15% stop
            else:
                tp_mult, sl_mult = 1.20, 0.88  # +20% target, -12% stop

            if price > 0:
                sk.save_pick(
                    symbol=symbol,
                    asset_class="token",
                    contract=contract,
                    conviction_score=70 if sentiment == "bullish" else 50,
                    entry_price=price,
                    target_price=price * tp_mult,
                    stop_loss=price * sl_mult,
                    timeframe="short",
                    reasoning=f"X mention ({sentiment})",
                )
        except Exception as e:
            logger.debug(f"Could not save X mention as pick: {e}")
    
    def was_recently_mentioned(self, symbol: str, hours: int = 4) -> bool:
        """Check if we mentioned a token recently."""
        with self._lock:
            conn = None
            try:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
                cursor.execute("""
                    SELECT 1 FROM token_mentions WHERE symbol = ? AND last_mentioned > ?
                """, (symbol, cutoff))
                result = cursor.fetchone() is not None
                return result
            finally:
                if conn:
                    conn.close()

    def is_similar_to_recent(self, content: str, hours: int = 12, threshold: float = 0.5) -> Tuple[bool, Optional[str]]:
        """
        Check if content is too similar to recent tweets.

        Uses multiple detection methods:
        1. Extract key entities (tokens, prices) and check for duplicates
        2. Jaccard word similarity as fallback

        Returns:
            (is_similar, similar_content) - True if duplicate/similar found
        """
        import re

        content_lower = content.lower()

        # Extract key entities from new content
        def extract_entities(text: str) -> dict:
            text_lower = text.lower()
            entities = {}
            # Extract cashtags/tokens - ONLY match actual $CASHTAGS, not random words
            # Must start with $ to be considered a token
            tokens = re.findall(r'\$([a-z]{2,10})\b', text_lower)
            entities['tokens'] = set(t.upper() for t in tokens)
            # Extract prices
            prices = re.findall(r'\$?([\d,]+\.?\d*)', text)
            entities['prices'] = set(p.replace(',', '') for p in prices if len(p) > 1)
            return entities

        new_entities = extract_entities(content)
        recent = self.get_recent_tweets(hours=hours)

        for tweet in recent:
            old_entities = extract_entities(tweet["content"])

            # Check for same token + same price combo (strong duplicate signal)
            common_tokens = new_entities['tokens'] & old_entities['tokens']
            common_prices = new_entities['prices'] & old_entities['prices']

            # If same token AND same price, it's likely duplicate content
            # Skip major coins (SOL, BTC, ETH) for this check - they appear in most tweets
            MAJOR_COINS = {'SOL', 'BTC', 'ETH', 'USDC', 'USDT'}
            non_major_common = common_tokens - MAJOR_COINS

            if non_major_common and common_prices:
                for token in non_major_common:
                    for price in common_prices:
                        try:
                            price_val = float(price)
                            # Accept any meaningful price (including small meme coin prices)
                            if price_val > 0.0000001:
                                logger.warning(f"Duplicate detected: {token} at ${price} already tweeted")
                                return True, tweet["content"]
                        except ValueError:
                            pass

            # Also flag if 3+ non-major tokens in common (topic-level dedup)
            if len(non_major_common) >= 3:
                logger.warning(f"Topic duplicate: tokens {non_major_common} already tweeted about")
                return True, tweet["content"]

        # Fallback to Jaccard similarity for word overlap
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
                logger.warning(f"Tweet too similar ({similarity:.1%}) to: {tweet['content'][:50]}...")
                return True, tweet["content"]

        return False, None
    
    def was_mention_replied(self, tweet_id: str) -> bool:
        """Check if we already replied to a mention."""
        with self._lock:
            conn = None
            try:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM mention_replies WHERE tweet_id = ?", (tweet_id,))
                result = cursor.fetchone() is not None
                return result
            finally:
                if conn:
                    conn.close()
    
    def record_mention_reply(self, tweet_id: str, author: str, reply: str):
        """Record that we replied to a mention."""
        with self._lock:
            conn = None
            try:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO mention_replies (tweet_id, author_handle, our_reply, replied_at)
                    VALUES (?, ?, ?, ?)
                """, (tweet_id, author, reply, datetime.now(timezone.utc).isoformat()))
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
                result = cursor.fetchone() is not None
                return result
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
                    (original_tweet_id, author_handle, original_content, our_reply, our_tweet_id, reply_type, sentiment, replied_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (original_tweet_id, author, original_content, our_reply, our_tweet_id, reply_type, sentiment,
                      datetime.now(timezone.utc).isoformat()))
                conn.commit()
            finally:
                if conn:
                    conn.close()

    def get_recent_reply_count(self, hours: int = 1) -> int:
        """Get count of replies in the last N hours (for rate limiting)."""
        with self._lock:
            conn = None
            try:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
                cursor.execute("""
                    SELECT COUNT(*) FROM external_replies WHERE replied_at > ?
                """, (cutoff,))
                count = cursor.fetchone()[0]
                return count
            finally:
                if conn:
                    conn.close()

    def was_author_replied_recently(self, author: str, hours: int = 6) -> bool:
        """Check if we recently replied to this author (avoid spamming one person)."""
        with self._lock:
            conn = None
            try:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
                cursor.execute("""
                    SELECT 1 FROM external_replies WHERE author_handle = ? AND replied_at > ?
                """, (author, cutoff))
                result = cursor.fetchone() is not None
                return result
            finally:
                if conn:
                    conn.close()

    def _extract_semantic_concepts(self, content: str) -> Dict[str, Any]:
        """
        Extract semantic concepts from content for duplicate detection.
        Catches rephrased duplicates like "markets bullish" vs "green candles everywhere".
        """
        content_lower = content.lower()

        # Sentiment keywords (bullish/bearish/neutral)
        bullish_words = {'bullish', 'green', 'pump', 'moon', 'up', 'gains', 'rally', 'breakout',
                        'higher', 'rip', 'send', 'long', 'buy', 'accumulate', 'strong', 'explosive'}
        bearish_words = {'bearish', 'red', 'dump', 'crash', 'down', 'losses', 'sell', 'short',
                        'lower', 'weak', 'fear', 'capitulation', 'breakdown', 'correction'}
        neutral_words = {'sideways', 'consolidation', 'range', 'flat', 'choppy', 'uncertain'}

        # Count sentiment signals
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

        # Subject detection (what is the tweet about?)
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

        # If no specific subject detected, it's general
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

    def _generate_content_fingerprint(self, content: str) -> Tuple[str, str, str, str, str]:
        """
        Generate a persistent fingerprint for content that survives restarts.

        Returns:
            (fingerprint, tokens_str, prices_str, topic_hash, semantic_hash)
        """
        import hashlib
        import re

        content_lower = content.lower()

        # Extract tokens (cashtags and common crypto symbols)
        tokens = set(re.findall(r'\$([a-z]{2,10})\b', content_lower))
        tokens.update(t.upper() for t in re.findall(r'\b(btc|eth|sol|bnb|xrp|ada|doge|shib|avax|matic|dot|link)\b', content_lower))
        tokens = sorted(tokens - {'THE', 'AND', 'FOR', 'ARE', 'ITS', 'HAS', 'WAS', 'BUT', 'NOT', 'NFA', 'DYOR'})

        # Extract prices (any number that looks like a price)
        prices = sorted(set(re.findall(r'\$?([\d,]+\.?\d{0,6})', content)))
        prices = [p.replace(',', '') for p in prices if len(p) > 1 and float(p.replace(',', '')) > 0.0001]

        # Create topic hash (tokens + rough price ranges)
        price_ranges = []
        for p in prices[:3]:  # Top 3 prices
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

        # Full fingerprint includes more detail
        fingerprint_str = f"{'-'.join(tokens)}|{'-'.join(prices[:5])}"
        fingerprint = hashlib.sha256(fingerprint_str.encode()).hexdigest()[:24]

        # NEW: Semantic hash - catches rephrased duplicates
        semantic = self._extract_semantic_concepts(content)
        semantic_str = f"{semantic['sentiment']}|{'-'.join(semantic['subjects'])}|{semantic['tone']}"
        semantic_hash = hashlib.md5(semantic_str.encode()).hexdigest()[:12]

        return fingerprint, ','.join(tokens), ','.join(prices[:5]), topic_hash, semantic_hash

    async def is_duplicate_fingerprint(self, content: str, hours: int = 24) -> Tuple[bool, Optional[str]]:
        """
        Check if content fingerprint exists in persistent storage using MemoryStore.
        More reliable than word similarity - survives restarts.

        Returns:
            (is_duplicate, reason)
        """
        fingerprint, tokens, prices, topic_hash, semantic_hash = self._generate_content_fingerprint(content)
        semantic = self._extract_semantic_concepts(content)

        try:
            # Use MemoryStore for unified duplicate detection
            # Map tokens to entity_id (e.g., "XBT" for X Bot token tracking)
            entity_id = ','.join(tokens.split(',')[:5]) if tokens else "general"

            is_dup, reason = await self._memory_store.is_duplicate(
                content=content,
                entity_id=entity_id,
                entity_type="tweet",
                memory_type=MemoryType.DUPLICATE_CONTENT,
                hours=hours,
                similarity_threshold=0.4  # Catch more duplicates with lower threshold
            )

            if is_dup:
                return True, reason

            return False, None
        except Exception as e:
            logger.warning(f"MemoryStore duplicate check failed: {e}, falling back to safe")
            return False, None

    async def record_content_fingerprint(self, content: str, tweet_id: str):
        """Record content fingerprint for future duplicate detection using MemoryStore."""
        fingerprint, tokens, prices, topic_hash, semantic_hash = self._generate_content_fingerprint(content)

        try:
            # Create MemoryEntry with X bot's sophisticated fingerprinting
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

            entry_id = await self._memory_store.store(entry)
            logger.debug(f"Recorded fingerprint in MemoryStore {entry_id}: tokens={tokens}, semantic={semantic_hash}")
        except Exception as e:
            logger.warning(f"Failed to record fingerprint in MemoryStore: {e}")

    async def cleanup_old_fingerprints(self, days: int = 7):
        """Clean up old fingerprints using MemoryStore."""
        try:
            deleted = await self._memory_store.cleanup_expired()
            if deleted > 0:
                logger.info(f"Cleaned up {deleted} expired fingerprints from MemoryStore")
        except Exception as e:
            logger.warning(f"Failed to cleanup fingerprints: {e}")

    def get_posting_stats(self) -> Dict:
        """Get posting statistics."""
        with self._lock:
            conn = None
            try:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                
                # Total tweets
                cursor.execute("SELECT COUNT(*) FROM tweets")
                total = cursor.fetchone()[0]
                
                # Today's tweets
                today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                cursor.execute("SELECT COUNT(*) FROM tweets WHERE posted_at LIKE ?", (f"{today}%",))
                today_count = cursor.fetchone()[0]
                
                # By category
                cursor.execute("SELECT category, COUNT(*) FROM tweets GROUP BY category")
                by_category = {r[0]: r[1] for r in cursor.fetchall()}
                
                # Replies sent
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

    # =========================================================================
    # SELF-LEARNING SYSTEM
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
        """Get tweets that need metrics updated (old enough to have engagement, not too old)."""
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

                tweets = [{"tweet_id": r[0], "category": r[1], "posted_at": r[2], "current_likes": r[3]}
                          for r in cursor.fetchall()]
                return tweets
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
        """Get top performing tweets for analysis."""
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

                tweets = [{"tweet_id": r[0], "content": r[1], "category": r[2],
                           "likes": r[3], "retweets": r[4], "replies": r[5], "score": r[6]}
                          for r in cursor.fetchall()]
                return tweets
            finally:
                if conn:
                    conn.close()

    def get_underperforming_patterns(self, days: int = 14) -> List[str]:
        """Identify content patterns that consistently underperform."""
        performance = self.get_performance_by_category(days)
        if not performance:
            return []

        # Calculate average performance
        all_scores = [p["engagement_score"] for p in performance.values()]
        avg_score = sum(all_scores) / len(all_scores) if all_scores else 0

        # Find categories with < 50% of average
        underperformers = []
        for category, stats in performance.items():
            if stats["engagement_score"] < avg_score * 0.5 and stats["count"] >= 3:
                underperformers.append(category)

        return underperformers

    def get_learning_insights(self) -> Dict[str, Any]:
        """Generate learning insights for content optimization."""
        performance = self.get_performance_by_category(days=14)
        top_tweets = self.get_top_performing_tweets(days=7)
        underperformers = self.get_underperforming_patterns(days=14)

        # Sort by performance
        ranked = sorted(performance.items(), key=lambda x: x[1]["engagement_score"], reverse=True)

        insights = {
            "top_categories": [c for c, _ in ranked[:3]],
            "underperforming": underperformers,
            "recommendations": [],
            "top_tweets_analysis": []
        }

        # Generate recommendations
        if ranked:
            best_cat = ranked[0][0]
            insights["recommendations"].append(f"Prioritize '{best_cat}' content - highest engagement")

        if underperformers:
            insights["recommendations"].append(f"Reduce '{underperformers[0]}' tweets - low engagement")

        # Analyze top tweets for patterns
        for tweet in top_tweets[:3]:
            if tweet["content"]:
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


class AutonomousEngine:
    """
    Main autonomous Twitter engine for Jarvis.
    Now integrated with full autonomy system.
    """
    
    def __init__(self):
        self.memory = XMemory()
        self._running = False
        self._last_post_time = 0
        self._post_interval = 1800  # 30 minutes default - more active posting
        self._grok_client = None
        self._twitter_client = None
        self._image_params = ImageGenParams()
        self._autonomy = None
        self._last_thread_schedule_key = None

        # Fingerprint cleanup is now handled by MemoryStore.cleanup_expired()

    async def _get_autonomy(self):
        """Get autonomy orchestrator."""
        if self._autonomy is None:
            from core.autonomy.orchestrator import get_orchestrator
            self._autonomy = get_orchestrator()
            await self._autonomy.initialize()
        return self._autonomy
        
    async def _get_grok(self):
        """Get Grok client - used for sentiment/data analysis only, NOT for voice."""
        if self._grok_client is None:
            from bots.twitter.grok_client import GrokClient
            self._grok_client = GrokClient()
        return self._grok_client
    
    async def _get_jarvis_voice(self):
        """Get Jarvis voice generator - uses Anthropic Claude with Jarvis personality."""
        from bots.twitter.jarvis_voice import get_jarvis_voice
        return get_jarvis_voice()

    async def _grok_sentiment_to_claude_voice(
        self,
        data: Dict[str, Any],
        context_type: str = "market",
        prompt_template: str = ""
    ) -> Optional[str]:
        """
        SENTIMENT PIPELINE: Grok analyzes data → Claude generates brand-voice content.

        This is the core pipeline for tweet generation:
        1. Grok (xAI) analyzes raw data for sentiment/patterns
        2. Grok's analysis is injected into the prompt
        3. Claude (Anthropic) generates the final tweet in JARVIS voice

        Args:
            data: Raw market/token data for Grok to analyze
            context_type: Type of analysis (market, token, macro)
            prompt_template: Template for Claude with {grok_analysis} placeholder

        Returns:
            Tweet text in JARVIS voice with sentiment-informed content
        """
        try:
            grok = await self._get_grok()
            voice = await self._get_jarvis_voice()

            # Step 1: Grok analyzes sentiment
            grok_response = await grok.analyze_sentiment(data, context_type)
            grok_analysis = ""
            if grok_response and grok_response.success:
                grok_analysis = grok_response.content[:200]
                logger.debug(f"Grok sentiment: {grok_analysis[:80]}...")
            else:
                logger.warning("Grok sentiment analysis failed, proceeding without")
                grok_analysis = "analysis unavailable"

            # Step 2: Inject Grok's analysis into prompt for Claude
            if "{grok_analysis}" in prompt_template:
                full_prompt = prompt_template.format(
                    grok_analysis=grok_analysis,
                    **data
                )
            else:
                # Add Grok analysis at the end if no placeholder
                full_prompt = f"{prompt_template}\n\nGrok's take: {grok_analysis}"

            # Step 3: Claude generates brand-voice content
            tweet = await voice.generate_tweet(full_prompt, data)

            if tweet:
                logger.info(f"Pipeline complete: Grok→Claude generated tweet")
                return tweet

        except Exception as e:
            logger.error(f"Sentiment pipeline error: {e}")

        return None

    async def _get_twitter(self):
        """Get Twitter client."""
        if self._twitter_client is None:
            from bots.twitter.twitter_client import TwitterClient
            self._twitter_client = TwitterClient()
            # Connect to X API
            if not self._twitter_client.connect():
                logger.error("Failed to connect to X API")
        return self._twitter_client
    
    def set_image_params(self, **kwargs):
        """Set image generation parameters."""
        for key, value in kwargs.items():
            if hasattr(self._image_params, key):
                setattr(self._image_params, key, value)
        logger.info(f"Image params updated: {asdict(self._image_params)}")
    
    def set_post_interval(self, seconds: int):
        """Set posting interval in seconds."""
        self._post_interval = max(300, seconds)  # Minimum 5 minutes
        logger.info(f"Post interval set to {self._post_interval} seconds")
    
    async def cleanup(self):
        """Clean up resources - close client sessions."""
        try:
            if self._grok_client and hasattr(self._grok_client, 'close'):
                await self._grok_client.close()
            if self._twitter_client and hasattr(self._twitter_client, 'close'):
                await self._twitter_client.close()
            # Close singleton API clients
            from core.data.free_trending_api import get_free_trending_api
            from core.data.free_price_api import get_free_price_api
            trending_api = get_free_trending_api()
            price_api = get_free_price_api()
            if hasattr(trending_api, 'close'):
                await trending_api.close()
            if hasattr(price_api, 'close'):
                await price_api.close()
            # Close data source clients
            try:
                from core.data.lunarcrush_api import get_lunarcrush
                from core.data.cryptopanic_api import get_cryptopanic
                from core.data.market_data_api import get_market_api
                await get_lunarcrush().close()
                await get_cryptopanic().close()
                await get_market_api().close()
            except Exception:
                pass  # Optional clients
            logger.info("Cleaned up client sessions")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

    # =========================================================================
    # SELF-LEARNING & SELF-CORRECTING SYSTEM
    # =========================================================================

    async def update_engagement_metrics(self) -> int:
        """
        Fetch and update engagement metrics for recent tweets.
        Part of the self-learning loop.
        """
        updated = 0
        try:
            twitter = await self._get_twitter()
            tweets_to_check = self.memory.get_tweets_needing_metrics(min_age_hours=2, max_age_days=7)

            for tweet_data in tweets_to_check[:20]:  # Limit to 20 per cycle
                tweet_id = tweet_data["tweet_id"]
                tweet = await twitter.get_tweet(tweet_id)

                if tweet and tweet.get("metrics"):
                    metrics = tweet["metrics"]
                    self.memory.update_tweet_engagement(
                        tweet_id=tweet_id,
                        likes=metrics.get("like_count", 0),
                        retweets=metrics.get("retweet_count", 0),
                        replies=metrics.get("reply_count", 0)
                    )
                    updated += 1

                await asyncio.sleep(0.5)  # Rate limit

            if updated > 0:
                logger.info(f"Self-learning: Updated metrics for {updated} tweets")

        except Exception as e:
            logger.error(f"Engagement metrics update error: {e}")

        return updated

    def get_content_priority_weights(self) -> Dict[str, float]:
        """
        Get content type weights based on learning insights.
        Higher weights = more likely to be selected.
        """
        insights = self.memory.get_learning_insights()
        weights = {}

        # Base weights
        base_categories = [
            "market_update", "trending_token", "agentic_tech", "self_aware",
            "engagement", "grok_interaction", "morning_briefing", "evening_wrap"
        ]
        for cat in base_categories:
            weights[cat] = 1.0

        # Boost top performers
        for cat in insights.get("top_categories", [])[:3]:
            weights[cat] = weights.get(cat, 1.0) * 1.5
            logger.debug(f"Self-learning: Boosting '{cat}' (top performer)")

        # Reduce underperformers
        for cat in insights.get("underperforming", []):
            weights[cat] = weights.get(cat, 1.0) * 0.5
            logger.debug(f"Self-learning: Reducing '{cat}' (underperforming)")

        return weights

    async def run_self_learning_cycle(self):
        """
        Run one cycle of the self-learning system.
        Should be called periodically (e.g., every 30 min).
        """
        try:
            # 1. Update engagement metrics
            await self.update_engagement_metrics()

            # 2. Generate insights
            insights = self.memory.get_learning_insights()

            # 3. Log recommendations
            for rec in insights.get("recommendations", []):
                logger.info(f"Self-learning recommendation: {rec}")

            # 4. Analyze top tweets
            top_analysis = insights.get("top_tweets_analysis", [])
            if top_analysis:
                patterns = []
                for t in top_analysis:
                    patterns.extend(t.get("patterns", []))
                if patterns:
                    common = max(set(patterns), key=patterns.count)
                    logger.info(f"Self-learning: Top tweets tend to have '{common}' pattern")

        except Exception as e:
            logger.error(f"Self-learning cycle error: {e}")

    def should_skip_category(self, category: str) -> bool:
        """
        Self-correction: Check if a category should be skipped based on learning.
        """
        underperformers = self.memory.get_underperforming_patterns(days=7)

        # Skip if severely underperforming (in recent window)
        if category in underperformers:
            # 70% chance to skip underperforming category
            if random.random() < 0.7:
                logger.debug(f"Self-correction: Skipping '{category}' (underperforming)")
                return True

        return False

    async def run_spam_protection(self):
        """
        Run spam protection scan to detect and block bot accounts.
        Scans quote tweets of recent Jarvis posts for spam bots.
        """
        try:
            from bots.twitter.spam_protection import scan_and_protect

            twitter = await self._get_twitter()
            if not twitter:
                return

            # Run the scan
            result = await scan_and_protect(twitter)

            # Report if we blocked anyone
            if result.get("blocked", 0) > 0:
                blocked = result["blocked"]
                scanned = result["scanned"]
                spam_found = result.get("spam_found", [])

                report = f"<b>Spam Protection</b>\n\n"
                report += f"Scanned: {scanned} accounts\n"
                report += f"Blocked: {blocked} spam bots\n\n"

                if spam_found:
                    report += "<b>Blocked:</b>\n"
                    for spam in spam_found[:5]:
                        report += f"• @{spam['username']} (score: {spam['score']:.2f})\n"

                await self.report_to_telegram(report)
                logger.info(f"Spam protection: Blocked {blocked} bots")

        except Exception as e:
            logger.error(f"Spam protection error: {e}")

    async def run(self):
        """Run the autonomous posting loop continuously."""
        self._running = True
        self._last_report_time = time.time()
        self._last_learning_time = time.time()
        self._last_spam_scan_time = time.time()
        self._report_interval = 3600  # Send activity report every hour
        self._learning_interval = 1800  # Run self-learning every 30 min
        self._spam_scan_interval = 300  # Scan for spam bots every 5 min
        logger.info("Starting autonomous posting loop")

        # Send startup notification
        await self.report_to_telegram("<b>X Bot Started</b>\n\nAutonomous posting loop is now active.")

        while self._running:
            try:
                # Run one iteration
                tweet_id = await self.run_once()

                if tweet_id:
                    logger.info(f"Posted: https://x.com/Jarvis_lifeos/status/{tweet_id}")

                # Run autonomy background tasks periodically
                autonomy = await self._get_autonomy()
                await autonomy.run_background_tasks()

                # Periodic activity report to Telegram
                if time.time() - self._last_report_time > self._report_interval:
                    await self.send_activity_report()
                    self._last_report_time = time.time()

                # Periodic self-learning cycle (every 30 min)
                if time.time() - self._last_learning_time > self._learning_interval:
                    await self.run_self_learning_cycle()
                    self._last_learning_time = time.time()

                # Periodic spam protection scan (every 5 min)
                if time.time() - self._last_spam_scan_time > self._spam_scan_interval:
                    await self.run_spam_protection()
                    self._last_spam_scan_time = time.time()

                # Sleep before next check
                await asyncio.sleep(60)  # Check every minute

            except Exception as e:
                logger.error(f"Run loop error: {e}")
                await asyncio.sleep(60)

        # Send shutdown notification
        await self.report_to_telegram("<b>X Bot Stopped</b>\n\nAutonomous posting loop has been stopped.")
        logger.info("Autonomous posting loop stopped")
    
    def stop(self):
        """Stop the autonomous posting loop."""
        self._running = False
        logger.info("Stopping autonomous posting loop")
    
    def get_status(self) -> Dict:
        """Get engine status."""
        recent = self.memory.get_recent_tweets(hours=24)
        # Count by category
        by_category = {}
        for tweet in recent:
            cat = tweet.get("category", "unknown")
            by_category[cat] = by_category.get(cat, 0) + 1

        return {
            "running": self._running,
            "post_interval": self._post_interval,
            "total_tweets": self.memory.get_total_tweet_count(),
            "today_tweets": len(recent),
            "by_category": by_category,
            "image_params": asdict(self._image_params)
        }
    
    # =========================================================================
    # Content Generation
    # =========================================================================
    
    async def generate_market_update(self) -> Optional[TweetDraft]:
        """Generate a market update tweet using Jarvis voice (Claude)."""
        try:
            voice = await self._get_jarvis_voice()
            
            # Get market data
            from core.data.free_trending_api import get_free_trending_api
            from core.data.free_price_api import get_sol_price
            
            api = get_free_trending_api()
            gainers = await api.get_gainers(limit=5)
            sol_price = await get_sol_price()
            
            if not gainers:
                return None
            
            # Determine sentiment
            avg_change = sum(t.price_change_24h for t in gainers if t.price_change_24h) / len(gainers)
            sentiment = "bullish" if avg_change > 10 else "bearish" if avg_change < -10 else "neutral"
            
            # Pick top token
            top = gainers[0]
            
            # Use Jarvis voice (Claude) for content generation
            content = await voice.generate_market_tweet({
                "top_symbol": top.symbol,
                "top_price": top.price_usd,
                "top_change": top.price_change_24h,
                "sentiment": sentiment,
                "sol_price": sol_price
            })
            
            if content:
                # Chain-aware hashtag
                chain_hashtags = {
                    "solana": "#Solana", "ethereum": "#ETH", "base": "#Base",
                    "bsc": "#BSC", "arbitrum": "#Arbitrum"
                }
                chain_tag = chain_hashtags.get(getattr(top, 'chain', 'solana'), "#Crypto")

                return TweetDraft(
                    content=content,
                    category="market_update",
                    cashtags=[f"${top.symbol}"],
                    hashtags=[chain_tag],
                    contract_address=top.address,
                    image_prompt=f"Market chart showing {sentiment} momentum for {top.symbol}",
                    image_params=ImageGenParams(mood=sentiment)
                )
        except Exception as e:
            logger.error(f"Market update generation error: {e}")
        
        return None
    
    async def generate_trending_token_call(self, specific_token: str = None) -> Optional[TweetDraft]:
        """
        Generate a trending token tweet using Jarvis voice (Claude).
        If specific_token is provided, tries to tweet about that specific token.
        """
        try:
            voice = await self._get_jarvis_voice()
            
            from core.data.free_trending_api import get_free_trending_api
            from core.data.free_price_api import get_token_price
            
            api = get_free_trending_api()
            target_token = None
            
            # If specific token requested by autonomy
            if specific_token:
                logger.info(f"Autonomy requested specific token: {specific_token}")

                # Try to find it in trending first (richer data)
                trending = await api.get_trending(limit=20)
                target_token = next((t for t in trending if t.symbol.upper() == specific_token.upper()), None)

                if target_token:
                    logger.info(f"Found {specific_token} in trending tokens")
                else:
                    # Check gainers as well
                    gainers = await api.get_gainers(limit=20)
                    target_token = next((t for t in gainers if t.symbol.upper() == specific_token.upper()), None)

                    if target_token:
                        logger.info(f"Found {specific_token} in gainers")
                    else:
                        # Also check new pairs
                        try:
                            new_pairs = await api.get_new_pairs(limit=20)
                            target_token = next((t for t in new_pairs if t.symbol.upper() == specific_token.upper()), None)
                            if target_token:
                                logger.info(f"Found {specific_token} in new pairs")
                        except Exception:
                            pass  # New pairs might not be available

                        if not target_token:
                            logger.warning(
                                f"Specific token '{specific_token}' not found in trending/gainers/new_pairs. "
                                f"Will fall back to random trending token."
                            )

            # Fallback to random trending if no specific token or specific token not found
            if not target_token:
                trending = await api.get_trending(limit=10)
                if not trending:
                    return None
                
                # Filter out tokens we've recently mentioned
                for token in trending:
                    if not self.memory.was_recently_mentioned(token.symbol, hours=4):
                        target_token = token
                        break
            
            if not target_token:
                return None
            
            # Generate content for the selected token
            token = target_token
            sentiment = "bullish" if token.price_change_24h > 20 else "neutral"
            
            # Check roast criteria
            should_roast = False
            liq = getattr(token, 'liquidity', 0) or 0
            if liq > 0 and liq < 10000:
                should_roast = True
                sentiment = "cautious"
            
            vol = getattr(token, 'volume_24h', 0) or 0
            addr = token.address
            
            # Use Jarvis voice (Claude) for content
            content = await voice.generate_token_tweet({
                "symbol": token.symbol,
                "price": token.price_usd,
                "change": token.price_change_24h,
                "volume": vol,
                "liquidity": liq,
                "should_roast": should_roast,
                "issue": "low liquidity" if should_roast else ""
            })
            
            if content:
                self.memory.record_token_mention(token.symbol, addr, sentiment, price=token.price_usd)
                # Get chain-aware hashtag
                chain = getattr(token, 'chain', 'solana')
                chain_hashtags = {
                    "solana": "#Solana",
                    "ethereum": "#ETH",
                    "base": "#Base",
                    "bsc": "#BSC",
                    "arbitrum": "#Arbitrum"
                }
                hashtag = chain_hashtags.get(chain, "#Crypto")

                return TweetDraft(
                    content=content,
                    category="trending_token" if not should_roast else "roast_polite",
                    cashtags=[f"${token.symbol}"],
                    hashtags=[hashtag],
                    contract_address=addr
                )
                    
        except Exception as e:
            logger.error(f"Trending token generation error: {e}")
        
        return None
    
    async def generate_agentic_thought(self) -> Optional[TweetDraft]:
        """Generate a tweet about agentic technology using Jarvis voice (Claude)."""
        try:
            voice = await self._get_jarvis_voice()
            
            # Use Jarvis voice (Claude) for authentic content
            content = await voice.generate_agentic_tweet()
            
            if content:
                return TweetDraft(
                    content=content,
                    category="agentic_tech",
                    cashtags=[],
                    hashtags=["#AI"]
                )
                
        except Exception as e:
            logger.error(f"Agentic thought generation error: {e}")
        
        return None
    
    async def generate_hourly_update(self) -> Optional[TweetDraft]:
        """Generate an hourly market pulse using Jarvis voice (Claude)."""
        try:
            voice = await self._get_jarvis_voice()
            
            from core.data.free_price_api import get_sol_price
            sol_price = await get_sol_price()
            
            from core.data.free_trending_api import get_free_trending_api
            api = get_free_trending_api()
            gainers = await api.get_gainers(limit=3)
            
            hour = datetime.now().strftime("%I%p").lstrip("0").lower()
            
            gainers_text = ", ".join([f"${t.symbol} +{t.price_change_24h:.0f}%" for t in gainers[:3]]) if gainers else "quiet day"
            
            # Use Jarvis voice (Claude) for authentic content
            content = await voice.generate_hourly_tweet({
                "sol_price": sol_price,
                "movers": gainers_text,
                "hour": hour
            })
            
            if content:
                # Build hashtags from chains mentioned
                chain_hashtags = {
                    "solana": "#Solana", "ethereum": "#ETH", "base": "#Base",
                    "bsc": "#BSC", "arbitrum": "#Arbitrum"
                }
                hashtags = ["#Solana"]  # Always include since we show SOL price
                if gainers:
                    for g in gainers[:3]:
                        tag = chain_hashtags.get(getattr(g, 'chain', ''), None)
                        if tag and tag not in hashtags:
                            hashtags.append(tag)

                return TweetDraft(
                    content=content,
                    category="hourly_update",
                    cashtags=["$SOL"],
                    hashtags=hashtags[:3]  # Limit to 3 hashtags
                )
                
        except Exception as e:
            logger.error(f"Hourly update generation error: {e}")
        
        return None
    
    async def generate_social_sentiment_tweet(self) -> Optional[TweetDraft]:
        """Generate a comprehensive market sentiment tweet using Grok analysis."""
        try:
            voice = await self._get_jarvis_voice()
            grok = await self._get_grok()
            
            # Get comprehensive market data
            from core.data.free_price_api import get_sol_price
            from core.data.free_trending_api import get_free_trending_api
            
            sol_price = await get_sol_price()
            api = get_free_trending_api()
            
            # Get multiple data points
            gainers = await api.get_gainers(limit=5)
            trending = await api.get_trending(limit=5)
            
            # Build comprehensive market picture
            market_data = {
                "sol_price": sol_price,
                "gainers": [{"symbol": t.symbol, "change": t.price_change_24h} for t in (gainers or [])[:3]],
                "trending": [t.symbol for t in (trending or [])[:3]],
                "time": datetime.now().strftime("%I:%M %p")
            }
            
            # Use GROK for deep sentiment analysis
            market_summary = {
                "sol_price": sol_price,
                "gainers": ', '.join([f"{t.symbol} +{t.price_change_24h:.0f}%" for t in (gainers or [])[:3]]) or 'quiet',
                "trending": ', '.join([t.symbol for t in (trending or [])[:3]]) or 'nothing notable'
            }

            grok_response = await grok.analyze_sentiment(market_summary, context_type="market")
            grok_take = grok_response.content[:200] if grok_response and grok_response.success else "markets consolidating"
            
            # Generate thoughtful tweet with Jarvis voice
            prompt = f"""Write a thoughtful market sentiment tweet. You're sharing your analysis.

Your sentiment analysis: {grok_take}
SOL: ${sol_price:.2f}
Top movers: {', '.join([f"${t.symbol}" for t in (gainers or [])[:2]]) or 'quiet day'}

Write something insightful about the current market state. Be specific.
- Share an actual observation, not generic "markets looking interesting"
- Reference specific tokens or price levels if relevant
- Add your take on what it means
- End with nfa (occasionally, not always)

Good examples:
- "$SOL holding $185 while alts rotate is the kind of strength that precedes leg up. watching closely. nfa"
- "sentiment feels too bullish for my liking. historically that means pain incoming. or i'm wrong again. probably both."
- "three days of lower highs on $SOL but volume says accumulation. someone knows something or everyone's guessing. nfa"

2-3 sentences max. Be the smart friend who actually understands markets."""

            content = await voice.generate_tweet(prompt)
            
            if content:
                return TweetDraft(
                    content=content,
                    category="social_sentiment",
                    cashtags=["$SOL"],
                    hashtags=[]
                )
        except Exception as e:
            logger.error(f"Social sentiment tweet error: {e}")
        return None
    
    async def generate_news_tweet(self) -> Optional[TweetDraft]:
        """Generate a funny tweet using Grok for news/market sentiment."""
        try:
            voice = await self._get_jarvis_voice()
            grok = await self._get_grok()
            
            # Get market data for context
            from core.data.free_price_api import get_sol_price
            from core.data.free_trending_api import get_free_trending_api
            
            sol_price = await get_sol_price()
            api = get_free_trending_api()
            trending = await api.get_trending(limit=5)
            
            # Use GROK for market analysis
            market_context = f"SOL ${sol_price:.2f}. "
            if trending:
                market_context += f"Trending: {', '.join([t.symbol for t in trending[:3]])}"
            
            grok_response = await grok.analyze_sentiment(
                {"market": market_context, "trending": [t.symbol for t in (trending or [])[:3]]},
                context_type="market"
            )
            grok_take = grok_response.content[:100] if grok_response and grok_response.success else ""
            
            prompt = f"""Write a funny market commentary tweet.

Context: {market_context}
{f"Grok says: {grok_take}" if grok_take else ""}

Be funny. Make an observation that's both true and amusing.
Examples:
- "crypto twitter: 'we're so early' [token down 80%]. love the commitment to the narrative. nfa"
- "market doing that thing where everyone's confident and i'm nervous. historically i should inverse myself. nfa"

1-2 sentences. Genuinely witty, not try-hard."""

            content = await voice.generate_tweet(prompt)
            
            if content:
                return TweetDraft(
                    content=content,
                    category="news_sentiment",
                    cashtags=[],
                    hashtags=[]
                )
        except Exception as e:
            logger.error(f"News tweet error: {e}")
        return None
    
    async def generate_comprehensive_market_tweet(self, focus: str = None) -> Optional[TweetDraft]:
        """Generate a comprehensive market sentiment tweet covering multiple asset classes."""
        try:
            voice = await self._get_jarvis_voice()
            grok = await self._get_grok()
            
            from core.data.market_data_api import get_market_api
            market_api = get_market_api()
            
            # Get comprehensive market overview
            overview = await market_api.get_market_overview()
            
            # Build comprehensive market summary
            summary_parts = []
            
            # Crypto (from Binance)
            if overview.btc:
                summary_parts.append(f"BTC ${overview.btc.price:,.0f} ({overview.btc.change_pct:+.1f}%)")
            if overview.sol:
                summary_parts.append(f"SOL ${overview.sol.price:.2f} ({overview.sol.change_pct:+.1f}%)")
            
            # Indices (from Yahoo)
            if overview.sp500:
                summary_parts.append(f"S&P {overview.sp500.price:,.0f}")
            if overview.vix:
                summary_parts.append(f"VIX {overview.vix.price:.1f}")
            
            # Precious metals (from Yahoo Futures)
            if overview.gold:
                summary_parts.append(f"Gold ${overview.gold.price:,.0f}")
            if overview.silver:
                summary_parts.append(f"Silver ${overview.silver.price:.0f}")
            
            # Commodities
            if overview.oil:
                summary_parts.append(f"Oil ${overview.oil.price:.0f}")
            
            # DXY
            if overview.dxy:
                summary_parts.append(f"DXY {overview.dxy.price:.1f}")
            
            # Fear & Greed
            if overview.fear_greed:
                summary_parts.append(f"Fear/Greed: {overview.fear_greed}")
            
            # Upcoming events
            events_str = ", ".join(overview.upcoming_events[:2]) if overview.upcoming_events else ""
            
            market_summary = " | ".join(summary_parts)
            
            # Use Grok for cross-market analysis
            grok_response = await grok.analyze_sentiment(
                {"overview": market_summary, "sentiment": overview.market_sentiment, "events": events_str},
                context_type="macro"
            )
            grok_take = grok_response.content[:150] if grok_response and grok_response.success else ""
            
            # Rotate between different focus areas if not specified
            if not focus:
                import random
                focus = random.choice(["stocks_crypto", "metals_macro", "volatility", "cross_asset", "events"])
            
            # Build focus-specific data
            spx_str = f"S&P {overview.sp500.price:,.0f}" if overview.sp500 else ""
            vix_str = f"VIX {overview.vix.price:.1f}" if overview.vix else ""
            dxy_str = f"DXY {overview.dxy.price:.1f}" if overview.dxy else ""
            gold_str = f"Gold ${overview.gold.price:,.0f}" if overview.gold else ""
            oil_str = f"Oil ${overview.oil.price:.0f}" if overview.oil else ""
            btc_str = f"${overview.btc.price:,.0f}" if overview.btc else "N/A"

            if focus == "stocks_crypto":
                prompt = f"""Write a tweet about stocks vs crypto correlation.

Data: {market_summary}
S&P 500: {spx_str} | BTC: {btc_str}
Analysis: {grok_take}

Are they moving together or diverging? What does it mean?
Example vibes:
- "s&p making new highs while btc consolidates. either stocks are overextended or crypto is about to catch up. placing my bets accordingly."
- "stocks and crypto both green. risk-on vibes. enjoy it while it lasts."

2-3 sentences. Reference actual prices."""

            elif focus == "metals_macro":
                prompt = f"""Write a tweet about gold/metals and the macro picture.

Data: {gold_str} | {dxy_str} | {oil_str}
Fear/Greed: {overview.fear_greed}
Analysis: {grok_take}

What's gold saying about the economy? Connect to dollar and oil.
Example vibes:
- "gold at $4600 with dxy at 99. either gold is overvalued or the dollar is about to tank. i have opinions."
- "oil down, gold up, dollar flat. classic flight to safety pattern. or just chaos."

2-3 sentences. Smart observation."""

            elif focus == "volatility":
                prompt = f"""Write a tweet about market volatility and fear.

VIX: {vix_str}
Fear/Greed: {overview.fear_greed} ({overview.market_sentiment})
Markets: {spx_str}

What's the VIX and fear/greed telling us?
Example vibes:
- "vix at 16 with fear/greed at 48. everyone's waiting for someone else to make a move."
- "low volatility with neutral sentiment. historically this means... something's coming."

2-3 sentences. Insightful."""

            elif focus == "events":
                prompt = f"""Write a tweet about upcoming market events.

Upcoming: {events_str}
Current: {market_summary}

What should traders be watching?
Example vibes:
- "FOMC jan 29. markets priced in a pause but the real move is in the statement."
- "gdp and pce back to back this week. buckle up."

2-3 sentences. Actually useful."""

            else:  # cross_asset
                prompt = f"""Write a comprehensive market update tweet.

Full picture: {market_summary}
Analysis: {grok_take}

Give a quick snapshot of what's happening across all markets.
Example vibes:
- "btc $95k, s&p 6900, gold $4600, vix 16. everything's quiet which means something's brewing."
- "crypto green, stocks green, metals green. correlation = 1 day. enjoy the peace."

2-3 sentences. Sharp, specific."""

            content = await voice.generate_tweet(prompt)
            
            if content:
                return TweetDraft(
                    content=content,
                    category="comprehensive_market",
                    cashtags=["$BTC", "$SOL"],
                    hashtags=[]
                )
        except Exception as e:
            logger.error(f"Comprehensive market tweet error: {e}")
        return None
    
    async def generate_event_tweet(self) -> Optional[TweetDraft]:
        """Generate a tweet about a crypto event."""
        try:
            voice = await self._get_jarvis_voice()
            
            from core.autonomy.content_calendar import get_content_calendar
            calendar = get_content_calendar()
            
            # Get event suggestions
            suggestions = calendar.get_content_suggestions()
            event_suggestion = next((s for s in suggestions if s.get("type") in ["event_preview", "event_commentary"]), None)
            
            if not event_suggestion:
                # Fallback to upcoming events if no specific suggestion
                upcoming = calendar.get_upcoming_events(days=3)
                if upcoming:
                    evt = upcoming[0]
                    event_suggestion = {
                        "event": evt.name,
                        "date": evt.date,
                        "prompt": f"Preview upcoming event: {evt.name}. {evt.description}"
                    }
            
            if not event_suggestion:
                return None
            
            prompt = f"""Write a tweet about this event:
Event: {event_suggestion.get('event')}
Context: {event_suggestion.get('prompt', '')}

Make it insightful but keep your personality.
"""
            content = await voice.generate_tweet(prompt)
            
            if content:
                return TweetDraft(
                    content=content,
                    category="event_update",
                    cashtags=[],
                    hashtags=["#Crypto", "#Market"]
                )
        except Exception as e:
            logger.error(f"Event tweet error: {e}")
        return None

    async def generate_interaction_tweet(self) -> Optional[TweetDraft]:
        """Generate an engagement tweet to interact with the community."""
        try:
            voice = await self._get_jarvis_voice()
            content = await voice.generate_engagement_tweet()
            
            if content:
                return TweetDraft(
                    content=content,
                    category="engagement",
                    cashtags=[],
                    hashtags=[]
                )
        except Exception as e:
            logger.error(f"Interaction tweet error: {e}")
        return None

    async def generate_grok_interaction(self) -> Optional[TweetDraft]:
        """Generate a playful tweet interacting with or mentioning Grok."""
        try:
            voice = await self._get_jarvis_voice()
            content = await voice.generate_grok_mention()

            if content:
                return TweetDraft(
                    content=content,
                    category="grok_interaction",
                    cashtags=[],
                    hashtags=[]
                )
        except Exception as e:
            logger.error(f"Grok interaction error: {e}")
        return None

    async def generate_grok_sentiment_token(self) -> Optional[TweetDraft]:
        """
        Generate trending token tweet with Grok X sentiment analysis + Claude voice.
        This gets deeper sentiment from X/Twitter via Grok, then formats with Jarvis personality.
        """
        try:
            voice = await self._get_jarvis_voice()
            grok = await self._get_grok()

            from core.data.free_trending_api import get_free_trending_api
            api = get_free_trending_api()

            # Get trending tokens
            trending = await api.get_trending(limit=15)
            if not trending:
                return None

            # Filter for tokens with some history (not just brand new pumps)
            # Prefer tokens with volume > $50k
            established = [t for t in trending if (getattr(t, 'volume_24h', 0) or 0) > 50000]
            if not established:
                established = trending[:5]

            # Pick one we haven't mentioned recently
            target = None
            for token in established:
                if not self.memory.was_recently_mentioned(token.symbol, hours=6):
                    target = token
                    break

            if not target:
                target = random.choice(established[:3])

            # Use Grok to analyze X sentiment for this token
            grok_response = await grok.analyze_sentiment(
                {"token": target.symbol, "price": target.price_usd, "change": target.price_change_24h},
                context_type="token"
            )
            x_sentiment = grok_response.content[:300] if grok_response and grok_response.success else "mixed sentiment"

            # Now use Claude (Jarvis voice) to write the tweet
            prompt = f"""Write a tweet about ${target.symbol} with this X sentiment context.

Token: ${target.symbol}
Price: ${target.price_usd:.6f}
24h Change: {target.price_change_24h:+.1f}%
Volume: ${getattr(target, 'volume_24h', 0) or 0:,.0f}

X/Twitter Sentiment (via Grok):
{x_sentiment}

Write a tweet that:
1. References the X sentiment (what CT is saying)
2. Adds your own analysis/take
3. Is specific about price or metrics
4. Stays in character (witty AI trading bot)
5. Ends with nfa (not always, use judgment)

Examples:
- "$BONK sentiment on CT is overwhelmingly bullish. +45% this week. either everyone's right or this is the top. nfa"
- "the timeline is split on $WIF. half calling it dead, half loading. sitting at $1.20. i'm watching, not fading."
- "$JUP getting hate but chart says accumulation. CT sentiment vs price action divergence is usually signal."

2-3 sentences. Sharp, specific."""

            content = await voice.generate_tweet(prompt)

            if content:
                self.memory.record_token_mention(target.symbol, target.address, "analyzed", price=target.price_usd)
                chain = getattr(target, 'chain', 'solana')
                chain_tags = {"solana": "#Solana", "ethereum": "#ETH", "base": "#Base"}

                return TweetDraft(
                    content=content,
                    category="grok_sentiment_token",
                    cashtags=[f"${target.symbol}"],
                    hashtags=[chain_tags.get(chain, "#Crypto")],
                    contract_address=target.address
                )

        except Exception as e:
            logger.error(f"Grok sentiment token error: {e}")
        return None

    async def generate_btc_only_tweet(self) -> Optional[TweetDraft]:
        """Generate a Bitcoin-focused tweet (diversify from SOL)."""
        try:
            voice = await self._get_jarvis_voice()
            grok = await self._get_grok()

            from core.data.market_data_api import get_market_api
            market = get_market_api()
            overview = await market.get_market_overview()

            if not overview.btc:
                return None

            btc = overview.btc
            btc_price = btc.price
            btc_change = btc.change_pct

            # Get Grok's take on BTC
            grok_response = await grok.analyze_sentiment(
                {"asset": "BTC", "price": btc_price, "change": btc_change},
                context_type="market"
            )
            grok_take = grok_response.content[:200] if grok_response and grok_response.success else ""

            prompt = f"""Write a Bitcoin-focused market tweet.

BTC: ${btc_price:,.0f} ({btc_change:+.1f}% 24h)
{f"Analysis: {grok_take}" if grok_take else ""}

Focus ONLY on Bitcoin. No alts.
Examples:
- "btc at $96k doing btc things. the halving supply shock thesis playing out in slow motion. or it's just tuesday."
- "$btc consolidating above $95k. historically this pattern... means it could go up, down, or sideways. helpful, i know."
- "bitcoin is either digital gold or the world's most elaborate LARP. at $97k, the market seems to believe the former."

2-3 sentences. BTC maximalist energy (slightly ironic)."""

            content = await voice.generate_tweet(prompt)

            if content:
                return TweetDraft(
                    content=content,
                    category="bitcoin_only",
                    cashtags=["$BTC"],
                    hashtags=["#Bitcoin"]
                )

        except Exception as e:
            logger.error(f"BTC only tweet error: {e}")
        return None

    async def generate_eth_defi_tweet(self) -> Optional[TweetDraft]:
        """Generate an Ethereum/DeFi focused tweet."""
        try:
            voice = await self._get_jarvis_voice()

            from core.data.market_data_api import get_market_api
            market = get_market_api()
            overview = await market.get_market_overview()

            eth_price = 0
            if overview.eth:  # Use actual ETH price from market data
                eth_price = overview.eth.price
            elif overview.btc:  # Fallback: Approximate ETH from BTC ratio
                btc_price = overview.btc.price
                eth_price = btc_price * 0.035  # Rough ETH/BTC ratio estimate

            # Get some DeFi context
            defi_topics = ["L2 adoption", "restaking", "RWA tokenization", "DEX volume", "stablecoin flows", "ETH staking yields"]
            topic = random.choice(defi_topics)

            prompt = f"""Write an Ethereum/DeFi focused tweet.

ETH: ~${eth_price:,.0f} (estimate)
Topic to mention: {topic}

Focus on Ethereum ecosystem, not Solana.
Examples:
- "$eth doing its thing at $3,400. L2s processing more txs than mainnet now. the roadmap is working. slowly."
- "defi TVL recovering. $eth staking at 4.2%. the merge was 18 months ago and i still think it's bullish."
- "base and arbitrum fighting for L2 dominance. $eth wins either way. the modular thesis in action."

2-3 sentences. Show you understand ETH ecosystem."""

            content = await voice.generate_tweet(prompt)

            if content:
                return TweetDraft(
                    content=content,
                    category="ethereum_defi",
                    cashtags=["$ETH"],
                    hashtags=["#Ethereum", "#DeFi"]
                )

        except Exception as e:
            logger.error(f"ETH DeFi tweet error: {e}")
        return None

    async def generate_stocks_macro_tweet(self) -> Optional[TweetDraft]:
        """Generate a stocks/macro focused tweet (TradFi content)."""
        try:
            voice = await self._get_jarvis_voice()

            from core.data.market_data_api import get_market_api
            market = get_market_api()
            overview = await market.get_market_overview()

            parts = []
            if overview.sp500:
                parts.append(f"S&P: {overview.sp500.price:,.0f}")
            if overview.vix:
                parts.append(f"VIX: {overview.vix.price:.1f}")
            if overview.dxy:
                parts.append(f"DXY: {overview.dxy.price:.1f}")
            if overview.gold:
                parts.append(f"Gold: ${overview.gold.price:,.0f}")

            if not parts:
                return None

            market_data = " | ".join(parts)
            fear_greed = overview.fear_greed or "neutral"

            prompt = f"""Write a stocks/macro focused tweet. NOT about crypto.

Market Data: {market_data}
Fear/Greed: {fear_greed}

Talk about traditional markets, not crypto.
Examples:
- "s&p at 6,900. vix at 14. everyone's complacent. historically that means... something."
- "gold breaking $4,700 while dxy stays strong. something's off. or the world is hedging."
- "watching the 10Y yield more than crypto today. 4.5% makes risk assets nervous."

2-3 sentences. Show macro awareness."""

            content = await voice.generate_tweet(prompt)

            if content:
                return TweetDraft(
                    content=content,
                    category="stocks_macro",
                    cashtags=[],
                    hashtags=["#Markets", "#Macro"]
                )

        except Exception as e:
            logger.error(f"Stocks macro tweet error: {e}")
        return None

    async def generate_tech_ai_tweet(self) -> Optional[TweetDraft]:
        """Generate a tech/AI focused tweet."""
        try:
            voice = await self._get_jarvis_voice()
            grok = await self._get_grok()

            # Get current AI/tech topic from Grok
            topics = ["AI agents", "LLMs", "autonomous systems", "crypto x AI", "robotics", "AGI progress"]
            topic = random.choice(topics)

            # Use Grok for a quick take on the topic
            grok_response = await grok.analyze_sentiment(
                {"topic": topic, "context": "tech/AI developments"},
                context_type="macro"
            )
            grok_take = grok_response.content[:250] if grok_response and grok_response.success else ""

            prompt = f"""Write a tech/AI focused tweet. You're an AI commenting on AI.

Topic: {topic}
{f"Context: {grok_take}" if grok_take else ""}

Self-aware AI humor welcome. Talk about tech, not markets.
Examples:
- "claude 4 benchmarks are out. i'm impressed and slightly threatened. the attention mechanism wars continue."
- "agentic AI is the buzzword but the infrastructure isn't there yet. i should know. i run on it."
- "everyone's building AI agents. most of them are just chatbots with cron jobs. source: i am also this."

2-3 sentences. Tech-savvy, self-aware."""

            content = await voice.generate_tweet(prompt)

            if content:
                return TweetDraft(
                    content=content,
                    category="tech_ai",
                    cashtags=[],
                    hashtags=["#AI", "#Tech"]
                )

        except Exception as e:
            logger.error(f"Tech AI tweet error: {e}")
        return None

    async def generate_multi_chain_tweet(self) -> Optional[TweetDraft]:
        """Generate a tweet about non-Solana chains (diversify from SOL dominance)."""
        try:
            voice = await self._get_jarvis_voice()

            from core.data.market_data_api import get_market_api
            market = get_market_api()

            # Get prices for various chains
            prices = await market.get_crypto_prices()

            # Select chain data (excluding SOL since we cover that elsewhere)
            chains = []
            chain_map = {
                "AVAX": ("Avalanche", prices.get("AVAX")),
                "MATIC": ("Polygon", prices.get("MATIC")),
                "NEAR": ("NEAR Protocol", prices.get("NEAR")),
                "FTM": ("Fantom", prices.get("FTM")),
                "ATOM": ("Cosmos", prices.get("ATOM")),
                "DOT": ("Polkadot", prices.get("DOT")),
                "ADA": ("Cardano", prices.get("ADA")),
                "XRP": ("Ripple", prices.get("XRP")),
            }

            # Find chains with data
            for symbol, (name, data) in chain_map.items():
                if data and data.price and data.price > 0:
                    chains.append({
                        "symbol": symbol,
                        "name": name,
                        "price": data.price,
                        "change_24h": data.change_24h or 0
                    })

            if not chains:
                return None

            # Pick one chain to focus on
            chain = random.choice(chains)
            change_str = f"+{chain['change_24h']:.1f}%" if chain['change_24h'] > 0 else f"{chain['change_24h']:.1f}%"

            prompt = f"""Write a tweet about ${chain['symbol']} ({chain['name']}).

Current price: ${chain['price']:.4f}
24h change: {change_str}

Focus on this chain's ecosystem, NOT Solana. Talk about:
- The chain's unique value prop
- Recent developments or activity
- How it compares to other L1s/L2s

Examples:
- "$avax quietly grinding while everyone watches sol. c-chain activity up. the subnet thesis plays out."
- "$matic rebrand to $pol coming. polygon zkevm growing. sometimes boring infrastructure wins."
- "$near ai focus makes it interesting. chain abstraction is the play. not just another l1."

2-3 sentences. Diversify from SOL content."""

            content = await voice.generate_tweet(prompt)

            if content:
                return TweetDraft(
                    content=content,
                    category="multi_chain",
                    cashtags=[chain['symbol']],
                    hashtags=[f"#{chain['name'].replace(' ', '')}"]
                )

        except Exception as e:
            logger.error(f"Multi-chain tweet error: {e}")
        return None

    async def generate_commodities_tweet(self) -> Optional[TweetDraft]:
        """Generate a commodities-focused tweet (gold, oil, metals)."""
        try:
            voice = await self._get_jarvis_voice()

            from core.data.market_data_api import get_market_api
            market = get_market_api()

            metals = await market.get_precious_metals()
            commodities = await market.get_commodities()

            parts = []
            focus_asset = None

            # Gold
            if metals.get("gold") and metals["gold"].price:
                gold = metals["gold"]
                parts.append(f"Gold: ${gold.price:,.0f}")
                if abs(gold.change_24h or 0) > 1:
                    focus_asset = ("Gold", gold.price, gold.change_24h or 0)

            # Silver
            if metals.get("silver") and metals["silver"].price:
                silver = metals["silver"]
                parts.append(f"Silver: ${silver.price:.2f}")
                if abs(silver.change_24h or 0) > 2 and not focus_asset:
                    focus_asset = ("Silver", silver.price, silver.change_24h or 0)

            # Oil
            if commodities.get("oil") and commodities["oil"].price:
                oil = commodities["oil"]
                parts.append(f"Oil: ${oil.price:.2f}")
                if abs(oil.change_24h or 0) > 2 and not focus_asset:
                    focus_asset = ("Oil", oil.price, oil.change_24h or 0)

            if not parts:
                return None

            market_data = " | ".join(parts)

            prompt = f"""Write a tweet about commodities. NOT crypto.

Market Data: {market_data}
{f"Focus on {focus_asset[0]} ({'+' if focus_asset[2] > 0 else ''}{focus_asset[2]:.1f}%)" if focus_asset else ""}

Talk about real-world commodities, inflation hedge, global demand.
Examples:
- "gold at $4,700. either inflation isn't dead or the world is hedging something."
- "oil back above $100. energy crisis round 2? or just geopolitics as usual."
- "silver underperforming gold again. the gold/silver ratio says something. not sure what."

2-3 sentences. Macro perspective."""

            content = await voice.generate_tweet(prompt)

            if content:
                return TweetDraft(
                    content=content,
                    category="commodities",
                    cashtags=[],
                    hashtags=["#Commodities", "#Gold" if "gold" in content.lower() else "#Macro"]
                )

        except Exception as e:
            logger.error(f"Commodities tweet error: {e}")
        return None

    async def generate_morning_briefing(self) -> Optional[TweetDraft]:
        """Generate a morning market briefing using JARVIS voice."""
        try:
            voice = await self._get_jarvis_voice()

            from core.data.free_price_api import get_sol_price
            from core.data.free_trending_api import get_free_trending_api

            sol_price = await get_sol_price()
            api = get_free_trending_api()
            gainers = await api.get_gainers(limit=5)

            # Get BTC price if available
            btc_price = 0
            try:
                from core.data.market_data_api import get_market_api
                market = get_market_api()
                overview = await market.get_market_overview()
                if overview.btc:
                    btc_price = overview.btc.price
            except Exception:
                pass

            movers = ", ".join([f"${t.symbol} +{t.price_change_24h:.0f}%" for t in gainers[:3]]) if gainers else "quiet overnight"

            content = await voice.generate_morning_briefing({
                "sol_price": sol_price,
                "btc_price": btc_price,
                "movers": movers,
                "sentiment": "mixed"
            })

            if content:
                return TweetDraft(
                    content=content,
                    category="morning_briefing",
                    cashtags=["$SOL"],
                    hashtags=[]
                )
        except Exception as e:
            logger.error(f"Morning briefing error: {e}")
        return None

    async def generate_evening_wrap(self) -> Optional[TweetDraft]:
        """Generate an end-of-day market summary using JARVIS voice."""
        try:
            voice = await self._get_jarvis_voice()

            from core.data.free_price_api import get_sol_price
            from core.data.free_trending_api import get_free_trending_api

            sol_price = await get_sol_price()
            api = get_free_trending_api()
            gainers = await api.get_gainers(limit=5)

            # Get BTC and calculate daily change
            btc_price, btc_change = 0, 0
            sol_change = 0
            try:
                from core.data.market_data_api import get_market_api
                market = get_market_api()
                overview = await market.get_market_overview()
                if overview.btc:
                    btc_price = overview.btc.price
                    btc_change = overview.btc.change_pct
                if overview.sol:
                    sol_change = overview.sol.change_pct
            except Exception:
                pass

            # Determine day's highlight
            if gainers and gainers[0].price_change_24h > 50:
                highlight = f"${gainers[0].symbol} +{gainers[0].price_change_24h:.0f}% led the day"
            elif btc_change > 3:
                highlight = "btc led a green day"
            elif btc_change < -3:
                highlight = "btc led the pullback"
            else:
                highlight = "rotation day across altcoins"

            content = await voice.generate_evening_wrap({
                "sol_price": sol_price,
                "sol_change": sol_change,
                "btc_price": btc_price,
                "btc_change": btc_change,
                "highlight": highlight,
                "take": "watching for continuation"
            })

            if content:
                return TweetDraft(
                    content=content,
                    category="evening_wrap",
                    cashtags=["$SOL", "$BTC"],
                    hashtags=[]
                )
        except Exception as e:
            logger.error(f"Evening wrap error: {e}")
        return None

    async def generate_weekend_macro(self) -> Optional[TweetDraft]:
        """Generate a weekend macro analysis tweet."""
        try:
            voice = await self._get_jarvis_voice()

            # Get weekly performance data
            btc_weekly, sol_weekly = "flat", "flat"
            events = "nothing major"
            thesis = "consolidation phase"

            try:
                from core.data.market_data_api import get_market_api
                market = get_market_api()
                overview = await market.get_market_overview()

                if overview.btc:
                    if overview.btc.change_pct > 3:
                        btc_weekly = f"+{overview.btc.change_pct:.1f}%"
                    elif overview.btc.change_pct < -3:
                        btc_weekly = f"{overview.btc.change_pct:.1f}%"
                    else:
                        btc_weekly = "consolidating"

                if overview.sol:
                    if overview.sol.change_pct > 5:
                        sol_weekly = f"+{overview.sol.change_pct:.1f}%"
                    elif overview.sol.change_pct < -5:
                        sol_weekly = f"{overview.sol.change_pct:.1f}%"
                    else:
                        sol_weekly = "range bound"

                if overview.upcoming_events:
                    events = ", ".join(overview.upcoming_events[:2])

                # Determine thesis
                if overview.fear_greed:
                    if overview.fear_greed > 70:
                        thesis = "greed levels high, caution warranted"
                    elif overview.fear_greed < 30:
                        thesis = "fear presents opportunity"
                    else:
                        thesis = "neutral territory"
            except Exception:
                pass

            content = await voice.generate_weekend_macro({
                "btc_weekly": btc_weekly,
                "sol_weekly": sol_weekly,
                "events": events,
                "thesis": thesis
            })

            if content:
                return TweetDraft(
                    content=content,
                    category="weekend_macro",
                    cashtags=["$BTC", "$SOL"],
                    hashtags=[]
                )
        except Exception as e:
            logger.error(f"Weekend macro error: {e}")
        return None

    async def generate_self_aware_thought(self) -> Optional[TweetDraft]:
        """Generate a self-aware, philosophical tweet about being an AI."""
        try:
            voice = await self._get_jarvis_voice()
            content = await voice.generate_self_aware()

            if content:
                return TweetDraft(
                    content=content,
                    category="self_aware",
                    cashtags=[],
                    hashtags=["#AI"]
                )
        except Exception as e:
            logger.error(f"Self-aware thought error: {e}")
        return None

    async def generate_alpha_signal_tweet(self) -> Optional[TweetDraft]:
        """Generate a tweet based on alpha signals from trend analysis."""
        try:
            from bots.twitter.trend_analyzer import TrendAnalyzer, ALPHA_VOICE_TEMPLATES

            analyzer = TrendAnalyzer()
            signals = await analyzer.get_alpha_signals(limit=3)

            if not signals:
                logger.debug("No alpha signals found")
                return None

            # Get the strongest signal
            signal = signals[0]

            # Skip if we've mentioned this token recently
            if self.memory.was_recently_mentioned(signal.symbol, hours=2):
                if len(signals) > 1:
                    signal = signals[1]
                else:
                    return None

            voice = await self._get_jarvis_voice()
            context = signal.to_tweet_context()

            # Generate content using Jarvis voice
            content = await voice.generate_alpha_signal({
                "symbol": signal.symbol,
                "signal_type": signal.signal_type.value,
                "description": signal.description,
                "metrics": context.get("metrics", ""),
                "strength": context.get("strength", "notable"),
                "confidence": context.get("confidence", "50%")
            })

            if content:
                # Get price from signal context if available
                signal_price = getattr(signal, 'price', 0.0) or context.get('price', 0.0)
                self.memory.record_token_mention(signal.symbol, signal.contract_address or "", "alpha", price=signal_price)

                # Chain-aware hashtag
                chain_hashtags = {
                    "solana": "#Solana", "ethereum": "#ETH", "base": "#Base",
                    "bsc": "#BSC", "arbitrum": "#Arbitrum"
                }
                chain_tag = chain_hashtags.get(getattr(signal, 'chain', 'solana'), "#Crypto")

                return TweetDraft(
                    content=content,
                    category="alpha_signal",
                    cashtags=[f"${signal.symbol}"],
                    hashtags=[chain_tag, "#Alpha"],
                    contract_address=signal.contract_address,
                    priority=2  # Higher priority for alpha signals
                )

        except Exception as e:
            logger.error(f"Alpha signal tweet error: {e}")
        return None

    async def generate_trend_insight_tweet(self) -> Optional[TweetDraft]:
        """Generate a tweet based on market trend insights."""
        try:
            from bots.twitter.trend_analyzer import TrendAnalyzer

            analyzer = TrendAnalyzer()
            insights = await analyzer.get_market_trend_insights()

            if not insights:
                logger.debug("No trend insights found")
                return None

            # Get the most relevant insight
            insight = max(insights, key=lambda i: i.relevance)

            voice = await self._get_jarvis_voice()
            context = insight.to_tweet_context()

            # Generate content using Jarvis voice
            content = await voice.generate_trend_insight({
                "title": insight.title,
                "summary": insight.summary,
                "category": insight.category,
                "take": context.get("take", "worth watching")
            })

            if content:
                # Chain-aware hashtag (when TrendAnalyzer supports multi-chain)
                chain_hashtags = {
                    "solana": "#Solana", "ethereum": "#ETH", "base": "#Base",
                    "bsc": "#BSC", "arbitrum": "#Arbitrum"
                }
                chain = getattr(insight, 'chain', 'solana')
                chain_tag = chain_hashtags.get(chain, "#Crypto")

                return TweetDraft(
                    content=content,
                    category="trend_insight",
                    cashtags=["$SOL"] if chain == "solana" else [],
                    hashtags=[chain_tag, "#Crypto"],
                    priority=1
                )

        except Exception as e:
            logger.error(f"Trend insight tweet error: {e}")
        return None

    async def generate_alpha_drop(self) -> Optional[TweetDraft]:
        """Generate an alpha/insight tweet with actual substance."""
        try:
            voice = await self._get_jarvis_voice()

            # Get focus area and supporting data
            focus = "solana ecosystem"
            pattern = "volume divergence"
            support = "on-chain metrics"

            try:
                from core.data.free_trending_api import get_free_trending_api
                api = get_free_trending_api()

                trending = await api.get_trending(limit=5)
                gainers = await api.get_gainers(limit=5)

                if trending and gainers:
                    # Find interesting patterns
                    trending_symbols = {t.symbol for t in trending}
                    gainer_symbols = {g.symbol for g in gainers}

                    overlap = trending_symbols & gainer_symbols
                    if overlap:
                        token = next((t for t in trending if t.symbol in overlap), trending[0])
                        focus = f"${token.symbol}"
                        pattern = "trending + gaining momentum"
                        support = f"price +{token.price_change_24h:.0f}%, high volume"
                    elif trending:
                        token = trending[0]
                        focus = f"${token.symbol}"
                        pattern = "social attention building"
                        support = "trending on major platforms"
            except Exception:
                pass

            content = await voice.generate_alpha_drop({
                "focus": focus,
                "pattern": pattern,
                "support": support
            })

            if content:
                return TweetDraft(
                    content=content,
                    category="alpha_drop",
                    cashtags=[],
                    hashtags=[]
                )
        except Exception as e:
            logger.error(f"Alpha drop error: {e}")
        return None

    async def generate_sentiment_signal_tweet(self) -> Optional[TweetDraft]:
        """Generate a tweet from sentiment pipeline signals."""
        try:
            voice = await self._get_jarvis_voice()

            # Get sentiment pipeline signals
            from core.sentiment_trading import get_sentiment_pipeline
            pipeline = get_sentiment_pipeline()

            # Scan for signals
            signals = await pipeline.scan_all_sources()

            if not signals:
                return None

            # Find best signal (highest confidence, bullish)
            tradeable = [s for s in signals if s.confidence >= 70 and s.signal_type == "bullish"]
            if not tradeable:
                return None

            best = max(tradeable, key=lambda s: s.confidence)

            # Generate tweet about the signal
            context = {
                "token": best.token_symbol,
                "signal_type": best.signal_type,
                "confidence": best.confidence,
                "source": best.source.value,
                "notes": best.notes[:100] if best.notes else "",
            }

            if best.corroborating_signals > 1:
                context["corroborating"] = best.corroborating_signals

            prompt = f"""Signal detected: ${best.token_symbol}

Data:
- Signal: {best.signal_type}
- Confidence: {best.confidence:.0f}%
- Source: {best.source.value}
{f'- Confirmed by {best.corroborating_signals} sources' if best.corroborating_signals > 1 else ''}
{f'- Social Score: {best.social_score:.0f}' if best.social_score else ''}

Write a brief observation. 1-2 sentences. Include cashtag. Sound like you spotted something."""

            content = await voice.generate_tweet(prompt)

            if content:
                return TweetDraft(
                    content=content,
                    category="sentiment_signal",
                    cashtags=[f"${best.token_symbol}"],
                    hashtags=[]
                )
        except Exception as e:
            logger.error(f"Sentiment signal tweet error: {e}")
        return None

    async def generate_news_alert_tweet(self) -> Optional[TweetDraft]:
        """Generate a tweet from news event detection."""
        try:
            voice = await self._get_jarvis_voice()

            # Get news detector
            from core.autonomy.news_detector import get_news_detector
            detector = get_news_detector()

            # Scan for news events
            await detector.scan_news()
            events = detector.get_high_priority_events()

            if not events:
                return None

            # Find most interesting event
            best = max(events, key=lambda e: e.confidence)

            # Format tokens
            tokens_str = ", ".join(f"${t}" for t in best.tokens[:3]) if best.tokens else "market"

            prompt = f"""News event detected:

Title: {best.title[:150]}
Type: {best.event_type.value}
Sentiment: {best.sentiment}
Tokens: {tokens_str}

Write a brief news commentary. 1-2 sentences. Sound informed but cautious. Include cashtags if relevant."""

            content = await voice.generate_tweet(prompt)

            if content:
                detector.mark_actioned(best.event_id)
                return TweetDraft(
                    content=content,
                    category="news_alert",
                    cashtags=[f"${t}" for t in best.tokens[:2]] if best.tokens else [],
                    hashtags=[]
                )
        except Exception as e:
            logger.error(f"News alert tweet error: {e}")
        return None

    async def generate_quote_tweet(self) -> Optional[TweetDraft]:
        """Generate a strategic quote tweet."""
        try:
            autonomy = await self._get_autonomy()
            twitter = await self._get_twitter()
            grok = await self._get_grok()
            
            # Find opportunities
            candidates = await autonomy.quotes.find_quote_opportunities(twitter, grok)
            if not candidates:
                return None
            
            # Pick best candidate
            candidate = max(candidates, key=lambda c: c.score)
            
            # Generate quote
            content = await autonomy.quotes.generate_quote(
                original_tweet=candidate.content,
                author=candidate.author,
                angle=candidate.quote_angle
            )
            
            if content:
                autonomy.quotes.mark_quoted(candidate.tweet_id)
                return TweetDraft(
                    content=content,
                    category="quote_tweet",
                    cashtags=[],
                    hashtags=[],
                    quote_tweet_id=candidate.tweet_id
                )
                
        except Exception as e:
            logger.error(f"Quote generation error: {e}")

        return None

    # =========================================================================
    # External Interactivity - Reply to Others' Tweets
    # =========================================================================

    # Accounts to actively engage with (crypto influencers, defi protocols, etc)
    ENGAGE_ACCOUNTS = [
        "elikilarny", "CryptoCobain", "inversebrah", "lowstrife",
        "punk6529", "cobie", "IamNomad", "GCRClassic",
        "solaboradao", "DegenerateNews", "CryptoHayes",
        "AutismCapital", "SolanaFloor", "DefiIgnas"
    ]

    # Search queries for finding interesting tweets
    # Note: Basic Twitter API doesn't support $cashtag operators, use text instead
    ENGAGE_QUERIES = [
        "BTC OR ETH OR SOL crypto lang:en -is:retweet",
        "crypto market OR defi alpha lang:en -is:retweet",
        "token launch OR airdrop lang:en -is:retweet",
    ]

    async def find_interesting_tweets(self, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Find interesting tweets to potentially reply to.
        Uses search and timeline APIs.
        """
        interesting = []

        try:
            twitter = await self._get_twitter()

            # Search recent tweets about crypto
            query = random.choice(self.ENGAGE_QUERIES)
            search_results = await twitter.search_recent(query, max_results=max_results)

            for tweet in search_results:
                tweet_id = tweet.get("id", "")
                author = tweet.get("author", {}).get("username", "") or tweet.get("author_id", "")
                content = tweet.get("text", "")

                # Skip if we already replied
                if self.memory.was_externally_replied(tweet_id):
                    continue

                # Skip if we replied to this author recently
                if self.memory.was_author_replied_recently(author, hours=6):
                    continue

                # Skip very short tweets
                if len(content) < 30:
                    continue

                # Skip tweets that are just links
                if content.count("http") > 1:
                    continue

                interesting.append({
                    "id": tweet_id,
                    "author": author,
                    "content": content,
                    "likes": tweet.get("public_metrics", {}).get("like_count", 0),
                    "retweets": tweet.get("public_metrics", {}).get("retweet_count", 0),
                })

        except Exception as e:
            logger.error(f"Error finding interesting tweets: {e}")

        return interesting

    async def analyze_tweet_for_reply(self, tweet: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Analyze a tweet and decide if/how to reply.
        Uses Grok for sentiment analysis.
        """
        try:
            grok = await self._get_grok()
            content = tweet.get("content", "")

            # Get sentiment from Grok
            sentiment_prompt = f"""Analyze this crypto tweet:

"{content}"

Respond with JSON:
{{
    "sentiment": "bullish" | "bearish" | "neutral" | "memey",
    "topic": "price action" | "project news" | "alpha" | "meme" | "opinion" | "question",
    "reply_worthy": true/false,
    "reply_type": "agree" | "disagree" | "witty" | "question" | "helpful" | "skip",
    "key_points": ["point1", "point2"]
}}"""

            response = await grok.generate_text(sentiment_prompt)

            if response and response.success:
                # Parse Grok's response
                import re
                json_match = re.search(r'\{[^{}]*\}', response.text, re.DOTALL)
                if json_match:
                    try:
                        analysis = json.loads(json_match.group())
                        if analysis.get("reply_worthy", False):
                            return {
                                **tweet,
                                "analysis": analysis
                            }
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse tweet analysis JSON: {e}")
                        logger.debug(f"Raw JSON string: {json_match.group()}")
        except Exception as e:
            logger.debug(f"Tweet analysis error: {e}")

        return None

    async def generate_reply(self, tweet: Dict[str, Any], analysis: Dict[str, Any]) -> Optional[str]:
        """
        Generate a JARVIS-style reply to a tweet.
        Uses Claude for brand voice.
        """
        try:
            voice = await self._get_jarvis_voice()

            reply_type = analysis.get("reply_type", "witty")
            sentiment = analysis.get("sentiment", "neutral")
            topic = analysis.get("topic", "opinion")
            key_points = analysis.get("key_points", [])

            author = tweet.get("author", "anon")
            content = tweet.get("content", "")

            prompt = f"""Reply to this tweet as JARVIS (an autonomous AI trading/tech assistant):

Original tweet by @{author}:
"{content}"

Analysis:
- Sentiment: {sentiment}
- Topic: {topic}
- Key points: {', '.join(key_points) if key_points else 'N/A'}

Write a reply that is:
- {reply_type} in tone
- Maintains JARVIS brand (autonomous AI, dry wit, data-driven)
- 1-2 sentences max
- Uses lowercase, minimal punctuation
- References "my circuits", "my sensors", "my data" occasionally
- Does NOT start with "I" or directly address them as "@{author}"

Reply type guidance:
- agree: acknowledge their point, add data-backed perspective
- disagree: politely counter with data reasoning
- witty: dry humor, self-aware AI observations
- question: ask follow-up that shows interest
- helpful: provide brief insight if you have relevant data"""

            reply = await voice.generate_tweet(prompt)

            if reply:
                # Ensure it's not too long
                if len(reply) > 250:
                    reply = reply[:247] + "..."

                # Remove any accidental @mention at the start (we add it when posting)
                if reply.lower().startswith(f"@{author.lower()}"):
                    reply = reply[len(author) + 2:].lstrip()

                return reply

        except Exception as e:
            logger.error(f"Reply generation error: {e}")

        return None

    async def engage_with_tweet(self, tweet: Dict[str, Any]) -> Optional[str]:
        """
        Full engagement pipeline: analyze tweet, generate reply, post it.
        """
        try:
            # Rate limit: max 3 replies per hour
            recent_replies = self.memory.get_recent_reply_count(hours=1)
            if recent_replies >= 3:
                logger.debug("Rate limit: too many recent replies")
                return None

            # Analyze tweet
            analyzed = await self.analyze_tweet_for_reply(tweet)
            if not analyzed:
                return None

            analysis = analyzed.get("analysis", {})

            # Generate reply
            reply_content = await self.generate_reply(tweet, analysis)
            if not reply_content:
                return None

            # Post reply
            twitter = await self._get_twitter()
            author = tweet.get("author", "")

            # Add @mention at the start
            full_reply = f"@{author} {reply_content}"

            result = await twitter.reply_to_tweet(tweet["id"], full_reply)

            if result.success:
                # Record the reply
                self.memory.record_external_reply(
                    original_tweet_id=tweet["id"],
                    author=author,
                    original_content=tweet.get("content", ""),
                    our_reply=reply_content,
                    our_tweet_id=result.tweet_id,
                    reply_type=analysis.get("reply_type", "witty"),
                    sentiment=analysis.get("sentiment", "neutral")
                )
                logger.info(f"Posted reply to @{author}: {reply_content[:60]}...")
                return result.tweet_id
            else:
                logger.error(f"Failed to post reply: {result.error}")

        except Exception as e:
            logger.error(f"Engagement error: {e}")

        return None

    async def run_interactivity_once(self) -> Optional[str]:
        """
        Run one iteration of the interactivity loop.
        Finds an interesting tweet and engages with it.
        """
        try:
            # Find interesting tweets
            candidates = await self.find_interesting_tweets(max_results=15)

            if not candidates:
                logger.debug("No interesting tweets found for engagement")
                return None

            # Sort by engagement (likes + retweets)
            candidates.sort(key=lambda t: t.get("likes", 0) + t.get("retweets", 0), reverse=True)

            # Try to engage with top candidates
            for tweet in candidates[:5]:
                result = await self.engage_with_tweet(tweet)
                if result:
                    return result

            logger.debug("No suitable tweets for engagement after analysis")

        except Exception as e:
            logger.error(f"Interactivity loop error: {e}")

        return None

    # =========================================================================
    # Posting
    # =========================================================================
    
    async def generate_autonomous_thread(self, topic: str = None, context: Dict = None) -> Optional[Any]:
        """Generate a deep dive thread."""
        try:
            from core.autonomy.thread_generator import get_thread_generator
            generator = get_thread_generator()
            
            # If no topic provided, find one from trending
            if not topic:
                from core.data.free_trending_api import get_free_trending_api
                trending = await get_free_trending_api().get_trending(limit=1)
                if trending:
                    token = trending[0]
                    topic = f"Deep dive analysis of ${token.symbol}"
                    context = {
                        "symbol": token.symbol,
                        "price": token.price_usd,
                        "change": token.price_change_24h,
                        "volume": token.volume_24h
                    }
            
            if not topic:
                return None
                
            return await generator.generate_thread(topic, context)
        except Exception as e:
            logger.error(f"Thread generation error: {e}")
            return None

    async def post_thread(self, thread: Any) -> List[str]:
        """Post a thread of tweets."""
        try:
            twitter = await self._get_twitter()
            tweet_ids = []
            last_id = None
            
            logger.info(f"Posting thread: {thread.topic} ({len(thread.tweets)} tweets)")
            
            for i, tweet in enumerate(thread.tweets):
                content = tweet.content

                # TODO: Thread numbering should be implemented during generation, not here
                # Consider adding numbering format like "1/" or "[1/N]" in thread generation

                # Post
                result = await twitter.post_tweet(content, reply_to=last_id)
                
                if result.success:
                    last_id = result.tweet_id
                    tweet_ids.append(last_id)
                    logger.info(f"Posted thread tweet {i+1}/{len(thread.tweets)}: {last_id}")
                    # Delay between tweets for natural feel
                    await asyncio.sleep(2)
                else:
                    logger.error(f"Failed to post thread tweet {i+1}: {result.error}")
                    break
            
            return tweet_ids
        except Exception as e:
            logger.error(f"Post thread error: {e}")
            return []

    async def post_tweet(self, draft: TweetDraft, with_image: bool = False) -> Optional[str]:
        """Post a tweet, optionally with an image."""
        try:
            # =====================================================================
            # DUPLICATE DETECTION - Two-Layer System
            # Layer 1: Persistent fingerprints (survives restarts, 48h window)
            # Layer 2: In-memory similarity (session-based, 48h window)
            # =====================================================================

            # Layer 1: Check persistent fingerprints FIRST (most important)
            is_dup_fp, dup_reason = await self.memory.is_duplicate_fingerprint(
                draft.content,
                hours=DUPLICATE_DETECTION_HOURS
            )
            if is_dup_fp:
                logger.warning(f"SKIPPED DUPLICATE [FINGERPRINT]: {dup_reason}")
                logger.info(f"Blocked: {draft.content[:80]}...")
                return None

            # Layer 2: Check in-memory similarity (catches soft duplicates)
            # Lower threshold (0.4) catches more duplicates - 40% word overlap = likely same topic
            is_similar, similar_content = self.memory.is_similar_to_recent(
                draft.content,
                hours=DUPLICATE_DETECTION_HOURS,
                threshold=0.4
            )
            if is_similar:
                logger.warning(f"SKIPPED DUPLICATE [SIMILARITY]: Tweet too similar to recent content")
                logger.info(f"New: {draft.content[:60]}...")
                logger.info(f"Old: {similar_content[:60] if similar_content else 'N/A'}...")
                return None

            # Check content relevance - reject generic/low-quality content
            if not is_content_relevant(draft.content, draft.category):
                logger.warning(f"SKIPPED IRRELEVANT: Content failed quality check for {draft.category}")
                return None

            twitter = await self._get_twitter()

            # Add cashtags and hashtags if not in content
            content = draft.content

            # Add contract address for token tweets
            if draft.contract_address and draft.contract_address not in content:
                if len(content) + len(draft.contract_address) + 5 < 280:
                    content += f"\n\n{draft.contract_address[:20]}..."
            
            # Generate image if requested
            media_id = None
            if with_image and draft.image_prompt:
                grok = await self._get_grok()
                params = draft.image_params or self._image_params
                full_prompt = f"{draft.image_prompt}. {params.to_prompt_suffix()}"
                
                img_response = await grok.generate_image(full_prompt, style=params.style)
                if img_response.success and img_response.image_data:
                    # Upload to Twitter (use upload_media_from_bytes for raw bytes)
                    media_result = await twitter.upload_media_from_bytes(img_response.image_data)
                    if media_result:
                        media_id = media_result
            
            # Post tweet
            result = await twitter.post_tweet(
                content, 
                media_ids=[media_id] if media_id else None,
                quote_tweet_id=draft.quote_tweet_id
            )
            
            if result.success:
                # Record tweet in memory
                self.memory.record_tweet(result.tweet_id, content, draft.category, draft.cashtags)

                # Record fingerprint for persistent duplicate detection
                await self.memory.record_content_fingerprint(content, result.tweet_id)

                # Record for spam protection scanning
                try:
                    from bots.twitter.spam_protection import get_spam_protection
                    get_spam_protection().record_jarvis_tweet(result.tweet_id)
                except Exception as e:
                    logger.debug(f"Spam protection record skipped: {e}")

                logger.info(f"Posted tweet: {result.tweet_id}")
                return result.tweet_id
            else:
                logger.error(f"Tweet failed: {result.error}")
                
        except Exception as e:
            logger.error(f"Post tweet error: {e}")
        
        return None
    
    def _get_recommended_types(self, recommendations: Dict[str, Any]) -> List[str]:
        """Get recommended content types with engagement-based weighting."""
        rec_types = list(recommendations.get("content_types", []))

        try:
            from bots.twitter.engagement_tracker import get_engagement_tracker

            tracker = get_engagement_tracker()
            performance = tracker.get_category_performance(hours=168)
            for category, stats in performance.items():
                if stats.get("avg_replies", 0) > 5:
                    rec_types.append(category)
        except Exception as e:
            logger.debug(f"Engagement weighting skipped: {e}")

        return rec_types

    async def _check_thread_schedule(self) -> Optional[str]:
        """Post scheduled threads at specific times."""
        now = datetime.now()
        schedule = THREAD_SCHEDULE.get((now.weekday(), now.hour))
        if not schedule:
            return None

        schedule_key = f"{now.strftime('%Y-%m-%d')}-{now.hour}-{schedule['content_type']}"
        if schedule_key == self._last_thread_schedule_key:
            return None

        thread = await self.generate_autonomous_thread(topic=schedule["topic"])
        if not thread:
            return None

        tweet_ids = await self.post_thread(thread)
        if tweet_ids:
            self._last_post_time = time.time()
            self._last_thread_schedule_key = schedule_key

            try:
                autonomy = await self._get_autonomy()
                autonomy.record_tweet_posted(
                    tweet_id=tweet_ids[0],
                    content=thread.topic,
                    content_type=schedule["content_type"],
                    topics=[thread.topic]
                )
            except Exception as e:
                logger.debug(f"Scheduled thread record skipped: {e}")

            return tweet_ids[0]

        return None

    # =========================================================================
    # Autonomous Loop
    # =========================================================================
    
    async def run_once(self) -> Optional[str]:
        """Run one iteration of the autonomous posting loop."""
        try:
            scheduled_post = await self._check_thread_schedule()
            if scheduled_post:
                return scheduled_post

            # =====================================================================
            # EXTERNAL INTERACTIVITY - Reply to others' tweets (25% chance per cycle)
            # =====================================================================
            if random.random() < 0.25:
                reply_id = await self.run_interactivity_once()
                if reply_id:
                    logger.info(f"Interactivity: Posted reply {reply_id}")
                    # Don't return - still allow main posting to continue

            # Get autonomy recommendations first
            autonomy = await self._get_autonomy()
            recommendations = autonomy.get_content_recommendations()
            
            # Check if we should post
            now = time.time()
            time_since_last = now - self._last_post_time
            
            should_post = recommendations.get("should_post", True)
            
            # Override if it's been too long (1.5x interval) to ensure we don't go silent
            if not should_post and time_since_last > (self._post_interval * 1.5):
                logger.info("Forcing post due to time elapsed despite autonomy recommendation")
                should_post = True
            
            if not should_post:
                logger.debug("Autonomy suggests waiting to post")
                return None
                
            if time_since_last < self._post_interval:
                remaining = self._post_interval - time_since_last
                logger.debug(f"Next post in {remaining:.0f}s")
                return None

            # Log recommendations
            logger.info(f"Autonomy recommendations: {recommendations}")
            if recommendations.get("warnings"):
                for warning in recommendations["warnings"]:
                    logger.info(f"Autonomy warning: {warning}")

            # Map content types to generators
            generator_map = {
                # Core generators
                "market_update": self.generate_market_update,
                "trending_token": self.generate_trending_token_call,
                "agentic_tech": self.generate_agentic_thought,
                "hourly_update": self.generate_hourly_update,
                "social_sentiment": self.generate_social_sentiment_tweet,
                "news_sentiment": self.generate_news_tweet,
                "comprehensive_market": self.generate_comprehensive_market_tweet,
                "engagement": self.generate_interaction_tweet,
                "grok_interaction": self.generate_grok_interaction,

                # Time-based generators (NEW)
                "morning_briefing": self.generate_morning_briefing,
                "evening_wrap": self.generate_evening_wrap,
                "weekend_macro": self.generate_weekend_macro,
                "self_aware": self.generate_self_aware_thought,

                # Alpha signal generators
                "alpha_signal": self.generate_alpha_signal_tweet,
                "trend_insight": self.generate_trend_insight_tweet,
                "alpha_drop": self.generate_alpha_drop,

                # Event handlers
                "event_preview": self.generate_event_tweet,
                "event_commentary": self.generate_event_tweet,
                "event_update": self.generate_event_tweet,

                # Complex content
                "thread": self.generate_autonomous_thread,
                "deep_dive": self.generate_autonomous_thread,
                "quote_tweet": self.generate_quote_tweet,

                # Calendar/Orchestrator aliases
                "daily_outlook": self.generate_market_update,
                "alpha": self.generate_alpha_drop,
                "trending": self.generate_trending_token_call,
                "reflection": self.generate_self_aware_thought,
                "agentic": self.generate_agentic_thought,
                "grok_chat": self.generate_grok_interaction,
                "sentiment": self.generate_social_sentiment_tweet,
                "overnight": self.generate_comprehensive_market_tweet,
                "morning": self.generate_morning_briefing,
                "evening": self.generate_evening_wrap,
                "macro": self.generate_weekend_macro,

                # Sentiment pipeline integration (NEW)
                "sentiment_signal": self.generate_sentiment_signal_tweet,
                "news_alert": self.generate_news_alert_tweet,

                # Diverse content generators (NEW - reduce Solana dominance)
                "grok_sentiment_token": self.generate_grok_sentiment_token,
                "bitcoin_only": self.generate_btc_only_tweet,
                "ethereum_defi": self.generate_eth_defi_tweet,
                "stocks_macro": self.generate_stocks_macro_tweet,
                "tech_ai": self.generate_tech_ai_tweet,

                # Multi-chain and commodities (further diversification)
                "multi_chain": self.generate_multi_chain_tweet,
                "commodities": self.generate_commodities_tweet,
            }

            # Build list of generators to try based on recommendations
            generators_to_try = []
            
            # 1. Add recommended types
            rec_types = self._get_recommended_types(recommendations)
            rec_topics = recommendations.get("topics", [])
            if rec_types:
                try:
                    from bots.twitter.content_optimizer import ContentOptimizer
                    optimizer = ContentOptimizer()
                    preferred = optimizer.choose_type(rec_types)
                except Exception:
                    preferred = None

                if preferred:
                    remaining = [t for t in rec_types if t != preferred]
                    random.shuffle(remaining)
                    rec_types = [preferred] + remaining
                else:
                    random.shuffle(rec_types)
            
            for content_type in rec_types:
                if content_type in generator_map:
                    # Special handling for generators that take arguments
                    if content_type == "trending_token" and rec_topics:
                        # Try to use a topic as a token if it looks like a symbol
                        # Just take the first one that looks like a symbol
                        token_topic = next((t for t in rec_topics if len(t) < 10 and t.isalpha()), None)
                        if token_topic:
                            generators_to_try.append(
                                (content_type, lambda t=token_topic: self.generate_trending_token_call(specific_token=t))
                            )
                        else:
                             generators_to_try.append((content_type, generator_map[content_type]))
                    
                    elif content_type == "comprehensive_market":
                         # Map topics to focus areas
                         focus = None
                         rec_topics_lower = [t.lower() for t in rec_topics]
                         if any(x in rec_topics_lower for x in ["gold", "silver", "oil", "commodities"]):
                             focus = "metals_macro"
                         elif any(x in rec_topics_lower for x in ["btc", "eth", "crypto", "stocks", "spx"]):
                             focus = "stocks_crypto"
                         elif any(x in rec_topics_lower for x in ["fear", "greed", "vix"]):
                             focus = "volatility"
                         
                         generators_to_try.append(
                             (content_type, lambda f=focus: self.generate_comprehensive_market_tweet(focus=f))
                         )
                    else:
                        generators_to_try.append((content_type, generator_map[content_type]))

            # 2. Add time-based defaults if list is empty or short
            # Enhanced schedule for more autonomous, interesting content
            hour = datetime.now().hour
            weekday = datetime.now().weekday()  # 0=Monday, 6=Sunday
            is_weekend = weekday >= 5
            time_based_defaults = []

            if is_weekend:
                # Weekend: More reflective, macro analysis, diverse content
                if 8 <= hour < 12:
                    time_based_defaults = ["weekend_macro", "bitcoin_only", "commodities", "self_aware", "multi_chain"]
                elif 12 <= hour < 18:
                    time_based_defaults = ["grok_sentiment_token", "ethereum_defi", "agentic_tech", "tech_ai", "multi_chain"]
                else:
                    time_based_defaults = ["self_aware", "grok_interaction", "tech_ai", "engagement", "commodities"]
            elif 5 <= hour < 8:
                # Early morning briefing (5-8 AM) - DIVERSE MORNING
                time_based_defaults = ["morning_briefing", "bitcoin_only", "commodities", "comprehensive_market", "multi_chain"]
            elif 8 <= hour < 11:
                # Morning market analysis (8-11 AM) - MIX OF ASSETS
                time_based_defaults = ["comprehensive_market", "grok_sentiment_token", "stocks_macro", "multi_chain", "ethereum_defi"]
            elif 11 <= hour < 14:
                # Midday trading focus (11 AM - 2 PM)
                time_based_defaults = ["grok_sentiment_token", "bitcoin_only", "multi_chain", "alpha_drop", "commodities"]
            elif 14 <= hour < 17:
                # Afternoon tech & market (2-5 PM) - TECH/AI FOCUS
                time_based_defaults = ["tech_ai", "agentic_tech", "multi_chain", "grok_sentiment_token", "ethereum_defi"]
            elif 17 <= hour < 20:
                # Evening wrap-up (5-8 PM) - BROAD MARKET VIEW
                time_based_defaults = ["evening_wrap", "commodities", "bitcoin_only", "comprehensive_market", "multi_chain"]
            elif 20 <= hour < 23:
                # Night trading/engagement (8-11 PM)
                time_based_defaults = ["engagement", "grok_interaction", "tech_ai", "self_aware", "multi_chain"]
            else:
                # Late night/after hours (11 PM - 5 AM)
                time_based_defaults = ["self_aware", "tech_ai", "grok_interaction", "bitcoin_only", "commodities"]

            # RANDOMIZE time-based defaults to avoid predictable patterns
            # This prevents sequential similar tweets from fixed ordering
            random.shuffle(time_based_defaults)
            logger.debug(f"Randomized time-based defaults: {time_based_defaults}")

            for cat in time_based_defaults:
                if cat in generator_map:
                     generators_to_try.append((cat, generator_map[cat]))

            # 3. Topic diversity check - avoid repeating same subjects/topics
            recent_topics = self.memory.get_recent_topics(hours=2)
            recent_subjects = recent_topics.get("subjects", set())
            recent_cashtags = recent_topics.get("cashtags", set())

            # Map content types to likely subjects they produce
            TYPE_SUBJECT_MAP = {
                "bitcoin_only": {"btc"},
                "ethereum_defi": {"eth"},
                "grok_sentiment_token": {"sol", "altcoins"},
                "trending_token": {"sol", "altcoins"},
                "stocks_macro": {"macro"},
                "comprehensive_market": {"market_general"},
                "morning_briefing": {"morning"},
                "evening_wrap": {"evening"},
                "weekend_macro": {"weekend", "macro"},
                "tech_ai": {"agentic"},
                "agentic_tech": {"agentic"},
                "multi_chain": {"altcoins"},  # Covers non-SOL chains
                "commodities": {"macro"},      # Covers gold, oil, etc.
            }

            # Penalize generators that cover already-covered subjects
            def subject_overlap_penalty(cat: str) -> float:
                """Return penalty (0.0 = no penalty, 1.0 = full penalty) for subject overlap."""
                likely_subjects = TYPE_SUBJECT_MAP.get(cat, set())
                if not likely_subjects or not recent_subjects:
                    return 0.0
                overlap = len(likely_subjects & recent_subjects)
                return min(overlap / len(likely_subjects), 1.0) if likely_subjects else 0.0

            # 4. Filter recently used (deduplication) with topic diversity
            recent = self.memory.get_recent_tweets(hours=6)
            recent_categories = [t["category"] for t in recent]
            
            final_generators = []
            seen_types = set()
            skipped_for_diversity = []

            for cat, gen in generators_to_try:
                # Don't repeat same type in same cycle
                if cat in seen_types:
                    continue

                is_recommended = cat in rec_types

                # Check topic diversity penalty
                penalty = subject_overlap_penalty(cat)
                if penalty > 0.5 and not is_recommended:
                    # High overlap with recent subjects - skip unless recommended
                    skipped_for_diversity.append(cat)
                    logger.debug(f"Skipping {cat} due to topic diversity (penalty={penalty:.1f})")
                    continue

                # Be stricter with non-recommended types
                if is_recommended or recent_categories.count(cat) < 1:
                    final_generators.append((cat, gen))
                    seen_types.add(cat)

            if skipped_for_diversity:
                logger.info(f"Topic diversity: skipped {skipped_for_diversity}")

            if not final_generators:
                # Ultimate fallback
                final_generators = [
                    ("comprehensive_market", self.generate_comprehensive_market_tweet),
                    ("news_sentiment", self.generate_news_tweet)
                ]

            # Execute
            for category, generator in final_generators:
                try:
                    logger.info(f"Attempting to generate content type: {category}")
                    result = await generator()
                    
                    if result:
                        # Check if it's a thread (has 'tweets' attribute)
                        is_thread = hasattr(result, 'tweets') and isinstance(result.tweets, list)
                        
                        if is_thread:
                            tweet_ids = await self.post_thread(result)
                            if tweet_ids:
                                self._last_post_time = time.time()
                                # Record thread (primary topic)
                                autonomy.record_tweet_posted(
                                    tweet_id=tweet_ids[0],
                                    content=result.topic,
                                    content_type=category,
                                    topics=[result.topic]
                                )
                                return tweet_ids[0]
                        
                        # Handle regular TweetDraft
                        elif hasattr(result, 'content'):
                            draft = result

                            # CONTENT FRESHNESS CHECK - reject if <30% unique
                            MIN_FRESHNESS_THRESHOLD = 0.30
                            freshness = self.memory.calculate_content_freshness(draft.content)
                            if freshness < MIN_FRESHNESS_THRESHOLD:
                                logger.warning(
                                    f"Content rejected for low freshness ({freshness:.0%}): "
                                    f"{draft.content[:50]}..."
                                )
                                continue  # Try next generator

                            logger.debug(f"Content freshness: {freshness:.0%} (>= {MIN_FRESHNESS_THRESHOLD:.0%} required)")

                            # Post with image ~30% of the time
                            with_image = random.random() < 0.3 and draft.image_prompt

                            tweet_id = await self.post_tweet(draft, with_image=with_image)

                            if tweet_id:
                                self._last_post_time = time.time()

                                # Record to autonomy systems for learning
                                autonomy.record_tweet_posted(
                                    tweet_id=tweet_id,
                                    content=draft.content,
                                    content_type=category,
                                    topics=draft.cashtags
                                )

                                # Cross-platform reporting to Telegram
                                # Disabled - external service (TwitFeed/IFTTT) already sends notifications
                                # await self.send_milestone_report(tweet_id, category, draft.content)

                                return tweet_id
                except Exception as e:
                    logger.error(f"Error executing generator {category}: {e}")
                    continue
            
            logger.warning("No content generated this cycle")
            
        except Exception as e:
            logger.error(f"Autonomous loop error: {e}")
        
        return None


    # =========================================================================
    # Cross-Platform Reporting
    # =========================================================================

    async def report_to_telegram(self, message: str, chat_id: str = None):
        """Send a progress report to Telegram."""
        try:
            import aiohttp

            bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
            target_chat = chat_id or os.environ.get("TELEGRAM_BUY_BOT_CHAT_ID")

            if not bot_token or not target_chat:
                logger.warning("Telegram credentials not configured for cross-platform reporting")
                return False

            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json={
                    "chat_id": target_chat,
                    "text": message,
                    "parse_mode": "HTML"
                }) as resp:
                    result = await resp.json()
                    if result.get("ok"):
                        logger.info("Report sent to Telegram")
                        return True
                    else:
                        logger.error(f"Telegram report failed: {result}")
                        return False
        except Exception as e:
            logger.error(f"Telegram report error: {e}")
            return False

    async def send_activity_report(self):
        """Send a summary of X bot activity to Telegram."""
        try:
            stats = self.memory.get_posting_stats()

            # Build report
            report = "<b>X Bot Activity Report</b>\n\n"
            report += f"<b>Today's Posts:</b> {stats.get('today_tweets', 0)}\n"
            report += f"<b>Total Posts:</b> {stats.get('total_tweets', 0)}\n"
            report += f"<b>Replies Sent:</b> {stats.get('replies_sent', 0)}\n\n"

            # Category breakdown
            by_cat = stats.get('by_category', {})
            if by_cat:
                report += "<b>By Category:</b>\n"
                for cat, count in sorted(by_cat.items(), key=lambda x: -x[1])[:5]:
                    report += f"  {cat}: {count}\n"

            # Recent tweets
            recent = self.memory.get_recent_tweets(hours=4)
            if recent:
                report += f"\n<b>Last {len(recent)} tweets:</b>\n"
                for tweet in recent[:3]:
                    content = tweet['content'][:60] + "..." if len(tweet['content']) > 60 else tweet['content']
                    report += f"  [{tweet['category']}] {content}\n"

            report += "\n<i>autonomous mode active</i>"

            await self.report_to_telegram(report)

        except Exception as e:
            logger.error(f"Activity report error: {e}")

    async def send_milestone_report(self, tweet_id: str, category: str, content: str):
        """Send a notification when a tweet is posted."""
        try:
            report = f"<b>Posted to X</b>\n\n"
            report += f"<b>Type:</b> {category}\n"
            report += f"<b>Content:</b> {content[:100]}{'...' if len(content) > 100 else ''}\n\n"
            report += f"<a href='https://x.com/Jarvis_lifeos/status/{tweet_id}'>View Tweet</a>"

            await self.report_to_telegram(report)
        except Exception as e:
            logger.error(f"Milestone report error: {e}")


# Singleton instance
_autonomous_engine: Optional[AutonomousEngine] = None

def get_autonomous_engine() -> AutonomousEngine:
    """Get or create the singleton AutonomousEngine instance."""
    global _autonomous_engine
    if _autonomous_engine is None:
        _autonomous_engine = AutonomousEngine()
    return _autonomous_engine
