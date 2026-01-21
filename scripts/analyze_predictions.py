#!/usr/bin/env python3
"""
Deep analysis of all sentiment predictions to find what actually predicts success.
"""

import json
import re
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime

PREDICTIONS_FILE = Path(__file__).parent.parent / "bots" / "buy_tracker" / "predictions_history.json"

@dataclass
class TokenCall:
    """A single token prediction."""
    symbol: str
    contract: str
    timestamp: str
    verdict: str  # BULLISH, BEARISH, NEUTRAL
    score: float
    price_at_prediction: float
    reasoning: str
    targets: str

    # Extracted metrics from reasoning
    change_24h: Optional[float] = None
    buy_sell_ratio: Optional[float] = None
    volume_mention: Optional[str] = None
    mcap_mention: Optional[str] = None
    liquidity_mention: Optional[str] = None


def extract_metrics_from_reasoning(reasoning: str) -> Dict:
    """Parse metrics mentioned in Grok's reasoning."""
    metrics = {}

    # Extract percentage changes (e.g., "+382%", "-86%")
    pct_match = re.search(r'([+-]?\d+(?:\.\d+)?)\s*%', reasoning)
    if pct_match:
        metrics['change_pct'] = float(pct_match.group(1))

    # Extract buy/sell ratio (e.g., "1.53x", "2.26x buy ratio")
    ratio_match = re.search(r'(\d+(?:\.\d+)?)\s*x\s*(?:buy)', reasoning, re.IGNORECASE)
    if ratio_match:
        metrics['buy_sell_ratio'] = float(ratio_match.group(1))

    # Check for liquidity mentions
    if 'low liquidity' in reasoning.lower() or 'no liquidity' in reasoning.lower():
        metrics['liquidity_warning'] = True
    elif 'high liquidity' in reasoning.lower() or 'solid liquidity' in reasoning.lower():
        metrics['liquidity_good'] = True

    # Check for mcap mentions
    if 'tiny mcap' in reasoning.lower() or 'low mcap' in reasoning.lower():
        metrics['mcap_warning'] = True

    # Check for rug/scam mentions
    if 'rug' in reasoning.lower() or 'scam' in reasoning.lower() or 'avoid' in reasoning.lower():
        metrics['rug_warning'] = True

    # Check for pump.fun mentions
    if 'pump' in reasoning.lower() and ('fun' in reasoning.lower() or 'launch' in reasoning.lower()):
        metrics['pump_fun_token'] = True

    return metrics


def load_and_parse_predictions() -> List[TokenCall]:
    """Load all predictions and parse them."""
    with open(PREDICTIONS_FILE, 'r', encoding='utf-8') as f:
        history = json.load(f)

    all_calls = []

    for entry in history:
        timestamp = entry.get('timestamp', '')
        token_predictions = entry.get('token_predictions', {})

        for symbol, data in token_predictions.items():
            call = TokenCall(
                symbol=symbol,
                contract=data.get('contract', ''),
                timestamp=timestamp,
                verdict=data.get('verdict', 'NEUTRAL'),
                score=data.get('score', 0),
                price_at_prediction=data.get('price_at_prediction', 0),
                reasoning=data.get('reasoning', ''),
                targets=data.get('targets', '')
            )

            # Extract metrics from reasoning
            metrics = extract_metrics_from_reasoning(call.reasoning)
            if 'change_pct' in metrics:
                call.change_24h = metrics['change_pct']
            if 'buy_sell_ratio' in metrics:
                call.buy_sell_ratio = metrics['buy_sell_ratio']

            all_calls.append(call)

    return all_calls


def analyze_calls(calls: List[TokenCall]) -> Dict:
    """Analyze all calls to find patterns."""

    # Group by verdict
    by_verdict = defaultdict(list)
    for call in calls:
        by_verdict[call.verdict].append(call)

    # Track unique tokens
    unique_tokens = set()
    for call in calls:
        unique_tokens.add(call.symbol)

    # Analyze bullish calls
    bullish_calls = by_verdict.get('BULLISH', [])
    bearish_calls = by_verdict.get('BEARISH', [])
    neutral_calls = by_verdict.get('NEUTRAL', [])

    # Score distribution for bullish calls
    bullish_scores = [c.score for c in bullish_calls]
    bearish_scores = [c.score for c in bearish_calls]

    # Buy/sell ratio analysis for bullish calls
    bullish_with_ratio = [c for c in bullish_calls if c.buy_sell_ratio]

    # Tokens with rug warnings that still got bullish
    rug_warnings_bullish = []
    for call in bullish_calls:
        metrics = extract_metrics_from_reasoning(call.reasoning)
        if metrics.get('rug_warning') or metrics.get('liquidity_warning'):
            rug_warnings_bullish.append(call)

    # Price change analysis
    extreme_pumps_bullish = [c for c in bullish_calls if c.change_24h and c.change_24h > 100]

    return {
        'total_predictions': len(calls),
        'unique_tokens': len(unique_tokens),
        'by_verdict': {
            'BULLISH': len(bullish_calls),
            'BEARISH': len(bearish_calls),
            'NEUTRAL': len(neutral_calls),
        },
        'bullish_score_avg': sum(bullish_scores) / len(bullish_scores) if bullish_scores else 0,
        'bullish_score_range': (min(bullish_scores) if bullish_scores else 0, max(bullish_scores) if bullish_scores else 0),
        'bearish_score_avg': sum(bearish_scores) / len(bearish_scores) if bearish_scores else 0,
        'bullish_with_buy_ratio': len(bullish_with_ratio),
        'avg_buy_ratio_bullish': sum(c.buy_sell_ratio for c in bullish_with_ratio) / len(bullish_with_ratio) if bullish_with_ratio else 0,
        'rug_warnings_still_bullish': len(rug_warnings_bullish),
        'extreme_pumps_called_bullish': len(extreme_pumps_bullish),
    }


