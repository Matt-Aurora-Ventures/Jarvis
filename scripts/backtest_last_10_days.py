#!/usr/bin/env python3
"""
Backtest proposed improvements against last 10 days of actual data.

Simulates:
1. Baseline: Take all bullish calls with fixed 15% TP / 15% SL
2. Current filters: SIMPLE mode from optimizer
3. Proposed improvements: Each strategy independently
4. Combined: All improvements together
"""

import pandas as pd
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Tuple

ROOT = Path(__file__).resolve().parents[1]
CSV_FILE = ROOT / "data" / "analysis" / "unified_calls_data.csv"

@dataclass
class BacktestResult:
    """Result of a strategy backtest."""
    strategy_name: str
    total_calls: int
    accepted: int
    wins: int
    losses: int
    win_rate: float
    avg_win_pct: float
    avg_loss_pct: float
    total_pnl: float
    expected_value: float
    accepted_tokens: List[str]

def load_data() -> pd.DataFrame:
    """Load the CSV data."""
    if not CSV_FILE.exists():
        raise FileNotFoundError(f"CSV not found: {CSV_FILE}")

    df = pd.read_csv(CSV_FILE)
    return df

def simulate_15pct_tp_sl(row: pd.Series) -> Tuple[bool, float]:
    """
    Simulate 15% TP / 15% SL strategy.
    Returns (hit_tp_first, pnl_pct)
    """
    max_gain = row['max_gain_pct'] if pd.notna(row['max_gain_pct']) else 0
    max_loss = abs(row['max_loss_pct']) if pd.notna(row['max_loss_pct']) else 0

    # Did it hit TP before SL?
    hit_tp = max_gain >= 15.0
    hit_sl = max_loss >= 15.0

    if hit_tp and not hit_sl:
        return True, 15.0  # Win
    elif hit_sl and not hit_tp:
        return False, -15.0  # Loss
    elif hit_tp and hit_sl:
        # Both hit - assume SL hit first for conservative estimate
        # (In reality, would need tick data to know which came first)
        return False, -15.0
    else:
        # Neither hit - use final P/L or 0
        final_pct = row['final_pct'] if pd.notna(row['final_pct']) else 0
        if abs(final_pct) < 15:
            # Exit at current price (neither TP nor SL hit yet)
            return final_pct > 0, final_pct
        else:
            return final_pct > 0, min(max(final_pct, -15), 15)

def simulate_dynamic_tp_sl(row: pd.Series, category: str) -> Tuple[bool, float]:
    """
    Strategy 1: Dynamic TP/SL based on asset volatility.
    """
    max_gain = row['max_gain_pct'] if pd.notna(row['max_gain_pct']) else 0
    max_loss = abs(row['max_loss_pct']) if pd.notna(row['max_loss_pct']) else 0

    # Determine TP/SL by category
    if category == 'meme':
        tp, sl = 20.0, 12.0
    elif category == 'other':  # wrapped/blue chips
        tp, sl = 12.0, 8.0
    else:
        tp, sl = 15.0, 15.0  # default

    hit_tp = max_gain >= tp
    hit_sl = max_loss >= sl

    if hit_tp and not hit_sl:
        return True, tp
    elif hit_sl and not hit_tp:
        return False, -sl
    elif hit_tp and hit_sl:
        return False, -sl  # Conservative: assume SL first
    else:
        final_pct = row['final_pct'] if pd.notna(row['final_pct']) else 0
        return final_pct > 0, min(max(final_pct, -sl), tp)

def simulate_trailing_stop(row: pd.Series) -> Tuple[bool, float]:
    """
    Strategy 2: Trailing stop after profit.
    - Once +10%, move SL to breakeven
    - Once +15%, trail at -5% from peak
    """
    max_gain = row['max_gain_pct'] if pd.notna(row['max_gain_pct']) else 0
    final_pct = row['final_pct'] if pd.notna(row['final_pct']) else 0

    # Did it hit +15% TP?
    if max_gain >= 15.0:
        # Trailing stop at peak - 5%
        exit_price = max_gain - 5.0
        return True, max(exit_price, 0)  # At worst breakeven
    elif max_gain >= 10.0:
        # Hit +10%, SL moved to breakeven
        # Check if it dumped below entry after that
        if final_pct < 0:
            return True, 0.0  # Breakeven exit
        else:
            return True, final_pct  # Still in profit
    else:
        # Never hit +10%, use normal 15% SL
        if final_pct <= -15.0:
            return False, -15.0
        else:
            return final_pct > 0, final_pct

