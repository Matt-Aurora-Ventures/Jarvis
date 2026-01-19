"""Reward function design for trading RL agent."""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class RewardCalculator:
    """Calculates rewards for trading actions based on outcomes."""

    def __init__(self, risk_free_rate: float = 0.02):
        """Initialize reward calculator.

        Args:
            risk_free_rate: Annual risk-free rate (default 2%)
        """
        self.risk_free_rate = risk_free_rate

    def calculate_reward(self, trade_result: Dict[str, Any]) -> float:
        """Calculate reward from trade result.

        Args:
            trade_result: Dict with keys: pnl_pct, max_drawdown, holding_time_hours

        Returns:
            Reward value (-1 to 1 range)
        """
        pnl = trade_result.get("pnl_pct", 0)
        drawdown = trade_result.get("max_drawdown", 0)
        hold_time = trade_result.get("holding_time_hours", 1)

        # Base reward from PnL
        if pnl > 10:
            base_reward = 1.0
        elif pnl > 5:
            base_reward = 0.7
        elif pnl > 0:
            base_reward = 0.3
        elif pnl > -5:
            base_reward = -0.2
        else:
            base_reward = -1.0

        # Penalize for drawdown
        drawdown_penalty = -0.1 * abs(drawdown)

        # Bonus for speed (faster trades = better capital efficiency)
        time_bonus = 0.1 if hold_time < 24 else (-0.1 if hold_time > 168 else 0)

        reward = base_reward + drawdown_penalty + time_bonus
        return max(-1.0, min(1.0, reward))  # Clamp to [-1, 1]

    def calculate_sharpe_reward(self, returns: list, risk_free_rate: float = 0.02) -> float:
        """Calculate reward based on Sharpe ratio.

        Args:
            returns: List of returns
            risk_free_rate: Risk-free rate

        Returns:
            Reward based on Sharpe ratio
        """
        if len(returns) < 2:
            return 0.0

        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        std_dev = variance ** 0.5

        if std_dev == 0:
            return 0.0

        sharpe = (mean_return - risk_free_rate) / std_dev
        return min(1.0, sharpe / 2)  # Normalize to [0, 1]


__all__ = ["RewardCalculator"]
