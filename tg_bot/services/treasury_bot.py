"""
Jarvis Treasury Bot - Premium Telegram Trading Interface

Professional features:
- Live portfolio dashboard with real-time updates
- One-click trading controls
- Advanced position management
- Comprehensive performance analytics
- Beautiful formatted reports
- Admin-only access
- Automatic position monitoring
- Integration with Grok sentiment
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from enum import Enum

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    InputMediaPhoto, ChatAction
)
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from bots.treasury.trading import TradingEngine, Position
from .treasury_dashboard import TreasuryDashboard

# Import emergency stop manager
try:
    from core.trading.emergency_stop import get_emergency_stop_manager, StopLevel, UnwindStrategy
    EMERGENCY_STOP_AVAILABLE = True
except ImportError:
    EMERGENCY_STOP_AVAILABLE = False
    get_emergency_stop_manager = None
    StopLevel = None
    UnwindStrategy = None

logger = logging.getLogger(__name__)


class TreasuryBotCommand(Enum):
    """Treasury bot commands."""
    DASHBOARD = "dashboard"
    PORTFOLIO = "portfolio"
    POSITIONS = "positions"
    TRADES = "trades"
    REPORT = "report"
    SETTINGS = "settings"
    HELP = "help"


class TreasuryBot:
    """
    Premium Telegram interface for Jarvis Treasury trading.

    Commands:
    /treasury_dashboard - Live portfolio view with metrics
    /treasury_positions - Detailed position breakdown
    /treasury_trades - Recent trade history
    /treasury_report - Performance analytics
    /treasury_settings - Configuration menu
    /treasury_help - Command reference
    """

    REFRESH_INTERVAL = 30  # seconds
    AUTO_UPDATE_ENABLED = True

    def __init__(
        self,
        trading_engine: TradingEngine,
        admin_ids: List[int],
        bot_token: str,
    ):
        """Initialize Treasury Bot."""
        self.engine = trading_engine
        self.admin_ids = admin_ids
        self.bot_token = bot_token
        self.dashboard = TreasuryDashboard(trading_engine)

        # Track active dashboard sessions for live updates
        self._dashboard_sessions: Dict[int, Dict[str, Any]] = {}

    def is_admin(self, user_id: int) -> bool:
        """Check if user is authorized."""
        return user_id in self.admin_ids

    def _check_admin(self, update: Update) -> bool:
        """Verify admin access."""
        if not self.is_admin(update.effective_user.id):
            return False
        return True

    # ==================== COMMAND HANDLERS ====================

    async def cmd_dashboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /treasury_dashboard command."""
        if not self._check_admin(update):
            await update.message.reply_text(
                "❌ <b>Access Denied</b>\n\nThis command requires admin privileges.",
                parse_mode=ParseMode.HTML
            )
            return

        # Show loading indicator
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action=ChatAction.TYPING
        )

        # Build dashboard
        dashboard_msg = self.dashboard.build_portfolio_dashboard(include_positions=True)
        keyboard = self._get_dashboard_keyboard(update.effective_user.id)

        msg = await update.message.reply_text(
            dashboard_msg,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )

        # Store session for live updates
        self._dashboard_sessions[update.effective_user.id] = {
            'message_id': msg.message_id,
            'chat_id': update.effective_chat.id,
            'last_update': datetime.utcnow(),
            'context': context,
        }

    async def cmd_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /treasury_positions command."""
        if not self._check_admin(update):
            return

        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action=ChatAction.TYPING
        )

        positions_msg = self.dashboard.build_detailed_positions()
        keyboard = self._get_positions_keyboard()

        await update.message.reply_text(
            positions_msg,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )

    async def cmd_trades(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /treasury_trades command."""
        if not self._check_admin(update):
            return

        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action=ChatAction.TYPING
        )

        trades_msg = self.dashboard.build_recent_trades(limit=15)
        keyboard = self._get_trades_keyboard()

        await update.message.reply_text(
            trades_msg,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )

    async def cmd_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /treasury_report command."""
        if not self._check_admin(update):
            return

        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action=ChatAction.TYPING
        )

        # Multi-period reports
        report_msg = f"""📋 <b>PERFORMANCE ANALYTICS</b>