def simulate_time_based_exit(row: pd.Series) -> Tuple[bool, float]:
    """
    Strategy 3: Time-based exit (simulated).
    Exit if no 5%+ movement - assume 50% of stagnant positions exit early at -2%.
    """
    max_gain = row['max_gain_pct'] if pd.notna(row['max_gain_pct']) else 0
    max_loss = abs(row['max_loss_pct']) if pd.notna(row['max_loss_pct']) else 0
    final_pct = row['final_pct'] if pd.notna(row['final_pct']) else 0

    # Check for movement
    if max_gain < 5.0 and max_loss < 5.0:
        # Stagnant - exit early with small loss
        return False, -2.0

    # Normal 15% TP/SL
    hit_tp = max_gain >= 15.0
    hit_sl = max_loss >= 15.0

    if hit_tp:
        return True, 15.0
    elif hit_sl:
        return False, -15.0
    else:
        return final_pct > 0, final_pct

def baseline_filter(row: pd.Series) -> bool:
    """Baseline: Accept all BULLISH."""
    return row['verdict'] == 'BULLISH'

def current_simple_filter(row: pd.Series) -> bool:
    """Current SIMPLE mode filter from optimizer."""
    if row['verdict'] != 'BULLISH':
        return False

    ratio = row['buy_sell_ratio'] if pd.notna(row['buy_sell_ratio']) else 0
    change_24h = row['change_24h'] if pd.notna(row['change_24h']) else 0

    # SIMPLE mode: ratio >= 1.2, pump <= 200%
    return ratio >= 1.2 and change_24h <= 200

def improved_filter_conservative(row: pd.Series) -> bool:
    """Improved filter: Stricter quality requirements."""
    if row['verdict'] != 'BULLISH':
        return False

    ratio = row['buy_sell_ratio'] if pd.notna(row['buy_sell_ratio']) else 0
    change_24h = row['change_24h'] if pd.notna(row['change_24h']) else 0
    score = row['initial_score'] if pd.notna(row['initial_score']) else 0

    # Stricter: ratio >= 2.0, pump <= 100%, score 0.5-0.7
    return (ratio >= 2.0 and
            change_24h <= 100 and
            0.5 <= score <= 0.7)

def improved_filter_balanced(row: pd.Series) -> bool:
    """Improved filter: Balanced quality/frequency."""
    if row['verdict'] != 'BULLISH':
        return False

    ratio = row['buy_sell_ratio'] if pd.notna(row['buy_sell_ratio']) else 0
    change_24h = row['change_24h'] if pd.notna(row['change_24h']) else 0
    has_momentum = row['has_momentum_mention'] if pd.notna(row['has_momentum_mention']) else False

    # Balanced: ratio >= 1.5, pump <= 150%, no momentum hype
    return (ratio >= 1.5 and
            change_24h <= 150 and
            not has_momentum)

def pre_market_research_filter(row: pd.Series) -> bool:
    """
    Strategy 8: Pre-market research (simulated).
    Assume tokens with very high pump (>500%) or very low ratio (<1.0) fail basic checks.
    """
    if row['verdict'] != 'BULLISH':
        return False

    change_24h = row['change_24h'] if pd.notna(row['change_24h']) else 0
    ratio = row['buy_sell_ratio'] if pd.notna(row['buy_sell_ratio']) else 0

    # Fail basic hygiene checks
    if change_24h > 500:  # Already mega-pumped
        return False
    if ratio < 1.0:  # More sellers than buyers
        return False

    # Pass to normal filter
    return ratio >= 1.5 and change_24h <= 200

def run_strategy(df: pd.DataFrame,
                 filter_func,
                 tp_sl_func,
                 strategy_name: str) -> BacktestResult:
    """Run a complete backtest for a strategy."""

    results = []
    accepted_tokens = []

    for idx, row in df.iterrows():
        # Apply filter
        if not filter_func(row):
            continue

        # Accepted
        accepted_tokens.append(row['symbol'])
        category = row['category'] if 'category' in row else 'meme'

        # Simulate TP/SL
        if tp_sl_func == simulate_dynamic_tp_sl:
            hit_tp, pnl = tp_sl_func(row, category)
        else:
            hit_tp, pnl = tp_sl_func(row)

        results.append({
            'symbol': row['symbol'],
            'hit_tp': hit_tp,
            'pnl': pnl
        })

    # Calculate metrics
    total_calls = len(df[df['verdict'] == 'BULLISH'])
    accepted = len(results)
    wins = [r for r in results if r['hit_tp']]
    losses = [r for r in results if not r['hit_tp']]

    win_rate = len(wins) / accepted if accepted > 0 else 0
    avg_win = sum(r['pnl'] for r in wins) / len(wins) if wins else 0
    avg_loss = sum(r['pnl'] for r in losses) / len(losses) if losses else 0
    total_pnl = sum(r['pnl'] for r in results)
    expected_value = (win_rate * avg_win) + ((1 - win_rate) * avg_loss)

    return BacktestResult(
        strategy_name=strategy_name,
        total_calls=total_calls,
        accepted=accepted,
        wins=len(wins),
        losses=len(losses),
        win_rate=win_rate,
        avg_win_pct=avg_win,
        avg_loss_pct=avg_loss,
        total_pnl=total_pnl,
        expected_value=expected_value,
        accepted_tokens=accepted_tokens
    )

