"""
Multi-Asset Risk Calculator

Calculates portfolio-level risk metrics:
- Portfolio volatility
- Value at Risk (VaR)
- Diversification benefit
- Portfolio beta

Prompts #293: Multi-Asset Support and Portfolio Optimization
"""

import logging
import numpy as np
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


@dataclass
class RiskMetrics:
    """Portfolio risk metrics."""
    volatility: float = 0.0  # Annualized portfolio volatility
    var_95: float = 0.0  # Value at Risk (95% confidence)
    var_99: float = 0.0  # Value at Risk (99% confidence)
    diversification_benefit: float = 0.0  # Risk reduction from diversification
    beta: float = 0.0  # Portfolio beta vs market
    max_drawdown: float = 0.0
    calculated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'volatility': self.volatility,
            'var_95': self.var_95,
            'var_99': self.var_99,
            'diversification_benefit': self.diversification_benefit,
            'beta': self.beta,
            'max_drawdown': self.max_drawdown,
            'calculated_at': self.calculated_at.isoformat()
        }


class MultiAssetRiskCalculator:
    """
    Calculates comprehensive risk metrics for multi-asset portfolios.

    Features:
    - Portfolio volatility with correlation effects
    - Value at Risk (VaR) at various confidence levels
    - Diversification benefit measurement
    - Portfolio beta vs market benchmark
    - Maximum portfolio volatility constraint
    """

    def __init__(
        self,
        max_volatility: float = 0.20,  # 20% annualized
        trading_days: int = 365,  # Crypto trades 365 days
    ):
        """
        Initialize risk calculator.

        Args:
            max_volatility: Maximum allowed portfolio volatility (annualized)
            trading_days: Number of trading days for annualization
        """
        self.max_volatility = max_volatility
        self.trading_days = trading_days

    def _validate_weights(self, weights: Dict[str, float]):
        """
        Validate that weights sum to approximately 1.

        Args:
            weights: Asset weights

        Raises:
            ValueError: If weights are invalid
        """
        total = sum(weights.values())
        if not (0.99 <= total <= 1.01):
            raise ValueError(f"Weights must sum to 1.0, got {total:.3f}")

        if any(w < -0.01 for w in weights.values()):
            raise ValueError("Negative weights not allowed (no short selling)")

    def calculate_portfolio_volatility(
        self,
        returns: Dict[str, List[float]],
        weights: Dict[str, float]
    ) -> float:
        """
        Calculate annualized portfolio volatility.

        Uses portfolio variance formula with correlations:
        Var(P) = w'Cw where C is the covariance matrix

        Args:
            returns: Historical returns by asset
            weights: Portfolio weights by asset

        Returns:
            Annualized portfolio volatility
        """
        self._validate_weights(weights)

        if not returns or not weights:
            return 0.0

        # Build aligned arrays
        assets = [a for a in weights.keys() if a in returns]
        if not assets:
            return 0.0

        w = np.array([weights[a] for a in assets])

        # Align return lengths
        min_len = min(len(returns[a]) for a in assets)
        if min_len < 2:
            return 0.0

        returns_matrix = np.array([returns[a][:min_len] for a in assets])

        # Covariance matrix (annualized)
        cov_matrix = np.cov(returns_matrix) * self.trading_days

        # Handle 1D case
        if len(assets) == 1:
            return float(np.sqrt(cov_matrix) * np.sqrt(self.trading_days))

        # Portfolio variance: w' * C * w
        port_variance = w.T @ cov_matrix @ w
        port_volatility = np.sqrt(port_variance)

        return float(port_volatility)

    def calculate_diversification_benefit(
        self,
        returns: Dict[str, List[float]],
        weights: Dict[str, float]
    ) -> float:
        """
        Calculate diversification benefit.

        Diversification benefit = (weighted avg individual vol) - (portfolio vol)

        A positive value means diversification is reducing risk.

        Args:
            returns: Historical returns by asset
            weights: Portfolio weights

        Returns:
            Diversification benefit (positive = good)
        """
        if not returns or not weights:
            return 0.0

        # Calculate individual volatilities
        individual_vols = {}
        for asset, ret in returns.items():
            if asset in weights and len(ret) >= 2:
                individual_vols[asset] = np.std(ret) * np.sqrt(self.trading_days)

        if not individual_vols:
            return 0.0

        # Weighted average of individual volatilities
        weighted_avg_vol = sum(
            weights.get(a, 0) * vol
            for a, vol in individual_vols.items()
        )

        # Portfolio volatility
        try:
            port_vol = self.calculate_portfolio_volatility(returns, weights)
        except ValueError:
            return 0.0

        # Benefit is the reduction from diversification
        benefit = weighted_avg_vol - port_vol

        return max(0, float(benefit))

    def calculate_var(
        self,
        returns: Dict[str, List[float]],
        weights: Dict[str, float],
        confidence: float = 0.95,
        portfolio_value: float = 10000
    ) -> float:
        """
        Calculate Value at Risk using historical simulation.

        VaR represents the maximum expected loss over a given time
        horizon at a given confidence level.

        Args:
            returns: Historical returns by asset
            weights: Portfolio weights
            confidence: Confidence level (0.95 = 95%)
            portfolio_value: Portfolio value in USD

        Returns:
            VaR in USD (negative number = potential loss)
        """
        if not returns or not weights:
            return 0.0

        # Calculate portfolio returns
        assets = [a for a in weights.keys() if a in returns]
        if not assets:
            return 0.0

        # Align lengths
        min_len = min(len(returns[a]) for a in assets)
        if min_len < 2:
            return 0.0

        # Weighted portfolio returns
        portfolio_returns = np.zeros(min_len)
        for asset in assets:
            w = weights.get(asset, 0)
            portfolio_returns += w * np.array(returns[asset][:min_len])

        # VaR at percentile
        percentile = (1 - confidence) * 100  # e.g., 5th percentile for 95% VaR
        var_return = np.percentile(portfolio_returns, percentile)

        # Convert to USD
        var_usd = var_return * portfolio_value

        return float(var_usd)

    def calculate_portfolio_beta(
        self,
        returns: Dict[str, List[float]],
        weights: Dict[str, float],
        market_returns: List[float]
    ) -> float:
        """
        Calculate portfolio beta relative to market benchmark.

        Beta = Cov(portfolio, market) / Var(market)

        Args:
            returns: Historical returns by asset
            weights: Portfolio weights
            market_returns: Market benchmark returns (e.g., SOL or BTC)

        Returns:
            Portfolio beta
        """
        if not returns or not weights or not market_returns:
            return 0.0

        # Calculate portfolio returns
        assets = [a for a in weights.keys() if a in returns]
        if not assets:
            return 0.0

        # Align lengths
        min_len = min(
            min(len(returns[a]) for a in assets),
            len(market_returns)
        )
        if min_len < 2:
            return 0.0

        # Weighted portfolio returns
        portfolio_returns = np.zeros(min_len)
        for asset in assets:
            w = weights.get(asset, 0)
            portfolio_returns += w * np.array(returns[asset][:min_len])

        market = np.array(market_returns[:min_len])

        # Beta = Cov(P, M) / Var(M)
        covariance = np.cov(portfolio_returns, market)[0, 1]
        market_variance = np.var(market)

        if market_variance == 0:
            return 0.0

        beta = covariance / market_variance

        return float(beta)

    def exceeds_volatility_limit(
        self,
        returns: Dict[str, List[float]],
        weights: Dict[str, float]
    ) -> bool:
        """
        Check if portfolio exceeds maximum volatility constraint.

        Args:
            returns: Historical returns by asset
            weights: Portfolio weights

        Returns:
            True if portfolio volatility exceeds max_volatility
        """
        try:
            vol = self.calculate_portfolio_volatility(returns, weights)
            return vol > self.max_volatility
        except ValueError:
            return True  # Invalid weights = exceeds limit

    def calculate_max_drawdown(
        self,
        returns: Dict[str, List[float]],
        weights: Dict[str, float]
    ) -> float:
        """
        Calculate maximum drawdown of the portfolio.

        Args:
            returns: Historical returns by asset
            weights: Portfolio weights

        Returns:
            Maximum drawdown as a positive percentage
        """
        if not returns or not weights:
            return 0.0

        # Calculate portfolio returns
        assets = [a for a in weights.keys() if a in returns]
        if not assets:
            return 0.0

        min_len = min(len(returns[a]) for a in assets)
        if min_len < 2:
            return 0.0

        # Weighted portfolio returns
        portfolio_returns = np.zeros(min_len)
        for asset in assets:
            w = weights.get(asset, 0)
            portfolio_returns += w * np.array(returns[asset][:min_len])

        # Calculate cumulative returns
        cumulative = np.cumprod(1 + portfolio_returns)

        # Calculate running maximum
        running_max = np.maximum.accumulate(cumulative)

        # Drawdown at each point
        drawdowns = (running_max - cumulative) / running_max

        # Maximum drawdown
        max_dd = np.max(drawdowns)

        return float(max_dd)

    def get_risk_summary(
        self,
        returns: Dict[str, List[float]],
        weights: Dict[str, float],
        market_returns: Optional[List[float]] = None,
        portfolio_value: float = 10000
    ) -> Dict[str, Any]:
        """
        Get comprehensive risk metrics summary.

        Args:
            returns: Historical returns by asset
            weights: Portfolio weights
            market_returns: Market benchmark returns (optional)
            portfolio_value: Portfolio value in USD

        Returns:
            Dict with all risk metrics
        """
        try:
            volatility = self.calculate_portfolio_volatility(returns, weights)
        except ValueError as e:
            return {'error': str(e)}

        var_95 = self.calculate_var(returns, weights, 0.95, portfolio_value)
        var_99 = self.calculate_var(returns, weights, 0.99, portfolio_value)
        div_benefit = self.calculate_diversification_benefit(returns, weights)
        max_dd = self.calculate_max_drawdown(returns, weights)

        beta = 0.0
        if market_returns:
            beta = self.calculate_portfolio_beta(returns, weights, market_returns)

        return {
            'volatility': volatility,
            'volatility_pct': volatility * 100,
            'var_95': var_95,
            'var_99': var_99,
            'diversification_benefit': div_benefit,
            'diversification_benefit_pct': div_benefit * 100,
            'beta': beta,
            'max_drawdown': max_dd,
            'max_drawdown_pct': max_dd * 100,
            'exceeds_limit': volatility > self.max_volatility,
            'max_volatility': self.max_volatility,
            'calculated_at': datetime.now().isoformat()
        }


