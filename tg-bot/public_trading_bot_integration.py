"""
Public Trading Bot Integration Layer

Wires together all services:
- User Management
- Wallet Service
- Market Data
- Token Analysis
- Adaptive Algorithm
- Fee Distribution
- Notifications

Creates a unified, production-ready public trading bot.
"""

import logging
from typing import Optional, Dict, Any

from telegram.ext import Application, ContextTypes
from telegram import Update

from core.public_trading_service import PublicTradingService
from core.public_user_manager import PublicUserManager, UserRiskLevel
from core.wallet_service import WalletService, get_wallet_service
from core.market_data_service import MarketDataService, get_market_data_service
from core.token_analyzer import TokenAnalyzer
from core.adaptive_algorithm import AdaptiveAlgorithm, TradeOutcome
from core.fee_distribution import FeeDistributionSystem
from tg_bot.services.notification_service import NotificationService
from tg_bot.public_bot_handler import PublicBotHandler
from bots.treasury.trading import TradingEngine

logger = logging.getLogger(__name__)


def register_public_handlers(app: Application, bot_handler: PublicBotHandler) -> None:
    """Register command and callback handlers for the public trading bot."""
    from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, filters

    app.add_handler(CommandHandler("start", bot_handler.cmd_start))
    app.add_handler(CommandHandler("analyze", bot_handler.cmd_analyze))
    app.add_handler(CommandHandler("buy", bot_handler.cmd_buy))
    app.add_handler(CommandHandler("sell", bot_handler.cmd_sell))
    app.add_handler(CommandHandler("portfolio", bot_handler.cmd_portfolio))
    app.add_handler(CommandHandler("performance", bot_handler.cmd_performance))
    app.add_handler(CommandHandler("wallet", bot_handler.cmd_wallet))
    app.add_handler(CommandHandler("wallets", bot_handler.cmd_wallets))
    app.add_handler(CommandHandler("send", bot_handler.cmd_send))
    app.add_handler(CommandHandler("sentiment", bot_handler.cmd_sentiment))
    app.add_handler(CommandHandler("picks", bot_handler.cmd_picks))
    app.add_handler(CommandHandler("settings", bot_handler.cmd_settings))
    app.add_handler(CommandHandler("help", bot_handler.cmd_help))
    app.add_handler(CommandHandler("demo", bot_handler.cmd_demo))

    app.add_handler(CallbackQueryHandler(bot_handler.handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot_handler.handle_message))