def print_results(results: List[BacktestResult]):
    """Print formatted comparison table."""
    print("\n" + "=" * 120)
    print("BACKTEST RESULTS: Last 10 Days Data (Jan 17-25, 2026)")
    print("=" * 120)
    print(f"{'Strategy':<40} {'Total':>6} {'Accept':>6} {'Wins':>6} {'Loss':>6} "
          f"{'WinRate':>8} {'AvgWin':>8} {'AvgLoss':>9} {'TotPnL':>8} {'ExpVal':>8}")
    print("-" * 120)

    # Sort by expected value
    results = sorted(results, key=lambda r: r.expected_value, reverse=True)

    for r in results:
        print(f"{r.strategy_name:<40} {r.total_calls:>6} {r.accepted:>6} "
              f"{r.wins:>6} {r.losses:>6} "
              f"{r.win_rate*100:>7.1f}% {r.avg_win_pct:>7.1f}% {r.avg_loss_pct:>8.1f}% "
              f"{r.total_pnl:>7.1f}% {r.expected_value:>7.1f}%")

    print("-" * 120)

    # Show best strategy detail
    if results:
        best = results[0]
        print(f"\n{'BEST STRATEGY: ' + best.strategy_name:^120}")
        print("-" * 120)
        print(f"Expected Value: {best.expected_value:+.2f}% per trade")
        print(f"Win Rate: {best.win_rate*100:.1f}%")
        print(f"Total P/L: {best.total_pnl:+.1f}% on {best.accepted} trades")
        print(f"Accepted tokens: {', '.join(best.accepted_tokens)}")

        # Risk metrics
        if best.accepted > 0:
            sharpe_approx = best.expected_value / abs(best.avg_loss_pct) if best.avg_loss_pct != 0 else 0
            print(f"Risk/Reward: {abs(best.avg_win_pct / best.avg_loss_pct):.2f}" if best.avg_loss_pct != 0 else "N/A")
            print(f"Sharpe (approx): {sharpe_approx:.2f}")

    print("\n")

def main():
    """Run all backtests."""
    print("\nLoading data...")
    df = load_data()
    print(f"Loaded {len(df)} calls")
    print(f"Bullish calls: {len(df[df['verdict'] == 'BULLISH'])}")

    # Define strategies to test
    strategies = [
        # Baseline
        ("1. Baseline: All BULLISH (15% TP/SL)",
         baseline_filter, simulate_15pct_tp_sl),

        # Current
        ("2. Current SIMPLE Mode (15% TP/SL)",
         current_simple_filter, simulate_15pct_tp_sl),

        # Proposed improvements
        ("3. Dynamic TP/SL by Volatility",
         baseline_filter, simulate_dynamic_tp_sl),

        ("4. Trailing Stop Loss",
         baseline_filter, simulate_trailing_stop),

        ("5. Time-Based Early Exit",
         baseline_filter, simulate_time_based_exit),

        ("6. Pre-Market Research Filter (15% TP/SL)",
         pre_market_research_filter, simulate_15pct_tp_sl),

        ("7. Improved Conservative Filter (15% TP/SL)",
         improved_filter_conservative, simulate_15pct_tp_sl),

        ("8. Improved Balanced Filter (15% TP/SL)",
         improved_filter_balanced, simulate_15pct_tp_sl),

        # Combinations
        ("9. Balanced Filter + Dynamic TP/SL",
         improved_filter_balanced, simulate_dynamic_tp_sl),

        ("10. Balanced Filter + Trailing Stop",
         improved_filter_balanced, simulate_trailing_stop),

        ("11. SIMPLE Mode + Dynamic TP/SL",
         current_simple_filter, simulate_dynamic_tp_sl),

        ("12. SIMPLE Mode + Trailing Stop",
         current_simple_filter, simulate_trailing_stop),
    ]

    # Run all strategies
    results = []
    for name, filter_func, tp_sl_func in strategies:
        result = run_strategy(df, filter_func, tp_sl_func, name)
        results.append(result)

    # Print comparison
    print_results(results)

    # Export results
    results_file = ROOT / "data" / "analysis" / "strategy_backtest_10days.json"
    import json
    with open(results_file, 'w') as f:
        json.dump([{
            'strategy': r.strategy_name,
            'total_calls': r.total_calls,
            'accepted': r.accepted,
            'wins': r.wins,
            'losses': r.losses,
            'win_rate': r.win_rate,
            'avg_win': r.avg_win_pct,
            'avg_loss': r.avg_loss_pct,
            'total_pnl': r.total_pnl,
            'expected_value': r.expected_value,
            'tokens': r.accepted_tokens
        } for r in results], f, indent=2)

    print(f"Results saved to: {results_file}\n")

if __name__ == "__main__":
    main()
