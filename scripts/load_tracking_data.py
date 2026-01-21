"""
Load historical prediction and trade data into the tracking database.

This script:
1. Loads all predictions from predictions_history.json
2. Loads all trades from .trade_history.json
3. Calculates factor statistics
4. Generates the probability model
"""

import json
import sqlite3
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

# Paths
ROOT = Path(__file__).resolve().parents[1]
PREDICTIONS_FILE = ROOT / "bots" / "buy_tracker" / "predictions_history.json"
TRADES_FILE = ROOT / "bots" / "treasury" / ".trade_history.json"
DB_PATH = ROOT / "data" / "call_tracking.db"

# Ensure data directory exists
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def extract_metrics_from_reasoning(reasoning: str) -> Dict[str, Any]:
    """Extract numeric metrics from reasoning text."""
    metrics = {}

    # Extract change_24h
    change_match = re.search(r'24h[:\s]*([+-]?\d+\.?\d*)%', reasoning)
    if change_match:
        try:
            metrics['change_24h'] = float(change_match.group(1))
        except ValueError:
            pass

    # Extract buy/sell ratio
    ratio_match = re.search(r'ratio[:\s]*(\d+\.?\d*)', reasoning, re.IGNORECASE)
    if ratio_match:
        try:
            metrics['buy_sell_ratio'] = float(ratio_match.group(1))
        except ValueError:
            pass

    # Alternative ratio pattern
    if 'buy_sell_ratio' not in metrics:
        ratio_match = re.search(r'(\d+\.?\d*)x\s*(?:buy|ratio)', reasoning, re.IGNORECASE)
        if ratio_match:
            try:
                metrics['buy_sell_ratio'] = float(ratio_match.group(1))
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


def categorize_pump(change_pct: Optional[float]) -> str:
    """Categorize the existing pump level."""
    if change_pct is None:
        return 'unknown'
    if change_pct < 20:
        return 'early'
    if change_pct < 100:
        return 'moderate'
    if change_pct < 500:
        return 'large'
    return 'extreme'


def categorize_ratio(ratio: Optional[float]) -> str:
    """Categorize buy/sell ratio."""
    if ratio is None:
        return 'unknown'
    if ratio < 1.5:
        return 'weak'
    if ratio < 2.0:
        return 'moderate'
    if ratio < 3.0:
        return 'strong'
    return 'very_strong'


def categorize_score(score: Optional[float]) -> str:
    """Categorize sentiment score."""
    if score is None:
        return 'unknown'
    if score < 0.4:
        return 'low'
    if score < 0.6:
        return 'medium'
    if score < 0.8:
        return 'high'
    return 'very_high'


def load_predictions(conn: sqlite3.Connection) -> int:
    """Load predictions into the calls table."""
    if not PREDICTIONS_FILE.exists():
        print(f"Predictions file not found: {PREDICTIONS_FILE}")
        return 0

    with open(PREDICTIONS_FILE, 'r', encoding='utf-8') as f:
        history = json.load(f)

    cursor = conn.cursor()
    count = 0

    for entry in history:
        timestamp = entry.get('timestamp', '')
        market_regime = entry.get('market_regime', 'UNKNOWN')
        token_predictions = entry.get('token_predictions', {})

        for symbol, data in token_predictions.items():
            # Generate unique ID
            call_id = str(uuid.uuid4())[:8]

            # Extract data
            verdict = data.get('verdict', 'NEUTRAL')
            score = data.get('score', 0)
            price = data.get('price_at_prediction', 0)
            reasoning = data.get('reasoning', '')
            contract = data.get('contract', '')

            # Extract metrics from reasoning
            metrics = extract_metrics_from_reasoning(reasoning)

            # Insert into database
            cursor.execute('''
                INSERT OR IGNORE INTO calls
                (id, timestamp, source, symbol, contract, verdict, score,
                 price_at_call, reasoning, change_24h_at_call, buy_sell_ratio,
                 volume_24h, market_cap, market_regime)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                call_id, timestamp, 'predictions', symbol, contract,
                verdict, score, price, reasoning,
                metrics.get('change_24h'), metrics.get('buy_sell_ratio'),
                metrics.get('volume'), metrics.get('market_cap'),
                market_regime
            ))
            count += 1

    conn.commit()
    return count


def load_trades(conn: sqlite3.Connection) -> int:
    """Load trades into the trades table."""
    if not TRADES_FILE.exists():
        print(f"Trades file not found: {TRADES_FILE}")
        return 0

    with open(TRADES_FILE, 'r', encoding='utf-8') as f:
        trades = json.load(f)

    cursor = conn.cursor()
    count = 0

    for trade in trades:
        trade_id = str(uuid.uuid4())[:8]

        cursor.execute('''
            INSERT OR IGNORE INTO trades
            (id, symbol, contract, entry_time, exit_time, entry_price, exit_price,
             position_size, pnl_pct, pnl_usd, status, exit_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            trade_id,
            trade.get('symbol', ''),
            trade.get('contract', ''),
            trade.get('entry_time', ''),
            trade.get('exit_time', ''),
            trade.get('entry_price'),
            trade.get('exit_price'),
            trade.get('sol_amount'),
            trade.get('pnl_pct'),
            trade.get('pnl'),
            trade.get('status', ''),
            trade.get('exit_reason', '')
        ))
        count += 1

    conn.commit()
    return count


