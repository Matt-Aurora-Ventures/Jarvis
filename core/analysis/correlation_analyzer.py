"""
Correlation Analyzer - Advanced correlation analysis for trading portfolios.

Provides:
- Pairwise correlation calculation with statistical significance
- Rolling correlation windows for regime detection
- Correlation matrix and heatmap generation
- Correlation breakdown detection for risk management
- Lead/lag relationship analysis
- Portfolio diversification scoring

Usage:
    from core.analysis.correlation_analyzer import CorrelationAnalyzer

    analyzer = CorrelationAnalyzer()

    # Calculate correlation matrix
    price_data = {
        "BTC": [100, 110, 105, 115, 120],
        "ETH": [10, 11, 10.5, 11.5, 12],
        "SOL": [1, 1.1, 1.05, 1.15, 1.2]
    }
    matrix = analyzer.calculate_correlation_matrix(price_data)

    # Detect correlation breakdown
    rolling = analyzer.calculate_rolling_correlation(prices_a, prices_b, window=20)
    breakdowns = analyzer.detect_correlation_breakdown(rolling, threshold=0.3)

    # Analyze portfolio diversification
    holdings = {"BTC": 0.4, "ETH": 0.3, "SOL": 0.3}
    result = analyzer.analyze_diversification(price_data, holdings)
"""

import math
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any, Union
from enum import Enum

logger = logging.getLogger(__name__)


@dataclass
class CorrelationResult:
    """Result of a correlation calculation between two assets."""

    asset_a: str
    asset_b: str
    correlation: float
    sample_size: int
    p_value: float = 1.0
    confidence_interval: Optional[Tuple[float, float]] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def is_significant(self, alpha: float = 0.05) -> bool:
        """Check if correlation is statistically significant."""
        return self.p_value < alpha


@dataclass
class BreakdownEvent:
    """Event indicating a correlation breakdown."""

    index: int
    previous_correlation: float
    current_correlation: float
    change: float
    timestamp: Optional[str] = None

    @property
    def is_breakdown(self) -> bool:
        """True if this represents a significant breakdown."""
        return abs(self.change) > 0.3


@dataclass
class LeadLagResult:
    """Result of lead/lag analysis between two assets."""

    leader: str
    follower: str
    lag_periods: int
    correlation: float
    confidence: float


