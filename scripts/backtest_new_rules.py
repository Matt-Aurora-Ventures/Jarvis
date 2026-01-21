"""
Backtest New Sentiment Engine Rules vs Old Rules

Compares the OLD scoring system against the NEW data-driven rules
to validate the expected improvement in TP rate.

Created: 2026-01-21
"""

import pandas as pd
import json
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Tuple

# Paths
DATA_DIR = Path(__file__).parent.parent / "data" / "analysis"
CSV_FILE = DATA_DIR / "unified_calls_data.csv"


@dataclass
class BacktestResult:
    """Result of applying a rule set to historical data"""
    rule_name: str
    total_calls: int
    bullish_calls: int
    bullish_hit_tp25: int
    bullish_hit_tp10: int
    bullish_hit_sl15: int
    bullish_avg_max_gain: float
    bullish_avg_final: float
    rejected_calls: int  # Calls that would have been bullish under looser rules but weren't
    rejected_that_hit_tp: int  # How many rejected calls actually would have hit TP


def apply_old_rules(row: pd.Series) -> Tuple[bool, float, str]:
    """
    Apply OLD sentiment scoring rules.

    OLD Rules:
    - BULLISH if score > 0.55 and ratio >= 1.5 and change_24h <= 50
    - Chasing penalty: 50%+ = -0.20, 30%+ = -0.10

    Returns: (is_bullish, adjusted_score, rejection_reason)
    """
    score = row['initial_score']
    ratio = row['buy_sell_ratio'] if pd.notna(row['buy_sell_ratio']) else 0
    change_24h = row['change_24h'] if pd.notna(row['change_24h']) else 0

    # Apply old pump penalties
    chasing_pump = False
    if change_24h > 50:
        chasing_pump = True
        score -= 0.20
    elif change_24h > 30:
        chasing_pump = True
        score -= 0.10

    # Old BULLISH criteria
    is_bullish = score > 0.55 and ratio >= 1.5 and not chasing_pump

    reason = ""
    if not is_bullish:
        if score <= 0.55:
            reason = "score_too_low"
        elif ratio < 1.5:
            reason = "ratio_too_low"
        elif chasing_pump:
            reason = "chasing_pump"

    return is_bullish, score, reason


def apply_new_rules(row: pd.Series) -> Tuple[bool, float, str]:
    """
    Apply NEW data-driven sentiment scoring rules.

    NEW Rules:
    - BULLISH if score > 0.55 and ratio >= 2.0 and change_24h <= 40
    - Stricter chasing: 100%+ = -0.40, 50%+ = -0.30, 40%+ = -0.15, 30%+ = -0.08
    - High score (>=0.7) penalty
    - Keyword penalties for momentum/pump mentions

    Returns: (is_bullish, adjusted_score, rejection_reason)
    """
    score = row['initial_score']
    ratio = row['buy_sell_ratio'] if pd.notna(row['buy_sell_ratio']) else 0
    change_24h = row['change_24h'] if pd.notna(row['change_24h']) else 0
    has_momentum = row['has_momentum_mention'] if pd.notna(row['has_momentum_mention']) else False
    has_pump = row['has_pump_mention'] if pd.notna(row['has_pump_mention']) else False

    # Apply NEW stricter pump penalties
    chasing_pump = False
    if change_24h > 100:
        chasing_pump = True
        score -= 0.40
    elif change_24h > 50:
        chasing_pump = True
        score -= 0.30
    elif change_24h > 40:
        chasing_pump = True
        score -= 0.15
    elif change_24h > 30:
        score -= 0.08

    # NEW: High score penalty (overconfidence)
    if score >= 0.70:
        overconfidence_penalty = (score - 0.65) * 0.5
        score -= overconfidence_penalty

    # NEW: Keyword penalties
    if has_momentum:
        score -= 0.10
    if has_pump:
        score -= 0.08

    # NEW: Stricter BULLISH criteria (ratio >= 2.0)
    is_bullish = score > 0.55 and ratio >= 2.0 and not chasing_pump

    reason = ""
    if not is_bullish:
        if score <= 0.55:
            reason = "score_too_low"
        elif ratio < 2.0:
            reason = "ratio_below_2x"
        elif chasing_pump:
            reason = "chasing_pump"

    return is_bullish, score, reason


