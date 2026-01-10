"""
Squads Multisig Integration
Prompt #81: Treasury wallet architecture with Squads v4 multisig

Provides secure multisig operations for treasury reserve wallet.
"""

import asyncio
import base64
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
import struct

logger = logging.getLogger("jarvis.treasury.squads")


# =============================================================================
# CONSTANTS
# =============================================================================

# Squads v4 Program ID
SQUADS_V4_PROGRAM_ID = "SQDS4ep65T869zMMBKyuUq6aD6EgTu8psMjkvj52pCf"

# Transaction states
TX_STATE_ACTIVE = 0
TX_STATE_EXECUTED = 1
TX_STATE_REJECTED = 2
TX_STATE_CANCELLED = 3

# Timelock for high-value transactions (in seconds)
HIGH_VALUE_THRESHOLD_SOL = 100  # Transactions > 100 SOL require timelock
TIMELOCK_DURATION_SECONDS = 86400  # 24 hours


# =============================================================================
# MODELS
# =============================================================================

class MultisigRole(str, Enum):
    """Member roles in multisig"""
    MEMBER = "member"          # Can vote
    PROPOSER = "proposer"      # Can propose + vote
    EXECUTOR = "executor"      # Can execute approved txs
    ADMIN = "admin"            # Full permissions


class TransactionStatus(str, Enum):
    """Status of a multisig transaction"""
    DRAFT = "draft"
    ACTIVE = "active"
    APPROVED = "approved"
    TIMELOCKED = "timelocked"
    EXECUTED = "executed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


@dataclass
class SquadsConfig:
    """Configuration for Squads multisig"""
    multisig_address: str
    program_id: str = SQUADS_V4_PROGRAM_ID
    threshold: int = 2
    members: List[str] = field(default_factory=list)
    timelock_seconds: int = TIMELOCK_DURATION_SECONDS
    high_value_threshold_lamports: int = HIGH_VALUE_THRESHOLD_SOL * 1_000_000_000

    @classmethod
    def from_env(cls) -> "SquadsConfig":
        """Load config from environment"""
        members = os.getenv("SQUADS_MEMBERS", "").split(",")
        members = [m.strip() for m in members if m.strip()]

        return cls(
            multisig_address=os.getenv("SQUADS_MULTISIG_ADDRESS", ""),
            program_id=os.getenv("SQUADS_PROGRAM_ID", SQUADS_V4_PROGRAM_ID),
            threshold=int(os.getenv("SQUADS_THRESHOLD", "2")),
            members=members,
            timelock_seconds=int(os.getenv("SQUADS_TIMELOCK_SECONDS", str(TIMELOCK_DURATION_SECONDS))),
        )


@dataclass
class MultisigMember:
    """A member of the multisig"""
    pubkey: str
    role: MultisigRole
    added_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True
    last_vote: Optional[datetime] = None


@dataclass
class MultisigTransaction:
    """A pending multisig transaction"""
    id: str
    index: int
    creator: str
    status: TransactionStatus
    created_at: datetime

    # Transaction details
    instructions: List[Dict[str, Any]]
    description: str
    amount_lamports: int = 0
    destination: Optional[str] = None

    # Voting
    approvals: List[str] = field(default_factory=list)
    rejections: List[str] = field(default_factory=list)
    threshold: int = 2

    # Timelock
    requires_timelock: bool = False
    timelock_ends: Optional[datetime] = None

    # Execution
    executed_at: Optional[datetime] = None
    signature: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "index": self.index,
            "creator": self.creator,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "description": self.description,
            "amount_lamports": self.amount_lamports,
            "destination": self.destination,
            "approvals": self.approvals,
            "rejections": self.rejections,
            "threshold": self.threshold,
            "requires_timelock": self.requires_timelock,
            "timelock_ends": self.timelock_ends.isoformat() if self.timelock_ends else None,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "signature": self.signature,
        }


@dataclass
class MultisigState:
    """Current state of the multisig"""
    address: str
    threshold: int
    member_count: int
    transaction_index: int
    pending_transactions: int
    total_executed: int
    balance_lamports: int


