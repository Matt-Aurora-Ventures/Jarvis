"""
Copy Trade Executor

Handles the actual execution of copy trades.
Includes position sizing, slippage protection, and execution tracking.

WARNING: This module is DISABLED by default. Real money operations
require full security audit before enabling.

Prompts #103-106: Copy Trading Service
"""

import asyncio
import logging
import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List, Any, Callable
from enum import Enum
from pathlib import Path

from .leader import LeaderManager, get_leader_manager
from .follower import (
    FollowerManager,
    Follower,
    FollowConfig,
    CopyMode,
    get_follower_manager
)

logger = logging.getLogger(__name__)

# SAFETY: Master kill switch
COPY_TRADING_ENABLED = False  # SET TO FALSE UNTIL FULLY AUDITED


class CopyTradeStatus(str, Enum):
    """Status of a copy trade"""
    PENDING = "pending"
    QUEUED = "queued"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class FailureReason(str, Enum):
    """Reason for copy trade failure"""
    DISABLED = "copy_trading_disabled"
    INSUFFICIENT_BALANCE = "insufficient_balance"
    SLIPPAGE_TOO_HIGH = "slippage_too_high"
    TOKEN_BLOCKED = "token_blocked"
    DAILY_LIMIT_REACHED = "daily_limit_reached"
    POSITION_LIMIT_REACHED = "position_limit_reached"
    EXECUTION_ERROR = "execution_error"
    TIMEOUT = "timeout"
    LEADER_NOT_FOUND = "leader_not_found"
    FOLLOWER_NOT_FOUND = "follower_not_found"


@dataclass
class LeaderTrade:
    """A trade executed by a leader"""
    trade_id: str
    leader_id: str
    token_in: str
    token_out: str
    amount_in: float
    amount_out: float
    price: float
    is_buy: bool
    timestamp: datetime = field(default_factory=datetime.now)
    tx_hash: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "trade_id": self.trade_id,
            "leader_id": self.leader_id,
            "token_in": self.token_in,
            "token_out": self.token_out,
            "amount_in": self.amount_in,
            "amount_out": self.amount_out,
            "price": self.price,
            "is_buy": self.is_buy,
            "timestamp": self.timestamp.isoformat(),
            "tx_hash": self.tx_hash
        }


