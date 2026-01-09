"""
Comprehensive Signal Service.

Integrates with core Jarvis signal aggregator for:
- Grok/X sentiment analysis
- DexTools hot pairs
- GMGN security & smart money
- DexScreener price data
- Multi-source trending

This service wraps core functionality for Telegram bot use.
"""

import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add Jarvis root to path for core imports
jarvis_root = Path(__file__).parent.parent.parent
if str(jarvis_root) not in sys.path:
    sys.path.insert(0, str(jarvis_root))

from tg_bot.config import get_config
from tg_bot.services.cost_tracker import get_tracker

logger = logging.getLogger(__name__)


@dataclass
class TokenSignal:
    """Comprehensive token signal with all data sources."""

    # Basic info
    address: str
    symbol: str
    name: str = ""
    chain: str = "solana"

    # Price data
    price_usd: float = 0.0
    price_change_5m: float = 0.0
    price_change_1h: float = 0.0
    price_change_24h: float = 0.0

    # Volume/Liquidity
    volume_24h: float = 0.0
    volume_1h: float = 0.0
    liquidity_usd: float = 0.0

    # Momentum
    momentum_score: float = 0.0
    dextools_hot_level: int = 0
    lute_call_count: int = 0

    # Security (GMGN)
    security_score: float = 0.0
    risk_level: str = "unknown"
    security_warnings: List[str] = field(default_factory=list)
    is_honeypot: bool = False
    lp_locked: bool = False

    # Smart money (GMGN)
    smart_money_signal: str = "neutral"
    insider_buys: int = 0
    insider_sells: int = 0

    # Sentiment (Grok)
    sentiment: str = "neutral"
    sentiment_score: float = 0.0
    sentiment_confidence: float = 0.0
    sentiment_summary: str = ""
    sentiment_topics: List[str] = field(default_factory=list)

    # Aggregated signal
    signal: str = "NEUTRAL"
    signal_score: float = 0.0
    signal_reasons: List[str] = field(default_factory=list)

    # Metadata
    sources_used: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "address": self.address,
            "symbol": self.symbol,
            "name": self.name,
            "price_usd": self.price_usd,
            "price_change_1h": self.price_change_1h,
            "price_change_24h": self.price_change_24h,
            "volume_24h": self.volume_24h,
            "liquidity_usd": self.liquidity_usd,
            "security_score": self.security_score,
            "risk_level": self.risk_level,
            "sentiment": self.sentiment,
            "sentiment_score": self.sentiment_score,
            "signal": self.signal,
            "signal_score": self.signal_score,
            "signal_reasons": self.signal_reasons,
            "sources_used": self.sources_used,
        }


