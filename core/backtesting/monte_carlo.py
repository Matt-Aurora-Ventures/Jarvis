"""
Monte Carlo Simulation Module

Provides Monte Carlo simulation for trading strategies:
- Simulate 1000+ potential trading scenarios
- Vary entry timing, exit prices, position sizes
- Calculate P10, P50, P90 percentiles
- Compute Value at Risk (VaR) and confidence intervals
- Generate probability distribution curves
"""

import logging
import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
import statistics

logger = logging.getLogger(__name__)


@dataclass
class MonteCarloResult:
    """Result of Monte Carlo simulation."""
    n_simulations: int
    initial_capital: float
    mean_return: float
    std_return: float
    median_return: float
    p10: float  # 10th percentile
    p25: float  # 25th percentile
    p50: float  # 50th percentile (median)
    p75: float  # 75th percentile
    p90: float  # 90th percentile
    min_return: float
    max_return: float
    returns: List[float]  # All simulated returns
    final_capitals: List[float]  # All simulated final capitals

    def probability_of_loss(self, threshold: float = 0.0) -> float:
        """
        Calculate probability of losing more than threshold.

        Args:
            threshold: Loss threshold as fraction (e.g., 0.10 = 10% loss)

        Returns:
            Probability (0-1) of exceeding the loss threshold
        """
        if not self.returns:
            return 0

        loss_threshold = -abs(threshold) * 100  # Convert to percentage
        losses = [r for r in self.returns if r < loss_threshold]
        return len(losses) / len(self.returns)

    def probability_of_profit(self, threshold: float = 0.0) -> float:
        """
        Calculate probability of gaining more than threshold.

        Args:
            threshold: Gain threshold as fraction (e.g., 0.20 = 20% gain)

        Returns:
            Probability (0-1) of exceeding the gain threshold
        """
        if not self.returns:
            return 0

        gain_threshold = abs(threshold) * 100  # Convert to percentage
        gains = [r for r in self.returns if r > gain_threshold]
        return len(gains) / len(self.returns)

    def confidence_interval(self, confidence: float = 0.95) -> Dict[str, float]:
        """
        Calculate confidence interval for returns.

        Args:
            confidence: Confidence level (e.g., 0.95 for 95%)

        Returns:
            Dict with 'lower' and 'upper' bounds
        """
        if not self.returns:
            return {'lower': 0, 'upper': 0}

        sorted_returns = sorted(self.returns)
        n = len(sorted_returns)

        alpha = 1 - confidence
        lower_idx = int(n * (alpha / 2))
        upper_idx = int(n * (1 - alpha / 2))

        return {
            'lower': sorted_returns[lower_idx],
            'upper': sorted_returns[min(upper_idx, n - 1)],
            'confidence': confidence
        }

    def value_at_risk(self, confidence: float = 0.95) -> float:
        """
        Calculate Value at Risk (VaR).

        VaR represents the maximum expected loss at a given confidence level.

        Args:
            confidence: Confidence level (e.g., 0.95 for 95% VaR)

        Returns:
            VaR as a percentage (negative number representing max loss)
        """
        if not self.returns:
            return 0

        sorted_returns = sorted(self.returns)
        n = len(sorted_returns)

        # VaR is the (1-confidence) percentile
        idx = int(n * (1 - confidence))
        return sorted_returns[idx]

    def expected_shortfall(self, confidence: float = 0.95) -> float:
        """
        Calculate Expected Shortfall (Conditional VaR).

        ES is the average loss given that loss exceeds VaR.

        Args:
            confidence: Confidence level

        Returns:
            Expected shortfall as a percentage
        """
        if not self.returns:
            return 0

        var = self.value_at_risk(confidence)
        tail_losses = [r for r in self.returns if r <= var]

        if not tail_losses:
            return var

        return sum(tail_losses) / len(tail_losses)

    def get_distribution(self) -> Dict[str, Any]:
        """
        Get full distribution data.

        Returns:
            Dictionary with returns, histogram, and statistics
        """
        if not self.returns:
            return {'returns': [], 'histogram': [], 'stats': {}}

        # Create histogram bins
        min_r = min(self.returns)
        max_r = max(self.returns)
        n_bins = 50
        bin_width = (max_r - min_r) / n_bins if max_r != min_r else 1

        histogram = []
        for i in range(n_bins):
            bin_start = min_r + i * bin_width
            bin_end = bin_start + bin_width
            count = len([r for r in self.returns if bin_start <= r < bin_end])
            histogram.append({
                'bin_start': bin_start,
                'bin_end': bin_end,
                'count': count,
                'frequency': count / len(self.returns)
            })

        return {
            'returns': self.returns,
            'histogram': histogram,
            'stats': {
                'mean': self.mean_return,
                'std': self.std_return,
                'median': self.median_return,
                'min': self.min_return,
                'max': self.max_return,
                'skewness': self._calculate_skewness(),
                'kurtosis': self._calculate_kurtosis()
            }
        }

    def _calculate_skewness(self) -> float:
        """Calculate skewness of returns distribution."""
        if len(self.returns) < 3 or self.std_return == 0:
            return 0

        n = len(self.returns)
        mean = self.mean_return
        std = self.std_return

        skew = sum((r - mean) ** 3 for r in self.returns) / n
        return skew / (std ** 3)

    def _calculate_kurtosis(self) -> float:
        """Calculate kurtosis of returns distribution."""
        if len(self.returns) < 4 or self.std_return == 0:
            return 0

        n = len(self.returns)
        mean = self.mean_return
        std = self.std_return

        kurt = sum((r - mean) ** 4 for r in self.returns) / n
        return (kurt / (std ** 4)) - 3  # Excess kurtosis

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            'n_simulations': self.n_simulations,
            'initial_capital': self.initial_capital,
            'mean_return': self.mean_return,
            'std_return': self.std_return,
            'median_return': self.median_return,
            'percentiles': {
                'p10': self.p10,
                'p25': self.p25,
                'p50': self.p50,
                'p75': self.p75,
                'p90': self.p90,
            },
            'min_return': self.min_return,
            'max_return': self.max_return,
            'var_95': self.value_at_risk(0.95),
            'var_99': self.value_at_risk(0.99),
            'prob_loss_10pct': self.probability_of_loss(0.10),
            'prob_loss_25pct': self.probability_of_loss(0.25),
            'prob_profit_20pct': self.probability_of_profit(0.20),
        }


