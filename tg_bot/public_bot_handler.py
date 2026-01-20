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
from core.adaptive_algorithm import AdaptiveAlgorithm, TradeOutcome
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
        self.default_slippage_bps = 100

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
                InlineKeyboardButton("✅ I Understand & Accept the Risks", callback_data="demo_accept"),
                InlineKeyboardButton("❌ Exit", callback_data="demo_exit"),
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
                InlineKeyboardButton("🧠 Jarvis Picks", callback_data="menu_picks"),
                InlineKeyboardButton("📊 Sentiment", callback_data="menu_sentiment"),
            ],
            [
                InlineKeyboardButton("💰 Buy", callback_data="menu_buy"),
                InlineKeyboardButton("💸 Sell", callback_data="menu_sell"),
            ],
            [
                InlineKeyboardButton("👛 Wallet", callback_data="menu_wallet"),
                InlineKeyboardButton("⚙️ Settings", callback_data="menu_settings"),
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
        username = update.effective_user.username or ""
        if username not in DEMO_AUTHORIZED_USERS:
            await update.message.reply_text("Demo mode is not available.")
            return

        await self._show_demo_disclaimer(update)

    # ==================== START AND REGISTRATION ====================
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command - onboarding and wallet creation."""
        try:
            user_id = update.effective_user.id
            username = update.effective_user.username or update.effective_user.first_name

            profile = self.user_manager.get_user_profile(user_id)
            if not profile:
                success, profile = self.user_manager.register_user(user_id, username)
                if not success:
                    await update.message.reply_text("? Registration failed. Please try again.")
                    return

            existing_wallet = self.user_manager.get_primary_wallet(user_id)
            if existing_wallet:
                await update.message.reply_text(
                    f"? Wallet ready: <code>{existing_wallet.public_key}</code>

"
                    "Use /wallet for balances or /buy to trade.",
                    parse_mode=ParseMode.HTML,
                )
                return

            wallet_password = self._get_public_wallet_password()
            if not wallet_password:
                await update.message.reply_text(
                    "? Wallet encryption not configured.
"
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

            onboarding_text = (
                "<b>?? Your New Wallet</b>

"
                "Address:
"
                f"<code>{generated_wallet.public_key}</code>

"
                "<b>?? SAVE THIS NOW</b>
"
                "This will only be shown once.

"
                f"Seed phrase:
<code>{generated_wallet.seed_phrase}</code>

"
                f"Private key:
<tg-spoiler>{generated_wallet.private_key}</tg-spoiler>

"
                "We will NEVER ask for your seed phrase or private key."
            )

            keyboard = [[
                InlineKeyboardButton("? I saved my seed phrase", callback_data="onboard_confirm"),
                InlineKeyboardButton("? Cancel", callback_data="onboard_cancel"),
            ]]

            await update.message.reply_text(
                onboarding_text,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(keyboard),
                disable_web_page_preview=True,
            )

        except Exception as e:
            logger.error(f"Start command failed: {e}")
            await update.message.reply_text(f"? Error: {e}")

    # ==================== TOKEN ANALYSIS ====================

    async def cmd_analyze(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /analyze <token> command."""
        try:
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
                        InlineKeyboardButton("💰 Buy", callback_data=f"buy_{token_symbol}"),
                        InlineKeyboardButton("📊 Details", callback_data=f"analyze_details_{token_symbol}"),
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
            user_id = update.effective_user.id
            profile = self.user_manager.get_user_profile(user_id)

            if not profile:
                await update.message.reply_text("? Please register first with /start")
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
                keyboard.append([InlineKeyboardButton(label, callback_data=f"sell_pick:{idx}")])

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
            user_id = update.effective_user.id
            wallet = self.user_manager.get_primary_wallet(user_id)
            if not wallet:
                await update.message.reply_text("? No wallet found. Create one with /start")
                return

            trading = await self._get_public_trading()
            portfolio = await trading.get_portfolio(wallet.public_key)

            total_value = portfolio.sol_value_usd + sum(h.value_usd for h in portfolio.holdings)
            lines = [
                "<b>?? Wallet</b>",
                "",
                f"Address: <code>{wallet.public_key}</code>",
                f"SOL: {portfolio.sol_balance:.4f} (~${portfolio.sol_value_usd:,.2f})",
                "",
                "<b>Top Holdings</b>",
            ]

            if portfolio.holdings:
                for holding in portfolio.holdings[:10]:
                    lines.append(
                        f"? {holding.symbol}: {holding.amount:.4f} (~${holding.value_usd:,.2f})"
                    )
            else:
                lines.append("? No token holdings yet")

            lines.append("")
            lines.append(f"Total value: ${total_value:,.2f}")

            keyboard = [
                [
                    InlineKeyboardButton("?? Deposit", callback_data="wallet_deposit"),
                    InlineKeyboardButton("?? Withdraw", callback_data="wallet_withdraw"),
                ],
                [
                    InlineKeyboardButton("?? Export Key", callback_data="wallet_export"),
                    InlineKeyboardButton("?? Import Wallet", callback_data="wallet_import"),
                ],
            ]

            await update.message.reply_text(
                "
".join(lines),
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(keyboard),
                disable_web_page_preview=True,
            )

        except Exception as e:
            logger.error(f"Wallet command failed: {e}")
            await update.message.reply_text(f"? Error: {e}")

    async def cmd_send(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /send command - start send flow."""
        try:
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

            message = (
                "?? JARVIS SENTIMENT ANALYSIS
"
                "????????????????????????????
"
                f"Token: {resolved.symbol}
"
                "????????????????????????????

"
                f"Sentiment Score: {score}/100 ({sentiment_label})
"
                f"Confidence: {confidence_pct}%

"
                "?? V1 Early Access - Trade small amounts
"
                "????????????????????????????"
            )

            context.user_data["sentiment_token"] = {
                "mint": resolved.mint,
                "symbol": resolved.symbol,
            }

            keyboard = [
                [
                    InlineKeyboardButton("Buy 0.1 SOL", callback_data="sentiment_buy:0.1"),
                    InlineKeyboardButton("Buy 0.5 SOL", callback_data="sentiment_buy:0.5"),
                    InlineKeyboardButton("Buy 1 SOL", callback_data="sentiment_buy:1"),
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

            lines = [
                "?? JARVIS PICKS",
                "????????????????????????????",
                f"Updated: {datetime.utcnow().strftime('%H:%M UTC')}",
                "????????????????????????????",
                "",
            ]

            tradeable = []
            trading = await self._get_public_trading()

            for i, pick in enumerate(picks_data[:5]):
                symbol = pick.get("symbol", "?")
                conviction = pick.get("conviction", 0)
                reasoning = (pick.get("reasoning") or "").strip()
                lines.append(f"#{i+1} {symbol} | Conviction: {conviction}/100")
                if reasoning:
                    lines.append(f"  {reasoning}")
                lines.append("")

                mint = pick.get("contract") or ""
                if mint and trading.validate_address(mint):
                    tradeable.append({"symbol": symbol, "mint": mint})

            await update.message.reply_text("
".join(lines))

            if tradeable:
                context.user_data["picks_tokens"] = tradeable
                for idx, pick in enumerate(tradeable[:3]):
                    buttons = [
                        [
                            InlineKeyboardButton("Buy 0.1 SOL", callback_data=f"pick_buy:{idx}:0.1"),
                            InlineKeyboardButton("Buy 0.5 SOL", callback_data=f"pick_buy:{idx}:0.5"),
                            InlineKeyboardButton("Buy 1 SOL", callback_data=f"pick_buy:{idx}:1"),
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
                InlineKeyboardButton("📊 Risk Level", callback_data="settings_risk"),
                InlineKeyboardButton("💰 Limits", callback_data="settings_limits"),
            ], [
                InlineKeyboardButton("🔒 Safety", callback_data="settings_safety"),
                InlineKeyboardButton("🤖 Learning", callback_data="settings_learning"),
            ]]

            reply_markup = InlineKeyboardMarkup(keyboard)

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

        data = query.data or ""
        await query.answer()

        if data == "ui_test_ping":
            await query.edit_message_text("UI callback OK.")
            return

        if data == "demo_exit":
            await query.edit_message_text("Demo mode canceled.")
            return

        if data == "demo_accept":
            context.user_data["demo_ack"] = True
            await query.edit_message_text("Demo mode enabled.")
            await self._show_main_menu(query.message.chat_id, context)
            return

        if data == "cancel":
            await query.edit_message_text("Canceled.")
            return

        if data.startswith("buy_"):
            token_symbol = data.split("_", 1)[1]
            await query.edit_message_text(
                f"Use /buy {token_symbol} <amount> to place an order."
            )
            return

        if data.startswith("confirm_buy_"):
            if not self.trading_engine:
                await query.edit_message_text("Trading engine not available.")
                return
            await query.edit_message_text("Trade execution not wired yet.")
            return

        if data in {
            "create_wallet",
            "import_wallet",
            "export_wallet",
            "settings_risk",
            "settings_limits",
            "settings_safety",
            "settings_learning",
        }:
            await query.edit_message_text("This action is not wired yet.")
            return

        if data == "menu_picks":
            await query.edit_message_text("Use /picks to view Jarvis Picks.")
            return

        if data == "menu_sentiment":
            await query.edit_message_text("Use /sentiment <token> to view sentiment.")
            return

        if data == "menu_buy":
            await query.edit_message_text("Use /buy <token> <amount> to place a buy.")
            return

        if data == "menu_sell":
            await query.edit_message_text("Use /sell to view positions.")
            return

        if data == "menu_wallet":
            await query.edit_message_text("Use /wallets to manage wallets.")
            return

        if data == "menu_settings":
            await query.edit_message_text("Use /settings to adjust preferences.")
            return

        await query.edit_message_text("Action not supported yet.")
