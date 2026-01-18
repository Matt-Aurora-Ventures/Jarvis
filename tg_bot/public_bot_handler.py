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

import logging
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from core.public_user_manager import PublicUserManager, UserProfile, UserRiskLevel, Wallet
from core.adaptive_algorithm import AdaptiveAlgorithm, TradeOutcome
from core.token_analyzer import TokenAnalyzer
from bots.treasury.trading import TradingEngine

logger = logging.getLogger(__name__)


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

    def __init__(self, trading_engine: TradingEngine):
        """Initialize public bot handler."""
        self.trading_engine = trading_engine
        self.user_manager = PublicUserManager()
        self.algorithm = AdaptiveAlgorithm()
        self.token_analyzer = TokenAnalyzer()

    # ==================== START AND REGISTRATION ====================

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command - register or welcome back."""
        try:
            user_id = update.effective_user.id
            username = update.effective_user.username or update.effective_user.first_name

            # Check if user exists
            profile = self.user_manager.get_user_profile(user_id)

            if not profile:
                # New user - register
                success, profile = self.user_manager.register_user(user_id, username)
                if not success:
                    await update.message.reply_text(
                        "❌ Registration failed. Please try again."
                    )
                    return

                # Welcome message
                welcome_text = f"""
🎉 <b>Welcome to Jarvis Trading Bot!</b>

I'm your AI-powered token analyzer and trading assistant. Here's what I can do:

<b>📊 Analysis</b>
/analyze &lt;token&gt; - Deep analysis of any Solana token
    Example: /analyze SOL

<b>💰 Trading</b>
/buy &lt;token&gt; - Buy a token
/sell - Close positions
/portfolio - View your holdings
/performance - Your trading stats

<b>🔐 Wallets</b>
/wallets - Create, import, manage wallets
/export - Export wallet backup

<b>⚙️ Settings</b>
/settings - Adjust risk level and preferences
/help - Full command reference

<b>⚡ Tips</b>
• Start with conservative risk level
• Always set stop losses
• Never invest more than you can afford to lose
• Use /analyze to check tokens first

Ready? Try: /analyze BTC
"""

                await update.message.reply_text(
                    welcome_text,
                    parse_mode=ParseMode.HTML
                )
            else:
                # Returning user
                welcome_back = f"""
👋 Welcome back, {username}!

Your stats:
📈 Trades: {self.user_manager.get_user_stats(user_id).total_trades if self.user_manager.get_user_stats(user_id) else 0}
💵 P&L: ${self.user_manager.get_user_stats(user_id).total_pnl_usd:.2f if self.user_manager.get_user_stats(user_id) else 0}

What would you like to do?
/analyze - Analyze a token
/portfolio - View holdings
/help - Full commands
"""
                await update.message.reply_text(
                    welcome_back,
                    parse_mode=ParseMode.HTML
                )

        except Exception as e:
            logger.error(f"Start command failed: {e}")
            await update.message.reply_text(f"❌ Error: {e}")

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
        """Handle /buy <token> <amount_usd> command."""
        try:
            user_id = update.effective_user.id
            profile = self.user_manager.get_user_profile(user_id)

            if not profile:
                await update.message.reply_text(
                    "❌ Please register first with /start"
                )
                return

            # Check rate limits
            allowed, reason = self.user_manager.check_rate_limits(user_id)
            if not allowed:
                await update.message.reply_text(f"❌ {reason}")
                return

            if len(context.args) < 2:
                await update.message.reply_text(
                    "💰 Buy a token\n\n"
                    "Usage: /buy &lt;token&gt; &lt;amount_usd&gt;\n"
                    "Example: /buy SOL 50",
                    parse_mode=ParseMode.HTML
                )
                return

            token_symbol = context.args[0].upper()
            try:
                amount_usd = float(context.args[1])
            except ValueError:
                await update.message.reply_text(f"❌ Invalid amount: {context.args[1]}")
                return

            # Validate amount
            if amount_usd < 10:
                await update.message.reply_text("❌ Minimum trade size: $10")
                return

            if amount_usd > 10_000:
                await update.message.reply_text("❌ Maximum trade size: $10,000")
                return

            # Get user's primary wallet
            wallet = self.user_manager.get_primary_wallet(user_id)
            if not wallet:
                await update.message.reply_text(
                    "❌ No wallet found. Create one with /wallets"
                )
                return

            # Request confirmation
            confirm_text = f"""
💰 <b>Confirm Buy Order</b>

Token: {token_symbol}
Amount: ${amount_usd:.2f}
Wallet: {wallet.public_key[:10]}...

