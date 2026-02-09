"""
Demo Bot - Position Callback Handler

Handles: positions, positions_all, pos_adjust, trailing_stops, tsl_*, adj_tp/sl
"""

import logging
from datetime import datetime
from typing import Any, Dict, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def handle_position(
    ctx,
    action: str,
    data: str,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    state: Dict[str, Any],
) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Handle position callbacks.

    Args:
        ctx: DemoContextLoader instance
        action: The action
        data: Full callback data
        update: Telegram update
        context: Bot context
        state: Shared state dict

    Returns:
        Tuple of (text, keyboard)
    """
    theme = ctx.JarvisTheme
    DemoMenuBuilder = ctx.DemoMenuBuilder
    positions = state.get("positions", [])
    total_pnl = state.get("total_pnl", 0.0)

    if action == "positions":
        return DemoMenuBuilder.positions_menu(
            positions=positions,
            total_pnl=total_pnl,
        )

    elif action == "positions_all":
        if not positions:
            return DemoMenuBuilder.error_message(
                error="No open positions",
                retry_action="demo:main",
            )

        lines = [
            f"{theme.CHART} *ALL OPEN POSITIONS ({len(positions)})*",
            "=" * 20,
            "",
        ]

        for i, pos in enumerate(positions, 1):
            symbol = pos.get("symbol", "???")
            pnl_pct = pos.get("pnl_pct", 0)
            pnl_usd = pos.get("pnl_usd", 0)
            entry_price = pos.get("entry_price", 0)
            current_price = pos.get("current_price", 0)

            pnl_emoji = "{green}" if pnl_pct >= 0 else "{red}"
            pnl_sign = "+" if pnl_pct >= 0 else ""

            lines.extend([
                f"{i}. *{symbol}* {pnl_emoji}",
                f"   P&L: {pnl_sign}{pnl_pct:.1f}% (${pnl_usd:+.2f})",
                f"   Entry: ${entry_price:.8f}" if entry_price < 0.01 else f"   Entry: ${entry_price:.4f}",
                f"   Current: ${current_price:.8f}" if current_price < 0.01 else f"   Current: ${current_price:.4f}",
                "",
            ])

        # Add summary
        winners = sum(1 for p in positions if p.get("pnl_pct", 0) >= 0)
        losers = len(positions) - winners
        total_pnl_sum = sum(p.get("pnl_usd", 0) for p in positions)
        total_pnl_sign = "+" if total_pnl_sum >= 0 else ""

        lines.extend([
            "=" * 20,
            f"{theme.CHART} *Summary*",
            f"| Total P&L: ${total_pnl_sign}{abs(total_pnl_sum):.2f}",
            f"| Winners: {winners}",
            f"| Losers: {losers}",
            f"| Win Rate: {(winners/len(positions)*100):.0f}%",
        ])

        text = "\n".join(lines)
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"{theme.CHART} P&L Report", callback_data="demo:pnl_report"),
                InlineKeyboardButton(f"{theme.CHART} Positions", callback_data="demo:positions"),
            ],
            [
                InlineKeyboardButton(f"{theme.BACK} Main Menu", callback_data="demo:main"),
            ],
        ])
        return text, keyboard

    elif action == "pnl_report":
        # Calculate stats from positions
        winners = sum(1 for p in positions if p.get("pnl_pct", 0) >= 0)
        losers = sum(1 for p in positions if p.get("pnl_pct", 0) < 0)
        total_pnl_pct = sum(p.get("pnl_pct", 0) for p in positions) / max(len(positions), 1)

        best_trade = max(positions, key=lambda p: p.get("pnl_pct", 0)) if positions else None
        worst_trade = min(positions, key=lambda p: p.get("pnl_pct", 0)) if positions else None

        return DemoMenuBuilder.pnl_report_view(
            positions=positions,
            total_pnl_usd=total_pnl,
            total_pnl_percent=total_pnl_pct,
            winners=winners,
            losers=losers,
            best_trade=best_trade,
            worst_trade=worst_trade,
        )

    elif action == "trailing_stops":
        trailing_stops = context.user_data.get("trailing_stops", [])
        return DemoMenuBuilder.trailing_stop_overview(
            trailing_stops=trailing_stops,
            positions=positions,
        )

    elif action == "tsl_new":
        return DemoMenuBuilder.trailing_stop_setup(positions=positions)

    elif action == "adj_cancel":
        return DemoMenuBuilder.positions_menu(
            positions=context.user_data.get("positions", []),
        )

    # Handle prefixed patterns
    if data.startswith("demo:pos_adjust:"):
        pos_id = data.split(":")[2]
        position = next((p for p in positions if p.get("id") == pos_id), None)

        if position:
            return DemoMenuBuilder.position_adjust_menu(
                pos_id=pos_id,
                symbol=position.get("symbol", "???"),
                current_tp=position.get("take_profit", 50.0),
                current_sl=position.get("stop_loss", 20.0),
                pnl_pct=position.get("pnl_pct", 0.0),
            )
        else:
            return _position_not_found(theme)

    elif data.startswith("demo:set_tp:"):
        return await _handle_set_tp(ctx, data, update, context, positions, theme)

    elif data.startswith("demo:set_sl:"):
        return await _handle_set_sl(ctx, data, update, context, positions, theme)

    elif data.startswith("demo:adj_tp:"):
        return await _handle_adj_tp(ctx, data, context, positions, theme)

    elif data.startswith("demo:adj_sl:"):
        return await _handle_adj_sl(ctx, data, context, positions, theme)

    elif data.startswith("demo:adj_save:"):
        return await _handle_adj_save(ctx, data, context, positions, theme)

    elif data.startswith("demo:tsl_select:"):
        pos_id = data.split(":")[2]
        position = next((p for p in positions if p.get("id") == pos_id), None)

        if position:
            return DemoMenuBuilder.trailing_stop_setup(position=position)
        else:
            return _position_not_found(theme)

    elif data.startswith("demo:tsl_create:"):
        return await _handle_tsl_create(ctx, data, context, positions, theme)

    elif data.startswith("demo:tsl_edit:"):
        return await _handle_tsl_edit(ctx, data, context, positions, theme)

    elif data.startswith("demo:tsl_delete:"):
        stop_id = data.split(":")[2]
        trailing_stops = context.user_data.get("trailing_stops", [])
        context.user_data["trailing_stops"] = [
            s for s in trailing_stops if s.get("id") != stop_id
        ]
        return DemoMenuBuilder.trailing_stop_overview(
            trailing_stops=context.user_data.get("trailing_stops", []),
            positions=positions,
        )

    elif data.startswith("demo:tsl_custom:"):
        pos_id = data.split(":")[2]
        text = f"""
{theme.SETTINGS} *CUSTOM TRAIL %*
{'=' * 20}

