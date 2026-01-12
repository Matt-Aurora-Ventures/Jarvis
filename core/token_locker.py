"""
Token Locker - Manage token locks, vesting schedules, and unlock tracking.
Track LP locks, team tokens, and vesting schedules for risk assessment.
"""
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional


class LockType(Enum):
    """Types of token locks."""
    LP_LOCK = "lp_lock"            # Liquidity pool lock
    TEAM_LOCK = "team_lock"        # Team token lock
    VESTING = "vesting"            # Vesting schedule
    TREASURY = "treasury"          # Treasury lock
    AIRDROP = "airdrop"            # Airdrop vesting
    INVESTOR = "investor"          # Investor lock
    STAKING = "staking"            # Staking lock


class LockPlatform(Enum):
    """Lock platforms."""
    STREAMFLOW = "streamflow"
    MEAN_FINANCE = "mean_finance"
    UNCX = "uncx"
    TEAM_FINANCE = "team_finance"
    CUSTOM = "custom"
    INTERNAL = "internal"


class LockStatus(Enum):
    """Lock status."""
    ACTIVE = "active"              # Currently locked
    UNLOCKING = "unlocking"        # In vesting/cliff
    UNLOCKED = "unlocked"          # Fully unlocked
    CANCELLED = "cancelled"        # Lock cancelled


@dataclass
class TokenLock:
    """A token lock entry."""
    lock_id: str
    token_address: str
    token_symbol: str
    lock_type: LockType
    platform: LockPlatform
    owner: str
    recipient: str
    total_amount: float
    locked_amount: float
    unlocked_amount: float
    lock_date: datetime
    unlock_start: datetime
    unlock_end: datetime
    cliff_date: Optional[datetime]
    vesting_period_days: int
    status: LockStatus
    tx_hash: Optional[str]
    metadata: Dict = field(default_factory=dict)


@dataclass
class VestingSchedule:
    """Vesting schedule details."""
    schedule_id: str
    token_address: str
    token_symbol: str
    beneficiary: str
    total_amount: float
    released_amount: float
    pending_amount: float
    start_date: datetime
    cliff_date: Optional[datetime]
    end_date: datetime
    release_frequency: str         # "daily", "weekly", "monthly", "linear"
    next_release_date: Optional[datetime]
    next_release_amount: float
    status: str


@dataclass
class UnlockEvent:
    """Upcoming unlock event."""
    event_id: str
    lock_id: str
    token_address: str
    token_symbol: str
    amount: float
    percent_of_supply: float
    unlock_date: datetime
    lock_type: LockType
    impact_assessment: str         # "low", "medium", "high", "critical"


@dataclass
class LockAnalysis:
    """Analysis of token locks for a project."""
    token_address: str
    token_symbol: str
    total_supply: float
    locked_amount: float
    locked_percent: float
    lp_locked_percent: float
    team_locked_percent: float
    vesting_locked_percent: float
    unlock_in_7d: float
    unlock_in_30d: float
    unlock_in_90d: float
    risk_score: float              # 0-100 (higher = more risky)
    analyzed_at: datetime