Choose a reporting period:"""

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("7 Days", callback_data="report_7d"),
                InlineKeyboardButton("30 Days", callback_data="report_30d"),
            ],
            [
                InlineKeyboardButton("90 Days", callback_data="report_90d"),
                InlineKeyboardButton("1 Year", callback_data="report_365d"),
            ],
            [InlineKeyboardButton("← Back", callback_data="main_menu")]
        ])

        await update.message.reply_text(
            report_msg,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )

    async def cmd_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /treasury_settings command."""
        if not self._check_admin(update):
            return

        is_live = not self.engine.dry_run
        mode = "🟢 LIVE TRADING" if is_live else "🟡 DRY RUN (Paper)"
        risk = self.engine.risk_level.value

        settings_msg = f"""⚙️ <b>TREASURY SETTINGS</b>

<b>Current Configuration:</b>
  • Mode: {mode}
  • Risk Level: {risk}
  • Max Positions: {self.engine.max_positions}
  • Position Size: See risk level

<b>Risk Levels:</b>
  • Conservative: 1% per position
  • Moderate: 2% per position
  • Aggressive: 5% per position
  • Degen: 10% per position

<i>⚠️ Changes require admin confirmation</i>
"""

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🔴 Enable Live" if not is_live else "🟡 Enable Dry Run",
                    callback_data="toggle_live_mode"
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
            [InlineKeyboardButton("← Back", callback_data="main_menu")]
        ])

        await update.message.reply_text(
            settings_msg,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )

    async def cmd_emergency_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stop command - activate emergency trading halt."""
        if not self._check_admin(update):
            await update.message.reply_text(
                "❌ <b>Access Denied</b>\n\nEmergency controls require admin privileges.",
                parse_mode=ParseMode.HTML
            )
            return

        if not EMERGENCY_STOP_AVAILABLE:
            await update.message.reply_text(
                "❌ Emergency stop system not available",
                parse_mode=ParseMode.HTML
            )
            return

        # Parse command arguments
        args = context.args or []
        level = args[0].upper() if args else "SOFT"
        reason = " ".join(args[1:]) if len(args) > 1 else "Manual stop via Telegram"

        emergency_manager = get_emergency_stop_manager()
        user_id = update.effective_user.id

        # Activate appropriate stop level
        if level == "KILL":
            success, msg = emergency_manager.activate_kill_switch(
                reason=reason,
                activated_by=f"telegram_user_{user_id}",
                unwind_strategy=UnwindStrategy.IMMEDIATE
            )
            icon = "🚨"
        elif level == "HARD":
            success, msg = emergency_manager.activate_hard_stop(
                reason=reason,
                activated_by=f"telegram_user_{user_id}",
                unwind_strategy=UnwindStrategy.GRACEFUL
            )
            icon = "🛑"
        else:  # SOFT
            success, msg = emergency_manager.activate_soft_stop(
                reason=reason,
                activated_by=f"telegram_user_{user_id}"
            )
            icon = "⚠️"

        if success:
            status = emergency_manager.get_status()
            response = f"""{icon} <b>EMERGENCY STOP ACTIVATED</b>

<b>Level:</b> {status['level']}
<b>Reason:</b> {reason}
<b>Trading:</b> {'❌ BLOCKED' if not status['trading_allowed'] else '✅ Allowed'}
<b>Should Unwind:</b> {'Yes' if status['should_unwind'] else 'No'}
<b>Strategy:</b> {status['unwind_strategy']}

