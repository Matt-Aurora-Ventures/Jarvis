"""
Exit Intent System
==================

Manages exit strategies (TP ladder, stop loss, time stops) for LUT micro-alpha
and Jupiter Perps positions. Persists intents to disk for daemon enforcement.

Critical Safety Guarantee:
- The moment a buy fills, the exit intent MUST be persisted to disk
- Daemon enforcement checks intents every poll cycle
- Time stops trigger even if price targets aren't hit

Usage:
    from core.exit_intents import create_spot_intent, persist_intent, load_active_intents

    # On entry
    intent = create_spot_intent(position_id, mint, entry_price, quantity)
    persist_intent(intent)

    # Daemon loop
    intents = load_active_intents()
    for intent in intents:
        actions = check_intent_triggers(intent, current_price)
        for action in actions:
            execute_action(intent, action)
"""

from __future__ import annotations

import fcntl
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core import strategy_scores

logger = logging.getLogger(__name__)


def _merge_notes(*parts: str) -> str:
    cleaned = [part.strip() for part in parts if part and part.strip()]
    return "; ".join(cleaned)


def _extract_strategy_id(notes: str) -> Optional[str]:
    if not notes:
        return None
    match = re.search(r"strategy=([A-Za-z0-9_-]+)", notes)
    if match:
        return match.group(1)
    return None


def _record_strategy_execution_failure(intent: "ExitIntent", error: str) -> None:
    strategy_id = _extract_strategy_id(intent.notes)
    if not strategy_id:
        return
    strategy_scores.update_score(
        strategy_id,
        0.0,
        execution_error=True,
        reason=error,
        metadata={"symbol": intent.symbol, "position_id": intent.position_id},
    )

# State file locations
TRADING_DIR = Path.home() / ".lifeos" / "trading"
INTENTS_FILE = TRADING_DIR / "exit_intents.json"
RELIABILITY_FILE = TRADING_DIR / "execution_reliability.json"


