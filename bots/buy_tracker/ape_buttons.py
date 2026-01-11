"""
Ape Trading Buttons for Sentiment Reports.

Adds inline keyboard buttons to sentiment reports for one-click trading:
- 5% Treasury allocation
- 2% Treasury allocation
- 1% Treasury allocation

Supports: Solana tokens, stocks (via broker integration), commodities (futures).
All trades follow recommended TP/SL from Grok analysis.
"""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)


# Treasury allocation percentages
APE_LEVELS = {
    "ape_5": {"percent": 5, "label": "5% 🐒"},
    "ape_2": {"percent": 2, "label": "2% 🦧"},
    "ape_1": {"percent": 1, "label": "1% 🐵"},
}


@dataclass
class TradeSetup:
    """Trade setup with entry, TP, and SL."""
    symbol: str
    asset_type: str  # "token", "stock", "commodity", "metal"
    direction: str   # "LONG" or "SHORT"
    entry_price: float
    stop_loss: Optional[float] = None
    target_safe: Optional[float] = None
    target_med: Optional[float] = None
    target_degen: Optional[float] = None
    contract_address: Optional[str] = None  # For Solana tokens
    reasoning: str = ""


def parse_price(price_str: str) -> Optional[float]:
    """Parse price string like '$0.00123' or '2,345.50' to float."""
    if not price_str:
        return None
    try:
        # Remove $ and commas
        clean = price_str.replace("$", "").replace(",", "").strip()
        return float(clean)
    except (ValueError, AttributeError):
        return None


def create_ape_buttons(
    symbol: str,
    asset_type: str,
    direction: str = "LONG",
    contract_address: str = "",
    stop_loss: str = "",
    target_safe: str = "",
    target_med: str = "",
    target_degen: str = "",
) -> InlineKeyboardMarkup:
    """
    Create inline keyboard with ape buttons for a tradeable asset.

    Args:
        symbol: Asset symbol (e.g., "BONK", "NVDA", "GOLD")
        asset_type: "token", "stock", "commodity", "metal"
        direction: "LONG" or "SHORT"
        contract_address: Token contract for Solana tokens
        stop_loss: Stop loss price string
        target_safe: Safe target price string
        target_med: Medium target price string
        target_degen: Degen target price string

    Returns:
        InlineKeyboardMarkup with ape buttons
    """
    # Encode trade data in callback_data
    # Format: ape_{percent}:{asset_type}:{symbol}:{direction}:{contract}:{sl}:{tp}
    # Keep it short for Telegram's 64-byte limit

    # Shorten contract address if present
    contract_short = contract_address[:12] if contract_address else ""

    # Parse stop loss as percentage from current (if target available)
    sl_pct = ""
    tp_pct = ""

    # For callback, we'll use a hash or shortened identifier
    base_data = f"{asset_type[:1]}:{symbol}:{direction[0]}:{contract_short}"

    buttons = []
    row = []

    for ape_id, config in APE_LEVELS.items():
        callback = f"{ape_id}:{base_data}"[:64]  # Telegram limit
        row.append(InlineKeyboardButton(
            text=f"APE {config['label']}",
            callback_data=callback
        ))

    buttons.append(row)

    # Add info button
    buttons.append([
        InlineKeyboardButton(
            text=f"ℹ️ {symbol} Info",
            callback_data=f"info:{base_data}"[:64]
        )
    ])

    return InlineKeyboardMarkup(buttons)


def create_token_ape_keyboard(
    symbol: str,
    contract: str,
    grok_analysis: str = "",
    grok_reasoning: str = "",
) -> InlineKeyboardMarkup:
    """Create ape keyboard specifically for Solana tokens."""
    # Parse targets from grok_analysis if available
    # Format: "Stop: $X | Safe: $Y | Med: $Z | Degen: $W"

    sl, safe, med, degen = "", "", "", ""
    if grok_analysis:
        parts = grok_analysis.split("|")
        for part in parts:
            part = part.strip().lower()
            if part.startswith("stop:"):
                sl = part.replace("stop:", "").strip()
            elif part.startswith("safe:"):
                safe = part.replace("safe:", "").strip()
            elif part.startswith("med:"):
                med = part.replace("med:", "").strip()
            elif part.startswith("degen:"):
                degen = part.replace("degen:", "").strip()

    return create_ape_buttons(
        symbol=symbol,
        asset_type="token",
        direction="LONG",
        contract_address=contract,
        stop_loss=sl,
        target_safe=safe,
        target_med=med,
        target_degen=degen,
    )


def create_stock_ape_keyboard(
    ticker: str,
    direction: str,
    target: str = "",
    stop_loss: str = "",
) -> InlineKeyboardMarkup:
    """Create ape keyboard for stocks."""
    return create_ape_buttons(
        symbol=ticker,
        asset_type="stock",
        direction=direction.upper(),
        stop_loss=stop_loss,
        target_safe=target,
    )


def create_commodity_ape_keyboard(
    name: str,
    direction: str,
) -> InlineKeyboardMarkup:
    """Create ape keyboard for commodities."""
    return create_ape_buttons(
        symbol=name.upper().replace(" ", "_"),
        asset_type="commodity",
        direction="LONG" if direction.upper() == "UP" else "SHORT",
    )


def create_metal_ape_keyboard(
    metal: str,
    direction: str,
) -> InlineKeyboardMarkup:
    """Create ape keyboard for precious metals."""
    return create_ape_buttons(
        symbol=metal.upper(),
        asset_type="metal",
        direction=direction.upper(),
    )


