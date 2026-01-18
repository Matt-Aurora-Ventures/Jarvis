#!/usr/bin/env python3
"""
Backtesting CLI Script

Usage:
    python scripts/run_backtest.py --strategy breakout --period 3m --output reports/backtest_2026_01.html
    python scripts/run_backtest.py --strategy mean_reversion --symbol SOL --initial-capital 10000
    python scripts/run_backtest.py --strategy momentum --monte-carlo 1000
    python scripts/run_backtest.py --strategy rsi --walk-forward 5
    python scripts/run_backtest.py --strategy grid --optimize

Available strategies: breakout, mean_reversion, momentum, rsi, macd, bollinger
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Callable

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.backtesting.backtest_engine import AdvancedBacktestEngine, BacktestConfig
from core.backtesting.walk_forward import WalkForwardAnalyzer
from core.backtesting.monte_carlo import MonteCarloSimulator
from core.backtesting.parameter_optimizer import ParameterOptimizer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# BUILT-IN STRATEGIES
# ============================================================================

def strategy_breakout(engine, candle):
    """Breakout strategy: buy when price breaks above 20-day high."""
    period = 20
    if engine._current_idx < period:
        return

    # Get 20-day high
    high_20 = max(engine.high(i) for i in range(1, period + 1))
    current_close = engine.close()

    if engine.is_flat() and current_close > high_20:
        engine.buy(1.0, "Breakout above 20-day high")
    elif engine.is_long():
        # Exit on 10-day low breakout
        low_10 = min(engine.low(i) for i in range(1, 11))
        if current_close < low_10:
            engine.sell_all("Breakdown below 10-day low")


def strategy_mean_reversion(engine, candle):
    """Mean reversion strategy: buy oversold RSI, sell overbought."""
    rsi = engine.rsi(14)

    if engine.is_flat() and rsi < 30:
        engine.buy(1.0, f"RSI oversold ({rsi:.1f})")
    elif engine.is_long() and rsi > 70:
        engine.sell_all(f"RSI overbought ({rsi:.1f})")


def strategy_momentum(engine, candle):
    """Momentum strategy: buy when short SMA crosses above long SMA."""
    fast_sma = engine.sma(10)
    slow_sma = engine.sma(30)

    if engine.is_flat() and fast_sma > slow_sma:
        engine.buy(1.0, "SMA crossover bullish")
    elif engine.is_long() and fast_sma < slow_sma:
        engine.sell_all("SMA crossover bearish")


def strategy_rsi(engine, candle):
    """RSI strategy with dynamic thresholds."""
    rsi = engine.rsi(14)

    if engine.is_flat() and rsi < 35:
        engine.buy(1.0, f"RSI low ({rsi:.1f})")
    elif engine.is_long():
        if rsi > 65:
            engine.sell_all(f"RSI high ({rsi:.1f})")
        # Trailing stop: if unrealized loss > 5%
        if engine.position.entry_price > 0:
            pnl_pct = (engine.close() - engine.position.entry_price) / engine.position.entry_price
            if pnl_pct < -0.05:
                engine.sell_all("Stop loss triggered")


def strategy_macd(engine, candle):
    """MACD crossover strategy."""
    macd = engine.macd()

    if engine.is_flat() and macd['histogram'] > 0:
        engine.buy(1.0, "MACD bullish")
    elif engine.is_long() and macd['histogram'] < 0:
        engine.sell_all("MACD bearish")


def strategy_bollinger(engine, candle):
    """Bollinger Bands mean reversion strategy."""
    bb = engine.bollinger_bands(20, 2)
    close = engine.close()

    if engine.is_flat() and close < bb['lower']:
        engine.buy(1.0, "Price below lower band")
    elif engine.is_long() and close > bb['middle']:
        engine.sell_all("Price at middle band")


STRATEGIES: Dict[str, Callable] = {
    'breakout': strategy_breakout,
    'mean_reversion': strategy_mean_reversion,
    'momentum': strategy_momentum,
    'rsi': strategy_rsi,
    'macd': strategy_macd,
    'bollinger': strategy_bollinger,
}


# ============================================================================
# DATA GENERATION (for demo purposes)
# ============================================================================

def generate_sample_data(days: int = 252, start_price: float = 100.0) -> List[Dict]:
    """Generate sample OHLCV data for testing."""
    import random
    random.seed(42)

    data = []
    price = start_price

    start_date = datetime.now() - timedelta(days=days)

    for i in range(days):
        # Random walk with slight upward drift
        change = random.gauss(0.0005, 0.02)  # 0.05% drift, 2% volatility
        price = price * (1 + change)

        open_price = price * (1 + random.uniform(-0.005, 0.005))
        high = max(price, open_price) * (1 + random.uniform(0, 0.02))
        low = min(price, open_price) * (1 - random.uniform(0, 0.02))
        volume = random.uniform(1000000, 5000000)

        data.append({
            'timestamp': (start_date + timedelta(days=i)).isoformat(),
            'open': open_price,
            'high': high,
            'low': low,
            'close': price,
            'volume': volume
        })

    return data


def load_historical_data(symbol: str, period: str) -> List[Dict]:
    """
    Load historical data from files or APIs.

    Period format: 1m (1 month), 3m (3 months), 1y (1 year)
    """
    # Try to load from cached data
    cache_file = PROJECT_ROOT / 'data' / 'historical' / f'{symbol.lower()}_{period}.json'

    if cache_file.exists():
        with open(cache_file) as f:
            return json.load(f)

    # Generate sample data based on period
    period_days = {
        '1m': 30,
        '3m': 90,
        '6m': 180,
        '1y': 365,
        '2y': 730,
    }

    days = period_days.get(period, 252)
    logger.info(f"Generating {days} days of sample data for {symbol}")

    return generate_sample_data(days)


# ============================================================================
# MAIN CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Jarvis Backtesting CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        '--strategy',
        type=str,
        choices=list(STRATEGIES.keys()),
        default='momentum',
        help='Strategy to backtest'
    )

    parser.add_argument(
        '--symbol',
        type=str,
        default='SOL',
        help='Trading symbol (default: SOL)'
    )

    parser.add_argument(
        '--period',
        type=str,
        default='1y',
        help='Backtest period: 1m, 3m, 6m, 1y, 2y (default: 1y)'
    )

    parser.add_argument(
        '--initial-capital',
        type=float,
        default=10000.0,
        help='Initial capital (default: 10000)'
    )

    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Output file path (JSON or HTML)'
    )

    parser.add_argument(
        '--walk-forward',
        type=int,
        default=0,
        help='Run walk-forward analysis with N splits'
    )

    parser.add_argument(
        '--monte-carlo',
        type=int,
        default=0,
        help='Run Monte Carlo simulation with N iterations'
    )

    parser.add_argument(
        '--optimize',
        action='store_true',
        help='Run parameter optimization'
    )

    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Verbose output'
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load data
    logger.info(f"Loading {args.period} historical data for {args.symbol}")
    data = load_historical_data(args.symbol, args.period)

    if not data:
        logger.error("No data available")
        return 1

    logger.info(f"Loaded {len(data)} data points")

    # Get strategy
    strategy = STRATEGIES[args.strategy]

    # Determine date range from data
    start_date = data[0]['timestamp'][:10]
    end_date = data[-1]['timestamp'][:10]

    # Run backtest
    logger.info(f"Running backtest: {args.strategy} on {args.symbol}")
    logger.info(f"Period: {start_date} to {end_date}")
    logger.info(f"Initial capital: ${args.initial_capital:,.2f}")

    engine = AdvancedBacktestEngine()
    engine.load_data(args.symbol, data)

    config = BacktestConfig(
        symbol=args.symbol,
        start_date=start_date,
        end_date=end_date,
        initial_capital=args.initial_capital
    )

    result = engine.run(strategy, config, args.strategy)

    # Print summary
    print("\n" + "=" * 60)
    print(result.to_text())

    # Walk-forward analysis
    if args.walk_forward > 0:
        print("\n" + "=" * 60)
        print("WALK-FORWARD ANALYSIS")
        print("=" * 60)

        wf_analyzer = WalkForwardAnalyzer()
        wf_result = wf_analyzer.run_walk_forward(
            data=data,
            strategy=strategy,
            symbol=args.symbol,
            train_size=0.7,
            test_size=0.3,
            n_splits=args.walk_forward,
            initial_capital=args.initial_capital,
            strategy_name=args.strategy
        )

        print(wf_analyzer.generate_report(wf_result))

    # Monte Carlo simulation
    if args.monte_carlo > 0 and result.trades:
        print("\n" + "=" * 60)
        print("MONTE CARLO SIMULATION")
        print("=" * 60)

        # Convert trades for Monte Carlo
        trades_for_mc = [
            {
                'id': t.id,
                'entry_time': t.timestamp,
                'exit_time': t.timestamp,
                'entry_price': t.price,
                'exit_price': t.price,
                'pnl': t.pnl,
                'pnl_pct': (t.pnl / t.value * 100) if t.value else 0,
                'position_size': t.quantity,
            }
            for t in result.trades
        ]

        mc_simulator = MonteCarloSimulator()
        mc_result = mc_simulator.run_simulation(
            trades=trades_for_mc,
            n_simulations=args.monte_carlo,
            initial_capital=args.initial_capital,
            entry_timing_variance=0.05,
            exit_price_variance=0.05,
            position_size_variance=0.10,
            shuffle_trades=True
        )

        print(mc_simulator.generate_report(mc_result))

    # Parameter optimization
    if args.optimize:
        print("\n" + "=" * 60)
        print("PARAMETER OPTIMIZATION")
        print("=" * 60)

        optimizer = ParameterOptimizer()

        # Define parameter space based on strategy
        if args.strategy == 'rsi':
            optimizer.add_parameter('rsi_low', [25, 30, 35, 40])
            optimizer.add_parameter('rsi_high', [60, 65, 70, 75])

            def strategy_factory(params):
                def strategy(engine, candle):
                    rsi = engine.rsi(14)
                    if engine.is_flat() and rsi < params['rsi_low']:
                        engine.buy(1.0)
                    elif engine.is_long() and rsi > params['rsi_high']:
                        engine.sell_all()
                return strategy

        elif args.strategy == 'momentum':
            optimizer.add_parameter('fast_period', [5, 10, 15, 20])
            optimizer.add_parameter('slow_period', [20, 30, 40, 50])

            def strategy_factory(params):
                def strategy(engine, candle):
                    fast = engine.sma(params['fast_period'])
                    slow = engine.sma(params['slow_period'])
                    if engine.is_flat() and fast > slow:
                        engine.buy(1.0)
                    elif engine.is_long() and fast < slow:
                        engine.sell_all()
                return strategy

        else:
            # Generic optimization with stop loss / take profit
            optimizer.add_parameter('stop_loss', [0.05, 0.10, 0.15])
            optimizer.add_parameter('take_profit', [0.20, 0.50, 1.00])

            def strategy_factory(params):
                def strategy(engine, candle):
                    if engine.is_flat():
                        engine.buy(1.0)
                    elif engine.is_long() and engine.position.entry_price > 0:
                        pnl_pct = (engine.close() - engine.position.entry_price) / engine.position.entry_price
                        if pnl_pct < -params['stop_loss']:
                            engine.sell_all("Stop loss")
                        elif pnl_pct > params['take_profit']:
                            engine.sell_all("Take profit")
                return strategy

        opt_result = optimizer.grid_search(
            data=data,
            symbol=args.symbol,
            strategy_factory=strategy_factory,
            initial_capital=args.initial_capital,
            metric='sharpe_ratio'
        )

        print(optimizer.generate_report(opt_result))

    # Save output
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if output_path.suffix == '.json':
            with open(output_path, 'w') as f:
                json.dump(result.to_json(), f, indent=2)
            logger.info(f"Saved JSON report to {output_path}")

        elif output_path.suffix == '.html':
            html = generate_html_report(result, args)
            with open(output_path, 'w') as f:
                f.write(html)
            logger.info(f"Saved HTML report to {output_path}")

        else:
            # Default to JSON
            with open(output_path, 'w') as f:
                json.dump(result.to_json(), f, indent=2)
            logger.info(f"Saved report to {output_path}")

    return 0


def generate_html_report(result, args) -> str:
    """Generate HTML report with charts."""
    equity_data = json.dumps([
        {'x': e['timestamp'][:10], 'y': e['equity']}
        for e in result.equity_curve
    ])

    drawdown_data = json.dumps([
        {'x': d['timestamp'][:10], 'y': d['drawdown']}
        for d in result.drawdown_curve
    ])

    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Backtest Report: {args.strategy} on {args.symbol}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .metrics {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin: 20px 0; }}
        .metric {{ background: #f5f5f5; padding: 15px; border-radius: 8px; }}
        .metric h3 {{ margin: 0 0 5px 0; font-size: 14px; color: #666; }}
        .metric .value {{ font-size: 24px; font-weight: bold; }}
        .positive {{ color: #22c55e; }}
        .negative {{ color: #ef4444; }}
        .chart-container {{ height: 300px; margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Backtest Report</h1>
        <p>Strategy: <strong>{args.strategy}</strong> | Symbol: <strong>{args.symbol}</strong></p>
        <p>Period: {result.config.start_date} to {result.config.end_date}</p>

        <div class="metrics">
            <div class="metric">
                <h3>Total Return</h3>
                <div class="value {'positive' if result.metrics.total_return_pct > 0 else 'negative'}">
                    {result.metrics.total_return_pct:+.2f}%
                </div>
            </div>
            <div class="metric">
                <h3>Sharpe Ratio</h3>
                <div class="value">{result.metrics.sharpe_ratio:.2f}</div>
            </div>
            <div class="metric">
                <h3>Max Drawdown</h3>
                <div class="value negative">{result.metrics.max_drawdown:.2f}%</div>
            </div>
            <div class="metric">
                <h3>Win Rate</h3>
                <div class="value">{result.metrics.win_rate:.1f}%</div>
            </div>
            <div class="metric">
                <h3>Profit Factor</h3>
                <div class="value">{result.metrics.profit_factor:.2f}</div>
            </div>
            <div class="metric">
                <h3>Total Trades</h3>
                <div class="value">{result.metrics.total_trades}</div>
            </div>
            <div class="metric">
                <h3>Calmar Ratio</h3>
                <div class="value">{result.metrics.calmar_ratio:.2f}</div>
            </div>
            <div class="metric">
                <h3>Final Capital</h3>
                <div class="value">${result.final_capital:,.2f}</div>
            </div>
        </div>

        <h2>Equity Curve</h2>
        <div class="chart-container">
            <canvas id="equityChart"></canvas>
        </div>

        <h2>Drawdown</h2>
        <div class="chart-container">
            <canvas id="drawdownChart"></canvas>
        </div>
    </div>

    <script>
        const equityData = {equity_data};
        const drawdownData = {drawdown_data};

        new Chart(document.getElementById('equityChart'), {{
            type: 'line',
            data: {{
                labels: equityData.map(d => d.x),
                datasets: [{{
                    label: 'Equity',
                    data: equityData.map(d => d.y),
                    borderColor: '#3b82f6',
                    fill: false,
                    tension: 0.1
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false
            }}
        }});

        new Chart(document.getElementById('drawdownChart'), {{
            type: 'line',
            data: {{
                labels: drawdownData.map(d => d.x),
                datasets: [{{
                    label: 'Drawdown %',
                    data: drawdownData.map(d => -d.y),
                    borderColor: '#ef4444',
                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                    fill: true,
                    tension: 0.1
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false
            }}
        }});
    </script>
</body>
</html>
"""
    return html


if __name__ == '__main__':
    sys.exit(main())
