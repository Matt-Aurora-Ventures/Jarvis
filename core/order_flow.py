"""
Order Flow Analyzer - Analyze order flow and market microstructure.
Tracks buy/sell pressure, large orders, and flow imbalances.
"""
import sqlite3
import threading
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class OrderType(Enum):
    """Order types."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    ICEBERG = "iceberg"


class TradeSide(Enum):
    """Trade side (aggressor)."""
    BUY = "buy"                    # Buyer lifted the offer
    SELL = "sell"                  # Seller hit the bid


class FlowSignal(Enum):
    """Order flow signals."""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    ABSORPTION = "absorption"      # Large orders absorbed
    EXHAUSTION = "exhaustion"      # Buying/selling exhaustion


@dataclass
class Trade:
    """A single trade."""
    trade_id: str
    symbol: str
    side: TradeSide
    price: float
    size: float
    value: float
    timestamp: datetime
    is_large: bool = False
    metadata: Dict = field(default_factory=dict)


@dataclass
class OrderFlowMetrics:
    """Order flow metrics for a period."""
    symbol: str
    period_minutes: int
    buy_volume: float
    sell_volume: float
    buy_count: int
    sell_count: int
    net_flow: float               # Buy - Sell
    flow_ratio: float             # Buy / Sell
    large_buy_volume: float
    large_sell_volume: float
    vwap: float
    avg_trade_size: float
    imbalance: float              # -1 to 1
    signal: FlowSignal
    timestamp: datetime


@dataclass
class VolumeProfile:
    """Volume profile at price levels."""
    symbol: str
    price_levels: Dict[float, float]  # Price -> Volume
    poc: float                        # Point of control
    vah: float                        # Value area high
    val: float                        # Value area low
    total_volume: float
    calculated_at: datetime


@dataclass
class DeltaMetrics:
    """Cumulative delta metrics."""
    symbol: str
    cumulative_delta: float       # Running buy - sell
    delta_divergence: bool        # Delta diverging from price
    price_trend: str              # "up", "down", "sideways"
    delta_trend: str              # "up", "down", "sideways"
    timestamp: datetime


@dataclass
class LargeOrder:
    """Detected large order."""
    order_id: str
    symbol: str
    side: TradeSide
    total_size: float
    avg_price: float
    num_fills: int
    duration_seconds: float
    detected_at: datetime
    is_iceberg: bool
    metadata: Dict = field(default_factory=dict)


class OrderFlowAnalyzer:
    """
    Analyzes order flow to detect market sentiment and large player activity.
    """

    # Large order threshold (as multiple of average)
    LARGE_ORDER_MULTIPLIER = 5

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or str(
            Path(__file__).parent.parent / "data" / "order_flow.db"
        )
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

        # Trade history per symbol
        self.trades: Dict[str, deque] = {}
        self.max_trades = 10000

        # Cumulative delta per symbol
        self.cumulative_delta: Dict[str, float] = {}

        # Average trade size for large order detection
        self.avg_trade_size: Dict[str, float] = {}

        # Potential iceberg orders being tracked
        self.iceberg_candidates: Dict[str, List[Trade]] = {}

        self._lock = threading.Lock()
        self.signal_callbacks: List = []

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
                CREATE TABLE IF NOT EXISTS trades (
                    trade_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    price REAL NOT NULL,
                    size REAL NOT NULL,
                    value REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    is_large INTEGER DEFAULT 0,
                    metadata TEXT
                );

                CREATE TABLE IF NOT EXISTS flow_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    period_minutes INTEGER NOT NULL,
                    buy_volume REAL NOT NULL,
                    sell_volume REAL NOT NULL,
                    net_flow REAL NOT NULL,
                    flow_ratio REAL NOT NULL,
                    imbalance REAL NOT NULL,
                    signal TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS large_orders (
                    order_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    total_size REAL NOT NULL,
                    avg_price REAL NOT NULL,
                    num_fills INTEGER NOT NULL,
                    duration_seconds REAL NOT NULL,
                    detected_at TEXT NOT NULL,
                    is_iceberg INTEGER DEFAULT 0,
                    metadata TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
                CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp);
                CREATE INDEX IF NOT EXISTS idx_flow_symbol ON flow_metrics(symbol);
            """)

    def add_trade(
        self,
        trade_id: str,
        symbol: str,
        side: TradeSide,
        price: float,
        size: float,
        timestamp: Optional[datetime] = None
    ) -> Trade:
        """Add a trade for analysis."""
        import json

        timestamp = timestamp or datetime.now()
        value = price * size

        # Check if large order
        avg = self.avg_trade_size.get(symbol, size)
        is_large = size > avg * self.LARGE_ORDER_MULTIPLIER

        trade = Trade(
            trade_id=trade_id,
            symbol=symbol,
            side=side,
            price=price,
            size=size,
            value=value,
            timestamp=timestamp,
            is_large=is_large
        )

        with self._lock:
            if symbol not in self.trades:
                self.trades[symbol] = deque(maxlen=self.max_trades)
            self.trades[symbol].append(trade)

            # Update cumulative delta
            delta = size if side == TradeSide.BUY else -size
            self.cumulative_delta[symbol] = self.cumulative_delta.get(symbol, 0) + delta

            # Update average trade size (exponential moving average)
            alpha = 0.01
            self.avg_trade_size[symbol] = alpha * size + (1 - alpha) * avg

            # Check for iceberg orders
            self._check_iceberg(trade)

        # Save to database
        with self._get_db() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO trades
                (trade_id, symbol, side, price, size, value, timestamp, is_large, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade_id, symbol, side.value, price, size, value,
                timestamp.isoformat(), 1 if is_large else 0,
                json.dumps(trade.metadata)
            ))

        return trade

    def _check_iceberg(self, trade: Trade):
        """Check if trade might be part of an iceberg order."""
        symbol = trade.symbol
        if symbol not in self.iceberg_candidates:
            self.iceberg_candidates[symbol] = []

        candidates = self.iceberg_candidates[symbol]

        # Look for repeated orders at same price within time window
        time_window = timedelta(seconds=60)
        price_tolerance = 0.001  # 0.1%

        matching = [
            t for t in candidates
            if abs(t.price - trade.price) / trade.price < price_tolerance
            and trade.timestamp - t.timestamp < time_window
            and t.side == trade.side
        ]

        if len(matching) >= 3:
            # Likely iceberg detected
            self._record_iceberg(trade.symbol, trade.side, matching + [trade])

        # Add to candidates and clean old ones
        candidates.append(trade)
        cutoff = datetime.now() - time_window
        self.iceberg_candidates[symbol] = [
            t for t in candidates if t.timestamp > cutoff
        ][-100:]  # Keep last 100

    def _record_iceberg(self, symbol: str, side: TradeSide, trades: List[Trade]):
        """Record detected iceberg order."""
        import uuid
        import json

        total_size = sum(t.size for t in trades)
        avg_price = sum(t.price * t.size for t in trades) / total_size
        duration = (trades[-1].timestamp - trades[0].timestamp).total_seconds()

        order = LargeOrder(
            order_id=str(uuid.uuid4())[:12],
            symbol=symbol,
            side=side,
            total_size=total_size,
            avg_price=avg_price,
            num_fills=len(trades),
            duration_seconds=duration,
            detected_at=datetime.now(),
            is_iceberg=True
        )

        with self._get_db() as conn:
            conn.execute("""
                INSERT INTO large_orders
                (order_id, symbol, side, total_size, avg_price, num_fills,
                 duration_seconds, detected_at, is_iceberg, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            """, (
                order.order_id, symbol, side.value, total_size,
                avg_price, len(trades), duration,
                order.detected_at.isoformat(), json.dumps({})
            ))

    def calculate_flow_metrics(
        self,
        symbol: str,
        period_minutes: int = 5
    ) -> Optional[OrderFlowMetrics]:
        """Calculate order flow metrics for a period."""
        trades = list(self.trades.get(symbol, []))
        if not trades:
            return None

        cutoff = datetime.now() - timedelta(minutes=period_minutes)
        period_trades = [t for t in trades if t.timestamp > cutoff]

        if not period_trades:
            return None

        buy_trades = [t for t in period_trades if t.side == TradeSide.BUY]
        sell_trades = [t for t in period_trades if t.side == TradeSide.SELL]

        buy_volume = sum(t.size for t in buy_trades)
        sell_volume = sum(t.size for t in sell_trades)
        total_volume = buy_volume + sell_volume

        net_flow = buy_volume - sell_volume
        flow_ratio = buy_volume / sell_volume if sell_volume > 0 else float('inf')

        large_buy = sum(t.size for t in buy_trades if t.is_large)
        large_sell = sum(t.size for t in sell_trades if t.is_large)

        # VWAP
        total_value = sum(t.value for t in period_trades)
        vwap = total_value / total_volume if total_volume > 0 else 0

        # Imbalance (-1 to 1)
        imbalance = net_flow / total_volume if total_volume > 0 else 0

        # Determine signal
        signal = self._determine_signal(imbalance, large_buy, large_sell)

        metrics = OrderFlowMetrics(
            symbol=symbol,
            period_minutes=period_minutes,
            buy_volume=buy_volume,
            sell_volume=sell_volume,
            buy_count=len(buy_trades),
            sell_count=len(sell_trades),
            net_flow=net_flow,
            flow_ratio=flow_ratio,
            large_buy_volume=large_buy,
            large_sell_volume=large_sell,
            vwap=vwap,
            avg_trade_size=total_volume / len(period_trades) if period_trades else 0,
            imbalance=imbalance,
            signal=signal,
            timestamp=datetime.now()
        )

        # Save to database
        with self._get_db() as conn:
            conn.execute("""
                INSERT INTO flow_metrics
                (symbol, period_minutes, buy_volume, sell_volume, net_flow,
                 flow_ratio, imbalance, signal, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                symbol, period_minutes, buy_volume, sell_volume, net_flow,
                flow_ratio, imbalance, signal.value, metrics.timestamp.isoformat()
            ))

        return metrics

    def _determine_signal(
        self,
        imbalance: float,
        large_buy: float,
        large_sell: float
    ) -> FlowSignal:
        """Determine order flow signal."""
        if imbalance > 0.3:
            if large_sell > large_buy * 2:
                return FlowSignal.ABSORPTION  # Selling absorbed
            return FlowSignal.BULLISH
        elif imbalance < -0.3:
            if large_buy > large_sell * 2:
                return FlowSignal.ABSORPTION  # Buying absorbed
            return FlowSignal.BEARISH
        else:
            return FlowSignal.NEUTRAL

    def get_volume_profile(
        self,
        symbol: str,
        period_minutes: int = 60,
        num_levels: int = 20
    ) -> Optional[VolumeProfile]:
        """Calculate volume profile."""
        trades = list(self.trades.get(symbol, []))
        if not trades:
            return None

        cutoff = datetime.now() - timedelta(minutes=period_minutes)
        period_trades = [t for t in trades if t.timestamp > cutoff]

        if not period_trades:
            return None

        # Find price range
        prices = [t.price for t in period_trades]
        min_price = min(prices)
        max_price = max(prices)
        price_range = max_price - min_price

        if price_range == 0:
            return None

        level_size = price_range / num_levels

        # Aggregate volume by price level
        levels: Dict[float, float] = {}
        for trade in period_trades:
            level = min_price + ((trade.price - min_price) // level_size) * level_size
            levels[level] = levels.get(level, 0) + trade.size

        total_volume = sum(levels.values())

        # Find Point of Control (highest volume level)
        poc = max(levels.items(), key=lambda x: x[1])[0]

        # Calculate Value Area (70% of volume)
        target_volume = total_volume * 0.7
        sorted_levels = sorted(levels.items(), key=lambda x: x[1], reverse=True)

        cumulative = 0
        value_area_levels = []
        for level, vol in sorted_levels:
            cumulative += vol
            value_area_levels.append(level)
            if cumulative >= target_volume:
                break

        vah = max(value_area_levels)
        val = min(value_area_levels)

        return VolumeProfile(
            symbol=symbol,
            price_levels=levels,
            poc=poc,
            vah=vah,
            val=val,
            total_volume=total_volume,
            calculated_at=datetime.now()
        )

    def get_delta_metrics(self, symbol: str) -> Optional[DeltaMetrics]:
        """Get cumulative delta metrics."""
        trades = list(self.trades.get(symbol, []))
        if len(trades) < 10:
            return None

        delta = self.cumulative_delta.get(symbol, 0)

        # Calculate trends
        recent = trades[-100:]
        old_delta = 0
        new_delta = 0
        mid = len(recent) // 2

        for i, trade in enumerate(recent):
            d = trade.size if trade.side == TradeSide.BUY else -trade.size
            if i < mid:
                old_delta += d
            else:
                new_delta += d

        delta_trend = "up" if new_delta > old_delta * 1.2 else (
            "down" if new_delta < old_delta * 0.8 else "sideways"
        )

        # Price trend
        old_price = sum(t.price for t in recent[:mid]) / mid
        new_price = sum(t.price for t in recent[mid:]) / (len(recent) - mid)

        price_trend = "up" if new_price > old_price * 1.01 else (
            "down" if new_price < old_price * 0.99 else "sideways"
        )

        # Divergence
        divergence = (
            (price_trend == "up" and delta_trend == "down") or
            (price_trend == "down" and delta_trend == "up")
        )

        return DeltaMetrics(
            symbol=symbol,
            cumulative_delta=delta,
            delta_divergence=divergence,
            price_trend=price_trend,
            delta_trend=delta_trend,
            timestamp=datetime.now()
        )

    def get_large_orders(
        self,
        symbol: str,
        hours: int = 24
    ) -> List[LargeOrder]:
        """Get recent large orders."""
        import json

        cutoff = datetime.now() - timedelta(hours=hours)

        with self._get_db() as conn:
            rows = conn.execute("""
                SELECT * FROM large_orders
                WHERE symbol = ? AND detected_at > ?
                ORDER BY detected_at DESC
            """, (symbol, cutoff.isoformat())).fetchall()

            return [
                LargeOrder(
                    order_id=row["order_id"],
                    symbol=row["symbol"],
                    side=TradeSide(row["side"]),
                    total_size=row["total_size"],
                    avg_price=row["avg_price"],
                    num_fills=row["num_fills"],
                    duration_seconds=row["duration_seconds"],
                    detected_at=datetime.fromisoformat(row["detected_at"]),
                    is_iceberg=bool(row["is_iceberg"]),
                    metadata=json.loads(row["metadata"] or "{}")
                )
                for row in rows
            ]

    def register_signal_callback(self, callback):
        """Register callback for flow signals."""
        self.signal_callbacks.append(callback)


# Singleton instance
_order_flow_analyzer: Optional[OrderFlowAnalyzer] = None


def get_order_flow_analyzer() -> OrderFlowAnalyzer:
    """Get or create the order flow analyzer singleton."""
    global _order_flow_analyzer
    if _order_flow_analyzer is None:
        _order_flow_analyzer = OrderFlowAnalyzer()
    return _order_flow_analyzer
