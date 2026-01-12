"""
Correlation Tracker - Track correlations between assets and market indicators.
"""

import math
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict
from pathlib import Path
import json
import sqlite3
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@dataclass
class PricePoint:
    """A single price observation."""
    timestamp: str
    symbol: str
    price: float
    volume: float = 0.0


@dataclass
class CorrelationResult:
    """Correlation between two assets."""
    asset_a: str
    asset_b: str
    correlation: float  # -1 to 1
    sample_size: int
    period_days: int
    p_value: float = 0.0
    last_updated: str = ""


@dataclass
class LeadLagResult:
    """Lead-lag relationship between assets."""
    leader: str
    follower: str
    lag_periods: int
    correlation: float
    confidence: float


class CorrelationDB:
    """SQLite storage for price history."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    price REAL NOT NULL,
                    volume REAL DEFAULT 0,
                    source TEXT DEFAULT 'unknown'
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS correlations (
                    asset_a TEXT,
                    asset_b TEXT,
                    correlation REAL,
                    sample_size INTEGER,
                    period_days INTEGER,
                    last_updated TEXT,
                    PRIMARY KEY (asset_a, asset_b, period_days)
                )
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_prices_symbol ON price_history(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_prices_timestamp ON price_history(timestamp)")

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

    def record_price(self, symbol: str, price: float, volume: float = 0, source: str = ""):
        """Record a price observation."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO price_history (timestamp, symbol, price, volume, source)
                VALUES (?, ?, ?, ?, ?)
            """, (
                datetime.now(timezone.utc).isoformat(),
                symbol.upper(),
                price,
                volume,
                source
            ))
            conn.commit()

    def get_prices(
        self,
        symbol: str,
        days: int = 30,
        interval: str = "hourly"
    ) -> List[PricePoint]:
        """Get price history for a symbol."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # For hourly, take the last price of each hour
            if interval == "hourly":
                cursor.execute("""
                    SELECT timestamp, symbol, price, volume
                    FROM price_history
                    WHERE symbol = ?
                    AND datetime(timestamp) > datetime('now', ?)
                    GROUP BY strftime('%Y-%m-%d %H', timestamp)
                    ORDER BY timestamp ASC
                """, (symbol.upper(), f'-{days} days'))
            else:  # daily
                cursor.execute("""
                    SELECT timestamp, symbol, price, volume
                    FROM price_history
                    WHERE symbol = ?
                    AND datetime(timestamp) > datetime('now', ?)
                    GROUP BY date(timestamp)
                    ORDER BY timestamp ASC
                """, (symbol.upper(), f'-{days} days'))

            return [
                PricePoint(
                    timestamp=row['timestamp'],
                    symbol=row['symbol'],
                    price=row['price'],
                    volume=row['volume']
                )
                for row in cursor.fetchall()
            ]

    def save_correlation(self, result: CorrelationResult):
        """Save correlation result."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO correlations
                (asset_a, asset_b, correlation, sample_size, period_days, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                result.asset_a, result.asset_b, result.correlation,
                result.sample_size, result.period_days, result.last_updated
            ))
            conn.commit()

    def get_correlations(self, asset: str = None, period_days: int = 30) -> List[CorrelationResult]:
        """Get stored correlations."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            if asset:
                cursor.execute("""
                    SELECT * FROM correlations
                    WHERE (asset_a = ? OR asset_b = ?)
                    AND period_days = ?
                    ORDER BY ABS(correlation) DESC
                """, (asset, asset, period_days))
            else:
                cursor.execute("""
                    SELECT * FROM correlations
                    WHERE period_days = ?
                    ORDER BY ABS(correlation) DESC
                """, (period_days,))

            return [
                CorrelationResult(
                    asset_a=row['asset_a'],
                    asset_b=row['asset_b'],
                    correlation=row['correlation'],
                    sample_size=row['sample_size'],
                    period_days=row['period_days'],
                    last_updated=row['last_updated']
                )
                for row in cursor.fetchall()
            ]


