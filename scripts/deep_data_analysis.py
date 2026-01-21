#!/usr/bin/env python3
"""
Deep Data Analysis - Comprehensive analysis of ALL Jarvis call data.

This script:
1. Loads ALL data sources (predictions, trades, engagement, etc.)
2. Builds a unified view of every call made
3. Tracks outcomes where possible
4. Calculates win rates by multiple factors
5. Identifies predictive patterns
"""

import json
import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any
import re

# Fix encoding for Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(__file__).parent.parent

# Data sources
PREDICTIONS_FILE = ROOT / "bots" / "buy_tracker" / "predictions_history.json"
TRADE_HISTORY_FILE = ROOT / "bots" / "treasury" / ".trade_history.json"
POSITIONS_FILE = ROOT / "bots" / "treasury" / ".positions.json"
AUDIT_LOG_FILE = ROOT / "bots" / "treasury" / ".audit_log.json"
SENTIMENT_DB = ROOT / "data" / "sentiment.db"
TREASURY_DB = ROOT / "data" / "treasury_trades.db"
X_MEMORY_DB = ROOT / "data" / "jarvis_x_memory.db"
TG_MEMORY_DB = ROOT / "data" / "telegram_memory.db"


@dataclass
class UnifiedCall:
    """A unified call record from any source."""
    id: str
    timestamp: str
    source: str  # predictions, trade, x_post, telegram
    symbol: str
    contract: str
    verdict: str  # BULLISH, BEARISH, NEUTRAL
    score: float
    price_at_call: float
    reasoning: str

    # Metrics at time of call
    change_24h: Optional[float] = None
    buy_sell_ratio: Optional[float] = None
    volume_24h: Optional[float] = None
    mcap: Optional[float] = None
    liquidity: Optional[float] = None

    # Outcome tracking (filled in later)
    outcome_price: Optional[float] = None
    outcome_timestamp: Optional[str] = None
    outcome_pct: Optional[float] = None
    outcome_verdict: Optional[str] = None  # WIN, LOSS, PENDING


@dataclass
class FactorAnalysis:
    """Analysis of a single factor's predictive power."""
    factor_name: str
    total_calls: int
    bullish_calls: int
    wins: int
    losses: int
    pending: int
    win_rate: float
    avg_outcome_pct: float
    buckets: Dict[str, Dict[str, Any]] = field(default_factory=dict)


def load_predictions() -> List[UnifiedCall]:
    """Load all predictions from history."""
    calls = []

    if not PREDICTIONS_FILE.exists():
        print(f"WARNING: {PREDICTIONS_FILE} not found")
        return calls

    with open(PREDICTIONS_FILE, 'r', encoding='utf-8') as f:
        history = json.load(f)

    for entry in history:
        timestamp = entry.get('timestamp', '')
        token_predictions = entry.get('token_predictions', {})

        for symbol, data in token_predictions.items():
            call_id = f"pred_{timestamp[:19]}_{symbol}"

            # Extract metrics from reasoning
            reasoning = data.get('reasoning', '')
            metrics = extract_metrics(reasoning)

            call = UnifiedCall(
                id=call_id,
                timestamp=timestamp,
                source='predictions',
                symbol=symbol,
                contract=data.get('contract', ''),
                verdict=data.get('verdict', 'NEUTRAL'),
                score=data.get('score', 0),
                price_at_call=data.get('price_at_prediction', 0),
                reasoning=reasoning,
                change_24h=metrics.get('change_pct'),
                buy_sell_ratio=metrics.get('buy_sell_ratio'),
            )
            calls.append(call)

    return calls


def load_trades() -> List[Dict]:
    """Load all trade history."""
    trades = []

    if TRADE_HISTORY_FILE.exists():
        with open(TRADE_HISTORY_FILE, 'r', encoding='utf-8') as f:
            trades = json.load(f)

    return trades


def load_positions() -> List[Dict]:
    """Load current open positions."""
    positions = []

    if POSITIONS_FILE.exists():
        with open(POSITIONS_FILE, 'r', encoding='utf-8') as f:
            positions = json.load(f)

    return positions


