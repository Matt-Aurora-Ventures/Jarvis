"""Tests for trailing stop strategy."""

import pytest
from core.trading.strategies.trailing_stop import TrailingStopStrategy, TrailingStopConfig


def test_trailing_stop_initialization():
    """Test strategy initialization."""
    config = TrailingStopConfig(trail_percentage=10.0, min_profit_pct=5.0)
    strategy = TrailingStopStrategy(config)
    assert strategy.config.trail_percentage == 10.0
    assert len(strategy.positions) == 0


def test_enter_position():
    """Test entering a position."""
    strategy = TrailingStopStrategy()
    result = strategy.enter_position('SOL', 100.0, 'pos1')
    assert result['symbol'] == 'SOL'
    assert result['entry_price'] == 100.0
    assert result['stop_loss'] == pytest.approx(95.0)


def test_trailing_stop_activation():
    """Test trailing stop activates on profit."""
    strategy = TrailingStopStrategy()
    strategy.enter_position('SOL', 100.0, 'pos1')
    result = strategy.update_trailing_stop('pos1', 110.0)
    assert result['trailing_active'] is True
    assert result['stop_moved'] is True
    assert result['profit_pct'] == pytest.approx(10.0)


def test_stop_loss_never_moves_down():
    """Test stop loss only moves up."""
    strategy = TrailingStopStrategy()
    strategy.enter_position('SOL', 100.0, 'pos1')
    strategy.update_trailing_stop('pos1', 110.0)
    first_stop = strategy.positions['pos1']['stop_loss']
    strategy.update_trailing_stop('pos1', 105.0)
    assert strategy.positions['pos1']['stop_loss'] == pytest.approx(first_stop)


def test_exit_signal_on_stop_hit():
    """Test exit when stop loss is hit."""
    strategy = TrailingStopStrategy()
    strategy.enter_position('SOL', 100.0, 'pos1')
    strategy.update_trailing_stop('pos1', 110.0)
    result = strategy.check_exit_signal('pos1', 98.0)
    assert result['should_exit'] is True
    assert result['reason'] == 'Trailing stop hit'


def test_close_position():
    """Test closing a position."""
    strategy = TrailingStopStrategy()
    strategy.enter_position('SOL', 100.0, 'pos1')
    assert len(strategy.positions) == 1
    assert strategy.close_position('pos1') is True
    assert len(strategy.positions) == 0


def test_get_all_positions():
    """Test getting all positions."""
    strategy = TrailingStopStrategy()
    strategy.enter_position('SOL', 100.0, 'pos1')
    strategy.enter_position('BTC', 45000.0, 'pos2')
    positions = strategy.get_all_positions()
    assert len(positions) == 2
    assert 'pos1' in positions
    assert 'pos2' in positions
