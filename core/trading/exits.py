"""
ATR-Based Trailing Stop with Volume Confirmation.

Replaces fixed percentage trailing stops with adaptive exits that:
    - Scale stop width to recent volatility (ATR)
    - Require volume confirmation before exiting (prevent flash-wick shakeouts)
    - Use time-based widening for new token entries
    - Implement progressive profit floors
    - Support tiered exits (1/3 tight, 1/3 medium, 1/3 wide)

CRITICAL RULE: Do NOT exit just because price touched the stop.
Require BOTH:
    1. Price CLOSES below the stop (not just wicks)
    2. Volume > 1.5x average (confirms real selling)

Flash wicks on Solana frequently recover within the same candle.
Exiting on wicks is one of the biggest sources of loss.

Usage::

    from core.trading.exits import (
        calculate_atr,
        calculate_atr_trailing_stop,
        should_exit,
        get_profit_floor,
        TIERED_EXIT_PLAN,
    )
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    pd = None

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    np = None


# ---------------------------------------------------------------------------
# ATR calculation
# ---------------------------------------------------------------------------

def calculate_atr(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    period: int = 7,
) -> float:
    """
    Calculate Average True Range over the given period.

    True Range = max(high - low, |high - prev_close|, |low - prev_close|)
    ATR = SMA of True Range over *period* bars.

    Short period (7) = responsive to recent volatility.
    """
    if len(highs) < 2 or len(lows) < 2 or len(closes) < 2:
        return 0.0

    n = min(len(highs), len(lows), len(closes))
    true_ranges: List[float] = []

    for i in range(1, n):
        h = highs[i]
        l = lows[i]
        prev_c = closes[i - 1]
        tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
        true_ranges.append(tr)

    if not true_ranges:
        return 0.0

    # Use last *period* true ranges
    recent = true_ranges[-period:] if len(true_ranges) >= period else true_ranges
    return sum(recent) / len(recent)


def calculate_atr_series(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    period: int = 7,
) -> List[float]:
    """Calculate a rolling ATR series (one value per bar, starting from bar *period*)."""
    n = min(len(highs), len(lows), len(closes))
    true_ranges: List[float] = [0.0]  # First bar has no TR

    for i in range(1, n):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        true_ranges.append(tr)

    atr_values: List[float] = []
    for i in range(n):
        start = max(0, i - period + 1)
        window = true_ranges[start:i + 1]
        atr_values.append(sum(window) / len(window) if window else 0.0)

    return atr_values


# ---------------------------------------------------------------------------
# Trailing stop
# ---------------------------------------------------------------------------

def calculate_atr_trailing_stop(
    closes: List[float],
    highs: List[float],
    lows: List[float],
    atr_period: int = 7,
    multiplier: float = 4.0,
    dynamic_multiplier: bool = True,
) -> List[float]:
    """
    Calculate ATR-based trailing stop levels.

    Stop = highest_high_N - (ATR × multiplier)
    Stop only ratchets UP (never moves down).

    Dynamic multiplier: if (ATR_7 / ATR_14) > 1.5, volatility is expanding
    → multiply by 1.5 to widen the stop automatically.

    Args:
        closes: Close prices (oldest first)
        highs: High prices
        lows: Low prices
        atr_period: ATR lookback period (default 7)
        multiplier: ATR multiplier (3.5–5.0 for crypto, default 4.0)
        dynamic_multiplier: Whether to adjust multiplier on expanding volatility

    Returns:
        List of trailing stop levels (one per bar)
    """
    n = min(len(closes), len(highs), len(lows))
    if n < 2:
        return [0.0] * n

    # Calculate ATR series
    atr_short = calculate_atr_series(highs, lows, closes, atr_period)
    atr_long = calculate_atr_series(highs, lows, closes, atr_period * 2) if dynamic_multiplier else atr_short

    stops: List[float] = [0.0] * n
    highest_stop = 0.0

    for i in range(1, n):
        # Dynamic multiplier adjustment
        eff_mult = multiplier
        if dynamic_multiplier and atr_long[i] > 0:
            vol_ratio = atr_short[i] / atr_long[i]
            if vol_ratio > 1.5:
                eff_mult = multiplier * 1.5  # Widen during volatile periods

        # Calculate stop from recent high
        lookback = min(i + 1, atr_period)
        recent_high = max(highs[i - lookback + 1:i + 1])

        stop_level = recent_high - (atr_short[i] * eff_mult)

        # Ratchet: stop only moves UP
        if stop_level > highest_stop:
            highest_stop = stop_level

        stops[i] = highest_stop

    return stops


# ---------------------------------------------------------------------------
# Exit decision with volume confirmation
# ---------------------------------------------------------------------------

VOLUME_CONFIRMATION_MULTIPLIER = 1.5


def should_exit(
    current_close: float,
    trailing_stop: float,
    current_volume: float,
    avg_volume_20: float,
    *,
    require_volume_confirmation: bool = True,
) -> bool:
    """
    Determine if a position should be exited.

    CRITICAL: Do NOT exit just because price touched the stop.
    Require BOTH conditions:
        1. Price CLOSES below the stop (close, not wick)
        2. Volume > 1.5x 20-bar average (confirms real selling)

    Flash wicks on Solana frequently recover within the same candle.
    Exiting on wicks generates massive unnecessary losses.

    Args:
        current_close: Current bar's close price
        trailing_stop: Current trailing stop level
        current_volume: Current bar's volume
        avg_volume_20: 20-bar average volume
        require_volume_confirmation: If False, exit on price only (hard risk limits)

    Returns:
        True if exit criteria are met
    """
    # Price must close below stop
    if current_close >= trailing_stop:
        return False

    # Volume confirmation (unless disabled for hard risk limits)
    if require_volume_confirmation:
        if avg_volume_20 <= 0:
            return True  # Can't confirm volume — exit conservatively
        volume_ratio = current_volume / avg_volume_20
        if volume_ratio < VOLUME_CONFIRMATION_MULTIPLIER:
            return False  # Low volume = likely manipulation, hold

    return True


# ---------------------------------------------------------------------------
# Time-based stop widths for new token entries
# ---------------------------------------------------------------------------

@dataclass
class NewTokenStopWidth:
    """Stop width configuration for recently launched tokens."""

    label: str
    hours_from: float
    hours_to: float
    trail_pct: Optional[float]  # None = switch to ATR-based

    def applies_at(self, hours_since_entry: float) -> bool:
        return self.hours_from <= hours_since_entry < self.hours_to


NEW_TOKEN_STOP_SCHEDULE = [
    NewTokenStopWidth("0-1h", 0, 1, 0.40),       # First hour: 40% trail
    NewTokenStopWidth("1-4h", 1, 4, 0.25),        # Hours 1–4: 25% trail
    NewTokenStopWidth("4-24h", 4, 24, 0.15),       # Hours 4–24: 15% trail
    NewTokenStopWidth("24h+", 24, float("inf"), None),  # Use ATR-based after 24h
]


def get_new_token_trail_pct(hours_since_entry: float) -> Optional[float]:
    """
    Return the trailing stop percentage for a new token based on time since entry.

    Returns None after 24 hours (switch to ATR-based stops).
    """
    for slot in NEW_TOKEN_STOP_SCHEDULE:
        if slot.applies_at(hours_since_entry):
            return slot.trail_pct
    return None


# ---------------------------------------------------------------------------
# Progressive profit floors
# ---------------------------------------------------------------------------

def get_profit_floor(unrealized_gain_pct: float) -> float:
    """
    Lock in partial gains as position moves.

    Returns the minimum gain percentage to preserve:
        - Unrealized gain > 100%: floor at 50%
        - Unrealized gain > 200%: floor at 100%
        - Unrealized gain > 300%: floor at 200%
        - Below 100%: no floor (use trailing stop only)
    """
    if unrealized_gain_pct >= 3.0:
        return 2.0
    if unrealized_gain_pct >= 2.0:
        return 1.0
    if unrealized_gain_pct >= 1.0:
        return 0.5
    return 0.0  # No floor below 100% gain


# ---------------------------------------------------------------------------
# Tiered exit plan
# ---------------------------------------------------------------------------

@dataclass
class TieredExit:
    """A single tier in the exit plan."""

    pct_position: float     # Fraction of position to sell at this tier
    atr_multiplier: float   # ATR multiplier for this tier's stop
    label: str = ""


TIERED_EXIT_PLAN = [
    TieredExit(0.33, 2.0, "tight"),     # Exit 1/3 at tight stop
    TieredExit(0.33, 3.0, "medium"),    # Exit 1/3 at medium stop
    TieredExit(0.34, 5.0, "wide"),      # Hold 1/3 for big move
]


def calculate_tiered_stops(
    entry_price: float,
    current_high: float,
    atr: float,
    tiers: Optional[List[TieredExit]] = None,
) -> List[dict]:
    """
    Calculate stop levels for each exit tier.

    Returns a list of dicts with: tier, stop_price, pct_position
    """
    if tiers is None:
        tiers = TIERED_EXIT_PLAN

    results = []
    for tier in tiers:
        stop = current_high - (atr * tier.atr_multiplier)
        results.append({
            "tier": tier.label,
            "stop_price": max(0, stop),
            "pct_position": tier.pct_position,
            "atr_multiplier": tier.atr_multiplier,
        })
    return results
