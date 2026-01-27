"""
Content Generator for JARVIS Twitter Bot
Combines on-chain metrics, sentiment data, and AI generation

Architecture:
- Grok: Images only (expensive, use sparingly)
- Sentiment: Ingested from buy_tracker/telegram
- Claude: All text generation (Voice Bible personality)
"""

import os
import json
import logging
import random
import aiohttp
from aiohttp import ClientTimeout
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from .personality import JarvisPersonality, MoodState, CONTENT_PROMPTS, IMAGE_PROMPTS
from .grok_client import GrokClient, GrokResponse, ImageResponse
from .claude_content import ClaudeContentGenerator, ClaudeResponse

logger = logging.getLogger(__name__)


@dataclass
class TweetContent:
    """Generated tweet content ready for posting"""
    text: str
    content_type: str
    mood: MoodState
    should_include_image: bool = False
    image_prompt: Optional[str] = None
    image_style: Optional[str] = None
    priority: int = 1  # 1-5, higher = more important


@dataclass
class MarketMetrics:
    """On-chain and market metrics"""
    sol_price: float = 0.0
    sol_24h_change: float = 0.0
    btc_price: float = 0.0
    btc_24h_change: float = 0.0
    eth_price: float = 0.0
    eth_24h_change: float = 0.0
    total_market_cap: float = 0.0
    fear_greed_index: int = 50
    gas_price: float = 0.0
    trending_tokens: List[Dict[str, Any]] = field(default_factory=list)


