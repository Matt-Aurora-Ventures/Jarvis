"""
Tests for Trade Replay/Simulation System

TDD: Write tests first, then implement the functionality.

The trade replay system allows:
1. Loading historical trade data
2. Replaying trades at configurable speeds (1x, 10x, 100x)
3. Event injection for "what-if" scenarios
4. State snapshotting for comparison
5. Performance comparison between actual and simulated results
"""

import pytest
import json
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from dataclasses import dataclass


# ============================================================================
# TEST FIXTURES
# ============================================================================

@pytest.fixture
def sample_trade_history() -> List[Dict[str, Any]]:
    """Generate sample historical trade data."""
    trades = []
    base_time = datetime(2024, 1, 1, 9, 0, 0)

    for i in range(20):
        # Simulate trades over time
        entry_time = base_time + timedelta(hours=i * 4)
        exit_time = entry_time + timedelta(hours=2)

        # Alternate between winning and losing trades
        pnl = 50 if i % 3 != 0 else -30
        entry_price = 100.0 + i * 0.5
        exit_price = entry_price * (1 + pnl / 1000)

        trades.append({
            'id': f'trade_{i}',
            'token_mint': f'mint_{i % 5}',
            'token_symbol': f'TOKEN{i % 5}',
            'direction': 'LONG',
            'entry_time': entry_time.isoformat(),
            'exit_time': exit_time.isoformat(),
            'entry_price': entry_price,
            'exit_price': exit_price,
            'amount': 100.0,
            'amount_usd': 100.0,
            'pnl_usd': pnl,
            'pnl_pct': pnl / 100 * 100,
            'sentiment_grade': 'B' if i % 2 == 0 else 'A',
            'exit_reason': 'TAKE_PROFIT' if pnl > 0 else 'STOP_LOSS'
        })

    return trades


@pytest.fixture
def sample_price_events() -> List[Dict[str, Any]]:
    """Generate sample price events for replay."""
    events = []
    base_time = datetime(2024, 1, 1, 9, 0, 0)

    for i in range(100):
        timestamp = base_time + timedelta(minutes=i * 15)
        events.append({
            'timestamp': timestamp.isoformat(),
            'type': 'price_update',
            'token_mint': 'mint_0',
            'price': 100.0 + (i % 20 - 10) * 0.5,  # Oscillating price
            'volume_24h': 1000000 + i * 10000
        })

    return events


@pytest.fixture
def sample_market_events() -> List[Dict[str, Any]]:
    """Generate sample market events (liquidations, whale moves, etc.)."""
    events = []
    base_time = datetime(2024, 1, 1, 9, 0, 0)

    # Add some market events
    events.append({
        'timestamp': (base_time + timedelta(hours=2)).isoformat(),
        'type': 'liquidation',
        'amount_usd': 500000,
        'direction': 'LONG',
        'impact': 'bearish'
    })

    events.append({
        'timestamp': (base_time + timedelta(hours=5)).isoformat(),
        'type': 'whale_buy',
        'amount_usd': 1000000,
        'token_mint': 'mint_0',
        'impact': 'bullish'
    })

    events.append({
        'timestamp': (base_time + timedelta(hours=8)).isoformat(),
        'type': 'sentiment_shift',
        'old_grade': 'B',
        'new_grade': 'A',
        'token_mint': 'mint_0'
    })

    return events


@pytest.fixture
def replay_config() -> Dict[str, Any]:
    """Default replay configuration."""
    return {
        'speed': 1.0,  # 1x realtime
        'initial_balance': 10000.0,
        'enable_events': True,
        'enable_snapshots': True,
        'snapshot_interval': 10  # Every 10 events
    }


# ============================================================================
# TRADE REPLAY ENGINE TESTS
# ============================================================================

