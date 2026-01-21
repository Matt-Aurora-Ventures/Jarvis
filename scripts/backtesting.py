"""
Backtesting Framework for Sentiment Engine Strategies.

This framework allows testing different scoring strategies and entry rules
against historical prediction/outcome data.

CHANGELOG:
=========
2026-01-21: Integrated data-driven strategy (strategy_data_driven_2026)
- Added: strategy_data_driven_2026 implementing all new rules
- Added: CSV-based backtest for comprehensive analysis (run_csv_backtest)
- Added: Keyword detection for momentum/pump mentions
- Added: High score penalty logic
- Added: Detailed comparison report generation
- Integrated from: backtest_new_rules.py (now deprecated)

Usage:
    python scripts/backtesting.py              # Run JSON-based backtest
    python scripts/backtesting.py --csv        # Run CSV-based backtest (comprehensive)
    python scripts/backtesting.py --compare    # Run old vs new rules comparison
"""

import json
import re
import sys
import pandas as pd
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# Fix unicode output on Windows
sys.stdout.reconfigure(encoding='utf-8')

# Paths
ROOT = Path(__file__).resolve().parents[1]
PREDICTIONS_FILE = ROOT / "bots" / "buy_tracker" / "predictions_history.json"
TRADES_FILE = ROOT / "bots" / "treasury" / ".trade_history.json"
DATA_DIR = ROOT / "data" / "analysis"
CSV_FILE = DATA_DIR / "unified_calls_data.csv"


@dataclass
class Prediction:
    """A single prediction with all relevant data."""
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
    volume: Optional[float] = None
    market_cap: Optional[float] = None
    # New fields for data-driven analysis (2026-01-21)
    has_momentum_mention: bool = False
    has_pump_mention: bool = False
    report_count: int = 1


@dataclass
class TradeOutcome:
    """Actual trade outcome for validation."""
    symbol: str
    contract: str
    entry_time: str
    exit_time: str
    entry_price: float
    exit_price: float
    pnl_pct: float
    status: str


@dataclass
class BacktestResult:
    """Results from a backtest run."""
    strategy_name: str
    total_signals: int
    accepted_signals: int
    rejection_rate: float
    simulated_wins: int
    simulated_losses: int
    win_rate: float
    avg_win_pct: float
    avg_loss_pct: float
    expected_value: float
    max_drawdown: float
    signals_detail: List[Dict] = field(default_factory=list)


@dataclass
class CSVBacktestResult:
    """Result of applying a rule set to CSV historical data."""
    rule_name: str
    total_calls: int
    bullish_calls: int
    bullish_hit_tp25: int
    bullish_hit_tp10: int
    bullish_hit_sl15: int
    bullish_avg_max_gain: float
    bullish_avg_final: float
    rejected_calls: int
    rejected_that_hit_tp: int


def extract_metrics(reasoning: str) -> Dict[str, Any]:
    """Extract numeric metrics from reasoning text."""
    metrics = {}

    # Extract change_24h
    change_match = re.search(r'24h[:\s]*([+-]?\d+\.?\d*)%', reasoning)
    if change_match:
        try:
            metrics['change_24h'] = float(change_match.group(1))
        except ValueError:
            pass

    # Extract buy/sell ratio (multiple patterns)
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

    # Extract volume
    vol_match = re.search(r'vol(?:ume)?[:\s]*\$?([\d,]+\.?\d*)[kKmM]?', reasoning, re.IGNORECASE)
    if vol_match:
        vol_str = vol_match.group(1).replace(',', '')
        if vol_str:
            try:
                metrics['volume'] = float(vol_str)
            except ValueError:
                pass

    # Extract market cap
    mc_match = re.search(r'(?:mc|market\s*cap)[:\s]*\$?([\d,]+\.?\d*)[kKmM]?', reasoning, re.IGNORECASE)
    if mc_match:
        mc_str = mc_match.group(1).replace(',', '')
        if mc_str:
            try:
                metrics['market_cap'] = float(mc_str)
            except ValueError:
                pass

    # NEW: Detect hype keywords (2026-01-21)
    reasoning_lower = reasoning.lower()
    metrics['has_momentum_mention'] = 'momentum' in reasoning_lower
    metrics['has_pump_mention'] = 'pump' in reasoning_lower and 'pump.fun' not in reasoning_lower

    return metrics


def load_predictions() -> List[Prediction]:
    """Load all predictions from history."""
    if not PREDICTIONS_FILE.exists():
        return []

    with open(PREDICTIONS_FILE, 'r', encoding='utf-8') as f:
        history = json.load(f)

    predictions = []
    symbol_counts = {}  # Track how many times each symbol appears

    for entry in history:
        timestamp = entry.get('timestamp', '')
        market_regime = entry.get('market_regime', 'UNKNOWN')

        for symbol, data in entry.get('token_predictions', {}).items():
            # Track symbol frequency
            symbol_counts[symbol] = symbol_counts.get(symbol, 0) + 1

            metrics = extract_metrics(data.get('reasoning', ''))

            pred = Prediction(
                timestamp=timestamp,
                symbol=symbol,
                contract=data.get('contract', ''),
                verdict=data.get('verdict', 'NEUTRAL'),
                score=data.get('score', 0),
                price=data.get('price_at_prediction', 0),
                reasoning=data.get('reasoning', ''),
                market_regime=market_regime,
                change_24h=metrics.get('change_24h'),
                buy_sell_ratio=metrics.get('buy_sell_ratio'),
                volume=metrics.get('volume'),
                market_cap=metrics.get('market_cap'),
                has_momentum_mention=metrics.get('has_momentum_mention', False),
                has_pump_mention=metrics.get('has_pump_mention', False),
            )
            predictions.append(pred)

    # Update report counts
    for pred in predictions:
        pred.report_count = symbol_counts.get(pred.symbol, 1)

    return predictions


