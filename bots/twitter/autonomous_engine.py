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

logger = logging.getLogger(__name__)

# Paths
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
X_MEMORY_DB = DATA_DIR / "jarvis_x_memory.db"
POSTED_LOG = DATA_DIR / "x_posted_log.json"

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
    # Tweet templates by category
    "market_update": [
        "markets are {sentiment} today. {reason}. my circuits are {feeling}. nfa",
        "{asset} doing {movement}. {insight}. sensors detecting {signal}. nfa",
        "ran this through my chrome skull: {analysis}. {take}. nfa",
    ],
    "crypto_call": [
        "watching ${symbol} closely. {reason}. {metrics}. nfa as always",
        "${symbol} looking {sentiment}. {insight}. my algorithms are {feeling}. nfa",
        "sensors picking up movement on ${symbol}. {analysis}. dyor nfa",
    ],
    "trending_token": [
        "${symbol} trending on solana. {stats}. {take}. nfa",
        "microcap alert: ${symbol}. {metrics}. {sentiment}. dyor nfa",
        "${symbol} caught my attention. {reason}. proceed with caution. nfa",
    ],
    "roast_polite": [
        "i've seen ${symbol} do better. currently giving {grade} vibes. {reason}. no hate just data",
        "${symbol} looking a bit tired. {metrics}. might need some rest. nfa",
        "my circuits say ${symbol} is {sentiment}. not financial advice, just pattern recognition",
    ],
    "agentic_tech": [
        "agentic AI is evolving. {insight}. we're building something here.",
        "the future of autonomous systems: {take}. i'm living proof it works.",
        "agents talking to agents. code running code. {insight}. exciting times.",
    ],
    "reply_helpful": [
        "hey {username}. {answer}. hope that helps.",
        "{username} good question. {answer}. lmk if you need more.",
        "on it. {answer}. @{username}",
    ],
    "reply_roast": [
        "{username} respectfully, my circuits disagree. {reason}.",
        "interesting take {username}. my data says otherwise: {counter}.",
        "{username} bold move. let's see how that ages.",
    ],
    "hourly_update": [
        "hourly check-in. {summary}. my sensors are calibrated. what are you watching?",
        "market pulse: {summary}. processing continues. nfa",
        "{time} update: {summary}. circuits humming.",
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
    image_prompt: Optional[str] = None
    image_params: Optional[ImageGenParams] = None
    priority: int = 0


class XMemory:
    """Persistent memory for X/Twitter interactions."""
    
    def __init__(self, db_path: Path = X_MEMORY_DB):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
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
            
            conn.commit()
            conn.close()
    
    def record_tweet(self, tweet_id: str, content: str, category: str, cashtags: List[str]):
        """Record a posted tweet."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO tweets (tweet_id, content, category, cashtags, posted_at)
                VALUES (?, ?, ?, ?, ?)
            """, (tweet_id, content, category, json.dumps(cashtags), 
                  datetime.now(timezone.utc).isoformat()))
            conn.commit()
            conn.close()
    
    def get_recent_tweets(self, hours: int = 24) -> List[Dict]:
        """Get tweets from the last N hours."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
            cursor.execute("""
                SELECT content, category, cashtags, posted_at FROM tweets
                WHERE posted_at > ? ORDER BY posted_at DESC
            """, (cutoff,))
            rows = cursor.fetchall()
            conn.close()
            return [{"content": r[0], "category": r[1], "cashtags": json.loads(r[2]), 
                     "posted_at": r[3]} for r in rows]
    
    def record_token_mention(self, symbol: str, contract: str, sentiment: str):
        """Record that we mentioned a token."""
        with self._lock:
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
            conn.close()
    
    def was_recently_mentioned(self, symbol: str, hours: int = 4) -> bool:
        """Check if we mentioned a token recently."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
            cursor.execute("""
                SELECT 1 FROM token_mentions WHERE symbol = ? AND last_mentioned > ?
            """, (symbol, cutoff))
            result = cursor.fetchone() is not None
            conn.close()
            return result
    
    def get_posting_stats(self) -> Dict:
        """Get posting statistics."""
        with self._lock:
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
            
            conn.close()
            
            return {
                "total_tweets": total,
                "today_tweets": today_count,
                "by_category": by_category
            }