class IntentStatus(Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    PARTIAL = "partial"  # Some TPs filled but position still open


class ExitAction(Enum):
    TRIGGER_TP = "trigger_tp"
    TRIGGER_SL = "trigger_sl"
    TRIGGER_TIME_STOP = "trigger_time_stop"
    ADJUST_SL_TO_BREAKEVEN = "adjust_sl_to_breakeven"
    SENTIMENT_EXIT = "sentiment_exit"
    TRAILING_STOP_UPDATE = "trailing_stop_update"


@dataclass
class TakeProfit:
    """Take profit level configuration."""
    level: int                     # TP1, TP2, etc.
    price: float                   # Target price
    size_pct: float                # % of original position to sell
    filled: bool = False
    fill_price: Optional[float] = None
    fill_timestamp: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TakeProfit":
        return cls(**data)


@dataclass
class StopLoss:
    """Stop loss configuration with adjustment tracking."""
    price: float                   # Stop price
    size_pct: float = 100.0        # % of remaining position
    adjusted: bool = False         # True after moved to breakeven
    original_price: Optional[float] = None  # Original SL before adjustment

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StopLoss":
        return cls(**data)


@dataclass
class TimeStop:
    """Time-based exit trigger."""
    deadline_timestamp: float      # When to trigger
    action: str = "exit_fully"     # "exit_fully" or "reduce_to_runner"
    triggered: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TimeStop":
        return cls(**data)


@dataclass
class TrailingStop:
    """Trailing stop configuration."""
    active: bool = False
    trail_pct: float = 0.05        # 5% trail
    highest_price: float = 0.0     # Highest price seen since TP1
    current_stop: float = 0.0      # Current trailing stop price

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TrailingStop":
        return cls(**data)


@dataclass
class ExitIntent:
    """Complete exit strategy for a position."""
    id: str
    position_id: str
    position_type: str             # "spot" or "perps"
    token_mint: str
    symbol: str
    entry_price: float
    entry_timestamp: float
    original_quantity: float
    remaining_quantity: float

    take_profits: List[TakeProfit]
    stop_loss: StopLoss
    time_stop: TimeStop
    trailing_stop: TrailingStop

    status: str = "active"         # IntentStatus value
    sentiment_invalidated: bool = False

    # Tracking
    last_check_timestamp: float = 0.0
    last_check_price: float = 0.0
    enforcement_attempts: int = 0
    enforcement_failures: int = 0

    # Paper trading flag
    is_paper: bool = True

    # Notes for logging
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "id": self.id,
            "position_id": self.position_id,
            "position_type": self.position_type,
            "token_mint": self.token_mint,
            "symbol": self.symbol,
            "entry_price": self.entry_price,
            "entry_timestamp": self.entry_timestamp,
            "original_quantity": self.original_quantity,
            "remaining_quantity": self.remaining_quantity,
            "take_profits": [tp.to_dict() for tp in self.take_profits],
            "stop_loss": self.stop_loss.to_dict(),
            "time_stop": self.time_stop.to_dict(),
            "trailing_stop": self.trailing_stop.to_dict(),
            "status": self.status,
            "sentiment_invalidated": self.sentiment_invalidated,
            "last_check_timestamp": self.last_check_timestamp,
            "last_check_price": self.last_check_price,
            "enforcement_attempts": self.enforcement_attempts,
            "enforcement_failures": self.enforcement_failures,
            "is_paper": self.is_paper,
            "notes": self.notes,
        }
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExitIntent":
        return cls(
            id=data["id"],
            position_id=data["position_id"],
            position_type=data.get("position_type", "spot"),
            token_mint=data["token_mint"],
            symbol=data.get("symbol", ""),
            entry_price=data["entry_price"],
            entry_timestamp=data["entry_timestamp"],
            original_quantity=data["original_quantity"],
            remaining_quantity=data["remaining_quantity"],
            take_profits=[TakeProfit.from_dict(tp) for tp in data["take_profits"]],
            stop_loss=StopLoss.from_dict(data["stop_loss"]),
            time_stop=TimeStop.from_dict(data["time_stop"]),
            trailing_stop=TrailingStop.from_dict(data.get("trailing_stop", {})),
            status=data.get("status", "active"),
            sentiment_invalidated=data.get("sentiment_invalidated", False),
            last_check_timestamp=data.get("last_check_timestamp", 0.0),
            last_check_price=data.get("last_check_price", 0.0),
            enforcement_attempts=data.get("enforcement_attempts", 0),
            enforcement_failures=data.get("enforcement_failures", 0),
            is_paper=data.get("is_paper", True),
            notes=data.get("notes", ""),
        )


# ============================================================================
# Intent Creation
# ============================================================================

def create_spot_intent(
    position_id: str,
    token_mint: str,
    symbol: str,
    entry_price: float,
    quantity: float,
    *,
    is_paper: bool = True,
    strategy_id: str = "",
    notes: str = "",
    # Default TP ladder: 60% @ +8%, 25% @ +18%, 15% @ +40%
    tp1_pct: float = 0.08,
    tp1_size: float = 0.60,
    tp2_pct: float = 0.18,
    tp2_size: float = 0.25,
    tp3_pct: float = 0.40,
    tp3_size: float = 0.15,
    # Stop loss: -9%
    sl_pct: float = 0.09,
    # Time stop: 90 minutes
    time_stop_minutes: int = 90,
) -> ExitIntent:
    """
    Create exit intent for a spot position with default LUT micro-alpha parameters.

    Default Exit Template (High-Risk Momentum Scalp + Runner):
    - TP1: sell 60% at +8%
    - TP2: sell 25% at +18%
    - TP3: sell 15% at +40% (runner)
    - SL: -9% initially
    - Time stop: 90 minutes
    """
    now = time.time()

    take_profits = [
        TakeProfit(level=1, price=entry_price * (1 + tp1_pct), size_pct=tp1_size * 100),
        TakeProfit(level=2, price=entry_price * (1 + tp2_pct), size_pct=tp2_size * 100),
        TakeProfit(level=3, price=entry_price * (1 + tp3_pct), size_pct=tp3_size * 100),
    ]

    stop_loss = StopLoss(
        price=entry_price * (1 - sl_pct),
        size_pct=100.0,
        original_price=entry_price * (1 - sl_pct),
    )

    time_stop = TimeStop(
        deadline_timestamp=now + (time_stop_minutes * 60),
        action="exit_fully",
    )

    trailing_stop = TrailingStop(
        active=False,
        trail_pct=0.05,
        highest_price=entry_price,
    )

    return ExitIntent(
        id=str(uuid.uuid4())[:8],
        position_id=position_id,
        position_type="spot",
        token_mint=token_mint,
        symbol=symbol,
        entry_price=entry_price,
        entry_timestamp=now,
        original_quantity=quantity,
        remaining_quantity=quantity,
        take_profits=take_profits,
        stop_loss=stop_loss,
        time_stop=time_stop,
        trailing_stop=trailing_stop,
        is_paper=is_paper,
        notes=_merge_notes(f"strategy={strategy_id}" if strategy_id else "", notes),
    )


