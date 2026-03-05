"""
ATR-Based Position Sizing with Kelly Criterion and Liquidity Guards.

Core formula:
    position_size = (account_balance × risk_per_trade) / (ATR × 3)

Maximum risk per trade: 1% of account.

Asset class hard limits:
    - NATIVE_SOLANA (large cap): 5% per position
    - MID_CAP memecoin: 3% per position
    - BAGS_GRADUATED: 0.5% per position
    - BAGS_PRE_GRAD: 0.25% per position
    - XSTOCK: 2% per position
    - Any single memecoin: 1% max

Kelly criterion: QUARTER Kelly (0.25 × full Kelly).
Full Kelly on crypto destroys accounts.

Liquidity check: trade size must be < 5% of pool liquidity.

Usage::

    from core.trading.position_sizing import calculate_position_size

    size = calculate_position_size(
        account_balance_usd=10000,
        entry_price=150.0,
        stop_loss_price=140.0,
        atr=5.0,
        asset_class=AssetClass.NATIVE_SOLANA,
        pool_liquidity_usd=5_000_000,
    )
    print(f"Position size: ${size.position_usd:.2f} ({size.position_pct:.1%})")
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from core.data.asset_registry import AssetClass
except ImportError:
    from enum import Enum
    class AssetClass(Enum):  # type: ignore[no-redef]
        NATIVE_SOLANA = "native_solana"
        BAGS_BONDING_CURVE = "bags_bonding_curve"
        BAGS_GRADUATED = "bags_graduated"
        XSTOCK = "xstock"
        MEMECOIN = "memecoin"
        STABLECOIN = "stablecoin"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# Maximum risk per trade as fraction of account
MAX_RISK_PER_TRADE = 0.01  # 1%

# Maximum position size as fraction of portfolio (hard limits)
MAX_POSITION_PCT = {
    AssetClass.NATIVE_SOLANA: 0.05,        # 5%
    AssetClass.MEMECOIN: 0.01,             # 1% — any single memecoin
    AssetClass.BAGS_BONDING_CURVE: 0.0025, # 0.25% — extremely speculative
    AssetClass.BAGS_GRADUATED: 0.005,      # 0.5% — graduation pools still risky
    AssetClass.XSTOCK: 0.02,              # 2%
    AssetClass.STABLECOIN: 0.10,          # 10% — stables are low risk
}

# Default for unknown asset classes
DEFAULT_MAX_POSITION_PCT = 0.01  # 1%

# Maximum fraction of pool liquidity our trade can consume
MAX_POOL_IMPACT_PCT = 0.05  # 5%

# Kelly fraction (quarter Kelly)
KELLY_FRACTION = 0.25


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class PositionSize:
    """Calculated position sizing result."""

    position_usd: float         # Absolute USD size
    position_pct: float         # As fraction of portfolio
    quantity: float             # Token quantity at entry price
    risk_usd: float            # Max loss if stop hit
    risk_pct: float            # Risk as fraction of portfolio
    method: str                # Sizing method used
    capped_by: str             # What constraint limited the size
    kelly_raw: float           # Raw full Kelly sizing (for reference)
    kelly_quarter: float       # Quarter Kelly sizing used

    def summary(self) -> str:
        return (
            f"Size: ${self.position_usd:.2f} ({self.position_pct:.1%} of portfolio) | "
            f"Risk: ${self.risk_usd:.2f} ({self.risk_pct:.1%}) | "
            f"Capped by: {self.capped_by}"
        )


# ---------------------------------------------------------------------------
# Kelly criterion
# ---------------------------------------------------------------------------

def calculate_kelly(
    win_rate: float,
    avg_win_pct: float,
    avg_loss_pct: float,
) -> float:
    """
    Calculate the Kelly criterion fraction.

    f* = (p × b - q) / b

    where:
        p = win probability
        q = 1 - p
        b = ratio of average win to average loss

    Returns the optimal fraction of capital to risk.
    Negative values mean the strategy has negative expected value.
    """
    if avg_loss_pct <= 0 or win_rate <= 0 or win_rate >= 1:
        return 0.0

    b = avg_win_pct / avg_loss_pct
    q = 1 - win_rate
    kelly = (win_rate * b - q) / b

    return max(0.0, kelly)


# ---------------------------------------------------------------------------
# Main sizing function
# ---------------------------------------------------------------------------

def calculate_position_size(
    account_balance_usd: float,
    entry_price: float,
    stop_loss_price: float,
    atr: float,
    asset_class: AssetClass,
    pool_liquidity_usd: float,
    *,
    risk_per_trade: float = MAX_RISK_PER_TRADE,
    win_rate: Optional[float] = None,
    avg_win_pct: Optional[float] = None,
    avg_loss_pct: Optional[float] = None,
) -> PositionSize:
    """
    Calculate position size using ATR-based risk management.

    Primary formula:
        position_size = (account_balance × risk_per_trade) / (ATR × 3)

    Then constrained by:
        1. Asset class maximum (e.g., 5% for SOL, 0.25% for pre-grad Bags)
        2. Pool liquidity (trade < 5% of pool)
        3. Quarter Kelly criterion (if historical stats available)

    The most restrictive constraint wins.

    Args:
        account_balance_usd: Total portfolio value in USD
        entry_price: Expected entry price
        stop_loss_price: Stop loss price level
        atr: Average True Range of the asset
        asset_class: Asset classification
        pool_liquidity_usd: USD liquidity in the trading pool
        risk_per_trade: Max risk fraction (default 1%)
        win_rate: Historical win rate (optional, for Kelly)
        avg_win_pct: Average win percentage (optional, for Kelly)
        avg_loss_pct: Average loss percentage (optional, for Kelly)
    """
    if account_balance_usd <= 0 or entry_price <= 0:
        return PositionSize(
            position_usd=0, position_pct=0, quantity=0,
            risk_usd=0, risk_pct=0, method="none",
            capped_by="invalid_input", kelly_raw=0, kelly_quarter=0,
        )

    capped_by = "atr_risk"

    # 1. ATR-based sizing: risk budget / (ATR × 3)
    risk_budget = account_balance_usd * risk_per_trade
    atr_distance = atr * 3 if atr > 0 else abs(entry_price - stop_loss_price)

    if atr_distance <= 0:
        # Fallback: use entry-to-stop distance
        atr_distance = abs(entry_price - stop_loss_price)
        if atr_distance <= 0:
            atr_distance = entry_price * 0.05  # 5% default stop distance

    position_usd = risk_budget / (atr_distance / entry_price) if atr_distance > 0 else 0
    position_pct = position_usd / account_balance_usd if account_balance_usd > 0 else 0

    # 2. Asset class maximum
    max_pct = MAX_POSITION_PCT.get(asset_class, DEFAULT_MAX_POSITION_PCT)
    max_usd_class = account_balance_usd * max_pct
    if position_usd > max_usd_class:
        position_usd = max_usd_class
        capped_by = f"asset_class_max:{max_pct:.2%}"

    # 3. Pool liquidity constraint (< 5% of pool)
    if pool_liquidity_usd > 0:
        max_usd_liquidity = pool_liquidity_usd * MAX_POOL_IMPACT_PCT
        if position_usd > max_usd_liquidity:
            position_usd = max_usd_liquidity
            capped_by = f"pool_liquidity:{MAX_POOL_IMPACT_PCT:.0%}"

    # 4. Kelly criterion (if stats available)
    kelly_raw = 0.0
    kelly_quarter = 0.0
    if win_rate is not None and avg_win_pct is not None and avg_loss_pct is not None:
        kelly_raw = calculate_kelly(win_rate, avg_win_pct, avg_loss_pct)
        kelly_quarter = kelly_raw * KELLY_FRACTION
        max_usd_kelly = account_balance_usd * kelly_quarter
        if kelly_quarter > 0 and position_usd > max_usd_kelly:
            position_usd = max_usd_kelly
            capped_by = f"quarter_kelly:{kelly_quarter:.2%}"

    # Final calculations
    position_pct = position_usd / account_balance_usd if account_balance_usd > 0 else 0
    quantity = position_usd / entry_price if entry_price > 0 else 0
    risk_usd = position_usd * (atr_distance / entry_price)
    risk_pct = risk_usd / account_balance_usd if account_balance_usd > 0 else 0

    result = PositionSize(
        position_usd=round(position_usd, 2),
        position_pct=round(position_pct, 6),
        quantity=round(quantity, 8),
        risk_usd=round(risk_usd, 2),
        risk_pct=round(risk_pct, 6),
        method="atr_risk",
        capped_by=capped_by,
        kelly_raw=round(kelly_raw, 6),
        kelly_quarter=round(kelly_quarter, 6),
    )

    logger.debug(result.summary())
    return result
