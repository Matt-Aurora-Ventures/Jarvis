"""
Market Maker Module - Automated market making with spread management.
Provides liquidity by placing bid/ask orders around a fair price.
"""
import asyncio
import sqlite3
import threading
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Callable
import math


class MMStrategy(Enum):
    """Market making strategies."""
    SIMPLE = "simple"              # Fixed spread around mid price
    DYNAMIC = "dynamic"            # Spread adjusts to volatility
    INVENTORY = "inventory"        # Spread skews based on inventory
    AVELLANEDA = "avellaneda"      # Avellaneda-Stoikov optimal MM
    GRID = "grid"                  # Grid-based market making


class OrderSide(Enum):
    """Order side."""
    BID = "bid"
    ASK = "ask"


class MMOrderStatus(Enum):
    """Market maker order status."""
    ACTIVE = "active"
    FILLED = "filled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


@dataclass
class MMOrder:
    """A market maker order."""
    order_id: str
    symbol: str
    side: OrderSide
    price: float
    size: float
    filled_size: float
    status: MMOrderStatus
    created_at: datetime
    updated_at: datetime
    fill_price: Optional[float] = None
    metadata: Dict = field(default_factory=dict)


@dataclass
class MMConfig:
    """Market maker configuration."""
    symbol: str
    strategy: MMStrategy
    base_spread_bps: float         # Base spread in basis points
    min_spread_bps: float          # Minimum spread
    max_spread_bps: float          # Maximum spread
    order_size: float              # Size per order
    num_levels: int                # Number of price levels
    level_spacing_bps: float       # Spacing between levels
    max_inventory: float           # Maximum inventory to hold
    inventory_target: float        # Target inventory (usually 0)
    refresh_interval_ms: int       # Order refresh interval
    min_order_value: float         # Minimum order value
    enabled: bool = True


@dataclass
class InventoryState:
    """Current inventory state."""
    symbol: str
    base_balance: float            # Balance in base currency
    quote_balance: float           # Balance in quote currency
    inventory_delta: float         # Delta from target
    skew: float                    # Price skew to apply
    updated_at: datetime


@dataclass
class MMStats:
    """Market maker statistics."""
    symbol: str
    total_volume: float
    total_trades: int
    total_pnl: float
    realized_pnl: float
    unrealized_pnl: float
    spread_captured: float
    inventory_cost: float
    uptime_percent: float
    fill_rate: float


