"""
xStock / Tokenized Equity Strategy — Market hours gating and oracle validation.

xStocks trade 24/7 on Solana but their Chainlink oracle data goes stale after
4 PM ET and on weekends. Running momentum and MA strategies on stale oracle
data generates pure noise signals.

Key constraints:
    - All xStock algorithm logic MUST gate through ``is_market_hours()``
    - Oracle staleness > 5 min during market hours → degraded, widen spread
    - Oracle staleness > 30 min → halt trading entirely
    - Max backtest history: ~8 months (launched June 30, 2025)

xStock-specific slippage:
    - TSLAx, NVDAx, SPYx, AAPLx: ~1% round-trip (highest liquidity)
    - All others: 2–5% round-trip (thin pools), max 0.25% portfolio

Usage::

    from core.trading.xstock_strategy import is_market_hours, get_oracle_status

    if not is_market_hours():
        return  # Do not trade on stale oracle data

    status = get_oracle_status(last_oracle_update, current_time)
    if status.halted:
        return  # Oracle too stale
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timezone, timedelta
from enum import Enum
from typing import Optional, Set

logger = logging.getLogger(__name__)

try:
    import pytz
    HAS_PYTZ = True
    US_EASTERN = pytz.timezone("America/New_York")
except ImportError:
    HAS_PYTZ = False
    US_EASTERN = None

# Fallback UTC offset for US Eastern (ET is UTC-5, EDT is UTC-4)
# Used only when pytz is not available
_ET_OFFSET_STANDARD = timedelta(hours=-5)
_ET_OFFSET_DST = timedelta(hours=-4)


# ---------------------------------------------------------------------------
# Market hours
# ---------------------------------------------------------------------------

MARKET_OPEN = time(9, 30)   # 9:30 AM ET
MARKET_CLOSE = time(16, 0)  # 4:00 PM ET

# U.S. market holidays for 2025-2026 (NYSE/NASDAQ)
US_MARKET_HOLIDAYS: Set[date] = {
    # 2025
    date(2025, 1, 1),    # New Year's Day
    date(2025, 1, 20),   # MLK Day
    date(2025, 2, 17),   # Presidents' Day
    date(2025, 4, 18),   # Good Friday
    date(2025, 5, 26),   # Memorial Day
    date(2025, 6, 19),   # Juneteenth
    date(2025, 7, 4),    # Independence Day
    date(2025, 9, 1),    # Labor Day
    date(2025, 11, 27),  # Thanksgiving
    date(2025, 12, 25),  # Christmas
    # 2026
    date(2026, 1, 1),    # New Year's Day
    date(2026, 1, 19),   # MLK Day
    date(2026, 2, 16),   # Presidents' Day
    date(2026, 4, 3),    # Good Friday
    date(2026, 5, 25),   # Memorial Day
    date(2026, 6, 19),   # Juneteenth
    date(2026, 7, 3),    # Independence Day (observed)
    date(2026, 9, 7),    # Labor Day
    date(2026, 11, 26),  # Thanksgiving
    date(2026, 12, 25),  # Christmas
}


def _to_eastern(dt: datetime) -> datetime:
    """Convert a datetime to US Eastern time."""
    if HAS_PYTZ:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(US_EASTERN)
    else:
        # Approximate DST (second Sunday in March to first Sunday in November)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        # Simple heuristic: March 8 – Nov 1 is roughly DST
        month = dt.month
        is_dst = 3 < month < 11 or (month == 3 and dt.day >= 8) or (month == 11 and dt.day < 1)
        offset = _ET_OFFSET_DST if is_dst else _ET_OFFSET_STANDARD
        return dt.astimezone(timezone(offset))


def is_market_hours(dt: Optional[datetime] = None) -> bool:
    """
    Return True if the given datetime falls within US equity market hours.

    Checks:
        - Weekday (Monday–Friday)
        - Between 9:30 AM and 4:00 PM Eastern
        - Not a U.S. market holiday

    If *dt* is None, uses the current UTC time.
    """
    if dt is None:
        dt = datetime.now(timezone.utc)

    et = _to_eastern(dt)

    # Weekend check
    if et.weekday() >= 5:  # Saturday=5, Sunday=6
        return False

    # Holiday check
    if et.date() in US_MARKET_HOLIDAYS:
        return False

    # Time check
    current_time = et.time()
    return MARKET_OPEN <= current_time < MARKET_CLOSE


def is_market_day(dt: Optional[datetime] = None) -> bool:
    """Return True if the date is a trading day (weekday + not holiday)."""
    if dt is None:
        dt = datetime.now(timezone.utc)
    et = _to_eastern(dt)
    if et.weekday() >= 5:
        return False
    return et.date() not in US_MARKET_HOLIDAYS


# ---------------------------------------------------------------------------
# Oracle staleness
# ---------------------------------------------------------------------------

class OracleCondition(Enum):
    """Health status of the Chainlink oracle feed."""

    FRESH = "fresh"             # < 5 minutes stale during market hours
    DEGRADED = "degraded"       # 5–30 minutes stale (widen spread)
    HALTED = "halted"           # > 30 minutes stale (do not trade)
    AFTER_HOURS = "after_hours" # Market is closed


@dataclass
class OracleStatus:
    """Oracle health assessment for an xStock."""

    condition: OracleCondition
    staleness_minutes: float
    is_market_hours: bool
    halted: bool
    spread_multiplier: float    # Multiply normal spread by this factor

    def summary(self) -> str:
        return (
            f"Oracle {self.condition.value}: "
            f"staleness={self.staleness_minutes:.1f}m, "
            f"market={'OPEN' if self.is_market_hours else 'CLOSED'}, "
            f"spread×{self.spread_multiplier:.1f}"
        )


def get_oracle_status(
    last_update: datetime,
    current_time: Optional[datetime] = None,
) -> OracleStatus:
    """
    Assess Chainlink oracle health for an xStock.

    Args:
        last_update: Timestamp of last oracle price update
        current_time: Current time (defaults to now UTC)

    Returns:
        OracleStatus with trading recommendation
    """
    now = current_time or datetime.now(timezone.utc)

    if last_update.tzinfo is None:
        last_update = last_update.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    staleness_s = (now - last_update).total_seconds()
    staleness_m = staleness_s / 60

    market_open = is_market_hours(now)

    if not market_open:
        return OracleStatus(
            condition=OracleCondition.AFTER_HOURS,
            staleness_minutes=staleness_m,
            is_market_hours=False,
            halted=True,   # Do not trade after hours regardless
            spread_multiplier=5.0,
        )

    if staleness_m > 30:
        return OracleStatus(
            condition=OracleCondition.HALTED,
            staleness_minutes=staleness_m,
            is_market_hours=True,
            halted=True,
            spread_multiplier=10.0,
        )

    if staleness_m > 5:
        # Spread widens linearly: 1.0 at 5m → 3.0 at 30m
        multiplier = 1.0 + (staleness_m - 5) * (2.0 / 25)
        return OracleStatus(
            condition=OracleCondition.DEGRADED,
            staleness_minutes=staleness_m,
            is_market_hours=True,
            halted=False,
            spread_multiplier=round(multiplier, 2),
        )

    return OracleStatus(
        condition=OracleCondition.FRESH,
        staleness_minutes=staleness_m,
        is_market_hours=True,
        halted=False,
        spread_multiplier=1.0,
    )


# ---------------------------------------------------------------------------
# xStock liquidity tiers
# ---------------------------------------------------------------------------

# Tickers with highest on-chain liquidity (lower slippage)
HIGH_LIQUIDITY_XSTOCKS = frozenset({"TSLA", "NVDA", "SPY", "AAPL"})


def get_xstock_max_position_pct(underlying_ticker: str) -> float:
    """
    Maximum portfolio allocation for an xStock position.

    - High-liquidity tickers: 2% max
    - All others: 0.25% max (thin pools)
    """
    if underlying_ticker.upper() in HIGH_LIQUIDITY_XSTOCKS:
        return 0.02
    return 0.0025


def get_xstock_expected_slippage(underlying_ticker: str) -> float:
    """
    Expected round-trip slippage percentage for an xStock.

    - High-liquidity: ~1%
    - Others: ~3%
    """
    if underlying_ticker.upper() in HIGH_LIQUIDITY_XSTOCKS:
        return 0.01
    return 0.03


# ---------------------------------------------------------------------------
# Backtest constraints
# ---------------------------------------------------------------------------

# xStocks launched June 30, 2025
XSTOCK_LAUNCH_DATE = datetime(2025, 6, 30, tzinfo=timezone.utc)
XSTOCK_MAX_BACKTEST_MONTHS = 8

def validate_xstock_backtest_period(
    start_date: datetime,
    end_date: datetime,
) -> bool:
    """
    Validate that a backtest period is reasonable for xStocks.

    Returns False if start_date is before launch or span exceeds available data.
    Warns about limited statistical confidence.
    """
    if start_date < XSTOCK_LAUNCH_DATE:
        logger.warning(
            "xStock backtest start %s is before launch date %s — adjusting",
            start_date.date(), XSTOCK_LAUNCH_DATE.date(),
        )
        return False

    span_months = (end_date - start_date).days / 30
    if span_months > XSTOCK_MAX_BACKTEST_MONTHS:
        logger.warning(
            "xStock backtest span %.1f months exceeds available data (~%d months)",
            span_months, XSTOCK_MAX_BACKTEST_MONTHS,
        )

    return True
