"""Position manager for Jupiter Perps — tracks open positions and generates exit intents.

Seven exit triggers run every price tick:
    1. Hard stop loss          (-5% default)
    2. Take profit             (+10% default)
    3. Trailing stop           (8% from peak, activates at +3%)
    4. Time decay              (48h max hold)
    5. Funding bleed           (2% of notional in borrow fees)
    6. Signal reversal         (opposite AI signal with decent confidence)
    7. Emergency stop          (-15% instant close + operator alert)

Every trigger is a pure function: (TrackedPosition, config) -> ExitDecision | None.
The position manager itself is stateful but contains zero IO — all side effects
(intent queuing, price fetching) happen in the caller (runner.py).
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class PositionManagerConfig:
    stop_loss_pct: float = 5.0
    take_profit_pct: float = 10.0
    trailing_stop_pct: float = 8.0
    trailing_activate_pct: float = 3.0
    max_hold_hours: float = 48.0
    max_borrow_pct: float = 2.0
    emergency_stop_pct: float = 15.0

    @classmethod
    def from_env(cls) -> PositionManagerConfig:
        return cls(
            stop_loss_pct=float(os.environ.get("PERPS_STOP_LOSS_PCT", "5.0")),
            take_profit_pct=float(os.environ.get("PERPS_TAKE_PROFIT_PCT", "10.0")),
            trailing_stop_pct=float(os.environ.get("PERPS_TRAILING_STOP_PCT", "8.0")),
            trailing_activate_pct=float(os.environ.get("PERPS_TRAILING_ACTIVATE_PCT", "3.0")),
            max_hold_hours=float(os.environ.get("PERPS_MAX_HOLD_HOURS", "48")),
            max_borrow_pct=float(os.environ.get("PERPS_MAX_BORROW_PCT", "2.0")),
            emergency_stop_pct=float(os.environ.get("PERPS_EMERGENCY_STOP_PCT", "15.0")),
        )


# ---------------------------------------------------------------------------
# Tracked position
# ---------------------------------------------------------------------------


@dataclass
class TrackedPosition:
    """In-memory representation of an open leveraged position."""

    pda: str
    idempotency_key: str
    market: str
    side: str                      # "long" | "short"
    size_usd: float                # notional (collateral * leverage)
    collateral_usd: float
    leverage: float
    entry_price: float
    opened_at: float               # time.time() epoch
    peak_price: float              # best favourable price seen
    current_price: float
    source: str                    # signal source that opened this
    cumulative_borrow_usd: float = 0.0

    @property
    def hold_hours(self) -> float:
        return (time.time() - self.opened_at) / 3600.0

    @property
    def unrealized_pnl_pct(self) -> float:
        """Percentage P&L based on current vs entry price."""
        if self.entry_price <= 0:
            return 0.0
        if self.side == "long":
            raw = (self.current_price - self.entry_price) / self.entry_price
        else:
            raw = (self.entry_price - self.current_price) / self.entry_price
        return raw * self.leverage * 100.0  # as percentage points

    @property
    def unrealized_pnl_usd(self) -> float:
        return self.collateral_usd * (self.unrealized_pnl_pct / 100.0)

    @property
    def peak_pnl_pct(self) -> float:
        """P&L at peak price."""
        if self.entry_price <= 0:
            return 0.0
        if self.side == "long":
            raw = (self.peak_price - self.entry_price) / self.entry_price
        else:
            raw = (self.entry_price - self.peak_price) / self.entry_price
        return raw * self.leverage * 100.0

    @property
    def drawdown_from_peak_pct(self) -> float:
        """How far current price has dropped from peak (always >= 0)."""
        return max(0.0, self.peak_pnl_pct - self.unrealized_pnl_pct)


# ---------------------------------------------------------------------------
# Exit decision
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExitDecision:
    """Recommendation to close or reduce a position."""

    idempotency_key: str
    position_pda: str
    market: str
    trigger: str          # "stop_loss", "take_profit", "trailing_stop", etc.
    action: str           # "close" | "reduce_50"
    urgency: str          # "normal" | "urgent"
    reason: str

    @property
    def is_urgent(self) -> bool:
        return self.urgency == "urgent"


# ---------------------------------------------------------------------------
# Exit trigger functions (pure — no side effects)
# ---------------------------------------------------------------------------


def _check_emergency_stop(pos: TrackedPosition, cfg: PositionManagerConfig) -> ExitDecision | None:
    if pos.unrealized_pnl_pct <= -cfg.emergency_stop_pct:
        return ExitDecision(
            idempotency_key=pos.idempotency_key,
            position_pda=pos.pda,
            market=pos.market,
            trigger="emergency_stop",
            action="close",
            urgency="urgent",
            reason=f"Emergency stop: {pos.unrealized_pnl_pct:+.1f}% <= -{cfg.emergency_stop_pct}%",
        )
    return None


def _check_stop_loss(pos: TrackedPosition, cfg: PositionManagerConfig) -> ExitDecision | None:
    if pos.unrealized_pnl_pct <= -cfg.stop_loss_pct:
        return ExitDecision(
            idempotency_key=pos.idempotency_key,
            position_pda=pos.pda,
            market=pos.market,
            trigger="stop_loss",
            action="close",
            urgency="urgent",
            reason=f"Stop loss: {pos.unrealized_pnl_pct:+.1f}% <= -{cfg.stop_loss_pct}%",
        )
    return None


def _check_take_profit(pos: TrackedPosition, cfg: PositionManagerConfig) -> ExitDecision | None:
    if pos.unrealized_pnl_pct >= cfg.take_profit_pct:
        return ExitDecision(
            idempotency_key=pos.idempotency_key,
            position_pda=pos.pda,
            market=pos.market,
            trigger="take_profit",
            action="close",
            urgency="normal",
            reason=f"Take profit: {pos.unrealized_pnl_pct:+.1f}% >= +{cfg.take_profit_pct}%",
        )
    return None


def _check_trailing_stop(pos: TrackedPosition, cfg: PositionManagerConfig) -> ExitDecision | None:
    # Only active after position has reached activation threshold
    if pos.peak_pnl_pct < cfg.trailing_activate_pct:
        return None

    if pos.drawdown_from_peak_pct >= cfg.trailing_stop_pct:
        return ExitDecision(
            idempotency_key=pos.idempotency_key,
            position_pda=pos.pda,
            market=pos.market,
            trigger="trailing_stop",
            action="close",
            urgency="normal",
            reason=(
                f"Trailing stop: peak P&L {pos.peak_pnl_pct:+.1f}%, "
                f"current {pos.unrealized_pnl_pct:+.1f}%, "
                f"drawdown {pos.drawdown_from_peak_pct:.1f}% >= {cfg.trailing_stop_pct}%"
            ),
        )
    return None


def _check_time_decay(pos: TrackedPosition, cfg: PositionManagerConfig) -> ExitDecision | None:
    if pos.hold_hours >= cfg.max_hold_hours:
        return ExitDecision(
            idempotency_key=pos.idempotency_key,
            position_pda=pos.pda,
            market=pos.market,
            trigger="time_decay",
            action="close",
            urgency="normal",
            reason=f"Time decay: held {pos.hold_hours:.1f}h >= {cfg.max_hold_hours}h",
        )
    return None


def _check_funding_bleed(pos: TrackedPosition, cfg: PositionManagerConfig) -> ExitDecision | None:
    max_borrow = pos.size_usd * (cfg.max_borrow_pct / 100.0)
    if pos.cumulative_borrow_usd >= max_borrow:
        return ExitDecision(
            idempotency_key=pos.idempotency_key,
            position_pda=pos.pda,
            market=pos.market,
            trigger="funding_bleed",
            action="close",
            urgency="normal",
            reason=(
                f"Funding bleed: ${pos.cumulative_borrow_usd:.2f} borrow fees "
                f">= {cfg.max_borrow_pct}% of ${pos.size_usd:.0f} notional"
            ),
        )
    return None


# Ordered by severity — emergency first, then stop loss, etc.
_EXIT_TRIGGERS = [
    _check_emergency_stop,
    _check_stop_loss,
    _check_take_profit,
    _check_trailing_stop,
    _check_time_decay,
    _check_funding_bleed,
]


# ---------------------------------------------------------------------------
# Position Manager
# ---------------------------------------------------------------------------


class PositionManager:
    """Tracks open leveraged positions and generates exit decisions.

    Pure in-memory state. All IO (price feeds, intent queuing, alerts)
    happens in the caller — this class has zero side effects.
    """

    def __init__(self, config: PositionManagerConfig | None = None) -> None:
        self._config = config or PositionManagerConfig.from_env()
        self._positions: dict[str, TrackedPosition] = {}  # keyed by idempotency_key
        self._daily_pnl_usd: float = 0.0
        self._daily_pnl_reset_day: int = 0
        self._daily_trade_count: int = 0
        self._pending_exits: set[str] = set()  # keys with exit in flight

    @property
    def config(self) -> PositionManagerConfig:
        return self._config

    # --- Registration ---

    def register_open(
        self,
        idempotency_key: str,
        market: str,
        side: str,
        size_usd: float,
        collateral_usd: float,
        leverage: float,
        entry_price: float,
        source: str,
        pda: str = "",
    ) -> None:
        """Register a newly opened position for tracking."""
        now = time.time()
        pos = TrackedPosition(
            pda=pda or idempotency_key,
            idempotency_key=idempotency_key,
            market=market,
            side=side,
            size_usd=size_usd,
            collateral_usd=collateral_usd,
            leverage=leverage,
            entry_price=entry_price,
            opened_at=now,
            peak_price=entry_price,
            current_price=entry_price,
            source=source,
        )
        self._positions[idempotency_key] = pos
        self._check_daily_reset()
        self._daily_trade_count += 1
        log.info(
            "Position registered: %s %s %s %.0fx $%.0f @ %.4f [%s]",
            idempotency_key[:12], market, side, leverage, size_usd, entry_price, source,
        )

    # --- Price updates + exit checks ---

    def update_price(self, market: str, price: float) -> list[ExitDecision]:
        """Update price for all positions in a market and check exit triggers.

        Returns a list of ExitDecision — one per position that should be closed.
        Only the first (highest severity) trigger fires per position.
        """
        exits: list[ExitDecision] = []

        for key, pos in list(self._positions.items()):
            if pos.market != market:
                continue
            if key in self._pending_exits:
                continue

            # Update current price
            pos.current_price = price

            # Fill in entry price on first real price tick (registered with 0.0)
            if pos.entry_price <= 0.0 and price > 0:
                pos.entry_price = price
                pos.peak_price = price
                log.info("Entry price filled: %s %s @ %.4f", key[:12], market, price)
                continue  # Don't check exits on the same tick we set entry price

            # Update peak price (directional)
            if pos.side == "long":
                pos.peak_price = max(pos.peak_price, price)
            else:
                pos.peak_price = min(pos.peak_price, price)

            # Run exit triggers in severity order — first match wins
            for trigger_fn in _EXIT_TRIGGERS:
                decision = trigger_fn(pos, self._config)
                if decision is not None:
                    exits.append(decision)
                    self._pending_exits.add(key)
                    log.info("Exit triggered: %s %s — %s", key[:12], decision.trigger, decision.reason)
                    break

        return exits

    def update_borrow_fees(self) -> None:
        """Recalculate cumulative borrow fees for all open positions.

        Uses the Jupiter dual-slope borrow model. Called periodically (every 60s).
        """
        try:
            from core.backtesting.jupiter_fee_adapter import calculate_borrow_fee  # noqa: PLC0415
        except ImportError:
            return

        for pos in self._positions.values():
            pos.cumulative_borrow_usd = calculate_borrow_fee(
                notional_usd=pos.size_usd,
                hours_held=pos.hold_hours,
                avg_utilization=0.65,
            )

    def check_signal_reversal(self, asset: str, direction: str, confidence: float) -> list[ExitDecision]:
        """Check if an AI signal reverses any open position (trigger 6).

        Args:
            asset: e.g. "SOL"
            direction: "long" or "short"
            confidence: signal confidence (0.0–1.0)
        """
        exits: list[ExitDecision] = []
        market = f"{asset}-USD"

        for key, pos in list(self._positions.items()):
            if pos.market != market:
                continue
            if key in self._pending_exits:
                continue

            # Signal opposes position direction
            is_reversal = (
                (pos.side == "long" and direction == "short")
                or (pos.side == "short" and direction == "long")
            )

            if is_reversal and confidence >= 0.50:
                decision = ExitDecision(
                    idempotency_key=key,
                    position_pda=pos.pda,
                    market=pos.market,
                    trigger="signal_reversal",
                    action="close",
                    urgency="normal",
                    reason=f"Signal reversal: {direction} signal at {confidence:.0%} opposes {pos.side} position",
                )
                exits.append(decision)
                self._pending_exits.add(key)
                log.info("Signal reversal exit: %s — %s", key[:12], decision.reason)

        return exits

    # --- Position lifecycle ---

    def mark_closed(self, idempotency_key: str) -> TrackedPosition | None:
        """Remove a position from tracking after successful close. Returns the closed position."""
        self._pending_exits.discard(idempotency_key)
        pos = self._positions.pop(idempotency_key, None)
        if pos is not None:
            # Track daily P&L
            self._update_daily_pnl(pos.unrealized_pnl_usd)
            log.info(
                "Position closed: %s %s P&L %+.2f USD",
                idempotency_key[:12], pos.market, pos.unrealized_pnl_usd,
            )
        return pos

    def cancel_pending_exit(self, idempotency_key: str) -> None:
        """Cancel a pending exit (e.g., if close intent failed)."""
        self._pending_exits.discard(idempotency_key)

    # --- Queries ---

    def get_open_positions(self) -> list[TrackedPosition]:
        return list(self._positions.values())

    def get_position_count(self) -> int:
        return len(self._positions)

    def get_total_exposure_usd(self) -> float:
        return sum(p.size_usd for p in self._positions.values())

    def get_asset_exposure_usd(self, market: str) -> float:
        return sum(p.size_usd for p in self._positions.values() if p.market == market)

    def has_position(self, market: str, side: str) -> bool:
        """Check if a position exists for the given market and side."""
        return any(
            p.market == market and p.side == side
            for p in self._positions.values()
        )

    def get_daily_pnl_usd(self) -> float:
        """Get today's realized + unrealized P&L."""
        self._check_daily_reset()
        unrealized = sum(p.unrealized_pnl_usd for p in self._positions.values())
        return self._daily_pnl_usd + unrealized

    def get_trades_opened_today(self) -> int:
        """Get count of opened positions for current UTC day."""
        self._check_daily_reset()
        return self._daily_trade_count

    # --- On-chain TP/SL trigger price computation ---

    # Jupiter close fee: 0.06% (6 bps) base + estimated price impact
    _CLOSE_FEE_BPS: float = 8.0  # 6 bps base + ~2 bps estimated impact buffer

    def compute_tpsl_trigger_prices(self, idempotency_key: str) -> list[dict[str, Any]]:
        """Compute stop-loss and take-profit trigger prices for on-chain TP/SL orders.

        Returns a list of dicts with keys:
            position_pda, trigger_price, trigger_above_threshold, kind ("stop_loss" | "take_profit")

        TP trigger is adjusted outward to account for Jupiter's close fee (0.06% base
        + estimated impact), ensuring realized P&L meets the target after fees.
        SL trigger is NOT adjusted — we want it to fire at the raw loss threshold.

        For longs:
            SL triggers when price <= sl_price (trigger_above_threshold=False)
            TP triggers when price >= tp_price (trigger_above_threshold=True)
        For shorts:
            SL triggers when price >= sl_price (trigger_above_threshold=True)
            TP triggers when price <= tp_price (trigger_above_threshold=False)
        """
        pos = self._positions.get(idempotency_key)
        if pos is None or pos.entry_price <= 0:
            return []

        results: list[dict[str, Any]] = []
        cfg = self._config

        # P&L formula: pnl_pct = (price_move / entry) * leverage * 100
        # So price_move = pnl_pct * entry / (leverage * 100)
        sl_delta = cfg.stop_loss_pct * pos.entry_price / (pos.leverage * 100.0)
        tp_delta = cfg.take_profit_pct * pos.entry_price / (pos.leverage * 100.0)

        # Fee compensation: push TP trigger outward so realized P&L still meets target.
        # Close fee is charged on notional, which translates to a price delta.
        fee_delta = pos.entry_price * (self._CLOSE_FEE_BPS / 10_000.0)

        if pos.side == "long":
            sl_price = pos.entry_price - sl_delta
            tp_price = pos.entry_price + tp_delta + fee_delta  # push TP higher to cover fees
            results.append({
                "position_pda": pos.pda,
                "trigger_price": sl_price,
                "trigger_above_threshold": False,  # trigger when price drops to SL
                "kind": "stop_loss",
            })
            results.append({
                "position_pda": pos.pda,
                "trigger_price": tp_price,
                "trigger_above_threshold": True,  # trigger when price rises to TP
                "kind": "take_profit",
            })
        else:
            sl_price = pos.entry_price + sl_delta
            tp_price = pos.entry_price - tp_delta - fee_delta  # push TP lower to cover fees
            results.append({
                "position_pda": pos.pda,
                "trigger_price": sl_price,
                "trigger_above_threshold": True,  # trigger when price rises to SL (bad for short)
                "kind": "stop_loss",
            })
            results.append({
                "position_pda": pos.pda,
                "trigger_price": tp_price,
                "trigger_above_threshold": False,  # trigger when price drops to TP (good for short)
                "kind": "take_profit",
            })

        log.info(
            "TP/SL prices for %s %s %s: SL=%.4f TP=%.4f (entry=%.4f, %sx, fee_adj=%.4f)",
            idempotency_key[:12], pos.market, pos.side,
            sl_price, tp_price, pos.entry_price, pos.leverage, fee_delta,
        )
        return results

    # --- Internal helpers ---

    def _update_daily_pnl(self, realized_pnl: float) -> None:
        self._check_daily_reset()
        self._daily_pnl_usd += realized_pnl

    def _check_daily_reset(self) -> None:
        import datetime  # noqa: PLC0415
        today = datetime.datetime.now(datetime.timezone.utc).toordinal()
        if today != self._daily_pnl_reset_day:
            self._daily_pnl_usd = 0.0
            self._daily_trade_count = 0
            self._daily_pnl_reset_day = today
