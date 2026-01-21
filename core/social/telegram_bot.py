"""
JARVIS Telegram Prediction Bot

Public predictions and user copy trading system.
Copy trading is DISABLED until security audit complete.

Prompts #161-164: Telegram Bot, User Accounts, Key Manager, Copy Trading
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from enum import Enum
import json
import hashlib

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    """User risk level settings"""
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


class SubscriptionTier(str, Enum):
    """User subscription tiers"""
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    WHALE = "whale"


@dataclass
class UserAccount:
    """User account for predictions and copy trading"""
    telegram_id: int
    username: str
    wallet_address: str  # Their Jarvis custodial wallet
    encrypted_private_key: str  # Encrypted, NEVER stored plaintext
    balance_sol: float = 0.0
    is_copy_trading_enabled: bool = False  # DISABLED BY DEFAULT
    risk_level: RiskLevel = RiskLevel.CONSERVATIVE
    max_trade_size_pct: float = 0.10  # Max 10% of balance per trade
    subscription_tier: SubscriptionTier = SubscriptionTier.FREE
    created_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)
    total_trades: int = 0
    total_pnl_sol: float = 0.0

    def to_dict(self) -> Dict:
        """Convert to dictionary (excluding sensitive data)"""
        return {
            "telegram_id": self.telegram_id,
            "username": self.username,
            "wallet_address": self.wallet_address,
            "balance_sol": self.balance_sol,
            "is_copy_trading_enabled": self.is_copy_trading_enabled,
            "risk_level": self.risk_level.value,
            "max_trade_size_pct": self.max_trade_size_pct,
            "subscription_tier": self.subscription_tier.value,
            "created_at": self.created_at.isoformat(),
            "last_active": self.last_active.isoformat(),
            "total_trades": self.total_trades,
            "total_pnl_sol": self.total_pnl_sol
        }


@dataclass
class Position:
    """User trading position"""
    position_id: str
    user_id: int
    token_address: str
    token_symbol: str
    entry_price: float
    current_price: float
    amount: float
    value_sol: float
    pnl_pct: float
    opened_at: datetime = field(default_factory=datetime.now)


class SecureKeyManager:
    """
    Secure key management for user wallets

    CRITICAL: This must be audited before enabling trading
    """

    def __init__(self):
        self.enabled = True
        try:
            self.master_key = self._derive_master_key()
        except Exception as e:
            self.enabled = False
            self.master_key = None
            logger.error(f"Key manager disabled: {e}")

    def _derive_master_key(self) -> bytes:
        """Derive master encryption key"""
        try:
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            from cryptography.hazmat.primitives import hashes

            # Get from secure environment
            password = os.environ.get("JARVIS_MASTER_KEY")
            if not password:
                raise RuntimeError("JARVIS_MASTER_KEY not set")

            salt_value = os.environ.get("JARVIS_KEY_SALT")
            if not salt_value:
                raise RuntimeError("JARVIS_KEY_SALT not set")

            salt = salt_value.encode()

            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=480000,
            )

            return kdf.derive(password.encode())

        except ImportError:
            raise RuntimeError("cryptography not installed")

    def encrypt(self, data: bytes, context: str) -> str:
        """Encrypt sensitive data"""
        if not self.enabled or not self.master_key:
            raise RuntimeError("Key manager not configured")

        try:
            from cryptography.fernet import Fernet
            import base64

            # Derive context-specific key
            context_key = hashlib.sha256(
                self.master_key + context.encode()
            ).digest()

            fernet = Fernet(base64.urlsafe_b64encode(context_key))
            encrypted = fernet.encrypt(data)

            return base64.b64encode(encrypted).decode()

        except ImportError:
            logger.error("cryptography not installed")
            raise RuntimeError("Encryption not available")

    def decrypt(self, encrypted_data: str, context: str) -> bytes:
        """Decrypt sensitive data"""
        if not self.enabled or not self.master_key:
            raise RuntimeError("Key manager not configured")

        try:
            from cryptography.fernet import Fernet
            import base64

            # Derive context-specific key
            context_key = hashlib.sha256(
                self.master_key + context.encode()
            ).digest()

            fernet = Fernet(base64.urlsafe_b64encode(context_key))
            encrypted = base64.b64decode(encrypted_data)

            return fernet.decrypt(encrypted)

        except ImportError:
            logger.error("cryptography not installed")
            raise RuntimeError("Decryption not available")


class UserManager:
    """Manages user accounts and wallets"""

    def __init__(self, db_path: str = "data/telegram_users.json"):
        self.db_path = db_path
        self.key_manager = SecureKeyManager()
        self.users: Dict[int, UserAccount] = {}
        self._load_users()

    def _load_users(self):
        """Load users from database"""
        try:
            if os.path.exists(self.db_path):
                with open(self.db_path, "r") as f:
                    data = json.load(f)

                for user_data in data.get("users", []):
                    account = UserAccount(
                        telegram_id=user_data["telegram_id"],
                        username=user_data["username"],
                        wallet_address=user_data["wallet_address"],
                        encrypted_private_key=user_data["encrypted_private_key"],
                        balance_sol=user_data.get("balance_sol", 0.0),
                        is_copy_trading_enabled=False,  # Always disabled on load
                        risk_level=RiskLevel(user_data.get("risk_level", "conservative")),
                        max_trade_size_pct=user_data.get("max_trade_size_pct", 0.10),
                        subscription_tier=SubscriptionTier(user_data.get("subscription_tier", "free")),
                        created_at=datetime.fromisoformat(user_data["created_at"]),
                        last_active=datetime.fromisoformat(user_data.get("last_active", user_data["created_at"])),
                        total_trades=user_data.get("total_trades", 0),
                        total_pnl_sol=user_data.get("total_pnl_sol", 0.0)
                    )
                    self.users[account.telegram_id] = account

                logger.info(f"Loaded {len(self.users)} users")
        except Exception as e:
            logger.error(f"Failed to load users: {e}")

    def _save_users(self):
        """Save users to database"""
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

            data = {
                "users": [
                    {
                        **user.to_dict(),
                        "encrypted_private_key": user.encrypted_private_key
                    }
                    for user in self.users.values()
                ],
                "updated_at": datetime.now().isoformat()
            }

            with open(self.db_path, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save users: {e}")

    async def create_account(
        self,
        telegram_id: int,
        username: str
    ) -> UserAccount:
        """Create a new user account with custodial wallet"""
        if not self.key_manager.enabled:
            raise RuntimeError("Custodial wallet disabled (missing master key config)")

        try:
            from solders.keypair import Keypair
        except ImportError:
            raise RuntimeError("solders library required for wallet creation")

        keypair = Keypair()
        wallet_address = str(keypair.pubkey())
        key_bytes = bytes(keypair)
        encrypted_key = self.key_manager.encrypt(
            key_bytes,
            context=f"user_{telegram_id}",
        )

        account = UserAccount(
            telegram_id=telegram_id,
            username=username or f"user_{telegram_id}",
            wallet_address=wallet_address,
            encrypted_private_key=encrypted_key,
            balance_sol=0.0,
            is_copy_trading_enabled=False,
            risk_level=RiskLevel.CONSERVATIVE,
            max_trade_size_pct=0.10
        )

        self.users[telegram_id] = account
        self._save_users()

        del keypair
        del key_bytes

        logger.info(f"Created account for user {telegram_id}")
        return account

    async def get_account(self, telegram_id: int) -> Optional[UserAccount]:
        """Get user account by Telegram ID"""
        return self.users.get(telegram_id)

    async def update_account(self, account: UserAccount):
        """Update user account"""
        account.last_active = datetime.now()
        self.users[account.telegram_id] = account
        self._save_users()

    async def get_balance(self, wallet_address: str) -> float:
        """Get wallet balance from chain"""
        # Placeholder - would connect to Solana RPC
        return 0.0

    async def get_positions(self, wallet_address: str) -> List[Position]:
        """Get user's open positions"""
        # Placeholder - would fetch from database
        return []


