"""
Funding Rate Tracker - Track perpetual funding rates.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import json
import sqlite3
from pathlib import Path
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class FundingDirection(Enum):
    """Funding direction."""
    LONGS_PAY = "longs_pay"  # Positive funding, longs pay shorts
    SHORTS_PAY = "shorts_pay"  # Negative funding, shorts pay longs
    NEUTRAL = "neutral"


class FundingTrend(Enum):
    """Funding rate trend."""
    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"


@dataclass
class FundingRate:
    """A funding rate reading."""
    symbol: str
    rate: float  # As percentage
    rate_8h: float  # Annualized 8h rate
    rate_annual: float  # Annualized rate
    direction: FundingDirection
    timestamp: str
    next_funding_time: str
    mark_price: float
    index_price: float
    open_interest: float


@dataclass
class FundingHistory:
    """Funding rate history for a symbol."""
    symbol: str
    current_rate: FundingRate
    avg_rate_24h: float
    avg_rate_7d: float
    avg_rate_30d: float
    trend: FundingTrend
    trend_strength: float
    cumulative_funding_24h: float
    cumulative_funding_7d: float
    historical_rates: List[FundingRate]


@dataclass
class FundingArbitrage:
    """Funding arbitrage opportunity."""
    long_symbol: str
    short_symbol: str
    rate_differential: float
    expected_profit_8h: float
    expected_profit_annual: float
    confidence: float
    risk_level: str
    recommendation: str


@dataclass
class FundingPayment:
    """A funding payment record."""
    position_id: str
    symbol: str
    side: str
    size: float
    rate: float
    payment: float  # Positive = received, negative = paid
    timestamp: str


class FundingTrackerDB:
    """SQLite storage for funding data."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS funding_rates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    rate REAL,
                    rate_8h REAL,
                    rate_annual REAL,
                    direction TEXT,
                    timestamp TEXT,
                    next_funding_time TEXT,
                    mark_price REAL,
                    index_price REAL,
                    open_interest REAL
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS funding_payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    position_id TEXT,
                    symbol TEXT NOT NULL,
                    side TEXT,
                    size REAL,
                    rate REAL,
                    payment REAL,
                    timestamp TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS funding_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    alert_type TEXT,
                    threshold REAL,
                    triggered_rate REAL,
                    timestamp TEXT
                )
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_funding_symbol ON funding_rates(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_funding_time ON funding_rates(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_symbol ON funding_payments(symbol)")

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


class FundingTracker:
    """
    Track perpetual funding rates.

    Usage:
        tracker = FundingTracker()

        # Update funding rate
        tracker.update_rate("SOL-PERP", 0.01, mark_price=100)

        # Get funding history
        history = tracker.get_funding_history("SOL-PERP")

        # Find arbitrage opportunities
        opportunities = tracker.find_arbitrage_opportunities()

        # Calculate funding for position
        payment = tracker.calculate_funding("position_123", "SOL-PERP", "long", 1000)
    """

    # Common perp pairs
    TRACKED_SYMBOLS = ["SOL-PERP", "BTC-PERP", "ETH-PERP", "JUP-PERP", "BONK-PERP"]

    def __init__(self, db_path: Optional[Path] = None):
        db_path = db_path or Path(__file__).parent.parent / "data" / "funding.db"
        self.db = FundingTrackerDB(db_path)
        self._current_rates: Dict[str, FundingRate] = {}
        self._rate_providers: Dict[str, Callable] = {}

    def set_rate_provider(self, exchange: str, provider: Callable):
        """Set funding rate provider for an exchange."""
        self._rate_providers[exchange] = provider

    def update_rate(
        self,
        symbol: str,
        rate: float,
        mark_price: float = 0,
        index_price: float = 0,
        open_interest: float = 0,
        next_funding_time: str = ""
    ):
        """Update funding rate for a symbol."""
        symbol = symbol.upper()
        now = datetime.now(timezone.utc)

        # Determine direction
        if rate > 0.005:
            direction = FundingDirection.LONGS_PAY
        elif rate < -0.005:
            direction = FundingDirection.SHORTS_PAY
        else:
            direction = FundingDirection.NEUTRAL

        # Calculate annualized rates
        rate_8h = rate  # Assuming rate is already 8h rate
        rate_annual = rate * 3 * 365  # 3 funding periods per day

        if not next_funding_time:
            # Calculate next funding time (every 8 hours)
            hours_to_next = 8 - (now.hour % 8)
            next_funding = now + timedelta(hours=hours_to_next)
            next_funding = next_funding.replace(minute=0, second=0, microsecond=0)
            next_funding_time = next_funding.isoformat()

        funding_rate = FundingRate(
            symbol=symbol,
            rate=rate,
            rate_8h=rate_8h,
            rate_annual=rate_annual,
            direction=direction,
            timestamp=now.isoformat(),
            next_funding_time=next_funding_time,
            mark_price=mark_price,
            index_price=index_price,
            open_interest=open_interest
        )

        self._current_rates[symbol] = funding_rate
        self._save_rate(funding_rate)

        logger.debug(f"Updated funding rate for {symbol}: {rate:.4f}% ({direction.value})")

    def _save_rate(self, rate: FundingRate):
        """Save funding rate to database."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO funding_rates
                (symbol, rate, rate_8h, rate_annual, direction, timestamp,
                 next_funding_time, mark_price, index_price, open_interest)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                rate.symbol, rate.rate, rate.rate_8h, rate.rate_annual,
                rate.direction.value, rate.timestamp, rate.next_funding_time,
                rate.mark_price, rate.index_price, rate.open_interest
            ))
            conn.commit()

    def get_current_rate(self, symbol: str) -> Optional[FundingRate]:
        """Get current funding rate for a symbol."""
        return self._current_rates.get(symbol.upper())

    def get_funding_history(
        self,
        symbol: str,
        days: int = 7
    ) -> FundingHistory:
        """Get funding rate history for a symbol."""
        symbol = symbol.upper()

        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            # Get historical rates
            cursor.execute("""
                SELECT * FROM funding_rates
                WHERE symbol = ?
                AND datetime(timestamp) > datetime('now', ?)
                ORDER BY timestamp DESC
            """, (symbol, f'-{days} days'))

            rates = [
                FundingRate(
                    symbol=row['symbol'],
                    rate=row['rate'],
                    rate_8h=row['rate_8h'],
                    rate_annual=row['rate_annual'],
                    direction=FundingDirection(row['direction']),
                    timestamp=row['timestamp'],
                    next_funding_time=row['next_funding_time'],
                    mark_price=row['mark_price'],
                    index_price=row['index_price'],
                    open_interest=row['open_interest']
                )
                for row in cursor.fetchall()
            ]

            # Calculate averages
            if rates:
                all_rates = [r.rate for r in rates]
                rates_24h = [r.rate for r in rates if self._is_within_hours(r.timestamp, 24)]
                rates_7d = [r.rate for r in rates if self._is_within_hours(r.timestamp, 168)]

                avg_24h = sum(rates_24h) / len(rates_24h) if rates_24h else 0
                avg_7d = sum(rates_7d) / len(rates_7d) if rates_7d else 0
                avg_30d = sum(all_rates) / len(all_rates) if all_rates else 0

                # Calculate cumulative funding
                cumulative_24h = sum(rates_24h)
                cumulative_7d = sum(rates_7d)

                # Calculate trend
                if len(rates) >= 3:
                    recent = sum(r.rate for r in rates[:3]) / 3
                    older = sum(r.rate for r in rates[-3:]) / 3

                    diff = recent - older
                    if diff > 0.01:
                        trend = FundingTrend.INCREASING
                    elif diff < -0.01:
                        trend = FundingTrend.DECREASING
                    else:
                        trend = FundingTrend.STABLE

                    trend_strength = min(abs(diff) / 0.1, 1.0)
                else:
                    trend = FundingTrend.STABLE
                    trend_strength = 0

                current = self._current_rates.get(symbol) or rates[0] if rates else None
            else:
                avg_24h = avg_7d = avg_30d = 0
                cumulative_24h = cumulative_7d = 0
                trend = FundingTrend.STABLE
                trend_strength = 0
                current = self._current_rates.get(symbol)

            if not current:
                current = FundingRate(
                    symbol=symbol,
                    rate=0,
                    rate_8h=0,
                    rate_annual=0,
                    direction=FundingDirection.NEUTRAL,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    next_funding_time="",
                    mark_price=0,
                    index_price=0,
                    open_interest=0
                )

            return FundingHistory(
                symbol=symbol,
                current_rate=current,
                avg_rate_24h=avg_24h,
                avg_rate_7d=avg_7d,
                avg_rate_30d=avg_30d,
                trend=trend,
                trend_strength=trend_strength,
                cumulative_funding_24h=cumulative_24h,
                cumulative_funding_7d=cumulative_7d,
                historical_rates=rates[:100]  # Last 100 readings
            )

    def _is_within_hours(self, timestamp: str, hours: int) -> bool:
        """Check if timestamp is within specified hours."""
        try:
            ts = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
            return ts > cutoff
        except Exception:
            return False

    def calculate_funding(
        self,
        position_id: str,
        symbol: str,
        side: str,
        size_usd: float,
        record: bool = True
    ) -> float:
        """Calculate and optionally record funding payment."""
        rate = self._current_rates.get(symbol.upper())
        if not rate:
            return 0

        # Calculate payment
        # Positive rate: longs pay shorts
        # Negative rate: shorts pay longs
        payment = size_usd * (rate.rate / 100)

        if side == "long":
            payment = -payment  # Longs pay when rate is positive
        # Shorts receive when rate is positive (payment stays positive)

        if record:
            self._record_payment(
                position_id=position_id,
                symbol=symbol.upper(),
                side=side,
                size=size_usd,
                rate=rate.rate,
                payment=payment
            )

        return payment

    def _record_payment(
        self,
        position_id: str,
        symbol: str,
        side: str,
        size: float,
        rate: float,
        payment: float
    ):
        """Record funding payment."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO funding_payments
                (position_id, symbol, side, size, rate, payment, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                position_id, symbol, side, size, rate, payment,
                datetime.now(timezone.utc).isoformat()
            ))
            conn.commit()

    def get_funding_payments(
        self,
        position_id: Optional[str] = None,
        symbol: Optional[str] = None,
        days: int = 30
    ) -> List[FundingPayment]:
        """Get funding payment history."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            query = """
                SELECT * FROM funding_payments
                WHERE datetime(timestamp) > datetime('now', ?)
            """
            params = [f'-{days} days']

            if position_id:
                query += " AND position_id = ?"
                params.append(position_id)

            if symbol:
                query += " AND symbol = ?"
                params.append(symbol.upper())

            query += " ORDER BY timestamp DESC"

            cursor.execute(query, params)

            return [
                FundingPayment(
                    position_id=row['position_id'],
                    symbol=row['symbol'],
                    side=row['side'],
                    size=row['size'],
                    rate=row['rate'],
                    payment=row['payment'],
                    timestamp=row['timestamp']
                )
                for row in cursor.fetchall()
            ]

    def find_arbitrage_opportunities(
        self,
        min_differential: float = 0.05
    ) -> List[FundingArbitrage]:
        """Find funding rate arbitrage opportunities."""
        opportunities = []

        symbols = list(self._current_rates.keys())

        for i, sym1 in enumerate(symbols):
            for sym2 in symbols[i + 1:]:
                rate1 = self._current_rates[sym1]
                rate2 = self._current_rates[sym2]

                differential = abs(rate1.rate - rate2.rate)

                if differential >= min_differential:
                    # Determine direction
                    if rate1.rate > rate2.rate:
                        long_symbol = sym2  # Lower rate
                        short_symbol = sym1  # Higher rate
                    else:
                        long_symbol = sym1
                        short_symbol = sym2

                    # Expected profit (assuming $10k position each side)
                    position_size = 10000
                    profit_8h = (differential / 100) * position_size
                    profit_annual = profit_8h * 3 * 365

                    # Risk assessment
                    if differential > 0.2:
                        risk_level = "high"
                        confidence = 0.6
                    elif differential > 0.1:
                        risk_level = "medium"
                        confidence = 0.75
                    else:
                        risk_level = "low"
                        confidence = 0.85

                    recommendation = f"Long {long_symbol}, Short {short_symbol} to capture {differential:.2f}% spread"

                    opportunities.append(FundingArbitrage(
                        long_symbol=long_symbol,
                        short_symbol=short_symbol,
                        rate_differential=differential,
                        expected_profit_8h=profit_8h,
                        expected_profit_annual=profit_annual,
                        confidence=confidence,
                        risk_level=risk_level,
                        recommendation=recommendation
                    ))

        # Sort by expected profit
        opportunities.sort(key=lambda x: x.expected_profit_8h, reverse=True)

        return opportunities

    def get_all_rates(self) -> Dict[str, FundingRate]:
        """Get all current funding rates."""
        return self._current_rates.copy()

    def get_highest_rates(self, n: int = 5) -> List[FundingRate]:
        """Get symbols with highest positive funding rates."""
        rates = list(self._current_rates.values())
        rates.sort(key=lambda x: x.rate, reverse=True)
        return rates[:n]

    def get_lowest_rates(self, n: int = 5) -> List[FundingRate]:
        """Get symbols with lowest (most negative) funding rates."""
        rates = list(self._current_rates.values())
        rates.sort(key=lambda x: x.rate)
        return rates[:n]

    def get_statistics(self, symbol: str, days: int = 30) -> Dict[str, Any]:
        """Get funding statistics for a symbol."""
        history = self.get_funding_history(symbol, days)

        if not history.historical_rates:
            return {'symbol': symbol, 'no_data': True}

        rates = [r.rate for r in history.historical_rates]

        # Calculate percentiles
        sorted_rates = sorted(rates)
        n = len(sorted_rates)

        return {
            'symbol': symbol,
            'period_days': days,
            'current_rate': history.current_rate.rate,
            'avg_rate': sum(rates) / len(rates),
            'min_rate': min(rates),
            'max_rate': max(rates),
            'median_rate': sorted_rates[n // 2],
            'p25_rate': sorted_rates[int(n * 0.25)],
            'p75_rate': sorted_rates[int(n * 0.75)],
            'cumulative_funding': sum(rates),
            'trend': history.trend.value,
            'trend_strength': history.trend_strength,
            'readings_count': n
        }


# Singleton
_tracker: Optional[FundingTracker] = None


def get_funding_tracker() -> FundingTracker:
    """Get singleton funding tracker."""
    global _tracker
    if _tracker is None:
        _tracker = FundingTracker()
    return _tracker
