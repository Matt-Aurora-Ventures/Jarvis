"""
Treasury Bot Manager - Integrated Dashboard, Alerts, and Market Intelligence

Complete Treasury Bot system with all services unified:
- Premium dashboard with real-time metrics
- Advanced charting and visualization
- Real-time alerts and monitoring
- Market intelligence and analysis
- Professional help system
- Admin controls and reporting

This is the main entry point for Treasury Bot functionality.
"""

import asyncio
import logging
from typing import List, Optional
from datetime import datetime

from telegram.ext import Application, ContextTypes
from telegram.constants import ParseMode

from bots.treasury.trading import TradingEngine
from tg_bot.services.treasury_bot import TreasuryBot
from tg_bot.services.treasury_dashboard import TreasuryDashboard
from tg_bot.services.chart_generator import ChartGenerator
from tg_bot.services.chart_integration import ChartIntegration
from tg_bot.services.alert_system import AlertSystem
from tg_bot.services.market_intelligence import MarketIntelligence
from tg_bot.services.help_reference import HelpReference
from tg_bot.handlers.treasury_handler import register_treasury_handlers

logger = logging.getLogger(__name__)


class TreasuryBotManager:
    """
    Unified Treasury Bot Manager

    Integrates all Treasury Bot services:
    - Dashboard and UI
    - Charts and visualization
    - Alerts and monitoring
    - Market intelligence
    - Help and support
    """

    def __init__(
        self,
        bot_token: str,
        trading_engine: TradingEngine,
        admin_ids: List[int],
    ):
        """
        Initialize Treasury Bot Manager.

        Args:
            bot_token: Telegram bot token
            trading_engine: TradingEngine instance
            admin_ids: List of admin user IDs
        """
        self.bot_token = bot_token
        self.engine = trading_engine
        self.admin_ids = admin_ids

        # Initialize services
        self.dashboard = TreasuryDashboard(trading_engine)
        self.chart_gen = ChartGenerator()
        self.chart_integration = ChartIntegration(trading_engine, self.dashboard)
        self.alerts = AlertSystem(trading_engine)
        self.alerts.set_admin_ids(admin_ids)
        self.market_intel = MarketIntelligence()
        self.help_ref = HelpReference()

        # Telegram application
        self.app: Optional[Application] = None
        self.treasury_bot: Optional[TreasuryBot] = None

        # Monitoring tasks
        self._monitoring_task: Optional[asyncio.Task] = None
        self._running = False

        logger.info(f"TreasuryBotManager initialized for {len(admin_ids)} admins")

    # ==================== INITIALIZATION ====================

    async def initialize(self) -> bool:
        """
        Initialize and start the Treasury Bot.

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("Initializing Treasury Bot...")

            # Create Telegram application
            self.app = Application.builder().token(self.bot_token).build()

            # Register all handlers
            self.treasury_bot = register_treasury_handlers(
                app=self.app,
                trading_engine=self.engine,
                admin_ids=self.admin_ids,
                bot_token=self.bot_token,
            )

            # Initialize application
            await self.app.initialize()
            await self.app.start()

            logger.info("Treasury Bot initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Treasury Bot: {e}")
            return False

    async def start_polling(self) -> bool:
        """
        Start Telegram polling.

        Returns:
            True if successful
        """
        try:
            if not self.app or not self.app.updater:
                logger.error("Application not initialized")
                return False

            await self.app.updater.start_polling(drop_pending_updates=True)
            logger.info("Treasury Bot polling started")

            # Start background monitoring
            self._start_background_tasks()

            return True

        except Exception as e:
            logger.error(f"Failed to start polling: {e}")
            return False

    # ==================== BACKGROUND MONITORING ====================

    def _start_background_tasks(self):
        """Start background monitoring tasks."""
        if self._running:
            logger.warning("Background tasks already running")
            return

        self._running = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Background monitoring tasks started")

    async def _monitoring_loop(self):
        """Main background monitoring loop."""
        logger.info("Treasury Bot monitoring loop started")

        while self._running:
            try:
                # Check for alerts
                if self.app and self.app.bot:
                    await self.alerts.check_price_alerts(ContextTypes.DEFAULT_TYPE())
                    await self.alerts.check_profit_alerts(ContextTypes.DEFAULT_TYPE())
                    await self.alerts.check_stop_loss_alerts(ContextTypes.DEFAULT_TYPE())
                    await self.alerts.check_risk_alerts(ContextTypes.DEFAULT_TYPE())

                # Check every 10 seconds
                await asyncio.sleep(10)

            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")
                await asyncio.sleep(10)

    # ==================== COMMAND HANDLERS ====================

    async def handle_help_command(self, update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /treasury_help command with full reference."""
        help_text = self.help_ref.get_full_commands()

        await update.message.reply_text(
            help_text,
            parse_mode=ParseMode.HTML
        )

    async def handle_quick_start(self, update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /quick_start command."""
        quick_start = self.help_ref.get_quick_start()

        await update.message.reply_text(
            quick_start,
            parse_mode=ParseMode.HTML
        )

    async def handle_market_overview(self, update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /market_overview command."""
        market_msg = self.market_intel.build_market_overview()

        await update.message.reply_text(
            market_msg,
            parse_mode=ParseMode.HTML
        )

    async def handle_sentiment(self, update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /market_sentiment command."""
        sentiment_msg = self.market_intel.build_sentiment_analysis()

        await update.message.reply_text(
            sentiment_msg,
            parse_mode=ParseMode.HTML
        )

    async def handle_liquidations(self, update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /market_liquidations command."""
        liq_msg = self.market_intel.build_liquidation_heatmap()

        await update.message.reply_text(
            liq_msg,
            parse_mode=ParseMode.HTML
        )

    async def handle_volume(self, update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /market_volume command."""
        volume_msg = self.market_intel.build_volume_analysis()

        await update.message.reply_text(
            volume_msg,
            parse_mode=ParseMode.HTML
        )

    async def handle_trending(self, update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /market_trending command."""
        trending_msg = self.market_intel.build_trending_tokens()

        await update.message.reply_text(
            trending_msg,
            parse_mode=ParseMode.HTML
        )

    async def handle_macro(self, update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /market_macro command."""
        macro_msg = self.market_intel.build_macro_indicators()

        await update.message.reply_text(
            macro_msg,
            parse_mode=ParseMode.HTML
        )

    # ==================== SHUTDOWN ====================

    async def shutdown(self):
        """Gracefully shutdown Treasury Bot."""
        logger.info("Shutting down Treasury Bot...")

        self._running = False

        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

        if self.app and self.app.updater:
            await self.app.updater.stop()

        if self.app:
            await self.app.stop()
            await self.app.shutdown()

        logger.info("Treasury Bot shutdown complete")

    # ==================== STATUS & REPORTING ====================

    def get_status(self) -> str:
        """Get Treasury Bot status."""
        positions = self.engine.get_open_positions()
        balance = self.engine.get_balance() if hasattr(self.engine, 'get_balance') else {'total': 0}

        status = f"""
<b>Treasury Bot Status</b>

<b>System:</b>
  Running: {'✅ Yes' if self._running else '❌ No'}
  Polling: {'✅ Yes' if self.app and self.app.updater else '❌ No'}
  Last Check: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}

<b>Trading:</b>
  Mode: {'🟢 LIVE' if not self.engine.dry_run else '🟡 DRY RUN'}
  Positions: {len(positions)}
  Balance: ${balance.get('total', 0):,.2f}
  Risk Level: {self.engine.risk_level.value if hasattr(self.engine, 'risk_level') else 'N/A'}

<b>Services:</b>
  Dashboard: ✅
  Charts: ✅
  Alerts: ✅ ({self.alerts.ALERT_COOLDOWN_SECONDS}s cooldown)
  Market Intel: ✅
  Help: ✅

<b>Admins:</b>
  {len(self.admin_ids)} authorized users
"""
        return status

    # ==================== UTILITY METHODS ====================

    def register_market_commands(self, app: Application):
        """Register all market intelligence commands."""
        from telegram.ext import CommandHandler

        app.add_handler(CommandHandler("market_overview", self.handle_market_overview))
        app.add_handler(CommandHandler("market_sentiment", self.handle_sentiment))
        app.add_handler(CommandHandler("market_liquidations", self.handle_liquidations))
        app.add_handler(CommandHandler("market_volume", self.handle_volume))
        app.add_handler(CommandHandler("market_trending", self.handle_trending))
        app.add_handler(CommandHandler("market_macro", self.handle_macro))

        logger.info("Market commands registered")

    def register_help_commands(self, app: Application):
        """Register help commands."""
        from telegram.ext import CommandHandler

        app.add_handler(CommandHandler("quick_start", self.handle_quick_start))
        app.add_handler(CommandHandler("treasury_help", self.handle_help_command))

        logger.info("Help commands registered")