def create_perps_intent(
    position_id: str,
    asset: str,
    direction: str,  # "long" or "short"
    entry_price: float,
    quantity: float,
    leverage: float,
    liquidation_price: float,
    *,
    is_paper: bool = True,
    strategy_id: str = "",
    notes: str = "",
    # Perps TP ladder: 50% @ +4%, 30% @ +8%, 20% runner
    tp1_pct: float = 0.04,
    tp1_size: float = 0.50,
    tp2_pct: float = 0.08,
    tp2_size: float = 0.30,
    tp3_pct: float = 0.15,
    tp3_size: float = 0.20,
    # Stop loss for perps (tighter due to leverage)
    sl_pct: float = 0.03,
    # Time stop: 60 minutes for perps
    time_stop_minutes: int = 60,
) -> ExitIntent:
    """
    Create exit intent for a perps position.

    Default Exit Template (Perps):
    - TP1: close 50% at +4%
    - TP2: close 30% at +8%
    - Runner: 20% with trailing stop
    - SL: immediately at invalidation or -3%
    - Time stop: 60 minutes
    """
    now = time.time()

    # Calculate TP/SL prices based on direction
    if direction == "long":
        tp_multipliers = [(1 + tp1_pct), (1 + tp2_pct), (1 + tp3_pct)]
        sl_price = entry_price * (1 - sl_pct)
    else:  # short
        tp_multipliers = [(1 - tp1_pct), (1 - tp2_pct), (1 - tp3_pct)]
        sl_price = entry_price * (1 + sl_pct)

    take_profits = [
        TakeProfit(level=1, price=entry_price * tp_multipliers[0], size_pct=tp1_size * 100),
        TakeProfit(level=2, price=entry_price * tp_multipliers[1], size_pct=tp2_size * 100),
        TakeProfit(level=3, price=entry_price * tp_multipliers[2], size_pct=tp3_size * 100),
    ]

    stop_loss = StopLoss(
        price=sl_price,
        size_pct=100.0,
        original_price=sl_price,
    )

    time_stop = TimeStop(
        deadline_timestamp=now + (time_stop_minutes * 60),
        action="exit_fully",
    )

    trailing_stop = TrailingStop(
        active=False,
        trail_pct=0.03,  # Tighter for perps
        highest_price=entry_price,
    )

    intent = ExitIntent(
        id=str(uuid.uuid4())[:8],
        position_id=position_id,
        position_type="perps",
        token_mint=asset,  # Use asset name as "mint" for perps
        symbol=f"{asset}-PERP-{direction.upper()}",
        entry_price=entry_price,
        entry_timestamp=now,
        original_quantity=quantity,
        remaining_quantity=quantity,
        take_profits=take_profits,
        stop_loss=stop_loss,
        time_stop=time_stop,
        trailing_stop=trailing_stop,
        is_paper=is_paper,
    )

    intent.notes = _merge_notes(
        f"strategy={strategy_id}" if strategy_id else "",
        notes,
        f"leverage={leverage}x, liq_price={liquidation_price:.2f}, direction={direction}",
    )

    return intent


# ============================================================================
# Persistence (with file locking for concurrent daemon access)
# ============================================================================

