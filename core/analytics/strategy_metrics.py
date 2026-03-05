"""
Strategy Metrics Display — Standardized thresholds and color coding.

Defines the unified metric thresholds for all dashboard displays:

    | Metric         | Poor    | Acceptable | Good    | Excellent |
    |----------------|---------|-----------|---------|-----------|
    | Sharpe Ratio   | < 0.5   | 0.5–1.0   | 1.0–2.0 | > 2.0     |
    | Sortino Ratio  | < 0.8   | 0.8–1.5   | 1.5–3.0 | > 3.0     |
    | Profit Factor  | < 1.0   | 1.0–1.3   | 1.3–2.0 | > 2.0     |
    | Max Drawdown   | > 40%   | 20–40%    | 10–20%  | < 10%     |
    | Wilson LB      | < 0.52  | 0.52–0.56 | 0.56–0.62| > 0.62   |

Live Sharpe estimate: backtest_sharpe × 0.6

Replaces "WR Gate: UNVERIFIED" labels with proper confidence reporting.

Usage::

    from core.analytics.strategy_metrics import (
        classify_metric,
        MetricTier,
        format_strategy_status,
        estimate_live_sharpe,
    )

    tier = classify_metric("sharpe", 1.5)
    # → MetricTier.GOOD

    status = format_strategy_status(
        name="PUMP FRESH TIGHT",
        total_trades=246,
        wins=140,
        gross_profit=5000,
        gross_loss=4400,
    )
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from core.analytics.strategy_confidence import (
    wilson_lower_bound,
    is_strategy_deployable,
    get_confidence_tier,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tiers
# ---------------------------------------------------------------------------

class MetricTier(Enum):
    """Quality tier for a metric value."""

    POOR = "poor"
    ACCEPTABLE = "acceptable"
    GOOD = "good"
    EXCELLENT = "excellent"


# Color mapping for dashboards (CSS / terminal)
TIER_COLORS = {
    MetricTier.POOR: "#ef4444",       # Red
    MetricTier.ACCEPTABLE: "#f59e0b", # Amber
    MetricTier.GOOD: "#22c55e",       # Green
    MetricTier.EXCELLENT: "#3b82f6",  # Blue
}


# ---------------------------------------------------------------------------
# Threshold definitions
# ---------------------------------------------------------------------------

# Each metric: (poor_upper, acceptable_upper, good_upper)
# Values >= good_upper → EXCELLENT
# Drawdown is inverted (lower is better)

THRESHOLDS = {
    "sharpe": (0.5, 1.0, 2.0),
    "sortino": (0.8, 1.5, 3.0),
    "profit_factor": (1.0, 1.3, 2.0),
    "wilson_lb": (0.52, 0.56, 0.62),
}

# Drawdown thresholds (inverted: lower is better)
DRAWDOWN_THRESHOLDS = {
    "max_drawdown": (0.40, 0.20, 0.10),  # > 40% = poor, 20-40% = acceptable, 10-20% = good, < 10% = excellent
}


def classify_metric(metric_name: str, value: float) -> MetricTier:
    """
    Classify a metric value into a quality tier.

    Args:
        metric_name: "sharpe", "sortino", "profit_factor", "wilson_lb", or "max_drawdown"
        value: The metric value

    Returns:
        MetricTier enum value
    """
    if metric_name in DRAWDOWN_THRESHOLDS:
        poor_limit, acceptable_limit, good_limit = DRAWDOWN_THRESHOLDS[metric_name]
        if value > poor_limit:
            return MetricTier.POOR
        if value > acceptable_limit:
            return MetricTier.ACCEPTABLE
        if value > good_limit:
            return MetricTier.GOOD
        return MetricTier.EXCELLENT

    if metric_name not in THRESHOLDS:
        return MetricTier.ACCEPTABLE  # Unknown metric → neutral

    poor_limit, acceptable_limit, good_limit = THRESHOLDS[metric_name]
    if value < poor_limit:
        return MetricTier.POOR
    if value < acceptable_limit:
        return MetricTier.ACCEPTABLE
    if value < good_limit:
        return MetricTier.GOOD
    return MetricTier.EXCELLENT


def get_metric_color(metric_name: str, value: float) -> str:
    """Return the hex color for a metric value."""
    tier = classify_metric(metric_name, value)
    return TIER_COLORS[tier]


# ---------------------------------------------------------------------------
# Live Sharpe estimate
# ---------------------------------------------------------------------------

LIVE_DISCOUNT_FACTOR = 0.6


def estimate_live_sharpe(backtest_sharpe: float) -> float:
    """
    Estimate realistic live Sharpe from backtest Sharpe.

    Live Sharpe is typically 30-50% lower than backtested due to
    execution costs, slippage, and regime changes.

    Returns backtest_sharpe × 0.6
    """
    return backtest_sharpe * LIVE_DISCOUNT_FACTOR


# ---------------------------------------------------------------------------
# Annualization indicator
# ---------------------------------------------------------------------------

def get_annualization_note(asset_class_name: str) -> str:
    """
    Return annualization note for Sharpe display.

    Crypto uses 365-day annualization, xStocks use 252-day.
    """
    if asset_class_name.lower() in ("xstock", "tokenized_equity"):
        return "252-day annualized"
    return "365-day annualized (24/7)"


# ---------------------------------------------------------------------------
# Strategy status formatter
# ---------------------------------------------------------------------------

@dataclass
class StrategyStatus:
    """Formatted strategy status for dashboard display."""

    name: str
    total_trades: int
    raw_win_rate: float
    wilson_lb: float
    wilson_tier: str
    profit_factor: float
    deployable: bool
    deploy_reason: str
    sharpe: Optional[float] = None
    live_sharpe_estimate: Optional[float] = None
    sortino: Optional[float] = None
    max_drawdown: Optional[float] = None

    def to_display_dict(self) -> Dict[str, Any]:
        """Return dict formatted for dashboard rendering."""
        d: Dict[str, Any] = {
            "name": self.name,
            "trades": self.total_trades,
            "confidence_score": round(self.wilson_lb, 3),
            "confidence_tier": self.wilson_tier,
            "raw_win_rate": round(self.raw_win_rate, 3),
            "profit_factor": round(self.profit_factor, 2),
            "deployable": self.deployable,
            "status_reason": self.deploy_reason,
            "progress_pct": min(100, int(self.total_trades / 30 * 100)) if self.total_trades < 30 else 100,
        }
        if self.sharpe is not None:
            d["sharpe"] = round(self.sharpe, 2)
            d["sharpe_tier"] = classify_metric("sharpe", self.sharpe).value
            d["live_sharpe_estimate"] = round(estimate_live_sharpe(self.sharpe), 2)
        if self.sortino is not None:
            d["sortino"] = round(self.sortino, 2)
            d["sortino_tier"] = classify_metric("sortino", self.sortino).value
        if self.max_drawdown is not None:
            d["max_drawdown"] = round(self.max_drawdown, 4)
            d["drawdown_tier"] = classify_metric("max_drawdown", self.max_drawdown).value
        return d


def format_strategy_status(
    name: str,
    total_trades: int,
    wins: int,
    gross_profit: float,
    gross_loss: float,
    *,
    sharpe: Optional[float] = None,
    sortino: Optional[float] = None,
    max_drawdown: Optional[float] = None,
) -> StrategyStatus:
    """
    Create a formatted strategy status for dashboard display.

    Replaces "WR Gate: UNVERIFIED" with proper statistical reporting.
    """
    raw_wr = wins / total_trades if total_trades > 0 else 0.0
    wilson_lb_val = wilson_lower_bound(wins, total_trades)
    deployable, reason = is_strategy_deployable(wins, total_trades, gross_profit, gross_loss)
    wilson_tier = get_confidence_tier(wilson_lb_val)
    pf = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    return StrategyStatus(
        name=name,
        total_trades=total_trades,
        raw_win_rate=raw_wr,
        wilson_lb=wilson_lb_val,
        wilson_tier=wilson_tier,
        profit_factor=pf,
        deployable=deployable,
        deploy_reason=reason,
        sharpe=sharpe,
        live_sharpe_estimate=estimate_live_sharpe(sharpe) if sharpe is not None else None,
        sortino=sortino,
        max_drawdown=max_drawdown,
    )
