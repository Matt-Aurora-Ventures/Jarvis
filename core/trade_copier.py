"""
Trade Copier - Copy trades from master wallets/traders to your wallet.
Supports multiple sources, size scaling, and filtering.
"""
import asyncio
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Callable, Set


class CopyMode(Enum):
    """Trade copy modes."""
    MIRROR = "mirror"              # Copy exact trades
    PROPORTIONAL = "proportional"  # Scale by portfolio size
    FIXED = "fixed"                # Fixed size per trade
    PERCENTAGE = "percentage"      # Percentage of your balance


class SignalType(Enum):
    """Types of trade signals."""
    BUY = "buy"
    SELL = "sell"
    LONG = "long"
    SHORT = "short"
    CLOSE = "close"


class SourceType(Enum):
    """Types of trade sources."""
    WALLET = "wallet"              # On-chain wallet
    TELEGRAM = "telegram"          # Telegram channel
    DISCORD = "discord"            # Discord channel
    API = "api"                    # External API
    MANUAL = "manual"              # Manual entry


class CopyStatus(Enum):
    """Copy trade status."""
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TradeSource:
    """A source of trade signals."""
    source_id: str
    name: str
    source_type: SourceType
    address: Optional[str]         # Wallet address if applicable
    enabled: bool
    priority: int                  # Higher = more important
    copy_mode: CopyMode
    size_multiplier: float         # For proportional/fixed modes
    max_position_size: float       # Maximum size to copy
    min_position_size: float       # Minimum size to copy
    allowed_tokens: Set[str]       # Empty = all allowed
    blocked_tokens: Set[str]       # Tokens to never copy
    delay_seconds: int             # Delay before copying
    created_at: datetime
    stats: Dict = field(default_factory=dict)


@dataclass
class TradeSignal:
    """A trade signal to copy."""
    signal_id: str
    source_id: str
    signal_type: SignalType
    token: str
    amount: float
    price: Optional[float]
    timestamp: datetime
    tx_hash: Optional[str]
    metadata: Dict = field(default_factory=dict)


@dataclass
class CopiedTrade:
    """A copied trade."""
    copy_id: str
    signal_id: str
    source_id: str
    signal_type: SignalType
    token: str
    original_amount: float
    copied_amount: float
    original_price: float
    executed_price: Optional[float]
    status: CopyStatus
    created_at: datetime
    executed_at: Optional[datetime]
    tx_hash: Optional[str]
    pnl: Optional[float]
    error_message: Optional[str]


@dataclass
class CopyConfig:
    """Global copy trading configuration."""
    enabled: bool = True
    max_concurrent_copies: int = 5
    max_daily_trades: int = 50
    max_daily_volume: float = 10000
    global_size_limit: float = 1000
    require_confirmation: bool = False
    copy_stop_losses: bool = True
    copy_take_profits: bool = True
    auto_close_on_source_close: bool = True