# Singleton instance
_risk_calculator: Optional[MultiAssetRiskCalculator] = None


def get_risk_calculator() -> MultiAssetRiskCalculator:
    """Get risk calculator singleton."""
    global _risk_calculator

    if _risk_calculator is None:
        _risk_calculator = MultiAssetRiskCalculator()

    return _risk_calculator


# Testing
if __name__ == "__main__":
    import numpy as np

    np.random.seed(42)

    # Sample returns
    returns = {
        'SOL': list(np.random.normal(0.001, 0.03, 100)),
        'ETH': list(np.random.normal(0.001, 0.02, 100)),
        'BTC': list(np.random.normal(0.001, 0.015, 100)),
    }

    weights = {'SOL': 0.4, 'ETH': 0.35, 'BTC': 0.25}
    market_returns = list(np.random.normal(0.001, 0.025, 100))

    calc = MultiAssetRiskCalculator()

    # Calculate metrics
    vol = calc.calculate_portfolio_volatility(returns, weights)
    print(f"Portfolio Volatility: {vol*100:.1f}%")

    var_95 = calc.calculate_var(returns, weights, 0.95, 10000)
    print(f"VaR (95%): ${var_95:.2f}")

    var_99 = calc.calculate_var(returns, weights, 0.99, 10000)
    print(f"VaR (99%): ${var_99:.2f}")

    div_benefit = calc.calculate_diversification_benefit(returns, weights)
    print(f"Diversification Benefit: {div_benefit*100:.1f}%")

    beta = calc.calculate_portfolio_beta(returns, weights, market_returns)
    print(f"Portfolio Beta: {beta:.2f}")

    max_dd = calc.calculate_max_drawdown(returns, weights)
    print(f"Max Drawdown: {max_dd*100:.1f}%")

    print("\nFull Summary:")
    summary = calc.get_risk_summary(returns, weights, market_returns)
    for k, v in summary.items():
        print(f"  {k}: {v}")