def load_trade_outcomes() -> Dict[str, TradeOutcome]:
    """Load actual trade outcomes keyed by symbol."""
    if not TRADES_FILE.exists():
        return {}

    with open(TRADES_FILE, 'r', encoding='utf-8') as f:
        trades = json.load(f)

    outcomes = {}
    for trade in trades:
        symbol = trade.get('token_symbol', '')
        if not symbol or symbol == 'SOL':  # Skip test SOL trades
            continue

        outcomes[symbol] = TradeOutcome(
            symbol=symbol,
            contract=trade.get('token_mint', ''),
            entry_time=trade.get('opened_at', ''),
            exit_time=trade.get('closed_at', ''),
            entry_price=trade.get('entry_price', 0),
            exit_price=trade.get('exit_price', 0),
            pnl_pct=trade.get('pnl_pct', 0),
            status=trade.get('status', ''),
        )

    return outcomes


# ============================================================================
# STRATEGY FILTERS
# ============================================================================

def strategy_current(pred: Prediction) -> Tuple[bool, str]:
    """
    Current strategy: Accept all bullish signals with score > 0.5.
    This is essentially what we've been doing.
    """
    if pred.verdict != 'BULLISH':
        return False, "Not bullish"
    if pred.score < 0.5:
        return False, f"Score too low: {pred.score}"
    return True, "Accepted"


def strategy_old_rules(pred: Prediction) -> Tuple[bool, str]:
    """
    OLD Rules (before 2026-01-21):
    - BULLISH if score > 0.55 and ratio >= 1.5 and NOT chasing (>50% pump)
    """
    if pred.verdict != 'BULLISH':
        return False, "Not bullish"

    score = pred.score
    ratio = pred.buy_sell_ratio if pred.buy_sell_ratio is not None else 0
    change_24h = pred.change_24h if pred.change_24h is not None else 0

    # Old chasing threshold was 50%
    chasing_pump = change_24h > 50

    # Old BULLISH criteria
    if score > 0.55 and ratio >= 1.5 and not chasing_pump:
        return True, "Accepted (old rules)"

    reasons = []
    if score <= 0.55:
        reasons.append("score_too_low")
    if ratio < 1.5:
        reasons.append("ratio_below_1.5x")
    if chasing_pump:
        reasons.append("chasing_pump_50pct")

    return False, "+".join(reasons) if reasons else "unknown"


def strategy_data_driven_2026(pred: Prediction) -> Tuple[bool, str]:
    """
    NEW Data-Driven Rules (2026-01-21):
    Based on backtested analysis of 56 calls:
    - Early Entry (<50% pump) = 67% TP rate
    - High Ratio (>=2x) = 67% TP rate
    - High Score (>=0.7) = 0% TP rate (penalize!)
    - Momentum mentions = 14% TP rate (penalize!)
    - Pump mentions = 20% TP rate (penalize!)
    - Multi-sighting (>=5 reports) = 36% TP rate (bonus)

    Returns: (would_approve, rejection_reason)
    """
    if pred.verdict != 'BULLISH':
        return False, "Not bullish"

    score = pred.score
    ratio = pred.buy_sell_ratio if pred.buy_sell_ratio is not None else 0
    change_24h = pred.change_24h if pred.change_24h is not None else 0
    has_momentum = pred.has_momentum_mention
    has_pump = pred.has_pump_mention
    report_count = pred.report_count

    # New chasing threshold is 40%
    chasing_pump = change_24h > 40

    # Apply score adjustments
    adjusted_score = score

    # High score penalty (data shows >=0.7 = 0% TP rate)
    if adjusted_score >= 0.70:
        overconfidence_penalty = (adjusted_score - 0.65) * 0.5
        adjusted_score -= overconfidence_penalty

    # Keyword penalties (data shows these correlate with worse outcomes)
    if has_momentum:
        adjusted_score -= 0.10
    if has_pump:
        adjusted_score -= 0.08

    # Multi-sighting bonus (data shows >=5 reports = 36% TP vs <5 = 0%)
    if report_count >= 5:
        adjusted_score += 0.08
    elif report_count < 3:
        adjusted_score -= 0.05

    # NEW BULLISH criteria: adjusted score > 0.55, ratio >= 2.0, not chasing
    if adjusted_score > 0.55 and ratio >= 2.0 and not chasing_pump:
        return True, f"Accepted (score={adjusted_score:.2f}, ratio={ratio:.1f}x, pump={change_24h:.0f}%)"

    # Build rejection reason
    reasons = []
    if adjusted_score <= 0.55:
        reasons.append(f"score_penalized({adjusted_score:.2f})")
    if ratio < 2.0:
        reasons.append(f"ratio_below_2x({ratio:.1f})")
    if chasing_pump:
        reasons.append(f"chasing_pump_40pct({change_24h:.0f}%)")

    return False, "+".join(reasons) if reasons else "unknown"


def strategy_data_driven_relaxed(pred: Prediction) -> Tuple[bool, str]:
    """
    RELAXED Data-Driven Rules - Less strict to catch more winners.
    - Ratio >= 1.5x (instead of 2.0x)
    - Pump threshold at 50% (instead of 40%)
    - Still applies score penalties
    """
    if pred.verdict != 'BULLISH':
        return False, "Not bullish"

    score = pred.score
    ratio = pred.buy_sell_ratio if pred.buy_sell_ratio is not None else 0
    change_24h = pred.change_24h if pred.change_24h is not None else 0
    has_momentum = pred.has_momentum_mention
    has_pump = pred.has_pump_mention

    chasing_pump = change_24h > 50  # Relaxed from 40%
    adjusted_score = score

    if adjusted_score >= 0.70:
        overconfidence_penalty = (adjusted_score - 0.65) * 0.5
        adjusted_score -= overconfidence_penalty

    if has_momentum:
        adjusted_score -= 0.10
    if has_pump:
        adjusted_score -= 0.08

    if adjusted_score > 0.55 and ratio >= 1.5 and not chasing_pump:  # Relaxed ratio
        return True, f"Accepted (relaxed: score={adjusted_score:.2f}, ratio={ratio:.1f}x)"

    reasons = []
    if adjusted_score <= 0.55:
        reasons.append("score_penalized")
    if ratio < 1.5:
        reasons.append("ratio_below_1.5x")
    if chasing_pump:
        reasons.append("chasing_pump_50pct")

    return False, "+".join(reasons) if reasons else "unknown"


