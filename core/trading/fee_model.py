"""
Realistic Fee Model Engine — Must be used by EVERY backtest and live trade.

Models the true round-trip cost of trading on Solana DEXs including:
    - AMM swap fees
    - AMM price impact (based on trade size vs pool liquidity)
    - MEV / sandwich attack exposure
    - Bags.fm perpetual creator fees (1% each direction)
    - Solana priority fees

Round-trip cost benchmarks:
    - HIGH tier (SOL/USDC):        0.3 – 0.6%
    - MID tier ($100K–$1M pool):   1 – 3%
    - MICRO tier ($10K–$100K):     3 – 8%
    - BAGS pre-graduation:         2% base + 2% creator fees + curve impact
    - BAGS post-graduation:        4 – 15% (thin new pool + 2% creator fees)
    - XSTOCK:                      1 – 3% (+ oracle spread off-hours)

A trade is only worth taking if:
    Expected_Edge > (total_round_trip_cost × 2.0)

Usage::

    from core.trading.fee_model import calculate_trade_cost, is_trade_viable
    from core.data.asset_registry import AssetClass

    cost = calculate_trade_cost(
        asset_class=AssetClass.NATIVE_SOLANA,
        pool_liquidity_usd=5_000_000,
        trade_size_usd=500,
    )
    print(f"Round-trip cost: {cost.total_round_trip_pct:.2%}")

    viable = is_trade_viable(expected_edge_pct=0.03, cost=cost)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)

# Import AssetClass — graceful fallback if asset_registry not available
try:
    from core.data.asset_registry import AssetClass
except ImportError:
    # Standalone usage without registry
    class AssetClass(Enum):  # type: ignore[no-redef]
        NATIVE_SOLANA = "native_solana"
        BAGS_BONDING_CURVE = "bags_bonding_curve"
        BAGS_GRADUATED = "bags_graduated"
        XSTOCK = "xstock"
        MEMECOIN = "memecoin"
        STABLECOIN = "stablecoin"


# ---------------------------------------------------------------------------
# Liquidity tiers
# ---------------------------------------------------------------------------

class LiquidityTier(Enum):
    """Classification by pool liquidity depth."""

    HIGH = "high"                   # Pool liquidity > $1M
    MID = "mid"                     # $100K – $1M
    MICRO = "micro"                 # $10K – $100K
    BAGS_PRE_GRAD = "bags_pre_grad"
    BAGS_POST_GRAD = "bags_post_grad"
    XSTOCK = "xstock"


def classify_liquidity(pool_liquidity_usd: float) -> LiquidityTier:
    """Classify a pool by its USD liquidity."""
    if pool_liquidity_usd >= 1_000_000:
        return LiquidityTier.HIGH
    if pool_liquidity_usd >= 100_000:
        return LiquidityTier.MID
    return LiquidityTier.MICRO


# ---------------------------------------------------------------------------
# Cost result
# ---------------------------------------------------------------------------

@dataclass
class TradeCost:
    """All-in cost breakdown for a single trade (one direction)."""

    dex_fee_pct: float              # AMM swap fee (e.g., 0.25% for Raydium)
    price_impact_pct: float         # AMM price impact for this trade size
    mev_cost_pct: float             # Expected MEV / sandwich cost
    creator_fee_pct: float          # Bags.fm creator fee (1% if applicable)
    priority_fee_sol: float         # Solana priority fee in SOL
    priority_fee_usd: float         # Priority fee converted to USD
    total_one_way_pct: float        # Sum of all percentage costs (one direction)
    total_round_trip_pct: float     # Both buy AND sell combined
    liquidity_tier: LiquidityTier

    def to_dict(self) -> dict:
        return {
            "dex_fee_pct": self.dex_fee_pct,
            "price_impact_pct": self.price_impact_pct,
            "mev_cost_pct": self.mev_cost_pct,
            "creator_fee_pct": self.creator_fee_pct,
            "priority_fee_sol": self.priority_fee_sol,
            "priority_fee_usd": self.priority_fee_usd,
            "total_one_way_pct": self.total_one_way_pct,
            "total_round_trip_pct": self.total_round_trip_pct,
            "liquidity_tier": self.liquidity_tier.value,
        }


# ---------------------------------------------------------------------------
# Fee parameters by tier
# ---------------------------------------------------------------------------

# DEX swap fees (Raydium/Orca standard)
DEX_FEE_BPS = {
    LiquidityTier.HIGH: 25,           # 0.25%
    LiquidityTier.MID: 25,
    LiquidityTier.MICRO: 30,          # Higher fee pools
    LiquidityTier.BAGS_PRE_GRAD: 100, # 1% bonding curve fee
    LiquidityTier.BAGS_POST_GRAD: 30,
    LiquidityTier.XSTOCK: 30,
}

# Expected MEV / sandwich cost by tier
MEV_COST_BPS = {
    LiquidityTier.HIGH: 5,            # 0.05% — large pools harder to sandwich
    LiquidityTier.MID: 30,            # 0.30%
    LiquidityTier.MICRO: 100,         # 1.0% — easy targets
    LiquidityTier.BAGS_PRE_GRAD: 50,  # 0.5%
    LiquidityTier.BAGS_POST_GRAD: 150,# 1.5% — graduation hype = MEV magnet
    LiquidityTier.XSTOCK: 20,         # 0.2%
}

# Default priority fee in SOL
DEFAULT_PRIORITY_FEE_SOL = 0.0005
DEFAULT_SOL_PRICE_USD = 150.0  # Fallback if live price unavailable


# ---------------------------------------------------------------------------
# Core calculation
# ---------------------------------------------------------------------------

def calculate_trade_cost(
    asset_class: AssetClass,
    pool_liquidity_usd: float,
    trade_size_usd: float,
    *,
    is_bags_token: bool = False,
    bags_creator_fee_pct: float = 0.0,
    priority_fee_sol: Optional[float] = None,
    sol_price_usd: Optional[float] = None,
    oracle_staleness_minutes: float = 0.0,
) -> TradeCost:
    """
    Calculate the realistic all-in cost for a trade.

    AMM price impact formula:
        impact = trade_size / (2 × pool_liquidity)

    Args:
        asset_class: Classification of the asset being traded
        pool_liquidity_usd: Total USD liquidity in the pool
        trade_size_usd: Notional USD value of the trade
        is_bags_token: Whether this is a Bags.fm token
        bags_creator_fee_pct: Per-direction creator fee (usually 1.0)
        priority_fee_sol: Override Solana priority fee
        sol_price_usd: Current SOL price for fee conversion
        oracle_staleness_minutes: For xStocks — spread widens with staleness
    """
    sol_price = sol_price_usd or DEFAULT_SOL_PRICE_USD
    prio_fee = priority_fee_sol if priority_fee_sol is not None else DEFAULT_PRIORITY_FEE_SOL

    # Determine liquidity tier
    if asset_class == AssetClass.BAGS_BONDING_CURVE:
        tier = LiquidityTier.BAGS_PRE_GRAD
    elif asset_class == AssetClass.BAGS_GRADUATED:
        tier = LiquidityTier.BAGS_POST_GRAD
    elif asset_class == AssetClass.XSTOCK:
        tier = LiquidityTier.XSTOCK
    else:
        tier = classify_liquidity(pool_liquidity_usd)

    # 1. DEX swap fee
    dex_fee_pct = DEX_FEE_BPS[tier] / 10_000

    # 2. Price impact: trade_size / (2 × pool_liquidity)
    if pool_liquidity_usd > 0:
        price_impact_pct = trade_size_usd / (2 * pool_liquidity_usd)
    else:
        price_impact_pct = 0.10  # 10% fallback for unknown liquidity

    # 3. MEV cost
    mev_cost_pct = MEV_COST_BPS[tier] / 10_000

    # 4. Creator fee (Bags.fm only)
    creator_fee_pct = 0.0
    if is_bags_token or asset_class in (AssetClass.BAGS_BONDING_CURVE, AssetClass.BAGS_GRADUATED):
        creator_fee_pct = bags_creator_fee_pct / 100 if bags_creator_fee_pct > 0 else 0.01  # Default 1%

    # 5. Oracle staleness spread (xStocks)
    staleness_spread = 0.0
    if asset_class == AssetClass.XSTOCK and oracle_staleness_minutes > 5:
        # Spread widens with staleness: 0.1% per 5 minutes of staleness
        staleness_spread = min(0.03, oracle_staleness_minutes * 0.0002)

    # 6. Priority fee as percentage of trade
    prio_fee_usd = prio_fee * sol_price
    prio_fee_pct = prio_fee_usd / trade_size_usd if trade_size_usd > 0 else 0.0

    # Total one-way cost
    total_one_way = (
        dex_fee_pct
        + price_impact_pct
        + mev_cost_pct
        + creator_fee_pct
        + staleness_spread
        + prio_fee_pct
    )

    # Round-trip = buy costs + sell costs
    # Most costs apply both directions; price impact doubles
    total_round_trip = (
        (dex_fee_pct * 2)
        + (price_impact_pct * 2)
        + (mev_cost_pct * 2)
        + (creator_fee_pct * 2)    # Creator fee on BOTH buy and sell
        + (staleness_spread * 2)
        + (prio_fee_pct * 2)       # Priority fee on both txns
    )

    return TradeCost(
        dex_fee_pct=dex_fee_pct,
        price_impact_pct=price_impact_pct,
        mev_cost_pct=mev_cost_pct,
        creator_fee_pct=creator_fee_pct,
        priority_fee_sol=prio_fee,
        priority_fee_usd=prio_fee_usd,
        total_one_way_pct=total_one_way,
        total_round_trip_pct=total_round_trip,
        liquidity_tier=tier,
    )


# ---------------------------------------------------------------------------
# Viability check
# ---------------------------------------------------------------------------

MINIMUM_EDGE_TO_COST_RATIO = 2.0


def is_trade_viable(
    expected_edge_pct: float,
    cost: TradeCost,
    min_ratio: float = MINIMUM_EDGE_TO_COST_RATIO,
) -> bool:
    """
    A trade is only worth taking if:
        Expected_Edge > (total_round_trip_cost × min_ratio)

    Default min_ratio is 2.0 — the edge must be at least 2x the cost.
    """
    if cost.total_round_trip_pct <= 0:
        return expected_edge_pct > 0
    ratio = expected_edge_pct / cost.total_round_trip_pct
    return ratio >= min_ratio


def edge_to_cost_ratio(expected_edge_pct: float, cost: TradeCost) -> float:
    """Return the ratio of expected edge to total round-trip cost."""
    if cost.total_round_trip_pct <= 0:
        return float("inf") if expected_edge_pct > 0 else 0.0
    return expected_edge_pct / cost.total_round_trip_pct


def minimum_edge_for_asset(
    asset_class: AssetClass,
    pool_liquidity_usd: float,
    trade_size_usd: float = 500.0,
    **kwargs,
) -> float:
    """
    Return the minimum expected edge (%) needed for a viable trade on this asset.

    This is: total_round_trip_cost × MINIMUM_EDGE_TO_COST_RATIO
    """
    cost = calculate_trade_cost(asset_class, pool_liquidity_usd, trade_size_usd, **kwargs)
    return cost.total_round_trip_pct * MINIMUM_EDGE_TO_COST_RATIO


# ---------------------------------------------------------------------------
# Backtest cost deduction helper
# ---------------------------------------------------------------------------

def deduct_costs(
    entry_price: float,
    exit_price: float,
    entry_cost: TradeCost,
    exit_cost: Optional[TradeCost] = None,
) -> float:
    """
    Apply realistic costs to a backtest trade and return net P&L percentage.

    If exit_cost is not provided, uses the same cost profile as entry.
    """
    if exit_cost is None:
        exit_cost = entry_cost

    gross_pnl_pct = (exit_price - entry_price) / entry_price if entry_price > 0 else 0.0

    # Deduct entry costs (buy side)
    net_entry = entry_price * (1 + entry_cost.total_one_way_pct)
    # Deduct exit costs (sell side)
    net_exit = exit_price * (1 - exit_cost.total_one_way_pct)

    net_pnl_pct = (net_exit - net_entry) / net_entry if net_entry > 0 else 0.0
    return net_pnl_pct