class MarketMaker:
    """
    Automated market maker for providing liquidity.
    Places bid/ask orders around fair price with configurable spreads.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or str(
            Path(__file__).parent.parent / "data" / "market_maker.db"
        )
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

        self.configs: Dict[str, MMConfig] = {}
        self.active_orders: Dict[str, Dict[str, MMOrder]] = defaultdict(dict)
        self.inventory: Dict[str, InventoryState] = {}
        self.stats: Dict[str, MMStats] = {}

        self._lock = threading.Lock()
        self._running = False
        self._tasks: Dict[str, asyncio.Task] = {}

        # Callbacks
        self.order_callbacks: List[Callable] = []
        self.fill_callbacks: List[Callable] = []

        # Price feeds (to be connected)
        self.price_feeds: Dict[str, float] = {}
        self.volatility: Dict[str, float] = {}

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
                CREATE TABLE IF NOT EXISTS mm_configs (
                    symbol TEXT PRIMARY KEY,
                    strategy TEXT NOT NULL,
                    base_spread_bps REAL NOT NULL,
                    min_spread_bps REAL NOT NULL,
                    max_spread_bps REAL NOT NULL,
                    order_size REAL NOT NULL,
                    num_levels INTEGER NOT NULL,
                    level_spacing_bps REAL NOT NULL,
                    max_inventory REAL NOT NULL,
                    inventory_target REAL NOT NULL,
                    refresh_interval_ms INTEGER NOT NULL,
                    min_order_value REAL NOT NULL,
                    enabled INTEGER DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS mm_orders (
                    order_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    price REAL NOT NULL,
                    size REAL NOT NULL,
                    filled_size REAL DEFAULT 0,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    fill_price REAL,
                    metadata TEXT
                );

                CREATE TABLE IF NOT EXISTS mm_trades (
                    trade_id TEXT PRIMARY KEY,
                    order_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    price REAL NOT NULL,
                    size REAL NOT NULL,
                    fee REAL DEFAULT 0,
                    pnl REAL DEFAULT 0,
                    executed_at TEXT NOT NULL,
                    FOREIGN KEY (order_id) REFERENCES mm_orders(order_id)
                );

                CREATE TABLE IF NOT EXISTS mm_stats (
                    symbol TEXT PRIMARY KEY,
                    total_volume REAL DEFAULT 0,
                    total_trades INTEGER DEFAULT 0,
                    total_pnl REAL DEFAULT 0,
                    realized_pnl REAL DEFAULT 0,
                    spread_captured REAL DEFAULT 0,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_orders_symbol ON mm_orders(symbol);
                CREATE INDEX IF NOT EXISTS idx_orders_status ON mm_orders(status);
                CREATE INDEX IF NOT EXISTS idx_trades_symbol ON mm_trades(symbol);
            """)

    def configure(
        self,
        symbol: str,
        strategy: MMStrategy = MMStrategy.DYNAMIC,
        base_spread_bps: float = 10,
        min_spread_bps: float = 5,
        max_spread_bps: float = 50,
        order_size: float = 100,
        num_levels: int = 3,
        level_spacing_bps: float = 5,
        max_inventory: float = 1000,
        inventory_target: float = 0,
        refresh_interval_ms: int = 5000,
        min_order_value: float = 10
    ) -> MMConfig:
        """Configure market making for a symbol."""
        config = MMConfig(
            symbol=symbol,
            strategy=strategy,
            base_spread_bps=base_spread_bps,
            min_spread_bps=min_spread_bps,
            max_spread_bps=max_spread_bps,
            order_size=order_size,
            num_levels=num_levels,
            level_spacing_bps=level_spacing_bps,
            max_inventory=max_inventory,
            inventory_target=inventory_target,
            refresh_interval_ms=refresh_interval_ms,
            min_order_value=min_order_value,
            enabled=True
        )

        self.configs[symbol] = config

        with self._get_db() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO mm_configs
                (symbol, strategy, base_spread_bps, min_spread_bps, max_spread_bps,
                 order_size, num_levels, level_spacing_bps, max_inventory,
                 inventory_target, refresh_interval_ms, min_order_value, enabled)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (
                symbol, strategy.value, base_spread_bps, min_spread_bps,
                max_spread_bps, order_size, num_levels, level_spacing_bps,
                max_inventory, inventory_target, refresh_interval_ms, min_order_value
            ))

        return config

    def update_price(self, symbol: str, mid_price: float, volatility: Optional[float] = None):
        """Update price feed for a symbol."""
        self.price_feeds[symbol] = mid_price
        if volatility is not None:
            self.volatility[symbol] = volatility

    def update_inventory(
        self,
        symbol: str,
        base_balance: float,
        quote_balance: float
    ):
        """Update inventory state."""
        config = self.configs.get(symbol)
        if not config:
            return

        delta = base_balance - config.inventory_target
        skew = self._calculate_inventory_skew(delta, config.max_inventory)

        self.inventory[symbol] = InventoryState(
            symbol=symbol,
            base_balance=base_balance,
            quote_balance=quote_balance,
            inventory_delta=delta,
            skew=skew,
            updated_at=datetime.now()
        )

    def _calculate_inventory_skew(self, delta: float, max_inventory: float) -> float:
        """Calculate price skew based on inventory."""
        if max_inventory == 0:
            return 0

        # Linear skew based on inventory
        skew_factor = delta / max_inventory
        # Clamp between -1 and 1
        return max(-1, min(1, skew_factor))

    def calculate_quotes(self, symbol: str) -> Tuple[List[Tuple[float, float]], List[Tuple[float, float]]]:
        """Calculate bid and ask quotes."""
        config = self.configs.get(symbol)
        if not config:
            return [], []

        mid_price = self.price_feeds.get(symbol)
        if not mid_price:
            return [], []

        # Calculate spread based on strategy
        spread_bps = self._calculate_spread(symbol, config)

        # Get inventory skew
        inventory = self.inventory.get(symbol)
        skew = inventory.skew if inventory else 0

        # Calculate bid and ask prices
        half_spread = spread_bps / 10000 / 2
        bid_price = mid_price * (1 - half_spread - skew * half_spread)
        ask_price = mid_price * (1 + half_spread - skew * half_spread)

        # Generate multiple levels
        bids = []
        asks = []
        level_spacing = config.level_spacing_bps / 10000

        for i in range(config.num_levels):
            level_bid = bid_price * (1 - i * level_spacing)
            level_ask = ask_price * (1 + i * level_spacing)

            # Size decreases at outer levels
            size_factor = 1 / (1 + i * 0.5)
            level_size = config.order_size * size_factor

            bids.append((level_bid, level_size))
            asks.append((level_ask, level_size))

        return bids, asks

    def _calculate_spread(self, symbol: str, config: MMConfig) -> float:
        """Calculate spread based on strategy."""
        base_spread = config.base_spread_bps

        if config.strategy == MMStrategy.SIMPLE:
            return base_spread

        elif config.strategy == MMStrategy.DYNAMIC:
            # Adjust spread based on volatility
            vol = self.volatility.get(symbol, 0.02)
            vol_factor = 1 + vol * 10  # Higher vol = wider spread
            spread = base_spread * vol_factor
            return max(config.min_spread_bps, min(config.max_spread_bps, spread))

        elif config.strategy == MMStrategy.INVENTORY:
            # Widen spread when inventory is high
            inventory = self.inventory.get(symbol)
            if inventory:
                inv_factor = 1 + abs(inventory.skew) * 0.5
                spread = base_spread * inv_factor
                return max(config.min_spread_bps, min(config.max_spread_bps, spread))
            return base_spread

        elif config.strategy == MMStrategy.AVELLANEDA:
            # Avellaneda-Stoikov optimal market making
            return self._avellaneda_spread(symbol, config)

        return base_spread

    def _avellaneda_spread(self, symbol: str, config: MMConfig) -> float:
        """Calculate Avellaneda-Stoikov optimal spread."""
        vol = self.volatility.get(symbol, 0.02)
        gamma = 0.1  # Risk aversion parameter
        k = 1.5      # Order arrival intensity

        # Optimal spread formula: sigma^2 * gamma + 2/gamma * ln(1 + gamma/k)
        optimal_spread = vol**2 * gamma + (2 / gamma) * math.log(1 + gamma / k)

        # Convert to basis points
        spread_bps = optimal_spread * 10000

        return max(config.min_spread_bps, min(config.max_spread_bps, spread_bps))

    async def place_orders(self, symbol: str) -> List[MMOrder]:
        """Place market maker orders."""
        import uuid

        config = self.configs.get(symbol)
        if not config or not config.enabled:
            return []

        bids, asks = self.calculate_quotes(symbol)
        orders = []
        now = datetime.now()

        # Cancel existing orders first
        await self.cancel_all_orders(symbol)

        with self._lock:
            # Place bids
            for price, size in bids:
                if price * size < config.min_order_value:
                    continue

                order = MMOrder(
                    order_id=str(uuid.uuid4())[:12],
                    symbol=symbol,
                    side=OrderSide.BID,
                    price=price,
                    size=size,
                    filled_size=0,
                    status=MMOrderStatus.ACTIVE,
                    created_at=now,
                    updated_at=now
                )
                self.active_orders[symbol][order.order_id] = order
                orders.append(order)

            # Place asks
            for price, size in asks:
                if price * size < config.min_order_value:
                    continue

                order = MMOrder(
                    order_id=str(uuid.uuid4())[:12],
                    symbol=symbol,
                    side=OrderSide.ASK,
                    price=price,
                    size=size,
                    filled_size=0,
                    status=MMOrderStatus.ACTIVE,
                    created_at=now,
                    updated_at=now
                )
                self.active_orders[symbol][order.order_id] = order
                orders.append(order)

        # Save to database
        for order in orders:
            self._save_order(order)

        # Notify callbacks
        for callback in self.order_callbacks:
            try:
                callback(orders)
            except Exception:
                pass

        return orders

    def _save_order(self, order: MMOrder):
        """Save order to database."""
        import json
        with self._get_db() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO mm_orders
                (order_id, symbol, side, price, size, filled_size, status,
                 created_at, updated_at, fill_price, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                order.order_id, order.symbol, order.side.value,
                order.price, order.size, order.filled_size,
                order.status.value, order.created_at.isoformat(),
                order.updated_at.isoformat(), order.fill_price,
                json.dumps(order.metadata)
            ))

    async def cancel_all_orders(self, symbol: str):
        """Cancel all active orders for a symbol."""
        with self._lock:
            if symbol in self.active_orders:
                for order_id, order in self.active_orders[symbol].items():
                    order.status = MMOrderStatus.CANCELLED
                    order.updated_at = datetime.now()
                    self._save_order(order)
                self.active_orders[symbol].clear()

    def handle_fill(
        self,
        order_id: str,
        fill_price: float,
        fill_size: float,
        fee: float = 0
    ) -> Optional[MMOrder]:
        """Handle an order fill."""
        import uuid

        order = None
        for symbol_orders in self.active_orders.values():
            if order_id in symbol_orders:
                order = symbol_orders[order_id]
                break

        if not order:
            return None

        now = datetime.now()
        order.filled_size += fill_size
        order.fill_price = fill_price
        order.updated_at = now

        if order.filled_size >= order.size:
            order.status = MMOrderStatus.FILLED
            with self._lock:
                if order.symbol in self.active_orders:
                    self.active_orders[order.symbol].pop(order_id, None)

        self._save_order(order)

        # Calculate PnL
        mid_price = self.price_feeds.get(order.symbol, fill_price)
        if order.side == OrderSide.BID:
            pnl = (mid_price - fill_price) * fill_size - fee
        else:
            pnl = (fill_price - mid_price) * fill_size - fee

        # Record trade
        with self._get_db() as conn:
            conn.execute("""
                INSERT INTO mm_trades
                (trade_id, order_id, symbol, side, price, size, fee, pnl, executed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(uuid.uuid4())[:12], order_id, order.symbol,
                order.side.value, fill_price, fill_size, fee, pnl,
                now.isoformat()
            ))

            # Update stats
            conn.execute("""
                INSERT INTO mm_stats (symbol, total_volume, total_trades, realized_pnl, updated_at)
                VALUES (?, ?, 1, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                total_volume = total_volume + ?,
                total_trades = total_trades + 1,
                realized_pnl = realized_pnl + ?,
                updated_at = ?
            """, (
                order.symbol, fill_size * fill_price, pnl, now.isoformat(),
                fill_size * fill_price, pnl, now.isoformat()
            ))

        # Notify callbacks
        for callback in self.fill_callbacks:
            try:
                callback(order, fill_price, fill_size, pnl)
            except Exception:
                pass

        return order

    async def start(self, symbol: str):
        """Start market making for a symbol."""
        config = self.configs.get(symbol)
        if not config:
            raise ValueError(f"No config for symbol: {symbol}")

        self._running = True

        async def mm_loop():
            while self._running and config.enabled:
                try:
                    await self.place_orders(symbol)
                except Exception:
                    pass
                await asyncio.sleep(config.refresh_interval_ms / 1000)

        self._tasks[symbol] = asyncio.create_task(mm_loop())

    async def stop(self, symbol: str):
        """Stop market making for a symbol."""
        if symbol in self._tasks:
            self._tasks[symbol].cancel()
            del self._tasks[symbol]

        await self.cancel_all_orders(symbol)

    def stop_all(self):
        """Stop all market making."""
        self._running = False
        for task in self._tasks.values():
            task.cancel()
        self._tasks.clear()

    def get_stats(self, symbol: str) -> Optional[MMStats]:
        """Get market making statistics."""
        with self._get_db() as conn:
            row = conn.execute(
                "SELECT * FROM mm_stats WHERE symbol = ?",
                (symbol,)
            ).fetchone()

            if not row:
                return None

            return MMStats(
                symbol=symbol,
                total_volume=row["total_volume"],
                total_trades=row["total_trades"],
                total_pnl=row["realized_pnl"],
                realized_pnl=row["realized_pnl"],
                unrealized_pnl=0,  # Would need current positions
                spread_captured=row.get("spread_captured", 0),
                inventory_cost=0,
                uptime_percent=0,
                fill_rate=0
            )

    def register_order_callback(self, callback: Callable):
        """Register callback for new orders."""
        self.order_callbacks.append(callback)

    def register_fill_callback(self, callback: Callable):
        """Register callback for fills."""
        self.fill_callbacks.append(callback)


# Singleton instance
_market_maker: Optional[MarketMaker] = None


def get_market_maker() -> MarketMaker:
    """Get or create the market maker singleton."""
    global _market_maker
    if _market_maker is None:
        _market_maker = MarketMaker()
    return _market_maker
