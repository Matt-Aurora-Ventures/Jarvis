"""
Multi-Wallet Manager - Manage multiple wallets with role-based access.
"""

import os
import logging
import json
import base58
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path
from enum import Enum, auto
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


class WalletRole(Enum):
    """Roles for wallet access."""
    TREASURY = "treasury"      # Main treasury wallet
    TRADING = "trading"        # Active trading wallet
    COLD_STORAGE = "cold"      # Cold storage wallet
    HOT_WALLET = "hot"         # Hot wallet for frequent txs
    DEV = "dev"                # Development/testing wallet
    MONITORING = "monitoring"  # View-only monitoring


class WalletStatus(Enum):
    """Wallet status."""
    ACTIVE = "active"
    PAUSED = "paused"
    LOCKED = "locked"
    ARCHIVED = "archived"


@dataclass
class WalletConfig:
    """Configuration for a wallet."""
    name: str
    address: str
    role: WalletRole
    status: WalletStatus = WalletStatus.ACTIVE
    daily_limit_sol: float = 1.0
    single_tx_limit_sol: float = 0.1
    allowed_tokens: List[str] = field(default_factory=list)  # Empty = all allowed
    blocked_tokens: List[str] = field(default_factory=list)
    description: str = ""
    created_at: str = ""
    last_used: Optional[str] = None
    total_spent_today_sol: float = 0.0
    last_reset_date: str = ""
    tags: List[str] = field(default_factory=list)


@dataclass
class WalletBalance:
    """Wallet balance snapshot."""
    address: str
    sol_balance: float
    usd_value: float
    token_balances: Dict[str, float]  # mint -> amount
    last_updated: str


@dataclass
class WalletTransaction:
    """Transaction record for a wallet."""
    wallet_address: str
    tx_signature: str
    timestamp: str
    tx_type: str  # SEND, RECEIVE, SWAP
    amount: float
    currency: str
    counterparty: str = ""
    fee: float = 0.0
    status: str = "confirmed"


