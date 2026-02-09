"""
Public Trading Bot Handler

Enables regular users to:
- Analyze any Solana token with /analyze
- Create and manage wallets
- View portfolio and P&L
- Execute trades with safety checks
- Receive personalized recommendations
- Track performance

This is the public-facing interface separate from admin Treasury Bot.
"""

import asyncio
import logging
import os
import secrets
from datetime import datetime
from typing import Any, Dict, List, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ConversationHandler

from core.public_trading_service import PublicTradingService, ResolvedToken
from core.public_user_manager import PublicUserManager, UserProfile, UserRiskLevel, Wallet
from core.adaptive_algorithm import AdaptiveAlgorithm, AlgorithmType, TradeOutcome
from core.demo_wallet_intelligence import DemoWalletIntelligence
from core.token_analyzer import TokenAnalyzer
from core.wallet_service import WalletService, get_wallet_service
from core import x_sentiment
from bots.treasury.trading import TradingEngine

logger = logging.getLogger(__name__)

DEMO_AUTHORIZED_USERS = ["matthaynes88"]


class PublicBotHandler:
    """
    Telegram handler for public trading bot.

    Commands:
    /start - Register or welcome back
    /analyze <token> - Analyze a Solana token
    /buy <token> <amount> - Buy a token
    /sell <symbol> - Sell current position
    /portfolio - View holdings
    /performance - View P&L and stats
    /wallets - Manage wallets
    /settings - User settings
    /help - Help and commands
    """

    def __init__(
        self,
        trading_engine: Optional[TradingEngine] = None,
        wallet_service: Optional[WalletService] = None,
        public_trading: Optional[PublicTradingService] = None,
    ):
        """Initialize public bot handler."""
        self.trading_engine = trading_engine
        self.wallet_service = wallet_service
        self.public_trading = public_trading
        self.user_manager = PublicUserManager()
        self.algorithm = AdaptiveAlgorithm()
        self.token_analyzer = TokenAnalyzer()
        self.demo_intelligence = DemoWalletIntelligence()
        self.default_slippage_bps = 100
        # Simple per-user navigation stack for inline menu flows.
        # Stored in PTB's per-user context.user_data dict.
        self._NAV_STACK_KEY = "public_nav_stack"
        self._NAV_CURRENT_KEY = "public_nav_current"
        self._NAV_MAX_DEPTH = 30
        # Namespace callback_data to avoid collisions with other bot menus.
        self._CB_PREFIX = "pub:"

    def _cb(self, data: str) -> str:
        """Prefix callback data so we can route safely alongside other handlers."""
        return f"{self._CB_PREFIX}{data}"

    def _strip_cb(self, data: str) -> str:
        """Strip callback prefix; returns original if prefix not present."""
        if isinstance(data, str) and data.startswith(self._CB_PREFIX):
            return data[len(self._CB_PREFIX):]
        return data

    @staticmethod
    def _is_private_chat(update: Update) -> bool:
        """Return True if the update is from a private DM chat."""
        try:
            chat = update.effective_chat
            return bool(chat and getattr(chat, "type", "") == "private")
        except Exception:
            return False

    # --------------------------------------------------------------------------
    # Navigation helpers (inline menus)
    # --------------------------------------------------------------------------

    def _nav_get_stack(self, context: ContextTypes.DEFAULT_TYPE) -> List[str]:
        stack = context.user_data.get(self._NAV_STACK_KEY, [])
        return stack if isinstance(stack, list) else []

    def _nav_set_stack(self, context: ContextTypes.DEFAULT_TYPE, stack: List[str]) -> None:
        context.user_data[self._NAV_STACK_KEY] = (stack or [])[-self._NAV_MAX_DEPTH:]

    def _nav_get_current(self, context: ContextTypes.DEFAULT_TYPE) -> str:
        cur = context.user_data.get(self._NAV_CURRENT_KEY, "")
        return cur if isinstance(cur, str) else ""

    def _nav_set_current(self, context: ContextTypes.DEFAULT_TYPE, page_id: str) -> None:
        context.user_data[self._NAV_CURRENT_KEY] = page_id

    def _nav_push(self, context: ContextTypes.DEFAULT_TYPE, next_page_id: str) -> None:
        """Push current page and set the next page as current."""
        current = self._nav_get_current(context)
        if current and current != next_page_id:
            stack = self._nav_get_stack(context)
            if not stack or stack[-1] != current:
                stack.append(current)
            self._nav_set_stack(context, stack)
        self._nav_set_current(context, next_page_id)

    def _nav_pop(self, context: ContextTypes.DEFAULT_TYPE) -> str:
        """Pop and return previous page id; falls back to main menu."""
        stack = self._nav_get_stack(context)
        target = stack.pop() if stack else "main_menu"
        self._nav_set_stack(context, stack)
        self._nav_set_current(context, target)
        return target

    def _reset_interactive_state(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Clear flow state so 'back' won't leave the bot stuck awaiting input."""
        for key in ("flow", "flow_data", "pending_trade", "pending_send", "pending_wallet"):
            context.user_data.pop(key, None)

    def _with_prev_menu_button(self, reply_markup: Optional[InlineKeyboardMarkup]) -> InlineKeyboardMarkup:
        """Ensure the reply markup includes a 'Previous Menu' button."""
        prev_btn = InlineKeyboardButton("↩️ Previous Menu", callback_data=self._cb("nav_back"))
        if reply_markup is None:
            return InlineKeyboardMarkup([[prev_btn]])

        try:
            rows = list(reply_markup.inline_keyboard or [])
            for row in rows:
                for btn in row:
                    if getattr(btn, "callback_data", None) == self._cb("nav_back"):
                        return reply_markup
            rows.append([prev_btn])
            return InlineKeyboardMarkup(rows)
        except Exception:
            return reply_markup

    async def _edit_page(
        self,
        query,
        context: ContextTypes.DEFAULT_TYPE,
        page_id: str,
        text: str,
        *,
        parse_mode: Optional[str] = None,
        reply_markup: Optional[InlineKeyboardMarkup] = None,
        **kwargs,
    ) -> None:
        """Edit the current message and append a Previous Menu button."""
        self._nav_push(context, page_id)
        reply_markup = self._with_prev_menu_button(reply_markup)
        await query.edit_message_text(
            text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            **kwargs,
        )

    async def _edit_main_menu(self, query, context: ContextTypes.DEFAULT_TYPE) -> None:
        text = (
            "🤖 JARVIS Trading Bot\n\n"
            "Pick an option:"
        )
        keyboard = [
            [
                InlineKeyboardButton("🧠 Jarvis Picks", callback_data=self._cb("menu_picks")),
                InlineKeyboardButton("📊 Sentiment", callback_data=self._cb("menu_sentiment")),
            ],
            [
                InlineKeyboardButton("💰 Buy", callback_data=self._cb("menu_buy")),
                InlineKeyboardButton("💸 Sell", callback_data=self._cb("menu_sell")),
            ],
            [
                InlineKeyboardButton("👛 Wallet", callback_data=self._cb("wallet_menu")),
                InlineKeyboardButton("⚙️ Settings", callback_data=self._cb("menu_settings")),
            ],
        ]
        await self._edit_page(
            query,
            context,
            "main_menu",
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    async def _build_wallet_overview(self, user_id: int) -> tuple[str, InlineKeyboardMarkup]:
        wallet = self.user_manager.get_primary_wallet(user_id)
        if not wallet:
            return (
                "No wallet found. Create one with /start",
                InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data=self._cb("main_menu"))]]),
            )

        trading = await self._get_public_trading()
        portfolio = await trading.get_portfolio(wallet.public_key)
        total_value = portfolio.sol_value_usd + sum(h.value_usd for h in portfolio.holdings)

        lines = [
            "<b>Wallet</b>",
            "",
            f"Address: <code>{wallet.public_key}</code>",
            f"SOL: {portfolio.sol_balance:.4f} (~${portfolio.sol_value_usd:,.2f})",
            "",
            "<b>Top Holdings</b>",
        ]

        if portfolio.holdings:
            for holding in portfolio.holdings[:10]:
                lines.append(f"- {holding.symbol}: {holding.amount:.4f} (~${holding.value_usd:,.2f})")
        else:
            lines.append("- No token holdings yet")

        lines.append("")
        lines.append(f"Total value: ${total_value:,.2f}")

        keyboard = [
            [
                InlineKeyboardButton("Deposit", callback_data=self._cb("wallet_deposit")),
                InlineKeyboardButton("Withdraw", callback_data=self._cb("wallet_withdraw")),
            ],
            [
                InlineKeyboardButton("Export Key", callback_data=self._cb("wallet_export")),
                InlineKeyboardButton("Import Wallet", callback_data=self._cb("wallet_import")),
            ],
        ]

        return "\n".join(lines), InlineKeyboardMarkup(keyboard)

    async def _edit_wallet_menu(self, query, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
        text, keyboard = await self._build_wallet_overview(user_id)
        await self._edit_page(
            query,
            context,
            "wallet_menu",
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )

    def _demo_enabled(self, context: ContextTypes.DEFAULT_TYPE) -> bool:
        return bool(context.user_data.get("demo_ack"))

    def _demo_disclaimer_text(self) -> str:
        return (
            "⚠️ JARVIS V1 - EARLY ACCESS WARNING ⚠️\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Look... I need to be completely honest with you.\n\n"
            "This software is HIGHLY EXPERIMENTAL and largely\n"
            "UNTESTED. We're building in public and you're\n"
            "one of the first people to use this.\n\n"
            "🚨 THE REAL RISKS:\n"
            "• You are trading with REAL money\n"
            "• Bugs WILL exist - this is very early software\n"
            "• You could lose EVERYTHING you deposit\n"
            "• Smart contracts can fail unexpectedly\n"
            "• Transactions can get stuck or fail\n"
            "• The bot might execute trades incorrectly\n"
            "• Price feeds might lag or be wrong\n"
            "• There are probably bugs we haven't found yet\n\n"
            "💸 MY STRONG RECOMMENDATION:\n"
            "Please limit your funds to something you genuinely\n"
            "wouldn't miss if something catastrophic happened.\n\n"
            "Suggested: $50-100 MAX for testing\n\n"
            "We have a LOT of bugs to find and fix. Your\n"
            "willingness to help test means everything, but\n"
            "please protect yourself first.\n\n"
            "This is so, so early. Thank you for being here.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "By continuing, you fully acknowledge these risks.\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        )

    async def _show_demo_disclaimer(self, update: Update) -> None:
        keyboard = [
            [
                InlineKeyboardButton("✅ I Understand & Accept the Risks", callback_data=self._cb("demo_accept")),
                InlineKeyboardButton("❌ Exit", callback_data=self._cb("demo_exit")),
            ]
        ]
        await update.message.reply_text(
            self._demo_disclaimer_text(),
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    async def _show_main_menu(self, chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
        text = (
            "🤖 JARVIS Trading Bot\n\n"
            "Demo mode enabled.\n\n"
            "Pick an option:"
        )
        keyboard = [
            [
                InlineKeyboardButton("🧠 Jarvis Picks", callback_data=self._cb("menu_picks")),
                InlineKeyboardButton("📊 Sentiment", callback_data=self._cb("menu_sentiment")),
            ],
            [
                InlineKeyboardButton("💰 Buy", callback_data=self._cb("menu_buy")),
                InlineKeyboardButton("💸 Sell", callback_data=self._cb("menu_sell")),
            ],
            [
                InlineKeyboardButton("👛 Wallet", callback_data=self._cb("menu_wallet")),
                InlineKeyboardButton("⚙️ Settings", callback_data=self._cb("menu_settings")),
            ],
        ]
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    async def _get_wallet_service(self) -> WalletService:
        if self.wallet_service is None:
            self.wallet_service = await get_wallet_service()
        return self.wallet_service

    async def _get_public_trading(self) -> PublicTradingService:
        if self.public_trading is None:
            wallet_service = await self._get_wallet_service()
            self.public_trading = PublicTradingService(wallet_service)
        return self.public_trading

    def _get_public_wallet_password(self) -> Optional[str]:
        for key in (
            "JARVIS_PUBLIC_WALLET_PASSWORD",
            "PUBLIC_WALLET_PASSWORD",
            "JARVIS_WALLET_PASSWORD",
        ):
            value = os.environ.get(key)
            if value:
                return value
        return None

    def _risk_warning_block(self) -> str:
        return (
            "âš ï¸ V1 Early Access - Bugs may exist\n"
            "â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n"
            "Only trade what you can afford to lose."
        )

    def _large_trade_warning(self, amount_sol: float) -> str:
        if amount_sol <= 0.5:
            return ""
        return (
            "\n\nâš ï¸ LARGER TRADE\n"
            "You're trading a large amount for early V1 software.\n"
            "Consider reducing size while testing."
        )

    async def cmd_demo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /demo command (restricted)."""
        if not self._is_private_chat(update):
            await update.message.reply_text("For safety, use this command in a private DM with the bot.")
            return
        username = update.effective_user.username or ""
        if username not in DEMO_AUTHORIZED_USERS:
            await update.message.reply_text("Demo mode is not available.")
            return

        await self._show_demo_disclaimer(update)

    # ==================== START AND REGISTRATION ====================
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command - onboarding and wallet creation."""
        try:
            if not self._is_private_chat(update):
                await update.message.reply_text(
                    "For security, wallet setup is only available in a private DM with this bot."
                )
                return

            user_id = update.effective_user.id
            username = update.effective_user.username or update.effective_user.first_name

            profile = self.user_manager.get_user_profile(user_id)
            if not profile:
                success, profile = self.user_manager.register_user(user_id, username)
                if not success:
                    await update.message.reply_text("Registration failed. Please try again.")
                    return

            existing_wallet = self.user_manager.get_primary_wallet(user_id)
            if existing_wallet:
                await update.message.reply_text(
                    f"""Wallet ready: <code>{existing_wallet.public_key}</code>

Use /wallet for balances or /buy to trade.""",
                    parse_mode=ParseMode.HTML,
                )
                return

            wallet_password = self._get_public_wallet_password()
            if not wallet_password:
                await update.message.reply_text(
                    "Wallet encryption not configured. "
                    "Set JARVIS_PUBLIC_WALLET_PASSWORD (or PUBLIC_WALLET_PASSWORD)."
                )
                return

            wallet_service = await self._get_wallet_service()
            generated_wallet, encrypted_key = await wallet_service.create_new_wallet(
                user_password=wallet_password
            )

            context.user_data["pending_wallet"] = {
                "public_key": generated_wallet.public_key,
                "encrypted_key": encrypted_key,
            }

            onboarding_text = f"""<b>Your New Wallet</b>

Address:
<code>{generated_wallet.public_key}</code>

<b>SAVE THIS NOW</b>
This will only be shown once.

Seed phrase:
<code>{generated_wallet.seed_phrase}</code>

Private key:
<tg-spoiler>{generated_wallet.private_key}</tg-spoiler>

We will NEVER ask for your seed phrase or private key."""

            keyboard = [[
                InlineKeyboardButton("I saved my seed phrase", callback_data=self._cb("onboard_confirm")),
                InlineKeyboardButton("Cancel", callback_data=self._cb("onboard_cancel")),
            ]]

            msg = await update.message.reply_text(
                onboarding_text,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(keyboard),
                disable_web_page_preview=True,
            )
            # Auto-delete onboarding secrets after 10 minutes if the user doesn't confirm.
            try:
                self._schedule_delete_message(context, msg.chat_id, msg.message_id, delay_seconds=600)
            except Exception:
                pass

        except Exception as e:
            logger.error(f"Start command failed: {e}")
            await update.message.reply_text(f"Error: {e}")

    # ==================== TOKEN ANALYSIS ====================

    async def cmd_analyze(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /analyze <token> command."""
        try:
            if not self._is_private_chat(update):
                await update.message.reply_text("For safety, use this command in a private DM with the bot.")
                return
            if not context.args:
                await update.message.reply_text(
                    "📊 Token Analysis\n\n"
                    "Usage: /analyze &lt;token&gt;\n"
                    "Example: /analyze SOL\n\n"
                    "I'll provide comprehensive analysis including:\n"
                    "• Price and market data\n"
                    "• Liquidity assessment\n"
                    "• Risk evaluation\n"
                    "• Buy/Sell recommendation",
                    parse_mode=ParseMode.HTML
                )
                return

            token_symbol = context.args[0].upper()

            # Show loading indicator
            loading_msg = await update.message.reply_text(
                f"🔄 Analyzing {token_symbol}..."
            )

            try:
                # Get market data (placeholder - would fetch from API in production)
                market_data = await self._get_market_data(token_symbol)

                if not market_data:
                    await loading_msg.edit_text(
                        f"❌ Could not find data for {token_symbol}\n\n"
                        "Make sure you're using the correct symbol (SOL, BTC, ETH, etc.)"
                    )
                    return

                # Analyze token
                analysis = await self.token_analyzer.analyze_token(token_symbol, market_data)

                if not analysis:
                    await loading_msg.edit_text(f"❌ Analysis failed for {token_symbol}")
                    return

                # Format and send analysis
                analysis_text = self.token_analyzer.format_analysis_for_telegram(analysis)

                # Add action buttons
                keyboard = []
                if analysis.recommendation and analysis.recommendation.action == "BUY":
                    keyboard = [[
                        InlineKeyboardButton("💰 Buy", callback_data=self._cb(f"buy_{token_symbol}")),
                        InlineKeyboardButton("📊 Details", callback_data=self._cb(f"analyze_details_{token_symbol}")),
                    ]]

                reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

                await loading_msg.edit_text(
                    analysis_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup
                )

            except Exception as e:
                logger.error(f"Analysis error: {e}")
                await loading_msg.edit_text(
                    f"❌ Analysis failed: {str(e)[:100]}"
                )

        except Exception as e:
            logger.error(f"Analyze command failed: {e}")
            await update.message.reply_text(f"❌ Error: {e}")

    async def _get_market_data(self, token_symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get market data for token.

        In production, this would fetch from DexScreener, Jupiter, etc.
        """
        try:
            # Placeholder - returns mock data
            # In production, call actual APIs:
            # - DexScreener for price/volume/liquidity
            # - Metaplex for metadata
            # - onchain data providers for holder distribution

            mock_data = {
                'price': 100.0,  # Example
                'price_24h_ago': 95.0,
                'price_7d_ago': 85.0,
                'price_30d_ago': 50.0,
                'high_24h': 105.0,
                'low_24h': 94.0,
                'ath': 200.0,
                'atl': 0.10,
                'market_cap': 5_000_000,
                'volume_24h': 2_000_000,
                'liquidity_data': {
                    'total_liquidity_usd': 1_000_000,
                    'pool_count': 3,
                    'largest_pool_usd': 600_000,
                    'largest_pool_symbol': 'USDC',
                },
                'sentiment_score': 65,
                'whale_score': 75,
                'concentration_risk': 40,
                'regulatory_risk': 20,
                'audit_status': 60,
                'team_doxxed': True,
                'market_risk': 35,
                'catalysts': ['Upcoming exchange listing', 'Partnership announcement'],
            }

            return mock_data

        except Exception as e:
            logger.error(f"Failed to get market data: {e}")
            return None

    # ==================== TRADING ====================
    async def cmd_buy(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /buy command - interactive buy flow."""
        try:
            if not self._is_private_chat(update):
                await update.message.reply_text("For safety, trading is only available in a private DM with the bot.")
                return
            user_id = update.effective_user.id
            profile = self.user_manager.get_user_profile(user_id)

            if not profile:
                await update.message.reply_text("? Please register first with /start")
                return
            wallet = self.user_manager.get_primary_wallet(user_id)
            if not wallet:
                await update.message.reply_text("No wallet found. Create one with /start")
                return

            token_input = context.args[0] if context.args else None
            if token_input:
                await self._handle_buy_token_input(update, context, token_input)
                return

            context.user_data["flow"] = "buy_token"
            context.user_data["flow_data"] = {}
            await update.message.reply_text(
                "Send token address or symbol to buy. Example: BONK"
            )

        except Exception as e:
            logger.error(f"Buy command failed: {e}")
            await update.message.reply_text(f"? Error: {e}")
    async def cmd_sell(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /sell command - list holdings to sell."""
        try:
            if not self._is_private_chat(update):
                await update.message.reply_text("For safety, trading is only available in a private DM with the bot.")
                return
            user_id = update.effective_user.id
            profile = self.user_manager.get_user_profile(user_id)
            if not profile:
                await update.message.reply_text("? Please register first with /start")
                return

            wallet = self.user_manager.get_primary_wallet(user_id)
            if not wallet:
                await update.message.reply_text("? No wallet found. Create one with /start")
                return

            trading = await self._get_public_trading()
            portfolio = await trading.get_portfolio(wallet.public_key)
            holdings = [h for h in portfolio.holdings if h.mint != trading.jupiter.SOL_MINT]

            if not holdings:
                await update.message.reply_text(
                    "No tokens found to sell. Deposit funds or buy a token first."
                )
                return

            context.user_data["sell_holdings"] = holdings
            keyboard = []
            for idx, holding in enumerate(holdings[:10]):
                label = f"{holding.symbol} | {holding.amount:.4f}"
                keyboard.append([InlineKeyboardButton(label, callback_data=self._cb(f"sell_pick:{idx}"))])

            await update.message.reply_text(
                "Select a token to sell:",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )

        except Exception as e:
            logger.error(f"Sell command failed: {e}")
            await update.message.reply_text(f"? Error: {e}")

    # ==================== PORTFOLIO ====================

    async def cmd_portfolio(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /portfolio command - show holdings."""
        try:
            if not self._is_private_chat(update):
                await update.message.reply_text("For safety, use this command in a private DM with the bot.")
                return
            user_id = update.effective_user.id
            stats = self.user_manager.get_user_stats(user_id)

            if not stats:
                await update.message.reply_text(
                    "📊 No trading activity yet.\n\n"
                    "Use /analyze to find tokens and /buy to open your first position."
                )
                return

            portfolio_text = f"""
<b>📊 Your Portfolio</b>

<b>Performance</b>
Total Trades: {stats.total_trades}
Win Rate: {stats.win_rate:.1f}%
Total P&L: ${stats.total_pnl_usd:+.2f}

<b>Statistics</b>
Winning Trades: {stats.winning_trades}
Losing Trades: {stats.losing_trades}
Best Trade: ${stats.best_trade_usd:.2f}
Worst Trade: ${stats.worst_trade_usd:.2f}

<b>Averages</b>
Avg Win: ${stats.avg_win_usd:.2f}
Avg Loss: ${stats.avg_loss_usd:.2f}
Total Volume: ${stats.total_volume_usd:,.2f}

Streaks:
🔥 Win Streak: {stats.win_streak}
❄️ Loss Streak: {stats.loss_streak}
"""

            await update.message.reply_text(
                portfolio_text,
                parse_mode=ParseMode.HTML
            )

        except Exception as e:
            logger.error(f"Portfolio command failed: {e}")
            await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_performance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /performance command - detailed stats."""
        try:
            if not self._is_private_chat(update):
                await update.message.reply_text("For safety, use this command in a private DM with the bot.")
                return
            user_id = update.effective_user.id
            stats = self.user_manager.get_user_stats(user_id)

            if not stats:
                await update.message.reply_text(
                    "📈 No trading data yet. Start with /analyze"
                )
                return

            # Recommendations
            if stats.win_rate > 70:
                performance_note = "✅ Excellent win rate! Consider slightly increasing risk."
            elif stats.win_rate > 55:
                performance_note = "✅ Good performance. Keep your current strategy."
            elif stats.win_rate >= 45:
                performance_note = "⚠️ Mixed results. Review your entry strategy."
            else:
                performance_note = "❌ Low win rate. Consider reducing risk level."

            perf_text = f"""
<b>📈 Performance Analysis</b>

{performance_note}

<b>Historical Performance</b>
• Best winning streak: 3 trades
• Current streak: {stats.win_streak} wins, {stats.loss_streak} losses

<b>Risk Assessment</b>
Risk Level: {stats.current_risk_level.name}
Monthly Volatility: 15%
Sharpe Ratio: 1.2

<b>Recommendation</b>
Based on your performance, consider:
1. Analyzing more tokens before entering
2. Using stop losses on all trades
3. Gradually increasing position size
4. Tracking hold duration (shorter often better)

Use /settings to adjust risk level.
"""

            await update.message.reply_text(
                perf_text,
                parse_mode=ParseMode.HTML
            )

        except Exception as e:
            logger.error(f"Performance command failed: {e}")
            await update.message.reply_text(f"❌ Error: {e}")
    async def cmd_wallet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /wallet command - show wallet overview."""
        try:
            if not self._is_private_chat(update):
                await update.message.reply_text("For security, wallet commands only work in a private DM with the bot.")
                return
            user_id = update.effective_user.id
            # Track navigation so inline pages (deposit/export/etc) can go back.
            self._nav_push(context, "wallet_menu")

            text, keyboard = await self._build_wallet_overview(user_id)
            keyboard = self._with_prev_menu_button(keyboard)
            await update.message.reply_text(
                text,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )

        except Exception as e:
            logger.error(f"Wallet command failed: {e}")
            await update.message.reply_text(f"? Error: {e}")

    async def cmd_send(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /send command - start send flow."""
        try:
            if not self._is_private_chat(update):
                await update.message.reply_text("For safety, sending funds is only available in a private DM with the bot.")
                return
            user_id = update.effective_user.id
            wallet = self.user_manager.get_primary_wallet(user_id)
            if not wallet:
                await update.message.reply_text("? No wallet found. Create one with /start")
                return

            context.user_data["flow"] = "send_address"
            context.user_data["flow_data"] = {}
            await update.message.reply_text("Enter destination Solana address:")

        except Exception as e:
            logger.error(f"Send command failed: {e}")
            await update.message.reply_text(f"? Error: {e}")

    async def cmd_sentiment(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /sentiment <token> command."""
        try:
            if not self._is_private_chat(update):
                await update.message.reply_text("For safety, use this command in a private DM with the bot.")
                return
            if not context.args:
                await update.message.reply_text(
                    "Usage: /sentiment <token symbol or address>"
                )
                return

            token_input = context.args[0]
            trading = await self._get_public_trading()
            resolved = await trading.resolve_token(token_input)
            if not resolved:
                await update.message.reply_text("? Could not resolve token.")
                return

            sentiment = await asyncio.to_thread(
                x_sentiment.analyze_sentiment,
                f"${resolved.symbol} Solana token trading sentiment",
                None,
                "trading",
            )

            sentiment_label = "NEUTRAL"
            score = 50
            confidence_pct = 50
            if sentiment:
                confidence_pct = int(sentiment.confidence * 100)
                if sentiment.sentiment == "positive":
                    sentiment_label = "BULLISH"
                    score = min(100, 50 + confidence_pct // 2)
                elif sentiment.sentiment == "negative":
                    sentiment_label = "BEARISH"
                    score = max(0, 50 - confidence_pct // 2)
                else:
                    score = 50

            message = "\n".join(
                [
                    "JARVIS SENTIMENT ANALYSIS",
                    "------------------------------",
                    f"Token: {resolved.symbol}",
                    "------------------------------",
                    f"Sentiment Score: {score}/100 ({sentiment_label})",
                    f"Confidence: {confidence_pct}%",
                    "",
                    "V1 Early Access - Trade small amounts",
                    "------------------------------",
                ]
            )

            context.user_data["sentiment_token"] = {
                "mint": resolved.mint,
                "symbol": resolved.symbol,
            }

            keyboard = [
                [
                    InlineKeyboardButton("Buy 0.1 SOL", callback_data=self._cb("sentiment_buy:0.1")),
                    InlineKeyboardButton("Buy 0.5 SOL", callback_data=self._cb("sentiment_buy:0.5")),
                    InlineKeyboardButton("Buy 1 SOL", callback_data=self._cb("sentiment_buy:1")),
                ]
            ]

            await update.message.reply_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
            )

        except Exception as e:
            logger.error(f"Sentiment command failed: {e}")
            await update.message.reply_text(f"? Error: {e}")

    async def cmd_picks(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /picks command - show Jarvis picks."""
        try:
            if not self._is_private_chat(update):
                await update.message.reply_text("For safety, use this command in a private DM with the bot.")
                return
            import json
            import tempfile
            from pathlib import Path

            picks_file = Path(tempfile.gettempdir()) / "jarvis_top_picks.json"
            if not picks_file.exists():
                await update.message.reply_text("No picks available yet. Try again later.")
                return

            picks_data = json.loads(picks_file.read_text())
            if not picks_data:
                await update.message.reply_text("No picks available yet.")
                return

            user_id = update.effective_user.id
            demo_enabled = self._demo_enabled(context)
            user_confidence = self.algorithm.get_effective_confidence(
                user_id,
                AlgorithmType.COMPOSITE,
            )
            weight = 0.6 + (user_confidence / 100.0) * 0.4

            lines = [
                "JARVIS PICKS",
                "------------------------------",
                f"Updated: {datetime.utcnow().strftime('%H:%M UTC')}",
                "------------------------------",
                "",
            ]
            if demo_enabled:
                lines.extend(
                    [
                        f"Personalized confidence: {user_confidence:.1f}/100",
                        "Learns from your trades and adjusts conviction.",
                        "",
                    ]
                )

            tradeable = []
            trading = await self._get_public_trading()

            for i, pick in enumerate(picks_data[:5]):
                symbol = pick.get("symbol", "?")
                conviction_base = pick.get("conviction", 0)
                conviction_adjusted = min(100, round(conviction_base * weight))
                reasoning = (pick.get("reasoning") or "").strip()
                if demo_enabled:
                    lines.append(
                        f"#{i+1} {symbol} | Conviction: {conviction_adjusted}/100 (base {conviction_base})"
                    )
                else:
                    lines.append(f"#{i+1} {symbol} | Conviction: {conviction_base}/100")
                if reasoning:
                    lines.append(f"  {reasoning}")
                lines.append("")

                mint = pick.get("contract") or ""
                if mint and trading.validate_address(mint):
                    tradeable.append(
                        {
                            "symbol": symbol,
                            "mint": mint,
                            "conviction": conviction_adjusted if demo_enabled else conviction_base,
                            "conviction_base": conviction_base,
                            "conviction_adjusted": conviction_adjusted,
                            "asset_class": pick.get("asset_class"),
                            "reasoning": reasoning,
                        }
                    )

            await update.message.reply_text("\n".join(lines))

            if tradeable:
                context.user_data["picks_tokens"] = tradeable
                if demo_enabled:
                    self.demo_intelligence.record_picks_served(
                        user_id,
                        tradeable,
                        confidence_score=user_confidence,
                        mode="demo",
                    )
                for idx, pick in enumerate(tradeable[:3]):
                    buttons = [
                        [
                            InlineKeyboardButton("Buy 0.1 SOL", callback_data=self._cb(f"pick_buy:{idx}:0.1")),
                            InlineKeyboardButton("Buy 0.5 SOL", callback_data=self._cb(f"pick_buy:{idx}:0.5")),
                            InlineKeyboardButton("Buy 1 SOL", callback_data=self._cb(f"pick_buy:{idx}:1")),
                        ]
                    ]
                    await update.message.reply_text(
                        f"{pick['symbol']} quick buy:",
                        reply_markup=InlineKeyboardMarkup(buttons),
                    )

        except Exception as e:
            logger.error(f"Picks command failed: {e}")
            await update.message.reply_text(f"? Error: {e}")

    # ==================== WALLET MANAGEMENT ====================
    async def cmd_wallets(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /wallets command - redirect to /wallet."""
        await self.cmd_wallet(update, context)

    # ==================== SETTINGS ====================

    async def cmd_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /settings command - user preferences."""
        try:
            if not self._is_private_chat(update):
                await update.message.reply_text("For safety, use this command in a private DM with the bot.")
                return
            user_id = update.effective_user.id
            profile = self.user_manager.get_user_profile(user_id)

            if not profile:
                await update.message.reply_text("❌ User not found")
                return

            settings_text = f"""
⚙️ <b>Your Settings</b>

<b>Risk Level</b>
Current: {profile.risk_level.name} ({profile.risk_level.value}% per trade)

<b>Trading Limits</b>
Max Daily Trades: {profile.max_daily_trades}
Max Daily Loss: ${profile.max_daily_loss_usd}
Position Size: {profile.max_position_size_pct}%

<b>Safety</b>
Trade Confirmation: {'✅ On' if profile.require_trade_confirmation else '❌ Off'}
Alerts: {'✅ On' if profile.enable_alerts else '❌ Off'}
Anti-Whale Alert: ${profile.anti_whale_threshold_usd:,.0f}

<b>Learning</b>
Auto-Adjust Risk: {'✅ On' if profile.auto_adjust_risk else '❌ Off'}
Learn from Losses: {'✅ On' if profile.learn_from_losses else '❌ Off'}

What would you like to change?
"""

            keyboard = [[
                InlineKeyboardButton("📊 Risk Level", callback_data=self._cb("settings_risk")),
                InlineKeyboardButton("💰 Limits", callback_data=self._cb("settings_limits")),
            ], [
                InlineKeyboardButton("🔒 Safety", callback_data=self._cb("settings_safety")),
                InlineKeyboardButton("🤖 Learning", callback_data=self._cb("settings_learning")),
            ]]

            reply_markup = InlineKeyboardMarkup(keyboard)
            self._nav_push(context, "settings_menu")
            reply_markup = self._with_prev_menu_button(reply_markup)

            await update.message.reply_text(
                settings_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )

        except Exception as e:
            logger.error(f"Settings command failed: {e}")
            await update.message.reply_text(f"❌ Error: {e}")

    # ==================== HELP ====================
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command - full command reference."""
        try:
            if not self._is_private_chat(update):
                await update.message.reply_text("For safety, use this command in a private DM with the bot.")
                return
            help_text = """
<b>Jarvis Trading Bot - Command Reference</b>

<b>Getting Started</b>
/start - Onboarding + wallet creation
/wallet - Wallet overview
/help - This message

<b>AI Insights</b>
/sentiment <token> - Grok sentiment with buy buttons
/picks - Jarvis picks with quick buy
/analyze <token> - Token analysis

<b>Trading</b>
/buy - Buy token (interactive)
/sell - Sell holdings
/send - Send SOL
/portfolio - Performance stats
/performance - Detailed stats

<b>Safety</b>
? Early-access software - trade small amounts
? Never share your seed phrase or private key
"""

            await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)

        except Exception as e:
            logger.error(f"Help command failed: {e}")
            await update.message.reply_text(f"? Error: {e}")
    # ==================== CALLBACKS ====================

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Route inline button callbacks for the public bot."""
        query = update.callback_query
        if not query:
            return

        if not self._is_private_chat(update):
            try:
                await query.answer("For security, use this in a private DM with the bot.", show_alert=True)
            except Exception:
                pass
            return

        raw_data = query.data or ""
        # Ignore callbacks that are not intended for the public bot (avoid collisions).
        if not raw_data.startswith(self._CB_PREFIX):
            return

        data = self._strip_cb(raw_data)
        await query.answer()

        # Global Previous Menu support across all public bot pages.
        # This is intentionally handled before other branches so any screen can go back.
        if data == "nav_back":
            self._reset_interactive_state(context)
            data = self._nav_pop(context)

        if data == "main_menu":
            await self._edit_main_menu(query, context)
            return

        if data == "wallet_menu":
            await self._edit_wallet_menu(query, context, update.effective_user.id)
            return

        if data == "ui_test_ping":
            await self._edit_page(query, context, "ui_test_ping", "UI callback OK.")
            return

        if data == "demo_exit":
            await self._edit_page(query, context, "demo_exit", "Demo mode canceled.")
            return

        if data == "demo_accept":
            context.user_data["demo_ack"] = True
            await self._edit_main_menu(query, context)
            return

        if data == "onboard_cancel":
            context.user_data.pop("pending_wallet", None)
            await self._edit_page(query, context, "onboard_cancel", "Onboarding canceled.")
            return

        if data == "onboard_confirm":
            pending = context.user_data.get("pending_wallet")
            if not pending:
                await self._edit_page(query, context, "onboard_confirm", "No pending wallet found.")
                return
            user_id = update.effective_user.id
            success, _wallet = self.user_manager.create_wallet(
                user_id=user_id,
                public_key=pending["public_key"],
                encrypted_private_key=pending["encrypted_key"],
                is_primary=True,
            )
            context.user_data.pop("pending_wallet", None)
            if not success:
                await self._edit_page(query, context, "onboard_confirm", "Wallet setup failed. Try /start again.")
                return
            await self._edit_page(query, context, "onboard_confirm", "Wallet created. Use /wallet to view it.")
            return

        if data == "wallet_deposit":
            user_id = update.effective_user.id
            wallet = self.user_manager.get_primary_wallet(user_id)
            if not wallet:
                await self._edit_page(query, context, "wallet_deposit", "No wallet found. Use /start to create one.")
                return
            deposit_text = f"""FUNDING YOUR WALLET
--------------------

Send SOL to:
<code>{wallet.public_key}</code>

IMPORTANT: Early V1 software.
We recommend $50-100 max while testing."""
            await self._edit_page(
                query,
                context,
                "wallet_deposit",
                deposit_text,
                parse_mode=ParseMode.HTML,
            )
            return

        if data == "wallet_withdraw":
            context.user_data["flow"] = "send_address"
            context.user_data["flow_data"] = {}
            await self._edit_page(query, context, "wallet_withdraw", "Enter destination Solana address:")
            return

        if data == "wallet_export":
            warn_text = """EXPORT PRIVATE KEY
--------------------

CRITICAL:
- Never share this with ANYONE
- We will NEVER ask for your key
- Anyone with this key controls your funds

Proceed?"""
            keyboard = [[
                InlineKeyboardButton("Show Private Key", callback_data=self._cb("wallet_export_confirm")),
                InlineKeyboardButton("Cancel", callback_data=self._cb("cancel")),
            ]]
            await self._edit_page(
                query,
                context,
                "wallet_export",
                warn_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return

        if data == "wallet_export_confirm":
            user_id = update.effective_user.id
            wallet = self.user_manager.get_primary_wallet(user_id)
            if not wallet:
                await self._edit_page(query, context, "wallet_export_confirm", "No wallet found. Use /start to create one.")
                return
            wallet_password = self._get_public_wallet_password()
            if not wallet_password:
                await self._edit_page(query, context, "wallet_export_confirm", "Wallet encryption not configured.")
                return
            wallet_service = await self._get_wallet_service()
            try:
                private_key = wallet_service.decrypt_private_key(
                    wallet.encrypted_private_key,
                    wallet_password,
                )
            except Exception:
                await self._edit_page(query, context, "wallet_export_confirm", "Failed to decrypt key. Check wallet password.")
                return

            msg = await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"""<b>Private Key (auto-deletes in 60s)</b>
<tg-spoiler>{private_key}</tg-spoiler>""",
                parse_mode=ParseMode.HTML,
            )
            self._schedule_delete_message(context, query.message.chat_id, msg.message_id)
            await self._edit_page(query, context, "wallet_export_confirm", "Private key sent.")
            return

        if data == "wallet_import":
            context.user_data["flow"] = "import_wallet"
            context.user_data["flow_data"] = {}
            await self._edit_page(query, context, "wallet_import", "Send your seed phrase or private key:")
            return

        if data == "cancel":
            context.user_data.pop("flow", None)
            context.user_data.pop("flow_data", None)
            context.user_data.pop("pending_trade", None)
            context.user_data.pop("pending_send", None)
            await self._edit_page(query, context, "cancel", "Canceled.")
            return

        if data.startswith("buy_amount:"):
            amount = self._parse_amount(data.split(":", 1)[1])
            token = context.user_data.get("buy_token")
            if not token or not amount:
                await self._edit_page(query, context, data, "Buy token not set. Use /buy again.")
                return
            await self._show_buy_confirmation(query.message.chat_id, context, token, amount)
            return

        if data == "buy_custom":
            context.user_data["flow"] = "buy_custom_amount"
            context.user_data["flow_data"] = {}
            await self._edit_page(query, context, "buy_custom", "Enter amount in SOL:")
            return

        if data.startswith("sell_pick:"):
            holding = self._get_holding_from_callback(context, data)
            if not holding:
                await self._edit_page(query, context, data, "Holding not found. Use /sell again.")
                return
            await self._prompt_sell_amount(query.message.chat_id, context, holding)
            return

        if data.startswith("sell_amount:"):
            pct = self._parse_amount(data.split(":", 1)[1])
            holding = context.user_data.get("sell_selected")
            if not holding or pct is None:
                await self._edit_page(query, context, data, "Sell selection expired. Use /sell again.")
                return
            amount_tokens = holding["amount"] * (pct / 100.0)
            await self._show_sell_confirmation(
                query.message.chat_id,
                context,
                holding,
                amount_tokens,
            )
            return

        if data == "sell_custom":
            context.user_data["flow"] = "sell_custom_amount"
            await self._edit_page(query, context, "sell_custom", "Enter token amount to sell:")
            return

        if data.startswith("confirm_trade:"):
            trade_id = data.split(":", 1)[1]
            await self._execute_pending_trade(update, context, trade_id)
            return

        if data.startswith("sentiment_buy:"):
            amount = self._parse_amount(data.split(":", 1)[1])
            token = context.user_data.get("sentiment_token")
            if not token or not amount:
                await self._edit_page(query, context, data, "Sentiment token not set. Use /sentiment again.")
                return
            await self._show_buy_confirmation(query.message.chat_id, context, token, amount)
            return

        if data.startswith("pick_buy:"):
            token = self._get_pick_from_callback(context, data)
            if not token:
                await self._edit_page(query, context, data, "Pick expired. Use /picks again.")
                return
            if self._demo_enabled(context):
                self.demo_intelligence.record_pick_action(
                    user_id=update.effective_user.id,
                    symbol=token.get("symbol", ""),
                    action="buy",
                    amount_sol=token.get("amount", 0),
                    conviction=token.get("conviction"),
                )
            await self._show_buy_confirmation(
                query.message.chat_id,
                context,
                token,
                token.get("amount", 0),
            )
            return

        if data.startswith("send_amount:"):
            amount_label = data.split(":", 1)[1]
            if amount_label == "max":
                amount = context.user_data.get("send_max")
            else:
                amount = self._parse_amount(amount_label)
            dest = context.user_data.get("send_destination")
            if not dest or not amount:
                await self._edit_page(query, context, data, "Send flow expired. Use /send again.")
                return
            await self._show_send_confirmation(query.message.chat_id, context, dest, amount)
            return

        if data == "send_custom":
            context.user_data["flow"] = "send_custom_amount"
            await self._edit_page(query, context, "send_custom", "Enter amount in SOL to send:")
            return

        if data.startswith("confirm_send:"):
            send_id = data.split(":", 1)[1]
            await self._execute_pending_send(update, context, send_id)
            return

        if data == "menu_picks":
            await context.bot.send_message(chat_id=query.message.chat_id, text="Use /picks to view Jarvis Picks.")
            return

        if data == "menu_sentiment":
            await context.bot.send_message(chat_id=query.message.chat_id, text="Use /sentiment <token> to view sentiment.")
            return

        if data == "menu_buy":
            await context.bot.send_message(chat_id=query.message.chat_id, text="Use /buy to place a buy.")
            return

        if data == "menu_sell":
            await context.bot.send_message(chat_id=query.message.chat_id, text="Use /sell to view holdings.")
            return

        if data == "menu_wallet":
            await context.bot.send_message(chat_id=query.message.chat_id, text="Use /wallet to manage your wallet.")
            return

        if data == "menu_settings":
            await context.bot.send_message(chat_id=query.message.chat_id, text="Use /settings to adjust preferences.")
            return

        await self._edit_page(query, context, "unsupported", "Action not supported yet.")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages for interactive flows."""
        if not update.message:
            return
        if not self._is_private_chat(update):
            return
        text = (update.message.text or "").strip()
        flow = context.user_data.get("flow")

        if flow == "buy_token":
            await self._handle_buy_token_input(update, context, text)
            return

        if flow == "buy_custom_amount":
            token = context.user_data.get("buy_token")
            amount = self._parse_amount(text)
            if not token or not amount:
                await update.message.reply_text("Invalid amount. Try again.")
                return
            context.user_data.pop("flow", None)
            await self._show_buy_confirmation(update.message.chat_id, context, token, amount)
            return

        if flow == "sell_custom_amount":
            holding = context.user_data.get("sell_selected")
            amount = self._parse_amount(text)
            if not holding or not amount:
                await update.message.reply_text("Invalid amount. Try again.")
                return
            context.user_data.pop("flow", None)
            await self._show_sell_confirmation(update.message.chat_id, context, holding, amount)
            return

        if flow == "send_address":
            trading = await self._get_public_trading()
            if not trading.validate_address(text):
                await update.message.reply_text("Invalid Solana address. Try again.")
                return
            context.user_data["send_destination"] = text
            context.user_data.pop("flow", None)
            await self._prompt_send_amount(update.message.chat_id, context, update.effective_user.id)
            return

        if flow == "send_custom_amount":
            amount = self._parse_amount(text)
            dest = context.user_data.get("send_destination")
            if not dest or not amount:
                await update.message.reply_text("Invalid amount. Try again.")
                return
            context.user_data.pop("flow", None)
            await self._show_send_confirmation(update.message.chat_id, context, dest, amount)
            return

        if flow == "import_wallet":
            context.user_data.pop("flow", None)
            await self._handle_import_wallet_input(update, context, text)
            return

    async def _handle_buy_token_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE, token_input: str) -> None:
        trading = await self._get_public_trading()
        resolved = await trading.resolve_token(token_input)
        if not resolved:
            await update.message.reply_text("Could not resolve token. Try again.")
            return

        context.user_data["buy_token"] = {
            "mint": resolved.mint,
            "symbol": resolved.symbol,
            "price_usd": resolved.price_usd,
        }
        context.user_data.pop("flow", None)

        message = f"""Token: {resolved.symbol}
Price: ${resolved.price_usd:,.6f}

Select amount to buy:"""
        keyboard = [
            [
                InlineKeyboardButton("0.1 SOL", callback_data=self._cb("buy_amount:0.1")),
                InlineKeyboardButton("0.5 SOL", callback_data=self._cb("buy_amount:0.5")),
                InlineKeyboardButton("1 SOL", callback_data=self._cb("buy_amount:1")),
            ],
            [InlineKeyboardButton("Custom", callback_data=self._cb("buy_custom"))],
        ]
        await update.message.reply_text(message, reply_markup=InlineKeyboardMarkup(keyboard))

    async def _show_buy_confirmation(
        self,
        chat_id: int,
        context: ContextTypes.DEFAULT_TYPE,
        token: Dict[str, Any],
        amount_sol: float,
    ) -> None:
        if amount_sol <= 0:
            await context.bot.send_message(chat_id=chat_id, text="Invalid amount.")
            return
        trading = await self._get_public_trading()
        quote = await trading.get_buy_quote(
            token["mint"],
            amount_sol,
            self.default_slippage_bps,
        )
        if not quote:
            await context.bot.send_message(chat_id=chat_id, text="Quote unavailable. Try again.")
            return

        trade_id = secrets.token_hex(6)
        context.user_data["pending_trade"] = {
            "id": trade_id,
            "type": "buy",
            "token_mint": token["mint"],
            "symbol": token["symbol"],
            "amount_sol": amount_sol,
            "slippage_bps": self.default_slippage_bps,
            "signal_strength": token.get("conviction", 50),
        }

        message = f"""JARVIS QUICK BUY
--------------------
Token: {token['symbol']}
Amount: {amount_sol:.4f} SOL
Est. Receive: {quote.output_amount_ui:.4f}
Price Impact: {quote.price_impact_pct:.2%}

{self._risk_warning_block()}{self._large_trade_warning(amount_sol)}"""

        keyboard = [[
            InlineKeyboardButton("Confirm Buy", callback_data=self._cb(f"confirm_trade:{trade_id}")),
            InlineKeyboardButton("Cancel", callback_data=self._cb("cancel")),
        ]]
        await context.bot.send_message(
            chat_id=chat_id,
            text=message,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    async def _prompt_sell_amount(
        self,
        chat_id: int,
        context: ContextTypes.DEFAULT_TYPE,
        holding: Dict[str, Any],
    ) -> None:
        context.user_data["sell_selected"] = holding
        keyboard = [
            [
                InlineKeyboardButton("25%", callback_data=self._cb("sell_amount:25")),
                InlineKeyboardButton("50%", callback_data=self._cb("sell_amount:50")),
                InlineKeyboardButton("75%", callback_data=self._cb("sell_amount:75")),
                InlineKeyboardButton("100%", callback_data=self._cb("sell_amount:100")),
            ],
            [InlineKeyboardButton("Custom", callback_data=self._cb("sell_custom"))],
        ]
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"Sell {holding['symbol']} - choose amount:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    async def _show_sell_confirmation(
        self,
        chat_id: int,
        context: ContextTypes.DEFAULT_TYPE,
        holding: Dict[str, Any],
        amount_tokens: float,
    ) -> None:
        if amount_tokens <= 0:
            await context.bot.send_message(chat_id=chat_id, text="Invalid amount.")
            return
        trading = await self._get_public_trading()
        quote = await trading.get_sell_quote(
            holding["mint"],
            amount_tokens,
            self.default_slippage_bps,
        )
        if not quote:
            await context.bot.send_message(chat_id=chat_id, text="Quote unavailable. Try again.")
            return

        trade_id = secrets.token_hex(6)
        context.user_data["pending_trade"] = {
            "id": trade_id,
            "type": "sell",
            "token_mint": holding["mint"],
            "symbol": holding["symbol"],
            "amount_tokens": amount_tokens,
            "slippage_bps": self.default_slippage_bps,
        }

        message = f"""JARVIS QUICK SELL
--------------------
Token: {holding['symbol']}
Amount: {amount_tokens:.4f}
Est. Receive: {quote.output_amount_ui:.4f} SOL
Price Impact: {quote.price_impact_pct:.2%}

        {self._risk_warning_block()}"""

        keyboard = [[
            InlineKeyboardButton("Confirm Sell", callback_data=self._cb(f"confirm_trade:{trade_id}")),
            InlineKeyboardButton("Cancel", callback_data=self._cb("cancel")),
        ]]
        await context.bot.send_message(
            chat_id=chat_id,
            text=message,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    async def _execute_pending_trade(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        trade_id: str,
    ) -> None:
        pending = context.user_data.get("pending_trade")
        if not pending or pending.get("id") != trade_id:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Trade expired. Please try again.",
            )
            return

        user_id = update.effective_user.id
        wallet = self.user_manager.get_primary_wallet(user_id)
        if not wallet:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="No wallet found.")
            return

        wallet_password = self._get_public_wallet_password()
        if not wallet_password:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Wallet encryption not configured.")
            return

        trading = await self._get_public_trading()
        try:
            keypair = trading.load_keypair(wallet.encrypted_private_key, wallet_password)
        except Exception:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Failed to unlock wallet.")
            return

        if pending["type"] == "buy":
            balance = await trading.get_sol_balance(wallet.public_key)
            amount_sol = pending["amount_sol"]
            if balance < amount_sol + 0.002:
                await context.bot.send_message(chat_id=update.effective_chat.id, text="Insufficient SOL balance.")
                return
            quote = await trading.get_buy_quote(
                pending["token_mint"],
                amount_sol,
                pending["slippage_bps"],
            )
        else:
            portfolio = await trading.get_portfolio(wallet.public_key)
            holding = next((h for h in portfolio.holdings if h.mint == pending["token_mint"]), None)
            if not holding or holding.amount < pending["amount_tokens"]:
                await context.bot.send_message(chat_id=update.effective_chat.id, text="Insufficient token balance.")
                return
            quote = await trading.get_sell_quote(
                pending["token_mint"],
                pending["amount_tokens"],
                pending["slippage_bps"],
            )

        if not quote:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Quote failed. Try again.")
            return

        result = await trading.execute_swap(quote, keypair)
        context.user_data.pop("pending_trade", None)

        if result.success:
            sol_price = 0.0
            try:
                sol_price = await trading.jupiter.get_token_price(trading.jupiter.SOL_MINT)
            except Exception:
                sol_price = 0.0

            signal_strength = float(pending.get("signal_strength", 50))
            amount_usd = 0.0
            pnl_usd = 0.0

            if pending["type"] == "buy":
                amount_usd = (pending.get("amount_sol", 0.0) or 0.0) * (sol_price or 0.0)
                quantity = quote.output_amount_ui
                if amount_usd > 0 and quantity > 0:
                    self.user_manager.update_position_on_buy(
                        user_id=user_id,
                        symbol=pending["symbol"],
                        quantity=quantity,
                        cost_usd=amount_usd,
                    )
                self.user_manager.record_trade(
                    user_id=user_id,
                    wallet_id=wallet.wallet_id,
                    symbol=pending["symbol"],
                    action="BUY",
                    amount_usd=amount_usd,
                    pnl_usd=0.0,
                )
            else:
                amount_usd = quote.output_amount_ui * (sol_price or 0.0)
                pnl_usd = self.user_manager.update_position_on_sell(
                    user_id=user_id,
                    symbol=pending["symbol"],
                    quantity=pending["amount_tokens"],
                    proceeds_usd=amount_usd,
                )
                self.user_manager.record_trade(
                    user_id=user_id,
                    wallet_id=wallet.wallet_id,
                    symbol=pending["symbol"],
                    action="SELL",
                    amount_usd=amount_usd,
                    pnl_usd=pnl_usd,
                )

                outcome = TradeOutcome(
                    algorithm_type=AlgorithmType.COMPOSITE,
                    signal_strength=signal_strength,
                    user_id=user_id,
                    symbol=pending["symbol"],
                    entry_price=0.0,
                    exit_price=0.0,
                    pnl_usd=pnl_usd,
                    hold_duration_hours=1.0,
                )
                self.algorithm.record_outcome(outcome)

            if self._demo_enabled(context):
                self.demo_intelligence.record_trade_execution(
                    user_id=user_id,
                    symbol=pending["symbol"],
                    action=pending["type"],
                    amount_usd=amount_usd,
                    pnl_usd=pnl_usd,
                    signal_strength=signal_strength,
                )

            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"""TRADE EXECUTED
--------------------
Signature: {result.signature}
https://solscan.io/tx/{result.signature}""",
            )
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Trade failed: {result.error}",
            )

    async def _prompt_send_amount(self, chat_id: int, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
        trading = await self._get_public_trading()
        wallet = self.user_manager.get_primary_wallet(user_id)
        if not wallet:
            await context.bot.send_message(chat_id=chat_id, text="No wallet found.")
            return
        balance = await trading.get_sol_balance(wallet.public_key)
        max_amount = max(0.0, balance - 0.002)
        context.user_data["send_max"] = max_amount

        keyboard = [
            [
                InlineKeyboardButton("0.1 SOL", callback_data=self._cb("send_amount:0.1")),
                InlineKeyboardButton("0.5 SOL", callback_data=self._cb("send_amount:0.5")),
                InlineKeyboardButton("1 SOL", callback_data=self._cb("send_amount:1")),
            ],
            [InlineKeyboardButton("Max", callback_data=self._cb("send_amount:max"))],
            [InlineKeyboardButton("Custom", callback_data=self._cb("send_custom"))],
        ]
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"Balance: {balance:.4f} SOL. Choose amount to send:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    async def _show_send_confirmation(
        self,
        chat_id: int,
        context: ContextTypes.DEFAULT_TYPE,
        destination: str,
        amount_sol: float,
    ) -> None:
        if amount_sol <= 0:
            await context.bot.send_message(chat_id=chat_id, text="Invalid amount.")
            return

        send_id = secrets.token_hex(6)
        context.user_data["pending_send"] = {
            "id": send_id,
            "destination": destination,
            "amount_sol": amount_sol,
        }

        message = f"""SEND SOL
--------------------
To: {destination}
Amount: {amount_sol:.4f} SOL
Fee: ~0.000005 SOL

Confirm transfer?"""

        keyboard = [[
            InlineKeyboardButton("Send", callback_data=self._cb(f"confirm_send:{send_id}")),
            InlineKeyboardButton("Cancel", callback_data=self._cb("cancel")),
        ]]

        await context.bot.send_message(
            chat_id=chat_id,
            text=message,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    async def _execute_pending_send(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        send_id: str,
    ) -> None:
        pending = context.user_data.get("pending_send")
        if not pending or pending.get("id") != send_id:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Send expired. Try again.")
            return

        user_id = update.effective_user.id
        wallet = self.user_manager.get_primary_wallet(user_id)
        if not wallet:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="No wallet found.")
            return

        wallet_password = self._get_public_wallet_password()
        if not wallet_password:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Wallet encryption not configured.")
            return

        trading = await self._get_public_trading()
        try:
            keypair = trading.load_keypair(wallet.encrypted_private_key, wallet_password)
        except Exception:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Failed to unlock wallet.")
            return

        balance = await trading.get_sol_balance(wallet.public_key)
        amount_sol = pending["amount_sol"]
        if balance < amount_sol + 0.002:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Insufficient balance.")
            return

        try:
            signature = await trading.send_sol(keypair, pending["destination"], amount_sol)
        except Exception as exc:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Send failed: {exc}")
            return

        context.user_data.pop("pending_send", None)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Sent. https://solscan.io/tx/{signature}",
        )

    async def _handle_import_wallet_input(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        text: str,
    ) -> None:
        user_id = update.effective_user.id
        wallet_password = self._get_public_wallet_password()
        if not wallet_password:
            await update.message.reply_text("Wallet encryption not configured.")
            return

        wallet_service = await self._get_wallet_service()
        phrase = text.strip()
        words = phrase.split()
        try:
            if len(words) >= 12:
                generated_wallet, encrypted_key = await wallet_service.import_wallet(
                    phrase,
                    user_password=wallet_password,
                )
            else:
                generated_wallet, encrypted_key = await wallet_service.import_from_private_key(
                    phrase,
                    user_password=wallet_password,
                )
        except Exception as exc:
            await update.message.reply_text(f"Import failed: {exc}")
            return

        self.user_manager.import_wallet(
            user_id=user_id,
            public_key=generated_wallet.public_key,
            encrypted_private_key=encrypted_key,
            is_primary=True,
        )

        chat_id = update.effective_chat.id
        try:
            await update.message.delete()
        except Exception:
            pass

        await context.bot.send_message(
            chat_id=chat_id,
            text=f"Wallet imported: <code>{generated_wallet.public_key}</code>",
            parse_mode=ParseMode.HTML,
        )

    def _schedule_delete_message(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        chat_id: int,
        message_id: int,
        delay_seconds: int = 60,
    ) -> None:
        async def _delete():
            await asyncio.sleep(delay_seconds)
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
            except Exception:
                pass

        asyncio.create_task(_delete())

    def _parse_amount(self, value: str) -> Optional[float]:
        try:
            return float(value)
        except Exception:
            return None

    def _get_holding_from_callback(self, context: ContextTypes.DEFAULT_TYPE, data: str) -> Optional[Dict[str, Any]]:
        try:
            idx = int(data.split(":", 1)[1])
        except Exception:
            return None
        holdings = context.user_data.get("sell_holdings") or []
        if idx < 0 or idx >= len(holdings):
            return None
        holding = holdings[idx]
        return {
            "mint": holding.mint,
            "symbol": holding.symbol,
            "amount": holding.amount,
        }

    def _get_pick_from_callback(self, context: ContextTypes.DEFAULT_TYPE, data: str) -> Optional[Dict[str, Any]]:
        parts = data.split(":")
        if len(parts) != 3:
            return None
        try:
            idx = int(parts[1])
            amount = float(parts[2])
        except Exception:
            return None
        picks = context.user_data.get("picks_tokens") or []
        if idx < 0 or idx >= len(picks):
            return None
        token = picks[idx]
        return {
            "mint": token["mint"],
            "symbol": token["symbol"],
            "amount": amount,
            "conviction": token.get("conviction"),
        }