def strategy_data_driven_balanced(pred: Prediction) -> Tuple[bool, str]:
    """
    BALANCED Data-Driven Rules - Middle ground.
    - Ratio >= 1.8x (between 1.5 and 2.0)
    - Pump threshold at 45% (between 40 and 50)
    - Still applies score penalties
    """
    if pred.verdict != 'BULLISH':
        return False, "Not bullish"

    score = pred.score
    ratio = pred.buy_sell_ratio if pred.buy_sell_ratio is not None else 0
    change_24h = pred.change_24h if pred.change_24h is not None else 0
    has_momentum = pred.has_momentum_mention
    has_pump = pred.has_pump_mention

    chasing_pump = change_24h > 45
    adjusted_score = score

    if adjusted_score >= 0.70:
        overconfidence_penalty = (adjusted_score - 0.65) * 0.5
        adjusted_score -= overconfidence_penalty

    if has_momentum:
        adjusted_score -= 0.10
    if has_pump:
        adjusted_score -= 0.08

    if adjusted_score > 0.55 and ratio >= 1.8 and not chasing_pump:
        return True, f"Accepted (balanced: score={adjusted_score:.2f}, ratio={ratio:.1f}x)"

    reasons = []
    if adjusted_score <= 0.55:
        reasons.append("score_penalized")
    if ratio < 1.8:
        reasons.append("ratio_below_1.8x")
    if chasing_pump:
        reasons.append("chasing_pump_45pct")

    return False, "+".join(reasons) if reasons else "unknown"


def strategy_pump_filter_only(pred: Prediction) -> Tuple[bool, str]:
    """
    PUMP FILTER ONLY - Test impact of pump threshold alone.
    Only filters based on pump level, no ratio requirement.
    """
    if pred.verdict != 'BULLISH':
        return False, "Not bullish"
    if pred.score < 0.5:
        return False, f"Score too low: {pred.score}"

    change_24h = pred.change_24h if pred.change_24h is not None else 0

    if change_24h > 40:
        return False, f"Chasing pump: {change_24h:.0f}%"

    return True, f"Accepted - early entry ({change_24h:.0f}% pump)"


def strategy_ratio_filter_only(pred: Prediction) -> Tuple[bool, str]:
    """
    RATIO FILTER ONLY - Test impact of ratio requirement alone.
    Only filters based on ratio, no pump threshold.
    """
    if pred.verdict != 'BULLISH':
        return False, "Not bullish"
    if pred.score < 0.5:
        return False, f"Score too low: {pred.score}"

    ratio = pred.buy_sell_ratio if pred.buy_sell_ratio is not None else 0

    if ratio < 2.0:
        return False, f"Weak ratio: {ratio:.1f}x"

    return True, f"Accepted - strong ratio ({ratio:.1f}x)"


def strategy_score_penalty_only(pred: Prediction) -> Tuple[bool, str]:
    """
    SCORE PENALTY ONLY - Test impact of score adjustments alone.
    No ratio or pump filters, just score penalties.
    """
    if pred.verdict != 'BULLISH':
        return False, "Not bullish"

    score = pred.score
    has_momentum = pred.has_momentum_mention
    has_pump = pred.has_pump_mention
    adjusted_score = score

    if adjusted_score >= 0.70:
        overconfidence_penalty = (adjusted_score - 0.65) * 0.5
        adjusted_score -= overconfidence_penalty

    if has_momentum:
        adjusted_score -= 0.10
    if has_pump:
        adjusted_score -= 0.08

    if adjusted_score <= 0.50:
        return False, f"Score too low after penalties: {adjusted_score:.2f}"

    return True, f"Accepted (adjusted score: {adjusted_score:.2f})"


def strategy_no_pump_chasing(pred: Prediction) -> Tuple[bool, str]:
    """
    Strategy: Reject signals on tokens already pumped >50%.
    """
    if pred.verdict != 'BULLISH':
        return False, "Not bullish"
    if pred.score < 0.5:
        return False, f"Score too low: {pred.score}"
    if pred.change_24h is not None and pred.change_24h > 50:
        return False, f"Already pumped {pred.change_24h}%"
    return True, "Accepted - early entry"


def strategy_early_entry_only(pred: Prediction) -> Tuple[bool, str]:
    """
    Strategy: Only accept if token is up <20% (very early entry).
    """
    if pred.verdict != 'BULLISH':
        return False, "Not bullish"
    if pred.score < 0.5:
        return False, f"Score too low: {pred.score}"
    if pred.change_24h is None:
        return False, "No 24h change data"
    if pred.change_24h > 20:
        return False, f"Too late: already {pred.change_24h}%"
    return True, "Accepted - early entry <20%"


def strategy_high_ratio_early(pred: Prediction) -> Tuple[bool, str]:
    """
    Strategy: Require both high ratio (>2x) AND early entry (<30% pump).
    """
    if pred.verdict != 'BULLISH':
        return False, "Not bullish"
    if pred.score < 0.5:
        return False, f"Score too low: {pred.score}"
    if pred.change_24h is None or pred.buy_sell_ratio is None:
        return False, "Missing metrics"
    if pred.change_24h > 30:
        return False, f"Too late: {pred.change_24h}%"
    if pred.buy_sell_ratio < 2.0:
        return False, f"Weak ratio: {pred.buy_sell_ratio}x"
    return True, f"Accepted - ratio {pred.buy_sell_ratio}x, pump {pred.change_24h}%"


