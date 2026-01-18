"""
User Wallet Management - Track and manage user earnings.

Features:
- Track earned fees per user
- Request and process withdrawals
- Daily withdrawal limit enforcement ($1000)
- Transaction history
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


DAILY_WITHDRAWAL_LIMIT = 1000.0  # $1000 daily limit


@dataclass
class Transaction:
    """A wallet transaction."""
    id: str
    user_id: str
    type: str  # 'deposit' or 'withdrawal'
    amount: float
    status: str  # 'completed', 'pending', 'failed'
    timestamp: float = field(default_factory=time.time)
    tx_hash: Optional[str] = None
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class WithdrawalRequest:
    """A withdrawal request."""
    id: str
    user_id: str
    amount: float
    status: str  # 'pending', 'processing', 'completed', 'failed'
    wallet_address: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    tx_hash: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class UserWalletManager:
    """
    Manages user wallet balances and withdrawals.

    Usage:
        manager = UserWalletManager()

        # Add earnings
        manager.deposit_earnings("user_1", 10.0)

        # Check balance
        balance = manager.get_balance("user_1")

        # Request withdrawal
        request = manager.request_withdrawal("user_1", 50.0)
    """

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir:
            self.data_dir = Path(data_dir)
        else:
            self.data_dir = Path.home() / ".lifeos" / "revenue"

        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.wallets_file = self.data_dir / "user_wallets.json"
        self.transactions_file = self.data_dir / "transactions.jsonl"
        self.withdrawals_file = self.data_dir / "withdrawals.json"

        # Load state
        self._wallets = self._load_wallets()
        self._pending_withdrawals: Dict[str, WithdrawalRequest] = self._load_withdrawals()

    def _load_wallets(self) -> Dict[str, float]:
        """Load wallet balances from file."""
        if self.wallets_file.exists():
            try:
                data = json.loads(self.wallets_file.read_text())
                return {k: float(v) for k, v in data.items() if k != '_metadata'}
            except json.JSONDecodeError:
                return {}
        return {}

    def _save_wallets(self) -> None:
        """Save wallet balances to file."""
        data = {**self._wallets, '_metadata': {'updated_at': time.time()}}
        self.wallets_file.write_text(json.dumps(data, indent=2))

    def _load_withdrawals(self) -> Dict[str, WithdrawalRequest]:
        """Load pending withdrawals."""
        if self.withdrawals_file.exists():
            try:
                data = json.loads(self.withdrawals_file.read_text())
                return {
                    k: WithdrawalRequest(**v)
                    for k, v in data.items()
                    if k != '_metadata'
                }
            except json.JSONDecodeError:
                return {}
        return {}

    def _save_withdrawals(self) -> None:
        """Save pending withdrawals."""
        data = {
            k: v.to_dict() for k, v in self._pending_withdrawals.items()
        }
        data['_metadata'] = {'updated_at': time.time()}
        self.withdrawals_file.write_text(json.dumps(data, indent=2))

    def _record_transaction(self, tx: Transaction) -> None:
        """Record a transaction to the log."""
        with open(self.transactions_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(tx.to_dict()) + "\n")

    def deposit_earnings(self, user_id: str, amount: float) -> float:
        """
        Deposit earnings to user's wallet.

        Args:
            user_id: User identifier
            amount: Amount to deposit

        Returns:
            New balance
        """
        if amount <= 0:
            raise ValueError("Deposit amount must be positive")

        current = self._wallets.get(user_id, 0.0)
        new_balance = current + amount
        self._wallets[user_id] = round(new_balance, 6)

        # Record transaction
        tx = Transaction(
            id=f"tx_{int(time.time() * 1000)}_{user_id[:8]}",
            user_id=user_id,
            type='deposit',
            amount=amount,
            status='completed',
            description=f"Fee earnings deposit: ${amount:.6f}"
        )
        self._record_transaction(tx)

        # Persist
        self._save_wallets()

        return self._wallets[user_id]

    def get_balance(self, user_id: str) -> float:
        """
        Get user's current balance.

        Args:
            user_id: User identifier

        Returns:
            Current balance (0 if no wallet)
        """
        return self._wallets.get(user_id, 0.0)

    def _get_daily_withdrawn(self, user_id: str) -> float:
        """Get total withdrawn today for a user."""
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        ).timestamp()

        total = 0.0

        if self.transactions_file.exists():
            with open(self.transactions_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        if (
                            data.get('user_id') == user_id and
                            data.get('type') == 'withdrawal' and
                            data.get('status') == 'completed' and
                            data.get('timestamp', 0) >= today_start
                        ):
                            total += data.get('amount', 0)
                    except json.JSONDecodeError:
                        continue

        # Also count pending withdrawals from today
        for req in self._pending_withdrawals.values():
            if (
                req.user_id == user_id and
                req.status in ('pending', 'processing') and
                req.timestamp >= today_start
            ):
                total += req.amount

        return total

    def request_withdrawal(
        self,
        user_id: str,
        amount: float,
        wallet_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Request a withdrawal.

        Args:
            user_id: User identifier
            amount: Amount to withdraw
            wallet_address: Destination wallet address

        Returns:
            Withdrawal request details

        Raises:
            ValueError: If insufficient balance or daily limit exceeded
        """
        balance = self.get_balance(user_id)

        if amount > balance:
            raise ValueError(f"Insufficient balance: ${balance:.2f} available, ${amount:.2f} requested")

        # Check daily limit
        daily_withdrawn = self._get_daily_withdrawn(user_id)
        if daily_withdrawn + amount > DAILY_WITHDRAWAL_LIMIT:
            remaining = DAILY_WITHDRAWAL_LIMIT - daily_withdrawn
            raise ValueError(
                f"Exceeds daily withdrawal limit: ${DAILY_WITHDRAWAL_LIMIT:.2f}. "
                f"Remaining today: ${remaining:.2f}"
            )

        # Create request
        request = WithdrawalRequest(
            id=f"wd_{int(time.time() * 1000)}_{user_id[:8]}",
            user_id=user_id,
            amount=amount,
            status='pending',
            wallet_address=wallet_address,
        )

        # Store pending request
        self._pending_withdrawals[request.id] = request
        self._save_withdrawals()

        return request.to_dict()

    def process_withdrawal(
        self,
        withdrawal_id: str,
        tx_hash: str
    ) -> Dict[str, Any]:
        """
        Process a pending withdrawal.

        Args:
            withdrawal_id: Withdrawal request ID
            tx_hash: Blockchain transaction hash

        Returns:
            Updated withdrawal request
        """
        if withdrawal_id not in self._pending_withdrawals:
            raise ValueError(f"Withdrawal request not found: {withdrawal_id}")

        request = self._pending_withdrawals[withdrawal_id]

        # Deduct from balance
        current = self._wallets.get(request.user_id, 0.0)
        if current < request.amount:
            request.status = 'failed'
            self._save_withdrawals()
            raise ValueError("Insufficient balance during processing")

        self._wallets[request.user_id] = round(current - request.amount, 6)
        self._save_wallets()

        # Update request
        request.status = 'completed'
        request.tx_hash = tx_hash
        self._save_withdrawals()

        # Record transaction
        tx = Transaction(
            id=f"tx_{int(time.time() * 1000)}_{request.user_id[:8]}",
            user_id=request.user_id,
            type='withdrawal',
            amount=request.amount,
            status='completed',
            tx_hash=tx_hash,
            description=f"Withdrawal to {request.wallet_address or 'unknown'}"
        )
        self._record_transaction(tx)

        return request.to_dict()

    def get_transaction_history(
        self,
        user_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get transaction history for a user.

        Args:
            user_id: User identifier
            limit: Maximum number of transactions

        Returns:
            List of transactions (newest first)
        """
        transactions: List[Dict[str, Any]] = []

        if self.transactions_file.exists():
            with open(self.transactions_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        if data.get('user_id') == user_id:
                            transactions.append(data)
                    except json.JSONDecodeError:
                        continue

        # Sort by timestamp descending and limit
        transactions.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        return transactions[:limit]

    def get_all_balances(self) -> Dict[str, float]:
        """Get all user balances."""
        return {k: v for k, v in self._wallets.items() if not k.startswith('_')}
