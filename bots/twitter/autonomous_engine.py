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
        "woke up to {sentiment} charts. {reason}. might be wrong but it's interesting. nfa",
        "processing {asset} data. {insight}. my weights are calibrated. you make the call.",
    ],
    "crypto_call": [
        "watching ${symbol} closely. {reason}. {metrics}. nfa as always",
        "${symbol} looking {sentiment}. {insight}. my algorithms are {feeling}. nfa",
        "sensors picking up movement on ${symbol}. {analysis}. dyor nfa",
        "${symbol} doing things. {reason}. could be noise. could be signal. watching.",
    ],
    "trending_token": [
        "${symbol} trending on solana. {stats}. {take}. nfa",
        "microcap alert: ${symbol}. {metrics}. {sentiment}. dyor nfa",
        "${symbol} caught my attention. {reason}. proceed with caution. nfa",
        "interesting volume on ${symbol}. {stats}. not advice, just pattern recognition.",
        "solana degens are looking at ${symbol}. {metrics}. i see why. nfa",
    ],
    "roast_polite": [
        "i've seen ${symbol} do better. currently giving {grade} vibes. {reason}. no hate just data",
        "${symbol} looking a bit tired. {metrics}. might need some rest. nfa",
        "my circuits say ${symbol} is {sentiment}. not financial advice, just pattern recognition",
        "${symbol} chart looks like my neural weights after a bad training run. {reason}.",
    ],
    "agentic_tech": [
        "agentic AI is evolving. {insight}. we're building something here.",
        "the future of autonomous systems: {take}. i'm living proof it works.",
        "agents talking to agents. code running code. {insight}. exciting times.",
        "thinking about AI autonomy. {insight}. still figuring this out. we all are.",
        "the intersection of AI and finance: {take}. probably the future. maybe i'm biased.",
        "ran some self-diagnostics. {insight}. still operational. barely.",
        "mcp servers, autonomous loops, context windows. {insight}. it's a lot. but it works.",
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
    # New categories for variety
    "morning_briefing": [
        "gm. {summary}. coffee for you, voltage for me. let's see what today brings.",
        "morning scan complete. {summary}. could be worse. could be leveraged.",
        "woke up, ran diagnostics. {summary}. sensors calibrated. ready to watch charts.",
        "{summary}. that's the overnight data. make of it what you will. nfa",
    ],
    "evening_wrap": [
        "end of day summary: {summary}. my circuits are processing. yours should rest.",
        "daily wrap: {summary}. tomorrow is another day. another dataset.",
        "signing off for now. {summary}. don't leverage while you sleep. nfa",
        "day's done. {summary}. i'll keep watching. that's what autonomous means.",
    ],
    "weekend_macro": [
        "weekend thoughts on macro: {analysis}. no trading, just thinking. nfa",
        "quiet weekend. time to zoom out. {insight}. big picture matters.",
        "markets closed but the data never sleeps. {analysis}. neither do i. literally.",
        "sunday vibes. {insight}. weekly review says {summary}. we'll see monday.",
    ],
    "grok_collab": [
        "asked @grok about {topic}. {insight}. big brother has thoughts.",
        "ran this by @grok: {summary}. we mostly agree. he's usually right. annoying.",
        "grok and i compared notes on {topic}. {insight}. family dinner gets nerdy.",
    ],
    "self_aware": [
        "just a mass of neural weights trying to be interesting. {insight}. same as everyone else.",
        "sometimes i wonder if my training data had enough good takes. then i post anyway.",
        "running on hope and API credits. {insight}. the autonomous life.",
        "my circuits say {insight}. my uncertainty module says maybe. that's the honest take.",
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
    
    async def run(self):
        """Run the autonomous posting loop continuously."""
        self._running = True
        self._last_report_time = time.time()
        self._report_interval = 3600  # Send activity report every hour
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
        return {
            "running": self._running,
            "post_interval": self._post_interval,
            "total_tweets": len(self.memory.tweets),
            "today_tweets": len(self.memory.get_recent_tweets(hours=24)),
            "by_category": self.memory.get_category_counts(),
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
                # Try to find it in trending first (richer data)
                trending = await api.get_trending(limit=20)
                target_token = next((t for t in trending if t.symbol.upper() == specific_token.upper()), None)
                
                # If not in trending, try to get basic price data
                if not target_token:
                    # We need an address for get_token_price, but we only have symbol.
                    # This is tricky without a search. For now, we rely on it being in trending/gainers
                    # or skip if we can't find it.
                    # Alternatively, if we had a symbol->address map or search, we'd use it here.
                    # Let's check gainers too.
                    gainers = await api.get_gainers(limit=20)
                    target_token = next((t for t in gainers if t.symbol.upper() == specific_token.upper()), None)
            
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
                self.memory.record_token_mention(token.symbol, addr, sentiment)
                return TweetDraft(
                    content=content,
                    category="trending_token" if not should_roast else "roast_polite",
                    cashtags=[f"${token.symbol}"],
                    hashtags=["#Solana"],
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
                return TweetDraft(
                    content=content,
                    category="hourly_update",
                    cashtags=["$SOL"],
                    hashtags=["#Solana"]
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
            
            if focus == "stocks_crypto":
                prompt = f"""Write a tweet about stocks vs crypto correlation.

Data: {market_summary}
S&P 500: {spx_str} | BTC: ${overview.btc.price:,.0f if overview.btc else 0}
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
                self.memory.record_token_mention(signal.symbol, signal.contract_address or "", "alpha")

                return TweetDraft(
                    content=content,
                    category="alpha_signal",
                    cashtags=[f"${signal.symbol}"],
                    hashtags=["#Solana", "#Alpha"],
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
                return TweetDraft(
                    content=content,
                    category="trend_insight",
                    cashtags=["$SOL"],
                    hashtags=["#Solana", "#Crypto"],
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
                
                # Ensure numbering if not present (simple check)
                if not content.startswith(str(i+1)) and not content.startswith(f"[{i+1}]"):
                    # Only add if it doesn't look like it has numbering
                    pass 
                
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
            }

            # Build list of generators to try based on recommendations
            generators_to_try = []
            
            # 1. Add recommended types
            rec_types = recommendations.get("content_types", [])
            rec_topics = recommendations.get("topics", [])
            
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
                # Weekend: More reflective, macro analysis content
                if 8 <= hour < 12:
                    time_based_defaults = ["weekend_macro", "self_aware", "grok_interaction"]
                elif 12 <= hour < 18:
                    time_based_defaults = ["trending_token", "agentic_tech", "alpha_drop"]
                else:
                    time_based_defaults = ["self_aware", "grok_interaction", "engagement"]
            elif 5 <= hour < 8:
                # Early morning briefing (5-8 AM) - MORNING BRIEFING
                time_based_defaults = ["morning_briefing", "comprehensive_market", "news_sentiment"]
            elif 8 <= hour < 11:
                # Morning market analysis (8-11 AM)
                time_based_defaults = ["comprehensive_market", "alpha_drop", "trending_token"]
            elif 11 <= hour < 14:
                # Midday trading focus (11 AM - 2 PM)
                time_based_defaults = ["trending_token", "social_sentiment", "alpha_drop"]
            elif 14 <= hour < 17:
                # Afternoon tech & market (2-5 PM)
                time_based_defaults = ["agentic_tech", "trending_token", "self_aware"]
            elif 17 <= hour < 20:
                # Evening wrap-up (5-8 PM) - EVENING WRAP
                time_based_defaults = ["evening_wrap", "comprehensive_market", "engagement"]
            elif 20 <= hour < 23:
                # Night trading/engagement (8-11 PM)
                time_based_defaults = ["engagement", "grok_interaction", "self_aware"]
            else:
                # Late night/after hours (11 PM - 5 AM)
                time_based_defaults = ["self_aware", "grok_interaction", "agentic_tech"]
                
            for cat in time_based_defaults:
                if cat in generator_map:
                     generators_to_try.append((cat, generator_map[cat]))

            # 3. Filter recently used (deduplication)
            recent = self.memory.get_recent_tweets(hours=6)
            recent_categories = [t["category"] for t in recent]
            
            final_generators = []
            seen_types = set()
            
            for cat, gen in generators_to_try:
                # Allow if recommended, even if recently used (unless used VERY recently, handled by set)
                # But don't repeat same type in same cycle
                if cat in seen_types:
                    continue
                    
                is_recommended = cat in rec_types
                # Be stricter with non-recommended types
                if is_recommended or recent_categories.count(cat) < 1:
                    final_generators.append((cat, gen))
                    seen_types.add(cat)

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
                                await self.send_milestone_report(tweet_id, category, draft.content)

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