def find_repeated_tokens(calls: List[TokenCall]) -> Dict[str, List[TokenCall]]:
    """Find tokens that appear multiple times to track consistency."""
    by_token = defaultdict(list)
    for call in calls:
        by_token[call.symbol].append(call)

    # Only return tokens with 2+ appearances
    return {k: v for k, v in by_token.items() if len(v) >= 2}


def track_verdict_changes(calls: List[TokenCall]) -> List[Dict]:
    """Find tokens where verdict changed between predictions."""
    repeated = find_repeated_tokens(calls)
    changes = []

    for symbol, token_calls in repeated.items():
        # Sort by timestamp
        sorted_calls = sorted(token_calls, key=lambda x: x.timestamp)

        for i in range(1, len(sorted_calls)):
            prev = sorted_calls[i-1]
            curr = sorted_calls[i]

            if prev.verdict != curr.verdict:
                changes.append({
                    'symbol': symbol,
                    'from_verdict': prev.verdict,
                    'from_score': prev.score,
                    'to_verdict': curr.verdict,
                    'to_score': curr.score,
                    'time_diff': curr.timestamp[:16] + ' vs ' + prev.timestamp[:16],
                    'price_at_first': prev.price_at_prediction,
                    'price_at_second': curr.price_at_prediction,
                })

    return changes


def print_analysis():
    """Run full analysis and print results."""
    print("Loading predictions...")
    calls = load_and_parse_predictions()
    print(f"Loaded {len(calls)} total predictions\n")

    # Basic analysis
    analysis = analyze_calls(calls)

    print("=" * 60)
    print("OVERALL STATISTICS")
    print("=" * 60)
    print(f"Total predictions made: {analysis['total_predictions']}")
    print(f"Unique tokens covered: {analysis['unique_tokens']}")
    print()
    print("Verdict breakdown:")
    for verdict, count in analysis['by_verdict'].items():
        pct = count / analysis['total_predictions'] * 100
        print(f"  {verdict}: {count} ({pct:.1f}%)")

    print()
    print("=" * 60)
    print("BULLISH CALL ANALYSIS")
    print("=" * 60)
    print(f"Average score for bullish calls: {analysis['bullish_score_avg']:.2f}")
    print(f"Score range: {analysis['bullish_score_range'][0]:.2f} to {analysis['bullish_score_range'][1]:.2f}")
    print(f"Bullish calls with buy/sell ratio data: {analysis['bullish_with_buy_ratio']}")
    print(f"Average buy/sell ratio on bullish: {analysis['avg_buy_ratio_bullish']:.2f}x")
    print(f"Calls with rug/liquidity warnings but still bullish: {analysis['rug_warnings_still_bullish']}")
    print(f"Extreme pumps (>100%) called bullish: {analysis['extreme_pumps_called_bullish']}")

    print()
    print("=" * 60)
    print("VERDICT CONSISTENCY (tokens that flipped)")
    print("=" * 60)
    changes = track_verdict_changes(calls)
    print(f"Total verdict changes tracked: {len(changes)}")
    print()

    # Show some examples
    for change in changes[:15]:
        price_change = ""
        if change['price_at_first'] and change['price_at_second']:
            pct = (change['price_at_second'] - change['price_at_first']) / change['price_at_first'] * 100
            price_change = f" (price: {pct:+.1f}%)"
        print(f"  {change['symbol']}: {change['from_verdict']}({change['from_score']:.1f}) -> {change['to_verdict']}({change['to_score']:.1f}){price_change}")

    # Find tokens that went from BULLISH to BEARISH (potential missed exits)
    print()
    print("=" * 60)
    print("BULLISH -> BEARISH FLIPS (potential missed exits)")
    print("=" * 60)
    bullish_to_bearish = [c for c in changes if c['from_verdict'] == 'BULLISH' and c['to_verdict'] == 'BEARISH']
    for change in bullish_to_bearish[:10]:
        price_change = ""
        if change['price_at_first'] and change['price_at_second']:
            pct = (change['price_at_second'] - change['price_at_first']) / change['price_at_first'] * 100
            price_change = f" (price moved: {pct:+.1f}%)"
        print(f"  {change['symbol']}: score {change['from_score']:.1f} -> {change['to_score']:.1f}{price_change}")

    # Find tokens with highest bullish scores
    print()
    print("=" * 60)
    print("HIGHEST CONVICTION BULLISH CALLS (score > 0.7)")
    print("=" * 60)
    high_conviction = [c for c in calls if c.verdict == 'BULLISH' and c.score >= 0.7]
    high_conviction.sort(key=lambda x: x.score, reverse=True)

    seen = set()
    for call in high_conviction[:20]:
        if call.symbol in seen:
            continue
        seen.add(call.symbol)
        print(f"  {call.symbol}: score={call.score:.2f}, price=${call.price_at_prediction:.8f}")
        print(f"    Reason: {call.reasoning[:80]}...")
        print()