class WalletManager:
    """
    Manage multiple wallets with role-based access and limits.

    Usage:
        manager = WalletManager()

        # Add wallets
        manager.add_wallet(WalletConfig(
            name="Trading Wallet",
            address="ABC123...",
            role=WalletRole.TRADING,
            daily_limit_sol=1.0
        ))

        # Get wallet for trading
        wallet = manager.get_wallet_for_role(WalletRole.TRADING)

        # Check if trade is allowed
        can_trade, reason = manager.can_trade(wallet.address, 0.5)
    """

    def __init__(
        self,
        config_path: Optional[Path] = None,
        encryption_key: Optional[str] = None
    ):
        self.config_path = config_path or Path(__file__).parent.parent / "config" / "wallets.json"
        self.wallets: Dict[str, WalletConfig] = {}
        self.balances: Dict[str, WalletBalance] = {}
        self._fernet: Optional[Fernet] = None

        if encryption_key:
            self._fernet = Fernet(encryption_key.encode())

        self._load_wallets()

    def _load_wallets(self):
        """Load wallets from config file."""
        if not self.config_path.exists():
            logger.info("No wallet config found, starting fresh")
            return

        try:
            with open(self.config_path, 'r') as f:
                data = json.load(f)

            for wallet_data in data.get('wallets', []):
                config = WalletConfig(
                    name=wallet_data['name'],
                    address=wallet_data['address'],
                    role=WalletRole(wallet_data['role']),
                    status=WalletStatus(wallet_data.get('status', 'active')),
                    daily_limit_sol=wallet_data.get('daily_limit_sol', 1.0),
                    single_tx_limit_sol=wallet_data.get('single_tx_limit_sol', 0.1),
                    allowed_tokens=wallet_data.get('allowed_tokens', []),
                    blocked_tokens=wallet_data.get('blocked_tokens', []),
                    description=wallet_data.get('description', ''),
                    created_at=wallet_data.get('created_at', ''),
                    tags=wallet_data.get('tags', [])
                )
                self.wallets[config.address] = config

            logger.info(f"Loaded {len(self.wallets)} wallets")

        except Exception as e:
            logger.error(f"Failed to load wallets: {e}")

    def _save_wallets(self):
        """Save wallets to config file."""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                'wallets': [
                    {
                        'name': w.name,
                        'address': w.address,
                        'role': w.role.value,
                        'status': w.status.value,
                        'daily_limit_sol': w.daily_limit_sol,
                        'single_tx_limit_sol': w.single_tx_limit_sol,
                        'allowed_tokens': w.allowed_tokens,
                        'blocked_tokens': w.blocked_tokens,
                        'description': w.description,
                        'created_at': w.created_at,
                        'tags': w.tags
                    }
                    for w in self.wallets.values()
                ]
            }

            with open(self.config_path, 'w') as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save wallets: {e}")

    def add_wallet(self, config: WalletConfig) -> bool:
        """Add a new wallet."""
        if not self._validate_address(config.address):
            logger.error(f"Invalid Solana address: {config.address}")
            return False

        if config.address in self.wallets:
            logger.warning(f"Wallet already exists: {config.address}")
            return False

        config.created_at = datetime.now(timezone.utc).isoformat()
        self.wallets[config.address] = config
        self._save_wallets()

        logger.info(f"Added wallet: {config.name} ({config.role.value})")
        return True

    def remove_wallet(self, address: str) -> bool:
        """Remove a wallet."""
        if address not in self.wallets:
            return False

        # Don't allow removing the treasury wallet
        if self.wallets[address].role == WalletRole.TREASURY:
            logger.error("Cannot remove treasury wallet")
            return False

        del self.wallets[address]
        self._save_wallets()

        logger.info(f"Removed wallet: {address}")
        return True

    def update_wallet(self, address: str, updates: Dict[str, Any]) -> bool:
        """Update wallet configuration."""
        if address not in self.wallets:
            return False

        wallet = self.wallets[address]

        for key, value in updates.items():
            if hasattr(wallet, key):
                if key == 'role':
                    value = WalletRole(value)
                elif key == 'status':
                    value = WalletStatus(value)
                setattr(wallet, key, value)

        self._save_wallets()
        return True

    def get_wallet(self, address: str) -> Optional[WalletConfig]:
        """Get wallet by address."""
        return self.wallets.get(address)

    def get_wallets_by_role(self, role: WalletRole) -> List[WalletConfig]:
        """Get all wallets with a specific role."""
        return [w for w in self.wallets.values() if w.role == role]

    def get_wallet_for_role(self, role: WalletRole) -> Optional[WalletConfig]:
        """Get the primary active wallet for a role."""
        wallets = [
            w for w in self.wallets.values()
            if w.role == role and w.status == WalletStatus.ACTIVE
        ]
        return wallets[0] if wallets else None

    def get_active_wallets(self) -> List[WalletConfig]:
        """Get all active wallets."""
        return [w for w in self.wallets.values() if w.status == WalletStatus.ACTIVE]

    def set_status(self, address: str, status: WalletStatus) -> bool:
        """Update wallet status."""
        if address not in self.wallets:
            return False

        self.wallets[address].status = status
        self._save_wallets()

        logger.info(f"Wallet {address} status changed to {status.value}")
        return True

    def can_trade(
        self,
        address: str,
        amount_sol: float,
        token_mint: str = None
    ) -> Tuple[bool, str]:
        """Check if a trade is allowed for this wallet."""
        wallet = self.wallets.get(address)

        if not wallet:
            return False, "Wallet not found"

        if wallet.status != WalletStatus.ACTIVE:
            return False, f"Wallet is {wallet.status.value}"

        if wallet.role == WalletRole.MONITORING:
            return False, "Monitoring wallets cannot trade"

        if wallet.role == WalletRole.COLD_STORAGE:
            return False, "Cold storage wallets cannot trade"

        # Check single transaction limit
        if amount_sol > wallet.single_tx_limit_sol:
            return False, f"Amount {amount_sol} exceeds tx limit {wallet.single_tx_limit_sol}"

        # Check daily limit
        self._maybe_reset_daily_limit(wallet)
        if wallet.total_spent_today_sol + amount_sol > wallet.daily_limit_sol:
            remaining = wallet.daily_limit_sol - wallet.total_spent_today_sol
            return False, f"Would exceed daily limit. Remaining: {remaining:.4f} SOL"

        # Check token restrictions
        if token_mint:
            if wallet.blocked_tokens and token_mint in wallet.blocked_tokens:
                return False, "Token is blocked for this wallet"

            if wallet.allowed_tokens and token_mint not in wallet.allowed_tokens:
                return False, "Token not in allowed list"

        return True, "OK"

    def record_trade(self, address: str, amount_sol: float):
        """Record a trade against wallet limits."""
        wallet = self.wallets.get(address)
        if not wallet:
            return

        self._maybe_reset_daily_limit(wallet)
        wallet.total_spent_today_sol += amount_sol
        wallet.last_used = datetime.now(timezone.utc).isoformat()

    def _maybe_reset_daily_limit(self, wallet: WalletConfig):
        """Reset daily limit if it's a new day."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if wallet.last_reset_date != today:
            wallet.total_spent_today_sol = 0.0
            wallet.last_reset_date = today

    def _validate_address(self, address: str) -> bool:
        """Validate Solana address format."""
        try:
            decoded = base58.b58decode(address)
            return len(decoded) == 32
        except Exception:
            return False

    def update_balance(
        self,
        address: str,
        sol_balance: float,
        token_balances: Dict[str, float] = None,
        usd_value: float = 0.0
    ):
        """Update cached balance for a wallet."""
        self.balances[address] = WalletBalance(
            address=address,
            sol_balance=sol_balance,
            usd_value=usd_value,
            token_balances=token_balances or {},
            last_updated=datetime.now(timezone.utc).isoformat()
        )

    def get_balance(self, address: str) -> Optional[WalletBalance]:
        """Get cached balance for a wallet."""
        return self.balances.get(address)

    def get_total_balance(self) -> Dict[str, float]:
        """Get total balance across all wallets."""
        total_sol = sum(b.sol_balance for b in self.balances.values())
        total_usd = sum(b.usd_value for b in self.balances.values())

        # Aggregate token balances
        token_totals: Dict[str, float] = {}
        for balance in self.balances.values():
            for mint, amount in balance.token_balances.items():
                token_totals[mint] = token_totals.get(mint, 0) + amount

        return {
            'total_sol': total_sol,
            'total_usd': total_usd,
            'token_balances': token_totals,
            'wallet_count': len(self.balances)
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all wallets."""
        by_role = {}
        for role in WalletRole:
            wallets = self.get_wallets_by_role(role)
            if wallets:
                by_role[role.value] = {
                    'count': len(wallets),
                    'active': len([w for w in wallets if w.status == WalletStatus.ACTIVE]),
                    'addresses': [w.address[:8] + "..." for w in wallets]
                }

        return {
            'total_wallets': len(self.wallets),
            'active_wallets': len(self.get_active_wallets()),
            'by_role': by_role,
            'total_balance': self.get_total_balance()
        }

    def export_addresses(self, role: WalletRole = None) -> List[str]:
        """Export wallet addresses for monitoring."""
        if role:
            return [w.address for w in self.get_wallets_by_role(role)]
        return list(self.wallets.keys())