def run_backtest(df: pd.DataFrame, rule_func, rule_name: str) -> BacktestResult:
    """Run backtest with a specific rule set"""

    bullish_calls = []
    rejected_calls = []

    for idx, row in df.iterrows():
        is_bullish, adj_score, reason = rule_func(row)

        if is_bullish:
            bullish_calls.append(row)
        else:
            # Track rejections for analysis
            rejected_calls.append({
                'row': row,
                'reason': reason,
                'adjusted_score': adj_score
            })

    # Calculate metrics for bullish calls
    if bullish_calls:
        bullish_df = pd.DataFrame(bullish_calls)
        bullish_hit_tp25 = bullish_df['hit_tp_25'].sum()
        bullish_hit_tp10 = bullish_df['hit_tp_10'].sum()
        bullish_hit_sl15 = bullish_df['hit_sl_15'].sum()
        bullish_avg_max_gain = bullish_df['max_gain_pct'].mean()
        bullish_avg_final = bullish_df['final_pct'].mean()
    else:
        bullish_hit_tp25 = 0
        bullish_hit_tp10 = 0
        bullish_hit_sl15 = 0
        bullish_avg_max_gain = 0
        bullish_avg_final = 0

    # Count rejected calls that would have hit TP
    rejected_that_hit_tp = sum(
        1 for r in rejected_calls
        if r['row']['hit_tp_25'] == True
    )

    return BacktestResult(
        rule_name=rule_name,
        total_calls=len(df),
        bullish_calls=len(bullish_calls),
        bullish_hit_tp25=bullish_hit_tp25,
        bullish_hit_tp10=bullish_hit_tp10,
        bullish_hit_sl15=bullish_hit_sl15,
        bullish_avg_max_gain=bullish_avg_max_gain,
        bullish_avg_final=bullish_avg_final,
        rejected_calls=len(rejected_calls),
        rejected_that_hit_tp=rejected_that_hit_tp
    )


def analyze_specific_improvements(df: pd.DataFrame) -> Dict:
    """Analyze how each specific rule change would have helped"""

    analysis = {
        'ratio_upgrade': {'filtered_out': 0, 'filtered_out_lost': 0, 'filtered_out_won': 0},
        'pump_threshold': {'filtered_out': 0, 'filtered_out_lost': 0, 'filtered_out_won': 0},
        'high_score_penalty': {'affected': 0, 'would_have_lost': 0},
        'keyword_penalty': {'affected': 0, 'would_have_lost': 0},
    }

    for idx, row in df.iterrows():
        ratio = row['buy_sell_ratio'] if pd.notna(row['buy_sell_ratio']) else 0
        change_24h = row['change_24h'] if pd.notna(row['change_24h']) else 0
        score = row['initial_score']
        hit_tp = row['hit_tp_25']
        has_momentum = row['has_momentum_mention']
        has_pump = row['has_pump_mention']

        # Only analyze originally bullish calls
        if row['verdict'] != 'BULLISH':
            continue

        # Ratio upgrade: Would 1.5-2.0 ratio calls have been filtered?
        if 1.5 <= ratio < 2.0:
            analysis['ratio_upgrade']['filtered_out'] += 1
            if hit_tp:
                analysis['ratio_upgrade']['filtered_out_won'] += 1
            else:
                analysis['ratio_upgrade']['filtered_out_lost'] += 1

        # Pump threshold: Would 40-50% pump calls have been filtered?
        if 40 < change_24h <= 50:
            analysis['pump_threshold']['filtered_out'] += 1
            if hit_tp:
                analysis['pump_threshold']['filtered_out_won'] += 1
            else:
                analysis['pump_threshold']['filtered_out_lost'] += 1

        # High score penalty: How many had score >= 0.7?
        if score >= 0.7:
            analysis['high_score_penalty']['affected'] += 1
            if not hit_tp:
                analysis['high_score_penalty']['would_have_lost'] += 1

        # Keyword penalty: How many had hype keywords?
        if has_momentum or has_pump:
            analysis['keyword_penalty']['affected'] += 1
            if not hit_tp:
                analysis['keyword_penalty']['would_have_lost'] += 1

    return analysis


