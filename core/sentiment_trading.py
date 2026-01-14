"""
Sentiment Trading Pipeline - Multi-source signal aggregation and evaluation.

Integrates:
- Social signals from trusted handles (@xinsanityo, etc.)
- News events from CryptoPanic
- Social sentiment from LunarCrush
- Alpha signals from on-chain detection
- Automated signal processing pipeline
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
SIGNALS_DIR = ROOT / "data" / "trader" / "sentiment_signals"
CONFIG_PATH = ROOT / "data" / "trader" / "sentiment_config.json"
PIPELINE_STATE_PATH = ROOT / "data" / "trader" / "pipeline_state.json"


class SignalSource(Enum):
    """Sources of trading signals."""
    SOCIAL = "social"  # Twitter/X accounts
    NEWS = "news"  # CryptoPanic, news feeds
    ONCHAIN = "onchain"  # Alpha detector, whale moves
    SENTIMENT = "sentiment"  # LunarCrush social sentiment
    MANUAL = "manual"  # Manual entry


@dataclass
class SentimentTradeConfig:
    """Configuration for sentiment-based trading."""
    
    # Risk parameters - LOOSER for vetted social signals
    capital_usd: float = 10.0
    risk_per_trade: float = 0.10  # 10% per trade (higher for conviction)
    max_position_pct: float = 0.50  # 50% max position
    stop_loss_pct: float = 0.15  # 15% stop loss (wider for volatile memes)
    take_profit_pct: float = 0.50  # 50% take profit (memes can run)
    trailing_stop_pct: float = 0.20  # 20% trailing stop after profit
    
    # Safety filters - LOOSER for vetted accounts
    min_liquidity_usd: float = 10000.0  # Lower threshold (was 50k)
    min_volume_24h_usd: float = 5000.0  # Lower threshold (was 50k)
    require_locked_lp: bool = False  # Don't require locked LP
    min_locked_pct: float = 0.0  # No minimum
    require_revoked_authorities: bool = False  # Don't require
    max_transfer_fee_bps: float = 100.0  # Allow up to 1% fee
    
    # Execution
    fee_bps: float = 50.0  # Higher fees for meme tokens
    slippage_bps: float = 100.0  # 1% slippage (memes are volatile)
    max_slippage_bps: float = 500.0  # 5% absolute max
    
    # Signal source
    trusted_handles: List[str] = None
    
    def __post_init__(self):
        if self.trusted_handles is None:
            self.trusted_handles = ["xinsanityo"]


@dataclass
class SentimentSignal:
    """A trading signal from social sentiment."""

    handle: str
    token_symbol: str
    token_address: Optional[str]
    signal_type: str  # "bullish", "bearish", "watch"
    conviction: str  # "high", "medium", "low"
    source_url: Optional[str]
    timestamp: float
    notes: str = ""
    source: SignalSource = SignalSource.SOCIAL
    confidence: float = 50.0  # 0-100
    social_score: float = 0.0  # LunarCrush score
    news_sentiment: str = ""  # Aggregated news sentiment
    corroborating_signals: int = 0  # Number of confirming signals

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["source"] = self.source.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SentimentSignal":
        """Create signal from dict, handling enum conversion."""
        if "source" in data and isinstance(data["source"], str):
            data["source"] = SignalSource(data["source"])
        return cls(**data)


def get_default_config() -> SentimentTradeConfig:
    """Get default sentiment trading config."""
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text())
            return SentimentTradeConfig(**data)
        except (json.JSONDecodeError, TypeError):
            pass
    return SentimentTradeConfig()


def save_config(config: SentimentTradeConfig) -> None:
    """Save sentiment trading config."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(asdict(config), indent=2))


def log_signal(signal: SentimentSignal) -> None:
    """Log a sentiment signal for tracking."""
    SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Append to daily log
    date_str = time.strftime("%Y-%m-%d")
    log_path = SIGNALS_DIR / f"signals_{date_str}.jsonl"
    
    with open(log_path, "a") as f:
        f.write(json.dumps(signal.to_dict()) + "\n")


