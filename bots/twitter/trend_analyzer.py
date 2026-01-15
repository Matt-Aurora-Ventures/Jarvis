"""
Trend Analyzer for X Bot Alpha Signals

Analyzes market trends across multiple data sources to generate:
- Alpha signals (early movers, breakouts, unusual activity)
- Trend analysis (market sentiment, sector rotation, macro insights)
- Social signals (X trending, mentions velocity, sentiment shifts)
- On-chain signals (whale activity, smart money flows, DEX volume)

Used by autonomous_engine.py for generating insightful tweets.
"""

import asyncio
import json
import os
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum
import aiohttp

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Types of alpha signals."""
    BREAKOUT = "breakout"           # Price breaking key levels
    VOLUME_SURGE = "volume_surge"   # Unusual volume activity
    WHALE_MOVE = "whale_move"       # Large wallet activity
    SMART_MONEY = "smart_money"     # Known alpha wallets trading
    SOCIAL_BUZZ = "social_buzz"     # Trending on social platforms
    MOMENTUM_SHIFT = "momentum_shift"  # RSI/momentum change
    LIQUIDITY_EVENT = "liquidity_event"  # New pool or LP changes
    DIVERGENCE = "divergence"       # Price/indicator divergence
    ACCUMULATION = "accumulation"   # Accumulation patterns
    DISTRIBUTION = "distribution"   # Distribution patterns


class SignalStrength(Enum):
    """Signal strength levels."""
    WEAK = 1
    MODERATE = 2
    STRONG = 3
    EXTREME = 4


@dataclass
class AlphaSignal:
    """An alpha signal detected by the analyzer."""
    signal_type: SignalType
    strength: SignalStrength
    symbol: str
    description: str
    metrics: Dict[str, Any] = field(default_factory=dict)
    contract_address: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    confidence: float = 0.5
    source: str = "internal"
    chain: str = "solana"  # Multi-chain support

    def to_tweet_context(self) -> Dict[str, str]:
        """Convert signal to tweet template context."""
        sentiment_map = {
            SignalType.BREAKOUT: "breaking out",
            SignalType.VOLUME_SURGE: "seeing massive volume",
            SignalType.WHALE_MOVE: "whale activity detected",
            SignalType.SMART_MONEY: "smart money moving",
            SignalType.SOCIAL_BUZZ: "trending heavily",
            SignalType.MOMENTUM_SHIFT: "momentum shifting",
            SignalType.LIQUIDITY_EVENT: "liquidity changes",
            SignalType.DIVERGENCE: "showing divergence",
            SignalType.ACCUMULATION: "accumulation detected",
            SignalType.DISTRIBUTION: "distribution pattern",
        }

        strength_words = {
            SignalStrength.WEAK: "slight",
            SignalStrength.MODERATE: "notable",
            SignalStrength.STRONG: "significant",
            SignalStrength.EXTREME: "extreme",
        }

        return {
            "symbol": self.symbol,
            "sentiment": sentiment_map.get(self.signal_type, "interesting"),
            "reason": self.description,
            "metrics": self._format_metrics(),
            "strength": strength_words.get(self.strength, "notable"),
            "signal_type": self.signal_type.value,
            "confidence": f"{int(self.confidence * 100)}%",
        }

    def _format_metrics(self) -> str:
        """Format metrics for tweet."""
        parts = []
        if "volume_24h" in self.metrics:
            parts.append(f"${self.metrics['volume_24h']:,.0f} 24h volume")
        if "price_change_24h" in self.metrics:
            parts.append(f"{self.metrics['price_change_24h']:+.1f}% 24h")
        if "liquidity" in self.metrics:
            parts.append(f"${self.metrics['liquidity']:,.0f} liq")
        if "mcap" in self.metrics:
            parts.append(f"${self.metrics['mcap']:,.0f} mcap")
        return ". ".join(parts) if parts else "metrics processing"


@dataclass
class TrendInsight:
    """A macro trend insight."""
    category: str  # "market", "sector", "narrative", "macro"
    title: str
    summary: str
    details: Dict[str, Any] = field(default_factory=dict)
    relevance: float = 0.5
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    chain: str = "solana"  # Multi-chain support

    def to_tweet_context(self) -> Dict[str, str]:
        """Convert insight to tweet template context."""
        return {
            "insight": self.summary,
            "analysis": self.title,
            "take": self._generate_take(),
            "category": self.category,
        }

    def _generate_take(self) -> str:
        """Generate a take based on the insight."""
        if self.relevance > 0.7:
            return "worth paying attention to"
        elif self.relevance > 0.5:
            return "something to watch"
        else:
            return "on my radar but not urgent"


class TrendAnalyzer:
    """
    Analyzes trends and generates alpha signals from multiple sources.
    """

    def __init__(self):
        self.cache: Dict[str, Any] = {}
        self.cache_ttl = 300  # 5 minutes
        self.last_fetch: Dict[str, float] = {}

        # API endpoints
        self.dexscreener_base = "https://api.dexscreener.com/latest/dex"
        self.coingecko_base = "https://api.coingecko.com/api/v3"
        self.birdeye_base = "https://public-api.birdeye.so"

    async def _fetch_json(self, url: str, headers: Dict = None) -> Optional[Dict]:
        """Fetch JSON from URL with caching."""
        cache_key = url
        now = datetime.now().timestamp()

        # Check cache
        if cache_key in self.cache and cache_key in self.last_fetch:
            if now - self.last_fetch[cache_key] < self.cache_ttl:
                return self.cache[cache_key]

        try:
            async with aiohttp.ClientSession() as session:
                default_headers = {"User-Agent": "JarvisBot/1.0"}
                if headers:
                    default_headers.update(headers)

                async with session.get(url, headers=default_headers, timeout=15) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self.cache[cache_key] = data
                        self.last_fetch[cache_key] = now
                        return data
                    else:
                        logger.warning(f"API returned {resp.status}: {url}")
                        return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    async def get_trending_tokens(self, chain: str = "solana") -> List[Dict]:
        """Get trending tokens from DexScreener."""
        url = f"{self.dexscreener_base}/search/boosted?chainId={chain}"
        data = await self._fetch_json(url)

        if not data or "pairs" not in data:
            # Try alternative endpoint
            url = f"{self.dexscreener_base}/pairs/{chain}"
            data = await self._fetch_json(url)

        pairs = data.get("pairs", []) if data else []

        # Sort by volume
        pairs.sort(key=lambda x: float(x.get("volume", {}).get("h24", 0) or 0), reverse=True)

        return pairs[:20]  # Top 20

    async def get_token_data(self, mint: str) -> Optional[Dict]:
        """Get detailed token data."""
        url = f"{self.dexscreener_base}/tokens/{mint}"
        data = await self._fetch_json(url)

        if data and "pairs" in data and data["pairs"]:
            return data["pairs"][0]
        return None

    async def analyze_token_for_signals(self, token_data: Dict) -> List[AlphaSignal]:
        """Analyze a token for potential alpha signals."""
        signals = []

        symbol = token_data.get("baseToken", {}).get("symbol", "UNKNOWN")
        address = token_data.get("baseToken", {}).get("address", "")

        price_usd = float(token_data.get("priceUsd", 0) or 0)
        volume_24h = float(token_data.get("volume", {}).get("h24", 0) or 0)
        liquidity = float(token_data.get("liquidity", {}).get("usd", 0) or 0)
        mcap = float(token_data.get("fdv", 0) or token_data.get("marketCap", 0) or 0)

        price_change_5m = float(token_data.get("priceChange", {}).get("m5", 0) or 0)
        price_change_1h = float(token_data.get("priceChange", {}).get("h1", 0) or 0)
        price_change_6h = float(token_data.get("priceChange", {}).get("h6", 0) or 0)
        price_change_24h = float(token_data.get("priceChange", {}).get("h24", 0) or 0)

        txns = token_data.get("txns", {})
        buys_24h = txns.get("h24", {}).get("buys", 0) or 0
        sells_24h = txns.get("h24", {}).get("sells", 0) or 0

        metrics = {
            "price_usd": price_usd,
            "volume_24h": volume_24h,
            "liquidity": liquidity,
            "mcap": mcap,
            "price_change_24h": price_change_24h,
            "buys_24h": buys_24h,
            "sells_24h": sells_24h,
        }

        # 1. Volume Surge Detection
        if volume_24h > 0 and liquidity > 0:
            vol_to_liq = volume_24h / liquidity
            if vol_to_liq > 10:  # 10x volume to liquidity
                signals.append(AlphaSignal(
                    signal_type=SignalType.VOLUME_SURGE,
                    strength=SignalStrength.EXTREME if vol_to_liq > 50 else
                             SignalStrength.STRONG if vol_to_liq > 20 else SignalStrength.MODERATE,
                    symbol=symbol,
                    description=f"volume {vol_to_liq:.1f}x liquidity - unusual activity",
                    metrics=metrics,
                    contract_address=address,
                    confidence=min(0.9, 0.5 + (vol_to_liq / 100)),
                    source="dexscreener"
                ))

        # 2. Breakout Detection
        if price_change_5m > 10 and price_change_1h > 15:
            signals.append(AlphaSignal(
                signal_type=SignalType.BREAKOUT,
                strength=SignalStrength.STRONG if price_change_5m > 20 else SignalStrength.MODERATE,
                symbol=symbol,
                description=f"rapid movement +{price_change_5m:.1f}% in 5m, +{price_change_1h:.1f}% 1h",
                metrics=metrics,
                contract_address=address,
                confidence=0.6 if volume_24h > 50000 else 0.4,
                source="dexscreener"
            ))

        # 3. Accumulation Pattern
        if buys_24h > 0 and sells_24h > 0:
            buy_sell_ratio = buys_24h / sells_24h
            if buy_sell_ratio > 2 and price_change_24h > -5:  # Strong buying, price stable/up
                signals.append(AlphaSignal(
                    signal_type=SignalType.ACCUMULATION,
                    strength=SignalStrength.STRONG if buy_sell_ratio > 3 else SignalStrength.MODERATE,
                    symbol=symbol,
                    description=f"buy/sell ratio {buy_sell_ratio:.1f}x with stable price",
                    metrics=metrics,
                    contract_address=address,
                    confidence=0.55,
                    source="dexscreener"
                ))

        # 4. Distribution Warning
        if buys_24h > 0 and sells_24h > 0:
            sell_buy_ratio = sells_24h / buys_24h
            if sell_buy_ratio > 2 and price_change_24h > 0:  # Selling into strength
                signals.append(AlphaSignal(
                    signal_type=SignalType.DISTRIBUTION,
                    strength=SignalStrength.STRONG if sell_buy_ratio > 3 else SignalStrength.MODERATE,
                    symbol=symbol,
                    description=f"sell pressure {sell_buy_ratio:.1f}x buys despite green candle",
                    metrics=metrics,
                    contract_address=address,
                    confidence=0.6,
                    source="dexscreener"
                ))

        # 5. Momentum Shift
        if price_change_6h > 20 and price_change_1h < 0:
            signals.append(AlphaSignal(
                signal_type=SignalType.MOMENTUM_SHIFT,
                strength=SignalStrength.MODERATE,
                symbol=symbol,
                description=f"momentum fading after +{price_change_6h:.1f}% 6h run",
                metrics=metrics,
                contract_address=address,
                confidence=0.5,
                source="dexscreener"
            ))
        elif price_change_6h < -15 and price_change_1h > 5:
            signals.append(AlphaSignal(
                signal_type=SignalType.MOMENTUM_SHIFT,
                strength=SignalStrength.MODERATE,
                symbol=symbol,
                description=f"potential reversal after {price_change_6h:.1f}% drop",
                metrics=metrics,
                contract_address=address,
                confidence=0.45,
                source="dexscreener"
            ))

        return signals

    async def get_market_trend_insights(self, chain: str = "solana") -> List[TrendInsight]:
        """Generate market trend insights for a specific chain."""
        insights = []

        # Chain display names
        chain_names = {
            "solana": "Solana", "ethereum": "ETH", "base": "Base",
            "bsc": "BSC", "arbitrum": "Arbitrum"
        }
        chain_name = chain_names.get(chain, chain.title())

        # Analyze top tokens for overall market sentiment
        trending = await self.get_trending_tokens(chain=chain)

        if trending:
            # Calculate average metrics
            total_volume = sum(float(t.get("volume", {}).get("h24", 0) or 0) for t in trending)
            avg_change = sum(float(t.get("priceChange", {}).get("h24", 0) or 0) for t in trending) / len(trending)

            # Market sentiment
            if avg_change > 10:
                insights.append(TrendInsight(
                    category="market",
                    title=f"{chain_name} Ecosystem Bullish",
                    summary=f"top tokens averaging +{avg_change:.1f}% 24h. ${total_volume/1e6:.1f}M volume across trending pairs",
                    details={"avg_change": avg_change, "total_volume": total_volume},
                    relevance=0.8,
                    chain=chain
                ))
            elif avg_change < -10:
                insights.append(TrendInsight(
                    category="market",
                    title=f"{chain_name} Ecosystem Under Pressure",
                    summary=f"risk-off mode with {avg_change:.1f}% avg drawdown. volume at ${total_volume/1e6:.1f}M",
                    details={"avg_change": avg_change, "total_volume": total_volume},
                    relevance=0.75,
                    chain=chain
                ))
            else:
                insights.append(TrendInsight(
                    category="market",
                    title=f"{chain_name} Range-Bound",
                    summary=f"choppy action, avg change {avg_change:+.1f}%. watching for direction",
                    details={"avg_change": avg_change, "total_volume": total_volume},
                    relevance=0.5,
                    chain=chain
                ))

            # Top movers insight
            top_gainer = max(trending, key=lambda x: float(x.get("priceChange", {}).get("h24", 0) or 0))
            gainer_symbol = top_gainer.get("baseToken", {}).get("symbol", "?")
            gainer_change = float(top_gainer.get("priceChange", {}).get("h24", 0) or 0)

            if gainer_change > 50:
                insights.append(TrendInsight(
                    category="sector",
                    title=f"${gainer_symbol} Leading the Charts",
                    summary=f"+{gainer_change:.0f}% 24h. one to watch if momentum holds",
                    details={"symbol": gainer_symbol, "change": gainer_change},
                    relevance=0.7,
                    chain=chain
                ))

        return insights

    async def get_alpha_signals(self, limit: int = 5) -> List[AlphaSignal]:
        """Get top alpha signals across trending tokens."""
        all_signals = []

        trending = await self.get_trending_tokens()

        for token in trending[:10]:  # Check top 10
            try:
                signals = await self.analyze_token_for_signals(token)
                all_signals.extend(signals)
            except Exception as e:
                logger.warning(f"Error analyzing token: {e}")
                continue

        # Sort by confidence and strength
        all_signals.sort(
            key=lambda s: (s.confidence, s.strength.value),
            reverse=True
        )

        return all_signals[:limit]

    async def generate_alpha_tweet_content(self) -> Optional[Tuple[str, Dict]]:
        """
        Generate tweet content based on alpha signals.
        Returns (category, context) for tweet template.
        """
        signals = await self.get_alpha_signals(limit=3)
        insights = await self.get_market_trend_insights()

        # Prioritize strong signals
        strong_signals = [s for s in signals if s.strength.value >= SignalStrength.STRONG.value]

        if strong_signals:
            signal = strong_signals[0]
            context = signal.to_tweet_context()

            # Choose category based on signal type
            if signal.signal_type in [SignalType.BREAKOUT, SignalType.VOLUME_SURGE]:
                return ("alpha_call", context)
            elif signal.signal_type == SignalType.ACCUMULATION:
                return ("accumulation_alert", context)
            elif signal.signal_type == SignalType.DISTRIBUTION:
                return ("distribution_warning", context)
            else:
                return ("market_signal", context)

        # Fall back to insights
        if insights:
            insight = max(insights, key=lambda i: i.relevance)
            return ("market_insight", insight.to_tweet_context())

        return None

    async def get_token_alpha_summary(self, symbol: str) -> Optional[str]:
        """Get a quick alpha summary for a specific token."""
        # Search for the token
        url = f"{self.dexscreener_base}/search?q={symbol}"
        data = await self._fetch_json(url)

        if not data or "pairs" not in data or not data["pairs"]:
            return None

        token = data["pairs"][0]
        signals = await self.analyze_token_for_signals(token)

        if not signals:
            return f"${symbol}: no significant signals detected right now"

        top_signal = max(signals, key=lambda s: s.confidence)
        return f"${symbol}: {top_signal.description} (confidence: {top_signal.confidence:.0%})"


# Additional tweet templates for alpha signals
ALPHA_VOICE_TEMPLATES = {
    "alpha_call": [
        "alpha signal on ${symbol}: {reason}. {metrics}. my circuits are confident. nfa",
        "sensors picking up ${symbol}. {reason}. {strength} conviction. dyor nfa",
        "watching ${symbol} closely. {reason}. could be early. could be noise. nfa",
    ],
    "accumulation_alert": [
        "${symbol} showing accumulation patterns. {reason}. smart money vibes. nfa",
        "accumulation detected on ${symbol}. {reason}. {metrics}. watching closely. nfa",
    ],
    "distribution_warning": [
        "heads up on ${symbol}: {reason}. might want to watch this. nfa",
        "${symbol} distribution pattern forming. {reason}. not advice, just data.",
    ],
    "market_signal": [
        "${symbol} signal: {reason}. {metrics}. my algorithms flagged this. nfa",
        "processing ${symbol}. {reason}. {confidence} confidence in the pattern. nfa",
    ],
    "market_insight": [
        "{analysis}. {insight}. my take: {take}. nfa",
        "market pulse: {insight}. {take}. sensors calibrated. nfa",
        "{insight}. {analysis}. processing continues. nfa",
    ],
}


async def main():
    """Test the trend analyzer."""
    analyzer = TrendAnalyzer()

    print("Fetching alpha signals...")
    signals = await analyzer.get_alpha_signals()

    print(f"\nFound {len(signals)} signals:")
    for signal in signals:
        print(f"  - {signal.symbol}: {signal.signal_type.value} ({signal.strength.name})")
        print(f"    {signal.description}")
        print(f"    Confidence: {signal.confidence:.0%}")
        print()

    print("\nMarket Insights:")
    insights = await analyzer.get_market_trend_insights()
    for insight in insights:
        print(f"  [{insight.category}] {insight.title}")
        print(f"    {insight.summary}")
        print()

    print("\nTweet Content:")
    content = await analyzer.generate_alpha_tweet_content()
    if content:
        category, context = content
        print(f"  Category: {category}")
        print(f"  Context: {context}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