class TokenLocker:
    """
    Manages and tracks token locks, vesting schedules, and unlocks.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or str(
            Path(__file__).parent.parent / "data" / "token_locker.db"
        )
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

        self.locks: Dict[str, TokenLock] = {}
        self.schedules: Dict[str, VestingSchedule] = {}
        self._lock = threading.Lock()

        # Callbacks for unlock alerts
        self.unlock_callbacks: List = []

        self._load_locks()

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
                CREATE TABLE IF NOT EXISTS token_locks (
                    lock_id TEXT PRIMARY KEY,
                    token_address TEXT NOT NULL,
                    token_symbol TEXT NOT NULL,
                    lock_type TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    recipient TEXT NOT NULL,
                    total_amount REAL NOT NULL,
                    locked_amount REAL NOT NULL,
                    unlocked_amount REAL DEFAULT 0,
                    lock_date TEXT NOT NULL,
                    unlock_start TEXT NOT NULL,
                    unlock_end TEXT NOT NULL,
                    cliff_date TEXT,
                    vesting_period_days INTEGER DEFAULT 0,
                    status TEXT NOT NULL,
                    tx_hash TEXT,
                    metadata TEXT
                );

                CREATE TABLE IF NOT EXISTS vesting_schedules (
                    schedule_id TEXT PRIMARY KEY,
                    token_address TEXT NOT NULL,
                    token_symbol TEXT NOT NULL,
                    beneficiary TEXT NOT NULL,
                    total_amount REAL NOT NULL,
                    released_amount REAL DEFAULT 0,
                    start_date TEXT NOT NULL,
                    cliff_date TEXT,
                    end_date TEXT NOT NULL,
                    release_frequency TEXT NOT NULL,
                    status TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS unlock_events (
                    event_id TEXT PRIMARY KEY,
                    lock_id TEXT NOT NULL,
                    token_address TEXT NOT NULL,
                    token_symbol TEXT NOT NULL,
                    amount REAL NOT NULL,
                    percent_of_supply REAL NOT NULL,
                    unlock_date TEXT NOT NULL,
                    lock_type TEXT NOT NULL,
                    impact_assessment TEXT NOT NULL,
                    notified INTEGER DEFAULT 0,
                    FOREIGN KEY (lock_id) REFERENCES token_locks(lock_id)
                );

                CREATE INDEX IF NOT EXISTS idx_locks_token ON token_locks(token_address);
                CREATE INDEX IF NOT EXISTS idx_locks_status ON token_locks(status);
                CREATE INDEX IF NOT EXISTS idx_events_date ON unlock_events(unlock_date);
            """)

    def _load_locks(self):
        """Load active locks from database."""
        import json

        with self._get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM token_locks WHERE status IN ('active', 'unlocking')"
            ).fetchall()

            for row in rows:
                lock = TokenLock(
                    lock_id=row["lock_id"],
                    token_address=row["token_address"],
                    token_symbol=row["token_symbol"],
                    lock_type=LockType(row["lock_type"]),
                    platform=LockPlatform(row["platform"]),
                    owner=row["owner"],
                    recipient=row["recipient"],
                    total_amount=row["total_amount"],
                    locked_amount=row["locked_amount"],
                    unlocked_amount=row["unlocked_amount"],
                    lock_date=datetime.fromisoformat(row["lock_date"]),
                    unlock_start=datetime.fromisoformat(row["unlock_start"]),
                    unlock_end=datetime.fromisoformat(row["unlock_end"]),
                    cliff_date=datetime.fromisoformat(row["cliff_date"]) if row["cliff_date"] else None,
                    vesting_period_days=row["vesting_period_days"],
                    status=LockStatus(row["status"]),
                    tx_hash=row["tx_hash"],
                    metadata=json.loads(row["metadata"] or "{}")
                )
                self.locks[lock.lock_id] = lock

    def add_lock(
        self,
        token_address: str,
        token_symbol: str,
        lock_type: LockType,
        amount: float,
        unlock_date: datetime,
        owner: str,
        recipient: Optional[str] = None,
        platform: LockPlatform = LockPlatform.INTERNAL,
        cliff_date: Optional[datetime] = None,
        vesting_period_days: int = 0,
        tx_hash: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> TokenLock:
        """Add a new token lock."""
        import json
        import uuid

        now = datetime.now()
        lock = TokenLock(
            lock_id=str(uuid.uuid4())[:12],
            token_address=token_address,
            token_symbol=token_symbol,
            lock_type=lock_type,
            platform=platform,
            owner=owner,
            recipient=recipient or owner,
            total_amount=amount,
            locked_amount=amount,
            unlocked_amount=0,
            lock_date=now,
            unlock_start=cliff_date or unlock_date,
            unlock_end=unlock_date,
            cliff_date=cliff_date,
            vesting_period_days=vesting_period_days,
            status=LockStatus.ACTIVE,
            tx_hash=tx_hash,
            metadata=metadata or {}
        )

        with self._lock:
            self.locks[lock.lock_id] = lock

        with self._get_db() as conn:
            conn.execute("""
                INSERT INTO token_locks
                (lock_id, token_address, token_symbol, lock_type, platform,
                 owner, recipient, total_amount, locked_amount, unlocked_amount,
                 lock_date, unlock_start, unlock_end, cliff_date,
                 vesting_period_days, status, tx_hash, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                lock.lock_id, token_address, token_symbol, lock_type.value,
                platform.value, owner, lock.recipient, amount, amount, 0,
                now.isoformat(), lock.unlock_start.isoformat(),
                unlock_date.isoformat(),
                cliff_date.isoformat() if cliff_date else None,
                vesting_period_days, LockStatus.ACTIVE.value, tx_hash,
                json.dumps(metadata or {})
            ))

        # Create unlock event
        self._create_unlock_event(lock)

        return lock

    def _create_unlock_event(self, lock: TokenLock):
        """Create unlock event for a lock."""
        import uuid

        # Simplified - would need token supply for accurate percent
        event = UnlockEvent(
            event_id=str(uuid.uuid4())[:12],
            lock_id=lock.lock_id,
            token_address=lock.token_address,
            token_symbol=lock.token_symbol,
            amount=lock.total_amount,
            percent_of_supply=0,  # Would calculate from supply
            unlock_date=lock.unlock_end,
            lock_type=lock.lock_type,
            impact_assessment=self._assess_impact(lock)
        )

        with self._get_db() as conn:
            conn.execute("""
                INSERT INTO unlock_events
                (event_id, lock_id, token_address, token_symbol, amount,
                 percent_of_supply, unlock_date, lock_type, impact_assessment)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.event_id, event.lock_id, event.token_address,
                event.token_symbol, event.amount, event.percent_of_supply,
                event.unlock_date.isoformat(), event.lock_type.value,
                event.impact_assessment
            ))

    def _assess_impact(self, lock: TokenLock) -> str:
        """Assess impact of an unlock."""
        # Simplified impact assessment
        if lock.lock_type == LockType.LP_LOCK:
            return "critical"  # LP unlocks are always critical
        elif lock.lock_type == LockType.TEAM_LOCK:
            return "high"
        elif lock.total_amount > 1000000:
            return "medium"
        return "low"

    def update_lock_status(
        self,
        lock_id: str,
        unlocked_amount: float
    ) -> Optional[TokenLock]:
        """Update lock with unlocked amount."""
        with self._lock:
            if lock_id not in self.locks:
                return None

            lock = self.locks[lock_id]
            lock.unlocked_amount = unlocked_amount
            lock.locked_amount = lock.total_amount - unlocked_amount

            if lock.locked_amount <= 0:
                lock.status = LockStatus.UNLOCKED
            elif unlocked_amount > 0:
                lock.status = LockStatus.UNLOCKING

            with self._get_db() as conn:
                conn.execute("""
                    UPDATE token_locks SET
                    locked_amount = ?, unlocked_amount = ?, status = ?
                    WHERE lock_id = ?
                """, (lock.locked_amount, unlocked_amount, lock.status.value, lock_id))

            return lock

    def get_locks_for_token(self, token_address: str) -> List[TokenLock]:
        """Get all locks for a token."""
        return [l for l in self.locks.values() if l.token_address == token_address]

    def get_upcoming_unlocks(
        self,
        days: int = 30,
        token_address: Optional[str] = None
    ) -> List[UnlockEvent]:
        """Get upcoming unlock events."""
        cutoff = datetime.now() + timedelta(days=days)

        with self._get_db() as conn:
            if token_address:
                rows = conn.execute("""
                    SELECT * FROM unlock_events
                    WHERE unlock_date <= ? AND unlock_date > datetime('now')
                    AND token_address = ?
                    ORDER BY unlock_date ASC
                """, (cutoff.isoformat(), token_address)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM unlock_events
                    WHERE unlock_date <= ? AND unlock_date > datetime('now')
                    ORDER BY unlock_date ASC
                """, (cutoff.isoformat(),)).fetchall()

            return [
                UnlockEvent(
                    event_id=row["event_id"],
                    lock_id=row["lock_id"],
                    token_address=row["token_address"],
                    token_symbol=row["token_symbol"],
                    amount=row["amount"],
                    percent_of_supply=row["percent_of_supply"],
                    unlock_date=datetime.fromisoformat(row["unlock_date"]),
                    lock_type=LockType(row["lock_type"]),
                    impact_assessment=row["impact_assessment"]
                )
                for row in rows
            ]

    def analyze_token_locks(
        self,
        token_address: str,
        total_supply: float
    ) -> LockAnalysis:
        """Analyze all locks for a token."""
        locks = self.get_locks_for_token(token_address)

        if not locks:
            return LockAnalysis(
                token_address=token_address,
                token_symbol="",
                total_supply=total_supply,
                locked_amount=0,
                locked_percent=0,
                lp_locked_percent=0,
                team_locked_percent=0,
                vesting_locked_percent=0,
                unlock_in_7d=0,
                unlock_in_30d=0,
                unlock_in_90d=0,
                risk_score=100,
                analyzed_at=datetime.now()
            )

        symbol = locks[0].token_symbol
        total_locked = sum(l.locked_amount for l in locks if l.status == LockStatus.ACTIVE)

        lp_locked = sum(
            l.locked_amount for l in locks
            if l.lock_type == LockType.LP_LOCK and l.status == LockStatus.ACTIVE
        )
        team_locked = sum(
            l.locked_amount for l in locks
            if l.lock_type == LockType.TEAM_LOCK and l.status == LockStatus.ACTIVE
        )
        vesting_locked = sum(
            l.locked_amount for l in locks
            if l.lock_type == LockType.VESTING and l.status == LockStatus.ACTIVE
        )

        # Calculate upcoming unlocks
        now = datetime.now()
        unlock_7d = sum(
            l.locked_amount for l in locks
            if l.unlock_end <= now + timedelta(days=7) and l.status == LockStatus.ACTIVE
        )
        unlock_30d = sum(
            l.locked_amount for l in locks
            if l.unlock_end <= now + timedelta(days=30) and l.status == LockStatus.ACTIVE
        )
        unlock_90d = sum(
            l.locked_amount for l in locks
            if l.unlock_end <= now + timedelta(days=90) and l.status == LockStatus.ACTIVE
        )

        # Calculate risk score
        risk_score = self._calculate_risk_score(
            total_locked / total_supply if total_supply > 0 else 0,
            lp_locked / total_supply if total_supply > 0 else 0,
            unlock_7d / total_supply if total_supply > 0 else 0,
            locks
        )

        return LockAnalysis(
            token_address=token_address,
            token_symbol=symbol,
            total_supply=total_supply,
            locked_amount=total_locked,
            locked_percent=total_locked / total_supply * 100 if total_supply > 0 else 0,
            lp_locked_percent=lp_locked / total_supply * 100 if total_supply > 0 else 0,
            team_locked_percent=team_locked / total_supply * 100 if total_supply > 0 else 0,
            vesting_locked_percent=vesting_locked / total_supply * 100 if total_supply > 0 else 0,
            unlock_in_7d=unlock_7d,
            unlock_in_30d=unlock_30d,
            unlock_in_90d=unlock_90d,
            risk_score=risk_score,
            analyzed_at=datetime.now()
        )

    def _calculate_risk_score(
        self,
        locked_percent: float,
        lp_locked_percent: float,
        unlock_7d_percent: float,
        locks: List[TokenLock]
    ) -> float:
        """Calculate risk score (0-100, higher = riskier)."""
        score = 50  # Start at medium

        # LP lock bonus (lower risk if LP is locked)
        if lp_locked_percent > 0.9:
            score -= 30
        elif lp_locked_percent > 0.5:
            score -= 15
        elif lp_locked_percent < 0.1:
            score += 20

        # Upcoming unlocks penalty
        if unlock_7d_percent > 0.1:
            score += 25
        elif unlock_7d_percent > 0.05:
            score += 10

        # Lock duration bonus
        now = datetime.now()
        avg_duration = sum(
            (l.unlock_end - now).days for l in locks if l.unlock_end > now
        ) / len(locks) if locks else 0

        if avg_duration > 365:
            score -= 10
        elif avg_duration < 30:
            score += 15

        # Platform trust bonus
        trusted_platforms = [LockPlatform.STREAMFLOW, LockPlatform.UNCX, LockPlatform.TEAM_FINANCE]
        if any(l.platform in trusted_platforms for l in locks):
            score -= 5

        return max(0, min(100, score))

    def create_vesting_schedule(
        self,
        token_address: str,
        token_symbol: str,
        beneficiary: str,
        total_amount: float,
        start_date: datetime,
        end_date: datetime,
        cliff_date: Optional[datetime] = None,
        release_frequency: str = "linear"
    ) -> VestingSchedule:
        """Create a vesting schedule."""
        import uuid

        schedule = VestingSchedule(
            schedule_id=str(uuid.uuid4())[:12],
            token_address=token_address,
            token_symbol=token_symbol,
            beneficiary=beneficiary,
            total_amount=total_amount,
            released_amount=0,
            pending_amount=total_amount,
            start_date=start_date,
            cliff_date=cliff_date,
            end_date=end_date,
            release_frequency=release_frequency,
            next_release_date=cliff_date or start_date,
            next_release_amount=0,
            status="active"
        )

        with self._get_db() as conn:
            conn.execute("""
                INSERT INTO vesting_schedules
                (schedule_id, token_address, token_symbol, beneficiary,
                 total_amount, released_amount, start_date, cliff_date,
                 end_date, release_frequency, status)
                VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?, 'active')
            """, (
                schedule.schedule_id, token_address, token_symbol,
                beneficiary, total_amount, start_date.isoformat(),
                cliff_date.isoformat() if cliff_date else None,
                end_date.isoformat(), release_frequency
            ))

        self.schedules[schedule.schedule_id] = schedule
        return schedule

    def register_unlock_callback(self, callback):
        """Register callback for unlock alerts."""
        self.unlock_callbacks.append(callback)


# Singleton instance
_token_locker: Optional[TokenLocker] = None


def get_token_locker() -> TokenLocker:
    """Get or create the token locker singleton."""
    global _token_locker
    if _token_locker is None:
        _token_locker = TokenLocker()
    return _token_locker