def load_recent_signals(days: int = 7) -> List[SentimentSignal]:
    """Load recent sentiment signals."""
    SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
    signals = []

    cutoff = time.time() - (days * 86400)

    for path in sorted(SIGNALS_DIR.glob("signals_*.jsonl")):
        try:
            with open(path) as f:
                for line in f:
                    data = json.loads(line.strip())
                    if data.get("timestamp", 0) >= cutoff:
                        # Handle old format without source field
                        if "source" not in data:
                            data["source"] = SignalSource.SOCIAL
                        signals.append(SentimentSignal.from_dict(data))
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            logger.debug(f"Error loading signal: {e}")
            continue

    return sorted(signals, key=lambda s: s.timestamp, reverse=True)


def evaluate_signal_for_trade(
    signal: SentimentSignal,
    config: Optional[SentimentTradeConfig] = None,
) -> Dict[str, Any]:
    """
    Evaluate if a signal should trigger a trade.
    
    Returns assessment with:
        - should_trade: bool
        - position_size_pct: float
        - stop_loss: float
        - take_profit: float
        - warnings: list
    """
    if config is None:
        config = get_default_config()
    
    warnings = []
    should_trade = False
    position_size = 0.0
    
    # Check if handle is trusted
    if signal.handle not in config.trusted_handles:
        warnings.append(f"Handle @{signal.handle} not in trusted list")
        return {
            "should_trade": False,
            "position_size_pct": 0,
            "warnings": warnings,
        }
    
    # Only trade bullish signals
    if signal.signal_type != "bullish":
        warnings.append(f"Signal type '{signal.signal_type}' not tradeable")
        return {
            "should_trade": False,
            "position_size_pct": 0,
            "warnings": warnings,
        }
    
    # Position sizing based on conviction
    conviction_multipliers = {
        "high": 1.0,
        "medium": 0.6,
        "low": 0.3,
    }
    multiplier = conviction_multipliers.get(signal.conviction, 0.3)
    position_size = config.max_position_pct * multiplier
    
    # Determine if we should trade
    if signal.token_address:
        should_trade = True
    else:
        warnings.append("No token address - need to look up manually")
        should_trade = False
    
    # Add warning if no address
    if not signal.token_address:
        warnings.append("Token address missing - search required")
    
    return {
        "should_trade": should_trade,
        "position_size_pct": position_size,
        "stop_loss_pct": config.stop_loss_pct,
        "take_profit_pct": config.take_profit_pct,
        "trailing_stop_pct": config.trailing_stop_pct,
        "max_slippage_bps": config.max_slippage_bps,
        "warnings": warnings,
        "config": asdict(config),
    }


def format_trade_plan(
    signal: SentimentSignal,
    evaluation: Dict[str, Any],
    current_price: Optional[float] = None,
) -> str:
    """Format a trade plan for display."""
    lines = [
        "=" * 50,
        "SENTIMENT TRADE PLAN",
        "=" * 50,
        f"Source: @{signal.handle}",
        f"Token: {signal.token_symbol}",
        f"Address: {signal.token_address or 'UNKNOWN'}",
        f"Signal: {signal.signal_type.upper()}",
        f"Conviction: {signal.conviction.upper()}",
        "",
    ]
    
    if evaluation["should_trade"]:
        lines.extend([
            "TRADE PARAMETERS:",
            f"  Position Size: {evaluation['position_size_pct']*100:.1f}% of capital",
            f"  Stop Loss: {evaluation['stop_loss_pct']*100:.1f}%",
            f"  Take Profit: {evaluation['take_profit_pct']*100:.1f}%",
            f"  Trailing Stop: {evaluation['trailing_stop_pct']*100:.1f}%",
            f"  Max Slippage: {evaluation['max_slippage_bps']/100:.1f}%",
        ])
        
        if current_price:
            config = evaluation.get("config", {})
            capital = config.get("capital_usd", 10.0)
            position_usd = capital * evaluation["position_size_pct"]
            lines.extend([
                "",
                "EXECUTION:",
                f"  Entry: ~${current_price:.6f}",
                f"  Position: ${position_usd:.2f}",
                f"  Stop: ~${current_price * (1 - evaluation['stop_loss_pct']):.6f}",
                f"  Target: ~${current_price * (1 + evaluation['take_profit_pct']):.6f}",
            ])
    else:
        lines.append("DO NOT TRADE - See warnings below")
    
    if evaluation["warnings"]:
        lines.extend(["", "WARNINGS:"])
        for w in evaluation["warnings"]:
            lines.append(f"  - {w}")
    
    lines.append("=" * 50)
    return "\n".join(lines)


