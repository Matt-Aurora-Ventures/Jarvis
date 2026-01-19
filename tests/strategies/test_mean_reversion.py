"""Tests for mean reversion strategy."""

import pytest
from core.trading.strategies.mean_reversion import MeanReversionStrategy, MeanReversionConfig


def test_mean_reversion_initialization():
    """Test strategy initialization."""
    config = MeanReversionConfig(short_window=7, long_window=25)
    strategy = MeanReversionStrategy(config)
    assert strategy.config.short_window == 7
    assert strategy.config.long_window == 25


def test_add_price_point():
    """Test adding price points."""
    strategy = MeanReversionStrategy()
    strategy.add_price_point('SOL', 100.0)
    assert 'SOL' in strategy.price_history
    assert len(strategy.price_history['SOL']) == 1


def test_insufficient_data_signal():
    """Test signal with insufficient data."""
    strategy = MeanReversionStrategy()
    strategy.add_price_point('SOL', 100.0)
    result = strategy.calculate_reversion_signal('SOL', 100.0)
    assert result['signal'] == 'INSUFFICIENT_DATA'
    assert result['confidence'] == 0


def test_moving_average_calculation():
    """Test MA calculations with sufficient data."""
    strategy = MeanReversionStrategy()
    prices = [100.0 + i for i in range(30)]
    for price in prices:
        strategy.add_price_point('SOL', price)
    
    ma_data = strategy.calculate_moving_averages('SOL')
    assert ma_data['sufficient_data'] is True
    assert ma_data['short_ma'] is not None
    assert ma_data['long_ma'] is not None


def test_signal_generation():
    """Test signal generation with trending prices."""
    strategy = MeanReversionStrategy()
    prices = [100.0 + (i * 0.5) for i in range(30)]
    for price in prices:
        strategy.add_price_point('SOL', price)
    
    result = strategy.calculate_reversion_signal('SOL', 110.0)
    assert 'signal' in result
    assert 'confidence' in result


def test_get_target_price():
    """Test target price calculation."""
    strategy = MeanReversionStrategy()
    for price in [100.0 + i for i in range(30)]:
        strategy.add_price_point('SOL', price)
    
    target = strategy.get_target_price('SOL')
    assert target is not None
    assert 110 < target < 120


def test_risk_reward_ratio():
    """Test risk/reward calculation."""
    strategy = MeanReversionStrategy()
    for price in [100.0 + i for i in range(30)]:
        strategy.add_price_point('SOL', price)
    
    rr = strategy.get_risk_reward_ratio('SOL', 100.0, stop_loss_pct=10.0)
    assert 'risk_reward_ratio' in rr
    assert rr['profitable'] is True


def test_clear_history():
    """Test clearing price history."""
    strategy = MeanReversionStrategy()
    strategy.add_price_point('SOL', 100.0)
    strategy.add_price_point('BTC', 45000.0)
    assert len(strategy.price_history) == 2
    
    strategy.clear_history('SOL')
    assert 'SOL' not in strategy.price_history
    assert 'BTC' in strategy.price_history


def test_get_signal_strength():
    """Test getting signal strength."""
    strategy = MeanReversionStrategy()
    for price in [100.0 + i for i in range(30)]:
        strategy.add_price_point('SOL', price)
    
    strategy.calculate_reversion_signal('SOL', 100.0)
    strength = strategy.get_signal_strength('SOL')
    assert 0 <= strength <= 100
