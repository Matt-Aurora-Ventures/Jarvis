"""
Demo Bot - TP/SL Callback Handler

Handles: tpsl_*, set_tpsl_*, ladder_*
Provides UI for setting custom TP/SL values and ladder exit templates.
"""

import logging
from typing import Any, Dict, Tuple, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


# =============================================================================
# Ladder Exit Templates
# =============================================================================

LADDER_TEMPLATES = {
    "conservative": {
        "name": "Conservative",
        "description": "Lower targets, secure profits early",
        "exits": [
            {"pnl_multiple": 1.5, "percent": 50},  # 50% at 1.5x
            {"pnl_multiple": 2.0, "percent": 30},  # 30% at 2x
            {"pnl_multiple": 3.0, "percent": 20},  # 20% at 3x
        ],
    },
    "balanced": {
        "name": "Balanced (Default)",
        "description": "Standard 2x/5x/10x targets",
        "exits": [
            {"pnl_multiple": 2.0, "percent": 50},  # 50% at 2x
            {"pnl_multiple": 5.0, "percent": 30},  # 30% at 5x
            {"pnl_multiple": 10.0, "percent": 20}, # 20% at 10x
        ],
    },
    "aggressive": {
        "name": "Aggressive",
        "description": "Higher targets, let winners run",
        "exits": [
            {"pnl_multiple": 3.0, "percent": 40},  # 40% at 3x
            {"pnl_multiple": 10.0, "percent": 35}, # 35% at 10x
            {"pnl_multiple": 25.0, "percent": 25}, # 25% at 25x
        ],
    },
    "moon": {
        "name": "Moon Bag",
        "description": "Extreme targets, small early exits",
        "exits": [
            {"pnl_multiple": 5.0, "percent": 25},  # 25% at 5x
            {"pnl_multiple": 20.0, "percent": 35}, # 35% at 20x
            {"pnl_multiple": 50.0, "percent": 40}, # 40% at 50x (moon!)
        ],
    },
}


# =============================================================================
# Handler
# =============================================================================

async def handle_tpsl(
    ctx,
    action: str,
    data: str,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    state: Dict[str, Any],
) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Handle TP/SL setting callbacks.

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
    query = update.callback_query
    positions = state.get("positions", [])

    # Main TP/SL settings menu
    if action == "tpsl_settings":
        return _tpsl_settings_menu(ctx, context)

    # Quick TP/SL presets
    elif action == "tpsl_quick":
        return _tpsl_quick_menu(ctx, context)

    # Set quick TP/SL preset
    elif data.startswith("demo:tpsl_preset:"):
        parts = data.split(":")
        tp = float(parts[2]) if len(parts) > 2 else 50
        sl = float(parts[3]) if len(parts) > 3 else 20
        return await _apply_tpsl_preset(ctx, context, tp, sl)

    # Custom TP input
    elif action == "tpsl_custom_tp":
        context.user_data["awaiting_custom_tp"] = True
        return _custom_tp_prompt(ctx)

    # Custom SL input
    elif action == "tpsl_custom_sl":
        context.user_data["awaiting_custom_sl"] = True
        return _custom_sl_prompt(ctx)

    # Ladder exit menu
    elif action == "ladder_menu":
        return _ladder_menu(ctx, context)

    # Select ladder template
    elif data.startswith("demo:ladder_select:"):
        template_key = data.split(":")[2]
        return await _apply_ladder_template(ctx, context, template_key)

    # Show ladder preview
    elif data.startswith("demo:ladder_preview:"):
        template_key = data.split(":")[2]
        return _ladder_preview(ctx, template_key)

    # Disable ladder exits
    elif action == "ladder_disable":
        context.user_data["ladder_exits"] = None
        return DemoMenuBuilder.success_message(
            action="Ladder Exits Disabled",
            details="Positions will use simple TP/SL instead of ladder exits.",
        )

    # Edit position TP/SL
    elif data.startswith("demo:edit_tpsl:"):
        pos_id = data.split(":")[2]
        position = next((p for p in positions if p.get("id") == pos_id), None)
        if position:
            return _edit_position_tpsl(ctx, context, position)
        return DemoMenuBuilder.error_message("Position not found")

    # Apply TP to position
    elif data.startswith("demo:pos_tp:"):
        parts = data.split(":")
        pos_id = parts[2]
        tp_pct = float(parts[3]) if len(parts) > 3 else 50
        return await _apply_position_tp(ctx, context, positions, pos_id, tp_pct)

    # Apply SL to position
    elif data.startswith("demo:pos_sl:"):
        parts = data.split(":")
        pos_id = parts[2]
        sl_pct = float(parts[3]) if len(parts) > 3 else 20
        return await _apply_position_sl(ctx, context, positions, pos_id, sl_pct)

    # Default
    return _tpsl_settings_menu(ctx, context)