class CorrelationAnalyzer:
    """
    Advanced correlation analysis for trading portfolios.

    Supports:
    - Pearson correlation calculation
    - Rolling window correlations
    - Correlation matrix generation
    - Breakdown detection
    - Lead/lag analysis
    - Diversification scoring
    """

    def __init__(self, min_sample_size: int = 5):
        """
        Initialize the correlation analyzer.

        Args:
            min_sample_size: Minimum number of samples required for correlation
        """
        self.min_sample_size = min_sample_size

    def pearson_correlation(self, x: List[float], y: List[float]) -> float:
        """
        Calculate Pearson correlation coefficient between two series.

        Args:
            x: First series of values
            y: Second series of values

        Returns:
            Correlation coefficient between -1 and 1, or 0 if calculation fails
        """
        n = min(len(x), len(y))

        if n < 2:
            return 0.0

        # Truncate to same length
        x = x[:n]
        y = y[:n]

        # Filter out NaN and Inf values
        valid_pairs = [
            (xi, yi) for xi, yi in zip(x, y)
            if self._is_valid_number(xi) and self._is_valid_number(yi)
        ]

        if len(valid_pairs) < 2:
            return 0.0

        x = [p[0] for p in valid_pairs]
        y = [p[1] for p in valid_pairs]
        n = len(x)

        # Calculate means
        mean_x = sum(x) / n
        mean_y = sum(y) / n

        # Calculate covariance and standard deviations
        numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
        denominator_x = math.sqrt(sum((xi - mean_x) ** 2 for xi in x))
        denominator_y = math.sqrt(sum((yi - mean_y) ** 2 for yi in y))

        # Handle zero variance (constant series)
        if denominator_x == 0 or denominator_y == 0:
            return 0.0

        correlation = numerator / (denominator_x * denominator_y)

        # Clamp to valid range due to floating point errors
        return max(-1.0, min(1.0, correlation))

    def calculate_returns(self, prices: List[float]) -> List[float]:
        """
        Calculate percentage returns from a price series.

        Args:
            prices: List of prices

        Returns:
            List of returns (one fewer than prices)
        """
        if len(prices) < 2:
            return []

        returns = []
        for i in range(1, len(prices)):
            prev = prices[i - 1]
            curr = prices[i]

            # Skip invalid values
            if not self._is_valid_number(prev) or not self._is_valid_number(curr):
                continue

            # Skip division by zero
            if prev == 0:
                continue

            ret = (curr - prev) / prev
            if self._is_valid_number(ret):
                returns.append(ret)

        return returns

    def calculate_correlation_matrix(
        self,
        price_data: Dict[str, List[float]]
    ) -> Dict[str, Dict[str, float]]:
        """
        Calculate correlation matrix for multiple assets.

        Args:
            price_data: Dictionary of asset -> price series

        Returns:
            Nested dictionary with correlations: matrix[asset_a][asset_b]
        """
        if not price_data:
            return {}

        assets = list(price_data.keys())
        matrix = {asset: {} for asset in assets}

        # Calculate returns for all assets
        returns_data = {}
        for asset, prices in price_data.items():
            returns_data[asset] = self.calculate_returns(prices)

        # Fill the matrix
        for i, asset_a in enumerate(assets):
            # Diagonal is always 1.0
            matrix[asset_a][asset_a] = 1.0

            for asset_b in assets[i + 1:]:
                returns_a = returns_data[asset_a]
                returns_b = returns_data[asset_b]

                # Calculate correlation
                corr = self.pearson_correlation(returns_a, returns_b)

                # Symmetric matrix
                matrix[asset_a][asset_b] = corr
                matrix[asset_b][asset_a] = corr

        return matrix

    def calculate_rolling_correlation(
        self,
        prices_a: List[float],
        prices_b: List[float],
        window: int = 20
    ) -> List[float]:
        """
        Calculate rolling window correlation between two price series.

        Args:
            prices_a: First price series
            prices_b: Second price series
            window: Size of rolling window

        Returns:
            List of correlation values for each window
        """
        n = min(len(prices_a), len(prices_b))

        if n < window:
            return []

        # Calculate returns first
        returns_a = self.calculate_returns(prices_a[:n])
        returns_b = self.calculate_returns(prices_b[:n])

        # Now calculate rolling correlation on returns
        n_returns = min(len(returns_a), len(returns_b))

        if n_returns < window:
            return []

        rolling_correlations = []

        for i in range(n_returns - window + 1):
            window_a = returns_a[i:i + window]
            window_b = returns_b[i:i + window]

            corr = self.pearson_correlation(window_a, window_b)
            rolling_correlations.append(corr)

        return rolling_correlations

    def detect_correlation_breakdown(
        self,
        rolling_correlations: List[float],
        threshold: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        Detect significant changes in correlation over time.

        Args:
            rolling_correlations: Time series of correlation values
            threshold: Minimum change to be considered a breakdown

        Returns:
            List of breakdown events with index, previous/current values, and change
        """
        if len(rolling_correlations) < 2:
            return []

        breakdowns = []

        for i in range(1, len(rolling_correlations)):
            prev = rolling_correlations[i - 1]
            curr = rolling_correlations[i]

            change = curr - prev

            if abs(change) >= threshold:
                breakdowns.append({
                    "index": i,
                    "previous_correlation": prev,
                    "current_correlation": curr,
                    "change": change
                })

        return breakdowns

    def detect_lead_lag(
        self,
        prices_a: List[float],
        prices_b: List[float],
        max_lag: int = 10
    ) -> Optional[Dict[str, Any]]:
        """
        Detect lead/lag relationship between two price series.

        Args:
            prices_a: First price series (labeled as "A")
            prices_b: Second price series (labeled as "B")
            max_lag: Maximum lag to test in each direction

        Returns:
            Dictionary with leader, follower, lag_periods, correlation, confidence
            or None if insufficient data
        """
        n = min(len(prices_a), len(prices_b))

        if n < max_lag * 2 + 5:
            return None

        returns_a = self.calculate_returns(prices_a[:n])
        returns_b = self.calculate_returns(prices_b[:n])

        n_returns = min(len(returns_a), len(returns_b))

        if n_returns < max_lag * 2:
            return None

        best_correlation = 0.0
        best_lag = 0

        # Test different lag values
        for lag in range(-max_lag, max_lag + 1):
            if lag == 0:
                corr = self.pearson_correlation(returns_a, returns_b)
            elif lag > 0:
                # A leads B: compare A[:-lag] with B[lag:]
                if len(returns_a) > lag and len(returns_b) > lag:
                    corr = self.pearson_correlation(
                        returns_a[:-lag],
                        returns_b[lag:]
                    )
                else:
                    continue
            else:
                # B leads A: compare A[-lag:] with B[:lag]
                abs_lag = abs(lag)
                if len(returns_a) > abs_lag and len(returns_b) > abs_lag:
                    corr = self.pearson_correlation(
                        returns_a[abs_lag:],
                        returns_b[:-abs_lag]
                    )
                else:
                    continue

            if abs(corr) > abs(best_correlation):
                best_correlation = corr
                best_lag = lag

        # Determine leader/follower
        if best_lag > 0:
            leader = "A"
            follower = "B"
            lag_periods = best_lag
        elif best_lag < 0:
            leader = "B"
            follower = "A"
            lag_periods = abs(best_lag)
        else:
            leader = "A"  # Arbitrary when synchronous
            follower = "B"
            lag_periods = 0

        return {
            "leader": leader,
            "follower": follower,
            "lag_periods": lag_periods,
            "correlation": best_correlation,
            "confidence": abs(best_correlation)
        }

    def generate_heatmap_data(
        self,
        price_data: Dict[str, List[float]]
    ) -> Dict[str, Any]:
        """
        Generate data suitable for heatmap visualization.

        Args:
            price_data: Dictionary of asset -> price series

        Returns:
            Dictionary with 'assets', 'matrix' (2D list), and 'values' (flat list)
        """
        if not price_data:
            return {"assets": [], "matrix": [], "values": []}

        assets = sorted(price_data.keys())
        corr_matrix = self.calculate_correlation_matrix(price_data)

        # Convert to 2D list
        matrix = []
        values = []

        for asset_a in assets:
            row = []
            for asset_b in assets:
                corr = corr_matrix.get(asset_a, {}).get(asset_b, 0.0)
                row.append(corr)
                values.append({
                    "x": asset_a,
                    "y": asset_b,
                    "value": corr
                })
            matrix.append(row)

        return {
            "assets": assets,
            "matrix": matrix,
            "values": values
        }

    def analyze_diversification(
        self,
        price_data: Dict[str, List[float]],
        holdings: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Analyze portfolio diversification based on correlations.

        Args:
            price_data: Dictionary of asset -> price series
            holdings: Dictionary of asset -> allocation weight (0-1)

        Returns:
            Dictionary with score, avg_correlation, highly_correlated_pairs, recommendation
        """
        assets = list(holdings.keys())

        if len(assets) < 2:
            return {
                "score": 100.0,
                "avg_correlation": 0.0,
                "highly_correlated_pairs": [],
                "recommendation": "Single asset - consider diversifying"
            }

        # Calculate correlation matrix
        matrix = self.calculate_correlation_matrix(price_data)

        # Calculate weighted average correlation
        total_weight = 0.0
        weighted_corr = 0.0
        highly_correlated = []

        for i, asset_a in enumerate(assets):
            for asset_b in assets[i + 1:]:
                corr = matrix.get(asset_a, {}).get(asset_b, 0.0)
                weight = holdings.get(asset_a, 0) * holdings.get(asset_b, 0)

                weighted_corr += abs(corr) * weight
                total_weight += weight

                if abs(corr) > 0.7:
                    highly_correlated.append({
                        "pair": f"{asset_a}/{asset_b}",
                        "correlation": corr,
                        "combined_allocation": holdings.get(asset_a, 0) + holdings.get(asset_b, 0)
                    })

        avg_corr = weighted_corr / total_weight if total_weight > 0 else 0.0

        # Score: 100 = perfectly uncorrelated, 0 = perfectly correlated
        score = (1 - avg_corr) * 100

        return {
            "score": round(score, 1),
            "avg_correlation": round(avg_corr, 3),
            "highly_correlated_pairs": highly_correlated,
            "recommendation": self._get_diversification_recommendation(score)
        }

    def find_correlated_pairs(
        self,
        price_data: Dict[str, List[float]],
        min_correlation: float = 0.7,
        include_negative: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Find pairs of assets with correlation above threshold.

        Uses price-level correlation to better detect inverse trending pairs.

        Args:
            price_data: Dictionary of asset -> price series
            min_correlation: Minimum absolute correlation to include
            include_negative: Include negatively correlated pairs

        Returns:
            List of pairs with asset_a, asset_b, correlation
        """
        assets = list(price_data.keys())
        pairs: List[Dict[str, Any]] = []

        for i, asset_a in enumerate(assets):
            series_a = price_data.get(asset_a, [])
            for asset_b in assets[i + 1:]:
                series_b = price_data.get(asset_b, [])
                corr = self.pearson_correlation(series_a, series_b)

                if include_negative:
                    if abs(corr) >= min_correlation:
                        pairs.append({
                            "asset_a": asset_a,
                            "asset_b": asset_b,
                            "correlation": corr
                        })
                else:
                    if corr >= min_correlation:
                        pairs.append({
                            "asset_a": asset_a,
                            "asset_b": asset_b,
                            "correlation": corr
                        })

        # Sort by absolute correlation descending
        pairs.sort(key=lambda x: abs(x["correlation"]), reverse=True)

        return pairs

    def correlation_with_significance(
        self,
        x: List[float],
        y: List[float]
    ) -> Tuple[float, float]:
        """
        Calculate correlation with statistical significance (p-value).

        Uses t-test for correlation coefficient.

        Args:
            x: First series
            y: Second series

        Returns:
            Tuple of (correlation, p_value)
        """
        n = min(len(x), len(y))

        if n < 3:
            return (0.0, 1.0)

        corr = self.pearson_correlation(x[:n], y[:n])

        # Calculate t-statistic
        if abs(corr) >= 1.0:
            # Perfect correlation - highly significant
            return (corr, 0.0)

        try:
            t_stat = corr * math.sqrt((n - 2) / (1 - corr ** 2))
        except (ZeroDivisionError, ValueError):
            return (corr, 1.0)

        # Approximate p-value using t-distribution
        # For simplicity, use a normal approximation for large n
        p_value = self._t_distribution_p_value(abs(t_stat), n - 2)

        return (corr, p_value)

    def _t_distribution_p_value(self, t: float, df: int) -> float:
        """
        Approximate two-tailed p-value from t-distribution.

        Uses a simple approximation for large degrees of freedom.
        """
        if df <= 0:
            return 1.0

        # For large df, t-distribution approaches normal
        # Use a simple approximation
        if df > 30:
            # Normal approximation
            return 2 * (1 - self._normal_cdf(abs(t)))

        # For smaller df, use a rougher approximation
        # This is not exact but gives reasonable estimates
        z = t * (1 - 1 / (4 * df)) / math.sqrt(1 + t ** 2 / (2 * df))
        return 2 * (1 - self._normal_cdf(abs(z)))

    def _normal_cdf(self, x: float) -> float:
        """
        Approximate cumulative distribution function for standard normal.

        Uses the error function approximation.
        """
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    def _get_diversification_recommendation(self, score: float) -> str:
        """Generate recommendation based on diversification score."""
        if score >= 80:
            return "Excellent diversification - portfolio is well balanced"
        elif score >= 60:
            return "Good diversification - minor improvements possible"
        elif score >= 40:
            return "Moderate correlation risk - consider reducing correlated positions"
        elif score >= 20:
            return "High correlation risk - portfolio may move together"
        else:
            return "Very high correlation - consider diversifying into uncorrelated assets"

    def _is_valid_number(self, x: float) -> bool:
        """Check if a number is valid (not NaN or Inf)."""
        if x is None:
            return False
        try:
            return math.isfinite(x)
        except (TypeError, ValueError):
            return False


# Singleton instance
_analyzer: Optional[CorrelationAnalyzer] = None


def get_correlation_analyzer() -> CorrelationAnalyzer:
    """Get singleton correlation analyzer instance."""
    global _analyzer
    if _analyzer is None:
        _analyzer = CorrelationAnalyzer()
    return _analyzer