class TestTradeReplayEngine:
    """Tests for the main trade replay engine."""

    def test_engine_initialization(self):
        """Test engine can be initialized with default settings."""
        from core.simulation.trade_replay import TradeReplayEngine

        engine = TradeReplayEngine()

        assert engine is not None
        assert engine.speed == 1.0
        assert engine.state is not None

    def test_engine_initialization_with_config(self, replay_config):
        """Test engine initialization with custom config."""
        from core.simulation.trade_replay import TradeReplayEngine

        engine = TradeReplayEngine(
            speed=replay_config['speed'],
            initial_balance=replay_config['initial_balance']
        )

        assert engine.speed == 1.0
        assert engine.state.balance == 10000.0

    def test_load_trade_history(self, sample_trade_history):
        """Test loading historical trade data."""
        from core.simulation.trade_replay import TradeReplayEngine

        engine = TradeReplayEngine()
        engine.load_trades(sample_trade_history)

        assert engine.has_trades()
        assert len(engine.trades) == 20

    def test_load_price_events(self, sample_price_events):
        """Test loading price event data."""
        from core.simulation.trade_replay import TradeReplayEngine

        engine = TradeReplayEngine()
        engine.load_price_events(sample_price_events)

        assert engine.has_price_events()
        assert len(engine.price_events) == 100

    def test_load_market_events(self, sample_market_events):
        """Test loading market events."""
        from core.simulation.trade_replay import TradeReplayEngine

        engine = TradeReplayEngine()
        engine.load_market_events(sample_market_events)

        assert engine.has_market_events()
        assert len(engine.market_events) == 3


class TestSpeedControl:
    """Tests for replay speed control."""

    def test_set_speed_1x(self):
        """Test setting 1x speed."""
        from core.simulation.trade_replay import TradeReplayEngine

        engine = TradeReplayEngine()
        engine.set_speed(1.0)

        assert engine.speed == 1.0
        assert engine.delay_multiplier == 1.0

    def test_set_speed_10x(self):
        """Test setting 10x speed."""
        from core.simulation.trade_replay import TradeReplayEngine

        engine = TradeReplayEngine()
        engine.set_speed(10.0)

        assert engine.speed == 10.0
        assert engine.delay_multiplier == 0.1

    def test_set_speed_100x(self):
        """Test setting 100x speed."""
        from core.simulation.trade_replay import TradeReplayEngine

        engine = TradeReplayEngine()
        engine.set_speed(100.0)

        assert engine.speed == 100.0
        assert engine.delay_multiplier == 0.01

    def test_speed_bounds(self):
        """Test speed limits are enforced."""
        from core.simulation.trade_replay import TradeReplayEngine

        engine = TradeReplayEngine()

        # Should clamp to max
        engine.set_speed(1000.0)
        assert engine.speed <= 100.0

        # Should clamp to min
        engine.set_speed(0.001)
        assert engine.speed >= 0.1

    def test_pause_resume(self):
        """Test pausing and resuming replay."""
        from core.simulation.trade_replay import TradeReplayEngine

        engine = TradeReplayEngine()

        assert not engine.is_paused

        engine.pause()
        assert engine.is_paused

        engine.resume()
        assert not engine.is_paused


