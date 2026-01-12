"""
Sentiment Report Generator - Automated 10-token sentiment analysis using Grok + indicators.

Posts beautiful sentiment reports to Telegram every 30 minutes.
Includes macro events, geopolitical analysis, and traditional market sentiment.
"""

import asyncio
import logging
import os
import json
import aiohttp
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from pathlib import Path
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# Import ape buttons with TP/SL profiles
from bots.buy_tracker.ape_buttons import create_ape_buttons_with_tp_sl

# Import XStocks/PreStocks universe
from core.tokenized_equities_universe import (
    fetch_xstocks_universe,
    fetch_prestocks_universe,
    EquityToken,
)

logger = logging.getLogger(__name__)

# Prediction tracking file
PREDICTIONS_FILE = Path(__file__).parent / "predictions_history.json"


# Custom emoji IDs from the KR8TIV pack (t.me/addemoji/KR8TIV)
# Format: <tg-emoji emoji-id="ID">fallback</tg-emoji>
# To add more: forward emoji to @RawDataBot to get the ID
KR8TIV_EMOJI_IDS = {
    "robot": "5990286304724655084",  # KR8TIV robot emoji
    # Add more emoji IDs here as you get them from the pack
    # "bull": "ID_HERE",
    # "bear": "ID_HERE",
    # etc.
}

# Standard emoji fallbacks (used when custom not available)
STANDARD_EMOJIS = {
    "bull": "🟢",
    "bear": "🔴",
    "neutral": "🟡",
    "rocket": "🚀",
    "fire": "🔥",
    "chart_up": "📈",
    "chart_down": "📉",
    "money": "💰",
    "robot": "🤖",
    "ape": "🦍",
    "crown": "👑",
    "target": "🎯",
    "warning": "⚠️",
    "diamond": "💎",
}


def get_emoji(name: str, use_custom: bool = True) -> str:
    """Get emoji, using custom KR8TIV pack when available.

    Args:
        name: Emoji name (robot, bull, bear, etc.)
        use_custom: If True, use custom emoji when available

    Returns:
        HTML string with custom emoji or standard fallback
    """
    if use_custom and name in KR8TIV_EMOJI_IDS:
        emoji_id = KR8TIV_EMOJI_IDS[name]
        fallback = STANDARD_EMOJIS.get(name, "")
        return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'
    return STANDARD_EMOJIS.get(name, "")


@dataclass
class MacroAnalysis:
    """Macro events and geopolitical analysis."""
    short_term: str = ""      # Next 24 hours
    medium_term: str = ""     # Next 3 days
    long_term: str = ""       # 1 week to 1 month
    key_events: List[str] = field(default_factory=list)


@dataclass
class TraditionalMarkets:
    """DXY and US stocks sentiment."""
    dxy_sentiment: str = ""           # Dollar index outlook
    dxy_direction: str = "NEUTRAL"    # BULLISH/BEARISH/NEUTRAL
    stocks_sentiment: str = ""         # US stocks outlook
    stocks_direction: str = "NEUTRAL"  # BULLISH/BEARISH/NEUTRAL
    next_24h: str = ""
    next_week: str = ""
    correlation_note: str = ""         # How it affects crypto


@dataclass
class StockPick:
    """A stock pick with reasoning."""
    ticker: str
    direction: str  # BULLISH/BEARISH
    reason: str
    target: str = ""
    stop_loss: str = ""


@dataclass
class CommodityMover:
    """A commodity mover with outlook."""
    name: str
    direction: str  # UP/DOWN
    change: str
    reason: str
    outlook: str = ""


@dataclass
class PreciousMetalsOutlook:
    """Precious metals weekly outlook."""
    gold_direction: str = "NEUTRAL"
    gold_outlook: str = ""
    silver_direction: str = "NEUTRAL"
    silver_outlook: str = ""
    platinum_direction: str = "NEUTRAL"
    platinum_outlook: str = ""


@dataclass
class PredictionRecord:
    """Track predictions for accuracy measurement."""
    timestamp: str
    token_predictions: Dict[str, dict] = field(default_factory=dict)  # symbol -> {verdict, targets, price_at_prediction}
    macro_predictions: Dict[str, str] = field(default_factory=dict)
    market_predictions: Dict[str, str] = field(default_factory=dict)
    stock_picks: List[str] = field(default_factory=list)  # Track stock tickers for change detection
    commodity_movers: List[str] = field(default_factory=list)
    precious_metals: Dict[str, str] = field(default_factory=dict)


@dataclass
class TokenSentiment:
    """Sentiment data for a single token."""
    symbol: str
    name: str
    price_usd: float
    change_1h: float
    change_24h: float
    volume_24h: float
    mcap: float
    buys_24h: int
    sells_24h: int
    liquidity: float
    contract_address: str = ""  # Token mint/contract address

    # Calculated
    buy_sell_ratio: float = 0.0
    sentiment_score: float = 0.0  # -1 to 1
    sentiment_label: str = "NEUTRAL"
    grok_analysis: str = ""       # Price targets
    grok_reasoning: str = ""      # WHY bullish/bearish/neutral
    grade: str = "C"

    grok_score: float = 0.0  # Grok AI score (-1 to 1)
    grok_verdict: str = ""   # Grok's one-word verdict

    # Grok-provided targets (for ape buttons)
    grok_stop_loss: str = ""      # e.g. "$0.000015"
    grok_target_safe: str = ""    # Conservative target
    grok_target_med: str = ""     # Medium risk target
    grok_target_degen: str = ""   # Moon target
    grok_grade: str = ""          # Grade (A+, A, B+, etc.)

    def calculate_sentiment(self, include_grok: bool = True):
        """
        Calculate sentiment from metrics + Grok AI score.

        Enhanced with learnings from accuracy analysis (84.6% accuracy):
        - Strong sell pressure detection (ratio < 0.7x = heavily bearish)
        - Extreme momentum bonuses (>100% pumps)
        - Profit-taking warning (big gains + sell pressure)
        - Better grade thresholds based on performance data
        """
        score = 0.0

        # === PRICE MOMENTUM (weight: 25%) ===
        # Enhanced: Extreme pumps get bonus, extreme dumps get extra penalty
        if self.change_24h > 100:
            # Extreme pump - strong momentum signal (learned: these often continue)
            score += 0.30
        elif self.change_24h > 50:
            score += 0.27
        elif self.change_24h > 10:
            score += 0.25
        elif self.change_24h > 5:
            score += 0.15
        elif self.change_24h > 0:
            score += 0.08
        elif self.change_24h > -5:
            score -= 0.08
        elif self.change_24h > -10:
            score -= 0.15
        elif self.change_24h > -30:
            score -= 0.25
        else:
            # Extreme dump - heavy penalty
            score -= 0.35

        # === BUY/SELL RATIO (weight: 35%) ===
        # Increased weight - this was our most predictive indicator
        self.buy_sell_ratio = self.buys_24h / max(self.sells_24h, 1)

        if self.buy_sell_ratio > 3:
            # Extreme buying pressure - very bullish
            score += 0.35
        elif self.buy_sell_ratio > 2:
            score += 0.30
        elif self.buy_sell_ratio > 1.5:
            score += 0.22
        elif self.buy_sell_ratio > 1.2:
            score += 0.15
        elif self.buy_sell_ratio > 1:
            score += 0.08
        elif self.buy_sell_ratio > 0.8:
            score -= 0.10
        elif self.buy_sell_ratio > 0.7:
            # Warning zone - sellers gaining control
            score -= 0.18
        elif self.buy_sell_ratio > 0.5:
            # Heavy sell pressure - strongly bearish (learned: sub-0.7x = danger)
            score -= 0.28
        else:
            # Extreme sell pressure - capitulation signal
            score -= 0.35

        # === PROFIT-TAKING DETECTION ===
        # Learned: Big gains + weak buy ratio = profit-taking, bearish signal
        if self.change_24h > 50 and self.buy_sell_ratio < 0.8:
            # Token pumped but sellers dominating - likely profit-taking
            score -= 0.15  # Penalty for profit-taking pattern
        elif self.change_24h > 30 and self.buy_sell_ratio < 0.7:
            # Moderate pump with heavy selling - bearish divergence
            score -= 0.12

        # === VOLUME HEALTH (weight: 15%) ===
        vol_to_mcap = (self.volume_24h / max(self.mcap, 1)) * 100
        if vol_to_mcap > 100:
            # Extreme volume - strong interest (could be pump or dump)
            score += 0.18
        elif vol_to_mcap > 50:
            score += 0.15
        elif vol_to_mcap > 20:
            score += 0.08
        elif vol_to_mcap > 10:
            score += 0.03
        elif vol_to_mcap < 5:
            # Low volume = low conviction
            score -= 0.12

        # === LIQUIDITY (weight: 10%) ===
        if self.liquidity > 100000:
            score += 0.1
        elif self.liquidity > 50000:
            score += 0.05
        elif self.liquidity > 20000:
            score += 0.02
        elif self.liquidity < 10000:
            # Low liquidity - higher risk
            score -= 0.12

        # === GROK AI SCORE (weight: 15%) ===
        # Slightly reduced - technical signals more reliable
        if include_grok and self.grok_score != 0:
            score += self.grok_score * 0.15

        self.sentiment_score = max(-1, min(1, score))

        # === GRADE ASSIGNMENT ===
        # Refined thresholds based on accuracy data
        if self.sentiment_score > 0.45:
            self.sentiment_label = "BULLISH"
            self.grade = "A" if self.sentiment_score > 0.55 else "A-"
        elif self.sentiment_score > 0.20:
            self.sentiment_label = "SLIGHTLY BULLISH"
            self.grade = "B+" if self.sentiment_score > 0.32 else "B"
        elif self.sentiment_score > -0.20:
            self.sentiment_label = "NEUTRAL"
            self.grade = "C+" if self.sentiment_score > 0.05 else "C"
        elif self.sentiment_score > -0.40:
            self.sentiment_label = "SLIGHTLY BEARISH"
            self.grade = "C-" if self.sentiment_score > -0.30 else "D+"
        else:
            self.sentiment_label = "BEARISH"
            self.grade = "D" if self.sentiment_score > -0.55 else "F"