def analyze_chasing_pumps():
    """Deep analysis of calling bullish on already-pumped tokens."""
    print("\n" + "=" * 60)
    print("CHASING PUMPS ANALYSIS (calling bullish on already-pumped tokens)")
    print("=" * 60)

    calls = load_and_parse_predictions()
    bullish = [c for c in calls if c.verdict == 'BULLISH']

    # Categorize by existing pump at time of call
    no_pump = []       # < 20% change
    moderate_pump = [] # 20-100% change
    large_pump = []    # 100-500% change
    extreme_pump = []  # > 500% change

    for call in bullish:
        if call.change_24h is None:
            continue
        if call.change_24h < 20:
            no_pump.append(call)
        elif call.change_24h < 100:
            moderate_pump.append(call)
        elif call.change_24h < 500:
            large_pump.append(call)
        else:
            extreme_pump.append(call)

    print(f"\nBullish calls by existing pump at time of call:")
    print(f"  No/low pump (<20%): {len(no_pump)}")
    print(f"  Moderate pump (20-100%): {len(moderate_pump)}")
    print(f"  Large pump (100-500%): {len(large_pump)}")
    print(f"  Extreme pump (>500%): {len(extreme_pump)}")

    print(f"\nExtreme pump bullish calls (>500% already up - DANGER ZONE):")
    for call in extreme_pump[:10]:
        print(f"  {call.symbol}: score={call.score:.2f}, already pumped {call.change_24h:.0f}%")
        print(f"    {call.reasoning[:70]}...")

    # Analyze which later flipped bearish
    changes = track_verdict_changes(calls)
    bullish_to_bearish = [c for c in changes if c['from_verdict'] == 'BULLISH' and c['to_verdict'] == 'BEARISH']

    print(f"\n" + "=" * 60)
    print("TOKENS THAT WENT BULLISH -> BEARISH (our losses)")
    print("=" * 60)

    # Track the original calls
    for change in bullish_to_bearish:
        symbol = change['symbol']
        # Find original bullish call
        original = next((c for c in bullish if c.symbol == symbol and abs(c.score - change['from_score']) < 0.01), None)
        if original:
            price_change = ""
            if change['price_at_first'] and change['price_at_second']:
                pct = (change['price_at_second'] - change['price_at_first']) / change['price_at_first'] * 100
                price_change = f"{pct:+.1f}%"

            print(f"\n{symbol}:")
            print(f"  Bullish score: {change['from_score']:.2f} -> Bearish score: {change['to_score']:.2f}")
            print(f"  Price outcome: {price_change}")
            print(f"  Already pumped at call: {original.change_24h:.0f}%" if original.change_24h else "  Already pumped: unknown")
            print(f"  Reasoning: {original.reasoning[:80]}...")