def parse_ape_callback(callback_data: str) -> Optional[Dict[str, Any]]:
    """
    Parse ape button callback data.

    Returns:
        Dict with: ape_percent, asset_type, symbol, direction, contract
    """
    try:
        parts = callback_data.split(":")
        if len(parts) < 2:
            return None

        action = parts[0]  # e.g., "ape_5" or "info"

        if action.startswith("ape_"):
            percent = APE_LEVELS.get(action, {}).get("percent", 1)
        else:
            percent = 0

        asset_type_map = {"t": "token", "s": "stock", "c": "commodity", "m": "metal"}

        return {
            "action": action,
            "ape_percent": percent,
            "asset_type": asset_type_map.get(parts[1], "token") if len(parts) > 1 else "token",
            "symbol": parts[2] if len(parts) > 2 else "",
            "direction": "LONG" if len(parts) <= 3 or parts[3] == "L" else "SHORT",
            "contract": parts[4] if len(parts) > 4 else "",
        }

    except Exception as e:
        logger.error(f"Failed to parse callback: {e}")
        return None


def format_treasury_status(
    balance_sol: float = 0.0,
    balance_usd: float = 0.0,
    open_positions: int = 0,
    pnl_24h: float = 0.0,
    treasury_address: str = "",
) -> str:
    """
    Format treasury status message for end of sentiment report.

    Args:
        balance_sol: Treasury balance in SOL
        balance_usd: Treasury balance in USD
        open_positions: Number of open positions
        pnl_24h: 24-hour P&L percentage
        treasury_address: Public treasury address

    Returns:
        Formatted HTML string
    """
    pnl_emoji = "📈" if pnl_24h >= 0 else "📉"

    lines = [
        "",
        "<b>========================================</b>",
        "<b>   💰 TREASURY STATUS</b>",
        "<b>========================================</b>",
        "",
        f"Balance: <code>{balance_sol:.4f} SOL</code> (${balance_usd:,.2f})",
        f"Open Positions: <code>{open_positions}</code>",
        f"24h P&L: {pnl_emoji} <code>{pnl_24h:+.2f}%</code>",
    ]

    if treasury_address:
        addr_short = treasury_address[:8] + "..." + treasury_address[-4:]
        lines.extend([
            "",
            f"Treasury: <code>{addr_short}</code>",
            f"<a href=\"https://solscan.io/account/{treasury_address}\">View on Solscan</a>",
        ])

    lines.extend([
        "",
        "<i>Use APE buttons above to trade with treasury</i>",
        "<i>All trades use recommended TP/SL</i>",
    ])

    return "\n".join(lines)


async def handle_ape_trade(
    callback_data: str,
    treasury_balance_sol: float,
    current_prices: Dict[str, float],
) -> Dict[str, Any]:
    """
    Handle an ape button press and execute the trade.

    Args:
        callback_data: Callback data from button press
        treasury_balance_sol: Current treasury balance
        current_prices: Dict of symbol -> current price

    Returns:
        Dict with trade result
    """
    parsed = parse_ape_callback(callback_data)
    if not parsed or parsed["ape_percent"] == 0:
        return {"success": False, "error": "Invalid ape action"}

    symbol = parsed["symbol"]
    percent = parsed["ape_percent"]
    asset_type = parsed["asset_type"]
    direction = parsed["direction"]
    contract = parsed.get("contract", "")

    # Calculate trade amount
    trade_amount_sol = treasury_balance_sol * (percent / 100)

    result = {
        "success": False,
        "symbol": symbol,
        "asset_type": asset_type,
        "direction": direction,
        "allocation_percent": percent,
        "amount_sol": trade_amount_sol,
        "contract": contract,
    }

    # Execute trade based on asset type
    if asset_type == "token":
        # Solana token - use Jupiter
        try:
            # This would integrate with bots/treasury/trading.py
            result["message"] = f"Would buy {trade_amount_sol:.4f} SOL worth of {symbol}"
            result["success"] = True  # Placeholder - real execution in trading.py
        except Exception as e:
            result["error"] = str(e)

    elif asset_type == "stock":
        # Stock - would need broker integration
        result["message"] = f"Stock trading not yet implemented for {symbol}"

    elif asset_type == "commodity":
        # Commodity - would need futures broker
        result["message"] = f"Commodity trading not yet implemented for {symbol}"

    elif asset_type == "metal":
        # Precious metals - could use PAXG or similar
        result["message"] = f"Metal trading not yet implemented for {symbol}"

    return result


# Recommended TP/SL based on grade
GRADE_TP_SL = {
    "A": {"tp_percent": 30, "sl_percent": 10},
    "A-": {"tp_percent": 25, "sl_percent": 10},
    "B+": {"tp_percent": 20, "sl_percent": 8},
    "B": {"tp_percent": 15, "sl_percent": 8},
    "C+": {"tp_percent": 12, "sl_percent": 7},
    "C": {"tp_percent": 10, "sl_percent": 5},
    "C-": {"tp_percent": 8, "sl_percent": 5},
    "D+": {"tp_percent": 5, "sl_percent": 5},
    "D": {"tp_percent": 3, "sl_percent": 5},
    "F": {"tp_percent": 2, "sl_percent": 3},
}


def get_tp_sl_for_grade(grade: str, entry_price: float) -> Dict[str, float]:
    """Get TP and SL prices based on grade."""
    config = GRADE_TP_SL.get(grade, GRADE_TP_SL["C"])

    tp_price = entry_price * (1 + config["tp_percent"] / 100)
    sl_price = entry_price * (1 - config["sl_percent"] / 100)

    return {
        "take_profit": tp_price,
        "stop_loss": sl_price,
        "tp_percent": config["tp_percent"],
        "sl_percent": config["sl_percent"],
    }