class TestEventInjection:
    """Tests for event injection functionality."""

    def test_inject_price_event(self, sample_trade_history):
        """Test injecting a price event during replay."""
        from core.simulation.trade_replay import TradeReplayEngine

        engine = TradeReplayEngine()
        engine.load_trades(sample_trade_history)

        # Inject a price spike event
        engine.inject_event({
            'type': 'price_update',
            'timestamp': '2024-01-01T12:00:00',
            'token_mint': 'mint_0',
            'price': 150.0,  # 50% spike
            'injected': True
        })

        assert engine.has_injected_events()
        assert len(engine.injected_events) == 1

    def test_inject_liquidation_event(self, sample_trade_history):
        """Test injecting a liquidation event."""
        from core.simulation.trade_replay import TradeReplayEngine

        engine = TradeReplayEngine()
        engine.load_trades(sample_trade_history)

        engine.inject_event({
            'type': 'liquidation',
            'timestamp': '2024-01-01T14:00:00',
            'amount_usd': 2000000,
            'direction': 'LONG',
            'impact': 'bearish',
            'injected': True
        })

        assert len(engine.injected_events) == 1
        assert engine.injected_events[0]['type'] == 'liquidation'

    def test_inject_sentiment_change(self, sample_trade_history):
        """Test injecting a sentiment change event."""
        from core.simulation.trade_replay import TradeReplayEngine

        engine = TradeReplayEngine()
        engine.load_trades(sample_trade_history)

        engine.inject_event({
            'type': 'sentiment_shift',
            'timestamp': '2024-01-01T10:00:00',
            'token_mint': 'mint_0',
            'old_grade': 'B',
            'new_grade': 'D',  # Downgrade
            'injected': True
        })

        # Verify event was added
        assert any(e['type'] == 'sentiment_shift' for e in engine.injected_events)

    def test_clear_injected_events(self, sample_trade_history):
        """Test clearing injected events."""
        from core.simulation.trade_replay import TradeReplayEngine

        engine = TradeReplayEngine()
        engine.load_trades(sample_trade_history)

        engine.inject_event({'type': 'test', 'timestamp': '2024-01-01T12:00:00'})
        assert len(engine.injected_events) == 1

        engine.clear_injected_events()
        assert len(engine.injected_events) == 0


class TestStateSnapshotting:
    """Tests for state snapshotting functionality."""

    def test_create_snapshot(self):
        """Test creating a state snapshot."""
        from core.simulation.trade_replay import TradeReplayEngine

        engine = TradeReplayEngine(initial_balance=10000.0)

        snapshot = engine.create_snapshot()

        assert snapshot is not None
        assert snapshot['balance'] == 10000.0
        assert 'timestamp' in snapshot
        assert 'event_index' in snapshot

    def test_restore_snapshot(self):
        """Test restoring from a snapshot."""
        from core.simulation.trade_replay import TradeReplayEngine

        engine = TradeReplayEngine(initial_balance=10000.0)

        # Create snapshot at initial state
        snapshot = engine.create_snapshot()

        # Modify state
        engine.state.balance = 5000.0
        engine.state.positions = {'test': {'amount': 100}}

        # Restore
        engine.restore_snapshot(snapshot)

        assert engine.state.balance == 10000.0
        assert len(engine.state.positions) == 0

    def test_snapshot_includes_positions(self, sample_trade_history):
        """Test that snapshots include position data."""
        from core.simulation.trade_replay import TradeReplayEngine

        engine = TradeReplayEngine(initial_balance=10000.0)
        engine.load_trades(sample_trade_history)

        # Simulate having an open position
        engine.state.positions = {
            'position_1': {
                'token_mint': 'mint_0',
                'amount': 100,
                'entry_price': 100.0
            }
        }

        snapshot = engine.create_snapshot()

        assert 'positions' in snapshot
        assert 'position_1' in snapshot['positions']

    def test_snapshot_history(self, sample_trade_history):
        """Test that snapshot history is maintained."""
        from core.simulation.trade_replay import TradeReplayEngine

        engine = TradeReplayEngine(initial_balance=10000.0)

        # Create multiple snapshots
        for i in range(5):
            engine.state.balance = 10000.0 + i * 100
            engine.create_snapshot(save_to_history=True)

        assert len(engine.snapshot_history) == 5
        assert engine.snapshot_history[0]['balance'] == 10000.0
        assert engine.snapshot_history[4]['balance'] == 10400.0

    def test_get_snapshot_at_time(self, sample_trade_history):
        """Test getting snapshot closest to a specific time."""
        from core.simulation.trade_replay import TradeReplayEngine

        engine = TradeReplayEngine(initial_balance=10000.0)

        # Create snapshots at different times
        times = [
            '2024-01-01T09:00:00',
            '2024-01-01T12:00:00',
            '2024-01-01T15:00:00'
        ]

        for i, t in enumerate(times):
            engine.state.balance = 10000.0 + i * 500
            engine.create_snapshot(
                save_to_history=True,
                timestamp=datetime.fromisoformat(t)
            )

        # Get snapshot closest to 11:00
        snapshot = engine.get_snapshot_at_time('2024-01-01T11:00:00')

        assert snapshot is not None
        # Should return the 09:00 snapshot (closest before 11:00)
        assert snapshot['balance'] == 10000.0