def strategy_inverted_pump_scoring(pred: Prediction) -> Tuple[bool, str]:
    """
    Strategy: Invert the score based on existing pump.
    High pumps REDUCE score instead of increasing it.
    """
    if pred.verdict != 'BULLISH':
        return False, "Not bullish"

    # Start with base score
    adjusted_score = pred.score

    # INVERT: Penalize existing pumps instead of rewarding them
    if pred.change_24h is not None:
        if pred.change_24h > 100:
            adjusted_score -= 0.3  # Heavy penalty for >100% pump
        elif pred.change_24h > 50:
            adjusted_score -= 0.2  # Moderate penalty
        elif pred.change_24h > 20:
            adjusted_score -= 0.1  # Small penalty
        elif pred.change_24h < 10:
            adjusted_score += 0.1  # Bonus for early entry

    if adjusted_score < 0.5:
        return False, f"Adjusted score too low: {adjusted_score:.2f}"

    return True, f"Accepted with adjusted score: {adjusted_score:.2f}"


def strategy_conservative(pred: Prediction) -> Tuple[bool, str]:
    """
    Very conservative strategy:
    - High score (>0.7)
    - Early entry (<30% pump)
    - Good ratio (>1.5x)

    NOTE: This strategy FAILS in backtesting because high scores
    correlate with WORSE outcomes (0% TP rate for score >= 0.7)
    """
    if pred.verdict != 'BULLISH':
        return False, "Not bullish"
    if pred.score < 0.7:
        return False, f"Score below 0.7: {pred.score}"

    # Require metrics
    if pred.change_24h is None or pred.buy_sell_ratio is None:
        return False, "Missing metrics"

    if pred.change_24h > 30:
        return False, f"Too pumped: {pred.change_24h}%"
    if pred.buy_sell_ratio < 1.5:
        return False, f"Weak ratio: {pred.buy_sell_ratio}x"

    return True, "Accepted - conservative criteria met"


# ============================================================================
# CSV-BASED BACKTESTING (2026-01-21)
# ============================================================================

def would_old_rules_approve_csv(row: pd.Series) -> Tuple[bool, str]:
    """
    Check if OLD rules would have approved this as BULLISH.
    For CSV data analysis.
    """
    score = row['initial_score']
    ratio = row['buy_sell_ratio'] if pd.notna(row['buy_sell_ratio']) else 0
    change_24h = row['change_24h'] if pd.notna(row['change_24h']) else 0

    chasing_pump = change_24h > 50
    would_approve = score > 0.55 and ratio >= 1.5 and not chasing_pump

    reason = ""
    if not would_approve:
        if score <= 0.55:
            reason = "score_too_low"
        elif ratio < 1.5:
            reason = "ratio_below_1.5x"
        elif chasing_pump:
            reason = "chasing_pump_50pct"

    return would_approve, reason


def would_new_rules_approve_csv(row: pd.Series) -> Tuple[bool, str]:
    """
    Check if NEW rules would approve this as BULLISH.
    For CSV data analysis.
    """
    score = row['initial_score']
    ratio = row['buy_sell_ratio'] if pd.notna(row['buy_sell_ratio']) else 0
    change_24h = row['change_24h'] if pd.notna(row['change_24h']) else 0
    has_momentum = row['has_momentum_mention'] if pd.notna(row['has_momentum_mention']) else False
    has_pump = row['has_pump_mention'] if pd.notna(row['has_pump_mention']) else False

    chasing_pump = change_24h > 40
    adjusted_score = score

    # High score penalty
    if adjusted_score >= 0.70:
        overconfidence_penalty = (adjusted_score - 0.65) * 0.5
        adjusted_score -= overconfidence_penalty

    # Keyword penalties
    if has_momentum:
        adjusted_score -= 0.10
    if has_pump:
        adjusted_score -= 0.08

    would_approve = adjusted_score > 0.55 and ratio >= 2.0 and not chasing_pump

    reason = ""
    if not would_approve:
        reasons = []
        if adjusted_score <= 0.55:
            reasons.append("score_penalized")
        if ratio < 2.0:
            reasons.append("ratio_below_2x")
        if chasing_pump:
            reasons.append("chasing_pump_40pct")
        reason = "+".join(reasons) if reasons else "unknown"

    return would_approve, reason


def run_csv_backtest() -> Dict:
    """
    Run backtest using CSV data (unified_calls_data.csv).
    Analyzes what WAS actually called bullish, then sees how new rules would filter them.
    """
    if not CSV_FILE.exists():
        print(f"CSV file not found: {CSV_FILE}")
        return {}

    df = pd.read_csv(CSV_FILE)
    actual_bullish = df[df['verdict'] == 'BULLISH'].copy()

    results = {
        'actual_bullish_count': len(actual_bullish),
        'actual_bullish_hit_tp25': actual_bullish['hit_tp_25'].sum() if 'hit_tp_25' in actual_bullish.columns else 0,
        'actual_bullish_hit_sl15': actual_bullish['hit_sl_15'].sum() if 'hit_sl_15' in actual_bullish.columns else 0,
        'actual_tp_rate': 0,
        'old_rules_would_approve': [],
        'new_rules_would_approve': [],
        'new_rules_would_reject': [],
        'filtered_out_details': []
    }

    if len(actual_bullish) > 0 and 'hit_tp_25' in actual_bullish.columns:
        results['actual_tp_rate'] = (actual_bullish['hit_tp_25'].sum() / len(actual_bullish)) * 100

    for idx, row in actual_bullish.iterrows():
        symbol = row['symbol']
        hit_tp = row['hit_tp_25'] if 'hit_tp_25' in row else False
        max_gain = row['max_gain_pct'] if 'max_gain_pct' in row else None
        final_pct = row['final_pct'] if 'final_pct' in row else None

        old_approve, old_reason = would_old_rules_approve_csv(row)
        new_approve, new_reason = would_new_rules_approve_csv(row)

        if old_approve:
            results['old_rules_would_approve'].append(symbol)

        if new_approve:
            results['new_rules_would_approve'].append(symbol)
        else:
            results['new_rules_would_reject'].append(symbol)
            results['filtered_out_details'].append({
                'symbol': symbol,
                'reason': new_reason,
                'hit_tp': bool(hit_tp),
                'max_gain': max_gain,
                'final_pct': final_pct,
                'ratio': row['buy_sell_ratio'] if 'buy_sell_ratio' in row else None,
                'change_24h': row['change_24h'] if 'change_24h' in row else None,
                'score': row['initial_score'] if 'initial_score' in row else None
            })

    return results