# =============================================================================
# Menu Builders
# =============================================================================

def _tpsl_settings_menu(ctx, context) -> Tuple[str, InlineKeyboardMarkup]:
    """Build main TP/SL settings menu."""
    theme = ctx.JarvisTheme

    current_tp = context.user_data.get("tp_percent", 50.0)
    current_sl = context.user_data.get("sl_percent", 20.0)
    ladder = context.user_data.get("ladder_exits")
    ladder_status = "Enabled" if ladder else "Disabled"

    text = f"""
{theme.SETTINGS} *TP/SL SETTINGS*
{'=' * 20}

*Current Default Settings:*
{theme.SNIPE} Take Profit: *+{current_tp:.0f}%*
{theme.ERROR} Stop Loss: *-{current_sl:.0f}%*
{theme.CHART} Ladder Exits: *{ladder_status}*

{'=' * 20}
_These defaults apply to new trades._
_Existing positions can be edited individually._
"""

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f"{theme.SNIPE} Quick Presets",
                callback_data="demo:tpsl_quick"
            ),
        ],
        [
            InlineKeyboardButton(
                f"{theme.SETTINGS} Custom TP",
                callback_data="demo:tpsl_custom_tp"
            ),
            InlineKeyboardButton(
                f"{theme.SETTINGS} Custom SL",
                callback_data="demo:tpsl_custom_sl"
            ),
        ],
        [
            InlineKeyboardButton(
                f"{theme.CHART} Ladder Exits",
                callback_data="demo:ladder_menu"
            ),
        ],
        [
            InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:settings"),
        ],
    ])

    return text, keyboard


def _tpsl_quick_menu(ctx, context) -> Tuple[str, InlineKeyboardMarkup]:
    """Build quick TP/SL preset menu."""
    theme = ctx.JarvisTheme

    text = f"""
{theme.SNIPE} *QUICK TP/SL PRESETS*
{'=' * 20}

Select a preset or customize:

*Conservative:* +20% TP / -10% SL
*Moderate:* +50% TP / -20% SL
*Aggressive:* +100% TP / -30% SL
*Degen:* +200% TP / -50% SL
"""

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "Conservative (+20/-10)",
                callback_data="demo:tpsl_preset:20:10"
            ),
        ],
        [
            InlineKeyboardButton(
                "Moderate (+50/-20)",
                callback_data="demo:tpsl_preset:50:20"
            ),
        ],
        [
            InlineKeyboardButton(
                "Aggressive (+100/-30)",
                callback_data="demo:tpsl_preset:100:30"
            ),
        ],
        [
            InlineKeyboardButton(
                "Degen (+200/-50)",
                callback_data="demo:tpsl_preset:200:50"
            ),
        ],
        [
            InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:tpsl_settings"),
        ],
    ])

    return text, keyboard


def _ladder_menu(ctx, context) -> Tuple[str, InlineKeyboardMarkup]:
    """Build ladder exit template menu."""
    theme = ctx.JarvisTheme

    current = context.user_data.get("ladder_exits")
    status = "Enabled" if current else "Disabled"

    text = f"""
{theme.CHART} *LADDER EXIT TEMPLATES*
{'=' * 20}

Ladder exits sell portions at multiple price targets:

*Conservative:* 1.5x/2x/3x
*Balanced:* 2x/5x/10x (default)
*Aggressive:* 3x/10x/25x
*Moon:* 5x/20x/50x

Current: *{status}*
"""

    buttons = []
    for key, template in LADDER_TEMPLATES.items():
        buttons.append([
            InlineKeyboardButton(
                f"{template['name']}",
                callback_data=f"demo:ladder_preview:{key}"
            ),
        ])

    if current:
        buttons.append([
            InlineKeyboardButton(
                f"{theme.CLOSE} Disable Ladder",
                callback_data="demo:ladder_disable"
            ),
        ])

    buttons.append([
        InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:tpsl_settings"),
    ])

    return text, InlineKeyboardMarkup(buttons)