def analyze_buy_sell_correlation():
    """Analyze correlation between buy/sell ratio and outcomes."""
    print("\n" + "=" * 60)
    print("BUY/SELL RATIO ANALYSIS")
    print("=" * 60)

    calls = load_and_parse_predictions()
    bullish = [c for c in calls if c.verdict == 'BULLISH' and c.buy_sell_ratio]

    # Group by buy/sell ratio
    low_ratio = [c for c in bullish if c.buy_sell_ratio < 1.5]
    medium_ratio = [c for c in bullish if 1.5 <= c.buy_sell_ratio < 2.5]
    high_ratio = [c for c in bullish if c.buy_sell_ratio >= 2.5]

    print(f"\nBullish calls by buy/sell ratio:")
    print(f"  Low (<1.5x): {len(low_ratio)}")
    print(f"  Medium (1.5-2.5x): {len(medium_ratio)}")
    print(f"  High (>2.5x): {len(high_ratio)}")

    # Check which ones later flipped
    changes = track_verdict_changes(calls)
    bullish_to_bearish = {c['symbol'] for c in changes if c['from_verdict'] == 'BULLISH' and c['to_verdict'] == 'BEARISH'}

    low_flipped = sum(1 for c in low_ratio if c.symbol in bullish_to_bearish)
    medium_flipped = sum(1 for c in medium_ratio if c.symbol in bullish_to_bearish)
    high_flipped = sum(1 for c in high_ratio if c.symbol in bullish_to_bearish)

    print(f"\nFlip rate (bullish -> bearish) by ratio:")
    if low_ratio:
        print(f"  Low ratio: {low_flipped}/{len(low_ratio)} ({low_flipped/len(low_ratio)*100:.0f}%)")
    if medium_ratio:
        print(f"  Medium ratio: {medium_flipped}/{len(medium_ratio)} ({medium_flipped/len(medium_ratio)*100:.0f}%)")
    if high_ratio:
        print(f"  High ratio: {high_flipped}/{len(high_ratio)} ({high_flipped/len(high_ratio)*100:.0f}%)")


def find_successful_patterns():
    """Find patterns in calls that stayed bullish or improved."""
    print("\n" + "=" * 60)
    print("SUCCESSFUL PATTERN ANALYSIS")
    print("=" * 60)

    calls = load_and_parse_predictions()
    changes = track_verdict_changes(calls)

    # Find tokens that stayed bullish or went neutral->bullish
    improving = [c for c in changes if c['to_verdict'] == 'BULLISH' and c['from_verdict'] != 'BULLISH']
    price_up = [c for c in changes if c['price_at_first'] and c['price_at_second'] and
                (c['price_at_second'] - c['price_at_first']) / c['price_at_first'] > 0.2]

    print(f"\nTokens that improved to BULLISH: {len(improving)}")
    for change in improving[:5]:
        pct = (change['price_at_second'] - change['price_at_first']) / change['price_at_first'] * 100 if change['price_at_first'] else 0
        print(f"  {change['symbol']}: {change['from_verdict']} -> {change['to_verdict']} (price: {pct:+.1f}%)")

    print(f"\nTokens with >20% price increase between calls: {len(price_up)}")
    for change in price_up[:10]:
        pct = (change['price_at_second'] - change['price_at_first']) / change['price_at_first'] * 100
        print(f"  {change['symbol']}: {change['from_verdict']} -> {change['to_verdict']} (price: {pct:+.1f}%)")


def analyze_score_vs_outcome():
    """Analyze if score correlates with outcome."""
    print("\n" + "=" * 60)
    print("SCORE VS OUTCOME CORRELATION")
    print("=" * 60)

    calls = load_and_parse_predictions()
    changes = track_verdict_changes(calls)

    # Track price changes by original score
    high_score_outcomes = []
    low_score_outcomes = []

    for change in changes:
        if change['price_at_first'] and change['price_at_second']:
            pct = (change['price_at_second'] - change['price_at_first']) / change['price_at_first'] * 100

            if change['from_verdict'] == 'BULLISH':
                if change['from_score'] >= 0.6:
                    high_score_outcomes.append(pct)
                else:
                    low_score_outcomes.append(pct)

    if high_score_outcomes:
        print(f"\nHigh conviction bullish (score >= 0.6):")
        print(f"  Count: {len(high_score_outcomes)}")
        print(f"  Avg price change: {sum(high_score_outcomes)/len(high_score_outcomes):.1f}%")
        print(f"  Winners (>0%): {sum(1 for x in high_score_outcomes if x > 0)}")
        print(f"  Losers (<0%): {sum(1 for x in high_score_outcomes if x < 0)}")
        print(f"  Big losses (>-50%): {sum(1 for x in high_score_outcomes if x < -50)}")

    if low_score_outcomes:
        print(f"\nLow conviction bullish (score < 0.6):")
        print(f"  Count: {len(low_score_outcomes)}")
        print(f"  Avg price change: {sum(low_score_outcomes)/len(low_score_outcomes):.1f}%")
        print(f"  Winners (>0%): {sum(1 for x in low_score_outcomes if x > 0)}")
        print(f"  Losers (<0%): {sum(1 for x in low_score_outcomes if x < 0)}")


if __name__ == "__main__":
    print_analysis()
    analyze_chasing_pumps()
    analyze_buy_sell_correlation()
    find_successful_patterns()
    analyze_score_vs_outcome()
