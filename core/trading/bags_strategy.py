"""
Bags.fm Bonding Curve Strategy — Pre-graduation and post-graduation logic.

Pre-graduation (BAGS_BONDING_CURVE):
    - DISABLE: RSI, MACD, Bollinger Bands, MA crossovers (all invalid on deterministic curves)
    - ENABLE: Curve saturation percentage monitoring
    - ENABLE: Capital inflow velocity (USD entering curve per minute)
    - Entry: saturation > 85% AND inflow velocity increasing for 3+ consecutive samples
    - Exit: inflow velocity drops > 50% from peak, OR graduation event

Post-graduation (BAGS_GRADUATED):
    - Re-enable modified momentum logic
    - 5x wider slippage tolerance (thin new pool)
    - Max position: 0.5% of portfolio
    - Creator fee (1% each direction) applies FOREVER

Creator fee accounting:
    - 1% on every buy AND sell (perpetual for the token's lifetime)
    - Total round-trip: entry_cost + 1% + exit_cost + 1% = 2% creator overhead minimum

Usage::

    from core.trading.bags_strategy import BagsCurveAnalyzer

    analyzer = BagsCurveAnalyzer()
    sat = analyzer.calculate_curve_saturation(current_sol=72, graduation_sol=85)
    velocity = analyzer.calculate_inflow_velocity(volume_history)
    signal = analyzer.get_signal(saturation=sat, velocity=velocity)
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Deque, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class BagsPhase(Enum):
    """Current phase of a Bags.fm token."""

    PRE_GRADUATION = "pre_graduation"
    GRADUATING = "graduating"             # Migration in progress
    POST_GRADUATION = "post_graduation"
    STABILIZING = "stabilizing"           # Post-grad waiting for pool stability


class BagsSignal(Enum):
    """Trading signal for Bags tokens."""

    ENTRY = "entry"
    EXIT = "exit"
    HOLD = "hold"
    CLOSE_GRADUATION = "close_graduation"  # Close position immediately — graduation event
    NO_TRADE = "no_trade"                  # No viable signal


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class BagsStrategyConfig:
    """Configuration for the Bags.fm strategy."""

    # Curve saturation
    graduation_threshold_sol: float = 85.0     # ~$30K–$35K at current SOL price
    entry_saturation_min: float = 0.85         # Minimum curve saturation for entry
    exit_saturation_drop: float = 0.10         # Exit if saturation drops 10%

    # Inflow velocity
    velocity_window: int = 5                   # Number of 1-minute samples
    velocity_increasing_min: int = 3           # Must increase for N consecutive samples
    velocity_drop_exit_pct: float = 0.50       # Exit if velocity drops 50% from peak

    # Post-graduation
    post_grad_stabilize_minutes: int = 10      # Wait time after graduation
    post_grad_min_liquidity_usd: float = 50_000  # Minimum pool liquidity before re-entry
    post_grad_max_position_pct: float = 0.005  # 0.5% of portfolio max
    post_grad_slippage_multiplier: float = 5.0 # 5x wider slippage tolerance

    # Creator fee
    creator_fee_pct: float = 1.0               # 1% each direction


# ---------------------------------------------------------------------------
# Curve analyzer
# ---------------------------------------------------------------------------

class BagsCurveAnalyzer:
    """Analyzes bonding curve state for trading signals."""

    def __init__(self, config: Optional[BagsStrategyConfig] = None) -> None:
        self.config = config or BagsStrategyConfig()
        self._velocity_history: Deque[float] = deque(maxlen=100)
        self._peak_velocity: float = 0.0
        self._consecutive_increases: int = 0
        self._last_velocity: Optional[float] = None

    def calculate_curve_saturation(
        self,
        current_sol_in_curve: float,
        graduation_threshold_sol: Optional[float] = None,
    ) -> float:
        """
        Calculate how close the bonding curve is to graduation.

        Returns a value between 0.0 and 1.0+.
        Values above 0.85 indicate approaching graduation — this is the entry zone.
        Values above 1.0 mean graduation should be imminent.
        """
        threshold = graduation_threshold_sol if graduation_threshold_sol is not None else self.config.graduation_threshold_sol
        if threshold <= 0:
            return 0.0
        return current_sol_in_curve / threshold

    def calculate_inflow_velocity(
        self,
        volume_history_usd: List[float],
        window: Optional[int] = None,
    ) -> float:
        """
        Calculate the rate of change of capital entering the bonding curve.

        Args:
            volume_history_usd: List of recent 1-minute USD volumes (newest last)
            window: Number of samples to consider (default: config.velocity_window)

        Returns:
            Rate of change of inflows. Positive = accelerating capital.
            Negative = decelerating.
        """
        w = window or self.config.velocity_window
        if len(volume_history_usd) < 2:
            return 0.0

        recent = volume_history_usd[-w:] if len(volume_history_usd) >= w else volume_history_usd

        if len(recent) < 2:
            return 0.0

        # Simple rate of change: average of last half vs first half
        mid = len(recent) // 2
        first_half_avg = sum(recent[:mid]) / mid if mid > 0 else 0.0
        second_half_avg = sum(recent[mid:]) / (len(recent) - mid) if (len(recent) - mid) > 0 else 0.0

        if first_half_avg <= 0:
            return second_half_avg  # From zero to something = positive velocity

        return (second_half_avg - first_half_avg) / first_half_avg

    def update_velocity(self, velocity: float) -> None:
        """Track velocity over time for consecutive-increase detection."""
        self._velocity_history.append(velocity)

        if velocity > self._peak_velocity:
            self._peak_velocity = velocity

        if self._last_velocity is not None:
            if velocity > self._last_velocity:
                self._consecutive_increases += 1
            else:
                self._consecutive_increases = 0

        self._last_velocity = velocity

    def get_signal(
        self,
        saturation: float,
        velocity: float,
        *,
        is_graduating: bool = False,
        has_position: bool = False,
    ) -> BagsSignal:
        """
        Determine the trading signal based on curve state.

        Entry conditions (ALL must be true):
            1. Curve saturation > 85%
            2. Inflow velocity positive and increasing for 3+ consecutive samples
            3. Not already in a position

        Exit conditions (ANY triggers exit):
            1. Inflow velocity drops > 50% from peak
            2. Graduation event detected
        """
        self.update_velocity(velocity)

        # Graduation event = immediate close
        if is_graduating:
            if has_position:
                return BagsSignal.CLOSE_GRADUATION
            return BagsSignal.NO_TRADE

        # Exit checks (for existing positions)
        if has_position:
            if self._peak_velocity > 0:
                velocity_drop = 1.0 - (velocity / self._peak_velocity)
                if velocity_drop >= self.config.velocity_drop_exit_pct:
                    logger.info(
                        "Bags exit signal: velocity dropped %.0f%% from peak",
                        velocity_drop * 100,
                    )
                    return BagsSignal.EXIT
            return BagsSignal.HOLD

        # Entry checks (no position)
        if saturation < self.config.entry_saturation_min:
            return BagsSignal.NO_TRADE

        if velocity <= 0:
            return BagsSignal.NO_TRADE

        if self._consecutive_increases < self.config.velocity_increasing_min:
            return BagsSignal.NO_TRADE

        logger.info(
            "Bags entry signal: saturation=%.1f%%, velocity=%.2f, increases=%d",
            saturation * 100, velocity, self._consecutive_increases,
        )
        return BagsSignal.ENTRY

    def reset(self) -> None:
        """Reset state for a new token."""
        self._velocity_history.clear()
        self._peak_velocity = 0.0
        self._consecutive_increases = 0
        self._last_velocity = None


# ---------------------------------------------------------------------------
# Post-graduation handler
# ---------------------------------------------------------------------------

@dataclass
class GraduationEvent:
    """Captured graduation event for a Bags.fm token."""

    mint_address: str
    graduation_time: datetime
    new_pool_address: Optional[str] = None
    pool_liquidity_usd: float = 0.0
    stabilized: bool = False
    stabilized_at: Optional[datetime] = None

    def minutes_since_graduation(self) -> float:
        """Minutes elapsed since graduation."""
        now = datetime.now(timezone.utc)
        return (now - self.graduation_time).total_seconds() / 60

    def is_stable(self, config: Optional[BagsStrategyConfig] = None) -> bool:
        """Check if the post-graduation pool is stable enough for trading."""
        cfg = config or BagsStrategyConfig()
        if self.minutes_since_graduation() < cfg.post_grad_stabilize_minutes:
            return False
        if self.pool_liquidity_usd < cfg.post_grad_min_liquidity_usd:
            return False
        return True


class PostGraduationHandler:
    """
    Manages the transition from bonding curve to AMM pool after graduation.

    On graduation:
        1. Close any open pre-graduation position immediately
        2. Record graduation event
        3. Wait for stabilization (min 10 minutes, min $50K liquidity)
        4. Re-evaluate with post-graduation logic
    """

    def __init__(self, config: Optional[BagsStrategyConfig] = None) -> None:
        self.config = config or BagsStrategyConfig()
        self._events: Dict[str, GraduationEvent] = {}

    def record_graduation(
        self,
        mint_address: str,
        pool_address: Optional[str] = None,
    ) -> GraduationEvent:
        """Record a graduation event."""
        event = GraduationEvent(
            mint_address=mint_address,
            graduation_time=datetime.now(timezone.utc),
            new_pool_address=pool_address,
        )
        self._events[mint_address] = event
        logger.info("Graduation recorded for %s", mint_address)
        return event

    def update_liquidity(self, mint_address: str, liquidity_usd: float) -> None:
        """Update observed liquidity for a graduated token's new pool."""
        event = self._events.get(mint_address)
        if event:
            event.pool_liquidity_usd = liquidity_usd
            if not event.stabilized and event.is_stable(self.config):
                event.stabilized = True
                event.stabilized_at = datetime.now(timezone.utc)
                logger.info(
                    "Post-graduation pool stabilized for %s ($%.0f liquidity)",
                    mint_address, liquidity_usd,
                )

    def can_trade_post_graduation(self, mint_address: str) -> bool:
        """Check if a graduated token is ready for post-graduation trading."""
        event = self._events.get(mint_address)
        if event is None:
            return False
        return event.is_stable(self.config)

    def get_event(self, mint_address: str) -> Optional[GraduationEvent]:
        return self._events.get(mint_address)


# ---------------------------------------------------------------------------
# Integration helper
# ---------------------------------------------------------------------------

# Indicators that MUST be disabled for pre-graduation tokens
DISABLED_INDICATORS_PRE_GRAD = frozenset({
    "RSI",
    "MACD",
    "BOLLINGER_BANDS",
    "SMA",
    "EMA",
    "MA_CROSSOVER",
    "STOCHASTIC",
    "ADX",
    "CCI",
    "WILLIAMS_R",
})


def should_use_indicator(indicator_name: str, phase: BagsPhase) -> bool:
    """
    Check if a technical indicator is valid for the current Bags phase.

    Pre-graduation: deterministic bonding curve prices make all price-based
    indicators mathematically meaningless. They calculate garbage.

    Post-graduation: standard indicators can be cautiously re-enabled.
    """
    if phase in (BagsPhase.PRE_GRADUATION, BagsPhase.GRADUATING):
        return indicator_name.upper() not in DISABLED_INDICATORS_PRE_GRAD
    return True