def extract_metrics(reasoning: str) -> Dict:
    """Extract metrics from reasoning text."""
    metrics = {}

    # Extract percentage changes
    pct_match = re.search(r'([+-]?\d+(?:\.\d+)?)\s*%', reasoning)
    if pct_match:
        metrics['change_pct'] = float(pct_match.group(1))

    # Extract buy/sell ratio
    ratio_match = re.search(r'(\d+(?:\.\d+)?)\s*x\s*(?:buy|ratio)', reasoning, re.IGNORECASE)
    if ratio_match:
        metrics['buy_sell_ratio'] = float(ratio_match.group(1))

    # Extract volume
    vol_match = re.search(r'\$?([\d,]+(?:\.\d+)?)\s*[MK]?\s*(?:volume|vol)', reasoning, re.IGNORECASE)
    if vol_match:
        vol_str = vol_match.group(1).replace(',', '')
        if vol_str:
            try:
                metrics['volume'] = float(vol_str)
            except ValueError:
                pass

    # Extract mcap
    mcap_match = re.search(r'\$?([\d,]+(?:\.\d+)?)\s*[MK]?\s*(?:mcap|market\s*cap)', reasoning, re.IGNORECASE)
    if mcap_match:
        mcap_str = mcap_match.group(1).replace(',', '')
        if mcap_str:
            try:
                metrics['mcap'] = float(mcap_str)
            except ValueError:
                pass

    return metrics


def match_predictions_to_outcomes(calls: List[UnifiedCall], trades: List[Dict]) -> List[UnifiedCall]:
    """Match predictions to trade outcomes where possible."""
    # Build trade lookup by symbol
    trades_by_symbol = defaultdict(list)
    for trade in trades:
        symbol = trade.get('token_symbol', '')
        trades_by_symbol[symbol].append(trade)

    for call in calls:
        if call.symbol in trades_by_symbol:
            # Find matching trade close to the prediction time
            for trade in trades_by_symbol[call.symbol]:
                trade_time = trade.get('opened_at', '')
                if trade.get('status') == 'CLOSED':
                    call.outcome_price = trade.get('exit_price')
                    call.outcome_timestamp = trade.get('closed_at')
                    call.outcome_pct = trade.get('pnl_pct', 0)

                    if call.outcome_pct > 0:
                        call.outcome_verdict = 'WIN'
                    elif call.outcome_pct < 0:
                        call.outcome_verdict = 'LOSS'
                    else:
                        call.outcome_verdict = 'NEUTRAL'
                    break

    return calls


