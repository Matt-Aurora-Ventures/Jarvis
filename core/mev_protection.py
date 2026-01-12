"""
MEV Protection - Protection against sandwich attacks, front-running, and MEV extraction.
Implements transaction privacy, slippage protection, and MEV-aware routing.
"""
import asyncio
import hashlib
import secrets
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Callable


class MEVThreatType(Enum):
    """Types of MEV threats."""
    SANDWICH = "sandwich"           # Sandwich attack
    FRONTRUN = "frontrun"           # Front-running
    BACKRUN = "backrun"             # Back-running
    JIT_LIQUIDITY = "jit"           # Just-in-time liquidity
    ARBITRAGE = "arbitrage"         # Cross-DEX arbitrage
    LIQUIDATION = "liquidation"     # Liquidation hunting


class ProtectionStrategy(Enum):
    """MEV protection strategies."""
    PRIVATE_MEMPOOL = "private"     # Submit to private mempool
    FLASHBOTS = "flashbots"         # Use Flashbots/Jito bundles
    COMMIT_REVEAL = "commit_reveal" # Two-phase commit
    TIME_DELAY = "time_delay"       # Randomized delay
    SPLIT_ORDER = "split_order"     # Split into smaller orders
    STEALTH_ADDRESS = "stealth"     # Use stealth addresses
    DECOY_TX = "decoy"              # Submit decoy transactions


