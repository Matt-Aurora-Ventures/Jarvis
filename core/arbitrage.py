"""
Arbitrage Scanner - Cross-DEX arbitrage detection and execution.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import json
import sqlite3
from pathlib import Path
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class ArbitrageType(Enum):
    """Types of arbitrage."""
    CROSS_DEX = "cross_dex"  # Same token, different DEXs
    TRIANGULAR = "triangular"  # A->B->C->A
    STATISTICAL = "statistical"  # Mean reversion based
    FLASH_LOAN = "flash_loan"  # Using flash loans


class ArbitrageStatus(Enum):
    """Arbitrage opportunity status."""
    DETECTED = "detected"
    VALIDATING = "validating"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class DEXPrice:
    """Price on a specific DEX."""
    dex: str
    price: float
    liquidity: float
    timestamp: str
    slippage_1k: float = 0.0  # Slippage for $1000 trade
    slippage_10k: float = 0.0  # Slippage for $10000 trade


@dataclass
class ArbitrageOpportunity:
    """An arbitrage opportunity."""
    id: str
    arb_type: ArbitrageType
    symbol: str
    buy_dex: str
    sell_dex: str
    buy_price: float
    sell_price: float
    spread: float
    spread_bps: float
    profit_estimate: float
    profit_after_fees: float
    max_size: float
    detected_at: str
    expires_at: str
    status: ArbitrageStatus = ArbitrageStatus.DETECTED
    executed_at: Optional[str] = None
    actual_profit: float = 0.0
    path: List[str] = field(default_factory=list)  # For triangular
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TriangularPath:
    """A triangular arbitrage path."""
    tokens: List[str]  # e.g., ["SOL", "USDC", "RAY", "SOL"]
    dexes: List[str]  # DEX for each hop
    prices: List[float]
    total_return: float  # > 1.0 means profit
    profit_bps: float
    max_size: float
    bottleneck: str  # Which pair has lowest liquidity


@dataclass
class ArbitrageConfig:
    """Arbitrage scanner configuration."""
    min_spread_bps: float = 30  # Minimum spread in basis points
    min_profit_usd: float = 1.0  # Minimum profit after fees
    max_trade_size: float = 10000  # Maximum trade size in USD
    execution_timeout: float = 30  # Seconds before opportunity expires
    gas_estimate: float = 0.001  # Estimated gas in SOL
    fee_bps: float = 30  # Exchange fees in bps
    slippage_tolerance: float = 0.5  # Max slippage %


class ArbitrageDB:
    """SQLite storage for arbitrage data."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS arbitrage_opportunities (
                    id TEXT PRIMARY KEY,
                    arb_type TEXT,
                    symbol TEXT,
                    buy_dex TEXT,
                    sell_dex TEXT,
                    buy_price REAL,
                    sell_price REAL,
                    spread REAL,
                    spread_bps REAL,
                    profit_estimate REAL,
                    profit_after_fees REAL,
                    max_size REAL,
                    detected_at TEXT,
                    expires_at TEXT,
                    status TEXT,
                    executed_at TEXT,
                    actual_profit REAL,
                    path_json TEXT,
                    metadata_json TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dex_prices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    dex TEXT NOT NULL,
                    price REAL,
                    liquidity REAL,
                    slippage_1k REAL,
                    slippage_10k REAL,
                    timestamp TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS arbitrage_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    opportunities_found INTEGER DEFAULT 0,
                    opportunities_executed INTEGER DEFAULT 0,
                    total_profit REAL DEFAULT 0,
                    avg_spread_bps REAL DEFAULT 0,
                    best_dex_pair TEXT
                )
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_arb_symbol ON arbitrage_opportunities(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_arb_status ON arbitrage_opportunities(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_prices_symbol ON dex_prices(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_prices_time ON dex_prices(timestamp)")

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


class ArbitrageScanner:
    """
    Scan for and execute arbitrage opportunities.

    Usage:
        scanner = ArbitrageScanner()

        # Set price feeds
        scanner.add_price_feed("SOL", "jupiter", get_jupiter_price)
        scanner.add_price_feed("SOL", "raydium", get_raydium_price)

        # Start scanning
        await scanner.start_scanning()

        # Or manually scan
        opportunities = await scanner.scan_cross_dex("SOL")
    """

    # Known DEXs on Solana
    DEXES = ["jupiter", "raydium", "orca", "phoenix", "lifinity", "openbook"]

    def __init__(
        self,
        db_path: Optional[Path] = None,
        config: ArbitrageConfig = None
    ):
        db_path = db_path or Path(__file__).parent.parent / "data" / "arbitrage.db"
        self.db = ArbitrageDB(db_path)
        self.config = config or ArbitrageConfig()

        self._price_feeds: Dict[str, Dict[str, Callable]] = {}  # symbol -> dex -> callback
        self._prices: Dict[str, Dict[str, DEXPrice]] = {}  # Cached prices
        self._execution_callback: Optional[Callable] = None
        self._scanning = False
        self._opportunity_counter = 0

    def add_price_feed(
        self,
        symbol: str,
        dex: str,
        callback: Callable[[], Tuple[float, float]]  # Returns (price, liquidity)
    ):
        """Add a price feed for a symbol on a DEX."""
        symbol = symbol.upper()
        if symbol not in self._price_feeds:
            self._price_feeds[symbol] = {}
        self._price_feeds[symbol][dex] = callback
        logger.info(f"Added price feed: {symbol} on {dex}")

    def set_execution_callback(self, callback: Callable):
        """Set callback for executing arbitrage."""
        self._execution_callback = callback

    async def fetch_prices(self, symbol: str) -> Dict[str, DEXPrice]:
        """Fetch prices from all DEXs for a symbol."""
        symbol = symbol.upper()
        feeds = self._price_feeds.get(symbol, {})

        if not feeds:
            return {}

        prices = {}
        timestamp = datetime.now(timezone.utc).isoformat()

        for dex, callback in feeds.items():
            try:
                price, liquidity = await asyncio.to_thread(callback)
                prices[dex] = DEXPrice(
                    dex=dex,
                    price=price,
                    liquidity=liquidity,
                    timestamp=timestamp
                )

                # Save to database
                self._save_price(symbol, prices[dex])

            except Exception as e:
                logger.error(f"Error fetching {symbol} price from {dex}: {e}")

        self._prices[symbol] = prices
        return prices

    def _save_price(self, symbol: str, price: DEXPrice):
        """Save price to database."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO dex_prices
                (symbol, dex, price, liquidity, slippage_1k, slippage_10k, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                symbol, price.dex, price.price, price.liquidity,
                price.slippage_1k, price.slippage_10k, price.timestamp
            ))
            conn.commit()

    async def scan_cross_dex(self, symbol: str) -> List[ArbitrageOpportunity]:
        """Scan for cross-DEX arbitrage opportunities."""
        prices = await self.fetch_prices(symbol)

        if len(prices) < 2:
            return []

        opportunities = []
        dexes = list(prices.keys())
        timestamp = datetime.now(timezone.utc)
        expires = timestamp + timedelta(seconds=self.config.execution_timeout)

        # Compare all pairs
        for i, dex1 in enumerate(dexes):
            for dex2 in dexes[i + 1:]:
                p1 = prices[dex1]
                p2 = prices[dex2]

                # Determine buy/sell direction
                if p1.price < p2.price:
                    buy_dex, sell_dex = dex1, dex2
                    buy_price, sell_price = p1.price, p2.price
                    buy_liquidity = p1.liquidity
                else:
                    buy_dex, sell_dex = dex2, dex1
                    buy_price, sell_price = p2.price, p1.price
                    buy_liquidity = p2.liquidity

                spread = sell_price - buy_price
                spread_bps = (spread / buy_price) * 10000

                if spread_bps < self.config.min_spread_bps:
                    continue

                # Calculate max size based on liquidity
                max_size = min(
                    buy_liquidity * 0.1,  # Don't use more than 10% of liquidity
                    self.config.max_trade_size
                )

                # Estimate profit
                gross_profit = (spread / buy_price) * max_size
                fees = (self.config.fee_bps / 10000) * max_size * 2  # Buy and sell fees
                gas = self.config.gas_estimate * buy_price  # Convert gas to USD
                profit_after_fees = gross_profit - fees - gas

                if profit_after_fees < self.config.min_profit_usd:
                    continue

                self._opportunity_counter += 1
                opp_id = f"arb_{timestamp.strftime('%Y%m%d_%H%M%S')}_{self._opportunity_counter}"

                opportunity = ArbitrageOpportunity(
                    id=opp_id,
                    arb_type=ArbitrageType.CROSS_DEX,
                    symbol=symbol,
                    buy_dex=buy_dex,
                    sell_dex=sell_dex,
                    buy_price=buy_price,
                    sell_price=sell_price,
                    spread=spread,
                    spread_bps=spread_bps,
                    profit_estimate=gross_profit,
                    profit_after_fees=profit_after_fees,
                    max_size=max_size,
                    detected_at=timestamp.isoformat(),
                    expires_at=expires.isoformat()
                )

                opportunities.append(opportunity)
                self._save_opportunity(opportunity)

                logger.info(f"Found arbitrage: {symbol} {buy_dex}->{sell_dex} "
                           f"spread={spread_bps:.1f}bps profit=${profit_after_fees:.2f}")

        return opportunities

    async def scan_triangular(
        self,
        base_token: str,
        intermediate_tokens: List[str] = None
    ) -> List[TriangularPath]:
        """Scan for triangular arbitrage opportunities."""
        if intermediate_tokens is None:
            intermediate_tokens = ["USDC", "RAY", "BONK", "JUP"]

        paths = []
        base = base_token.upper()

        for mid in intermediate_tokens:
            mid = mid.upper()
            if mid == base:
                continue

            # Path: BASE -> MID -> USDC -> BASE
            path_tokens = [base, mid, "USDC", base]

            try:
                # Get prices for each leg
                prices = []
                min_liquidity = float('inf')
                bottleneck = ""

                for i in range(len(path_tokens) - 1):
                    from_token = path_tokens[i]
                    to_token = path_tokens[i + 1]

                    # This would need actual price fetching
                    # For now, return empty as this requires multiple price feeds
                    pair_prices = await self.fetch_prices(f"{from_token}/{to_token}")
                    if not pair_prices:
                        break

                    best_price = max(pair_prices.values(), key=lambda x: x.liquidity)
                    prices.append(best_price.price)

                    if best_price.liquidity < min_liquidity:
                        min_liquidity = best_price.liquidity
                        bottleneck = f"{from_token}/{to_token}"

                if len(prices) != 3:
                    continue

                # Calculate total return
                # Start with 1 unit of base, end with how many units of base
                total_return = 1.0
                for price in prices:
                    total_return *= price

                profit_bps = (total_return - 1) * 10000

                if profit_bps > self.config.min_spread_bps:
                    paths.append(TriangularPath(
                        tokens=path_tokens,
                        dexes=["jupiter"] * 3,  # Would be actual DEX selection
                        prices=prices,
                        total_return=total_return,
                        profit_bps=profit_bps,
                        max_size=min(min_liquidity * 0.1, self.config.max_trade_size),
                        bottleneck=bottleneck
                    ))

            except Exception as e:
                logger.error(f"Error scanning triangular path {path_tokens}: {e}")

        return paths

    def _save_opportunity(self, opp: ArbitrageOpportunity):
        """Save opportunity to database."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO arbitrage_opportunities
                (id, arb_type, symbol, buy_dex, sell_dex, buy_price, sell_price,
                 spread, spread_bps, profit_estimate, profit_after_fees, max_size,
                 detected_at, expires_at, status, executed_at, actual_profit,
                 path_json, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                opp.id, opp.arb_type.value, opp.symbol, opp.buy_dex, opp.sell_dex,
                opp.buy_price, opp.sell_price, opp.spread, opp.spread_bps,
                opp.profit_estimate, opp.profit_after_fees, opp.max_size,
                opp.detected_at, opp.expires_at, opp.status.value,
                opp.executed_at, opp.actual_profit,
                json.dumps(opp.path), json.dumps(opp.metadata)
            ))
            conn.commit()

    async def execute_opportunity(
        self,
        opportunity: ArbitrageOpportunity,
        size: Optional[float] = None
    ) -> Dict[str, Any]:
        """Execute an arbitrage opportunity."""
        # Validate opportunity is still valid
        now = datetime.now(timezone.utc)
        expires = datetime.fromisoformat(opportunity.expires_at.replace('Z', '+00:00'))

        if now > expires:
            opportunity.status = ArbitrageStatus.EXPIRED
            self._save_opportunity(opportunity)
            return {"success": False, "error": "Opportunity expired"}

        opportunity.status = ArbitrageStatus.VALIDATING
        self._save_opportunity(opportunity)

        # Re-fetch prices to validate spread
        prices = await self.fetch_prices(opportunity.symbol)
        buy_price = prices.get(opportunity.buy_dex)
        sell_price = prices.get(opportunity.sell_dex)

        if not buy_price or not sell_price:
            opportunity.status = ArbitrageStatus.FAILED
            self._save_opportunity(opportunity)
            return {"success": False, "error": "Price feed unavailable"}

        current_spread_bps = ((sell_price.price - buy_price.price) / buy_price.price) * 10000

        if current_spread_bps < self.config.min_spread_bps:
            opportunity.status = ArbitrageStatus.FAILED
            opportunity.metadata['failure_reason'] = f"Spread narrowed to {current_spread_bps:.1f}bps"
            self._save_opportunity(opportunity)
            return {"success": False, "error": "Spread narrowed below threshold"}

        # Execute if callback is set
        if not self._execution_callback:
            opportunity.status = ArbitrageStatus.FAILED
            self._save_opportunity(opportunity)
            return {"success": False, "error": "No execution callback set"}

        opportunity.status = ArbitrageStatus.EXECUTING
        self._save_opportunity(opportunity)

        trade_size = size or opportunity.max_size

        try:
            result = await self._execution_callback(
                symbol=opportunity.symbol,
                buy_dex=opportunity.buy_dex,
                sell_dex=opportunity.sell_dex,
                size=trade_size,
                buy_price=buy_price.price,
                sell_price=sell_price.price
            )

            if result.get('success'):
                opportunity.status = ArbitrageStatus.COMPLETED
                opportunity.executed_at = datetime.now(timezone.utc).isoformat()
                opportunity.actual_profit = result.get('profit', 0)
                opportunity.metadata['execution_details'] = result
                self._save_opportunity(opportunity)

                logger.info(f"Executed arbitrage {opportunity.id}: profit=${opportunity.actual_profit:.4f}")
                return {"success": True, "profit": opportunity.actual_profit}
            else:
                opportunity.status = ArbitrageStatus.FAILED
                opportunity.metadata['failure_reason'] = result.get('error')
                self._save_opportunity(opportunity)
                return {"success": False, "error": result.get('error')}

        except Exception as e:
            opportunity.status = ArbitrageStatus.FAILED
            opportunity.metadata['failure_reason'] = str(e)
            self._save_opportunity(opportunity)
            return {"success": False, "error": str(e)}

    async def start_scanning(
        self,
        symbols: List[str] = None,
        interval: float = 1.0,
        auto_execute: bool = False
    ):
        """Start continuous arbitrage scanning."""
        if symbols is None:
            symbols = list(self._price_feeds.keys())

        self._scanning = True
        logger.info(f"Started arbitrage scanning for {symbols}")

        while self._scanning:
            try:
                for symbol in symbols:
                    opportunities = await self.scan_cross_dex(symbol)

                    if auto_execute and opportunities:
                        # Execute best opportunity
                        best = max(opportunities, key=lambda x: x.profit_after_fees)
                        if best.profit_after_fees >= self.config.min_profit_usd:
                            await self.execute_opportunity(best)

                await asyncio.sleep(interval)

            except Exception as e:
                logger.error(f"Error in arbitrage scan: {e}")
                await asyncio.sleep(5)

    def stop_scanning(self):
        """Stop scanning."""
        self._scanning = False
        logger.info("Stopped arbitrage scanning")

    def get_recent_opportunities(
        self,
        symbol: Optional[str] = None,
        status: Optional[ArbitrageStatus] = None,
        hours: int = 24,
        limit: int = 100
    ) -> List[ArbitrageOpportunity]:
        """Get recent arbitrage opportunities."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            query = """
                SELECT * FROM arbitrage_opportunities
                WHERE datetime(detected_at) > datetime('now', ?)
            """
            params = [f'-{hours} hours']

            if symbol:
                query += " AND symbol = ?"
                params.append(symbol.upper())

            if status:
                query += " AND status = ?"
                params.append(status.value)

            query += " ORDER BY detected_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)

            return [
                ArbitrageOpportunity(
                    id=row['id'],
                    arb_type=ArbitrageType(row['arb_type']),
                    symbol=row['symbol'],
                    buy_dex=row['buy_dex'],
                    sell_dex=row['sell_dex'],
                    buy_price=row['buy_price'],
                    sell_price=row['sell_price'],
                    spread=row['spread'],
                    spread_bps=row['spread_bps'],
                    profit_estimate=row['profit_estimate'],
                    profit_after_fees=row['profit_after_fees'],
                    max_size=row['max_size'],
                    detected_at=row['detected_at'],
                    expires_at=row['expires_at'],
                    status=ArbitrageStatus(row['status']),
                    executed_at=row['executed_at'],
                    actual_profit=row['actual_profit'] or 0,
                    path=json.loads(row['path_json']) if row['path_json'] else [],
                    metadata=json.loads(row['metadata_json']) if row['metadata_json'] else {}
                )
                for row in cursor.fetchall()
            ]

    def get_statistics(self, days: int = 7) -> Dict[str, Any]:
        """Get arbitrage statistics."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            # Total opportunities
            cursor.execute("""
                SELECT COUNT(*) FROM arbitrage_opportunities
                WHERE datetime(detected_at) > datetime('now', ?)
            """, (f'-{days} days',))
            total = cursor.fetchone()[0]

            # By status
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM arbitrage_opportunities
                WHERE datetime(detected_at) > datetime('now', ?)
                GROUP BY status
            """, (f'-{days} days',))
            by_status = {row['status']: row['count'] for row in cursor.fetchall()}

            # Total profit
            cursor.execute("""
                SELECT SUM(actual_profit) FROM arbitrage_opportunities
                WHERE status = 'completed'
                AND datetime(detected_at) > datetime('now', ?)
            """, (f'-{days} days',))
            total_profit = cursor.fetchone()[0] or 0

            # Average spread
            cursor.execute("""
                SELECT AVG(spread_bps) FROM arbitrage_opportunities
                WHERE datetime(detected_at) > datetime('now', ?)
            """, (f'-{days} days',))
            avg_spread = cursor.fetchone()[0] or 0

            # Best DEX pairs
            cursor.execute("""
                SELECT buy_dex || '->' || sell_dex as pair, COUNT(*) as count,
                       AVG(profit_after_fees) as avg_profit
                FROM arbitrage_opportunities
                WHERE datetime(detected_at) > datetime('now', ?)
                GROUP BY pair
                ORDER BY count DESC
                LIMIT 5
            """, (f'-{days} days',))
            best_pairs = [
                {
                    'pair': row['pair'],
                    'count': row['count'],
                    'avg_profit': row['avg_profit']
                }
                for row in cursor.fetchall()
            ]

            return {
                'period_days': days,
                'total_opportunities': total,
                'by_status': by_status,
                'executed': by_status.get('completed', 0),
                'success_rate': by_status.get('completed', 0) / total if total > 0 else 0,
                'total_profit': total_profit,
                'avg_spread_bps': avg_spread,
                'best_pairs': best_pairs
            }

    def get_price_history(
        self,
        symbol: str,
        dex: Optional[str] = None,
        hours: int = 24
    ) -> List[Dict]:
        """Get price history for analysis."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            query = """
                SELECT dex, price, liquidity, timestamp
                FROM dex_prices
                WHERE symbol = ?
                AND datetime(timestamp) > datetime('now', ?)
            """
            params = [symbol.upper(), f'-{hours} hours']

            if dex:
                query += " AND dex = ?"
                params.append(dex)

            query += " ORDER BY timestamp ASC"

            cursor.execute(query, params)

            return [
                {
                    'dex': row['dex'],
                    'price': row['price'],
                    'liquidity': row['liquidity'],
                    'timestamp': row['timestamp']
                }
                for row in cursor.fetchall()
            ]


# Singleton
_scanner: Optional[ArbitrageScanner] = None


def get_arbitrage_scanner() -> ArbitrageScanner:
    """Get singleton arbitrage scanner."""
    global _scanner
    if _scanner is None:
        _scanner = ArbitrageScanner()
    return _scanner