Use /resume to restore normal trading.
Use /stop_status to check current state.
"""
        else:
            response = f"❌ <b>Failed to activate emergency stop</b>\n\n{msg}"

        await update.message.reply_text(response, parse_mode=ParseMode.HTML)

    async def cmd_resume_trading(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /resume command - resume normal trading."""
        if not self._check_admin(update):
            await update.message.reply_text(
                "❌ <b>Access Denied</b>\n\nEmergency controls require admin privileges.",
                parse_mode=ParseMode.HTML
            )
            return

        if not EMERGENCY_STOP_AVAILABLE:
            await update.message.reply_text(
                "❌ Emergency stop system not available",
                parse_mode=ParseMode.HTML
            )
            return

        emergency_manager = get_emergency_stop_manager()
        user_id = update.effective_user.id

        success, msg = emergency_manager.resume_trading(
            resumed_by=f"telegram_user_{user_id}"
        )

        if success:
            response = """✅ <b>TRADING RESUMED</b>

All emergency stops cleared.
Normal trading operations restored.

Use /stop to activate emergency stop again if needed.
"""
        else:
            response = f"❌ <b>Failed to resume trading</b>\n\n{msg}"

        await update.message.reply_text(response, parse_mode=ParseMode.HTML)

    async def cmd_stop_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stop_status command - show emergency stop status."""
        if not self._check_admin(update):
            return

        if not EMERGENCY_STOP_AVAILABLE:
            await update.message.reply_text(
                "❌ Emergency stop system not available",
                parse_mode=ParseMode.HTML
            )
            return

        emergency_manager = get_emergency_stop_manager()
        status = emergency_manager.get_status()

        # Determine icon
        if status['level'] == 'KILL_SWITCH':
            icon = "🚨"
        elif status['level'] == 'HARD_STOP':
            icon = "🛑"
        elif status['level'] == 'SOFT_STOP':
            icon = "⚠️"
        elif status['level'] == 'TOKEN_PAUSE':
            icon = "⏸️"
        else:
            icon = "✅"

        response = f"""{icon} <b>EMERGENCY STOP STATUS</b>

<b>Current Level:</b> {status['level']}
<b>Trading Allowed:</b> {'✅ Yes' if status['trading_allowed'] else '❌ No'}
"""

        if status['activated_at']:
            response += f"<b>Activated:</b> {status['activated_at']}\n"
            response += f"<b>By:</b> {status['activated_by']}\n"
            response += f"<b>Reason:</b> {status['reason']}\n"

        if status['paused_tokens']:
            response += f"\n<b>Paused Tokens:</b> {len(status['paused_tokens'])}\n"
            for token in list(status['paused_tokens'])[:5]:
                response += f"  • {token[:8]}...\n"

        if status['should_unwind']:
            response += f"\n<b>Unwind Strategy:</b> {status['unwind_strategy']}\n"

        if status['level'] == 'NONE':
            response += "\n<i>Normal trading operations</i>"

        await update.message.reply_text(response, parse_mode=ParseMode.HTML)

    async def cmd_pause_token(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /pause_token command - pause trading for specific token."""
        if not self._check_admin(update):
            return

        if not EMERGENCY_STOP_AVAILABLE:
            await update.message.reply_text(
                "❌ Emergency stop system not available",
                parse_mode=ParseMode.HTML
            )
            return

        # Parse arguments
        args = context.args or []
        if not args:
            await update.message.reply_text(
                "Usage: /pause_token <token_mint> [reason]",
                parse_mode=ParseMode.HTML
            )
            return

        token_mint = args[0]
        reason = " ".join(args[1:]) if len(args) > 1 else "Manual pause via Telegram"

        emergency_manager = get_emergency_stop_manager()
        user_id = update.effective_user.id

        success, msg = emergency_manager.pause_token(
            token_mint=token_mint,
            reason=reason,
            activated_by=f"telegram_user_{user_id}"
        )

        if success:
            response = f"""⏸️ <b>TOKEN PAUSED</b>

<b>Token:</b> {token_mint[:8]}...
<b>Reason:</b> {reason}

Trading for this token is now blocked.
Use /resume_token {token_mint} to resume.
"""
        else:
            response = f"❌ <b>Failed to pause token</b>\n\n{msg}"

        await update.message.reply_text(response, parse_mode=ParseMode.HTML)

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /treasury_help command."""
        help_msg = """👑 <b>JARVIS TREASURY BOT</b> - Command Reference