def _ladder_preview(ctx, template_key: str) -> Tuple[str, InlineKeyboardMarkup]:
    """Preview a ladder template before applying."""
    theme = ctx.JarvisTheme

    if template_key not in LADDER_TEMPLATES:
        return ctx.DemoMenuBuilder.error_message("Template not found")

    template = LADDER_TEMPLATES[template_key]

    exits_text = ""
    for i, exit_tier in enumerate(template["exits"], 1):
        exits_text += f"  {i}. {exit_tier['percent']}% at {exit_tier['pnl_multiple']}x\n"

    text = f"""
{theme.CHART} *{template['name'].upper()}*
{'=' * 20}

{template['description']}

*Exit Tiers:*
{exits_text}
_Select to apply this template._
"""

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f"{theme.SUCCESS} Apply Template",
                callback_data=f"demo:ladder_select:{template_key}"
            ),
        ],
        [
            InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:ladder_menu"),
        ],
    ])

    return text, keyboard


def _custom_tp_prompt(ctx) -> Tuple[str, InlineKeyboardMarkup]:
    """Prompt for custom TP input."""
    theme = ctx.JarvisTheme

    text = f"""
{theme.SNIPE} *CUSTOM TAKE PROFIT*
{'=' * 20}

Enter your desired take-profit percentage:

*Examples:*
- 30 (sell at +30% profit)
- 75 (sell at +75% profit)
- 150 (sell at +150% profit)

*Limits:* 5% - 500%

_Send a number like "50" or "100"_
"""

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{theme.CLOSE} Cancel", callback_data="demo:tpsl_settings")],
    ])

    return text, keyboard


def _custom_sl_prompt(ctx) -> Tuple[str, InlineKeyboardMarkup]:
    """Prompt for custom SL input."""
    theme = ctx.JarvisTheme

    text = f"""
{theme.ERROR} *CUSTOM STOP LOSS*
{'=' * 20}

Enter your desired stop-loss percentage:

*Examples:*
- 10 (sell if price drops 10%)
- 25 (sell if price drops 25%)
- 50 (sell if price drops 50%)

*Limits:* 5% - 90%

_Send a number like "20" or "35"_
"""

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{theme.CLOSE} Cancel", callback_data="demo:tpsl_settings")],
    ])

    return text, keyboard


def _edit_position_tpsl(ctx, context, position: Dict) -> Tuple[str, InlineKeyboardMarkup]:
    """Edit TP/SL for a specific position."""
    theme = ctx.JarvisTheme

    symbol = position.get("symbol", "TOKEN")
    pos_id = position.get("id", "")
    current_tp = position.get("tp_percent", 50)
    current_sl = position.get("sl_percent", 20)

    text = f"""
{theme.SETTINGS} *EDIT TP/SL*
{theme.COIN} *{symbol}*
{'=' * 20}

{theme.SNIPE} Take Profit: *+{current_tp:.0f}%*
{theme.ERROR} Stop Loss: *-{current_sl:.0f}%*

_Adjust with buttons below:_
"""

    keyboard = InlineKeyboardMarkup([
        # TP row
        [
            InlineKeyboardButton("+20%", callback_data=f"demo:pos_tp:{pos_id}:20"),
            InlineKeyboardButton("+50%", callback_data=f"demo:pos_tp:{pos_id}:50"),
            InlineKeyboardButton("+100%", callback_data=f"demo:pos_tp:{pos_id}:100"),
            InlineKeyboardButton("+200%", callback_data=f"demo:pos_tp:{pos_id}:200"),
        ],
        # SL row
        [
            InlineKeyboardButton("-10%", callback_data=f"demo:pos_sl:{pos_id}:10"),
            InlineKeyboardButton("-20%", callback_data=f"demo:pos_sl:{pos_id}:20"),
            InlineKeyboardButton("-30%", callback_data=f"demo:pos_sl:{pos_id}:30"),
            InlineKeyboardButton("-50%", callback_data=f"demo:pos_sl:{pos_id}:50"),
        ],
        [
            InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:positions"),
        ],
    ])

    return text, keyboard