def print_comparison_report(old_result: BacktestResult, new_result: BacktestResult, improvements: Dict):
    """Print detailed comparison report"""

    print("=" * 80)
    print("SENTIMENT ENGINE BACKTEST: OLD RULES vs NEW RULES")
    print("=" * 80)
    print(f"\nData: {old_result.total_calls} total calls analyzed")
    print()

    # Side-by-side comparison
    print("-" * 80)
    print(f"{'METRIC':<35} {'OLD RULES':<20} {'NEW RULES':<20}")
    print("-" * 80)

    old_tp_rate = (old_result.bullish_hit_tp25 / old_result.bullish_calls * 100) if old_result.bullish_calls > 0 else 0
    new_tp_rate = (new_result.bullish_hit_tp25 / new_result.bullish_calls * 100) if new_result.bullish_calls > 0 else 0

    old_sl_rate = (old_result.bullish_hit_sl15 / old_result.bullish_calls * 100) if old_result.bullish_calls > 0 else 0
    new_sl_rate = (new_result.bullish_hit_sl15 / new_result.bullish_calls * 100) if new_result.bullish_calls > 0 else 0

    print(f"{'Bullish Calls Made':<35} {old_result.bullish_calls:<20} {new_result.bullish_calls:<20}")
    print(f"{'Hit 25% TP':<35} {old_result.bullish_hit_tp25:<20} {new_result.bullish_hit_tp25:<20}")
    print(f"{'TP Rate (25%)':<35} {old_tp_rate:.1f}%{'':<15} {new_tp_rate:.1f}%{'':<15}")
    print(f"{'Hit 15% SL':<35} {old_result.bullish_hit_sl15:<20} {new_result.bullish_hit_sl15:<20}")
    print(f"{'SL Rate':<35} {old_sl_rate:.1f}%{'':<15} {new_sl_rate:.1f}%{'':<15}")
    print(f"{'Avg Max Gain':<35} {old_result.bullish_avg_max_gain:.1f}%{'':<14} {new_result.bullish_avg_max_gain:.1f}%{'':<14}")
    print(f"{'Avg Final Return':<35} {old_result.bullish_avg_final:.1f}%{'':<14} {new_result.bullish_avg_final:.1f}%{'':<14}")
    print("-" * 80)

    # Calculate improvement
    tp_improvement = new_tp_rate - old_tp_rate
    calls_reduction = old_result.bullish_calls - new_result.bullish_calls

    print(f"\n{'IMPROVEMENT SUMMARY':^80}")
    print("-" * 80)
    print(f"TP Rate Change: {old_tp_rate:.1f}% → {new_tp_rate:.1f}% ({tp_improvement:+.1f}%)")
    print(f"Calls Reduction: {old_result.bullish_calls} → {new_result.bullish_calls} (-{calls_reduction} calls filtered)")
    print(f"Rejected calls that would have hit TP: {new_result.rejected_that_hit_tp}")

    # Rule-by-rule breakdown
    print(f"\n{'RULE-BY-RULE IMPACT':^80}")
    print("-" * 80)

    ratio = improvements['ratio_upgrade']
    print(f"\n1. RATIO UPGRADE (1.5x → 2.0x minimum):")
    print(f"   Filtered out: {ratio['filtered_out']} calls")
    print(f"   - Would have LOST: {ratio['filtered_out_lost']}")
    print(f"   - Would have WON: {ratio['filtered_out_won']}")
    net = ratio['filtered_out_lost'] - ratio['filtered_out_won']
    print(f"   Net benefit: {'+' if net >= 0 else ''}{net} avoided losses")

    pump = improvements['pump_threshold']
    print(f"\n2. PUMP THRESHOLD (50% → 40%):")
    print(f"   Filtered out: {pump['filtered_out']} calls")
    print(f"   - Would have LOST: {pump['filtered_out_lost']}")
    print(f"   - Would have WON: {pump['filtered_out_won']}")
    net = pump['filtered_out_lost'] - pump['filtered_out_won']
    print(f"   Net benefit: {'+' if net >= 0 else ''}{net} avoided losses")

    high_score = improvements['high_score_penalty']
    print(f"\n3. HIGH SCORE PENALTY (>=0.7):")
    print(f"   Affected: {high_score['affected']} calls")
    print(f"   - Would have LOST: {high_score['would_have_lost']}")
    print(f"   Penalty helps avoid: {high_score['would_have_lost']} losing calls")

    keyword = improvements['keyword_penalty']
    print(f"\n4. KEYWORD PENALTY (momentum/pump mentions):")
    print(f"   Affected: {keyword['affected']} calls")
    print(f"   - Would have LOST: {keyword['would_have_lost']}")
    print(f"   Penalty helps avoid: {keyword['would_have_lost']} losing calls")

    print("\n" + "=" * 80)
    print("CONCLUSION")
    print("=" * 80)

    if new_tp_rate > old_tp_rate:
        print(f"\n✓ NEW RULES VALIDATED: TP rate improved from {old_tp_rate:.1f}% to {new_tp_rate:.1f}%")
        print(f"✓ Trade quality over quantity: Fewer calls ({new_result.bullish_calls} vs {old_result.bullish_calls})")
        print(f"✓ Better selectivity means higher win rate")
    else:
        print(f"\n⚠ NEW RULES NEED ADJUSTMENT: TP rate did not improve")
        print(f"  Consider loosening some criteria")

    print("\n")


