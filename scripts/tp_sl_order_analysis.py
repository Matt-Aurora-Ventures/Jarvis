"""
TP vs SL Order Analysis.

For each token, determine what happens FIRST:
- TP hit (exit with profit)
- SL hit (exit with loss)
- Neither (still holding)

This clarifies whether the SL is "too tight" or appropriately catching rugs.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import re

ROOT = Path(__file__).resolve().parents[1]
PREDICTIONS_FILE = ROOT / "bots" / "buy_tracker" / "predictions_history.json"


def extract_metrics(reasoning: str) -> Dict:
    metrics = {}
    change_match = re.search(r'24h[:\s]*([+-]?\d+\.?\d*)%', reasoning)
    if change_match:
        try:
            metrics['change_24h'] = float(change_match.group(1))
        except ValueError:
            pass
    return metrics


def load_token_data():
    with open(PREDICTIONS_FILE, 'r', encoding='utf-8') as f:
        history = json.load(f)

    token_data = {}
    for entry in history:
        timestamp = entry.get('timestamp', '')
        for symbol, data in entry.get('token_predictions', {}).items():
            if symbol not in token_data:
                token_data[symbol] = []
            price = data.get('price_at_prediction', 0)
            if price <= 0:
                continue
            metrics = extract_metrics(data.get('reasoning', ''))
            token_data[symbol].append({
                'timestamp': timestamp,
                'price': price,
                'verdict': data.get('verdict', 'NEUTRAL'),
                'score': data.get('score', 0),
                'change_24h': metrics.get('change_24h'),
            })
    return token_data


def analyze_tp_sl_order(tp_pct: float, sl_pct: float):
    """Analyze which comes first - TP or SL - for each token."""
    token_data = load_token_data()

    results = []

    for symbol, points in token_data.items():
        if len(points) < 2:
            continue

        points.sort(key=lambda p: p['timestamp'])

        # Find first BULLISH call as entry
        entry_idx = None
        for i, p in enumerate(points):
            if p['verdict'] == 'BULLISH':
                entry_idx = i
                break

        if entry_idx is None:
            continue

        entry_price = points[entry_idx]['price']
        points_after = points[entry_idx:]

        # Track the path
        tp_hit_idx = None
        sl_hit_idx = None
        max_gain = 0
        max_loss = 0

        for i, p in enumerate(points_after):
            change = ((p['price'] - entry_price) / entry_price) * 100

            if change > max_gain:
                max_gain = change
            if change < max_loss:
                max_loss = change

            # Check TP first (because if both happen in same period, TP wins)
            if change >= tp_pct and tp_hit_idx is None:
                tp_hit_idx = i
            # Check SL
            if change <= sl_pct and sl_hit_idx is None:
                sl_hit_idx = i

        final_pct = ((points[-1]['price'] - entry_price) / entry_price) * 100

        # Determine outcome
        if tp_hit_idx is not None and (sl_hit_idx is None or tp_hit_idx <= sl_hit_idx):
            outcome = "TP_WIN"
            exit_pct = tp_pct  # Exit at TP
        elif sl_hit_idx is not None:
            outcome = "SL_LOSS"
            # Calculate actual SL exit (could be worse than SL level due to gaps)
            exit_pct = ((points_after[sl_hit_idx]['price'] - entry_price) / entry_price) * 100
        else:
            outcome = "HOLDING"
            exit_pct = final_pct

        results.append({
            'symbol': symbol,
            'outcome': outcome,
            'exit_pct': exit_pct,
            'max_gain': max_gain,
            'max_loss': max_loss,
            'final_pct': final_pct,
            'tp_idx': tp_hit_idx,
            'sl_idx': sl_hit_idx,
        })

    return results


def print_analysis(tp_pct: float, sl_pct: float):
    results = analyze_tp_sl_order(tp_pct, sl_pct)

    print(f"\n{'='*90}")
    print(f"TP {tp_pct}% / SL {sl_pct}% - ORDER ANALYSIS")
    print(f"{'='*90}")

    # Group by outcome
    tp_wins = [r for r in results if r['outcome'] == 'TP_WIN']
    sl_losses = [r for r in results if r['outcome'] == 'SL_LOSS']
    holding = [r for r in results if r['outcome'] == 'HOLDING']

    print(f"\nTotal tokens: {len(results)}")
    print(f"  TP Wins (exit at +{tp_pct}%): {len(tp_wins)}")
    print(f"  SL Losses: {len(sl_losses)}")
    print(f"  Still Holding: {len(holding)}")

    # Calculate returns
    total_return = sum(r['exit_pct'] for r in results)
    avg_return = total_return / len(results)

    print(f"\nTotal Return: {total_return:.1f}%")
    print(f"Avg Return: {avg_return:.1f}%")

    # Show TP Wins
    print(f"\n{'-'*90}")
    print("TP WINS (Exited at profit):")
    print(f"{'-'*90}")
    print(f"{'Symbol':<15} {'Exit':<10} {'Max Gain':<12} {'Final (if HODL)':<15}")
    print("-" * 55)
    for r in sorted(tp_wins, key=lambda x: x['max_gain'], reverse=True):
        print(f"{r['symbol']:<15} +{tp_pct:.0f}%{'':<5} {r['max_gain']:>10.1f}% {r['final_pct']:>13.1f}%")

    # Analyze SL losses - were they "premature" or "saved from rug"?
    print(f"\n{'-'*90}")
    print("SL LOSSES - Analysis:")
    print(f"{'-'*90}")

    premature_stops = []  # SL triggered but token recovered
    good_stops = []  # SL saved us from worse

    for r in sl_losses:
        if r['final_pct'] > r['exit_pct']:
            # Token ended up higher than our SL exit - premature!
            premature_stops.append(r)
        else:
            # Token went even lower - good SL
            good_stops.append(r)

    print(f"\n  Good stops (saved from worse): {len(good_stops)}")
    print(f"  Premature stops (token recovered): {len(premature_stops)}")

    if good_stops:
        print(f"\n  GOOD STOPS - SL Protected Us:")
        print(f"  {'Symbol':<15} {'SL Exit':<10} {'Final HODL':<12} {'Saved'}")
        print("  " + "-" * 50)
        for r in sorted(good_stops, key=lambda x: x['final_pct']):
            saved = r['exit_pct'] - r['final_pct']
            print(f"  {r['symbol']:<15} {r['exit_pct']:>8.1f}% {r['final_pct']:>10.1f}% {saved:>+8.1f}%")

    if premature_stops:
        print(f"\n  PREMATURE STOPS - Missed Recovery:")
        print(f"  {'Symbol':<15} {'SL Exit':<10} {'Final HODL':<12} {'Missed'}")
        print("  " + "-" * 50)
        for r in sorted(premature_stops, key=lambda x: x['final_pct'] - x['exit_pct'], reverse=True):
            missed = r['final_pct'] - r['exit_pct']
            print(f"  {r['symbol']:<15} {r['exit_pct']:>8.1f}% {r['final_pct']:>10.1f}% {missed:>+8.1f}%")

    # Show holding
    if holding:
        print(f"\n{'-'*90}")
        print("STILL HOLDING (Neither TP nor SL hit):")
        print(f"{'-'*90}")
        print(f"{'Symbol':<15} {'Current':<10} {'Max Gain':<12} {'Max Loss':<12}")
        print("-" * 50)
        for r in sorted(holding, key=lambda x: x['final_pct'], reverse=True):
            print(f"{r['symbol']:<15} {r['final_pct']:>8.1f}% {r['max_gain']:>10.1f}% {r['max_loss']:>10.1f}%")

    return results


def compare_sl_levels():
    print("\n" + "=" * 90)
    print("COMPARING DIFFERENT SL LEVELS (Fixed TP 25%)")
    print("=" * 90)

    sl_levels = [-15, -20, -25, -30]

    print(f"\n{'SL Level':<10} {'TP Wins':<10} {'SL Losses':<12} {'Holding':<10} {'Good SL':<10} {'Premature':<10} {'Avg Ret':<10}")
    print("-" * 75)

    for sl in sl_levels:
        results = analyze_tp_sl_order(25, sl)

        tp_wins = len([r for r in results if r['outcome'] == 'TP_WIN'])
        sl_losses = [r for r in results if r['outcome'] == 'SL_LOSS']
        holding = len([r for r in results if r['outcome'] == 'HOLDING'])

        good_sl = len([r for r in sl_losses if r['final_pct'] <= r['exit_pct']])
        premature = len([r for r in sl_losses if r['final_pct'] > r['exit_pct']])

        avg_ret = sum(r['exit_pct'] for r in results) / len(results)

        print(f"{sl}%{'':<7} {tp_wins:<10} {len(sl_losses):<12} {holding:<10} {good_sl:<10} {premature:<10} {avg_ret:>+.1f}%")

    # Now show what happens with combo strategies
    print("\n" + "=" * 90)
    print("THE REAL INSIGHT: PREMATURE STOPS ARE RARE")
    print("=" * 90)

    # Check -15% specifically
    results = analyze_tp_sl_order(25, -15)
    sl_losses = [r for r in results if r['outcome'] == 'SL_LOSS']
    premature = [r for r in sl_losses if r['final_pct'] > r['exit_pct']]

    if premature:
        print(f"\nWith TP 25%/SL -15%, only {len(premature)} premature stop(s):")
        for r in premature:
            print(f"  {r['symbol']}: Stopped at {r['exit_pct']:.1f}%, "
                  f"ended at {r['final_pct']:.1f}% (missed {r['final_pct'] - r['exit_pct']:.1f}%)")
    else:
        print("\nWith TP 25%/SL -15%, ZERO premature stops!")
        print("Every SL was protecting us from worse losses.")


if __name__ == "__main__":
    # Analyze the recommended -15% SL
    print_analysis(25, -15)

    # Compare different levels
    compare_sl_levels()

    # Also show -20% for comparison
    print("\n")
    print_analysis(25, -20)
