"""
Gas/Priority Fee Optimizer - Optimize transaction fees on Solana.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import json
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from collections import deque

logger = logging.getLogger(__name__)


class PriorityLevel(Enum):
    """Transaction priority levels."""
    LOW = "low"  # Cheapest, may take longer
    MEDIUM = "medium"  # Default, balanced
    HIGH = "high"  # Faster, more expensive
    URGENT = "urgent"  # Fastest, most expensive


class NetworkCondition(Enum):
    """Network congestion levels."""
    IDLE = "idle"
    NORMAL = "normal"
    BUSY = "busy"
    CONGESTED = "congested"


@dataclass
class FeeEstimate:
    """Fee estimation result."""
    priority: PriorityLevel
    priority_fee: int  # In micro-lamports
    compute_units: int
    total_fee_lamports: int
    total_fee_sol: float
    total_fee_usd: float
    estimated_time_ms: int
    confidence: float


@dataclass
class FeeRecommendation:
    """Fee recommendation."""
    recommended_priority: PriorityLevel
    priority_fee: int
    compute_units: int
    rationale: str
    alternatives: List[FeeEstimate]


@dataclass
class TransactionCost:
    """Record of transaction cost."""
    tx_signature: str
    priority_level: PriorityLevel
    priority_fee: int
    compute_units_requested: int
    compute_units_used: int
    base_fee: int
    priority_fee_paid: int
    total_fee_lamports: int
    confirmation_time_ms: int
    slot: int
    timestamp: str
    success: bool


class GasOptimizerDB:
    """SQLite storage for gas optimization data."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transaction_costs (
                    tx_signature TEXT PRIMARY KEY,
                    priority_level TEXT,
                    priority_fee INTEGER,
                    compute_units_requested INTEGER,
                    compute_units_used INTEGER,
                    base_fee INTEGER,
                    priority_fee_paid INTEGER,
                    total_fee_lamports INTEGER,
                    confirmation_time_ms INTEGER,
                    slot INTEGER,
                    timestamp TEXT,
                    success INTEGER
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS fee_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    network_condition TEXT,
                    avg_priority_fee INTEGER,
                    median_priority_fee INTEGER,
                    p75_priority_fee INTEGER,
                    p90_priority_fee INTEGER,
                    slot INTEGER
                )
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_costs_time ON transaction_costs(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_time ON fee_snapshots(timestamp)")

            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()


class GasOptimizer:
    """
    Optimize transaction fees on Solana.

    Usage:
        optimizer = GasOptimizer()

        # Get fee recommendation
        recommendation = optimizer.get_recommendation(
            compute_units=200000,
            priority=PriorityLevel.MEDIUM
        )

        # Estimate fees for all priority levels
        estimates = optimizer.estimate_fees(compute_units=200000)

        # Record transaction cost
        optimizer.record_transaction(tx_signature, cost_data)
    """

    # Base fee constants (micro-lamports per signature)
    BASE_FEE_LAMPORTS = 5000

    # Default compute unit prices by priority (micro-lamports per CU)
    DEFAULT_PRIORITY_FEES = {
        PriorityLevel.LOW: 1,
        PriorityLevel.MEDIUM: 1000,
        PriorityLevel.HIGH: 10000,
        PriorityLevel.URGENT: 100000
    }

    # Estimated confirmation times (ms)
    ESTIMATED_TIMES = {
        PriorityLevel.LOW: 60000,
        PriorityLevel.MEDIUM: 2000,
        PriorityLevel.HIGH: 500,
        PriorityLevel.URGENT: 400
    }

    def __init__(self, db_path: Optional[Path] = None):
        db_path = db_path or Path(__file__).parent.parent / "data" / "gas_optimizer.db"
        self.db = GasOptimizerDB(db_path)

        # Recent fee data
        self._recent_fees: deque = deque(maxlen=1000)
        self._recent_times: Dict[PriorityLevel, deque] = {
            level: deque(maxlen=100) for level in PriorityLevel
        }

        # Current network state
        self._network_condition = NetworkCondition.NORMAL
        self._sol_price_usd = 100.0  # Default, should be updated

        self._load_recent_data()

    def _load_recent_data(self):
        """Load recent transaction data."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM transaction_costs
                WHERE datetime(timestamp) > datetime('now', '-1 hour')
                ORDER BY timestamp DESC
            """)

            for row in cursor.fetchall():
                self._recent_fees.append(row['priority_fee'])
                level = PriorityLevel(row['priority_level'])
                self._recent_times[level].append(row['confirmation_time_ms'])

    def update_sol_price(self, price_usd: float):
        """Update SOL price for USD calculations."""
        self._sol_price_usd = price_usd

    def update_network_condition(self, condition: NetworkCondition):
        """Update network condition."""
        self._network_condition = condition

    def get_priority_fee(self, priority: PriorityLevel) -> int:
        """Get priority fee for a given level."""
        # Use historical data if available
        if self._recent_fees:
            fees = sorted(self._recent_fees)
            n = len(fees)

            if priority == PriorityLevel.LOW:
                return fees[int(n * 0.1)]
            elif priority == PriorityLevel.MEDIUM:
                return fees[int(n * 0.5)]
            elif priority == PriorityLevel.HIGH:
                return fees[int(n * 0.75)]
            elif priority == PriorityLevel.URGENT:
                return fees[int(n * 0.95)]

        # Fall back to defaults
        base_fee = self.DEFAULT_PRIORITY_FEES[priority]

        # Adjust for network conditions
        if self._network_condition == NetworkCondition.CONGESTED:
            base_fee *= 5
        elif self._network_condition == NetworkCondition.BUSY:
            base_fee *= 2
        elif self._network_condition == NetworkCondition.IDLE:
            base_fee = max(1, base_fee // 2)

        return base_fee

    def estimate_fees(self, compute_units: int = 200000) -> List[FeeEstimate]:
        """Estimate fees for all priority levels."""
        estimates = []

        for priority in PriorityLevel:
            estimate = self._estimate_fee(priority, compute_units)
            estimates.append(estimate)

        return estimates

    def _estimate_fee(self, priority: PriorityLevel, compute_units: int) -> FeeEstimate:
        """Estimate fee for a specific priority level."""
        priority_fee = self.get_priority_fee(priority)

        # Calculate total fee
        # Priority fee = (compute_units * priority_fee_per_cu) / 1_000_000
        priority_fee_lamports = (compute_units * priority_fee) // 1_000_000
        total_fee_lamports = self.BASE_FEE_LAMPORTS + priority_fee_lamports

        # Convert to SOL and USD
        total_fee_sol = total_fee_lamports / 1_000_000_000
        total_fee_usd = total_fee_sol * self._sol_price_usd

        # Estimate confirmation time
        estimated_time = self.ESTIMATED_TIMES[priority]
        if self._recent_times[priority]:
            avg_recent = sum(self._recent_times[priority]) / len(self._recent_times[priority])
            estimated_time = int(avg_recent * 0.7 + estimated_time * 0.3)

        # Confidence based on data availability
        confidence = min(len(self._recent_fees) / 100, 1.0)

        return FeeEstimate(
            priority=priority,
            priority_fee=priority_fee,
            compute_units=compute_units,
            total_fee_lamports=total_fee_lamports,
            total_fee_sol=total_fee_sol,
            total_fee_usd=total_fee_usd,
            estimated_time_ms=estimated_time,
            confidence=confidence
        )

    def get_recommendation(
        self,
        compute_units: int = 200000,
        priority: PriorityLevel = PriorityLevel.MEDIUM,
        max_fee_usd: Optional[float] = None,
        max_time_ms: Optional[int] = None
    ) -> FeeRecommendation:
        """Get fee recommendation."""
        estimates = self.estimate_fees(compute_units)

        # Start with requested priority
        recommended = estimates[list(PriorityLevel).index(priority)]
        rationale_parts = []

        # Check constraints
        if max_fee_usd and recommended.total_fee_usd > max_fee_usd:
            # Find cheaper option
            for est in estimates:
                if est.total_fee_usd <= max_fee_usd:
                    recommended = est
                    rationale_parts.append(f"Adjusted to stay under ${max_fee_usd:.4f} budget")
                    break

        if max_time_ms and recommended.estimated_time_ms > max_time_ms:
            # Find faster option
            for est in reversed(estimates):
                if est.estimated_time_ms <= max_time_ms:
                    if not max_fee_usd or est.total_fee_usd <= max_fee_usd:
                        recommended = est
                        rationale_parts.append(f"Upgraded for faster confirmation (<{max_time_ms}ms)")
                        break

        # Add network condition context
        if self._network_condition == NetworkCondition.CONGESTED:
            rationale_parts.append("Network is congested - higher fees recommended")
        elif self._network_condition == NetworkCondition.IDLE:
            rationale_parts.append("Network is idle - lower fees may suffice")

        rationale = ". ".join(rationale_parts) if rationale_parts else "Standard recommendation based on current conditions"

        return FeeRecommendation(
            recommended_priority=recommended.priority,
            priority_fee=recommended.priority_fee,
            compute_units=compute_units,
            rationale=rationale,
            alternatives=estimates
        )

    def record_transaction(
        self,
        tx_signature: str,
        priority_level: PriorityLevel,
        priority_fee: int,
        compute_units_requested: int,
        compute_units_used: int,
        total_fee_lamports: int,
        confirmation_time_ms: int,
        slot: int,
        success: bool = True
    ):
        """Record transaction cost data."""
        now = datetime.now(timezone.utc).isoformat()

        cost = TransactionCost(
            tx_signature=tx_signature,
            priority_level=priority_level,
            priority_fee=priority_fee,
            compute_units_requested=compute_units_requested,
            compute_units_used=compute_units_used,
            base_fee=self.BASE_FEE_LAMPORTS,
            priority_fee_paid=(compute_units_used * priority_fee) // 1_000_000,
            total_fee_lamports=total_fee_lamports,
            confirmation_time_ms=confirmation_time_ms,
            slot=slot,
            timestamp=now,
            success=success
        )

        # Save to database
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO transaction_costs
                (tx_signature, priority_level, priority_fee, compute_units_requested,
                 compute_units_used, base_fee, priority_fee_paid, total_fee_lamports,
                 confirmation_time_ms, slot, timestamp, success)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                cost.tx_signature, cost.priority_level.value, cost.priority_fee,
                cost.compute_units_requested, cost.compute_units_used,
                cost.base_fee, cost.priority_fee_paid, cost.total_fee_lamports,
                cost.confirmation_time_ms, cost.slot, cost.timestamp,
                1 if cost.success else 0
            ))
            conn.commit()

        # Update in-memory data
        self._recent_fees.append(priority_fee)
        self._recent_times[priority_level].append(confirmation_time_ms)

        logger.debug(f"Recorded tx {tx_signature[:8]}...: {total_fee_lamports} lamports, {confirmation_time_ms}ms")

    def save_fee_snapshot(self):
        """Save current fee snapshot."""
        if not self._recent_fees:
            return

        fees = sorted(self._recent_fees)
        n = len(fees)

        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO fee_snapshots
                (timestamp, network_condition, avg_priority_fee, median_priority_fee,
                 p75_priority_fee, p90_priority_fee, slot)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now(timezone.utc).isoformat(),
                self._network_condition.value,
                int(sum(fees) / n),
                fees[int(n * 0.5)],
                fees[int(n * 0.75)],
                fees[int(n * 0.9)],
                0  # Would need actual slot
            ))
            conn.commit()

    def get_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """Get fee statistics."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    COUNT(*) as total_txs,
                    AVG(total_fee_lamports) as avg_fee,
                    MIN(total_fee_lamports) as min_fee,
                    MAX(total_fee_lamports) as max_fee,
                    AVG(confirmation_time_ms) as avg_time,
                    SUM(total_fee_lamports) as total_spent,
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful
                FROM transaction_costs
                WHERE datetime(timestamp) > datetime('now', ?)
            """, (f'-{hours} hours',))

            row = cursor.fetchone()

            total_txs = row['total_txs'] or 0
            total_spent_lamports = row['total_spent'] or 0
            total_spent_sol = total_spent_lamports / 1_000_000_000

            # By priority level
            cursor.execute("""
                SELECT
                    priority_level,
                    COUNT(*) as count,
                    AVG(total_fee_lamports) as avg_fee,
                    AVG(confirmation_time_ms) as avg_time
                FROM transaction_costs
                WHERE datetime(timestamp) > datetime('now', ?)
                GROUP BY priority_level
            """, (f'-{hours} hours',))

            by_priority = {
                r['priority_level']: {
                    'count': r['count'],
                    'avg_fee_lamports': r['avg_fee'],
                    'avg_time_ms': r['avg_time']
                }
                for r in cursor.fetchall()
            }

            return {
                'period_hours': hours,
                'total_transactions': total_txs,
                'successful_transactions': row['successful'] or 0,
                'success_rate': (row['successful'] or 0) / total_txs if total_txs > 0 else 0,
                'avg_fee_lamports': row['avg_fee'] or 0,
                'min_fee_lamports': row['min_fee'] or 0,
                'max_fee_lamports': row['max_fee'] or 0,
                'avg_confirmation_ms': row['avg_time'] or 0,
                'total_spent_sol': total_spent_sol,
                'total_spent_usd': total_spent_sol * self._sol_price_usd,
                'by_priority': by_priority,
                'network_condition': self._network_condition.value
            }

    def get_optimal_compute_units(self, instruction_count: int = 1) -> int:
        """Estimate optimal compute units for transaction."""
        # Base CU per instruction
        base_cu = 50000

        # Add buffer
        buffer = 1.2

        return int(instruction_count * base_cu * buffer)


# Singleton
_optimizer: Optional[GasOptimizer] = None


def get_gas_optimizer() -> GasOptimizer:
    """Get singleton gas optimizer."""
    global _optimizer
    if _optimizer is None:
        _optimizer = GasOptimizer()
    return _optimizer