def main():
    """Main backtest execution"""

    print("\nLoading historical data...")
    df = pd.read_csv(CSV_FILE)
    print(f"Loaded {len(df)} calls")

    # Filter to only bullish-eligible calls (had positive initial scores and verdicts)
    # We want to see what the engine would have called bullish

    print("\nRunning backtest with OLD rules...")
    old_result = run_backtest(df, apply_old_rules, "OLD RULES (pre-2026-01-21)")

    print("Running backtest with NEW rules...")
    new_result = run_backtest(df, apply_new_rules, "NEW RULES (2026-01-21)")

    print("Analyzing specific improvements...")
    improvements = analyze_specific_improvements(df)

    # Print comparison report
    print_comparison_report(old_result, new_result, improvements)

    # Export detailed results
    results = {
        'old_rules': {
            'bullish_calls': old_result.bullish_calls,
            'tp_rate_25': (old_result.bullish_hit_tp25 / old_result.bullish_calls * 100) if old_result.bullish_calls > 0 else 0,
            'sl_rate_15': (old_result.bullish_hit_sl15 / old_result.bullish_calls * 100) if old_result.bullish_calls > 0 else 0,
            'avg_max_gain': old_result.bullish_avg_max_gain,
            'avg_final': old_result.bullish_avg_final
        },
        'new_rules': {
            'bullish_calls': new_result.bullish_calls,
            'tp_rate_25': (new_result.bullish_hit_tp25 / new_result.bullish_calls * 100) if new_result.bullish_calls > 0 else 0,
            'sl_rate_15': (new_result.bullish_hit_sl15 / new_result.bullish_calls * 100) if new_result.bullish_calls > 0 else 0,
            'avg_max_gain': new_result.bullish_avg_max_gain,
            'avg_final': new_result.bullish_avg_final
        },
        'improvements': improvements
    }

    results_file = DATA_DIR / "backtest_results.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nDetailed results saved to: {results_file}")


if __name__ == "__main__":
    main()