# =============================================================================
# SQUADS CLIENT
# =============================================================================

class SquadsClient:
    """
    Client for Squads v4 multisig operations.

    Handles:
    - Transaction creation and proposal
    - Approval collection
    - Execution after threshold met
    - Timelock enforcement for high-value txs
    """

    def __init__(self, config: SquadsConfig = None, rpc_url: str = None):
        self.config = config or SquadsConfig.from_env()
        self.rpc_url = rpc_url or os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")

        # In-memory cache (would be database in production)
        self._transactions: Dict[str, MultisigTransaction] = {}
        self._members: Dict[str, MultisigMember] = {}
        self._transaction_index = 0

        self._initialize_members()

    def _initialize_members(self):
        """Initialize member list from config"""
        for pubkey in self.config.members:
            self._members[pubkey] = MultisigMember(
                pubkey=pubkey,
                role=MultisigRole.MEMBER,
            )

    # =========================================================================
    # TRANSACTION CREATION
    # =========================================================================

    async def create_transaction(
        self,
        instructions: List[Dict[str, Any]],
        description: str,
        creator: str,
        amount_lamports: int = 0,
        destination: Optional[str] = None,
    ) -> MultisigTransaction:
        """
        Create a new multisig transaction proposal.

        Args:
            instructions: List of instruction data
            description: Human-readable description
            creator: Pubkey of the proposer
            amount_lamports: Amount being transferred (for display)
            destination: Destination address (for display)

        Returns:
            The created transaction
        """
        import uuid

        # Validate creator is a member
        if creator not in self._members:
            raise ValueError(f"Creator {creator} is not a multisig member")

        member = self._members[creator]
        if member.role not in [MultisigRole.PROPOSER, MultisigRole.ADMIN]:
            # Regular members can't propose, only vote
            raise ValueError(f"Member {creator} does not have propose permissions")

        self._transaction_index += 1
        tx_id = str(uuid.uuid4())[:8]

        # Check if timelock required
        requires_timelock = amount_lamports > self.config.high_value_threshold_lamports

        tx = MultisigTransaction(
            id=tx_id,
            index=self._transaction_index,
            creator=creator,
            status=TransactionStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
            instructions=instructions,
            description=description,
            amount_lamports=amount_lamports,
            destination=destination,
            threshold=self.config.threshold,
            requires_timelock=requires_timelock,
        )

        # Creator auto-approves
        tx.approvals.append(creator)

        self._transactions[tx_id] = tx

        logger.info(f"Created multisig transaction {tx_id}: {description}")
        return tx

    async def create_transfer_transaction(
        self,
        destination: str,
        amount_lamports: int,
        creator: str,
        memo: str = "",
    ) -> MultisigTransaction:
        """
        Create a SOL transfer transaction.

        Args:
            destination: Recipient address
            amount_lamports: Amount to transfer
            creator: Proposer pubkey
            memo: Optional memo

        Returns:
            The created transaction
        """
        instructions = [
            {
                "program_id": "11111111111111111111111111111111",  # System program
                "accounts": [
                    {"pubkey": self.config.multisig_address, "is_signer": True, "is_writable": True},
                    {"pubkey": destination, "is_signer": False, "is_writable": True},
                ],
                "data": self._encode_transfer_data(amount_lamports),
            }
        ]

        if memo:
            instructions.append({
                "program_id": "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr",
                "accounts": [],
                "data": base64.b64encode(memo.encode()).decode(),
            })

        return await self.create_transaction(
            instructions=instructions,
            description=f"Transfer {amount_lamports / 1e9:.4f} SOL to {destination[:8]}...",
            creator=creator,
            amount_lamports=amount_lamports,
            destination=destination,
        )

    def _encode_transfer_data(self, amount: int) -> str:
        """Encode transfer instruction data"""
        # System program transfer instruction: discriminator (4 bytes) + amount (8 bytes)
        data = struct.pack("<I", 2) + struct.pack("<Q", amount)
        return base64.b64encode(data).decode()

    # =========================================================================
    # VOTING
    # =========================================================================

    async def approve_transaction(
        self,
        tx_id: str,
        signer: str,
    ) -> MultisigTransaction:
        """
        Approve a pending transaction.

        Args:
            tx_id: Transaction ID
            signer: Pubkey of the approver

        Returns:
            Updated transaction
        """
        tx = self._transactions.get(tx_id)
        if not tx:
            raise ValueError(f"Transaction {tx_id} not found")

        if tx.status != TransactionStatus.ACTIVE:
            raise ValueError(f"Transaction is not active: {tx.status.value}")

        if signer not in self._members:
            raise ValueError(f"Signer {signer} is not a multisig member")

        if signer in tx.approvals:
            raise ValueError(f"Signer {signer} has already approved")

        if signer in tx.rejections:
            raise ValueError(f"Signer {signer} has already rejected")

        tx.approvals.append(signer)
        self._members[signer].last_vote = datetime.now(timezone.utc)

        # Check if threshold reached
        if len(tx.approvals) >= tx.threshold:
            if tx.requires_timelock:
                tx.status = TransactionStatus.TIMELOCKED
                tx.timelock_ends = datetime.now(timezone.utc).replace(
                    second=0, microsecond=0
                )
                from datetime import timedelta
                tx.timelock_ends += timedelta(seconds=self.config.timelock_seconds)
                logger.info(f"Transaction {tx_id} approved, timelock until {tx.timelock_ends}")
            else:
                tx.status = TransactionStatus.APPROVED
                logger.info(f"Transaction {tx_id} approved, ready for execution")

        return tx

    async def reject_transaction(
        self,
        tx_id: str,
        signer: str,
    ) -> MultisigTransaction:
        """
        Reject a pending transaction.

        Args:
            tx_id: Transaction ID
            signer: Pubkey of the rejector

        Returns:
            Updated transaction
        """
        tx = self._transactions.get(tx_id)
        if not tx:
            raise ValueError(f"Transaction {tx_id} not found")

        if tx.status != TransactionStatus.ACTIVE:
            raise ValueError(f"Transaction is not active: {tx.status.value}")

        if signer not in self._members:
            raise ValueError(f"Signer {signer} is not a multisig member")

        if signer in tx.rejections:
            raise ValueError(f"Signer {signer} has already rejected")

        if signer in tx.approvals:
            # Remove approval and add rejection
            tx.approvals.remove(signer)

        tx.rejections.append(signer)
        self._members[signer].last_vote = datetime.now(timezone.utc)

        # Check if rejection threshold reached (more rejections than possible approvals)
        remaining_voters = len(self._members) - len(tx.approvals) - len(tx.rejections)
        if len(tx.approvals) + remaining_voters < tx.threshold:
            tx.status = TransactionStatus.REJECTED
            logger.info(f"Transaction {tx_id} rejected")

        return tx

    # =========================================================================
    # EXECUTION
    # =========================================================================

    async def execute_transaction(
        self,
        tx_id: str,
        executor: str = None,
    ) -> str:
        """
        Execute an approved transaction.

        Args:
            tx_id: Transaction ID
            executor: Optional executor pubkey

        Returns:
            Transaction signature
        """
        tx = self._transactions.get(tx_id)
        if not tx:
            raise ValueError(f"Transaction {tx_id} not found")

        # Validate status
        if tx.status == TransactionStatus.TIMELOCKED:
            if datetime.now(timezone.utc) < tx.timelock_ends:
                raise ValueError(f"Timelock active until {tx.timelock_ends}")
            tx.status = TransactionStatus.APPROVED

        if tx.status != TransactionStatus.APPROVED:
            raise ValueError(f"Transaction cannot be executed: {tx.status.value}")

        # Execute on-chain
        try:
            signature = await self._execute_on_chain(tx)

            tx.status = TransactionStatus.EXECUTED
            tx.executed_at = datetime.now(timezone.utc)
            tx.signature = signature

            logger.info(f"Transaction {tx_id} executed: {signature}")
            return signature

        except Exception as e:
            tx.error = str(e)
            logger.error(f"Transaction {tx_id} execution failed: {e}")
            raise

    async def _execute_on_chain(self, tx: MultisigTransaction) -> str:
        """
        Execute transaction on Solana.

        In production, this would:
        1. Build the Squads execute instruction
        2. Sign with collected signatures
        3. Submit to Solana
        """
        # Mock implementation - would integrate with solana-py
        import hashlib
        mock_sig = hashlib.sha256(tx.id.encode()).hexdigest()[:64]
        return mock_sig

    # =========================================================================
    # QUERIES
    # =========================================================================

    async def get_transaction(self, tx_id: str) -> Optional[MultisigTransaction]:
        """Get a transaction by ID"""
        return self._transactions.get(tx_id)

    async def get_pending_transactions(self) -> List[MultisigTransaction]:
        """Get all pending transactions"""
        return [
            tx for tx in self._transactions.values()
            if tx.status in [TransactionStatus.ACTIVE, TransactionStatus.TIMELOCKED, TransactionStatus.APPROVED]
        ]

    async def get_transaction_history(
        self,
        limit: int = 50,
        status: Optional[TransactionStatus] = None,
    ) -> List[MultisigTransaction]:
        """Get transaction history"""
        txs = list(self._transactions.values())

        if status:
            txs = [tx for tx in txs if tx.status == status]

        txs.sort(key=lambda t: t.created_at, reverse=True)
        return txs[:limit]

    async def get_multisig_state(self) -> MultisigState:
        """Get current multisig state"""
        pending = len(await self.get_pending_transactions())
        executed = len([tx for tx in self._transactions.values() if tx.status == TransactionStatus.EXECUTED])

        return MultisigState(
            address=self.config.multisig_address,
            threshold=self.config.threshold,
            member_count=len(self._members),
            transaction_index=self._transaction_index,
            pending_transactions=pending,
            total_executed=executed,
            balance_lamports=0,  # Would fetch from RPC
        )

    async def get_members(self) -> List[MultisigMember]:
        """Get all multisig members"""
        return list(self._members.values())

    # =========================================================================
    # MEMBER MANAGEMENT
    # =========================================================================

    async def add_member(
        self,
        pubkey: str,
        role: MultisigRole,
        proposer: str,
    ) -> MultisigTransaction:
        """
        Propose adding a new member.

        This creates a transaction that must be approved.
        """
        instructions = [
            {
                "program_id": self.config.program_id,
                "instruction": "add_member",
                "accounts": [
                    {"pubkey": self.config.multisig_address, "is_signer": True, "is_writable": True},
                    {"pubkey": pubkey, "is_signer": False, "is_writable": False},
                ],
                "data": {"member": pubkey, "role": role.value},
            }
        ]

        return await self.create_transaction(
            instructions=instructions,
            description=f"Add member {pubkey[:8]}... as {role.value}",
            creator=proposer,
        )

    async def remove_member(
        self,
        pubkey: str,
        proposer: str,
    ) -> MultisigTransaction:
        """
        Propose removing a member.
        """
        if pubkey not in self._members:
            raise ValueError(f"Member {pubkey} not found")

        instructions = [
            {
                "program_id": self.config.program_id,
                "instruction": "remove_member",
                "accounts": [
                    {"pubkey": self.config.multisig_address, "is_signer": True, "is_writable": True},
                    {"pubkey": pubkey, "is_signer": False, "is_writable": False},
                ],
                "data": {"member": pubkey},
            }
        ]

        return await self.create_transaction(
            instructions=instructions,
            description=f"Remove member {pubkey[:8]}...",
            creator=proposer,
        )

    async def change_threshold(
        self,
        new_threshold: int,
        proposer: str,
    ) -> MultisigTransaction:
        """
        Propose changing the approval threshold.
        """
        if new_threshold < 1:
            raise ValueError("Threshold must be at least 1")
        if new_threshold > len(self._members):
            raise ValueError("Threshold cannot exceed member count")

        instructions = [
            {
                "program_id": self.config.program_id,
                "instruction": "change_threshold",
                "accounts": [
                    {"pubkey": self.config.multisig_address, "is_signer": True, "is_writable": True},
                ],
                "data": {"threshold": new_threshold},
            }
        ]

        return await self.create_transaction(
            instructions=instructions,
            description=f"Change threshold from {self.config.threshold} to {new_threshold}",
            creator=proposer,
        )


