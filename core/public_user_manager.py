"""
Public Trading Bot - User and Wallet Management System

Multi-tenant system supporting:
- Per-user wallet creation and management
- Wallet import/export functionality
- User settings and preferences
- Transaction history
- Security and rate limiting
- Adaptive trading profiles
"""

import json
import logging
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)


class UserRiskLevel(Enum):
    """User risk profile levels."""
    CONSERVATIVE = 1  # 0.5% per trade
    MODERATE = 2      # 2% per trade
    AGGRESSIVE = 5    # 5% per trade
    DEGEN = 10        # 10% per trade (risky)


class WalletSource(Enum):
    """Where the wallet came from."""
    GENERATED = "generated"      # Created by bot
    IMPORTED = "imported"        # User imported
    RECOVERED = "recovered"      # Recovered from seed


@dataclass
class Wallet:
    """User wallet information."""
    wallet_id: str
    user_id: int
    public_key: str
    encrypted_private_key: str  # Encrypted for security
    source: WalletSource
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_used: datetime = field(default_factory=datetime.utcnow)
    balance_sol: float = 0.0
    total_traded_usd: float = 0.0
    is_primary: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (safe - no private key)."""
        return {
            'wallet_id': self.wallet_id,
            'user_id': self.user_id,
            'public_key': self.public_key,
            'source': self.source.value,
            'created_at': self.created_at.isoformat(),
            'last_used': self.last_used.isoformat(),
            'balance_sol': self.balance_sol,
            'total_traded_usd': self.total_traded_usd,
            'is_primary': self.is_primary,
        }


@dataclass
class UserProfile:
    """User trading profile and settings."""
    user_id: int
    telegram_username: str

    # Trading settings
    risk_level: UserRiskLevel = UserRiskLevel.MODERATE
    max_position_size_pct: float = 2.0  # % of wallet per trade
    max_daily_trades: int = 20
    max_daily_loss_usd: float = 100.0

    # Safety settings
    require_trade_confirmation: bool = True
    enable_alerts: bool = True
    anti_whale_threshold_usd: float = 50000.0

    # Adaptive learning
    auto_adjust_risk: bool = True
    learn_from_losses: bool = True

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_active: datetime = field(default_factory=datetime.utcnow)
    is_active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'user_id': self.user_id,
            'telegram_username': self.telegram_username,
            'risk_level': self.risk_level.name,
            'max_position_size_pct': self.max_position_size_pct,
            'max_daily_trades': self.max_daily_trades,
            'max_daily_loss_usd': self.max_daily_loss_usd,
            'require_trade_confirmation': self.require_trade_confirmation,
            'enable_alerts': self.enable_alerts,
            'anti_whale_threshold_usd': self.anti_whale_threshold_usd,
            'auto_adjust_risk': self.auto_adjust_risk,
            'learn_from_losses': self.learn_from_losses,
            'created_at': self.created_at.isoformat(),
            'last_active': self.last_active.isoformat(),
            'is_active': self.is_active,
        }


@dataclass
class UserStats:
    """User trading statistics and performance."""
    user_id: int
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl_usd: float = 0.0
    win_rate: float = 0.0
    avg_win_usd: float = 0.0
    avg_loss_usd: float = 0.0
    best_trade_usd: float = 0.0
    worst_trade_usd: float = 0.0
    total_volume_usd: float = 0.0

    # Adaptive metrics
    current_risk_level: UserRiskLevel = UserRiskLevel.MODERATE
    last_adjusted: datetime = field(default_factory=datetime.utcnow)
    win_streak: int = 0
    loss_streak: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class PublicUserManager:
    """
    Manages users, wallets, and settings for public trading bot.

    Responsibilities:
    - User registration and profile management
    - Wallet creation, import, and export
    - User settings and preferences
    - Trading limits and risk management
    - User statistics and performance tracking
    - Security and rate limiting
    """

    def __init__(self, db_path: str = "~/.lifeos/public_users.db"):
        """Initialize user manager with database."""
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _init_database(self):
        """Initialize SQLite database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                telegram_username TEXT UNIQUE NOT NULL,
                risk_level TEXT DEFAULT 'MODERATE',
                max_position_size_pct REAL DEFAULT 2.0,
                max_daily_trades INTEGER DEFAULT 20,
                max_daily_loss_usd REAL DEFAULT 100.0,
                require_trade_confirmation BOOLEAN DEFAULT 1,
                enable_alerts BOOLEAN DEFAULT 1,
                anti_whale_threshold_usd REAL DEFAULT 50000.0,
                auto_adjust_risk BOOLEAN DEFAULT 1,
                learn_from_losses BOOLEAN DEFAULT 1,
                created_at TEXT NOT NULL,
                last_active TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 1
            )
        """)

        # Wallets table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wallets (
                wallet_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                public_key TEXT UNIQUE NOT NULL,
                encrypted_private_key TEXT NOT NULL,
                source TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_used TEXT NOT NULL,
                balance_sol REAL DEFAULT 0.0,
                total_traded_usd REAL DEFAULT 0.0,
                is_primary BOOLEAN DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # User stats table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_stats (
                user_id INTEGER PRIMARY KEY,
                total_trades INTEGER DEFAULT 0,
                winning_trades INTEGER DEFAULT 0,
                losing_trades INTEGER DEFAULT 0,
                total_pnl_usd REAL DEFAULT 0.0,
                win_rate REAL DEFAULT 0.0,
                avg_win_usd REAL DEFAULT 0.0,
                avg_loss_usd REAL DEFAULT 0.0,
                best_trade_usd REAL DEFAULT 0.0,
                worst_trade_usd REAL DEFAULT 0.0,
                total_volume_usd REAL DEFAULT 0.0,
                current_risk_level TEXT DEFAULT 'MODERATE',
                last_adjusted TEXT NOT NULL,
                win_streak INTEGER DEFAULT 0,
                loss_streak INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # Transactions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                tx_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                wallet_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                action TEXT NOT NULL,
                amount_usd REAL NOT NULL,
                executed_at TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                pnl_usd REAL DEFAULT 0.0,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (wallet_id) REFERENCES wallets(wallet_id)
            )
        """)

        # Rate limiting table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rate_limits (
                user_id INTEGER PRIMARY KEY,
                trades_today INTEGER DEFAULT 0,
                loss_today_usd REAL DEFAULT 0.0,
                last_reset TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        conn.commit()
        conn.close()
        logger.info(f"User database initialized at {self.db_path}")

    # ==================== USER MANAGEMENT ====================

    def register_user(self, user_id: int, username: str) -> Tuple[bool, UserProfile]:
        """
        Register a new user.

        Args:
            user_id: Telegram user ID
            username: Telegram username

        Returns:
            (success, UserProfile)
        """
        try:
            profile = UserProfile(
                user_id=user_id,
                telegram_username=username,
            )

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO users (
                    user_id, telegram_username, risk_level,
                    max_position_size_pct, max_daily_trades, max_daily_loss_usd,
                    require_trade_confirmation, enable_alerts, anti_whale_threshold_usd,
                    auto_adjust_risk, learn_from_losses, created_at, last_active, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id, username, profile.risk_level.name,
                profile.max_position_size_pct, profile.max_daily_trades, profile.max_daily_loss_usd,
                profile.require_trade_confirmation, profile.enable_alerts, profile.anti_whale_threshold_usd,
                profile.auto_adjust_risk, profile.learn_from_losses,
                datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), True
            ))

            # Initialize stats
            cursor.execute("""
                INSERT INTO user_stats (user_id, last_adjusted)
                VALUES (?, ?)
            """, (user_id, datetime.utcnow().isoformat()))

            # Initialize rate limits
            cursor.execute("""
                INSERT INTO rate_limits (user_id, last_reset)
                VALUES (?, ?)
            """, (user_id, datetime.utcnow().isoformat()))

            conn.commit()
            conn.close()

            logger.info(f"User {user_id} ({username}) registered")
            return True, profile

        except sqlite3.IntegrityError:
            logger.warning(f"User {user_id} already exists")
            return False, self.get_user_profile(user_id)
        except Exception as e:
            logger.error(f"User registration failed: {e}")
            return False, None

    def get_user_profile(self, user_id: int) -> Optional[UserProfile]:
        """Get user profile."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            conn.close()

            if not row:
                return None

            cols = ['user_id', 'telegram_username', 'risk_level', 'max_position_size_pct',
                   'max_daily_trades', 'max_daily_loss_usd', 'require_trade_confirmation',
                   'enable_alerts', 'anti_whale_threshold_usd', 'auto_adjust_risk',
                   'learn_from_losses', 'created_at', 'last_active', 'is_active']

            data = dict(zip(cols, row))

            return UserProfile(
                user_id=data['user_id'],
                telegram_username=data['telegram_username'],
                risk_level=UserRiskLevel[data['risk_level']],
                max_position_size_pct=data['max_position_size_pct'],
                max_daily_trades=data['max_daily_trades'],
                max_daily_loss_usd=data['max_daily_loss_usd'],
                require_trade_confirmation=bool(data['require_trade_confirmation']),
                enable_alerts=bool(data['enable_alerts']),
                anti_whale_threshold_usd=data['anti_whale_threshold_usd'],
                auto_adjust_risk=bool(data['auto_adjust_risk']),
                learn_from_losses=bool(data['learn_from_losses']),
                created_at=datetime.fromisoformat(data['created_at']),
                last_active=datetime.fromisoformat(data['last_active']),
                is_active=bool(data['is_active']),
            )
        except Exception as e:
            logger.error(f"Failed to get user profile: {e}")
            return None

    def update_user_settings(self, user_id: int, **settings) -> bool:
        """Update user settings."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Build update query
            valid_fields = {
                'risk_level', 'max_position_size_pct', 'max_daily_trades',
                'max_daily_loss_usd', 'require_trade_confirmation', 'enable_alerts',
                'anti_whale_threshold_usd', 'auto_adjust_risk', 'learn_from_losses'
            }

            update_fields = [k for k in settings.keys() if k in valid_fields]
            if not update_fields:
                return False

            set_clause = ', '.join([f"{field} = ?" for field in update_fields])
            values = [settings[field] for field in update_fields]
            values.append(user_id)

            cursor.execute(
                f"UPDATE users SET {set_clause}, last_active = ? WHERE user_id = ?",
                values[:-1] + [datetime.utcnow().isoformat(), user_id]
            )

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            logger.error(f"Failed to update user settings: {e}")
            return False

    # ==================== WALLET MANAGEMENT ====================

    def create_wallet(self, user_id: int, public_key: str, encrypted_private_key: str,
                     is_primary: bool = False) -> Tuple[bool, Optional[Wallet]]:
        """
        Create a new wallet for user.

        Args:
            user_id: User ID
            public_key: Solana public key
            encrypted_private_key: Encrypted private key (never stored unencrypted)
            is_primary: Make this the primary wallet

        Returns:
            (success, Wallet)
        """
        try:
            wallet_id = f"wallet_{user_id}_{secrets.token_hex(8)}"
            wallet = Wallet(
                wallet_id=wallet_id,
                user_id=user_id,
                public_key=public_key,
                encrypted_private_key=encrypted_private_key,
                source=WalletSource.GENERATED,
                is_primary=is_primary,
            )

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # If primary, unset other primary wallets
            if is_primary:
                cursor.execute(
                    "UPDATE wallets SET is_primary = 0 WHERE user_id = ?",
                    (user_id,)
                )

            cursor.execute("""
                INSERT INTO wallets (
                    wallet_id, user_id, public_key, encrypted_private_key,
                    source, created_at, last_used, is_primary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                wallet.wallet_id, wallet.user_id, wallet.public_key,
                wallet.encrypted_private_key, wallet.source.value,
                wallet.created_at.isoformat(), wallet.last_used.isoformat(),
                wallet.is_primary
            ))

            conn.commit()
            conn.close()

            logger.info(f"Wallet {wallet_id} created for user {user_id}")
            return True, wallet

        except Exception as e:
            logger.error(f"Failed to create wallet: {e}")
            return False, None

    def import_wallet(self, user_id: int, public_key: str, encrypted_private_key: str,
                     is_primary: bool = False) -> Tuple[bool, Optional[Wallet]]:
        """
        Import an existing wallet.

        Args:
            user_id: User ID
            public_key: Solana public key
            encrypted_private_key: Encrypted private key
            is_primary: Make this the primary wallet

        Returns:
            (success, Wallet)
        """
        try:
            wallet_id = f"wallet_{user_id}_{secrets.token_hex(8)}"
            wallet = Wallet(
                wallet_id=wallet_id,
                user_id=user_id,
                public_key=public_key,
                encrypted_private_key=encrypted_private_key,
                source=WalletSource.IMPORTED,
                is_primary=is_primary,
            )

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            if is_primary:
                cursor.execute(
                    "UPDATE wallets SET is_primary = 0 WHERE user_id = ?",
                    (user_id,)
                )

            cursor.execute("""
                INSERT INTO wallets (
                    wallet_id, user_id, public_key, encrypted_private_key,
                    source, created_at, last_used, is_primary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                wallet.wallet_id, wallet.user_id, wallet.public_key,
                wallet.encrypted_private_key, wallet.source.value,
                wallet.created_at.isoformat(), wallet.last_used.isoformat(),
                wallet.is_primary
            ))

            conn.commit()
            conn.close()

            logger.info(f"Wallet {wallet_id} imported for user {user_id}")
            return True, wallet

        except Exception as e:
            logger.error(f"Failed to import wallet: {e}")
            return False, None

    def get_user_wallets(self, user_id: int) -> List[Wallet]:
        """Get all wallets for user."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                "SELECT * FROM wallets WHERE user_id = ? ORDER BY is_primary DESC, created_at DESC",
                (user_id,)
            )
            rows = cursor.fetchall()
            conn.close()

            wallets = []
            for row in rows:
                cols = ['wallet_id', 'user_id', 'public_key', 'encrypted_private_key',
                       'source', 'created_at', 'last_used', 'balance_sol', 'total_traded_usd',
                       'is_primary']
                data = dict(zip(cols, row))

                wallet = Wallet(
                    wallet_id=data['wallet_id'],
                    user_id=data['user_id'],
                    public_key=data['public_key'],
                    encrypted_private_key=data['encrypted_private_key'],
                    source=WalletSource(data['source']),
                    created_at=datetime.fromisoformat(data['created_at']),
                    last_used=datetime.fromisoformat(data['last_used']),
                    balance_sol=data['balance_sol'],
                    total_traded_usd=data['total_traded_usd'],
                    is_primary=bool(data['is_primary']),
                )
                wallets.append(wallet)

            return wallets

        except Exception as e:
            logger.error(f"Failed to get user wallets: {e}")
            return []

    def get_primary_wallet(self, user_id: int) -> Optional[Wallet]:
        """Get user's primary wallet."""
        wallets = self.get_user_wallets(user_id)
        for w in wallets:
            if w.is_primary:
                return w
        return wallets[0] if wallets else None

    def export_wallet(self, user_id: int, wallet_id: str) -> Optional[Dict[str, str]]:
        """
        Export wallet for backup (returns encrypted data).

        Args:
            user_id: User ID
            wallet_id: Wallet ID to export

        Returns:
            {'public_key': str, 'encrypted_private_key': str} or None
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                "SELECT public_key, encrypted_private_key FROM wallets WHERE wallet_id = ? AND user_id = ?",
                (wallet_id, user_id)
            )
            row = cursor.fetchone()
            conn.close()

            if not row:
                return None

            return {
                'public_key': row[0],
                'encrypted_private_key': row[1],  # Still encrypted
            }

        except Exception as e:
            logger.error(f"Failed to export wallet: {e}")
            return None

    # ==================== USER STATISTICS ====================

    def get_user_stats(self, user_id: int) -> Optional[UserStats]:
        """Get user trading statistics."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM user_stats WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            conn.close()

            if not row:
                return None

            cols = ['user_id', 'total_trades', 'winning_trades', 'losing_trades',
                   'total_pnl_usd', 'win_rate', 'avg_win_usd', 'avg_loss_usd',
                   'best_trade_usd', 'worst_trade_usd', 'total_volume_usd',
                   'current_risk_level', 'last_adjusted', 'win_streak', 'loss_streak']
            data = dict(zip(cols, row))

            return UserStats(
                user_id=data['user_id'],
                total_trades=data['total_trades'],
                winning_trades=data['winning_trades'],
                losing_trades=data['losing_trades'],
                total_pnl_usd=data['total_pnl_usd'],
                win_rate=data['win_rate'],
                avg_win_usd=data['avg_win_usd'],
                avg_loss_usd=data['avg_loss_usd'],
                best_trade_usd=data['best_trade_usd'],
                worst_trade_usd=data['worst_trade_usd'],
                total_volume_usd=data['total_volume_usd'],
                current_risk_level=UserRiskLevel[data['current_risk_level']],
                last_adjusted=datetime.fromisoformat(data['last_adjusted']),
                win_streak=data['win_streak'],
                loss_streak=data['loss_streak'],
            )
        except Exception as e:
            logger.error(f"Failed to get user stats: {e}")
            return None

    def record_trade(self, user_id: int, wallet_id: str, symbol: str, action: str,
                    amount_usd: float, pnl_usd: float = 0.0) -> bool:
        """
        Record a trade for the user.

        Args:
            user_id: User ID
            wallet_id: Wallet used
            symbol: Token symbol
            action: 'BUY' or 'SELL'
            amount_usd: Trade amount in USD
            pnl_usd: Profit/loss if this is a close (0 for opens)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            tx_id = f"tx_{user_id}_{secrets.token_hex(8)}"

            # Record transaction
            cursor.execute("""
                INSERT INTO transactions (
                    tx_id, user_id, wallet_id, symbol, action, amount_usd, executed_at, pnl_usd
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (tx_id, user_id, wallet_id, symbol, action, amount_usd,
                 datetime.utcnow().isoformat(), pnl_usd))

            # Update user stats
            stats = self.get_user_stats(user_id)
            if stats:
                stats.total_trades += 1
                stats.total_volume_usd += amount_usd

                if pnl_usd != 0:
                    stats.total_pnl_usd += pnl_usd

                    if pnl_usd > 0:
                        stats.winning_trades += 1
                        stats.win_streak += 1
                        stats.loss_streak = 0
                        if pnl_usd > stats.best_trade_usd:
                            stats.best_trade_usd = pnl_usd
                        stats.avg_win_usd = stats.total_pnl_usd / stats.winning_trades
                    else:
                        stats.losing_trades += 1
                        stats.loss_streak += 1
                        stats.win_streak = 0
                        if pnl_usd < stats.worst_trade_usd:
                            stats.worst_trade_usd = pnl_usd
                        stats.avg_loss_usd = -stats.total_pnl_usd / stats.losing_trades

                stats.win_rate = (stats.winning_trades / stats.total_trades * 100) if stats.total_trades > 0 else 0

                cursor.execute("""
                    UPDATE user_stats SET
                        total_trades = ?, winning_trades = ?, losing_trades = ?,
                        total_pnl_usd = ?, win_rate = ?, avg_win_usd = ?, avg_loss_usd = ?,
                        best_trade_usd = ?, worst_trade_usd = ?, total_volume_usd = ?,
                        win_streak = ?, loss_streak = ?
                    WHERE user_id = ?
                """, (
                    stats.total_trades, stats.winning_trades, stats.losing_trades,
                    stats.total_pnl_usd, stats.win_rate, stats.avg_win_usd, stats.avg_loss_usd,
                    stats.best_trade_usd, stats.worst_trade_usd, stats.total_volume_usd,
                    stats.win_streak, stats.loss_streak, user_id
                ))

            conn.commit()
            conn.close()

            logger.info(f"Trade recorded for user {user_id}: {symbol} {action} ${amount_usd:.2f}")
            return True

        except Exception as e:
            logger.error(f"Failed to record trade: {e}")
            return False

    # ==================== RATE LIMITING ====================

    def check_rate_limits(self, user_id: int) -> Tuple[bool, str]:
        """
        Check if user has exceeded rate limits.

        Returns:
            (allowed, reason)
        """
        try:
            profile = self.get_user_profile(user_id)
            if not profile:
                return False, "User profile not found"

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                "SELECT trades_today, loss_today_usd, last_reset FROM rate_limits WHERE user_id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            conn.close()

            if not row:
                return False, "Rate limit record not found"

            trades_today, loss_today_usd, last_reset = row

            # Check if day has passed
            last_reset_dt = datetime.fromisoformat(last_reset)
            if datetime.utcnow() - last_reset_dt > timedelta(days=1):
                # Reset counters
                self._reset_daily_limits(user_id)
                trades_today = 0
                loss_today_usd = 0.0

            # Check limits
            if trades_today >= profile.max_daily_trades:
                return False, f"Daily trade limit ({profile.max_daily_trades}) reached"

            if loss_today_usd >= profile.max_daily_loss_usd:
                return False, f"Daily loss limit (${profile.max_daily_loss_usd:.2f}) reached"

            return True, "OK"

        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            return False, f"Error checking limits: {e}"

    def _reset_daily_limits(self, user_id: int):
        """Reset daily trade and loss counters."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE rate_limits SET trades_today = 0, loss_today_usd = 0.0, last_reset = ? WHERE user_id = ?",
                (datetime.utcnow().isoformat(), user_id)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to reset daily limits: {e}")

    def increment_trade_count(self, user_id: int, loss_amount: float = 0.0):
        """Increment user's daily trade count and loss."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                "UPDATE rate_limits SET trades_today = trades_today + 1, loss_today_usd = loss_today_usd + ? WHERE user_id = ?",
                (max(0, loss_amount), user_id)
            )

            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to increment trade count: {e}")