class TestReplayExecution:
    """Tests for actual replay execution."""

    @pytest.mark.asyncio
    async def test_run_replay_basic(self, sample_trade_history):
        """Test running a basic replay."""
        from core.simulation.trade_replay import TradeReplayEngine

        engine = TradeReplayEngine(initial_balance=10000.0)
        engine.load_trades(sample_trade_history)
        engine.set_speed(100.0)  # Fast replay

        result = await engine.run_replay()

        assert result is not None
        assert result.completed
        assert result.trades_replayed > 0

    @pytest.mark.asyncio
    async def test_run_replay_with_events(self, sample_trade_history, sample_price_events):
        """Test replay with price events."""
        from core.simulation.trade_replay import TradeReplayEngine

        engine = TradeReplayEngine(initial_balance=10000.0)
        engine.load_trades(sample_trade_history)
        engine.load_price_events(sample_price_events)
        engine.set_speed(100.0)

        result = await engine.run_replay()

        assert result is not None
        assert result.events_processed > 0

    @pytest.mark.asyncio
    async def test_run_replay_with_injected_events(self, sample_trade_history):
        """Test replay with injected events affecting outcome."""
        from core.simulation.trade_replay import TradeReplayEngine

        engine = TradeReplayEngine(initial_balance=10000.0)
        engine.load_trades(sample_trade_history)
        engine.set_speed(100.0)

        # Inject a price crash event
        engine.inject_event({
            'type': 'price_update',
            'timestamp': '2024-01-01T10:00:00',
            'token_mint': 'mint_0',
            'price': 50.0,  # 50% crash
            'injected': True
        })

        result = await engine.run_replay()

        assert result is not None
        assert result.injected_events_applied > 0

    @pytest.mark.asyncio
    async def test_replay_callbacks(self, sample_trade_history):
        """Test that callbacks are invoked during replay."""
        from core.simulation.trade_replay import TradeReplayEngine

        engine = TradeReplayEngine(initial_balance=10000.0)
        engine.load_trades(sample_trade_history)
        engine.set_speed(100.0)

        events_received = []

        def on_event(event):
            events_received.append(event)

        engine.on_event(on_event)

        await engine.run_replay()

        assert len(events_received) > 0

    @pytest.mark.asyncio
    async def test_step_through_replay(self, sample_trade_history):
        """Test stepping through replay one event at a time."""
        from core.simulation.trade_replay import TradeReplayEngine

        engine = TradeReplayEngine(initial_balance=10000.0)
        engine.load_trades(sample_trade_history)

        # Step through first 5 events
        for i in range(5):
            event = await engine.step()
            assert event is not None

        assert engine.current_event_index == 5


