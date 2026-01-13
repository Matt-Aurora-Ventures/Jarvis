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
    
    def was_mention_replied(self, tweet_id: str) -> bool:
        """Check if we already replied to a mention."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM mention_replies WHERE tweet_id = ?", (tweet_id,))
            result = cursor.fetchone() is not None
            conn.close()
            return result
    
    def record_mention_reply(self, tweet_id: str, author: str, reply: str):
        """Record that we replied to a mention."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO mention_replies (tweet_id, author_handle, our_reply, replied_at)
                VALUES (?, ?, ?, ?)
            """, (tweet_id, author, reply, datetime.now(timezone.utc).isoformat()))
            conn.commit()
            conn.close()
    
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
            
            # Replies sent
            cursor.execute("SELECT COUNT(*) FROM mention_replies")
            replies_sent = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                "total_tweets": total,
                "today_tweets": today_count,
                "by_category": by_category,
                "replies_sent": replies_sent
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
        """Get Grok client - used for sentiment/data analysis only, NOT for voice."""
        if self._grok_client is None:
            from bots.twitter.grok_client import GrokClient
            self._grok_client = GrokClient()
        return self._grok_client
    
    async def _get_jarvis_voice(self):
        """Get Jarvis voice generator - uses Anthropic Claude with Jarvis personality."""
        from bots.twitter.jarvis_voice import get_jarvis_voice
        return get_jarvis_voice()
    
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
        """Generate a market update tweet using Jarvis voice (Claude)."""
        try:
            voice = await self._get_jarvis_voice()
            
            # Get market data
            from core.data.free_trending_api import FreeTrendingAPI
            from core.data.free_price_api import get_sol_price
            
            api = FreeTrendingAPI()
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
                return TweetDraft(
                    content=content,
                    category="market_update",
                    cashtags=[f"${top.symbol}"],
                    hashtags=["#Solana"],
                    contract_address=top.address,
                    image_prompt=f"Market chart showing {sentiment} momentum for {top.symbol}",
                    image_params=ImageGenParams(mood=sentiment)
                )
        except Exception as e:
            logger.error(f"Market update generation error: {e}")
        
        return None
    
    async def generate_trending_token_call(self) -> Optional[TweetDraft]:
        """Generate a trending token tweet using Jarvis voice (Claude)."""
        try:
            voice = await self._get_jarvis_voice()
            
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
                        self.memory.record_token_mention(token.symbol, addr, sentiment)
                        return TweetDraft(
                            content=content,
                            category="trending_token" if not should_roast else "roast_polite",
                            cashtags=[f"${token.symbol}"],
                            hashtags=["#Solana"],
                            contract_address=addr
                        )
                    break
                    
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
            
            from core.data.free_trending_api import FreeTrendingAPI
            api = FreeTrendingAPI()
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
                return TweetDraft(
                    content=content,
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
            
            # Decide what to post based on variety AND time of day
            recent = self.memory.get_recent_tweets(hours=6)
            recent_categories = [t["category"] for t in recent]
            
            # Time-based content preferences
            hour = datetime.now().hour
            
            # Morning (6-10): Market updates, set the tone
            # Midday (10-14): Trending tokens, engagement
            # Afternoon (14-18): Agentic thoughts, Grok interactions
            # Evening (18-22): Engagement, community building
            # Night (22-6): Lighter content, agentic musings
            
            if 6 <= hour < 10:
                # Morning - market focus
                generators = [
                    ("market_update", self.generate_market_update),
                    ("hourly_update", self.generate_hourly_update),
                    ("trending_token", self.generate_trending_token_call),
                ]
            elif 10 <= hour < 14:
                # Midday - tokens and engagement
                generators = [
                    ("trending_token", self.generate_trending_token_call),
                    ("engagement", self.generate_interaction_tweet),
                    ("market_update", self.generate_market_update),
                ]
            elif 14 <= hour < 18:
                # Afternoon - thoughts and interactions
                generators = [
                    ("agentic_tech", self.generate_agentic_thought),
                    ("grok_interaction", self.generate_grok_interaction),
                    ("trending_token", self.generate_trending_token_call),
                ]
            elif 18 <= hour < 22:
                # Evening - community and recap
                generators = [
                    ("engagement", self.generate_interaction_tweet),
                    ("hourly_update", self.generate_hourly_update),
                    ("agentic_tech", self.generate_agentic_thought),
                ]
            else:
                # Night - lighter content
                generators = [
                    ("agentic_tech", self.generate_agentic_thought),
                    ("engagement", self.generate_interaction_tweet),
                    ("grok_interaction", self.generate_grok_interaction),
                ]
            
            # Filter out categories we've used recently
            generators = [(cat, gen) for cat, gen in generators if recent_categories.count(cat) < 2]
            
            # Add fallbacks if all filtered out
            if not generators:
                generators = [
                    ("market_update", self.generate_market_update),
                    ("hourly_update", self.generate_hourly_update),
                ]
            
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
    
    async def check_and_reply_mentions(self) -> int:
        """Check for mentions and reply to them. Returns number of replies sent."""
        try:
            twitter = await self._get_twitter()
            voice = await self._get_jarvis_voice()
            
            # Get recent mentions
            mentions = await twitter.get_mentions(max_results=10)
            if not mentions:
                return 0
            
            replies_sent = 0
            for mention in mentions[:5]:  # Process up to 5 mentions per cycle
                tweet_id = mention.get("id")
                text = mention.get("text", "")
                author = mention.get("author_username", "friend")
                
                # Skip if we already replied (check memory)
                if self.memory.was_mention_replied(tweet_id):
                    continue
                
                # Generate a helpful, kind reply
                reply_content = await voice.generate_reply(text, author)
                
                if reply_content:
                    result = await twitter.reply_to_tweet(tweet_id, reply_content)
                    if result.success:
                        self.memory.record_mention_reply(tweet_id, author, reply_content)
                        replies_sent += 1
                        logger.info(f"Replied to @{author}: {reply_content[:50]}...")
            
            return replies_sent
            
        except Exception as e:
            logger.error(f"Mentions check error: {e}")
            return 0
    
    async def generate_interaction_tweet(self) -> Optional[TweetDraft]:
        """Generate an interactive tweet that encourages engagement."""
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
            logger.error(f"Engagement tweet error: {e}")
        return None
    
    async def generate_grok_interaction(self) -> Optional[TweetDraft]:
        """Generate a tweet mentioning big brother Grok."""
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
    
    async def run(self):
        """Run the autonomous engine continuously."""
        self._running = True
        logger.info(f"Autonomous engine started. Posting every {self._post_interval}s")
        
        mention_check_interval = 300  # Check mentions every 5 minutes
        last_mention_check = 0
        
        while self._running:
            try:
                # Check and reply to mentions
                now = time.time()
                if now - last_mention_check > mention_check_interval:
                    replies = await self.check_and_reply_mentions()
                    if replies > 0:
                        logger.info(f"Sent {replies} replies to mentions")
                    last_mention_check = now
                
                # Regular posting
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
