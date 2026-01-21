"""
Combined Exit Strategy Analysis for Volatile Early Runners.

Tests combinations of:
- Wider stop losses (-20%, -25%, -30%)
- Sentiment-based exits (verdict flip, score drop)
- Time-based exits
- Volume/ratio change exits

Goal: Find optimal combo for highly volatile tokens where -15% SL is too tight.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import re

ROOT = Path(__file__).resolve().parents[1]
PREDICTIONS_FILE = ROOT / "bots" / "buy_tracker" / "predictions_history.json"


@dataclass
class PricePoint:
    """A single price observation."""
    timestamp: str
    price: float
    verdict: str
    score: float
    change_24h: Optional[float] = None
    buy_sell_ratio: Optional[float] = None


@dataclass
class TokenHistory:
    """Complete history for a token."""
    symbol: str
    contract: str
    price_points: List[PricePoint]
    entry_price: float  # Price at first BULLISH call
    entry_time: str
    entry_score: float
    max_gain_pct: float
    max_loss_pct: float
    final_pct: float


def extract_metrics(reasoning: str) -> Dict:
    """Extract metrics from reasoning text."""
    metrics = {}

    # Extract change_24h
    change_match = re.search(r'24h[:\s]*([+-]?\d+\.?\d*)%', reasoning)
    if change_match:
        try:
            metrics['change_24h'] = float(change_match.group(1))
        except ValueError:
            pass

    # Extract buy/sell ratio
    ratio_patterns = [
        r'ratio[:\s]*(\d+\.?\d*)',
        r'(\d+\.?\d*)x\s*(?:buy|ratio)',
        r'buy[/-]sell[:\s]*(\d+\.?\d*)',
    ]
    for pattern in ratio_patterns:
        match = re.search(pattern, reasoning, re.IGNORECASE)
        if match:
            try:
                metrics['buy_sell_ratio'] = float(match.group(1))
                break
            except ValueError:
                pass

    return metrics


def load_token_histories() -> Dict[str, TokenHistory]:
    """Load and organize all token price histories."""
    if not PREDICTIONS_FILE.exists():
        print(f"File not found: {PREDICTIONS_FILE}")
        return {}

    with open(PREDICTIONS_FILE, 'r', encoding='utf-8') as f:
        history = json.load(f)

    # Organize by token
    token_data: Dict[str, List[PricePoint]] = {}

    for entry in history:
        timestamp = entry.get('timestamp', '')
        for symbol, data in entry.get('token_predictions', {}).items():
            if symbol not in token_data:
                token_data[symbol] = []

            price = data.get('price_at_prediction', 0)
            if price <= 0:
                continue

            metrics = extract_metrics(data.get('reasoning', ''))

            token_data[symbol].append(PricePoint(
                timestamp=timestamp,
                price=price,
                verdict=data.get('verdict', 'NEUTRAL'),
                score=data.get('score', 0),
                change_24h=metrics.get('change_24h'),
                buy_sell_ratio=metrics.get('buy_sell_ratio'),
            ))

    # Build token histories
    histories = {}

    for symbol, points in token_data.items():
        if len(points) < 2:
            continue

        # Sort by timestamp
        points.sort(key=lambda p: p.timestamp)

        # Find first BULLISH call as entry
        entry_idx = None
        for i, p in enumerate(points):
            if p.verdict == 'BULLISH':
                entry_idx = i
                break

        if entry_idx is None:
            continue

        entry = points[entry_idx]
        entry_price = entry.price

        # Calculate metrics from entry forward
        max_gain = 0
        max_loss = 0

        for p in points[entry_idx:]:
            change = ((p.price - entry_price) / entry_price) * 100
            if change > max_gain:
                max_gain = change
            if change < max_loss:
                max_loss = change

        final_price = points[-1].price
        final_pct = ((final_price - entry_price) / entry_price) * 100

        histories[symbol] = TokenHistory(
            symbol=symbol,
            contract='',
            price_points=points[entry_idx:],
            entry_price=entry_price,
            entry_time=entry.timestamp,
            entry_score=entry.score,
            max_gain_pct=max_gain,
            max_loss_pct=max_loss,
            final_pct=final_pct,
        )

    return histories


def simulate_exit_strategy(
    history: TokenHistory,
    tp_pct: float,
    sl_pct: float,
    exit_on_bearish: bool = False,
    exit_on_score_drop: Optional[float] = None,
    max_hold_periods: Optional[int] = None,
    exit_on_ratio_drop: Optional[float] = None,
) -> Tuple[float, str]:
    """
    Simulate an exit strategy and return (exit_pct, exit_reason).

    Args:
        history: Token price history
        tp_pct: Take profit percentage (e.g., 25.0)
        sl_pct: Stop loss percentage (e.g., -20.0) - should be negative
        exit_on_bearish: Exit if verdict flips to BEARISH
        exit_on_score_drop: Exit if score drops by this amount from entry
        max_hold_periods: Maximum periods to hold
        exit_on_ratio_drop: Exit if buy/sell ratio drops below this

    Returns:
        (exit_pct, exit_reason)
    """
    entry_price = history.entry_price
    entry_score = history.entry_score
    entry_ratio = history.price_points[0].buy_sell_ratio

    for i, point in enumerate(history.price_points):
        change_pct = ((point.price - entry_price) / entry_price) * 100

        # Check take profit
        if change_pct >= tp_pct:
            return change_pct, "TP_HIT"

        # Check stop loss
        if change_pct <= sl_pct:
            return change_pct, "SL_HIT"

        # Check bearish flip (skip first point - it's entry)
        if exit_on_bearish and i > 0 and point.verdict == 'BEARISH':
            return change_pct, "BEARISH_FLIP"

        # Check score drop
        if exit_on_score_drop is not None and i > 0:
            score_change = entry_score - point.score
            if score_change >= exit_on_score_drop:
                return change_pct, "SCORE_DROP"

        # Check ratio drop
        if exit_on_ratio_drop is not None and i > 0:
            if entry_ratio and point.buy_sell_ratio:
                if point.buy_sell_ratio < exit_on_ratio_drop:
                    return change_pct, "RATIO_DROP"

        # Check max hold periods
        if max_hold_periods is not None and i >= max_hold_periods:
            return change_pct, "TIME_EXIT"

    # Still holding at end
    final_pct = history.final_pct
    return final_pct, "HELD_TO_END"


def test_strategy(
    histories: Dict[str, TokenHistory],
    tp_pct: float,
    sl_pct: float,
    exit_on_bearish: bool = False,
    exit_on_score_drop: Optional[float] = None,
    max_hold_periods: Optional[int] = None,
    exit_on_ratio_drop: Optional[float] = None,
) -> Dict:
    """Test a strategy across all tokens and return results."""
    results = []

    for symbol, history in histories.items():
        exit_pct, exit_reason = simulate_exit_strategy(
            history, tp_pct, sl_pct,
            exit_on_bearish=exit_on_bearish,
            exit_on_score_drop=exit_on_score_drop,
            max_hold_periods=max_hold_periods,
            exit_on_ratio_drop=exit_on_ratio_drop,
        )
        results.append({
            'symbol': symbol,
            'exit_pct': exit_pct,
            'exit_reason': exit_reason,
            'max_gain': history.max_gain_pct,
            'max_loss': history.max_loss_pct,
        })

    # Calculate aggregate metrics
    wins = [r for r in results if r['exit_pct'] > 0]
    losses = [r for r in results if r['exit_pct'] <= 0]

    total = len(results)
    win_rate = len(wins) / total if total > 0 else 0
    avg_win = sum(r['exit_pct'] for r in wins) / len(wins) if wins else 0
    avg_loss = sum(r['exit_pct'] for r in losses) / len(losses) if losses else 0
    total_return = sum(r['exit_pct'] for r in results)
    avg_return = total_return / total if total > 0 else 0

    # Count exit reasons
    reasons = {}
    for r in results:
        reason = r['exit_reason']
        reasons[reason] = reasons.get(reason, 0) + 1

    return {
        'total': total,
        'wins': len(wins),
        'losses': len(losses),
        'win_rate': win_rate,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'avg_return': avg_return,
        'total_return': total_return,
        'exit_reasons': reasons,
        'details': results,
    }


def main():
    print("Loading token histories...")
    histories = load_token_histories()
    print(f"Loaded {len(histories)} tokens with price history")

    # Show baseline stats
    print("\n" + "=" * 80)
    print("BASELINE: HODL to end")
    print("=" * 80)

    hodl_gains = [h.final_pct for h in histories.values()]
    hodl_wins = sum(1 for g in hodl_gains if g > 0)
    hodl_avg = sum(hodl_gains) / len(hodl_gains)
    print(f"Win rate: {hodl_wins}/{len(hodl_gains)} = {hodl_wins/len(hodl_gains)*100:.1f}%")
    print(f"Avg return: {hodl_avg:.1f}%")
    print(f"Total return: {sum(hodl_gains):.1f}%")

    # Test different SL levels
    print("\n" + "=" * 80)
    print("TESTING WIDER STOP LOSSES (Fixed TP 25%)")
    print("=" * 80)

    sl_levels = [-15, -20, -25, -30, -35, -40]
    print(f"\n{'SL Level':<10} {'Win Rate':<12} {'Avg Win':<12} {'Avg Loss':<12} {'Avg Return':<12} {'Total':<12}")
    print("-" * 70)

    for sl in sl_levels:
        result = test_strategy(histories, tp_pct=25, sl_pct=sl)
        print(f"{sl}%{'':<7} {result['win_rate']*100:.1f}%{'':<7} "
              f"{result['avg_win']:.1f}%{'':<7} {result['avg_loss']:.1f}%{'':<7} "
              f"{result['avg_return']:.1f}%{'':<7} {result['total_return']:.1f}%")

    # Test SL + Bearish Flip
    print("\n" + "=" * 80)
    print("TESTING: WIDER SL + EXIT ON BEARISH FLIP")
    print("=" * 80)

    print(f"\n{'Strategy':<30} {'Win Rate':<10} {'Avg Ret':<10} {'Total Ret':<10} {'Exit Reasons'}")
    print("-" * 90)

    for sl in [-20, -25, -30]:
        # SL only
        result1 = test_strategy(histories, tp_pct=25, sl_pct=sl)
        reasons1 = ', '.join(f"{k}:{v}" for k, v in sorted(result1['exit_reasons'].items()))
        print(f"TP25/SL{sl}{'':<17} {result1['win_rate']*100:.1f}%{'':<5} "
              f"{result1['avg_return']:.1f}%{'':<5} {result1['total_return']:.1f}%{'':<5} {reasons1}")

        # SL + Bearish exit
        result2 = test_strategy(histories, tp_pct=25, sl_pct=sl, exit_on_bearish=True)
        reasons2 = ', '.join(f"{k}:{v}" for k, v in sorted(result2['exit_reasons'].items()))
        print(f"TP25/SL{sl}+BEARISH{'':<10} {result2['win_rate']*100:.1f}%{'':<5} "
              f"{result2['avg_return']:.1f}%{'':<5} {result2['total_return']:.1f}%{'':<5} {reasons2}")

    # Test SL + Score Drop
    print("\n" + "=" * 80)
    print("TESTING: WIDER SL + EXIT ON SCORE DROP")
    print("=" * 80)

    print(f"\n{'Strategy':<35} {'Win Rate':<10} {'Avg Ret':<10} {'Total Ret':<10}")
    print("-" * 70)

    for sl in [-25, -30]:
        for score_drop in [0.1, 0.15, 0.2]:
            result = test_strategy(histories, tp_pct=25, sl_pct=sl, exit_on_score_drop=score_drop)
            print(f"TP25/SL{sl}+ScoreDrop{score_drop}{'':<10} "
                  f"{result['win_rate']*100:.1f}%{'':<5} "
                  f"{result['avg_return']:.1f}%{'':<5} {result['total_return']:.1f}%")

    # Test SL + Time Exit
    print("\n" + "=" * 80)
    print("TESTING: WIDER SL + TIME-BASED EXIT")
    print("=" * 80)

    print(f"\n{'Strategy':<35} {'Win Rate':<10} {'Avg Ret':<10} {'Total Ret':<10}")
    print("-" * 70)

    for sl in [-25, -30]:
        for periods in [3, 5, 10]:
            result = test_strategy(histories, tp_pct=25, sl_pct=sl, max_hold_periods=periods)
            print(f"TP25/SL{sl}+MaxHold{periods}{'':<13} "
                  f"{result['win_rate']*100:.1f}%{'':<5} "
                  f"{result['avg_return']:.1f}%{'':<5} {result['total_return']:.1f}%")

    # Test combinations
    print("\n" + "=" * 80)
    print("TESTING: BEST COMBINATIONS")
    print("=" * 80)

    combos = [
        {'tp_pct': 25, 'sl_pct': -25, 'exit_on_bearish': True},
        {'tp_pct': 25, 'sl_pct': -25, 'exit_on_bearish': True, 'max_hold_periods': 5},
        {'tp_pct': 25, 'sl_pct': -30, 'exit_on_bearish': True},
        {'tp_pct': 25, 'sl_pct': -30, 'exit_on_bearish': True, 'max_hold_periods': 5},
        {'tp_pct': 25, 'sl_pct': -25, 'exit_on_score_drop': 0.15},
        {'tp_pct': 25, 'sl_pct': -30, 'exit_on_score_drop': 0.15},
        {'tp_pct': 30, 'sl_pct': -25, 'exit_on_bearish': True},
        {'tp_pct': 20, 'sl_pct': -20, 'exit_on_bearish': True},
    ]

    print(f"\n{'Strategy':<50} {'Win%':<8} {'AvgRet':<8} {'Total':<10}")
    print("-" * 80)

    best_result = None
    best_total = float('-inf')
    best_name = ""

    for combo in combos:
        result = test_strategy(histories, **combo)

        # Build name
        name_parts = [f"TP{combo['tp_pct']}/SL{combo['sl_pct']}"]
        if combo.get('exit_on_bearish'):
            name_parts.append("+BEARISH")
        if combo.get('exit_on_score_drop'):
            name_parts.append(f"+ScoreDrop{combo['exit_on_score_drop']}")
        if combo.get('max_hold_periods'):
            name_parts.append(f"+MaxHold{combo['max_hold_periods']}")
        name = ''.join(name_parts)

        print(f"{name:<50} {result['win_rate']*100:.1f}%{'':<3} "
              f"{result['avg_return']:.1f}%{'':<3} {result['total_return']:.1f}%")

        if result['total_return'] > best_total:
            best_total = result['total_return']
            best_result = result
            best_name = name

    # Print best strategy details
    print("\n" + "=" * 80)
    print(f"BEST STRATEGY: {best_name}")
    print("=" * 80)
    print(f"Win Rate: {best_result['win_rate']*100:.1f}%")
    print(f"Avg Return: {best_result['avg_return']:.1f}%")
    print(f"Total Return: {best_result['total_return']:.1f}%")
    print(f"Avg Win: +{best_result['avg_win']:.1f}%")
    print(f"Avg Loss: {best_result['avg_loss']:.1f}%")
    print(f"\nExit Reasons:")
    for reason, count in sorted(best_result['exit_reasons'].items()):
        print(f"  {reason}: {count}")

    # Show trade-by-trade for best strategy
    print("\n" + "=" * 80)
    print("TRADE DETAILS (Best Strategy)")
    print("=" * 80)

    wins = sorted([d for d in best_result['details'] if d['exit_pct'] > 0],
                  key=lambda x: x['exit_pct'], reverse=True)
    losses = sorted([d for d in best_result['details'] if d['exit_pct'] <= 0],
                    key=lambda x: x['exit_pct'])

    print("\nTOP WINS:")
    for w in wins[:5]:
        print(f"  {w['symbol']}: +{w['exit_pct']:.1f}% ({w['exit_reason']}) "
              f"[max was +{w['max_gain']:.1f}%]")

    print("\nWORST LOSSES:")
    for l in losses[:5]:
        print(f"  {l['symbol']}: {l['exit_pct']:.1f}% ({l['exit_reason']}) "
              f"[max loss was {l['max_loss']:.1f}%]")

    # Comparison summary
    print("\n" + "=" * 80)
    print("COMPARISON SUMMARY")
    print("=" * 80)
    print(f"HODL to end:           {hodl_avg:.1f}% avg, {sum(hodl_gains):.1f}% total")
    tight_sl = test_strategy(histories, tp_pct=25, sl_pct=-15)
    print(f"TP25/SL-15 (tight):    {tight_sl['avg_return']:.1f}% avg, {tight_sl['total_return']:.1f}% total")
    print(f"Best combo:            {best_result['avg_return']:.1f}% avg, {best_result['total_return']:.1f}% total")


if __name__ == "__main__":
    main()