class TestPerformanceComparison:
    """Tests for comparing actual vs simulated performance."""

    def test_calculate_performance_metrics(self, sample_trade_history):
        """Test calculating performance metrics from trades."""
        from core.simulation.trade_replay import TradeReplayEngine

        engine = TradeReplayEngine(initial_balance=10000.0)
        engine.load_trades(sample_trade_history)

        metrics = engine.calculate_metrics()

        assert 'total_pnl' in metrics
        assert 'win_rate' in metrics
        assert 'total_trades' in metrics
        assert 'sharpe_ratio' in metrics
        assert 'max_drawdown' in metrics

    @pytest.mark.asyncio
    async def test_compare_actual_vs_simulated(self, sample_trade_history):
        """Test comparing actual trades vs simulated with modified params."""
        from core.simulation.trade_replay import TradeReplayEngine

        engine = TradeReplayEngine(initial_balance=10000.0)
        engine.load_trades(sample_trade_history)
        engine.set_speed(100.0)

        # Run simulation with different parameters
        result = await engine.run_replay(
            modified_params={
                'take_profit_multiplier': 1.5,  # 50% higher TP
                'stop_loss_multiplier': 0.5     # 50% tighter SL
            }
        )

        comparison = engine.compare_results()

        assert 'actual' in comparison
        assert 'simulated' in comparison
        assert 'difference' in comparison

    def test_performance_diff_calculation(self, sample_trade_history):
        """Test calculating performance difference."""
        from core.simulation.trade_replay import TradeReplayEngine, PerformanceComparison

        actual_metrics = {
            'total_pnl': 500.0,
            'win_rate': 0.65,
            'sharpe_ratio': 1.2,
            'max_drawdown': 0.08
        }

        simulated_metrics = {
            'total_pnl': 750.0,
            'win_rate': 0.70,
            'sharpe_ratio': 1.5,
            'max_drawdown': 0.05
        }

        comparison = PerformanceComparison.calculate(actual_metrics, simulated_metrics)

        assert comparison.pnl_difference == 250.0
        assert comparison.win_rate_difference == 0.05
        assert comparison.sharpe_improvement == pytest.approx(0.3, rel=0.01)
        assert comparison.drawdown_improvement == pytest.approx(0.03, rel=0.01)

    def test_generate_comparison_report(self, sample_trade_history):
        """Test generating a comparison report."""
        from core.simulation.trade_replay import TradeReplayEngine

        engine = TradeReplayEngine(initial_balance=10000.0)
        engine.load_trades(sample_trade_history)

        # Set up mock comparison data
        engine.actual_metrics = {
            'total_pnl': 500.0,
            'win_rate': 0.65,
            'total_trades': 20
        }
        engine.simulated_metrics = {
            'total_pnl': 750.0,
            'win_rate': 0.70,
            'total_trades': 18
        }

        report = engine.generate_comparison_report()

        assert 'actual' in report.lower() or 'ACTUAL' in report
        assert 'simulated' in report.lower() or 'SIMULATED' in report


class TestWhatIfScenarios:
    """Tests for what-if scenario analysis."""

    @pytest.mark.asyncio
    async def test_what_if_earlier_entry(self, sample_trade_history):
        """Test what-if scenario with earlier entry times."""
        from core.simulation.trade_replay import TradeReplayEngine, WhatIfScenario

        engine = TradeReplayEngine(initial_balance=10000.0)
        engine.load_trades(sample_trade_history)
        engine.set_speed(100.0)

        scenario = WhatIfScenario(
            name='earlier_entry',
            description='Enter trades 1 hour earlier',
            modifications={
                'entry_time_offset': timedelta(hours=-1)
            }
        )

        result = await engine.run_scenario(scenario)

        assert result is not None
        assert result.scenario_name == 'earlier_entry'
        assert 'total_pnl' in result.metrics

    @pytest.mark.asyncio
    async def test_what_if_tighter_stop_loss(self, sample_trade_history):
        """Test what-if scenario with tighter stop losses."""
        from core.simulation.trade_replay import TradeReplayEngine, WhatIfScenario

        engine = TradeReplayEngine(initial_balance=10000.0)
        engine.load_trades(sample_trade_history)
        engine.set_speed(100.0)

        scenario = WhatIfScenario(
            name='tight_sl',
            description='Use 5% stop loss instead of 10%',
            modifications={
                'stop_loss_pct': 0.05
            }
        )

        result = await engine.run_scenario(scenario)

        assert result is not None
        assert result.scenario_name == 'tight_sl'

    @pytest.mark.asyncio
    async def test_what_if_higher_grade_only(self, sample_trade_history):
        """Test what-if scenario trading only A-grade tokens."""
        from core.simulation.trade_replay import TradeReplayEngine, WhatIfScenario

        engine = TradeReplayEngine(initial_balance=10000.0)
        engine.load_trades(sample_trade_history)
        engine.set_speed(100.0)

        scenario = WhatIfScenario(
            name='a_grade_only',
            description='Only trade A-grade sentiment tokens',
            modifications={
                'min_grade': 'A'
            }
        )

        result = await engine.run_scenario(scenario)

        # Should have fewer trades (filtered to A-grade only)
        assert result is not None
        assert result.trades_executed <= len([t for t in sample_trade_history if t.get('sentiment_grade') == 'A'])

    @pytest.mark.asyncio
    async def test_run_multiple_scenarios(self, sample_trade_history):
        """Test running multiple what-if scenarios."""
        from core.simulation.trade_replay import TradeReplayEngine, WhatIfScenario

        engine = TradeReplayEngine(initial_balance=10000.0)
        engine.load_trades(sample_trade_history)
        engine.set_speed(100.0)

        scenarios = [
            WhatIfScenario(name='baseline', description='No changes', modifications={}),
            WhatIfScenario(name='tight_sl', description='5% SL', modifications={'stop_loss_pct': 0.05}),
            WhatIfScenario(name='wide_tp', description='50% TP', modifications={'take_profit_pct': 0.50})
        ]

        results = await engine.run_scenarios(scenarios)

        assert len(results) == 3
        assert all(r.scenario_name in ['baseline', 'tight_sl', 'wide_tp'] for r in results)


