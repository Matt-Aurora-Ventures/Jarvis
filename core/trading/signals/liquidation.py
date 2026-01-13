"""
Liquidation-Based Trading Signals

Implements contrarian trading strategy based on liquidation data.
Key insight: Large liquidation cascades create oversold/overbought conditions
that often lead to mean reversion.

Strategy:
- Go LONG after large long liquidations (expect bounce from oversold)
- Go SHORT after large short liquidations (expect dump from overbought)
- Require 1.5x imbalance between sides
- Minimum volume threshold of $500,000
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List, Dict, Any
from collections import deque

logger = logging.getLogger(__name__)


class SignalDirection(Enum):
    """Trading signal direction."""
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"


@dataclass
class Liquidation:
    """Single liquidation event."""
    timestamp: datetime
    symbol: str
    side: str  # 'BUY' (short liquidated) or 'SELL' (long liquidated)
    quantity: float
    price: float
    value_usd: float
    exchange: str = "unknown"

    @property
    def is_long_liquidation(self) -> bool:
        """Long positions are liquidated via SELL orders."""
        return self.side.upper() == 'SELL'

    @property
    def is_short_liquidation(self) -> bool:
        """Short positions are liquidated via BUY orders."""
        return self.side.upper() == 'BUY'


@dataclass
class LiquidationSignal:
    """
    Trading signal generated from liquidation analysis.
    """
    direction: SignalDirection
    confidence: float  # 0.0 to 1.0
    long_volume: float
    short_volume: float
    imbalance_ratio: float
    total_volume: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    window_minutes: int = 5
    whale_events: int = 0  # Number of $5M+ liquidations

    @property
    def is_valid(self) -> bool:
        """Check if signal meets minimum criteria."""
        return (
            self.direction != SignalDirection.NEUTRAL and
            self.total_volume >= 500_000 and
            self.imbalance_ratio >= 1.5
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'direction': self.direction.value,
            'confidence': self.confidence,
            'long_volume': self.long_volume,
            'short_volume': self.short_volume,
            'imbalance_ratio': self.imbalance_ratio,
            'total_volume': self.total_volume,
            'timestamp': self.timestamp.isoformat(),
            'window_minutes': self.window_minutes,
            'whale_events': self.whale_events,
            'is_valid': self.is_valid,
        }


class LiquidationAnalyzer:
    """
    Analyzes liquidation data to generate trading signals.

    Configuration:
        imbalance_threshold: Minimum ratio for signal (default 1.5x)
        min_volume_usd: Minimum total volume for valid signal (default $500k)
        window_minutes: Time window for aggregation (default 5 min)
        whale_threshold: USD value for whale classification (default $5M)
    """

    def __init__(
        self,
        imbalance_threshold: float = 1.5,
        min_volume_usd: float = 500_000,
        window_minutes: int = 5,
        whale_threshold: float = 5_000_000,
        max_history_size: int = 10000,
    ):
        self.imbalance_threshold = imbalance_threshold
        self.min_volume_usd = min_volume_usd
        self.window_minutes = window_minutes
        self.whale_threshold = whale_threshold

        # Rolling window of liquidations
        self._liquidations: deque = deque(maxlen=max_history_size)

        # Signal history for analysis
        self._signal_history: List[LiquidationSignal] = []

        # Stats tracking
        self._total_long_volume = 0.0
        self._total_short_volume = 0.0
        self._whale_count = 0

        logger.info(
            f"LiquidationAnalyzer initialized: "
            f"imbalance={imbalance_threshold}x, min_vol=${min_volume_usd:,.0f}, "
            f"window={window_minutes}min"
        )

    def add_liquidation(self, liq: Liquidation) -> None:
        """Add a new liquidation event to the analyzer."""
        self._liquidations.append(liq)

        # Track whale events
        if liq.value_usd >= self.whale_threshold:
            self._whale_count += 1
            logger.warning(
                f"WHALE LIQUIDATION: ${liq.value_usd:,.0f} "
                f"{'LONG' if liq.is_long_liquidation else 'SHORT'} on {liq.symbol}"
            )

    def add_liquidations_batch(self, liquidations: List[Liquidation]) -> None:
        """Add multiple liquidation events."""
        for liq in liquidations:
            self.add_liquidation(liq)

    def get_recent_liquidations(
        self,
        symbol: Optional[str] = None,
        minutes: Optional[int] = None
    ) -> List[Liquidation]:
        """Get liquidations within the specified time window."""
        window = minutes or self.window_minutes
        cutoff = datetime.utcnow() - timedelta(minutes=window)

        result = []
        for liq in self._liquidations:
            if liq.timestamp >= cutoff:
                if symbol is None or liq.symbol.upper() == symbol.upper():
                    result.append(liq)

        return result

    def analyze(self, symbol: Optional[str] = None) -> LiquidationSignal:
        """
        Analyze recent liquidations and generate a trading signal.

        Returns:
            LiquidationSignal with direction, confidence, and metrics
        """
        recent = self.get_recent_liquidations(symbol)

        # Calculate volumes by side
        long_volume = sum(
            liq.value_usd for liq in recent if liq.is_long_liquidation
        )
        short_volume = sum(
            liq.value_usd for liq in recent if liq.is_short_liquidation
        )
        total_volume = long_volume + short_volume

        # Count whale events in window
        whale_events = sum(
            1 for liq in recent if liq.value_usd >= self.whale_threshold
        )

        # Determine direction based on imbalance
        direction = SignalDirection.NEUTRAL
        imbalance_ratio = 1.0
        confidence = 0.0

        if total_volume >= self.min_volume_usd:
            if long_volume > 0 and short_volume > 0:
                if long_volume > short_volume:
                    imbalance_ratio = long_volume / short_volume
                    if imbalance_ratio >= self.imbalance_threshold:
                        # Large long liquidations = oversold = expect bounce = GO LONG
                        direction = SignalDirection.LONG
                        confidence = min(0.9, 0.5 + (imbalance_ratio - 1.5) * 0.1)
                else:
                    imbalance_ratio = short_volume / long_volume
                    if imbalance_ratio >= self.imbalance_threshold:
                        # Large short liquidations = overbought = expect dump = GO SHORT
                        direction = SignalDirection.SHORT
                        confidence = min(0.9, 0.5 + (imbalance_ratio - 1.5) * 0.1)
            elif long_volume > self.min_volume_usd:
                # Only long liquidations
                direction = SignalDirection.LONG
                imbalance_ratio = float('inf')
                confidence = 0.8
            elif short_volume > self.min_volume_usd:
                # Only short liquidations
                direction = SignalDirection.SHORT
                imbalance_ratio = float('inf')
                confidence = 0.8

        # Boost confidence for whale events
        if whale_events > 0:
            confidence = min(0.95, confidence + 0.05 * whale_events)

        signal = LiquidationSignal(
            direction=direction,
            confidence=confidence,
            long_volume=long_volume,
            short_volume=short_volume,
            imbalance_ratio=imbalance_ratio,
            total_volume=total_volume,
            window_minutes=self.window_minutes,
            whale_events=whale_events,
        )

        # Store in history
        self._signal_history.append(signal)
        if len(self._signal_history) > 1000:
            self._signal_history = self._signal_history[-500:]

        if signal.is_valid:
            logger.info(
                f"LIQUIDATION SIGNAL: {signal.direction.value.upper()} "
                f"(confidence={signal.confidence:.2f}, "
                f"imbalance={signal.imbalance_ratio:.2f}x, "
                f"volume=${signal.total_volume:,.0f})"
            )

        return signal

    def get_signal_stats(self) -> Dict[str, Any]:
        """Get statistics about signal generation."""
        valid_signals = [s for s in self._signal_history if s.is_valid]

        return {
            'total_signals': len(self._signal_history),
            'valid_signals': len(valid_signals),
            'long_signals': sum(1 for s in valid_signals if s.direction == SignalDirection.LONG),
            'short_signals': sum(1 for s in valid_signals if s.direction == SignalDirection.SHORT),
            'avg_confidence': (
                sum(s.confidence for s in valid_signals) / len(valid_signals)
                if valid_signals else 0
            ),
            'whale_events_total': self._whale_count,
            'liquidations_tracked': len(self._liquidations),
        }

    def clear_history(self) -> None:
        """Clear all stored data."""
        self._liquidations.clear()
        self._signal_history.clear()
        self._whale_count = 0


# Convenience function for quick signal check
async def get_liquidation_signal(
    liquidations: List[Dict[str, Any]],
    symbol: str = "BTC",
    window_minutes: int = 5,
) -> LiquidationSignal:
    """
    Quick function to get a liquidation signal from raw data.

    Args:
        liquidations: List of liquidation dicts with keys:
            timestamp, symbol, side, quantity, price, value_usd
        symbol: Symbol to filter for
        window_minutes: Time window for analysis

    Returns:
        LiquidationSignal
    """
    analyzer = LiquidationAnalyzer(window_minutes=window_minutes)

    for liq_data in liquidations:
        liq = Liquidation(
            timestamp=liq_data.get('timestamp', datetime.utcnow()),
            symbol=liq_data.get('symbol', symbol),
            side=liq_data.get('side', 'SELL'),
            quantity=liq_data.get('quantity', 0),
            price=liq_data.get('price', 0),
            value_usd=liq_data.get('value_usd', 0),
            exchange=liq_data.get('exchange', 'unknown'),
        )
        analyzer.add_liquidation(liq)

    return analyzer.analyze(symbol)