# =============================================================================
# Apply Functions
# =============================================================================

async def _apply_tpsl_preset(ctx, context, tp: float, sl: float) -> Tuple[str, InlineKeyboardMarkup]:
    """Apply TP/SL preset to user settings."""
    context.user_data["tp_percent"] = tp
    context.user_data["sl_percent"] = sl

    return ctx.DemoMenuBuilder.success_message(
        action="TP/SL Updated",
        details=f"Take Profit: +{tp:.0f}%\nStop Loss: -{sl:.0f}%\n\n_Applied to new trades._",
    )


async def _apply_ladder_template(ctx, context, template_key: str) -> Tuple[str, InlineKeyboardMarkup]:
    """Apply ladder exit template."""
    if template_key not in LADDER_TEMPLATES:
        return ctx.DemoMenuBuilder.error_message("Template not found")

    template = LADDER_TEMPLATES[template_key]
    ladder_exits = [
        {"pnl_multiple": e["pnl_multiple"], "percent": e["percent"], "executed": False}
        for e in template["exits"]
    ]

    context.user_data["ladder_exits"] = ladder_exits

    return ctx.DemoMenuBuilder.success_message(
        action=f"Ladder Template Applied: {template['name']}",
        details=f"{template['description']}\n\n_Applied to new trades with ladder exits._",
    )


async def _apply_position_tp(ctx, context, positions, pos_id: str, tp_pct: float) -> Tuple[str, InlineKeyboardMarkup]:
    """Apply TP to specific position."""
    for pos in positions:
        if pos.get("id") == pos_id:
            pos["tp_percent"] = tp_pct
            entry = pos.get("entry_price", 0)
            if entry > 0:
                pos["tp_price"] = entry * (1 + tp_pct / 100)
            context.user_data["positions"] = positions

            return ctx.DemoMenuBuilder.success_message(
                action="Take Profit Updated",
                details=f"{pos.get('symbol', 'TOKEN')}: +{tp_pct:.0f}%",
            )

    return ctx.DemoMenuBuilder.error_message("Position not found")


async def _apply_position_sl(ctx, context, positions, pos_id: str, sl_pct: float) -> Tuple[str, InlineKeyboardMarkup]:
    """Apply SL to specific position."""
    for pos in positions:
        if pos.get("id") == pos_id:
            pos["sl_percent"] = sl_pct
            entry = pos.get("entry_price", 0)
            if entry > 0:
                pos["sl_price"] = entry * (1 - sl_pct / 100)
            context.user_data["positions"] = positions

            return ctx.DemoMenuBuilder.success_message(
                action="Stop Loss Updated",
                details=f"{pos.get('symbol', 'TOKEN')}: -{sl_pct:.0f}%",
            )

    return ctx.DemoMenuBuilder.error_message("Position not found")


# =============================================================================
# Input Handlers (for text responses)
# =============================================================================

def validate_custom_tp(value: str) -> Tuple[bool, float, str]:
    """
    Validate custom TP input.

    Returns:
        Tuple of (is_valid, value, error_message)
    """
    try:
        tp = float(value.strip())
        if tp < 5:
            return False, 0, "TP must be at least 5%"
        if tp > 500:
            return False, 0, "TP cannot exceed 500%"
        return True, tp, ""
    except ValueError:
        return False, 0, "Invalid number. Enter a number like 50 or 100"


def validate_custom_sl(value: str) -> Tuple[bool, float, str]:
    """
    Validate custom SL input.

    Returns:
        Tuple of (is_valid, value, error_message)
    """
    try:
        sl = float(value.strip())
        if sl < 5:
            return False, 0, "SL must be at least 5%"
        if sl > 90:
            return False, 0, "SL cannot exceed 90%"
        return True, sl, ""
    except ValueError:
        return False, 0, "Invalid number. Enter a number like 20 or 30"