class SentimentReportGenerator:
    """
    Generates and posts sentiment reports using Grok AI + technical indicators.
    """

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        xai_api_key: str,
        interval_minutes: int = 30,
    ):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.xai_api_key = xai_api_key
        self.interval_minutes = interval_minutes
        self._running = False
        self._session: Optional[aiohttp.ClientSession] = None

    async def start(self):
        """Start the sentiment report scheduler."""
        self._running = True
        self._session = aiohttp.ClientSession()

        logger.info(f"Starting sentiment report generator (every {self.interval_minutes} min)")

        # Post initial report
        await self.generate_and_post_report()

        # Schedule loop
        while self._running:
            await asyncio.sleep(self.interval_minutes * 60)
            if self._running:
                await self.generate_and_post_report()

    async def stop(self):
        """Stop the generator."""
        self._running = False
        if self._session:
            await self._session.close()

    async def generate_and_post_report(self):
        """Generate sentiment report and post to Telegram."""
        try:
            # Get top 10 tokens
            tokens = await self._get_trending_tokens(limit=10)

            if not tokens:
                logger.warning("No tokens found for sentiment report")
                return

            # Calculate initial technical sentiment (without Grok)
            for token in tokens:
                token.calculate_sentiment(include_grok=False)

            # Have Grok evaluate each token individually
            await self._get_grok_token_scores(tokens)

            # Recalculate final sentiment with Grok scores
            for token in tokens:
                token.calculate_sentiment(include_grok=True)

            # Get Grok's overall market summary
            grok_summary = await self._get_grok_summary(tokens)

            # Get macro events and traditional markets analysis
            macro = await self._get_macro_analysis()
            markets = await self._get_traditional_markets()

            # Get stock picks with change tracking
            previous_picks = self._get_previous_stock_picks()
            stock_picks, picks_changes = await self._get_stock_picks(previous_picks)

            # Get commodity movers and precious metals
            commodities = await self._get_commodity_movers()
            precious_metals = await self._get_precious_metals_outlook()

            # Save predictions for tracking
            self._save_predictions(tokens, macro, markets, stock_picks, commodities, precious_metals)

            # Format report
            report = self._format_report(tokens, grok_summary, macro, markets, stock_picks, picks_changes, commodities, precious_metals)

            # Post to Telegram with ape buttons for bullish tokens
            await self._post_to_telegram(report, tokens=tokens)

            logger.info(f"Posted sentiment report with {len(tokens)} tokens + stocks + commodities + metals")

        except Exception as e:
            logger.error(f"Failed to generate sentiment report: {e}")

    async def _get_trending_tokens(self, limit: int = 10) -> List[TokenSentiment]:
        """Get HOT trending Solana tokens from DexScreener - no major caps."""
        tokens = []
        seen_symbols = set()

        # Major tokens to exclude (we want microcaps/trending, not blue chips)
        EXCLUDED_SYMBOLS = {
            "SOL", "WSOL", "USDC", "USDT", "RAY", "JUP", "PYTH", "JTO",
            "ORCA", "MNGO", "SRM", "FIDA", "STEP", "COPE", "MEDIA",
            "ETH", "BTC", "WBTC", "WETH"
        }

        try:
            # Fetch trending/boosted tokens from DexScreener
            trending_url = "https://api.dexscreener.com/token-boosts/top/v1"

            async with self._session.get(trending_url) as resp:
                if resp.status == 200:
                    data = await resp.json()

                    # Filter for Solana tokens
                    for item in data:
                        if len(tokens) >= limit:
                            break

                        if item.get("chainId") != "solana":
                            continue

                        token_addr = item.get("tokenAddress", "")
                        if not token_addr:
                            continue

                        # Fetch full pair data for this token
                        try:
                            async with self._session.get(
                                f"https://api.dexscreener.com/latest/dex/tokens/{token_addr}"
                            ) as pair_resp:
                                if pair_resp.status == 200:
                                    pair_data = await pair_resp.json()
                                    pairs = pair_data.get("pairs", [])

                                    if pairs:
                                        pair = pairs[0]  # Get main pair
                                        base = pair.get("baseToken", {})
                                        symbol = base.get("symbol", "").upper()

                                        # Skip excluded and duplicates
                                        if symbol in EXCLUDED_SYMBOLS or symbol in seen_symbols:
                                            continue

                                        seen_symbols.add(symbol)
                                        txns = pair.get("txns", {}).get("h24", {})

                                        token = TokenSentiment(
                                            symbol=base.get("symbol", "???"),
                                            name=base.get("name", "Unknown"),
                                            price_usd=float(pair.get("priceUsd", 0) or 0),
                                            change_1h=pair.get("priceChange", {}).get("h1", 0) or 0,
                                            change_24h=pair.get("priceChange", {}).get("h24", 0) or 0,
                                            volume_24h=pair.get("volume", {}).get("h24", 0) or 0,
                                            mcap=pair.get("marketCap", 0) or pair.get("fdv", 0) or 0,
                                            buys_24h=txns.get("buys", 0),
                                            sells_24h=txns.get("sells", 0),
                                            liquidity=pair.get("liquidity", {}).get("usd", 0) or 0,
                                            contract_address=base.get("address", token_addr),
                                        )
                                        tokens.append(token)

                            await asyncio.sleep(0.15)  # Rate limit

                        except Exception as e:
                            logger.debug(f"Failed to fetch pair data: {e}")

            # If we don't have enough from trending, supplement with gainers
            if len(tokens) < limit:
                async with self._session.get(
                    "https://api.dexscreener.com/latest/dex/search?q=solana"
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        pairs = data.get("pairs", [])

                        # Sort by 24h change (momentum)
                        pairs = sorted(
                            [p for p in pairs if p.get("chainId") == "solana"],
                            key=lambda p: p.get("priceChange", {}).get("h24", 0) or 0,
                            reverse=True
                        )

                        for pair in pairs:
                            if len(tokens) >= limit:
                                break

                            base = pair.get("baseToken", {})
                            symbol = base.get("symbol", "").upper()

                            if symbol in EXCLUDED_SYMBOLS or symbol in seen_symbols:
                                continue

                            seen_symbols.add(symbol)
                            txns = pair.get("txns", {}).get("h24", {})

                            token = TokenSentiment(
                                symbol=base.get("symbol", "???"),
                                name=base.get("name", "Unknown"),
                                price_usd=float(pair.get("priceUsd", 0) or 0),
                                change_1h=pair.get("priceChange", {}).get("h1", 0) or 0,
                                change_24h=pair.get("priceChange", {}).get("h24", 0) or 0,
                                volume_24h=pair.get("volume", {}).get("h24", 0) or 0,
                                mcap=pair.get("marketCap", 0) or pair.get("fdv", 0) or 0,
                                buys_24h=txns.get("buys", 0),
                                sells_24h=txns.get("sells", 0),
                                liquidity=pair.get("liquidity", {}).get("usd", 0) or 0,
                                contract_address=base.get("address", ""),
                            )
                            tokens.append(token)

            logger.info(f"Found {len(tokens)} trending tokens")

        except Exception as e:
            logger.error(f"Failed to get trending tokens: {e}")

        return tokens

    async def _get_grok_token_scores(self, tokens: List[TokenSentiment]) -> None:
        """Have Grok evaluate each token and assign sentiment scores."""
        if not self.xai_api_key:
            return

        try:
            # Build token data for Grok
            token_data = "\n".join([
                f"{i+1}. {t.symbol}: Price ${t.price_usd:.8f}, 24h Change {t.change_24h:+.1f}%, "
                f"Buy/Sell Ratio {t.buy_sell_ratio:.2f}x, Volume ${t.volume_24h:,.0f}, MCap ${t.mcap:,.0f}"
                for i, t in enumerate(tokens)
            ])

            prompt = f"""Score each MICROCAP token's sentiment from -100 (extremely bearish) to +100 (extremely bullish).
These are HIGH RISK microcaps - basically lottery tickets. Be honest about the risk.
Analyze onchain metrics (buy/sell ratio), volume, momentum, and fundamentals.
For BULLISH tokens, provide price targets. For ALL tokens, explain WHY.

MICROCAP TOKENS (with onchain data):
{token_data}

Respond in EXACTLY this format for each token (one per line):
SYMBOL|SCORE|VERDICT|REASON|STOP_LOSS|TARGET_SAFE|TARGET_MED|TARGET_DEGEN

Example:
BONK|45|BULLISH|Strong buy pressure 2.1x ratio, volume surge, meme momentum|$0.000015|$0.000025|$0.000040|$0.000080
WIF|-20|BEARISH|Sell pressure dominating, declining volume, weak hands exiting||||
POPCAT|10|NEUTRAL|Mixed signals, buy/sell balanced, waiting for catalyst||||

Rules:
- Score: -100 to +100
- Verdict: BULLISH, BEARISH, or NEUTRAL
- REASON: Brief explanation (15-25 words) covering onchain metrics, volume trends, momentum, or catalysts
- Only include price targets for BULLISH tokens
- Stop loss = recommended exit if trade goes wrong (protect capital!)
- Target Safe = conservative target (reasonable expectation)
- Target Med = medium risk target (optimistic but possible)
- Target Degen = full send target (moonshot potential)
- Consider: buy/sell ratio, volume health, price momentum, liquidity depth
- Remember: these are volatile microcaps, not blue chips

Respond with ONLY the formatted lines, no other text."""

            async with self._session.post(
                "https://api.x.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.xai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "grok-3",
                    "messages": [
                        {"role": "system", "content": "You are a crypto trading analyst. Provide precise, actionable analysis."},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 500,
                    "temperature": 0.5,
                }
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    response = data["choices"][0]["message"]["content"].strip()

                    # Parse Grok's response (new format: SYMBOL|SCORE|VERDICT|REASON|STOP|SAFE|MED|DEGEN)
                    for line in response.split("\n"):
                        line = line.strip()
                        if "|" not in line:
                            continue

                        parts = line.split("|")
                        if len(parts) < 4:
                            continue

                        symbol = parts[0].strip().upper()
                        try:
                            score = int(parts[1].strip())
                        except:
                            continue

                        verdict = parts[2].strip().upper()
                        reason = parts[3].strip() if len(parts) > 3 else ""

                        # Find matching token
                        for token in tokens:
                            if token.symbol.upper() == symbol:
                                token.grok_score = score / 100.0  # Normalize to -1 to 1
                                token.grok_verdict = verdict
                                token.grok_reasoning = reason

                                # Parse price targets if bullish (now at indices 4-7)
                                if len(parts) >= 8 and verdict == "BULLISH":
                                    token.grok_stop_loss = parts[4].strip()
                                    token.grok_target_safe = parts[5].strip()
                                    token.grok_target_med = parts[6].strip()
                                    token.grok_target_degen = parts[7].strip()
                                    token.grok_analysis = (
                                        f"Stop: {parts[4]} | "
                                        f"Safe: {parts[5]} | "
                                        f"Med: {parts[6]} | "
                                        f"Degen: {parts[7]}"
                                    )
                                break

                    logger.info(f"Grok scored {len(tokens)} tokens")
                else:
                    logger.error(f"Grok API error: {resp.status}")

        except Exception as e:
            logger.error(f"Grok scoring failed: {e}")

    async def _get_grok_summary(self, tokens: List[TokenSentiment]) -> str:
        """Get overall market summary from Grok."""
        if not self.xai_api_key:
            return "AI analysis unavailable"

        try:
            bullish = [t for t in tokens if t.grok_verdict == "BULLISH"]
            bearish = [t for t in tokens if t.grok_verdict == "BEARISH"]

            context = f"""Solana MICROCAP market snapshot (high risk lottery tickets):
- Bullish microcaps: {', '.join(t.symbol for t in bullish) or 'None'}
- Bearish microcaps: {', '.join(t.symbol for t in bearish) or 'None'}
- Top performer: {max(tokens, key=lambda t: t.change_24h).symbol} ({max(tokens, key=lambda t: t.change_24h).change_24h:+.1f}%)
- Worst performer: {min(tokens, key=lambda t: t.change_24h).symbol} ({min(tokens, key=lambda t: t.change_24h).change_24h:+.1f}%)

Give a 2 sentence microcap market outlook. Be direct, acknowledge the risk, but point out opportunities. Keep it real."""

            async with self._session.post(
                "https://api.x.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.xai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "grok-3",
                    "messages": [
                        {"role": "user", "content": context}
                    ],
                    "max_tokens": 100,
                    "temperature": 0.7,
                }
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"].strip()

        except Exception as e:
            logger.error(f"Grok summary failed: {e}")

        return "Market analysis pending..."

    async def _get_macro_analysis(self) -> MacroAnalysis:
        """Get macro events and geopolitical analysis from Grok."""
        macro = MacroAnalysis()

        if not self.xai_api_key:
            return macro

        try:
            prompt = """Analyze current macro events and geopolitics affecting crypto markets.

Provide analysis for THREE timeframes:

1. SHORT TERM (Next 24 hours):
- Any scheduled economic data releases (CPI, jobs, Fed speakers)?
- Immediate geopolitical risks or catalysts?
- What should traders watch TODAY?

2. MEDIUM TERM (Next 3 days):
- Any major events coming this week?
- Developing geopolitical situations?
- Key support/resistance levels to watch?

3. LONG TERM (1 week to 1 month):
- Major macro themes playing out?
- Upcoming Fed meetings, halving events, regulatory deadlines?
- Big picture trends affecting risk assets?

Format your response EXACTLY like this:
SHORT|[Your 24h analysis in 2-3 sentences]
MEDIUM|[Your 3-day analysis in 2-3 sentences]
LONG|[Your 1w-1m analysis in 2-3 sentences]
EVENTS|[Comma-separated list of key dates/events to watch]

Be specific and actionable. Focus on what actually matters for crypto traders."""

            async with self._session.post(
                "https://api.x.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.xai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "grok-3",
                    "messages": [
                        {"role": "system", "content": "You are a macro analyst specializing in crypto markets. Provide current, actionable analysis based on real-time news and events."},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 600,
                    "temperature": 0.6,
                }
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    response = data["choices"][0]["message"]["content"].strip()

                    for line in response.split("\n"):
                        line = line.strip()
                        if "|" not in line:
                            continue

                        parts = line.split("|", 1)
                        if len(parts) < 2:
                            continue

                        key = parts[0].strip().upper()
                        value = parts[1].strip()

                        if key == "SHORT":
                            macro.short_term = value
                        elif key == "MEDIUM":
                            macro.medium_term = value
                        elif key == "LONG":
                            macro.long_term = value
                        elif key == "EVENTS":
                            macro.key_events = [e.strip() for e in value.split(",")]

                    logger.info("Grok completed macro analysis")

        except Exception as e:
            logger.error(f"Macro analysis failed: {e}")

        return macro

    async def _get_traditional_markets(self) -> TraditionalMarkets:
        """Get DXY and US stocks sentiment from Grok."""
        markets = TraditionalMarkets()

        if not self.xai_api_key:
            return markets

        try:
            prompt = """Analyze DXY (US Dollar Index) and US stock market sentiment.

Consider:
- Recent Fed policy/commentary
- Treasury yields movement
- Risk-on vs risk-off sentiment
- How dollar strength/weakness affects crypto
- S&P 500, Nasdaq, overall equity sentiment

Provide your analysis in EXACTLY this format:
DXY_DIR|[BULLISH/BEARISH/NEUTRAL]
DXY|[2-3 sentence analysis of dollar outlook]
STOCKS_DIR|[BULLISH/BEARISH/NEUTRAL]
STOCKS|[2-3 sentence analysis of US stocks outlook]
24H|[What to expect in next 24 hours for both]
WEEK|[What to expect this week]
CRYPTO_IMPACT|[How does this affect crypto? 1-2 sentences on correlation]

Be direct and specific. Traders need actionable intel, not fluff."""

            async with self._session.post(
                "https://api.x.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.xai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "grok-3",
                    "messages": [
                        {"role": "system", "content": "You are a traditional markets analyst. Provide current market analysis based on real-time data."},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 500,
                    "temperature": 0.6,
                }
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    response = data["choices"][0]["message"]["content"].strip()

                    for line in response.split("\n"):
                        line = line.strip()
                        if "|" not in line:
                            continue

                        parts = line.split("|", 1)
                        if len(parts) < 2:
                            continue

                        key = parts[0].strip().upper()
                        value = parts[1].strip()

                        if key == "DXY_DIR":
                            markets.dxy_direction = value.upper()
                        elif key == "DXY":
                            markets.dxy_sentiment = value
                        elif key == "STOCKS_DIR":
                            markets.stocks_direction = value.upper()
                        elif key == "STOCKS":
                            markets.stocks_sentiment = value
                        elif key == "24H":
                            markets.next_24h = value
                        elif key == "WEEK":
                            markets.next_week = value
                        elif key == "CRYPTO_IMPACT":
                            markets.correlation_note = value

                    logger.info("Grok completed traditional markets analysis")

        except Exception as e:
            logger.error(f"Traditional markets analysis failed: {e}")

        return markets

    async def _get_stock_picks(self, previous_picks: List[str] = None) -> tuple[List[StockPick], str]:
        """Get top 5 stock picks from Grok with change tracking."""
        picks = []
        changes_note = ""

        if not self.xai_api_key:
            return picks, changes_note

        try:
            prev_context = ""
            if previous_picks:
                prev_context = f"\nPrevious top picks were: {', '.join(previous_picks)}. If any changed, briefly explain why they're no longer top picks."

            prompt = f"""Give me your TOP 5 STOCK PICKS for the next week.

For each pick provide:
- Ticker symbol
- BULLISH or BEARISH direction
- Brief reason (15-25 words) covering catalysts, technicals, or fundamentals
- Price target
- Stop loss level
{prev_context}

Format EXACTLY like this (one per line):
TICKER|DIRECTION|REASON|TARGET|STOP_LOSS

Example:
NVDA|BULLISH|AI demand surge, strong earnings momentum, breaking resistance at $500|$550|$480
TSLA|BEARISH|Delivery miss concerns, competition pressure, head and shoulders pattern forming|$180|$220

If previous picks changed, add a final line:
CHANGES|[Brief explanation of why old picks were dropped]

Respond with ONLY the formatted lines."""

            async with self._session.post(
                "https://api.x.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.xai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "grok-3",
                    "messages": [
                        {"role": "system", "content": "You are a stock market analyst. Provide actionable picks with clear reasoning."},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 500,
                    "temperature": 0.6,
                }
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    response = data["choices"][0]["message"]["content"].strip()

                    for line in response.split("\n"):
                        line = line.strip()
                        if "|" not in line:
                            continue

                        parts = line.split("|")
                        if parts[0].strip().upper() == "CHANGES":
                            changes_note = parts[1].strip() if len(parts) > 1 else ""
                            continue

                        if len(parts) >= 3:
                            pick = StockPick(
                                ticker=parts[0].strip().upper(),
                                direction=parts[1].strip().upper(),
                                reason=parts[2].strip(),
                                target=parts[3].strip() if len(parts) > 3 else "",
                                stop_loss=parts[4].strip() if len(parts) > 4 else "",
                            )
                            picks.append(pick)

                    logger.info(f"Grok provided {len(picks)} stock picks")

        except Exception as e:
            logger.error(f"Stock picks failed: {e}")

        return picks[:5], changes_note

    async def _get_commodity_movers(self) -> List[CommodityMover]:
        """Get top 5 commodity movers with outlook."""
        movers = []

        if not self.xai_api_key:
            return movers

        try:
            prompt = """Identify the TOP 5 COMMODITY MOVERS right now.

Consider: Oil, Natural Gas, Copper, Wheat, Corn, Soybeans, Coffee, Sugar, Cotton, Lumber, etc.

For each mover provide:
- Commodity name
- Direction (UP or DOWN)
- Recent change/move description
- Why it's moving (supply/demand, weather, geopolitics)
- Short-term outlook (next few days)

Format EXACTLY like this (one per line):
COMMODITY|DIRECTION|CHANGE|REASON|OUTLOOK

Example:
Crude Oil|UP|+3.2% this week|Middle East tensions, OPEC cuts|Likely to test $85 resistance
Natural Gas|DOWN|-8% weekly|Warm weather forecast, storage surplus|Further downside to $2.50

Respond with ONLY the formatted lines."""

            async with self._session.post(
                "https://api.x.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.xai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "grok-3",
                    "messages": [
                        {"role": "system", "content": "You are a commodities analyst. Provide current market movers with actionable insights."},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 400,
                    "temperature": 0.6,
                }
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    response = data["choices"][0]["message"]["content"].strip()

                    for line in response.split("\n"):
                        line = line.strip()
                        if "|" not in line:
                            continue

                        parts = line.split("|")
                        if len(parts) >= 4:
                            mover = CommodityMover(
                                name=parts[0].strip(),
                                direction=parts[1].strip().upper(),
                                change=parts[2].strip(),
                                reason=parts[3].strip(),
                                outlook=parts[4].strip() if len(parts) > 4 else "",
                            )
                            movers.append(mover)

                    logger.info(f"Grok provided {len(movers)} commodity movers")

        except Exception as e:
            logger.error(f"Commodity movers failed: {e}")

        return movers[:5]

    async def _get_precious_metals_outlook(self) -> PreciousMetalsOutlook:
        """Get weekly outlook for Gold, Silver, and Platinum."""
        outlook = PreciousMetalsOutlook()

        if not self.xai_api_key:
            return outlook

        try:
            prompt = """Provide your WEEKLY OUTLOOK for precious metals: Gold, Silver, and Platinum.

For each metal analyze:
- Current price action and trend
- Key drivers (Fed policy, dollar strength, inflation, industrial demand)
- Support/resistance levels
- Direction for next week (BULLISH/BEARISH/NEUTRAL)

Format EXACTLY like this:
GOLD_DIR|[BULLISH/BEARISH/NEUTRAL]
GOLD|[2-3 sentence outlook with price levels and reasoning]
SILVER_DIR|[BULLISH/BEARISH/NEUTRAL]
SILVER|[2-3 sentence outlook with price levels and reasoning]
PLATINUM_DIR|[BULLISH/BEARISH/NEUTRAL]
PLATINUM|[2-3 sentence outlook with price levels and reasoning]

Be specific about price targets and key levels to watch."""

            async with self._session.post(
                "https://api.x.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.xai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "grok-3",
                    "messages": [
                        {"role": "system", "content": "You are a precious metals analyst. Provide actionable weekly outlook with specific price levels."},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 400,
                    "temperature": 0.6,
                }
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    response = data["choices"][0]["message"]["content"].strip()

                    for line in response.split("\n"):
                        line = line.strip()
                        if "|" not in line:
                            continue

                        parts = line.split("|", 1)
                        if len(parts) < 2:
                            continue

                        key = parts[0].strip().upper()
                        value = parts[1].strip()

                        if key == "GOLD_DIR":
                            outlook.gold_direction = value.upper()
                        elif key == "GOLD":
                            outlook.gold_outlook = value
                        elif key == "SILVER_DIR":
                            outlook.silver_direction = value.upper()
                        elif key == "SILVER":
                            outlook.silver_outlook = value
                        elif key == "PLATINUM_DIR":
                            outlook.platinum_direction = value.upper()
                        elif key == "PLATINUM":
                            outlook.platinum_outlook = value

                    logger.info("Grok completed precious metals outlook")

        except Exception as e:
            logger.error(f"Precious metals outlook failed: {e}")

        return outlook

    def _get_previous_stock_picks(self) -> List[str]:
        """Get previous stock picks from history for change tracking."""
        try:
            if PREDICTIONS_FILE.exists():
                with open(PREDICTIONS_FILE, "r") as f:
                    history = json.load(f)
                    if history and "stock_picks" in history[-1]:
                        return history[-1]["stock_picks"]
        except Exception as e:
            logger.debug(f"Could not load previous picks: {e}")
        return []

    def _save_predictions(self, tokens: List[TokenSentiment], macro: MacroAnalysis, markets: TraditionalMarkets,
                          stock_picks: List[StockPick] = None, commodities: List[CommodityMover] = None,
                          precious_metals: PreciousMetalsOutlook = None):
        """Save predictions to track accuracy over time."""
        try:
            # Load existing predictions
            history = []
            if PREDICTIONS_FILE.exists():
                with open(PREDICTIONS_FILE, "r") as f:
                    history = json.load(f)

            # Create new prediction record
            record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "token_predictions": {
                    t.symbol: {
                        "verdict": t.grok_verdict,
                        "score": t.grok_score,
                        "price_at_prediction": t.price_usd,
                        "targets": t.grok_analysis,
                        "reasoning": t.grok_reasoning,
                        "contract": t.contract_address,
                    }
                    for t in tokens if t.grok_verdict
                },
                "macro_predictions": {
                    "short_term": macro.short_term,
                    "medium_term": macro.medium_term,
                    "long_term": macro.long_term,
                },
                "market_predictions": {
                    "dxy_direction": markets.dxy_direction,
                    "stocks_direction": markets.stocks_direction,
                    "next_24h": markets.next_24h,
                    "next_week": markets.next_week,
                },
                "stock_picks": [p.ticker for p in (stock_picks or [])],
                "stock_picks_detail": {
                    p.ticker: {"direction": p.direction, "reason": p.reason, "target": p.target}
                    for p in (stock_picks or [])
                },
                "commodity_movers": [c.name for c in (commodities or [])],
                "precious_metals": {
                    "gold": precious_metals.gold_direction if precious_metals else "",
                    "silver": precious_metals.silver_direction if precious_metals else "",
                    "platinum": precious_metals.platinum_direction if precious_metals else "",
                }
            }

            history.append(record)

            # Keep last 100 predictions
            if len(history) > 100:
                history = history[-100:]

            with open(PREDICTIONS_FILE, "w") as f:
                json.dump(history, f, indent=2)

            logger.info(f"Saved prediction record (total: {len(history)})")

        except Exception as e:
            logger.error(f"Failed to save predictions: {e}")

    def _format_report(self, tokens: List[TokenSentiment], grok_summary: str, macro: MacroAnalysis = None,
                        markets: TraditionalMarkets = None, stock_picks: List[StockPick] = None,
                        picks_changes: str = "", commodities: List[CommodityMover] = None,
                        precious_metals: PreciousMetalsOutlook = None) -> List[str]:
        """Format beautiful sentiment report. Returns list of messages (split for Telegram limit)."""
        now = datetime.now(timezone.utc)

        # Sort by sentiment score
        tokens_sorted = sorted(tokens, key=lambda t: t.sentiment_score, reverse=True)

        # Header
        lines = [
            "<b>========================================</b>",
            "<b>     JARVIS SENTIMENT REPORT</b>",
            "<b>========================================</b>",
            f"<i>{now.strftime('%B %d, %Y')} | {now.strftime('%H:%M')} UTC</i>",
            "",
            "<b>HOT TRENDING SOLANA TOKENS</b>",
            "<b>________________________________________</b>",
            "",
        ]

        # Token rows
        for i, t in enumerate(tokens_sorted, 1):
            # Sentiment emoji based on combined score
            if t.sentiment_score > 0.3:
                emoji = "🟢"
            elif t.sentiment_score > 0:
                emoji = "🟡"
            elif t.sentiment_score > -0.3:
                emoji = "🟠"
            else:
                emoji = "🔴"

            # Grok verdict indicator
            grok_icon = ""
            if t.grok_verdict == "BULLISH":
                grok_icon = "🤖+"
            elif t.grok_verdict == "BEARISH":
                grok_icon = "🤖-"
            elif t.grok_verdict:
                grok_icon = "🤖"

            # Trend arrow
            if t.change_24h > 5:
                trend = "+++"
            elif t.change_24h > 0:
                trend = "++"
            elif t.change_24h > -5:
                trend = "--"
            else:
                trend = "---"

            # Format price
            if t.price_usd >= 1:
                price_str = f"${t.price_usd:,.2f}"
            elif t.price_usd >= 0.01:
                price_str = f"${t.price_usd:.4f}"
            else:
                price_str = f"${t.price_usd:.6f}"

            # Format market cap
            if t.mcap >= 1_000_000:
                mcap_str = f"${t.mcap/1_000_000:.2f}M"
            elif t.mcap >= 1_000:
                mcap_str = f"${t.mcap/1_000:.1f}K"
            else:
                mcap_str = f"${t.mcap:.0f}"

            # Build token entry with contract and DexScreener link
            entry = (
                f"{emoji} <b>{i}. {t.symbol}</b>  {t.grade} {grok_icon}\n"
                f"   {price_str}  <code>{t.change_24h:+.1f}%</code> {trend}\n"
                f"   MCap: <code>{mcap_str}</code> | B/S: <code>{t.buy_sell_ratio:.2f}x</code> | Vol: <code>${t.volume_24h/1000:.0f}K</code>"
            )

            # Add contract address and DexScreener link (always show if available)
            if t.contract_address:
                addr_short = t.contract_address[:6] + "..." + t.contract_address[-4:]
                entry += f"\n   📋 <code>{t.contract_address}</code>"
                entry += f"\n   📊 <a href=\"https://dexscreener.com/solana/{t.contract_address}\">DexScreener</a> | <a href=\"https://solscan.io/token/{t.contract_address}\">Solscan</a>"

            # Add reasoning for ALL tokens
            if t.grok_reasoning:
                entry += f"\n   <i>Why: {t.grok_reasoning}</i>"

            # Add price targets for bullish tokens
            if t.grok_verdict == "BULLISH" and t.grok_analysis:
                entry += f"\n   <b>Targets:</b> <i>{t.grok_analysis}</i>"

            lines.append(entry)
            lines.append("")

        # Summary stats
        bullish_count = sum(1 for t in tokens if t.sentiment_score > 0.1)
        bearish_count = sum(1 for t in tokens if t.sentiment_score < -0.1)
        neutral_count = len(tokens) - bullish_count - bearish_count

        avg_change = sum(t.change_24h for t in tokens) / len(tokens)

        lines.extend([
            "<b>________________________________________</b>",
            "",
            "<b>MICROCAP SUMMARY</b>",
            f"   🟢 Bullish:  <code>{bullish_count}</code>",
            f"   🟡 Neutral:  <code>{neutral_count}</code>",
            f"   🔴 Bearish:  <code>{bearish_count}</code>",
            f"   Avg 24h:    <code>{avg_change:+.1f}%</code>",
            "",
            "<i>Markets + Macro analysis in next message...</i>",
        ])

        # Build message 1: Token analysis
        msg1 = "\n".join(lines)

        # Build message 2: Markets + Macro + Summary
        lines2 = []

        # Traditional Markets Section
        if markets and (markets.dxy_sentiment or markets.stocks_sentiment):
            dxy_emoji = "🟢" if markets.dxy_direction == "BULLISH" else "🔴" if markets.dxy_direction == "BEARISH" else "🟡"
            stocks_emoji = "🟢" if markets.stocks_direction == "BULLISH" else "🔴" if markets.stocks_direction == "BEARISH" else "🟡"

            lines2.extend([
                "<b>========================================</b>",
                "<b>   TRADITIONAL MARKETS</b>",
                "<b>========================================</b>",
                "",
                f"{dxy_emoji} <b>DXY (Dollar)</b>: {markets.dxy_direction}",
            ])
            if markets.dxy_sentiment:
                lines2.append(f"<i>{markets.dxy_sentiment}</i>")
            lines2.append("")

            lines2.extend([
                f"{stocks_emoji} <b>US Stocks</b>: {markets.stocks_direction}",
            ])
            if markets.stocks_sentiment:
                lines2.append(f"<i>{markets.stocks_sentiment}</i>")
            lines2.append("")

            if markets.next_24h:
                lines2.append(f"<b>Next 24h:</b> <i>{markets.next_24h}</i>")
            if markets.next_week:
                lines2.append(f"<b>This Week:</b> <i>{markets.next_week}</i>")
            if markets.correlation_note:
                lines2.extend(["", f"<b>Crypto Impact:</b> <i>{markets.correlation_note}</i>"])
            lines2.append("")

        # Macro Events Section
        if macro and (macro.short_term or macro.medium_term or macro.long_term):
            lines2.extend([
                "<b>________________________________________</b>",
                "",
                "<b>MACRO & GEOPOLITICS</b>",
                "",
            ])
            if macro.short_term:
                lines2.extend([
                    "⏰ <b>Next 24 Hours:</b>",
                    f"<i>{macro.short_term}</i>",
                    "",
                ])
            if macro.medium_term:
                lines2.extend([
                    "📅 <b>Next 3 Days:</b>",
                    f"<i>{macro.medium_term}</i>",
                    "",
                ])
            if macro.long_term:
                lines2.extend([
                    "🗓 <b>1 Week - 1 Month:</b>",
                    f"<i>{macro.long_term}</i>",
                    "",
                ])
            if macro.key_events:
                lines2.extend([
                    "<b>Key Events to Watch:</b>",
                    f"<i>{', '.join(macro.key_events[:5])}</i>",
                    "",
                ])

        # Grok's Overall Take
        lines2.extend([
            "<b>________________________________________</b>",
            "",
            "<b>GROK'S TAKE</b>",
            f"<i>{grok_summary}</i>",
            "",
            "<i>Stocks, Commodities & Metals in next message...</i>",
        ])

        msg2 = "\n".join(lines2)

        # Build message 3: Stocks, Commodities, Precious Metals
        lines3 = []

        # Stock Picks Section
        if stock_picks:
            lines3.extend([
                "<b>========================================</b>",
                "<b>   TOP 5 STOCK PICKS</b>",
                "<b>========================================</b>",
                "",
            ])

            for i, pick in enumerate(stock_picks, 1):
                emoji = "🟢" if pick.direction == "BULLISH" else "🔴"
                lines3.append(f"{emoji} <b>{i}. {pick.ticker}</b> - {pick.direction}")
                lines3.append(f"   <i>{pick.reason}</i>")
                if pick.target or pick.stop_loss:
                    targets = []
                    if pick.target:
                        targets.append(f"Target: {pick.target}")
                    if pick.stop_loss:
                        targets.append(f"Stop: {pick.stop_loss}")
                    lines3.append(f"   <b>{' | '.join(targets)}</b>")
                lines3.append("")

            if picks_changes:
                lines3.extend([
                    "<b>Changes from last report:</b>",
                    f"<i>{picks_changes}</i>",
                    "",
                ])

        # Commodity Movers Section
        if commodities:
            lines3.extend([
                "<b>________________________________________</b>",
                "",
                "<b>TOP 5 COMMODITY MOVERS</b>",
                "",
            ])

            for i, c in enumerate(commodities, 1):
                emoji = "📈" if c.direction == "UP" else "📉"
                lines3.append(f"{emoji} <b>{i}. {c.name}</b> ({c.change})")
                lines3.append(f"   <i>Why: {c.reason}</i>")
                if c.outlook:
                    lines3.append(f"   <b>Outlook:</b> <i>{c.outlook}</i>")
                lines3.append("")

        # Precious Metals Section
        if precious_metals and (precious_metals.gold_outlook or precious_metals.silver_outlook):
            lines3.extend([
                "<b>________________________________________</b>",
                "",
                "<b>PRECIOUS METALS (Weekly)</b>",
                "",
            ])

            # Gold
            gold_emoji = "🟢" if precious_metals.gold_direction == "BULLISH" else "🔴" if precious_metals.gold_direction == "BEARISH" else "🟡"
            lines3.extend([
                f"{gold_emoji} <b>GOLD</b>: {precious_metals.gold_direction}",
                f"<i>{precious_metals.gold_outlook}</i>",
                "",
            ])

            # Silver
            silver_emoji = "🟢" if precious_metals.silver_direction == "BULLISH" else "🔴" if precious_metals.silver_direction == "BEARISH" else "🟡"
            lines3.extend([
                f"{silver_emoji} <b>SILVER</b>: {precious_metals.silver_direction}",
                f"<i>{precious_metals.silver_outlook}</i>",
                "",
            ])

            # Platinum
            plat_emoji = "🟢" if precious_metals.platinum_direction == "BULLISH" else "🔴" if precious_metals.platinum_direction == "BEARISH" else "🟡"
            lines3.extend([
                f"{plat_emoji} <b>PLATINUM</b>: {precious_metals.platinum_direction}",
                f"<i>{precious_metals.platinum_outlook}</i>",
                "",
            ])

        # Disclaimer
        lines3.extend([
            "<b>========================================</b>",
            "",
            "<b>DISCLAIMER</b>",
            "<i>Grok and JARVIS are giving their best guesses, not financial advice. All trades are YOUR responsibility. DYOR. NFA.</i>",
            "",
            "<i>Powered by JARVIS AI - Predictions tracked internally for accuracy</i>",
        ])

        msg3 = "\n".join(lines3)

        return [msg1, msg2, msg3]

    def _split_message(self, msg: str, max_len: int = 4000) -> List[str]:
        """Split a message into chunks that fit Telegram's limit (4096 chars)."""
        if len(msg) <= max_len:
            return [msg]

        chunks = []
        lines = msg.split("\n")
        current_chunk = []
        current_len = 0

        for line in lines:
            # +1 for the newline
            line_len = len(line) + 1
            if current_len + line_len > max_len:
                if current_chunk:
                    chunks.append("\n".join(current_chunk))
                current_chunk = [line]
                current_len = line_len
            else:
                current_chunk.append(line)
                current_len += line_len

        if current_chunk:
            chunks.append("\n".join(current_chunk))

        return chunks

    async def _post_to_telegram(self, messages: List[str], tokens: List[TokenSentiment] = None):
        """Post report messages to Telegram with ape buttons for tradeable assets."""
        msg_num = 0
        for i, msg in enumerate(messages):
            # Split long messages
            chunks = self._split_message(msg)

            for chunk in chunks:
                msg_num += 1
                try:
                    payload = {
                        "chat_id": self.chat_id,
                        "text": chunk,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": "true",
                    }

                    async with self._session.post(
                        f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                        json=payload
                    ) as resp:
                        result = await resp.json()
                        if not result.get("ok"):
                            logger.error(f"Telegram error on message {msg_num}: {result}")

                    # Small delay between messages
                    await asyncio.sleep(0.3)

                except Exception as e:
                    logger.error(f"Failed to post message {msg_num} to Telegram: {e}")

        # Post ape buttons for bullish crypto tokens with TP/SL profiles
        await self._post_ape_buttons(tokens)

        # Post XStocks/PreStocks tradeable section
        await self._post_xstocks_section()

        # Post treasury status as final message
        await self._post_treasury_status()

    async def _post_ape_buttons(self, tokens: List[TokenSentiment] = None):
        """Post ape buttons with Grok-driven TP/SL targets for bullish tokens."""
        if not tokens:
            logger.debug("No tokens provided for ape buttons")
            return

        # Filter for bullish tokens with contracts AND Grok targets
        tradeable = [
            t for t in tokens
            if t.grok_verdict == "BULLISH"
            and t.contract_address
            and t.grok_target_safe  # Must have Grok targets
        ]

        logger.info(f"Found {len(tradeable)} bullish tokens with Grok targets")

        if not tradeable:
            # If no tokens have full targets, try any bullish with contract
            tradeable = [t for t in tokens if t.grok_verdict == "BULLISH" and t.contract_address]
            if not tradeable:
                logger.debug("No tradeable bullish tokens found")
                return

        try:
            # Header message
            header = """
<b>========================================</b>
<b>   🦍 SOLANA APE BUTTONS</b>
<b>========================================</b>

<b>Grok-Driven Targets:</b>
🛡️ SAFE = Conservative target
⚖️ MED = Medium risk target
🔥 DEGEN = Moon target

<i>All TP/SL set by Grok AI analysis</i>
<i>Treasury protected - MUST hit targets</i>
"""
            async with self._session.post(
                f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": header,
                    "parse_mode": "HTML",
                }
            ) as resp:
                await resp.json()

            await asyncio.sleep(0.3)

            # Post buttons for top 3 bullish tokens
            for t in tradeable[:3]:
                try:
                    # Build Grok targets display
                    targets_display = []
                    if t.grok_stop_loss:
                        targets_display.append(f"🛑 SL: {t.grok_stop_loss}")
                    if t.grok_target_safe:
                        targets_display.append(f"🛡️ Safe: {t.grok_target_safe}")
                    if t.grok_target_med:
                        targets_display.append(f"⚖️ Med: {t.grok_target_med}")
                    if t.grok_target_degen:
                        targets_display.append(f"🔥 Degen: {t.grok_target_degen}")

                    targets_str = " | ".join(targets_display) if targets_display else "Awaiting targets..."

                    # Create simple buttons with Grok targets
                    keyboard = self._create_grok_ape_keyboard(t)

                    # Escape HTML in reasoning and truncate safely
                    import html
                    reasoning = html.escape(t.grok_reasoning[:80]) if t.grok_reasoning else "Grok analysis pending"
                    if len(t.grok_reasoning) > 80:
                        reasoning += "..."

                    token_msg = (
                        f"<b>{html.escape(t.symbol)}</b> ({t.grok_verdict})\n"
                        f"${t.price_usd:.8f}\n"
                        f"{reasoning}\n\n"
                        f"<b>Grok Targets:</b>\n"
                        f"{targets_str}"
                    )

                    async with self._session.post(
                        f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                        json={
                            "chat_id": self.chat_id,
                            "text": token_msg,
                            "parse_mode": "HTML",
                            "reply_markup": keyboard.to_dict(),
                        }
                    ) as resp:
                        result = await resp.json()
                        if not result.get("ok"):
                            logger.error(f"Failed to post ape buttons for {t.symbol}: {result}")
                        else:
                            logger.info(f"Posted ape buttons for {t.symbol}")

                    await asyncio.sleep(0.3)

                except Exception as e:
                    logger.error(f"Error posting ape buttons for {t.symbol}: {e}")

        except Exception as e:
            logger.error(f"Failed to post ape buttons section: {e}")

    def _create_grok_ape_keyboard(self, token: 'TokenSentiment') -> InlineKeyboardMarkup:
        """Create ape keyboard with Grok-driven targets."""
        contract_short = token.contract_address[:10] if token.contract_address else ""

        buttons = []

        # Header row showing token info
        buttons.append([
            InlineKeyboardButton(
                text=f"📊 {token.symbol} Info",
                callback_data=f"info:t:{token.symbol}:{contract_short}"[:64]
            )
        ])

        # Row 1: 5% allocation with three risk levels
        buttons.append([
            InlineKeyboardButton(
                text="5% 🛡️ Safe",
                callback_data=f"ape:5:s:t:{token.symbol}:{contract_short}"[:64]
            ),
            InlineKeyboardButton(
                text="5% ⚖️ Med",
                callback_data=f"ape:5:m:t:{token.symbol}:{contract_short}"[:64]
            ),
            InlineKeyboardButton(
                text="5% 🔥 Degen",
                callback_data=f"ape:5:d:t:{token.symbol}:{contract_short}"[:64]
            ),
        ])

        # Row 2: 2% allocation
        buttons.append([
            InlineKeyboardButton(
                text="2% 🛡️ Safe",
                callback_data=f"ape:2:s:t:{token.symbol}:{contract_short}"[:64]
            ),
            InlineKeyboardButton(
                text="2% ⚖️ Med",
                callback_data=f"ape:2:m:t:{token.symbol}:{contract_short}"[:64]
            ),
            InlineKeyboardButton(
                text="2% 🔥 Degen",
                callback_data=f"ape:2:d:t:{token.symbol}:{contract_short}"[:64]
            ),
        ])

        # Row 3: 1% allocation
        buttons.append([
            InlineKeyboardButton(
                text="1% 🛡️ Safe",
                callback_data=f"ape:1:s:t:{token.symbol}:{contract_short}"[:64]
            ),
            InlineKeyboardButton(
                text="1% ⚖️ Med",
                callback_data=f"ape:1:m:t:{token.symbol}:{contract_short}"[:64]
            ),
            InlineKeyboardButton(
                text="1% 🔥 Degen",
                callback_data=f"ape:1:d:t:{token.symbol}:{contract_short}"[:64]
            ),
        ])

        return InlineKeyboardMarkup(buttons)

    async def _post_xstocks_section(self):
        """Post XStocks/PreStocks tradeable stocks section."""
        try:
            # Fetch XStocks universe
            xstocks, xstocks_warnings = fetch_xstocks_universe()
            prestocks, prestocks_warnings = fetch_prestocks_universe()

            # Combine and filter
            all_stocks = xstocks + prestocks

            if not all_stocks:
                logger.debug("No XStocks/PreStocks available")
                return

            # Header message with stock-appropriate targets
            header = """
<b>========================================</b>
<b>   📊 XSTOCKS TRADEABLE</b>
<b>========================================</b>

<b>Tokenized Stocks on Solana</b>
Trade stocks 24/7 with SOL/USDC

<b>Stock Risk Profiles:</b>
🛡️ SAFE: +5% TP / -2% SL
⚖️ MED: +10% TP / -4% SL
🔥 DEGEN: +20% TP / -8% SL

<i>Source: XStocks.fi + PreStocks.com</i>
"""
            async with self._session.post(
                f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": header,
                    "parse_mode": "HTML",
                }
            ) as resp:
                await resp.json()

            await asyncio.sleep(0.3)

            # Group by issuer
            xstocks_list = [s for s in all_stocks if s.issuer == "xstocks"][:5]
            prestocks_list = [s for s in all_stocks if s.issuer == "prestocks"][:5]

            # Post XStocks
            if xstocks_list:
                for stock in xstocks_list:
                    try:
                        keyboard = create_ape_buttons_with_tp_sl(
                            symbol=stock.symbol,
                            asset_type="stock",
                            contract_address=stock.mint_address or "",
                            entry_price=0.0,  # Price fetched at trade time
                            grade="",
                        )

                        stock_msg = f"<b>📈 {stock.symbol}</b> ({stock.underlying_ticker}) - XStocks"

                        async with self._session.post(
                            f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                            json={
                                "chat_id": self.chat_id,
                                "text": stock_msg,
                                "parse_mode": "HTML",
                                "reply_markup": keyboard.to_dict(),
                            }
                        ) as resp:
                            result = await resp.json()
                            if not result.get("ok"):
                                logger.debug(f"XStock button error: {result}")

                        await asyncio.sleep(0.2)

                    except Exception as e:
                        logger.debug(f"XStock button error for {stock.symbol}: {e}")

            # Post PreStocks
            if prestocks_list:
                for stock in prestocks_list:
                    if stock.symbol == "UNKNOWN":
                        continue
                    try:
                        keyboard = create_ape_buttons_with_tp_sl(
                            symbol=stock.symbol,
                            asset_type="stock",
                            contract_address=stock.mint_address or "",
                            entry_price=0.0,
                            grade="",
                        )

                        stock_msg = f"<b>📈 {stock.symbol}</b> ({stock.underlying_ticker}) - PreStocks"

                        async with self._session.post(
                            f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                            json={
                                "chat_id": self.chat_id,
                                "text": stock_msg,
                                "parse_mode": "HTML",
                                "reply_markup": keyboard.to_dict(),
                            }
                        ) as resp:
                            result = await resp.json()
                            if not result.get("ok"):
                                logger.debug(f"PreStock button error: {result}")

                        await asyncio.sleep(0.2)

                    except Exception as e:
                        logger.debug(f"PreStock button error for {stock.symbol}: {e}")

        except Exception as e:
            logger.error(f"Failed to post XStocks section: {e}")

    async def _post_treasury_status(self):
        """Post treasury status at the end of report."""
        try:
            # Try to get treasury status
            treasury_status = await self._get_treasury_status()

            if treasury_status:
                status_msg = f"""
<b>========================================</b>
<b>   💰 TREASURY STATUS</b>
<b>========================================</b>

Balance: <code>{treasury_status['balance_sol']:.4f} SOL</code> (~${treasury_status['balance_usd']:,.2f})
Open Positions: <code>{treasury_status['positions']}</code>
24h P&L: {'📈' if treasury_status['pnl_24h'] >= 0 else '📉'} <code>{treasury_status['pnl_24h']:+.2f}%</code>

Treasury: <code>{treasury_status['address'][:12]}...{treasury_status['address'][-4:]}</code>
<a href="https://solscan.io/account/{treasury_status['address']}">View on Solscan</a>

<i>Use APE buttons above to trade with treasury</i>
<i>All trades follow Grok's recommended TP/SL</i>
"""
                async with self._session.post(
                    f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                    data={
                        "chat_id": self.chat_id,
                        "text": status_msg,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": "false",
                    }
                ) as resp:
                    result = await resp.json()
                    if not result.get("ok"):
                        logger.debug(f"Treasury status not posted: {result}")

        except Exception as e:
            logger.debug(f"Could not post treasury status: {e}")

    async def _get_treasury_status(self) -> Optional[Dict[str, Any]]:
        """Get current treasury status from blockchain."""
        try:
            from bots.treasury.trading import TreasuryTrader

            trader = TreasuryTrader()
            initialized, msg = await trader._ensure_initialized()

            if initialized and trader._engine:
                balance_sol, balance_usd = await trader._engine.get_portfolio_value()
                address = os.environ.get("TREASURY_WALLET_ADDRESS", "")

                return {
                    "address": address,
                    "balance_sol": balance_sol,
                    "balance_usd": balance_usd,
                    "positions": 0,  # Would get from trading engine
                    "pnl_24h": 0.0,  # Would calculate from trade history
                }
            else:
                logger.debug(f"Treasury init failed: {msg}")

        except Exception as e:
            logger.debug(f"Treasury not available: {e}")

        # Fallback: Try to fetch balance directly via RPC
        try:
            treasury_addr = os.environ.get("TREASURY_WALLET_ADDRESS", "")
            helius_rpc = os.environ.get("HELIUS_RPC_URL", "")

            if treasury_addr and helius_rpc and self._session:
                # Fetch SOL balance via RPC
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getBalance",
                    "params": [treasury_addr]
                }
                async with self._session.post(helius_rpc, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        lamports = data.get("result", {}).get("value", 0)
                        balance_sol = lamports / 1_000_000_000

                        # Fetch SOL price
                        sol_price = 100  # Default
                        try:
                            async with self._session.get(
                                "https://api.dexscreener.com/latest/dex/tokens/So11111111111111111111111111111111111111112"
                            ) as price_resp:
                                if price_resp.status == 200:
                                    price_data = await price_resp.json()
                                    pairs = price_data.get("pairs", [])
                                    if pairs:
                                        sol_price = float(pairs[0].get("priceUsd", 100) or 100)
                        except:
                            pass

                        return {
                            "address": treasury_addr,
                            "balance_sol": balance_sol,
                            "balance_usd": balance_sol * sol_price,
                            "positions": 0,
                            "pnl_24h": 0.0,
                        }
        except Exception as e:
            logger.debug(f"RPC balance fetch failed: {e}")

        return None


async def run_sentiment_reporter():
    """Run the sentiment report generator."""
    from pathlib import Path

    # Load env
    env_path = Path(__file__).resolve().parents[2] / "tg_bot" / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_BUY_BOT_CHAT_ID")
    xai_key = os.environ.get("XAI_API_KEY")

    if not all([bot_token, chat_id]):
        print("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_BUY_BOT_CHAT_ID")
        return

    generator = SentimentReportGenerator(
        bot_token=bot_token,
        chat_id=chat_id,
        xai_api_key=xai_key,
        interval_minutes=30,
    )

    try:
        await generator.start()
    except KeyboardInterrupt:
        await generator.stop()


if __name__ == "__main__":
    import sys
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_sentiment_reporter())