Enter a custom trailing percentage
(e.g., 7 for 7% trail).

_This feature coming soon!_
"""
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("5%", callback_data=f"demo:tsl_create:{pos_id}:5")],
            [InlineKeyboardButton("10%", callback_data=f"demo:tsl_create:{pos_id}:10")],
            [InlineKeyboardButton(f"{theme.BACK} Back", callback_data=f"demo:tsl_select:{pos_id}")],
        ])
        return text, keyboard

    elif data.startswith("demo:trailing_setup:"):
        pos_id = data.split(":")[2]
        position = next((p for p in positions if p.get("id") == pos_id), None)

        if position:
            return DemoMenuBuilder.trailing_stop_setup(position=position)
        else:
            return _position_not_found(theme)

    # Default
    return DemoMenuBuilder.positions_menu(positions=positions, total_pnl=total_pnl)


def _position_not_found(theme):
    """Return position not found error."""
    text = f"{theme.ERROR} Position not found"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:positions")]
    ])
    return text, keyboard


async def _handle_set_tp(ctx, data, update, context, positions, theme):
    """Handle set_tp callback."""
    DemoMenuBuilder = ctx.DemoMenuBuilder
    query = update.callback_query

    try:
        parts = data.split(":")
        pos_id = parts[2]
        tp_value = float(parts[3])

        for p in positions:
            if p.get("id") == pos_id:
                p["take_profit"] = tp_value
                break

        context.user_data["positions"] = positions

        position = next((p for p in positions if p.get("id") == pos_id), None)
        if position:
            return DemoMenuBuilder.position_adjust_menu(
                pos_id=pos_id,
                symbol=position.get("symbol", "???"),
                current_tp=tp_value,
                current_sl=position.get("stop_loss", 20.0),
                pnl_pct=position.get("pnl_pct", 0.0),
            )
        else:
            return _position_not_found(theme)
    except (ValueError, IndexError) as e:
        logger.warning(f"Set TP error: {e}")
        return DemoMenuBuilder.error_message(
            error="Error setting TP",
            retry_action="demo:positions",
        )


async def _handle_set_sl(ctx, data, update, context, positions, theme):
    """Handle set_sl callback."""
    DemoMenuBuilder = ctx.DemoMenuBuilder
    query = update.callback_query

    try:
        parts = data.split(":")
        pos_id = parts[2]
        sl_value = float(parts[3])

        for p in positions:
            if p.get("id") == pos_id:
                p["stop_loss"] = sl_value
                break

        context.user_data["positions"] = positions

        position = next((p for p in positions if p.get("id") == pos_id), None)
        if position:
            return DemoMenuBuilder.position_adjust_menu(
                pos_id=pos_id,
                symbol=position.get("symbol", "???"),
                current_tp=position.get("take_profit", 50.0),
                current_sl=sl_value,
                pnl_pct=position.get("pnl_pct", 0.0),
            )
        else:
            return _position_not_found(theme)
    except (ValueError, IndexError) as e:
        logger.warning(f"Set SL error: {e}")
        return DemoMenuBuilder.error_message(
            error="Error setting SL",
            retry_action="demo:positions",
        )


async def _handle_adj_tp(ctx, data, context, positions, theme):
    """Handle adj_tp callback (TP/SL adjustment)."""
    parts = data.split(":")
    if len(parts) >= 4:
        pos_id = parts[2]
        delta = float(parts[3])

        pos = next((p for p in positions if p.get("id") == pos_id), None)

        if pos:
            current_tp = pos.get("tp_percent", 50.0)
            new_tp = max(5.0, min(200.0, current_tp + delta))
            pos["tp_percent"] = new_tp

            entry_price = pos.get("entry_price", 0)
            if entry_price > 0:
                pos["tp_price"] = entry_price * (1 + new_tp / 100)

            context.user_data["positions"] = positions

            symbol = ctx.safe_symbol(pos.get("symbol", "TOKEN"))
            sl_pct = pos.get("sl_percent", 20.0)

            text = f"""
{theme.SETTINGS} *ADJUST TP/SL*
{theme.COIN} *{symbol}*

