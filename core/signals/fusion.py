"""
Signal Fusion System

Combines multiple signal sources into unified trading signals.
Uses weighted averaging with dynamic weight adjustment based on
historical accuracy.

Prompts #128-135: Signal Processing
"""

import asyncio
import logging
import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Callable
from enum import Enum
from pathlib import Path
from collections import defaultdict

logger = logging.getLogger(__name__)


class SignalDirection(str, Enum):
    """Signal direction"""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    NEUTRAL = "neutral"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


class SignalSource(str, Enum):
    """Sources of trading signals"""
    TECHNICAL = "technical"           # RSI, MACD, etc.
    SENTIMENT = "sentiment"           # Social media sentiment
    WHALE = "whale"                   # Whale activity
    ON_CHAIN = "on_chain"            # On-chain metrics
    ML_MODEL = "ml_model"            # Machine learning predictions
    VOLUME = "volume"                 # Volume analysis
    ORDERBOOK = "orderbook"          # Order book analysis
    NEWS = "news"                     # News sentiment
    CORRELATION = "correlation"       # Correlation with BTC/ETH
    CUSTOM = "custom"                 # Custom indicators


@dataclass
class SignalWeight:
    """Weight configuration for a signal source"""
    source: SignalSource
    base_weight: float = 1.0
    current_weight: float = 1.0
    accuracy_30d: float = 0.5         # Historical accuracy
    signals_count: int = 0            # Number of signals generated
    profitable_signals: int = 0       # Number that were profitable
    last_updated: datetime = field(default_factory=datetime.now)

    def update_accuracy(self, was_profitable: bool):
        """Update accuracy based on signal outcome"""
        self.signals_count += 1
        if was_profitable:
            self.profitable_signals += 1

        if self.signals_count > 0:
            self.accuracy_30d = self.profitable_signals / self.signals_count

        # Adjust weight based on accuracy
        # High accuracy = higher weight, low accuracy = lower weight
        accuracy_multiplier = 0.5 + self.accuracy_30d  # 0.5 to 1.5x
        self.current_weight = self.base_weight * accuracy_multiplier
        self.last_updated = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "source": self.source.value,
            "base_weight": self.base_weight,
            "current_weight": self.current_weight,
            "accuracy_30d": self.accuracy_30d,
            "signals_count": self.signals_count,
            "profitable_signals": self.profitable_signals,
            "last_updated": self.last_updated.isoformat()
        }


@dataclass
class RawSignal:
    """A raw signal from a single source"""
    source: SignalSource
    token: str
    direction: SignalDirection
    strength: float  # 0-1
    confidence: float  # 0-1
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    expires_at: Optional[datetime] = None

    def is_expired(self) -> bool:
        """Check if signal has expired"""
        if self.expires_at:
            return datetime.now() > self.expires_at
        # Default 1 hour expiry
        return datetime.now() > self.timestamp + timedelta(hours=1)

    def to_numeric(self) -> float:
        """Convert direction to numeric value (-1 to 1)"""
        direction_values = {
            SignalDirection.STRONG_BUY: 1.0,
            SignalDirection.BUY: 0.5,
            SignalDirection.NEUTRAL: 0.0,
            SignalDirection.SELL: -0.5,
            SignalDirection.STRONG_SELL: -1.0
        }
        return direction_values.get(self.direction, 0.0) * self.strength


@dataclass
class FusedSignal:
    """A fused signal combining multiple sources"""
    signal_id: str
    token: str
    direction: SignalDirection
    strength: float  # 0-1
    confidence: float  # 0-1
    timestamp: datetime = field(default_factory=datetime.now)

    # Source breakdown
    source_signals: Dict[str, float] = field(default_factory=dict)  # source -> contribution
    source_count: int = 0
    agreement_score: float = 0.0  # How much sources agree (0-1)

    # Interpretation
    interpretation: str = ""
    risk_level: str = "medium"  # low, medium, high
    suggested_action: str = ""

    # Tracking
    valid_until: datetime = field(default_factory=lambda: datetime.now() + timedelta(hours=2))
    outcome: Optional[str] = None  # "profitable", "loss", "neutral" after resolution

    def __post_init__(self):
        if not self.signal_id:
            data = f"{self.token}{self.timestamp.isoformat()}"
            self.signal_id = f"FSIG-{hashlib.sha256(data.encode()).hexdigest()[:12].upper()}"

    def is_valid(self) -> bool:
        """Check if signal is still valid"""
        return datetime.now() < self.valid_until

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "signal_id": self.signal_id,
            "token": self.token,
            "direction": self.direction.value,
            "strength": self.strength,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
            "source_signals": self.source_signals,
            "source_count": self.source_count,
            "agreement_score": self.agreement_score,
            "interpretation": self.interpretation,
            "risk_level": self.risk_level,
            "suggested_action": self.suggested_action,
            "valid_until": self.valid_until.isoformat(),
            "outcome": self.outcome
        }