def calculate_factor_stats(conn: sqlite3.Connection) -> None:
    """Calculate win/loss rates by factor."""
    cursor = conn.cursor()

    # Get all bullish calls with outcomes from trades
    cursor.execute('''
        SELECT c.id, c.change_24h_at_call, c.buy_sell_ratio, c.score,
               t.pnl_pct
        FROM calls c
        JOIN trades t ON c.symbol = t.symbol AND c.timestamp <= t.entry_time
        WHERE c.verdict = 'BULLISH'
    ''')

    # Factor statistics
    stats = {
        'pump_level': {},
        'ratio_level': {},
        'score_level': {}
    }

    rows = cursor.fetchall()

    for row in rows:
        call_id, change_24h, ratio, score, pnl_pct = row

        # Skip if no outcome
        if pnl_pct is None:
            continue

        is_win = pnl_pct > 0

        # Categorize factors
        pump = categorize_pump(change_24h)
        ratio_cat = categorize_ratio(ratio)
        score_cat = categorize_score(score)

        # Update stats
        for factor, category in [('pump_level', pump), ('ratio_level', ratio_cat), ('score_level', score_cat)]:
            if category not in stats[factor]:
                stats[factor][category] = {'wins': 0, 'losses': 0, 'total': 0, 'pnl_sum': 0}

            stats[factor][category]['total'] += 1
            stats[factor][category]['pnl_sum'] += pnl_pct
            if is_win:
                stats[factor][category]['wins'] += 1
            else:
                stats[factor][category]['losses'] += 1

    # Clear existing factor stats
    cursor.execute('DELETE FROM factor_stats')

    # Insert new stats
    now = datetime.now().isoformat()
    for factor_name, levels in stats.items():
        for level, data in levels.items():
            total = data['total']
            wins = data['wins']
            losses = data['losses']
            win_rate = wins / total if total > 0 else 0
            avg_pnl = data['pnl_sum'] / total if total > 0 else 0

            cursor.execute('''
                INSERT INTO factor_stats
                (id, factor_name, factor_level, total_calls, wins, losses, avg_pnl_pct, win_rate, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                str(uuid.uuid4())[:8],
                factor_name, level, total, wins, losses, avg_pnl, win_rate, now
            ))

    conn.commit()


def generate_probability_model(conn: sqlite3.Connection) -> None:
    """Generate probability model based on factor combinations."""
    cursor = conn.cursor()

    # Clear existing model
    cursor.execute('DELETE FROM probability_model')

    # Get all bullish calls with outcomes
    cursor.execute('''
        SELECT c.change_24h_at_call, c.buy_sell_ratio, c.score, c.market_regime,
               t.pnl_pct
        FROM calls c
        JOIN trades t ON c.symbol = t.symbol
        WHERE c.verdict = 'BULLISH' AND t.pnl_pct IS NOT NULL
    ''')

    # Group by factor combinations
    combos = {}

    for row in cursor.fetchall():
        change_24h, ratio, score, regime, pnl_pct = row

        pump = categorize_pump(change_24h)
        ratio_cat = categorize_ratio(ratio)
        score_cat = categorize_score(score)

        key = (pump, ratio_cat, score_cat, regime)

        if key not in combos:
            combos[key] = {'wins': [], 'losses': []}

        if pnl_pct > 0:
            combos[key]['wins'].append(pnl_pct)
        else:
            combos[key]['losses'].append(pnl_pct)

    # Calculate probabilities
    now = datetime.now().isoformat()

    for (pump, ratio_cat, score_cat, regime), data in combos.items():
        wins = data['wins']
        losses = data['losses']
        total = len(wins) + len(losses)

        if total == 0:
            continue

        win_prob = len(wins) / total
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else 0

        # Expected value = P(win) * avg_win + P(loss) * avg_loss
        expected_value = win_prob * avg_win + (1 - win_prob) * avg_loss

        cursor.execute('''
            INSERT INTO probability_model
            (id, pump_level, ratio_level, score_level, regime, sample_size,
             win_probability, avg_win_pct, avg_loss_pct, expected_value, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            str(uuid.uuid4())[:8],
            pump, ratio_cat, score_cat, regime, total,
            win_prob, avg_win, avg_loss, expected_value, now
        ))

    conn.commit()