def _ensure_dir():
    """Ensure trading directory exists."""
    TRADING_DIR.mkdir(parents=True, exist_ok=True)


def persist_intent(intent: ExitIntent) -> bool:
    """
    Persist exit intent to disk. CRITICAL: Call immediately after entry fills.

    Uses file locking for safe concurrent access from multiple daemons.
    """
    _ensure_dir()

    try:
        # Load existing intents
        intents = _load_all_intents()

        # Update or add
        intents[intent.id] = intent.to_dict()

        # Write with lock
        with open(INTENTS_FILE, "w") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            json.dump(intents, f, indent=2)
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        logger.info(f"[exit_intents] Persisted intent {intent.id} for {intent.symbol}")
        return True

    except Exception as e:
        logger.error(f"[exit_intents] Failed to persist intent: {e}")
        return False


def load_active_intents() -> List[ExitIntent]:
    """Load all active exit intents."""
    intents = _load_all_intents()
    active = []

    for intent_data in intents.values():
        if intent_data.get("status") == "active":
            try:
                active.append(ExitIntent.from_dict(intent_data))
            except Exception as e:
                logger.warning(f"[exit_intents] Failed to parse intent: {e}")

    return active


def load_intent(intent_id: str) -> Optional[ExitIntent]:
    """Load a specific intent by ID."""
    intents = _load_all_intents()
    data = intents.get(intent_id)
    if data:
        return ExitIntent.from_dict(data)
    return None


def _load_all_intents() -> Dict[str, Dict[str, Any]]:
    """Load all intents from file."""
    if not INTENTS_FILE.exists():
        return {}

    try:
        with open(INTENTS_FILE, "r") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            data = json.load(f)
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            if isinstance(data, list):
                return {str(item.get("id") or idx): item for idx, item in enumerate(data)}
            if isinstance(data, dict):
                return data
            return {}
    except (json.JSONDecodeError, IOError):
        return {}


def update_intent(intent: ExitIntent) -> bool:
    """Update an existing intent."""
    return persist_intent(intent)


def cancel_intent(intent_id: str, reason: str = "") -> bool:
    """Cancel an intent (e.g., for emergency exit)."""
    intent = load_intent(intent_id)
    if intent:
        intent.status = IntentStatus.CANCELLED.value
        intent.notes += f" | Cancelled: {reason}"
        return persist_intent(intent)
    return False


# ============================================================================
# Trigger Checking
# ============================================================================

