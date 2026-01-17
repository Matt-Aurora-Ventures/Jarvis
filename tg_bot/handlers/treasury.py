"""
Treasury Display Handler - Telegram commands for portfolio and trading display.

Commands:
- /treasury - Full treasury display with positions, performance, streaks
- /portfolio or /p - Quick portfolio overview
- /balance or /b - Balance summary
- /pnl - P&L summary by period
"""

import logging
from typing import Optional
from pathlib import Path
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from tg_bot.handlers import error_handler
from bots.treasury.display import TreasuryDisplay

logger = logging.getLogger(__name__)


class TreasuryHandler:
    """Handler for treasury and portfolio commands."""

    def __init__(self, data_dir: str = None):
        """Initialize treasury handler."""
        self.data_dir = Path(data_dir or "./bots/treasury")
        self.positions_file = self.data_dir / ".positions.json"
        self.trades_file = self.data_dir / ".trade_history.json"

    @error_handler
    async def handle_treasury(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /treasury command - Full display."""
        try:
            # Load treasury data
            display = TreasuryDisplay.from_json_files(
                str(self.positions_file),
                str(self.trades_file),
            )

            # Generate display
            full_display = display.generate_full_display(include_recent_trades=True)

            # Split into chunks if too long (Telegram limit 4096 chars)
            chunks = self._split_message(full_display, 4096)

            for i, chunk in enumerate(chunks):
                await update.message.reply_text(
                    f"```\n{chunk}\n```",
                    parse_mode=ParseMode.MARKDOWN,
                )

                # Add separator between chunks
                if i < len(chunks) - 1:
                    await update.message.reply_text("...")

        except Exception as e:
            logger.error(f"Error in treasury handler: {e}")
            await update.message.reply_text(
                f"❌ Failed to load treasury data: {str(e)[:100]}",
                parse_mode=ParseMode.MARKDOWN,
            )

    @error_handler
    async def handle_portfolio(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /portfolio or /p command - Quick overview."""
        try:
            display = TreasuryDisplay.from_json_files(
                str(self.positions_file),
                str(self.trades_file),
            )

            # Generate portfolio section only
            portfolio_section = display._build_portfolio_section()

            # Also add summary
            total_value = display.calculate_total_portfolio_value()
            total_pnl = display.calculate_total_pnl()
            win_rate = display.calculate_win_rate()

            summary = f"""
📊 PORTFOLIO SUMMARY
{'='*60}
Portfolio Value:      ${total_value:,.2f}
Total P&L:            ${total_pnl:,.2f}
Win Rate:             {win_rate:.1f}%
Open Positions:       {len(display.positions)}
Closed Trades:        {len(display.closed_trades)}
"""

            message = summary + "\n" + portfolio_section

            # Split and send
            chunks = self._split_message(message, 4096)
            for chunk in chunks:
                await update.message.reply_text(
                    f"```\n{chunk}\n```",
                    parse_mode=ParseMode.MARKDOWN,
                )

        except Exception as e:
            logger.error(f"Error in portfolio handler: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)[:100]}")

    @error_handler
    async def handle_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /balance or /b command - Balance summary."""
        try:
            display = TreasuryDisplay.from_json_files(
                str(self.positions_file),
                str(self.trades_file),
            )

            # Generate balance summary
            total_value = display.calculate_total_portfolio_value()
            unrealized_pnl = display.calculate_total_unrealized_pnl()
            realized_pnl = display.calculate_total_realized_pnl()
            total_pnl = display.calculate_total_pnl()

            pnl_pct = (total_pnl / total_value * 100) if total_value > 0 else 0

            message = f"""
💰 BALANCE SUMMARY

Portfolio Value:  ${total_value:>12,.2f}
───────────────────────────
P&L (Realized):   ${realized_pnl:>12,.2f}
P&L (Unrealized): ${unrealized_pnl:>12,.2f}
P&L (Total):      ${total_pnl:>12,.2f}
P&L %:            {pnl_pct:>12.2f}%
───────────────────────────
Positions:        {len(display.positions):>12}
Trades Closed:    {len(display.closed_trades):>12}
"""

            await update.message.reply_text(
                f"```{message}\n```",
                parse_mode=ParseMode.MARKDOWN,
            )

        except Exception as e:
            logger.error(f"Error in balance handler: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)[:100]}")

    @error_handler
    async def handle_pnl(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /pnl command - P&L details."""
        try:
            display = TreasuryDisplay.from_json_files(
                str(self.positions_file),
                str(self.trades_file),
            )

            # Generate performance section
            perf_section = display._build_performance_section()
            streaks_section = display._build_streaks_section()

            message = perf_section + "\n" + streaks_section

            await update.message.reply_text(
                f"```\n{message}\n```",
                parse_mode=ParseMode.MARKDOWN,
            )

        except Exception as e:
            logger.error(f"Error in PnL handler: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)[:100]}")

    @error_handler
    async def handle_sector(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /sector command - Sector breakdown."""
        try:
            display = TreasuryDisplay.from_json_files(
                str(self.positions_file),
                str(self.trades_file),
            )

            # Generate sector section
            sector_section = display._build_sector_section()

            await update.message.reply_text(
                f"```\n{sector_section}\n```",
                parse_mode=ParseMode.MARKDOWN,
            )

        except Exception as e:
            logger.error(f"Error in sector handler: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)[:100]}")

    @staticmethod
    def _split_message(text: str, max_length: int = 4096) -> list:
        """Split long message into chunks."""
        if len(text) <= max_length:
            return [text]

        chunks = []
        current_chunk = ""

        for line in text.split("\n"):
            if len(current_chunk) + len(line) + 1 > max_length:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = line
            else:
                current_chunk += "\n" + line if current_chunk else line

        if current_chunk:
            chunks.append(current_chunk)

        return chunks


# Singleton instance
_handler: Optional[TreasuryHandler] = None


def get_treasury_handler(data_dir: str = None) -> TreasuryHandler:
    """Get or create treasury handler."""
    global _handler
    if _handler is None:
        _handler = TreasuryHandler(data_dir)
    return _handler


__all__ = [
    'TreasuryHandler',
    'get_treasury_handler',
]
