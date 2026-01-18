"""
Jarvis Treasury Telegram Trading UI
Stunning Jupiter-like interface with live metrics and controls
"""

import os
import asyncio
import logging
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    InputMediaPhoto
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)
from telegram.constants import ParseMode

from .wallet import SecureWallet, WalletInfo
from .jupiter import JupiterClient
from .trading import TradingEngine, Position, TradeDirection, RiskLevel, TradeStatus

logger = logging.getLogger(__name__)


class TradingUI:
    """
    Telegram Trading Interface for Jarvis Treasury.

    Features:
    - Live portfolio dashboard with real-time updates
    - One-click trading from sentiment signals
    - Position management with TP/SL controls
    - Full trade history and P&L reports
    - Admin-only access for security
    """

    # UI Constants
    REFRESH_INTERVAL = 30  # seconds

    # Emoji constants for visual flair
    EMOJI = {
        'bull': '',
        'bear': '',
        'money': '',
        'chart': '',
        'rocket': '',
        'fire': '',
        'warning': '',
        'check': '',
        'cross': '',
        'diamond': '',
        'crown': '',
        'target': '',
        'stop': '',
        'clock': '',
        'wallet': '',
        'trade': '',
        'profit': '',
        'loss': '',
        'neutral': '',
        'settings': '',
        'refresh': '',
        'back': '',
        'close': '',
    }

    def __init__(
        self,
        bot_token: str,
        trading_engine: TradingEngine,
        admin_ids: List[int]
    ):
        """
        Initialize Trading UI.

        Args:
            bot_token: Telegram bot token
            trading_engine: TradingEngine instance
            admin_ids: List of admin Telegram user IDs
        """
        self.bot_token = bot_token
        self.engine = trading_engine
        self.admin_ids = admin_ids
        self.app: Optional[Application] = None
        self._running = False
        self._dashboard_messages: Dict[int, int] = {}  # user_id -> message_id

    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin."""
        return user_id in self.admin_ids

    async def start(self):
        """Start the trading bot."""
        self.app = Application.builder().token(self.bot_token).build()

        # Command handlers
        self.app.add_handler(CommandHandler("start", self._cmd_start))
        self.app.add_handler(CommandHandler("dashboard", self._cmd_dashboard))
        self.app.add_handler(CommandHandler("portfolio", self._cmd_portfolio))
        self.app.add_handler(CommandHandler("positions", self._cmd_positions))
        self.app.add_handler(CommandHandler("history", self._cmd_history))
        self.app.add_handler(CommandHandler("trade", self._cmd_trade))
        self.app.add_handler(CommandHandler("close", self._cmd_close))
        self.app.add_handler(CommandHandler("report", self._cmd_report))
        self.app.add_handler(CommandHandler("settings", self._cmd_settings))
        self.app.add_handler(CommandHandler("help", self._cmd_help))

        # Callback handlers
        self.app.add_handler(CallbackQueryHandler(self._handle_callback))

        self._running = True
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling(drop_pending_updates=True)

        # Start background position monitor
        asyncio.create_task(self._position_monitor_loop())

        logger.info("Trading UI started")

    async def _position_monitor_loop(self):
        """
        Background task to monitor positions and close breached stop losses.

        Runs every 60 seconds to catch positions that missed their limit orders.
        """
        logger.info("Position monitor started")
        while self._running:
            try:
                # Monitor and close any breached positions
                closed = await self.engine.monitor_stop_losses()

                # Notify admins of any closed positions
                if closed and self.admin_ids:
                    for pos_info in closed:
                        symbol = pos_info.get("symbol", "UNKNOWN")
                        reason = pos_info.get("reason", "AUTO")
                        pnl_usd = pos_info.get("pnl_usd", 0)
                        pnl_pct = pos_info.get("pnl_pct", 0)

                        emoji = self.EMOJI['profit'] if pnl_usd >= 0 else self.EMOJI['loss']
                        alert = (
                            f"{self.EMOJI['warning']} <b>AUTO-CLOSED POSITION</b>\n\n"
                            f"<b>Token:</b> {symbol}\n"
                            f"<b>Reason:</b> {reason}\n"
                            f"<b>P&L:</b> {emoji} <code>${pnl_usd:+.2f}</code> ({pnl_pct:+.1f}%)"
                        )

                        for admin_id in self.admin_ids:
                            try:
                                await self.app.bot.send_message(
                                    chat_id=admin_id,
                                    text=alert,
                                    parse_mode=ParseMode.HTML
                                )
                            except Exception as e:
                                logger.warning(f"Failed to notify admin {admin_id}: {e}")

            except Exception as e:
                logger.error(f"Position monitor error: {e}")

            # Wait 60 seconds before next check
            await asyncio.sleep(60)

    async def stop(self):
        """Stop the trading bot."""
        self._running = False
        if self.app:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()

    # ============ Command Handlers ============

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        user_id = update.effective_user.id

        if not self.is_admin(user_id):
            await update.message.reply_text(
                " <b>Access Denied</b>\n\n"
                "This trading interface is restricted to authorized admins only.",
                parse_mode=ParseMode.HTML
            )
            return

        welcome = f"""
{self.EMOJI['crown']} <b>JARVIS TREASURY TRADING</b> {self.EMOJI['crown']}

