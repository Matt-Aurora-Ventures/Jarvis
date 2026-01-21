"""
Backtesting Framework for Sentiment Engine Strategies.

This framework allows testing different scoring strategies and entry rules
against historical prediction/outcome data.

Usage:
    python scripts/backtesting.py
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# Paths
ROOT = Path(__file__).resolve().parents[1]
PREDICTIONS_FILE = ROOT / "bots" / "buy_tracker" / "predictions_history.json"
TRADES_FILE = ROOT / "bots" / "treasury" / ".trade_history.json"


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

    return metrics


def load_predictions() -> List[Prediction]:
    """Load all predictions from history."""
    if not PREDICTIONS_FILE.exists():
        return []

    with open(PREDICTIONS_FILE, 'r', encoding='utf-8') as f:
        history = json.load(f)

    predictions = []
    for entry in history:
        timestamp = entry.get('timestamp', '')
        market_regime = entry.get('market_regime', 'UNKNOWN')

        for symbol, data in entry.get('token_predictions', {}).items():
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
            )
            predictions.append(pred)

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
        ("Current (baseline)", strategy_current),
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