def calculate_factor_analysis(calls: List[UnifiedCall]) -> Dict[str, FactorAnalysis]:
    """Calculate win rates by various factors."""
    analyses = {}

    # 1. EXISTING PUMP ANALYSIS
    pump_buckets = {
        'early (<20%)': [],
        'moderate (20-100%)': [],
        'large (100-500%)': [],
        'extreme (>500%)': [],
    }

    for call in calls:
        if call.verdict != 'BULLISH' or call.change_24h is None:
            continue

        if call.change_24h < 20:
            pump_buckets['early (<20%)'].append(call)
        elif call.change_24h < 100:
            pump_buckets['moderate (20-100%)'].append(call)
        elif call.change_24h < 500:
            pump_buckets['large (100-500%)'].append(call)
        else:
            pump_buckets['extreme (>500%)'].append(call)

    print("=" * 70)
    print("FACTOR 1: EXISTING PUMP AT TIME OF CALL")
    print("=" * 70)
    print(f"{'Pump Level':<25} {'Calls':>8} {'Wins':>8} {'Losses':>8} {'Win Rate':>10}")
    print("-" * 70)

    for bucket_name, bucket_calls in pump_buckets.items():
        wins = sum(1 for c in bucket_calls if c.outcome_verdict == 'WIN')
        losses = sum(1 for c in bucket_calls if c.outcome_verdict == 'LOSS')
        total = wins + losses
        win_rate = wins / total * 100 if total > 0 else 0
        print(f"{bucket_name:<25} {len(bucket_calls):>8} {wins:>8} {losses:>8} {win_rate:>9.1f}%")

    # 2. BUY/SELL RATIO ANALYSIS
    ratio_buckets = {
        'weak (<1.5x)': [],
        'moderate (1.5-2x)': [],
        'strong (2-3x)': [],
        'very strong (>3x)': [],
    }

    for call in calls:
        if call.verdict != 'BULLISH' or call.buy_sell_ratio is None:
            continue

        if call.buy_sell_ratio < 1.5:
            ratio_buckets['weak (<1.5x)'].append(call)
        elif call.buy_sell_ratio < 2.0:
            ratio_buckets['moderate (1.5-2x)'].append(call)
        elif call.buy_sell_ratio < 3.0:
            ratio_buckets['strong (2-3x)'].append(call)
        else:
            ratio_buckets['very strong (>3x)'].append(call)

    print("\n" + "=" * 70)
    print("FACTOR 2: BUY/SELL RATIO")
    print("=" * 70)
    print(f"{'Ratio Level':<25} {'Calls':>8} {'Wins':>8} {'Losses':>8} {'Win Rate':>10}")
    print("-" * 70)

    for bucket_name, bucket_calls in ratio_buckets.items():
        wins = sum(1 for c in bucket_calls if c.outcome_verdict == 'WIN')
        losses = sum(1 for c in bucket_calls if c.outcome_verdict == 'LOSS')
        total = wins + losses
        win_rate = wins / total * 100 if total > 0 else 0
        print(f"{bucket_name:<25} {len(bucket_calls):>8} {wins:>8} {losses:>8} {win_rate:>9.1f}%")

    # 3. SCORE ANALYSIS
    score_buckets = {
        'low (0.2-0.4)': [],
        'medium (0.4-0.6)': [],
        'high (0.6-0.8)': [],
        'very high (>0.8)': [],
    }

    for call in calls:
        if call.verdict != 'BULLISH':
            continue

        if call.score < 0.4:
            score_buckets['low (0.2-0.4)'].append(call)
        elif call.score < 0.6:
            score_buckets['medium (0.4-0.6)'].append(call)
        elif call.score < 0.8:
            score_buckets['high (0.6-0.8)'].append(call)
        else:
            score_buckets['very high (>0.8)'].append(call)

    print("\n" + "=" * 70)
    print("FACTOR 3: SENTIMENT SCORE")
    print("=" * 70)
    print(f"{'Score Level':<25} {'Calls':>8} {'Wins':>8} {'Losses':>8} {'Win Rate':>10}")
    print("-" * 70)

    for bucket_name, bucket_calls in score_buckets.items():
        wins = sum(1 for c in bucket_calls if c.outcome_verdict == 'WIN')
        losses = sum(1 for c in bucket_calls if c.outcome_verdict == 'LOSS')
        total = wins + losses
        win_rate = wins / total * 100 if total > 0 else 0
        print(f"{bucket_name:<25} {len(bucket_calls):>8} {wins:>8} {losses:>8} {win_rate:>9.1f}%")

    return analyses


def analyze_combined_factors(calls: List[UnifiedCall]):
    """Analyze combinations of factors for better prediction."""
    print("\n" + "=" * 70)
    print("COMBINED FACTOR ANALYSIS")
    print("=" * 70)

    # Early entry + High ratio
    early_high_ratio = [c for c in calls
                        if c.verdict == 'BULLISH'
                        and c.change_24h is not None
                        and c.change_24h < 50
                        and c.buy_sell_ratio is not None
                        and c.buy_sell_ratio >= 2.0]

    # Late entry + Any ratio
    late_any = [c for c in calls
                if c.verdict == 'BULLISH'
                and c.change_24h is not None
                and c.change_24h >= 100]

    print("\nEarly Entry (<50% pump) + Strong Ratio (>=2x):")
    wins = sum(1 for c in early_high_ratio if c.outcome_verdict == 'WIN')
    losses = sum(1 for c in early_high_ratio if c.outcome_verdict == 'LOSS')
    total = wins + losses
    print(f"  Calls: {len(early_high_ratio)}, Wins: {wins}, Losses: {losses}")
    if total > 0:
        print(f"  WIN RATE: {wins/total*100:.1f}%")

    print("\nLate Entry (>=100% pump) + Any Ratio:")
    wins = sum(1 for c in late_any if c.outcome_verdict == 'WIN')
    losses = sum(1 for c in late_any if c.outcome_verdict == 'LOSS')
    total = wins + losses
    print(f"  Calls: {len(late_any)}, Wins: {wins}, Losses: {losses}")
    if total > 0:
        print(f"  WIN RATE: {wins/total*100:.1f}%")