Welcome to the Jarvis Treasury Management System.

<b>Quick Commands:</b>
/dashboard - Live portfolio dashboard
/positions - View open positions
/trade - Execute a trade
/report - Performance report
/help - Full command list

<b>Status:</b> {'<code>DRY RUN MODE</code>' if self.engine.dry_run else '<code>LIVE TRADING</code>'}

{self.EMOJI['warning']} <i>Admin access verified</i>
"""
        keyboard = self._get_main_menu_keyboard()
        await update.message.reply_text(
            welcome,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )

    async def _cmd_dashboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show live trading dashboard."""
        if not self.is_admin(update.effective_user.id):
            return

        dashboard = await self._build_dashboard()
        keyboard = self._get_dashboard_keyboard()

        msg = await update.message.reply_text(
            dashboard,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )

        # Store for live updates
        self._dashboard_messages[update.effective_user.id] = msg.message_id

    async def _cmd_portfolio(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show portfolio breakdown."""
        if not self.is_admin(update.effective_user.id):
            return

        portfolio = await self._build_portfolio_view()
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{self.EMOJI['refresh']} Refresh", callback_data="refresh_portfolio")],
            [InlineKeyboardButton(f"{self.EMOJI['back']} Back", callback_data="main_menu")]
        ])

        await update.message.reply_text(
            portfolio,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )

    async def _cmd_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show open positions."""
        if not self.is_admin(update.effective_user.id):
            return

        positions = await self._build_positions_view()
        keyboard = self._get_positions_keyboard()

        await update.message.reply_text(
            positions,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )

    async def _cmd_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show trade history."""
        if not self.is_admin(update.effective_user.id):
            return

        history = self._build_history_view()

        await update.message.reply_text(
            history,
            parse_mode=ParseMode.HTML
        )

    async def _cmd_trade(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show trade interface."""
        if not self.is_admin(update.effective_user.id):
            return

        # Check for arguments: /trade <token_mint> [amount_usd]
        args = context.args

        if not args:
            await update.message.reply_text(
                f"{self.EMOJI['trade']} <b>QUICK TRADE</b>\n\n"
                "Usage: <code>/trade &lt;token_mint&gt; [amount_usd]</code>\n\n"
                "Example:\n"
                "<code>/trade So11111111111111111111111111111111111111112 50</code>\n\n"
                "Or use the dashboard to trade from sentiment signals.",
                parse_mode=ParseMode.HTML
            )
            return

        token_mint = args[0]
        amount_usd = float(args[1]) if len(args) > 1 else None

        # Get token info
        token_info = await self.engine.jupiter.get_token_info(token_mint)
        if not token_info:
            await update.message.reply_text(
                f"{self.EMOJI['cross']} Token not found: <code>{token_mint[:8]}...</code>",
                parse_mode=ParseMode.HTML
            )
            return

        current_price = await self.engine.jupiter.get_token_price(token_mint)

        # Build trade confirmation
        trade_view = f"""
{self.EMOJI['trade']} <b>TRADE CONFIRMATION</b>

<b>Token:</b> {token_info.symbol}
<b>Address:</b> <code>{token_mint[:12]}...{token_mint[-4:]}</code>
<b>Current Price:</b> <code>${current_price:.6f}</code>
<b>Amount:</b> <code>${amount_usd or 'Default sizing'}</code>

<b>Risk Level:</b> {self.engine.risk_level.value}
<b>Mode:</b> {'DRY RUN' if self.engine.dry_run else 'LIVE'}

{self.EMOJI['warning']} Confirm to execute trade
"""

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    f"{self.EMOJI['bull']} BUY",
                    callback_data=f"exec_buy:{token_mint}:{amount_usd or 0}"
                ),
                InlineKeyboardButton(
                    f"{self.EMOJI['bear']} SKIP",
                    callback_data="cancel_trade"
                )
            ],
            [InlineKeyboardButton(f"{self.EMOJI['back']} Cancel", callback_data="main_menu")]
        ])

        await update.message.reply_text(
            trade_view,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )

    async def _cmd_close(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Close a position."""
        if not self.is_admin(update.effective_user.id):
            return

        args = context.args

        if not args:
            # Show list of positions to close
            positions = self.engine.get_open_positions()
            if not positions:
                await update.message.reply_text(
                    f"{self.EMOJI['neutral']} No open positions to close.",
                    parse_mode=ParseMode.HTML
                )
                return

            buttons = []
            for pos in positions:
                pnl = pos.unrealized_pnl_pct
                emoji = self.EMOJI['profit'] if pnl >= 0 else self.EMOJI['loss']
                buttons.append([
                    InlineKeyboardButton(
                        f"{emoji} {pos.token_symbol} ({pnl:+.1f}%)",
                        callback_data=f"close_pos:{pos.id}"
                    )
                ])

            buttons.append([InlineKeyboardButton(f"{self.EMOJI['back']} Cancel", callback_data="main_menu")])

            await update.message.reply_text(
                f"{self.EMOJI['close']} <b>SELECT POSITION TO CLOSE</b>",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            return

        # Close specific position
        position_id = args[0]
        success, message = await self.engine.close_position(
            position_id,
            user_id=update.effective_user.id
        )

        emoji = self.EMOJI['check'] if success else self.EMOJI['cross']
        await update.message.reply_text(
            f"{emoji} {message}",
            parse_mode=ParseMode.HTML
        )

    async def _cmd_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show performance report."""
        if not self.is_admin(update.effective_user.id):
            return

        report = self.engine.generate_report()

        await update.message.reply_text(
            report.to_telegram_message(),
            parse_mode=ParseMode.HTML
        )

    async def _cmd_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show settings menu."""
        if not self.is_admin(update.effective_user.id):
            return

        settings = f"""
{self.EMOJI['settings']} <b>TRADING SETTINGS</b>

<b>Mode:</b> {'DRY RUN (Paper Trading)' if self.engine.dry_run else 'LIVE TRADING'}
<b>Risk Level:</b> {self.engine.risk_level.value}
<b>Max Positions:</b> {self.engine.max_positions}

<b>Position Sizing:</b>
- Conservative: 1% of portfolio
- Moderate: 2% of portfolio
- Aggressive: 5% of portfolio
- Degen: 10% of portfolio
"""

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    " Enable Live" if self.engine.dry_run else " Enable Dry Run",
                    callback_data="toggle_mode"
                )
            ],
            [
                InlineKeyboardButton("Conservative", callback_data="risk_conservative"),
                InlineKeyboardButton("Moderate", callback_data="risk_moderate"),
            ],
            [
                InlineKeyboardButton("Aggressive", callback_data="risk_aggressive"),
                InlineKeyboardButton("Degen", callback_data="risk_degen"),
            ],
            [InlineKeyboardButton(f"{self.EMOJI['back']} Back", callback_data="main_menu")]
        ])

        await update.message.reply_text(
            settings,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help message."""
        help_text = f"""
{self.EMOJI['crown']} <b>JARVIS TREASURY COMMANDS</b>

<b>Dashboard & Monitoring:</b>
/dashboard - Live trading dashboard
/portfolio - Portfolio breakdown
/positions - View open positions
/history - Trade history

<b>Trading:</b>
/trade &lt;mint&gt; [amount] - Execute trade
/close [position_id] - Close position

<b>Reports:</b>
/report - Performance summary

<b>Settings:</b>
/settings - Configure trading params

<b>Mode:</b> {'DRY RUN' if self.engine.dry_run else 'LIVE'}
"""

        await update.message.reply_text(
            help_text,
            parse_mode=ParseMode.HTML
        )

    # ============ Callback Handlers ============

    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks."""
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id
        if not self.is_admin(user_id):
            return

        data = query.data

        if data == "main_menu":
            keyboard = self._get_main_menu_keyboard()
            await query.edit_message_text(
                f"{self.EMOJI['crown']} <b>JARVIS TREASURY</b>\n\nSelect an option:",
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )

        elif data == "show_dashboard":
            dashboard = await self._build_dashboard()
            keyboard = self._get_dashboard_keyboard()
            await query.edit_message_text(
                dashboard,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )

        elif data == "refresh_dashboard":
            await self.engine.update_positions()
            dashboard = await self._build_dashboard()
            keyboard = self._get_dashboard_keyboard()
            await query.edit_message_text(
                dashboard,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )

        elif data == "refresh_portfolio":
            await self.engine.update_positions()  # Refresh prices before display
            portfolio = await self._build_portfolio_view()
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{self.EMOJI['refresh']} Refresh", callback_data="refresh_portfolio")],
                [InlineKeyboardButton(f"{self.EMOJI['back']} Back", callback_data="main_menu")]
            ])
            await query.edit_message_text(
                portfolio,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )

        elif data == "show_positions":
            await self.engine.update_positions()  # Refresh prices before display
            positions = await self._build_positions_view()
            keyboard = self._get_positions_keyboard()
            await query.edit_message_text(
                positions,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )

        elif data == "show_report":
            report = self.engine.generate_report()
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{self.EMOJI['back']} Back", callback_data="main_menu")]
            ])
            await query.edit_message_text(
                report.to_telegram_message(),
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )

        elif data.startswith("exec_buy:"):
            parts = data.split(":")
            token_mint = parts[1]
            amount = float(parts[2]) if parts[2] != "0" else None

            success, msg, position = await self.engine.open_position(
                token_mint=token_mint,
                token_symbol="TOKEN",  # Will be updated
                direction=TradeDirection.LONG,
                amount_usd=amount,
                user_id=user_id
            )

            emoji = self.EMOJI['check'] if success else self.EMOJI['cross']
            await query.edit_message_text(
                f"{emoji} {msg}",
                parse_mode=ParseMode.HTML
            )

        elif data.startswith("close_pos:"):
            position_id = data.split(":")[1]
            success, msg = await self.engine.close_position(position_id, user_id)

            emoji = self.EMOJI['check'] if success else self.EMOJI['cross']
            await query.edit_message_text(
                f"{emoji} {msg}",
                parse_mode=ParseMode.HTML
            )

        elif data == "toggle_mode":
            self.engine.dry_run = not self.engine.dry_run
            mode = "DRY RUN" if self.engine.dry_run else "LIVE"
            await query.edit_message_text(
                f"{self.EMOJI['check']} Mode changed to: <b>{mode}</b>",
                parse_mode=ParseMode.HTML
            )

        elif data.startswith("risk_"):
            risk_map = {
                "risk_conservative": RiskLevel.CONSERVATIVE,
                "risk_moderate": RiskLevel.MODERATE,
                "risk_aggressive": RiskLevel.AGGRESSIVE,
                "risk_degen": RiskLevel.DEGEN
            }
            if data in risk_map:
                self.engine.risk_level = risk_map[data]
                await query.edit_message_text(
                    f"{self.EMOJI['check']} Risk level: <b>{self.engine.risk_level.value}</b>",
                    parse_mode=ParseMode.HTML
                )

        elif data == "cancel_trade":
            await query.edit_message_text(
                f"{self.EMOJI['cross']} Trade cancelled",
                parse_mode=ParseMode.HTML
            )

    # ============ View Builders ============

    async def _build_dashboard(self) -> str:
        """Build the main trading dashboard."""
        # Get portfolio value
        sol_balance, usd_value = await self.engine.get_portfolio_value()

        # Get open positions
        positions = self.engine.get_open_positions()
        await self.engine.update_positions()

        # Calculate totals
        unrealized_pnl = sum(p.unrealized_pnl for p in positions)
        report = self.engine.generate_report()

        # Check position health and build alerts
        alerts = []
        pos_lines = []
        for pos in positions[:5]:  # Top 5
            pnl = pos.unrealized_pnl_pct

            # Determine position health status
            status = ""
            if pos.current_price <= pos.stop_loss_price:
                status = " [SL BREACHED]"
                alerts.append(f"{self.EMOJI['warning']} {pos.token_symbol} breached SL ({pnl:+.1f}%)")
            elif pnl <= -50:
                status = " [CRITICAL]"
                alerts.append(f"{self.EMOJI['warning']} {pos.token_symbol} down {pnl:.1f}%")
            elif pnl <= -20:
                status = " [WARNING]"
            elif pos.current_price >= pos.take_profit_price:
                status = " [TP HIT]"
                alerts.append(f"{self.EMOJI['target']} {pos.token_symbol} hit TP!")

            emoji = self.EMOJI['profit'] if pnl >= 0 else self.EMOJI['loss']

            # Calculate TP/SL percentages from entry
            tp_pct = ((pos.take_profit_price - pos.entry_price) / pos.entry_price * 100) if pos.entry_price > 0 else 0
            sl_pct = ((pos.stop_loss_price - pos.entry_price) / pos.entry_price * 100) if pos.entry_price > 0 else 0

            # Smart price formatting - use scientific notation for very small prices
            def fmt_price(p: float) -> str:
                if p >= 1:
                    return f"${p:.4f}"
                elif p >= 0.0001:
                    return f"${p:.6f}"
                else:
                    return f"${p:.2e}"

            pos_lines.append(
                f"  {emoji} <b>{pos.token_symbol}</b>{status}\n"
                f"      Entry: <code>{fmt_price(pos.entry_price)}</code> → Now: <code>{fmt_price(pos.current_price)}</code>\n"
                f"      P&L: <code>{pnl:+.1f}%</code> (${pos.unrealized_pnl:+.2f})\n"
                f"      TP: <code>{tp_pct:+.0f}%</code> | SL: <code>{sl_pct:.0f}%</code>"
            )

        positions_text = "\n".join(pos_lines) if pos_lines else "  No open positions"

        # Build alerts section
        alerts_text = ""
        if alerts:
            alerts_text = f"""
<b>{self.EMOJI['warning']} ALERTS</b>
{chr(10).join(alerts)}
"""

        now = datetime.utcnow().strftime("%H:%M:%S UTC")

        # Calculate wins/losses
        wins = report.winning_trades
        losses = report.losing_trades

        return f"""
{self.EMOJI['chart']} <b>JARVIS TREASURY DASHBOARD</b>
{alerts_text}
<b>Portfolio Value</b>
{self.EMOJI['wallet']} SOL: <code>{sol_balance:.4f}</code>
{self.EMOJI['money']} USD: <code>${usd_value:,.2f}</code>

<b>Performance (Win/Loss)</b>
{self.EMOJI['chart']} Record: <code>{wins}W/{losses}L</code> ({report.win_rate:.1f}%)
{self.EMOJI['profit' if report.total_pnl_usd >= 0 else 'loss']} Realized P&L: <code>${report.total_pnl_usd:+,.2f}</code>
{self.EMOJI['trade']} Total Trades: <code>{report.total_trades}</code>
{self.EMOJI['diamond']} Avg Win: <code>${report.average_win_usd:+.2f}</code> | Avg Loss: <code>${report.average_loss_usd:.2f}</code>

<b>Open Positions ({len(positions)}/{self.engine.max_positions})</b>
{positions_text}
{self.EMOJI['profit' if unrealized_pnl >= 0 else 'loss']} Unrealized: <code>${unrealized_pnl:+.2f}</code>

<b>Mode:</b> {'<code>DRY RUN</code>' if self.engine.dry_run else '<code>LIVE</code>'}
{self.EMOJI['clock']} Updated: {now}
"""

    async def _build_portfolio_view(self) -> str:
        """Build portfolio breakdown view."""
        treasury = self.engine.wallet.get_treasury()
        if not treasury:
            return f"{self.EMOJI['cross']} No treasury wallet configured"

        sol_balance, sol_usd = await self.engine.wallet.get_balance(treasury.address)
        token_balances = await self.engine.wallet.get_token_balances(treasury.address)

        # Build token list
        tokens = []
        total_token_usd = 0

        for mint, info in token_balances.items():
            price = await self.engine.jupiter.get_token_price(mint)
            usd_value = info['balance'] * price
            total_token_usd += usd_value

            token_info = await self.engine.jupiter.get_token_info(mint)
            symbol = token_info.symbol if token_info else mint[:6]

            if usd_value >= 1:  # Only show tokens worth $1+
                tokens.append({
                    'symbol': symbol,
                    'balance': info['balance'],
                    'usd': usd_value
                })

        tokens.sort(key=lambda x: x['usd'], reverse=True)
        total_usd = sol_usd + total_token_usd

        token_lines = []
        for t in tokens[:10]:  # Top 10 tokens
            pct = (t['usd'] / total_usd * 100) if total_usd > 0 else 0
            token_lines.append(
                f"  <b>{t['symbol']}</b>: {t['balance']:.4f} (${t['usd']:.2f} - {pct:.1f}%)"
            )

        token_text = "\n".join(token_lines) if token_lines else "  No tokens"

        return f"""
{self.EMOJI['wallet']} <b>PORTFOLIO BREAKDOWN</b>

<b>Treasury Address:</b>
<code>{treasury.address[:12]}...{treasury.address[-4:]}</code>

<b>SOL Balance:</b>
  <code>{sol_balance:.4f}</code> SOL (<code>${sol_usd:.2f}</code>)

<b>Token Holdings:</b>
{token_text}

<b>Total Value:</b> <code>${total_usd:,.2f}</code>
"""

    async def _build_positions_view(self) -> str:
        """Build positions view."""
        # Refresh prices before displaying
        await self.engine.update_positions()
        positions = self.engine.get_open_positions()

        if not positions:
            return f"""
{self.EMOJI['trade']} <b>OPEN POSITIONS</b>

No open positions.

Use /trade to open a new position.
"""

        pos_details = []
        for pos in positions:
            pnl_emoji = self.EMOJI['profit'] if pos.unrealized_pnl >= 0 else self.EMOJI['loss']

            detail = f"""
{pnl_emoji} <b>{pos.token_symbol}</b> ({pos.direction.value})
   Entry: <code>${pos.entry_price:.6f}</code>
   Current: <code>${pos.current_price:.6f}</code>
   P&L: <code>{pos.unrealized_pnl_pct:+.1f}%</code> (${pos.unrealized_pnl:+.2f})
   {self.EMOJI['target']} TP: <code>${pos.take_profit_price:.6f}</code>
   {self.EMOJI['stop']} SL: <code>${pos.stop_loss_price:.6f}</code>
   ID: <code>{pos.id}</code>
"""
            pos_details.append(detail)

        return f"""
{self.EMOJI['trade']} <b>OPEN POSITIONS</b> ({len(positions)})
{''.join(pos_details)}
Total Unrealized: <code>${sum(p.unrealized_pnl for p in positions):+.2f}</code>
"""

    def _build_history_view(self) -> str:
        """Build trade history view."""
        all_history = self.engine.trade_history
        history = all_history[-15:]  # Last 15

        if not all_history:
            return f"{self.EMOJI['chart']} <b>TRADE HISTORY</b>\n\nNo completed trades yet."

        # Calculate stats
        wins = [t for t in all_history if t.pnl_usd > 0]
        losses = [t for t in all_history if t.pnl_usd < 0]
        total_pnl = sum(t.pnl_usd for t in all_history)
        win_rate = (len(wins) / len(all_history) * 100) if all_history else 0

        trades = []
        for pos in reversed(history):
            emoji = self.EMOJI['profit'] if pos.pnl_usd >= 0 else self.EMOJI['loss']
            close_type = ""
            if hasattr(pos, 'exit_price') and hasattr(pos, 'take_profit_price'):
                if pos.exit_price and pos.take_profit_price:
                    if pos.exit_price >= pos.take_profit_price:
                        close_type = " [TP]"
                    elif hasattr(pos, 'stop_loss_price') and pos.exit_price <= pos.stop_loss_price:
                        close_type = " [SL]"
            trades.append(
                f"{emoji} <b>{pos.token_symbol}</b>{close_type}: "
                f"<code>{pos.pnl_pct:+.1f}%</code> (${pos.pnl_usd:+.2f})"
            )

        return f"""
{self.EMOJI['chart']} <b>TRADE HISTORY</b>

<b>Stats:</b> {len(wins)}W / {len(losses)}L ({win_rate:.1f}% win rate)
<b>Total P&L:</b> ${total_pnl:+.2f}

<b>Recent Trades ({len(history)}/{len(all_history)}):</b>
{chr(10).join(trades)}

Use /report for full performance summary.
"""

    # ============ Keyboards ============

    def _get_main_menu_keyboard(self) -> InlineKeyboardMarkup:
        """Get main menu keyboard."""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"{self.EMOJI['chart']} Dashboard", callback_data="show_dashboard"),
                InlineKeyboardButton(f"{self.EMOJI['wallet']} Portfolio", callback_data="refresh_portfolio"),
            ],
            [
                InlineKeyboardButton(f"{self.EMOJI['trade']} Positions", callback_data="show_positions"),
                InlineKeyboardButton(f"{self.EMOJI['chart']} Report", callback_data="show_report"),
            ],
            [
                InlineKeyboardButton(f"{self.EMOJI['settings']} Settings", callback_data="show_settings"),
            ]
        ])

    def _get_dashboard_keyboard(self) -> InlineKeyboardMarkup:
        """Get dashboard keyboard."""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"{self.EMOJI['refresh']} Refresh", callback_data="refresh_dashboard"),
                InlineKeyboardButton(f"{self.EMOJI['trade']} Positions", callback_data="show_positions"),
            ],
            [InlineKeyboardButton(f"{self.EMOJI['back']} Menu", callback_data="main_menu")]
        ])

    def _get_positions_keyboard(self) -> InlineKeyboardMarkup:
        """Get positions keyboard."""
        positions = self.engine.get_open_positions()

        buttons = []
        for pos in positions[:4]:  # Max 4 close buttons
            buttons.append(
                InlineKeyboardButton(
                    f"{self.EMOJI['close']} Close {pos.token_symbol}",
                    callback_data=f"close_pos:{pos.id}"
                )
            )

        rows = []
        for i in range(0, len(buttons), 2):
            rows.append(buttons[i:i+2])

        rows.append([
            InlineKeyboardButton(f"{self.EMOJI['refresh']} Refresh", callback_data="show_positions"),
            InlineKeyboardButton(f"{self.EMOJI['back']} Back", callback_data="main_menu")
        ])

        return InlineKeyboardMarkup(rows)

    # ============ Sentiment Integration ============

    async def send_trade_signal(
        self,
        chat_id: int,
        token_mint: str,
        token_symbol: str,
        sentiment_grade: str,
        sentiment_score: float,
        current_price: float,
        change_24h: float,
        mcap: float
    ):
        """
        Send a trade signal to the trading channel with action buttons.

        This is called from the sentiment report generator.
        """
        if not self.app:
            return

        # Calculate TP/SL levels
        tp_price, sl_price = self.engine.get_tp_sl_levels(current_price, sentiment_grade)

        # Determine signal strength
        if sentiment_score > 0.45:
            signal = f"{self.EMOJI['rocket']} STRONG BUY"
            color = ""
        elif sentiment_score > 0.25:
            signal = f"{self.EMOJI['bull']} BUY"
            color = ""
        elif sentiment_score < -0.35:
            signal = f"{self.EMOJI['bear']} AVOID"
            color = ""
        else:
            signal = f"{self.EMOJI['neutral']} NEUTRAL"
            color = ""

        # Format market cap
        if mcap >= 1_000_000:
            mcap_str = f"${mcap/1_000_000:.2f}M"
        else:
            mcap_str = f"${mcap/1_000:.1f}K"

        message = f"""
{color} <b>TRADING SIGNAL</b>

<b>{token_symbol}</b> | Grade: <b>{sentiment_grade}</b>
{signal}

<b>Price:</b> <code>${current_price:.6f}</code>
<b>24h:</b> <code>{change_24h:+.1f}%</code>
<b>MCap:</b> <code>{mcap_str}</code>

<b>Trade Levels:</b>
{self.EMOJI['target']} Take Profit: <code>${tp_price:.6f}</code> (+{((tp_price/current_price)-1)*100:.0f}%)
{self.EMOJI['stop']} Stop Loss: <code>${sl_price:.6f}</code> (-{(1-(sl_price/current_price))*100:.0f}%)

<code>{token_mint}</code>
"""

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    f"{self.EMOJI['money']} Trade $25",
                    callback_data=f"exec_buy:{token_mint}:25"
                ),
                InlineKeyboardButton(
                    f"{self.EMOJI['money']} Trade $50",
                    callback_data=f"exec_buy:{token_mint}:50"
                ),
            ],
            [
                InlineKeyboardButton(
                    f"{self.EMOJI['money']} Trade $100",
                    callback_data=f"exec_buy:{token_mint}:100"
                ),
                InlineKeyboardButton(
                    f"{self.EMOJI['cross']} Skip",
                    callback_data="cancel_trade"
                ),
            ]
        ])

        try:
            await self.app.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
        except Exception as e:
            logger.error(f"Failed to send trade signal: {e}")
