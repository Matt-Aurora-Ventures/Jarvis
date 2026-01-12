"""
Cross-Chain Bridge Monitor - Track and manage cross-chain bridge transfers.
Monitors bridge transactions, tracks confirmations, and manages bridge risks.
"""
import asyncio
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Callable


class Chain(Enum):
    """Supported blockchains."""
    SOLANA = "solana"
    ETHEREUM = "ethereum"
    BSC = "bsc"
    POLYGON = "polygon"
    ARBITRUM = "arbitrum"
    OPTIMISM = "optimism"
    AVALANCHE = "avalanche"
    BASE = "base"
    SUI = "sui"
    APTOS = "aptos"


class BridgeProtocol(Enum):
    """Bridge protocols."""
    WORMHOLE = "wormhole"
    DEBRIDGE = "debridge"
    ALLBRIDGE = "allbridge"
    PORTAL = "portal"
    LAYERZERO = "layerzero"
    ACROSS = "across"
    STARGATE = "stargate"
    HOP = "hop"
    CELER = "celer"
    MAYAN = "mayan"


class TransferStatus(Enum):
    """Bridge transfer status."""
    PENDING = "pending"             # Transaction submitted
    SOURCE_CONFIRMED = "source"     # Confirmed on source chain
    IN_TRANSIT = "transit"          # Being processed by bridge
    FINALIZING = "finalizing"       # Finalizing on destination
    COMPLETED = "completed"         # Successfully bridged
    FAILED = "failed"               # Transfer failed
    REFUNDED = "refunded"           # Refunded on source chain
    STUCK = "stuck"                 # Stuck in bridge


class BridgeRisk(Enum):
    """Bridge risk levels."""
    LOW = "low"                     # Established, audited bridge
    MEDIUM = "medium"               # Newer but reputable
    HIGH = "high"                   # Less established
    CRITICAL = "critical"           # Known issues or vulnerabilities


@dataclass
class BridgeTransfer:
    """A cross-chain bridge transfer."""
    transfer_id: str
    bridge: BridgeProtocol
    source_chain: Chain
    dest_chain: Chain
    token: str
    amount: float
    sender: str
    recipient: str
    source_tx: Optional[str]
    dest_tx: Optional[str]
    status: TransferStatus
    fee: float
    created_at: datetime
    updated_at: datetime
    estimated_completion: Optional[datetime]
    actual_completion: Optional[datetime]
    confirmations: int
    required_confirmations: int
    metadata: Dict = field(default_factory=dict)


@dataclass
class BridgeQuote:
    """Quote for a bridge transfer."""
    bridge: BridgeProtocol
    source_chain: Chain
    dest_chain: Chain
    token: str
    amount_in: float
    amount_out: float
    fee: float
    fee_usd: float
    estimated_time_minutes: int
    route: List[str]
    quoted_at: datetime
    expires_at: datetime


@dataclass
class BridgeHealth:
    """Health status of a bridge."""
    bridge: BridgeProtocol
    status: str                     # "operational", "degraded", "down"
    tvl_usd: float
    volume_24h: float
    avg_time_minutes: float
    success_rate: float
    last_incident: Optional[datetime]
    risk_level: BridgeRisk


