"""
Execution Optimizer - Optimize trade execution for best fills.
Analyzes market conditions and recommends optimal execution strategies.
"""
import asyncio
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class ExecutionStrategy(Enum):
    """Execution strategies."""
    MARKET = "market"              # Immediate market order
    LIMIT = "limit"                # Passive limit order
    TWAP = "twap"                  # Time-weighted average
    VWAP = "vwap"                  # Volume-weighted average
    ICEBERG = "iceberg"            # Hidden size
    SNIPER = "sniper"              # Wait for price level
    MOMENTUM = "momentum"          # Trade with momentum
    MEAN_REVERT = "mean_revert"    # Trade against momentum


class MarketCondition(Enum):
    """Market condition types."""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"
    LOW_LIQUIDITY = "low_liquidity"
    HIGH_VOLUME = "high_volume"


class UrgencyLevel(Enum):
    """Execution urgency."""
    LOW = "low"                    # Can wait for best price
    MEDIUM = "medium"              # Balance speed and price
    HIGH = "high"                  # Speed priority
    IMMEDIATE = "immediate"        # Must execute now


@dataclass
class ExecutionPlan:
    """A recommended execution plan."""
    plan_id: str
    symbol: str
    side: str
    total_size: float
    strategy: ExecutionStrategy
    urgency: UrgencyLevel
    expected_slippage: float
    expected_price: float
    num_orders: int
    order_sizes: List[float]
    time_intervals: List[int]      # Seconds between orders
    limit_prices: List[float]
    estimated_duration_seconds: int
    market_condition: MarketCondition
    confidence: float
    created_at: datetime
    expires_at: datetime
    metadata: Dict = field(default_factory=dict)


@dataclass
class ExecutionResult:
    """Result of an execution."""
    plan_id: str
    symbol: str
    side: str
    total_size: float
    filled_size: float
    avg_fill_price: float
    expected_price: float
    slippage: float
    num_fills: int
    total_fees: float
    execution_time_seconds: float
    success: bool
    started_at: datetime
    completed_at: datetime


@dataclass
class MarketAnalysis:
    """Analysis of current market conditions."""
    symbol: str
    condition: MarketCondition
    spread_bps: float
    depth_ratio: float             # Bid depth / Ask depth
    volatility: float
    momentum: float                # -1 to 1
    volume_profile: str            # "high", "normal", "low"
    best_strategy: ExecutionStrategy
    analyzed_at: datetime


