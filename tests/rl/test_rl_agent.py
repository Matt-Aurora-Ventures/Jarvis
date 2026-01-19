"""Tests for reinforcement learning trading agent."""

import pytest
from core.rl.q_learner import TradingQLearner
from core.rl.reward_function import RewardCalculator


def test_q_learner_init():
    """Test Q-Learner initialization."""
    learner = TradingQLearner(learning_rate=0.1, discount_factor=0.95)
    assert learner.alpha == 0.1
    assert learner.gamma == 0.95
    assert learner.trades_completed == 0


def test_get_state():
    """Test state discretization."""
    learner = TradingQLearner()
    market_data = {
        "price": 150,
        "volume_24h": 2.5e9,
        "sentiment_score": 75,
    }
    state = learner.get_state(market_data)
    assert isinstance(state, tuple)
    assert len(state) == 3
    assert all(isinstance(x, int) for x in state)


def test_select_action():
    """Test action selection."""
    learner = TradingQLearner(epsilon=0.0)  # Greedy
    state = (1, 1, 1)
    actions = ["BUY", "SELL", "HOLD"]
    action = learner.select_action(state, actions)
    assert action in actions


def test_update_q_value():
    """Test Q-value update."""
    learner = TradingQLearner()
    state = (0, 0, 0)
    action = "BUY"
    reward = 0.5
    next_state = (1, 1, 1)
    next_actions = ["BUY", "SELL", "HOLD"]

    initial_q = learner.q_table[(state, action)]
    learner.update_q_value(state, action, reward, next_state, next_actions)
    updated_q = learner.q_table[(state, action)]

    assert updated_q > initial_q


def test_record_trade():
    """Test trade recording."""
    learner = TradingQLearner()
    market_data = {"price": 100, "volume_24h": 1e9, "sentiment_score": 50}

    learner.record_trade("SOL", "BUY", 100, 110, market_data)

    assert learner.trades_completed == 1
    assert len(learner.trade_history) == 1
    assert learner.trade_history[0]["pnl_pct"] == 10.0


def test_win_rate_positive():
    """Test win rate calculation for profitable trades."""
    learner = TradingQLearner()
    market_data = {"price": 100, "volume_24h": 1e9, "sentiment_score": 50}

    # Winning trade
    learner.record_trade("SOL", "BUY", 100, 115, market_data)

    win_rate = learner.get_win_rate()
    assert win_rate == 1.0  # 1 win out of 1


def test_win_rate_mixed():
    """Test win rate with mixed results."""
    learner = TradingQLearner()
    market_data = {"price": 100, "volume_24h": 1e9, "sentiment_score": 50}

    # Winning trade (+15%)
    learner.record_trade("SOL", "BUY", 100, 115, market_data)
    # Losing trade (-10%, below -5% threshold)
    learner.record_trade("BTC", "BUY", 100, 90, market_data)

    win_rate = learner.get_win_rate()
    assert 0 <= win_rate <= 1
    assert learner.trades_completed == 2


def test_q_table_summary():
    """Test Q-table statistics."""
    learner = TradingQLearner()
    market_data = {"price": 100, "volume_24h": 1e9, "sentiment_score": 50}
    learner.record_trade("SOL", "BUY", 100, 110, market_data)

    summary = learner.get_q_table_summary()
    assert "entries" in summary
    assert "states" in summary
    assert summary["entries"] > 0


def test_reward_calculator():
    """Test reward calculation."""
    calc = RewardCalculator()
    trade_result = {
        "pnl_pct": 8.0,
        "max_drawdown": 2.0,
        "holding_time_hours": 12,
    }
    reward = calc.calculate_reward(trade_result)
    assert -1 <= reward <= 1


def test_reward_calculation_winning_trade():
    """Test reward for winning trade."""
    calc = RewardCalculator()
    trade_result = {
        "pnl_pct": 12.0,
        "max_drawdown": 1.0,
        "holding_time_hours": 6,
    }
    reward = calc.calculate_reward(trade_result)
    assert reward > 0.5


def test_reward_calculation_losing_trade():
    """Test reward for losing trade."""
    calc = RewardCalculator()
    trade_result = {
        "pnl_pct": -10.0,
        "max_drawdown": 8.0,
        "holding_time_hours": 24,
    }
    reward = calc.calculate_reward(trade_result)
    assert reward < 0


def test_sharpe_reward_positive_returns():
    """Test Sharpe ratio based reward with positive returns."""
    calc = RewardCalculator()
    returns = [0.02, 0.03, 0.025, 0.032, 0.028]
    reward = calc.calculate_sharpe_reward(returns)
    assert -1 <= reward <= 1  # Should be within valid range


__all__ = []
