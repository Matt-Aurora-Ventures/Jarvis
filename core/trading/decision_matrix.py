"""
JARVIS Decision Matrix

Centralized decision-making framework that combines multiple signals
and enforces trading rules.

Features:
- Multiple signal source integration (liquidation, MA, sentiment)
- Configurable entry/exit conditions
- Position sizing rules
- Risk checks before execution
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable
from enum import Enum

from .signals.liquidation import LiquidationSignal, SignalDirection
from .signals.dual_ma import DualMASignal
from .signals.meta_labeler import MetaLabeler, SignalFeatures, MarketRegime
from .cooldown import CooldownManager, get_cooldown_manager

logger = logging.getLogger(__name__)


class DecisionType(Enum):
    """Type of trading decision."""
    ENTER_LONG = "enter_long"
    ENTER_SHORT = "enter_short"
    EXIT = "exit"
    HOLD = "hold"
    BLOCKED = "blocked"


@dataclass
class EntryConditions:
    """
    Configurable entry conditions.
    """
    # Liquidation signal requirements
    liquidation_enabled: bool = True
    liquidation_imbalance_threshold: float = 1.5
    liquidation_min_volume: float = 500_000
    liquidation_window_minutes: int = 5

    # MA signal requirements
    ma_enabled: bool = True
    ma_fast_period: int = 13
    ma_slow_period: int = 33
    ma_trend_filter_period: int = 100  # Use 100, NOT 200

    # Trend filter
    require_trend_alignment: bool = True

    # Cooldown
    cooldown_enabled: bool = True
    cooldown_minutes: int = 30

    # Position sizing
    max_position_size_pct: float = 0.25  # 25% max
    max_notional_usd: float = 10_000_000  # $10M cap

    # Meta-labeler
    meta_labeler_enabled: bool = True
    min_probability: float = 0.6
    min_confidence: float = 0.5

    # Signal combination
    require_multiple_signals: bool = False  # Require 2+ signals to agree
    signal_weights: Dict[str, float] = field(default_factory=lambda: {
        'liquidation': 0.4,
        'ma': 0.3,
        'sentiment': 0.3,
    })


@dataclass
class ExitConditions:
    """
    Configurable exit conditions.
    """
    # Take profit / Stop loss
    take_profit_pct: float = 0.01  # 1%
    stop_loss_pct: float = 0.03   # 3%

    # Trailing stop
    trailing_stop_enabled: bool = False
    trailing_stop_distance: float = 0.02  # 2%

    # Time-based exit
    time_stop_enabled: bool = False
    time_stop_hours: int = 24

    # Signal-based exit
    exit_on_opposite_signal: bool = True
    exit_on_trend_break: bool = True


@dataclass
class TradeDecision:
    """
    Result of decision matrix evaluation.
    """
    decision: DecisionType
    direction: str  # 'long', 'short', 'neutral'
    confidence: float
    position_size_pct: float
    take_profit_pct: float
    stop_loss_pct: float
    signals_used: List[str]
    reasoning: List[str]
    blocked_reason: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def should_trade(self) -> bool:
        return self.decision in [DecisionType.ENTER_LONG, DecisionType.ENTER_SHORT]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'decision': self.decision.value,
            'direction': self.direction,
            'confidence': self.confidence,
            'position_size_pct': self.position_size_pct,
            'take_profit_pct': self.take_profit_pct,
            'stop_loss_pct': self.stop_loss_pct,
            'signals_used': self.signals_used,
            'reasoning': self.reasoning,
            'blocked_reason': self.blocked_reason,
            'should_trade': self.should_trade,
            'timestamp': self.timestamp.isoformat(),
        }


class DecisionMatrix:
    """
    Centralized decision-making engine for JARVIS trading.

    Combines multiple signal sources and enforces rules:
    1. Collect signals from all enabled sources
    2. Check entry conditions and filters
    3. Run meta-labeler for final approval
    4. Calculate position size
    5. Return actionable decision
    """

    def __init__(
        self,
        entry_conditions: Optional[EntryConditions] = None,
        exit_conditions: Optional[ExitConditions] = None,
    ):
        self.entry = entry_conditions or EntryConditions()
        self.exit = exit_conditions or ExitConditions()

        # Meta-labeler for final signal quality check
        self._meta_labeler = MetaLabeler(
            probability_threshold=self.entry.min_probability,
            min_confidence=self.entry.min_confidence,
        )

        # Cooldown manager
        self._cooldown = get_cooldown_manager()

        # Decision history
        self._decisions: List[TradeDecision] = []

        # Signal cache (for combining multiple signals)
        self._signal_cache: Dict[str, Any] = {}

        logger.info("DecisionMatrix initialized")

    def add_signal(
        self,
        source: str,
        signal: Any,
    ) -> None:
        """
        Add a signal to the cache for combined evaluation.

        Args:
            source: Signal source name ('liquidation', 'ma', 'sentiment')
            signal: The signal object
        """
        self._signal_cache[source] = {
            'signal': signal,
            'timestamp': datetime.utcnow(),
        }

    def evaluate(
        self,
        symbol: str,
        current_price: float,
        portfolio_value: float,
        has_position: bool = False,
        position_side: Optional[str] = None,
        market_regime: MarketRegime = MarketRegime.UNKNOWN,
    ) -> TradeDecision:
        """
        Evaluate all signals and conditions to make a trading decision.

        Args:
            symbol: Trading pair symbol
            current_price: Current market price
            portfolio_value: Total portfolio value in USD
            has_position: Whether we currently have a position
            position_side: Current position side if any
            market_regime: Current market regime classification

        Returns:
            TradeDecision with action and parameters
        """
        reasoning = []
        signals_used = []
        direction_votes = {'long': 0.0, 'short': 0.0}

        # 1. Check cooldown
        if self.entry.cooldown_enabled:
            can_trade, block_reason = self._cooldown.can_enter_trade(symbol)
            if not can_trade:
                return TradeDecision(
                    decision=DecisionType.BLOCKED,
                    direction='neutral',
                    confidence=0,
                    position_size_pct=0,
                    take_profit_pct=0,
                    stop_loss_pct=0,
                    signals_used=[],
                    reasoning=[block_reason],
                    blocked_reason=block_reason,
                )

        # 2. Collect and weight signals
        if self.entry.liquidation_enabled and 'liquidation' in self._signal_cache:
            liq_signal: LiquidationSignal = self._signal_cache['liquidation']['signal']
            if liq_signal.is_valid:
                weight = self.entry.signal_weights.get('liquidation', 0.4)
                if liq_signal.direction == SignalDirection.LONG:
                    direction_votes['long'] += weight * liq_signal.confidence
                elif liq_signal.direction == SignalDirection.SHORT:
                    direction_votes['short'] += weight * liq_signal.confidence
                signals_used.append('liquidation')
                reasoning.append(
                    f"Liquidation signal: {liq_signal.direction.value} "
                    f"(conf={liq_signal.confidence:.2f}, imbalance={liq_signal.imbalance_ratio:.1f}x)"
                )

        if self.entry.ma_enabled and 'ma' in self._signal_cache:
            ma_signal: DualMASignal = self._signal_cache['ma']['signal']
            if ma_signal.is_valid:
                weight = self.entry.signal_weights.get('ma', 0.3)
                if ma_signal.direction == 'long':
                    direction_votes['long'] += weight * ma_signal.confidence
                elif ma_signal.direction == 'short':
                    direction_votes['short'] += weight * ma_signal.confidence
                signals_used.append('ma')
                reasoning.append(
                    f"MA signal: {ma_signal.direction} "
                    f"(type={ma_signal.signal_type.value}, aligned={ma_signal.trend_aligned})"
                )

        if 'sentiment' in self._signal_cache:
            sent_signal = self._signal_cache['sentiment']['signal']
            weight = self.entry.signal_weights.get('sentiment', 0.3)
            if hasattr(sent_signal, 'direction') and hasattr(sent_signal, 'confidence'):
                if sent_signal.direction == 'long':
                    direction_votes['long'] += weight * sent_signal.confidence
                elif sent_signal.direction == 'short':
                    direction_votes['short'] += weight * sent_signal.confidence
                signals_used.append('sentiment')
                reasoning.append(f"Sentiment signal: {sent_signal.direction}")

        # 3. Determine direction from weighted votes
        if not signals_used:
            return TradeDecision(
                decision=DecisionType.HOLD,
                direction='neutral',
                confidence=0,
                position_size_pct=0,
                take_profit_pct=0,
                stop_loss_pct=0,
                signals_used=[],
                reasoning=["No valid signals"],
            )

        long_score = direction_votes['long']
        short_score = direction_votes['short']

        if long_score > short_score and long_score > 0.3:
            direction = 'long'
            confidence = long_score
        elif short_score > long_score and short_score > 0.3:
            direction = 'short'
            confidence = short_score
        else:
            direction = 'neutral'
            confidence = 0

        reasoning.append(f"Direction votes: long={long_score:.2f}, short={short_score:.2f}")

        # 4. Check multiple signal requirement
        if self.entry.require_multiple_signals and len(signals_used) < 2:
            return TradeDecision(
                decision=DecisionType.HOLD,
                direction='neutral',
                confidence=0,
                position_size_pct=0,
                take_profit_pct=0,
                stop_loss_pct=0,
                signals_used=signals_used,
                reasoning=reasoning + ["Requires multiple signals, only 1 present"],
            )

        # 5. Run meta-labeler
        if self.entry.meta_labeler_enabled and direction != 'neutral':
            features = SignalFeatures(
                signal_direction=direction,
                signal_strength=confidence,
                signal_source=signals_used[0] if signals_used else 'unknown',
                market_regime=market_regime,
            )

            meta_result = self._meta_labeler.classify(features)

            if not meta_result.should_trade:
                return TradeDecision(
                    decision=DecisionType.BLOCKED,
                    direction=direction,
                    confidence=confidence,
                    position_size_pct=0,
                    take_profit_pct=0,
                    stop_loss_pct=0,
                    signals_used=signals_used,
                    reasoning=reasoning + meta_result.reasoning,
                    blocked_reason="Meta-labeler rejected signal",
                )

            confidence = meta_result.probability
            reasoning.extend(meta_result.reasoning)

        # 6. Calculate position size
        position_size_pct = self._calculate_position_size(
            confidence=confidence,
            portfolio_value=portfolio_value,
        )

        # 7. Create decision
        if direction == 'long':
            decision_type = DecisionType.ENTER_LONG
        elif direction == 'short':
            decision_type = DecisionType.ENTER_SHORT
        else:
            decision_type = DecisionType.HOLD

        decision = TradeDecision(
            decision=decision_type,
            direction=direction,
            confidence=confidence,
            position_size_pct=position_size_pct,
            take_profit_pct=self.exit.take_profit_pct,
            stop_loss_pct=self.exit.stop_loss_pct,
            signals_used=signals_used,
            reasoning=reasoning,
        )

        # Store in history
        self._decisions.append(decision)
        if len(self._decisions) > 1000:
            self._decisions = self._decisions[-500:]

        # Clear signal cache
        self._signal_cache.clear()

        if decision.should_trade:
            logger.info(
                f"DECISION: {decision_type.value} {symbol} "
                f"(size={position_size_pct:.1%}, conf={confidence:.2f})"
            )

        return decision

    def _calculate_position_size(
        self,
        confidence: float,
        portfolio_value: float,
    ) -> float:
        """
        Calculate position size based on confidence and limits.
        """
        # Base size from confidence
        base_size = min(confidence * 0.3, self.entry.max_position_size_pct)

        # Check notional limit
        notional = portfolio_value * base_size
        if notional > self.entry.max_notional_usd:
            base_size = self.entry.max_notional_usd / portfolio_value

        return min(base_size, self.entry.max_position_size_pct)

    def should_exit(
        self,
        symbol: str,
        entry_price: float,
        current_price: float,
        position_side: str,
        entry_time: datetime,
    ) -> tuple[bool, str]:
        """
        Check if position should be exited.

        Returns:
            Tuple of (should_exit, reason)
        """
        pnl_pct = (current_price - entry_price) / entry_price
        if position_side == 'short':
            pnl_pct = -pnl_pct

        # Take profit check
        if pnl_pct >= self.exit.take_profit_pct:
            return True, f"Take profit hit ({pnl_pct:.2%})"

        # Stop loss check
        if pnl_pct <= -self.exit.stop_loss_pct:
            return True, f"Stop loss hit ({pnl_pct:.2%})"

        # Time stop check
        if self.exit.time_stop_enabled:
            hours_held = (datetime.utcnow() - entry_time).total_seconds() / 3600
            if hours_held >= self.exit.time_stop_hours:
                return True, f"Time stop hit ({hours_held:.1f} hours)"

        # Signal-based exit check
        if self.exit.exit_on_opposite_signal:
            # Check if we have an opposite signal
            for source, data in self._signal_cache.items():
                signal = data.get('signal')
                if hasattr(signal, 'direction'):
                    sig_dir = getattr(signal, 'direction', None)
                    if sig_dir == 'long' and position_side == 'short':
                        return True, "Opposite signal (long) received"
                    elif sig_dir == 'short' and position_side == 'long':
                        return True, "Opposite signal (short) received"

        return False, ""

    def get_stats(self) -> Dict[str, Any]:
        """Get decision matrix statistics."""
        recent_decisions = [d for d in self._decisions if d.should_trade]

        return {
            'total_decisions': len(self._decisions),
            'trade_decisions': len(recent_decisions),
            'long_decisions': sum(1 for d in recent_decisions if d.direction == 'long'),
            'short_decisions': sum(1 for d in recent_decisions if d.direction == 'short'),
            'avg_confidence': (
                sum(d.confidence for d in recent_decisions) / len(recent_decisions)
                if recent_decisions else 0
            ),
            'avg_position_size': (
                sum(d.position_size_pct for d in recent_decisions) / len(recent_decisions)
                if recent_decisions else 0
            ),
            'meta_labeler_stats': self._meta_labeler.get_stats(),
            'cooldown_stats': self._cooldown.get_stats(),
        }

    def update_config(
        self,
        entry: Optional[EntryConditions] = None,
        exit: Optional[ExitConditions] = None,
    ) -> None:
        """Update configuration."""
        if entry:
            self.entry = entry
        if exit:
            self.exit = exit
        logger.info("DecisionMatrix configuration updated")