class TradeCopier:
    """
    Trade copier that mirrors trades from master traders/wallets.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or str(
            Path(__file__).parent.parent / "data" / "trade_copier.db"
        )
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

        self.sources: Dict[str, TradeSource] = {}
        self.pending_signals: Dict[str, TradeSignal] = {}
        self.config = CopyConfig()

        self._lock = threading.Lock()
        self._running = False

        # Callbacks
        self.signal_callbacks: List[Callable] = []
        self.copy_callbacks: List[Callable] = []
        self.error_callbacks: List[Callable] = []

        # Statistics
        self.daily_trades = 0
        self.daily_volume = 0.0
        self.last_reset = datetime.now().date()

        self._load_sources()

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
                CREATE TABLE IF NOT EXISTS sources (
                    source_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    address TEXT,
                    enabled INTEGER DEFAULT 1,
                    priority INTEGER DEFAULT 0,
                    copy_mode TEXT NOT NULL,
                    size_multiplier REAL DEFAULT 1,
                    max_position_size REAL DEFAULT 1000,
                    min_position_size REAL DEFAULT 10,
                    allowed_tokens TEXT,
                    blocked_tokens TEXT,
                    delay_seconds INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    stats TEXT
                );

                CREATE TABLE IF NOT EXISTS signals (
                    signal_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    token TEXT NOT NULL,
                    amount REAL NOT NULL,
                    price REAL,
                    timestamp TEXT NOT NULL,
                    tx_hash TEXT,
                    metadata TEXT,
                    processed INTEGER DEFAULT 0,
                    FOREIGN KEY (source_id) REFERENCES sources(source_id)
                );

                CREATE TABLE IF NOT EXISTS copied_trades (
                    copy_id TEXT PRIMARY KEY,
                    signal_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    token TEXT NOT NULL,
                    original_amount REAL NOT NULL,
                    copied_amount REAL NOT NULL,
                    original_price REAL NOT NULL,
                    executed_price REAL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    executed_at TEXT,
                    tx_hash TEXT,
                    pnl REAL,
                    error_message TEXT,
                    FOREIGN KEY (signal_id) REFERENCES signals(signal_id),
                    FOREIGN KEY (source_id) REFERENCES sources(source_id)
                );

                CREATE INDEX IF NOT EXISTS idx_signals_source ON signals(source_id);
                CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON signals(timestamp);
                CREATE INDEX IF NOT EXISTS idx_copied_status ON copied_trades(status);
            """)

    def _load_sources(self):
        """Load sources from database."""
        import json

        with self._get_db() as conn:
            rows = conn.execute("SELECT * FROM sources").fetchall()

            for row in rows:
                source = TradeSource(
                    source_id=row["source_id"],
                    name=row["name"],
                    source_type=SourceType(row["source_type"]),
                    address=row["address"],
                    enabled=bool(row["enabled"]),
                    priority=row["priority"],
                    copy_mode=CopyMode(row["copy_mode"]),
                    size_multiplier=row["size_multiplier"],
                    max_position_size=row["max_position_size"],
                    min_position_size=row["min_position_size"],
                    allowed_tokens=set(json.loads(row["allowed_tokens"] or "[]")),
                    blocked_tokens=set(json.loads(row["blocked_tokens"] or "[]")),
                    delay_seconds=row["delay_seconds"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    stats=json.loads(row["stats"] or "{}")
                )
                self.sources[source.source_id] = source

    def add_source(
        self,
        name: str,
        source_type: SourceType,
        address: Optional[str] = None,
        copy_mode: CopyMode = CopyMode.PROPORTIONAL,
        size_multiplier: float = 1.0,
        max_position_size: float = 1000,
        min_position_size: float = 10,
        allowed_tokens: Optional[List[str]] = None,
        blocked_tokens: Optional[List[str]] = None,
        delay_seconds: int = 0,
        priority: int = 0
    ) -> TradeSource:
        """Add a new trade source."""
        import json
        import uuid

        source = TradeSource(
            source_id=str(uuid.uuid4())[:8],
            name=name,
            source_type=source_type,
            address=address,
            enabled=True,
            priority=priority,
            copy_mode=copy_mode,
            size_multiplier=size_multiplier,
            max_position_size=max_position_size,
            min_position_size=min_position_size,
            allowed_tokens=set(allowed_tokens or []),
            blocked_tokens=set(blocked_tokens or []),
            delay_seconds=delay_seconds,
            created_at=datetime.now()
        )

        self.sources[source.source_id] = source

        with self._get_db() as conn:
            conn.execute("""
                INSERT INTO sources
                (source_id, name, source_type, address, enabled, priority,
                 copy_mode, size_multiplier, max_position_size, min_position_size,
                 allowed_tokens, blocked_tokens, delay_seconds, created_at, stats)
                VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, '{}')
            """, (
                source.source_id, name, source_type.value, address, priority,
                copy_mode.value, size_multiplier, max_position_size,
                min_position_size, json.dumps(list(source.allowed_tokens)),
                json.dumps(list(source.blocked_tokens)), delay_seconds,
                source.created_at.isoformat()
            ))

        return source

    def remove_source(self, source_id: str) -> bool:
        """Remove a trade source."""
        if source_id not in self.sources:
            return False

        del self.sources[source_id]

        with self._get_db() as conn:
            conn.execute("DELETE FROM sources WHERE source_id = ?", (source_id,))

        return True

    def enable_source(self, source_id: str, enabled: bool = True):
        """Enable or disable a source."""
        if source_id in self.sources:
            self.sources[source_id].enabled = enabled

            with self._get_db() as conn:
                conn.execute(
                    "UPDATE sources SET enabled = ? WHERE source_id = ?",
                    (1 if enabled else 0, source_id)
                )

    def receive_signal(self, signal: TradeSignal) -> Optional[str]:
        """Receive a trade signal from a source."""
        import json

        source = self.sources.get(signal.source_id)
        if not source or not source.enabled:
            return None

        # Check if token is allowed
        if source.allowed_tokens and signal.token not in source.allowed_tokens:
            return None
        if signal.token in source.blocked_tokens:
            return None

        # Store signal
        with self._get_db() as conn:
            conn.execute("""
                INSERT INTO signals
                (signal_id, source_id, signal_type, token, amount, price,
                 timestamp, tx_hash, metadata, processed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, (
                signal.signal_id, signal.source_id, signal.signal_type.value,
                signal.token, signal.amount, signal.price,
                signal.timestamp.isoformat(), signal.tx_hash,
                json.dumps(signal.metadata)
            ))

        # Queue for processing
        self.pending_signals[signal.signal_id] = signal

        # Notify callbacks
        for callback in self.signal_callbacks:
            try:
                callback(signal)
            except Exception:
                pass

        return signal.signal_id

    async def process_signal(self, signal: TradeSignal) -> Optional[CopiedTrade]:
        """Process and execute a trade signal."""
        import uuid

        source = self.sources.get(signal.source_id)
        if not source:
            return None

        # Reset daily limits if needed
        self._check_daily_reset()

        # Check limits
        if self.daily_trades >= self.config.max_daily_trades:
            return self._skip_trade(signal, "Daily trade limit reached")

        # Calculate copy size
        copy_amount = self._calculate_copy_size(signal, source)
        if copy_amount < source.min_position_size:
            return self._skip_trade(signal, "Below minimum size")
        if copy_amount > source.max_position_size:
            copy_amount = source.max_position_size

        if copy_amount * (signal.price or 1) > self.config.global_size_limit:
            copy_amount = self.config.global_size_limit / (signal.price or 1)

        # Apply delay if configured
        if source.delay_seconds > 0:
            await asyncio.sleep(source.delay_seconds)

        # Create copied trade record
        now = datetime.now()
        copied = CopiedTrade(
            copy_id=str(uuid.uuid4())[:12],
            signal_id=signal.signal_id,
            source_id=signal.source_id,
            signal_type=signal.signal_type,
            token=signal.token,
            original_amount=signal.amount,
            copied_amount=copy_amount,
            original_price=signal.price or 0,
            executed_price=None,
            status=CopyStatus.EXECUTING,
            created_at=now,
            executed_at=None,
            tx_hash=None,
            pnl=None,
            error_message=None
        )

        self._save_copied_trade(copied)

        # Execute the trade (placeholder - would connect to actual trading)
        try:
            # Simulate trade execution
            copied.executed_price = signal.price  # Would get actual fill price
            copied.executed_at = datetime.now()
            copied.status = CopyStatus.COMPLETED
            copied.tx_hash = f"sim_{copied.copy_id}"

            self.daily_trades += 1
            self.daily_volume += copy_amount * (signal.price or 1)

            # Update source stats
            source.stats["total_copies"] = source.stats.get("total_copies", 0) + 1
            source.stats["total_volume"] = source.stats.get("total_volume", 0) + copy_amount

        except Exception as e:
            copied.status = CopyStatus.FAILED
            copied.error_message = str(e)

            for callback in self.error_callbacks:
                try:
                    callback(copied, e)
                except Exception:
                    pass

        self._save_copied_trade(copied)

        # Mark signal as processed
        with self._get_db() as conn:
            conn.execute(
                "UPDATE signals SET processed = 1 WHERE signal_id = ?",
                (signal.signal_id,)
            )

        # Remove from pending
        self.pending_signals.pop(signal.signal_id, None)

        # Notify callbacks
        for callback in self.copy_callbacks:
            try:
                callback(copied)
            except Exception:
                pass

        return copied

    def _calculate_copy_size(self, signal: TradeSignal, source: TradeSource) -> float:
        """Calculate the size to copy based on mode."""
        if source.copy_mode == CopyMode.MIRROR:
            return signal.amount

        elif source.copy_mode == CopyMode.PROPORTIONAL:
            return signal.amount * source.size_multiplier

        elif source.copy_mode == CopyMode.FIXED:
            return source.size_multiplier

        elif source.copy_mode == CopyMode.PERCENTAGE:
            # Would need access to balance
            return signal.amount * source.size_multiplier

        return signal.amount

    def _skip_trade(self, signal: TradeSignal, reason: str) -> CopiedTrade:
        """Create a skipped trade record."""
        import uuid

        copied = CopiedTrade(
            copy_id=str(uuid.uuid4())[:12],
            signal_id=signal.signal_id,
            source_id=signal.source_id,
            signal_type=signal.signal_type,
            token=signal.token,
            original_amount=signal.amount,
            copied_amount=0,
            original_price=signal.price or 0,
            executed_price=None,
            status=CopyStatus.SKIPPED,
            created_at=datetime.now(),
            executed_at=None,
            tx_hash=None,
            pnl=None,
            error_message=reason
        )

        self._save_copied_trade(copied)
        return copied

    def _save_copied_trade(self, copied: CopiedTrade):
        """Save copied trade to database."""
        with self._get_db() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO copied_trades
                (copy_id, signal_id, source_id, signal_type, token,
                 original_amount, copied_amount, original_price, executed_price,
                 status, created_at, executed_at, tx_hash, pnl, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                copied.copy_id, copied.signal_id, copied.source_id,
                copied.signal_type.value, copied.token, copied.original_amount,
                copied.copied_amount, copied.original_price, copied.executed_price,
                copied.status.value, copied.created_at.isoformat(),
                copied.executed_at.isoformat() if copied.executed_at else None,
                copied.tx_hash, copied.pnl, copied.error_message
            ))

    def _check_daily_reset(self):
        """Reset daily counters if needed."""
        today = datetime.now().date()
        if today > self.last_reset:
            self.daily_trades = 0
            self.daily_volume = 0.0
            self.last_reset = today

    async def start_monitoring(self):
        """Start monitoring for signals."""
        self._running = True

        while self._running:
            # Process pending signals
            for signal_id, signal in list(self.pending_signals.items()):
                try:
                    await self.process_signal(signal)
                except Exception:
                    pass

            await asyncio.sleep(1)

    def stop_monitoring(self):
        """Stop monitoring."""
        self._running = False

    def get_source_performance(self, source_id: str) -> Dict:
        """Get performance statistics for a source."""
        with self._get_db() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM copied_trades WHERE source_id = ?",
                (source_id,)
            ).fetchone()[0]

            completed = conn.execute(
                "SELECT COUNT(*) FROM copied_trades WHERE source_id = ? AND status = 'completed'",
                (source_id,)
            ).fetchone()[0]

            total_pnl = conn.execute(
                "SELECT COALESCE(SUM(pnl), 0) FROM copied_trades WHERE source_id = ? AND pnl IS NOT NULL",
                (source_id,)
            ).fetchone()[0]

            total_volume = conn.execute(
                "SELECT COALESCE(SUM(copied_amount * original_price), 0) FROM copied_trades WHERE source_id = ? AND status = 'completed'",
                (source_id,)
            ).fetchone()[0]

        return {
            "source_id": source_id,
            "total_signals": total,
            "completed_copies": completed,
            "success_rate": completed / total if total > 0 else 0,
            "total_pnl": total_pnl,
            "total_volume": total_volume
        }

    def get_recent_copies(self, limit: int = 50) -> List[CopiedTrade]:
        """Get recent copied trades."""
        with self._get_db() as conn:
            rows = conn.execute("""
                SELECT * FROM copied_trades
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,)).fetchall()

            return [
                CopiedTrade(
                    copy_id=row["copy_id"],
                    signal_id=row["signal_id"],
                    source_id=row["source_id"],
                    signal_type=SignalType(row["signal_type"]),
                    token=row["token"],
                    original_amount=row["original_amount"],
                    copied_amount=row["copied_amount"],
                    original_price=row["original_price"],
                    executed_price=row["executed_price"],
                    status=CopyStatus(row["status"]),
                    created_at=datetime.fromisoformat(row["created_at"]),
                    executed_at=datetime.fromisoformat(row["executed_at"]) if row["executed_at"] else None,
                    tx_hash=row["tx_hash"],
                    pnl=row["pnl"],
                    error_message=row["error_message"]
                )
                for row in rows
            ]

    def register_signal_callback(self, callback: Callable[[TradeSignal], None]):
        """Register callback for new signals."""
        self.signal_callbacks.append(callback)

    def register_copy_callback(self, callback: Callable[[CopiedTrade], None]):
        """Register callback for copied trades."""
        self.copy_callbacks.append(callback)

    def register_error_callback(self, callback: Callable[[CopiedTrade, Exception], None]):
        """Register callback for errors."""
        self.error_callbacks.append(callback)


# Singleton instance
_trade_copier: Optional[TradeCopier] = None


def get_trade_copier() -> TradeCopier:
    """Get or create the trade copier singleton."""
    global _trade_copier
    if _trade_copier is None:
        _trade_copier = TradeCopier()
    return _trade_copier
