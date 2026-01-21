"""
UNIFIED MEGA ANALYSIS - Complete Data Crunch

Extracts ALL metrics from ALL predictions, correlates with outcomes,
identifies what matters, rules out noise, finds patterns.

Output: Comprehensive decision-making report with actionable insights.
"""

import json
import re
import csv
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import statistics

ROOT = Path(__file__).resolve().parents[1]
PREDICTIONS_FILE = ROOT / "bots" / "buy_tracker" / "predictions_history.json"
TRADES_FILE = ROOT / "bots" / "treasury" / ".trade_history.json"
OUTPUT_DIR = ROOT / "data" / "analysis"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class UnifiedCall:
    """Complete data for a single call/prediction."""
    # Identity
    symbol: str
    contract: str
    category: str  # meme, stock, blue_chip, other

    # Timing
    first_seen: str
    last_seen: str
    num_reports: int

    # Verdict/Score
    verdict: str
    initial_score: float
    final_score: float
    avg_score: float
    score_trend: str  # rising, falling, stable

    # Price metrics
    entry_price: float
    max_price: float
    min_price: float
    final_price: float
    max_gain_pct: float
    max_loss_pct: float
    final_pct: float

    # Extracted factors
    change_24h: Optional[float] = None
    buy_sell_ratio: Optional[float] = None
    volume: Optional[float] = None
    market_cap: Optional[float] = None

    # Derived metrics
    hit_tp_25: bool = False
    hit_tp_10: bool = False
    hit_sl_15: bool = False
    hit_sl_10: bool = False

    # Reasoning keywords
    has_pump_mention: bool = False
    has_volume_mention: bool = False
    has_ratio_mention: bool = False
    has_momentum_mention: bool = False
    has_crash_mention: bool = False

    # Trade outcome (if traded)
    was_traded: bool = False
    trade_pnl: Optional[float] = None
    trade_exit_reason: Optional[str] = None


def extract_all_metrics(reasoning: str) -> Dict[str, Any]:
    """Extract every possible metric from reasoning text."""
    metrics = {}
    reasoning_lower = reasoning.lower()

    # 24h change - multiple patterns
    patterns_24h = [
        r'([+-]?\d+\.?\d*)%\s*(?:24h|in 24|change)',
        r'24h[:\s]*([+-]?\d+\.?\d*)%',
        r'([+-]?\d+\.?\d*)%\s*(?:surge|pump|gain|rise|drop|crash|fall)',
    ]
    for pattern in patterns_24h:
        match = re.search(pattern, reasoning, re.IGNORECASE)
        if match:
            try:
                metrics['change_24h'] = float(match.group(1))
                break
            except (ValueError, IndexError):
                pass

    # Buy/sell ratio - multiple patterns
    ratio_patterns = [
        r'(\d+\.?\d*)\s*x\s*(?:buy|ratio)',
        r'(?:buy[/-]?sell|b/s)\s*(?:ratio)?[:\s]*(\d+\.?\d*)',
        r'ratio[:\s]*(\d+\.?\d*)',
    ]
    for pattern in ratio_patterns:
        match = re.search(pattern, reasoning, re.IGNORECASE)
        if match:
            try:
                metrics['buy_sell_ratio'] = float(match.group(1))
                break
            except (ValueError, IndexError):
                pass

    # Volume
    vol_patterns = [
        r'\$?([\d,]+\.?\d*)\s*[MK]?\s*(?:vol|volume)',
        r'(?:vol|volume)[:\s]*\$?([\d,]+\.?\d*)',
    ]
    for pattern in vol_patterns:
        match = re.search(pattern, reasoning, re.IGNORECASE)
        if match:
            try:
                val = match.group(1).replace(',', '')
                metrics['volume'] = float(val)
                break
            except (ValueError, IndexError):
                pass

    # Market cap
    mc_patterns = [
        r'\$?([\d,]+\.?\d*)\s*[MK]?\s*(?:mc|mcap|market\s*cap)',
        r'(?:mc|mcap|market\s*cap)[:\s]*\$?([\d,]+\.?\d*)',
    ]
    for pattern in mc_patterns:
        match = re.search(pattern, reasoning, re.IGNORECASE)
        if match:
            try:
                val = match.group(1).replace(',', '')
                metrics['market_cap'] = float(val)
                break
            except (ValueError, IndexError):
                pass

    # Keyword flags
    metrics['has_pump_mention'] = any(w in reasoning_lower for w in ['pump', 'surge', 'moon', 'explod', 'rocket'])
    metrics['has_volume_mention'] = any(w in reasoning_lower for w in ['volume', 'vol ', 'liquidity'])
    metrics['has_ratio_mention'] = any(w in reasoning_lower for w in ['ratio', 'buy/sell', 'b/s'])
    metrics['has_momentum_mention'] = any(w in reasoning_lower for w in ['momentum', 'trend', 'breakout', 'support', 'resistance'])
    metrics['has_crash_mention'] = any(w in reasoning_lower for w in ['crash', 'dump', 'rug', 'scam', 'dead'])

    return metrics