<b>Main Commands:</b>
  /treasury_dashboard - Live portfolio view with real-time metrics
  /treasury_positions - Detailed breakdown of all open positions
  /treasury_trades - Recent trade history with P&L
  /treasury_report - Performance analytics by period
  /treasury_settings - Configuration and risk management
  /treasury_help - This help message

<b>Emergency Controls:</b>
  /stop [SOFT|HARD|KILL] [reason] - Emergency trading halt
  /resume - Resume normal trading
  /stop_status - Check emergency stop state
  /pause_token <mint> [reason] - Pause specific token
  /resume_token <mint> - Resume specific token

<b>Dashboard Features:</b>
  ✅ Real-time P&L tracking
  ✅ Position exposure analysis
  ✅ Win rate and performance metrics
  ✅ Auto-refresh with live updates
  ✅ Quick access to all controls

<b>Position Management:</b>
  ✅ View all open trades
  ✅ Monitor entry/exit prices
  ✅ Track profit targets and stops
  ✅ Duration and holding time metrics

<b>Performance Reports:</b>
  ✅ Period returns (7d, 30d, 90d, 1y)
  ✅ Risk metrics (Sharpe, Sortino, max drawdown)
  ✅ Trade statistics (win rate, profit factor)
  ✅ Trend analysis with visual indicators

<b>Safety Features:</b>
  🔒 Admin-only access
  🔒 Emergency stop controls
  🔒 Real-time position monitoring
  🔒 Automatic stop loss enforcement

<b>Emergency Stop Levels:</b>
  • SOFT - Block new positions only
  • HARD - Block new + close existing (graceful)
  • KILL - Immediate halt + unwind all positions

<b>Keyboard Shortcuts:</b>
  • Use inline buttons for quick navigation
  • Refresh buttons for live updates
  • Back buttons to return to menus