def check_intent_triggers(
    intent: ExitIntent,
    current_price: float,
    *,
    sentiment_reversed: bool = False,
) -> List[Tuple[ExitAction, Dict[str, Any]]]:
    """
    Check if any exit triggers are met.

    Returns list of (action, params) tuples for the daemon to execute.
    """
    actions: List[Tuple[ExitAction, Dict[str, Any]]] = []
    now = time.time()

    # Update tracking
    intent.last_check_timestamp = now
    intent.last_check_price = current_price
    intent.enforcement_attempts += 1

    # 1. Check sentiment reversal (highest priority)
    if sentiment_reversed and not intent.sentiment_invalidated:
        intent.sentiment_invalidated = True
        actions.append((ExitAction.SENTIMENT_EXIT, {
            "reason": "sentiment_reversal",
            "price": current_price,
            "size_pct": 100.0,
        }))
        return actions  # Exit immediately

    # 2. Check stop loss
    is_long = intent.position_type == "spot" or "LONG" in intent.symbol
    if is_long:
        if current_price <= intent.stop_loss.price:
            actions.append((ExitAction.TRIGGER_SL, {
                "price": current_price,
                "stop_price": intent.stop_loss.price,
                "size_pct": intent.stop_loss.size_pct,
            }))
            return actions  # Stop loss exits everything
    else:  # Short
        if current_price >= intent.stop_loss.price:
            actions.append((ExitAction.TRIGGER_SL, {
                "price": current_price,
                "stop_price": intent.stop_loss.price,
                "size_pct": intent.stop_loss.size_pct,
            }))
            return actions

    # 3. Check time stop
    if now >= intent.time_stop.deadline_timestamp and intent.remaining_quantity > 0:
        intent.time_stop.triggered = True
        actions.append((ExitAction.TRIGGER_TIME_STOP, {
            "action": intent.time_stop.action,
            "size_pct": 100.0 if intent.time_stop.action == "exit_fully" else 85.0,
            "price": current_price,
        }))
        return actions

    # 4. Check take profits (in order)
    for tp in intent.take_profits:
        if tp.filled:
            continue

        if is_long:
            if current_price >= tp.price:
                actions.append((ExitAction.TRIGGER_TP, {
                    "level": tp.level,
                    "price": current_price,
                    "target_price": tp.price,
                    "size_pct": tp.size_pct,
                }))
                tp.filled = True
                tp.fill_price = current_price
                tp.fill_timestamp = now

                # After TP1, adjust SL to breakeven
                if tp.level == 1 and not intent.stop_loss.adjusted:
                    actions.append((ExitAction.ADJUST_SL_TO_BREAKEVEN, {
                        "old_price": intent.stop_loss.price,
                        "new_price": intent.entry_price,
                    }))
                    intent.stop_loss.adjusted = True
                    intent.stop_loss.price = intent.entry_price

                    # Activate trailing stop
                    intent.trailing_stop.active = True
                    intent.trailing_stop.highest_price = current_price

        else:  # Short
            if current_price <= tp.price:
                actions.append((ExitAction.TRIGGER_TP, {
                    "level": tp.level,
                    "price": current_price,
                    "target_price": tp.price,
                    "size_pct": tp.size_pct,
                }))
                tp.filled = True
                tp.fill_price = current_price
                tp.fill_timestamp = now

    if not intent.trailing_stop.active and intent.remaining_quantity > 0:
        if any(tp.filled for tp in intent.take_profits):
            intent.trailing_stop.active = True
            intent.trailing_stop.highest_price = current_price
            if is_long:
                intent.trailing_stop.current_stop = current_price * (1 - intent.trailing_stop.trail_pct)
            else:
                intent.trailing_stop.current_stop = current_price * (1 + intent.trailing_stop.trail_pct)

    # 5. Check trailing stop (if active)
    if intent.trailing_stop.active:
        if is_long:
            # Update highest price
            if current_price > intent.trailing_stop.highest_price:
                intent.trailing_stop.highest_price = current_price
                intent.trailing_stop.current_stop = current_price * (1 - intent.trailing_stop.trail_pct)

            # Check if trailing stop hit
            if current_price <= intent.trailing_stop.current_stop:
                actions.append((ExitAction.TRIGGER_SL, {
                    "price": current_price,
                    "stop_price": intent.trailing_stop.current_stop,
                    "size_pct": 100.0,
                    "trailing": True,
                }))
        else:  # Short
            if current_price < intent.trailing_stop.highest_price:
                intent.trailing_stop.highest_price = current_price
                intent.trailing_stop.current_stop = current_price * (1 + intent.trailing_stop.trail_pct)

            if current_price >= intent.trailing_stop.current_stop:
                actions.append((ExitAction.TRIGGER_SL, {
                    "price": current_price,
                    "stop_price": intent.trailing_stop.current_stop,
                    "size_pct": 100.0,
                    "trailing": True,
                }))

    return actions


def check_time_stop(
    intent: ExitIntent,
    fallback_price: float,
) -> List[Tuple[ExitAction, Dict[str, Any]]]:
    """Check time stop using a fallback price when market data is unavailable."""
    actions: List[Tuple[ExitAction, Dict[str, Any]]] = []
    now = time.time()
    intent.last_check_timestamp = now
    intent.last_check_price = fallback_price
    intent.enforcement_attempts += 1

    if now >= intent.time_stop.deadline_timestamp and intent.remaining_quantity > 0:
        intent.time_stop.triggered = True
        actions.append((ExitAction.TRIGGER_TIME_STOP, {
            "action": intent.time_stop.action,
            "size_pct": 100.0 if intent.time_stop.action == "exit_fully" else 85.0,
            "price": fallback_price,
        }))
    return actions


# ============================================================================
# Execution (Paper Trading)
# ============================================================================

