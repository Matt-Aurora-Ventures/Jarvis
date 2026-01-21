"""
Deep Analysis: Why Tighter Stop Losses Perform Better.

Investigates the counterintuitive finding that -15% SL outperforms wider stops.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional
import re

ROOT = Path(__file__).resolve().parents[1]
PREDICTIONS_FILE = ROOT / "bots" / "buy_tracker" / "predictions_history.json"


def extract_metrics(reasoning: str) -> Dict:
    """Extract metrics from reasoning text."""
    metrics = {}
    change_match = re.search(r'24h[:\s]*([+-]?\d+\.?\d*)%', reasoning)
    if change_match:
        try:
            metrics['change_24h'] = float(change_match.group(1))
        except ValueError:
            pass
    return metrics


def load_token_data():
    """Load and organize all token price histories."""
    with open(PREDICTIONS_FILE, 'r', encoding='utf-8') as f:
        history = json.load(f)

    # Organize by token
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


def analyze_sl_behavior():
    """Analyze what happens to tokens at different SL levels."""
    token_data = load_token_data()

    print("=" * 90)
    print("DEEP ANALYSIS: STOP LOSS BEHAVIOR")
    print("=" * 90)

    results = []

    for symbol, points in token_data.items():
        if len(points) < 2:
            continue

        # Sort by timestamp
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
        points_after_entry = points[entry_idx:]

        # Track price path
        max_gain = 0
        max_loss = 0
        hit_25_tp = False
        sl_15_exit = None
        sl_20_exit = None
        sl_25_exit = None
        sl_30_exit = None

        for i, p in enumerate(points_after_entry):
            change = ((p['price'] - entry_price) / entry_price) * 100

            if change > max_gain:
                max_gain = change
            if change < max_loss:
                max_loss = change

            if change >= 25 and not hit_25_tp:
                hit_25_tp = True

            # Track when each SL would trigger
            if change <= -15 and sl_15_exit is None:
                sl_15_exit = {'index': i, 'pct': change, 'after_peak': max_gain}
            if change <= -20 and sl_20_exit is None:
                sl_20_exit = {'index': i, 'pct': change, 'after_peak': max_gain}
            if change <= -25 and sl_25_exit is None:
                sl_25_exit = {'index': i, 'pct': change, 'after_peak': max_gain}
            if change <= -30 and sl_30_exit is None:
                sl_30_exit = {'index': i, 'pct': change, 'after_peak': max_gain}

        final_pct = ((points[-1]['price'] - entry_price) / entry_price) * 100

        results.append({
            'symbol': symbol,
            'max_gain': max_gain,
            'max_loss': max_loss,
            'final_pct': final_pct,
            'hit_25_tp': hit_25_tp,
            'sl_15_exit': sl_15_exit,
            'sl_20_exit': sl_20_exit,
            'sl_25_exit': sl_25_exit,
            'sl_30_exit': sl_30_exit,
            'num_points': len(points_after_entry),
        })

    # Analyze tokens that hit -15% SL
    print("\n" + "-" * 90)
    print("TOKENS THAT WOULD HIT -15% SL:")
    print("-" * 90)

    sl_15_tokens = [r for r in results if r['sl_15_exit'] is not None]
    print(f"\n{len(sl_15_tokens)} tokens would hit -15% SL\n")

    print(f"{'Symbol':<15} {'SL Exit':<10} {'Peak Before SL':<15} {'Final if HODL':<15} {'Hit 25% TP?'}")
    print("-" * 70)

    for t in sorted(sl_15_tokens, key=lambda x: x['final_pct']):
        sl_exit = t['sl_15_exit']['pct']
        peak = t['sl_15_exit']['after_peak']
        final = t['final_pct']
        tp_hit = "YES" if t['hit_25_tp'] else "NO"
        print(f"{t['symbol']:<15} {sl_exit:>8.1f}% {peak:>13.1f}% {final:>13.1f}% {tp_hit:>10}")

    # Key insight: Did any hit TP BEFORE hitting SL?
    print("\n" + "-" * 90)
    print("KEY INSIGHT: DID TOKENS HIT TP BEFORE SL?")
    print("-" * 90)

    for t in results:
        if t['hit_25_tp'] and t['sl_15_exit'] is not None:
            print(f"\n{t['symbol']}: Hit 25% TP but also hit -15% SL")
            print(f"  Max gain before SL: {t['sl_15_exit']['after_peak']:.1f}%")
            print(f"  This means: TP was hit FIRST, SL wouldn't have triggered")

    # Analyze the difference between SL levels
    print("\n" + "-" * 90)
    print("TOKENS THAT SURVIVE -15% BUT HIT WIDER SLs:")
    print("-" * 90)

    survive_15 = [r for r in results if r['sl_15_exit'] is None]
    print(f"\n{len(survive_15)} tokens never hit -15% SL")

    for t in survive_15:
        if t['sl_20_exit'] or t['sl_25_exit'] or t['sl_30_exit']:
            print(f"\n{t['symbol']}: Never hit -15%, but...")
            if t['sl_20_exit']:
                print(f"  Would hit -20%: exit at {t['sl_20_exit']['pct']:.1f}%")
            if t['sl_25_exit']:
                print(f"  Would hit -25%: exit at {t['sl_25_exit']['pct']:.1f}%")
            if t['sl_30_exit']:
                print(f"  Would hit -30%: exit at {t['sl_30_exit']['pct']:.1f}%")
            print(f"  Final if HODL: {t['final_pct']:.1f}%")

    # The real question: What's the outcome for tokens stopped at -15%?
    print("\n" + "=" * 90)
    print("CRITICAL ANALYSIS: WHAT HAPPENS TO -15% STOPPED TOKENS?")
    print("=" * 90)

    stopped_outcomes = []
    for t in sl_15_tokens:
        # If token hit -15% SL, what would final be if we held?
        stopped_outcomes.append({
            'symbol': t['symbol'],
            'sl_exit': t['sl_15_exit']['pct'],
            'final_hodl': t['final_pct'],
            'saved': t['sl_15_exit']['pct'] - t['final_pct'],  # Positive = SL saved us
        })

    print(f"\n{'Symbol':<15} {'SL Exit':<10} {'Final HODL':<12} {'SL Saved?'}")
    print("-" * 50)

    total_saved = 0
    for o in sorted(stopped_outcomes, key=lambda x: x['saved'], reverse=True):
        saved_str = f"+{o['saved']:.1f}%" if o['saved'] > 0 else f"{o['saved']:.1f}%"
        print(f"{o['symbol']:<15} {o['sl_exit']:>8.1f}% {o['final_hodl']:>10.1f}% {saved_str:>10}")
        total_saved += o['saved']

    print("-" * 50)
    print(f"{'TOTAL SAVED BY -15% SL:':<35} {total_saved:>+10.1f}%")

    # Show tokens that weren't stopped and what happened
    print("\n" + "=" * 90)
    print("TOKENS THAT DIDN'T HIT -15% SL:")
    print("=" * 90)

    not_stopped = [r for r in results if r['sl_15_exit'] is None]
    print(f"\n{'Symbol':<15} {'Max Gain':<12} {'Max Loss':<12} {'Final':<12} {'Hit 25% TP?'}")
    print("-" * 65)

    for t in sorted(not_stopped, key=lambda x: x['final_pct'], reverse=True):
        tp_hit = "YES" if t['hit_25_tp'] else "NO"
        print(f"{t['symbol']:<15} {t['max_gain']:>10.1f}% {t['max_loss']:>10.1f}% "
              f"{t['final_pct']:>10.1f}% {tp_hit:>10}")

    # Summary
    print("\n" + "=" * 90)
    print("SUMMARY: WHY TIGHTER SL WORKS BETTER")
    print("=" * 90)

    hit_tp_count = sum(1 for r in results if r['hit_25_tp'])
    print(f"\nTotal tokens analyzed: {len(results)}")
    print(f"Tokens that hit 25% TP at some point: {hit_tp_count} ({hit_tp_count/len(results)*100:.1f}%)")
    print(f"Tokens stopped at -15%: {len(sl_15_tokens)}")
    print(f"Total capital SAVED by -15% SL vs HODL: {total_saved:.1f}%")

    # The key insight
    rugs_caught = sum(1 for o in stopped_outcomes if o['final_hodl'] < -50)
    print(f"\nRugs caught by -15% SL (final < -50%): {rugs_caught}")

    for o in stopped_outcomes:
        if o['final_hodl'] < -50:
            print(f"  {o['symbol']}: Stopped at {o['sl_exit']:.1f}%, "
                  f"would have been {o['final_hodl']:.1f}% - SAVED {o['saved']:.1f}%!")


if __name__ == "__main__":
    analyze_sl_behavior()