{theme.SNIPE} Take Profit: *+{new_tp:.0f}%*
{theme.ERROR} Stop Loss: *-{sl_pct:.0f}%*

_Use buttons to adjust_
"""
            keyboard = _build_adj_keyboard(theme, pos_id, new_tp, sl_pct)
            return text, keyboard
        else:
            return ctx.DemoMenuBuilder.error_message("Position not found")

    return ctx.DemoMenuBuilder.error_message("Invalid request")


async def _handle_adj_sl(ctx, data, context, positions, theme):
    """Handle adj_sl callback (TP/SL adjustment)."""
    parts = data.split(":")
    if len(parts) >= 4:
        pos_id = parts[2]
        delta = float(parts[3])

        pos = next((p for p in positions if p.get("id") == pos_id), None)

        if pos:
            current_sl = pos.get("sl_percent", 20.0)
            new_sl = max(5.0, min(100.0, current_sl + delta))
            pos["sl_percent"] = new_sl

            entry_price = pos.get("entry_price", 0)
            if entry_price > 0:
                pos["sl_price"] = entry_price * (1 - new_sl / 100)

            context.user_data["positions"] = positions

            symbol = ctx.safe_symbol(pos.get("symbol", "TOKEN"))
            tp_pct = pos.get("tp_percent", 50.0)

            text = f"""
{theme.SETTINGS} *ADJUST TP/SL*
{theme.COIN} *{symbol}*

{theme.SNIPE} Take Profit: *+{tp_pct:.0f}%*
{theme.ERROR} Stop Loss: *-{new_sl:.0f}%*

