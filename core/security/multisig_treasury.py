"""
Multisig Treasury Management
Prompt #51: Secure treasury with multi-signature requirements
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
import hashlib
import json

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

DEFAULT_THRESHOLD = 3  # 3 of N required
DEFAULT_TIMELOCK = timedelta(hours=24)
EMERGENCY_THRESHOLD = 2  # Lower threshold for emergencies
MAX_TRANSACTION_VALUE = 1_000_000 * 10**9  # 1M tokens


# =============================================================================
# MODELS
# =============================================================================

class TransactionStatus(str, Enum):
    PROPOSED = "proposed"
    PENDING_SIGNATURES = "pending_signatures"
    READY = "ready"
    TIMELOCKED = "timelocked"
    EXECUTED = "executed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REJECTED = "rejected"


class TransactionType(str, Enum):
    TRANSFER = "transfer"
    STAKE = "stake"
    BURN = "burn"
    UPGRADE = "upgrade"
    CONFIG_CHANGE = "config_change"
    EMERGENCY = "emergency"


class SignerRole(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    GUARDIAN = "guardian"  # Can only veto, not propose


@dataclass
class Signer:
    """A multisig signer"""
    pubkey: str
    name: str
    role: SignerRole
    added_at: datetime = field(default_factory=datetime.utcnow)
    is_active: bool = True
    last_signature: Optional[datetime] = None


@dataclass
class Signature:
    """A signature on a transaction"""
    signer: str
    signature: str
    signed_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MultisigTransaction:
    """A multi-signature transaction"""
    id: str
    tx_type: TransactionType
    proposer: str
    description: str
    instructions: List[Dict[str, Any]]
    value: int = 0  # Value in tokens/lamports
    threshold: int = DEFAULT_THRESHOLD
    signatures: List[Signature] = field(default_factory=list)
    status: TransactionStatus = TransactionStatus.PROPOSED
    created_at: datetime = field(default_factory=datetime.utcnow)
    executed_at: Optional[datetime] = None
    execution_signature: Optional[str] = None
    timelock_ends: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    rejections: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def signature_count(self) -> int:
        return len(self.signatures)

    @property
    def has_quorum(self) -> bool:
        return self.signature_count >= self.threshold

    @property
    def is_timelocked(self) -> bool:
        if not self.timelock_ends:
            return False
        return datetime.utcnow() < self.timelock_ends

    @property
    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at

    def has_signed(self, signer: str) -> bool:
        return any(s.signer == signer for s in self.signatures)


@dataclass
class MultisigConfig:
    """Configuration for multisig treasury"""
    threshold: int = DEFAULT_THRESHOLD
    timelock: timedelta = field(default_factory=lambda: DEFAULT_TIMELOCK)
    max_transaction_value: int = MAX_TRANSACTION_VALUE
    proposal_expiry: timedelta = field(default_factory=lambda: timedelta(days=7))
    emergency_threshold: int = EMERGENCY_THRESHOLD
    require_timelock_above: int = 100_000 * 10**9  # 100K tokens


# =============================================================================
# MULTISIG MANAGER
# =============================================================================

class MultisigTreasury:
    """Manages multi-signature treasury operations"""

    def __init__(
        self,
        treasury_address: str,
        config: Optional[MultisigConfig] = None
    ):
        self.treasury_address = treasury_address
        self.config = config or MultisigConfig()

        self.signers: Dict[str, Signer] = {}
        self.transactions: Dict[str, MultisigTransaction] = {}
        self.executed_hashes: Set[str] = set()  # For replay protection

        # Event callbacks
        self._on_proposal: List[Callable] = []
        self._on_signature: List[Callable] = []
        self._on_execution: List[Callable] = []

    # =========================================================================
    # SIGNER MANAGEMENT
    # =========================================================================

    async def add_signer(
        self,
        pubkey: str,
        name: str,
        role: SignerRole = SignerRole.OPERATOR,
        approver: str = None
    ) -> Signer:
        """Add a new signer (requires multisig approval)"""
        if pubkey in self.signers:
            raise ValueError("Signer already exists")

        signer = Signer(
            pubkey=pubkey,
            name=name,
            role=role
        )

        # For the first signers, add directly
        if len(self.signers) < self.config.threshold:
            self.signers[pubkey] = signer
            logger.info(f"Added initial signer: {name} ({pubkey[:8]}...)")
            return signer

        # Otherwise, create a transaction for approval
        await self.propose_transaction(
            tx_type=TransactionType.CONFIG_CHANGE,
            proposer=approver,
            description=f"Add signer: {name}",
            instructions=[{
                "type": "add_signer",
                "pubkey": pubkey,
                "name": name,
                "role": role.value
            }]
        )

        return signer

    async def remove_signer(
        self,
        pubkey: str,
        proposer: str
    ):
        """Remove a signer (requires multisig approval)"""
        if pubkey not in self.signers:
            raise ValueError("Signer not found")

        # Cannot go below threshold
        if len(self.signers) <= self.config.threshold:
            raise ValueError("Cannot remove signer: would be below threshold")

        await self.propose_transaction(
            tx_type=TransactionType.CONFIG_CHANGE,
            proposer=proposer,
            description=f"Remove signer: {self.signers[pubkey].name}",
            instructions=[{
                "type": "remove_signer",
                "pubkey": pubkey
            }]
        )

    def get_signers(self, active_only: bool = True) -> List[Signer]:
        """Get all signers"""
        signers = list(self.signers.values())
        if active_only:
            signers = [s for s in signers if s.is_active]
        return signers

    # =========================================================================
    # TRANSACTION MANAGEMENT
    # =========================================================================

    async def propose_transaction(
        self,
        tx_type: TransactionType,
        proposer: str,
        description: str,
        instructions: List[Dict[str, Any]],
        value: int = 0
    ) -> MultisigTransaction:
        """Propose a new transaction"""
        import uuid

        # Validate proposer
        if proposer not in self.signers:
            raise ValueError("Proposer is not a signer")

        signer = self.signers[proposer]
        if signer.role == SignerRole.GUARDIAN:
            raise ValueError("Guardians cannot propose transactions")

        # Validate value
        if value > self.config.max_transaction_value:
            raise ValueError(f"Transaction value exceeds maximum: {self.config.max_transaction_value}")

        # Determine threshold and timelock
        threshold = self.config.threshold
        timelock = None

        if tx_type == TransactionType.EMERGENCY:
            threshold = self.config.emergency_threshold
        elif value > self.config.require_timelock_above:
            timelock = datetime.utcnow() + self.config.timelock

        tx = MultisigTransaction(
            id=str(uuid.uuid4()),
            tx_type=tx_type,
            proposer=proposer,
            description=description,
            instructions=instructions,
            value=value,
            threshold=threshold,
            timelock_ends=timelock,
            expires_at=datetime.utcnow() + self.config.proposal_expiry,
            status=TransactionStatus.PENDING_SIGNATURES
        )

        self.transactions[tx.id] = tx
        await self._emit_proposal(tx)

        logger.info(f"Transaction proposed: {tx.id} - {description}")
        return tx

    async def sign_transaction(
        self,
        tx_id: str,
        signer_pubkey: str,
        signature: str
    ) -> MultisigTransaction:
        """Sign a pending transaction"""
        tx = self.transactions.get(tx_id)
        if not tx:
            raise ValueError("Transaction not found")

        if tx.status != TransactionStatus.PENDING_SIGNATURES:
            raise ValueError(f"Transaction not pending: {tx.status}")

        if tx.is_expired:
            tx.status = TransactionStatus.EXPIRED
            raise ValueError("Transaction has expired")

        if signer_pubkey not in self.signers:
            raise ValueError("Not a valid signer")

        if tx.has_signed(signer_pubkey):
            raise ValueError("Already signed")

        # Verify signature
        if not await self._verify_signature(tx, signer_pubkey, signature):
            raise ValueError("Invalid signature")

        tx.signatures.append(Signature(
            signer=signer_pubkey,
            signature=signature
        ))

        self.signers[signer_pubkey].last_signature = datetime.utcnow()

        # Check if we have quorum
        if tx.has_quorum:
            if tx.is_timelocked:
                tx.status = TransactionStatus.TIMELOCKED
            else:
                tx.status = TransactionStatus.READY

        await self._emit_signature(tx, signer_pubkey)

        logger.info(
            f"Transaction {tx.id} signed by {signer_pubkey[:8]}... "
            f"({tx.signature_count}/{tx.threshold})"
        )

        return tx

    async def reject_transaction(
        self,
        tx_id: str,
        signer_pubkey: str
    ) -> MultisigTransaction:
        """Reject a transaction (guardians can veto)"""
        tx = self.transactions.get(tx_id)
        if not tx:
            raise ValueError("Transaction not found")

        if signer_pubkey not in self.signers:
            raise ValueError("Not a valid signer")

        if signer_pubkey in tx.rejections:
            raise ValueError("Already rejected")

        tx.rejections.append(signer_pubkey)

        # Guardian veto power
        signer = self.signers[signer_pubkey]
        if signer.role == SignerRole.GUARDIAN:
            tx.status = TransactionStatus.REJECTED
            tx.metadata["vetoed_by"] = signer_pubkey
            logger.info(f"Transaction {tx.id} vetoed by guardian")

        # Majority rejection
        active_signers = len([s for s in self.signers.values() if s.is_active])
        if len(tx.rejections) > active_signers // 2:
            tx.status = TransactionStatus.REJECTED
            logger.info(f"Transaction {tx.id} rejected by majority")

        return tx

    async def execute_transaction(
        self,
        tx_id: str,
        executor: str
    ) -> Dict[str, Any]:
        """Execute a ready transaction"""
        tx = self.transactions.get(tx_id)
        if not tx:
            raise ValueError("Transaction not found")

        if tx.status == TransactionStatus.TIMELOCKED:
            if tx.is_timelocked:
                raise ValueError(
                    f"Transaction still timelocked until {tx.timelock_ends}"
                )
            tx.status = TransactionStatus.READY

        if tx.status != TransactionStatus.READY:
            raise ValueError(f"Transaction not ready: {tx.status}")

        # Replay protection
        tx_hash = self._hash_transaction(tx)
        if tx_hash in self.executed_hashes:
            raise ValueError("Transaction already executed (replay)")

        try:
            # Execute each instruction
            results = []
            for instruction in tx.instructions:
                result = await self._execute_instruction(instruction)
                results.append(result)

            tx.status = TransactionStatus.EXECUTED
            tx.executed_at = datetime.utcnow()
            tx.execution_signature = results[-1].get("signature", "")

            self.executed_hashes.add(tx_hash)
            await self._emit_execution(tx)

            logger.info(f"Transaction {tx.id} executed")

            return {
                "tx_id": tx.id,
                "status": "executed",
                "results": results,
                "signature": tx.execution_signature
            }

        except Exception as e:
            logger.error(f"Transaction {tx.id} execution failed: {e}")
            tx.metadata["execution_error"] = str(e)
            raise

    async def cancel_transaction(
        self,
        tx_id: str,
        canceller: str
    ) -> MultisigTransaction:
        """Cancel a pending transaction (proposer only)"""
        tx = self.transactions.get(tx_id)
        if not tx:
            raise ValueError("Transaction not found")

        if tx.proposer != canceller:
            raise ValueError("Only proposer can cancel")

        if tx.status not in [
            TransactionStatus.PROPOSED,
            TransactionStatus.PENDING_SIGNATURES,
            TransactionStatus.TIMELOCKED
        ]:
            raise ValueError("Cannot cancel transaction in current state")

        tx.status = TransactionStatus.CANCELLED
        logger.info(f"Transaction {tx.id} cancelled")
        return tx

    # =========================================================================
    # VIEW FUNCTIONS
    # =========================================================================

    async def get_transaction(self, tx_id: str) -> Optional[MultisigTransaction]:
        """Get a transaction by ID"""
        return self.transactions.get(tx_id)

    async def get_pending_transactions(self) -> List[MultisigTransaction]:
        """Get all pending transactions"""
        return [
            tx for tx in self.transactions.values()
            if tx.status in [
                TransactionStatus.PROPOSED,
                TransactionStatus.PENDING_SIGNATURES,
                TransactionStatus.TIMELOCKED,
                TransactionStatus.READY
            ]
        ]

    async def get_signer_pending(self, signer: str) -> List[MultisigTransaction]:
        """Get transactions awaiting a signer's signature"""
        pending = await self.get_pending_transactions()
        return [tx for tx in pending if not tx.has_signed(signer)]

    async def get_treasury_balance(self) -> Dict[str, int]:
        """Get treasury token balances"""
        # In production, query on-chain
        return {
            "SOL": 1000 * 10**9,
            "KR8TIV": 10_000_000 * 10**9
        }

    async def get_activity_log(
        self,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get recent treasury activity"""
        executed = [
            tx for tx in self.transactions.values()
            if tx.status == TransactionStatus.EXECUTED
        ]
        executed.sort(key=lambda x: x.executed_at or datetime.min, reverse=True)

        return [
            {
                "tx_id": tx.id,
                "type": tx.tx_type.value,
                "description": tx.description,
                "value": tx.value,
                "executed_at": tx.executed_at.isoformat() if tx.executed_at else None,
                "proposer": tx.proposer,
                "signatures": len(tx.signatures)
            }
            for tx in executed[:limit]
        ]

    # =========================================================================
    # INTERNAL HELPERS
    # =========================================================================

    async def _verify_signature(
        self,
        tx: MultisigTransaction,
        signer: str,
        signature: str
    ) -> bool:
        """Verify a signature is valid"""
        # In production, verify Ed25519 signature
        return True

    def _hash_transaction(self, tx: MultisigTransaction) -> str:
        """Create a unique hash for a transaction"""
        data = json.dumps({
            "id": tx.id,
            "instructions": tx.instructions,
            "value": tx.value,
            "created_at": tx.created_at.isoformat()
        }, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()

    async def _execute_instruction(
        self,
        instruction: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a single instruction"""
        ix_type = instruction.get("type")

        if ix_type == "transfer":
            return await self._execute_transfer(instruction)
        elif ix_type == "stake":
            return await self._execute_stake(instruction)
        elif ix_type == "burn":
            return await self._execute_burn(instruction)
        elif ix_type == "add_signer":
            return await self._execute_add_signer(instruction)
        elif ix_type == "remove_signer":
            return await self._execute_remove_signer(instruction)
        else:
            raise ValueError(f"Unknown instruction type: {ix_type}")

    async def _execute_transfer(self, ix: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a transfer instruction"""
        # In production, create and send Solana transaction
        return {"signature": "mock_transfer_sig"}

    async def _execute_stake(self, ix: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a staking instruction"""
        return {"signature": "mock_stake_sig"}

    async def _execute_burn(self, ix: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a burn instruction"""
        return {"signature": "mock_burn_sig"}

    async def _execute_add_signer(self, ix: Dict[str, Any]) -> Dict[str, Any]:
        """Execute add signer instruction"""
        pubkey = ix["pubkey"]
        self.signers[pubkey] = Signer(
            pubkey=pubkey,
            name=ix["name"],
            role=SignerRole(ix["role"])
        )
        return {"status": "added"}

    async def _execute_remove_signer(self, ix: Dict[str, Any]) -> Dict[str, Any]:
        """Execute remove signer instruction"""
        pubkey = ix["pubkey"]
        if pubkey in self.signers:
            self.signers[pubkey].is_active = False
        return {"status": "removed"}

    # =========================================================================
    # EVENT CALLBACKS
    # =========================================================================

    def on_proposal(self, callback: Callable):
        """Register proposal callback"""
        self._on_proposal.append(callback)

    def on_signature(self, callback: Callable):
        """Register signature callback"""
        self._on_signature.append(callback)

    def on_execution(self, callback: Callable):
        """Register execution callback"""
        self._on_execution.append(callback)

    async def _emit_proposal(self, tx: MultisigTransaction):
        for cb in self._on_proposal:
            try:
                await cb(tx) if asyncio.iscoroutinefunction(cb) else cb(tx)
            except Exception as e:
                logger.error(f"Proposal callback error: {e}")

    async def _emit_signature(self, tx: MultisigTransaction, signer: str):
        for cb in self._on_signature:
            try:
                await cb(tx, signer) if asyncio.iscoroutinefunction(cb) else cb(tx, signer)
            except Exception as e:
                logger.error(f"Signature callback error: {e}")

    async def _emit_execution(self, tx: MultisigTransaction):
        for cb in self._on_execution:
            try:
                await cb(tx) if asyncio.iscoroutinefunction(cb) else cb(tx)
            except Exception as e:
                logger.error(f"Execution callback error: {e}")


# =============================================================================
# API ENDPOINTS
# =============================================================================

def create_multisig_endpoints(treasury: MultisigTreasury):
    """Create API endpoints for multisig treasury"""
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel

    router = APIRouter(prefix="/api/treasury", tags=["Multisig Treasury"])

    class ProposeTransactionRequest(BaseModel):
        tx_type: str
        description: str
        instructions: List[Dict[str, Any]]
        value: int = 0

    class SignTransactionRequest(BaseModel):
        signature: str

    @router.get("/signers")
    async def get_signers():
        """Get all treasury signers"""
        signers = treasury.get_signers()
        return [
            {
                "pubkey": s.pubkey,
                "name": s.name,
                "role": s.role.value,
                "is_active": s.is_active,
                "last_signature": s.last_signature.isoformat() if s.last_signature else None
            }
            for s in signers
        ]

    @router.get("/balance")
    async def get_balance():
        """Get treasury balances"""
        return await treasury.get_treasury_balance()

    @router.get("/transactions/pending")
    async def get_pending():
        """Get pending transactions"""
        txs = await treasury.get_pending_transactions()
        return [_format_tx(tx) for tx in txs]

    @router.get("/transactions/{tx_id}")
    async def get_transaction(tx_id: str):
        """Get transaction details"""
        tx = await treasury.get_transaction(tx_id)
        if not tx:
            raise HTTPException(status_code=404, detail="Transaction not found")
        return _format_tx(tx)

    @router.post("/transactions")
    async def propose_transaction(proposer: str, request: ProposeTransactionRequest):
        """Propose a new transaction"""
        try:
            tx = await treasury.propose_transaction(
                tx_type=TransactionType(request.tx_type),
                proposer=proposer,
                description=request.description,
                instructions=request.instructions,
                value=request.value
            )
            return {"tx_id": tx.id, "status": tx.status.value}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.post("/transactions/{tx_id}/sign")
    async def sign_transaction(tx_id: str, signer: str, request: SignTransactionRequest):
        """Sign a transaction"""
        try:
            tx = await treasury.sign_transaction(tx_id, signer, request.signature)
            return {
                "tx_id": tx.id,
                "signatures": tx.signature_count,
                "threshold": tx.threshold,
                "status": tx.status.value
            }
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.post("/transactions/{tx_id}/execute")
    async def execute_transaction(tx_id: str, executor: str):
        """Execute a ready transaction"""
        try:
            result = await treasury.execute_transaction(tx_id, executor)
            return result
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.post("/transactions/{tx_id}/reject")
    async def reject_transaction(tx_id: str, signer: str):
        """Reject a transaction"""
        try:
            tx = await treasury.reject_transaction(tx_id, signer)
            return {"tx_id": tx.id, "status": tx.status.value}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.get("/activity")
    async def get_activity(limit: int = 50):
        """Get treasury activity log"""
        return await treasury.get_activity_log(limit)

    def _format_tx(tx: MultisigTransaction) -> Dict[str, Any]:
        return {
            "id": tx.id,
            "type": tx.tx_type.value,
            "proposer": tx.proposer,
            "description": tx.description,
            "value": tx.value,
            "status": tx.status.value,
            "signatures": tx.signature_count,
            "threshold": tx.threshold,
            "has_quorum": tx.has_quorum,
            "is_timelocked": tx.is_timelocked,
            "timelock_ends": tx.timelock_ends.isoformat() if tx.timelock_ends else None,
            "expires_at": tx.expires_at.isoformat() if tx.expires_at else None,
            "created_at": tx.created_at.isoformat(),
            "signers": [s.signer for s in tx.signatures],
            "rejections": tx.rejections
        }

    return router
