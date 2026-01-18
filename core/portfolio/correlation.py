"""
Portfolio Correlation Matrix

Calculates and maintains correlation matrix between assets.
Used for diversification and avoiding redundant positions.

Prompts #293: Multi-Asset Support and Portfolio Optimization
"""

import logging
import json
import numpy as np
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class CorrelationResult:
    """Result of correlation calculation."""
    matrix: Dict[str, Dict[str, float]]
    assets: List[str]
    calculated_at: datetime = field(default_factory=datetime.now)
    data_points: int = 0


class CorrelationMatrix:
    """
    Calculates and maintains correlation matrix between assets.

    Features:
    - Calculate correlations from price series
    - Daily updates with new data
    - Find low-correlation pairs for diversification
    - Visualization support (heatmap data)
    """

    STORAGE_FILE = Path("data/portfolio/correlation_matrix.json")

    def __init__(
        self,
        lookback_days: int = 30,
        min_data_points: int = 5,
        storage_path: Optional[str] = None
    ):
        """
        Initialize correlation matrix calculator.

        Args:
            lookback_days: Number of days of data to use
            min_data_points: Minimum data points required for correlation
            storage_path: Path to store correlation data
        """
        self.lookback_days = lookback_days
        self.min_data_points = min_data_points
        self.storage_path = Path(storage_path) if storage_path else self.STORAGE_FILE

        # Internal state
        self._price_history: Dict[str, List[float]] = defaultdict(list)
        self._correlation_matrix: Dict[str, Dict[str, float]] = {}
        self._last_calculated: Optional[datetime] = None

        self._load_state()

    def calculate(self, prices: Dict[str, List[float]]) -> Dict[str, Dict[str, float]]:
        """
        Calculate correlation matrix from price series.

        Args:
            prices: Dict mapping asset symbol to list of prices
                    Prices should be in chronological order

        Returns:
            Nested dict of correlations: matrix[asset_a][asset_b] = correlation
        """
        if not prices:
            return {}

        assets = list(prices.keys())
        n_assets = len(assets)

        if n_assets < 2:
            # Single asset or empty - return identity matrix
            return {assets[0]: {assets[0]: 1.0}} if assets else {}

        # Store price history
        for asset, price_list in prices.items():
            self._price_history[asset] = price_list

        # Calculate returns from prices
        returns = {}
        for asset, price_list in prices.items():
            if len(price_list) < 2:
                returns[asset] = []
            else:
                returns[asset] = [
                    (price_list[i] - price_list[i-1]) / price_list[i-1]
                    if price_list[i-1] != 0 else 0
                    for i in range(1, len(price_list))
                ]

        # Build correlation matrix
        matrix: Dict[str, Dict[str, float]] = {}

        for i, asset_a in enumerate(assets):
            matrix[asset_a] = {}
            for j, asset_b in enumerate(assets):
                if i == j:
                    matrix[asset_a][asset_b] = 1.0
                elif j < i:
                    # Use already calculated value (symmetric)
                    matrix[asset_a][asset_b] = matrix[asset_b][asset_a]
                else:
                    # Calculate correlation
                    corr = self._calculate_correlation(
                        returns.get(asset_a, []),
                        returns.get(asset_b, [])
                    )
                    matrix[asset_a][asset_b] = corr

        self._correlation_matrix = matrix
        self._last_calculated = datetime.now()
        self._save_state()

        return matrix

    def _calculate_correlation(
        self,
        returns_a: List[float],
        returns_b: List[float]
    ) -> float:
        """
        Calculate Pearson correlation between two return series.

        Args:
            returns_a: Returns for asset A
            returns_b: Returns for asset B

        Returns:
            Correlation coefficient (-1 to 1), or 0 if insufficient data
        """
        # Align lengths (use shorter)
        min_len = min(len(returns_a), len(returns_b))

        if min_len < self.min_data_points:
            return 0.0

        a = np.array(returns_a[:min_len])
        b = np.array(returns_b[:min_len])

        # Handle constant series
        if np.std(a) == 0 or np.std(b) == 0:
            return 0.0

        # Pearson correlation
        correlation = np.corrcoef(a, b)[0, 1]

        # Handle NaN
        if np.isnan(correlation):
            return 0.0

        return float(correlation)

    def update(
        self,
        new_prices: Dict[str, List[float]],
        append: bool = False
    ) -> Dict[str, Dict[str, float]]:
        """
        Update correlation matrix with new price data.

        Args:
            new_prices: New price data for assets
            append: If True, append to existing history; else replace

        Returns:
            Updated correlation matrix
        """
        if append:
            for asset, prices in new_prices.items():
                self._price_history[asset].extend(prices)
                # Trim to lookback period
                max_points = self.lookback_days * 24  # Assuming hourly data max
                if len(self._price_history[asset]) > max_points:
                    self._price_history[asset] = self._price_history[asset][-max_points:]

            return self.calculate(dict(self._price_history))
        else:
            return self.calculate(new_prices)

    def get_matrix(self) -> Dict[str, Dict[str, float]]:
        """Get the current correlation matrix."""
        return self._correlation_matrix

    def get_correlation(self, asset_a: str, asset_b: str) -> float:
        """
        Get correlation between two specific assets.

        Args:
            asset_a: First asset symbol
            asset_b: Second asset symbol

        Returns:
            Correlation coefficient, or 0 if not found
        """
        if asset_a in self._correlation_matrix:
            return self._correlation_matrix[asset_a].get(asset_b, 0.0)
        return 0.0

    def get_low_correlation_pairs(
        self,
        threshold: float = 0.7
    ) -> List[Tuple[str, str, float]]:
        """
        Find asset pairs with correlation below threshold.

        Good for diversification - pairs that don't move together.

        Args:
            threshold: Maximum correlation to include

        Returns:
            List of (asset_a, asset_b, correlation) tuples
        """
        pairs = []
        assets = list(self._correlation_matrix.keys())

        for i, asset_a in enumerate(assets):
            for j, asset_b in enumerate(assets):
                if j > i:  # Avoid duplicates
                    corr = abs(self._correlation_matrix[asset_a].get(asset_b, 0))
                    if corr < threshold:
                        pairs.append((asset_a, asset_b, corr))

        # Sort by correlation (lowest first = best for diversification)
        pairs.sort(key=lambda x: x[2])

        return pairs

    def get_high_correlation_pairs(
        self,
        threshold: float = 0.7
    ) -> List[Tuple[str, str, float]]:
        """
        Find asset pairs with correlation above threshold.

        Warns against holding redundant positions.

        Args:
            threshold: Minimum correlation to include

        Returns:
            List of (asset_a, asset_b, correlation) tuples
        """
        pairs = []
        assets = list(self._correlation_matrix.keys())

        for i, asset_a in enumerate(assets):
            for j, asset_b in enumerate(assets):
                if j > i:  # Avoid duplicates and self-correlation
                    corr = self._correlation_matrix[asset_a].get(asset_b, 0)
                    if abs(corr) >= threshold:
                        pairs.append((asset_a, asset_b, corr))

        # Sort by correlation (highest first)
        pairs.sort(key=lambda x: abs(x[2]), reverse=True)

        return pairs

    def get_heatmap_data(self) -> Dict[str, Any]:
        """
        Get data formatted for heatmap visualization.

        Returns:
            Dict with assets, matrix values, and metadata
        """
        assets = list(self._correlation_matrix.keys())

        # Build 2D array
        values = []
        for asset_a in assets:
            row = []
            for asset_b in assets:
                row.append(self._correlation_matrix.get(asset_a, {}).get(asset_b, 0))
            values.append(row)

        return {
            'assets': assets,
            'values': values,
            'min_correlation': min(min(row) for row in values) if values else 0,
            'max_correlation': max(max(row) for row in values) if values else 1,
            'calculated_at': self._last_calculated.isoformat() if self._last_calculated else None
        }

    def _save_state(self):
        """Save correlation state to disk."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                'correlation_matrix': self._correlation_matrix,
                'price_history': dict(self._price_history),
                'last_calculated': self._last_calculated.isoformat() if self._last_calculated else None,
                'saved_at': datetime.now().isoformat()
            }

            with open(self.storage_path, 'w') as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save correlation state: {e}")

    def _load_state(self):
        """Load correlation state from disk."""
        if not self.storage_path.exists():
            return

        try:
            with open(self.storage_path) as f:
                data = json.load(f)

            self._correlation_matrix = data.get('correlation_matrix', {})
            self._price_history = defaultdict(list, data.get('price_history', {}))

            last_calc = data.get('last_calculated')
            if last_calc:
                self._last_calculated = datetime.fromisoformat(last_calc)

            logger.info(f"Loaded correlation matrix for {len(self._correlation_matrix)} assets")

        except Exception as e:
            logger.error(f"Failed to load correlation state: {e}")


# Singleton instance
_correlation_matrix: Optional[CorrelationMatrix] = None


def get_correlation_matrix() -> CorrelationMatrix:
    """Get correlation matrix singleton."""
    global _correlation_matrix

    if _correlation_matrix is None:
        _correlation_matrix = CorrelationMatrix()

    return _correlation_matrix


# Testing
if __name__ == "__main__":
    # Example usage
    cm = CorrelationMatrix()

    # Sample prices
    prices = {
        'SOL': [100, 110, 105, 115, 120, 118, 125],
        'ETH': [3000, 3100, 3050, 3150, 3200, 3180, 3250],
        'BTC': [40000, 41000, 40500, 41500, 42000, 41800, 42500],
        'BONK': [0.001, 0.0015, 0.0012, 0.0018, 0.0014, 0.0020, 0.0016],
    }

    matrix = cm.calculate(prices)

    print("Correlation Matrix:")
    for asset_a in matrix:
        print(f"\n{asset_a}:")
        for asset_b, corr in matrix[asset_a].items():
            print(f"  {asset_b}: {corr:.3f}")

    print("\nLow correlation pairs (< 0.7):")
    for a, b, corr in cm.get_low_correlation_pairs(0.7):
        print(f"  {a} - {b}: {corr:.3f}")

    print("\nHigh correlation pairs (> 0.7):")
    for a, b, corr in cm.get_high_correlation_pairs(0.7):
        print(f"  {a} - {b}: {corr:.3f}")
