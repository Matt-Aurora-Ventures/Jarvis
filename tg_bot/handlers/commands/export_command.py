"""
/export Command Handler.

Provides trading history export in CSV and JSON formats.
"""

import csv
import io
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional, Any

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from tg_bot.handlers import error_handler, admin_only
from tg_bot.config import get_config

logger = logging.getLogger(__name__)


# Paths to trading data
POSITIONS_PATH = Path.home() / ".lifeos" / "trading" / "positions.json"
TRADES_PATH = Path.home() / ".lifeos" / "trading" / "trades.json"
PNL_PATH = Path.home() / ".lifeos" / "trading" / "pnl_history.json"


async def get_trading_data() -> Dict[str, Any]:
    """
    Collect all trading data for export.

    Returns:
        Dictionary with positions, trades, and PnL data
    """
    data = {
        "positions": [],
        "trades": [],
        "pnl": [],
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }

    # Load positions
    if POSITIONS_PATH.exists():
        try:
            with open(POSITIONS_PATH, "r") as f:
                data["positions"] = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load positions: {e}")

    # Load trades
    if TRADES_PATH.exists():
        try:
            with open(TRADES_PATH, "r") as f:
                data["trades"] = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load trades: {e}")

    # Load PnL history
    if PNL_PATH.exists():
        try:
            with open(PNL_PATH, "r") as f:
                data["pnl"] = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load PnL: {e}")

    # Also check treasury positions
    treasury_pos_path = Path("bots/treasury/.positions.json")
    if treasury_pos_path.exists():
        try:
            with open(treasury_pos_path, "r") as f:
                treasury_positions = json.load(f)
                if isinstance(treasury_positions, list):
                    data["positions"].extend(treasury_positions)
                elif isinstance(treasury_positions, dict):
                    data["positions"].append(treasury_positions)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load treasury positions: {e}")

    return data


def format_positions_csv(positions: List[Dict]) -> str:
    """
    Format positions as CSV.

    Args:
        positions: List of position dictionaries

    Returns:
        CSV string
    """
    output = io.StringIO()

    # Define columns
    fieldnames = [
        "symbol", "address", "entry_price", "current_price",
        "amount", "value_usd", "pnl_usd", "pnl_pct",
        "entry_time", "holding_time_hours"
    ]

    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()

    for pos in positions:
        # Normalize field names
        row = {
            "symbol": pos.get("symbol", pos.get("token_symbol", "")),
            "address": pos.get("address", pos.get("token_address", "")),
            "entry_price": pos.get("entry_price", pos.get("avg_entry", 0)),
            "current_price": pos.get("current_price", 0),
            "amount": pos.get("amount", pos.get("quantity", 0)),
            "value_usd": pos.get("value_usd", pos.get("current_value", 0)),
            "pnl_usd": pos.get("pnl_usd", pos.get("unrealized_pnl", 0)),
            "pnl_pct": pos.get("pnl_pct", pos.get("pnl_percentage", 0)),
            "entry_time": pos.get("entry_time", pos.get("created_at", "")),
            "holding_time_hours": pos.get("holding_time_hours", ""),
        }
        writer.writerow(row)

    return output.getvalue()


def format_trades_csv(trades: List[Dict]) -> str:
    """
    Format trades as CSV.

    Args:
        trades: List of trade dictionaries

    Returns:
        CSV string
    """
    output = io.StringIO()

    fieldnames = [
        "id", "symbol", "side", "amount", "price",
        "value_usd", "fee", "timestamp", "status"
    ]

    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()

    for trade in trades:
        row = {
            "id": trade.get("id", trade.get("tx_hash", "")),
            "symbol": trade.get("symbol", trade.get("token_symbol", "")),
            "side": trade.get("side", trade.get("type", "")),
            "amount": trade.get("amount", trade.get("quantity", 0)),
            "price": trade.get("price", 0),
            "value_usd": trade.get("value_usd", trade.get("total_value", 0)),
            "fee": trade.get("fee", 0),
            "timestamp": trade.get("timestamp", trade.get("created_at", "")),
            "status": trade.get("status", "completed"),
        }
        writer.writerow(row)

    return output.getvalue()


def format_pnl_csv(pnl_history: List[Dict]) -> str:
    """
    Format PnL history as CSV.

    Args:
        pnl_history: List of PnL records

    Returns:
        CSV string
    """
    output = io.StringIO()

    fieldnames = [
        "date", "realized_pnl", "unrealized_pnl", "total_pnl",
        "portfolio_value", "win_rate", "num_trades"
    ]

    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()

    for record in pnl_history:
        writer.writerow(record)

    return output.getvalue()