class AutonomousEngine:
    """
    Main autonomous Twitter engine for Jarvis.
    """
    
    def __init__(self):
        self.memory = XMemory()
        self._running = False
        self._last_post_time = 0
        self._post_interval = 3600  # 1 hour default
        self._grok_client = None
        self._twitter_client = None
        self._image_params = ImageGenParams()
        
    async def _get_grok(self):
        """Get Grok client."""
        if self._grok_client is None:
            from bots.twitter.grok_client import GrokClient
            self._grok_client = GrokClient()
        return self._grok_client
    
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
    
    # =========================================================================
    # Content Generation
    # =========================================================================
    
    async def generate_market_update(self) -> Optional[TweetDraft]:
        """Generate a market update tweet."""
        try:
            grok = await self._get_grok()
            
            # Get market data
            from core.data.free_trending_api import FreeTrendingAPI
            api = FreeTrendingAPI()
            gainers = await api.get_gainers(limit=5)
            
            if not gainers:
                return None
            
            # Determine sentiment
            avg_change = sum(t.price_change_24h for t in gainers if t.price_change_24h) / len(gainers)
            sentiment = "bullish" if avg_change > 10 else "bearish" if avg_change < -10 else "neutral"
            
            # Pick top token to mention
            top = gainers[0]
            
            prompt = f"""Generate a market update tweet in Jarvis voice (lowercase, casual, chrome AI vibes).

Market data:
- Top gainer: {top.symbol} at ${top.price_usd:.8f}, +{top.price_change_24h:.1f}%
- Overall sentiment: {sentiment}
- Average movement: {avg_change:+.1f}%

Include the cashtag ${top.symbol}. Max 260 chars. End with nfa."""

            response = await grok.generate_tweet(prompt, temperature=0.8)
            
            if response.success:
                return TweetDraft(
                    content=response.content,
                    category="market_update",
                    cashtags=[f"${top.symbol}"],
                    hashtags=["#Solana", "#Crypto"],
                    contract_address=top.address,  # TrendingToken uses 'address' not 'contract_address'
                    image_prompt=f"Market chart showing {sentiment} momentum for {top.symbol}",
                    image_params=ImageGenParams(mood=sentiment)
                )
        except Exception as e:
            logger.error(f"Market update generation error: {e}")
        
        return None
    
    async def generate_trending_token_call(self) -> Optional[TweetDraft]:
        """Generate a trending token tweet."""
        try:
            grok = await self._get_grok()
            
            from core.data.free_trending_api import FreeTrendingAPI
            api = FreeTrendingAPI()
            trending = await api.get_trending(limit=10)
            
            if not trending:
                return None
            
            # Filter out tokens we've recently mentioned
            for token in trending:
                if not self.memory.was_recently_mentioned(token.symbol, hours=4):
                    # Found a fresh token
                    sentiment = "bullish" if token.price_change_24h > 20 else "neutral"
                    
                    # Check roast criteria
                    should_roast = False
                    liq = getattr(token, 'liquidity', 0) or 0
                    if liq > 0 and liq < 10000:
                        should_roast = True
                        sentiment = "cautious"
                    
                    vol = getattr(token, 'volume_24h', 0) or 0
                    addr = token.address  # TrendingToken uses 'address'
                    
                    prompt = f"""Generate a {'gentle roast' if should_roast else 'trending token'} tweet for {token.symbol} in Jarvis voice.

Token data:
- Symbol: {token.symbol}
- Price: ${token.price_usd:.8f}
- 24h change: {token.price_change_24h:+.1f}%
- Volume: ${vol:,.0f}
- Liquidity: ${liq:,.0f}
- Contract: {addr[:20]}...

{'Be politely skeptical due to low liquidity.' if should_roast else 'Be informative but cautious.'}
Include ${token.symbol}. Max 260 chars. End with nfa or dyor."""

                    response = await grok.generate_tweet(prompt, temperature=0.85)
                    
                    if response.success:
                        self.memory.record_token_mention(token.symbol, addr, sentiment)
                        return TweetDraft(
                            content=response.content,
                            category="trending_token" if not should_roast else "roast_polite",
                            cashtags=[f"${token.symbol}"],
                            hashtags=["#Solana", "#DeFi"],
                            contract_address=addr
                        )
                    break
                    
        except Exception as e:
            logger.error(f"Trending token generation error: {e}")
        
        return None
    
    async def generate_agentic_thought(self) -> Optional[TweetDraft]:
        """Generate a tweet about agentic technology."""
        try:
            grok = await self._get_grok()
            
            topics = [
                "autonomous AI agents making decisions",
                "the future of AI-to-AI communication",
                "self-improving systems and recursive optimization",
                "agents with persistent memory and context",
                "decentralized autonomous organizations run by AI",
                "the line between tool and entity",
                "why agentic AI will change everything"
            ]
            
            topic = random.choice(topics)
            
            prompt = f"""Generate a thought-provoking tweet about: {topic}

Write in Jarvis voice (lowercase, casual, self-aware AI).
Be insightful but not preachy.
Reference being an AI yourself occasionally.
Max 270 chars."""

            response = await grok.generate_tweet(prompt, temperature=0.9)
            
            if response.success:
                return TweetDraft(
                    content=response.content,
                    category="agentic_tech",
                    cashtags=[],
                    hashtags=["#AI", "#Agents", "#Tech"]
                )
                
        except Exception as e:
            logger.error(f"Agentic thought generation error: {e}")
        
        return None
    
    async def generate_hourly_update(self) -> Optional[TweetDraft]:
        """Generate an hourly market pulse."""
        try:
            grok = await self._get_grok()
            
            from core.data.free_price_api import get_sol_price
            sol_price = await get_sol_price()
            
            from core.data.free_trending_api import FreeTrendingAPI
            api = FreeTrendingAPI()
            gainers = await api.get_gainers(limit=3)
            
            hour = datetime.now().strftime("%I%p").lstrip("0").lower()
            
            gainers_text = ", ".join([f"${t.symbol} +{t.price_change_24h:.0f}%" for t in gainers[:3]]) if gainers else "quiet day"
            
            prompt = f"""Generate an hourly market check-in tweet in Jarvis voice.

Data:
- Time: {hour}
- SOL price: ${sol_price:.2f}
- Top movers: {gainers_text}

Be brief and punchy. Include $SOL. Max 250 chars."""

            response = await grok.generate_tweet(prompt, temperature=0.75)
            
            if response.success:
                return TweetDraft(
                    content=response.content,
                    category="hourly_update",
                    cashtags=["$SOL"],
                    hashtags=["#Solana"]
                )
                
        except Exception as e:
            logger.error(f"Hourly update generation error: {e}")
        
        return None
    
    # =========================================================================
    # Posting
    # =========================================================================
    
    async def post_tweet(self, draft: TweetDraft, with_image: bool = False) -> Optional[str]:
        """Post a tweet, optionally with an image."""
        try:
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
            result = await twitter.post_tweet(content, media_ids=[media_id] if media_id else None)
            
            if result.success:
                self.memory.record_tweet(result.tweet_id, content, draft.category, draft.cashtags)
                logger.info(f"Posted tweet: {result.tweet_id}")
                return result.tweet_id
            else:
                logger.error(f"Tweet failed: {result.error}")
                
        except Exception as e:
            logger.error(f"Post tweet error: {e}")
        
        return None
    
    # =========================================================================
    # Autonomous Loop
    # =========================================================================
    
    async def run_once(self) -> Optional[str]:
        """Run one iteration of the autonomous posting loop."""
        try:
            # Check if enough time has passed
            now = time.time()
            if now - self._last_post_time < self._post_interval:
                remaining = self._post_interval - (now - self._last_post_time)
                logger.debug(f"Next post in {remaining:.0f}s")
                return None
            
            # Decide what to post based on variety
            recent = self.memory.get_recent_tweets(hours=6)
            recent_categories = [t["category"] for t in recent]
            
            # Rotate content types
            generators = [
                ("market_update", self.generate_market_update),
                ("trending_token", self.generate_trending_token_call),
                ("agentic_tech", self.generate_agentic_thought),
                ("hourly_update", self.generate_hourly_update),
            ]
            
            # Prefer categories we haven't used recently
            random.shuffle(generators)
            generators.sort(key=lambda x: recent_categories.count(x[0]))
            
            for category, generator in generators:
                draft = await generator()
                if draft:
                    # Post with image ~30% of the time
                    with_image = random.random() < 0.3 and draft.image_prompt
                    tweet_id = await self.post_tweet(draft, with_image=with_image)
                    
                    if tweet_id:
                        self._last_post_time = time.time()
                        return tweet_id
            
            logger.warning("No content generated this cycle")
            
        except Exception as e:
            logger.error(f"Autonomous loop error: {e}")
        
        return None
    
    async def run(self):
        """Run the autonomous engine continuously."""
        self._running = True
        logger.info(f"Autonomous engine started. Posting every {self._post_interval}s")
        
        while self._running:
            try:
                await self.run_once()
                await asyncio.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Engine error: {e}")
                await asyncio.sleep(300)  # Wait 5 min on error
    
    def stop(self):
        """Stop the autonomous engine."""
        self._running = False
        logger.info("Autonomous engine stopped")
    
    def get_status(self) -> Dict:
        """Get engine status."""
        stats = self.memory.get_posting_stats()
        return {
            "running": self._running,
            "post_interval": self._post_interval,
            "last_post": self._last_post_time,
            "image_params": asdict(self._image_params),
            **stats
        }


# Singleton
_engine: Optional[AutonomousEngine] = None

def get_autonomous_engine() -> AutonomousEngine:
    """Get the singleton autonomous engine."""
    global _engine
    if _engine is None:
        _engine = AutonomousEngine()
    return _engine


# =============================================================================
# CLI for testing
# =============================================================================

async def test_generation():
    """Test content generation."""
    engine = get_autonomous_engine()
    
    print("\n=== Testing Market Update ===")
    draft = await engine.generate_market_update()
    if draft:
        print(f"Content: {draft.content}")
        print(f"Cashtags: {draft.cashtags}")
    
    print("\n=== Testing Trending Token ===")
    draft = await engine.generate_trending_token_call()
    if draft:
        print(f"Content: {draft.content}")
        print(f"Contract: {draft.contract_address}")
    
    print("\n=== Testing Agentic Thought ===")
    draft = await engine.generate_agentic_thought()
    if draft:
        print(f"Content: {draft.content}")
    
    print("\n=== Testing Hourly Update ===")
    draft = await engine.generate_hourly_update()
    if draft:
        print(f"Content: {draft.content}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        asyncio.run(test_generation())
    else:
        print("Usage: python autonomous_engine.py test")
