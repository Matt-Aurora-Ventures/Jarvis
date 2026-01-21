"""
Full Call Analysis - Track ALL predictions with outcomes.

This script analyzes every prediction we made and estimates outcomes
by tracking price evolution across multiple reports on the same token.
"""

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import re

ROOT = Path(__file__).resolve().parents[1]
PREDICTIONS_FILE = ROOT / "bots" / "buy_tracker" / "predictions_history.json"


@dataclass
class Call:
    """A single prediction call."""
    timestamp: str
    symbol: str
    contract: str
    verdict: str
    score: float
    price: float
    reasoning: str
    market_regime: str
    # Extracted metrics
    change_24h: Optional[float] = None
    buy_sell_ratio: Optional[float] = None


@dataclass
class TokenHistory:
    """Track a token's prediction history."""
    symbol: str
    contract: str
    calls: List[Call]
    first_price: float
    last_price: float
    price_change_pct: float
    first_verdict: str
    last_verdict: str
    verdict_flipped: bool
    max_price: float
    min_price: float
    max_gain_pct: float
    max_loss_pct: float


def extract_metrics(reasoning: str) -> Dict[str, Any]:
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


def load_and_process_predictions() -> Dict[str, TokenHistory]:
    """Load predictions and build token histories."""

    with open(PREDICTIONS_FILE, 'r', encoding='utf-8') as f:
        history = json.load(f)

    # Group calls by token
    token_calls: Dict[str, List[Call]] = defaultdict(list)

    for entry in history:
        timestamp = entry.get('timestamp', '')
        market_regime = entry.get('market_regime', 'UNKNOWN')

        for symbol, data in entry.get('token_predictions', {}).items():
            metrics = extract_metrics(data.get('reasoning', ''))
            price = data.get('price_at_prediction', 0)

            if price <= 0:
                continue

            call = Call(
                timestamp=timestamp,
                symbol=symbol,
                contract=data.get('contract', ''),
                verdict=data.get('verdict', 'NEUTRAL'),
                score=data.get('score', 0),
                price=price,
                reasoning=data.get('reasoning', ''),
                market_regime=market_regime,
                change_24h=metrics.get('change_24h'),
                buy_sell_ratio=metrics.get('buy_sell_ratio'),
            )
            token_calls[symbol].append(call)

    # Build token histories
    token_histories = {}

    for symbol, calls in token_calls.items():
        if len(calls) < 2:
            continue

        # Sort by timestamp
        calls = sorted(calls, key=lambda c: c.timestamp)

        prices = [c.price for c in calls]
        verdicts = [c.verdict for c in calls]

        first_price = prices[0]
        last_price = prices[-1]
        max_price = max(prices)
        min_price = min(prices)

        price_change = ((last_price - first_price) / first_price) * 100 if first_price > 0 else 0
        max_gain = ((max_price - first_price) / first_price) * 100 if first_price > 0 else 0
        max_loss = ((min_price - first_price) / first_price) * 100 if first_price > 0 else 0

        first_verdict = verdicts[0]
        last_verdict = verdicts[-1]
        flipped = first_verdict != last_verdict

        token_histories[symbol] = TokenHistory(
            symbol=symbol,
            contract=calls[0].contract,
            calls=calls,
            first_price=first_price,
            last_price=last_price,
            price_change_pct=price_change,
            first_verdict=first_verdict,
            last_verdict=last_verdict,
            verdict_flipped=flipped,
            max_price=max_price,
            min_price=min_price,
            max_gain_pct=max_gain,
            max_loss_pct=max_loss,
        )

    return token_histories