class TestReplayState:
    """Tests for replay state management."""

    def test_initial_state(self):
        """Test initial state is correct."""
        from core.simulation.trade_replay import ReplayState

        state = ReplayState(initial_balance=10000.0)

        assert state.balance == 10000.0
        assert len(state.positions) == 0
        assert len(state.trade_history) == 0
        assert state.pnl == 0.0

    def test_state_update_on_trade(self):
        """Test state updates correctly on trade."""
        from core.simulation.trade_replay import ReplayState

        state = ReplayState(initial_balance=10000.0)

        # Open a position
        state.open_position(
            position_id='pos_1',
            token_mint='mint_0',
            amount=100.0,
            entry_price=100.0
        )

        assert len(state.positions) == 1
        assert state.balance == 9900.0  # 10000 - 100

    def test_state_update_on_close(self):
        """Test state updates correctly on position close."""
        from core.simulation.trade_replay import ReplayState

        state = ReplayState(initial_balance=10000.0)

        # Open position
        state.open_position(
            position_id='pos_1',
            token_mint='mint_0',
            amount=100.0,
            entry_price=100.0
        )

        # Close with profit
        pnl = state.close_position('pos_1', exit_price=110.0)

        assert len(state.positions) == 0
        assert state.pnl == 10.0  # 10% gain on 100
        assert state.balance == 10010.0

    def test_state_to_dict(self):
        """Test state serialization."""
        from core.simulation.trade_replay import ReplayState

        state = ReplayState(initial_balance=10000.0)
        state.pnl = 500.0

        data = state.to_dict()

        assert data['balance'] == 10000.0
        assert data['pnl'] == 500.0
        assert 'positions' in data

    def test_state_from_dict(self):
        """Test state deserialization."""
        from core.simulation.trade_replay import ReplayState

        data = {
            'balance': 12000.0,
            'pnl': 2000.0,
            'positions': {},
            'trade_history': []
        }

        state = ReplayState.from_dict(data)

        assert state.balance == 12000.0
        assert state.pnl == 2000.0


class TestReplayResult:
    """Tests for replay result data class."""

    def test_result_initialization(self):
        """Test result initialization."""
        from core.simulation.trade_replay import ReplayResult

        result = ReplayResult(
            completed=True,
            trades_replayed=20,
            events_processed=100,
            final_balance=12000.0,
            total_pnl=2000.0
        )

        assert result.completed
        assert result.trades_replayed == 20
        assert result.total_pnl == 2000.0

    def test_result_to_json(self):
        """Test result JSON serialization."""
        from core.simulation.trade_replay import ReplayResult

        result = ReplayResult(
            completed=True,
            trades_replayed=20,
            events_processed=100,
            final_balance=12000.0,
            total_pnl=2000.0
        )

        json_data = result.to_json()

        assert 'completed' in json_data
        assert 'trades_replayed' in json_data
        assert json_data['total_pnl'] == 2000.0

    def test_result_summary(self):
        """Test result summary generation."""
        from core.simulation.trade_replay import ReplayResult

        result = ReplayResult(
            completed=True,
            trades_replayed=20,
            events_processed=100,
            final_balance=12000.0,
            total_pnl=2000.0,
            win_rate=0.65
        )

        summary = result.summary()

        assert 'Trades' in summary or 'trades' in summary.lower()
        assert '20' in summary
        assert '2000' in summary or '2,000' in summary


