"""
TWAP Executor - Time-Weighted Average Price order execution.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import json
import sqlite3
from pathlib import Path
from contextlib import contextmanager
import uuid
import random

logger = logging.getLogger(__name__)


class TWAPStatus(Enum):
    """TWAP order status."""
    PENDING = "pending"
    EXECUTING = "executing"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class TWAPSide(Enum):
    """Order side."""
    BUY = "buy"
    SELL = "sell"


class ExecutionStyle(Enum):
    """Execution style."""
    UNIFORM = "uniform"  # Equal sizes at equal intervals
    FRONT_LOADED = "front_loaded"  # More volume at start
    BACK_LOADED = "back_loaded"  # More volume at end
    RANDOM = "random"  # Randomized timing


@dataclass
class TWAPConfig:
    """TWAP execution configuration."""
    symbol: str
    side: TWAPSide
    total_size: float  # Total tokens to buy/sell
    total_value_usd: float  # Total USD value
    duration_minutes: int  # How long to execute
    num_slices: int  # Number of child orders
    execution_style: ExecutionStyle = ExecutionStyle.UNIFORM
    min_slice_size: float = 0.0  # Minimum slice size
    max_slice_size: float = 0.0  # Maximum slice size (0 = no limit)
    randomize_timing: bool = True  # Add random jitter to timing
    randomize_size: bool = True  # Add random variation to sizes
    price_limit: Optional[float] = None  # Don't execute above/below this
    pause_on_volatility: bool = False  # Pause if volatility spikes
    volatility_threshold: float = 5.0  # Volatility threshold %


@dataclass
class TWAPSlice:
    """A single TWAP slice (child order)."""
    slice_num: int
    scheduled_time: str
    target_size: float
    target_value: float
    executed: bool = False
    executed_size: float = 0.0
    executed_value: float = 0.0
    executed_price: float = 0.0
    executed_at: Optional[str] = None
    tx_signature: Optional[str] = None
    slippage_bps: float = 0.0
    status: str = "pending"


@dataclass
class TWAPOrder:
    """A TWAP order."""
    id: str
    config: TWAPConfig
    status: TWAPStatus
    slices: List[TWAPSlice]
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    executed_size: float = 0.0
    executed_value: float = 0.0
    average_price: float = 0.0
    vwap: float = 0.0  # Volume-weighted average price
    total_slippage_bps: float = 0.0
    progress_percent: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class TWAPDB:
    """SQLite storage for TWAP data."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS twap_orders (
                    id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    side TEXT,
                    total_size REAL,
                    total_value_usd REAL,
                    duration_minutes INTEGER,
                    num_slices INTEGER,
                    execution_style TEXT,
                    price_limit REAL,
                    status TEXT,
                    created_at TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    executed_size REAL DEFAULT 0,
                    executed_value REAL DEFAULT 0,
                    average_price REAL DEFAULT 0,
                    vwap REAL DEFAULT 0,
                    total_slippage_bps REAL DEFAULT 0,
                    config_json TEXT,
                    metadata_json TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS twap_slices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT NOT NULL,
                    slice_num INTEGER,
                    scheduled_time TEXT,
                    target_size REAL,
                    target_value REAL,
                    executed INTEGER DEFAULT 0,
                    executed_size REAL DEFAULT 0,
                    executed_value REAL DEFAULT 0,
                    executed_price REAL DEFAULT 0,
                    executed_at TEXT,
                    tx_signature TEXT,
                    slippage_bps REAL DEFAULT 0,
                    status TEXT,
                    FOREIGN KEY (order_id) REFERENCES twap_orders(id)
                )
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_twap_symbol ON twap_orders(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_twap_status ON twap_orders(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_slices_order ON twap_slices(order_id)")

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


class TWAPExecutor:
    """
    TWAP order execution engine.

    Usage:
        executor = TWAPExecutor()

        # Create a TWAP order
        order = await executor.create_order(TWAPConfig(
            symbol="SOL",
            side=TWAPSide.BUY,
            total_size=100,  # 100 SOL
            total_value_usd=10000,  # ~$100/SOL
            duration_minutes=60,  # Execute over 1 hour
            num_slices=12  # 12 slices, 5 min apart
        ))

        # Start execution
        await executor.start_execution(order.id)

        # Monitor progress
        stats = executor.get_order_stats(order.id)
    """

    def __init__(self, db_path: Optional[Path] = None):
        db_path = db_path or Path(__file__).parent.parent / "data" / "twap.db"
        self.db = TWAPDB(db_path)
        self._orders: Dict[str, TWAPOrder] = {}
        self._price_feeds: Dict[str, Callable] = {}
        self._execution_callback: Optional[Callable] = None
        self._volatility_callback: Optional[Callable] = None
        self._executing: Dict[str, bool] = {}  # Track which orders are executing

    async def create_order(self, config: TWAPConfig) -> TWAPOrder:
        """Create a new TWAP order."""
        order_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc)

        # Generate slices
        slices = self._generate_slices(config, now)

        order = TWAPOrder(
            id=order_id,
            config=config,
            status=TWAPStatus.PENDING,
            slices=slices,
            created_at=now.isoformat(),
            started_at=None,
            completed_at=None
        )

        self._save_order(order)
        self._orders[order_id] = order

        logger.info(f"Created TWAP order {order_id}: {config.side.value} "
                   f"{config.total_size} {config.symbol} over {config.duration_minutes}min "
                   f"in {config.num_slices} slices")

        return order

    def _generate_slices(
        self,
        config: TWAPConfig,
        start_time: datetime
    ) -> List[TWAPSlice]:
        """Generate TWAP slices based on configuration."""
        slices = []
        interval = timedelta(minutes=config.duration_minutes / config.num_slices)

        # Calculate slice sizes based on execution style
        if config.execution_style == ExecutionStyle.UNIFORM:
            sizes = [config.total_size / config.num_slices] * config.num_slices

        elif config.execution_style == ExecutionStyle.FRONT_LOADED:
            # More volume at start: decreasing sizes
            weights = [config.num_slices - i for i in range(config.num_slices)]
            total_weight = sum(weights)
            sizes = [(w / total_weight) * config.total_size for w in weights]

        elif config.execution_style == ExecutionStyle.BACK_LOADED:
            # More volume at end: increasing sizes
            weights = [i + 1 for i in range(config.num_slices)]
            total_weight = sum(weights)
            sizes = [(w / total_weight) * config.total_size for w in weights]

        elif config.execution_style == ExecutionStyle.RANDOM:
            # Random distribution that sums to total
            weights = [random.random() for _ in range(config.num_slices)]
            total_weight = sum(weights)
            sizes = [(w / total_weight) * config.total_size for w in weights]

        else:
            sizes = [config.total_size / config.num_slices] * config.num_slices

        # Apply randomization if enabled
        if config.randomize_size:
            # Add ±10% variation
            sizes = [s * random.uniform(0.9, 1.1) for s in sizes]
            # Normalize to ensure total is correct
            total = sum(sizes)
            sizes = [s * config.total_size / total for s in sizes]

        # Apply min/max constraints
        for i, size in enumerate(sizes):
            if config.min_slice_size > 0:
                sizes[i] = max(size, config.min_slice_size)
            if config.max_slice_size > 0:
                sizes[i] = min(size, config.max_slice_size)

        # Generate slices
        price_estimate = config.total_value_usd / config.total_size if config.total_size > 0 else 0

        for i in range(config.num_slices):
            scheduled = start_time + (interval * i)

            # Add timing jitter if enabled
            if config.randomize_timing and i > 0:
                jitter_seconds = random.randint(-30, 30)
                scheduled += timedelta(seconds=jitter_seconds)

            slices.append(TWAPSlice(
                slice_num=i + 1,
                scheduled_time=scheduled.isoformat(),
                target_size=sizes[i],
                target_value=sizes[i] * price_estimate
            ))

        return slices

    def _save_order(self, order: TWAPOrder):
        """Save order to database."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO twap_orders
                (id, symbol, side, total_size, total_value_usd, duration_minutes,
                 num_slices, execution_style, price_limit, status, created_at,
                 started_at, completed_at, executed_size, executed_value,
                 average_price, vwap, total_slippage_bps, config_json, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                order.id, order.config.symbol, order.config.side.value,
                order.config.total_size, order.config.total_value_usd,
                order.config.duration_minutes, order.config.num_slices,
                order.config.execution_style.value, order.config.price_limit,
                order.status.value, order.created_at, order.started_at,
                order.completed_at, order.executed_size, order.executed_value,
                order.average_price, order.vwap, order.total_slippage_bps,
                json.dumps({
                    'randomize_timing': order.config.randomize_timing,
                    'randomize_size': order.config.randomize_size,
                    'pause_on_volatility': order.config.pause_on_volatility,
                    'volatility_threshold': order.config.volatility_threshold
                }),
                json.dumps(order.metadata)
            ))

            # Save slices
            for slice in order.slices:
                cursor.execute("""
                    INSERT OR REPLACE INTO twap_slices
                    (order_id, slice_num, scheduled_time, target_size, target_value,
                     executed, executed_size, executed_value, executed_price,
                     executed_at, tx_signature, slippage_bps, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    order.id, slice.slice_num, slice.scheduled_time,
                    slice.target_size, slice.target_value,
                    1 if slice.executed else 0, slice.executed_size,
                    slice.executed_value, slice.executed_price,
                    slice.executed_at, slice.tx_signature,
                    slice.slippage_bps, slice.status
                ))

            conn.commit()

    def set_price_feed(self, symbol: str, callback: Callable[[], float]):
        """Set price feed for a symbol."""
        self._price_feeds[symbol.upper()] = callback

    def set_execution_callback(self, callback: Callable):
        """Set callback for executing trades."""
        self._execution_callback = callback

    def set_volatility_callback(self, callback: Callable):
        """Set callback for getting volatility."""
        self._volatility_callback = callback

    async def start_execution(self, order_id: str) -> bool:
        """Start executing a TWAP order."""
        order = self._orders.get(order_id)
        if not order:
            logger.error(f"Order {order_id} not found")
            return False

        if order.status not in [TWAPStatus.PENDING, TWAPStatus.PAUSED]:
            logger.error(f"Cannot start order {order_id} with status {order.status.value}")
            return False

        order.status = TWAPStatus.EXECUTING
        order.started_at = order.started_at or datetime.now(timezone.utc).isoformat()
        self._save_order(order)

        self._executing[order_id] = True

        # Start execution loop
        asyncio.create_task(self._execution_loop(order_id))

        logger.info(f"Started TWAP execution for order {order_id}")
        return True

    async def _execution_loop(self, order_id: str):
        """Main execution loop for a TWAP order."""
        order = self._orders.get(order_id)
        if not order:
            return

        while self._executing.get(order_id, False):
            try:
                # Check if order should pause on volatility
                if order.config.pause_on_volatility:
                    if await self._should_pause_volatility(order):
                        logger.warning(f"TWAP {order_id} paused due to high volatility")
                        await asyncio.sleep(60)
                        continue

                # Find next slice to execute
                next_slice = None
                now = datetime.now(timezone.utc)

                for slice in order.slices:
                    if slice.executed:
                        continue

                    scheduled = datetime.fromisoformat(slice.scheduled_time.replace('Z', '+00:00'))
                    if scheduled <= now:
                        next_slice = slice
                        break

                if next_slice:
                    await self._execute_slice(order, next_slice)

                # Check if order is complete
                if all(s.executed for s in order.slices):
                    order.status = TWAPStatus.COMPLETED
                    order.completed_at = datetime.now(timezone.utc).isoformat()
                    self._save_order(order)
                    self._executing[order_id] = False
                    logger.info(f"TWAP order {order_id} completed: "
                               f"executed {order.executed_size} @ avg {order.average_price:.4f}")
                    break

                await asyncio.sleep(5)  # Check every 5 seconds

            except Exception as e:
                logger.error(f"Error in TWAP execution loop: {e}")
                await asyncio.sleep(10)

    async def _should_pause_volatility(self, order: TWAPOrder) -> bool:
        """Check if execution should pause due to volatility."""
        if not self._volatility_callback:
            return False

        try:
            volatility = await self._volatility_callback(order.config.symbol)
            return volatility > order.config.volatility_threshold
        except Exception:
            return False

    async def _execute_slice(self, order: TWAPOrder, slice: TWAPSlice):
        """Execute a single TWAP slice."""
        # Get current price
        price_feed = self._price_feeds.get(order.config.symbol)
        if not price_feed:
            slice.status = "failed"
            slice.executed = True
            logger.error(f"No price feed for {order.config.symbol}")
            return

        try:
            current_price = price_feed()
        except Exception as e:
            slice.status = "failed"
            slice.executed = True
            logger.error(f"Error getting price: {e}")
            return

        # Check price limit
        if order.config.price_limit:
            if order.config.side == TWAPSide.BUY and current_price > order.config.price_limit:
                logger.info(f"Skipping slice: price {current_price} above limit {order.config.price_limit}")
                slice.status = "skipped"
                slice.executed = True
                self._save_order(order)
                return

            if order.config.side == TWAPSide.SELL and current_price < order.config.price_limit:
                logger.info(f"Skipping slice: price {current_price} below limit {order.config.price_limit}")
                slice.status = "skipped"
                slice.executed = True
                self._save_order(order)
                return

        # Execute trade
        executed_size = slice.target_size
        executed_price = current_price
        executed_value = executed_size * executed_price
        tx_signature = None

        if self._execution_callback:
            try:
                result = await self._execution_callback(
                    symbol=order.config.symbol,
                    side=order.config.side.value,
                    size=slice.target_size,
                    order_type="market"
                )

                if result.get('success'):
                    executed_size = result.get('size', slice.target_size)
                    executed_price = result.get('price', current_price)
                    executed_value = result.get('value', executed_size * executed_price)
                    tx_signature = result.get('tx_signature')
                else:
                    slice.status = "failed"
                    slice.executed = True
                    logger.error(f"Slice execution failed: {result.get('error')}")
                    self._save_order(order)
                    return

            except Exception as e:
                slice.status = "failed"
                slice.executed = True
                logger.error(f"Slice execution error: {e}")
                self._save_order(order)
                return

        # Calculate slippage
        expected_price = slice.target_value / slice.target_size if slice.target_size > 0 else current_price
        slippage_bps = abs(executed_price - expected_price) / expected_price * 10000

        # Update slice
        slice.executed = True
        slice.executed_size = executed_size
        slice.executed_value = executed_value
        slice.executed_price = executed_price
        slice.executed_at = datetime.now(timezone.utc).isoformat()
        slice.tx_signature = tx_signature
        slice.slippage_bps = slippage_bps
        slice.status = "completed"

        # Update order totals
        order.executed_size += executed_size
        order.executed_value += executed_value
        order.average_price = order.executed_value / order.executed_size if order.executed_size > 0 else 0
        order.progress_percent = (order.executed_size / order.config.total_size) * 100

        # Calculate VWAP
        total_vwap = sum(s.executed_size * s.executed_price for s in order.slices if s.executed)
        total_volume = sum(s.executed_size for s in order.slices if s.executed)
        order.vwap = total_vwap / total_volume if total_volume > 0 else 0

        # Calculate total slippage
        executed_slices = [s for s in order.slices if s.executed]
        order.total_slippage_bps = sum(s.slippage_bps for s in executed_slices) / len(executed_slices) if executed_slices else 0.0

        self._save_order(order)

        logger.info(f"TWAP slice {slice.slice_num}/{order.config.num_slices}: "
                   f"{executed_size:.6f} @ {executed_price:.4f} "
                   f"(slippage: {slippage_bps:.1f}bps)")

    async def pause_execution(self, order_id: str) -> bool:
        """Pause a TWAP order."""
        order = self._orders.get(order_id)
        if not order or order.status != TWAPStatus.EXECUTING:
            return False

        self._executing[order_id] = False
        order.status = TWAPStatus.PAUSED
        self._save_order(order)

        logger.info(f"Paused TWAP order {order_id}")
        return True

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a TWAP order."""
        order = self._orders.get(order_id)
        if not order:
            return False

        self._executing[order_id] = False
        order.status = TWAPStatus.CANCELLED
        order.completed_at = datetime.now(timezone.utc).isoformat()
        self._save_order(order)

        logger.info(f"Cancelled TWAP order {order_id}")
        return True

    def get_order(self, order_id: str) -> Optional[TWAPOrder]:
        """Get an order by ID."""
        return self._orders.get(order_id)

    def get_order_stats(self, order_id: str) -> Dict[str, Any]:
        """Get statistics for an order."""
        order = self._orders.get(order_id)
        if not order:
            return {}

        executed_slices = [s for s in order.slices if s.executed and s.status == "completed"]
        pending_slices = [s for s in order.slices if not s.executed]
        skipped_slices = [s for s in order.slices if s.status == "skipped"]
        failed_slices = [s for s in order.slices if s.status == "failed"]

        return {
            'order_id': order_id,
            'symbol': order.config.symbol,
            'side': order.config.side.value,
            'status': order.status.value,
            'target_size': order.config.total_size,
            'executed_size': order.executed_size,
            'remaining_size': order.config.total_size - order.executed_size,
            'progress_percent': order.progress_percent,
            'average_price': order.average_price,
            'vwap': order.vwap,
            'total_slippage_bps': order.total_slippage_bps,
            'slices_executed': len(executed_slices),
            'slices_pending': len(pending_slices),
            'slices_skipped': len(skipped_slices),
            'slices_failed': len(failed_slices),
            'slices_total': len(order.slices),
            'duration_minutes': order.config.duration_minutes,
            'elapsed_minutes': self._calculate_elapsed(order),
            'started_at': order.started_at,
            'completed_at': order.completed_at
        }

    def _calculate_elapsed(self, order: TWAPOrder) -> float:
        """Calculate elapsed time in minutes."""
        if not order.started_at:
            return 0

        start = datetime.fromisoformat(order.started_at.replace('Z', '+00:00'))
        end = datetime.now(timezone.utc)
        if order.completed_at:
            end = datetime.fromisoformat(order.completed_at.replace('Z', '+00:00'))

        return (end - start).total_seconds() / 60

    def get_active_orders(self) -> List[TWAPOrder]:
        """Get all active orders."""
        return [o for o in self._orders.values()
                if o.status in [TWAPStatus.EXECUTING, TWAPStatus.PAUSED]]

    def load_orders(self):
        """Load orders from database."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM twap_orders WHERE status IN ('pending', 'executing', 'paused')")

            for row in cursor.fetchall():
                config = TWAPConfig(
                    symbol=row['symbol'],
                    side=TWAPSide(row['side']),
                    total_size=row['total_size'],
                    total_value_usd=row['total_value_usd'],
                    duration_minutes=row['duration_minutes'],
                    num_slices=row['num_slices'],
                    execution_style=ExecutionStyle(row['execution_style']),
                    price_limit=row['price_limit']
                )

                config_data = json.loads(row['config_json']) if row['config_json'] else {}
                config.randomize_timing = config_data.get('randomize_timing', True)
                config.randomize_size = config_data.get('randomize_size', True)
                config.pause_on_volatility = config_data.get('pause_on_volatility', False)
                config.volatility_threshold = config_data.get('volatility_threshold', 5.0)

                # Load slices
                cursor.execute("""
                    SELECT * FROM twap_slices WHERE order_id = ? ORDER BY slice_num
                """, (row['id'],))

                slices = [
                    TWAPSlice(
                        slice_num=s['slice_num'],
                        scheduled_time=s['scheduled_time'],
                        target_size=s['target_size'],
                        target_value=s['target_value'],
                        executed=bool(s['executed']),
                        executed_size=s['executed_size'],
                        executed_value=s['executed_value'],
                        executed_price=s['executed_price'],
                        executed_at=s['executed_at'],
                        tx_signature=s['tx_signature'],
                        slippage_bps=s['slippage_bps'],
                        status=s['status']
                    )
                    for s in cursor.fetchall()
                ]

                order = TWAPOrder(
                    id=row['id'],
                    config=config,
                    status=TWAPStatus(row['status']),
                    slices=slices,
                    created_at=row['created_at'],
                    started_at=row['started_at'],
                    completed_at=row['completed_at'],
                    executed_size=row['executed_size'] or 0,
                    executed_value=row['executed_value'] or 0,
                    average_price=row['average_price'] or 0,
                    vwap=row['vwap'] or 0,
                    total_slippage_bps=row['total_slippage_bps'] or 0,
                    progress_percent=(row['executed_size'] or 0) / row['total_size'] * 100 if row['total_size'] > 0 else 0,
                    metadata=json.loads(row['metadata_json']) if row['metadata_json'] else {}
                )

                self._orders[order.id] = order

        logger.info(f"Loaded {len(self._orders)} TWAP orders")


# Singleton
_executor: Optional[TWAPExecutor] = None


def get_twap_executor() -> TWAPExecutor:
    """Get singleton TWAP executor."""
    global _executor
    if _executor is None:
        _executor = TWAPExecutor()
        _executor.load_orders()
    return _executor
