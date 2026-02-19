"""Pre-trade cost gate for Jupiter Perps.

Every OpenPosition intent must pass through the cost gate BEFORE reaching
the execution service. The gate rejects trades where:
    - Expected fees exceed a reasonable return for the confidence level
    - Portfolio exposure would exceed safety limits
    - Daily drawdown halt is active
    - Duplicate positions would be opened (same asset + direction)

The cost gate is a pure function — no side effects, no state mutation.
It reads from the position manager and fee adapter but writes nothing.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.jupiter_perps.position_manager import PositionManager

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class CostGateConfig:
    max_total_exposure_usd: float = 5_000.0
    max_asset_exposure_usd: float = 2_000.0
    max_positions: int = 5
    daily_drawdown_halt_pct: float = 3.0
    max_trades_per_day: int = 40
    daily_loss_limit_usd: float = 500.0
    # Expected hold hours per leverage tier — higher leverage = shorter hold
    leverage_to_hold_hours: dict[float, float] | None = None

    def __post_init__(self) -> None:
        if self.leverage_to_hold_hours is None:
            self.leverage_to_hold_hours = {
                2.0: 24.0,
                3.0: 16.0,
                5.0: 8.0,
                7.0: 4.0,
                10.0: 2.0,
                20.0: 1.0,
            }

    @classmethod
    def from_env(cls) -> CostGateConfig:
        return cls(
            max_total_exposure_usd=float(os.environ.get("PERPS_MAX_TOTAL_EXPOSURE_USD", "5000")),
            max_asset_exposure_usd=float(os.environ.get("PERPS_MAX_ASSET_EXPOSURE_USD", "2000")),
            max_positions=int(os.environ.get("PERPS_MAX_POSITIONS", "5")),
            daily_drawdown_halt_pct=float(os.environ.get("PERPS_DAILY_DRAWDOWN_HALT_PCT", "3.0")),
            max_trades_per_day=int(os.environ.get("PERPS_MAX_TRADES_PER_DAY", "40")),
            daily_loss_limit_usd=float(os.environ.get("PERPS_DAILY_LOSS_LIMIT_USD", "500.0")),
        )

    def expected_hold_hours(self, leverage: float) -> float:
        """Estimate how long a position at this leverage will be held."""
        if self.leverage_to_hold_hours is None:
            return 8.0
        # Find the closest leverage tier
        best_hours = 8.0
        best_dist = float("inf")
        for lev, hours in self.leverage_to_hold_hours.items():
            dist = abs(lev - leverage)
            if dist < best_dist:
                best_dist = dist
                best_hours = hours
        return best_hours


# ---------------------------------------------------------------------------
# Cost verdict
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CostVerdict:
    """Result of cost gate evaluation."""

    passed: bool
    reason: str
    hurdle_rate_pct: float = 0.0
    total_fees_usd: float = 0.0
    projected_exposure_usd: float = 0.0


# ---------------------------------------------------------------------------
# Cost gate
# ---------------------------------------------------------------------------


class CostGate:
    """Stateless pre-trade validator.

    Checks:
        1. Hurdle rate — fees must not exceed reasonable return
        2. Portfolio exposure cap
        3. Per-asset concentration cap
        4. Position count limit
        5. Daily drawdown halt
        6. Correlation guard (no duplicate asset+direction)
    """

    def __init__(self, config: CostGateConfig | None = None) -> None:
        self._config = config or CostGateConfig.from_env()

    @property
    def config(self) -> CostGateConfig:
        return self._config

    def evaluate(
        self,
        market: str,
        side: str,
        size_usd: float,
        leverage: float,
        confidence: float,
        position_manager: PositionManager,
    ) -> CostVerdict:
        """Evaluate whether a trade should be allowed.

        Args:
            market: e.g. "SOL-USD"
            side: "long" or "short"
            size_usd: notional position size
            leverage: leverage multiplier
            confidence: signal confidence (0.0–1.0)
            position_manager: current position state

        Returns:
            CostVerdict with passed=True/False and reason
        """
        cfg = self._config

        # --- Check 1: Hurdle rate ---
        hurdle_pct, total_fees = self._compute_hurdle(size_usd, leverage)
        max_acceptable_hurdle = confidence * 15.0  # 15% at confidence=1.0, 11.25% at 0.75
        if hurdle_pct > max_acceptable_hurdle:
            return CostVerdict(
                passed=False,
                reason=(
                    f"Hurdle rate {hurdle_pct:.2f}% > max acceptable {max_acceptable_hurdle:.2f}% "
                    f"(confidence={confidence:.2f}). Fees ${total_fees:.2f} on ${size_usd:.0f} notional"
                ),
                hurdle_rate_pct=hurdle_pct,
                total_fees_usd=total_fees,
            )

        # --- Check 2: Portfolio exposure ---
        current_exposure = position_manager.get_total_exposure_usd()
        projected_exposure = current_exposure + size_usd
        if projected_exposure > cfg.max_total_exposure_usd:
            return CostVerdict(
                passed=False,
                reason=(
                    f"Portfolio exposure ${projected_exposure:.0f} would exceed "
                    f"max ${cfg.max_total_exposure_usd:.0f}"
                ),
                hurdle_rate_pct=hurdle_pct,
                total_fees_usd=total_fees,
                projected_exposure_usd=projected_exposure,
            )

        # --- Check 3: Per-asset concentration ---
        asset_exposure = position_manager.get_asset_exposure_usd(market) + size_usd
        if asset_exposure > cfg.max_asset_exposure_usd:
            return CostVerdict(
                passed=False,
                reason=(
                    f"{market} exposure ${asset_exposure:.0f} would exceed "
                    f"max ${cfg.max_asset_exposure_usd:.0f}"
                ),
                hurdle_rate_pct=hurdle_pct,
                total_fees_usd=total_fees,
                projected_exposure_usd=projected_exposure,
            )

        # --- Check 4: Position count ---
        if position_manager.get_position_count() >= cfg.max_positions:
            return CostVerdict(
                passed=False,
                reason=f"Position count {position_manager.get_position_count()} >= max {cfg.max_positions}",
                hurdle_rate_pct=hurdle_pct,
                total_fees_usd=total_fees,
                projected_exposure_usd=projected_exposure,
            )

        # --- Check 5: Daily drawdown halt ---
        daily_pnl = position_manager.get_daily_pnl_usd()
        if current_exposure > 0:
            drawdown_pct = abs(min(daily_pnl, 0.0)) / current_exposure * 100.0
            if drawdown_pct >= cfg.daily_drawdown_halt_pct:
                return CostVerdict(
                    passed=False,
                    reason=(
                        f"Daily drawdown halt: {drawdown_pct:.1f}% loss today "
                        f">= {cfg.daily_drawdown_halt_pct}% threshold"
                    ),
                    hurdle_rate_pct=hurdle_pct,
                    total_fees_usd=total_fees,
                    projected_exposure_usd=projected_exposure,
                )

        # --- Check 6: Correlation guard ---
        if position_manager.has_position(market, side):
            return CostVerdict(
                passed=False,
                reason=f"Duplicate position: already have {market} {side}",
                hurdle_rate_pct=hurdle_pct,
                total_fees_usd=total_fees,
                projected_exposure_usd=projected_exposure,
            )

        # --- Check 7: Daily trade limiter ---
        opened_today = position_manager.get_trades_opened_today()
        if opened_today >= cfg.max_trades_per_day:
            return CostVerdict(
                passed=False,
                reason=f"Daily trade limit reached: {opened_today} >= {cfg.max_trades_per_day}",
                hurdle_rate_pct=hurdle_pct,
                total_fees_usd=total_fees,
                projected_exposure_usd=projected_exposure,
            )

        # --- Check 8: Daily loss limiter ---
        if position_manager.get_daily_pnl_usd() <= -cfg.daily_loss_limit_usd:
            return CostVerdict(
                passed=False,
                reason=(
                    f"Daily loss limit breached: ${position_manager.get_daily_pnl_usd():.2f} "
                    f"<= -${cfg.daily_loss_limit_usd:.2f}"
                ),
                hurdle_rate_pct=hurdle_pct,
                total_fees_usd=total_fees,
                projected_exposure_usd=projected_exposure,
            )

        # All checks passed
        return CostVerdict(
            passed=True,
            reason="ok",
            hurdle_rate_pct=hurdle_pct,
            total_fees_usd=total_fees,
            projected_exposure_usd=projected_exposure,
        )

    def _compute_hurdle(self, size_usd: float, leverage: float) -> tuple[float, float]:
        """Compute hurdle rate percentage and total fees in USD.

        Returns:
            (hurdle_rate_pct, total_fees_usd)
        """
        expected_hours = self._config.expected_hold_hours(leverage)

        try:
            from core.backtesting.jupiter_fee_adapter import JupiterFeeAdapter  # noqa: PLC0415

            fees = JupiterFeeAdapter.compute_full_fees(
                notional_usd=size_usd,
                hours_held=expected_hours,
                avg_utilization=0.65,
            )
            hurdle_pct = (fees.total_usd / size_usd) * 100.0 if size_usd > 0 else 0.0
            return hurdle_pct, fees.total_usd
        except ImportError:
            # Fee adapter not available — use conservative estimate
            # Open + close = 0.12%, borrow = ~0.01%/hr, execution = 0.10%
            conservative_pct = 0.22 + (expected_hours * 0.01)
            conservative_usd = size_usd * (conservative_pct / 100.0)
            return conservative_pct, conservative_usd