def analyze_bullish_calls(histories: Dict[str, TokenHistory]) -> None:
    """Analyze all bullish calls and their outcomes."""

    print("\n" + "=" * 90)
    print("BULLISH CALL ANALYSIS - All tokens where we went BULLISH at any point")
    print("=" * 90)

    # Find tokens where we were bullish
    bullish_tokens = []

    for symbol, hist in histories.items():
        bullish_calls = [c for c in hist.calls if c.verdict == 'BULLISH']
        if bullish_calls:
            # Find the first bullish call
            first_bullish = bullish_calls[0]

            # Calculate outcome from first bullish call to last known price
            entry_price = first_bullish.price

            # Get prices AFTER the bullish call
            later_prices = [c.price for c in hist.calls if c.timestamp > first_bullish.timestamp]

            if later_prices:
                final_price = later_prices[-1]
                max_after = max(later_prices)
                min_after = min(later_prices)
            else:
                final_price = hist.last_price
                max_after = hist.max_price
                min_after = hist.min_price

            outcome_pct = ((final_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
            max_up = ((max_after - entry_price) / entry_price) * 100 if entry_price > 0 else 0
            max_down = ((min_after - entry_price) / entry_price) * 100 if entry_price > 0 else 0

            bullish_tokens.append({
                'symbol': symbol,
                'first_bullish_time': first_bullish.timestamp,
                'score': first_bullish.score,
                'change_at_call': first_bullish.change_24h,
                'ratio_at_call': first_bullish.buy_sell_ratio,
                'entry_price': entry_price,
                'final_price': final_price,
                'outcome_pct': outcome_pct,
                'max_up_pct': max_up,
                'max_down_pct': max_down,
                'num_calls': len(bullish_calls),
                'avg_score': sum(c.score for c in bullish_calls) / len(bullish_calls),
            })

    # Sort by outcome
    bullish_tokens = sorted(bullish_tokens, key=lambda x: x['outcome_pct'], reverse=True)

    print(f"\nTotal tokens with bullish calls: {len(bullish_tokens)}")

    # Print results
    print(f"\n{'Symbol':<15} {'Score':>6} {'24h%':>8} {'Ratio':>6} {'Outcome':>10} {'MaxUp':>8} {'MaxDown':>9}")
    print("-" * 90)

    wins = []
    losses = []

    for t in bullish_tokens:
        score = t['score']
        change = t['change_at_call'] if t['change_at_call'] else 0
        ratio = t['ratio_at_call'] if t['ratio_at_call'] else 0
        outcome = t['outcome_pct']
        max_up = t['max_up_pct']
        max_down = t['max_down_pct']

        if outcome > 0:
            wins.append(t)
            status = "WIN"
        else:
            losses.append(t)
            status = "LOSS"

        print(f"{t['symbol']:<15} {score:>6.2f} {change:>7.1f}% {ratio:>5.1f}x "
              f"{outcome:>+9.1f}% {max_up:>+7.1f}% {max_down:>+8.1f}%  [{status}]")

    # Summary statistics
    print("\n" + "=" * 90)
    print("SUMMARY STATISTICS")
    print("=" * 90)

    total = len(bullish_tokens)
    win_count = len(wins)
    loss_count = len(losses)

    print(f"Total bullish calls: {total}")
    print(f"Wins: {win_count} ({win_count/total*100:.1f}%)")
    print(f"Losses: {loss_count} ({loss_count/total*100:.1f}%)")

    if wins:
        avg_win = sum(t['outcome_pct'] for t in wins) / len(wins)
        print(f"Average win: +{avg_win:.1f}%")
    if losses:
        avg_loss = sum(t['outcome_pct'] for t in losses) / len(losses)
        print(f"Average loss: {avg_loss:.1f}%")

    # Factor analysis
    print("\n" + "=" * 90)
    print("FACTOR ANALYSIS - What predicts success?")
    print("=" * 90)

    # By score level
    print("\n--- BY CONVICTION SCORE ---")
    score_buckets = {
        'Low (0.2-0.4)': lambda t: 0.2 <= t['score'] < 0.4,
        'Medium (0.4-0.6)': lambda t: 0.4 <= t['score'] < 0.6,
        'High (0.6-0.8)': lambda t: 0.6 <= t['score'] < 0.8,
        'Very High (>0.8)': lambda t: t['score'] >= 0.8,
    }

    for bucket_name, filter_func in score_buckets.items():
        bucket = [t for t in bullish_tokens if filter_func(t)]
        if bucket:
            w = len([t for t in bucket if t['outcome_pct'] > 0])
            l = len([t for t in bucket if t['outcome_pct'] <= 0])
            avg_out = sum(t['outcome_pct'] for t in bucket) / len(bucket)
            wr = w / len(bucket) * 100
            print(f"{bucket_name:<20}: {len(bucket):>3} calls, {w}W/{l}L ({wr:.0f}% WR), Avg: {avg_out:+.1f}%")

    # By existing pump level
    print("\n--- BY PUMP LEVEL AT CALL (24h change) ---")
    pump_buckets = {
        'Early (<20%)': lambda t: t['change_at_call'] is not None and t['change_at_call'] < 20,
        'Moderate (20-50%)': lambda t: t['change_at_call'] is not None and 20 <= t['change_at_call'] < 50,
        'Large (50-100%)': lambda t: t['change_at_call'] is not None and 50 <= t['change_at_call'] < 100,
        'Huge (100-300%)': lambda t: t['change_at_call'] is not None and 100 <= t['change_at_call'] < 300,
        'Extreme (>300%)': lambda t: t['change_at_call'] is not None and t['change_at_call'] >= 300,
        'Unknown': lambda t: t['change_at_call'] is None,
    }

    for bucket_name, filter_func in pump_buckets.items():
        bucket = [t for t in bullish_tokens if filter_func(t)]
        if bucket:
            w = len([t for t in bucket if t['outcome_pct'] > 0])
            l = len([t for t in bucket if t['outcome_pct'] <= 0])
            avg_out = sum(t['outcome_pct'] for t in bucket) / len(bucket)
            wr = w / len(bucket) * 100
            print(f"{bucket_name:<20}: {len(bucket):>3} calls, {w}W/{l}L ({wr:.0f}% WR), Avg: {avg_out:+.1f}%")

    # By buy/sell ratio
    print("\n--- BY BUY/SELL RATIO ---")
    ratio_buckets = {
        'Weak (<1.5x)': lambda t: t['ratio_at_call'] is not None and t['ratio_at_call'] < 1.5,
        'Moderate (1.5-2x)': lambda t: t['ratio_at_call'] is not None and 1.5 <= t['ratio_at_call'] < 2,
        'Strong (2-3x)': lambda t: t['ratio_at_call'] is not None and 2 <= t['ratio_at_call'] < 3,
        'Very Strong (>3x)': lambda t: t['ratio_at_call'] is not None and t['ratio_at_call'] >= 3,
        'Unknown': lambda t: t['ratio_at_call'] is None,
    }

    for bucket_name, filter_func in ratio_buckets.items():
        bucket = [t for t in bullish_tokens if filter_func(t)]
        if bucket:
            w = len([t for t in bucket if t['outcome_pct'] > 0])
            l = len([t for t in bucket if t['outcome_pct'] <= 0])
            avg_out = sum(t['outcome_pct'] for t in bucket) / len(bucket)
            wr = w / len(bucket) * 100
            print(f"{bucket_name:<20}: {len(bucket):>3} calls, {w}W/{l}L ({wr:.0f}% WR), Avg: {avg_out:+.1f}%")

    # Combined analysis - what works?
    print("\n" + "=" * 90)
    print("COMBINED FACTOR ANALYSIS - Finding winning combinations")
    print("=" * 90)

    combos = [
        ("Early + High Score", lambda t: t['change_at_call'] is not None and t['change_at_call'] < 30 and t['score'] >= 0.6),
        ("Early + Strong Ratio", lambda t: t['change_at_call'] is not None and t['change_at_call'] < 30 and t['ratio_at_call'] is not None and t['ratio_at_call'] >= 2),
        ("Early + High Score + Strong Ratio", lambda t: t['change_at_call'] is not None and t['change_at_call'] < 30 and t['score'] >= 0.6 and t['ratio_at_call'] is not None and t['ratio_at_call'] >= 2),
        ("Pumped (>50%) + Any", lambda t: t['change_at_call'] is not None and t['change_at_call'] >= 50),
        ("Very High Score (>0.7) + Any pump", lambda t: t['score'] >= 0.7),
    ]

    for combo_name, filter_func in combos:
        bucket = [t for t in bullish_tokens if filter_func(t)]
        if bucket:
            w = len([t for t in bucket if t['outcome_pct'] > 0])
            l = len([t for t in bucket if t['outcome_pct'] <= 0])
            avg_out = sum(t['outcome_pct'] for t in bucket) / len(bucket)
            wr = w / len(bucket) * 100
            print(f"{combo_name}:")
            print(f"  {len(bucket)} calls, {w}W/{l}L ({wr:.0f}% WR), Avg outcome: {avg_out:+.1f}%")

            # Show details if small sample
            if len(bucket) <= 10:
                for t in bucket:
                    status = "WIN" if t['outcome_pct'] > 0 else "LOSS"
                    print(f"    {t['symbol']}: {t['outcome_pct']:+.1f}% [{status}]")
            print()

    # Key insights
    print("\n" + "=" * 90)
    print("KEY INSIGHTS")
    print("=" * 90)

    # Best performing tokens
    print("\nTOP 5 WINS:")
    for t in bullish_tokens[:5]:
        if t['outcome_pct'] > 0:
            print(f"  {t['symbol']}: {t['outcome_pct']:+.1f}% (score={t['score']:.2f}, pump={t['change_at_call'] or 'N/A'}%)")

    # Worst performing tokens
    print("\nTOP 5 LOSSES:")
    for t in bullish_tokens[-5:]:
        if t['outcome_pct'] <= 0:
            print(f"  {t['symbol']}: {t['outcome_pct']:.1f}% (score={t['score']:.2f}, pump={t['change_at_call'] or 'N/A'}%)")

    # Calculate probability model
    print("\n" + "=" * 90)
    print("PROBABILITY MODEL")
    print("=" * 90)

    print("\nEstimated win probability by factor:")

    # Base rate
    base_wr = win_count / total if total > 0 else 0
    print(f"Base rate (all bullish calls): {base_wr*100:.1f}%")

    # Early entry bonus
    early = [t for t in bullish_tokens if t['change_at_call'] is not None and t['change_at_call'] < 30]
    if early:
        early_wr = len([t for t in early if t['outcome_pct'] > 0]) / len(early)
        print(f"Early entry (<30% pump): {early_wr*100:.1f}% (+{(early_wr-base_wr)*100:.1f}%)")

    # Late entry penalty
    late = [t for t in bullish_tokens if t['change_at_call'] is not None and t['change_at_call'] >= 50]
    if late:
        late_wr = len([t for t in late if t['outcome_pct'] > 0]) / len(late)
        print(f"Late entry (>50% pump): {late_wr*100:.1f}% ({(late_wr-base_wr)*100:+.1f}%)")


def main():
    print("Loading predictions...")
    histories = load_and_process_predictions()
    print(f"Loaded {len(histories)} tokens with 2+ predictions")

    analyze_bullish_calls(histories)


if __name__ == "__main__":
    main()