def analyze_rule_improvements(df: pd.DataFrame) -> Dict:
    """Analyze how each specific rule change would have helped."""
    analysis = {
        'ratio_upgrade': {'filtered_out': 0, 'filtered_out_lost': 0, 'filtered_out_won': 0},
        'pump_threshold': {'filtered_out': 0, 'filtered_out_lost': 0, 'filtered_out_won': 0},
        'high_score_penalty': {'affected': 0, 'would_have_lost': 0},
        'keyword_penalty': {'affected': 0, 'would_have_lost': 0},
    }

    for idx, row in df.iterrows():
        if row['verdict'] != 'BULLISH':
            continue

        ratio = row['buy_sell_ratio'] if pd.notna(row['buy_sell_ratio']) else 0
        change_24h = row['change_24h'] if pd.notna(row['change_24h']) else 0
        score = row['initial_score'] if 'initial_score' in row else 0
        hit_tp = row['hit_tp_25'] if 'hit_tp_25' in row else False
        has_momentum = row['has_momentum_mention'] if 'has_momentum_mention' in row else False
        has_pump = row['has_pump_mention'] if 'has_pump_mention' in row else False

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


def print_csv_backtest_report(backtest: Dict, improvements: Dict, df: pd.DataFrame):
    """Print detailed CSV backtest report comparing old vs new rules."""

    print("=" * 80)
    print("SENTIMENT ENGINE BACKTEST: OLD RULES vs NEW RULES (2026-01-21)")
    print("=" * 80)
    print(f"\nData: {len(df)} total calls analyzed")
    print(f"Original BULLISH calls: {backtest['actual_bullish_count']}")
    print()

    actual_tp_rate = backtest['actual_tp_rate']
    new_approved = len(backtest['new_rules_would_approve'])
    filtered_out = len(backtest['filtered_out_details'])

    # Calculate new TP rate
    new_approved_hit_tp = 0
    actual_bullish = df[df['verdict'] == 'BULLISH']
    for idx, row in actual_bullish.iterrows():
        if row['symbol'] in backtest['new_rules_would_approve']:
            if 'hit_tp_25' in row and row['hit_tp_25']:
                new_approved_hit_tp += 1

    new_tp_rate = (new_approved_hit_tp / new_approved * 100) if new_approved > 0 else 0

    # Side-by-side comparison
    print("-" * 80)
    print(f"{'METRIC':<40} {'OLD RULES':<18} {'NEW RULES':<18}")
    print("-" * 80)
    print(f"{'Bullish Calls':<40} {backtest['actual_bullish_count']:<18} {new_approved:<18}")
    print(f"{'Hit 25% TP':<40} {backtest['actual_bullish_hit_tp25']:<18} {new_approved_hit_tp:<18}")
    print(f"{'TP Rate':<40} {actual_tp_rate:.1f}%{'':<13} {new_tp_rate:.1f}%{'':<13}")
    print(f"{'Filtered Out':<40} {'0':<18} {filtered_out:<18}")
    print("-" * 80)

    # Improvement summary
    tp_improvement = new_tp_rate - actual_tp_rate
    print(f"\n{'IMPROVEMENT SUMMARY':^80}")
    print("-" * 80)
    print(f"TP Rate: {actual_tp_rate:.1f}% --> {new_tp_rate:.1f}% ({tp_improvement:+.1f}%)")
    print(f"Calls: {backtest['actual_bullish_count']} --> {new_approved} (-{filtered_out} filtered)")

    # Filtered out details
    print(f"\n{'FILTERED OUT DETAILS':^80}")
    print("-" * 80)
    print(f"{'Symbol':<15} {'Reason':<30} {'Hit TP?':<10} {'Max Gain':<12} {'Final':<12}")
    print("-" * 80)

    filtered_won = 0
    filtered_lost = 0
    for d in backtest['filtered_out_details']:
        hit_str = "YES" if d['hit_tp'] else "NO"
        max_gain = f"{d['max_gain']:.1f}%" if d['max_gain'] is not None else "N/A"
        final = f"{d['final_pct']:.1f}%" if d['final_pct'] is not None else "N/A"
        print(f"{d['symbol']:<15} {d['reason']:<30} {hit_str:<10} {max_gain:<12} {final:<12}")
        if d['hit_tp']:
            filtered_won += 1
        else:
            filtered_lost += 1

    print("-" * 80)
    print(f"Filtered that would have WON: {filtered_won}")
    print(f"Filtered that would have LOST: {filtered_lost}")
    net_benefit = filtered_lost - filtered_won
    print(f"Net benefit: {'+' if net_benefit >= 0 else ''}{net_benefit} avoided losses")

    # Rule-by-rule breakdown
    print(f"\n{'RULE-BY-RULE IMPACT':^80}")
    print("-" * 80)

    ratio = improvements['ratio_upgrade']
    print(f"\n1. RATIO UPGRADE (1.5x --> 2.0x minimum):")
    print(f"   Would filter: {ratio['filtered_out']} calls")
    print(f"   - Would have LOST: {ratio['filtered_out_lost']}")
    print(f"   - Would have WON: {ratio['filtered_out_won']}")
    net = ratio['filtered_out_lost'] - ratio['filtered_out_won']
    print(f"   Net benefit: {'+' if net >= 0 else ''}{net} avoided losses")

    pump = improvements['pump_threshold']
    print(f"\n2. PUMP THRESHOLD (50% --> 40%):")
    print(f"   Would filter: {pump['filtered_out']} calls")
    print(f"   - Would have LOST: {pump['filtered_out_lost']}")
    print(f"   - Would have WON: {pump['filtered_out_won']}")
    net = pump['filtered_out_lost'] - pump['filtered_out_won']
    print(f"   Net benefit: {'+' if net >= 0 else ''}{net} avoided losses")

    high_score = improvements['high_score_penalty']
    print(f"\n3. HIGH SCORE PENALTY (>=0.7):")
    print(f"   Affected: {high_score['affected']} calls")
    print(f"   - Would have LOST: {high_score['would_have_lost']}")

    keyword = improvements['keyword_penalty']
    print(f"\n4. KEYWORD PENALTY (momentum/pump mentions):")
    print(f"   Affected: {keyword['affected']} calls")
    print(f"   - Would have LOST: {keyword['would_have_lost']}")

    # Conclusion
    print("\n" + "=" * 80)
    print("CONCLUSION")
    print("=" * 80)

    if new_tp_rate > actual_tp_rate:
        print(f"\n[OK] NEW RULES VALIDATED:")
        print(f"    TP rate improved from {actual_tp_rate:.1f}% to {new_tp_rate:.1f}%")
        print(f"    Trade quality over quantity: {new_approved} calls vs {backtest['actual_bullish_count']}")
        print(f"    Net benefit: Avoided {net_benefit} losing trades")
    elif new_tp_rate == actual_tp_rate:
        print(f"\n[--] NEW RULES NEUTRAL: TP rate unchanged at {new_tp_rate:.1f}%")
    else:
        print(f"\n[!!] WARNING: TP rate decreased from {actual_tp_rate:.1f}% to {new_tp_rate:.1f}%")

    print("\n")


