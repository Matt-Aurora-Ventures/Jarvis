"""
Market Session Tracker - Track market hours and trading sessions.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import pytz

logger = logging.getLogger(__name__)


class MarketType(Enum):
    """Types of markets."""
    CRYPTO = "crypto"
    US_STOCK = "us_stock"
    EU_STOCK = "eu_stock"
    ASIA_STOCK = "asia_stock"
    FOREX = "forex"
    COMMODITIES = "commodities"


class SessionType(Enum):
    """Trading session types."""
    PRE_MARKET = "pre_market"
    REGULAR = "regular"
    AFTER_HOURS = "after_hours"
    CLOSED = "closed"


@dataclass
class MarketSession:
    """Market trading session information."""
    market: MarketType
    session: SessionType
    is_open: bool
    opens_at: Optional[datetime]
    closes_at: Optional[datetime]
    next_open: Optional[datetime]
    time_until_open: Optional[timedelta]
    time_until_close: Optional[timedelta]
    timezone: str


@dataclass
class MarketHours:
    """Trading hours for a market."""
    market: MarketType
    timezone: str
    regular_open: Tuple[int, int]  # (hour, minute)
    regular_close: Tuple[int, int]
    pre_market_open: Optional[Tuple[int, int]] = None
    after_hours_close: Optional[Tuple[int, int]] = None
    trading_days: List[int] = None  # 0=Monday, 6=Sunday

    def __post_init__(self):
        if self.trading_days is None:
            if self.market == MarketType.CRYPTO:
                self.trading_days = [0, 1, 2, 3, 4, 5, 6]  # 24/7
            else:
                self.trading_days = [0, 1, 2, 3, 4]  # Mon-Fri


class MarketSessionTracker:
    """
    Track market sessions and trading hours.

    Usage:
        tracker = MarketSessionTracker()

        # Check if US market is open
        session = tracker.get_session(MarketType.US_STOCK)
        if session.is_open:
            print("Market is open!")

        # Get all open markets
        open_markets = tracker.get_open_markets()

        # Get next market event
        next_event = tracker.get_next_market_event()
    """

    # Market configurations
    MARKETS = {
        MarketType.CRYPTO: MarketHours(
            market=MarketType.CRYPTO,
            timezone="UTC",
            regular_open=(0, 0),
            regular_close=(23, 59),
            trading_days=[0, 1, 2, 3, 4, 5, 6]
        ),
        MarketType.US_STOCK: MarketHours(
            market=MarketType.US_STOCK,
            timezone="America/New_York",
            regular_open=(9, 30),
            regular_close=(16, 0),
            pre_market_open=(4, 0),
            after_hours_close=(20, 0),
            trading_days=[0, 1, 2, 3, 4]
        ),
        MarketType.EU_STOCK: MarketHours(
            market=MarketType.EU_STOCK,
            timezone="Europe/London",
            regular_open=(8, 0),
            regular_close=(16, 30),
            trading_days=[0, 1, 2, 3, 4]
        ),
        MarketType.ASIA_STOCK: MarketHours(
            market=MarketType.ASIA_STOCK,
            timezone="Asia/Tokyo",
            regular_open=(9, 0),
            regular_close=(15, 0),
            trading_days=[0, 1, 2, 3, 4]
        ),
        MarketType.FOREX: MarketHours(
            market=MarketType.FOREX,
            timezone="UTC",
            regular_open=(22, 0),  # Sunday 22:00 UTC
            regular_close=(22, 0),  # Friday 22:00 UTC
            trading_days=[0, 1, 2, 3, 4, 6]  # Sun evening to Fri evening
        )
    }

    # US Market holidays (simplified - would need annual updates)
    US_HOLIDAYS_2024 = [
        "2024-01-01",  # New Year's Day
        "2024-01-15",  # MLK Day
        "2024-02-19",  # Presidents Day
        "2024-03-29",  # Good Friday
        "2024-05-27",  # Memorial Day
        "2024-06-19",  # Juneteenth
        "2024-07-04",  # Independence Day
        "2024-09-02",  # Labor Day
        "2024-11-28",  # Thanksgiving
        "2024-12-25",  # Christmas
    ]

    def __init__(self):
        self._holidays = self._load_holidays()

    def _load_holidays(self) -> Dict[MarketType, List[str]]:
        """Load market holidays."""
        return {
            MarketType.US_STOCK: self.US_HOLIDAYS_2024,
            MarketType.EU_STOCK: [],  # Add EU holidays
            MarketType.ASIA_STOCK: [],  # Add Asia holidays
        }

    def get_session(self, market: MarketType) -> MarketSession:
        """Get current session information for a market."""
        hours = self.MARKETS.get(market)
        if not hours:
            return MarketSession(
                market=market,
                session=SessionType.CLOSED,
                is_open=False,
                opens_at=None,
                closes_at=None,
                next_open=None,
                time_until_open=None,
                time_until_close=None,
                timezone="UTC"
            )

        now = datetime.now(timezone.utc)
        tz = pytz.timezone(hours.timezone)
        local_now = now.astimezone(tz)

        # Check if it's a trading day
        if local_now.weekday() not in hours.trading_days:
            return self._create_closed_session(market, hours, local_now)

        # Check for holidays
        if self._is_holiday(market, local_now):
            return self._create_closed_session(market, hours, local_now)

        # Crypto is always open
        if market == MarketType.CRYPTO:
            return MarketSession(
                market=market,
                session=SessionType.REGULAR,
                is_open=True,
                opens_at=None,
                closes_at=None,
                next_open=None,
                time_until_open=None,
                time_until_close=None,
                timezone=hours.timezone
            )

        # Check session type
        current_time = (local_now.hour, local_now.minute)

        # Regular hours
        if self._time_in_range(current_time, hours.regular_open, hours.regular_close):
            close_time = local_now.replace(
                hour=hours.regular_close[0],
                minute=hours.regular_close[1],
                second=0
            )
            return MarketSession(
                market=market,
                session=SessionType.REGULAR,
                is_open=True,
                opens_at=None,
                closes_at=close_time,
                next_open=None,
                time_until_open=None,
                time_until_close=close_time - local_now,
                timezone=hours.timezone
            )

        # Pre-market
        if hours.pre_market_open and self._time_in_range(
            current_time, hours.pre_market_open, hours.regular_open
        ):
            open_time = local_now.replace(
                hour=hours.regular_open[0],
                minute=hours.regular_open[1],
                second=0
            )
            return MarketSession(
                market=market,
                session=SessionType.PRE_MARKET,
                is_open=True,
                opens_at=open_time,
                closes_at=None,
                next_open=open_time,
                time_until_open=open_time - local_now,
                time_until_close=None,
                timezone=hours.timezone
            )

        # After hours
        if hours.after_hours_close and self._time_in_range(
            current_time, hours.regular_close, hours.after_hours_close
        ):
            close_time = local_now.replace(
                hour=hours.after_hours_close[0],
                minute=hours.after_hours_close[1],
                second=0
            )
            return MarketSession(
                market=market,
                session=SessionType.AFTER_HOURS,
                is_open=True,
                opens_at=None,
                closes_at=close_time,
                next_open=None,
                time_until_open=None,
                time_until_close=close_time - local_now,
                timezone=hours.timezone
            )

        # Market is closed
        return self._create_closed_session(market, hours, local_now)

    def _time_in_range(
        self,
        current: Tuple[int, int],
        start: Tuple[int, int],
        end: Tuple[int, int]
    ) -> bool:
        """Check if current time is in range."""
        current_mins = current[0] * 60 + current[1]
        start_mins = start[0] * 60 + start[1]
        end_mins = end[0] * 60 + end[1]
        return start_mins <= current_mins < end_mins

    def _is_holiday(self, market: MarketType, date: datetime) -> bool:
        """Check if date is a market holiday."""
        holidays = self._holidays.get(market, [])
        date_str = date.strftime("%Y-%m-%d")
        return date_str in holidays

    def _create_closed_session(
        self,
        market: MarketType,
        hours: MarketHours,
        local_now: datetime
    ) -> MarketSession:
        """Create a closed session with next open time."""
        next_open = self._get_next_open(market, hours, local_now)

        return MarketSession(
            market=market,
            session=SessionType.CLOSED,
            is_open=False,
            opens_at=next_open,
            closes_at=None,
            next_open=next_open,
            time_until_open=next_open - local_now if next_open else None,
            time_until_close=None,
            timezone=hours.timezone
        )

    def _get_next_open(
        self,
        market: MarketType,
        hours: MarketHours,
        local_now: datetime
    ) -> datetime:
        """Calculate next market open time."""
        # Start from tomorrow if market is closed today
        check_date = local_now

        for _ in range(8):  # Check up to a week ahead
            check_date = check_date + timedelta(days=1)

            if check_date.weekday() not in hours.trading_days:
                continue

            if self._is_holiday(market, check_date):
                continue

            # Found a trading day
            open_hour, open_min = hours.pre_market_open or hours.regular_open
            return check_date.replace(
                hour=open_hour,
                minute=open_min,
                second=0,
                microsecond=0
            )

        return None

    def get_open_markets(self) -> List[MarketSession]:
        """Get all currently open markets."""
        return [
            session for market in MarketType
            if (session := self.get_session(market)).is_open
        ]

    def get_all_sessions(self) -> Dict[MarketType, MarketSession]:
        """Get session info for all markets."""
        return {market: self.get_session(market) for market in MarketType}

    def get_next_market_event(self) -> Dict[str, any]:
        """Get the next market open/close event."""
        events = []
        now = datetime.now(timezone.utc)

        for market in MarketType:
            session = self.get_session(market)

            if session.time_until_close:
                events.append({
                    'market': market.value,
                    'event': 'close',
                    'time': session.closes_at,
                    'delta': session.time_until_close
                })

            if session.time_until_open:
                events.append({
                    'market': market.value,
                    'event': 'open',
                    'time': session.opens_at,
                    'delta': session.time_until_open
                })

        if not events:
            return None

        # Return the soonest event
        events.sort(key=lambda e: e['delta'])
        return events[0]

    def is_market_open(self, market: MarketType) -> bool:
        """Quick check if a market is open."""
        return self.get_session(market).is_open

    def get_trading_summary(self) -> str:
        """Get a human-readable trading summary."""
        lines = ["Market Session Summary", "=" * 30]

        for market in MarketType:
            session = self.get_session(market)
            status = "OPEN" if session.is_open else "CLOSED"

            if session.is_open:
                if session.time_until_close:
                    remaining = str(session.time_until_close).split('.')[0]
                    lines.append(f"{market.value}: {status} ({session.session.value}) - closes in {remaining}")
                else:
                    lines.append(f"{market.value}: {status} ({session.session.value}) - 24/7")
            else:
                if session.time_until_open:
                    remaining = str(session.time_until_open).split('.')[0]
                    lines.append(f"{market.value}: {status} - opens in {remaining}")
                else:
                    lines.append(f"{market.value}: {status}")

        return "\n".join(lines)


# Singleton
_tracker: Optional[MarketSessionTracker] = None

def get_market_tracker() -> MarketSessionTracker:
    """Get singleton market session tracker."""
    global _tracker
    if _tracker is None:
        _tracker = MarketSessionTracker()
    return _tracker


# Convenience functions
def is_us_market_open() -> bool:
    """Check if US stock market is open."""
    return get_market_tracker().is_market_open(MarketType.US_STOCK)


def is_crypto_market_open() -> bool:
    """Check if crypto market is open (always True)."""
    return True


def get_market_status() -> str:
    """Get current market status summary."""
    return get_market_tracker().get_trading_summary()
