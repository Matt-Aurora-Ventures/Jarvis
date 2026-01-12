"""
Order Book Manager - L2/L3 depth data from DEXs.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import json
import sqlite3
from pathlib import Path
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class OrderSide(Enum):
    """Order side."""
    BID = "bid"
    ASK = "ask"


class DEXSource(Enum):
    """DEX sources for order book data."""
    JUPITER = "jupiter"
    RAYDIUM = "raydium"
    ORCA = "orca"
    PHOENIX = "phoenix"
    OPENBOOK = "openbook"
    LIFINITY = "lifinity"


@dataclass
class OrderLevel:
    """Single price level in order book."""
    price: float
    size: float
    source: DEXSource
    orders_count: int = 1
    timestamp: str = ""


@dataclass
class OrderBook:
    """Full order book snapshot."""
    symbol: str
    bids: List[OrderLevel]  # Sorted high to low
    asks: List[OrderLevel]  # Sorted low to high
    timestamp: str
    source: DEXSource
    mid_price: float = 0.0
    spread: float = 0.0
    spread_bps: float = 0.0
    depth_imbalance: float = 0.0  # -1 to 1, positive = more bids

    def __post_init__(self):
        if self.bids and self.asks:
            best_bid = self.bids[0].price
            best_ask = self.asks[0].price
            self.mid_price = (best_bid + best_ask) / 2
            self.spread = best_ask - best_bid
            self.spread_bps = (self.spread / self.mid_price) * 10000 if self.mid_price > 0 else 0

            # Calculate depth imbalance
            bid_depth = sum(level.size * level.price for level in self.bids[:10])
            ask_depth = sum(level.size * level.price for level in self.asks[:10])
            total_depth = bid_depth + ask_depth
            if total_depth > 0:
                self.depth_imbalance = (bid_depth - ask_depth) / total_depth


@dataclass
class AggregatedOrderBook:
    """Order book aggregated from multiple DEXs."""
    symbol: str
    bids: List[OrderLevel]
    asks: List[OrderLevel]
    timestamp: str
    sources: List[DEXSource]
    mid_price: float = 0.0
    spread: float = 0.0
    spread_bps: float = 0.0
    depth_imbalance: float = 0.0
    total_bid_liquidity: float = 0.0
    total_ask_liquidity: float = 0.0
    best_bid_source: DEXSource = None
    best_ask_source: DEXSource = None


@dataclass
class LiquidityZone:
    """Significant liquidity concentration."""
    price: float
    total_size: float
    price_range: Tuple[float, float]
    side: OrderSide
    strength: float  # 0-1
    sources: List[DEXSource]


@dataclass
class OrderBookMetrics:
    """Order book analytics."""
    symbol: str
    timestamp: str
    spread_bps: float
    depth_1pct_bid: float  # Liquidity within 1% of mid
    depth_1pct_ask: float
    depth_5pct_bid: float  # Liquidity within 5% of mid
    depth_5pct_ask: float
    imbalance: float
    vwap_bid: float  # Volume-weighted average price
    vwap_ask: float
    support_levels: List[float]
    resistance_levels: List[float]


class OrderBookDB:
    """SQLite storage for order book data."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS order_book_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    source TEXT NOT NULL,
                    mid_price REAL,
                    spread_bps REAL,
                    depth_imbalance REAL,
                    bid_levels_json TEXT,
                    ask_levels_json TEXT,
                    timestamp TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS liquidity_zones (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    price REAL,
                    size REAL,
                    side TEXT,
                    strength REAL,
                    timestamp TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS spread_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    source TEXT NOT NULL,
                    spread_bps REAL,
                    timestamp TEXT
                )
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ob_symbol ON order_book_snapshots(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ob_time ON order_book_snapshots(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_lz_symbol ON liquidity_zones(symbol)")

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


class OrderBookManager:
    """
    Manage order book data from multiple DEXs.

    Usage:
        manager = OrderBookManager()

        # Update order book
        await manager.update_order_book("SOL", DEXSource.JUPITER, bids, asks)

        # Get aggregated book
        book = manager.get_aggregated_book("SOL")

        # Analyze liquidity
        zones = manager.find_liquidity_zones("SOL")

        # Get metrics
        metrics = manager.get_metrics("SOL")
    """

    def __init__(self, db_path: Optional[Path] = None):
        db_path = db_path or Path(__file__).parent.parent / "data" / "order_book.db"
        self.db = OrderBookDB(db_path)
        self._books: Dict[str, Dict[DEXSource, OrderBook]] = defaultdict(dict)
        self._aggregation_levels = 50  # Number of price levels to keep

    async def update_order_book(
        self,
        symbol: str,
        source: DEXSource,
        bids: List[Tuple[float, float]],  # (price, size)
        asks: List[Tuple[float, float]],
        orders_count: Optional[List[int]] = None
    ):
        """Update order book from a DEX."""
        timestamp = datetime.now(timezone.utc).isoformat()

        bid_levels = [
            OrderLevel(
                price=price,
                size=size,
                source=source,
                orders_count=orders_count[i] if orders_count else 1,
                timestamp=timestamp
            )
            for i, (price, size) in enumerate(bids)
        ]

        ask_levels = [
            OrderLevel(
                price=price,
                size=size,
                source=source,
                orders_count=orders_count[len(bids) + i] if orders_count else 1,
                timestamp=timestamp
            )
            for i, (price, size) in enumerate(asks)
        ]

        # Sort bids high to low, asks low to high
        bid_levels.sort(key=lambda x: x.price, reverse=True)
        ask_levels.sort(key=lambda x: x.price)

        book = OrderBook(
            symbol=symbol.upper(),
            bids=bid_levels[:self._aggregation_levels],
            asks=ask_levels[:self._aggregation_levels],
            timestamp=timestamp,
            source=source
        )

        self._books[symbol.upper()][source] = book

        # Save snapshot
        self._save_snapshot(book)

        logger.debug(f"Updated {symbol} order book from {source.value}: "
                    f"spread={book.spread_bps:.1f}bps, imbalance={book.depth_imbalance:.2f}")

    def _save_snapshot(self, book: OrderBook):
        """Save order book snapshot to database."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            bid_json = json.dumps([(l.price, l.size) for l in book.bids[:20]])
            ask_json = json.dumps([(l.price, l.size) for l in book.asks[:20]])

            cursor.execute("""
                INSERT INTO order_book_snapshots
                (symbol, source, mid_price, spread_bps, depth_imbalance,
                 bid_levels_json, ask_levels_json, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                book.symbol, book.source.value, book.mid_price,
                book.spread_bps, book.depth_imbalance,
                bid_json, ask_json, book.timestamp
            ))

            # Also save spread history
            cursor.execute("""
                INSERT INTO spread_history (symbol, source, spread_bps, timestamp)
                VALUES (?, ?, ?, ?)
            """, (book.symbol, book.source.value, book.spread_bps, book.timestamp))

            conn.commit()

    def get_order_book(self, symbol: str, source: DEXSource) -> Optional[OrderBook]:
        """Get order book from specific source."""
        return self._books.get(symbol.upper(), {}).get(source)

    def get_aggregated_book(self, symbol: str) -> Optional[AggregatedOrderBook]:
        """Get order book aggregated from all sources."""
        symbol = symbol.upper()
        source_books = self._books.get(symbol, {})

        if not source_books:
            return None

        # Collect all bids and asks
        all_bids: Dict[float, OrderLevel] = {}
        all_asks: Dict[float, OrderLevel] = {}

        best_bid_price = 0
        best_bid_source = None
        best_ask_price = float('inf')
        best_ask_source = None

        for source, book in source_books.items():
            for level in book.bids:
                price_key = round(level.price, 8)
                if price_key in all_bids:
                    all_bids[price_key].size += level.size
                else:
                    all_bids[price_key] = OrderLevel(
                        price=level.price,
                        size=level.size,
                        source=source,
                        timestamp=level.timestamp
                    )

                if level.price > best_bid_price:
                    best_bid_price = level.price
                    best_bid_source = source

            for level in book.asks:
                price_key = round(level.price, 8)
                if price_key in all_asks:
                    all_asks[price_key].size += level.size
                else:
                    all_asks[price_key] = OrderLevel(
                        price=level.price,
                        size=level.size,
                        source=source,
                        timestamp=level.timestamp
                    )

                if level.price < best_ask_price:
                    best_ask_price = level.price
                    best_ask_source = source

        # Sort and limit
        sorted_bids = sorted(all_bids.values(), key=lambda x: x.price, reverse=True)[:self._aggregation_levels]
        sorted_asks = sorted(all_asks.values(), key=lambda x: x.price)[:self._aggregation_levels]

        timestamp = datetime.now(timezone.utc).isoformat()

        # Calculate metrics
        mid_price = (best_bid_price + best_ask_price) / 2 if best_bid_price > 0 and best_ask_price < float('inf') else 0
        spread = best_ask_price - best_bid_price if best_ask_price < float('inf') else 0
        spread_bps = (spread / mid_price) * 10000 if mid_price > 0 else 0

        total_bid_liq = sum(l.price * l.size for l in sorted_bids)
        total_ask_liq = sum(l.price * l.size for l in sorted_asks)

        imbalance = 0
        if total_bid_liq + total_ask_liq > 0:
            imbalance = (total_bid_liq - total_ask_liq) / (total_bid_liq + total_ask_liq)

        return AggregatedOrderBook(
            symbol=symbol,
            bids=sorted_bids,
            asks=sorted_asks,
            timestamp=timestamp,
            sources=list(source_books.keys()),
            mid_price=mid_price,
            spread=spread,
            spread_bps=spread_bps,
            depth_imbalance=imbalance,
            total_bid_liquidity=total_bid_liq,
            total_ask_liquidity=total_ask_liq,
            best_bid_source=best_bid_source,
            best_ask_source=best_ask_source
        )

    def find_liquidity_zones(
        self,
        symbol: str,
        price_buckets: int = 20,
        min_strength: float = 0.3
    ) -> List[LiquidityZone]:
        """Find significant liquidity concentrations."""
        book = self.get_aggregated_book(symbol)
        if not book:
            return []

        zones = []

        # Analyze bid side
        if book.bids:
            bid_zones = self._find_zones_in_levels(
                book.bids, OrderSide.BID, price_buckets, min_strength
            )
            zones.extend(bid_zones)

        # Analyze ask side
        if book.asks:
            ask_zones = self._find_zones_in_levels(
                book.asks, OrderSide.ASK, price_buckets, min_strength
            )
            zones.extend(ask_zones)

        # Save significant zones
        for zone in zones:
            self._save_liquidity_zone(symbol, zone)

        return zones

    def _find_zones_in_levels(
        self,
        levels: List[OrderLevel],
        side: OrderSide,
        buckets: int,
        min_strength: float
    ) -> List[LiquidityZone]:
        """Find liquidity zones in order levels."""
        if not levels:
            return []

        # Create price buckets
        prices = [l.price for l in levels]
        min_price = min(prices)
        max_price = max(prices)
        price_range = max_price - min_price

        if price_range == 0:
            return []

        bucket_size = price_range / buckets
        bucket_liquidity: Dict[int, Tuple[float, List[DEXSource]]] = defaultdict(lambda: (0, []))

        for level in levels:
            bucket_idx = int((level.price - min_price) / bucket_size)
            bucket_idx = min(bucket_idx, buckets - 1)
            current_liq, sources = bucket_liquidity[bucket_idx]
            bucket_liquidity[bucket_idx] = (
                current_liq + level.size * level.price,
                sources + [level.source]
            )

        # Find significant zones
        total_liquidity = sum(liq for liq, _ in bucket_liquidity.values())
        if total_liquidity == 0:
            return []

        zones = []
        for bucket_idx, (liquidity, sources) in bucket_liquidity.items():
            strength = liquidity / total_liquidity
            if strength >= min_strength:
                bucket_min = min_price + bucket_idx * bucket_size
                bucket_max = bucket_min + bucket_size
                zones.append(LiquidityZone(
                    price=(bucket_min + bucket_max) / 2,
                    total_size=liquidity,
                    price_range=(bucket_min, bucket_max),
                    side=side,
                    strength=strength,
                    sources=list(set(sources))
                ))

        return sorted(zones, key=lambda z: z.strength, reverse=True)

    def _save_liquidity_zone(self, symbol: str, zone: LiquidityZone):
        """Save liquidity zone to database."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO liquidity_zones (symbol, price, size, side, strength, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                symbol, zone.price, zone.total_size, zone.side.value,
                zone.strength, datetime.now(timezone.utc).isoformat()
            ))
            conn.commit()

    def get_metrics(self, symbol: str) -> Optional[OrderBookMetrics]:
        """Get order book analytics."""
        book = self.get_aggregated_book(symbol)
        if not book or not book.mid_price:
            return None

        mid = book.mid_price

        # Calculate depth at different price levels
        depth_1pct_bid = sum(
            l.price * l.size for l in book.bids
            if l.price >= mid * 0.99
        )
        depth_1pct_ask = sum(
            l.price * l.size for l in book.asks
            if l.price <= mid * 1.01
        )
        depth_5pct_bid = sum(
            l.price * l.size for l in book.bids
            if l.price >= mid * 0.95
        )
        depth_5pct_ask = sum(
            l.price * l.size for l in book.asks
            if l.price <= mid * 1.05
        )

        # Calculate VWAP
        bid_value = sum(l.price * l.size for l in book.bids)
        bid_volume = sum(l.size for l in book.bids)
        vwap_bid = bid_value / bid_volume if bid_volume > 0 else 0

        ask_value = sum(l.price * l.size for l in book.asks)
        ask_volume = sum(l.size for l in book.asks)
        vwap_ask = ask_value / ask_volume if ask_volume > 0 else 0

        # Find support/resistance levels from liquidity zones
        zones = self.find_liquidity_zones(symbol)
        support_levels = [z.price for z in zones if z.side == OrderSide.BID][:3]
        resistance_levels = [z.price for z in zones if z.side == OrderSide.ASK][:3]

        return OrderBookMetrics(
            symbol=symbol,
            timestamp=book.timestamp,
            spread_bps=book.spread_bps,
            depth_1pct_bid=depth_1pct_bid,
            depth_1pct_ask=depth_1pct_ask,
            depth_5pct_bid=depth_5pct_bid,
            depth_5pct_ask=depth_5pct_ask,
            imbalance=book.depth_imbalance,
            vwap_bid=vwap_bid,
            vwap_ask=vwap_ask,
            support_levels=support_levels,
            resistance_levels=resistance_levels
        )

    def estimate_slippage(
        self,
        symbol: str,
        side: OrderSide,
        size_usd: float
    ) -> Dict[str, float]:
        """Estimate slippage for a given order size."""
        book = self.get_aggregated_book(symbol)
        if not book:
            return {"slippage_bps": 0, "avg_price": 0, "filled_size": 0}

        levels = book.asks if side == OrderSide.BID else book.bids
        if not levels:
            return {"slippage_bps": 0, "avg_price": 0, "filled_size": 0}

        remaining = size_usd
        total_cost = 0
        total_size = 0

        for level in levels:
            level_value = level.price * level.size
            if level_value >= remaining:
                # Partial fill at this level
                fill_size = remaining / level.price
                total_cost += remaining
                total_size += fill_size
                remaining = 0
                break
            else:
                # Full fill at this level
                total_cost += level_value
                total_size += level.size
                remaining -= level_value

        if total_size == 0:
            return {"slippage_bps": 0, "avg_price": 0, "filled_size": 0}

        avg_price = total_cost / total_size
        reference_price = levels[0].price
        slippage = abs(avg_price - reference_price) / reference_price
        slippage_bps = slippage * 10000

        return {
            "slippage_bps": slippage_bps,
            "avg_price": avg_price,
            "filled_size": total_size,
            "unfilled_usd": remaining
        }

    def get_spread_history(
        self,
        symbol: str,
        source: Optional[DEXSource] = None,
        hours: int = 24
    ) -> List[Dict]:
        """Get historical spread data."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            query = """
                SELECT source, spread_bps, timestamp
                FROM spread_history
                WHERE symbol = ?
                AND datetime(timestamp) > datetime('now', ?)
            """
            params = [symbol.upper(), f'-{hours} hours']

            if source:
                query += " AND source = ?"
                params.append(source.value)

            query += " ORDER BY timestamp ASC"

            cursor.execute(query, params)

            return [
                {
                    'source': row['source'],
                    'spread_bps': row['spread_bps'],
                    'timestamp': row['timestamp']
                }
                for row in cursor.fetchall()
            ]

    def get_best_execution_route(
        self,
        symbol: str,
        side: OrderSide,
        size_usd: float
    ) -> Dict[str, Any]:
        """Find best execution route across DEXs."""
        symbol = symbol.upper()
        source_books = self._books.get(symbol, {})

        if not source_books:
            return {"error": "No order book data available"}

        routes = []

        for source, book in source_books.items():
            slippage_info = self.estimate_slippage(symbol, side, size_usd)
            routes.append({
                "source": source.value,
                "slippage_bps": slippage_info["slippage_bps"],
                "avg_price": slippage_info["avg_price"],
                "liquidity_available": book.total_bid_liquidity if side == OrderSide.ASK else book.total_ask_liquidity
            })

        # Sort by slippage
        routes.sort(key=lambda r: r["slippage_bps"])

        return {
            "symbol": symbol,
            "side": side.value,
            "size_usd": size_usd,
            "best_route": routes[0] if routes else None,
            "all_routes": routes
        }


# Singleton
_manager: Optional[OrderBookManager] = None


def get_order_book_manager() -> OrderBookManager:
    """Get singleton order book manager."""
    global _manager
    if _manager is None:
        _manager = OrderBookManager()
    return _manager
