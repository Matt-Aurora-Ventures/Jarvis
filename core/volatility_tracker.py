"""
Volatility Tracker - Track and analyze market volatility across tokens.
Calculates historical volatility, implied volatility, and volatility regimes.
"""
import math
import sqlite3
import threading
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class VolatilityRegime(Enum):
    """Market volatility regimes."""
    VERY_LOW = "very_low"          # < 20% annualized
    LOW = "low"                    # 20-40%
    NORMAL = "normal"              # 40-60%
    HIGH = "high"                  # 60-100%
    EXTREME = "extreme"            # > 100%


class VolatilityType(Enum):
    """Types of volatility measures."""
    HISTORICAL = "historical"      # Realized volatility
    PARKINSON = "parkinson"        # High-low volatility
    GARMAN_KLASS = "garman_klass"  # OHLC-based volatility
    YANG_ZHANG = "yang_zhang"      # Open-to-close adjusted
    EWMA = "ewma"                  # Exponentially weighted


@dataclass
class PriceData:
    """Price data point."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class VolatilityReading:
    """A volatility measurement."""
    symbol: str
    volatility_type: VolatilityType
    value: float                   # As decimal (0.5 = 50%)
    annualized: float              # Annualized percentage
    period_days: int
    regime: VolatilityRegime
    timestamp: datetime
    percentile: Optional[float]    # Historical percentile


@dataclass
class VolatilityCone:
    """Volatility cone for different time periods."""
    symbol: str
    periods: List[int]             # e.g., [7, 14, 30, 60, 90]
    min_vol: Dict[int, float]
    max_vol: Dict[int, float]
    median_vol: Dict[int, float]
    current_vol: Dict[int, float]
    percentile: Dict[int, float]
    calculated_at: datetime


@dataclass
class VolatilityAlert:
    """Alert for volatility changes."""
    symbol: str
    alert_type: str                # "regime_change", "spike", "compression"
    old_value: float
    new_value: float
    old_regime: VolatilityRegime
    new_regime: VolatilityRegime
    triggered_at: datetime


class VolatilityTracker:
    """
    Tracks and analyzes volatility across multiple tokens.
    Provides historical, realized, and implied volatility metrics.
    """

    # Trading days per year for annualization
    TRADING_DAYS = 365

    # Regime thresholds (annualized)
    REGIME_THRESHOLDS = {
        VolatilityRegime.VERY_LOW: 0.20,
        VolatilityRegime.LOW: 0.40,
        VolatilityRegime.NORMAL: 0.60,
        VolatilityRegime.HIGH: 1.00,
        VolatilityRegime.EXTREME: float('inf')
    }

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or str(
            Path(__file__).parent.parent / "data" / "volatility_tracker.db"
        )
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

        # Price history per symbol
        self.price_history: Dict[str, deque] = {}
        self.max_history = 365  # 1 year of daily data

        # Volatility cache
        self.volatility_cache: Dict[str, Dict[int, VolatilityReading]] = {}

        # Alert callbacks
        self.alert_callbacks: List = []
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
                CREATE TABLE IF NOT EXISTS prices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL,
                    UNIQUE(symbol, timestamp)
                );

                CREATE TABLE IF NOT EXISTS volatility_readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    volatility_type TEXT NOT NULL,
                    value REAL NOT NULL,
                    annualized REAL NOT NULL,
                    period_days INTEGER NOT NULL,
                    regime TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    percentile REAL
                );

                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    old_value REAL NOT NULL,
                    new_value REAL NOT NULL,
                    old_regime TEXT NOT NULL,
                    new_regime TEXT NOT NULL,
                    triggered_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_prices_symbol ON prices(symbol);
                CREATE INDEX IF NOT EXISTS idx_prices_timestamp ON prices(timestamp);
                CREATE INDEX IF NOT EXISTS idx_vol_symbol ON volatility_readings(symbol);
            """)

    def add_price(
        self,
        symbol: str,
        timestamp: datetime,
        open_price: float,
        high: float,
        low: float,
        close: float,
        volume: float
    ):
        """Add a price data point."""
        price = PriceData(
            timestamp=timestamp,
            open=open_price,
            high=high,
            low=low,
            close=close,
            volume=volume
        )

        with self._lock:
            if symbol not in self.price_history:
                self.price_history[symbol] = deque(maxlen=self.max_history)
            self.price_history[symbol].append(price)

        with self._get_db() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO prices
                (symbol, timestamp, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                symbol, timestamp.isoformat(), open_price,
                high, low, close, volume
            ))

    def calculate_historical_volatility(
        self,
        symbol: str,
        period: int = 30,
        vol_type: VolatilityType = VolatilityType.HISTORICAL
    ) -> Optional[VolatilityReading]:
        """Calculate historical volatility for a symbol."""
        prices = list(self.price_history.get(symbol, []))
        if len(prices) < period + 1:
            return None

        recent_prices = prices[-(period + 1):]

        if vol_type == VolatilityType.HISTORICAL:
            vol = self._calc_close_to_close_vol(recent_prices)
        elif vol_type == VolatilityType.PARKINSON:
            vol = self._calc_parkinson_vol(recent_prices)
        elif vol_type == VolatilityType.GARMAN_KLASS:
            vol = self._calc_garman_klass_vol(recent_prices)
        elif vol_type == VolatilityType.YANG_ZHANG:
            vol = self._calc_yang_zhang_vol(recent_prices)
        elif vol_type == VolatilityType.EWMA:
            vol = self._calc_ewma_vol(recent_prices)
        else:
            vol = self._calc_close_to_close_vol(recent_prices)

        # Annualize
        annualized = vol * math.sqrt(self.TRADING_DAYS)
        regime = self._get_regime(annualized)

        # Calculate percentile
        percentile = self._calculate_percentile(symbol, vol, period)

        reading = VolatilityReading(
            symbol=symbol,
            volatility_type=vol_type,
            value=vol,
            annualized=annualized,
            period_days=period,
            regime=regime,
            timestamp=datetime.now(),
            percentile=percentile
        )

        # Cache the reading
        if symbol not in self.volatility_cache:
            self.volatility_cache[symbol] = {}
        self.volatility_cache[symbol][period] = reading

        # Save to database
        self._save_reading(reading)

        return reading

    def _calc_close_to_close_vol(self, prices: List[PriceData]) -> float:
        """Calculate close-to-close volatility."""
        if len(prices) < 2:
            return 0

        returns = []
        for i in range(1, len(prices)):
            if prices[i-1].close > 0:
                log_return = math.log(prices[i].close / prices[i-1].close)
                returns.append(log_return)

        if not returns:
            return 0

        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
        return math.sqrt(variance)

    def _calc_parkinson_vol(self, prices: List[PriceData]) -> float:
        """Calculate Parkinson volatility using high-low range."""
        if len(prices) < 2:
            return 0

        sum_sq = 0
        for price in prices:
            if price.low > 0:
                hl = math.log(price.high / price.low)
                sum_sq += hl ** 2

        n = len(prices)
        return math.sqrt(sum_sq / (4 * n * math.log(2)))

    def _calc_garman_klass_vol(self, prices: List[PriceData]) -> float:
        """Calculate Garman-Klass volatility using OHLC."""
        if len(prices) < 2:
            return 0

        sum_val = 0
        for price in prices:
            if price.low > 0 and price.open > 0:
                hl = math.log(price.high / price.low)
                co = math.log(price.close / price.open)
                sum_val += 0.5 * hl ** 2 - (2 * math.log(2) - 1) * co ** 2

        return math.sqrt(sum_val / len(prices))

    def _calc_yang_zhang_vol(self, prices: List[PriceData]) -> float:
        """Calculate Yang-Zhang volatility."""
        if len(prices) < 2:
            return 0

        n = len(prices)
        k = 0.34 / (1.34 + (n + 1) / (n - 1))

        # Overnight volatility
        overnight_returns = []
        for i in range(1, len(prices)):
            if prices[i-1].close > 0:
                overnight_returns.append(math.log(prices[i].open / prices[i-1].close))

        overnight_var = sum(r ** 2 for r in overnight_returns) / (n - 1) if overnight_returns else 0

        # Open-to-close volatility
        oc_returns = []
        for price in prices:
            if price.open > 0:
                oc_returns.append(math.log(price.close / price.open))

        oc_var = sum(r ** 2 for r in oc_returns) / (n - 1) if oc_returns else 0

        # Rogers-Satchell volatility
        rs_var = 0
        for price in prices:
            if price.open > 0 and price.low > 0:
                ho = math.log(price.high / price.open)
                lo = math.log(price.low / price.open)
                hc = math.log(price.high / price.close)
                lc = math.log(price.low / price.close)
                rs_var += ho * hc + lo * lc

        rs_var /= n

        return math.sqrt(overnight_var + k * oc_var + (1 - k) * rs_var)

    def _calc_ewma_vol(self, prices: List[PriceData], lambda_: float = 0.94) -> float:
        """Calculate EWMA volatility."""
        if len(prices) < 2:
            return 0

        returns = []
        for i in range(1, len(prices)):
            if prices[i-1].close > 0:
                returns.append(math.log(prices[i].close / prices[i-1].close))

        if not returns:
            return 0

        # Initialize with sample variance
        variance = sum(r ** 2 for r in returns) / len(returns)

        # EWMA recursion
        for ret in returns:
            variance = lambda_ * variance + (1 - lambda_) * ret ** 2

        return math.sqrt(variance)

    def _get_regime(self, annualized_vol: float) -> VolatilityRegime:
        """Determine volatility regime."""
        for regime, threshold in self.REGIME_THRESHOLDS.items():
            if annualized_vol < threshold:
                return regime
        return VolatilityRegime.EXTREME

    def _calculate_percentile(
        self,
        symbol: str,
        current_vol: float,
        period: int
    ) -> Optional[float]:
        """Calculate percentile of current volatility."""
        with self._get_db() as conn:
            rows = conn.execute("""
                SELECT value FROM volatility_readings
                WHERE symbol = ? AND period_days = ?
                ORDER BY timestamp DESC LIMIT 252
            """, (symbol, period)).fetchall()

            if len(rows) < 10:
                return None

            historical = [row["value"] for row in rows]
            below = sum(1 for v in historical if v < current_vol)
            return below / len(historical) * 100

    def _save_reading(self, reading: VolatilityReading):
        """Save volatility reading to database."""
        with self._get_db() as conn:
            conn.execute("""
                INSERT INTO volatility_readings
                (symbol, volatility_type, value, annualized, period_days,
                 regime, timestamp, percentile)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                reading.symbol, reading.volatility_type.value,
                reading.value, reading.annualized, reading.period_days,
                reading.regime.value, reading.timestamp.isoformat(),
                reading.percentile
            ))

    def get_volatility_cone(
        self,
        symbol: str,
        periods: List[int] = None
    ) -> Optional[VolatilityCone]:
        """Calculate volatility cone for multiple periods."""
        if periods is None:
            periods = [7, 14, 30, 60, 90]

        prices = list(self.price_history.get(symbol, []))
        if len(prices) < max(periods) + 1:
            return None

        min_vol = {}
        max_vol = {}
        median_vol = {}
        current_vol = {}
        percentile = {}

        for period in periods:
            # Calculate rolling volatilities
            vols = []
            for i in range(period, len(prices)):
                window = prices[i-period:i+1]
                vol = self._calc_close_to_close_vol(window)
                if vol > 0:
                    vols.append(vol * math.sqrt(self.TRADING_DAYS))

            if vols:
                vols.sort()
                min_vol[period] = vols[0]
                max_vol[period] = vols[-1]
                median_vol[period] = vols[len(vols) // 2]

                # Current volatility
                reading = self.calculate_historical_volatility(symbol, period)
                current_vol[period] = reading.annualized if reading else 0
                percentile[period] = reading.percentile if reading else None

        return VolatilityCone(
            symbol=symbol,
            periods=periods,
            min_vol=min_vol,
            max_vol=max_vol,
            median_vol=median_vol,
            current_vol=current_vol,
            percentile=percentile,
            calculated_at=datetime.now()
        )

    def detect_regime_change(self, symbol: str) -> Optional[VolatilityAlert]:
        """Detect if volatility regime has changed."""
        if symbol not in self.volatility_cache:
            return None

        cache = self.volatility_cache[symbol]
        if 30 not in cache:
            return None

        current = cache[30]

        # Get previous regime from database
        with self._get_db() as conn:
            row = conn.execute("""
                SELECT regime, annualized FROM volatility_readings
                WHERE symbol = ? AND period_days = 30
                ORDER BY timestamp DESC LIMIT 1 OFFSET 1
            """, (symbol,)).fetchone()

            if not row:
                return None

            old_regime = VolatilityRegime(row["regime"])
            old_value = row["annualized"]

            if old_regime != current.regime:
                alert = VolatilityAlert(
                    symbol=symbol,
                    alert_type="regime_change",
                    old_value=old_value,
                    new_value=current.annualized,
                    old_regime=old_regime,
                    new_regime=current.regime,
                    triggered_at=datetime.now()
                )

                # Save alert
                conn.execute("""
                    INSERT INTO alerts
                    (symbol, alert_type, old_value, new_value,
                     old_regime, new_regime, triggered_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    alert.symbol, alert.alert_type, alert.old_value,
                    alert.new_value, alert.old_regime.value,
                    alert.new_regime.value, alert.triggered_at.isoformat()
                ))

                # Trigger callbacks
                for callback in self.alert_callbacks:
                    try:
                        callback(alert)
                    except Exception:
                        pass

                return alert

        return None

    def get_volatility_term_structure(
        self,
        symbol: str
    ) -> Dict[int, float]:
        """Get volatility term structure."""
        structure = {}
        for period in [7, 14, 30, 60, 90, 180]:
            reading = self.calculate_historical_volatility(symbol, period)
            if reading:
                structure[period] = reading.annualized
        return structure

    def register_alert_callback(self, callback):
        """Register callback for volatility alerts."""
        self.alert_callbacks.append(callback)


# Singleton instance
_volatility_tracker: Optional[VolatilityTracker] = None


def get_volatility_tracker() -> VolatilityTracker:
    """Get or create the volatility tracker singleton."""
    global _volatility_tracker
    if _volatility_tracker is None:
        _volatility_tracker = VolatilityTracker()
    return _volatility_tracker