# ============================================================================
# THRESHOLD OPTIMIZER (2026-01-21)
# ============================================================================

def optimize_thresholds_csv(df: pd.DataFrame) -> Dict:
    """
    Test multiple threshold combinations to find the optimal strategy.
    Returns the best configuration with metrics.
    """
    bullish_df = df[df['verdict'] == 'BULLISH'].copy()

    if len(bullish_df) == 0:
        return {'error': 'No bullish calls to analyze'}

    # Threshold ranges to test
    ratio_thresholds = [1.5, 1.6, 1.7, 1.8, 1.9, 2.0, 2.5]
    pump_thresholds = [30, 35, 40, 45, 50, 60, 70, 100]

    results = []

    for ratio_min in ratio_thresholds:
        for pump_max in pump_thresholds:
            # Test this combination
            approved = []
            for idx, row in bullish_df.iterrows():
                score = row['initial_score'] if 'initial_score' in row else 0
                ratio = row['buy_sell_ratio'] if pd.notna(row['buy_sell_ratio']) else 0
                change_24h = row['change_24h'] if pd.notna(row['change_24h']) else 0
                has_momentum = row['has_momentum_mention'] if 'has_momentum_mention' in row else False
                has_pump = row['has_pump_mention'] if 'has_pump_mention' in row else False
                hit_tp = row['hit_tp_25'] if 'hit_tp_25' in row else False
                max_gain = row['max_gain_pct'] if 'max_gain_pct' in row else 0

                # Apply score penalties (same as data_driven_2026)
                adjusted_score = score
                if adjusted_score >= 0.70:
                    overconfidence_penalty = (adjusted_score - 0.65) * 0.5
                    adjusted_score -= overconfidence_penalty
                if has_momentum:
                    adjusted_score -= 0.10
                if has_pump:
                    adjusted_score -= 0.08

                # Check against thresholds
                if adjusted_score > 0.55 and ratio >= ratio_min and change_24h <= pump_max:
                    approved.append({
                        'symbol': row['symbol'],
                        'hit_tp': hit_tp,
                        'max_gain': max_gain
                    })

            # Calculate metrics
            n_approved = len(approved)
            if n_approved == 0:
                continue

            n_hit_tp = sum(1 for a in approved if a['hit_tp'])
            tp_rate = (n_hit_tp / n_approved) * 100
            avg_max_gain = sum(a['max_gain'] for a in approved if a['max_gain']) / n_approved if n_approved > 0 else 0

            # Calculate a combined score (balance TP rate, volume, and opportunity)
            # We want: high TP rate, reasonable volume, good average gains
            volume_score = min(n_approved / 5, 1.0)  # Cap at 5 trades = 1.0
            opportunity_score = min(avg_max_gain / 50, 1.0)  # Cap at 50% avg gain = 1.0
            combined_score = (tp_rate * 0.5) + (volume_score * 20) + (opportunity_score * 30)

            results.append({
                'ratio_min': ratio_min,
                'pump_max': pump_max,
                'n_approved': n_approved,
                'n_hit_tp': n_hit_tp,
                'tp_rate': tp_rate,
                'avg_max_gain': avg_max_gain,
                'combined_score': combined_score,
                'approved_symbols': [a['symbol'] for a in approved]
            })

    # Sort by combined score
    results.sort(key=lambda x: x['combined_score'], reverse=True)

    return {
        'best': results[0] if results else None,
        'top_10': results[:10],
        'all_results': results
    }


