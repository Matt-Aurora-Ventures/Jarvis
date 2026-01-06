"""
Jupiter Stop Loss / Take Profit Order Manager
==============================================

Implements stop loss and take profit functionality using Jupiter swap execution.

Since Jupiter doesn't support native limit orders for SL/TP, this module:
1. Monitors positions for SL/TP triggers
2. Executes market swaps via Jupiter when triggered
3. Persists pending orders to disk for daemon enforcement

Works with:
- core/exit_intents.py for intent persistence
- core/solana_execution.py for swap execution
- core/trading_daemon.py for monitoring

Usage:
    from core.jupiter_orders import create_sl_tp_order, check_and_execute_orders
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
ORDERS_DIR = ROOT / "data" / "trader" / "jupiter_orders"
ACTIVE_ORDERS_FILE = ORDERS_DIR / "active_orders.json"
HISTORY_FILE = ORDERS_DIR / "order_history.jsonl"

# Jupiter constants
SOL_MINT = "So11111111111111111111111111111111111111112"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


class OrderType(Enum):
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    TRAILING_STOP = "trailing_stop"
    TIME_STOP = "time_stop"


class OrderStatus(Enum):
    PENDING = "pending"
    TRIGGERED = "triggered"
    EXECUTING = "executing"
    FILLED = "filled"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


@dataclass
class JupiterOrder:
    """Stop loss or take profit order."""
    order_id: str
    order_type: str  # OrderType value
    position_id: str
    token_mint: str
    token_symbol: str
    
    # Order parameters
    trigger_price: float  # Price that triggers the order
    quantity: float  # Amount to sell/buy
    size_pct: float  # Percentage of position (for partial TPs)
    
    # Entry info
    entry_price: float
    entry_time: float
    
    # Order state
    status: str = "pending"  # OrderStatus value
    current_price: float = 0.0
    last_check: float = 0.0
    
    # Execution info
    executed_at: Optional[float] = None
    executed_price: Optional[float] = None
    signature: Optional[str] = None
    slippage_bps: int = 100  # 1% default
    
    # Trailing stop specific
    trail_pct: float = 0.0  # Trail percentage
    highest_price: float = 0.0  # Highest price since entry
    adjusted_trigger: float = 0.0  # Adjusted trigger for trailing
    
    # Time stop specific
    expiry_time: float = 0.0  # Time when order expires
    
    # Metadata
    notes: str = ""
    created_at: float = field(default_factory=time.time)


@dataclass
class OrderResult:
    """Result of order operation."""
    success: bool
    order: Optional[JupiterOrder] = None
    error: Optional[str] = None
    signature: Optional[str] = None


def _ensure_dirs():
    """Ensure order directories exist."""
    ORDERS_DIR.mkdir(parents=True, exist_ok=True)


def _load_orders() -> List[Dict[str, Any]]:
    """Load active orders from disk."""
    if not ACTIVE_ORDERS_FILE.exists():
        return []
    try:
        return json.loads(ACTIVE_ORDERS_FILE.read_text())
    except (json.JSONDecodeError, IOError):
        return []


def _save_orders(orders: List[Dict[str, Any]]):
    """Save active orders to disk."""
    _ensure_dirs()
    ACTIVE_ORDERS_FILE.write_text(json.dumps(orders, indent=2))


def _append_history(order: JupiterOrder):
    """Append order to history file."""
    _ensure_dirs()
    with open(HISTORY_FILE, "a") as f:
        f.write(json.dumps(asdict(order)) + "\n")


def create_order(
    *,
    order_type: OrderType,
    position_id: str,
    token_mint: str,
    token_symbol: str,
    trigger_price: float,
    quantity: float,
    entry_price: float,
    size_pct: float = 100.0,
    slippage_bps: int = 100,
    trail_pct: float = 0.0,
    expiry_minutes: float = 0.0,
    notes: str = "",
) -> OrderResult:
    """
    Create a new stop loss or take profit order.
    
    Args:
        order_type: Type of order (STOP_LOSS, TAKE_PROFIT, etc.)
        position_id: Unique position identifier
        token_mint: Token mint address
        token_symbol: Token symbol for logging
        trigger_price: Price that triggers execution
        quantity: Amount of tokens
        entry_price: Entry price of position
        size_pct: Percentage of position to exit
        slippage_bps: Slippage tolerance in basis points
        trail_pct: Trailing stop percentage (for trailing stops)
        expiry_minutes: Minutes until order expires (0 = no expiry)
        notes: Additional notes
    
    Returns:
        OrderResult with created order
    """
    try:
        order = JupiterOrder(
            order_id=str(uuid.uuid4())[:8],
            order_type=order_type.value,
            position_id=position_id,
            token_mint=token_mint,
            token_symbol=token_symbol,
            trigger_price=trigger_price,
            quantity=quantity,
            size_pct=size_pct,
            entry_price=entry_price,
            entry_time=time.time(),
            slippage_bps=slippage_bps,
            trail_pct=trail_pct,
            highest_price=entry_price,
            adjusted_trigger=trigger_price,
            expiry_time=time.time() + (expiry_minutes * 60) if expiry_minutes > 0 else 0,
            notes=notes,
        )
        
        # Save to active orders
        orders = _load_orders()
        orders.append(asdict(order))
        _save_orders(orders)
        
        logger.info(
            f"Created {order_type.value} order {order.order_id} for {token_symbol}: "
            f"trigger=${trigger_price:.6f}, qty={quantity:.4f}"
        )
        
        return OrderResult(success=True, order=order)
        
    except Exception as e:
        logger.error(f"Failed to create order: {e}")
        return OrderResult(success=False, error=str(e))


def create_sl_tp_pair(
    *,
    position_id: str,
    token_mint: str,
    token_symbol: str,
    quantity: float,
    entry_price: float,
    stop_loss_pct: float = 0.09,  # 9% default
    take_profit_pct: float = 0.20,  # 20% default
    slippage_bps: int = 100,
    expiry_minutes: float = 90.0,  # 90 min default time stop
) -> Tuple[OrderResult, OrderResult]:
    """
    Create both stop loss and take profit orders for a position.
    
    Args:
        position_id: Unique position identifier
        token_mint: Token mint address
        token_symbol: Token symbol
        quantity: Position size
        entry_price: Entry price
        stop_loss_pct: Stop loss percentage (e.g., 0.09 = 9%)
        take_profit_pct: Take profit percentage (e.g., 0.20 = 20%)
        slippage_bps: Slippage tolerance
        expiry_minutes: Time stop in minutes
    
    Returns:
        Tuple of (stop_loss_result, take_profit_result)
    """
    sl_price = entry_price * (1 - stop_loss_pct)
    tp_price = entry_price * (1 + take_profit_pct)
    
    sl_result = create_order(
        order_type=OrderType.STOP_LOSS,
        position_id=position_id,
        token_mint=token_mint,
        token_symbol=token_symbol,
        trigger_price=sl_price,
        quantity=quantity,
        entry_price=entry_price,
        slippage_bps=slippage_bps + 50,  # Extra slippage for SL
        expiry_minutes=expiry_minutes,
        notes=f"SL at -{stop_loss_pct*100:.1f}%",
    )
    
    tp_result = create_order(
        order_type=OrderType.TAKE_PROFIT,
        position_id=position_id,
        token_mint=token_mint,
        token_symbol=token_symbol,
        trigger_price=tp_price,
        quantity=quantity,
        entry_price=entry_price,
        slippage_bps=slippage_bps,
        notes=f"TP at +{take_profit_pct*100:.1f}%",
    )
    
    return sl_result, tp_result


def create_tp_ladder(
    *,
    position_id: str,
    token_mint: str,
    token_symbol: str,
    quantity: float,
    entry_price: float,
    ladder: List[Tuple[float, float]] = None,  # [(price_pct, size_pct), ...]
    slippage_bps: int = 100,
) -> List[OrderResult]:
    """
    Create a take profit ladder with multiple levels.
    
    Default ladder:
    - TP1: +8% (60% of position)
    - TP2: +18% (25% of position)
    - TP3: +40% (15% runner)
    
    Args:
        position_id: Position identifier
        token_mint: Token mint
        token_symbol: Token symbol
        quantity: Total position size
        entry_price: Entry price
        ladder: Custom ladder [(price_pct, size_pct), ...]
        slippage_bps: Slippage tolerance
    
    Returns:
        List of OrderResults for each TP level
    """
    if ladder is None:
        ladder = [
            (0.08, 60.0),   # TP1: +8%, 60%
            (0.18, 25.0),   # TP2: +18%, 25%
            (0.40, 15.0),   # TP3: +40%, 15% runner
        ]
    
    results = []
    for i, (price_pct, size_pct) in enumerate(ladder, 1):
        tp_price = entry_price * (1 + price_pct)
        tp_qty = quantity * (size_pct / 100)
        
        result = create_order(
            order_type=OrderType.TAKE_PROFIT,
            position_id=position_id,
            token_mint=token_mint,
            token_symbol=token_symbol,
            trigger_price=tp_price,
            quantity=tp_qty,
            entry_price=entry_price,
            size_pct=size_pct,
            slippage_bps=slippage_bps,
            notes=f"TP{i} at +{price_pct*100:.1f}%",
        )
        results.append(result)
    
    return results


def get_active_orders(position_id: Optional[str] = None) -> List[JupiterOrder]:
    """
    Get active orders, optionally filtered by position.
    
    Args:
        position_id: Filter by position (None = all orders)
    
    Returns:
        List of active JupiterOrders
    """
    orders_data = _load_orders()
    orders = []
    
    for data in orders_data:
        if data.get("status") not in ("pending", "triggered"):
            continue
        if position_id and data.get("position_id") != position_id:
            continue
        orders.append(JupiterOrder(**data))
    
    return orders


def check_order_triggers(
    order: JupiterOrder,
    current_price: float,
) -> Optional[str]:
    """
    Check if an order should be triggered.
    
    Args:
        order: The order to check
        current_price: Current token price
    
    Returns:
        Trigger reason if triggered, None otherwise
    """
    # Update order state
    order.current_price = current_price
    order.last_check = time.time()
    
    # Check time stop / expiry
    if order.expiry_time > 0 and time.time() > order.expiry_time:
        return "time_stop"
    
    if order.order_type == OrderType.STOP_LOSS.value:
        if current_price <= order.trigger_price:
            return "stop_loss_hit"
    
    elif order.order_type == OrderType.TAKE_PROFIT.value:
        if current_price >= order.trigger_price:
            return "take_profit_hit"
    
    elif order.order_type == OrderType.TRAILING_STOP.value:
        # Update highest price
        if current_price > order.highest_price:
            order.highest_price = current_price
            order.adjusted_trigger = current_price * (1 - order.trail_pct)
        
        if current_price <= order.adjusted_trigger:
            return "trailing_stop_hit"
    
    return None


async def execute_order(
    order: JupiterOrder,
    *,
    output_mint: str = USDC_MINT,
    dry_run: bool = False,
) -> OrderResult:
    """
    Execute an order via Jupiter swap.
    
    Args:
        order: Order to execute
        output_mint: Output token (default: USDC)
        dry_run: If True, simulate only
    
    Returns:
        OrderResult with execution status
    """
    try:
        from core import solana_execution
        
        order.status = OrderStatus.EXECUTING.value
        
        # Convert quantity to lamports/smallest unit
        # Note: This assumes quantity is already in token units
        amount_raw = int(order.quantity * 1_000_000)  # Assuming 6 decimals
        
        logger.info(
            f"Executing {order.order_type} order {order.order_id}: "
            f"selling {order.quantity:.4f} {order.token_symbol}"
        )
        
        if dry_run:
            # Simulate only
            quote = await solana_execution.get_swap_quote(
                input_mint=order.token_mint,
                output_mint=output_mint,
                amount=amount_raw,
                slippage_bps=order.slippage_bps,
            )
            
            if quote:
                order.status = OrderStatus.FILLED.value
                order.executed_at = time.time()
                order.executed_price = order.current_price
                return OrderResult(success=True, order=order)
            else:
                order.status = OrderStatus.FAILED.value
                return OrderResult(success=False, order=order, error="Quote failed")
        
        # Real execution
        result = await solana_execution.execute_swap_transaction(
            input_mint=order.token_mint,
            output_mint=output_mint,
            amount=amount_raw,
            slippage_bps=order.slippage_bps,
        )
        
        if result.success:
            order.status = OrderStatus.FILLED.value
            order.executed_at = time.time()
            order.executed_price = order.current_price
            order.signature = result.signature
            
            logger.info(
                f"Order {order.order_id} filled: sig={result.signature}, "
                f"price=${order.executed_price:.6f}"
            )
            
            return OrderResult(success=True, order=order, signature=result.signature)
        else:
            order.status = OrderStatus.FAILED.value
            logger.error(f"Order {order.order_id} failed: {result.error}")
            return OrderResult(success=False, order=order, error=result.error)
            
    except Exception as e:
        order.status = OrderStatus.FAILED.value
        logger.error(f"Order execution error: {e}")
        return OrderResult(success=False, order=order, error=str(e))


async def check_and_execute_orders(
    price_fetcher: callable,
    *,
    dry_run: bool = False,
) -> List[OrderResult]:
    """
    Check all active orders and execute any that are triggered.
    
    This is the main loop function for the trading daemon.
    
    Args:
        price_fetcher: Async function that returns Dict[mint, price]
        dry_run: If True, simulate only
    
    Returns:
        List of OrderResults for executed orders
    """
    orders = get_active_orders()
    if not orders:
        return []
    
    # Fetch current prices
    mints = list(set(o.token_mint for o in orders))
    try:
        prices = await price_fetcher(mints)
    except Exception as e:
        logger.error(f"Failed to fetch prices: {e}")
        return []
    
    results = []
    orders_to_update = []
    
    for order in orders:
        current_price = prices.get(order.token_mint)
        if current_price is None:
            continue
        
        trigger_reason = check_order_triggers(order, current_price)
        
        if trigger_reason:
            logger.info(
                f"Order {order.order_id} triggered: {trigger_reason} "
                f"(price=${current_price:.6f}, trigger=${order.trigger_price:.6f})"
            )
            
            result = await execute_order(order, dry_run=dry_run)
            results.append(result)
            
            # Record to history if filled or failed
            if order.status in (OrderStatus.FILLED.value, OrderStatus.FAILED.value):
                _append_history(order)
        
        orders_to_update.append(asdict(order))
    
    # Update active orders file
    # Remove filled/failed/cancelled orders
    active = [
        o for o in orders_to_update
        if o["status"] in ("pending", "triggered", "executing")
    ]
    _save_orders(active)
    
    return results


def cancel_order(order_id: str) -> bool:
    """Cancel an order by ID."""
    orders = _load_orders()
    updated = []
    found = False
    
    for o in orders:
        if o.get("order_id") == order_id:
            o["status"] = OrderStatus.CANCELLED.value
            _append_history(JupiterOrder(**o))
            found = True
        else:
            updated.append(o)
    
    if found:
        _save_orders(updated)
        logger.info(f"Cancelled order {order_id}")
    
    return found


def cancel_position_orders(position_id: str) -> int:
    """Cancel all orders for a position."""
    orders = _load_orders()
    updated = []
    cancelled = 0
    
    for o in orders:
        if o.get("position_id") == position_id:
            o["status"] = OrderStatus.CANCELLED.value
            _append_history(JupiterOrder(**o))
            cancelled += 1
        else:
            updated.append(o)
    
    _save_orders(updated)
    if cancelled:
        logger.info(f"Cancelled {cancelled} orders for position {position_id}")
    
    return cancelled


def adjust_stop_loss_to_breakeven(position_id: str, entry_price: float) -> bool:
    """
    Move stop loss to breakeven after TP1 hit.
    
    Args:
        position_id: Position identifier
        entry_price: Original entry price (becomes new SL)
    
    Returns:
        True if adjustment made
    """
    orders = _load_orders()
    updated = False
    
    for o in orders:
        if (o.get("position_id") == position_id and 
            o.get("order_type") == OrderType.STOP_LOSS.value and
            o.get("status") == "pending"):
            
            old_trigger = o["trigger_price"]
            o["trigger_price"] = entry_price
            o["notes"] = f"{o.get('notes', '')}; Adjusted to breakeven from ${old_trigger:.6f}"
            updated = True
            logger.info(f"Adjusted SL to breakeven for position {position_id}")
            break
    
    if updated:
        _save_orders(orders)
    
    return updated


def get_order_stats() -> Dict[str, Any]:
    """Get order statistics."""
    orders = _load_orders()
    
    stats = {
        "total_active": 0,
        "pending": 0,
        "triggered": 0,
        "by_type": {},
    }
    
    for o in orders:
        status = o.get("status", "pending")
        if status in ("pending", "triggered"):
            stats["total_active"] += 1
            stats[status] = stats.get(status, 0) + 1
            
            order_type = o.get("order_type", "unknown")
            stats["by_type"][order_type] = stats["by_type"].get(order_type, 0) + 1
    
    return stats


def clear_all_orders() -> int:
    """Clear all active orders (use with caution!)."""
    orders = _load_orders()
    count = len(orders)
    
    for o in orders:
        o["status"] = OrderStatus.CANCELLED.value
        _append_history(JupiterOrder(**o))
    
    _save_orders([])
    logger.warning(f"Cleared {count} active orders")
    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=== Jupiter Orders Manager ===")
    print(json.dumps(get_order_stats(), indent=2))