# =============================================================================
# API ENDPOINTS
# =============================================================================

def create_squads_endpoints(client: SquadsClient):
    """Create Squads API endpoints"""
    from fastapi import APIRouter, HTTPException, Query
    from pydantic import BaseModel
    from typing import List as TypeList

    router = APIRouter(prefix="/api/treasury/multisig", tags=["Multisig"])

    class CreateTransferRequest(BaseModel):
        destination: str
        amount_lamports: int
        creator: str
        memo: str = ""

    class VoteRequest(BaseModel):
        signer: str

    @router.get("/state")
    async def get_state():
        """Get multisig state"""
        state = await client.get_multisig_state()
        return {
            "address": state.address,
            "threshold": state.threshold,
            "member_count": state.member_count,
            "pending_transactions": state.pending_transactions,
            "total_executed": state.total_executed,
        }

    @router.get("/members")
    async def get_members():
        """Get multisig members"""
        members = await client.get_members()
        return [
            {
                "pubkey": m.pubkey,
                "role": m.role.value,
                "is_active": m.is_active,
                "last_vote": m.last_vote.isoformat() if m.last_vote else None,
            }
            for m in members
        ]

    @router.post("/transactions/transfer")
    async def create_transfer(request: CreateTransferRequest):
        """Create a transfer transaction"""
        try:
            tx = await client.create_transfer_transaction(
                destination=request.destination,
                amount_lamports=request.amount_lamports,
                creator=request.creator,
                memo=request.memo,
            )
            return tx.to_dict()
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.get("/transactions")
    async def get_transactions(
        status: str = None,
        limit: int = Query(default=50, le=100),
    ):
        """Get transaction history"""
        status_enum = TransactionStatus(status) if status else None
        txs = await client.get_transaction_history(limit=limit, status=status_enum)
        return [tx.to_dict() for tx in txs]

    @router.get("/transactions/pending")
    async def get_pending():
        """Get pending transactions"""
        txs = await client.get_pending_transactions()
        return [tx.to_dict() for tx in txs]

    @router.get("/transactions/{tx_id}")
    async def get_transaction(tx_id: str):
        """Get a specific transaction"""
        tx = await client.get_transaction(tx_id)
        if not tx:
            raise HTTPException(status_code=404, detail="Transaction not found")
        return tx.to_dict()

    @router.post("/transactions/{tx_id}/approve")
    async def approve_transaction(tx_id: str, request: VoteRequest):
        """Approve a transaction"""
        try:
            tx = await client.approve_transaction(tx_id, request.signer)
            return tx.to_dict()
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.post("/transactions/{tx_id}/reject")
    async def reject_transaction(tx_id: str, request: VoteRequest):
        """Reject a transaction"""
        try:
            tx = await client.reject_transaction(tx_id, request.signer)
            return tx.to_dict()
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.post("/transactions/{tx_id}/execute")
    async def execute_transaction(tx_id: str):
        """Execute an approved transaction"""
        try:
            signature = await client.execute_transaction(tx_id)
            return {"signature": signature, "status": "executed"}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    return router


# =============================================================================
# SINGLETON
# =============================================================================

_squads_client: Optional[SquadsClient] = None


def get_squads_client() -> SquadsClient:
    """Get or create the Squads client singleton"""
    global _squads_client
    if _squads_client is None:
        _squads_client = SquadsClient()
    return _squads_client