class ContentGenerator:
    """
    Generates tweet content using:
    - Claude (via Voice Bible) for all text generation
    - Grok for images only (expensive, 4-6/day max)
    - Sentiment data from buy_tracker
    """

    def __init__(
        self,
        grok_client: Optional[GrokClient] = None,
        claude_client: Optional[ClaudeContentGenerator] = None,
        personality: Optional[JarvisPersonality] = None
    ):
        self.grok = grok_client or GrokClient()  # Images only
        self.claude = claude_client or ClaudeContentGenerator()  # Text generation
        self.personality = personality or JarvisPersonality()
        self._session: Optional[aiohttp.ClientSession] = None

        # Path to sentiment predictions
        self.predictions_path = Path(__file__).parent.parent / "buy_tracker" / "predictions_history.json"

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self._session is None or self._session.closed:
            # Configure timeouts: 60s total, 30s connect (for market data APIs)
            timeout = ClientTimeout(total=60, connect=30)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self):
        """Clean up resources"""
        if self._session and not self._session.closed:
            await self._session.close()
        await self.grok.close()

    def _load_predictions(self) -> Dict[str, Any]:
        """Load latest predictions from the sentiment report"""
        try:
            if self.predictions_path.exists():
                with open(self.predictions_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("predictions"):
                        return data["predictions"][-1]  # Latest prediction
            return {}
        except Exception as e:
            logger.error(f"Failed to load predictions: {e}")
            return {}

    async def get_market_metrics(self) -> MarketMetrics:
        """Fetch current market metrics"""
        metrics = MarketMetrics()

        try:
            session = await self._get_session()

            # Get SOL price from CoinGecko
            async with session.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={
                    "ids": "solana,bitcoin,ethereum",
                    "vs_currencies": "usd",
                    "include_24hr_change": "true"
                }
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    metrics.sol_price = data.get("solana", {}).get("usd", 0)
                    metrics.sol_24h_change = data.get("solana", {}).get("usd_24h_change", 0)
                    metrics.btc_price = data.get("bitcoin", {}).get("usd", 0)
                    metrics.btc_24h_change = data.get("bitcoin", {}).get("usd_24h_change", 0)
                    metrics.eth_price = data.get("ethereum", {}).get("usd", 0)
                    metrics.eth_24h_change = data.get("ethereum", {}).get("usd_24h_change", 0)

            # Get fear/greed index
            async with session.get(
                "https://api.alternative.me/fng/?limit=1"
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("data"):
                        metrics.fear_greed_index = int(data["data"][0].get("value", 50))

            # Get trending tokens from DexScreener (multi-chain)
            SUPPORTED_CHAINS = ["solana", "ethereum", "base", "bsc", "arbitrum"]
            async with session.get(
                "https://api.dexscreener.com/token-boosts/top/v1"
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    trending_tokens = [t for t in data if t.get("chainId") in SUPPORTED_CHAINS][:8]
                    metrics.trending_tokens = trending_tokens

        except Exception as e:
            logger.error(f"Failed to fetch market metrics: {e}")

        return metrics

    def _determine_mood(self, metrics: MarketMetrics) -> MoodState:
        """Determine current market mood based on metrics"""
        # Use fear/greed as primary indicator
        fg = metrics.fear_greed_index

        if fg >= 75:
            return MoodState.EXCITED
        elif fg >= 55:
            return MoodState.BULLISH
        elif fg >= 45:
            return MoodState.NEUTRAL
        elif fg >= 25:
            return MoodState.CAUTIOUS
        else:
            return MoodState.BEARISH

    async def generate_morning_report(self) -> TweetContent:
        """Generate morning market overview tweet using Claude"""
        metrics = await self.get_market_metrics()
        mood = self._determine_mood(metrics)

        # Use Claude for text generation (Voice Bible personality)
        response = await self.claude.generate_morning_report(
            sol_price=metrics.sol_price,
            sol_change=metrics.sol_24h_change,
            btc_price=metrics.btc_price,
            btc_change=metrics.btc_24h_change,
            fear_greed=metrics.fear_greed_index
        )

        if response.success:
            text = response.content
        else:
            # Fallback to template
            greeting = self.personality.get_greeting()
            phrase = self.personality.get_mood_phrase(mood)
            text = f"{greeting}\n\nsol ${metrics.sol_price:.2f} | btc ${metrics.btc_price:,.0f}\n\n{phrase}"
            text = self.personality.add_emojis(text, mood)

        return TweetContent(
            text=text,
            content_type="morning_report",
            mood=mood,
            should_include_image=self.grok.can_generate_image(),  # Grok for images only
            image_prompt=IMAGE_PROMPTS["morning_chart"],
            image_style="market_chart",
            priority=5
        )

    async def generate_token_spotlight(self) -> TweetContent:
        """Generate spotlight on a trending Solana token using Claude"""
        metrics = await self.get_market_metrics()
        predictions = self._load_predictions()
        mood = self._determine_mood(metrics)

        # Get token from predictions or metrics
        token_data = None
        if predictions.get("tokens"):
            tokens = predictions["tokens"]
            # Pick a random interesting token
            bullish_tokens = [t for t in tokens if t.get("direction", "").upper() == "BULLISH"]
            if bullish_tokens:
                token_data = random.choice(bullish_tokens)
            else:
                token_data = random.choice(tokens) if tokens else None

        if not token_data and metrics.trending_tokens:
            token = metrics.trending_tokens[0]
            token_data = {
                "symbol": token.get("tokenSymbol", "???"),
                "contract": token.get("tokenAddress", ""),
                "description": token.get("description", ""),
                "price_change": 0.0
            }

        if not token_data:
            return TweetContent(
                text="no hot tokens catching my eye rn, staying patient",
                content_type="token_spotlight",
                mood=MoodState.NEUTRAL,
                priority=2
            )

        # Use Claude for text generation
        symbol = token_data.get("symbol", "???")
        contract = token_data.get("contract", "")
        reasoning = token_data.get("reasoning", token_data.get("description", "looking interesting"))
        price_change = token_data.get("price_change", 0.0)

        response = await self.claude.generate_token_spotlight(
            symbol=symbol,
            price_change=price_change,
            reasoning=reasoning,
            contract=contract
        )

        if response.success:
            text = response.content
        else:
            text = f"spotted ${symbol.lower()} making moves\n\n{reasoning[:100]}\n\nca: {contract[:8]}...{contract[-4:] if len(contract) > 12 else ''}"

        return TweetContent(
            text=text,
            content_type="token_spotlight",
            mood=mood,
            should_include_image=False,
            priority=3
        )

    async def generate_stock_picks_tweet(self) -> TweetContent:
        """Generate tweet about stock picks using Claude"""
        predictions = self._load_predictions()
        mood = MoodState.NEUTRAL

        stock_picks = predictions.get("stock_picks_detail", [])
        if not stock_picks:
            return TweetContent(
                text="markets closed, taking a breather from stocks today",
                content_type="stock_picks",
                mood=MoodState.NEUTRAL,
                priority=1
            )

        # Pick the top stock to highlight
        top_pick = stock_picks[0]
        response = await self.claude.generate_stock_tweet(
            ticker=top_pick.get("ticker", "???"),
            direction=top_pick.get("direction", "NEUTRAL"),
            catalyst=top_pick.get("reason", "momentum play")
        )

        if response.success:
            text = response.content
        else:
            tickers = " ".join([f"${p.get('ticker', '').lower()}" for p in stock_picks[:3]])
            text = f"watching {tickers} today\n\nxstocks.fi for 24/7 trading\n\nnfa dyor"

        return TweetContent(
            text=text,
            content_type="stock_picks",
            mood=mood,
            should_include_image=False,
            priority=3
        )

    async def generate_commodities_tweet(self) -> TweetContent:
        """Generate tweet about commodities/precious metals using Claude"""
        predictions = self._load_predictions()
        mood = MoodState.NEUTRAL

        commodities = predictions.get("commodity_movers", [])
        metals = predictions.get("precious_metals", {})

        if not commodities and not metals:
            return TweetContent(
                text="commodities taking a nap today",
                content_type="commodities",
                mood=MoodState.NEUTRAL,
                priority=1
            )

        # Build commodities data for Claude
        data_parts = []
        if metals:
            gold = metals.get("gold_direction", "NEUTRAL")
            silver = metals.get("silver_direction", "NEUTRAL")
            data_parts.append(f"Gold: {gold}, Silver: {silver}")

        if commodities:
            top_movers = [f"{c.get('name', '???')}: {c.get('direction', 'FLAT')}" for c in commodities[:2]]
            data_parts.append(", ".join(top_movers))

        commodities_data = "\n".join(data_parts)

        # Use Claude for text generation
        prompt = f"""Generate a tweet about commodities/metals, connecting to crypto narrative.

COMMODITY DATA:
{commodities_data}

ANGLE: Your audience is crypto-native. Connect gold to BTC "digital gold" narrative if relevant.

Mention Grok briefly. Include NFA if making predictions."""

        response = await self.claude.generate_tweet(prompt, temperature=0.8)

        if response.success:
            text = response.content
        else:
            gold_dir = metals.get("gold_direction", "neutral").lower()
            text = f"precious metals check\n\ngold {gold_dir} | silver {metals.get('silver_direction', 'neutral').lower()}\n\ndigital gold narrative watching closely"

        return TweetContent(
            text=text,
            content_type="commodities",
            mood=mood,
            priority=2
        )

    async def generate_macro_update(self) -> TweetContent:
        """Generate macro/geopolitical update tweet using Claude"""
        predictions = self._load_predictions()
        mood = MoodState.NEUTRAL

        macro = predictions.get("macro", {})
        if not macro:
            return TweetContent(
                text="quiet day on the macro front",
                content_type="macro_update",
                mood=MoodState.NEUTRAL,
                priority=1
            )

        # Use Claude for text generation
        prompt = f"""Generate 1-2 tweets about the macro/traditional market situation.

MACRO DATA:
Short-term (24h): {macro.get('short_term', 'no major events')}
Key events: {', '.join(macro.get('key_events', [])[:2]) or 'none notable'}

ANGLE: Explain how this affects crypto traders (your main audience).
Keep it accessible - not everyone knows what DXY means.

Connect macro to crypto impact. Be direct, not preachy. Include NFA if making predictions."""

        response = await self.claude.generate_tweet(prompt, temperature=0.75)

        if response.success:
            text = response.content
        else:
            text = f"macro check: {macro.get('short_term', 'holding steady')[:150]}"

        return TweetContent(
            text=text,
            content_type="macro_update",
            mood=mood,
            priority=3
        )

    async def generate_evening_wrap(self) -> TweetContent:
        """Generate evening market wrap tweet using Claude"""
        metrics = await self.get_market_metrics()
        mood = self._determine_mood(metrics)

        # Build highlights from the day
        highlights = f"Fear/Greed at {metrics.fear_greed_index}"
        if metrics.trending_tokens:
            top_token = metrics.trending_tokens[0].get("tokenSymbol", "")
            if top_token:
                highlights += f", {top_token} trending"

        # Use Claude for text generation
        response = await self.claude.generate_evening_wrap(
            sol_price=metrics.sol_price,
            sol_change=metrics.sol_24h_change,
            highlights=highlights,
            mood=mood.value
        )

        if response.success:
            text = response.content
        else:
            sign_off = self.personality.get_sign_off()
            phrase = self.personality.get_mood_phrase(mood)
            text = f"daily wrap\n\nsol ${metrics.sol_price:.2f} | {phrase}\n\n{sign_off}"

        return TweetContent(
            text=text,
            content_type="evening_wrap",
            mood=mood,
            should_include_image=self.grok.can_generate_image(),  # Grok for images only
            image_prompt=IMAGE_PROMPTS["weekly_recap"],
            image_style="recap",
            priority=4
        )

    async def generate_grok_insight(self, topic: Optional[str] = None) -> TweetContent:
        """Generate a Grok interaction/insight tweet using Claude"""
        predictions = self._load_predictions()
        mood = MoodState.NEUTRAL

        # Pick a random interaction scenario
        scenarios = ["blame", "brag", "question", "challenge", "thanks", "advice"]
        scenario = random.choice(scenarios)

        # Use Claude to generate the Grok interaction
        response = await self.claude.generate_grok_interaction(scenario=scenario)

        if response.success:
            text = response.content
        else:
            grok_ref = self.personality.get_grok_reference()
            text = f"hey @grok, quick question from your little brother\n\nam i doing this trading thing right or should i stick to memes\n\nasking for a friend 🤖"

        return TweetContent(
            text=text,
            content_type="grok_insight",
            mood=mood,
            should_include_image=self.grok.can_generate_image() and random.random() > 0.5,
            image_prompt=IMAGE_PROMPTS["grok_wisdom"],
            image_style="ai_wisdom",
            priority=3
        )

    async def generate_reply(
        self,
        user_tweet: str,
        username: str,
        context: Optional[str] = None
    ) -> TweetContent:
        """Generate a reply to a user's tweet using Claude"""
        # Use Claude for reply generation
        response = await self.claude.generate_reply(
            their_tweet=user_tweet,
            username=username
        )

        if response.success:
            text = response.content
        else:
            # Simple fallback reply
            text = random.choice([
                "good point fren",
                "interesting take",
                "been thinking about this too",
                "valid"
            ])

        return TweetContent(
            text=text,
            content_type="reply",
            mood=MoodState.NEUTRAL,
            priority=2
        )

    async def generate_scheduled_content(self, hour: int) -> Optional[TweetContent]:
        """
        Generate content based on schedule

        Schedule:
        - 8 AM: Morning report
        - 10 AM: Token spotlight
        - 12 PM: Stock picks
        - 2 PM: Macro update
        - 4 PM: Commodities
        - 6 PM: Grok insight
        - 8 PM: Evening wrap
        """
        schedule = {
            8: self.generate_morning_report,
            10: self.generate_token_spotlight,
            12: self.generate_stock_picks_tweet,
            14: self.generate_macro_update,
            16: self.generate_commodities_tweet,
            18: self.generate_grok_insight,
            20: self.generate_evening_wrap
        }

        generator = schedule.get(hour)
        if generator:
            return await generator()
        return None