def print_optimization_report(opt_results: Dict, df: pd.DataFrame):
    """Print the optimization results."""
    print("=" * 80)
    print("THRESHOLD OPTIMIZATION RESULTS")
    print("=" * 80)

    if 'error' in opt_results:
        print(f"Error: {opt_results['error']}")
        return

    best = opt_results['best']
    if not best:
        print("No valid configurations found.")
        return

    print(f"\nBASELINE (all bullish calls):")
    bullish_df = df[df['verdict'] == 'BULLISH']
    baseline_tp = (bullish_df['hit_tp_25'].sum() / len(bullish_df) * 100) if len(bullish_df) > 0 else 0
    print(f"  Calls: {len(bullish_df)}, TP Rate: {baseline_tp:.1f}%")

    print(f"\nBEST CONFIGURATION:")
    print(f"  Ratio >= {best['ratio_min']}x")
    print(f"  Pump <= {best['pump_max']}%")
    print(f"  Calls: {best['n_approved']} (filtered {len(bullish_df) - best['n_approved']})")
    print(f"  Hit TP: {best['n_hit_tp']}")
    print(f"  TP Rate: {best['tp_rate']:.1f}% (vs {baseline_tp:.1f}% baseline)")
    print(f"  Avg Max Gain: {best['avg_max_gain']:.1f}%")
    print(f"  Combined Score: {best['combined_score']:.1f}")
    print(f"  Approved: {', '.join(best['approved_symbols'])}")

    print(f"\nTOP 10 CONFIGURATIONS:")
    print("-" * 80)
    print(f"{'Ratio':>8} {'Pump':>8} {'Calls':>6} {'TP':>6} {'TP%':>8} {'AvgGain':>10} {'Score':>8}")
    print("-" * 80)

    for r in opt_results['top_10']:
        print(f"{r['ratio_min']:>7}x {r['pump_max']:>7}% {r['n_approved']:>6} "
              f"{r['n_hit_tp']:>6} {r['tp_rate']:>7.1f}% {r['avg_max_gain']:>9.1f}% "
              f"{r['combined_score']:>7.1f}")

    print("-" * 80)

    # Recommendation
    print(f"\nRECOMMENDATION:")
    if best['tp_rate'] >= 50 and best['n_approved'] >= 2:
        print(f"  [OK] Use ratio >= {best['ratio_min']}x, pump <= {best['pump_max']}%")
        print(f"       Expected: {best['tp_rate']:.0f}% win rate on ~{best['n_approved']} trades")
    elif best['tp_rate'] >= 40 and best['n_approved'] >= 3:
        print(f"  [OK] Use ratio >= {best['ratio_min']}x, pump <= {best['pump_max']}%")
        print(f"       Expected: {best['tp_rate']:.0f}% win rate on ~{best['n_approved']} trades")
    else:
        print(f"  [!!] Current data insufficient for confident recommendation")
        print(f"       Best found: {best['tp_rate']:.0f}% on {best['n_approved']} trades")

    print("\n")


# ============================================================================
# BACKTESTING ENGINE
# ============================================================================

def estimate_outcome(pred: Prediction, outcomes: Dict[str, TradeOutcome]) -> Optional[float]:
    """
    Estimate the outcome for a prediction.
    Uses actual trade data if available, otherwise estimates from price evolution.
    """
    # Check for actual trade outcome
    if pred.symbol in outcomes:
        return outcomes[pred.symbol].pnl_pct

    # No actual outcome - return None (unknown)
    return None


def run_backtest(
    strategy_name: str,
    strategy_filter: Callable[[Prediction], Tuple[bool, str]],
    predictions: List[Prediction],
    outcomes: Dict[str, TradeOutcome],
) -> BacktestResult:
    """Run a backtest with the given strategy filter."""

    accepted = []
    rejected = 0

    # Track unique tokens to avoid duplicate counting
    seen_tokens = set()

    for pred in predictions:
        accept, reason = strategy_filter(pred)
        if not accept:
            rejected += 1
            continue

        # Skip if we've already seen this token
        if pred.symbol in seen_tokens:
            continue
        seen_tokens.add(pred.symbol)

        outcome_pct = estimate_outcome(pred, outcomes)
        accepted.append({
            'symbol': pred.symbol,
            'timestamp': pred.timestamp,
            'score': pred.score,
            'change_24h': pred.change_24h,
            'ratio': pred.buy_sell_ratio,
            'reason': reason,
            'outcome_pct': outcome_pct,
        })

    # Calculate metrics
    total_signals = len(predictions)
    accepted_count = len(accepted)
    rejection_rate = rejected / total_signals if total_signals > 0 else 0

    # Separate wins and losses (only for signals with known outcomes)
    known_outcomes = [s for s in accepted if s['outcome_pct'] is not None]
    wins = [s for s in known_outcomes if s['outcome_pct'] > 0]
    losses = [s for s in known_outcomes if s['outcome_pct'] <= 0]

    win_count = len(wins)
    loss_count = len(losses)
    total_known = win_count + loss_count

    win_rate = win_count / total_known if total_known > 0 else 0

    avg_win = sum(s['outcome_pct'] for s in wins) / win_count if win_count > 0 else 0
    avg_loss = sum(s['outcome_pct'] for s in losses) / loss_count if loss_count > 0 else 0

    # Expected value = P(win) * avg_win + P(loss) * avg_loss
    expected_value = win_rate * avg_win + (1 - win_rate) * avg_loss

    # Calculate max drawdown (simplified)
    running_pnl = 0
    peak = 0
    max_dd = 0
    for s in known_outcomes:
        running_pnl += s['outcome_pct']
        if running_pnl > peak:
            peak = running_pnl
        dd = peak - running_pnl
        if dd > max_dd:
            max_dd = dd

    return BacktestResult(
        strategy_name=strategy_name,
        total_signals=total_signals,
        accepted_signals=accepted_count,
        rejection_rate=rejection_rate,
        simulated_wins=win_count,
        simulated_losses=loss_count,
        win_rate=win_rate,
        avg_win_pct=avg_win,
        avg_loss_pct=avg_loss,
        expected_value=expected_value,
        max_drawdown=max_dd,
        signals_detail=known_outcomes,
    )


def print_backtest_results(results: List[BacktestResult]) -> None:
    """Print formatted backtest results comparison."""

    print("\n" + "=" * 80)
    print("BACKTEST RESULTS COMPARISON")
    print("=" * 80)

    # Header
    print(f"{'Strategy':<30} {'Signals':>8} {'Accept':>8} {'Wins':>6} {'Losses':>6} "
          f"{'WinRate':>8} {'Avg Win':>8} {'Avg Loss':>9} {'EV':>8}")
    print("-" * 80)

    # Sort by expected value
    results = sorted(results, key=lambda r: r.expected_value, reverse=True)

    for r in results:
        print(f"{r.strategy_name:<30} {r.total_signals:>8} {r.accepted_signals:>8} "
              f"{r.simulated_wins:>6} {r.simulated_losses:>6} "
              f"{r.win_rate*100:>7.1f}% {r.avg_win_pct:>7.1f}% {r.avg_loss_pct:>8.1f}% "
              f"{r.expected_value:>7.1f}%")

    # Best strategy recommendation
    if results:
        best = results[0]
        print("\n" + "=" * 80)
        print(f"RECOMMENDED STRATEGY: {best.strategy_name}")
        print("=" * 80)
        print(f"Expected Value: {best.expected_value:.2f}% per trade")
        print(f"Win Rate: {best.win_rate*100:.1f}%")
        print(f"Signals Accepted: {best.accepted_signals} ({best.rejection_rate*100:.1f}% rejection rate)")

        # Show accepted signals detail
        if best.signals_detail:
            print("\nAccepted signals with outcomes:")
            for s in best.signals_detail:
                outcome = s['outcome_pct']
                status = "WIN" if outcome > 0 else "LOSS"
                print(f"  {s['symbol']}: {outcome:+.1f}% ({status})")