class CopyTrader:
    """
    Executes copy trades for subscribed users

    DISABLED UNTIL SECURITY AUDIT COMPLETE
    """

    ENABLED = False  # MUST BE FALSE UNTIL AUDIT

    def __init__(self, bags_client: Any = None):
        self.bags_client = bags_client
        self.key_manager = SecureKeyManager()

    async def execute_copy_trades(
        self,
        predictions: List[Any],
        subscribers: List[UserAccount]
    ):
        """Execute trades for all subscribers based on predictions"""

        if not self.ENABLED:
            logger.warning("Copy trading disabled - skipping execution")
            return

        for subscriber in subscribers:
            if not subscriber.is_copy_trading_enabled:
                continue

            try:
                await self._execute_for_user(subscriber, predictions)
            except Exception as e:
                logger.error(f"Copy trade failed for {subscriber.telegram_id}: {e}")

    async def _execute_for_user(
        self,
        user: UserAccount,
        predictions: List[Any]
    ):
        """Execute trades for a single user"""

        if not self.ENABLED:
            return

        # Get user balance
        balance = user.balance_sol

        if balance < 0.01:
            logger.debug(f"User {user.telegram_id} has insufficient balance")
            return

        # Calculate trade size based on risk level
        risk_multipliers = {
            RiskLevel.CONSERVATIVE: 0.05,
            RiskLevel.MODERATE: 0.10,
            RiskLevel.AGGRESSIVE: 0.15
        }

        max_trade_pct = risk_multipliers.get(user.risk_level, 0.05)
        trade_size = min(balance * max_trade_pct, balance * user.max_trade_size_pct)

        # Would execute trades here
        logger.info(f"Would execute {trade_size} SOL trade for user {user.telegram_id}")


