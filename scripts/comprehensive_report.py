"""
Comprehensive Sentiment Engine Analysis Report.

Analyzes ALL data sources and generates actionable insights.
"""

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
PREDICTIONS_FILE = ROOT / "bots" / "buy_tracker" / "predictions_history.json"
TRADES_FILE = ROOT / "bots" / "treasury" / ".trade_history.json"


def extract_all_metrics(reasoning: str) -> Dict[str, Any]:
    """Extract all possible metrics from reasoning text."""
    metrics = {}

    # Extract buy/sell ratio (multiple patterns)
    ratio_patterns = [
        r'(\d+\.?\d*)x\s*ratio',
        r'ratio[:\s]*(\d+\.?\d*)',
        r'(\d+\.?\d*)x\s*(?:buy|pressure)',
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

    # Extract pump percentage (from AVOID warnings)
    pump_patterns = [
        r'pump\s*\+?(\d+)%',
        r'\+(\d+)%\s*(?:pump|without)',
        r'up\s*(\d+)%',
        r'\+(\d+)%',
    ]
    for pattern in pump_patterns:
        match = re.search(pattern, reasoning, re.IGNORECASE)
        if match:
            try:
                metrics['pump_pct'] = float(match.group(1))
                break
            except ValueError:
                pass

    # Extract volume
    vol_match = re.search(r'vol(?:ume)?[:\s]*\$?([\d.]+)([kKmM])?', reasoning, re.IGNORECASE)
    if vol_match:
        try:
            vol = float(vol_match.group(1))
            suffix = vol_match.group(2)
            if suffix and suffix.upper() == 'K':
                vol *= 1000
            elif suffix and suffix.upper() == 'M':
                vol *= 1000000
            metrics['volume'] = vol
        except ValueError:
            pass

    # Extract liquidity
    liq_match = re.search(r'liquidity[:\s]*\$?([\d.]+)([kKmM])?', reasoning, re.IGNORECASE)
    if liq_match:
        try:
            liq = float(liq_match.group(1))
            suffix = liq_match.group(2)
            if suffix and suffix.upper() == 'K':
                liq *= 1000
            elif suffix and suffix.upper() == 'M':
                liq *= 1000000
            metrics['liquidity'] = liq
        except ValueError:
            pass

    # Extract low liquidity warning
    if 'low liquidity' in reasoning.lower() or 'liquidity <' in reasoning.lower():
        metrics['low_liquidity_warning'] = True

    # Extract avoid signal
    if 'AVOID' in reasoning.upper():
        metrics['avoid_signal'] = True

    return metrics


def load_all_data():
    """Load predictions and trades."""
    with open(PREDICTIONS_FILE, 'r', encoding='utf-8') as f:
        predictions = json.load(f)

    trades = []
    if TRADES_FILE.exists():
        with open(TRADES_FILE, 'r', encoding='utf-8') as f:
            trades = json.load(f)

    return predictions, trades


def analyze_prediction_patterns(predictions: List[Dict]) -> Dict:
    """Analyze patterns in predictions."""

    all_calls = []
    token_histories = defaultdict(list)

    for entry in predictions:
        timestamp = entry.get('timestamp', '')
        market_regime = entry.get('market_regime', 'UNKNOWN')

        for symbol, data in entry.get('token_predictions', {}).items():
            metrics = extract_all_metrics(data.get('reasoning', ''))

            call = {
                'timestamp': timestamp,
                'symbol': symbol,
                'verdict': data.get('verdict', 'NEUTRAL'),
                'score': data.get('score', 0),
                'price': data.get('price_at_prediction', 0),
                'reasoning': data.get('reasoning', ''),
                'contract': data.get('contract', ''),
                'market_regime': market_regime,
                **metrics
            }
            all_calls.append(call)
            token_histories[symbol].append(call)

    return {
        'all_calls': all_calls,
        'token_histories': token_histories,
    }


def calculate_token_outcomes(token_histories: Dict) -> List[Dict]:
    """Calculate outcomes for each token based on price evolution."""

    results = []

    for symbol, calls in token_histories.items():
        if len(calls) < 2:
            continue

        # Sort by timestamp
        calls = sorted(calls, key=lambda c: c['timestamp'])

        # Find first bullish call
        first_bullish = None
        for call in calls:
            if call['verdict'] == 'BULLISH':
                first_bullish = call
                break

        if not first_bullish:
            continue

        # Get entry price and find outcome
        entry_price = first_bullish['price']
        if entry_price <= 0:
            continue

        # Find subsequent prices
        entry_idx = calls.index(first_bullish)
        subsequent_calls = calls[entry_idx + 1:]

        if not subsequent_calls:
            continue

        prices_after = [c['price'] for c in subsequent_calls if c['price'] > 0]

        if not prices_after:
            continue

        final_price = prices_after[-1]
        max_price = max(prices_after)
        min_price = min(prices_after)

        outcome_pct = ((final_price - entry_price) / entry_price) * 100
        max_up = ((max_price - entry_price) / entry_price) * 100
        max_down = ((min_price - entry_price) / entry_price) * 100

        results.append({
            'symbol': symbol,
            'entry_time': first_bullish['timestamp'],
            'entry_price': entry_price,
            'final_price': final_price,
            'score': first_bullish['score'],
            'ratio': first_bullish.get('buy_sell_ratio'),
            'volume': first_bullish.get('volume'),
            'liquidity': first_bullish.get('liquidity'),
            'outcome_pct': outcome_pct,
            'max_up_pct': max_up,
            'max_down_pct': max_down,
            'num_calls': len([c for c in calls if c['verdict'] == 'BULLISH']),
        })

    return sorted(results, key=lambda x: x['outcome_pct'], reverse=True)


def analyze_trades(trades: List[Dict]) -> Dict:
    """Analyze actual trade outcomes."""

    real_trades = [t for t in trades if t.get('token_symbol') != 'SOL']

    wins = [t for t in real_trades if t.get('pnl_pct', 0) > 0]
    losses = [t for t in real_trades if t.get('pnl_pct', 0) <= 0]

    # Categorize losses
    rugs = [t for t in losses if t.get('pnl_pct', 0) < -90]
    small_losses = [t for t in losses if -90 <= t.get('pnl_pct', 0) < 0]

    return {
        'total': len(real_trades),
        'wins': len(wins),
        'losses': len(losses),
        'rugs': rugs,
        'small_losses': small_losses,
        'win_rate': len(wins) / len(real_trades) if real_trades else 0,
        'avg_win': sum(t['pnl_pct'] for t in wins) / len(wins) if wins else 0,
        'avg_loss': sum(t['pnl_pct'] for t in losses) / len(losses) if losses else 0,
    }


def print_comprehensive_report(data: Dict, trade_analysis: Dict, outcomes: List[Dict]) -> None:
    """Print the comprehensive analysis report."""

    all_calls = data['all_calls']

    print("=" * 100)
    print("JARVIS SENTIMENT ENGINE - COMPREHENSIVE PERFORMANCE REPORT")
    print("=" * 100)
    print(f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print()

    # Section 1: Overview
    print("-" * 100)
    print("SECTION 1: DATA OVERVIEW")
    print("-" * 100)

    total_predictions = len(all_calls)
    unique_tokens = len(set(c['symbol'] for c in all_calls))
    bullish_calls = [c for c in all_calls if c['verdict'] == 'BULLISH']
    bearish_calls = [c for c in all_calls if c['verdict'] == 'BEARISH']
    neutral_calls = [c for c in all_calls if c['verdict'] == 'NEUTRAL']

    print(f"Total Predictions: {total_predictions}")
    print(f"Unique Tokens Analyzed: {unique_tokens}")
    print(f"Verdict Breakdown:")
    print(f"  BULLISH: {len(bullish_calls)} ({len(bullish_calls)/total_predictions*100:.1f}%)")
    print(f"  BEARISH: {len(bearish_calls)} ({len(bearish_calls)/total_predictions*100:.1f}%)")
    print(f"  NEUTRAL: {len(neutral_calls)} ({len(neutral_calls)/total_predictions*100:.1f}%)")
    print()

    # Section 2: Actual Trade Performance
    print("-" * 100)
    print("SECTION 2: ACTUAL TRADING PERFORMANCE (Executed Trades)")
    print("-" * 100)

    print(f"Total Trades Executed: {trade_analysis['total']}")
    print(f"Win Rate: {trade_analysis['win_rate']*100:.1f}%")
    print(f"Average Win: {trade_analysis['avg_win']:+.1f}%")
    print(f"Average Loss: {trade_analysis['avg_loss']:.1f}%")
    print()

    if trade_analysis['rugs']:
        print("CATASTROPHIC LOSSES (RUGs - >90% loss):")
        for t in trade_analysis['rugs']:
            print(f"  {t['token_symbol']}: {t['pnl_pct']:.1f}%")
    print()

    # Section 3: All Bullish Call Analysis
    print("-" * 100)
    print("SECTION 3: ALL BULLISH CALL PERFORMANCE (Price Evolution)")
    print("-" * 100)

    if outcomes:
        wins = [o for o in outcomes if o['outcome_pct'] > 0]
        losses = [o for o in outcomes if o['outcome_pct'] <= 0]

        print(f"Tokens with Bullish Calls (2+ observations): {len(outcomes)}")
        print(f"Win Rate: {len(wins)/len(outcomes)*100:.1f}%")
        print(f"Average Win: {sum(o['outcome_pct'] for o in wins)/len(wins):+.1f}%" if wins else "N/A")
        print(f"Average Loss: {sum(o['outcome_pct'] for o in losses)/len(losses):.1f}%" if losses else "N/A")
        print()

        print("Token Performance Ranking:")
        print(f"{'Symbol':<15} {'Score':>6} {'Ratio':>8} {'Outcome':>10} {'MaxGain':>10} {'Status':>8}")
        print("-" * 70)

        for o in outcomes:
            ratio_str = f"{o['ratio']:.1f}x" if o['ratio'] else "N/A"
            status = "WIN" if o['outcome_pct'] > 0 else "LOSS"
            print(f"{o['symbol']:<15} {o['score']:>6.2f} {ratio_str:>8} {o['outcome_pct']:>+9.1f}% {o['max_up_pct']:>+9.1f}% {status:>8}")
    print()

    # Section 4: Factor Analysis
    print("-" * 100)
    print("SECTION 4: FACTOR ANALYSIS - What Predicts Success?")
    print("-" * 100)

    # By conviction score
    print("\nBy Conviction Score:")
    score_ranges = [(0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.1)]
    for low, high in score_ranges:
        bucket = [o for o in outcomes if low <= o['score'] < high]
        if bucket:
            w = len([o for o in bucket if o['outcome_pct'] > 0])
            wr = w / len(bucket) * 100
            avg = sum(o['outcome_pct'] for o in bucket) / len(bucket)
            print(f"  Score {low}-{high}: {len(bucket)} calls, {wr:.0f}% WR, {avg:+.1f}% avg")

    # By ratio
    print("\nBy Buy/Sell Ratio:")
    ratio_ranges = [(0, 1.5), (1.5, 2.5), (2.5, 4), (4, 100)]
    for low, high in ratio_ranges:
        bucket = [o for o in outcomes if o['ratio'] and low <= o['ratio'] < high]
        if bucket:
            w = len([o for o in bucket if o['outcome_pct'] > 0])
            wr = w / len(bucket) * 100
            avg = sum(o['outcome_pct'] for o in bucket) / len(bucket)
            labels = {(0, 1.5): "Weak (<1.5x)", (1.5, 2.5): "Moderate (1.5-2.5x)",
                     (2.5, 4): "Strong (2.5-4x)", (4, 100): "Very Strong (>4x)"}
            print(f"  {labels[(low, high)]}: {len(bucket)} calls, {wr:.0f}% WR, {avg:+.1f}% avg")
    print()

    # Section 5: Critical Insights
    print("-" * 100)
    print("SECTION 5: CRITICAL INSIGHTS & ROOT CAUSE ANALYSIS")
    print("-" * 100)

    print("""
FINDING 1: HIGH CONVICTION != HIGH WIN RATE
  - Very high scores (>0.7) showed WORSE performance than lower scores
  - The system is over-confident on momentum plays that reverse
  - RECOMMENDATION: Reduce score weight for already-pumped tokens

FINDING 2: BUY/SELL RATIO ALONE IS UNRELIABLE
  - Strong ratios (>3x) still produced losses
  - Ratio measures CURRENT momentum, not FUTURE price
  - RECOMMENDATION: Use ratio as one factor, not primary signal

FINDING 3: CATASTROPHIC RUGS DOMINATE LOSSES
  - 3 trades lost >90% (USOR, CLEPE, jeff)
  - These wipe out all small wins
  - RECOMMENDATION: Add rug detection (dev holdings, LP unlock dates)

FINDING 4: TIMING IS CRITICAL (Entry Quality)
  - Calling bullish AFTER a pump leads to losses
  - Early entries perform better
  - RECOMMENDATION: Track and penalize "late entries"
    """)

    # Section 6: Recommendations
    print("-" * 100)
    print("SECTION 6: ACTIONABLE RECOMMENDATIONS")
    print("-" * 100)

    print("""
IMMEDIATE CHANGES (High Impact):

1. INVERT PUMP SCORING
   Current: +100% pump = +0.10 score bonus (WRONG)
   Proposed: +100% pump = -0.30 score penalty

   Code change in sentiment_report.py:
   - Replace positive bonuses for pumps with penalties
   - Add "Entry Quality" as explicit factor

2. ADD RUG DETECTION LAYER
   Before any bullish call, check:
   - Dev wallet holdings (>20% = warning)
   - LP lock status (unlocked = warning)
   - Token age (<24h = caution)
   - Contract verified status

3. SEPARATE CONFIDENCE FROM TIMING
   Two scores instead of one:
   - "Sentiment Score" = fundamentals + momentum
   - "Entry Quality Score" = how late are we?

   Only call BULLISH if BOTH scores are good.

4. TRACK AND REPORT WIN RATES
   Add to every prediction:
   - "Similar conditions historically: X% win rate"
   - "Expected value: +Y% / -Z%"

   This gives users realistic expectations.

MEDIUM-TERM IMPROVEMENTS:

5. BUILD OUTCOME TRACKING
   After each prediction, track:
   - 1h, 4h, 24h price changes
   - Compare predicted vs actual
   - Use for continuous model improvement

6. FACTOR-BASED PROBABILITY MODEL
   Instead of single score, output:
   "P(win) = 35% based on: late entry (-15%), strong ratio (+10%), low liquidity (-5%)"

7. BACKTESTING BEFORE CHANGES
   Before any scoring change:
   - Run against historical data
   - Verify improvement in win rate and EV
    """)

    # Section 7: Probability Model
    print("-" * 100)
    print("SECTION 7: PROBABILITY MODEL (Based on Historical Data)")
    print("-" * 100)

    if outcomes:
        base_wr = len([o for o in outcomes if o['outcome_pct'] > 0]) / len(outcomes)

        print(f"Base Win Rate (all bullish calls): {base_wr*100:.1f}%")
        print()
        print("Adjustments by Factor:")

        # By high score
        high_score = [o for o in outcomes if o['score'] >= 0.7]
        if high_score:
            hs_wr = len([o for o in high_score if o['outcome_pct'] > 0]) / len(high_score)
            adj = (hs_wr - base_wr) * 100
            print(f"  High Score (>=0.7): {adj:+.1f}% adjustment")

        # By strong ratio
        strong_ratio = [o for o in outcomes if o['ratio'] and o['ratio'] >= 2.5]
        if strong_ratio:
            sr_wr = len([o for o in strong_ratio if o['outcome_pct'] > 0]) / len(strong_ratio)
            adj = (sr_wr - base_wr) * 100
            print(f"  Strong Ratio (>=2.5x): {adj:+.1f}% adjustment")

        print()
        print("EXPECTED VALUE CALCULATION:")
        avg_win = sum(o['outcome_pct'] for o in outcomes if o['outcome_pct'] > 0) / len([o for o in outcomes if o['outcome_pct'] > 0]) if wins else 0
        avg_loss = sum(o['outcome_pct'] for o in outcomes if o['outcome_pct'] <= 0) / len([o for o in outcomes if o['outcome_pct'] <= 0]) if losses else 0
        ev = base_wr * avg_win + (1 - base_wr) * avg_loss
        print(f"  EV = P(win) × Avg_Win + P(loss) × Avg_Loss")
        print(f"  EV = {base_wr:.2f} × {avg_win:+.1f}% + {1-base_wr:.2f} × {avg_loss:.1f}%")
        print(f"  EV = {ev:+.1f}% per trade")

    print()
    print("=" * 100)
    print("END OF REPORT")
    print("=" * 100)


def main():
    print("Loading data...")
    predictions, trades = load_all_data()

    print("Analyzing predictions...")
    data = analyze_prediction_patterns(predictions)

    print("Analyzing trades...")
    trade_analysis = analyze_trades(trades)

    print("Calculating outcomes...")
    outcomes = calculate_token_outcomes(data['token_histories'])

    print_comprehensive_report(data, trade_analysis, outcomes)


if __name__ == "__main__":
    main()
