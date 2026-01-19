"""Tests for arbitrage strategy."""

import pytest
from core.trading.strategies.arbitrage import ArbitrageStrategy, ArbitrageConfig


def test_arbitrage_initialization():
    """Test strategy initialization."""
    config = ArbitrageConfig(min_spread_pct=2.0, max_latency_seconds=30)
    strategy = ArbitrageStrategy(config)
    assert strategy.config.min_spread_pct == 2.0
    assert len(strategy.exchange_prices) == 0


def test_update_price():
    """Test price update from exchange."""
    strategy = ArbitrageStrategy()
    strategy.update_price('SOL', 'jupiter', 100.0, liquidity=50000, volume_24h=1000000)
    assert 'SOL' in strategy.exchange_prices
    assert 'jupiter' in strategy.exchange_prices['SOL']


def test_no_opportunity_single_exchange():
    """Test no opportunity with single exchange."""
    strategy = ArbitrageStrategy()
    strategy.update_price('SOL', 'jupiter', 100.0, liquidity=50000)
    opportunities = strategy.find_opportunities('SOL')
    assert len(opportunities) == 0


def test_profitable_opportunity_detection():
    """Test detection of profitable spread."""
    strategy = ArbitrageStrategy()
    strategy.update_price('SOL', 'jupiter', 100.0, liquidity=50000, volume_24h=1000000)
    strategy.update_price('SOL', 'raydium', 105.0, liquidity=50000, volume_24h=1000000)  # 5% spread

    opportunities = strategy.find_opportunities('SOL')
    assert len(opportunities) > 0
    assert opportunities[0]['buy_exchange'] == 'jupiter'
    assert opportunities[0]['profitable'] is True


def test_spread_below_minimum():
    """Test spreads below minimum are ignored."""
    strategy = ArbitrageStrategy()
    strategy.update_price('SOL', 'jupiter', 100.0, liquidity=50000)
    strategy.update_price('SOL', 'raydium', 100.5, liquidity=50000)
    
    opportunities = strategy.find_opportunities('SOL')
    assert len(opportunities) == 0


def test_best_opportunity_selection():
    """Test selection of best opportunity."""
    strategy = ArbitrageStrategy()
    strategy.update_price('SOL', 'jupiter', 100.0, liquidity=50000)
    strategy.update_price('SOL', 'raydium', 105.0, liquidity=50000)  # 5% spread
    strategy.update_price('SOL', 'orca', 107.0, liquidity=50000)  # 7% spread

    # Must find opportunities first to populate the cache
    strategy.find_opportunities('SOL')
    best = strategy.get_best_opportunity('SOL')
    assert best is not None
    assert best['sell_exchange'] == 'orca'  # Largest spread


def test_execute_arbitrage():
    """Test recording executed arbitrage."""
    strategy = ArbitrageStrategy()
    strategy.update_price('SOL', 'jupiter', 100.0, liquidity=50000)
    strategy.update_price('SOL', 'raydium', 105.0, liquidity=50000)  # 5% spread

    opps = strategy.find_opportunities('SOL')
    execution = strategy.execute_arbitrage('SOL', opps[0])

    assert execution['symbol'] == 'SOL'
    assert len(strategy.executed_arbs) == 1


def test_execution_history():
    """Test getting execution history."""
    strategy = ArbitrageStrategy()
    strategy.update_price('SOL', 'jupiter', 100.0, liquidity=50000)
    strategy.update_price('SOL', 'raydium', 105.0, liquidity=50000)  # 5% spread

    for _ in range(5):
        opps = strategy.find_opportunities('SOL')
        strategy.execute_arbitrage('SOL', opps[0])

    history = strategy.get_execution_history(limit=3)
    assert len(history) == 3


def test_total_profit_calculation():
    """Test total profit calculation."""
    strategy = ArbitrageStrategy()
    strategy.update_price('SOL', 'jupiter', 100.0, liquidity=50000)
    strategy.update_price('SOL', 'raydium', 105.0, liquidity=50000)  # 5% spread

    opps = strategy.find_opportunities('SOL')
    strategy.execute_arbitrage('SOL', opps[0])

    total_profit = strategy.get_total_profit()
    assert total_profit > 0


def test_statistics_summary():
    """Test statistics generation."""
    strategy = ArbitrageStrategy()
    strategy.update_price('SOL', 'jupiter', 100.0, liquidity=50000)
    strategy.update_price('SOL', 'raydium', 105.0, liquidity=50000)  # 5% spread

    opps = strategy.find_opportunities('SOL')
    strategy.execute_arbitrage('SOL', opps[0])

    stats = strategy.get_statistics()
    assert stats['total_trades'] == 1
    assert stats['total_profit_usd'] > 0


def test_scan_all_symbols():
    """Test scanning all symbols for opportunities."""
    strategy = ArbitrageStrategy()
    strategy.update_price('SOL', 'jupiter', 100.0, liquidity=50000)
    strategy.update_price('SOL', 'raydium', 102.5, liquidity=50000)
    strategy.update_price('BTC', 'jupiter', 45000.0, liquidity=100000)
    strategy.update_price('BTC', 'raydium', 46000.0, liquidity=100000)
    
    all_opps = strategy.scan_all_symbols()
    assert isinstance(all_opps, dict)