class SentimentPipeline:
    """
    Automated sentiment trading pipeline.

    Aggregates signals from:
    - Social accounts (Twitter/X)
    - News feeds (CryptoPanic)
    - Social sentiment (LunarCrush)
    - On-chain alpha (AlphaDetector)

    Evaluates signals with multi-source confirmation.
    """

    def __init__(self, config: Optional[SentimentTradeConfig] = None):
        self.config = config or get_default_config()
        self._news_detector = None
        self._alpha_detector = None
        self._lunarcrush = None
        self._cryptopanic = None
        self._telegram = None
        self.pending_signals: List[SentimentSignal] = []
        self.last_scan = None

    def _get_news_detector(self):
        """Lazy load news detector."""
        if self._news_detector is None:
            try:
                from core.autonomy.news_detector import get_news_detector
                self._news_detector = get_news_detector()
            except Exception as e:
                logger.debug(f"News detector not available: {e}")
        return self._news_detector

    def _get_alpha_detector(self):
        """Lazy load alpha detector."""
        if self._alpha_detector is None:
            try:
                from core.autonomy.alpha_detector import get_alpha_detector
                self._alpha_detector = get_alpha_detector()
            except Exception as e:
                logger.debug(f"Alpha detector not available: {e}")
        return self._alpha_detector

    def _get_lunarcrush(self):
        """Lazy load LunarCrush API."""
        if self._lunarcrush is None:
            try:
                from core.data.lunarcrush_api import get_lunarcrush
                self._lunarcrush = get_lunarcrush()
            except Exception as e:
                logger.debug(f"LunarCrush not available: {e}")
        return self._lunarcrush

    def _get_cryptopanic(self):
        """Lazy load CryptoPanic API."""
        if self._cryptopanic is None:
            try:
                from core.data.cryptopanic_api import get_cryptopanic
                self._cryptopanic = get_cryptopanic()
            except Exception as e:
                logger.debug(f"CryptoPanic not available: {e}")
        return self._cryptopanic

    def _get_telegram(self):
        """Lazy load Telegram notifier."""
        if self._telegram is None:
            try:
                from tg_bot.services.notifier import get_notifier
                self._telegram = get_notifier()
            except Exception:
                pass
        return self._telegram

    async def scan_all_sources(self) -> List[SentimentSignal]:
        """Scan all sources for trading signals."""
        signals = []

        # Scan news for token mentions
        news_signals = await self._scan_news_signals()
        signals.extend(news_signals)

        # Scan alpha detector
        alpha_signals = await self._scan_alpha_signals()
        signals.extend(alpha_signals)

        # Scan social sentiment for spikes
        sentiment_signals = await self._scan_sentiment_spikes()
        signals.extend(sentiment_signals)

        # Enrich signals with cross-source confirmation
        enriched = await self._enrich_signals(signals)

        self.pending_signals = enriched
        self.last_scan = time.time()

        logger.info(f"Pipeline scan found {len(enriched)} signals")
        return enriched

    async def _scan_news_signals(self) -> List[SentimentSignal]:
        """Convert news events to trading signals."""
        signals = []
        news_detector = self._get_news_detector()

        if not news_detector:
            return signals

        try:
            await news_detector.scan_news()

            for event in news_detector.get_high_priority_events():
                for token in event.tokens:
                    signal = SentimentSignal(
                        handle="news_detector",
                        token_symbol=token,
                        token_address=None,
                        signal_type=event.sentiment if event.sentiment != "neutral" else "watch",
                        conviction="high" if event.priority.value >= 2 else "medium",
                        source_url=event.url,
                        timestamp=time.time(),
                        notes=event.title[:200],
                        source=SignalSource.NEWS,
                        confidence=event.confidence,
                        news_sentiment=event.sentiment,
                    )
                    signals.append(signal)

        except Exception as e:
            logger.error(f"News signal scan error: {e}")

        return signals

    async def _scan_alpha_signals(self) -> List[SentimentSignal]:
        """Convert alpha detections to trading signals."""
        signals = []
        alpha_detector = self._get_alpha_detector()

        if not alpha_detector:
            return signals

        try:
            alpha_signals = await alpha_detector.scan_for_alpha()

            for alpha in alpha_signals:
                if alpha.strength >= 60:
                    signal = SentimentSignal(
                        handle="alpha_detector",
                        token_symbol=alpha.token,
                        token_address=alpha.data.get("address"),
                        signal_type="bullish" if alpha.strength > 70 else "watch",
                        conviction="high" if alpha.strength > 80 else "medium",
                        source_url=None,
                        timestamp=time.time(),
                        notes=alpha.description,
                        source=SignalSource.ONCHAIN,
                        confidence=alpha.strength,
                    )
                    signals.append(signal)

        except Exception as e:
            logger.error(f"Alpha signal scan error: {e}")

        return signals

    async def _scan_sentiment_spikes(self) -> List[SentimentSignal]:
        """Detect social sentiment spikes via LunarCrush."""
        signals = []
        lunarcrush = self._get_lunarcrush()

        if not lunarcrush:
            return signals

        try:
            trending = await lunarcrush.get_trending_coins(20)

            for coin in trending:
                galaxy_score = coin.get("galaxy_score", 0)
                sentiment = coin.get("sentiment", 50)

                # High galaxy score with strong sentiment = signal
                if galaxy_score > 85 or (galaxy_score > 70 and abs(sentiment - 50) > 20):
                    signal_type = "bullish" if sentiment > 60 else "bearish" if sentiment < 40 else "watch"

                    signal = SentimentSignal(
                        handle="lunarcrush",
                        token_symbol=coin.get("symbol", ""),
                        token_address=None,
                        signal_type=signal_type,
                        conviction="high" if galaxy_score > 90 else "medium",
                        source_url=None,
                        timestamp=time.time(),
                        notes=f"Galaxy: {galaxy_score}, Sentiment: {sentiment}",
                        source=SignalSource.SENTIMENT,
                        confidence=min(100, galaxy_score),
                        social_score=galaxy_score,
                    )
                    signals.append(signal)

        except Exception as e:
            logger.error(f"Sentiment spike scan error: {e}")

        return signals

    async def _enrich_signals(self, signals: List[SentimentSignal]) -> List[SentimentSignal]:
        """Enrich signals with cross-source confirmation."""
        # Group signals by token
        by_token: Dict[str, List[SentimentSignal]] = {}
        for signal in signals:
            token = signal.token_symbol.upper()
            if token not in by_token:
                by_token[token] = []
            by_token[token].append(signal)

        enriched = []
        for token, token_signals in by_token.items():
            # Find corroborating signals from different sources
            sources = set(s.source for s in token_signals)
            corroborating = len(sources)

            # Get LunarCrush data for the token
            lunarcrush = self._get_lunarcrush()
            social_score = 0.0
            if lunarcrush:
                try:
                    coin_data = await lunarcrush.get_coin_sentiment(token)
                    if coin_data:
                        social_score = coin_data.get("galaxy_score", 0)
                except Exception:
                    pass

            # Get news sentiment
            cryptopanic = self._get_cryptopanic()
            news_sentiment = ""
            if cryptopanic:
                try:
                    news = await cryptopanic.get_news(currencies=token, limit=5)
                    if news:
                        bullish = sum(1 for n in news if n.get("sentiment") == "bullish")
                        bearish = sum(1 for n in news if n.get("sentiment") == "bearish")
                        if bullish > bearish:
                            news_sentiment = "bullish"
                        elif bearish > bullish:
                            news_sentiment = "bearish"
                        else:
                            news_sentiment = "mixed"
                except Exception:
                    pass

            # Update each signal with enriched data
            for signal in token_signals:
                signal.corroborating_signals = corroborating
                if social_score and not signal.social_score:
                    signal.social_score = social_score
                if news_sentiment and not signal.news_sentiment:
                    signal.news_sentiment = news_sentiment

                # Boost confidence for multi-source confirmation
                if corroborating > 1:
                    signal.confidence = min(100, signal.confidence + (corroborating - 1) * 10)

                enriched.append(signal)

        return enriched

    async def evaluate_and_alert(self) -> List[Dict[str, Any]]:
        """Evaluate pending signals and send alerts for tradeable ones."""
        alerts = []

        for signal in self.pending_signals:
            evaluation = evaluate_signal_for_trade(signal, self.config)

            if evaluation["should_trade"] or (signal.confidence >= 80 and signal.corroborating_signals > 1):
                alert = {
                    "signal": signal.to_dict(),
                    "evaluation": evaluation,
                    "action": "TRADE" if evaluation["should_trade"] else "WATCH",
                }
                alerts.append(alert)

                # Log the signal
                log_signal(signal)

                # Send Telegram alert
                await self._send_alert(signal, evaluation)

        return alerts

    async def _send_alert(self, signal: SentimentSignal, evaluation: Dict[str, Any]):
        """Send alert to Telegram."""
        telegram = self._get_telegram()
        if not telegram:
            return

        try:
            action = "🚀 TRADE SIGNAL" if evaluation["should_trade"] else "👀 WATCH"
            sentiment_emoji = "🟢" if signal.signal_type == "bullish" else "🔴" if signal.signal_type == "bearish" else "⚪"

            msg = (
                f"{action}\n\n"
                f"Token: ${signal.token_symbol}\n"
                f"Signal: {sentiment_emoji} {signal.signal_type.upper()}\n"
                f"Conviction: {signal.conviction.upper()}\n"
                f"Confidence: {signal.confidence:.0f}%\n"
                f"Source: {signal.source.value}\n"
            )

            if signal.corroborating_signals > 1:
                msg += f"Corroborating sources: {signal.corroborating_signals}\n"

            if signal.social_score:
                msg += f"Social Score: {signal.social_score:.0f}\n"

            if signal.news_sentiment:
                msg += f"News: {signal.news_sentiment}\n"

            if evaluation["should_trade"]:
                msg += (
                    f"\nTrade Plan:\n"
                    f"Position: {evaluation['position_size_pct']*100:.0f}%\n"
                    f"Stop: {evaluation['stop_loss_pct']*100:.0f}%\n"
                    f"Target: {evaluation['take_profit_pct']*100:.0f}%\n"
                )

            if signal.notes:
                msg += f"\n{signal.notes[:100]}"

            await telegram.send_message(msg)

        except Exception as e:
            logger.error(f"Alert send error: {e}")

    def get_summary(self) -> Dict[str, Any]:
        """Get pipeline summary."""
        if not self.pending_signals:
            return {"status": "no_signals", "last_scan": self.last_scan}

        by_source = {}
        by_type = {}
        tokens = set()

        for signal in self.pending_signals:
            source = signal.source.value
            by_source[source] = by_source.get(source, 0) + 1
            by_type[signal.signal_type] = by_type.get(signal.signal_type, 0) + 1
            tokens.add(signal.token_symbol)

        tradeable = [s for s in self.pending_signals if s.confidence >= 70 and s.signal_type == "bullish"]

        return {
            "total_signals": len(self.pending_signals),
            "by_source": by_source,
            "by_type": by_type,
            "unique_tokens": len(tokens),
            "tradeable_count": len(tradeable),
            "top_tokens": list(tokens)[:10],
            "last_scan": self.last_scan,
        }


# Singleton pipeline
_pipeline: Optional[SentimentPipeline] = None


def get_sentiment_pipeline() -> SentimentPipeline:
    """Get singleton sentiment pipeline."""
    global _pipeline
    if _pipeline is None:
        _pipeline = SentimentPipeline()
    return _pipeline


# Initialize default config
if not CONFIG_PATH.exists():
    save_config(SentimentTradeConfig())


if __name__ == "__main__":
    # Example usage
    config = get_default_config()
    print("Sentiment Trading Config:")
    print(json.dumps(asdict(config), indent=2))
    
    # Example signal
    signal = SentimentSignal(
        handle="xinsanityo",
        token_symbol="HORSE",
        token_address=None,  # Would need to look up
        signal_type="bullish",
        conviction="medium",
        source_url="https://x.com/xinsanityo/status/123",
        timestamp=time.time(),
        notes="Horse meta for 2026",
    )
    
    evaluation = evaluate_signal_for_trade(signal, config)
    print("\n" + format_trade_plan(signal, evaluation))
