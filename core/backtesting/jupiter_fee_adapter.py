"""
jupiter_fee_adapter.py — Freqtrade plugin for accurate Jupiter Perps backtesting.

Standard Freqtrade futures modeling is insufficient for Jupiter Perps because:
    1. Jupiter uses a DUAL-SLOPE hourly borrow fee (not a flat rate)
    2. There is an impact fee that scales with position size / pool liquidity
    3. There is an open/close base fee (fixed, paid at entry and exit)
    4. Standard Freqtrade uses simplified linear interest models

Without this adapter, backtests overestimate profitability on held positions.

Usage (in your Freqtrade strategy):
    from core.backtesting.jupiter_fee_adapter import JupiterFeeAdapter

    class MyStrategy(IStrategy):
        def custom_fee(self, pair, trade, ...) -> float:
            return JupiterFeeAdapter.total_fee_for_trade(trade)

Alternatively, monkey-patch Freqtrade's funding_fee calculation:
    from core.backtesting.jupiter_fee_adapter import patch_freqtrade_funding
    patch_freqtrade_funding()

Jupiter Perps Fee Structure (as of 2025-Q4):
    Base fee (open + close):  0.06% each (6 bps)
    Borrow fee:               Dual-slope hourly rate
    Price impact:             Scalar based on size vs pool depth

Dual-Slope Borrow Rate Model:
    Optimal utilization: 70% (JLP pool parameter)
    Rate at 0%:          0.0060% / hour (base rate)
    Rate at optimal:     0.0120% / hour (target rate)
    Rate at 100%:        0.1800% / hour (max rate)

    If utilization <= optimal:
        rate = base_rate + (target_rate - base_rate) * (utilization / optimal)
    If utilization > optimal:
        rate = target_rate + (max_rate - target_rate) * ((utilization - optimal) / (1 - optimal))

Reference:
    https://dev.jup.ag/docs/perps/how-perp-works
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Protocol

log = logging.getLogger(__name__)

# ─── Jupiter Perps Fee Constants ──────────────────────────────────────────────

# Base open/close fee (applied once at entry, once at exit)
OPEN_FEE_BPS: float = 6.0    # 0.06%
CLOSE_FEE_BPS: float = 6.0   # 0.06%

# Dual-slope borrow rate parameters (per hour)
BASE_RATE_HOURLY: float = 0.000060      # 0.006% / hour at 0% utilization
TARGET_RATE_HOURLY: float = 0.000120    # 0.012% / hour at optimal utilization
MAX_RATE_HOURLY: float = 0.001800       # 0.18%  / hour at 100% utilization
OPTIMAL_UTILIZATION: float = 0.70       # 70%

# Conservative execution penalty (flat, applied to all trades)
EXECUTION_PENALTY: float = 0.0005       # 0.05%

# Price impact model parameters
# Impact fee = size_usd / (pool_liquidity * IMPACT_DIVISOR) * IMPACT_SCALAR
POOL_LIQUIDITY_USD: float = 1_400_000_000.0   # ~$1.4B JLP pool (approximate)
IMPACT_DIVISOR: float = 1_000_000.0
IMPACT_SCALAR: float = 0.02


# ─── Core Fee Calculations ────────────────────────────────────────────────────

def calculate_borrow_rate(utilization: float) -> float:
    """
    Compute the Jupiter dual-slope hourly borrow rate for a given utilization.

    Args:
        utilization: Pool utilization ratio (0.0 – 1.0)

    Returns:
        Hourly borrow rate as a decimal (e.g. 0.000120 = 0.012% / hour)
    """
    utilization = max(0.0, min(1.0, utilization))

    if utilization <= OPTIMAL_UTILIZATION:
        # Slope 1: linear from base_rate to target_rate
        rate = BASE_RATE_HOURLY + (TARGET_RATE_HOURLY - BASE_RATE_HOURLY) * (
            utilization / OPTIMAL_UTILIZATION
        )
    else:
        # Slope 2: steeper linear from target_rate to max_rate
        excess = (utilization - OPTIMAL_UTILIZATION) / (1.0 - OPTIMAL_UTILIZATION)
        rate = TARGET_RATE_HOURLY + (MAX_RATE_HOURLY - TARGET_RATE_HOURLY) * excess

    return rate


def calculate_borrow_fee(
    notional_usd: float,
    hours_held: float,
    avg_utilization: float = 0.65,
) -> float:
    """
    Calculate total borrow fee for a position held for a given duration.

    Args:
        notional_usd: Position size in USD (notional, not collateral)
        hours_held: How long the position was held (fractional hours OK)
        avg_utilization: Average pool utilization during the hold period.
                         Conservative default: 0.65 (near optimal, typical)

    Returns:
        Total borrow fee in USD
    """
    hourly_rate = calculate_borrow_rate(avg_utilization)
    return notional_usd * hourly_rate * hours_held


def calculate_impact_fee(
    size_usd: float,
    pool_liquidity_usd: float = POOL_LIQUIDITY_USD,
) -> float:
    """
    Estimate the price impact fee for a given position size.

    This is an approximation — actual impact depends on oracle price and
    real-time pool state. Conservative (over-estimates for safety).

    Args:
        size_usd: Position size in USD
        pool_liquidity_usd: Total JLP pool liquidity in USD

    Returns:
        Impact fee as a decimal (e.g. 0.0003 = 0.03%)
    """
    if pool_liquidity_usd <= 0:
        return 0.0
    impact = (size_usd / pool_liquidity_usd) * IMPACT_SCALAR
    return min(impact, 0.005)  # cap at 0.5% to avoid extreme outliers


def bps_to_decimal(bps: float) -> float:
    return bps / 10_000.0


# ─── High-Level Trade Fee Calculator ─────────────────────────────────────────

@dataclass
class JupiterTradeFees:
    """All fees for a single Jupiter Perps trade round-trip."""
    open_fee_usd: float
    close_fee_usd: float
    borrow_fee_usd: float
    impact_fee_open_usd: float
    impact_fee_close_usd: float
    execution_penalty_usd: float

    @property
    def total_usd(self) -> float:
        return (
            self.open_fee_usd
            + self.close_fee_usd
            + self.borrow_fee_usd
            + self.impact_fee_open_usd
            + self.impact_fee_close_usd
            + self.execution_penalty_usd
        )

    @property
    def total_pct(self) -> float:
        """Total fees as a percentage (rough — denominator is borrow notional)."""
        return self.total_usd

    def __str__(self) -> str:
        return (
            f"JupiterTradeFees("
            f"open={self.open_fee_usd:.4f}, "
            f"close={self.close_fee_usd:.4f}, "
            f"borrow={self.borrow_fee_usd:.4f}, "
            f"impact={self.impact_fee_open_usd + self.impact_fee_close_usd:.4f}, "
            f"execution={self.execution_penalty_usd:.4f}, "
            f"TOTAL={self.total_usd:.4f} USD"
            f")"
        )


class JupiterFeeAdapter:
    """
    Adapter between Jupiter Perps fee model and Freqtrade backtesting.

    Usage in Freqtrade strategy:

        def custom_fee(self, pair, trade, order_type, amount, price, fee_side, **kwargs):
            return JupiterFeeAdapter.open_fee_rate()

        def custom_exit_price(self, pair, trade, current_time, proposed_rate, current_profit, **kwargs):
            # Deduct borrow fee from exit price
            hours = (current_time - trade.open_date_utc).total_seconds() / 3600
            borrow_usd = JupiterFeeAdapter.borrow_fee_usd(trade.stake_amount * trade.leverage, hours)
            # Adjust for fee
            borrow_pct = borrow_usd / (trade.stake_amount * trade.leverage)
            return proposed_rate * (1 - borrow_pct)
    """

    @staticmethod
    def open_fee_rate() -> float:
        """Open fee as a decimal rate (for Freqtrade fee= parameter)."""
        return bps_to_decimal(OPEN_FEE_BPS) + EXECUTION_PENALTY

    @staticmethod
    def close_fee_rate() -> float:
        """Close fee as a decimal rate."""
        return bps_to_decimal(CLOSE_FEE_BPS) + EXECUTION_PENALTY

    @staticmethod
    def borrow_fee_usd(
        notional_usd: float,
        hours_held: float,
        avg_utilization: float = 0.65,
    ) -> float:
        """Compute borrow fee in USD for a held position."""
        return calculate_borrow_fee(notional_usd, hours_held, avg_utilization)

    @staticmethod
    def impact_fee_rate(size_usd: float) -> float:
        """Price impact fee as a decimal rate."""
        return calculate_impact_fee(size_usd)

    @staticmethod
    def compute_full_fees(
        notional_usd: float,
        hours_held: float,
        avg_utilization: float = 0.65,
        pool_liquidity_usd: float = POOL_LIQUIDITY_USD,
    ) -> JupiterTradeFees:
        """
        Compute all fees for a complete trade (open → hold → close).

        Args:
            notional_usd: Position size in USD (collateral × leverage)
            hours_held: How long the position was held
            avg_utilization: Average JLP pool utilization (default 0.65)
            pool_liquidity_usd: JLP pool total liquidity (default 1.4B)

        Returns:
            JupiterTradeFees dataclass with all fee components
        """
        open_fee = notional_usd * bps_to_decimal(OPEN_FEE_BPS)
        close_fee = notional_usd * bps_to_decimal(CLOSE_FEE_BPS)
        borrow_fee = calculate_borrow_fee(notional_usd, hours_held, avg_utilization)
        impact_open = notional_usd * calculate_impact_fee(notional_usd, pool_liquidity_usd)
        impact_close = notional_usd * calculate_impact_fee(notional_usd, pool_liquidity_usd)
        execution = notional_usd * EXECUTION_PENALTY * 2  # open + close

        return JupiterTradeFees(
            open_fee_usd=open_fee,
            close_fee_usd=close_fee,
            borrow_fee_usd=borrow_fee,
            impact_fee_open_usd=impact_open,
            impact_fee_close_usd=impact_close,
            execution_penalty_usd=execution,
        )

    @staticmethod
    def minimum_win_pct(
        notional_usd: float,
        hours_held: float,
        avg_utilization: float = 0.65,
    ) -> float:
        """
        Compute the minimum price movement % needed to break even on a trade.

        This is the hurdle rate: any trade with expected return below this
        value is unprofitable after fees.

        Returns: decimal (e.g. 0.0020 = 0.20% minimum win required)
        """
        fees = JupiterFeeAdapter.compute_full_fees(
            notional_usd, hours_held, avg_utilization
        )
        return fees.total_usd / notional_usd


# ─── Freqtrade Integration ────────────────────────────────────────────────────

def patch_freqtrade_funding() -> None:
    """
    Monkey-patch Freqtrade's funding fee model with Jupiter's dual-slope rate.

    Call this ONCE at module load in your Freqtrade strategy file:
        from core.backtesting.jupiter_fee_adapter import patch_freqtrade_funding
        patch_freqtrade_funding()

    This patches freqtrade.exchange.Exchange.get_funding_fees to use the
    Jupiter dual-slope model instead of the exchange-reported funding rate.
    """
    try:
        import freqtrade.exchange as ft_exchange  # noqa: PLC0415

        original_get_funding_fees = ft_exchange.Exchange.get_funding_fees

        def jupiter_funding_fees(
            self: Any,
            pair: str,
            amount: float,
            is_short: bool,
            open_date: Any,
        ) -> float:
            """Jupiter dual-slope borrow fee replacing Freqtrade's funding fee."""
            import datetime  # noqa: PLC0415

            if hasattr(open_date, "timestamp"):
                import datetime as dt  # noqa: PLC0415
                hours = (dt.datetime.utcnow() - open_date).total_seconds() / 3600
            else:
                hours = 1.0  # fallback

            # amount is in base currency — convert to USD approximately
            # In Freqtrade backtesting, amount * close_price ≈ notional_usd
            # We use a conservative 65% utilization assumption
            notional_usd = abs(amount) * self.get_pair_base_currency_usd_price(pair)
            fee_usd = calculate_borrow_fee(notional_usd, hours, avg_utilization=0.65)
            return -fee_usd if not is_short else fee_usd

        ft_exchange.Exchange.get_funding_fees = jupiter_funding_fees
        log.info("Freqtrade funding fee model patched with Jupiter dual-slope model")

    except ImportError:
        log.warning("freqtrade not installed — skipping funding fee patch")
    except Exception as e:
        log.error("Failed to patch Freqtrade funding fees: %s", e)


# ─── Standalone Validation ────────────────────────────────────────────────────

if __name__ == "__main__":
    """Quick sanity check — run directly to validate fee model."""
    print("Jupiter Perps Fee Model Validation")
    print("=" * 50)

    for util in [0.0, 0.35, 0.70, 0.85, 1.0]:
        rate = calculate_borrow_rate(util)
        print(f"  Utilization {util*100:5.1f}%:  {rate*100*24:.4f}% / day  ({rate*100:.6f}% / hour)")

    print()
    print("Trade Example: $10,000 position, 10x leverage, held 24 hours, 65% utilization")
    notional = 100_000.0  # $10k collateral × 10x leverage
    fees = JupiterFeeAdapter.compute_full_fees(notional, 24.0)
    print(f"  {fees}")
    hurdle = JupiterFeeAdapter.minimum_win_pct(notional, 24.0)
    print(f"  Minimum win required: {hurdle*100:.4f}%")
    print()
    print("Trade Example: $1,000 position, 5x leverage, held 4 hours")
    fees2 = JupiterFeeAdapter.compute_full_fees(5_000.0, 4.0)
    print(f"  {fees2}")
