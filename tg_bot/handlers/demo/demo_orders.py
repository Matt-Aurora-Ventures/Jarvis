"""
Demo Bot - TP/SL Order Management Module

Contains:
- Background TP/SL monitoring
- Exit trigger checking
- Auto-exit execution
- Trailing stop management
- Alert formatting
"""

import asyncio
import os
import time
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from telegram.ext import ContextTypes
from telegram import Update
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration Helpers
# =============================================================================

def _exit_checks_enabled() -> bool:
    """Check if exit checks are enabled via environment."""
    return os.environ.get("DEMO_EXIT_CHECKS", "1").strip().lower() not in ("0", "false", "off")


def _auto_exit_enabled(context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if auto-exit is enabled for this user."""
    if os.environ.get("DEMO_TPSL_AUTO_EXECUTE", "1").strip().lower() in ("0", "false", "off"):
        return False
    return bool(context.user_data.get("ai_auto_trade", False))


def _get_exit_check_interval_seconds() -> int:
    """Get the exit check interval from environment."""
    raw = os.environ.get("DEMO_EXIT_CHECK_INTERVAL_SECONDS", "30")
    try:
        return max(5, int(float(raw)))
    except ValueError:
        return 30


def _should_run_exit_checks(context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Determine if exit checks should run based on throttling."""
    if not _exit_checks_enabled():
        return False
    positions = context.user_data.get("positions", [])
    if not positions:
        return False
    interval = _get_exit_check_interval_seconds()
    now = time.time()
    last = context.user_data.get("last_exit_check_ts")
    if last and (now - last) < interval:
        return False
    context.user_data["last_exit_check_ts"] = now
    return True


# =============================================================================
# Exit Trigger Checking
# =============================================================================

async def _check_demo_exit_triggers(
    context_or_user_data: Any,
    positions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Check TP/SL/trailing stops for demo positions.

    Args:
        context_or_user_data: Either a context object or user_data dict
        positions: List of position dictionaries

    Returns:
        List of alert dictionaries for triggered conditions
    """
    # Import here to avoid circular imports
    from tg_bot.handlers.demo.demo_trading import _get_jupiter_client

    if not positions or not _exit_checks_enabled():
        return []

    # Handle both context object and raw user_data dict
    if hasattr(context_or_user_data, 'user_data'):
        user_data = context_or_user_data.user_data
    else:
        user_data = context_or_user_data

    alerts: List[Dict[str, Any]] = []
    jupiter = _get_jupiter_client()
    trailing_stops = user_data.get("trailing_stops", [])

    for pos in positions:
        token_mint = pos.get("address")
        entry_price = float(pos.get("entry_price", 0) or 0)
        current_price = float(pos.get("current_price", 0) or 0)

        if not current_price and token_mint:
            try:
                current_price = await jupiter.get_token_price(token_mint)
                pos["current_price"] = current_price
            except Exception:
                continue

        if entry_price <= 0 or current_price <= 0:
            continue

        # Check take-profit
        tp_pct = pos.get("tp_percent", pos.get("take_profit"))
        if tp_pct is not None:
            tp_price = entry_price * (1 + float(tp_pct) / 100)
            if current_price >= tp_price and not pos.get("tp_triggered"):
                pos["tp_triggered"] = True
                alerts.append({"type": "take_profit", "position": pos, "price": current_price})

        # Check stop-loss
        sl_pct = pos.get("sl_percent", pos.get("stop_loss"))
        if sl_pct is not None:
            sl_price = entry_price * (1 - float(sl_pct) / 100)
            if current_price <= sl_price and not pos.get("sl_triggered"):
                pos["sl_triggered"] = True
                alerts.append({"type": "stop_loss", "position": pos, "price": current_price})

    # Update trailing stops
    for stop in trailing_stops:
        if not stop.get("active", True):
            continue
        pos_id = stop.get("position_id")
        position = next((p for p in positions if p.get("id") == pos_id), None)
        if not position:
            continue
        current_price = float(position.get("current_price", 0) or 0)
        if current_price <= 0:
            continue
        highest = float(stop.get("highest_price", 0) or 0)
        trail_pct = float(stop.get("trail_percent", 10) or 10) / 100
        if current_price > highest:
            highest = current_price
            stop["highest_price"] = highest
            stop["current_stop_price"] = highest * (1 - trail_pct)
        current_stop = float(stop.get("current_stop_price", 0) or 0)
        if current_stop and current_price <= current_stop and not stop.get("triggered"):
            stop["triggered"] = True
            stop["active"] = False
            alerts.append({"type": "trailing_stop", "position": position, "price": current_price})

    # Update trailing stops in user_data if using context
    if hasattr(context_or_user_data, 'user_data'):
        context_or_user_data.user_data["trailing_stops"] = trailing_stops

    return alerts


# =============================================================================
# Exit Execution
# =============================================================================

async def _maybe_execute_exit(
    context: ContextTypes.DEFAULT_TYPE,
    alert: Dict[str, Any],
) -> bool:
    """
    Execute an auto-exit if enabled.

    Args:
        context: Telegram context
        alert: Alert dictionary with position info

    Returns:
        True if position was closed, False otherwise
    """
    # Import here to avoid circular imports
    from tg_bot.handlers.demo.demo_trading import _execute_swap_with_fallback, _get_demo_slippage_bps

    if not _auto_exit_enabled(context):
        return False

    position = alert.get("position", {})
    token_mint = position.get("address")
    token_amount = position.get("amount", 0)
    wallet_address = context.user_data.get("wallet_address", "demo_wallet")
    slippage_bps = _get_demo_slippage_bps()

    swap = await _execute_swap_with_fallback(
        from_token=token_mint,
        to_token="So11111111111111111111111111111111111111112",
        amount=token_amount,
        wallet_address=wallet_address,
        slippage_bps=slippage_bps,
    )

    if swap.get("success"):
        position["closed_at"] = datetime.now(timezone.utc).isoformat()
        position["exit_tx"] = swap.get("tx_hash")
        position["exit_source"] = swap.get("source")
        position["exit_reason"] = alert.get("type")
        return True
    return False


# =============================================================================
# Alert Formatting
# =============================================================================

def _format_exit_alert_message(alert: Dict[str, Any], auto_executed: bool) -> str:
    """
    Format an exit alert message for Telegram.

    Args:
        alert: Alert dictionary
        auto_executed: Whether the exit was auto-executed

    Returns:
        Formatted message string
    """
    # Import here to avoid circular imports
    from tg_bot.services.digest_formatter import escape_markdown_v1 as escape_md

    position = alert.get("position", {})
    symbol = escape_md(position.get("symbol", "TOKEN"))
    entry_price = float(position.get("entry_price", 0) or 0)
    current_price = float(alert.get("price", 0) or position.get("current_price", 0) or 0)
    alert_type = alert.get("type", "alert")

    reason_map = {
        "take_profit": "Target hit",
        "stop_loss": "Stop-loss hit",
        "trailing_stop": "Trailing stop hit",
    }
    reason = reason_map.get(alert_type, "Exit alert")

    lines = [f"{reason} - *{symbol}*"]
    if entry_price:
        lines.append(f"Entry: ${entry_price:.6f}")
    if current_price:
        lines.append(f"Now: ${current_price:.6f}")
    if entry_price and current_price:
        pnl_pct = ((current_price - entry_price) / entry_price) * 100
        lines.append(f"P&L: {pnl_pct:+.1f}%")

    if auto_executed:
        source = position.get("exit_source", "swap")
        tx_hash = position.get("exit_tx")
        tx_display = f"{tx_hash[:8]}...{tx_hash[-8:]}" if tx_hash else "N/A"
        lines.append(f"Auto-exit: {source}")
        lines.append(f"TX: {tx_display}")
    else:
        lines.append("_Auto-exit disabled - review position._")

    return "\n".join(lines)


# =============================================================================
# Background Monitoring
# =============================================================================

async def _background_tp_sl_monitor(context: Any) -> None:
    """
    Background job to monitor TP/SL triggers for all users.

    This runs every 5 minutes to check if any positions have hit
    their take-profit or stop-loss levels and auto-executes exits.

    Note: Individual callbacks also run exit checks for real-time responsiveness.
    """
    try:
        if not context or not hasattr(context, 'application'):
            return

        user_data_dict = getattr(context.application, 'user_data', {})
        if not user_data_dict:
            return

        checked_count = 0
        triggered_count = 0

        for user_id, user_data in user_data_dict.items():
            positions = user_data.get("positions", [])
            if not positions:
                continue

            checked_count += 1

            try:
                alerts = await asyncio.wait_for(
                    _check_demo_exit_triggers(user_data, positions),
                    timeout=2.0,
                )
            except asyncio.TimeoutError:
                logger.warning(f"TP/SL check timed out for user {user_id}")
                continue

            if not alerts:
                continue

            triggered_count += len(alerts)
            closed_ids: List[str] = []

            for alert in alerts:
                try:
                    # Create a mock context-like object for _maybe_execute_exit
                    class MockContext:
                        def __init__(self, ud):
                            self.user_data = ud

                    mock_ctx = MockContext(user_data)
                    executed = await asyncio.wait_for(
                        _maybe_execute_exit(mock_ctx, alert),
                        timeout=5.0,
                    )
                except asyncio.TimeoutError:
                    logger.warning(f"TP/SL auto-exit timed out for user {user_id}")
                    continue
                except Exception as exc:
                    logger.warning(f"TP/SL auto-exit failed for user {user_id}: {exc}")
                    continue

                position = alert.get("position", {})
                if executed and position.get("id"):
                    closed_ids.append(position.get("id"))

                # Send alert to user
                try:
                    message = _format_exit_alert_message(alert, executed)
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=message,
                        parse_mode=ParseMode.MARKDOWN,
                    )
                except Exception as exc:
                    logger.debug(f"Failed to send TP/SL alert to user {user_id}: {exc}")

            # Update positions after exits
            if closed_ids:
                user_data["positions"] = [
                    p for p in positions if p.get("id") not in closed_ids
                ]
                trailing_stops = user_data.get("trailing_stops", [])
                if trailing_stops:
                    user_data["trailing_stops"] = [
                        s for s in trailing_stops if s.get("position_id") not in closed_ids
                    ]

        if checked_count > 0:
            logger.info(f"TP/SL monitor: checked {checked_count} users, {triggered_count} triggers")

    except Exception as exc:
        logger.warning(f"Background TP/SL monitor failed: {exc}")


# =============================================================================
# Per-Request Exit Processing
# =============================================================================

async def _process_demo_exit_checks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Run TP/SL/trailing checks with throttling and optional auto-exit.

    Called during callback handling for real-time responsiveness.
    """
    try:
        if not _should_run_exit_checks(context):
            return

        positions = context.user_data.get("positions", [])
        if not positions:
            return

        try:
            alerts = await asyncio.wait_for(
                _check_demo_exit_triggers(context, positions),
                timeout=2.0,
            )
        except asyncio.TimeoutError:
            logger.warning("Demo exit checks timed out")
            return

        if not alerts:
            return

        closed_ids: List[str] = []
        chat_id = update.effective_chat.id if update and update.effective_chat else None

        for alert in alerts:
            executed = False
            try:
                executed = await asyncio.wait_for(
                    _maybe_execute_exit(context, alert),
                    timeout=5.0,
                )
            except asyncio.TimeoutError:
                logger.warning("Demo auto-exit timed out")
            except Exception as exc:
                logger.warning(f"Demo auto-exit failed: {exc}")

            position = alert.get("position", {})
            if executed and position.get("id"):
                closed_ids.append(position.get("id"))

            if chat_id:
                message = _format_exit_alert_message(alert, executed)
                try:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=message,
                        parse_mode=ParseMode.MARKDOWN,
                    )
                except Exception as exc:
                    logger.warning(f"Failed to send demo exit alert: {exc}")

        if closed_ids:
            context.user_data["positions"] = [
                p for p in positions if p.get("id") not in closed_ids
            ]
            trailing_stops = context.user_data.get("trailing_stops", [])
            if trailing_stops:
                context.user_data["trailing_stops"] = [
                    s for s in trailing_stops if s.get("position_id") not in closed_ids
                ]
        else:
            context.user_data["positions"] = positions

    except Exception as exc:
        logger.warning(f"Exit check processing failed: {exc}")
