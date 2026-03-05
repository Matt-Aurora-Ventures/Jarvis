"""
Trading Pipeline - Wires event detection to execution through all phases.

The pipeline implements the correct execution order:

    Event Detected
        -> Asset Class Identified
        -> Cost Check (is this tradeable?)
        -> Strategy Router (Thompson Sampling selects strategy)
        -> Position Sizing (ATR + Kelly)
        -> Exit Management (ATR trailing + volume confirmation)
        -> Execute or Reject

This is NOT a traditional "signal -> trade" pipeline. The event is the
primary trigger, not a price signal. Indicators are secondary confirmation.

Usage::

    from core.events.trading_pipeline import TradingPipeline

    pipeline = TradingPipeline(account_balance_usd=10_000)
    result = pipeline.evaluate(market_event)

    if result.action == PipelineAction.ENTER:
        # Execute the trade with result.position_size, result.exit_plan
        pass
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Import all pipeline components with graceful fallback
try:
    from core.events.market_events import (
        MarketEvent,
        MarketEventType,
        EventUrgency,
        precheck_cost,
    )
except ImportError:
    MarketEvent = None  # type: ignore[assignment,misc]
    MarketEventType = None  # type: ignore[assignment,misc]

try:
    from core.data.asset_registry import AssetClass
except ImportError:
    from enum import Enum as _Enum
    class AssetClass(_Enum):  # type: ignore[no-redef]
        NATIVE_SOLANA = "native_solana"
        BAGS_BONDING_CURVE = "bags_bonding_curve"
        BAGS_GRADUATED = "bags_graduated"
        XSTOCK = "xstock"
        MEMECOIN = "memecoin"
        STABLECOIN = "stablecoin"

try:
    from core.trading.fee_model import (
        calculate_trade_cost,
        TradeCost,
        is_trade_viable,
        MINIMUM_EDGE_TO_COST_RATIO,
    )
except ImportError:
    calculate_trade_cost = None  # type: ignore[assignment]

try:
    from core.analytics.strategy_confidence import (
        StrategyRouter,
        is_strategy_deployable,
    )
except ImportError:
    StrategyRouter = None  # type: ignore[assignment,misc]

try:
    from core.trading.position_sizing import (
        calculate_position_size,
        PositionSize,
    )
except ImportError:
    calculate_position_size = None  # type: ignore[assignment]
    PositionSize = None  # type: ignore[assignment,misc]

try:
    from core.trading.exits import (
        calculate_atr,
        calculate_atr_trailing_stop,
        should_exit,
        get_profit_floor,
        TIERED_EXIT_PLAN,
        calculate_tiered_stops,
    )
except ImportError:
    calculate_atr = None  # type: ignore[assignment]

try:
    from core.trading.bags_strategy import (
        BagsCurveAnalyzer,
        BagsSignal,
        should_use_indicator,
    )
except ImportError:
    BagsCurveAnalyzer = None  # type: ignore[assignment,misc]

try:
    from core.trading.xstock_strategy import (
        is_market_hours,
        get_oracle_status,
        OracleStatus,
    )
except ImportError:
    is_market_hours = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Pipeline types
# ---------------------------------------------------------------------------

class PipelineAction(Enum):
    """What the pipeline recommends."""

    ENTER = "enter"         # Open a new position
    EXIT = "exit"           # Close an existing position
    SKIP = "skip"           # Don't trade (cost too high, no edge, etc.)
    HOLD = "hold"           # Maintain current position
    REDUCE = "reduce"       # Partial exit (tiered)


class RejectionReason(Enum):
    """Why a trade was rejected."""

    COST_TOO_HIGH = "cost_too_high"
    INSUFFICIENT_EDGE = "insufficient_edge"
    NO_STRATEGY = "no_strategy"
    ASSET_CLASS_UNKNOWN = "asset_class_unknown"
    MARKET_CLOSED = "market_closed"
    ORACLE_STALE = "oracle_stale"
    INVALID_INDICATOR = "invalid_indicator"
    POSITION_LIMIT = "position_limit"
    KILL_SWITCH = "kill_switch"
    INSUFFICIENT_DATA = "insufficient_data"
    BAGS_NOT_READY = "bags_not_ready"


@dataclass
class ExitPlan:
    """Pre-computed exit levels for a new position."""

    stop_loss_price: float = 0.0
    take_profit_price: float = 0.0
    trailing_stop_atr_multiplier: float = 4.0

    # Tiered exits
    tiers: List[Dict[str, Any]] = field(default_factory=list)

    # Bags-specific
    graduation_exit: bool = False  # Auto-exit on graduation event

    # Profit floors
    floor_at_100pct: float = 0.50  # Lock 50% gain at 100% unrealized
    floor_at_200pct: float = 1.00  # Lock 100% gain at 200% unrealized
    floor_at_300pct: float = 2.00  # Lock 200% gain at 300% unrealized


@dataclass
class PipelineResult:
    """Complete output of the trading pipeline."""

    action: PipelineAction
    event: Optional[Any] = None  # MarketEvent

    # Strategy
    strategy_id: Optional[str] = None
    strategy_confidence: float = 0.0

    # Position sizing
    position_size: Optional[Any] = None  # PositionSize
    trade_size_usd: float = 0.0

    # Cost analysis
    estimated_cost: Optional[Any] = None  # TradeCost
    round_trip_cost_pct: float = 0.0

    # Exit plan
    exit_plan: Optional[ExitPlan] = None

    # Rejection info
    rejection_reason: Optional[RejectionReason] = None
    rejection_detail: str = ""

    # Timing
    latency_ms: float = 0.0

    # Asset info
    asset_class: Optional[AssetClass] = None
    mint_address: str = ""
    symbol: str = ""

    def __repr__(self) -> str:
        if self.action == PipelineAction.SKIP:
            return f"PipelineResult(SKIP: {self.rejection_reason}, {self.rejection_detail})"
        return (
            f"PipelineResult({self.action.value}, "
            f"strategy={self.strategy_id}, "
            f"size=${self.trade_size_usd:.2f}, "
            f"cost={self.round_trip_cost_pct:.2%})"
        )


# ---------------------------------------------------------------------------
# Trading Pipeline
# ---------------------------------------------------------------------------

class TradingPipeline:
    """
    The core trading pipeline. Processes MarketEvents into trade decisions.

    Architecture:
        Event -> Classify -> Cost Check -> Strategy Select -> Size -> Exit Plan

    The pipeline is stateless per evaluation. State (positions, balances)
    must be injected via parameters.
    """

    def __init__(
        self,
        account_balance_usd: float = 10_000.0,
        strategy_router: Optional[Any] = None,
        dry_run: bool = True,
    ) -> None:
        self._balance = account_balance_usd
        self._router = strategy_router
        self._dry_run = dry_run
        self._evaluations = 0
        self._entries = 0
        self._rejections = 0

    # -- Main entry point -------------------------------------------------------

    def evaluate(
        self,
        event: Any,
        *,
        account_balance_usd: Optional[float] = None,
        trade_size_usd: float = 500.0,
        current_positions: int = 0,
        max_positions: int = 50,
        atr: float = 0.0,
        entry_price: float = 0.0,
        stop_loss_price: float = 0.0,
        pool_liquidity_usd: float = 0.0,
        win_rate: Optional[float] = None,
        avg_win_pct: Optional[float] = None,
        avg_loss_pct: Optional[float] = None,
    ) -> PipelineResult:
        """
        Evaluate a MarketEvent and return a trade decision.

        This runs the full pipeline:
            1. Validate event and asset class
            2. Asset-class-specific gates (market hours, oracle, bags phase)
            3. Cost viability check
            4. Strategy router selection
            5. Position sizing
            6. Exit plan generation
        """
        start = time.time()
        self._evaluations += 1
        balance = account_balance_usd or self._balance

        # Use event data for defaults
        if hasattr(event, 'pool_liquidity_usd') and pool_liquidity_usd == 0:
            pool_liquidity_usd = event.pool_liquidity_usd
        if hasattr(event, 'current_price') and entry_price == 0:
            entry_price = event.current_price

        # Step 1: Validate event
        result = self._validate_event(event, current_positions, max_positions)
        if result is not None:
            result.latency_ms = (time.time() - start) * 1000
            return result

        asset_class = event.asset_class

        # Step 2: Asset-class-specific gates
        result = self._check_asset_gates(event, asset_class)
        if result is not None:
            result.latency_ms = (time.time() - start) * 1000
            return result

        # Step 3: Cost check
        if calculate_trade_cost is not None and asset_class is not None:
            liq = pool_liquidity_usd if pool_liquidity_usd > 0 else 50_000
            cost = calculate_trade_cost(
                asset_class=asset_class,
                pool_liquidity_usd=liq,
                trade_size_usd=trade_size_usd,
            )

            # For events without edge estimates, use cost threshold
            if cost.total_round_trip_pct >= 0.10:
                self._rejections += 1
                return PipelineResult(
                    action=PipelineAction.SKIP,
                    event=event,
                    rejection_reason=RejectionReason.COST_TOO_HIGH,
                    rejection_detail=f"RT cost {cost.total_round_trip_pct:.2%} >= 10% threshold",
                    estimated_cost=cost,
                    round_trip_cost_pct=cost.total_round_trip_pct,
                    asset_class=asset_class,
                    mint_address=getattr(event, 'mint_address', '') or '',
                    latency_ms=(time.time() - start) * 1000,
                )
        else:
            cost = None

        # Step 4: Strategy router
        strategy_id = None
        strategy_confidence = 0.0

        if self._router is not None and hasattr(self._router, 'select_strategy'):
            strategy_id = self._router.select_strategy()
            if strategy_id and hasattr(self._router, 'get_effective_win_rate'):
                strategy_confidence = self._router.get_effective_win_rate(strategy_id)

        if strategy_id is None:
            # Fallback: use event type as strategy selector
            strategy_id = self._default_strategy(event, asset_class)

        # Step 5: Position sizing
        position = None
        if (
            calculate_position_size is not None
            and entry_price > 0
            and balance > 0
            and asset_class is not None
        ):
            sl = stop_loss_price if stop_loss_price > 0 else entry_price * 0.95
            atr_val = atr if atr > 0 else entry_price * 0.03  # 3% fallback ATR
            liq = pool_liquidity_usd if pool_liquidity_usd > 0 else 50_000

            position = calculate_position_size(
                account_balance_usd=balance,
                entry_price=entry_price,
                stop_loss_price=sl,
                atr=atr_val,
                asset_class=asset_class,
                pool_liquidity_usd=liq,
                win_rate=win_rate,
                avg_win_pct=avg_win_pct,
                avg_loss_pct=avg_loss_pct,
            )
            trade_size_usd = position.position_usd

        # Step 6: Exit plan
        exit_plan = self._build_exit_plan(
            event=event,
            asset_class=asset_class,
            entry_price=entry_price,
            atr=atr if atr > 0 else entry_price * 0.03,
            stop_loss_price=stop_loss_price,
        )

        self._entries += 1

        return PipelineResult(
            action=PipelineAction.ENTER,
            event=event,
            strategy_id=strategy_id,
            strategy_confidence=strategy_confidence,
            position_size=position,
            trade_size_usd=trade_size_usd,
            estimated_cost=cost,
            round_trip_cost_pct=cost.total_round_trip_pct if cost else 0.0,
            exit_plan=exit_plan,
            asset_class=asset_class,
            mint_address=getattr(event, 'mint_address', '') or '',
            symbol=getattr(event, 'symbol', '') or '',
            latency_ms=(time.time() - start) * 1000,
        )

    # -- Step implementations ---------------------------------------------------

    def _validate_event(
        self,
        event: Any,
        current_positions: int,
        max_positions: int,
    ) -> Optional[PipelineResult]:
        """Step 1: Basic validation."""
        if event is None:
            return PipelineResult(
                action=PipelineAction.SKIP,
                rejection_reason=RejectionReason.INSUFFICIENT_DATA,
                rejection_detail="No event provided",
            )

        asset_class = getattr(event, 'asset_class', None)
        if asset_class is None:
            return PipelineResult(
                action=PipelineAction.SKIP,
                event=event,
                rejection_reason=RejectionReason.ASSET_CLASS_UNKNOWN,
                rejection_detail="Cannot trade without asset classification",
                mint_address=getattr(event, 'mint_address', '') or '',
            )

        if current_positions >= max_positions:
            return PipelineResult(
                action=PipelineAction.SKIP,
                event=event,
                rejection_reason=RejectionReason.POSITION_LIMIT,
                rejection_detail=f"At max positions: {current_positions}/{max_positions}",
                asset_class=asset_class,
                mint_address=getattr(event, 'mint_address', '') or '',
            )

        return None  # Validation passed

    def _check_asset_gates(
        self,
        event: Any,
        asset_class: Optional[AssetClass],
    ) -> Optional[PipelineResult]:
        """Step 2: Asset-class-specific gates."""
        if asset_class is None:
            return None

        # xStock: market hours gate
        if asset_class == AssetClass.XSTOCK:
            event_time = getattr(event, "timestamp", None)
            if event_time is None:
                event_time = datetime.now(timezone.utc)

            if is_market_hours is not None and not is_market_hours(event_time):
                return PipelineResult(
                    action=PipelineAction.SKIP,
                    event=event,
                    rejection_reason=RejectionReason.MARKET_CLOSED,
                    rejection_detail="US equity markets closed",
                    asset_class=asset_class,
                    mint_address=getattr(event, 'mint_address', '') or '',
                )

            oracle_last_update = None
            event_data = getattr(event, "data", None)
            if isinstance(event_data, dict):
                oracle_last_update = event_data.get("oracle_last_update")

            if oracle_last_update is None:
                return PipelineResult(
                    action=PipelineAction.SKIP,
                    event=event,
                    rejection_reason=RejectionReason.ORACLE_STALE,
                    rejection_detail="Missing oracle timestamp for xStock trade",
                    asset_class=asset_class,
                    mint_address=getattr(event, "mint_address", "") or "",
                )

            if get_oracle_status is not None:
                status = get_oracle_status(oracle_last_update, current_time=event_time)
                if getattr(status, "halted", False):
                    return PipelineResult(
                        action=PipelineAction.SKIP,
                        event=event,
                        rejection_reason=RejectionReason.ORACLE_STALE,
                        rejection_detail="Oracle data stale > 30min, trading halted",
                        asset_class=asset_class,
                        mint_address=getattr(event, 'mint_address', '') or '',
                    )

        # Bags pre-graduation: check that event type is appropriate
        if asset_class == AssetClass.BAGS_BONDING_CURVE:
            event_type = getattr(event, 'event_type', None)
            if MarketEventType is not None and event_type == MarketEventType.PRICE_BREAKOUT:
                return PipelineResult(
                    action=PipelineAction.SKIP,
                    event=event,
                    rejection_reason=RejectionReason.INVALID_INDICATOR,
                    rejection_detail="Indicator-based signals invalid on bonding curves",
                    asset_class=asset_class,
                    mint_address=getattr(event, 'mint_address', '') or '',
                )

        return None  # All gates passed

    def _default_strategy(
        self,
        event: Any,
        asset_class: Optional[AssetClass],
    ) -> str:
        """Fallback strategy selection based on event type and asset class."""
        event_type = getattr(event, 'event_type', None)

        if event_type is not None and MarketEventType is not None:
            if event_type == MarketEventType.TOKEN_LAUNCH:
                return "bags_fresh_snipe"
            if event_type == MarketEventType.GRADUATION:
                return "bags_momentum"
            if event_type == MarketEventType.VOLUME_EXPLOSION:
                if asset_class == AssetClass.MEMECOIN:
                    return "volume_spike"
                return "momentum"

        if asset_class == AssetClass.NATIVE_SOLANA:
            return "bluechip_trend_follow"
        if asset_class == AssetClass.XSTOCK:
            return "xstock_intraday"
        if asset_class == AssetClass.BAGS_BONDING_CURVE:
            return "pump_fresh_tight"
        if asset_class == AssetClass.BAGS_GRADUATED:
            return "bags_dip_buyer"
        if asset_class == AssetClass.MEMECOIN:
            return "meme_classic"

        return "momentum"

    def _build_exit_plan(
        self,
        event: Any,
        asset_class: Optional[AssetClass],
        entry_price: float,
        atr: float,
        stop_loss_price: float,
    ) -> ExitPlan:
        """Step 6: Build the exit plan based on asset class and volatility."""
        plan = ExitPlan()

        if entry_price <= 0:
            return plan

        # Default stop loss
        if stop_loss_price > 0:
            plan.stop_loss_price = stop_loss_price
        elif atr > 0:
            plan.stop_loss_price = entry_price - (atr * 3)
        else:
            plan.stop_loss_price = entry_price * 0.95

        # Default TP at 3:1 risk/reward
        risk = entry_price - plan.stop_loss_price
        plan.take_profit_price = entry_price + (risk * 3) if risk > 0 else entry_price * 1.15

        # Asset-class-specific adjustments
        if asset_class == AssetClass.BAGS_BONDING_CURVE:
            plan.graduation_exit = True
            plan.trailing_stop_atr_multiplier = 5.0  # Wider for extreme volatility

        elif asset_class == AssetClass.BAGS_GRADUATED:
            plan.trailing_stop_atr_multiplier = 5.0  # Still very volatile post-grad

        elif asset_class == AssetClass.XSTOCK:
            plan.trailing_stop_atr_multiplier = 3.5  # Tighter for equity-like behavior

        elif asset_class == AssetClass.NATIVE_SOLANA:
            plan.trailing_stop_atr_multiplier = 4.0  # Standard crypto

        # Tiered exits (if ATR available)
        if atr > 0 and calculate_tiered_stops is not None:
            high_since_entry = entry_price  # Will be updated in real-time
            plan.tiers = calculate_tiered_stops(
                entry_price=entry_price,
                current_high=high_since_entry,
                atr=atr,
            )

        return plan

    # -- Stats ------------------------------------------------------------------

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "evaluations": self._evaluations,
            "entries": self._entries,
            "rejections": self._rejections,
            "entry_rate": self._entries / self._evaluations if self._evaluations > 0 else 0,
            "dry_run": self._dry_run,
            "balance": self._balance,
        }