_Use buttons to adjust_
"""
            keyboard = _build_adj_keyboard(theme, pos_id, tp_pct, new_sl)
            return text, keyboard
        else:
            return ctx.DemoMenuBuilder.error_message("Position not found")

    return ctx.DemoMenuBuilder.error_message("Invalid request")


async def _handle_adj_save(ctx, data, context, positions, theme):
    """Handle adj_save callback."""
    DemoMenuBuilder = ctx.DemoMenuBuilder
    parts = data.split(":")
    pos_id = parts[2] if len(parts) > 2 else ""

    pos = next((p for p in positions if p.get("id") == pos_id), None)

    if pos:
        symbol = ctx.safe_symbol(pos.get("symbol", "TOKEN"))
        tp_pct = pos.get("tp_percent", 50.0)
        sl_pct = pos.get("sl_percent", 20.0)

        return DemoMenuBuilder.success_message(
            action="TP/SL Updated",
            details=f"*{symbol}*\nTake Profit: +{tp_pct:.0f}%\nStop Loss: -{sl_pct:.0f}%",
        )
    else:
        return DemoMenuBuilder.error_message("Position not found")


def _build_adj_keyboard(theme, pos_id, tp_pct, sl_pct):
    """Build TP/SL adjustment keyboard."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("-10%", callback_data=f"demo:adj_tp:{pos_id}:-10"),
            InlineKeyboardButton("-5%", callback_data=f"demo:adj_tp:{pos_id}:-5"),
            InlineKeyboardButton(f"TP +{tp_pct:.0f}%", callback_data=f"demo:adj_tp:{pos_id}:0"),
            InlineKeyboardButton("+5%", callback_data=f"demo:adj_tp:{pos_id}:5"),
            InlineKeyboardButton("+10%", callback_data=f"demo:adj_tp:{pos_id}:10"),
        ],
        [
            InlineKeyboardButton("-10%", callback_data=f"demo:adj_sl:{pos_id}:-10"),
            InlineKeyboardButton("-5%", callback_data=f"demo:adj_sl:{pos_id}:-5"),
            InlineKeyboardButton(f"SL -{sl_pct:.0f}%", callback_data=f"demo:adj_sl:{pos_id}:0"),
            InlineKeyboardButton("+5%", callback_data=f"demo:adj_sl:{pos_id}:5"),
            InlineKeyboardButton("+10%", callback_data=f"demo:adj_sl:{pos_id}:10"),
        ],
        [
            InlineKeyboardButton(f"{theme.SUCCESS} Save", callback_data=f"demo:adj_save:{pos_id}"),
            InlineKeyboardButton(f"{theme.CLOSE} Cancel", callback_data="demo:adj_cancel"),
        ],
    ])


async def _handle_tsl_create(ctx, data, context, positions, theme):
    """Handle tsl_create callback."""
    DemoMenuBuilder = ctx.DemoMenuBuilder
    try:
        parts = data.split(":")
        pos_id = parts[2]
        trail_percent = float(parts[3])

        position = next((p for p in positions if p.get("id") == pos_id), None)

        if position:
            current_price = position.get("current_price", 0)
            initial_stop = current_price * (1 - trail_percent / 100)

            new_stop = {
                "id": f"tsl_{pos_id}_{datetime.now().strftime('%H%M%S')}",
                "position_id": pos_id,
                "symbol": position.get("symbol", "???"),
                "trail_percent": trail_percent,
                "current_stop_price": initial_stop,
                "highest_price": current_price,
                "protected_value": position.get("value_usd", 0),
                "protected_pnl": position.get("pnl_pct", 0),
                "active": True,
                "created_at": datetime.now().isoformat(),
            }

            if "trailing_stops" not in context.user_data:
                context.user_data["trailing_stops"] = []
            context.user_data["trailing_stops"].append(new_stop)

            return DemoMenuBuilder.trailing_stop_created(
                symbol=position.get("symbol", "???"),
                trail_percent=trail_percent,
                initial_stop=initial_stop,
                current_price=current_price,
            )
        else:
            return DemoMenuBuilder.error_message(
                "Position not found",
                retry_action="demo:trailing_stops",
                context_hint="Position may have been closed"
            )
    except (ValueError, IndexError) as e:
        logger.warning(f"Trailing stop create error: {e}")
        return DemoMenuBuilder.operation_failed(
            "Trailing Stop",
            f"Invalid configuration: {str(e)[:50]}",
            retry_action="demo:trailing_stops"
        )


async def _handle_tsl_edit(ctx, data, context, positions, theme):
    """Handle tsl_edit callback."""
    DemoMenuBuilder = ctx.DemoMenuBuilder
    stop_id = data.split(":")[2]
    trailing_stops = context.user_data.get("trailing_stops", [])
    stop = next((s for s in trailing_stops if s.get("id") == stop_id), None)

    if stop:
        position = next((p for p in positions if p.get("id") == stop.get("position_id")), None)

        if position:
            return DemoMenuBuilder.trailing_stop_setup(position=position)
        else:
            text = f"{theme.SETTINGS} *Edit Trailing Stop*\n\n{stop.get('symbol', '???')} - {stop.get('trail_percent', 10)}%\n\n_Position no longer exists_"
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{theme.ERROR} Delete Stop", callback_data=f"demo:tsl_delete:{stop_id}")],
                [InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:trailing_stops")]
            ])
            return text, keyboard
    else:
        text = f"{theme.ERROR} Trailing stop not found"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:trailing_stops")]
        ])
        return text, keyboard