class JarvisTelegramBot:
    """
    Telegram bot for public predictions and user copy trading

    Copy trading is DISABLED until security audit complete.
    """

    def __init__(
        self,
        token: str,
        prediction_group_id: int,
        prediction_engine: Any = None
    ):
        self.token = token
        self.prediction_group_id = prediction_group_id
        self.prediction_engine = prediction_engine

        self.user_manager = UserManager()
        self.copy_trader = CopyTrader()

        # Feature flags - CRITICAL SECURITY FLAGS
        self.COPY_TRADING_ENABLED = False  # SET TO FALSE UNTIL AUDITED
        self.WITHDRAWALS_ENABLED = False   # SET TO FALSE UNTIL AUDITED
        self.DEPOSITS_ENABLED = True       # Can receive deposits

        # Bot instance
        self.bot = None
        self.app = None
        self.running = False

        # Initialize bot
        self._initialize_bot()

    def _initialize_bot(self):
        """Initialize Telegram bot"""
        try:
            from telegram import Bot
            from telegram.ext import Application, CommandHandler, MessageHandler, filters

            self.bot = Bot(self.token)
            self.app = Application.builder().token(self.token).build()

            # Register handlers
            self.app.add_handler(CommandHandler("start", self.cmd_start))
            self.app.add_handler(CommandHandler("help", self.cmd_help))
            self.app.add_handler(CommandHandler("predictions", self.cmd_predictions))
            self.app.add_handler(CommandHandler("accuracy", self.cmd_accuracy))
            self.app.add_handler(CommandHandler("deposit", self.cmd_deposit))
            self.app.add_handler(CommandHandler("balance", self.cmd_balance))
            self.app.add_handler(CommandHandler("withdraw", self.cmd_withdraw))
            self.app.add_handler(CommandHandler("history", self.cmd_history))
            self.app.add_handler(CommandHandler("settings", self.cmd_settings))
            self.app.add_handler(CommandHandler("subscribe", self.cmd_subscribe))
            self.app.add_handler(CommandHandler("unsubscribe", self.cmd_unsubscribe))

            logger.info("Telegram bot initialized")

        except ImportError:
            logger.warning("python-telegram-bot not installed")
            self.bot = None
            self.app = None

    async def run(self):
        """Start the bot"""
        if not self.app:
            logger.error("Bot not initialized")
            return

        self.running = True
        logger.info("Starting Jarvis Telegram Bot...")

        # Avoid polling conflicts with other bots using same token
        try:
            from core.utils.instance_lock import acquire_instance_lock
            self._polling_lock = acquire_instance_lock(self.token, name="telegram_polling", max_wait_seconds=0)
        except Exception as exc:
            logger.warning(f"Polling lock helper unavailable: {exc}")
            self._polling_lock = None

        if not self._polling_lock:
            logger.warning("Telegram polling lock held by another process; skipping startup")
            self.running = False
            return

        # Start prediction scheduler
        asyncio.create_task(self._prediction_loop())

        # Start the bot
        await self.app.run_polling()

    def stop(self):
        """Stop the bot"""
        self.running = False
        logger.info("Telegram bot stopping...")
        if getattr(self, "_polling_lock", None):
            try:
                self._polling_lock.close()
            except Exception:
                pass

    async def _prediction_loop(self):
        """Post predictions every 30 minutes"""

        while self.running:
            try:
                await self._post_predictions()
                await asyncio.sleep(30 * 60)  # 30 minutes
            except Exception as e:
                logger.error(f"Prediction loop error: {e}")
                await asyncio.sleep(60)

    async def _post_predictions(self):
        """Generate and post predictions to public group"""

        if not self.prediction_engine:
            logger.debug("No prediction engine configured")
            return

        try:
            # Get top predictions
            predictions = await self.prediction_engine.get_top_predictions(
                count=5,
                min_confidence=0.6
            )

            if not predictions:
                return

            # Get historical accuracy
            accuracy = await self._get_accuracy_stats()

            # Format message
            message = self._format_prediction_message(predictions, accuracy)

            # Post to group
            if self.bot:
                await self.bot.send_message(
                    chat_id=self.prediction_group_id,
                    text=message,
                    parse_mode="HTML"
                )

            # If copy trading enabled, execute for subscribers
            if self.COPY_TRADING_ENABLED:
                subscribers = [
                    user for user in self.user_manager.users.values()
                    if user.is_copy_trading_enabled
                ]
                await self.copy_trader.execute_copy_trades(predictions, subscribers)

        except Exception as e:
            logger.error(f"Failed to post predictions: {e}")

    def _format_prediction_message(
        self,
        predictions: List[Any],
        accuracy: Dict
    ) -> str:
        """Format predictions for Telegram"""

        direction_emoji = {
            "bullish": "🟢",
            "bearish": "🔴",
            "neutral": "🟡"
        }

        lines = [
            "📊 <b>JARVIS PREDICTIONS</b>",
            f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}",
            ""
        ]

        for pred in predictions[:5]:
            emoji = direction_emoji.get(pred.direction, "⚪️")
            conf_bar = "█" * int(pred.confidence * 10) + "░" * (10 - int(pred.confidence * 10))

            signals = ", ".join(pred.key_signals[:2]) if hasattr(pred, 'key_signals') and pred.key_signals else "Multiple signals"

            lines.append(
                f"{emoji} <b>${pred.asset}</b> - {pred.direction.capitalize()}\n"
                f"   Confidence: [{conf_bar}] {int(pred.confidence * 100)}%\n"
                f"   Signals: {signals}"
            )
            lines.append("")

        # Add accuracy stats
        lines.extend([
            "─────────────────",
            f"📈 <b>24H Performance:</b> {accuracy.get('24h_performance', 'Tracking...')}",
            f"🎯 <b>Historical Accuracy:</b> {accuracy.get('overall', 'Tracking...')}",
            f"📊 <b>Total Predictions:</b> {accuracy.get('total_predictions', 0)}",
            "",
            "<i>NFA - Not Financial Advice | DYOR</i>",
            "",
            "💬 Commands: /accuracy /history /subscribe"
        ])

        return "\n".join(lines)

    async def _get_accuracy_stats(self) -> Dict:
        """Get prediction accuracy statistics"""
        # Placeholder - would track actual prediction outcomes
        return {
            "24h_performance": "Tracking...",
            "overall": "Tracking...",
            "total_predictions": 0
        }

    # ==================== COMMAND HANDLERS ====================

    async def cmd_start(self, update, context):
        """Handle /start command"""
        user = update.effective_user

        # Check if account exists
        existing = await self.user_manager.get_account(user.id)

        if existing:
            await update.message.reply_text(
                f"Welcome back, {user.first_name}! 👋\n\n"
                f"Your account is active.\n"
                f"Use /balance to check your balance.\n"
                f"Use /deposit to add funds.\n"
                f"Use /predictions to see latest calls."
            )
            return

        # Create new account
        try:
            account = await self.user_manager.create_account(user.id, user.username)
        except RuntimeError as e:
            logger.error(f"Account creation failed for {user.id}: {e}")
            await update.message.reply_text(
                "Account creation is temporarily disabled. Please try again later."
            )
            return

        await update.message.reply_text(
            f"Welcome to Jarvis Trading! 🤖\n\n"
            f"Your account has been created.\n\n"
            f"📬 Your deposit address:\n"
            f"<code>{account.wallet_address}</code>\n\n"
            f"⚠️ Send SOL to this address to fund your account.\n"
            f"⚠️ Only send SOL on Solana network!\n\n"
            f"Commands:\n"
            f"/deposit - Show deposit address\n"
            f"/balance - Check balance\n"
            f"/predictions - Latest predictions\n"
            f"/accuracy - Track record\n"
            f"/settings - Configure preferences",
            parse_mode="HTML"
        )

    async def cmd_help(self, update, context):
        """Handle /help command"""
        help_text = (
            "🤖 <b>JARVIS Trading Bot</b>\n\n"
            "<b>Public Commands:</b>\n"
            "/start - Create account\n"
            "/predictions - Latest predictions\n"
            "/accuracy - Track record\n"
            "/help - This message\n\n"
            "<b>Account Commands:</b>\n"
            "/deposit - Get deposit address\n"
            "/balance - Check balance\n"
            "/history - Trade history\n"
            "/settings - Configure risk/alerts\n\n"
            "<b>Copy Trading:</b>\n"
            "/subscribe - Enable copy trading\n"
            "/unsubscribe - Disable copy trading\n\n"
            "<i>NFA - Not Financial Advice</i>"
        )
        await update.message.reply_text(help_text, parse_mode="HTML")

    async def cmd_predictions(self, update, context):
        """Show latest predictions"""
        if not self.prediction_engine:
            await update.message.reply_text(
                "📊 Predictions coming soon!\n\n"
                "Join our group @JarvisPredictions for updates."
            )
            return

        try:
            predictions = await self.prediction_engine.get_top_predictions(count=3)
            accuracy = await self._get_accuracy_stats()
            message = self._format_prediction_message(predictions, accuracy)
            await update.message.reply_text(message, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Failed to get predictions: {e}")
            await update.message.reply_text("Failed to fetch predictions. Try again later.")

    async def cmd_accuracy(self, update, context):
        """Show accuracy statistics"""
        stats = await self._get_accuracy_stats()

        message = (
            "📊 <b>JARVIS Track Record</b>\n\n"
            f"🎯 Overall Accuracy: {stats.get('overall', 'Tracking...')}\n"
            f"📈 24H Performance: {stats.get('24h_performance', 'Tracking...')}\n"
            f"📊 Total Predictions: {stats.get('total_predictions', 0)}\n\n"
            "All predictions are publicly tracked for transparency.\n\n"
            "<i>Past performance ≠ future results | NFA</i>"
        )
        await update.message.reply_text(message, parse_mode="HTML")

    async def cmd_deposit(self, update, context):
        """Show deposit address"""
        user = update.effective_user
        account = await self.user_manager.get_account(user.id)

        if not account:
            await update.message.reply_text("Please /start first to create an account.")
            return

        await update.message.reply_text(
            f"📬 Your deposit address:\n\n"
            f"<code>{account.wallet_address}</code>\n\n"
            f"⚠️ Only send SOL on Solana network!\n"
            f"⚠️ Minimum deposit: 0.01 SOL\n"
            f"⚠️ Deposits usually confirm in ~30 seconds",
            parse_mode="HTML"
        )

    async def cmd_balance(self, update, context):
        """Show account balance"""
        user = update.effective_user
        account = await self.user_manager.get_account(user.id)

        if not account:
            await update.message.reply_text("Please /start first to create an account.")
            return

        # Get fresh balance
        balance = account.balance_sol

        # Get positions
        positions = await self.user_manager.get_positions(account.wallet_address)
        position_value = sum(p.value_sol for p in positions)

        copy_status = "✅ Active" if account.is_copy_trading_enabled else "❌ Inactive"

        await update.message.reply_text(
            f"💰 <b>Account Balance</b>\n\n"
            f"Available: {balance:.4f} SOL\n"
            f"In Positions: {position_value:.4f} SOL\n"
            f"Total: {balance + position_value:.4f} SOL\n\n"
            f"Copy Trading: {copy_status}\n"
            f"Risk Level: {account.risk_level.value.capitalize()}\n"
            f"Total Trades: {account.total_trades}\n"
            f"Total P&L: {account.total_pnl_sol:+.4f} SOL",
            parse_mode="HTML"
        )

    async def cmd_withdraw(self, update, context):
        """Withdraw funds"""
        if not self.WITHDRAWALS_ENABLED:
            await update.message.reply_text(
                "⚠️ Withdrawals are temporarily disabled.\n\n"
                "This feature is undergoing security audit. Your funds "
                "are safe and you will be able to withdraw soon.\n\n"
                "Expected: Within 1 week"
            )
            return

        # Withdrawal logic would go here
        await update.message.reply_text("Withdrawal feature coming soon.")

    async def cmd_history(self, update, context):
        """Show trade history"""
        user = update.effective_user
        account = await self.user_manager.get_account(user.id)

        if not account:
            await update.message.reply_text("Please /start first to create an account.")
            return

        if account.total_trades == 0:
            await update.message.reply_text(
                "📜 <b>Trade History</b>\n\n"
                "No trades yet.\n\n"
                "Enable copy trading with /subscribe to start "
                "automatically copying our predictions.",
                parse_mode="HTML"
            )
            return

        # Would fetch actual trade history
        await update.message.reply_text(
            f"📜 <b>Trade History</b>\n\n"
            f"Total Trades: {account.total_trades}\n"
            f"Total P&L: {account.total_pnl_sol:+.4f} SOL\n\n"
            f"Detailed history coming soon.",
            parse_mode="HTML"
        )

    async def cmd_settings(self, update, context):
        """Configure account settings"""
        user = update.effective_user
        account = await self.user_manager.get_account(user.id)

        if not account:
            await update.message.reply_text("Please /start first to create an account.")
            return

        await update.message.reply_text(
            f"⚙️ <b>Account Settings</b>\n\n"
            f"Risk Level: {account.risk_level.value.capitalize()}\n"
            f"Max Trade Size: {int(account.max_trade_size_pct * 100)}% of balance\n"
            f"Subscription: {account.subscription_tier.value.capitalize()}\n\n"
            f"To change settings, use:\n"
            f"/settings risk [conservative|moderate|aggressive]\n"
            f"/settings maxsize [5-20]",
            parse_mode="HTML"
        )

    async def cmd_subscribe(self, update, context):
        """Enable copy trading"""
        if not self.COPY_TRADING_ENABLED:
            await update.message.reply_text(
                "⚠️ Copy trading is currently disabled.\n\n"
                "This feature is undergoing security audit and will be "
                "enabled soon. Stay tuned!\n\n"
                "In the meantime, you can:\n"
                "• Follow /predictions for manual trading\n"
                "• Use /accuracy to see our track record"
            )
            return

        user = update.effective_user
        account = await self.user_manager.get_account(user.id)

        if not account:
            await update.message.reply_text("Please /start first to create an account.")
            return

        if account.balance_sol < 0.1:
            await update.message.reply_text(
                "⚠️ Minimum balance required: 0.1 SOL\n\n"
                "Use /deposit to fund your account."
            )
            return

        account.is_copy_trading_enabled = True
        await self.user_manager.update_account(account)

        await update.message.reply_text(
            "✅ Copy trading enabled!\n\n"
            f"Risk level: {account.risk_level.value.capitalize()}\n"
            f"Max trade size: {int(account.max_trade_size_pct * 100)}% of balance\n\n"
            "You will now automatically copy our high-conviction trades.\n"
            "Use /unsubscribe to disable at any time.\n\n"
            "<i>NFA - Trading involves risk</i>",
            parse_mode="HTML"
        )

    async def cmd_unsubscribe(self, update, context):
        """Disable copy trading"""
        user = update.effective_user
        account = await self.user_manager.get_account(user.id)

        if not account:
            await update.message.reply_text("Please /start first to create an account.")
            return

        account.is_copy_trading_enabled = False
        await self.user_manager.update_account(account)

        await update.message.reply_text(
            "❌ Copy trading disabled.\n\n"
            "You can still:\n"
            "• Follow /predictions manually\n"
            "• Check /accuracy for track record\n"
            "• Re-enable with /subscribe"
        )


# Singleton instance
_telegram_bot_instance: Optional[JarvisTelegramBot] = None


def get_telegram_bot() -> Optional[JarvisTelegramBot]:
    """Get the Telegram bot singleton"""
    global _telegram_bot_instance

    if _telegram_bot_instance is None:
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        group_id = os.environ.get("TELEGRAM_PREDICTION_GROUP_ID")

        if token and group_id:
            _telegram_bot_instance = JarvisTelegramBot(
                token=token,
                prediction_group_id=int(group_id)
            )
        else:
            logger.warning("Telegram credentials not found in environment")

    return _telegram_bot_instance


if __name__ == "__main__":
    bot = get_telegram_bot()
    if bot:
        asyncio.run(bot.run())
    else:
        print("Telegram bot not configured - set environment variables")