<i>For more info: /help</i>
"""

        await update.message.reply_text(
            help_msg,
            parse_mode=ParseMode.HTML
        )

    # ==================== CALLBACK HANDLERS ====================

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline button callbacks."""
        query = update.callback_query
        user_id = query.from_user.id

        if not self.is_admin(user_id):
            await query.answer("❌ Access denied", show_alert=True)
            return

        await query.answer()  # Remove loading indicator

        # Route to handler
        data = query.data

        if data == "main_menu":
            await self._show_main_menu(query, context)
        elif data.startswith("report_"):
            period = int(data.split("_")[1].rstrip("d"))
            await self._show_report(query, context, period)
        elif data == "refresh_dashboard":
            await self._refresh_dashboard(query, context)
        elif data == "toggle_live_mode":
            await self._toggle_mode(query, context)
        elif data.startswith("risk_"):
            risk_level = data.split("_")[1]
            await self._set_risk_level(query, context, risk_level)
        else:
            await query.edit_message_text("Unknown action")

    async def _show_main_menu(self, query, context):
        """Show main menu."""
        menu_msg = """👑 <b>JARVIS TREASURY</b>

Select an action:"""

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"{self.dashboard.EMOJI['portfolio']} Dashboard", callback_data="refresh_dashboard"),
                InlineKeyboardButton(f"{self.dashboard.EMOJI['positions']} Positions", callback_data="cmd_positions"),
            ],
            [
                InlineKeyboardButton(f"{self.dashboard.EMOJI['trades']} Trades", callback_data="cmd_trades"),
                InlineKeyboardButton(f"{self.dashboard.EMOJI['report']} Reports", callback_data="cmd_report"),
            ],
            [
                InlineKeyboardButton(f"{self.dashboard.EMOJI['settings']} Settings", callback_data="cmd_settings"),
            ]
        ])

        await query.edit_message_text(
            menu_msg,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )

    async def _show_report(self, query, context, period_days: int):
        """Show period report."""
        report_msg = self.dashboard.build_performance_report(period_days)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("← Back", callback_data="main_menu")]
        ])

        await query.edit_message_text(
            report_msg,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )

    async def _refresh_dashboard(self, query, context):
        """Refresh dashboard."""
        dashboard_msg = self.dashboard.build_portfolio_dashboard(include_positions=True)
        keyboard = self._get_dashboard_keyboard(query.from_user.id)

        await query.edit_message_text(
            dashboard_msg,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )

    async def _toggle_mode(self, query, context):
        """Toggle between live and dry run."""
        old_mode = self.engine.dry_run
        self.engine.dry_run = not old_mode
        mode_name = "Dry Run" if self.engine.dry_run else "Live Trading"

        await query.answer(f"Mode changed to {mode_name}", show_alert=True)
        await self._refresh_settings(query, context)

    async def _set_risk_level(self, query, context, risk_level: str):
        """Set risk level."""
        from bots.treasury.trading import RiskLevel
        try:
            self.engine.risk_level = RiskLevel[risk_level.upper()]
            await query.answer(f"Risk level set to {risk_level}", show_alert=True)
            await self._refresh_settings(query, context)
        except Exception as e:
            await query.answer(f"Error: {str(e)}", show_alert=True)

    async def _refresh_settings(self, query, context):
        """Refresh settings display."""
        # Re-run settings command
        await self.cmd_settings(query.message, context)

    # ==================== KEYBOARD BUILDERS ====================

    def _get_dashboard_keyboard(self, user_id: int) -> InlineKeyboardMarkup:
        """Build dashboard control keyboard."""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"{self.dashboard.EMOJI['refresh']} Refresh", callback_data="refresh_dashboard"),
                InlineKeyboardButton(f"{self.dashboard.EMOJI['positions']} Details", callback_data="cmd_positions"),
            ],
            [
                InlineKeyboardButton(f"{self.dashboard.EMOJI['report']} Report", callback_data="cmd_report"),
                InlineKeyboardButton(f"{self.dashboard.EMOJI['settings']} Settings", callback_data="cmd_settings"),
            ]
        ])

    def _get_positions_keyboard(self) -> InlineKeyboardMarkup:
        """Build positions control keyboard."""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"{self.dashboard.EMOJI['refresh']} Refresh", callback_data="refresh_positions"),
            ],
            [InlineKeyboardButton("← Back", callback_data="main_menu")]
        ])

    def _get_trades_keyboard(self) -> InlineKeyboardMarkup:
        """Build trades control keyboard."""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"{self.dashboard.EMOJI['refresh']} Refresh", callback_data="refresh_trades"),
            ],
            [InlineKeyboardButton("← Back", callback_data="main_menu")]
        ])

    # ==================== MONITORING ====================

    async def start_monitoring(self):
        """Start background monitoring and auto-updates."""
        logger.info("Treasury Bot monitoring started")
        while True:
            try:
                # Update all active dashboards
                for user_id, session in list(self._dashboard_sessions.items()):
                    try:
                        await self._auto_update_dashboard(session)
                    except Exception as e:
                        logger.debug(f"Dashboard auto-update failed for user {user_id}: {e}")

                await asyncio.sleep(self.REFRESH_INTERVAL)

            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                await asyncio.sleep(self.REFRESH_INTERVAL)

    async def _auto_update_dashboard(self, session: Dict[str, Any]):
        """Auto-update dashboard if changes detected."""
        time_since_update = datetime.utcnow() - session['last_update']

        if time_since_update.total_seconds() < self.REFRESH_INTERVAL:
            return

        try:
            context = session.get('context')
            if context and context.bot:
                dashboard_msg = self.dashboard.build_portfolio_dashboard(include_positions=True)
                keyboard = self._get_dashboard_keyboard(session.get('user_id', 0))

                await context.bot.edit_message_text(
                    chat_id=session['chat_id'],
                    message_id=session['message_id'],
                    text=dashboard_msg,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard
                )

                session['last_update'] = datetime.utcnow()
        except Exception as e:
            logger.debug(f"Auto-update edit failed (expected): {e}")