class CorrelationTracker:
    """
    Track and analyze correlations between assets.

    Usage:
        tracker = CorrelationTracker()

        # Record prices
        tracker.record_price("BTC", 50000)
        tracker.record_price("ETH", 3000)
        tracker.record_price("SOL", 100)

        # Calculate correlations
        corr = tracker.calculate_correlation("BTC", "ETH", days=30)
        print(f"BTC-ETH correlation: {corr.correlation}")

        # Find correlated assets
        related = tracker.find_correlated_assets("BTC", min_correlation=0.7)
    """

    def __init__(self, db_path: Optional[Path] = None):
        db_path = db_path or Path(__file__).parent.parent / "data" / "correlations.db"
        self.db = CorrelationDB(db_path)
        self._price_cache: Dict[str, List[float]] = defaultdict(list)

    def record_price(self, symbol: str, price: float, volume: float = 0, source: str = ""):
        """Record a price observation."""
        self.db.record_price(symbol, price, volume, source)
        self._price_cache[symbol.upper()].append(price)

    def calculate_correlation(
        self,
        asset_a: str,
        asset_b: str,
        days: int = 30
    ) -> Optional[CorrelationResult]:
        """Calculate Pearson correlation between two assets."""
        prices_a = self.db.get_prices(asset_a, days)
        prices_b = self.db.get_prices(asset_b, days)

        if len(prices_a) < 10 or len(prices_b) < 10:
            return None

        # Align time series
        returns_a = self._calculate_returns([p.price for p in prices_a])
        returns_b = self._calculate_returns([p.price for p in prices_b])

        # Use the shorter length
        min_len = min(len(returns_a), len(returns_b))
        returns_a = returns_a[:min_len]
        returns_b = returns_b[:min_len]

        if min_len < 5:
            return None

        # Calculate Pearson correlation
        correlation = self._pearson_correlation(returns_a, returns_b)

        result = CorrelationResult(
            asset_a=asset_a.upper(),
            asset_b=asset_b.upper(),
            correlation=correlation,
            sample_size=min_len,
            period_days=days,
            last_updated=datetime.now(timezone.utc).isoformat()
        )

        self.db.save_correlation(result)
        return result

    def _calculate_returns(self, prices: List[float]) -> List[float]:
        """Calculate percentage returns from prices."""
        if len(prices) < 2:
            return []

        returns = []
        for i in range(1, len(prices)):
            if prices[i-1] != 0:
                ret = (prices[i] - prices[i-1]) / prices[i-1]
                returns.append(ret)

        return returns

    def _pearson_correlation(self, x: List[float], y: List[float]) -> float:
        """Calculate Pearson correlation coefficient."""
        n = len(x)
        if n == 0:
            return 0.0

        mean_x = sum(x) / n
        mean_y = sum(y) / n

        numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
        denominator_x = math.sqrt(sum((x[i] - mean_x) ** 2 for i in range(n)))
        denominator_y = math.sqrt(sum((y[i] - mean_y) ** 2 for i in range(n)))

        if denominator_x * denominator_y == 0:
            return 0.0

        return numerator / (denominator_x * denominator_y)

    def find_correlated_assets(
        self,
        asset: str,
        min_correlation: float = 0.5,
        days: int = 30
    ) -> List[CorrelationResult]:
        """Find assets correlated with a given asset."""
        correlations = self.db.get_correlations(asset, days)

        return [
            c for c in correlations
            if abs(c.correlation) >= min_correlation
        ]

    def calculate_all_correlations(
        self,
        assets: List[str],
        days: int = 30
    ) -> Dict[Tuple[str, str], float]:
        """Calculate correlation matrix for all asset pairs."""
        results = {}

        for i, asset_a in enumerate(assets):
            for asset_b in assets[i+1:]:
                result = self.calculate_correlation(asset_a, asset_b, days)
                if result:
                    results[(asset_a, asset_b)] = result.correlation

        return results

    def detect_lead_lag(
        self,
        asset_a: str,
        asset_b: str,
        max_lag: int = 24,
        days: int = 30
    ) -> Optional[LeadLagResult]:
        """Detect lead-lag relationship between assets."""
        prices_a = self.db.get_prices(asset_a, days, interval="hourly")
        prices_b = self.db.get_prices(asset_b, days, interval="hourly")

        if len(prices_a) < max_lag * 2 or len(prices_b) < max_lag * 2:
            return None

        returns_a = self._calculate_returns([p.price for p in prices_a])
        returns_b = self._calculate_returns([p.price for p in prices_b])

        min_len = min(len(returns_a), len(returns_b))
        returns_a = returns_a[:min_len]
        returns_b = returns_b[:min_len]

        best_correlation = 0.0
        best_lag = 0

        # Test different lags
        for lag in range(-max_lag, max_lag + 1):
            if lag == 0:
                corr = self._pearson_correlation(returns_a, returns_b)
            elif lag > 0:
                # a leads b
                corr = self._pearson_correlation(
                    returns_a[:-lag],
                    returns_b[lag:]
                )
            else:
                # b leads a
                corr = self._pearson_correlation(
                    returns_a[-lag:],
                    returns_b[:lag]
                )

            if abs(corr) > abs(best_correlation):
                best_correlation = corr
                best_lag = lag

        if best_lag > 0:
            leader, follower = asset_a, asset_b
        else:
            leader, follower = asset_b, asset_a
            best_lag = abs(best_lag)

        return LeadLagResult(
            leader=leader,
            follower=follower,
            lag_periods=best_lag,
            correlation=best_correlation,
            confidence=abs(best_correlation)  # Simplified confidence
        )

    def get_correlation_matrix(
        self,
        assets: List[str],
        days: int = 30
    ) -> Dict[str, Dict[str, float]]:
        """Get correlation matrix as nested dict."""
        matrix = {a: {} for a in assets}

        for i, asset_a in enumerate(assets):
            matrix[asset_a][asset_a] = 1.0

            for asset_b in assets[i+1:]:
                result = self.calculate_correlation(asset_a, asset_b, days)
                corr = result.correlation if result else 0.0

                matrix[asset_a][asset_b] = corr
                matrix[asset_b][asset_a] = corr

        return matrix

    def get_diversification_score(
        self,
        holdings: Dict[str, float],
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Calculate portfolio diversification score.

        Args:
            holdings: Dict of asset -> allocation percentage

        Returns:
            Diversification metrics
        """
        assets = list(holdings.keys())
        if len(assets) < 2:
            return {
                'score': 100.0,
                'avg_correlation': 0.0,
                'highly_correlated_pairs': []
            }

        # Get correlation matrix
        correlations = self.calculate_all_correlations(assets, days)

        if not correlations:
            return {
                'score': 50.0,
                'avg_correlation': 0.0,
                'highly_correlated_pairs': [],
                'note': 'Insufficient data for correlation analysis'
            }

        # Calculate weighted average correlation
        total_weight = 0.0
        weighted_corr = 0.0
        highly_correlated = []

        for (a, b), corr in correlations.items():
            weight = holdings[a] * holdings[b]
            weighted_corr += abs(corr) * weight
            total_weight += weight

            if abs(corr) > 0.7:
                highly_correlated.append({
                    'pair': f"{a}/{b}",
                    'correlation': corr,
                    'combined_allocation': holdings[a] + holdings[b]
                })

        avg_corr = weighted_corr / total_weight if total_weight > 0 else 0.0

        # Score: 100 = perfectly diversified (0 correlation), 0 = fully correlated
        score = (1 - avg_corr) * 100

        return {
            'score': round(score, 1),
            'avg_correlation': round(avg_corr, 3),
            'highly_correlated_pairs': highly_correlated,
            'recommendation': self._get_diversification_recommendation(score)
        }

    def _get_diversification_recommendation(self, score: float) -> str:
        """Get recommendation based on diversification score."""
        if score >= 80:
            return "Excellent diversification"
        elif score >= 60:
            return "Good diversification, minor improvements possible"
        elif score >= 40:
            return "Moderate correlation risk - consider reducing correlated positions"
        elif score >= 20:
            return "High correlation risk - portfolio may move together"
        else:
            return "Very high correlation - consider diversifying into uncorrelated assets"


# Singleton
_tracker: Optional[CorrelationTracker] = None

def get_correlation_tracker() -> CorrelationTracker:
    """Get singleton correlation tracker."""
    global _tracker
    if _tracker is None:
        _tracker = CorrelationTracker()
    return _tracker