def print_summary(conn: sqlite3.Connection) -> None:
    """Print database summary."""
    cursor = conn.cursor()

    print("\n" + "=" * 60)
    print("DATABASE SUMMARY")
    print("=" * 60)

    # Calls count
    cursor.execute('SELECT COUNT(*) FROM calls')
    print(f"Total calls loaded: {cursor.fetchone()[0]}")

    # Trades count
    cursor.execute('SELECT COUNT(*) FROM trades')
    print(f"Total trades loaded: {cursor.fetchone()[0]}")

    # Factor stats
    print("\nFactor Statistics:")
    cursor.execute('''
        SELECT factor_name, factor_level, total_calls, wins, losses,
               ROUND(win_rate * 100, 1) as win_rate_pct
        FROM factor_stats
        ORDER BY factor_name, factor_level
    ''')

    current_factor = None
    for row in cursor.fetchall():
        factor_name, level, total, wins, losses, win_rate = row
        if factor_name != current_factor:
            print(f"\n  {factor_name}:")
            current_factor = factor_name
        print(f"    {level}: {total} calls, {wins}W/{losses}L ({win_rate}%)")

    # Probability model
    print("\nProbability Model:")
    cursor.execute('''
        SELECT pump_level, ratio_level, score_level, regime, sample_size,
               ROUND(win_probability * 100, 1) as win_prob,
               ROUND(expected_value, 2) as ev
        FROM probability_model
        WHERE sample_size >= 3
        ORDER BY win_probability DESC
    ''')

    for row in cursor.fetchall():
        pump, ratio, score, regime, n, win_prob, ev = row
        print(f"  {pump}/{ratio}/{score}/{regime}: {win_prob}% win ({n} samples), EV={ev}%")


def create_tables(conn: sqlite3.Connection) -> None:
    """Create database tables if they don't exist."""
    cursor = conn.cursor()

    # Calls table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS calls (
            id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            source TEXT NOT NULL,
            symbol TEXT NOT NULL,
            contract TEXT,
            verdict TEXT NOT NULL,
            score REAL,
            price_at_call REAL,
            reasoning TEXT,
            change_24h_at_call REAL,
            buy_sell_ratio REAL,
            volume_24h REAL,
            market_cap REAL,
            liquidity REAL,
            holders INTEGER,
            market_regime TEXT
        )
    ''')

    # Outcomes table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS outcomes (
            id TEXT PRIMARY KEY,
            call_id TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            price_after REAL,
            change_pct REAL,
            measured_at TEXT
        )
    ''')

    # Factor stats table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS factor_stats (
            id TEXT PRIMARY KEY,
            factor_name TEXT NOT NULL,
            factor_level TEXT NOT NULL,
            total_calls INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            avg_pnl_pct REAL,
            win_rate REAL,
            last_updated TEXT
        )
    ''')

    # Trades table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id TEXT PRIMARY KEY,
            call_id TEXT,
            symbol TEXT NOT NULL,
            contract TEXT,
            entry_time TEXT,
            exit_time TEXT,
            entry_price REAL,
            exit_price REAL,
            position_size REAL,
            pnl_pct REAL,
            pnl_usd REAL,
            status TEXT,
            exit_reason TEXT
        )
    ''')

    # Probability model table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS probability_model (
            id TEXT PRIMARY KEY,
            pump_level TEXT,
            ratio_level TEXT,
            score_level TEXT,
            regime TEXT,
            sample_size INTEGER,
            win_probability REAL,
            avg_win_pct REAL,
            avg_loss_pct REAL,
            expected_value REAL,
            last_updated TEXT
        )
    ''')

    conn.commit()


def main():
    """Main entry point."""
    print("Initializing tracking database...")
    print(f"Database path: {DB_PATH}")

    conn = sqlite3.connect(str(DB_PATH))

    # Create tables
    print("Creating tables...")
    create_tables(conn)

    # Load data
    print("\nLoading predictions...")
    pred_count = load_predictions(conn)
    print(f"  Loaded {pred_count} prediction records")

    print("\nLoading trades...")
    trade_count = load_trades(conn)
    print(f"  Loaded {trade_count} trade records")

    # Calculate statistics
    print("\nCalculating factor statistics...")
    calculate_factor_stats(conn)

    print("Generating probability model...")
    generate_probability_model(conn)

    # Print summary
    print_summary(conn)

    conn.close()
    print(f"\nDatabase saved to: {DB_PATH}")


if __name__ == "__main__":
    main()