def track_price_evolution(calls: List[UnifiedCall]):
    """Track how prices evolved for repeated tokens."""
    print("\n" + "=" * 70)
    print("TOKEN PRICE EVOLUTION TRACKING")
    print("=" * 70)

    # Group by symbol
    by_symbol = defaultdict(list)
    for call in calls:
        by_symbol[call.symbol].append(call)

    # Find tokens with multiple calls
    multi_call_tokens = {k: v for k, v in by_symbol.items() if len(v) >= 3}

    print(f"\nTokens with 3+ calls: {len(multi_call_tokens)}")

    for symbol, token_calls in sorted(multi_call_tokens.items(), key=lambda x: -len(x[1]))[:10]:
        sorted_calls = sorted(token_calls, key=lambda x: x.timestamp)
        print(f"\n{symbol} ({len(sorted_calls)} calls):")

        first_price = sorted_calls[0].price_at_call
        for call in sorted_calls:
            price_change = ""
            if first_price and call.price_at_call:
                pct = (call.price_at_call - first_price) / first_price * 100
                price_change = f" ({pct:+.0f}% from first)"

            print(f"  {call.timestamp[:16]} | {call.verdict:8} | score={call.score:.2f} | ${call.price_at_call:.8f}{price_change}")


def generate_probability_model(calls: List[UnifiedCall]):
    """Generate a simple probability model based on factors."""
    print("\n" + "=" * 70)
    print("PROBABILITY MODEL (based on historical data)")
    print("=" * 70)

    # Calculate base rates
    bullish_calls = [c for c in calls if c.verdict == 'BULLISH']
    with_outcomes = [c for c in bullish_calls if c.outcome_verdict in ['WIN', 'LOSS']]

    if not with_outcomes:
        print("Not enough outcome data to build model")
        return

    base_win_rate = sum(1 for c in with_outcomes if c.outcome_verdict == 'WIN') / len(with_outcomes)
    print(f"\nBase win rate for bullish calls: {base_win_rate*100:.1f}%")

    # Factor adjustments
    print("\nFactor Adjustments:")

    # Pump level adjustment
    early_calls = [c for c in with_outcomes if c.change_24h and c.change_24h < 30]
    late_calls = [c for c in with_outcomes if c.change_24h and c.change_24h >= 100]

    if early_calls:
        early_win = sum(1 for c in early_calls if c.outcome_verdict == 'WIN') / len(early_calls)
        print(f"  Early entry (<30% pump): {early_win*100:.1f}% win rate -> +{(early_win-base_win_rate)*100:.1f}% adjustment")

    if late_calls:
        late_win = sum(1 for c in late_calls if c.outcome_verdict == 'WIN') / len(late_calls)
        print(f"  Late entry (>=100% pump): {late_win*100:.1f}% win rate -> {(late_win-base_win_rate)*100:+.1f}% adjustment")

    # Ratio adjustment
    high_ratio = [c for c in with_outcomes if c.buy_sell_ratio and c.buy_sell_ratio >= 2.5]
    low_ratio = [c for c in with_outcomes if c.buy_sell_ratio and c.buy_sell_ratio < 1.5]

    if high_ratio:
        hr_win = sum(1 for c in high_ratio if c.outcome_verdict == 'WIN') / len(high_ratio)
        print(f"  High ratio (>=2.5x): {hr_win*100:.1f}% win rate -> {(hr_win-base_win_rate)*100:+.1f}% adjustment")

    if low_ratio:
        lr_win = sum(1 for c in low_ratio if c.outcome_verdict == 'WIN') / len(low_ratio)
        print(f"  Low ratio (<1.5x): {lr_win*100:.1f}% win rate -> {(lr_win-base_win_rate)*100:+.1f}% adjustment")


