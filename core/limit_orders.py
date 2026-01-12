"""
Limit Order System - Manage limit orders on DEXs.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
import json
import sqlite3
from pathlib import Path
from contextlib import contextmanager
import uuid
import threading

logger = logging.getLogger(__name__)


class OrderType(Enum):
    """Order types."""
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    TRAILING_STOP = "trailing_stop"
    OCO = "oco"  # One-cancels-other


class OrderStatus(Enum):
    """Order status."""
    PENDING = "pending"
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    FAILED = "failed"


class OrderSide(Enum):
    """Order side."""
    BUY = "buy"
    SELL = "sell"


class TimeInForce(Enum):
    """Time in force options."""
    GTC = "gtc"  # Good till cancelled
    IOC = "ioc"  # Immediate or cancel
    FOK = "fok"  # Fill or kill
    GTD = "gtd"  # Good till date


@dataclass
class LimitOrder:
    """A limit order."""
    id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    price: float
    size: float
    size_usd: float
    status: OrderStatus
    time_in_force: TimeInForce
    created_at: str
    updated_at: str
    expires_at: Optional[str] = None
    filled_size: float = 0.0
    filled_price: float = 0.0
    filled_at: Optional[str] = None
    stop_price: Optional[float] = None
    trailing_percent: Optional[float] = None
    linked_order_id: Optional[str] = None  # For OCO orders
    wallet_address: str = ""
    tx_signature: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrderFill:
    """An order fill event."""
    order_id: str
    fill_price: float
    fill_size: float
    fill_value: float
    fee: float
    timestamp: str
    tx_signature: str


@dataclass
class OrderBookState:
    """Current order book state for order matching."""
    best_bid: float
    best_ask: float
    mid_price: float
    timestamp: str


class LimitOrderDB:
    """SQLite storage for limit orders."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS limit_orders (
                    id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    order_type TEXT NOT NULL,
                    price REAL NOT NULL,
                    size REAL NOT NULL,
                    size_usd REAL,
                    status TEXT NOT NULL,
                    time_in_force TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    expires_at TEXT,
                    filled_size REAL DEFAULT 0,
                    filled_price REAL DEFAULT 0,
                    filled_at TEXT,
                    stop_price REAL,
                    trailing_percent REAL,
                    linked_order_id TEXT,
                    wallet_address TEXT,
                    tx_signature TEXT,
                    error_message TEXT,
                    metadata_json TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS order_fills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT NOT NULL,
                    fill_price REAL,
                    fill_size REAL,
                    fill_value REAL,
                    fee REAL,
                    timestamp TEXT,
                    tx_signature TEXT,
                    FOREIGN KEY (order_id) REFERENCES limit_orders(id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS order_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT NOT NULL,
                    old_status TEXT,
                    new_status TEXT,
                    timestamp TEXT,
                    details TEXT
                )
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_symbol ON limit_orders(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON limit_orders(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_wallet ON limit_orders(wallet_address)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_fills_order ON order_fills(order_id)")

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


class LimitOrderManager:
    """
    Manage limit orders across DEXs.

    Usage:
        manager = LimitOrderManager()

        # Create a limit buy order
        order = await manager.create_order(
            symbol="SOL",
            side=OrderSide.BUY,
            price=100.0,
            size=1.0,
            order_type=OrderType.LIMIT
        )

        # Create stop loss
        stop = await manager.create_order(
            symbol="SOL",
            side=OrderSide.SELL,
            price=95.0,
            size=1.0,
            order_type=OrderType.STOP_LOSS,
            stop_price=95.0
        )

        # Monitor and execute orders
        await manager.start_monitoring()
    """

    def __init__(self, db_path: Optional[Path] = None):
        db_path = db_path or Path(__file__).parent.parent / "data" / "limit_orders.db"
        self.db = LimitOrderDB(db_path)
        self._active_orders: Dict[str, LimitOrder] = {}
        self._price_feeds: Dict[str, Callable] = {}
        self._execution_callback: Optional[Callable] = None
        self._monitoring = False
        self._lock = threading.Lock()
        self._load_active_orders()

    def _load_active_orders(self):
        """Load active orders from database."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM limit_orders
                WHERE status IN ('pending', 'open', 'partially_filled')
            """)

            for row in cursor.fetchall():
                order = self._row_to_order(row)
                self._active_orders[order.id] = order

        logger.info(f"Loaded {len(self._active_orders)} active orders")

    def _row_to_order(self, row: sqlite3.Row) -> LimitOrder:
        """Convert database row to LimitOrder."""
        return LimitOrder(
            id=row['id'],
            symbol=row['symbol'],
            side=OrderSide(row['side']),
            order_type=OrderType(row['order_type']),
            price=row['price'],
            size=row['size'],
            size_usd=row['size_usd'] or 0,
            status=OrderStatus(row['status']),
            time_in_force=TimeInForce(row['time_in_force']) if row['time_in_force'] else TimeInForce.GTC,
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            expires_at=row['expires_at'],
            filled_size=row['filled_size'] or 0,
            filled_price=row['filled_price'] or 0,
            filled_at=row['filled_at'],
            stop_price=row['stop_price'],
            trailing_percent=row['trailing_percent'],
            linked_order_id=row['linked_order_id'],
            wallet_address=row['wallet_address'] or "",
            tx_signature=row['tx_signature'],
            error_message=row['error_message'],
            metadata=json.loads(row['metadata_json']) if row['metadata_json'] else {}
        )

    async def create_order(
        self,
        symbol: str,
        side: OrderSide,
        price: float,
        size: float,
        order_type: OrderType = OrderType.LIMIT,
        time_in_force: TimeInForce = TimeInForce.GTC,
        expires_at: Optional[datetime] = None,
        stop_price: Optional[float] = None,
        trailing_percent: Optional[float] = None,
        wallet_address: str = "",
        metadata: Dict[str, Any] = None
    ) -> LimitOrder:
        """Create a new limit order."""
        order_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc).isoformat()

        # Calculate USD value
        size_usd = size * price

        order = LimitOrder(
            id=order_id,
            symbol=symbol.upper(),
            side=side,
            order_type=order_type,
            price=price,
            size=size,
            size_usd=size_usd,
            status=OrderStatus.PENDING,
            time_in_force=time_in_force,
            created_at=now,
            updated_at=now,
            expires_at=expires_at.isoformat() if expires_at else None,
            stop_price=stop_price,
            trailing_percent=trailing_percent,
            wallet_address=wallet_address,
            metadata=metadata or {}
        )

        # Validate order
        self._validate_order(order)

        # Save to database
        self._save_order(order)

        # Add to active orders
        with self._lock:
            self._active_orders[order.id] = order

        # Update status to open
        await self._update_order_status(order, OrderStatus.OPEN)

        logger.info(f"Created {order_type.value} order {order_id}: "
                   f"{side.value} {size} {symbol} @ {price}")

        return order

    def _validate_order(self, order: LimitOrder):
        """Validate order parameters."""
        if order.price <= 0:
            raise ValueError("Price must be positive")
        if order.size <= 0:
            raise ValueError("Size must be positive")
        if order.order_type == OrderType.STOP_LOSS and order.side == OrderSide.BUY:
            if order.stop_price and order.stop_price < order.price:
                raise ValueError("Stop price for buy stop loss must be >= limit price")
        if order.order_type == OrderType.TRAILING_STOP and not order.trailing_percent:
            raise ValueError("Trailing stop requires trailing_percent")

    def _save_order(self, order: LimitOrder):
        """Save order to database."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO limit_orders
                (id, symbol, side, order_type, price, size, size_usd, status,
                 time_in_force, created_at, updated_at, expires_at, filled_size,
                 filled_price, filled_at, stop_price, trailing_percent,
                 linked_order_id, wallet_address, tx_signature, error_message,
                 metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                order.id, order.symbol, order.side.value, order.order_type.value,
                order.price, order.size, order.size_usd, order.status.value,
                order.time_in_force.value, order.created_at, order.updated_at,
                order.expires_at, order.filled_size, order.filled_price,
                order.filled_at, order.stop_price, order.trailing_percent,
                order.linked_order_id, order.wallet_address, order.tx_signature,
                order.error_message, json.dumps(order.metadata)
            ))
            conn.commit()

    async def _update_order_status(
        self,
        order: LimitOrder,
        new_status: OrderStatus,
        details: str = ""
    ):
        """Update order status."""
        old_status = order.status
        order.status = new_status
        order.updated_at = datetime.now(timezone.utc).isoformat()

        self._save_order(order)
        self._save_status_history(order.id, old_status, new_status, details)

        logger.info(f"Order {order.id} status: {old_status.value} -> {new_status.value}")

    def _save_status_history(
        self,
        order_id: str,
        old_status: OrderStatus,
        new_status: OrderStatus,
        details: str
    ):
        """Save order status change history."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO order_history (order_id, old_status, new_status, timestamp, details)
                VALUES (?, ?, ?, ?, ?)
            """, (
                order_id, old_status.value, new_status.value,
                datetime.now(timezone.utc).isoformat(), details
            ))
            conn.commit()

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        with self._lock:
            order = self._active_orders.get(order_id)

        if not order:
            logger.warning(f"Order {order_id} not found in active orders")
            return False

        if order.status not in [OrderStatus.PENDING, OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]:
            logger.warning(f"Cannot cancel order {order_id} with status {order.status.value}")
            return False

        await self._update_order_status(order, OrderStatus.CANCELLED)

        with self._lock:
            del self._active_orders[order_id]

        # Cancel linked OCO order if exists
        if order.linked_order_id:
            await self.cancel_order(order.linked_order_id)

        logger.info(f"Cancelled order {order_id}")
        return True

    async def create_oco_order(
        self,
        symbol: str,
        size: float,
        take_profit_price: float,
        stop_loss_price: float,
        wallet_address: str = ""
    ) -> tuple:
        """Create OCO (one-cancels-other) order pair."""
        # Create take profit order
        tp_order = await self.create_order(
            symbol=symbol,
            side=OrderSide.SELL,
            price=take_profit_price,
            size=size,
            order_type=OrderType.TAKE_PROFIT,
            wallet_address=wallet_address
        )

        # Create stop loss order
        sl_order = await self.create_order(
            symbol=symbol,
            side=OrderSide.SELL,
            price=stop_loss_price,
            size=size,
            order_type=OrderType.STOP_LOSS,
            stop_price=stop_loss_price,
            wallet_address=wallet_address
        )

        # Link orders
        tp_order.linked_order_id = sl_order.id
        sl_order.linked_order_id = tp_order.id
        self._save_order(tp_order)
        self._save_order(sl_order)

        logger.info(f"Created OCO pair: TP={tp_order.id}, SL={sl_order.id}")

        return (tp_order, sl_order)

    def set_price_feed(self, symbol: str, price_callback: Callable[[], float]):
        """Set price feed callback for a symbol."""
        self._price_feeds[symbol.upper()] = price_callback

    def set_execution_callback(self, callback: Callable[[LimitOrder, float, float], Any]):
        """Set callback for order execution."""
        self._execution_callback = callback

    async def check_and_execute_orders(self, book_state: OrderBookState):
        """Check orders against current prices and execute if triggered."""
        with self._lock:
            orders_to_check = list(self._active_orders.values())

        for order in orders_to_check:
            if order.status not in [OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]:
                continue

            # Check expiration
            if order.expires_at:
                if datetime.now(timezone.utc) > datetime.fromisoformat(order.expires_at.replace('Z', '+00:00')):
                    await self._update_order_status(order, OrderStatus.EXPIRED)
                    with self._lock:
                        del self._active_orders[order.id]
                    continue

            triggered = False
            execution_price = 0

            if order.order_type == OrderType.LIMIT:
                triggered, execution_price = self._check_limit_order(order, book_state)
            elif order.order_type == OrderType.STOP_LOSS:
                triggered, execution_price = self._check_stop_loss(order, book_state)
            elif order.order_type == OrderType.TAKE_PROFIT:
                triggered, execution_price = self._check_take_profit(order, book_state)
            elif order.order_type == OrderType.TRAILING_STOP:
                triggered, execution_price = self._check_trailing_stop(order, book_state)

            if triggered:
                await self._execute_order(order, execution_price)

    def _check_limit_order(
        self,
        order: LimitOrder,
        state: OrderBookState
    ) -> tuple:
        """Check if limit order should execute."""
        if order.side == OrderSide.BUY:
            # Buy limit triggers when ask <= limit price
            if state.best_ask <= order.price:
                return True, state.best_ask
        else:
            # Sell limit triggers when bid >= limit price
            if state.best_bid >= order.price:
                return True, state.best_bid

        return False, 0

    def _check_stop_loss(
        self,
        order: LimitOrder,
        state: OrderBookState
    ) -> tuple:
        """Check if stop loss should execute."""
        stop = order.stop_price or order.price

        if order.side == OrderSide.SELL:
            # Sell stop loss triggers when price falls to stop
            if state.best_bid <= stop:
                return True, state.best_bid
        else:
            # Buy stop loss triggers when price rises to stop
            if state.best_ask >= stop:
                return True, state.best_ask

        return False, 0

    def _check_take_profit(
        self,
        order: LimitOrder,
        state: OrderBookState
    ) -> tuple:
        """Check if take profit should execute."""
        if order.side == OrderSide.SELL:
            # Sell TP triggers when price rises to target
            if state.best_bid >= order.price:
                return True, state.best_bid
        else:
            # Buy TP triggers when price falls to target
            if state.best_ask <= order.price:
                return True, state.best_ask

        return False, 0

    def _check_trailing_stop(
        self,
        order: LimitOrder,
        state: OrderBookState
    ) -> tuple:
        """Check trailing stop order."""
        if not order.trailing_percent:
            return False, 0

        # Get highest price since order created (stored in metadata)
        high_price = order.metadata.get('high_price', order.price)

        if order.side == OrderSide.SELL:
            # Update high water mark
            if state.best_bid > high_price:
                order.metadata['high_price'] = state.best_bid
                self._save_order(order)
                high_price = state.best_bid

            # Calculate trailing stop price
            trail_price = high_price * (1 - order.trailing_percent / 100)

            if state.best_bid <= trail_price:
                return True, state.best_bid

        return False, 0

    async def _execute_order(self, order: LimitOrder, execution_price: float):
        """Execute an order."""
        logger.info(f"Executing order {order.id} at {execution_price}")

        try:
            # Call execution callback if set
            if self._execution_callback:
                result = await self._execution_callback(order, execution_price, order.size - order.filled_size)

                if result and result.get('success'):
                    order.filled_size = order.size
                    order.filled_price = execution_price
                    order.filled_at = datetime.now(timezone.utc).isoformat()
                    order.tx_signature = result.get('tx_signature')

                    await self._update_order_status(order, OrderStatus.FILLED)

                    # Record fill
                    self._record_fill(order, execution_price, order.size, result.get('fee', 0))

                    # Cancel linked OCO order
                    if order.linked_order_id:
                        await self.cancel_order(order.linked_order_id)

                    with self._lock:
                        del self._active_orders[order.id]
                else:
                    order.error_message = result.get('error', 'Execution failed')
                    await self._update_order_status(order, OrderStatus.FAILED, order.error_message)
            else:
                # Simulated execution
                order.filled_size = order.size
                order.filled_price = execution_price
                order.filled_at = datetime.now(timezone.utc).isoformat()

                await self._update_order_status(order, OrderStatus.FILLED)

                self._record_fill(order, execution_price, order.size, 0)

                if order.linked_order_id:
                    await self.cancel_order(order.linked_order_id)

                with self._lock:
                    del self._active_orders[order.id]

        except Exception as e:
            logger.error(f"Error executing order {order.id}: {e}")
            order.error_message = str(e)
            await self._update_order_status(order, OrderStatus.FAILED, str(e))

    def _record_fill(
        self,
        order: LimitOrder,
        fill_price: float,
        fill_size: float,
        fee: float
    ):
        """Record order fill."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO order_fills
                (order_id, fill_price, fill_size, fill_value, fee, timestamp, tx_signature)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                order.id, fill_price, fill_size, fill_price * fill_size,
                fee, datetime.now(timezone.utc).isoformat(), order.tx_signature
            ))
            conn.commit()

    async def start_monitoring(self, check_interval: float = 1.0):
        """Start monitoring orders."""
        self._monitoring = True
        logger.info("Started order monitoring")

        while self._monitoring:
            try:
                # Get current prices from feeds
                for symbol, price_callback in self._price_feeds.items():
                    try:
                        price = price_callback()
                        state = OrderBookState(
                            best_bid=price * 0.999,  # Simulated spread
                            best_ask=price * 1.001,
                            mid_price=price,
                            timestamp=datetime.now(timezone.utc).isoformat()
                        )
                        await self.check_and_execute_orders(state)
                    except Exception as e:
                        logger.error(f"Error getting price for {symbol}: {e}")

                await asyncio.sleep(check_interval)

            except Exception as e:
                logger.error(f"Error in order monitoring: {e}")
                await asyncio.sleep(5)

    def stop_monitoring(self):
        """Stop monitoring orders."""
        self._monitoring = False
        logger.info("Stopped order monitoring")

    def get_order(self, order_id: str) -> Optional[LimitOrder]:
        """Get order by ID."""
        with self._lock:
            if order_id in self._active_orders:
                return self._active_orders[order_id]

        # Check database
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM limit_orders WHERE id = ?", (order_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_order(row)

        return None

    def get_open_orders(self, symbol: Optional[str] = None) -> List[LimitOrder]:
        """Get all open orders."""
        with self._lock:
            orders = list(self._active_orders.values())

        if symbol:
            orders = [o for o in orders if o.symbol == symbol.upper()]

        return orders

    def get_order_history(
        self,
        symbol: Optional[str] = None,
        status: Optional[OrderStatus] = None,
        limit: int = 100
    ) -> List[LimitOrder]:
        """Get order history."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM limit_orders WHERE 1=1"
            params = []

            if symbol:
                query += " AND symbol = ?"
                params.append(symbol.upper())

            if status:
                query += " AND status = ?"
                params.append(status.value)

            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)

            return [self._row_to_order(row) for row in cursor.fetchall()]

    def get_fills(self, order_id: str) -> List[OrderFill]:
        """Get fills for an order."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM order_fills WHERE order_id = ? ORDER BY timestamp
            """, (order_id,))

            return [
                OrderFill(
                    order_id=row['order_id'],
                    fill_price=row['fill_price'],
                    fill_size=row['fill_size'],
                    fill_value=row['fill_value'],
                    fee=row['fee'],
                    timestamp=row['timestamp'],
                    tx_signature=row['tx_signature'] or ""
                )
                for row in cursor.fetchall()
            ]

    def get_statistics(self) -> Dict[str, Any]:
        """Get order statistics."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            # Total orders
            cursor.execute("SELECT COUNT(*) FROM limit_orders")
            total_orders = cursor.fetchone()[0]

            # By status
            cursor.execute("""
                SELECT status, COUNT(*) as count FROM limit_orders GROUP BY status
            """)
            by_status = {row['status']: row['count'] for row in cursor.fetchall()}

            # Total volume
            cursor.execute("""
                SELECT SUM(fill_value) FROM order_fills
            """)
            total_volume = cursor.fetchone()[0] or 0

            # Fill rate
            filled = by_status.get('filled', 0)
            fill_rate = filled / total_orders if total_orders > 0 else 0

            return {
                'total_orders': total_orders,
                'by_status': by_status,
                'active_orders': len(self._active_orders),
                'total_volume': total_volume,
                'fill_rate': fill_rate
            }


# Singleton
_manager: Optional[LimitOrderManager] = None


def get_limit_order_manager() -> LimitOrderManager:
    """Get singleton limit order manager."""
    global _manager
    if _manager is None:
        _manager = LimitOrderManager()
    return _manager
