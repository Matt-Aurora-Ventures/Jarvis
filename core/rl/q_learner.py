"""
Reinforcement Learning for Trading - Q-Learning based decision optimization.

Learns from trading outcomes to improve future decisions.
Tracks rewards (PnL), market states, and action values.
"""

import json
import logging
from collections import defaultdict
from typing import Dict, Any, Tuple
import numpy as np

logger = logging.getLogger(__name__)


class TradingQLearner:
    """Q-Learning agent for trading decisions."""

    def __init__(self, learning_rate: float = 0.1, discount_factor: float = 0.95, epsilon: float = 0.1):
        """Initialize Q-Learning agent.

        Args:
            learning_rate: Learning rate for Q-value updates
            discount_factor: Discount factor for future rewards
            epsilon: Exploration rate for epsilon-greedy strategy
        """
        self.alpha = learning_rate
        self.gamma = discount_factor
        self.epsilon = epsilon
        
        # Q-table: (state, action) -> Q-value
        self.q_table: Dict[Tuple, float] = defaultdict(float)
        
        # Trade history for learning
        self.trade_history = []
        
        # Stats
        self.trades_completed = 0
        self.total_reward = 0.0
        self.win_count = 0

    def get_state(self, market_data: Dict[str, Any]) -> Tuple:
        """Discretize market state into a hashable tuple."""
        price = market_data.get("price", 0)
        volume = market_data.get("volume_24h", 0)
        sentiment = market_data.get("sentiment_score", 50)

        # Discretize into levels (0=low, 1=mid, 2=high)
        price_level = 0 if price < 100 else (1 if price < 500 else 2)
        volume_level = 0 if volume < 1e9 else (1 if volume < 5e9 else 2)
        sentiment_level = 0 if sentiment < 40 else (1 if sentiment < 70 else 2)

        return (price_level, volume_level, sentiment_level)

    def select_action(self, state: Tuple, available_actions: list) -> str:
        """Select action using epsilon-greedy strategy."""
        if np.random.random() < self.epsilon:
            return np.random.choice(available_actions)

        # Choose action with highest Q-value
        q_values = {a: self.q_table[(state, a)] for a in available_actions}
        return max(q_values, key=q_values.get)

    def update_q_value(self, state: Tuple, action: str, reward: float, next_state: Tuple, next_actions: list):
        """Update Q-value using Q-Learning formula."""
        current_q = self.q_table[(state, action)]
        max_next_q = max(
            (self.q_table[(next_state, a)] for a in next_actions),
            default=0.0
        )
        new_q = current_q + self.alpha * (reward + self.gamma * max_next_q - current_q)
        self.q_table[(state, action)] = new_q
        logger.debug(f"Q-update: {state} {action} -> {new_q:.4f} (reward: {reward:.4f})")

    def record_trade(self, symbol: str, action: str, entry_price: float, exit_price: float, 
                     market_data: Dict[str, Any]):
        """Record a completed trade for learning."""
        pnl = (exit_price - entry_price) / entry_price * 100 if action == "BUY" else 0
        reward = 1.0 if pnl > 0 else (-0.5 if pnl < -5 else 0.1)

        self.trade_history.append({
            "symbol": symbol,
            "action": action,
            "entry": entry_price,
            "exit": exit_price,
            "pnl_pct": pnl,
            "reward": reward,
        })

        self.trades_completed += 1
        self.total_reward += reward
        if reward > 0:
            self.win_count += 1

        state = self.get_state(market_data)
        self.update_q_value(state, action, reward, state, ["BUY", "SELL", "HOLD"])
        logger.info(f"Trade recorded: {symbol} {action} {pnl:.2f}% (reward: {reward:.2f})")

    def get_win_rate(self) -> float:
        """Calculate win rate from trade history."""
        if self.trades_completed == 0:
            return 0.0
        return self.win_count / self.trades_completed

    def get_q_table_summary(self) -> Dict[str, Any]:
        """Get summary statistics of Q-table."""
        if not self.q_table:
            return {"states": 0, "entries": 0, "avg_q": 0}

        q_values = list(self.q_table.values())
        return {
            "states": len(set(k[0] for k in self.q_table.keys())),
            "entries": len(self.q_table),
            "avg_q": float(np.mean(q_values)),
            "max_q": float(np.max(q_values)),
            "min_q": float(np.min(q_values)),
        }

    def save_model(self, path: str = "data/rl_model.json"):
        """Save Q-table and stats to file."""
        model = {
            "q_table": {str(k): v for k, v in self.q_table.items()},
            "trades_completed": self.trades_completed,
            "total_reward": self.total_reward,
            "win_count": self.win_count,
            "win_rate": self.get_win_rate(),
        }

        try:
            with open(path, "w") as f:
                json.dump(model, f, indent=2)
            logger.info(f"RL model saved to {path}")
        except IOError as e:
            logger.error(f"Failed to save model: {e}")

    def load_model(self, path: str = "data/rl_model.json"):
        """Load Q-table and stats from file."""
        try:
            with open(path, "r") as f:
                model = json.load(f)
            self.trades_completed = model.get("trades_completed", 0)
            self.total_reward = model.get("total_reward", 0.0)
            self.win_count = model.get("win_count", 0)
            logger.info(f"RL model loaded from {path}")
        except (IOError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to load model: {e}")


__all__ = ["TradingQLearner"]
