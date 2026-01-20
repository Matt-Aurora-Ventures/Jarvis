"""
Portfolio Rebalancer - Advanced portfolio rebalancing system.

Features:
- Target allocation definitions with constraints
- Drift detection and calculation
- Multiple rebalancing strategies (threshold, periodic, band)
- Tax-efficient rebalancing with tax lot tracking
- Minimum trade size filters
- Transaction cost optimization
- Trade minimization algorithms

Usage:
    from core.trading.portfolio_rebalancer import (
        PortfolioRebalancer,
        PortfolioConfig,
        TargetAllocation,
        RebalanceStrategy,
    )

    rebalancer = PortfolioRebalancer()

    config = PortfolioConfig(
        name="Main Portfolio",
        target_allocations=[
            TargetAllocation("SOL", 40.0),
            TargetAllocation("ETH", 30.0),
            TargetAllocation("BTC", 20.0),
            TargetAllocation("USDC", 10.0),
        ],
        strategy=RebalanceStrategy.THRESHOLD,
        drift_threshold=5.0,
    )

    current_holdings = {
        "SOL": {"value": 5000.0, "quantity": 50.0, "price": 100.0},
        "ETH": {"value": 2000.0, "quantity": 1.0, "price": 2000.0},
        ...
    }

    drift = rebalancer.calculate_drift(config, current_holdings)
    trades = rebalancer.calculate_trades(config, current_holdings)
    result = await rebalancer.execute_rebalance(config, current_holdings)
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class RebalanceStrategy(Enum):
    """Rebalancing strategy types."""
    THRESHOLD = "threshold"  # Rebalance when drift exceeds threshold
    PERIODIC = "periodic"    # Rebalance on schedule regardless of drift
    BAND = "band"           # Use inner/outer bands for partial rebalancing
    HYBRID = "hybrid"       # Combination of threshold and periodic


class RebalanceStatus(Enum):
    """Rebalance operation status."""
    PENDING = "pending"
    CALCULATING = "calculating"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TargetAllocation:
    """
    Target allocation for an asset in the portfolio.

    Attributes:
        symbol: Asset symbol (e.g., "SOL", "ETH")
        target_percent: Target allocation percentage (0-100)
        min_percent: Minimum allowed allocation
        max_percent: Maximum allowed allocation
        drift_threshold: Per-asset drift threshold for rebalancing
        tax_lot_tracking: Enable tax lot tracking for this asset
        short_term_threshold_days: Days to consider a position short-term for tax purposes
    """
    symbol: str
    target_percent: float
    min_percent: float = 0.0
    max_percent: float = 100.0
    drift_threshold: float = 5.0
    tax_lot_tracking: bool = False
    short_term_threshold_days: int = 365


@dataclass
class TaxLot:
    """
    Tax lot for tracking cost basis and holding periods.

    Attributes:
        symbol: Asset symbol
        quantity: Quantity in this lot
        cost_basis: Cost basis per unit
        acquired_date: Date the lot was acquired
        id: Unique identifier for the lot
    """
    symbol: str
    quantity: float
    cost_basis: float
    acquired_date: datetime
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    @property
    def total_cost(self) -> float:
        """Total cost basis for this lot."""
        return self.quantity * self.cost_basis

    def is_long_term(self, threshold_days: int = 365) -> bool:
        """Check if this lot qualifies for long-term capital gains."""
        holding_period = datetime.now(timezone.utc) - self.acquired_date.replace(tzinfo=timezone.utc)
        return holding_period.days > threshold_days


@dataclass
class RebalanceTrade:
    """
    A trade calculated for rebalancing.

    Attributes:
        symbol: Asset symbol
        side: "buy" or "sell"
        quantity: Quantity to trade
        value: Dollar value of trade
        current_percent: Current allocation percentage
        target_percent: Target allocation percentage
        drift: Drift from target (current - target)
        estimated_fee: Estimated transaction fee
        tax_lots_used: Tax lots to use for sell orders
        wash_sale_warning: Warning if trade may trigger wash sale
    """
    symbol: str
    side: str  # "buy" or "sell"
    quantity: float
    value: float
    current_percent: float
    target_percent: float
    drift: float
    estimated_fee: float = 0.0
    tax_lots_used: List[TaxLot] = field(default_factory=list)
    wash_sale_warning: bool = False
    priority: int = 0


@dataclass
class RebalanceResult:
    """
    Result of a rebalancing operation.

    Attributes:
        id: Unique result identifier
        timestamp: ISO timestamp of operation
        portfolio_value_before: Portfolio value before rebalancing
        portfolio_value_after: Portfolio value after rebalancing
        trades_planned: Number of trades planned
        trades_executed: Number of trades executed
        total_traded_value: Total dollar value traded
        fees_paid: Total fees paid
        drift_before: Maximum drift before rebalancing
        drift_after: Maximum drift after rebalancing
        status: Operation status
        planned_trades: List of planned trades
        executed_trades: List of executed trades
        errors: List of error messages
        dry_run: Whether this was a dry run
    """
    id: str
    timestamp: str
    portfolio_value_before: float
    portfolio_value_after: float
    trades_planned: int
    trades_executed: int
    total_traded_value: float
    fees_paid: float
    drift_before: float
    drift_after: float
    status: RebalanceStatus
    planned_trades: List[RebalanceTrade] = field(default_factory=list)
    executed_trades: List[RebalanceTrade] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    dry_run: bool = False
    duration_seconds: float = 0.0


@dataclass
class PortfolioConfig:
    """
    Portfolio configuration for rebalancing.

    Attributes:
        name: Portfolio name
        target_allocations: List of target allocations
        strategy: Rebalancing strategy
        drift_threshold: Global drift threshold (%)
        min_trade_value: Minimum trade size in USD
        max_single_trade_pct: Maximum single trade as % of portfolio
        rebalance_interval_hours: Hours between periodic rebalances
        inner_band_percent: Inner band for band strategy (rebalance to here)
        outer_band_percent: Outer band for band strategy (trigger at)
        tax_lot_method: Tax lot selection method (FIFO, LIFO, HIFO, TAX_OPTIMAL)
        tax_loss_harvesting: Enable tax loss harvesting
        avoid_wash_sales: Avoid wash sale rule violations
        wash_sale_window_days: Days to check for wash sales
        consider_fees: Factor in transaction fees
    """
    name: str
    target_allocations: List[TargetAllocation]
    strategy: RebalanceStrategy = RebalanceStrategy.THRESHOLD
    drift_threshold: float = 5.0
    min_trade_value: float = 10.0
    max_single_trade_pct: float = 25.0
    rebalance_interval_hours: int = 24
    inner_band_percent: float = 3.0
    outer_band_percent: float = 5.0
    tax_lot_method: str = "FIFO"
    tax_loss_harvesting: bool = False
    avoid_wash_sales: bool = True
    wash_sale_window_days: int = 30
    consider_fees: bool = False

    def __post_init__(self):
        """Validate configuration after initialization."""
        total = sum(a.target_percent for a in self.target_allocations)
        if abs(total - 100.0) > 0.01:
            raise ValueError(
                f"Target allocations must sum to 100%, got {total:.2f}%"
            )


class PortfolioRebalancer:
    """
    Advanced portfolio rebalancer with multiple strategies.

    Supports:
    - Threshold-based rebalancing
    - Periodic rebalancing
    - Band-based rebalancing
    - Tax-efficient rebalancing
    - Trade minimization
    - Transaction cost optimization
    """

    def __init__(self, default_fee_rate: float = 0.001):
        """
        Initialize the rebalancer.

        Args:
            default_fee_rate: Default transaction fee rate (0.001 = 0.1%)
        """
        self.default_fee_rate = default_fee_rate
        self.portfolios: Dict[str, PortfolioConfig] = {}
        self._execution_callback: Optional[Callable] = None

    def set_execution_callback(self, callback: Callable):
        """
        Set callback for executing trades.

        Args:
            callback: Async function that takes a RebalanceTrade and returns result dict
        """
        self._execution_callback = callback

    def calculate_drift(
        self,
        config: PortfolioConfig,
        current_holdings: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calculate portfolio drift from target allocations.

        Args:
            config: Portfolio configuration
            current_holdings: Current holdings dict with format:
                {"SYMBOL": {"value": float, "quantity": float, "price": float}}

        Returns:
            Dict with drift information for each asset and aggregate stats
        """
        # Calculate total portfolio value
        total_value = sum(
            h.get("value", 0.0) for h in current_holdings.values()
        )

        result = {
            "total_value": total_value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Handle empty portfolio
        if total_value == 0:
            result["needs_rebalance"] = False
            result["max_drift"] = 0.0
            result["total_drift"] = 0.0
            for alloc in config.target_allocations:
                result[alloc.symbol] = {
                    "target_percent": alloc.target_percent,
                    "current_percent": 0.0,
                    "drift": -alloc.target_percent,
                    "exceeds_threshold": False,
                }
            return result

        max_drift = 0.0
        total_drift = 0.0

        for alloc in config.target_allocations:
            symbol = alloc.symbol
            holding = current_holdings.get(symbol, {})
            current_value = holding.get("value", 0.0)
            current_percent = (current_value / total_value * 100) if total_value > 0 else 0.0
            drift = current_percent - alloc.target_percent
            exceeds_threshold = abs(drift) > alloc.drift_threshold

            result[symbol] = {
                "target_percent": alloc.target_percent,
                "current_percent": current_percent,
                "current_value": current_value,
                "drift": drift,
                "exceeds_threshold": exceeds_threshold,
            }

            max_drift = max(max_drift, abs(drift))
            total_drift += abs(drift)

        result["max_drift"] = max_drift
        result["total_drift"] = total_drift
        result["needs_rebalance"] = max_drift > config.drift_threshold

        return result

    def should_rebalance(
        self,
        config: PortfolioConfig,
        current_holdings: Dict[str, Dict[str, Any]],
        last_rebalance: Optional[datetime] = None
    ) -> bool:
        """
        Determine if portfolio should be rebalanced based on strategy.

        Args:
            config: Portfolio configuration
            current_holdings: Current holdings
            last_rebalance: Datetime of last rebalance (for periodic strategy)

        Returns:
            True if rebalancing should occur
        """
        drift = self.calculate_drift(config, current_holdings)

        if config.strategy == RebalanceStrategy.THRESHOLD:
            return drift["needs_rebalance"]

        elif config.strategy == RebalanceStrategy.PERIODIC:
            if last_rebalance is None:
                return True
            time_since = datetime.now(timezone.utc) - last_rebalance
            hours_since = time_since.total_seconds() / 3600
            return hours_since >= config.rebalance_interval_hours

        elif config.strategy == RebalanceStrategy.BAND:
            # Check if any asset has breached outer band
            for alloc in config.target_allocations:
                symbol = alloc.symbol
                if symbol in drift and isinstance(drift[symbol], dict):
                    asset_drift = abs(drift[symbol]["drift"])
                    if asset_drift > config.outer_band_percent:
                        return True
            return False

        elif config.strategy == RebalanceStrategy.HYBRID:
            # Rebalance if threshold exceeded OR periodic time reached
            if drift["needs_rebalance"]:
                return True
            if last_rebalance:
                time_since = datetime.now(timezone.utc) - last_rebalance
                hours_since = time_since.total_seconds() / 3600
                if hours_since >= config.rebalance_interval_hours:
                    return True
            return False

        return False

    def calculate_trades(
        self,
        config: PortfolioConfig,
        current_holdings: Dict[str, Dict[str, Any]],
        tax_optimize: bool = False,
        recent_sells: Optional[List[Dict]] = None
    ) -> List[RebalanceTrade]:
        """
        Calculate trades needed to rebalance portfolio.

        Args:
            config: Portfolio configuration
            current_holdings: Current holdings
            tax_optimize: Enable tax-aware lot selection
            recent_sells: Recent sell transactions for wash sale detection

        Returns:
            List of RebalanceTrade objects
        """
        drift = self.calculate_drift(config, current_holdings)
        total_value = drift["total_value"]

        if total_value == 0:
            return []

        trades = []
        recent_sells = recent_sells or []

        for alloc in config.target_allocations:
            symbol = alloc.symbol

            if symbol not in drift or not isinstance(drift[symbol], dict):
                continue

            asset_drift = drift[symbol]["drift"]
            current_value = drift[symbol].get("current_value", 0.0)
            current_percent = drift[symbol]["current_percent"]
            holding = current_holdings.get(symbol, {})
            price = holding.get("price", 0.0)

            # Determine target value based on strategy
            if config.strategy == RebalanceStrategy.BAND:
                # For band strategy, rebalance to inner band, not target
                if asset_drift > config.outer_band_percent:
                    # Over-allocated: bring back to upper inner band
                    target_percent = alloc.target_percent + config.inner_band_percent
                elif asset_drift < -config.outer_band_percent:
                    # Under-allocated: bring up to lower inner band
                    target_percent = alloc.target_percent - config.inner_band_percent
                else:
                    continue  # Within bands, no trade needed
            else:
                target_percent = alloc.target_percent

            target_value = total_value * (target_percent / 100)
            value_diff = target_value - current_value

            # Check if trade meets minimum size
            if abs(value_diff) < config.min_trade_value:
                continue

            # Check asset-level threshold
            if config.strategy == RebalanceStrategy.THRESHOLD:
                if abs(asset_drift) < alloc.drift_threshold:
                    continue

            side = "buy" if value_diff > 0 else "sell"
            quantity = abs(value_diff) / price if price > 0 else 0.0

            # Estimate fee
            estimated_fee = abs(value_diff) * self.default_fee_rate if config.consider_fees else 0.0

            # Handle tax lot selection for sells
            tax_lots_used = []
            wash_sale_warning = False

            if side == "sell" and tax_optimize and "tax_lots" in holding:
                tax_lots_used = self._select_tax_lots(
                    holding["tax_lots"],
                    quantity,
                    price,
                    config.tax_lot_method,
                    config.tax_loss_harvesting
                )

            # Check for wash sale warning
            if side == "buy" and config.avoid_wash_sales:
                for recent in recent_sells:
                    if (recent.get("symbol") == symbol and
                        recent.get("loss") and
                        "date" in recent):
                        days_since = (datetime.now(timezone.utc) - recent["date"]).days
                        if days_since < config.wash_sale_window_days:
                            wash_sale_warning = True
                            break

            trade = RebalanceTrade(
                symbol=symbol,
                side=side,
                quantity=quantity,
                value=abs(value_diff),
                current_percent=current_percent,
                target_percent=target_percent,
                drift=asset_drift,
                estimated_fee=estimated_fee,
                tax_lots_used=tax_lots_used,
                wash_sale_warning=wash_sale_warning,
                priority=int(abs(asset_drift) * 10)
            )

            trades.append(trade)

        # Sort by priority (highest drift first)
        trades.sort(key=lambda t: t.priority, reverse=True)

        return trades

    def _select_tax_lots(
        self,
        tax_lots: List[TaxLot],
        quantity_needed: float,
        current_price: float,
        method: str,
        tax_loss_harvesting: bool
    ) -> List[TaxLot]:
        """
        Select tax lots for a sell order.

        Args:
            tax_lots: Available tax lots
            quantity_needed: Quantity to sell
            current_price: Current market price
            method: Selection method (FIFO, LIFO, HIFO, TAX_OPTIMAL)
            tax_loss_harvesting: Prefer lots with losses

        Returns:
            List of tax lots to use
        """
        if not tax_lots:
            return []

        # Calculate gain/loss for each lot
        lots_with_pnl = []
        for lot in tax_lots:
            pnl = (current_price - lot.cost_basis) * lot.quantity
            lots_with_pnl.append((lot, pnl))

        # Sort based on method
        if tax_loss_harvesting:
            # Prefer lots with losses (lowest PnL first)
            lots_with_pnl.sort(key=lambda x: x[1])
        elif method == "FIFO":
            # First in, first out (oldest first)
            lots_with_pnl.sort(key=lambda x: x[0].acquired_date)
        elif method == "LIFO":
            # Last in, first out (newest first)
            lots_with_pnl.sort(key=lambda x: x[0].acquired_date, reverse=True)
        elif method == "HIFO":
            # Highest in, first out (highest cost basis first)
            lots_with_pnl.sort(key=lambda x: x[0].cost_basis, reverse=True)
        elif method == "TAX_OPTIMAL":
            # Prefer long-term losses, then short-term losses, then long-term gains
            def tax_score(lot_tuple):
                lot, pnl = lot_tuple
                is_long_term = lot.is_long_term()
                is_loss = pnl < 0
                if is_loss and is_long_term:
                    return 0  # Best: long-term loss
                elif is_loss:
                    return 1  # Good: short-term loss
                elif is_long_term:
                    return 2  # OK: long-term gain (lower rate)
                else:
                    return 3  # Worst: short-term gain
            lots_with_pnl.sort(key=tax_score)

        # Select lots until quantity is satisfied
        selected = []
        remaining = quantity_needed

        for lot, _ in lots_with_pnl:
            if remaining <= 0:
                break
            selected.append(lot)
            remaining -= lot.quantity

        return selected

    async def execute_rebalance(
        self,
        config: PortfolioConfig,
        current_holdings: Dict[str, Dict[str, Any]],
        dry_run: bool = False,
        tax_optimize: bool = False
    ) -> RebalanceResult:
        """
        Execute portfolio rebalancing.

        Args:
            config: Portfolio configuration
            current_holdings: Current holdings
            dry_run: If True, don't execute trades, just calculate
            tax_optimize: Enable tax-aware lot selection

        Returns:
            RebalanceResult with outcome details
        """
        result_id = str(uuid.uuid4())[:8]
        start_time = datetime.now(timezone.utc)

        # Calculate drift before
        drift_before = self.calculate_drift(config, current_holdings)

        # Initialize result
        result = RebalanceResult(
            id=result_id,
            timestamp=start_time.isoformat(),
            portfolio_value_before=drift_before["total_value"],
            portfolio_value_after=drift_before["total_value"],
            trades_planned=0,
            trades_executed=0,
            total_traded_value=0.0,
            fees_paid=0.0,
            drift_before=drift_before["max_drift"],
            drift_after=drift_before["max_drift"],
            status=RebalanceStatus.CALCULATING,
            dry_run=dry_run
        )

        try:
            # Calculate trades
            trades = self.calculate_trades(
                config, current_holdings, tax_optimize=tax_optimize
            )
            result.planned_trades = trades
            result.trades_planned = len(trades)

            if dry_run:
                result.status = RebalanceStatus.COMPLETED
                result.duration_seconds = (
                    datetime.now(timezone.utc) - start_time
                ).total_seconds()
                logger.info(f"Dry run: {len(trades)} trades planned")
                return result

            if not trades:
                result.status = RebalanceStatus.COMPLETED
                result.duration_seconds = (
                    datetime.now(timezone.utc) - start_time
                ).total_seconds()
                logger.info("No trades needed")
                return result

            # Execute trades
            result.status = RebalanceStatus.EXECUTING
            total_fees = 0.0
            total_value = 0.0

            for trade in trades:
                try:
                    if self._execution_callback:
                        exec_result = await self._execution_callback(trade)

                        if exec_result.get("success"):
                            result.trades_executed += 1
                            result.executed_trades.append(trade)
                            total_value += exec_result.get("value", trade.value)
                            total_fees += exec_result.get("fee", trade.estimated_fee)
                        else:
                            result.errors.append(
                                f"{trade.symbol}: {exec_result.get('error', 'Unknown error')}"
                            )
                    else:
                        # Simulated execution
                        result.trades_executed += 1
                        result.executed_trades.append(trade)
                        total_value += trade.value
                        total_fees += trade.estimated_fee

                except Exception as e:
                    result.errors.append(f"{trade.symbol}: {str(e)}")
                    logger.error(f"Error executing trade for {trade.symbol}: {e}")

            result.total_traded_value = total_value
            result.fees_paid = total_fees

            # Calculate drift after (simulated for now)
            # In a real scenario, you'd fetch updated holdings
            result.drift_after = result.drift_before * (
                1 - result.trades_executed / max(result.trades_planned, 1)
            )

            result.status = RebalanceStatus.COMPLETED

        except Exception as e:
            result.status = RebalanceStatus.FAILED
            result.errors.append(str(e))
            logger.error(f"Rebalancing failed: {e}")

        result.duration_seconds = (
            datetime.now(timezone.utc) - start_time
        ).total_seconds()

        logger.info(
            f"Rebalancing complete: {result.trades_executed}/{result.trades_planned} trades, "
            f"drift {result.drift_before:.1f}% -> {result.drift_after:.1f}%"
        )

        return result


# Singleton instance
_rebalancer: Optional[PortfolioRebalancer] = None


def get_portfolio_rebalancer() -> PortfolioRebalancer:
    """Get singleton portfolio rebalancer instance."""
    global _rebalancer
    if _rebalancer is None:
        _rebalancer = PortfolioRebalancer()
    return _rebalancer


__all__ = [
    "PortfolioRebalancer",
    "PortfolioConfig",
    "TargetAllocation",
    "TaxLot",
    "RebalanceTrade",
    "RebalanceResult",
    "RebalanceStrategy",
    "RebalanceStatus",
    "get_portfolio_rebalancer",
]