@dataclass
class ExecutionResult:
    """Result of executing an exit action."""
    success: bool
    action: str
    price: float
    quantity: float
    pnl_usd: float = 0.0
    pnl_pct: float = 0.0
    fees_usd: float = 0.0
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def execute_action(
    intent: ExitIntent,
    action: ExitAction,
    params: Dict[str, Any],
    *,
    paper_mode: bool = True,
) -> ExecutionResult:
    """
    Execute an exit action. In paper mode, simulates the trade.

    Returns ExecutionResult with P&L calculation.
    """
    current_price = params.get("price", intent.last_check_price)
    size_pct = params.get("size_pct", 100.0)
    quantity = intent.remaining_quantity * (size_pct / 100.0)

    # Calculate P&L
    if intent.position_type == "spot" or "LONG" in intent.symbol:
        pnl_usd = (current_price - intent.entry_price) * quantity
    else:  # Short
        pnl_usd = (intent.entry_price - current_price) * quantity

    pnl_pct = ((current_price / intent.entry_price) - 1) * 100
    if "SHORT" in intent.symbol:
        pnl_pct = -pnl_pct

    # Estimate fees (0.5% for paper)
    fees_usd = abs(current_price * quantity * 0.005)

    if paper_mode:
        result = ExecutionResult(
            success=True,
            action=action.value,
            price=current_price,
            quantity=quantity,
            pnl_usd=pnl_usd - fees_usd,
            pnl_pct=pnl_pct,
            fees_usd=fees_usd,
        )

        # Update remaining quantity
        intent.remaining_quantity -= quantity

        # Check if position fully closed
        if intent.remaining_quantity <= 0.001:  # Dust threshold
            intent.status = IntentStatus.COMPLETED.value
            intent.remaining_quantity = 0
        elif any(tp.filled for tp in intent.take_profits):
            intent.status = IntentStatus.PARTIAL.value

        # Save intent
        persist_intent(intent)

        # Update reliability stats
        _record_execution(result)

        logger.info(
            f"[exit_intents] Executed {action.value} for {intent.symbol}: "
            f"qty={quantity:.4f} @ ${current_price:.4f}, PnL=${pnl_usd:.2f} ({pnl_pct:+.2f}%)"
        )

        return result

    # Live execution path
    def _fail_execution(error: str) -> ExecutionResult:
        _record_strategy_execution_failure(intent, error)
        return ExecutionResult(
            success=False,
            action=action.value,
            price=current_price,
            quantity=quantity,
            error=error,
        )

    try:
        import asyncio
        from core import solana_execution, solana_tokens, solana_wallet
    except Exception as exc:
        return _fail_execution(f"live_execution_unavailable:{exc}")

    keypair = solana_wallet.load_keypair()
    if not keypair:
        return _fail_execution("live_execution_blocked:no_keypair")

    if solana_execution.VersionedTransaction is None:
        return _fail_execution("live_execution_blocked:solana_sdk_unavailable")

    input_mint = intent.token_mint
    output_mint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"  # USDC
    decimals = solana_tokens.get_token_decimals(input_mint, fallback=9)
    amount_base_units = int(quantity * (10**decimals))
    endpoints = solana_execution.load_solana_rpc_endpoints()

    async def _run_swap():
        quote = await solana_execution.get_swap_quote(
            input_mint,
            output_mint,
            amount_base_units,
            slippage_bps=200,
        )
        if not quote:
            return solana_execution.SwapExecutionResult(success=False, error="quote_failed")
        swap_tx = await solana_execution.get_swap_transaction(quote, str(keypair.pubkey()))
        if not swap_tx:
            return solana_execution.SwapExecutionResult(success=False, error="swap_tx_failed")
        signed = solana_execution.VersionedTransaction.from_bytes(
            __import__("base64").b64decode(swap_tx)
        )
        signed_tx = solana_execution.VersionedTransaction(signed.message, [keypair])
        return await solana_execution.execute_swap_transaction(
            signed_tx,
            endpoints,
            simulate=True,
            commitment="confirmed",
        )

    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            result = asyncio.run(_run_swap())
        else:
            result = asyncio.run_coroutine_threadsafe(_run_swap(), loop).result()
    except Exception as exc:
        return _fail_execution(f"live_execution_failed:{exc}")

    if not result.success:
        error = result.error or "execution_failed"
        if result.simulation_error:
            error = f"{error}:{result.simulation_error}"
        return _fail_execution(error)

    intent.remaining_quantity -= quantity
    if intent.remaining_quantity <= 0.001:
        intent.status = IntentStatus.COMPLETED.value
        intent.remaining_quantity = 0
    elif any(tp.filled for tp in intent.take_profits):
        intent.status = IntentStatus.PARTIAL.value
    persist_intent(intent)
    _record_execution(
        ExecutionResult(
            success=True,
            action=action.value,
            price=current_price,
            quantity=quantity,
            pnl_usd=pnl_usd - fees_usd,
            pnl_pct=pnl_pct,
            fees_usd=fees_usd,
        )
    )
    return ExecutionResult(
        success=True,
        action=action.value,
        price=current_price,
        quantity=quantity,
        pnl_usd=pnl_usd - fees_usd,
        pnl_pct=pnl_pct,
        fees_usd=fees_usd,
    )


