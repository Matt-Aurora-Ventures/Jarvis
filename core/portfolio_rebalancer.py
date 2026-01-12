"""
Portfolio Rebalancer - Automated portfolio rebalancing.
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

logger = logging.getLogger(__name__)


class RebalanceStrategy(Enum):
    """Rebalancing strategy."""
    THRESHOLD = "threshold"  # Rebalance when drift exceeds threshold
    CALENDAR = "calendar"  # Rebalance on schedule
    TACTICAL = "tactical"  # Based on signals/momentum
    HYBRID = "hybrid"  # Combination


class RebalanceStatus(Enum):
    """Rebalance operation status."""
    PENDING = "pending"
    CALCULATING = "calculating"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AllocationMethod(Enum):
    """Allocation methodology."""
    FIXED = "fixed"  # Fixed percentage allocations
    EQUAL_WEIGHT = "equal_weight"  # Equal weights
    MARKET_CAP = "market_cap"  # Market cap weighted
    RISK_PARITY = "risk_parity"  # Risk-weighted
    MOMENTUM = "momentum"  # Momentum-based


@dataclass
class TargetAllocation:
    """Target allocation for an asset."""
    symbol: str
    target_percent: float
    min_percent: float = 0.0
    max_percent: float = 100.0
    drift_threshold: float = 5.0  # Rebalance if drift > this %


@dataclass
class CurrentHolding:
    """Current holding information."""
    symbol: str
    quantity: float
    current_price: float
    current_value: float
    current_percent: float
    cost_basis: float = 0.0
    unrealized_pnl: float = 0.0


@dataclass
class RebalanceTrade:
    """A trade needed for rebalancing."""
    symbol: str
    side: str  # "buy" or "sell"
    quantity: float
    value: float
    current_percent: float
    target_percent: float
    drift: float
    priority: int = 0


@dataclass
class RebalanceResult:
    """Result of a rebalancing operation."""
    id: str
    timestamp: str
    portfolio_value_before: float
    portfolio_value_after: float
    trades_planned: int
    trades_executed: int
    total_traded_value: float
    fees_paid: float
    drift_before: float
    drift_after: float
    duration_seconds: float
    status: RebalanceStatus
    trades: List[RebalanceTrade] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class PortfolioConfig:
    """Portfolio configuration."""
    name: str
    target_allocations: List[TargetAllocation]
    strategy: RebalanceStrategy = RebalanceStrategy.THRESHOLD
    allocation_method: AllocationMethod = AllocationMethod.FIXED
    drift_threshold: float = 5.0  # Global threshold
    min_trade_value: float = 10.0  # Min trade size in USD
    max_single_trade_pct: float = 25.0  # Max % of portfolio in single trade
    rebalance_frequency_hours: int = 24
    tax_loss_harvesting: bool = False
    avoid_wash_sales: bool = True


class RebalancerDB:
    """SQLite storage for rebalancer data."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS portfolios (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    strategy TEXT,
                    allocation_method TEXT,
                    drift_threshold REAL,
                    min_trade_value REAL,
                    rebalance_frequency_hours INTEGER,
                    config_json TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS target_allocations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    portfolio_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    target_percent REAL,
                    min_percent REAL,
                    max_percent REAL,
                    drift_threshold REAL,
                    FOREIGN KEY (portfolio_id) REFERENCES portfolios(id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rebalance_history (
                    id TEXT PRIMARY KEY,
                    portfolio_id TEXT NOT NULL,
                    timestamp TEXT,
                    portfolio_value_before REAL,
                    portfolio_value_after REAL,
                    trades_planned INTEGER,
                    trades_executed INTEGER,
                    total_traded_value REAL,
                    fees_paid REAL,
                    drift_before REAL,
                    drift_after REAL,
                    duration_seconds REAL,
                    status TEXT,
                    trades_json TEXT,
                    errors_json TEXT,
                    FOREIGN KEY (portfolio_id) REFERENCES portfolios(id)
                )
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_alloc_portfolio ON target_allocations(portfolio_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_hist_portfolio ON rebalance_history(portfolio_id)")

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


class PortfolioRebalancer:
    """
    Automated portfolio rebalancing.

    Usage:
        rebalancer = PortfolioRebalancer()

        # Create portfolio
        config = PortfolioConfig(
            name="Main Portfolio",
            target_allocations=[
                TargetAllocation("SOL", 40),
                TargetAllocation("ETH", 30),
                TargetAllocation("BTC", 20),
                TargetAllocation("USDC", 10),
            ]
        )
        portfolio_id = await rebalancer.create_portfolio(config)

        # Check drift
        drift = await rebalancer.calculate_drift(portfolio_id)

        # Rebalance if needed
        result = await rebalancer.rebalance(portfolio_id)
    """

    def __init__(self, db_path: Optional[Path] = None):
        db_path = db_path or Path(__file__).parent.parent / "data" / "rebalancer.db"
        self.db = RebalancerDB(db_path)
        self._portfolios: Dict[str, PortfolioConfig] = {}
        self._price_feeds: Dict[str, Callable] = {}
        self._holdings_callback: Optional[Callable] = None
        self._execution_callback: Optional[Callable] = None
        self._load_portfolios()

    def _load_portfolios(self):
        """Load portfolios from database."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM portfolios")

            for row in cursor.fetchall():
                # Load allocations
                cursor.execute("""
                    SELECT * FROM target_allocations WHERE portfolio_id = ?
                """, (row['id'],))

                allocations = [
                    TargetAllocation(
                        symbol=a['symbol'],
                        target_percent=a['target_percent'],
                        min_percent=a['min_percent'],
                        max_percent=a['max_percent'],
                        drift_threshold=a['drift_threshold']
                    )
                    for a in cursor.fetchall()
                ]

                config_data = json.loads(row['config_json']) if row['config_json'] else {}

                config = PortfolioConfig(
                    name=row['name'],
                    target_allocations=allocations,
                    strategy=RebalanceStrategy(row['strategy']),
                    allocation_method=AllocationMethod(row['allocation_method']),
                    drift_threshold=row['drift_threshold'],
                    min_trade_value=row['min_trade_value'],
                    rebalance_frequency_hours=row['rebalance_frequency_hours'],
                    tax_loss_harvesting=config_data.get('tax_loss_harvesting', False),
                    avoid_wash_sales=config_data.get('avoid_wash_sales', True)
                )

                self._portfolios[row['id']] = config

        logger.info(f"Loaded {len(self._portfolios)} portfolios")

    async def create_portfolio(self, config: PortfolioConfig) -> str:
        """Create a new portfolio configuration."""
        portfolio_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc).isoformat()

        # Validate allocations sum to 100%
        total = sum(a.target_percent for a in config.target_allocations)
        if abs(total - 100) > 0.01:
            raise ValueError(f"Target allocations must sum to 100%, got {total}%")

        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO portfolios
                (id, name, strategy, allocation_method, drift_threshold,
                 min_trade_value, rebalance_frequency_hours, config_json,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                portfolio_id, config.name, config.strategy.value,
                config.allocation_method.value, config.drift_threshold,
                config.min_trade_value, config.rebalance_frequency_hours,
                json.dumps({
                    'tax_loss_harvesting': config.tax_loss_harvesting,
                    'avoid_wash_sales': config.avoid_wash_sales,
                    'max_single_trade_pct': config.max_single_trade_pct
                }),
                now, now
            ))

            for alloc in config.target_allocations:
                cursor.execute("""
                    INSERT INTO target_allocations
                    (portfolio_id, symbol, target_percent, min_percent,
                     max_percent, drift_threshold)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    portfolio_id, alloc.symbol, alloc.target_percent,
                    alloc.min_percent, alloc.max_percent, alloc.drift_threshold
                ))

            conn.commit()

        self._portfolios[portfolio_id] = config

        logger.info(f"Created portfolio {portfolio_id}: {config.name}")
        return portfolio_id

    def set_price_feed(self, symbol: str, callback: Callable[[], float]):
        """Set price feed for a symbol."""
        self._price_feeds[symbol.upper()] = callback

    def set_holdings_callback(self, callback: Callable[[], Dict[str, float]]):
        """Set callback to get current holdings {symbol: quantity}."""
        self._holdings_callback = callback

    def set_execution_callback(self, callback: Callable):
        """Set callback for executing trades."""
        self._execution_callback = callback

    async def get_current_holdings(self, portfolio_id: str) -> List[CurrentHolding]:
        """Get current portfolio holdings."""
        config = self._portfolios.get(portfolio_id)
        if not config:
            raise ValueError(f"Portfolio {portfolio_id} not found")

        if not self._holdings_callback:
            raise ValueError("Holdings callback not set")

        # Get quantities from callback
        quantities = await asyncio.to_thread(self._holdings_callback)
        holdings = []
        total_value = 0

        # Get prices and calculate values
        for alloc in config.target_allocations:
            symbol = alloc.symbol
            quantity = quantities.get(symbol, 0)

            price_feed = self._price_feeds.get(symbol)
            if price_feed:
                try:
                    price = price_feed()
                except Exception:
                    price = 0
            else:
                price = 0

            value = quantity * price
            total_value += value

            holdings.append(CurrentHolding(
                symbol=symbol,
                quantity=quantity,
                current_price=price,
                current_value=value,
                current_percent=0  # Will update after total calculated
            ))

        # Update percentages
        for holding in holdings:
            holding.current_percent = (holding.current_value / total_value * 100) if total_value > 0 else 0

        return holdings

    async def calculate_drift(self, portfolio_id: str) -> Dict[str, Any]:
        """Calculate current portfolio drift from targets."""
        config = self._portfolios.get(portfolio_id)
        if not config:
            raise ValueError(f"Portfolio {portfolio_id} not found")

        holdings = await self.get_current_holdings(portfolio_id)
        holdings_dict = {h.symbol: h for h in holdings}
        total_value = sum(h.current_value for h in holdings)

        drifts = []
        max_drift = 0
        total_drift = 0

        for alloc in config.target_allocations:
            holding = holdings_dict.get(alloc.symbol)
            current_pct = holding.current_percent if holding else 0
            drift = current_pct - alloc.target_percent

            drifts.append({
                'symbol': alloc.symbol,
                'target_percent': alloc.target_percent,
                'current_percent': current_pct,
                'drift': drift,
                'drift_exceeded': abs(drift) > alloc.drift_threshold
            })

            max_drift = max(max_drift, abs(drift))
            total_drift += abs(drift)

        needs_rebalance = max_drift > config.drift_threshold

        return {
            'portfolio_id': portfolio_id,
            'total_value': total_value,
            'drifts': drifts,
            'max_drift': max_drift,
            'average_drift': total_drift / len(drifts) if drifts else 0,
            'needs_rebalance': needs_rebalance
        }

    async def calculate_trades(self, portfolio_id: str) -> List[RebalanceTrade]:
        """Calculate trades needed to rebalance."""
        config = self._portfolios.get(portfolio_id)
        if not config:
            raise ValueError(f"Portfolio {portfolio_id} not found")

        holdings = await self.get_current_holdings(portfolio_id)
        holdings_dict = {h.symbol: h for h in holdings}
        total_value = sum(h.current_value for h in holdings)

        trades = []

        for alloc in config.target_allocations:
            holding = holdings_dict.get(alloc.symbol)
            current_value = holding.current_value if holding else 0
            current_pct = holding.current_percent if holding else 0
            current_price = holding.current_price if holding else 0

            target_value = total_value * (alloc.target_percent / 100)
            value_diff = target_value - current_value
            drift = current_pct - alloc.target_percent

            # Skip if within threshold and below min trade
            if abs(drift) < alloc.drift_threshold:
                continue
            if abs(value_diff) < config.min_trade_value:
                continue

            # Enforce max single trade percentage
            max_trade_value = total_value * (config.max_single_trade_pct / 100)
            value_diff = max(-max_trade_value, min(max_trade_value, value_diff))

            side = "buy" if value_diff > 0 else "sell"
            quantity = abs(value_diff) / current_price if current_price > 0 else 0

            trades.append(RebalanceTrade(
                symbol=alloc.symbol,
                side=side,
                quantity=quantity,
                value=abs(value_diff),
                current_percent=current_pct,
                target_percent=alloc.target_percent,
                drift=drift,
                priority=int(abs(drift) * 10)  # Higher drift = higher priority
            ))

        # Sort by priority (highest drift first)
        trades.sort(key=lambda t: t.priority, reverse=True)

        return trades

    async def rebalance(
        self,
        portfolio_id: str,
        dry_run: bool = False
    ) -> RebalanceResult:
        """Execute portfolio rebalancing."""
        result_id = str(uuid.uuid4())[:8]
        start_time = datetime.now(timezone.utc)

        config = self._portfolios.get(portfolio_id)
        if not config:
            raise ValueError(f"Portfolio {portfolio_id} not found")

        result = RebalanceResult(
            id=result_id,
            timestamp=start_time.isoformat(),
            portfolio_value_before=0,
            portfolio_value_after=0,
            trades_planned=0,
            trades_executed=0,
            total_traded_value=0,
            fees_paid=0,
            drift_before=0,
            drift_after=0,
            duration_seconds=0,
            status=RebalanceStatus.CALCULATING
        )

        try:
            # Calculate current state
            drift_info = await self.calculate_drift(portfolio_id)
            result.portfolio_value_before = drift_info['total_value']
            result.drift_before = drift_info['max_drift']

            if not drift_info['needs_rebalance'] and not dry_run:
                result.status = RebalanceStatus.COMPLETED
                result.duration_seconds = (datetime.now(timezone.utc) - start_time).total_seconds()
                logger.info(f"Portfolio {portfolio_id} does not need rebalancing")
                return result

            # Calculate trades
            trades = await self.calculate_trades(portfolio_id)
            result.trades = trades
            result.trades_planned = len(trades)

            if dry_run:
                result.status = RebalanceStatus.COMPLETED
                result.duration_seconds = (datetime.now(timezone.utc) - start_time).total_seconds()
                logger.info(f"Dry run: {len(trades)} trades would be executed")
                return result

            # Execute trades
            result.status = RebalanceStatus.EXECUTING
            total_fees = 0
            total_value = 0

            for trade in trades:
                try:
                    if self._execution_callback:
                        exec_result = await self._execution_callback(
                            symbol=trade.symbol,
                            side=trade.side,
                            quantity=trade.quantity,
                            value=trade.value
                        )

                        if exec_result.get('success'):
                            result.trades_executed += 1
                            total_value += exec_result.get('value', trade.value)
                            total_fees += exec_result.get('fee', 0)
                        else:
                            result.errors.append(f"{trade.symbol}: {exec_result.get('error')}")
                    else:
                        # Simulated execution
                        result.trades_executed += 1
                        total_value += trade.value

                except Exception as e:
                    result.errors.append(f"{trade.symbol}: {str(e)}")
                    logger.error(f"Error executing trade for {trade.symbol}: {e}")

            result.total_traded_value = total_value
            result.fees_paid = total_fees

            # Calculate final state
            final_drift = await self.calculate_drift(portfolio_id)
            result.portfolio_value_after = final_drift['total_value']
            result.drift_after = final_drift['max_drift']

            result.status = RebalanceStatus.COMPLETED

        except Exception as e:
            result.status = RebalanceStatus.FAILED
            result.errors.append(str(e))
            logger.error(f"Rebalancing failed: {e}")

        result.duration_seconds = (datetime.now(timezone.utc) - start_time).total_seconds()

        # Save result
        self._save_result(portfolio_id, result)

        logger.info(f"Rebalancing complete: {result.trades_executed}/{result.trades_planned} trades, "
                   f"drift {result.drift_before:.1f}% -> {result.drift_after:.1f}%")

        return result

    def _save_result(self, portfolio_id: str, result: RebalanceResult):
        """Save rebalancing result to database."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO rebalance_history
                (id, portfolio_id, timestamp, portfolio_value_before, portfolio_value_after,
                 trades_planned, trades_executed, total_traded_value, fees_paid,
                 drift_before, drift_after, duration_seconds, status, trades_json, errors_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.id, portfolio_id, result.timestamp,
                result.portfolio_value_before, result.portfolio_value_after,
                result.trades_planned, result.trades_executed,
                result.total_traded_value, result.fees_paid,
                result.drift_before, result.drift_after,
                result.duration_seconds, result.status.value,
                json.dumps([{
                    'symbol': t.symbol,
                    'side': t.side,
                    'quantity': t.quantity,
                    'value': t.value,
                    'drift': t.drift
                } for t in result.trades]),
                json.dumps(result.errors)
            ))
            conn.commit()

    def get_portfolio(self, portfolio_id: str) -> Optional[PortfolioConfig]:
        """Get portfolio configuration."""
        return self._portfolios.get(portfolio_id)

    def get_portfolios(self) -> List[Dict[str, Any]]:
        """Get all portfolios."""
        return [
            {
                'id': pid,
                'name': config.name,
                'strategy': config.strategy.value,
                'num_assets': len(config.target_allocations),
                'drift_threshold': config.drift_threshold
            }
            for pid, config in self._portfolios.items()
        ]

    def get_rebalance_history(
        self,
        portfolio_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get rebalancing history."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM rebalance_history
                WHERE portfolio_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (portfolio_id, limit))

            return [
                {
                    'id': row['id'],
                    'timestamp': row['timestamp'],
                    'portfolio_value_before': row['portfolio_value_before'],
                    'portfolio_value_after': row['portfolio_value_after'],
                    'trades_executed': row['trades_executed'],
                    'total_traded_value': row['total_traded_value'],
                    'drift_before': row['drift_before'],
                    'drift_after': row['drift_after'],
                    'status': row['status']
                }
                for row in cursor.fetchall()
            ]

    async def update_allocations(
        self,
        portfolio_id: str,
        allocations: List[TargetAllocation]
    ):
        """Update target allocations for a portfolio."""
        if portfolio_id not in self._portfolios:
            raise ValueError(f"Portfolio {portfolio_id} not found")

        # Validate
        total = sum(a.target_percent for a in allocations)
        if abs(total - 100) > 0.01:
            raise ValueError(f"Target allocations must sum to 100%, got {total}%")

        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            # Delete old allocations
            cursor.execute("DELETE FROM target_allocations WHERE portfolio_id = ?", (portfolio_id,))

            # Insert new allocations
            for alloc in allocations:
                cursor.execute("""
                    INSERT INTO target_allocations
                    (portfolio_id, symbol, target_percent, min_percent,
                     max_percent, drift_threshold)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    portfolio_id, alloc.symbol, alloc.target_percent,
                    alloc.min_percent, alloc.max_percent, alloc.drift_threshold
                ))

            cursor.execute("""
                UPDATE portfolios SET updated_at = ? WHERE id = ?
            """, (datetime.now(timezone.utc).isoformat(), portfolio_id))

            conn.commit()

        self._portfolios[portfolio_id].target_allocations = allocations

        logger.info(f"Updated allocations for portfolio {portfolio_id}")


# Singleton
_rebalancer: Optional[PortfolioRebalancer] = None


def get_portfolio_rebalancer() -> PortfolioRebalancer:
    """Get singleton portfolio rebalancer."""
    global _rebalancer
    if _rebalancer is None:
        _rebalancer = PortfolioRebalancer()
    return _rebalancer