class SignalFusion:
    """
    Fuses multiple signal sources into unified trading signals

    Uses weighted averaging with dynamic weight adjustment based on
    historical accuracy of each source.
    """

    def __init__(
        self,
        storage_path: str = "data/signals/fusion.json",
        min_sources_for_signal: int = 2,
        min_confidence: float = 0.6
    ):
        self.storage_path = Path(storage_path)
        self.min_sources = min_sources_for_signal
        self.min_confidence = min_confidence

        # Signal sources and their weights
        self.weights: Dict[SignalSource, SignalWeight] = {}
        self._init_default_weights()

        # Pending signals by token
        self.pending_signals: Dict[str, Dict[SignalSource, RawSignal]] = defaultdict(dict)

        # Generated fused signals
        self.fused_signals: Dict[str, FusedSignal] = {}

        # Signal providers (functions that generate signals)
        self.providers: Dict[SignalSource, Callable] = {}

        self._load()

    def _init_default_weights(self):
        """Initialize default weights for all sources"""
        default_weights = {
            SignalSource.TECHNICAL: 1.2,
            SignalSource.SENTIMENT: 0.8,
            SignalSource.WHALE: 1.5,
            SignalSource.ON_CHAIN: 1.3,
            SignalSource.ML_MODEL: 1.0,
            SignalSource.VOLUME: 1.0,
            SignalSource.ORDERBOOK: 1.1,
            SignalSource.NEWS: 0.7,
            SignalSource.CORRELATION: 0.6,
            SignalSource.CUSTOM: 1.0
        }

        for source, base_weight in default_weights.items():
            self.weights[source] = SignalWeight(
                source=source,
                base_weight=base_weight,
                current_weight=base_weight
            )

    def _load(self):
        """Load signal data from storage"""
        if not self.storage_path.exists():
            return

        try:
            with open(self.storage_path) as f:
                data = json.load(f)

            # Load weights
            for weight_data in data.get("weights", []):
                source = SignalSource(weight_data["source"])
                self.weights[source] = SignalWeight(
                    source=source,
                    base_weight=weight_data.get("base_weight", 1.0),
                    current_weight=weight_data.get("current_weight", 1.0),
                    accuracy_30d=weight_data.get("accuracy_30d", 0.5),
                    signals_count=weight_data.get("signals_count", 0),
                    profitable_signals=weight_data.get("profitable_signals", 0)
                )

            logger.info(f"Loaded signal fusion weights")

        except Exception as e:
            logger.error(f"Failed to load signal fusion data: {e}")

    def _save(self):
        """Save signal data to storage"""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "weights": [w.to_dict() for w in self.weights.values()],
                "updated_at": datetime.now().isoformat()
            }

            with open(self.storage_path, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save signal fusion data: {e}")

    def register_provider(self, source: SignalSource, provider: Callable):
        """Register a signal provider function"""
        self.providers[source] = provider
        logger.info(f"Registered signal provider for {source.value}")

    async def add_signal(self, signal: RawSignal):
        """Add a raw signal from a source"""
        if signal.is_expired():
            logger.debug(f"Ignoring expired signal from {signal.source.value}")
            return

        # Store signal
        self.pending_signals[signal.token][signal.source] = signal
        logger.debug(f"Added {signal.source.value} signal for {signal.token}: {signal.direction.value}")

        # Check if we have enough signals to fuse
        await self._check_fusion(signal.token)

    async def _check_fusion(self, token: str):
        """Check if we have enough signals to create a fused signal"""
        pending = self.pending_signals.get(token, {})

        # Filter out expired signals
        active_signals = {
            source: sig for source, sig in pending.items()
            if not sig.is_expired()
        }

        if len(active_signals) < self.min_sources:
            return

        # Create fused signal
        fused = await self._fuse_signals(token, active_signals)

        if fused and fused.confidence >= self.min_confidence:
            self.fused_signals[fused.signal_id] = fused
            logger.info(f"Generated fused signal {fused.signal_id} for {token}: {fused.direction.value}")

            # Clear pending signals for this token
            self.pending_signals[token] = {}

    async def _fuse_signals(
        self,
        token: str,
        signals: Dict[SignalSource, RawSignal]
    ) -> Optional[FusedSignal]:
        """Fuse multiple signals into one"""
        if not signals:
            return None

        # Calculate weighted average
        weighted_sum = 0.0
        total_weight = 0.0
        source_contributions = {}
        confidences = []

        for source, signal in signals.items():
            weight = self.weights.get(source, SignalWeight(source=source))
            numeric_value = signal.to_numeric()

            contribution = numeric_value * weight.current_weight * signal.confidence
            weighted_sum += contribution
            total_weight += weight.current_weight

            source_contributions[source.value] = contribution
            confidences.append(signal.confidence)

        if total_weight == 0:
            return None

        # Calculate final values
        final_value = weighted_sum / total_weight
        avg_confidence = sum(confidences) / len(confidences)

        # Determine direction
        if final_value >= 0.7:
            direction = SignalDirection.STRONG_BUY
            strength = min(abs(final_value), 1.0)
        elif final_value >= 0.3:
            direction = SignalDirection.BUY
            strength = min(abs(final_value) * 1.5, 1.0)
        elif final_value <= -0.7:
            direction = SignalDirection.STRONG_SELL
            strength = min(abs(final_value), 1.0)
        elif final_value <= -0.3:
            direction = SignalDirection.SELL
            strength = min(abs(final_value) * 1.5, 1.0)
        else:
            direction = SignalDirection.NEUTRAL
            strength = 0.3

        # Calculate agreement score
        directions = [sig.direction for sig in signals.values()]
        unique_directions = set(directions)
        if len(unique_directions) == 1:
            agreement = 1.0
        elif len(unique_directions) == 2:
            agreement = 0.7
        else:
            agreement = 0.4

        # Adjust confidence based on agreement
        final_confidence = avg_confidence * (0.7 + 0.3 * agreement)

        # Generate interpretation
        interpretation = self._generate_interpretation(
            token, direction, strength, signals, source_contributions
        )

        # Determine risk level
        if strength >= 0.8 and final_confidence >= 0.8:
            risk_level = "low"
        elif strength >= 0.5 and final_confidence >= 0.6:
            risk_level = "medium"
        else:
            risk_level = "high"

        return FusedSignal(
            signal_id="",
            token=token,
            direction=direction,
            strength=strength,
            confidence=final_confidence,
            source_signals=source_contributions,
            source_count=len(signals),
            agreement_score=agreement,
            interpretation=interpretation,
            risk_level=risk_level,
            suggested_action=self._get_suggested_action(direction, strength)
        )

    def _generate_interpretation(
        self,
        token: str,
        direction: SignalDirection,
        strength: float,
        signals: Dict[SignalSource, RawSignal],
        contributions: Dict[str, float]
    ) -> str:
        """Generate human-readable interpretation"""
        # Find strongest contributors
        sorted_contrib = sorted(
            contributions.items(),
            key=lambda x: abs(x[1]),
            reverse=True
        )

        top_sources = [src for src, _ in sorted_contrib[:3]]

        direction_text = {
            SignalDirection.STRONG_BUY: "strongly bullish",
            SignalDirection.BUY: "bullish",
            SignalDirection.NEUTRAL: "neutral",
            SignalDirection.SELL: "bearish",
            SignalDirection.STRONG_SELL: "strongly bearish"
        }.get(direction, "neutral")

        return (
            f"Signal fusion indicates {direction_text} outlook for {token} "
            f"with {strength*100:.0f}% strength. "
            f"Primary drivers: {', '.join(top_sources)}. "
            f"Based on {len(signals)} signal sources."
        )

    def _get_suggested_action(
        self,
        direction: SignalDirection,
        strength: float
    ) -> str:
        """Get suggested trading action"""
        if direction in [SignalDirection.STRONG_BUY, SignalDirection.BUY]:
            if strength >= 0.8:
                return "Consider entering a long position with full allocation"
            elif strength >= 0.5:
                return "Consider entering a long position with partial allocation"
            else:
                return "Monitor for stronger buy signals"

        elif direction in [SignalDirection.STRONG_SELL, SignalDirection.SELL]:
            if strength >= 0.8:
                return "Consider exiting long positions or entering short"
            elif strength >= 0.5:
                return "Consider taking profits on existing positions"
            else:
                return "Monitor for stronger sell signals"

        else:
            return "No clear directional signal - consider waiting"

    async def collect_signals(self, token: str) -> Dict[SignalSource, RawSignal]:
        """Collect signals from all registered providers"""
        signals = {}

        for source, provider in self.providers.items():
            try:
                if asyncio.iscoroutinefunction(provider):
                    signal = await provider(token)
                else:
                    signal = provider(token)

                if signal:
                    signals[source] = signal
                    await self.add_signal(signal)

            except Exception as e:
                logger.error(f"Failed to collect signal from {source.value}: {e}")

        return signals

    async def get_signal(self, token: str) -> Optional[FusedSignal]:
        """Get the most recent valid fused signal for a token"""
        valid_signals = [
            sig for sig in self.fused_signals.values()
            if sig.token == token and sig.is_valid()
        ]

        if not valid_signals:
            return None

        return max(valid_signals, key=lambda s: s.timestamp)

    async def record_outcome(self, signal_id: str, was_profitable: bool):
        """Record the outcome of a signal for accuracy tracking"""
        signal = self.fused_signals.get(signal_id)
        if not signal:
            return

        signal.outcome = "profitable" if was_profitable else "loss"

        # Update source weights based on contributions
        for source_name, contribution in signal.source_signals.items():
            source = SignalSource(source_name)
            if source in self.weights:
                # A source contributed positively if its direction matched the outcome
                source_was_right = (contribution > 0) == was_profitable
                self.weights[source].update_accuracy(source_was_right)

        self._save()

    def get_weight_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all signal source weights"""
        return {
            source.value: weight.to_dict()
            for source, weight in self.weights.items()
        }

    async def get_active_signals(self) -> List[FusedSignal]:
        """Get all currently valid fused signals"""
        return [
            sig for sig in self.fused_signals.values()
            if sig.is_valid()
        ]


# Singleton instance
_signal_fusion: Optional[SignalFusion] = None


def get_signal_fusion() -> SignalFusion:
    """Get signal fusion singleton"""
    global _signal_fusion

    if _signal_fusion is None:
        _signal_fusion = SignalFusion()

    return _signal_fusion


# Testing
if __name__ == "__main__":
    async def test():
        fusion = SignalFusion()

        # Add some test signals
        await fusion.add_signal(RawSignal(
            source=SignalSource.TECHNICAL,
            token="SOL",
            direction=SignalDirection.BUY,
            strength=0.7,
            confidence=0.8
        ))

        await fusion.add_signal(RawSignal(
            source=SignalSource.WHALE,
            token="SOL",
            direction=SignalDirection.STRONG_BUY,
            strength=0.9,
            confidence=0.85
        ))

        await fusion.add_signal(RawSignal(
            source=SignalSource.SENTIMENT,
            token="SOL",
            direction=SignalDirection.BUY,
            strength=0.6,
            confidence=0.7
        ))

        # Get fused signal
        signal = await fusion.get_signal("SOL")
        if signal:
            print(f"Fused Signal: {signal.direction.value}")
            print(f"  Strength: {signal.strength:.2f}")
            print(f"  Confidence: {signal.confidence:.2f}")
            print(f"  Agreement: {signal.agreement_score:.2f}")
            print(f"  Interpretation: {signal.interpretation}")
            print(f"  Action: {signal.suggested_action}")

        # Show weights
        print("\nWeight Stats:")
        for source, stats in fusion.get_weight_stats().items():
            print(f"  {source}: weight={stats['current_weight']:.2f}, accuracy={stats['accuracy_30d']:.2f}")

    asyncio.run(test())