# ============================================================================
# Reliability Tracking
# ============================================================================

def _record_execution(result: ExecutionResult) -> None:
    """Record execution for reliability tracking."""
    _ensure_dir()

    stats = _load_reliability_stats()

    stats["total_executions"] = stats.get("total_executions", 0) + 1
    if result.success:
        stats["successful_executions"] = stats.get("successful_executions", 0) + 1
    else:
        stats["failed_executions"] = stats.get("failed_executions", 0) + 1

    stats["total_pnl_usd"] = stats.get("total_pnl_usd", 0) + result.pnl_usd
    stats["total_fees_usd"] = stats.get("total_fees_usd", 0) + result.fees_usd

    # Compute reliability
    total = stats.get("total_executions", 1)
    successful = stats.get("successful_executions", 0)
    stats["reliability_pct"] = (successful / total) * 100

    stats["last_updated"] = time.time()

    try:
        RELIABILITY_FILE.write_text(json.dumps(stats, indent=2))
    except IOError:
        pass


def _load_reliability_stats() -> Dict[str, Any]:
    """Load reliability statistics."""
    if RELIABILITY_FILE.exists():
        try:
            return json.loads(RELIABILITY_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def get_reliability_stats() -> Dict[str, Any]:
    """Get current reliability statistics."""
    return _load_reliability_stats()


# ============================================================================
# CLI Demo
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=== Exit Intent System Demo ===\n")

    # Create a test spot intent
    intent = create_spot_intent(
        position_id="test-pos-001",
        token_mint="7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",  # SAMO
        symbol="SAMO",
        entry_price=0.01234,
        quantity=1000.0,
        is_paper=True,
    )

    print(f"Created intent {intent.id}:")
    print(f"  Symbol: {intent.symbol}")
    print(f"  Entry: ${intent.entry_price:.5f}")
    print(f"  Quantity: {intent.original_quantity}")
    print(f"\nTake Profits:")
    for tp in intent.take_profits:
        print(f"  TP{tp.level}: ${tp.price:.5f} ({tp.size_pct:.0f}%)")
    print(f"\nStop Loss: ${intent.stop_loss.price:.5f}")
    print(f"Time Stop: {intent.time_stop.deadline_timestamp - time.time():.0f}s remaining")

    # Persist
    persist_intent(intent)
    print(f"\n✓ Intent persisted to {INTENTS_FILE}")

    # Simulate price check
    test_prices = [0.01200, 0.01350, 0.01100]
    for price in test_prices:
        print(f"\nChecking at ${price:.5f}...")
        actions = check_intent_triggers(intent, price)
        if actions:
            for action, params in actions:
                print(f"  → {action.value}: {params}")
                result = execute_action(intent, action, params, paper_mode=True)
                print(f"     Result: PnL=${result.pnl_usd:.2f} ({result.pnl_pct:+.2f}%)")
        else:
            print("  No triggers")

    # Show stats
    print(f"\nReliability Stats: {get_reliability_stats()}")
