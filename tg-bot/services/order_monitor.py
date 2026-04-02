"""
Order Monitor Service - Automatic TP/SL Execution

US-006: Advanced Order Types (Stop-Loss, Take-Profit, Limit Orders)

This service runs a 10-second loop checking all active positions with TP/SL orders.
When price triggers are hit, it automatically executes sells and notifies users.

Architecture:
- Runs as async background task in supervisor
- Checks positions every 10 seconds
- Executes via bags.fm API (same as manual sells)
- Updates position status in real-time
- Sends Telegram notifications on execution

Position File Schema:
    ~/.lifeos/trading/demo_positions.json
    {
      "positions": [
        {
          "id": "buy_abc123",
          "symbol": "PONKE",
          "address": "TokenMintAddress...",
          "amount": 265957.0,
          "amount_sol": 0.5,
          "entry_price": 0.45,
          "current_price": 0.587,  // Updated by monitor
          "tp_percent": 50.0,
          "sl_percent": 20.0,
          "tp_price": 0.675,
          "sl_price": 0.36,
          "status": "open",  // open, filled, cancelled
          "timestamp": "2026-01-24T10:00:00Z"
        }
      ]
    }
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
import traceback

logger = logging.getLogger(__name__)

# File paths
POSITIONS_FILE = Path.home() / ".lifeos" / "trading" / "demo_positions.json"
ORDERS_FILE = Path.home() / ".lifeos" / "trading" / "demo_orders.json"


# =============================================================================
# Position Storage
# =============================================================================

def load_positions() -> List[Dict[str, Any]]:
    """Load positions from disk."""
    if not POSITIONS_FILE.exists():
        return []

    try:
        with open(POSITIONS_FILE, 'r') as f:
            data = json.load(f)
            return data.get("positions", [])
    except Exception as e:
        logger.error(f"Failed to load positions: {e}")
        return []


def save_positions(positions: List[Dict[str, Any]]):
    """Save positions to disk."""
    try:
        POSITIONS_FILE.parent.mkdir(parents=True, exist_ok=True)

        with open(POSITIONS_FILE, 'w') as f:
            json.dump({"positions": positions}, f, indent=2)

        logger.debug(f"Saved {len(positions)} positions")
    except Exception as e:
        logger.error(f"Failed to save positions: {e}")


def get_position_by_id(position_id: str) -> Optional[Dict[str, Any]]:
    """Get a position by ID."""
    positions = load_positions()
    return next((p for p in positions if p.get("id") == position_id), None)


def update_position(position_id: str, updates: Dict[str, Any]):
    """Update a position with new data."""
    positions = load_positions()

    for i, pos in enumerate(positions):
        if pos.get("id") == position_id:
            positions[i].update(updates)
            save_positions(positions)
            logger.info(f"Updated position {position_id}: {list(updates.keys())}")
            return True

    logger.warning(f"Position {position_id} not found for update")
    return False


# =============================================================================
# Price Fetching
# =============================================================================

async def get_current_price(token_address: str) -> Optional[float]:
    """
    Get current token price from bags.fm API.

    Args:
        token_address: Token mint address

    Returns:
        Current price in USD, or None if unavailable
    """
    try:
        from core.bags_api import get_bags_api

        api = get_bags_api()
        token_info = await api.get_token_info(token_address)

        if token_info:
            return float(token_info.get("price_usd", 0) or token_info.get("price", 0) or 0)

        logger.warning(f"No price data for {token_address}")
        return None

    except Exception as e:
        logger.error(f"Failed to get price for {token_address}: {e}")
        return None


# =============================================================================
# Order Execution
# =============================================================================

async def execute_sell(
    position: Dict[str, Any],
    reason: str,
    current_price: float
) -> bool:
    """
    Execute a sell order for a position.

    Args:
        position: Position dict
        reason: Exit reason ("take_profit_hit", "stop_loss_hit", "manual")
        current_price: Current token price

    Returns:
        True if sell succeeded, False otherwise
    """
    try:
        from tg_bot.handlers.demo import _execute_swap_with_fallback, _get_demo_slippage_bps

        token_address = position.get("address")
        amount_tokens = position.get("amount", 0)
        wallet_address = position.get("wallet_address", "demo_wallet")

        if not token_address or amount_tokens <= 0:
            logger.error(f"Invalid position data: {position.get('id')}")
            return False

        # Execute swap (token -> SOL)
        slippage_bps = _get_demo_slippage_bps()
        swap = await _execute_swap_with_fallback(
            from_token=token_address,
            to_token="So11111111111111111111111111111111111111112",  # SOL
            amount=amount_tokens,
            wallet_address=wallet_address,
            slippage_bps=slippage_bps,
        )

        if not swap.get("success"):
            logger.error(f"Sell failed for {position.get('symbol')}: {swap.get('error')}")
            return False

        # Calculate PnL
        entry_price = float(position.get("entry_price", 0) or 0)
        pnl_usd = 0.0
        pnl_pct = 0.0

        if entry_price > 0:
            pnl_pct = ((current_price - entry_price) / entry_price) * 100
            pnl_usd = (current_price - entry_price) * amount_tokens

        # Update position
        update_position(position["id"], {
            "status": "closed",
            "exit_price": current_price,
            "exit_time": datetime.now(timezone.utc).isoformat(),
            "exit_reason": reason,
            "exit_tx": swap.get("tx_hash"),
            "exit_source": swap.get("source"),
            "pnl_usd": pnl_usd,
            "pnl_pct": pnl_pct,
        })

        logger.info(
            f"✅ Sold {position.get('symbol')} @ ${current_price:.6f} "
            f"(Reason: {reason}, PnL: {pnl_pct:+.1f}%)"
        )

        # Send Telegram notification
        await send_exit_notification(position, reason, current_price, pnl_usd, pnl_pct)

        # Log observation for AI learning (US-003)
        try:
            from tg_bot.services.observation_collector import log_sell_executed

            # Calculate hold duration
            entry_time = position.get("timestamp")
            hold_duration_minutes = None
            if entry_time:
                try:
                    entry_dt = datetime.fromisoformat(entry_time.replace("Z", "+00:00"))
                    exit_dt = datetime.now(timezone.utc)
                    hold_duration_minutes = int((exit_dt - entry_dt).total_seconds() / 60)
                except Exception:
                    pass

            log_sell_executed(
                user_id=position.get("user_id", 0),  # Demo mode
                token_symbol=position.get("symbol", "UNKNOWN"),
                token_address=token_address,
                amount_tokens=amount_tokens,
                entry_price=entry_price,
                exit_price=current_price,
                pnl_usd=pnl_usd,
                pnl_pct=pnl_pct,
                exit_reason=reason,
                hold_duration_minutes=hold_duration_minutes,
            )
        except Exception as e:
            logger.warning(f"Failed to log sell observation: {e}")

        return True

    except Exception as e:
        logger.error(f"Execute sell failed: {e}")
        logger.error(traceback.format_exc())
        return False


async def send_exit_notification(
    position: Dict[str, Any],
    reason: str,
    exit_price: float,
    pnl_usd: float,
    pnl_pct: float
):
    """Send Telegram notification when order executes."""
    try:
        from tg_bot.bot_core import application
        from core.config.loader import load_config

        config = load_config()
        admin_ids = config.get("telegram", {}).get("admin_ids", [])

        if not admin_ids or not application:
            logger.warning("Cannot send notification: no admin IDs or app not initialized")
            return

        # Format reason
        reason_map = {
            "take_profit_hit": "🎯 Take-Profit Hit",
            "stop_loss_hit": "🛑 Stop-Loss Hit",
            "trailing_stop_hit": "🛡️ Trailing Stop Hit",
            "manual": "👤 Manual Exit",
        }
        reason_text = reason_map.get(reason, "⚠️ Exit")

        # Emoji based on PnL
        emoji = "✅" if pnl_usd > 0 else "❌"

        message = (
            f"{emoji} **{reason_text}**\n\n"
            f"**Token:** {position.get('symbol', 'UNKNOWN')}\n"
            f"**Entry:** ${position.get('entry_price', 0):.6f}\n"
            f"**Exit:** ${exit_price:.6f}\n"
            f"**PnL:** ${pnl_usd:+,.2f} ({pnl_pct:+.1f}%)\n"
            f"**Amount:** {position.get('amount', 0):,.0f} tokens\n"
        )

        tx_hash = position.get("exit_tx")
        if tx_hash:
            message += f"\n[View Transaction](https://solscan.io/tx/{tx_hash})"

        # Send to all admins
        for admin_id in admin_ids:
            try:
                await application.bot.send_message(
                    chat_id=admin_id,
                    text=message,
                    parse_mode="Markdown",
                    disable_web_page_preview=True,
                )
            except Exception as e:
                logger.error(f"Failed to send notification to {admin_id}: {e}")

    except Exception as e:
        logger.error(f"Send notification failed: {e}")


# =============================================================================
# Order Monitor Main Loop
# =============================================================================

class OrderMonitor:
    """
    Background service monitoring positions for TP/SL triggers.

    Usage:
        monitor = OrderMonitor()
        await monitor.start()  # Runs forever, checking every 10s
    """

    def __init__(self, check_interval: int = 10):
        """
        Initialize order monitor.

        Args:
            check_interval: Seconds between price checks (default 10)
        """
        self.check_interval = check_interval
        self.running = False
        self.last_check_time = None

    async def start(self):
        """Start monitoring loop (runs forever)."""
        self.running = True
        logger.info("🔍 Order monitor started (checking every 10s)")

        while self.running:
            try:
                await self.check_all_positions()
                self.last_check_time = datetime.now(timezone.utc)

            except Exception as e:
                logger.error(f"Order monitor error: {e}")
                logger.error(traceback.format_exc())

            # Wait for next check
            await asyncio.sleep(self.check_interval)

    async def check_all_positions(self):
        """Check all open positions for TP/SL triggers."""
        positions = load_positions()
        active_positions = [p for p in positions if p.get("status") == "open"]

        if not active_positions:
            return  # Nothing to monitor

        logger.debug(f"Checking {len(active_positions)} active positions")

        for position in active_positions:
            try:
                await self.check_position(position)
            except Exception as e:
                logger.error(f"Failed to check position {position.get('id')}: {e}")

    async def check_position(self, position: Dict[str, Any]):
        """
        Check a single position for TP/SL triggers.

        Args:
            position: Position dict with TP/SL data
        """
        position_id = position.get("id")
        symbol = position.get("symbol", "TOKEN")
        token_address = position.get("address")

        tp_price = float(position.get("tp_price", 0) or 0)
        sl_price = float(position.get("sl_price", 0) or 0)

        if not token_address:
            logger.warning(f"Position {position_id} missing token address")
            return

        # Get current price
        current_price = await get_current_price(token_address)

        if current_price is None:
            logger.warning(f"Could not get price for {symbol}")
            return

        # Update current price in position
        update_position(position_id, {"current_price": current_price})

        # Check TP trigger
        if tp_price > 0 and current_price >= tp_price:
            logger.info(f"🎯 TAKE-PROFIT triggered: {symbol} @ ${current_price:.6f} (target: ${tp_price:.6f})")

            success = await execute_sell(
                position=position,
                reason="take_profit_hit",
                current_price=current_price
            )

            if not success:
                logger.error(f"Failed to execute TP for {symbol}")

            return  # Position closed, no need to check SL

        # Check SL trigger
        if sl_price > 0 and current_price <= sl_price:
            logger.info(f"🛑 STOP-LOSS triggered: {symbol} @ ${current_price:.6f} (stop: ${sl_price:.6f})")

            success = await execute_sell(
                position=position,
                reason="stop_loss_hit",
                current_price=current_price
            )

            if not success:
                logger.error(f"Failed to execute SL for {symbol}")

    def stop(self):
        """Stop the monitoring loop."""
        self.running = False
        logger.info("Order monitor stopped")


# =============================================================================
# Singleton Instance
# =============================================================================

_monitor_instance: Optional[OrderMonitor] = None


def get_order_monitor() -> OrderMonitor:
    """Get singleton order monitor instance."""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = OrderMonitor()
    return _monitor_instance


async def start_order_monitor():
    """Start the order monitor service (for use in supervisor)."""
    monitor = get_order_monitor()
    await monitor.start()


# =============================================================================
# Manual Testing
# =============================================================================

if __name__ == "__main__":
    # Test the order monitor
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    async def test():
        """Test order monitor."""
        monitor = OrderMonitor(check_interval=5)  # Check every 5s for testing

        print("Starting order monitor test...")
        print("Create a test position in ~/.lifeos/trading/demo_positions.json")
        print("Set TP/SL prices close to current price to test triggers")
        print("Press Ctrl+C to stop\n")

        try:
            await monitor.start()
        except KeyboardInterrupt:
            print("\nStopping...")
            monitor.stop()

    asyncio.run(test())