class BridgeMonitor:
    """
    Cross-chain bridge transfer monitor.
    Tracks transfers, monitors status, and manages bridge risks.
    """

    # Required confirmations by chain
    CONFIRMATIONS = {
        Chain.SOLANA: 32,
        Chain.ETHEREUM: 12,
        Chain.BSC: 15,
        Chain.POLYGON: 256,
        Chain.ARBITRUM: 1,
        Chain.OPTIMISM: 1,
        Chain.AVALANCHE: 1,
        Chain.BASE: 1,
        Chain.SUI: 1,
        Chain.APTOS: 1
    }

    # Estimated bridge times in minutes
    BRIDGE_TIMES = {
        BridgeProtocol.WORMHOLE: 15,
        BridgeProtocol.DEBRIDGE: 10,
        BridgeProtocol.ALLBRIDGE: 20,
        BridgeProtocol.PORTAL: 15,
        BridgeProtocol.LAYERZERO: 5,
        BridgeProtocol.ACROSS: 2,
        BridgeProtocol.STARGATE: 5,
        BridgeProtocol.HOP: 10,
        BridgeProtocol.CELER: 15,
        BridgeProtocol.MAYAN: 3
    }

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or str(
            Path(__file__).parent.parent / "data" / "bridge_monitor.db"
        )
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

        self.active_transfers: Dict[str, BridgeTransfer] = {}
        self.status_callbacks: List[Callable] = []
        self.completion_callbacks: List[Callable] = []
        self._lock = threading.Lock()
        self._monitoring = False

        # Bridge health cache
        self.bridge_health: Dict[BridgeProtocol, BridgeHealth] = {}

        self._load_active_transfers()

    @contextmanager
    def _get_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self):
        with self._get_db() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS transfers (
                    transfer_id TEXT PRIMARY KEY,
                    bridge TEXT NOT NULL,
                    source_chain TEXT NOT NULL,
                    dest_chain TEXT NOT NULL,
                    token TEXT NOT NULL,
                    amount REAL NOT NULL,
                    sender TEXT NOT NULL,
                    recipient TEXT NOT NULL,
                    source_tx TEXT,
                    dest_tx TEXT,
                    status TEXT NOT NULL,
                    fee REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    estimated_completion TEXT,
                    actual_completion TEXT,
                    confirmations INTEGER DEFAULT 0,
                    required_confirmations INTEGER NOT NULL,
                    metadata TEXT
                );

                CREATE TABLE IF NOT EXISTS bridge_health (
                    bridge TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    tvl_usd REAL DEFAULT 0,
                    volume_24h REAL DEFAULT 0,
                    avg_time_minutes REAL DEFAULT 0,
                    success_rate REAL DEFAULT 1,
                    last_incident TEXT,
                    risk_level TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS quotes_history (
                    quote_id TEXT PRIMARY KEY,
                    bridge TEXT NOT NULL,
                    source_chain TEXT NOT NULL,
                    dest_chain TEXT NOT NULL,
                    token TEXT NOT NULL,
                    amount_in REAL NOT NULL,
                    amount_out REAL NOT NULL,
                    fee REAL NOT NULL,
                    quoted_at TEXT NOT NULL,
                    used INTEGER DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_transfers_status ON transfers(status);
                CREATE INDEX IF NOT EXISTS idx_transfers_chains ON transfers(source_chain, dest_chain);
            """)

    def _load_active_transfers(self):
        """Load active transfers from database."""
        import json

        with self._get_db() as conn:
            rows = conn.execute("""
                SELECT * FROM transfers
                WHERE status NOT IN ('completed', 'failed', 'refunded')
            """).fetchall()

            for row in rows:
                transfer = BridgeTransfer(
                    transfer_id=row["transfer_id"],
                    bridge=BridgeProtocol(row["bridge"]),
                    source_chain=Chain(row["source_chain"]),
                    dest_chain=Chain(row["dest_chain"]),
                    token=row["token"],
                    amount=row["amount"],
                    sender=row["sender"],
                    recipient=row["recipient"],
                    source_tx=row["source_tx"],
                    dest_tx=row["dest_tx"],
                    status=TransferStatus(row["status"]),
                    fee=row["fee"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                    estimated_completion=datetime.fromisoformat(row["estimated_completion"]) if row["estimated_completion"] else None,
                    actual_completion=datetime.fromisoformat(row["actual_completion"]) if row["actual_completion"] else None,
                    confirmations=row["confirmations"],
                    required_confirmations=row["required_confirmations"],
                    metadata=json.loads(row["metadata"] or "{}")
                )
                self.active_transfers[transfer.transfer_id] = transfer

    def initiate_transfer(
        self,
        bridge: BridgeProtocol,
        source_chain: Chain,
        dest_chain: Chain,
        token: str,
        amount: float,
        sender: str,
        recipient: str,
        source_tx: Optional[str] = None,
        fee: float = 0,
        metadata: Optional[Dict] = None
    ) -> BridgeTransfer:
        """Initiate a new bridge transfer."""
        import json
        import uuid

        now = datetime.now()
        est_time = self.BRIDGE_TIMES.get(bridge, 15)
        required_confs = self.CONFIRMATIONS.get(source_chain, 12)

        transfer = BridgeTransfer(
            transfer_id=str(uuid.uuid4())[:12],
            bridge=bridge,
            source_chain=source_chain,
            dest_chain=dest_chain,
            token=token,
            amount=amount,
            sender=sender,
            recipient=recipient,
            source_tx=source_tx,
            dest_tx=None,
            status=TransferStatus.PENDING,
            fee=fee,
            created_at=now,
            updated_at=now,
            estimated_completion=now + timedelta(minutes=est_time),
            actual_completion=None,
            confirmations=0,
            required_confirmations=required_confs,
            metadata=metadata or {}
        )

        with self._lock:
            self.active_transfers[transfer.transfer_id] = transfer

        with self._get_db() as conn:
            conn.execute("""
                INSERT INTO transfers
                (transfer_id, bridge, source_chain, dest_chain, token, amount,
                 sender, recipient, source_tx, dest_tx, status, fee,
                 created_at, updated_at, estimated_completion, actual_completion,
                 confirmations, required_confirmations, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                transfer.transfer_id, bridge.value, source_chain.value,
                dest_chain.value, token, amount, sender, recipient,
                source_tx, None, transfer.status.value, fee,
                now.isoformat(), now.isoformat(),
                transfer.estimated_completion.isoformat() if transfer.estimated_completion else None,
                None, 0, required_confs, json.dumps(metadata or {})
            ))

        return transfer

    def update_transfer_status(
        self,
        transfer_id: str,
        status: TransferStatus,
        confirmations: Optional[int] = None,
        dest_tx: Optional[str] = None
    ) -> Optional[BridgeTransfer]:
        """Update transfer status."""
        now = datetime.now()

        with self._lock:
            if transfer_id not in self.active_transfers:
                return None

            transfer = self.active_transfers[transfer_id]
            old_status = transfer.status
            transfer.status = status
            transfer.updated_at = now

            if confirmations is not None:
                transfer.confirmations = confirmations

            if dest_tx:
                transfer.dest_tx = dest_tx

            if status == TransferStatus.COMPLETED:
                transfer.actual_completion = now
                del self.active_transfers[transfer_id]

                # Trigger completion callbacks
                for callback in self.completion_callbacks:
                    try:
                        callback(transfer)
                    except Exception:
                        pass

            # Trigger status callbacks
            if status != old_status:
                for callback in self.status_callbacks:
                    try:
                        callback(transfer, old_status, status)
                    except Exception:
                        pass

        # Update database
        with self._get_db() as conn:
            conn.execute("""
                UPDATE transfers SET
                status = ?, confirmations = ?, dest_tx = ?,
                updated_at = ?, actual_completion = ?
                WHERE transfer_id = ?
            """, (
                status.value, transfer.confirmations, transfer.dest_tx,
                now.isoformat(),
                transfer.actual_completion.isoformat() if transfer.actual_completion else None,
                transfer_id
            ))

        return transfer

    def get_transfer(self, transfer_id: str) -> Optional[BridgeTransfer]:
        """Get a transfer by ID."""
        if transfer_id in self.active_transfers:
            return self.active_transfers[transfer_id]

        # Check database for completed transfers
        import json
        with self._get_db() as conn:
            row = conn.execute(
                "SELECT * FROM transfers WHERE transfer_id = ?",
                (transfer_id,)
            ).fetchone()

            if row:
                return BridgeTransfer(
                    transfer_id=row["transfer_id"],
                    bridge=BridgeProtocol(row["bridge"]),
                    source_chain=Chain(row["source_chain"]),
                    dest_chain=Chain(row["dest_chain"]),
                    token=row["token"],
                    amount=row["amount"],
                    sender=row["sender"],
                    recipient=row["recipient"],
                    source_tx=row["source_tx"],
                    dest_tx=row["dest_tx"],
                    status=TransferStatus(row["status"]),
                    fee=row["fee"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                    estimated_completion=datetime.fromisoformat(row["estimated_completion"]) if row["estimated_completion"] else None,
                    actual_completion=datetime.fromisoformat(row["actual_completion"]) if row["actual_completion"] else None,
                    confirmations=row["confirmations"],
                    required_confirmations=row["required_confirmations"],
                    metadata=json.loads(row["metadata"] or "{}")
                )

        return None

    def get_quote(
        self,
        bridge: BridgeProtocol,
        source_chain: Chain,
        dest_chain: Chain,
        token: str,
        amount: float
    ) -> BridgeQuote:
        """Get quote for a bridge transfer."""
        # Estimate fee based on bridge and chains
        base_fee = amount * 0.001  # 0.1% base fee

        # Bridge-specific fee adjustments
        fee_multipliers = {
            BridgeProtocol.WORMHOLE: 1.0,
            BridgeProtocol.DEBRIDGE: 0.8,
            BridgeProtocol.ALLBRIDGE: 1.2,
            BridgeProtocol.PORTAL: 1.0,
            BridgeProtocol.LAYERZERO: 0.6,
            BridgeProtocol.ACROSS: 0.5,
            BridgeProtocol.STARGATE: 0.7,
            BridgeProtocol.HOP: 0.9,
            BridgeProtocol.CELER: 1.1,
            BridgeProtocol.MAYAN: 0.4
        }

        fee = base_fee * fee_multipliers.get(bridge, 1.0)
        amount_out = amount - fee

        now = datetime.now()
        return BridgeQuote(
            bridge=bridge,
            source_chain=source_chain,
            dest_chain=dest_chain,
            token=token,
            amount_in=amount,
            amount_out=amount_out,
            fee=fee,
            fee_usd=fee,  # Assuming 1:1 for simplicity
            estimated_time_minutes=self.BRIDGE_TIMES.get(bridge, 15),
            route=[source_chain.value, bridge.value, dest_chain.value],
            quoted_at=now,
            expires_at=now + timedelta(minutes=5)
        )

    def get_best_bridge(
        self,
        source_chain: Chain,
        dest_chain: Chain,
        token: str,
        amount: float,
        priority: str = "balanced"  # "fast", "cheap", "balanced"
    ) -> BridgeQuote:
        """Find the best bridge for a transfer."""
        available_bridges = self._get_available_bridges(source_chain, dest_chain)

        if not available_bridges:
            raise ValueError(f"No bridge available from {source_chain.value} to {dest_chain.value}")

        quotes = [
            self.get_quote(bridge, source_chain, dest_chain, token, amount)
            for bridge in available_bridges
        ]

        # Score quotes based on priority
        def score_quote(q: BridgeQuote) -> float:
            if priority == "fast":
                return -q.estimated_time_minutes
            elif priority == "cheap":
                return q.amount_out
            else:  # balanced
                time_score = 1 / (q.estimated_time_minutes + 1)
                value_score = q.amount_out / q.amount_in
                return time_score * 0.3 + value_score * 0.7

        return max(quotes, key=score_quote)

    def _get_available_bridges(
        self,
        source: Chain,
        dest: Chain
    ) -> List[BridgeProtocol]:
        """Get available bridges for a chain pair."""
        # Simplified availability matrix
        all_bridges = list(BridgeProtocol)

        # Solana-specific bridges
        if source == Chain.SOLANA or dest == Chain.SOLANA:
            return [
                BridgeProtocol.WORMHOLE,
                BridgeProtocol.ALLBRIDGE,
                BridgeProtocol.DEBRIDGE,
                BridgeProtocol.MAYAN
            ]

        # EVM chains
        return [
            BridgeProtocol.LAYERZERO,
            BridgeProtocol.ACROSS,
            BridgeProtocol.STARGATE,
            BridgeProtocol.HOP,
            BridgeProtocol.CELER
        ]

    def update_bridge_health(
        self,
        bridge: BridgeProtocol,
        status: str,
        tvl_usd: float,
        volume_24h: float,
        avg_time_minutes: float,
        success_rate: float,
        last_incident: Optional[datetime] = None
    ):
        """Update bridge health status."""
        # Determine risk level
        if success_rate < 0.95 or status == "degraded":
            risk_level = BridgeRisk.MEDIUM
        elif success_rate < 0.9 or status == "down":
            risk_level = BridgeRisk.HIGH
        elif tvl_usd < 10_000_000:
            risk_level = BridgeRisk.MEDIUM
        else:
            risk_level = BridgeRisk.LOW

        health = BridgeHealth(
            bridge=bridge,
            status=status,
            tvl_usd=tvl_usd,
            volume_24h=volume_24h,
            avg_time_minutes=avg_time_minutes,
            success_rate=success_rate,
            last_incident=last_incident,
            risk_level=risk_level
        )

        self.bridge_health[bridge] = health

        with self._get_db() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO bridge_health
                (bridge, status, tvl_usd, volume_24h, avg_time_minutes,
                 success_rate, last_incident, risk_level, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                bridge.value, status, tvl_usd, volume_24h, avg_time_minutes,
                success_rate, last_incident.isoformat() if last_incident else None,
                risk_level.value, datetime.now().isoformat()
            ))

    def get_stuck_transfers(
        self,
        threshold_minutes: int = 60
    ) -> List[BridgeTransfer]:
        """Get transfers that are stuck."""
        threshold = datetime.now() - timedelta(minutes=threshold_minutes)
        stuck = []

        for transfer in self.active_transfers.values():
            if transfer.status in [TransferStatus.PENDING, TransferStatus.IN_TRANSIT]:
                if transfer.created_at < threshold:
                    transfer.status = TransferStatus.STUCK
                    stuck.append(transfer)

        return stuck

    def register_status_callback(
        self,
        callback: Callable[[BridgeTransfer, TransferStatus, TransferStatus], None]
    ):
        """Register callback for status changes."""
        self.status_callbacks.append(callback)

    def register_completion_callback(
        self,
        callback: Callable[[BridgeTransfer], None]
    ):
        """Register callback for completed transfers."""
        self.completion_callbacks.append(callback)

    async def start_monitoring(self, interval: float = 30.0):
        """Start monitoring active transfers."""
        self._monitoring = True

        while self._monitoring:
            # Check for stuck transfers
            stuck = self.get_stuck_transfers()
            for transfer in stuck:
                for callback in self.status_callbacks:
                    try:
                        callback(transfer, TransferStatus.IN_TRANSIT, TransferStatus.STUCK)
                    except Exception:
                        pass

            await asyncio.sleep(interval)

    def stop_monitoring(self):
        """Stop monitoring."""
        self._monitoring = False

    def get_statistics(self) -> Dict:
        """Get bridge statistics."""
        with self._get_db() as conn:
            total = conn.execute("SELECT COUNT(*) FROM transfers").fetchone()[0]
            completed = conn.execute(
                "SELECT COUNT(*) FROM transfers WHERE status = 'completed'"
            ).fetchone()[0]
            total_volume = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM transfers WHERE status = 'completed'"
            ).fetchone()[0]
            total_fees = conn.execute(
                "SELECT COALESCE(SUM(fee), 0) FROM transfers WHERE status = 'completed'"
            ).fetchone()[0]

        return {
            "total_transfers": total,
            "completed_transfers": completed,
            "active_transfers": len(self.active_transfers),
            "success_rate": completed / total if total > 0 else 0,
            "total_volume": total_volume,
            "total_fees_paid": total_fees
        }


# Singleton instance
_bridge_monitor: Optional[BridgeMonitor] = None


def get_bridge_monitor() -> BridgeMonitor:
    """Get or create the bridge monitor singleton."""
    global _bridge_monitor
    if _bridge_monitor is None:
        _bridge_monitor = BridgeMonitor()
    return _bridge_monitor
