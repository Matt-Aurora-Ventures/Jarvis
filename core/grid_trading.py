"""
Grid Trading Bot - Automated grid trading strategies.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import json
import sqlite3
from pathlib import Path
from contextlib import contextmanager
import uuid

logger = logging.getLogger(__name__)


class GridType(Enum):
    """Grid trading types."""
    ARITHMETIC = "arithmetic"  # Equal price spacing
    GEOMETRIC = "geometric"  # Percentage spacing
    FIBONACCI = "fibonacci"  # Fib-based levels


class GridStatus(Enum):
    """Grid bot status."""
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETED = "completed"


class GridOrderSide(Enum):
    """Grid order side."""
    BUY = "buy"
    SELL = "sell"


class GridOrderStatus(Enum):
    """Grid order status."""
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    CANCELLED = "cancelled"


@dataclass
class GridLevel:
    """A single grid level."""
    level_id: int
    price: float
    buy_order_id: Optional[str] = None
    sell_order_id: Optional[str] = None
    buy_filled: bool = False
    sell_filled: bool = False
    buy_fill_price: float = 0.0
    sell_fill_price: float = 0.0
    profit: float = 0.0


@dataclass
class GridConfig:
    """Grid trading configuration."""
    symbol: str
    lower_price: float
    upper_price: float
    grid_count: int
    total_investment: float
    grid_type: GridType = GridType.ARITHMETIC
    take_profit: Optional[float] = None  # Stop if price exceeds
    stop_loss: Optional[float] = None  # Stop if price falls below
    trailing_up: bool = False  # Move grid up as price rises
    trailing_down: bool = False  # Move grid down as price falls


@dataclass
class GridBot:
    """A grid trading bot instance."""
    id: str
    config: GridConfig
    status: GridStatus
    levels: List[GridLevel]
    created_at: str
    updated_at: str
    started_at: Optional[str] = None
    stopped_at: Optional[str] = None
    total_trades: int = 0
    total_profit: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    current_price: float = 0.0
    invested_amount: float = 0.0
    base_balance: float = 0.0  # Token balance
    quote_balance: float = 0.0  # USD balance
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GridTrade:
    """A completed grid trade."""
    bot_id: str
    level_id: int
    side: GridOrderSide
    price: float
    size: float
    value: float
    fee: float
    timestamp: str
    tx_signature: Optional[str] = None


class GridTradingDB:
    """SQLite storage for grid trading."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS grid_bots (
                    id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    lower_price REAL,
                    upper_price REAL,
                    grid_count INTEGER,
                    grid_type TEXT,
                    total_investment REAL,
                    take_profit REAL,
                    stop_loss REAL,
                    trailing_up INTEGER,
                    trailing_down INTEGER,
                    status TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    started_at TEXT,
                    stopped_at TEXT,
                    total_trades INTEGER DEFAULT 0,
                    total_profit REAL DEFAULT 0,
                    realized_pnl REAL DEFAULT 0,
                    unrealized_pnl REAL DEFAULT 0,
                    invested_amount REAL DEFAULT 0,
                    base_balance REAL DEFAULT 0,
                    quote_balance REAL DEFAULT 0,
                    metadata_json TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS grid_levels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bot_id TEXT NOT NULL,
                    level_id INTEGER,
                    price REAL,
                    buy_order_id TEXT,
                    sell_order_id TEXT,
                    buy_filled INTEGER DEFAULT 0,
                    sell_filled INTEGER DEFAULT 0,
                    buy_fill_price REAL DEFAULT 0,
                    sell_fill_price REAL DEFAULT 0,
                    profit REAL DEFAULT 0,
                    FOREIGN KEY (bot_id) REFERENCES grid_bots(id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS grid_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bot_id TEXT NOT NULL,
                    level_id INTEGER,
                    side TEXT,
                    price REAL,
                    size REAL,
                    value REAL,
                    fee REAL,
                    timestamp TEXT,
                    tx_signature TEXT,
                    FOREIGN KEY (bot_id) REFERENCES grid_bots(id)
                )
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_grid_symbol ON grid_bots(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_grid_status ON grid_bots(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_levels_bot ON grid_levels(bot_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_bot ON grid_trades(bot_id)")

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


class GridTradingManager:
    """
    Manage grid trading bots.

    Usage:
        manager = GridTradingManager()

        # Create a grid bot
        bot = await manager.create_bot(GridConfig(
            symbol="SOL",
            lower_price=80.0,
            upper_price=120.0,
            grid_count=10,
            total_investment=1000.0
        ))

        # Start the bot
        await manager.start_bot(bot.id)

        # Monitor performance
        stats = manager.get_bot_stats(bot.id)
    """

    def __init__(self, db_path: Optional[Path] = None):
        db_path = db_path or Path(__file__).parent.parent / "data" / "grid_trading.db"
        self.db = GridTradingDB(db_path)
        self._bots: Dict[str, GridBot] = {}
        self._price_feeds: Dict[str, Callable] = {}
        self._order_callback: Optional[Callable] = None
        self._running = False

    async def create_bot(self, config: GridConfig) -> GridBot:
        """Create a new grid trading bot."""
        bot_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc).isoformat()

        # Generate grid levels
        levels = self._generate_levels(config)

        bot = GridBot(
            id=bot_id,
            config=config,
            status=GridStatus.CREATED,
            levels=levels,
            created_at=now,
            updated_at=now,
            quote_balance=config.total_investment
        )

        # Save to database
        self._save_bot(bot)

        # Store in memory
        self._bots[bot_id] = bot

        logger.info(f"Created grid bot {bot_id} for {config.symbol}: "
                   f"{config.lower_price}-{config.upper_price} with {config.grid_count} grids")

        return bot

    def _generate_levels(self, config: GridConfig) -> List[GridLevel]:
        """Generate grid price levels."""
        levels = []

        if config.grid_type == GridType.ARITHMETIC:
            # Equal price spacing
            step = (config.upper_price - config.lower_price) / (config.grid_count - 1)
            for i in range(config.grid_count):
                price = config.lower_price + (i * step)
                levels.append(GridLevel(level_id=i, price=price))

        elif config.grid_type == GridType.GEOMETRIC:
            # Percentage spacing
            ratio = (config.upper_price / config.lower_price) ** (1 / (config.grid_count - 1))
            for i in range(config.grid_count):
                price = config.lower_price * (ratio ** i)
                levels.append(GridLevel(level_id=i, price=price))

        elif config.grid_type == GridType.FIBONACCI:
            # Fibonacci retracement levels
            fib_levels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
            price_range = config.upper_price - config.lower_price

            for i, fib in enumerate(fib_levels):
                price = config.lower_price + (price_range * fib)
                levels.append(GridLevel(level_id=i, price=price))

        return levels

    def _save_bot(self, bot: GridBot):
        """Save bot to database."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO grid_bots
                (id, symbol, lower_price, upper_price, grid_count, grid_type,
                 total_investment, take_profit, stop_loss, trailing_up, trailing_down,
                 status, created_at, updated_at, started_at, stopped_at,
                 total_trades, total_profit, realized_pnl, unrealized_pnl,
                 invested_amount, base_balance, quote_balance, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                bot.id, bot.config.symbol, bot.config.lower_price, bot.config.upper_price,
                bot.config.grid_count, bot.config.grid_type.value, bot.config.total_investment,
                bot.config.take_profit, bot.config.stop_loss,
                1 if bot.config.trailing_up else 0, 1 if bot.config.trailing_down else 0,
                bot.status.value, bot.created_at, bot.updated_at, bot.started_at, bot.stopped_at,
                bot.total_trades, bot.total_profit, bot.realized_pnl, bot.unrealized_pnl,
                bot.invested_amount, bot.base_balance, bot.quote_balance,
                json.dumps(bot.metadata)
            ))

            # Save levels
            for level in bot.levels:
                cursor.execute("""
                    INSERT OR REPLACE INTO grid_levels
                    (bot_id, level_id, price, buy_order_id, sell_order_id,
                     buy_filled, sell_filled, buy_fill_price, sell_fill_price, profit)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    bot.id, level.level_id, level.price,
                    level.buy_order_id, level.sell_order_id,
                    1 if level.buy_filled else 0, 1 if level.sell_filled else 0,
                    level.buy_fill_price, level.sell_fill_price, level.profit
                ))

            conn.commit()

    def set_price_feed(self, symbol: str, callback: Callable[[], float]):
        """Set price feed for a symbol."""
        self._price_feeds[symbol.upper()] = callback

    def set_order_callback(self, callback: Callable):
        """Set callback for placing orders."""
        self._order_callback = callback

    async def start_bot(self, bot_id: str) -> bool:
        """Start a grid bot."""
        bot = self._bots.get(bot_id)
        if not bot:
            logger.error(f"Bot {bot_id} not found")
            return False

        if bot.status == GridStatus.RUNNING:
            logger.warning(f"Bot {bot_id} is already running")
            return False

        # Get current price
        price_feed = self._price_feeds.get(bot.config.symbol)
        if price_feed:
            bot.current_price = price_feed()
        else:
            logger.error(f"No price feed for {bot.config.symbol}")
            return False

        # Place initial orders
        await self._place_initial_orders(bot)

        bot.status = GridStatus.RUNNING
        bot.started_at = datetime.now(timezone.utc).isoformat()
        bot.updated_at = datetime.now(timezone.utc).isoformat()

        self._save_bot(bot)

        logger.info(f"Started grid bot {bot_id}")
        return True

    async def _place_initial_orders(self, bot: GridBot):
        """Place initial grid orders based on current price."""
        current_price = bot.current_price

        # Calculate order size per grid
        order_value = bot.config.total_investment / bot.config.grid_count
        invested = 0

        for level in bot.levels:
            if level.price < current_price:
                # Place buy order below current price
                size = order_value / level.price
                order_id = await self._place_order(
                    bot, level, GridOrderSide.BUY, level.price, size
                )
                level.buy_order_id = order_id
                invested += order_value

            elif level.price > current_price:
                # Mark as needing a sell order (will be placed when buy fills)
                pass

        bot.invested_amount = invested
        bot.quote_balance = bot.config.total_investment - invested

    async def _place_order(
        self,
        bot: GridBot,
        level: GridLevel,
        side: GridOrderSide,
        price: float,
        size: float
    ) -> Optional[str]:
        """Place a grid order."""
        if self._order_callback:
            try:
                result = await self._order_callback(
                    symbol=bot.config.symbol,
                    side=side.value,
                    price=price,
                    size=size,
                    metadata={'bot_id': bot.id, 'level_id': level.level_id}
                )
                return result.get('order_id')
            except Exception as e:
                logger.error(f"Failed to place order: {e}")
                return None
        else:
            # Simulated order ID
            return f"sim_{bot.id}_{level.level_id}_{side.value}"

    async def process_fill(
        self,
        bot_id: str,
        level_id: int,
        side: GridOrderSide,
        fill_price: float,
        fill_size: float,
        fee: float = 0
    ):
        """Process a filled order."""
        bot = self._bots.get(bot_id)
        if not bot:
            return

        level = next((l for l in bot.levels if l.level_id == level_id), None)
        if not level:
            return

        now = datetime.now(timezone.utc).isoformat()
        fill_value = fill_price * fill_size

        if side == GridOrderSide.BUY:
            level.buy_filled = True
            level.buy_fill_price = fill_price
            bot.base_balance += fill_size
            bot.quote_balance -= fill_value

            # Place corresponding sell order
            sell_price = self._get_sell_price(bot, level)
            sell_order_id = await self._place_order(
                bot, level, GridOrderSide.SELL, sell_price, fill_size
            )
            level.sell_order_id = sell_order_id

        else:  # SELL
            level.sell_filled = True
            level.sell_fill_price = fill_price
            bot.base_balance -= fill_size
            bot.quote_balance += fill_value

            # Calculate profit
            profit = (fill_price - level.buy_fill_price) * fill_size - fee
            level.profit = profit
            bot.realized_pnl += profit

            # Reset level for next cycle
            level.buy_filled = False
            level.sell_filled = False
            level.buy_fill_price = 0
            level.sell_fill_price = 0

            # Place new buy order
            buy_order_id = await self._place_order(
                bot, level, GridOrderSide.BUY, level.price, fill_size
            )
            level.buy_order_id = buy_order_id

        # Record trade
        trade = GridTrade(
            bot_id=bot_id,
            level_id=level_id,
            side=side,
            price=fill_price,
            size=fill_size,
            value=fill_value,
            fee=fee,
            timestamp=now
        )
        self._save_trade(trade)

        bot.total_trades += 1
        bot.total_profit = bot.realized_pnl
        bot.updated_at = now

        self._save_bot(bot)

        logger.info(f"Grid {bot_id} fill: {side.value} {fill_size} @ {fill_price}, profit: {level.profit:.4f}")

    def _get_sell_price(self, bot: GridBot, level: GridLevel) -> float:
        """Get sell price for a level (next level up)."""
        idx = bot.levels.index(level)
        if idx < len(bot.levels) - 1:
            return bot.levels[idx + 1].price
        return level.price * 1.02  # 2% above if at top

    def _save_trade(self, trade: GridTrade):
        """Save trade to database."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO grid_trades
                (bot_id, level_id, side, price, size, value, fee, timestamp, tx_signature)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade.bot_id, trade.level_id, trade.side.value, trade.price,
                trade.size, trade.value, trade.fee, trade.timestamp, trade.tx_signature
            ))
            conn.commit()

    async def stop_bot(self, bot_id: str, cancel_orders: bool = True) -> bool:
        """Stop a grid bot."""
        bot = self._bots.get(bot_id)
        if not bot:
            return False

        if cancel_orders:
            # Cancel all pending orders
            for level in bot.levels:
                if level.buy_order_id and not level.buy_filled:
                    await self._cancel_order(level.buy_order_id)
                if level.sell_order_id and not level.sell_filled:
                    await self._cancel_order(level.sell_order_id)

        bot.status = GridStatus.STOPPED
        bot.stopped_at = datetime.now(timezone.utc).isoformat()
        bot.updated_at = bot.stopped_at

        self._save_bot(bot)

        logger.info(f"Stopped grid bot {bot_id}")
        return True

    async def _cancel_order(self, order_id: str):
        """Cancel an order."""
        if self._order_callback:
            try:
                await self._order_callback(cancel=True, order_id=order_id)
            except Exception as e:
                logger.error(f"Failed to cancel order {order_id}: {e}")

    async def pause_bot(self, bot_id: str) -> bool:
        """Pause a grid bot."""
        bot = self._bots.get(bot_id)
        if not bot:
            return False

        bot.status = GridStatus.PAUSED
        bot.updated_at = datetime.now(timezone.utc).isoformat()
        self._save_bot(bot)

        logger.info(f"Paused grid bot {bot_id}")
        return True

    async def resume_bot(self, bot_id: str) -> bool:
        """Resume a paused grid bot."""
        bot = self._bots.get(bot_id)
        if not bot or bot.status != GridStatus.PAUSED:
            return False

        bot.status = GridStatus.RUNNING
        bot.updated_at = datetime.now(timezone.utc).isoformat()
        self._save_bot(bot)

        logger.info(f"Resumed grid bot {bot_id}")
        return True

    def update_price(self, bot_id: str, price: float):
        """Update current price for a bot."""
        bot = self._bots.get(bot_id)
        if not bot:
            return

        bot.current_price = price

        # Calculate unrealized PnL
        unrealized = 0
        for level in bot.levels:
            if level.buy_filled and not level.sell_filled:
                # Open position
                unrealized += (price - level.buy_fill_price) * (bot.quote_balance / len(bot.levels))

        bot.unrealized_pnl = unrealized

        # Check stop loss / take profit
        if bot.config.stop_loss and price <= bot.config.stop_loss:
            asyncio.create_task(self.stop_bot(bot_id))
            logger.warning(f"Grid {bot_id} hit stop loss at {price}")

        if bot.config.take_profit and price >= bot.config.take_profit:
            asyncio.create_task(self.stop_bot(bot_id))
            logger.info(f"Grid {bot_id} hit take profit at {price}")

    def get_bot(self, bot_id: str) -> Optional[GridBot]:
        """Get a bot by ID."""
        return self._bots.get(bot_id)

    def get_active_bots(self) -> List[GridBot]:
        """Get all active bots."""
        return [b for b in self._bots.values() if b.status == GridStatus.RUNNING]

    def get_bot_stats(self, bot_id: str) -> Dict[str, Any]:
        """Get statistics for a bot."""
        bot = self._bots.get(bot_id)
        if not bot:
            return {}

        filled_buys = sum(1 for l in bot.levels if l.buy_filled)
        filled_sells = sum(1 for l in bot.levels if l.sell_filled)
        total_value = bot.quote_balance + (bot.base_balance * bot.current_price)
        roi = ((total_value - bot.config.total_investment) / bot.config.total_investment) * 100

        return {
            'bot_id': bot_id,
            'symbol': bot.config.symbol,
            'status': bot.status.value,
            'grid_count': bot.config.grid_count,
            'price_range': f"{bot.config.lower_price}-{bot.config.upper_price}",
            'current_price': bot.current_price,
            'total_trades': bot.total_trades,
            'filled_buys': filled_buys,
            'filled_sells': filled_sells,
            'realized_pnl': bot.realized_pnl,
            'unrealized_pnl': bot.unrealized_pnl,
            'total_pnl': bot.realized_pnl + bot.unrealized_pnl,
            'roi_percent': roi,
            'base_balance': bot.base_balance,
            'quote_balance': bot.quote_balance,
            'total_value': total_value,
            'running_time': self._calculate_runtime(bot)
        }

    def _calculate_runtime(self, bot: GridBot) -> str:
        """Calculate bot runtime."""
        if not bot.started_at:
            return "Not started"

        start = datetime.fromisoformat(bot.started_at.replace('Z', '+00:00'))
        end = datetime.now(timezone.utc)
        if bot.stopped_at:
            end = datetime.fromisoformat(bot.stopped_at.replace('Z', '+00:00'))

        delta = end - start
        hours = delta.total_seconds() / 3600
        return f"{hours:.1f} hours"

    def get_trades(self, bot_id: str, limit: int = 100) -> List[GridTrade]:
        """Get trades for a bot."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM grid_trades
                WHERE bot_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (bot_id, limit))

            return [
                GridTrade(
                    bot_id=row['bot_id'],
                    level_id=row['level_id'],
                    side=GridOrderSide(row['side']),
                    price=row['price'],
                    size=row['size'],
                    value=row['value'],
                    fee=row['fee'],
                    timestamp=row['timestamp'],
                    tx_signature=row['tx_signature']
                )
                for row in cursor.fetchall()
            ]

    def load_bots(self):
        """Load all bots from database."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM grid_bots")

            for row in cursor.fetchall():
                config = GridConfig(
                    symbol=row['symbol'],
                    lower_price=row['lower_price'],
                    upper_price=row['upper_price'],
                    grid_count=row['grid_count'],
                    total_investment=row['total_investment'],
                    grid_type=GridType(row['grid_type']),
                    take_profit=row['take_profit'],
                    stop_loss=row['stop_loss'],
                    trailing_up=bool(row['trailing_up']),
                    trailing_down=bool(row['trailing_down'])
                )

                # Load levels
                cursor.execute("""
                    SELECT * FROM grid_levels WHERE bot_id = ? ORDER BY level_id
                """, (row['id'],))

                levels = [
                    GridLevel(
                        level_id=l['level_id'],
                        price=l['price'],
                        buy_order_id=l['buy_order_id'],
                        sell_order_id=l['sell_order_id'],
                        buy_filled=bool(l['buy_filled']),
                        sell_filled=bool(l['sell_filled']),
                        buy_fill_price=l['buy_fill_price'],
                        sell_fill_price=l['sell_fill_price'],
                        profit=l['profit']
                    )
                    for l in cursor.fetchall()
                ]

                bot = GridBot(
                    id=row['id'],
                    config=config,
                    status=GridStatus(row['status']),
                    levels=levels,
                    created_at=row['created_at'],
                    updated_at=row['updated_at'],
                    started_at=row['started_at'],
                    stopped_at=row['stopped_at'],
                    total_trades=row['total_trades'],
                    total_profit=row['total_profit'],
                    realized_pnl=row['realized_pnl'],
                    unrealized_pnl=row['unrealized_pnl'],
                    invested_amount=row['invested_amount'],
                    base_balance=row['base_balance'],
                    quote_balance=row['quote_balance'],
                    metadata=json.loads(row['metadata_json']) if row['metadata_json'] else {}
                )

                self._bots[bot.id] = bot

        logger.info(f"Loaded {len(self._bots)} grid bots")


# Singleton
_manager: Optional[GridTradingManager] = None


def get_grid_trading_manager() -> GridTradingManager:
    """Get singleton grid trading manager."""
    global _manager
    if _manager is None:
        _manager = GridTradingManager()
        _manager.load_bots()
    return _manager