@error_handler
@admin_only
async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /export command - export trading data.

    Usage:
        /export csv - Export as CSV
        /export json - Export as JSON
    """
    format_type = "csv"
    if context.args:
        format_type = context.args[0].lower()

    if format_type not in ("csv", "json"):
        await update.message.reply_text(
            "\U0001f4e4 *Export Trading Data*\n\n"
            "*Usage:*\n"
            "`/export csv` - Export as CSV files\n"
            "`/export json` - Export as JSON file\n\n"
            "*Includes:*\n"
            "  - Open positions\n"
            "  - Trade history\n"
            "  - PnL records",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # Send loading message
    loading = await update.message.reply_text(
        "_Preparing export..._",
        parse_mode=ParseMode.MARKDOWN,
    )

    try:
        data = await get_trading_data()

        if format_type == "json":
            # Export as single JSON file
            json_content = json.dumps(data, indent=2)
            filename = f"jarvis_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

            await update.message.reply_document(
                document=io.BytesIO(json_content.encode()),
                filename=filename,
                caption=f"\U0001f4e4 *Export Complete*\n\n"
                        f"Positions: {len(data['positions'])}\n"
                        f"Trades: {len(data['trades'])}\n"
                        f"PnL records: {len(data['pnl'])}",
                parse_mode=ParseMode.MARKDOWN,
            )

        else:  # CSV
            # Export positions
            if data["positions"]:
                positions_csv = format_positions_csv(data["positions"])
                await update.message.reply_document(
                    document=io.BytesIO(positions_csv.encode()),
                    filename=f"positions_{datetime.now().strftime('%Y%m%d')}.csv",
                    caption=f"\U0001f4ca *Positions* ({len(data['positions'])} records)",
                    parse_mode=ParseMode.MARKDOWN,
                )

            # Export trades
            if data["trades"]:
                trades_csv = format_trades_csv(data["trades"])
                await update.message.reply_document(
                    document=io.BytesIO(trades_csv.encode()),
                    filename=f"trades_{datetime.now().strftime('%Y%m%d')}.csv",
                    caption=f"\U0001f4b0 *Trades* ({len(data['trades'])} records)",
                    parse_mode=ParseMode.MARKDOWN,
                )

            # Export PnL
            if data["pnl"]:
                pnl_csv = format_pnl_csv(data["pnl"])
                await update.message.reply_document(
                    document=io.BytesIO(pnl_csv.encode()),
                    filename=f"pnl_{datetime.now().strftime('%Y%m%d')}.csv",
                    caption=f"\U0001f4c8 *PnL History* ({len(data['pnl'])} records)",
                    parse_mode=ParseMode.MARKDOWN,
                )

            if not any([data["positions"], data["trades"], data["pnl"]]):
                await update.message.reply_text(
                    "\U0001f4e4 *Export Complete*\n\n"
                    "_No trading data found to export._",
                    parse_mode=ParseMode.MARKDOWN,
                )

        await loading.delete()

    except Exception as e:
        logger.error(f"Export failed: {e}")
        await loading.edit_text(
            f"\u274c *Export Failed*\n\n_Error: {str(e)[:100]}_",
            parse_mode=ParseMode.MARKDOWN,
        )


@error_handler
@admin_only
async def export_positions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /exportpos command - quick positions export.
    """
    data = await get_trading_data()

    if not data["positions"]:
        await update.message.reply_text(
            "_No positions to export._",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    csv_content = format_positions_csv(data["positions"])

    await update.message.reply_document(
        document=io.BytesIO(csv_content.encode()),
        filename=f"positions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        caption=f"\U0001f4ca *Positions Export*\n\n{len(data['positions'])} positions",
        parse_mode=ParseMode.MARKDOWN,
    )


@error_handler
@admin_only
async def export_trades(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /exporttrades command - quick trades export.
    """
    data = await get_trading_data()

    if not data["trades"]:
        await update.message.reply_text(
            "_No trades to export._",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    csv_content = format_trades_csv(data["trades"])

    await update.message.reply_document(
        document=io.BytesIO(csv_content.encode()),
        filename=f"trades_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        caption=f"\U0001f4b0 *Trades Export*\n\n{len(data['trades'])} trades",
        parse_mode=ParseMode.MARKDOWN,
    )


__all__ = [
    "export_command",
    "export_positions",
    "export_trades",
    "get_trading_data",
    "format_positions_csv",
    "format_trades_csv",
]
