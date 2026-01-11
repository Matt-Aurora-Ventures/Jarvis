"""
Jarvis Treasury Bot Runner
Main entry point for the trading system
"""

import os
import sys
import asyncio
import logging
from pathlib import Path
from dotenv import load_dotenv

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from bots.treasury.wallet import SecureWallet, WalletManager
from bots.treasury.jupiter import JupiterClient
from bots.treasury.trading import TradingEngine, RiskLevel
from bots.treasury.telegram_ui import TradingUI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TreasuryBot:
    """
    Main Treasury Bot orchestrator.

    Coordinates wallet, trading engine, and Telegram UI.
    """

    def __init__(self):
        self.wallet: SecureWallet = None
        self.jupiter: JupiterClient = None
        self.engine: TradingEngine = None
        self.ui: TradingUI = None
        self._running = False

    async def initialize(self):
        """Initialize all components."""
        # Load environment
        env_path = Path(__file__).parent.parent.parent / 'tg_bot' / '.env'
        load_dotenv(env_path)

        # Get configuration
        bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        admin_ids_str = os.environ.get('TREASURY_ADMIN_IDS', '')
        wallet_password = os.environ.get('JARVIS_WALLET_PASSWORD')
        rpc_url = os.environ.get('SOLANA_RPC_URL', 'https://api.mainnet-beta.solana.com')

        if not bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN not set")

        if not wallet_password:
            raise ValueError("JARVIS_WALLET_PASSWORD not set")

        # Parse admin IDs
        admin_ids = []
        if admin_ids_str:
            admin_ids = [int(x.strip()) for x in admin_ids_str.split(',') if x.strip()]

        logger.info(f"Initializing Treasury Bot with {len(admin_ids)} admins")

        # Initialize wallet
        self.wallet = SecureWallet(wallet_password)

        # Check for existing treasury or create new
        treasury = self.wallet.get_treasury()
        if not treasury:
            logger.info("Creating new treasury wallet...")
            treasury = self.wallet.create_wallet(label="Jarvis Treasury", is_treasury=True)
            logger.info(f"Treasury wallet created: {treasury.address}")
        else:
            logger.info(f"Using existing treasury: {treasury.address}")

        # Initialize Jupiter client
        self.jupiter = JupiterClient(rpc_url)

        # Initialize trading engine
        self.engine = TradingEngine(
            wallet=self.wallet,
            jupiter=self.jupiter,
            admin_user_ids=admin_ids,
            risk_level=RiskLevel.MODERATE,
            max_positions=5,
            dry_run=True  # Start in dry run mode for safety
        )

        # Initialize limit order manager
        await self.engine.initialize_order_manager()

        # Initialize Telegram UI
        self.ui = TradingUI(
            bot_token=bot_token,
            trading_engine=self.engine,
            admin_ids=admin_ids
        )

        logger.info("Treasury Bot initialized successfully")
        logger.info(f"Mode: {'DRY RUN' if self.engine.dry_run else 'LIVE'}")

    async def start(self):
        """Start the treasury bot."""
        if self._running:
            return

        self._running = True

        try:
            # Start Telegram UI
            await self.ui.start()

            # Get treasury balance
            treasury = self.wallet.get_treasury()
            if treasury:
                sol, usd = await self.wallet.get_balance(treasury.address)
                logger.info(f"Treasury balance: {sol:.4f} SOL (${usd:.2f})")

            logger.info("Treasury Bot running...")

            # Keep running
            while self._running:
                await asyncio.sleep(1)

        except asyncio.CancelledError:
            logger.info("Treasury Bot cancelled")
        except Exception as e:
            logger.error(f"Treasury Bot error: {e}")
            raise
        finally:
            await self.shutdown()

    async def shutdown(self):
        """Shutdown the bot."""
        self._running = False

        logger.info("Shutting down Treasury Bot...")

        if self.ui:
            await self.ui.stop()

        if self.engine:
            await self.engine.shutdown()

        logger.info("Treasury Bot stopped")


async def main():
    """Main entry point."""
    bot = TreasuryBot()

    try:
        await bot.initialize()
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise
    finally:
        await bot.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