class MonteCarloSimulator:
    """
    Monte Carlo simulator for trading strategies.

    Simulates many possible outcomes by varying:
    - Entry timing (slippage in entry)
    - Exit prices (slippage in exit)
    - Position sizes
    - Trade order randomization

    This helps understand the range of possible outcomes
    and the probability of various scenarios.
    """

    def __init__(self, seed: Optional[int] = None):
        """
        Initialize Monte Carlo simulator.

        Args:
            seed: Random seed for reproducibility
        """
        if seed is not None:
            random.seed(seed)

    def run_simulation(
        self,
        trades: List[Dict[str, Any]],
        n_simulations: int = 1000,
        initial_capital: float = 10000,
        entry_timing_variance: float = 0.0,
        exit_price_variance: float = 0.0,
        position_size_variance: float = 0.0,
        shuffle_trades: bool = False
    ) -> MonteCarloResult:
        """
        Run Monte Carlo simulation.

        Args:
            trades: List of trade dictionaries with pnl, pnl_pct, position_size
            n_simulations: Number of simulations to run
            initial_capital: Starting capital
            entry_timing_variance: Variance in entry timing (0-1)
            exit_price_variance: Variance in exit prices (0-1)
            position_size_variance: Variance in position sizes (0-1)
            shuffle_trades: Whether to randomize trade order

        Returns:
            MonteCarloResult with distribution of outcomes
        """
        if not trades:
            raise ValueError("Cannot run Monte Carlo with empty trade list")

        returns = []
        final_capitals = []

        for sim in range(n_simulations):
            # Copy and optionally shuffle trades
            sim_trades = list(trades)
            if shuffle_trades:
                random.shuffle(sim_trades)

            # Simulate this scenario
            capital = initial_capital

            for trade in sim_trades:
                pnl = trade.get('pnl', 0)
                pnl_pct = trade.get('pnl_pct', 0)
                position_size = trade.get('position_size', capital * 0.1)

                # Apply entry timing variance (affects entry price -> affects PnL)
                if entry_timing_variance > 0:
                    timing_factor = 1 + random.uniform(-entry_timing_variance, entry_timing_variance)
                    pnl = pnl * timing_factor

                # Apply exit price variance
                if exit_price_variance > 0:
                    exit_factor = 1 + random.uniform(-exit_price_variance, exit_price_variance)
                    pnl = pnl * exit_factor

                # Apply position size variance
                if position_size_variance > 0:
                    size_factor = 1 + random.uniform(-position_size_variance, position_size_variance)
                    # Scale PnL by size factor
                    pnl = pnl * size_factor

                capital += pnl

                # Prevent negative capital
                if capital <= 0:
                    capital = 0
                    break

            final_capitals.append(capital)
            returns.append((capital - initial_capital) / initial_capital * 100)

        # Calculate statistics
        returns.sort()
        n = len(returns)

        mean_return = sum(returns) / n if n > 0 else 0
        std_return = statistics.stdev(returns) if n > 1 else 0
        median_return = statistics.median(returns) if n > 0 else 0

        p10 = returns[int(n * 0.10)] if n > 0 else 0
        p25 = returns[int(n * 0.25)] if n > 0 else 0
        p50 = returns[int(n * 0.50)] if n > 0 else 0
        p75 = returns[int(n * 0.75)] if n > 0 else 0
        p90 = returns[int(n * 0.90)] if n > 0 else 0

        return MonteCarloResult(
            n_simulations=n_simulations,
            initial_capital=initial_capital,
            mean_return=mean_return,
            std_return=std_return,
            median_return=median_return,
            p10=p10,
            p25=p25,
            p50=p50,
            p75=p75,
            p90=p90,
            min_return=min(returns) if returns else 0,
            max_return=max(returns) if returns else 0,
            returns=returns,
            final_capitals=final_capitals
        )

    def run_path_simulation(
        self,
        trades: List[Dict[str, Any]],
        n_simulations: int = 1000,
        initial_capital: float = 10000
    ) -> Dict[str, Any]:
        """
        Run path-dependent Monte Carlo simulation.

        Instead of just final outcomes, tracks the equity curve path
        for each simulation. Useful for analyzing drawdown distributions.

        Args:
            trades: List of trade dictionaries
            n_simulations: Number of simulations
            initial_capital: Starting capital

        Returns:
            Dictionary with paths and path statistics
        """
        if not trades:
            raise ValueError("Cannot run simulation with empty trade list")

        paths = []
        max_drawdowns = []

        for sim in range(n_simulations):
            sim_trades = list(trades)
            random.shuffle(sim_trades)

            path = [initial_capital]
            capital = initial_capital
            peak = initial_capital
            max_dd = 0

            for trade in sim_trades:
                pnl = trade.get('pnl', 0)
                # Add some randomness
                pnl = pnl * (1 + random.gauss(0, 0.1))
                capital += pnl

                if capital <= 0:
                    capital = 0

                path.append(capital)

                # Track drawdown
                if capital > peak:
                    peak = capital
                dd = (peak - capital) / peak if peak > 0 else 0
                max_dd = max(max_dd, dd)

            paths.append(path)
            max_drawdowns.append(max_dd * 100)

        return {
            'n_simulations': n_simulations,
            'paths': paths,
            'max_drawdowns': {
                'mean': sum(max_drawdowns) / len(max_drawdowns),
                'median': statistics.median(max_drawdowns),
                'p95': sorted(max_drawdowns)[int(len(max_drawdowns) * 0.95)],
                'max': max(max_drawdowns)
            },
            'path_lengths': len(trades) + 1
        }

    def generate_report(self, result: MonteCarloResult) -> str:
        """Generate text report for Monte Carlo results."""
        return f"""
MONTE CARLO SIMULATION REPORT
{'=' * 60}

Simulations: {result.n_simulations:,}
Initial Capital: ${result.initial_capital:,.2f}

RETURN DISTRIBUTION:
  Mean Return: {result.mean_return:+.2f}%
  Std Deviation: {result.std_return:.2f}%
  Median Return: {result.median_return:+.2f}%

PERCENTILES:
  10th Percentile (P10): {result.p10:+.2f}%
  25th Percentile (P25): {result.p25:+.2f}%
  50th Percentile (P50): {result.p50:+.2f}%
  75th Percentile (P75): {result.p75:+.2f}%
  90th Percentile (P90): {result.p90:+.2f}%

RANGE:
  Minimum Return: {result.min_return:+.2f}%
  Maximum Return: {result.max_return:+.2f}%

RISK METRICS:
  95% VaR: {result.value_at_risk(0.95):+.2f}%
  99% VaR: {result.value_at_risk(0.99):+.2f}%
  95% Expected Shortfall: {result.expected_shortfall(0.95):+.2f}%

PROBABILITY ANALYSIS:
  P(Loss > 10%): {result.probability_of_loss(0.10):.1%}
  P(Loss > 25%): {result.probability_of_loss(0.25):.1%}
  P(Profit > 20%): {result.probability_of_profit(0.20):.1%}
  P(Profit > 50%): {result.probability_of_profit(0.50):.1%}

CONFIDENCE INTERVALS:
  95% CI: [{result.confidence_interval(0.95)['lower']:+.2f}%, {result.confidence_interval(0.95)['upper']:+.2f}%]
  99% CI: [{result.confidence_interval(0.99)['lower']:+.2f}%, {result.confidence_interval(0.99)['upper']:+.2f}%]
"""