class SignalService:
    """
    Comprehensive signal service using core Jarvis modules.

    Provides:
    - Full token analysis with all data sources
    - Trending token discovery
    - Security scanning
    - Grok sentiment analysis
    """

    def __init__(self):
        self.config = get_config()
        self.tracker = get_tracker()
        self._core_available = self._check_core_modules()

    def _check_core_modules(self) -> Dict[str, bool]:
        """Check which core modules are available."""
        modules = {}

        try:
            from core import dexscreener
            modules["dexscreener"] = True
        except ImportError:
            modules["dexscreener"] = False

        try:
            from core import birdeye
            modules["birdeye"] = True
        except ImportError:
            modules["birdeye"] = False

        try:
            from core import dextools
            modules["dextools"] = True
        except ImportError:
            modules["dextools"] = False

        try:
            from core import gmgn_metrics
            modules["gmgn"] = True
        except ImportError:
            modules["gmgn"] = False

        try:
            from core import x_sentiment
            modules["grok"] = True
        except ImportError:
            modules["grok"] = False

        try:
            from core import signal_aggregator
            modules["signal_aggregator"] = True
        except ImportError:
            modules["signal_aggregator"] = False

        return modules

    def get_available_sources(self) -> List[str]:
        """Get list of available data sources."""
        return [k for k, v in self._core_available.items() if v]

    async def get_comprehensive_signal(
        self,
        token_address: str,
        symbol: str = "",
        include_sentiment: bool = True,
    ) -> TokenSignal:
        """
        Get comprehensive signal for a token using all available sources.

        Args:
            token_address: Solana token address
            symbol: Token symbol (optional)
            include_sentiment: Whether to include Grok sentiment

        Returns:
            TokenSignal with all available data
        """
        signal = TokenSignal(address=token_address, symbol=symbol or token_address[:8])

        # 1. Try core signal aggregator first (has everything)
        if self._core_available.get("signal_aggregator"):
            try:
                from core.signal_aggregator import get_comprehensive_signal as core_signal

                result = core_signal(
                    token_address,
                    include_sentiment=include_sentiment and self.config.has_grok(),
                )

                if result.success and result.data:
                    core_data = result.data
                    signal.symbol = core_data.symbol or signal.symbol
                    signal.name = core_data.name
                    signal.price_usd = core_data.price_usd
                    signal.price_change_5m = core_data.price_change_5m
                    signal.price_change_1h = core_data.price_change_1h
                    signal.price_change_24h = core_data.price_change_24h
                    signal.volume_24h = core_data.volume_24h
                    signal.volume_1h = core_data.volume_1h
                    signal.liquidity_usd = core_data.liquidity_usd
                    signal.momentum_score = core_data.momentum_score
                    signal.dextools_hot_level = core_data.dextools_hot_level
                    signal.lute_call_count = core_data.lute_call_count
                    signal.security_score = core_data.security_score
                    signal.risk_level = core_data.risk_level
                    signal.security_warnings = core_data.security_warnings
                    signal.smart_money_signal = core_data.smart_money_signal
                    signal.sentiment = core_data.sentiment
                    signal.sentiment_confidence = core_data.sentiment_confidence
                    signal.sentiment_topics = core_data.sentiment_topics
                    signal.signal = core_data.signal
                    signal.signal_score = core_data.signal_score
                    signal.signal_reasons = core_data.signal_reasons
                    signal.sources_used = core_data.sources_used

                    # Track API calls
                    for source in result.sources_tried:
                        self.tracker.record_call(source, "token_data")

                    if include_sentiment and "grok" in signal.sources_used:
                        self.tracker.record_call("grok", "sentiment", tokens_used=500)

                    return signal

            except Exception as e:
                logger.warning(f"Core signal aggregator failed: {e}")

        # 2. Fallback: Build signal from individual sources
        await self._fetch_price_data(signal, token_address)
        await self._fetch_security_data(signal, token_address)

        if include_sentiment and self.config.has_grok():
            await self._fetch_sentiment(signal)

        # Calculate final signal
        self._calculate_signal(signal)

        return signal

    async def _fetch_price_data(self, signal: TokenSignal, address: str):
        """Fetch price data from DexScreener."""
        if not self._core_available.get("dexscreener"):
            return

        try:
            from core import dexscreener

            result = dexscreener.get_pairs_by_token(address)
            self.tracker.record_call("dexscreener", "pairs")

            if result.success and result.data:
                pairs = result.data.get("pairs", [])
                if pairs:
                    pair = pairs[0]
                    base = pair.get("baseToken", {})
                    signal.symbol = base.get("symbol", signal.symbol)
                    signal.name = base.get("name", "")
                    signal.price_usd = float(pair.get("priceUsd", 0) or 0)
                    signal.price_change_5m = float(pair.get("priceChange", {}).get("m5", 0) or 0)
                    signal.price_change_1h = float(pair.get("priceChange", {}).get("h1", 0) or 0)
                    signal.price_change_24h = float(pair.get("priceChange", {}).get("h24", 0) or 0)
                    signal.volume_24h = float(pair.get("volume", {}).get("h24", 0) or 0)
                    signal.volume_1h = float(pair.get("volume", {}).get("h1", 0) or 0)
                    signal.liquidity_usd = float(pair.get("liquidity", {}).get("usd", 0) or 0)
                    signal.sources_used.append("dexscreener")

        except Exception as e:
            logger.debug(f"DexScreener failed: {e}")

    async def _fetch_security_data(self, signal: TokenSignal, address: str):
        """Fetch security data from GMGN."""
        if not self._core_available.get("gmgn"):
            return

        try:
            from core import gmgn_metrics

            result = gmgn_metrics.analyze_token_security(address, chain="sol")
            self.tracker.record_call("gmgn", "security")

            if result.success and result.data:
                sec = result.data
                signal.security_score = sec.security_score
                signal.risk_level = sec.risk_level
                signal.security_warnings = sec.warnings[:5]
                signal.is_honeypot = sec.is_honeypot
                signal.lp_locked = getattr(sec, "lp_locked", False)
                signal.sources_used.append("gmgn")

            # Smart money
            sm_result = gmgn_metrics.get_smart_money_activity(address)
            self.tracker.record_call("gmgn", "smart_money")

            if sm_result.success and sm_result.data:
                sm = sm_result.data
                signal.smart_money_signal = sm.smart_money_signal
                signal.insider_buys = sm.insider_buys
                signal.insider_sells = sm.insider_sells

        except Exception as e:
            logger.debug(f"GMGN failed: {e}")

    async def _fetch_sentiment(self, signal: TokenSignal):
        """Fetch sentiment from Grok."""
        if not self._core_available.get("grok"):
            return

        # Check rate limit
        can_check, reason = self.tracker.can_make_sentiment_call()
        if not can_check:
            logger.info(f"Sentiment rate limited: {reason}")
            return

        try:
            from core import x_sentiment

            text = f"${signal.symbol} Solana token trading sentiment"
            result = x_sentiment.analyze_sentiment(text, focus="trading")

            self.tracker.record_call("grok", "sentiment", tokens_used=500)

            if result:
                signal.sentiment = result.sentiment
                signal.sentiment_confidence = result.confidence
                signal.sentiment_summary = getattr(result, "summary", "")
                signal.sentiment_topics = result.key_topics[:5]
                signal.sentiment_score = _sentiment_to_score(result.sentiment, result.confidence)
                signal.sources_used.append("grok")

        except Exception as e:
            logger.warning(f"Grok sentiment failed: {e}")

    def _calculate_signal(self, signal: TokenSignal):
        """Calculate aggregated signal score."""
        score = 0.0
        reasons = []

        # Price momentum (25%)
        if signal.price_change_5m > 5:
            score += 10
            reasons.append(f"Strong 5m: +{signal.price_change_5m:.1f}%")
        elif signal.price_change_5m < -5:
            score -= 10
            reasons.append(f"Weak 5m: {signal.price_change_5m:.1f}%")

        if signal.price_change_1h > 10:
            score += 10
            reasons.append(f"Strong 1h: +{signal.price_change_1h:.1f}%")
        elif signal.price_change_1h < -10:
            score -= 10

        # Volume (15%)
        if signal.volume_1h > 100_000:
            score += 10
            reasons.append(f"High volume: ${signal.volume_1h/1000:.0f}K/1h")
        elif signal.volume_1h > 50_000:
            score += 5

        # Liquidity (10%)
        if signal.liquidity_usd > 100_000:
            score += 5
        elif signal.liquidity_usd < 10_000:
            score -= 15
            reasons.append(f"LOW LIQUIDITY: ${signal.liquidity_usd:.0f}")

        # Security (25%)
        if signal.is_honeypot:
            score -= 100
            reasons.append("HONEYPOT DETECTED")
        elif signal.risk_level == "critical":
            score -= 50
            reasons.append("CRITICAL RISK")
        elif signal.risk_level == "high":
            score -= 25
            reasons.append("High risk")
        elif signal.risk_level == "low":
            score += 15
            reasons.append("Safe token")

        if signal.security_warnings:
            score -= len(signal.security_warnings) * 3

        # Smart money (15%)
        if signal.smart_money_signal == "bullish":
            score += 15
            reasons.append("Smart money BULLISH")
        elif signal.smart_money_signal == "bearish":
            score -= 15
            reasons.append("Smart money bearish")

        # Sentiment (15%)
        if signal.sentiment == "positive" and signal.sentiment_confidence > 0.7:
            score += 15
            reasons.append(f"Grok: POSITIVE ({signal.sentiment_confidence:.0%})")
        elif signal.sentiment == "positive":
            score += 8
        elif signal.sentiment == "negative" and signal.sentiment_confidence > 0.7:
            score -= 15
            reasons.append(f"Grok: NEGATIVE ({signal.sentiment_confidence:.0%})")
        elif signal.sentiment == "negative":
            score -= 8

        # Momentum bonuses
        if signal.dextools_hot_level > 0:
            score += min(10, signal.dextools_hot_level * 2)
            reasons.append(f"DexTools HOT: {signal.dextools_hot_level}")

        if signal.lute_call_count >= 3:
            score += 10
            reasons.append(f"Lute: {signal.lute_call_count} calls")

        # Clamp and set
        score = max(-100, min(100, score))
        signal.signal_score = score
        signal.signal_reasons = reasons

        # Determine signal
        if signal.is_honeypot or signal.risk_level == "critical":
            signal.signal = "AVOID"
        elif score >= 40:
            signal.signal = "STRONG_BUY"
        elif score >= 20:
            signal.signal = "BUY"
        elif score <= -40:
            signal.signal = "STRONG_SELL"
        elif score <= -20:
            signal.signal = "SELL"
        else:
            signal.signal = "NEUTRAL"

    async def get_trending_tokens(self, limit: int = 10) -> List[TokenSignal]:
        """
        Get trending tokens with signals.

        Returns top tokens from multiple sources, ranked by signal score.
        Uses DexScreener boosted tokens endpoint for real trending data.
        """
        signals = []

        # Try DexScreener boosted tokens with full data (most reliable for trending)
        try:
            from core import dexscreener

            # First try get_boosted_tokens_with_data for full enriched data
            pairs = dexscreener.get_boosted_tokens_with_data(
                chain="solana",
                limit=limit * 2,  # Get extra to filter
                cache_ttl_seconds=120,
            )

            self.tracker.record_call("dexscreener", "boosted_tokens")

            if pairs:
                for pair in pairs:
                    # Skip if missing key data
                    if not pair.base_token_address or not pair.base_token_symbol:
                        continue

                    sig = TokenSignal(
                        address=pair.base_token_address,
                        symbol=pair.base_token_symbol,
                        name=pair.base_token_name,
                        price_usd=pair.price_usd,
                        price_change_5m=pair.price_change_5m,
                        price_change_1h=pair.price_change_1h,
                        price_change_24h=pair.price_change_24h,
                        volume_24h=pair.volume_24h,
                        volume_1h=pair.volume_1h,
                        liquidity_usd=pair.liquidity_usd,
                    )
                    sig.sources_used.append("dexscreener")
                    self._calculate_signal(sig)
                    signals.append(sig)

                    if len(signals) >= limit:
                        break

                if signals:
                    # Sort by signal score descending
                    signals.sort(key=lambda s: s.signal_score, reverse=True)
                    return signals[:limit]

        except Exception as e:
            logger.warning(f"DexScreener boosted tokens failed: {e}")

        # Try momentum tokens as second option
        try:
            from core import dexscreener

            pairs = dexscreener.get_momentum_tokens(
                min_liquidity=5_000,
                min_volume_24h=25_000,
                limit=limit * 2,
            )

            self.tracker.record_call("dexscreener", "momentum")

            if pairs:
                for pair in pairs:
                    if not pair.base_token_address:
                        continue

                    sig = TokenSignal(
                        address=pair.base_token_address,
                        symbol=pair.base_token_symbol,
                        name=pair.base_token_name,
                        price_usd=pair.price_usd,
                        price_change_5m=pair.price_change_5m,
                        price_change_1h=pair.price_change_1h,
                        price_change_24h=pair.price_change_24h,
                        volume_24h=pair.volume_24h,
                        volume_1h=pair.volume_1h,
                        liquidity_usd=pair.liquidity_usd,
                    )
                    sig.sources_used.append("dexscreener")
                    self._calculate_signal(sig)
                    signals.append(sig)

                    if len(signals) >= limit:
                        break

                if signals:
                    signals.sort(key=lambda s: s.signal_score, reverse=True)
                    return signals[:limit]

        except Exception as e:
            logger.warning(f"DexScreener momentum failed: {e}")

        # Fallback: fetch known popular tokens individually
        known_tokens = [
            ("So11111111111111111111111111111111111111112", "SOL", "Wrapped SOL"),
            ("DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "BONK", "Bonk"),
            ("EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm", "WIF", "dogwifhat"),
            ("JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN", "JUP", "Jupiter"),
            ("HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3", "PYTH", "Pyth Network"),
            ("7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr", "POPCAT", "Popcat"),
            ("MEW1gQWJ3nEXg2qgERiKu7FAFj79PHvQVREQUzScPP5", "MEW", "cat in a dogs world"),
            ("4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R", "RAY", "Raydium"),
        ]

        for addr, symbol, name in known_tokens[:limit]:
            sig = TokenSignal(address=addr, symbol=symbol, name=name)
            await self._fetch_price_data(sig, addr)
            self._calculate_signal(sig)
            if sig.price_usd > 0:  # Only add if we got data
                signals.append(sig)

        signals.sort(key=lambda s: s.signal_score, reverse=True)
        return signals[:limit]


def _sentiment_to_score(sentiment: str, confidence: float) -> float:
    """Convert sentiment string to numeric score."""
    base = {
        "positive": 1.0,
        "negative": -1.0,
        "neutral": 0.0,
        "mixed": 0.0,
    }.get(sentiment.lower(), 0.0)

    return base * confidence


# Singleton
_service: Optional[SignalService] = None


def get_signal_service() -> SignalService:
    """Get singleton signal service."""
    global _service
    if _service is None:
        _service = SignalService()
    return _service