class TestIntegration:
    """Integration tests for the complete replay system."""

    @pytest.mark.asyncio
    async def test_full_replay_workflow(self, sample_trade_history, sample_price_events):
        """Test complete replay workflow."""
        from core.simulation.trade_replay import TradeReplayEngine, WhatIfScenario

        # 1. Initialize engine
        engine = TradeReplayEngine(initial_balance=10000.0)

        # 2. Load data
        engine.load_trades(sample_trade_history)
        engine.load_price_events(sample_price_events)

        # 3. Set speed
        engine.set_speed(100.0)

        # 4. Create initial snapshot
        initial_snapshot = engine.create_snapshot(save_to_history=True)

        # 5. Run baseline replay
        baseline_result = await engine.run_replay()

        # 6. Restore and run what-if scenario
        engine.restore_snapshot(initial_snapshot)

        scenario = WhatIfScenario(
            name='test_scenario',
            description='Test',
            modifications={'stop_loss_pct': 0.05}
        )

        scenario_result = await engine.run_scenario(scenario)

        # 7. Compare results
        comparison = engine.compare_results()

        assert baseline_result.completed
        assert scenario_result is not None
        assert comparison is not None

    @pytest.mark.asyncio
    async def test_replay_with_callbacks_and_snapshots(self, sample_trade_history):
        """Test replay with callbacks and automatic snapshots."""
        from core.simulation.trade_replay import TradeReplayEngine

        engine = TradeReplayEngine(initial_balance=10000.0)
        engine.load_trades(sample_trade_history)
        engine.set_speed(100.0)

        trade_events = []
        snapshot_events = []

        def on_trade(event):
            if event.get('type') == 'trade':
                trade_events.append(event)

        def on_snapshot(snapshot):
            snapshot_events.append(snapshot)

        engine.on_event(on_trade)
        engine.on_snapshot(on_snapshot)
        engine.set_snapshot_interval(5)  # Snapshot every 5 trades

        await engine.run_replay()

        assert len(trade_events) > 0
        assert len(snapshot_events) > 0


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_trade_history(self):
        """Test handling empty trade history."""
        from core.simulation.trade_replay import TradeReplayEngine

        engine = TradeReplayEngine()
        engine.load_trades([])

        assert not engine.has_trades()

    def test_invalid_speed(self):
        """Test handling invalid speed values."""
        from core.simulation.trade_replay import TradeReplayEngine

        engine = TradeReplayEngine()

        # Negative speed should raise or clamp
        with pytest.raises(ValueError):
            engine.set_speed(-1.0)

    def test_restore_invalid_snapshot(self):
        """Test handling invalid snapshot data."""
        from core.simulation.trade_replay import TradeReplayEngine

        engine = TradeReplayEngine()

        with pytest.raises(ValueError):
            engine.restore_snapshot({'invalid': 'data'})

    @pytest.mark.asyncio
    async def test_replay_without_trades(self):
        """Test replay when no trades are loaded."""
        from core.simulation.trade_replay import TradeReplayEngine

        engine = TradeReplayEngine()

        with pytest.raises(ValueError):
            await engine.run_replay()

    def test_inject_event_invalid_type(self):
        """Test injecting event with invalid type."""
        from core.simulation.trade_replay import TradeReplayEngine

        engine = TradeReplayEngine()

        with pytest.raises(ValueError):
            engine.inject_event({'invalid': 'no type field'})
