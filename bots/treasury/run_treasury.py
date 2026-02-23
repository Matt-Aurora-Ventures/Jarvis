"""
Jarvis Treasury Bot Runner
Main entry point for the trading system
"""

import os
import sys
import asyncio
import logging
import json
import base64
from pathlib import Path
from dotenv import load_dotenv

from core.logging_utils import configure_component_logger

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from bots.treasury.wallet import SecureWallet, WalletManager, WalletInfo
from bots.treasury.jupiter import JupiterClient
from bots.treasury.trading import TradingEngine, RiskLevel, _SimpleWallet
from bots.treasury.telegram_ui import TradingUI

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
configure_component_logger("bots.treasury", "treasury_bot")


class TreasuryBot:
    """
    Main Treasury Bot orchestrator.

    Coordinates wallet, trading engine, and Telegram UI.
    """

    def __init__(self):
        self.wallet = None  # Can be SecureWallet or _SimpleWallet
        self.jupiter: JupiterClient = None
        self.engine: TradingEngine = None
        self.ui: TradingUI = None
        self._running = False

    def _load_encrypted_keypair(self, keypair_path: Path, password: str):
        """Load and decrypt keypair from treasury_keypair.json."""
        def pad_base64(s):
            """Add padding to base64 string if needed."""
            return s + '=' * (4 - len(s) % 4) if len(s) % 4 else s

        try:
            with open(keypair_path) as f:
                data = json.load(f)

            if 'encrypted_key' in data and 'salt' in data and 'nonce' in data:
                if not password:
                    logger.warning("No password provided for keypair decryption")
                    return None
                salt = base64.b64decode(pad_base64(data['salt']))
                nonce = base64.b64decode(pad_base64(data['nonce']))
                encrypted_key = base64.b64decode(pad_base64(data['encrypted_key']))

                # Try PyNaCl decryption
                try:
                    import nacl.secret
                    import nacl.pwhash

                    key = nacl.pwhash.argon2id.kdf(
                        nacl.secret.SecretBox.KEY_SIZE,
                        password.encode(),
                        salt,
                        opslimit=nacl.pwhash.argon2id.OPSLIMIT_MODERATE,
                        memlimit=nacl.pwhash.argon2id.MEMLIMIT_MODERATE,
                    )

                    box = nacl.secret.SecretBox(key)
                    decrypted = box.decrypt(encrypted_key, nonce)

                    from solders.keypair import Keypair
                    return Keypair.from_bytes(decrypted)

                except ImportError:
                    logger.warning("PyNaCl not installed")

            elif isinstance(data, list):
                from solders.keypair import Keypair
                return Keypair.from_bytes(bytes(data))

        except Exception as e:
            logger.error(f"Failed to load keypair: {e}")

        return None

    async def initialize(self):
        """Initialize all components."""
        # Load environment
        env_path = Path(__file__).parent.parent.parent / 'tg_bot' / '.env'
        load_dotenv(env_path)

        # Get configuration - MUST have unique token to avoid polling conflicts!
        bot_token = os.environ.get('TREASURY_BOT_TOKEN') or os.environ.get('TREASURY_BOT_TELEGRAM_TOKEN')

        if not bot_token:
            logger.error(
                "\n" + "="*80 + "\n"
                "CRITICAL ERROR: TREASURY_BOT_TOKEN not set!\n"
                "="*80 + "\n"
                "Treasury bot MUST have its own unique Telegram bot token.\n"
                "DO NOT share TELEGRAM_BOT_TOKEN - this causes polling conflicts!\n"
                "\n"
                "Exit code 4294967295 = Telegram polling conflict = multiple bots using same token\n"
                "\n"
                "TO FIX:\n"
                "1. Open Telegram and search for @BotFather\n"
                "2. Send: /newbot\n"
                "3. Name: 'JARVIS Treasury Bot'\n"
                "4. Username: jarvis_treasury_bot (must end in 'bot')\n"
                "5. Copy the token @BotFather sends you\n"
                "6. Add to lifeos/config/.env: TREASURY_BOT_TOKEN=<your_token>\n"
                "7. Restart supervisor: python bots/supervisor.py\n"
                "\n"
                "See: TELEGRAM_BOT_TOKEN_GENERATION_GUIDE.md\n"
                "="*80 + "\n"
            )
            raise ValueError("TREASURY_BOT_TOKEN not set - polling conflict will occur!")

        logger.info(f"Using unique treasury bot token (TREASURY_BOT_TOKEN)")
        admin_ids_str = os.environ.get('TREASURY_ADMIN_IDS', '')
        wallet_password = os.environ.get('JARVIS_WALLET_PASSWORD')
        rpc_url = os.environ.get('SOLANA_RPC_URL', 'https://api.mainnet-beta.solana.com')

        # Parse admin IDs
        admin_ids = []
        if admin_ids_str:
            admin_ids = [int(x.strip()) for x in admin_ids_str.split(',') if x.strip() and x.strip().lstrip('-').isdigit()]

        logger.info(f"Initializing Treasury Bot with {len(admin_ids)} admins")

        # Try to load keypair from data/treasury_keypair.json first
        env_wallet_path = os.environ.get('TREASURY_WALLET_PATH', '').strip()
        keypair_path = Path(env_wallet_path) if env_wallet_path else Path(__file__).parent.parent.parent / 'data' / 'treasury_keypair.json'
        treasury_address = None

        if keypair_path.exists():
            try:
                keypair = self._load_encrypted_keypair(keypair_path, wallet_password)
                if keypair:
                    treasury_address = str(keypair.pubkey())
                    logger.info(f"Loaded treasury keypair: {treasury_address[:8]}...")
                    self.wallet = _SimpleWallet(keypair, treasury_address)
            except Exception as e:
                logger.warning(f"Failed to load keypair: {e}")

        # Fallback to SecureWallet
        if not self.wallet:
            if not wallet_password:
                raise ValueError("JARVIS_WALLET_PASSWORD not set")

            self.wallet = SecureWallet(wallet_password)
            treasury = self.wallet.get_treasury()
            if not treasury:
                logger.info("Creating new treasury wallet...")
                treasury = self.wallet.create_wallet(label="Jarvis Treasury", is_treasury=True)
                logger.info(f"Treasury wallet created: {treasury.address}")
            else:
                treasury_address = treasury.address
                logger.info(f"Using existing treasury: {treasury.address}")

        # Initialize Jupiter client
        self.jupiter = JupiterClient(rpc_url)

        # Initialize trading engine
        # Check env for live mode override
        live_mode = os.environ.get('TREASURY_LIVE_MODE', '').lower() == 'true'

        self.engine = TradingEngine(
            wallet=self.wallet,
            jupiter=self.jupiter,
            admin_user_ids=admin_ids,
            risk_level=RiskLevel.MODERATE,
            max_positions=50,
            dry_run=not live_mode  # Live mode if TREASURY_LIVE_MODE=true
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