<b>Risk Level:</b> {profile.risk_level.name}
<b>Slippage:</b> 2%

<b>⚠️ Risks:</b>
• Market volatility
• Smart contract risk
• Impermanent loss

<i>Proceed?</i>
"""

            keyboard = [[
                InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_buy_{token_symbol}_{amount_usd}"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
            ]]

            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                confirm_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )

        except Exception as e:
            logger.error(f"Buy command failed: {e}")
            await update.message.reply_text(f"❌ Error: {e}")

    async def cmd_sell(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /sell command - list positions to sell."""
        try:
            user_id = update.effective_user.id

            # Get user's positions (from trading engine)
            positions = []  # Would fetch from trading engine in production

            if not positions:
                await update.message.reply_text(
                    "📊 No open positions to sell.\n\n"
                    "Use /buy to open a position."
                )
                return

            # Display positions with sell buttons
            text = "<b>📊 Your Positions</b>\n\n"
            for pos in positions:
                text += f"{pos['symbol']}: {pos['amount']:.4f} @ ${pos['entry']:.6f}\n"

            await update.message.reply_text(text, parse_mode=ParseMode.HTML)

        except Exception as e:
            logger.error(f"Sell command failed: {e}")
            await update.message.reply_text(f"❌ Error: {e}")

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

    # ==================== WALLET MANAGEMENT ====================

    async def cmd_wallets(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /wallets command - wallet management."""
        try:
            user_id = update.effective_user.id
            wallets = self.user_manager.get_user_wallets(user_id)

            if not wallets:
                wallet_text = """
🔐 <b>Wallet Management</b>

No wallets found. Create one:

<b>Create New Wallet</b>
The bot will generate a new Solana wallet for you.

<b>Import Existing Wallet</b>
Import a wallet using your seed phrase or private key.

What would you like to do?
"""

                keyboard = [[
                    InlineKeyboardButton("➕ Create New", callback_data="create_wallet"),
                    InlineKeyboardButton("📥 Import", callback_data="import_wallet"),
                ]]

                reply_markup = InlineKeyboardMarkup(keyboard)

                await update.message.reply_text(
                    wallet_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup
                )
            else:
                # Show existing wallets
                wallet_text = "<b>🔐 Your Wallets</b>\n\n"

                for i, wallet in enumerate(wallets):
                    primary = "👑 PRIMARY" if wallet.is_primary else ""
                    wallet_text += f"<b>Wallet {i+1}</b> {primary}\n"
                    wallet_text += f"Address: <code>{wallet.public_key}</code>\n"
                    wallet_text += f"Balance: {wallet.balance_sol:.4f} SOL\n\n"

                keyboard = [[
                    InlineKeyboardButton("➕ Add Wallet", callback_data="create_wallet"),
                    InlineKeyboardButton("📤 Export", callback_data="export_wallet"),
                ]]

                reply_markup = InlineKeyboardMarkup(keyboard)

                await update.message.reply_text(
                    wallet_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup
                )

        except Exception as e:
            logger.error(f"Wallets command failed: {e}")
            await update.message.reply_text(f"❌ Error: {e}")

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
<b>📚 Jarvis Trading Bot - Command Reference</b>

<b>Getting Started</b>
/start - Register and welcome
/help - This message

<b>📊 Analysis</b>
/analyze &lt;token&gt; - Deep dive token analysis
    Example: /analyze SOL
/sentiment &lt;token&gt; - Sentiment score only
/technicals &lt;token&gt; - Technical indicators

<b>💰 Trading</b>
/buy &lt;token&gt; &lt;amount&gt; - Buy token
    Example: /buy SOL 50
/sell - List positions to close
/portfolio - View holdings
/performance - Detailed stats

<b>🔐 Wallets</b>
/wallets - Manage wallets
/export - Backup wallet
/balance - SOL balance

<b>⚙️ Settings</b>
/settings - User preferences
/risk - Adjust risk level
/alerts - Notification settings

<b>📈 Learning</b>
/stats - Algorithm performance stats
/top_trades - Best performing trades
/losses - Learn from losses

<b>Tips & Safety</b>
✅ Always analyze before buying
✅ Use appropriate risk level
✅ Set stop losses
❌ Never invest more than you can lose
❌ Never share your seed phrase

Questions? Use /support
"""

            await update.message.reply_text(
                help_text,
                parse_mode=ParseMode.HTML
            )

        except Exception as e:
            logger.error(f"Help command failed: {e}")
            await update.message.reply_text(f"❌ Error: {e}")
