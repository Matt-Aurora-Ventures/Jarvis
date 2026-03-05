"""
Dynamic Jito Tip Calculator.

Replaces static tip values with context-aware calculations based on:
    - Projected profit
    - Market volatility regime
    - Whether this is a sniper entry (time-sensitive)

Rules:
    - Never tip more than 20% of projected profit
    - Never use a static hardcoded tip value
    - Scale tips with volatility and urgency

Usage::

    from core.trading.jito_tips import calculate_jito_tip

    tip_sol = calculate_jito_tip(
        projected_profit_usd=50.0,
        market_volatility="medium",
        is_sniper_entry=False,
        sol_price_usd=150.0,
    )
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class VolatilityRegime(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"  # Graduation events, flash crashes


# Baseline tips by volatility regime (in SOL)
BASELINE_TIPS_SOL = {
    VolatilityRegime.LOW: 0.001,
    VolatilityRegime.MEDIUM: 0.004,
    VolatilityRegime.HIGH: 0.015,
    VolatilityRegime.EXTREME: 0.04,
}

# Maximum tip caps by regime (in SOL)
MAX_TIPS_SOL = {
    VolatilityRegime.LOW: 0.005,
    VolatilityRegime.MEDIUM: 0.01,
    VolatilityRegime.HIGH: 0.02,
    VolatilityRegime.EXTREME: 0.05,
}

# Profit-proportional caps by regime
PROFIT_TIP_FRACTION = {
    VolatilityRegime.LOW: 0.10,       # Tip up to 10% of profit
    VolatilityRegime.MEDIUM: 0.15,    # 15%
    VolatilityRegime.HIGH: 0.15,      # 15%
    VolatilityRegime.EXTREME: 0.20,   # 20%
}

# Hard cap: NEVER tip more than this fraction of projected profit
MAX_PROFIT_TIP_FRACTION = 0.20


def calculate_jito_tip(
    projected_profit_usd: float,
    market_volatility: str = "low",
    is_sniper_entry: bool = False,
    sol_price_usd: float = 150.0,
) -> float:
    """
    Calculate the optimal Jito tip in SOL.

    Args:
        projected_profit_usd: Expected profit from this trade in USD
        market_volatility: "low", "medium", "high", or "extreme"
        is_sniper_entry: True if this is a time-sensitive sniper trade
        sol_price_usd: Current SOL price for USD conversion

    Returns:
        Recommended tip in SOL
    """
    try:
        regime = VolatilityRegime(market_volatility.lower())
    except ValueError:
        regime = VolatilityRegime.LOW

    if sol_price_usd <= 0:
        sol_price_usd = 150.0

    # Start with baseline for the volatility regime
    tip = BASELINE_TIPS_SOL[regime]

    # Sniper entries need higher tips for priority landing
    if is_sniper_entry:
        tip = max(tip, BASELINE_TIPS_SOL.get(VolatilityRegime.HIGH, 0.015))
        if regime == VolatilityRegime.EXTREME:
            tip = BASELINE_TIPS_SOL[VolatilityRegime.EXTREME]

    # Scale with projected profit
    if projected_profit_usd > 0:
        profit_fraction = PROFIT_TIP_FRACTION[regime]
        profit_based_tip = (projected_profit_usd * profit_fraction) / sol_price_usd
        tip = max(tip, profit_based_tip)

    # Apply hard caps
    # 1. Never exceed regime-specific SOL cap
    max_sol = MAX_TIPS_SOL[regime]
    tip = min(tip, max_sol)

    # 2. Never tip more than 20% of projected profit
    if projected_profit_usd > 0:
        max_from_profit = (projected_profit_usd * MAX_PROFIT_TIP_FRACTION) / sol_price_usd
        tip = min(tip, max_from_profit)

    # 3. Minimum floor — always tip at least 0.0005 SOL to get included
    tip = max(tip, 0.0005)

    logger.debug(
        "Jito tip: %.6f SOL (regime=%s, sniper=%s, profit=$%.2f)",
        tip, regime.value, is_sniper_entry, projected_profit_usd,
    )
    return round(tip, 9)


def tip_to_lamports(tip_sol: float) -> int:
    """Convert SOL tip to lamports."""
    return int(tip_sol * 1_000_000_000)
