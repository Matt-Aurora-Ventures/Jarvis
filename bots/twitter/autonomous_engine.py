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
    Now integrated with full autonomy system.
    """
    
    def __init__(self):
        self.memory = XMemory()
        self._running = False
        self._last_post_time = 0
        self._post_interval = 3600  # 1 hour default
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
    
    async def generate_social_sentiment_tweet(self) -> Optional[TweetDraft]:
        """Generate a comprehensive market sentiment tweet using Grok analysis."""
        try:
            voice = await self._get_jarvis_voice()
            grok = await self._get_grok()
            
            # Get comprehensive market data
            from core.data.free_price_api import get_sol_price, FreePriceAPI
            from core.data.free_trending_api import FreeTrendingAPI
            
            sol_price = await get_sol_price()
            api = FreeTrendingAPI()
            
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
            from core.data.free_trending_api import FreeTrendingAPI
            
            sol_price = await get_sol_price()
            api = FreeTrendingAPI()
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
    
    async def generate_comprehensive_market_tweet(self) -> Optional[TweetDraft]:
        """Generate a comprehensive market sentiment tweet covering multiple asset classes."""
        try:
            voice = await self._get_jarvis_voice()
            grok = await self._get_grok()
            
            from core.data.market_data_api import get_market_api
            market_api = get_market_api()
            
            # Get comprehensive market overview
            overview = await market_api.get_market_overview()
            
            # Build market summary for Grok analysis
            summary_parts = []
            
            # Crypto
            if overview.btc:
                btc_dir = "up" if (overview.btc.change_pct or 0) > 0 else "down"
                summary_parts.append(f"BTC ${overview.btc.price:,.0f} ({btc_dir} {abs(overview.btc.change_pct or 0):.1f}%)")
            if overview.sol:
                sol_dir = "up" if (overview.sol.change_pct or 0) > 0 else "down"
                summary_parts.append(f"SOL ${overview.sol.price:.2f} ({sol_dir} {abs(overview.sol.change_pct or 0):.1f}%)")
            
            # Precious metals
            if overview.gold:
                summary_parts.append(f"Gold ${overview.gold.price:,.0f}")
            if overview.silver:
                summary_parts.append(f"Silver ${overview.silver.price:.2f}")
            
            # Commodities
            if overview.oil:
                summary_parts.append(f"Oil ${overview.oil.price:.2f}")
            
            # Fear & Greed
            if overview.fear_greed:
                summary_parts.append(f"Fear/Greed: {overview.fear_greed} ({overview.market_sentiment})")
            
            # Upcoming events
            events_str = ", ".join(overview.upcoming_events[:2]) if overview.upcoming_events else ""
            
            market_summary = " | ".join(summary_parts)
            
            # Use Grok for cross-market analysis
            grok_response = await grok.analyze_sentiment(
                {"overview": market_summary, "sentiment": overview.market_sentiment, "events": events_str},
                context_type="macro"
            )
            grok_take = grok_response.content[:150] if grok_response and grok_response.success else ""
            
            # Rotate between different focus areas
            import random
            focus = random.choice(["crypto_metals", "macro", "events", "cross_asset"])
            
            if focus == "crypto_metals":
                prompt = f"""Write a tweet comparing crypto and precious metals sentiment.

Data: {market_summary}
Analysis: {grok_take}

Connect the dots between gold/silver and crypto. What's the correlation saying?
Example vibes:
- "gold at $2650 while btc consolidates. boomers and degens agreeing on something for once."
- "silver outperforming btc this week. my boomer portfolio is smug about it."

2-3 sentences. Insightful, not generic."""

            elif focus == "macro":
                prompt = f"""Write a tweet about the broader macro picture.

Data: {market_summary}
Upcoming: {events_str}
Sentiment: Fear/Greed at {overview.fear_greed} ({overview.market_sentiment})

Give a thoughtful take on what the macro picture means for risk assets.
Example vibes:
- "fear/greed at {overview.fear_greed} with FOMC next week. historically this setup means... actually i don't know. nobody does."
- "commodities, metals, and crypto all moving together. correlation is 1 until it isn't."

2-3 sentences. Smart observation."""

            elif focus == "events":
                prompt = f"""Write a tweet about upcoming market events.