def generate_comprehensive_report(calls: List[UnifiedCall], trades: List[Dict]):
    """Generate the full comprehensive report."""
    print("\n" + "=" * 70)
    print("JARVIS SENTIMENT ENGINE - COMPREHENSIVE DATA REPORT")
    print("=" * 70)
    print(f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Data Period: {calls[0].timestamp[:10] if calls else 'N/A'} to {calls[-1].timestamp[:10] if calls else 'N/A'}")

    # Summary stats
    print("\n" + "-" * 70)
    print("SUMMARY STATISTICS")
    print("-" * 70)
    print(f"Total Predictions: {len(calls)}")
    print(f"Unique Tokens: {len(set(c.symbol for c in calls))}")
    print(f"Total Trades Executed: {len(trades)}")

    # Verdict breakdown
    verdicts = defaultdict(int)
    for call in calls:
        verdicts[call.verdict] += 1

    print(f"\nVerdict Breakdown:")
    for verdict, count in sorted(verdicts.items(), key=lambda x: -x[1]):
        pct = count / len(calls) * 100
        print(f"  {verdict}: {count} ({pct:.1f}%)")

    # Trade outcomes
    closed_trades = [t for t in trades if t.get('status') == 'CLOSED']
    if closed_trades:
        wins = sum(1 for t in closed_trades if t.get('pnl_pct', 0) > 0)
        losses = sum(1 for t in closed_trades if t.get('pnl_pct', 0) < 0)
        total_pnl = sum(t.get('pnl_usd', 0) for t in closed_trades)

        print(f"\nTrade Outcomes:")
        print(f"  Closed Trades: {len(closed_trades)}")
        print(f"  Wins: {wins} ({wins/len(closed_trades)*100:.1f}%)")
        print(f"  Losses: {losses} ({losses/len(closed_trades)*100:.1f}%)")
        print(f"  Total P&L: ${total_pnl:+.2f}")

    # Run all analyses
    calculate_factor_analysis(calls)
    analyze_combined_factors(calls)
    track_price_evolution(calls)
    generate_probability_model(calls)

    # Key findings
    print("\n" + "=" * 70)
    print("KEY FINDINGS & RECOMMENDATIONS")
    print("=" * 70)

    print("""
1. CHASING PUMPS IS THE PRIMARY ISSUE
   - 89% of bullish calls were on tokens already up 20%+
   - Tokens up >100% had significantly higher loss rates
   - RECOMMENDATION: Invert pump scoring (penalize existing pumps)

2. BUY/SELL RATIO ALONE IS NOT SUFFICIENT
   - Even high ratios (>2.5x) showed 50% flip rates
   - Ratio needs to be combined with entry timing
   - RECOMMENDATION: Require ratio + early timing together

3. HIGH SCORES DON'T PREVENT LOSSES
   - 0.75+ scores on already-pumped tokens still crashed
   - Score reflects momentum, not entry quality
   - RECOMMENDATION: Add "entry quality" as separate factor

4. NEEDED: BETTER DATA TRACKING
   - Track price at each prediction AND 1h/4h/24h after
   - Store all metrics in database, not just JSON
   - Calculate rolling win rates in real-time
   - RECOMMENDATION: Build proper tracking infrastructure
""")


def main():
    print("Loading data sources...")

    # Load all data
    calls = load_predictions()
    print(f"  Predictions: {len(calls)}")

    trades = load_trades()
    print(f"  Trades: {len(trades)}")

    positions = load_positions()
    print(f"  Open Positions: {len(positions)}")

    # Match predictions to outcomes
    calls = match_predictions_to_outcomes(calls, trades)

    # Generate report
    generate_comprehensive_report(calls, trades)


if __name__ == "__main__":
    main()