def main():
    """Run backtesting framework."""
    import argparse
    parser = argparse.ArgumentParser(description='Backtest sentiment engine strategies')
    parser.add_argument('--csv', action='store_true', help='Run CSV-based comprehensive backtest')
    parser.add_argument('--compare', action='store_true', help='Run old vs new rules comparison')
    parser.add_argument('--optimize', action='store_true', help='Run threshold optimization to find best parameters')
    args = parser.parse_args()

    if args.optimize:
        # Run threshold optimization
        print("\nLoading CSV data for optimization...")
        if not CSV_FILE.exists():
            print(f"Error: CSV file not found at {CSV_FILE}")
            print("Run scripts/unified_mega_analysis.py first to generate the data.")
            return

        df = pd.read_csv(CSV_FILE)
        print(f"Loaded {len(df)} calls")

        print("\nRunning threshold optimization...")
        opt_results = optimize_thresholds_csv(df)

        # Print optimization report
        print_optimization_report(opt_results, df)

        # Export results
        results_file = DATA_DIR / "optimization_results.json"
        with open(results_file, 'w') as f:
            json.dump({
                'best': opt_results['best'],
                'top_10': opt_results['top_10']
            }, f, indent=2, default=str)
        print(f"Optimization results saved to: {results_file}")
        return

    if args.csv or args.compare:
        # CSV-based backtest
        print("\nLoading CSV data...")
        if not CSV_FILE.exists():
            print(f"Error: CSV file not found at {CSV_FILE}")
            print("Run scripts/unified_mega_analysis.py first to generate the data.")
            return

        df = pd.read_csv(CSV_FILE)
        print(f"Loaded {len(df)} calls")

        print("\nRunning backtest on actual bullish calls...")
        backtest = run_csv_backtest()

        print("Analyzing rule improvements...")
        improvements = analyze_rule_improvements(df)

        # Print comparison report
        print_csv_backtest_report(backtest, improvements, df)

        # Export results
        results_file = DATA_DIR / "backtest_results.json"
        results = {
            'actual_bullish_count': backtest['actual_bullish_count'],
            'actual_tp_rate': backtest['actual_tp_rate'],
            'new_rules_approved': len(backtest['new_rules_would_approve']),
            'new_rules_rejected': len(backtest['new_rules_would_reject']),
            'filtered_out_details': backtest['filtered_out_details'],
            'improvements': improvements
        }
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\nDetailed results saved to: {results_file}")
    else:
        # JSON-based backtest (original behavior)
        print("Loading data...")
        predictions = load_predictions()
        outcomes = load_trade_outcomes()

        print(f"Loaded {len(predictions)} predictions")
        print(f"Loaded {len(outcomes)} trade outcomes")

        # Only keep bullish predictions for comparison
        bullish_preds = [p for p in predictions if p.verdict == 'BULLISH']
        print(f"Bullish predictions: {len(bullish_preds)}")

        # Define strategies to test
        strategies = [
            # Baseline strategies
            ("Current (baseline)", strategy_current),
            ("Old Rules (pre-2026-01-21)", strategy_old_rules),
            # Data-driven variations
            ("Data-Driven 2026 (strict)", strategy_data_driven_2026),
            ("Data-Driven Balanced", strategy_data_driven_balanced),
            ("Data-Driven Relaxed", strategy_data_driven_relaxed),
            # Single-factor strategies
            ("Pump Filter Only (<40%)", strategy_pump_filter_only),
            ("Ratio Filter Only (>=2x)", strategy_ratio_filter_only),
            ("Score Penalty Only", strategy_score_penalty_only),
            # Other strategies
            ("No Pump Chasing (>50%)", strategy_no_pump_chasing),
            ("Early Entry Only (<20%)", strategy_early_entry_only),
            ("High Ratio + Early", strategy_high_ratio_early),
            ("Inverted Pump Scoring", strategy_inverted_pump_scoring),
            ("Conservative", strategy_conservative),
        ]

        # Run backtests
        results = []
        for name, filter_func in strategies:
            print(f"Testing: {name}...")
            result = run_backtest(name, filter_func, bullish_preds, outcomes)
            results.append(result)

        # Print comparison
        print_backtest_results(results)

        # Detailed analysis of losses
        print("\n" + "=" * 80)
        print("LOSS ANALYSIS - What would each strategy have avoided?")
        print("=" * 80)

        for name, filter_func in strategies:
            print(f"\n{name}:")
            avoided_losses = []
            for pred in bullish_preds:
                if pred.symbol in outcomes:
                    outcome = outcomes[pred.symbol]
                    if outcome.pnl_pct < -50:  # Major loss
                        accept, reason = filter_func(pred)
                        if not accept:
                            avoided_losses.append((pred.symbol, outcome.pnl_pct, reason))

            if avoided_losses:
                print(f"  Would have avoided {len(avoided_losses)} catastrophic losses:")
                for symbol, pnl, reason in avoided_losses:
                    print(f"    {symbol}: {pnl:.1f}% - Rejected: {reason}")
            else:
                print("  Would NOT have avoided any major losses")


if __name__ == "__main__":
    main()
