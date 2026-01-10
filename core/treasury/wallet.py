"""
Treasury Wallet Management.

Multi-wallet architecture for secure fund management:

1. Reserve Vault (60%)
   - Cold storage for majority of funds
   - Multisig protected (2-of-3)
   - Only moved for rebalancing or emergencies

2. Active Trading (30%)
   - Hot wallet for automated trading
   - Limited balance to minimize risk
   - Auto-replenished from reserve when low

3. Profit Buffer (10%)
   - Holds realized profits
   - Distributed weekly to stakers
   - Automatically swept to staking pool
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("jarvis.treasury.wallet")

# Constants
LAMPORTS_PER_SOL = 1_000_000_000


class WalletType(Enum):
    """Types of treasury wallets."""
    RESERVE = "reserve"        # Cold storage (60%)
    ACTIVE = "active"          # Hot wallet for trading (30%)
    PROFIT = "profit"          # Profit buffer (10%)
    STAKING = "staking"        # Staking rewards pool
    OPERATIONS = "operations"  # Team/ops wallet
    DEVELOPMENT = "development"  # Dev reserve


@dataclass
class WalletAllocation:
    """Target allocation for a wallet type."""
    wallet_type: WalletType
    target_percentage: float  # 0.0 to 1.0
    min_balance_sol: float = 0.0  # Minimum SOL to maintain
    max_balance_sol: float = float('inf')  # Maximum SOL allowed
    requires_multisig: bool = False
    signers_required: int = 1

    def __post_init__(self):
        if not 0 <= self.target_percentage <= 1:
            raise ValueError("target_percentage must be between 0 and 1")


# Default allocation strategy
DEFAULT_ALLOCATIONS = [
    WalletAllocation(
        wallet_type=WalletType.RESERVE,
        target_percentage=0.60,
        min_balance_sol=10.0,
        requires_multisig=True,
        signers_required=2,
    ),
    WalletAllocation(
        wallet_type=WalletType.ACTIVE,
        target_percentage=0.30,
        min_balance_sol=1.0,
        max_balance_sol=100.0,  # Cap active trading funds
    ),
    WalletAllocation(
        wallet_type=WalletType.PROFIT,
        target_percentage=0.10,
        min_balance_sol=0.0,
    ),
]


@dataclass
class WalletBalance:
    """Current balance of a wallet."""
    wallet_type: WalletType
    address: str
    sol_balance: int  # In lamports
    token_balances: Dict[str, int] = field(default_factory=dict)  # mint -> amount
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def sol_balance_decimal(self) -> Decimal:
        return Decimal(self.sol_balance) / Decimal(LAMPORTS_PER_SOL)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "wallet_type": self.wallet_type.value,
            "address": self.address,
            "sol_balance_lamports": self.sol_balance,
            "sol_balance": float(self.sol_balance_decimal),
            "token_balances": self.token_balances,
            "last_updated": self.last_updated.isoformat(),
        }


@dataclass
class TreasuryWallet:
    """Configuration for a treasury wallet."""
    wallet_type: WalletType
    address: str
    label: str
    is_multisig: bool = False
    multisig_address: Optional[str] = None  # Squads multisig address
    signers: List[str] = field(default_factory=list)
    threshold: int = 1
    keypair_path: Optional[str] = None  # Path to keypair (hot wallets only)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "wallet_type": self.wallet_type.value,
            "address": self.address,
            "label": self.label,
            "is_multisig": self.is_multisig,
            "multisig_address": self.multisig_address,
            "signers_count": len(self.signers),
            "threshold": self.threshold,
        }


class WalletManager:
    """
    Manages treasury wallet operations.

    Handles:
    - Balance tracking
    - SOL/token transfers
    - Multisig operations
    - Rebalancing between wallets
    """

    def __init__(
        self,
        wallets: Dict[WalletType, TreasuryWallet] = None,
        allocations: List[WalletAllocation] = None,
        rpc_url: str = None,
    ):
        """
        Initialize wallet manager.

        Args:
            wallets: Mapping of wallet type to wallet config
            allocations: Target allocation strategy
            rpc_url: Solana RPC URL
        """
        self.wallets = wallets or {}
        self.allocations = {a.wallet_type: a for a in (allocations or DEFAULT_ALLOCATIONS)}
        self.rpc_url = rpc_url or os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")

        self._balances: Dict[WalletType, WalletBalance] = {}
        self._last_rebalance: Optional[datetime] = None

    def add_wallet(self, wallet: TreasuryWallet):
        """Add a wallet to management."""
        self.wallets[wallet.wallet_type] = wallet
        logger.info(f"Added {wallet.wallet_type.value} wallet: {wallet.address}")

    async def get_balance(self, wallet_type: WalletType) -> Optional[WalletBalance]:
        """Get current balance for a wallet."""
        wallet = self.wallets.get(wallet_type)
        if not wallet:
            return None

        try:
            sol_balance = await self._fetch_sol_balance(wallet.address)
            token_balances = await self._fetch_token_balances(wallet.address)

            balance = WalletBalance(
                wallet_type=wallet_type,
                address=wallet.address,
                sol_balance=sol_balance,
                token_balances=token_balances,
            )

            self._balances[wallet_type] = balance
            return balance

        except Exception as e:
            logger.error(f"Failed to get balance for {wallet_type.value}: {e}")
            return self._balances.get(wallet_type)

    async def get_all_balances(self) -> Dict[WalletType, WalletBalance]:
        """Get balances for all managed wallets."""
        for wallet_type in self.wallets:
            await self.get_balance(wallet_type)

        return self._balances

    async def get_total_balance(self) -> int:
        """Get total SOL balance across all wallets (in lamports)."""
        balances = await self.get_all_balances()
        return sum(b.sol_balance for b in balances.values())

    async def check_allocation(self) -> Dict[WalletType, Dict[str, float]]:
        """
        Check current allocation vs targets.

        Returns:
            Dict with current vs target percentages
        """
        balances = await self.get_all_balances()
        total = sum(b.sol_balance for b in balances.values())

        if total == 0:
            return {}

        result = {}
        for wallet_type, balance in balances.items():
            allocation = self.allocations.get(wallet_type)
            current_pct = balance.sol_balance / total

            result[wallet_type] = {
                "current_balance": balance.sol_balance,
                "current_percentage": current_pct,
                "target_percentage": allocation.target_percentage if allocation else 0,
                "deviation": current_pct - (allocation.target_percentage if allocation else 0),
            }

        return result

    async def needs_rebalance(self, threshold: float = 0.05) -> bool:
        """
        Check if rebalancing is needed.

        Args:
            threshold: Maximum acceptable deviation from target

        Returns:
            True if any wallet exceeds threshold
        """
        allocation_status = await self.check_allocation()

        for wallet_type, status in allocation_status.items():
            if abs(status["deviation"]) > threshold:
                return True

        return False

    async def calculate_rebalance(self) -> List[Dict[str, Any]]:
        """
        Calculate required transfers to rebalance.

        Returns:
            List of transfer instructions
        """
        allocation_status = await self.check_allocation()
        total = sum(s["current_balance"] for s in allocation_status.values())

        transfers = []

        # Find wallets that need to send/receive
        senders = []
        receivers = []

        for wallet_type, status in allocation_status.items():
            allocation = self.allocations.get(wallet_type)
            if not allocation:
                continue

            target_balance = int(total * allocation.target_percentage)
            diff = target_balance - status["current_balance"]

            if diff < 0:  # Has excess
                senders.append((wallet_type, -diff))
            elif diff > 0:  # Needs more
                receivers.append((wallet_type, diff))

        # Match senders to receivers
        for sender_type, excess in senders:
            for i, (receiver_type, needed) in enumerate(receivers):
                if excess <= 0:
                    break
                if needed <= 0:
                    continue

                transfer_amount = min(excess, needed)

                sender = self.wallets.get(sender_type)
                receiver = self.wallets.get(receiver_type)

                if sender and receiver:
                    transfers.append({
                        "from_wallet": sender_type.value,
                        "from_address": sender.address,
                        "to_wallet": receiver_type.value,
                        "to_address": receiver.address,
                        "amount_lamports": transfer_amount,
                        "amount_sol": transfer_amount / LAMPORTS_PER_SOL,
                        "requires_multisig": sender.is_multisig,
                    })

                excess -= transfer_amount
                receivers[i] = (receiver_type, needed - transfer_amount)

        return transfers

    async def execute_transfer(
        self,
        from_wallet: WalletType,
        to_address: str,
        amount_lamports: int,
        memo: str = "",
    ) -> Optional[str]:
        """
        Execute a SOL transfer.

        Args:
            from_wallet: Source wallet type
            to_address: Destination address
            amount_lamports: Amount in lamports
            memo: Optional memo

        Returns:
            Transaction signature or None if failed
        """
        wallet = self.wallets.get(from_wallet)
        if not wallet:
            raise ValueError(f"Wallet not found: {from_wallet}")

        if wallet.is_multisig:
            return await self._create_multisig_transfer(wallet, to_address, amount_lamports, memo)
        else:
            return await self._execute_direct_transfer(wallet, to_address, amount_lamports, memo)

    async def _fetch_sol_balance(self, address: str) -> int:
        """Fetch SOL balance from RPC."""
        try:
            from solana.rpc.async_api import AsyncClient
            from solders.pubkey import Pubkey

            async with AsyncClient(self.rpc_url) as client:
                pubkey = Pubkey.from_string(address)
                response = await client.get_balance(pubkey)
                return response.value

        except ImportError:
            logger.warning("Solana SDK not installed")
            return 0
        except Exception as e:
            logger.error(f"Failed to fetch balance: {e}")
            return 0

    async def _fetch_token_balances(self, address: str) -> Dict[str, int]:
        """Fetch token balances for an address."""
        try:
            from solana.rpc.async_api import AsyncClient
            from solders.pubkey import Pubkey

            async with AsyncClient(self.rpc_url) as client:
                pubkey = Pubkey.from_string(address)
                response = await client.get_token_accounts_by_owner_json_parsed(pubkey)

                balances = {}
                for account in response.value:
                    info = account.account.data.parsed["info"]
                    mint = info["mint"]
                    amount = int(info["tokenAmount"]["amount"])
                    balances[mint] = amount

                return balances

        except ImportError:
            return {}
        except Exception as e:
            logger.error(f"Failed to fetch token balances: {e}")
            return {}

    async def _execute_direct_transfer(
        self,
        wallet: TreasuryWallet,
        to_address: str,
        amount_lamports: int,
        memo: str,
    ) -> Optional[str]:
        """Execute direct SOL transfer (hot wallet)."""
        try:
            from solana.rpc.async_api import AsyncClient
            from solana.transaction import Transaction
            from solders.keypair import Keypair
            from solders.pubkey import Pubkey
            from solders.system_program import transfer, TransferParams
            import json

            if not wallet.keypair_path:
                raise ValueError("Keypair path not configured for hot wallet")

            # Load keypair
            with open(wallet.keypair_path) as f:
                secret = json.load(f)
            keypair = Keypair.from_bytes(bytes(secret))

            # Create transfer instruction
            from_pubkey = Pubkey.from_string(wallet.address)
            to_pubkey = Pubkey.from_string(to_address)

            transfer_ix = transfer(TransferParams(
                from_pubkey=from_pubkey,
                to_pubkey=to_pubkey,
                lamports=amount_lamports,
            ))

            # Build and send transaction
            async with AsyncClient(self.rpc_url) as client:
                blockhash = (await client.get_latest_blockhash()).value.blockhash

                tx = Transaction()
                tx.recent_blockhash = blockhash
                tx.add(transfer_ix)
                tx.sign(keypair)

                result = await client.send_transaction(tx)
                signature = str(result.value)

                logger.info(f"Transfer executed: {amount_lamports} lamports, tx: {signature}")
                return signature

        except Exception as e:
            logger.error(f"Transfer failed: {e}")
            return None

    async def _create_multisig_transfer(
        self,
        wallet: TreasuryWallet,
        to_address: str,
        amount_lamports: int,
        memo: str,
    ) -> Optional[str]:
        """Create multisig transfer proposal (Squads)."""
        # This would integrate with Squads SDK
        # For now, return a placeholder
        logger.info(
            f"Multisig transfer proposal: {amount_lamports} lamports "
            f"from {wallet.address} to {to_address}"
        )

        # Would return proposal ID instead of signature
        return f"proposal_{int(datetime.now().timestamp())}"

    def get_wallet_status(self) -> Dict[str, Any]:
        """Get status of all wallets."""
        return {
            "wallets": {
                wt.value: w.to_dict()
                for wt, w in self.wallets.items()
            },
            "balances": {
                wt.value: b.to_dict()
                for wt, b in self._balances.items()
            },
            "allocations": {
                wt.value: {
                    "target_percentage": a.target_percentage,
                    "min_balance_sol": a.min_balance_sol,
                    "max_balance_sol": a.max_balance_sol,
                    "requires_multisig": a.requires_multisig,
                }
                for wt, a in self.allocations.items()
            },
            "last_rebalance": self._last_rebalance.isoformat() if self._last_rebalance else None,
        }