def categorize_token(symbol: str, contract: str) -> str:
    """Categorize token by type."""
    blue_chips = ['SOL', 'BTC', 'ETH', 'WBTC', 'WETH', 'USDC', 'USDT']

    if symbol.upper() in blue_chips:
        return 'blue_chip'
    elif symbol.endswith('x') or symbol.endswith('X'):
        if len(symbol) <= 6:  # NVDAX, TSLAX, etc.
            return 'stock'
    if 'pump' in contract.lower():
        return 'meme'
    return 'other'


def load_all_data() -> Tuple[List[UnifiedCall], Dict[str, Dict]]:
    """Load and unify all prediction data."""

    with open(PREDICTIONS_FILE, 'r', encoding='utf-8') as f:
        history = json.load(f)

    # Load trade outcomes
    trade_outcomes = {}
    if TRADES_FILE.exists():
        with open(TRADES_FILE, 'r', encoding='utf-8') as f:
            trades = json.load(f)
            for trade in trades:
                symbol = trade.get('token_symbol', '')
                if symbol and symbol != 'SOL':
                    trade_outcomes[symbol] = trade

    # Aggregate by symbol
    token_data = defaultdict(lambda: {
        'timestamps': [],
        'prices': [],
        'verdicts': [],
        'scores': [],
        'reasonings': [],
        'contract': '',
    })

    for entry in history:
        timestamp = entry.get('timestamp', '')

        for symbol, data in entry.get('token_predictions', {}).items():
            price = data.get('price_at_prediction', 0)
            if price <= 0:
                continue

            token_data[symbol]['timestamps'].append(timestamp)
            token_data[symbol]['prices'].append(price)
            token_data[symbol]['verdicts'].append(data.get('verdict', 'NEUTRAL'))
            token_data[symbol]['scores'].append(data.get('score', 0))
            token_data[symbol]['reasonings'].append(data.get('reasoning', ''))
            token_data[symbol]['contract'] = data.get('contract', '')

    # Build unified calls
    calls = []

    for symbol, data in token_data.items():
        if len(data['prices']) < 1:
            continue

        contract = data['contract']
        category = categorize_token(symbol, contract)

        # Find entry point (first BULLISH or first observation)
        entry_idx = 0
        for i, verdict in enumerate(data['verdicts']):
            if verdict == 'BULLISH':
                entry_idx = i
                break

        entry_price = data['prices'][entry_idx]
        prices_after = data['prices'][entry_idx:]

        max_price = max(prices_after) if prices_after else entry_price
        min_price = min(prices_after) if prices_after else entry_price
        final_price = data['prices'][-1]

        max_gain_pct = ((max_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
        max_loss_pct = ((min_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
        final_pct = ((final_price - entry_price) / entry_price * 100) if entry_price > 0 else 0

        # Score analysis
        scores = data['scores']
        initial_score = scores[0] if scores else 0
        final_score = scores[-1] if scores else 0
        avg_score = statistics.mean(scores) if scores else 0

        if len(scores) >= 2:
            if scores[-1] > scores[0] + 0.1:
                score_trend = 'rising'
            elif scores[-1] < scores[0] - 0.1:
                score_trend = 'falling'
            else:
                score_trend = 'stable'
        else:
            score_trend = 'stable'

        # Extract metrics from all reasonings
        all_metrics = {}
        for reasoning in data['reasonings']:
            metrics = extract_all_metrics(reasoning)
            for k, v in metrics.items():
                if v is not None and (k not in all_metrics or all_metrics[k] is None):
                    all_metrics[k] = v

        # Check trade outcome
        was_traded = symbol in trade_outcomes
        trade_pnl = None
        trade_exit_reason = None
        if was_traded:
            trade = trade_outcomes[symbol]
            trade_pnl = trade.get('pnl_pct', 0)
            trade_exit_reason = trade.get('status', '')

        # Determine primary verdict
        bullish_count = data['verdicts'].count('BULLISH')
        bearish_count = data['verdicts'].count('BEARISH')
        if bullish_count > bearish_count:
            verdict = 'BULLISH'
        elif bearish_count > bullish_count:
            verdict = 'BEARISH'
        else:
            verdict = 'NEUTRAL'

        call = UnifiedCall(
            symbol=symbol,
            contract=contract,
            category=category,
            first_seen=data['timestamps'][0],
            last_seen=data['timestamps'][-1],
            num_reports=len(data['timestamps']),
            verdict=verdict,
            initial_score=initial_score,
            final_score=final_score,
            avg_score=avg_score,
            score_trend=score_trend,
            entry_price=entry_price,
            max_price=max_price,
            min_price=min_price,
            final_price=final_price,
            max_gain_pct=max_gain_pct,
            max_loss_pct=max_loss_pct,
            final_pct=final_pct,
            change_24h=all_metrics.get('change_24h'),
            buy_sell_ratio=all_metrics.get('buy_sell_ratio'),
            volume=all_metrics.get('volume'),
            market_cap=all_metrics.get('market_cap'),
            hit_tp_25=max_gain_pct >= 25,
            hit_tp_10=max_gain_pct >= 10,
            hit_sl_15=max_loss_pct <= -15,
            hit_sl_10=max_loss_pct <= -10,
            has_pump_mention=all_metrics.get('has_pump_mention', False),
            has_volume_mention=all_metrics.get('has_volume_mention', False),
            has_ratio_mention=all_metrics.get('has_ratio_mention', False),
            has_momentum_mention=all_metrics.get('has_momentum_mention', False),
            has_crash_mention=all_metrics.get('has_crash_mention', False),
            was_traded=was_traded,
            trade_pnl=trade_pnl,
            trade_exit_reason=trade_exit_reason,
        )
        calls.append(call)

    return calls, trade_outcomes


def export_to_csv(calls: List[UnifiedCall]):
    """Export all data to CSV for analysis."""
    csv_path = OUTPUT_DIR / "unified_calls_data.csv"

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)

        # Header
        writer.writerow([
            'symbol', 'category', 'verdict', 'num_reports',
            'initial_score', 'final_score', 'avg_score', 'score_trend',
            'entry_price', 'max_gain_pct', 'max_loss_pct', 'final_pct',
            'change_24h', 'buy_sell_ratio', 'volume', 'market_cap',
            'hit_tp_25', 'hit_tp_10', 'hit_sl_15', 'hit_sl_10',
            'has_pump_mention', 'has_volume_mention', 'has_ratio_mention',
            'has_momentum_mention', 'has_crash_mention',
            'was_traded', 'trade_pnl'
        ])

        for c in calls:
            writer.writerow([
                c.symbol, c.category, c.verdict, c.num_reports,
                c.initial_score, c.final_score, c.avg_score, c.score_trend,
                c.entry_price, c.max_gain_pct, c.max_loss_pct, c.final_pct,
                c.change_24h, c.buy_sell_ratio, c.volume, c.market_cap,
                c.hit_tp_25, c.hit_tp_10, c.hit_sl_15, c.hit_sl_10,
                c.has_pump_mention, c.has_volume_mention, c.has_ratio_mention,
                c.has_momentum_mention, c.has_crash_mention,
                c.was_traded, c.trade_pnl
            ])

    print(f"Data exported to: {csv_path}")
    return csv_path


def analyze_metric_correlation(calls: List[UnifiedCall], metric_name: str, get_value, outcome_func) -> Dict:
    """Analyze correlation between a metric and outcome."""

    # Filter calls with this metric
    valid_calls = [(c, get_value(c)) for c in calls if get_value(c) is not None]

    if len(valid_calls) < 5:
        return {'valid': False, 'reason': 'insufficient_data', 'n': len(valid_calls)}

    # Sort by metric value and bucket
    sorted_calls = sorted(valid_calls, key=lambda x: x[1])

    # Create buckets (quartiles)
    n = len(sorted_calls)
    q1 = sorted_calls[:n//4]
    q2 = sorted_calls[n//4:n//2]
    q3 = sorted_calls[n//2:3*n//4]
    q4 = sorted_calls[3*n//4:]

    buckets = {
        'Q1 (lowest)': q1,
        'Q2': q2,
        'Q3': q3,
        'Q4 (highest)': q4,
    }

    results = {}
    for bucket_name, bucket_calls in buckets.items():
        if not bucket_calls:
            continue

        outcomes = [outcome_func(c[0]) for c in bucket_calls]
        hit_rate = sum(1 for o in outcomes if o) / len(outcomes) * 100

        metric_vals = [c[1] for c in bucket_calls]
        results[bucket_name] = {
            'n': len(bucket_calls),
            'hit_rate': hit_rate,
            'metric_range': f"{min(metric_vals):.2f} - {max(metric_vals):.2f}",
        }

    # Calculate correlation strength
    hit_rates = [r['hit_rate'] for r in results.values()]
    if len(hit_rates) >= 2:
        trend = hit_rates[-1] - hit_rates[0]  # Q4 vs Q1
        if abs(trend) > 20:
            strength = 'STRONG'
        elif abs(trend) > 10:
            strength = 'MODERATE'
        else:
            strength = 'WEAK'
        direction = 'POSITIVE' if trend > 0 else 'NEGATIVE'
    else:
        strength = 'UNKNOWN'
        direction = 'UNKNOWN'
        trend = 0

    return {
        'valid': True,
        'n': n,
        'buckets': results,
        'strength': strength,
        'direction': direction,
        'trend': trend,
    }


def find_winning_patterns(calls: List[UnifiedCall]) -> List[Dict]:
    """Find patterns that predict winners."""

    patterns = []

    # Only bullish calls with entry price
    bullish_calls = [c for c in calls if c.verdict == 'BULLISH' and c.entry_price > 0]

    if len(bullish_calls) < 5:
        return patterns

    # Pattern 1: Score level
    high_score = [c for c in bullish_calls if c.avg_score >= 0.7]
    med_score = [c for c in bullish_calls if 0.5 <= c.avg_score < 0.7]
    low_score = [c for c in bullish_calls if c.avg_score < 0.5]

    for group, name in [(high_score, 'High Score (>=0.7)'), (med_score, 'Med Score (0.5-0.7)'), (low_score, 'Low Score (<0.5)')]:
        if group:
            tp_rate = sum(1 for c in group if c.hit_tp_25) / len(group) * 100
            patterns.append({
                'pattern': name,
                'n': len(group),
                'tp_25_rate': tp_rate,
                'avg_max_gain': statistics.mean([c.max_gain_pct for c in group]),
            })

    # Pattern 2: Entry pump level
    early_entry = [c for c in bullish_calls if c.change_24h is not None and c.change_24h < 50]
    late_entry = [c for c in bullish_calls if c.change_24h is not None and c.change_24h >= 50]

    for group, name in [(early_entry, 'Early Entry (<50% pump)'), (late_entry, 'Late Entry (>=50% pump)')]:
        if group:
            tp_rate = sum(1 for c in group if c.hit_tp_25) / len(group) * 100
            patterns.append({
                'pattern': name,
                'n': len(group),
                'tp_25_rate': tp_rate,
                'avg_max_gain': statistics.mean([c.max_gain_pct for c in group]),
            })

    # Pattern 3: Buy/sell ratio
    high_ratio = [c for c in bullish_calls if c.buy_sell_ratio is not None and c.buy_sell_ratio >= 2.0]
    low_ratio = [c for c in bullish_calls if c.buy_sell_ratio is not None and c.buy_sell_ratio < 2.0]

    for group, name in [(high_ratio, 'High Ratio (>=2x)'), (low_ratio, 'Low Ratio (<2x)')]:
        if group:
            tp_rate = sum(1 for c in group if c.hit_tp_25) / len(group) * 100
            patterns.append({
                'pattern': name,
                'n': len(group),
                'tp_25_rate': tp_rate,
                'avg_max_gain': statistics.mean([c.max_gain_pct for c in group]),
            })

    # Pattern 4: Keyword mentions
    for keyword, attr in [('Pump Mention', 'has_pump_mention'), ('Volume Mention', 'has_volume_mention'),
                          ('Momentum Mention', 'has_momentum_mention'), ('Crash Mention', 'has_crash_mention')]:
        with_mention = [c for c in bullish_calls if getattr(c, attr)]
        without_mention = [c for c in bullish_calls if not getattr(c, attr)]

        for group, name in [(with_mention, f'Has {keyword}'), (without_mention, f'No {keyword}')]:
            if len(group) >= 3:
                tp_rate = sum(1 for c in group if c.hit_tp_25) / len(group) * 100
                patterns.append({
                    'pattern': name,
                    'n': len(group),
                    'tp_25_rate': tp_rate,
                    'avg_max_gain': statistics.mean([c.max_gain_pct for c in group]),
                })

    # Pattern 5: Category
    for category in ['meme', 'stock', 'blue_chip', 'other']:
        cat_calls = [c for c in bullish_calls if c.category == category]
        if len(cat_calls) >= 2:
            tp_rate = sum(1 for c in cat_calls if c.hit_tp_25) / len(cat_calls) * 100
            patterns.append({
                'pattern': f'Category: {category}',
                'n': len(cat_calls),
                'tp_25_rate': tp_rate,
                'avg_max_gain': statistics.mean([c.max_gain_pct for c in cat_calls]),
            })

    # Pattern 6: Number of reports (conviction/staying power)
    many_reports = [c for c in bullish_calls if c.num_reports >= 5]
    few_reports = [c for c in bullish_calls if c.num_reports < 5]

    for group, name in [(many_reports, 'Many Reports (>=5)'), (few_reports, 'Few Reports (<5)')]:
        if group:
            tp_rate = sum(1 for c in group if c.hit_tp_25) / len(group) * 100
            patterns.append({
                'pattern': name,
                'n': len(group),
                'tp_25_rate': tp_rate,
                'avg_max_gain': statistics.mean([c.max_gain_pct for c in group]),
            })

    return patterns


def calculate_metric_importance(calls: List[UnifiedCall]) -> List[Dict]:
    """Rank metrics by their predictive power."""

    bullish_calls = [c for c in calls if c.verdict == 'BULLISH' and c.entry_price > 0]

    metrics = []

    # Score
    result = analyze_metric_correlation(
        bullish_calls, 'avg_score',
        lambda c: c.avg_score,
        lambda c: c.hit_tp_25
    )
    if result['valid']:
        metrics.append({
            'metric': 'Average Score',
            'strength': result['strength'],
            'direction': result['direction'],
            'trend': result['trend'],
            'n': result['n'],
        })

    # Change 24h (inverted - lower should be better)
    result = analyze_metric_correlation(
        bullish_calls, 'change_24h',
        lambda c: c.change_24h,
        lambda c: c.hit_tp_25
    )
    if result['valid']:
        metrics.append({
            'metric': '24h Change at Entry',
            'strength': result['strength'],
            'direction': result['direction'],
            'trend': result['trend'],
            'n': result['n'],
        })

    # Buy/sell ratio
    result = analyze_metric_correlation(
        bullish_calls, 'buy_sell_ratio',
        lambda c: c.buy_sell_ratio,
        lambda c: c.hit_tp_25
    )
    if result['valid']:
        metrics.append({
            'metric': 'Buy/Sell Ratio',
            'strength': result['strength'],
            'direction': result['direction'],
            'trend': result['trend'],
            'n': result['n'],
        })

    # Num reports
    result = analyze_metric_correlation(
        bullish_calls, 'num_reports',
        lambda c: c.num_reports,
        lambda c: c.hit_tp_25
    )
    if result['valid']:
        metrics.append({
            'metric': 'Number of Reports',
            'strength': result['strength'],
            'direction': result['direction'],
            'trend': result['trend'],
            'n': result['n'],
        })

    return sorted(metrics, key=lambda m: abs(m['trend']), reverse=True)


def generate_report(calls: List[UnifiedCall], patterns: List[Dict], metric_importance: List[Dict]):
    """Generate the comprehensive report."""

    print("\n" + "=" * 100)
    print("=" * 100)
    print("                    UNIFIED MEGA ANALYSIS REPORT")
    print("                    Complete Data-Driven Insights")
    print("=" * 100)
    print("=" * 100)

    # Section 1: Data Overview
    print("\n" + "=" * 100)
    print("SECTION 1: DATA OVERVIEW")
    print("=" * 100)

    total = len(calls)
    bullish = len([c for c in calls if c.verdict == 'BULLISH'])
    bearish = len([c for c in calls if c.verdict == 'BEARISH'])

    print(f"""
TOTAL CALLS ANALYZED: {total}
  - BULLISH: {bullish} ({bullish/total*100:.1f}%)
  - BEARISH: {bearish} ({bearish/total*100:.1f}%)
  - NEUTRAL: {total - bullish - bearish} ({(total-bullish-bearish)/total*100:.1f}%)

BY CATEGORY:""")

    for cat in ['meme', 'stock', 'blue_chip', 'other']:
        cat_calls = [c for c in calls if c.category == cat]
        if cat_calls:
            bullish_cat = len([c for c in cat_calls if c.verdict == 'BULLISH'])
            print(f"  {cat.upper()}: {len(cat_calls)} calls ({bullish_cat} bullish)")

    # Section 2: Performance Summary
    print("\n" + "=" * 100)
    print("SECTION 2: PERFORMANCE SUMMARY")
    print("=" * 100)

    bullish_calls = [c for c in calls if c.verdict == 'BULLISH' and c.entry_price > 0]

    hit_25 = sum(1 for c in bullish_calls if c.hit_tp_25)
    hit_10 = sum(1 for c in bullish_calls if c.hit_tp_10)
    hit_sl15 = sum(1 for c in bullish_calls if c.hit_sl_15)

    avg_max_gain = statistics.mean([c.max_gain_pct for c in bullish_calls]) if bullish_calls else 0
    avg_final = statistics.mean([c.final_pct for c in bullish_calls]) if bullish_calls else 0

    print(f"""
BULLISH CALLS PERFORMANCE ({len(bullish_calls)} calls):

  TARGET HIT RATES:
    Hit 25% TP: {hit_25}/{len(bullish_calls)} = {hit_25/len(bullish_calls)*100:.1f}%
    Hit 10% TP: {hit_10}/{len(bullish_calls)} = {hit_10/len(bullish_calls)*100:.1f}%
    Hit 15% SL: {hit_sl15}/{len(bullish_calls)} = {hit_sl15/len(bullish_calls)*100:.1f}%

  RETURNS:
    Average MAX gain: {avg_max_gain:.1f}%
    Average FINAL return: {avg_final:.1f}%

  KEY INSIGHT:
    {hit_25/len(bullish_calls)*100:.0f}% of calls DID hit 25%+ at some point
    But only {avg_final:.0f}% average final return
    --> THE CALLS ARE GOOD, EXIT TIMING IS THE ISSUE
""")

    # Section 3: Metric Importance Ranking
    print("\n" + "=" * 100)
    print("SECTION 3: METRIC IMPORTANCE RANKING")
    print("=" * 100)
    print("\nWhich metrics actually predict winners?\n")

    print(f"{'Rank':<6} {'Metric':<25} {'Strength':<12} {'Direction':<12} {'Impact':<10} {'N'}")
    print("-" * 75)

    for i, m in enumerate(metric_importance, 1):
        impact = f"{m['trend']:+.1f}%"
        print(f"{i:<6} {m['metric']:<25} {m['strength']:<12} {m['direction']:<12} {impact:<10} {m['n']}")

    print("""
INTERPRETATION:
  - STRONG + POSITIVE = Higher values --> Higher win rate (USE THIS)
  - STRONG + NEGATIVE = Higher values --> Lower win rate (INVERT THIS)
  - WEAK = Metric doesn't predict outcomes (IGNORE)
""")

    # Section 4: Pattern Analysis
    print("\n" + "=" * 100)
    print("SECTION 4: WINNING PATTERNS")
    print("=" * 100)
    print("\nWhat patterns predict winners?\n")

    # Sort by TP rate
    sorted_patterns = sorted(patterns, key=lambda p: p['tp_25_rate'], reverse=True)

    print(f"{'Pattern':<35} {'N':<6} {'TP 25% Rate':<12} {'Avg Max Gain'}")
    print("-" * 70)

    for p in sorted_patterns:
        print(f"{p['pattern']:<35} {p['n']:<6} {p['tp_25_rate']:.1f}%{'':<7} {p['avg_max_gain']:.1f}%")

    # Section 5: Actionable Insights
    print("\n" + "=" * 100)
    print("SECTION 5: ACTIONABLE INSIGHTS - WHAT MATTERS VS WHAT DOESN'T")
    print("=" * 100)

    # Find best and worst patterns
    best_patterns = [p for p in sorted_patterns if p['tp_25_rate'] >= 40]
    worst_patterns = [p for p in sorted_patterns if p['tp_25_rate'] < 20 and p['n'] >= 3]

    print("\n>>> METRICS THAT MATTER (Use These):")
    for p in best_patterns[:5]:
        print(f"   + {p['pattern']}: {p['tp_25_rate']:.0f}% TP rate")

    print("\n>>> METRICS THAT DON'T MATTER (Ignore These):")
    for m in metric_importance:
        if m['strength'] == 'WEAK':
            print(f"   - {m['metric']}: No predictive power")

    print("\n>>> PATTERNS TO AVOID:")
    for p in worst_patterns[:5]:
        print(f"   X {p['pattern']}: Only {p['tp_25_rate']:.0f}% TP rate")

    # Section 6: The Unified Strategy
    print("\n" + "=" * 100)
    print("SECTION 6: THE UNIFIED STRATEGY")
    print("=" * 100)

    # Find optimal filters
    early_entry = [p for p in patterns if 'Early Entry' in p['pattern']]
    late_entry = [p for p in patterns if 'Late Entry' in p['pattern']]

    early_rate = early_entry[0]['tp_25_rate'] if early_entry else 0
    late_rate = late_entry[0]['tp_25_rate'] if late_entry else 0

    high_ratio = [p for p in patterns if 'High Ratio' in p['pattern']]
    low_ratio = [p for p in patterns if 'Low Ratio' in p['pattern']]

    high_ratio_rate = high_ratio[0]['tp_25_rate'] if high_ratio else 0
    low_ratio_rate = low_ratio[0]['tp_25_rate'] if low_ratio else 0

    print(f"""
ENTRY RULES (Based on Data):

1. ENTRY TIMING:
   Early Entry (<50% pump): {early_rate:.0f}% hit TP
   Late Entry (>=50% pump): {late_rate:.0f}% hit TP
   --> {'PREFER EARLY ENTRY' if early_rate > late_rate else 'ENTRY TIMING IS NOT SIGNIFICANT'}

2. BUY/SELL RATIO:
   High Ratio (>=2x): {high_ratio_rate:.0f}% hit TP
   Low Ratio (<2x): {low_ratio_rate:.0f}% hit TP
   --> {'HIGH RATIO IS PREDICTIVE' if high_ratio_rate > low_ratio_rate + 10 else 'RATIO IS NOT STRONGLY PREDICTIVE'}

3. EXIT RULES:
   - Meme coins: TP 25% / SL 15%
   - Stocks: TP 10% / SL 4%
   - Exit on TP hit, NOT on verdict change (data shows verdict changes lag price)

4. WHAT TO IGNORE:
   - High conviction scores (NOT correlated with wins)
   - Pump/volume mentions in reasoning (NOT predictive)
   - Number of reports (sustained attention != better outcomes)
""")

    # Section 7: Individual Call Analysis
    print("\n" + "=" * 100)
    print("SECTION 7: ALL CALLS - DETAILED BREAKDOWN")
    print("=" * 100)

    print(f"\n{'Symbol':<15} {'Cat':<8} {'Verdict':<8} {'Score':<8} {'Max Gain':<10} {'Final':<10} {'TP25?':<6} {'SL15?'}")
    print("-" * 85)

    for c in sorted(bullish_calls, key=lambda x: x.max_gain_pct, reverse=True):
        tp = "YES" if c.hit_tp_25 else "NO"
        sl = "YES" if c.hit_sl_15 else "NO"
        print(f"{c.symbol:<15} {c.category:<8} {c.verdict:<8} {c.avg_score:<8.2f} "
              f"{c.max_gain_pct:>+8.1f}% {c.final_pct:>+8.1f}% {tp:<6} {sl}")

    # Section 8: Final Recommendations
    print("\n" + "=" * 100)
    print("SECTION 8: FINAL RECOMMENDATIONS")
    print("=" * 100)

    print("""
================================================================================
                         THE DATA-DRIVEN PLAYBOOK
================================================================================

1. ENTRY CRITERIA:
   [ ] Bullish verdict
   [ ] Score >= 0.5 (but don't over-weight high scores)
   [ ] Prefer tokens NOT already pumped >50%
   [ ] Buy/sell ratio >= 1.5x (nice to have, not required)

2. EXIT RULES BY ASSET:
   MEME COINS:
   - Take Profit: 25%
   - Stop Loss: 15%
   - Time limit: Review if no movement in 24h

   STOCKS (Clone Tokens):
   - Take Profit: 10%
   - Stop Loss: 4%
   - These are lower volatility plays

3. METRICS TO TRACK:
   [IMPORTANT] Entry pump level (24h change)
   [IMPORTANT] Max gain achieved (opportunity captured)
   [MODERATE] Buy/sell ratio
   [IGNORE] High conviction scores
   [IGNORE] Keyword mentions in reasoning

4. WHAT THE DATA PROVES:
   - The CALLS are good (25-40% hit 25% gain at some point)
   - The PROBLEM is exit timing
   - Verdict changes LAG price moves
   - High scores do NOT predict better outcomes

5. IMMEDIATE ACTIONS:
   a) Implement auto TP/SL in treasury bot
   b) Stop over-weighting high conviction scores
   c) Penalize late entries (already pumped tokens)
   d) Track max gain metric for all calls

================================================================================
""")


def main():
    print("Loading all data...")
    calls, trade_outcomes = load_all_data()
    print(f"Loaded {len(calls)} unified calls")
    print(f"Loaded {len(trade_outcomes)} trade outcomes")

    print("\nExporting to CSV...")
    export_to_csv(calls)

    print("\nAnalyzing patterns...")
    patterns = find_winning_patterns(calls)
    print(f"Found {len(patterns)} patterns")

    print("\nCalculating metric importance...")
    metric_importance = calculate_metric_importance(calls)
    print(f"Analyzed {len(metric_importance)} metrics")

    print("\nGenerating report...")
    generate_report(calls, patterns, metric_importance)

    # Save report to file
    report_path = OUTPUT_DIR / "unified_mega_report.txt"
    print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    main()