class ExecutionOptimizer:
    """
    Optimizes trade execution by analyzing market conditions
    and recommending the best execution strategy.
    """

    # Strategy suitability by market condition
    STRATEGY_MATRIX = {
        MarketCondition.TRENDING_UP: {
            "buy": ExecutionStrategy.MOMENTUM,
            "sell": ExecutionStrategy.TWAP
        },
        MarketCondition.TRENDING_DOWN: {
            "buy": ExecutionStrategy.TWAP,
            "sell": ExecutionStrategy.MOMENTUM
        },
        MarketCondition.RANGING: {
            "buy": ExecutionStrategy.LIMIT,
            "sell": ExecutionStrategy.LIMIT
        },
        MarketCondition.VOLATILE: {
            "buy": ExecutionStrategy.VWAP,
            "sell": ExecutionStrategy.VWAP
        },
        MarketCondition.LOW_LIQUIDITY: {
            "buy": ExecutionStrategy.ICEBERG,
            "sell": ExecutionStrategy.ICEBERG
        },
        MarketCondition.HIGH_VOLUME: {
            "buy": ExecutionStrategy.MARKET,
            "sell": ExecutionStrategy.MARKET
        }
    }

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or str(
            Path(__file__).parent.parent / "data" / "execution_optimizer.db"
        )
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

        # Market data cache
        self.market_data: Dict[str, Dict] = {}
        self.order_books: Dict[str, Dict] = {}

        # Active plans
        self.active_plans: Dict[str, ExecutionPlan] = {}

        self._lock = threading.Lock()

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
                CREATE TABLE IF NOT EXISTS execution_plans (
                    plan_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    total_size REAL NOT NULL,
                    strategy TEXT NOT NULL,
                    urgency TEXT NOT NULL,
                    expected_slippage REAL NOT NULL,
                    expected_price REAL NOT NULL,
                    num_orders INTEGER NOT NULL,
                    market_condition TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    metadata TEXT
                );

                CREATE TABLE IF NOT EXISTS execution_results (
                    plan_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    total_size REAL NOT NULL,
                    filled_size REAL NOT NULL,
                    avg_fill_price REAL NOT NULL,
                    expected_price REAL NOT NULL,
                    slippage REAL NOT NULL,
                    num_fills INTEGER NOT NULL,
                    total_fees REAL NOT NULL,
                    execution_time_seconds REAL NOT NULL,
                    success INTEGER NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS market_analysis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    condition TEXT NOT NULL,
                    spread_bps REAL NOT NULL,
                    depth_ratio REAL NOT NULL,
                    volatility REAL NOT NULL,
                    momentum REAL NOT NULL,
                    volume_profile TEXT NOT NULL,
                    best_strategy TEXT NOT NULL,
                    analyzed_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_plans_symbol ON execution_plans(symbol);
                CREATE INDEX IF NOT EXISTS idx_results_symbol ON execution_results(symbol);
            """)

    def update_market_data(
        self,
        symbol: str,
        price: float,
        volume_24h: float,
        volatility: float,
        bid_depth: float,
        ask_depth: float,
        spread: float
    ):
        """Update market data for a symbol."""
        self.market_data[symbol] = {
            "price": price,
            "volume_24h": volume_24h,
            "volatility": volatility,
            "bid_depth": bid_depth,
            "ask_depth": ask_depth,
            "spread": spread,
            "updated_at": datetime.now()
        }

    def update_order_book(
        self,
        symbol: str,
        bids: List[Tuple[float, float]],  # (price, size)
        asks: List[Tuple[float, float]]
    ):
        """Update order book data."""
        self.order_books[symbol] = {
            "bids": bids,
            "asks": asks,
            "updated_at": datetime.now()
        }

    def analyze_market(self, symbol: str) -> Optional[MarketAnalysis]:
        """Analyze current market conditions."""
        data = self.market_data.get(symbol)
        if not data:
            return None

        # Calculate metrics
        spread_bps = data["spread"] / data["price"] * 10000
        depth_ratio = data["bid_depth"] / data["ask_depth"] if data["ask_depth"] > 0 else 1
        volatility = data["volatility"]

        # Determine momentum from depth imbalance
        if depth_ratio > 1.5:
            momentum = 0.5  # Bullish
        elif depth_ratio < 0.67:
            momentum = -0.5  # Bearish
        else:
            momentum = 0

        # Determine volume profile
        # Would need historical comparison
        volume_profile = "normal"

        # Determine market condition
        if volatility > 0.1:  # 10% daily volatility
            condition = MarketCondition.VOLATILE
        elif spread_bps > 50:  # > 0.5% spread
            condition = MarketCondition.LOW_LIQUIDITY
        elif momentum > 0.3:
            condition = MarketCondition.TRENDING_UP
        elif momentum < -0.3:
            condition = MarketCondition.TRENDING_DOWN
        else:
            condition = MarketCondition.RANGING

        # Get best strategy
        best_strategy = ExecutionStrategy.VWAP  # Default

        analysis = MarketAnalysis(
            symbol=symbol,
            condition=condition,
            spread_bps=spread_bps,
            depth_ratio=depth_ratio,
            volatility=volatility,
            momentum=momentum,
            volume_profile=volume_profile,
            best_strategy=best_strategy,
            analyzed_at=datetime.now()
        )

        # Save to database
        with self._get_db() as conn:
            conn.execute("""
                INSERT INTO market_analysis
                (symbol, condition, spread_bps, depth_ratio, volatility,
                 momentum, volume_profile, best_strategy, analyzed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                symbol, condition.value, spread_bps, depth_ratio, volatility,
                momentum, volume_profile, best_strategy.value,
                analysis.analyzed_at.isoformat()
            ))

        return analysis

    def create_execution_plan(
        self,
        symbol: str,
        side: str,
        size: float,
        urgency: UrgencyLevel = UrgencyLevel.MEDIUM,
        strategy: Optional[ExecutionStrategy] = None
    ) -> ExecutionPlan:
        """Create an optimized execution plan."""
        import json
        import uuid

        # Analyze market
        analysis = self.analyze_market(symbol)
        condition = analysis.condition if analysis else MarketCondition.RANGING

        # Get market data
        data = self.market_data.get(symbol, {})
        current_price = data.get("price", 0)
        volatility = data.get("volatility", 0.05)

        # Determine strategy
        if strategy is None:
            strategy_map = self.STRATEGY_MATRIX.get(condition, {})
            strategy = strategy_map.get(side, ExecutionStrategy.VWAP)

            # Override based on urgency
            if urgency == UrgencyLevel.IMMEDIATE:
                strategy = ExecutionStrategy.MARKET
            elif urgency == UrgencyLevel.HIGH and strategy == ExecutionStrategy.LIMIT:
                strategy = ExecutionStrategy.TWAP

        # Calculate execution parameters
        if strategy == ExecutionStrategy.MARKET:
            num_orders = 1
            order_sizes = [size]
            time_intervals = [0]
            limit_prices = [0]  # Market order
            duration = 0
        elif strategy == ExecutionStrategy.TWAP:
            # Split into 5-minute intervals
            duration = self._get_twap_duration(size, urgency)
            num_orders = max(3, duration // 300)  # At least 3 orders
            order_sizes = [size / num_orders] * num_orders
            time_intervals = [duration // num_orders] * num_orders
            limit_prices = [0] * num_orders
        elif strategy == ExecutionStrategy.VWAP:
            # Volume-weighted execution
            duration = self._get_vwap_duration(size, urgency)
            num_orders = max(5, duration // 180)
            order_sizes = self._calculate_vwap_sizes(size, num_orders)
            time_intervals = [duration // num_orders] * num_orders
            limit_prices = [0] * num_orders
        elif strategy == ExecutionStrategy.ICEBERG:
            # Hidden iceberg
            chunk_size = size / 10  # 10% visible
            num_orders = 10
            order_sizes = [chunk_size] * num_orders
            time_intervals = [30] * num_orders  # 30 seconds between
            limit_prices = [current_price] * num_orders
            duration = 300
        elif strategy == ExecutionStrategy.LIMIT:
            num_orders = 1
            order_sizes = [size]
            time_intervals = [0]
            # Slightly better than market
            offset = current_price * 0.001
            limit_prices = [current_price - offset if side == "buy" else current_price + offset]
            duration = 3600  # 1 hour limit
        else:
            # Default to TWAP
            num_orders = 5
            order_sizes = [size / 5] * 5
            time_intervals = [60] * 5
            limit_prices = [0] * 5
            duration = 300

        # Estimate slippage
        expected_slippage = self._estimate_slippage(symbol, side, size, strategy)
        expected_price = current_price * (1 + expected_slippage if side == "buy" else 1 - expected_slippage)

        # Calculate confidence
        confidence = self._calculate_confidence(analysis, strategy, size)

        now = datetime.now()
        plan = ExecutionPlan(
            plan_id=str(uuid.uuid4())[:12],
            symbol=symbol,
            side=side,
            total_size=size,
            strategy=strategy,
            urgency=urgency,
            expected_slippage=expected_slippage,
            expected_price=expected_price,
            num_orders=num_orders,
            order_sizes=order_sizes,
            time_intervals=time_intervals,
            limit_prices=limit_prices,
            estimated_duration_seconds=duration,
            market_condition=condition,
            confidence=confidence,
            created_at=now,
            expires_at=now + timedelta(minutes=5)
        )

        # Save plan
        with self._lock:
            self.active_plans[plan.plan_id] = plan

        with self._get_db() as conn:
            conn.execute("""
                INSERT INTO execution_plans
                (plan_id, symbol, side, total_size, strategy, urgency,
                 expected_slippage, expected_price, num_orders,
                 market_condition, confidence, created_at, expires_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                plan.plan_id, symbol, side, size, strategy.value,
                urgency.value, expected_slippage, expected_price,
                num_orders, condition.value, confidence,
                now.isoformat(), plan.expires_at.isoformat(),
                json.dumps(plan.metadata)
            ))

        return plan

    def _get_twap_duration(self, size: float, urgency: UrgencyLevel) -> int:
        """Get TWAP duration based on size and urgency."""
        base_duration = {
            UrgencyLevel.LOW: 3600,      # 1 hour
            UrgencyLevel.MEDIUM: 1800,   # 30 min
            UrgencyLevel.HIGH: 600,      # 10 min
            UrgencyLevel.IMMEDIATE: 60   # 1 min
        }
        return base_duration.get(urgency, 1800)

    def _get_vwap_duration(self, size: float, urgency: UrgencyLevel) -> int:
        """Get VWAP duration."""
        return self._get_twap_duration(size, urgency)

    def _calculate_vwap_sizes(self, total_size: float, num_orders: int) -> List[float]:
        """Calculate VWAP order sizes (larger at high volume times)."""
        # Simple bell curve distribution
        import math
        sizes = []
        for i in range(num_orders):
            # Higher in middle
            weight = 1 + 0.5 * math.sin(math.pi * i / (num_orders - 1))
            sizes.append(weight)

        # Normalize
        total_weight = sum(sizes)
        return [total_size * s / total_weight for s in sizes]

    def _estimate_slippage(
        self,
        symbol: str,
        side: str,
        size: float,
        strategy: ExecutionStrategy
    ) -> float:
        """Estimate slippage for execution."""
        data = self.market_data.get(symbol, {})
        spread = data.get("spread", 0) / data.get("price", 1) if data.get("price") else 0.001
        depth = data.get("bid_depth", 10000) if side == "sell" else data.get("ask_depth", 10000)

        # Base slippage from spread
        base_slippage = spread / 2

        # Size impact
        size_impact = (size / depth) * 0.5 if depth > 0 else 0.01

        # Strategy modifier
        strategy_modifier = {
            ExecutionStrategy.MARKET: 1.5,
            ExecutionStrategy.LIMIT: 0.1,
            ExecutionStrategy.TWAP: 0.7,
            ExecutionStrategy.VWAP: 0.6,
            ExecutionStrategy.ICEBERG: 0.5,
            ExecutionStrategy.SNIPER: 0.3,
            ExecutionStrategy.MOMENTUM: 1.2,
            ExecutionStrategy.MEAN_REVERT: 0.8
        }

        modifier = strategy_modifier.get(strategy, 1.0)

        return (base_slippage + size_impact) * modifier

    def _calculate_confidence(
        self,
        analysis: Optional[MarketAnalysis],
        strategy: ExecutionStrategy,
        size: float
    ) -> float:
        """Calculate confidence in the execution plan."""
        if not analysis:
            return 0.5

        # Base confidence
        confidence = 0.7

        # Adjust based on strategy suitability
        best = self.STRATEGY_MATRIX.get(analysis.condition, {})
        if strategy in best.values():
            confidence += 0.15

        # Adjust for volatility
        if analysis.volatility > 0.1:
            confidence -= 0.1

        # Adjust for liquidity
        if analysis.condition == MarketCondition.LOW_LIQUIDITY:
            confidence -= 0.15

        return max(0.1, min(0.95, confidence))

    def record_result(
        self,
        plan_id: str,
        filled_size: float,
        avg_fill_price: float,
        num_fills: int,
        total_fees: float,
        execution_time: float,
        success: bool
    ) -> ExecutionResult:
        """Record execution result."""
        plan = self.active_plans.get(plan_id)
        if not plan:
            raise ValueError(f"Plan not found: {plan_id}")

        slippage = (avg_fill_price - plan.expected_price) / plan.expected_price
        if plan.side == "sell":
            slippage = -slippage

        now = datetime.now()
        result = ExecutionResult(
            plan_id=plan_id,
            symbol=plan.symbol,
            side=plan.side,
            total_size=plan.total_size,
            filled_size=filled_size,
            avg_fill_price=avg_fill_price,
            expected_price=plan.expected_price,
            slippage=slippage,
            num_fills=num_fills,
            total_fees=total_fees,
            execution_time_seconds=execution_time,
            success=success,
            started_at=plan.created_at,
            completed_at=now
        )

        # Save result
        with self._get_db() as conn:
            conn.execute("""
                INSERT INTO execution_results
                (plan_id, symbol, side, total_size, filled_size, avg_fill_price,
                 expected_price, slippage, num_fills, total_fees,
                 execution_time_seconds, success, started_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                plan_id, result.symbol, result.side, result.total_size,
                filled_size, avg_fill_price, result.expected_price,
                slippage, num_fills, total_fees, execution_time,
                1 if success else 0, result.started_at.isoformat(),
                now.isoformat()
            ))

        # Remove from active plans
        self.active_plans.pop(plan_id, None)

        return result

    def get_execution_stats(self, symbol: Optional[str] = None) -> Dict:
        """Get execution statistics."""
        with self._get_db() as conn:
            if symbol:
                rows = conn.execute("""
                    SELECT * FROM execution_results WHERE symbol = ?
                """, (symbol,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM execution_results").fetchall()

            if not rows:
                return {}

            total = len(rows)
            successful = sum(1 for r in rows if r["success"])
            avg_slippage = sum(r["slippage"] for r in rows) / total
            total_fees = sum(r["total_fees"] for r in rows)
            avg_time = sum(r["execution_time_seconds"] for r in rows) / total

            return {
                "total_executions": total,
                "success_rate": successful / total,
                "avg_slippage": avg_slippage,
                "total_fees": total_fees,
                "avg_execution_time": avg_time
            }


# Singleton instance
_execution_optimizer: Optional[ExecutionOptimizer] = None


def get_execution_optimizer() -> ExecutionOptimizer:
    """Get or create the execution optimizer singleton."""
    global _execution_optimizer
    if _execution_optimizer is None:
        _execution_optimizer = ExecutionOptimizer()
    return _execution_optimizer
