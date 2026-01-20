"""
Public Trading Bot - Supervisor Integration

Registers the public trading bot as a managed component of the Jarvis supervisor.
This bot provides autonomous trading capabilities for all users.

Features:
- User registration and account management
- Wallet generation and encryption
- Token analysis and recommendations
- Adaptive trading algorithms with learning
- Fee distribution and transparency
- Real-time Telegram interface
- Complete audit trail

Architecture:
- Public Bot Handler: Telegram command interface
- Market Data Service: Real-time price aggregation
- Token Analyzer: Risk assessment and recommendations
- Adaptive Algorithm: Learning-based signal generation
- Fee Distribution: Transparent revenue sharing
- Wallet Service: Secure key management
"""

import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass

from tg_bot.public_trading_bot_integration import PublicTradingBotIntegration

logger = logging.getLogger(__name__)


@dataclass
class PublicBotConfig:
    """Configuration for public trading bot."""
    enabled: bool = True
    telegram_token: str = ""
    scan_interval_seconds: int = 60
    max_concurrent_users: int = 1000
    enable_live_trading: bool = False
    require_confirmation: bool = True
    min_confidence_threshold: float = 65.0
    max_daily_loss_per_user: float = 1000.0


class PublicTradingBotSupervisor:
    """
    Supervisor component for public trading bot.

    Manages:
    - Bot initialization and lifecycle
    - Component startup/shutdown
    - Health monitoring
    - Error recovery
    - Performance tracking
    """

    def __init__(self, config: Optional[PublicBotConfig] = None):
        """Initialize supervisor."""
        self.config = config or PublicBotConfig()
        self.bot: Optional[PublicTradingBotIntegration] = None
        self.running = False
        self.start_time: Optional[datetime] = None
        self.stats = {
            "messages_processed": 0,
            "users_active": 0,
            "trades_executed": 0,
            "fees_collected": 0.0,
            "errors": 0,
        }

    async def initialize(self) -> bool:
        """Initialize bot and all components."""
        try:
            logger.info("Initializing Public Trading Bot...")

            if not self.config.enabled:
                logger.info("Public Trading Bot is disabled (enable=false)")
                return False

            if not self.config.telegram_token:
                logger.error("Telegram token not configured")
                return False

            # Initialize bot integration
            self.bot = PublicTradingBotIntegration(
                bot_token=self.config.telegram_token,
                trading_engine=None,
                enable_live_trading=self.config.enable_live_trading,
            )

            await self.bot.initialize()

            self.running = True
            self.start_time = datetime.utcnow()

            logger.info("✓ Public Trading Bot initialized successfully")
            logger.info(f"  Config:")
            logger.info(f"    - Live trading: {self.config.enable_live_trading}")
            logger.info(f"    - Requires confirmation: {self.config.require_confirmation}")
            logger.info(f"    - Min confidence: {self.config.min_confidence_threshold}%")
            logger.info(f"    - Max daily loss: ${self.config.max_daily_loss_per_user}")

            return True

        except Exception as e:
            logger.error(f"Failed to initialize Public Trading Bot: {e}", exc_info=True)
            self.running = False
            return False

    async def start(self):
        """Start the bot polling."""
        if not self.running:
            logger.error("Cannot start bot - not initialized")
            return

        try:
            logger.info("Starting Public Trading Bot polling...")
            await self.bot.start_polling()
        except Exception as e:
            logger.error(f"Bot polling failed: {e}", exc_info=True)
            self.running = False

    async def shutdown(self):
        """Gracefully shutdown bot."""
        try:
            logger.info("Shutting down Public Trading Bot...")

            if self.bot:
                await self.bot.shutdown()

            self.running = False
            logger.info("✓ Public Trading Bot shutdown complete")

        except Exception as e:
            logger.error(f"Shutdown error: {e}", exc_info=True)

    def get_health(self) -> Dict[str, Any]:
        """Get bot health status."""
        return {
            "name": "public_trading_bot",
            "enabled": self.config.enabled,
            "running": self.running,
            "uptime_seconds": (datetime.utcnow() - self.start_time).total_seconds()
            if self.start_time else 0,
            "stats": self.stats,
            "config": {
                "live_trading": self.config.enable_live_trading,
                "requires_confirmation": self.config.require_confirmation,
                "min_confidence": self.config.min_confidence_threshold,
                "max_daily_loss": self.config.max_daily_loss_per_user,
            },
        }

    async def handle_command(self, command: str, args: Dict[str, Any]) -> Any:
        """Handle administrative commands."""
        try:
            if command == "status":
                return self.get_health()

            elif command == "stats":
                return self.stats

            elif command == "set_live_trading":
                enabled = args.get("enabled", False)
                self.config.enable_live_trading = enabled
                logger.info(f"Live trading set to: {enabled}")
                return {"status": "ok", "live_trading": enabled}

            elif command == "set_confirmation":
                enabled = args.get("enabled", True)
                self.config.require_confirmation = enabled
                logger.info(f"Confirmation requirement set to: {enabled}")
                return {"status": "ok", "confirmation_required": enabled}

            else:
                return {"error": f"Unknown command: {command}"}

        except Exception as e:
            logger.error(f"Command error: {e}")
            return {"error": str(e)}


# Singleton instance
_bot_supervisor: Optional[PublicTradingBotSupervisor] = None


async def get_public_bot_supervisor() -> PublicTradingBotSupervisor:
    """Get or create public bot supervisor."""
    global _bot_supervisor
    if _bot_supervisor is None:
        _bot_supervisor = PublicTradingBotSupervisor()
    return _bot_supervisor


async def initialize_public_bot_supervisor(config: Optional[PublicBotConfig] = None) -> bool:
    """Initialize the public bot supervisor."""
    supervisor = await get_public_bot_supervisor()

    if config:
        supervisor.config = config

    return await supervisor.initialize()


async def shutdown_public_bot_supervisor():
    """Shutdown the public bot supervisor."""
    global _bot_supervisor
    if _bot_supervisor:
        await _bot_supervisor.shutdown()
        _bot_supervisor = None