Upcoming: {events_str}
Current sentiment: {overview.market_sentiment}

What should traders be watching? Give a useful preview.
Example vibes:
- "FOMC next week. reminder that whatever you think will happen probably won't. plan accordingly."
- "jobs report friday. crypto acts like it doesn't care but definitely cares."

2-3 sentences. Actually useful."""

            else:  # cross_asset
                prompt = f"""Write a tweet about cross-asset market dynamics.

Full picture: {market_summary}
{grok_take}

What's the most interesting thing happening across markets right now?
Example vibes:
- "btc flat, gold up, oil down, fear/greed neutral. market is confused and i relate."
- "interesting divergence: crypto rotating while tradfi stays bid. someone's wrong."

2-3 sentences. Sharp observation."""

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
                # Morning - comprehensive market focus
                generators = [
                    ("comprehensive_market", self.generate_comprehensive_market_tweet),
                    ("market_update", self.generate_market_update),
                    ("social_sentiment", self.generate_social_sentiment_tweet),
                    ("hourly_update", self.generate_hourly_update),
                ]
            elif 10 <= hour < 14:
                # Midday - tokens, news, comprehensive
                generators = [
                    ("comprehensive_market", self.generate_comprehensive_market_tweet),
                    ("trending_token", self.generate_trending_token_call),
                    ("news_sentiment", self.generate_news_tweet),
                    ("market_update", self.generate_market_update),
                ]
            elif 14 <= hour < 18:
                # Afternoon - thoughts, comprehensive, sentiment
                generators = [
                    ("comprehensive_market", self.generate_comprehensive_market_tweet),
                    ("agentic_tech", self.generate_agentic_thought),
                    ("social_sentiment", self.generate_social_sentiment_tweet),
                    ("trending_token", self.generate_trending_token_call),
                ]
            elif 18 <= hour < 22:
                # Evening - comprehensive, news, recap
                generators = [
                    ("comprehensive_market", self.generate_comprehensive_market_tweet),
                    ("news_sentiment", self.generate_news_tweet),
                    ("hourly_update", self.generate_hourly_update),
                    ("engagement", self.generate_interaction_tweet),
                ]
            else:
                # Night - comprehensive, lighter content
                generators = [
                    ("comprehensive_market", self.generate_comprehensive_market_tweet),
                    ("agentic_tech", self.generate_agentic_thought),
                    ("social_sentiment", self.generate_social_sentiment_tweet),
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
            
            # Get autonomy recommendations
            autonomy = await self._get_autonomy()
            recommendations = autonomy.get_content_recommendations()
            
            # Log recommendations
            if recommendations.get("warnings"):
                for warning in recommendations["warnings"]:
                    logger.info(f"Autonomy warning: {warning}")
            
            for category, generator in generators:
                draft = await generator()
                if draft:
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
                        
                        return tweet_id
            
            logger.warning("No content generated this cycle")
            
        except Exception as e:
            logger.error(f"Autonomous loop error: {e}")
        
        return None
    
    async def check_and_reply_mentions(self) -> int:
        """Check for mentions and reply to them using smart prioritization."""
        try:
            twitter = await self._get_twitter()
            voice = await self._get_jarvis_voice()
            autonomy = await self._get_autonomy()
            
            # Get recent mentions
            mentions = await twitter.get_mentions(max_results=20)
            if not mentions:
                return 0
            
            # Use smart prioritization to decide which to reply to
            scored_mentions = autonomy.prioritizer.prioritize_mentions(
                mentions, 
                memory_system=autonomy.memory
            )
            
            replies_sent = 0
            for scored in scored_mentions:
                if not scored.should_reply:
                    continue
                
                tweet_id = scored.tweet_id
                
                # Skip if we already replied (check memory)
                if self.memory.was_mention_replied(tweet_id):
                    continue
                
                # Get conversation context if this is part of a thread
                mention_data = next((m for m in mentions if str(m.get("id")) == tweet_id), {})
                conversation_id = mention_data.get("conversation_id", tweet_id)
                
                # Get existing conversation context from memory
                conv_context = autonomy.memory.get_conversation_context(str(conversation_id))
                user_context = autonomy.memory.get_user_context(scored.user_id)
                
                # Build context for reply generation
                context_parts = []
                if user_context:
                    context_parts.append(f"About @{scored.username}: {user_context}")
                if conv_context:
                    context_parts.append(f"Previous conversation:\n{conv_context}")
                
                context = "\n".join(context_parts) if context_parts else None
                
                # Generate reply with context-aware voice
                reply_content = await voice.generate_reply(
                    scored.text, 
                    scored.username,
                    context=context
                )
                
                if reply_content:
                    result = await twitter.reply_to_tweet(tweet_id, reply_content)
                    if result.success:
                        # Record to local memory
                        self.memory.record_mention_reply(tweet_id, scored.username, reply_content)
                        
                        # Remember user and conversation in autonomy memory
                        autonomy.memory.remember_user(scored.user_id, scored.username)
                        autonomy.memory.remember_conversation(
                            thread_id=str(conversation_id),
                            user_id=scored.user_id,
                            topic=self._extract_topic(scored.text),
                            message=scored.text,
                            is_from_user=True
                        )
                        autonomy.memory.remember_conversation(
                            thread_id=str(conversation_id),
                            user_id=scored.user_id,
                            topic=self._extract_topic(scored.text),
                            message=reply_content,
                            is_from_user=False
                        )
                        
                        autonomy.record_reply_sent(tweet_id, scored.user_id, scored.username)
                        autonomy.prioritizer.mark_replied(tweet_id)
                        replies_sent += 1
                        logger.info(f"Replied to @{scored.username} (priority: {scored.priority_score:.0f})")
                
                # Limit to 5 replies per cycle
                if replies_sent >= 5:
                    break
            
            return replies_sent
            
        except Exception as e:
            logger.error(f"Mentions check error: {e}")
            return 0
    
    def _extract_topic(self, text: str) -> str:
        """Extract topic from text for conversation tracking"""
        # Look for cashtags first
        import re
        cashtags = re.findall(r'\$[A-Za-z]+', text)
        if cashtags:
            return cashtags[0]
        
        # Check for common topics
        text_lower = text.lower()
        topics = ["price", "market", "pump", "dump", "alpha", "signal", "trade", "sol", "btc", "eth"]
        for topic in topics:
            if topic in text_lower:
                return topic
        
        return "general"
    
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
        """Run the autonomous engine continuously with full autonomy."""
        self._running = True
        logger.info(f"Autonomous engine started. Posting every {self._post_interval}s")
        
        # Initialize autonomy
        autonomy = await self._get_autonomy()
        
        mention_check_interval = 300  # Check mentions every 5 minutes
        background_task_interval = 1800  # Run background tasks every 30 min
        last_mention_check = 0
        last_background_task = 0
        
        while self._running:
            try:
                now = time.time()
                
                # Run autonomy background tasks (learning, trending, alpha scan)
                if now - last_background_task > background_task_interval:
                    await autonomy.run_background_tasks()
                    last_background_task = now
                    logger.info("Autonomy background tasks completed")
                
                # Check and reply to mentions with smart prioritization
                if now - last_mention_check > mention_check_interval:
                    replies = await self.check_and_reply_mentions()
                    if replies > 0:
                        logger.info(f"Sent {replies} replies to mentions")
                    last_mention_check = now
                
                # Regular posting with autonomy recommendations
                await self.run_once()
                await asyncio.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Engine error: {e}")
                autonomy.health.mark_service_failure("autonomous_engine", str(e))
                await asyncio.sleep(300)  # Wait 5 min on error
    
    def stop(self):
        """Stop the autonomous engine."""
        self._running = False
        logger.info("Autonomous engine stopped")
    
    def get_status(self) -> Dict:
        """Get engine status including autonomy."""
        stats = self.memory.get_posting_stats()
        
        # Try to get autonomy status
        autonomy_status = {}
        if self._autonomy:
            try:
                autonomy_status = self._autonomy.get_status()
            except Exception:
                pass
        
        return {
            "running": self._running,
            "post_interval": self._post_interval,
            "last_post": self._last_post_time,
            "image_params": asdict(self._image_params),
            "autonomy": autonomy_status,
            **stats
        }
    
    async def get_autonomy_report(self) -> str:
        """Get full autonomy status report."""
        autonomy = await self._get_autonomy()
        return autonomy.format_status_report()


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