class TxStatus(Enum):
    """Transaction status."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    SANDWICHED = "sandwiched"
    FRONTRUN = "frontrun"


@dataclass
class MEVThreat:
    """Detected MEV threat."""
    threat_id: str
    threat_type: MEVThreatType
    confidence: float               # 0-1 confidence score
    attacker_address: Optional[str]
    target_tx: Optional[str]
    detected_at: datetime
    details: Dict = field(default_factory=dict)


@dataclass
class ProtectedTransaction:
    """A transaction with MEV protection."""
    tx_id: str
    original_tx: Dict               # Original transaction data
    protection_strategy: ProtectionStrategy
    protected_tx: Optional[Dict]    # Modified protected transaction
    status: TxStatus
    submitted_at: Optional[datetime]
    confirmed_at: Optional[datetime]
    gas_saved: float                # Estimated gas saved from MEV protection
    slippage_saved: float           # Estimated slippage saved
    metadata: Dict = field(default_factory=dict)


@dataclass
class SandwichDetection:
    """Detected sandwich attack."""
    detection_id: str
    victim_tx: str
    frontrun_tx: str
    backrun_tx: str
    profit_extracted: float
    token_pair: str
    dex: str
    block_number: int
    detected_at: datetime


@dataclass
class SlippageAnalysis:
    """Analysis of expected vs actual slippage."""
    expected_slippage: float
    actual_slippage: float
    excess_slippage: float
    is_suspicious: bool
    likely_cause: Optional[MEVThreatType]


class MEVProtection:
    """
    MEV protection system for Solana transactions.
    Protects against sandwich attacks, front-running, and other MEV extraction.
    """

    # Suspicious slippage threshold
    SUSPICIOUS_SLIPPAGE_MULTIPLIER = 2.0

    # Jito tip amounts by priority (in lamports)
    JITO_TIP_AMOUNTS = {
        "low": 1000,        # 0.000001 SOL
        "medium": 10000,    # 0.00001 SOL
        "high": 100000,     # 0.0001 SOL
        "urgent": 1000000   # 0.001 SOL
    }

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or str(
            Path(__file__).parent.parent / "data" / "mev_protection.db"
        )
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

        self.protected_txs: Dict[str, ProtectedTransaction] = {}
        self.threat_callbacks: List[Callable] = []
        self._lock = threading.Lock()

        # Jito bundle endpoint (for Solana)
        self.jito_endpoint: Optional[str] = None
        self.private_mempool_enabled = False

        # Statistics
        self.stats = {
            "txs_protected": 0,
            "threats_detected": 0,
            "slippage_saved_usd": 0.0,
            "sandwiches_prevented": 0
        }

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
                CREATE TABLE IF NOT EXISTS protected_transactions (
                    tx_id TEXT PRIMARY KEY,
                    original_tx TEXT NOT NULL,
                    protection_strategy TEXT NOT NULL,
                    protected_tx TEXT,
                    status TEXT NOT NULL,
                    submitted_at TEXT,
                    confirmed_at TEXT,
                    gas_saved REAL DEFAULT 0,
                    slippage_saved REAL DEFAULT 0,
                    metadata TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS detected_threats (
                    threat_id TEXT PRIMARY KEY,
                    threat_type TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    attacker_address TEXT,
                    target_tx TEXT,
                    detected_at TEXT NOT NULL,
                    details TEXT
                );

                CREATE TABLE IF NOT EXISTS sandwich_attacks (
                    detection_id TEXT PRIMARY KEY,
                    victim_tx TEXT NOT NULL,
                    frontrun_tx TEXT NOT NULL,
                    backrun_tx TEXT NOT NULL,
                    profit_extracted REAL NOT NULL,
                    token_pair TEXT NOT NULL,
                    dex TEXT NOT NULL,
                    block_number INTEGER NOT NULL,
                    detected_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS known_attackers (
                    address TEXT PRIMARY KEY,
                    threat_type TEXT NOT NULL,
                    attacks_count INTEGER DEFAULT 1,
                    total_profit REAL DEFAULT 0,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_threats_type ON detected_threats(threat_type);
                CREATE INDEX IF NOT EXISTS idx_sandwich_victim ON sandwich_attacks(victim_tx);
            """)

    def protect_transaction(
        self,
        tx_data: Dict,
        strategy: ProtectionStrategy = ProtectionStrategy.PRIVATE_MEMPOOL,
        max_slippage: float = 0.01,
        priority: str = "medium"
    ) -> ProtectedTransaction:
        """Apply MEV protection to a transaction."""
        import json
        import uuid

        tx_id = str(uuid.uuid4())[:12]

        # Apply protection based on strategy
        protected_tx = None
        if strategy == ProtectionStrategy.PRIVATE_MEMPOOL:
            protected_tx = self._apply_private_mempool(tx_data)
        elif strategy == ProtectionStrategy.FLASHBOTS:
            protected_tx = self._apply_jito_bundle(tx_data, priority)
        elif strategy == ProtectionStrategy.COMMIT_REVEAL:
            protected_tx = self._apply_commit_reveal(tx_data)
        elif strategy == ProtectionStrategy.TIME_DELAY:
            protected_tx = self._apply_time_delay(tx_data)
        elif strategy == ProtectionStrategy.SPLIT_ORDER:
            protected_tx = self._apply_split_order(tx_data, max_slippage)
        elif strategy == ProtectionStrategy.STEALTH_ADDRESS:
            protected_tx = self._apply_stealth_address(tx_data)
        elif strategy == ProtectionStrategy.DECOY_TX:
            protected_tx = self._apply_decoy_transactions(tx_data)

        # Estimate savings
        slippage_saved = self._estimate_slippage_savings(tx_data, strategy)

        now = datetime.now()
        protected = ProtectedTransaction(
            tx_id=tx_id,
            original_tx=tx_data,
            protection_strategy=strategy,
            protected_tx=protected_tx,
            status=TxStatus.PENDING,
            submitted_at=None,
            confirmed_at=None,
            gas_saved=0,
            slippage_saved=slippage_saved,
            metadata={"max_slippage": max_slippage, "priority": priority}
        )

        with self._lock:
            self.protected_txs[tx_id] = protected
            self.stats["txs_protected"] += 1

        # Save to database
        with self._get_db() as conn:
            conn.execute("""
                INSERT INTO protected_transactions
                (tx_id, original_tx, protection_strategy, protected_tx, status,
                 submitted_at, confirmed_at, gas_saved, slippage_saved, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?)
            """, (
                tx_id, json.dumps(tx_data), strategy.value,
                json.dumps(protected_tx) if protected_tx else None,
                protected.status.value, protected.gas_saved,
                protected.slippage_saved, json.dumps(protected.metadata),
                now.isoformat()
            ))

        return protected

    def _apply_private_mempool(self, tx_data: Dict) -> Dict:
        """Submit to private mempool (Jito on Solana)."""
        protected = tx_data.copy()
        protected["_mev_protection"] = {
            "type": "private_mempool",
            "use_jito": True,
            "skip_preflight": False
        }
        return protected

    def _apply_jito_bundle(self, tx_data: Dict, priority: str) -> Dict:
        """Create Jito bundle for transaction."""
        tip_amount = self.JITO_TIP_AMOUNTS.get(priority, self.JITO_TIP_AMOUNTS["medium"])

        protected = tx_data.copy()
        protected["_mev_protection"] = {
            "type": "jito_bundle",
            "tip_amount": tip_amount,
            "bundle_only": True
        }
        return protected

    def _apply_commit_reveal(self, tx_data: Dict) -> Dict:
        """Create commit-reveal transaction."""
        # Generate commitment
        nonce = secrets.token_hex(16)
        commitment = hashlib.sha256(
            (str(tx_data) + nonce).encode()
        ).hexdigest()

        protected = tx_data.copy()
        protected["_mev_protection"] = {
            "type": "commit_reveal",
            "phase": "commit",
            "commitment": commitment,
            "nonce": nonce,
            "reveal_delay_slots": 2
        }
        return protected

    def _apply_time_delay(self, tx_data: Dict) -> Dict:
        """Apply randomized time delay."""
        # Random delay between 1-5 seconds
        delay = secrets.randbelow(4000) + 1000  # 1000-5000ms

        protected = tx_data.copy()
        protected["_mev_protection"] = {
            "type": "time_delay",
            "delay_ms": delay,
            "randomized": True
        }
        return protected

    def _apply_split_order(self, tx_data: Dict, max_slippage: float) -> Dict:
        """Split order into smaller chunks."""
        amount = tx_data.get("amount", 0)

        # Determine optimal chunk count based on size
        if amount > 10000:
            chunks = 5
        elif amount > 1000:
            chunks = 3
        else:
            chunks = 2

        chunk_size = amount / chunks

        protected = tx_data.copy()
        protected["_mev_protection"] = {
            "type": "split_order",
            "chunks": chunks,
            "chunk_size": chunk_size,
            "delay_between_chunks_ms": secrets.randbelow(2000) + 500,
            "max_slippage_per_chunk": max_slippage / chunks
        }
        return protected

    def _apply_stealth_address(self, tx_data: Dict) -> Dict:
        """Use stealth address for transaction."""
        # Generate one-time stealth address
        stealth_key = secrets.token_hex(32)

        protected = tx_data.copy()
        protected["_mev_protection"] = {
            "type": "stealth_address",
            "stealth_key": stealth_key,
            "ephemeral": True
        }
        return protected

    def _apply_decoy_transactions(self, tx_data: Dict) -> Dict:
        """Submit decoy transactions."""
        # Generate 2-3 decoy transactions
        decoy_count = secrets.randbelow(2) + 2

        protected = tx_data.copy()
        protected["_mev_protection"] = {
            "type": "decoy",
            "decoy_count": decoy_count,
            "real_tx_index": secrets.randbelow(decoy_count + 1)
        }
        return protected

    def _estimate_slippage_savings(
        self,
        tx_data: Dict,
        strategy: ProtectionStrategy
    ) -> float:
        """Estimate slippage savings from protection."""
        amount = tx_data.get("amount", 0)

        # Estimated slippage saved by strategy
        savings_rates = {
            ProtectionStrategy.PRIVATE_MEMPOOL: 0.005,   # 0.5%
            ProtectionStrategy.FLASHBOTS: 0.008,         # 0.8%
            ProtectionStrategy.COMMIT_REVEAL: 0.003,     # 0.3%
            ProtectionStrategy.TIME_DELAY: 0.002,        # 0.2%
            ProtectionStrategy.SPLIT_ORDER: 0.004,       # 0.4%
            ProtectionStrategy.STEALTH_ADDRESS: 0.003,   # 0.3%
            ProtectionStrategy.DECOY_TX: 0.002           # 0.2%
        }

        rate = savings_rates.get(strategy, 0.003)
        return amount * rate

    def detect_sandwich_attack(
        self,
        victim_tx: str,
        block_txs: List[Dict]
    ) -> Optional[SandwichDetection]:
        """Detect if a transaction was sandwiched."""
        import uuid

        victim_idx = None
        for i, tx in enumerate(block_txs):
            if tx.get("signature") == victim_tx:
                victim_idx = i
                break

        if victim_idx is None or victim_idx == 0 or victim_idx >= len(block_txs) - 1:
            return None

        # Check transactions before and after
        pre_tx = block_txs[victim_idx - 1]
        post_tx = block_txs[victim_idx + 1]
        victim = block_txs[victim_idx]

        # Look for sandwich patterns
        if not self._is_potential_sandwich(pre_tx, victim, post_tx):
            return None

        # Calculate profit extracted
        profit = self._calculate_sandwich_profit(pre_tx, post_tx)

        detection = SandwichDetection(
            detection_id=str(uuid.uuid4())[:8],
            victim_tx=victim_tx,
            frontrun_tx=pre_tx.get("signature", ""),
            backrun_tx=post_tx.get("signature", ""),
            profit_extracted=profit,
            token_pair=victim.get("token_pair", "UNKNOWN"),
            dex=victim.get("dex", "unknown"),
            block_number=victim.get("block", 0),
            detected_at=datetime.now()
        )

        # Record in database
        with self._get_db() as conn:
            conn.execute("""
                INSERT INTO sandwich_attacks
                (detection_id, victim_tx, frontrun_tx, backrun_tx, profit_extracted,
                 token_pair, dex, block_number, detected_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                detection.detection_id, detection.victim_tx,
                detection.frontrun_tx, detection.backrun_tx,
                detection.profit_extracted, detection.token_pair,
                detection.dex, detection.block_number,
                detection.detected_at.isoformat()
            ))

            # Track attacker
            attacker = pre_tx.get("signer", "")
            if attacker:
                conn.execute("""
                    INSERT INTO known_attackers
                    (address, threat_type, attacks_count, total_profit, first_seen, last_seen)
                    VALUES (?, 'sandwich', 1, ?, ?, ?)
                    ON CONFLICT(address) DO UPDATE SET
                    attacks_count = attacks_count + 1,
                    total_profit = total_profit + ?,
                    last_seen = ?
                """, (
                    attacker, profit, detection.detected_at.isoformat(),
                    detection.detected_at.isoformat(), profit,
                    detection.detected_at.isoformat()
                ))

        self.stats["threats_detected"] += 1

        return detection

    def _is_potential_sandwich(
        self,
        pre_tx: Dict,
        victim_tx: Dict,
        post_tx: Dict
    ) -> bool:
        """Check if transactions match sandwich pattern."""
        # Same token pair
        if pre_tx.get("token_pair") != victim_tx.get("token_pair"):
            return False
        if post_tx.get("token_pair") != victim_tx.get("token_pair"):
            return False

        # Same DEX
        if pre_tx.get("dex") != victim_tx.get("dex"):
            return False

        # Pre and post have same signer (attacker)
        if pre_tx.get("signer") != post_tx.get("signer"):
            return False

        # Pre is buy, post is sell (or vice versa)
        pre_side = pre_tx.get("side", "").lower()
        post_side = post_tx.get("side", "").lower()

        if not ((pre_side == "buy" and post_side == "sell") or
                (pre_side == "sell" and post_side == "buy")):
            return False

        return True

    def _calculate_sandwich_profit(self, frontrun: Dict, backrun: Dict) -> float:
        """Calculate profit extracted from sandwich."""
        front_amount = frontrun.get("amount", 0)
        front_price = frontrun.get("price", 0)
        back_amount = backrun.get("amount", 0)
        back_price = backrun.get("price", 0)

        if frontrun.get("side") == "buy":
            # Bought low, sold high
            profit = (back_price - front_price) * min(front_amount, back_amount)
        else:
            # Sold high, bought low
            profit = (front_price - back_price) * min(front_amount, back_amount)

        return max(0, profit)

    def analyze_slippage(
        self,
        expected_slippage: float,
        actual_slippage: float
    ) -> SlippageAnalysis:
        """Analyze if slippage was caused by MEV."""
        excess = actual_slippage - expected_slippage
        is_suspicious = actual_slippage > expected_slippage * self.SUSPICIOUS_SLIPPAGE_MULTIPLIER

        likely_cause = None
        if is_suspicious:
            if excess > 0.02:  # > 2% excess
                likely_cause = MEVThreatType.SANDWICH
            elif excess > 0.01:  # > 1% excess
                likely_cause = MEVThreatType.FRONTRUN
            else:
                likely_cause = MEVThreatType.JIT_LIQUIDITY

        return SlippageAnalysis(
            expected_slippage=expected_slippage,
            actual_slippage=actual_slippage,
            excess_slippage=max(0, excess),
            is_suspicious=is_suspicious,
            likely_cause=likely_cause
        )

    def detect_frontrunning(
        self,
        pending_tx: Dict,
        recent_txs: List[Dict]
    ) -> Optional[MEVThreat]:
        """Detect potential front-running of a pending transaction."""
        import uuid

        target_token = pending_tx.get("token")
        target_dex = pending_tx.get("dex")
        target_side = pending_tx.get("side")

        for tx in recent_txs:
            if tx.get("confirmed", False):
                continue

            # Same token, same DEX, same side, different signer
            if (tx.get("token") == target_token and
                tx.get("dex") == target_dex and
                tx.get("side") == target_side and
                tx.get("signer") != pending_tx.get("signer")):

                # Check if it was submitted after our tx was visible
                if tx.get("first_seen", 0) > pending_tx.get("first_seen", 0):
                    threat = MEVThreat(
                        threat_id=str(uuid.uuid4())[:8],
                        threat_type=MEVThreatType.FRONTRUN,
                        confidence=0.7,
                        attacker_address=tx.get("signer"),
                        target_tx=pending_tx.get("signature"),
                        detected_at=datetime.now(),
                        details={
                            "frontrun_tx": tx.get("signature"),
                            "token": target_token,
                            "dex": target_dex
                        }
                    )

                    self._record_threat(threat)
                    return threat

        return None

    def _record_threat(self, threat: MEVThreat):
        """Record detected threat to database."""
        import json

        with self._get_db() as conn:
            conn.execute("""
                INSERT INTO detected_threats
                (threat_id, threat_type, confidence, attacker_address,
                 target_tx, detected_at, details)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                threat.threat_id, threat.threat_type.value,
                threat.confidence, threat.attacker_address,
                threat.target_tx, threat.detected_at.isoformat(),
                json.dumps(threat.details)
            ))

        self.stats["threats_detected"] += 1

        # Notify callbacks
        for callback in self.threat_callbacks:
            try:
                callback(threat)
            except Exception:
                pass

    def get_known_attackers(self, limit: int = 50) -> List[Dict]:
        """Get list of known MEV attackers."""
        with self._get_db() as conn:
            rows = conn.execute("""
                SELECT * FROM known_attackers
                ORDER BY total_profit DESC
                LIMIT ?
            """, (limit,)).fetchall()

            return [dict(row) for row in rows]

    def is_known_attacker(self, address: str) -> bool:
        """Check if an address is a known MEV attacker."""
        with self._get_db() as conn:
            row = conn.execute(
                "SELECT 1 FROM known_attackers WHERE address = ?",
                (address,)
            ).fetchone()
            return row is not None

    def get_optimal_strategy(
        self,
        tx_data: Dict,
        urgency: str = "normal"
    ) -> ProtectionStrategy:
        """Determine optimal protection strategy for a transaction."""
        amount = tx_data.get("amount", 0)
        token = tx_data.get("token", "")

        # High-value transactions
        if amount > 10000:
            if urgency == "high":
                return ProtectionStrategy.FLASHBOTS
            else:
                return ProtectionStrategy.SPLIT_ORDER

        # MEV-heavy tokens (memecoins, new tokens)
        mev_heavy_tokens = ["BONK", "WIF", "PEPE", "POPCAT"]
        if any(t in token.upper() for t in mev_heavy_tokens):
            return ProtectionStrategy.FLASHBOTS

        # Default strategy
        if self.jito_endpoint:
            return ProtectionStrategy.FLASHBOTS
        else:
            return ProtectionStrategy.PRIVATE_MEMPOOL

    def register_threat_callback(self, callback: Callable[[MEVThreat], None]):
        """Register callback for threat detection."""
        self.threat_callbacks.append(callback)

    def get_statistics(self) -> Dict:
        """Get MEV protection statistics."""
        with self._get_db() as conn:
            total_attacks = conn.execute(
                "SELECT COUNT(*) FROM sandwich_attacks"
            ).fetchone()[0]

            total_profit_stolen = conn.execute(
                "SELECT COALESCE(SUM(profit_extracted), 0) FROM sandwich_attacks"
            ).fetchone()[0]

        return {
            **self.stats,
            "total_sandwich_attacks_detected": total_attacks,
            "total_profit_stolen_detected": total_profit_stolen
        }

    def configure_jito(self, endpoint: str, api_key: Optional[str] = None):
        """Configure Jito bundle endpoint."""
        self.jito_endpoint = endpoint
        if api_key:
            self.jito_api_key = api_key

    def enable_private_mempool(self, enabled: bool = True):
        """Enable/disable private mempool submission."""
        self.private_mempool_enabled = enabled


# Singleton instance
_mev_protection: Optional[MEVProtection] = None


def get_mev_protection() -> MEVProtection:
    """Get or create the MEV protection singleton."""
    global _mev_protection
    if _mev_protection is None:
        _mev_protection = MEVProtection()
    return _mev_protection
