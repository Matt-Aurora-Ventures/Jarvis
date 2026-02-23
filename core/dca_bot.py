"""
DCA Bot - Dollar Cost Averaging automation.
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


class DCAFrequency(Enum):
    """DCA frequency options."""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"


class DCAStatus(Enum):
    """DCA plan status."""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DCACondition(Enum):
    """Conditional DCA execution."""
    ALWAYS = "always"  # Execute regardless of price
    DIP_ONLY = "dip_only"  # Only execute if price is below average
    ABOVE_MA = "above_ma"  # Only if above moving average
    BELOW_MA = "below_ma"  # Only if below moving average
    RSI_OVERSOLD = "rsi_oversold"  # Only if RSI < 30


@dataclass
class DCAConfig:
    """DCA plan configuration."""
    symbol: str
    amount_per_buy: float  # USD per purchase
    frequency: DCAFrequency
    total_budget: Optional[float] = None  # Total to invest
    num_buys: Optional[int] = None  # Number of purchases
    condition: DCACondition = DCACondition.ALWAYS
    condition_params: Dict[str, Any] = field(default_factory=dict)
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    min_price: Optional[float] = None  # Don't buy above this
    max_price: Optional[float] = None  # Don't buy below this
    wallet_address: str = ""


@dataclass
class DCAPurchase:
    """A single DCA purchase."""
    plan_id: str
    purchase_num: int
    symbol: str
    amount_usd: float
    price: float
    tokens_bought: float
    fee: float
    timestamp: str
    tx_signature: Optional[str] = None
    status: str = "completed"


@dataclass
class DCAPlan:
    """A DCA plan."""
    id: str
    config: DCAConfig
    status: DCAStatus
    created_at: str
    updated_at: str
    next_execution: Optional[str]
    total_invested: float = 0.0
    total_tokens: float = 0.0
    average_price: float = 0.0
    num_purchases: int = 0
    purchases: List[DCAPurchase] = field(default_factory=list)
    current_value: float = 0.0
    unrealized_pnl: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class DCADB:
    """SQLite storage for DCA data."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dca_plans (
                    id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    amount_per_buy REAL,
                    frequency TEXT,
                    total_budget REAL,
                    num_buys INTEGER,
                    condition TEXT,
                    condition_params_json TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    min_price REAL,
                    max_price REAL,
                    wallet_address TEXT,
                    status TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    next_execution TEXT,
                    total_invested REAL DEFAULT 0,
                    total_tokens REAL DEFAULT 0,
                    average_price REAL DEFAULT 0,
                    num_purchases INTEGER DEFAULT 0,
                    metadata_json TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dca_purchases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plan_id TEXT NOT NULL,
                    purchase_num INTEGER,
                    symbol TEXT,
                    amount_usd REAL,
                    price REAL,
                    tokens_bought REAL,
                    fee REAL,
                    timestamp TEXT,
                    tx_signature TEXT,
                    status TEXT,
                    FOREIGN KEY (plan_id) REFERENCES dca_plans(id)
                )
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_dca_symbol ON dca_plans(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_dca_status ON dca_plans(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_purchases_plan ON dca_purchases(plan_id)")

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


class DCABot:
    """
    Dollar Cost Averaging automation bot.

    Usage:
        bot = DCABot()

        # Create a DCA plan
        plan = await bot.create_plan(DCAConfig(
            symbol="SOL",
            amount_per_buy=100,  # $100 per purchase
            frequency=DCAFrequency.DAILY,
            total_budget=3000  # $3000 total
        ))

        # Start the bot
        await bot.start()

        # Check plan progress
        stats = bot.get_plan_stats(plan.id)
    """

    def __init__(self, db_path: Optional[Path] = None):
        db_path = db_path or Path(__file__).parent.parent / "data" / "dca.db"
        self.db = DCADB(db_path)
        self._plans: Dict[str, DCAPlan] = {}
        self._price_feeds: Dict[str, Callable] = {}
        self._execution_callback: Optional[Callable] = None
        self._indicator_callback: Optional[Callable] = None  # For MA, RSI
        self._running = False
        self._load_plans()

    def _load_plans(self):
        """Load active plans from database."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM dca_plans WHERE status = 'active'")

            for row in cursor.fetchall():
                plan = self._row_to_plan(row, conn)
                self._plans[plan.id] = plan

        logger.info(f"Loaded {len(self._plans)} active DCA plans")

    def _row_to_plan(self, row: sqlite3.Row, conn) -> DCAPlan:
        """Convert database row to DCAPlan."""
        config = DCAConfig(
            symbol=row['symbol'],
            amount_per_buy=row['amount_per_buy'],
            frequency=DCAFrequency(row['frequency']),
            total_budget=row['total_budget'],
            num_buys=row['num_buys'],
            condition=DCACondition(row['condition']) if row['condition'] else DCACondition.ALWAYS,
            condition_params=json.loads(row['condition_params_json']) if row['condition_params_json'] else {},
            start_time=row['start_time'],
            end_time=row['end_time'],
            min_price=row['min_price'],
            max_price=row['max_price'],
            wallet_address=row['wallet_address'] or ""
        )

        # Load purchases
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM dca_purchases WHERE plan_id = ? ORDER BY purchase_num
        """, (row['id'],))

        purchases = [
            DCAPurchase(
                plan_id=p['plan_id'],
                purchase_num=p['purchase_num'],
                symbol=p['symbol'],
                amount_usd=p['amount_usd'],
                price=p['price'],
                tokens_bought=p['tokens_bought'],
                fee=p['fee'],
                timestamp=p['timestamp'],
                tx_signature=p['tx_signature'],
                status=p['status']
            )
            for p in cursor.fetchall()
        ]

        return DCAPlan(
            id=row['id'],
            config=config,
            status=DCAStatus(row['status']),
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            next_execution=row['next_execution'],
            total_invested=row['total_invested'] or 0,
            total_tokens=row['total_tokens'] or 0,
            average_price=row['average_price'] or 0,
            num_purchases=row['num_purchases'] or 0,
            purchases=purchases,
            metadata=json.loads(row['metadata_json']) if row['metadata_json'] else {}
        )

    async def create_plan(self, config: DCAConfig) -> DCAPlan:
        """Create a new DCA plan."""
        plan_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc)

        # Calculate first execution time
        next_execution = self._calculate_next_execution(config.frequency, now)

        if config.start_time:
            start = datetime.fromisoformat(config.start_time.replace('Z', '+00:00'))
            if start > now:
                next_execution = start

        plan = DCAPlan(
            id=plan_id,
            config=config,
            status=DCAStatus.ACTIVE,
            created_at=now.isoformat(),
            updated_at=now.isoformat(),
            next_execution=next_execution.isoformat()
        )

        self._save_plan(plan)
        self._plans[plan_id] = plan

        logger.info(f"Created DCA plan {plan_id} for {config.symbol}: "
                   f"${config.amount_per_buy} {config.frequency.value}")

        return plan

    def _calculate_next_execution(
        self,
        frequency: DCAFrequency,
        from_time: datetime
    ) -> datetime:
        """Calculate next execution time."""
        if frequency == DCAFrequency.HOURLY:
            return from_time + timedelta(hours=1)
        elif frequency == DCAFrequency.DAILY:
            return from_time + timedelta(days=1)
        elif frequency == DCAFrequency.WEEKLY:
            return from_time + timedelta(weeks=1)
        elif frequency == DCAFrequency.BIWEEKLY:
            return from_time + timedelta(weeks=2)
        elif frequency == DCAFrequency.MONTHLY:
            return from_time + timedelta(days=30)
        return from_time + timedelta(days=1)

    def _save_plan(self, plan: DCAPlan):
        """Save plan to database."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO dca_plans
                (id, symbol, amount_per_buy, frequency, total_budget, num_buys,
                 condition, condition_params_json, start_time, end_time,
                 min_price, max_price, wallet_address, status, created_at,
                 updated_at, next_execution, total_invested, total_tokens,
                 average_price, num_purchases, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                plan.id, plan.config.symbol, plan.config.amount_per_buy,
                plan.config.frequency.value, plan.config.total_budget,
                plan.config.num_buys, plan.config.condition.value,
                json.dumps(plan.config.condition_params),
                plan.config.start_time, plan.config.end_time,
                plan.config.min_price, plan.config.max_price,
                plan.config.wallet_address, plan.status.value,
                plan.created_at, plan.updated_at, plan.next_execution,
                plan.total_invested, plan.total_tokens, plan.average_price,
                plan.num_purchases, json.dumps(plan.metadata)
            ))
            conn.commit()

    def _save_purchase(self, purchase: DCAPurchase):
        """Save purchase to database."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO dca_purchases
                (plan_id, purchase_num, symbol, amount_usd, price, tokens_bought,
                 fee, timestamp, tx_signature, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                purchase.plan_id, purchase.purchase_num, purchase.symbol,
                purchase.amount_usd, purchase.price, purchase.tokens_bought,
                purchase.fee, purchase.timestamp, purchase.tx_signature,
                purchase.status
            ))
            conn.commit()

    def set_price_feed(self, symbol: str, callback: Callable[[], float]):
        """Set price feed for a symbol."""
        self._price_feeds[symbol.upper()] = callback

    def set_execution_callback(self, callback: Callable):
        """Set callback for executing purchases."""
        self._execution_callback = callback

    def set_indicator_callback(self, callback: Callable):
        """Set callback for getting technical indicators."""
        self._indicator_callback = callback

    async def start(self, check_interval: float = 60):
        """Start the DCA bot."""
        self._running = True
        logger.info("Started DCA bot")

        while self._running:
            try:
                await self._check_executions()
                await asyncio.sleep(check_interval)
            except Exception as e:
                logger.error(f"Error in DCA bot: {e}")
                await asyncio.sleep(60)

    def stop(self):
        """Stop the DCA bot."""
        self._running = False
        logger.info("Stopped DCA bot")

    async def _check_executions(self):
        """Check and execute due DCA purchases."""
        now = datetime.now(timezone.utc)

        for plan_id, plan in list(self._plans.items()):
            if plan.status != DCAStatus.ACTIVE:
                continue

            if not plan.next_execution:
                continue

            next_exec = datetime.fromisoformat(plan.next_execution.replace('Z', '+00:00'))

            if now >= next_exec:
                await self._execute_purchase(plan)

    async def _execute_purchase(self, plan: DCAPlan):
        """Execute a DCA purchase."""
        # Check if plan should complete
        if self._should_complete(plan):
            plan.status = DCAStatus.COMPLETED
            plan.updated_at = datetime.now(timezone.utc).isoformat()
            self._save_plan(plan)
            logger.info(f"DCA plan {plan.id} completed")
            return

        # Get current price
        price_feed = self._price_feeds.get(plan.config.symbol)
        if not price_feed:
            logger.warning(f"No price feed for {plan.config.symbol}")
            return

        try:
            current_price = price_feed()
            if not current_price:
                logger.warning(f"Zero or None price for {plan.config.symbol}, skipping DCA cycle")
                self._schedule_next(plan)
                return
        except Exception as e:
            logger.error(f"Error getting price for {plan.config.symbol}: {e}")
            return

        # Check price limits
        if plan.config.min_price and current_price < plan.config.min_price:
            logger.info(f"Skipping DCA: price {current_price} below min {plan.config.min_price}")
            self._schedule_next(plan)
            return

        if plan.config.max_price and current_price > plan.config.max_price:
            logger.info(f"Skipping DCA: price {current_price} above max {plan.config.max_price}")
            self._schedule_next(plan)
            return

        # Check conditional execution
        if not await self._check_condition(plan, current_price):
            logger.info(f"DCA condition not met for {plan.config.symbol}")
            self._schedule_next(plan)
            return

        # Execute purchase
        amount = plan.config.amount_per_buy
        tokens = amount / current_price

        purchase = DCAPurchase(
            plan_id=plan.id,
            purchase_num=plan.num_purchases + 1,
            symbol=plan.config.symbol,
            amount_usd=amount,
            price=current_price,
            tokens_bought=tokens,
            fee=0,
            timestamp=datetime.now(timezone.utc).isoformat()
        )

        # Execute via callback if set
        if self._execution_callback:
            try:
                result = await self._execution_callback(
                    symbol=plan.config.symbol,
                    amount_usd=amount,
                    wallet=plan.config.wallet_address
                )

                if result.get('success'):
                    purchase.tx_signature = result.get('tx_signature')
                    purchase.fee = result.get('fee', 0)
                    purchase.tokens_bought = result.get('tokens', tokens)
                    purchase.price = result.get('price', current_price)
                else:
                    purchase.status = "failed"
                    logger.error(f"DCA purchase failed: {result.get('error')}")

            except Exception as e:
                purchase.status = "failed"
                logger.error(f"DCA execution error: {e}")

        # Update plan
        if purchase.status == "completed":
            plan.total_invested += purchase.amount_usd
            plan.total_tokens += purchase.tokens_bought
            plan.num_purchases += 1
            plan.average_price = plan.total_invested / plan.total_tokens if plan.total_tokens > 0 else 0
            plan.purchases.append(purchase)

        plan.updated_at = datetime.now(timezone.utc).isoformat()

        # Schedule next execution
        self._schedule_next(plan)

        # Save
        self._save_purchase(purchase)
        self._save_plan(plan)

        if purchase.status == "completed":
            logger.info(f"DCA purchase #{plan.num_purchases}: "
                       f"bought {purchase.tokens_bought:.6f} {plan.config.symbol} "
                       f"@ ${purchase.price:.2f}")

    def _should_complete(self, plan: DCAPlan) -> bool:
        """Check if plan should be marked complete."""
        # Check budget exhausted
        if plan.config.total_budget:
            if plan.total_invested >= plan.config.total_budget:
                return True

        # Check number of buys reached
        if plan.config.num_buys:
            if plan.num_purchases >= plan.config.num_buys:
                return True

        # Check end time
        if plan.config.end_time:
            end = datetime.fromisoformat(plan.config.end_time.replace('Z', '+00:00'))
            if datetime.now(timezone.utc) >= end:
                return True

        return False

    async def _check_condition(self, plan: DCAPlan, current_price: float) -> bool:
        """Check if DCA condition is met."""
        condition = plan.config.condition

        if condition == DCACondition.ALWAYS:
            return True

        if condition == DCACondition.DIP_ONLY:
            # Only buy if below average cost
            if plan.average_price > 0:
                return current_price < plan.average_price
            return True  # First buy always executes

        # For indicator-based conditions, use callback
        if not self._indicator_callback:
            return True

        try:
            indicators = await self._indicator_callback(plan.config.symbol)

            if condition == DCACondition.ABOVE_MA:
                ma_period = plan.config.condition_params.get('ma_period', 20)
                ma = indicators.get(f'ma_{ma_period}', current_price)
                return current_price > ma

            if condition == DCACondition.BELOW_MA:
                ma_period = plan.config.condition_params.get('ma_period', 20)
                ma = indicators.get(f'ma_{ma_period}', current_price)
                return current_price < ma

            if condition == DCACondition.RSI_OVERSOLD:
                rsi = indicators.get('rsi', 50)
                threshold = plan.config.condition_params.get('rsi_threshold', 30)
                return rsi < threshold

        except Exception as e:
            logger.error(f"Error checking condition: {e}")

        return True

    def _schedule_next(self, plan: DCAPlan):
        """Schedule next execution."""
        next_time = self._calculate_next_execution(
            plan.config.frequency,
            datetime.now(timezone.utc)
        )
        plan.next_execution = next_time.isoformat()

    async def pause_plan(self, plan_id: str) -> bool:
        """Pause a DCA plan."""
        plan = self._plans.get(plan_id)
        if not plan:
            return False

        plan.status = DCAStatus.PAUSED
        plan.updated_at = datetime.now(timezone.utc).isoformat()
        self._save_plan(plan)

        logger.info(f"Paused DCA plan {plan_id}")
        return True

    async def resume_plan(self, plan_id: str) -> bool:
        """Resume a paused plan."""
        plan = self._plans.get(plan_id)
        if not plan or plan.status != DCAStatus.PAUSED:
            return False

        plan.status = DCAStatus.ACTIVE
        plan.updated_at = datetime.now(timezone.utc).isoformat()
        self._schedule_next(plan)
        self._save_plan(plan)

        logger.info(f"Resumed DCA plan {plan_id}")
        return True

    async def cancel_plan(self, plan_id: str) -> bool:
        """Cancel a DCA plan."""
        plan = self._plans.get(plan_id)
        if not plan:
            return False

        plan.status = DCAStatus.CANCELLED
        plan.updated_at = datetime.now(timezone.utc).isoformat()
        self._save_plan(plan)

        logger.info(f"Cancelled DCA plan {plan_id}")
        return True

    def update_current_values(self):
        """Update current values and PnL for all plans."""
        for plan in self._plans.values():
            price_feed = self._price_feeds.get(plan.config.symbol)
            if price_feed:
                try:
                    current_price = price_feed()
                    plan.current_value = plan.total_tokens * current_price
                    plan.unrealized_pnl = plan.current_value - plan.total_invested
                except Exception:
                    pass

    def get_plan(self, plan_id: str) -> Optional[DCAPlan]:
        """Get a plan by ID."""
        return self._plans.get(plan_id)

    def get_active_plans(self, symbol: Optional[str] = None) -> List[DCAPlan]:
        """Get all active plans."""
        plans = [p for p in self._plans.values() if p.status == DCAStatus.ACTIVE]
        if symbol:
            plans = [p for p in plans if p.config.symbol == symbol.upper()]
        return plans

    def get_plan_stats(self, plan_id: str) -> Dict[str, Any]:
        """Get statistics for a plan."""
        plan = self._plans.get(plan_id)
        if not plan:
            return {}

        self.update_current_values()

        roi = 0
        if plan.total_invested > 0:
            roi = ((plan.current_value - plan.total_invested) / plan.total_invested) * 100

        return {
            'plan_id': plan_id,
            'symbol': plan.config.symbol,
            'status': plan.status.value,
            'frequency': plan.config.frequency.value,
            'amount_per_buy': plan.config.amount_per_buy,
            'num_purchases': plan.num_purchases,
            'total_invested': plan.total_invested,
            'total_tokens': plan.total_tokens,
            'average_price': plan.average_price,
            'current_value': plan.current_value,
            'unrealized_pnl': plan.unrealized_pnl,
            'roi_percent': roi,
            'next_execution': plan.next_execution,
            'budget_remaining': (plan.config.total_budget - plan.total_invested) if plan.config.total_budget else None,
            'buys_remaining': (plan.config.num_buys - plan.num_purchases) if plan.config.num_buys else None
        }

    def get_all_stats(self) -> Dict[str, Any]:
        """Get aggregate statistics."""
        self.update_current_values()

        total_invested = sum(p.total_invested for p in self._plans.values())
        total_value = sum(p.current_value for p in self._plans.values())
        total_pnl = total_value - total_invested

        by_symbol = {}
        for plan in self._plans.values():
            symbol = plan.config.symbol
            if symbol not in by_symbol:
                by_symbol[symbol] = {'invested': 0, 'value': 0, 'tokens': 0}
            by_symbol[symbol]['invested'] += plan.total_invested
            by_symbol[symbol]['value'] += plan.current_value
            by_symbol[symbol]['tokens'] += plan.total_tokens

        return {
            'active_plans': len([p for p in self._plans.values() if p.status == DCAStatus.ACTIVE]),
            'total_plans': len(self._plans),
            'total_invested': total_invested,
            'total_current_value': total_value,
            'total_pnl': total_pnl,
            'total_roi_percent': (total_pnl / total_invested * 100) if total_invested > 0 else 0,
            'by_symbol': by_symbol
        }

    def get_purchase_history(
        self,
        plan_id: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 100
    ) -> List[DCAPurchase]:
        """Get purchase history."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM dca_purchases WHERE 1=1"
            params = []

            if plan_id:
                query += " AND plan_id = ?"
                params.append(plan_id)

            if symbol:
                query += " AND symbol = ?"
                params.append(symbol.upper())

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)

            return [
                DCAPurchase(
                    plan_id=row['plan_id'],
                    purchase_num=row['purchase_num'],
                    symbol=row['symbol'],
                    amount_usd=row['amount_usd'],
                    price=row['price'],
                    tokens_bought=row['tokens_bought'],
                    fee=row['fee'],
                    timestamp=row['timestamp'],
                    tx_signature=row['tx_signature'],
                    status=row['status']
                )
                for row in cursor.fetchall()
            ]


# Singleton
_bot: Optional[DCABot] = None


def get_dca_bot() -> DCABot:
    """Get singleton DCA bot."""
    global _bot
    if _bot is None:
        _bot = DCABot()
    return _bot