# === WALLET SELECTION HELPER ===

class WalletSelector:
    """
    Select appropriate wallet for different operations.

    Usage:
        selector = WalletSelector(wallet_manager)

        # Get wallet for a trade
        wallet = selector.select_for_trade(amount=0.5, token="ABC...")
    """

    def __init__(self, manager: WalletManager):
        self.manager = manager

    def select_for_trade(
        self,
        amount: float,
        token_mint: str = None
    ) -> Optional[WalletConfig]:
        """Select the best wallet for a trade."""
        # First try trading wallet
        candidates = self.manager.get_wallets_by_role(WalletRole.TRADING)

        # Fall back to hot wallet
        if not candidates:
            candidates = self.manager.get_wallets_by_role(WalletRole.HOT_WALLET)

        # Filter by status and limits
        valid = []
        for wallet in candidates:
            can_trade, _ = self.manager.can_trade(wallet.address, amount, token_mint)
            if can_trade:
                valid.append(wallet)

        if not valid:
            return None

        # Sort by remaining daily limit (prefer wallet with more capacity)
        valid.sort(
            key=lambda w: w.daily_limit_sol - w.total_spent_today_sol,
            reverse=True
        )

        return valid[0]

    def select_for_monitoring(self) -> List[WalletConfig]:
        """Get all wallets to monitor."""
        return [
            w for w in self.manager.wallets.values()
            if w.status in (WalletStatus.ACTIVE, WalletStatus.PAUSED)
        ]


# Singleton
_manager: Optional[WalletManager] = None

def get_wallet_manager() -> WalletManager:
    """Get singleton wallet manager."""
    global _manager
    if _manager is None:
        _manager = WalletManager()
    return _manager
