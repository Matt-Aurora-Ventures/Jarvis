"""
Portfolio Optimizer

Implements Markowitz efficient frontier optimization.
Finds optimal asset allocation for target return with minimum risk.

Prompts #293: Multi-Asset Support and Portfolio Optimization
"""

import logging
import numpy as np
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
from scipy.optimize import minimize

logger = logging.getLogger(__name__)


@dataclass
class OptimizationResult:
    """Result of portfolio optimization."""
    weights: Dict[str, float]
    expected_return: float
    volatility: float
    sharpe_ratio: float
    assets_used: List[str]
    optimized_at: datetime = field(default_factory=datetime.now)


@dataclass
class FrontierPoint:
    """A point on the efficient frontier."""
    return_: float
    risk: float
    weights: Dict[str, float]
    sharpe_ratio: float


class PortfolioOptimizer:
    """
    Markowitz Mean-Variance Portfolio Optimizer.

    Features:
    - Efficient frontier calculation
    - Maximum assets constraint
    - Correlation-based filtering
    - Equal weight and risk parity allocation
    - Sector diversification constraints
    """

    def __init__(
        self,
        risk_free_rate: float = 0.05,
        max_assets: int = 10,
        max_correlation: float = 0.7,
        max_sector_allocation: float = 0.50,
        min_weight: float = 0.01,
    ):
        """
        Initialize portfolio optimizer.

        Args:
            risk_free_rate: Annual risk-free rate for Sharpe calculation
            max_assets: Maximum number of assets in portfolio
            max_correlation: Maximum allowed correlation between holdings
            max_sector_allocation: Maximum allocation to any single sector
            min_weight: Minimum meaningful weight (below this = 0)
        """
        self.risk_free_rate = risk_free_rate
        self.max_assets = max_assets
        self.max_correlation = max_correlation
        self.max_sector_allocation = max_sector_allocation
        self.min_weight = min_weight

    def optimize(
        self,
        returns: Dict[str, List[float]],
        target_return: Optional[float] = None,
        correlation_matrix: Optional[Dict[str, Dict[str, float]]] = None
    ) -> Dict[str, float]:
        """
        Find optimal portfolio weights for target return.

        Args:
            returns: Dict mapping asset to list of historical returns
            target_return: Target annualized return (if None, maximize Sharpe)
            correlation_matrix: Pre-computed correlation matrix (optional)

        Returns:
            Dict mapping asset to optimal weight (sums to 1.0)
        """
        if not returns:
            return {}

        assets = list(returns.keys())
        n_assets = len(assets)

        if n_assets == 0:
            return {}

        if n_assets == 1:
            return {assets[0]: 1.0}

        # Filter correlated assets if correlation matrix provided
        if correlation_matrix:
            assets = self._filter_correlated_assets(assets, correlation_matrix)
            returns = {k: v for k, v in returns.items() if k in assets}

        if not returns:
            return {}

        # Limit to max_assets (select by Sharpe ratio)
        if len(assets) > self.max_assets:
            assets = self._select_top_assets(returns, self.max_assets)
            returns = {k: v for k, v in returns.items() if k in assets}

        # Build numpy arrays
        assets = list(returns.keys())
        n_assets = len(assets)

        # Align return lengths
        min_len = min(len(r) for r in returns.values())
        if min_len < 2:
            # Equal weights if insufficient data
            return {a: 1.0 / n_assets for a in assets}

        returns_matrix = np.array([returns[a][:min_len] for a in assets])

        # Calculate expected returns and covariance
        mean_returns = np.mean(returns_matrix, axis=1) * 252  # Annualize
        cov_matrix = np.cov(returns_matrix) * 252  # Annualize

        # Handle 1D covariance for 1 asset
        if n_assets == 1:
            return {assets[0]: 1.0}

        # Optimization
        if target_return is not None:
            weights = self._minimize_variance_for_target(
                mean_returns, cov_matrix, target_return
            )
        else:
            weights = self._maximize_sharpe(mean_returns, cov_matrix)

        # Convert to dict and apply minimum weight threshold
        result = {}
        for i, asset in enumerate(assets):
            w = weights[i] if i < len(weights) else 0
            if w >= self.min_weight:
                result[asset] = float(w)

        # Normalize to sum to 1
        total = sum(result.values())
        if total > 0:
            result = {k: v / total for k, v in result.items()}
        else:
            # Fallback to equal weights
            result = {a: 1.0 / n_assets for a in assets}

        return result

    def _minimize_variance_for_target(
        self,
        mean_returns: np.ndarray,
        cov_matrix: np.ndarray,
        target_return: float
    ) -> np.ndarray:
        """
        Minimize portfolio variance for a target return.

        Args:
            mean_returns: Array of expected returns
            cov_matrix: Covariance matrix
            target_return: Target annualized return

        Returns:
            Array of optimal weights
        """
        n_assets = len(mean_returns)

        # Initial guess: equal weights
        init_weights = np.array([1.0 / n_assets] * n_assets)

        # Objective: minimize variance
        def portfolio_variance(weights):
            return weights.T @ cov_matrix @ weights

        # Constraints
        constraints = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0},  # Sum to 1
            {'type': 'eq', 'fun': lambda w: w @ mean_returns - target_return}  # Target return
        ]

        # Bounds: 0 <= w <= 1
        bounds = [(0.0, 1.0) for _ in range(n_assets)]

        try:
            result = minimize(
                portfolio_variance,
                init_weights,
                method='SLSQP',
                bounds=bounds,
                constraints=constraints,
                options={'maxiter': 1000}
            )

            if result.success:
                return result.x
            else:
                logger.warning(f"Optimization failed: {result.message}")
                return init_weights

        except Exception as e:
            logger.error(f"Optimization error: {e}")
            return init_weights

    def _maximize_sharpe(
        self,
        mean_returns: np.ndarray,
        cov_matrix: np.ndarray
    ) -> np.ndarray:
        """
        Find weights that maximize Sharpe ratio.

        Args:
            mean_returns: Array of expected returns
            cov_matrix: Covariance matrix

        Returns:
            Array of optimal weights
        """
        n_assets = len(mean_returns)

        # Initial guess: equal weights
        init_weights = np.array([1.0 / n_assets] * n_assets)

        # Objective: negative Sharpe (to minimize)
        def neg_sharpe(weights):
            port_return = weights @ mean_returns
            port_vol = np.sqrt(weights.T @ cov_matrix @ weights)
            if port_vol == 0:
                return 0
            return -(port_return - self.risk_free_rate) / port_vol

        # Constraints: weights sum to 1
        constraints = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0}
        ]

        # Bounds: 0 <= w <= 1
        bounds = [(0.0, 1.0) for _ in range(n_assets)]

        try:
            result = minimize(
                neg_sharpe,
                init_weights,
                method='SLSQP',
                bounds=bounds,
                constraints=constraints,
                options={'maxiter': 1000}
            )

            if result.success:
                return result.x
            else:
                return init_weights

        except Exception as e:
            logger.error(f"Sharpe optimization error: {e}")
            return init_weights

    def _filter_correlated_assets(
        self,
        assets: List[str],
        correlation_matrix: Dict[str, Dict[str, float]]
    ) -> List[str]:
        """
        Remove assets that are highly correlated with each other.

        Keeps asset with higher expected Sharpe from correlated pair.
        """
        filtered = assets.copy()
        removed = set()

        for i, asset_a in enumerate(assets):
            if asset_a in removed:
                continue
            for j, asset_b in enumerate(assets):
                if j <= i or asset_b in removed:
                    continue

                corr = abs(correlation_matrix.get(asset_a, {}).get(asset_b, 0))
                if corr >= self.max_correlation:
                    # Remove one of the correlated pair
                    removed.add(asset_b)
                    logger.debug(f"Removed {asset_b} (corr {corr:.2f} with {asset_a})")

        filtered = [a for a in filtered if a not in removed]
        return filtered

    def _select_top_assets(
        self,
        returns: Dict[str, List[float]],
        n: int
    ) -> List[str]:
        """
        Select top N assets by Sharpe ratio.
        """
        sharpe_scores = {}

        for asset, ret in returns.items():
            if len(ret) < 2:
                sharpe_scores[asset] = 0
                continue

            mean_return = np.mean(ret) * 252  # Annualize
            volatility = np.std(ret) * np.sqrt(252)

            if volatility > 0:
                sharpe = (mean_return - self.risk_free_rate) / volatility
            else:
                sharpe = 0

            sharpe_scores[asset] = sharpe

        # Sort by Sharpe, descending
        sorted_assets = sorted(sharpe_scores.keys(), key=lambda x: sharpe_scores[x], reverse=True)

        return sorted_assets[:n]

    def get_efficient_frontier(
        self,
        returns: Dict[str, List[float]],
        n_points: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Calculate points along the efficient frontier.

        Args:
            returns: Historical returns by asset
            n_points: Number of frontier points

        Returns:
            List of dicts with 'return', 'risk', 'weights', 'sharpe'
        """
        if not returns:
            return []

        assets = list(returns.keys())

        # Align return lengths
        min_len = min(len(r) for r in returns.values())
        if min_len < 2:
            return []

        returns_matrix = np.array([returns[a][:min_len] for a in assets])
        mean_returns = np.mean(returns_matrix, axis=1) * 252
        cov_matrix = np.cov(returns_matrix) * 252

        # Range of target returns
        min_return = np.min(mean_returns)
        max_return = np.max(mean_returns)
        target_returns = np.linspace(min_return, max_return, n_points)

        frontier = []
        for target in target_returns:
            weights = self._minimize_variance_for_target(mean_returns, cov_matrix, target)

            port_return = weights @ mean_returns
            port_vol = np.sqrt(weights.T @ cov_matrix @ weights)
            sharpe = (port_return - self.risk_free_rate) / port_vol if port_vol > 0 else 0

            frontier.append({
                'return': float(port_return),
                'risk': float(port_vol),
                'weights': {a: float(w) for a, w in zip(assets, weights) if w > 0.01},
                'sharpe': float(sharpe)
            })

        return frontier

    def get_equal_weights(self, assets: List[str]) -> Dict[str, float]:
        """
        Get equal weight allocation.

        Args:
            assets: List of asset symbols

        Returns:
            Dict with equal weights summing to 1.0
        """
        if not assets:
            return {}

        weight = 1.0 / len(assets)
        return {a: weight for a in assets}

    def get_risk_parity_weights(
        self,
        returns: Dict[str, List[float]]
    ) -> Dict[str, float]:
        """
        Get inverse volatility (risk parity) weights.

        Lower volatility assets get higher weights.

        Args:
            returns: Historical returns by asset

        Returns:
            Dict with risk-parity weights summing to 1.0
        """
        if not returns:
            return {}

        volatilities = {}
        for asset, ret in returns.items():
            if len(ret) < 2:
                volatilities[asset] = 1.0  # Default high vol
            else:
                volatilities[asset] = np.std(ret) * np.sqrt(252)

        # Inverse volatility
        inv_vol = {}
        for asset, vol in volatilities.items():
            if vol > 0:
                inv_vol[asset] = 1.0 / vol
            else:
                inv_vol[asset] = 1.0

        # Normalize
        total = sum(inv_vol.values())
        return {a: v / total for a, v in inv_vol.items()}

    def optimize_with_sectors(
        self,
        returns: Dict[str, List[float]],
        sector_rotation: Any,  # SectorRotation instance
        target_return: Optional[float] = None
    ) -> Dict[str, float]:
        """
        Optimize with sector diversification constraints.

        Args:
            returns: Historical returns by asset
            sector_rotation: SectorRotation instance for sector mapping
            target_return: Target return (optional)

        Returns:
            Dict with optimized weights respecting sector limits
        """
        # First, regular optimization
        weights = self.optimize(returns, target_return)

        if not weights:
            return {}

        # Check sector allocation
        sector_weights = {}
        for asset, weight in weights.items():
            sector = sector_rotation.get_sector(asset)
            sector_weights[sector] = sector_weights.get(sector, 0) + weight

        # Adjust if any sector exceeds limit
        for sector, sw in sector_weights.items():
            if sw > self.max_sector_allocation:
                # Reduce all assets in this sector proportionally
                excess_ratio = self.max_sector_allocation / sw
                for asset in weights:
                    if sector_rotation.get_sector(asset) == sector:
                        weights[asset] *= excess_ratio

        # Renormalize
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}

        return weights


# Singleton instance
_portfolio_optimizer: Optional[PortfolioOptimizer] = None


def get_portfolio_optimizer() -> PortfolioOptimizer:
    """Get portfolio optimizer singleton."""
    global _portfolio_optimizer

    if _portfolio_optimizer is None:
        _portfolio_optimizer = PortfolioOptimizer()

    return _portfolio_optimizer


# Testing
if __name__ == "__main__":
    import numpy as np

    np.random.seed(42)

    # Sample returns
    returns = {
        'SOL': list(np.random.normal(0.002, 0.04, 100)),
        'ETH': list(np.random.normal(0.001, 0.03, 100)),
        'BTC': list(np.random.normal(0.001, 0.02, 100)),
        'BONK': list(np.random.normal(0.003, 0.08, 100)),
    }

    optimizer = PortfolioOptimizer()

    # Optimize
    weights = optimizer.optimize(returns, target_return=0.10)
    print("Optimized weights:")
    for asset, w in sorted(weights.items(), key=lambda x: x[1], reverse=True):
        print(f"  {asset}: {w*100:.1f}%")

    print(f"\nTotal: {sum(weights.values())*100:.1f}%")

    # Equal weights
    equal = optimizer.get_equal_weights(list(returns.keys()))
    print("\nEqual weights:")
    for asset, w in equal.items():
        print(f"  {asset}: {w*100:.1f}%")

    # Risk parity
    risk_parity = optimizer.get_risk_parity_weights(returns)
    print("\nRisk parity weights:")
    for asset, w in sorted(risk_parity.items(), key=lambda x: x[1], reverse=True):
        print(f"  {asset}: {w*100:.1f}%")

    # Efficient frontier
    frontier = optimizer.get_efficient_frontier(returns, n_points=5)
    print("\nEfficient Frontier:")
    for point in frontier:
        print(f"  Return: {point['return']*100:.1f}%, Risk: {point['risk']*100:.1f}%, Sharpe: {point['sharpe']:.2f}")