@dataclass
class CopyTrade:
    """A copied trade execution"""
    copy_id: str
    leader_trade_id: str
    follower_id: str
    leader_id: str
    status: CopyTradeStatus = CopyTradeStatus.PENDING

    # Trade details
    token_in: str = ""
    token_out: str = ""
    intended_amount: float = 0.0
    executed_amount: float = 0.0
    price: float = 0.0
    slippage: float = 0.0

    # Results
    pnl: float = 0.0
    fees: float = 0.0
    profit_shared: float = 0.0

    # Metadata
    failure_reason: Optional[FailureReason] = None
    error_message: Optional[str] = None
    tx_hash: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    executed_at: Optional[datetime] = None

    def __post_init__(self):
        if not self.copy_id:
            data = f"{self.leader_trade_id}{self.follower_id}{self.created_at.isoformat()}"
            self.copy_id = f"COPY-{hashlib.sha256(data.encode()).hexdigest()[:12].upper()}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "copy_id": self.copy_id,
            "leader_trade_id": self.leader_trade_id,
            "follower_id": self.follower_id,
            "leader_id": self.leader_id,
            "status": self.status.value,
            "token_in": self.token_in,
            "token_out": self.token_out,
            "intended_amount": self.intended_amount,
            "executed_amount": self.executed_amount,
            "price": self.price,
            "slippage": self.slippage,
            "pnl": self.pnl,
            "fees": self.fees,
            "profit_shared": self.profit_shared,
            "failure_reason": self.failure_reason.value if self.failure_reason else None,
            "error_message": self.error_message,
            "tx_hash": self.tx_hash,
            "created_at": self.created_at.isoformat(),
            "executed_at": self.executed_at.isoformat() if self.executed_at else None
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CopyTrade":
        """Create from dictionary"""
        return cls(
            copy_id=data["copy_id"],
            leader_trade_id=data["leader_trade_id"],
            follower_id=data["follower_id"],
            leader_id=data["leader_id"],
            status=CopyTradeStatus(data.get("status", "pending")),
            token_in=data.get("token_in", ""),
            token_out=data.get("token_out", ""),
            intended_amount=data.get("intended_amount", 0.0),
            executed_amount=data.get("executed_amount", 0.0),
            price=data.get("price", 0.0),
            slippage=data.get("slippage", 0.0),
            pnl=data.get("pnl", 0.0),
            fees=data.get("fees", 0.0),
            profit_shared=data.get("profit_shared", 0.0),
            failure_reason=FailureReason(data["failure_reason"]) if data.get("failure_reason") else None,
            error_message=data.get("error_message"),
            tx_hash=data.get("tx_hash"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            executed_at=datetime.fromisoformat(data["executed_at"]) if data.get("executed_at") else None
        )


class TradeCopier:
    """
    Executes copy trades for followers

    WARNING: This class handles real money operations.
    COPY_TRADING_ENABLED must be True for any execution.
    """

    def __init__(
        self,
        leader_manager: Optional[LeaderManager] = None,
        follower_manager: Optional[FollowerManager] = None,
        storage_path: str = "data/copy_trading/copies.json",
        swap_executor: Optional[Callable] = None
    ):
        self.leader_manager = leader_manager or get_leader_manager()
        self.follower_manager = follower_manager or get_follower_manager()
        self.storage_path = Path(storage_path)
        self.swap_executor = swap_executor  # Injected swap function
        self.copy_trades: Dict[str, CopyTrade] = {}
        self.pending_queue: List[str] = []
        self._load()

    def _load(self):
        """Load copy trades from storage"""
        if not self.storage_path.exists():
            return

        try:
            with open(self.storage_path) as f:
                data = json.load(f)

            for copy_data in data.get("copies", []):
                copy = CopyTrade.from_dict(copy_data)
                self.copy_trades[copy.copy_id] = copy

            logger.info(f"Loaded {len(self.copy_trades)} copy trades")

        except Exception as e:
            logger.error(f"Failed to load copy trades: {e}")

    def _save(self):
        """Save copy trades to storage"""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "copies": [c.to_dict() for c in self.copy_trades.values()],
                "updated_at": datetime.now().isoformat()
            }

            with open(self.storage_path, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save copy trades: {e}")
            raise

    async def process_leader_trade(self, trade: LeaderTrade) -> List[CopyTrade]:
        """
        Process a new leader trade and create copies for followers

        Returns list of created copy trades.
        """
        # SAFETY CHECK
        if not COPY_TRADING_ENABLED:
            logger.warning("Copy trading is DISABLED - no copies will be executed")
            return []

        # Get leader
        leader = await self.leader_manager.get_leader(trade.leader_id)
        if not leader:
            logger.error(f"Leader {trade.leader_id} not found")
            return []

        # Get followers
        followers = await self.follower_manager.get_followers_of_leader(trade.leader_id)
        if not followers:
            logger.debug(f"No active followers for leader {trade.leader_id}")
            return []

        # Create copy trades for each follower
        copies = []
        for follower in followers:
            copy = await self._create_copy_trade(follower, trade, leader.profit_share_percent)
            if copy:
                copies.append(copy)

        return copies

    async def _create_copy_trade(
        self,
        follower: Follower,
        leader_trade: LeaderTrade,
        profit_share_percent: float
    ) -> Optional[CopyTrade]:
        """Create a copy trade for a single follower"""
        config = follower.following.get(leader_trade.leader_id)
        if not config:
            return None

        # Check if follower can copy this trade
        can_copy, reason = follower.can_copy_trade(leader_trade.leader_id)
        if not can_copy:
            copy = CopyTrade(
                copy_id="",
                leader_trade_id=leader_trade.trade_id,
                follower_id=follower.follower_id,
                leader_id=leader_trade.leader_id,
                status=CopyTradeStatus.SKIPPED,
                token_in=leader_trade.token_in,
                token_out=leader_trade.token_out,
                error_message=reason
            )
            self.copy_trades[copy.copy_id] = copy
            self._save()
            return copy

        # Check trade type filter
        if leader_trade.is_buy and not config.copy_buys:
            return None
        if not leader_trade.is_buy and not config.copy_sells:
            return None

        # Check token filter
        target_token = leader_trade.token_out if leader_trade.is_buy else leader_trade.token_in
        if config.allowed_tokens and target_token not in config.allowed_tokens:
            return None
        if target_token in config.blocked_tokens:
            return None

        # Calculate copy amount
        copy_amount = self._calculate_copy_amount(config, leader_trade)
        if copy_amount < config.min_trade_amount:
            return None

        # Create copy trade
        copy = CopyTrade(
            copy_id="",
            leader_trade_id=leader_trade.trade_id,
            follower_id=follower.follower_id,
            leader_id=leader_trade.leader_id,
            status=CopyTradeStatus.QUEUED,
            token_in=leader_trade.token_in,
            token_out=leader_trade.token_out,
            intended_amount=copy_amount
        )

        self.copy_trades[copy.copy_id] = copy
        self.pending_queue.append(copy.copy_id)
        self._save()

        logger.info(f"Queued copy trade {copy.copy_id} for follower {follower.follower_id}")

        # Handle delay if configured
        if config.delay_seconds > 0:
            asyncio.create_task(self._delayed_execute(copy.copy_id, config.delay_seconds))
        else:
            asyncio.create_task(self._execute_copy(copy.copy_id))

        return copy

    def _calculate_copy_amount(
        self,
        config: FollowConfig,
        leader_trade: LeaderTrade
    ) -> float:
        """Calculate the amount to copy based on config"""
        multiplier = config.get_position_multiplier()

        if config.copy_mode == CopyMode.FIXED_AMOUNT:
            amount = config.fixed_amount * multiplier

        elif config.copy_mode == CopyMode.PERCENTAGE:
            # Would need to query follower's portfolio value
            amount = config.fixed_amount * (config.percentage / 100) * multiplier

        elif config.copy_mode == CopyMode.PROPORTIONAL:
            # Match leader's position ratio
            amount = leader_trade.amount_in * multiplier

        else:  # MIRROR
            amount = leader_trade.amount_in

        # Apply maximum
        return min(amount, config.max_position_size)

    async def _delayed_execute(self, copy_id: str, delay_seconds: int):
        """Execute a copy trade after a delay"""
        await asyncio.sleep(delay_seconds)
        await self._execute_copy(copy_id)

    async def _execute_copy(self, copy_id: str):
        """Execute a single copy trade"""
        copy = self.copy_trades.get(copy_id)
        if not copy or copy.status != CopyTradeStatus.QUEUED:
            return

        # SAFETY CHECK
        if not COPY_TRADING_ENABLED:
            copy.status = CopyTradeStatus.FAILED
            copy.failure_reason = FailureReason.DISABLED
            copy.error_message = "Copy trading is globally disabled"
            self._save()
            return

        copy.status = CopyTradeStatus.EXECUTING
        self._save()

        try:
            # Check if we have a swap executor
            if not self.swap_executor:
                raise Exception("No swap executor configured")

            # Execute the swap
            result = await self.swap_executor(
                token_in=copy.token_in,
                token_out=copy.token_out,
                amount=copy.intended_amount,
                max_slippage=0.01  # 1% max slippage
            )

            if result.get("success"):
                copy.status = CopyTradeStatus.COMPLETED
                copy.executed_amount = result.get("amount_out", 0)
                copy.price = result.get("price", 0)
                copy.slippage = result.get("slippage", 0)
                copy.fees = result.get("fees", 0)
                copy.tx_hash = result.get("tx_hash")
                copy.executed_at = datetime.now()

                # Record in follower stats
                await self.follower_manager.record_copy_result(
                    copy.follower_id,
                    success=True,
                    fees=copy.fees
                )

                logger.info(f"Copy trade {copy_id} completed successfully")

            else:
                copy.status = CopyTradeStatus.FAILED
                copy.failure_reason = FailureReason.EXECUTION_ERROR
                copy.error_message = result.get("error", "Unknown error")

                await self.follower_manager.record_copy_result(
                    copy.follower_id,
                    success=False
                )

        except Exception as e:
            copy.status = CopyTradeStatus.FAILED
            copy.failure_reason = FailureReason.EXECUTION_ERROR
            copy.error_message = str(e)
            logger.error(f"Copy trade {copy_id} failed: {e}")

            await self.follower_manager.record_copy_result(
                copy.follower_id,
                success=False
            )

        # Remove from queue
        if copy_id in self.pending_queue:
            self.pending_queue.remove(copy_id)

        self._save()

    async def cancel_copy(self, copy_id: str) -> bool:
        """Cancel a pending copy trade"""
        copy = self.copy_trades.get(copy_id)
        if not copy:
            return False

        if copy.status not in [CopyTradeStatus.PENDING, CopyTradeStatus.QUEUED]:
            return False

        copy.status = CopyTradeStatus.CANCELLED
        if copy_id in self.pending_queue:
            self.pending_queue.remove(copy_id)

        self._save()
        return True

    async def get_copy_trade(self, copy_id: str) -> Optional[CopyTrade]:
        """Get a copy trade by ID"""
        return self.copy_trades.get(copy_id)

    async def get_follower_copies(
        self,
        follower_id: str,
        status: Optional[CopyTradeStatus] = None,
        limit: int = 100
    ) -> List[CopyTrade]:
        """Get copy trades for a follower"""
        copies = [
            c for c in self.copy_trades.values()
            if c.follower_id == follower_id
        ]

        if status:
            copies = [c for c in copies if c.status == status]

        copies.sort(key=lambda c: c.created_at, reverse=True)
        return copies[:limit]

    async def get_leader_copies(
        self,
        leader_id: str,
        limit: int = 100
    ) -> List[CopyTrade]:
        """Get all copy trades for a leader's trades"""
        copies = [
            c for c in self.copy_trades.values()
            if c.leader_id == leader_id
        ]

        copies.sort(key=lambda c: c.created_at, reverse=True)
        return copies[:limit]

    def get_stats(self) -> Dict[str, Any]:
        """Get copy trading statistics"""
        total = len(self.copy_trades)
        by_status = {}

        for copy in self.copy_trades.values():
            status = copy.status.value
            by_status[status] = by_status.get(status, 0) + 1

        total_volume = sum(c.executed_amount for c in self.copy_trades.values() if c.status == CopyTradeStatus.COMPLETED)
        total_fees = sum(c.fees for c in self.copy_trades.values())

        return {
            "enabled": COPY_TRADING_ENABLED,
            "total_copy_trades": total,
            "by_status": by_status,
            "pending_queue_size": len(self.pending_queue),
            "total_copied_volume": total_volume,
            "total_fees_collected": total_fees
        }


# Singleton instance
_trade_copier: Optional[TradeCopier] = None


def get_trade_copier() -> TradeCopier:
    """Get trade copier singleton"""
    global _trade_copier

    if _trade_copier is None:
        _trade_copier = TradeCopier()

    return _trade_copier


# Testing
if __name__ == "__main__":
    async def test():
        # Mock swap executor
        async def mock_swap(token_in, token_out, amount, max_slippage):
            return {
                "success": True,
                "amount_out": amount * 0.99,
                "price": 1.0,
                "slippage": 0.01,
                "fees": amount * 0.003,
                "tx_hash": "MOCK_TX_123"
            }

        copier = TradeCopier(
            storage_path="test_copies.json",
            swap_executor=mock_swap
        )

        print(f"Copy trading enabled: {COPY_TRADING_ENABLED}")
        print(f"Stats: {copier.get_stats()}")

        # In real usage, trades would be processed like:
        # leader_trade = LeaderTrade(...)
        # copies = await copier.process_leader_trade(leader_trade)

        # Clean up
        import os
        if os.path.exists("test_copies.json"):
            os.remove("test_copies.json")

    asyncio.run(test())