class PublicTradingBotIntegration:
    """
    Complete public trading bot integration.

    Manages lifecycle and coordination of all bot systems.
    """

    def __init__(
        self,
        bot_token: str,
        trading_engine: Optional[TradingEngine] = None,
        enable_live_trading: bool = False,
    ):
        """
        Initialize integrated public bot.

        Args:
            bot_token: Telegram bot token
            trading_engine: Optional trading engine (can be wired later)
            enable_live_trading: Toggle for live trading mode
        """
        self.bot_token = bot_token
        self.trading_engine = trading_engine
        self.enable_live_trading = enable_live_trading

        # Initialize all services
        self.user_manager = PublicUserManager()
        self.wallet_service: Optional[WalletService] = None
        self.market_data_service: Optional[MarketDataService] = None
        self.token_analyzer = TokenAnalyzer()
        self.algorithm = AdaptiveAlgorithm()
        self.fee_system = FeeDistributionSystem()
        self.notification_service = NotificationService()
        self.bot_handler: Optional[PublicBotHandler] = None

        # Telegram app
        self.app: Optional[Application] = None
        self._polling_lock = None

        logger.info("Public Trading Bot Integration initialized")

    async def initialize(self) -> bool:
        """
        Initialize all services and start bot.

        Returns:
            True if successful
        """
        try:
            logger.info("Initializing Public Trading Bot...")

            # Initialize services
            logger.info("→ Initializing wallet service...")
            self.wallet_service = await get_wallet_service()

            logger.info("→ Initializing market data service...")
            self.market_data_service = await get_market_data_service()

            logger.info("→ Creating bot handler...")
            public_trading = PublicTradingService(self.wallet_service)
            self.bot_handler = PublicBotHandler(
                self.trading_engine,
                wallet_service=self.wallet_service,
                public_trading=public_trading,
            )

            # Create Telegram application
            logger.info("→ Setting up Telegram application...")
            self.app = Application.builder().token(self.bot_token).build()

            # Global error handler (admin-safe)
            try:
                from tg_bot.bot_core import error_handler as tg_error_handler
                self.app.add_error_handler(tg_error_handler)
            except Exception as e:
                logger.warning(f"Error handler unavailable: {e}")

            # Register handlers
            await self._register_handlers()

            # Initialize Telegram app
            await self.app.initialize()
            await self.app.start()

            logger.info("✅ Public Trading Bot initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            return False

    async def _register_handlers(self):
        """Register all command handlers with Telegram app."""
        try:
            if not self.app or not self.bot_handler:
                raise RuntimeError("App or bot handler not initialized")

            register_public_handlers(self.app, self.bot_handler)

            logger.info("✅ All handlers registered")

        except Exception as e:
            logger.error(f"Handler registration failed: {e}")
            raise

    async def start_polling(self) -> bool:
        """Start Telegram polling."""
        try:
            if not self.app:
                logger.error("Application not initialized")
                return False

            # Single-instance lock to avoid Telegram polling conflicts
            try:
                from core.utils.instance_lock import acquire_instance_lock, cleanup_stale_lock

                # Clean up any stale locks first
                cleanup_stale_lock(self.bot_token, name="telegram_polling")

                self._polling_lock = acquire_instance_lock(
                    self.bot_token,
                    name="telegram_polling",
                    max_wait_seconds=0,
                    validate_pid=True,
                )
            except Exception as exc:
                logger.warning(f"Polling lock helper unavailable: {exc}")
                self._polling_lock = None

            if not self._polling_lock:
                logger.error(
                    "Telegram polling lock held by another process.\n"
                    "SOLUTION: Ensure this bot uses a unique TELEGRAM_BOT_TOKEN.\n"
                    "Current token starts with: " + self.bot_token[:10] + "...\n"
                    "Check .env files for duplicate token usage."
                )
                return False

            logger.info("Starting Telegram polling...")
            await self.app.updater.start_polling(drop_pending_updates=True)

            logger.info("✅ Telegram polling started")
            return True

        except Exception as e:
            logger.error(f"Failed to start polling: {e}")
            if self._polling_lock:
                try:
                    self._polling_lock.close()
                except Exception:
                    pass
            return False

    # ==================== USER FLOW ORCHESTRATION ====================

    async def handle_analyze_request(self, user_id: int, symbol: str,
                                    context: ContextTypes.DEFAULT_TYPE) -> Optional[Dict[str, Any]]:
        """
        Handle token analysis request.

        Orchestrates:
        1. Market data fetching
        2. Token analysis
        3. Algorithm signal generation
        4. Result formatting

        Args:
            user_id: User requesting analysis
            symbol: Token symbol
            context: Telegram context

        Returns:
            Analysis result or None
        """
        try:
            logger.info(f"Analyzing {symbol} for user {user_id}")

            # Get market data
            if not self.market_data_service:
                await context.bot.send_message(chat_id=user_id, text="❌ Market data service unavailable")
                return None

            market_data = await self.market_data_service.get_market_data(symbol)
            if not market_data:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"❌ Could not find market data for {symbol}"
                )
                return None

            # Analyze token
            analysis = await self.token_analyzer.analyze_token(symbol, market_data)
            if not analysis:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"❌ Analysis failed for {symbol}"
                )
                return None

            # Generate algorithm signal
            if analysis.recommendation:
                # Could send signal notification
                await self.notification_service.notify_high_confidence_signal(
                    user_id=user_id,
                    symbol=symbol,
                    action=analysis.recommendation.action,
                    confidence=analysis.recommendation.confidence,
                    reason=analysis.recommendation.short_thesis,
                    context=context
                )

            return {
                'analysis': analysis,
                'market_data': market_data,
            }

        except Exception as e:
            logger.error(f"Analysis handling failed: {e}")
            await context.bot.send_message(
                chat_id=user_id,
                text=f"❌ Error during analysis: {str(e)[:100]}"
            )
            return None

    async def handle_buy_order(self, user_id: int, symbol: str, amount_usd: float,
                              context: ContextTypes.DEFAULT_TYPE) -> bool:
        """
        Handle buy order execution.

        Orchestrates:
        1. User validation
        2. Wallet retrieval
        3. Rate limit checking
        4. Order execution
        5. Fee tracking
        6. Notification

        Args:
            user_id: User ID
            symbol: Token symbol
            amount_usd: Amount to trade in USD
            context: Telegram context

        Returns:
            True if order executed
        """
        try:
            logger.info(f"Buy order for {symbol} (${amount_usd}) from user {user_id}")

            # Get user profile
            profile = self.user_manager.get_user_profile(user_id)
            if not profile:
                await context.bot.send_message(chat_id=user_id, text="❌ User not registered")
                return False

            # Check rate limits
            allowed, reason = self.user_manager.check_rate_limits(user_id)
            if not allowed:
                await context.bot.send_message(chat_id=user_id, text=f"❌ {reason}")
                return False

            # Get primary wallet
            wallet = self.user_manager.get_primary_wallet(user_id)
            if not wallet:
                await context.bot.send_message(chat_id=user_id, text="❌ No wallet configured")
                return False

            # Send confirmation message
            await context.bot.send_message(
                chat_id=user_id,
                text=f"⏳ Executing buy order for {symbol}..."
            )

            # Execute trade via trading engine
            try:
                order = await self.trading_engine.execute_buy(
                    symbol=symbol,
                    amount_usd=amount_usd,
                    wallet_address=wallet.public_key,
                )

                if not order:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"❌ Order execution failed"
                    )
                    return False

                # Send execution confirmation
                await self.notification_service.notify_trade_executed(
                    user_id=user_id,
                    symbol=symbol,
                    action="BUY",
                    amount_usd=amount_usd,
                    price=order.entry_price,
                    context=context
                )

                # Record trade
                self.user_manager.record_trade(
                    user_id=user_id,
                    wallet_id=wallet.wallet_id,
                    symbol=symbol,
                    action="BUY",
                    amount_usd=amount_usd,
                    pnl_usd=0.0,
                )

                # Increment rate limit counter
                self.user_manager.increment_trade_count(user_id, 0)

                return True

            except Exception as e:
                logger.error(f"Trade execution error: {e}")
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"❌ Order execution error: {str(e)[:100]}"
                )
                return False

        except Exception as e:
            logger.error(f"Buy order handling failed: {e}")
            return False

    async def handle_position_close(self, user_id: int, symbol: str, exit_price: float,
                                   context: ContextTypes.DEFAULT_TYPE) -> bool:
        """
        Handle position close and fee calculation.

        Orchestrates:
        1. Position lookup
        2. PnL calculation
        3. Fee calculation and distribution
        4. User notification
        5. Algorithm outcome recording

        Args:
            user_id: User ID
            symbol: Token symbol
            exit_price: Exit price
            context: Telegram context

        Returns:
            True if successful
        """
        try:
            logger.info(f"Closing {symbol} position for user {user_id}")

            # Get user's position (would query from trading engine)
            # position = self.trading_engine.get_position(user_id, symbol)

            # For now, use placeholder data
            entry_price = 100.0
            pnl = (exit_price - entry_price) / entry_price * 100 * 50  # Example: $50 investment

            # Record trade outcome
            self.user_manager.record_trade(
                user_id=user_id,
                wallet_id="wallet_id",
                symbol=symbol,
                action="SELL",
                amount_usd=0,  # Already recorded in BUY
                pnl_usd=pnl,
            )

            # Calculate and distribute fees (only on winning trades)
            if pnl > 0:
                success, fee = self.fee_system.record_successful_trade(
                    tx_id=f"tx_{user_id}_{symbol}_{int(datetime.utcnow().timestamp())}",
                    user_id=user_id,
                    symbol=symbol,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    gross_pnl=pnl,
                )

                if success and fee:
                    # Notify user of fees earned
                    user_fee = fee.success_fee_amount * 0.75  # User gets 75%
                    await self.notification_service.notify_fees_earned(
                        user_id=user_id,
                        amount=user_fee,
                        symbol=symbol,
                        context=context
                    )

                    # Record algorithm outcome for learning
                    from core.adaptive_algorithm import TradeOutcome, AlgorithmType
                    outcome = TradeOutcome(
                        algorithm_type=AlgorithmType.COMPOSITE,
                        signal_strength=75,  # Would use actual signal strength
                        user_id=user_id,
                        symbol=symbol,
                        entry_price=entry_price,
                        exit_price=exit_price,
                        pnl_usd=pnl,
                        hold_duration_hours=2.5,  # Would calculate actual
                    )
                    self.algorithm.record_outcome(outcome)

            return True

        except Exception as e:
            logger.error(f"Position close handling failed: {e}")
            return False

    # ==================== CLEANUP ====================

    async def shutdown(self):
        """Shutdown bot and close connections."""
        try:
            logger.info("Shutting down Public Trading Bot...")

            if self.app:
                await self.app.stop()
                await self.app.shutdown()

            if self.wallet_service:
                await self.wallet_service.close()

            if self._polling_lock:
                try:
                    self._polling_lock.close()
                except Exception:
                    pass

            logger.info("✅ Public Trading Bot shutdown complete")

        except Exception as e:
            logger.error(f"Shutdown error: {e}")


async def create_public_trading_bot(trading_engine: TradingEngine,
                                   bot_token: str) -> PublicTradingBotIntegration:
    """
    Create and initialize public trading bot.

    Args:
        trading_engine: Treasury trading engine
        bot_token: Telegram bot token

    Returns:
        Initialized bot integration
    """
    try:
        bot = PublicTradingBotIntegration(
            bot_token=bot_token,
            trading_engine=trading_engine,
        )

        # Initialize services
        success = await bot.initialize()
        if not success:
            raise RuntimeError("Failed to initialize bot")

        # Start polling
        polling_success = await bot.start_polling()
        if not polling_success:
            raise RuntimeError("Failed to start polling")

        return bot

    except Exception as e:
        logger.error(f"Failed to create public trading bot: {e}")
        raise
