"""
Buy Tracker Database - SQLite storage for buy history, predictions, and analytics.
"""

import sqlite3
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from contextlib import contextmanager

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "buy_tracker.db"


@dataclass
class BuyRecord:
    """A single buy transaction record."""
    id: Optional[int] = None
    timestamp: str = ""
    token_symbol: str = ""
    token_name: str = ""
    token_mint: str = ""
    buyer_wallet: str = ""
    amount_sol: float = 0.0
    amount_usd: float = 0.0
    token_amount: float = 0.0
    price_at_buy: float = 0.0
    tx_signature: str = ""
    sentiment_score: float = 0.0
    sentiment_label: str = ""
    grok_verdict: str = ""
    alert_sent: bool = False


@dataclass
class PredictionRecord:
    """A prediction tracking record."""
    id: Optional[int] = None
    timestamp: str = ""
    token_symbol: str = ""
    token_mint: str = ""
    prediction_type: str = ""  # BULLISH, BEARISH, NEUTRAL
    confidence: float = 0.0
    price_at_prediction: float = 0.0
    target_price: float = 0.0
    stop_loss: float = 0.0
    outcome: str = ""  # WIN, LOSS, PENDING
    outcome_price: float = 0.0
    outcome_timestamp: str = ""
    pnl_percent: float = 0.0


class BuyTrackerDB:
    """SQLite database for buy tracking and analytics."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Buy history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS buys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    token_symbol TEXT NOT NULL,
                    token_name TEXT,
                    token_mint TEXT NOT NULL,
                    buyer_wallet TEXT NOT NULL,
                    amount_sol REAL,
                    amount_usd REAL,
                    token_amount REAL,
                    price_at_buy REAL,
                    tx_signature TEXT UNIQUE,
                    sentiment_score REAL,
                    sentiment_label TEXT,
                    grok_verdict TEXT,
                    alert_sent INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Predictions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    token_symbol TEXT NOT NULL,
                    token_mint TEXT,
                    prediction_type TEXT NOT NULL,
                    confidence REAL,
                    price_at_prediction REAL,
                    target_price REAL,
                    stop_loss REAL,
                    outcome TEXT DEFAULT 'PENDING',
                    outcome_price REAL,
                    outcome_timestamp TEXT,
                    pnl_percent REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Token metadata cache
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS token_metadata (
                    mint TEXT PRIMARY KEY,
                    symbol TEXT,
                    name TEXT,
                    decimals INTEGER,
                    logo_url TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Alert deduplication table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sent_alerts (
                    tx_signature TEXT PRIMARY KEY,
                    sent_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Indexes for fast queries
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_buys_timestamp ON buys(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_buys_token ON buys(token_mint)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_buys_wallet ON buys(buyer_wallet)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_predictions_token ON predictions(token_mint)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_predictions_outcome ON predictions(outcome)")

            conn.commit()
            logger.info(f"Database initialized at {self.db_path}")

    @contextmanager
    def _get_connection(self):
        """Get database connection with context manager."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    # === BUY RECORDS ===

    def record_buy(self, buy: BuyRecord) -> int:
        """Record a buy transaction. Returns ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO buys
                (timestamp, token_symbol, token_name, token_mint, buyer_wallet,
                 amount_sol, amount_usd, token_amount, price_at_buy, tx_signature,
                 sentiment_score, sentiment_label, grok_verdict, alert_sent)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                buy.timestamp or datetime.now(timezone.utc).isoformat(),
                buy.token_symbol, buy.token_name, buy.token_mint, buy.buyer_wallet,
                buy.amount_sol, buy.amount_usd, buy.token_amount, buy.price_at_buy,
                buy.tx_signature, buy.sentiment_score, buy.sentiment_label,
                buy.grok_verdict, 1 if buy.alert_sent else 0
            ))
            conn.commit()
            return cursor.lastrowid

    def is_duplicate_alert(self, tx_signature: str) -> bool:
        """Check if alert was already sent for this tx."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM sent_alerts WHERE tx_signature = ?", (tx_signature,))
            return cursor.fetchone() is not None

    def mark_alert_sent(self, tx_signature: str):
        """Mark alert as sent to prevent duplicates."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO sent_alerts (tx_signature) VALUES (?)",
                (tx_signature,)
            )
            conn.commit()

    def get_recent_buys(self, hours: int = 24, limit: int = 100) -> List[Dict]:
        """Get recent buy transactions."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM buys
                WHERE datetime(timestamp) > datetime('now', ?)
                ORDER BY timestamp DESC
                LIMIT ?
            """, (f'-{hours} hours', limit))
            return [dict(row) for row in cursor.fetchall()]

    def get_buys_by_token(self, token_mint: str, limit: int = 50) -> List[Dict]:
        """Get buy history for a specific token."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM buys
                WHERE token_mint = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (token_mint, limit))
            return [dict(row) for row in cursor.fetchall()]

    def get_buy_stats(self, hours: int = 24) -> Dict:
        """Get buy statistics for time period."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    COUNT(*) as total_buys,
                    COUNT(DISTINCT token_mint) as unique_tokens,
                    COUNT(DISTINCT buyer_wallet) as unique_buyers,
                    SUM(amount_sol) as total_sol,
                    SUM(amount_usd) as total_usd,
                    AVG(amount_usd) as avg_buy_usd
                FROM buys
                WHERE datetime(timestamp) > datetime('now', ?)
            """, (f'-{hours} hours',))
            row = cursor.fetchone()
            return dict(row) if row else {}

    # === PREDICTIONS ===

    def record_prediction(self, pred: PredictionRecord) -> int:
        """Record a prediction for tracking."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO predictions
                (timestamp, token_symbol, token_mint, prediction_type, confidence,
                 price_at_prediction, target_price, stop_loss, outcome)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDING')
            """, (
                pred.timestamp or datetime.now(timezone.utc).isoformat(),
                pred.token_symbol, pred.token_mint, pred.prediction_type,
                pred.confidence, pred.price_at_prediction, pred.target_price,
                pred.stop_loss
            ))
            conn.commit()
            return cursor.lastrowid

    def update_prediction_outcome(self, prediction_id: int, outcome: str,
                                   outcome_price: float, pnl_percent: float):
        """Update prediction with outcome."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE predictions
                SET outcome = ?, outcome_price = ?, pnl_percent = ?,
                    outcome_timestamp = ?
                WHERE id = ?
            """, (outcome, outcome_price, pnl_percent,
                  datetime.now(timezone.utc).isoformat(), prediction_id))
            conn.commit()

    def get_prediction_accuracy(self, days: int = 7) -> Dict:
        """Calculate prediction accuracy over time period."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    prediction_type,
                    COUNT(*) as total,
                    SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN outcome = 'LOSS' THEN 1 ELSE 0 END) as losses,
                    AVG(pnl_percent) as avg_pnl
                FROM predictions
                WHERE datetime(timestamp) > datetime('now', ?)
                AND outcome != 'PENDING'
                GROUP BY prediction_type
            """, (f'-{days} days',))

            results = {}
            for row in cursor.fetchall():
                row_dict = dict(row)
                total = row_dict['total']
                wins = row_dict['wins']
                results[row_dict['prediction_type']] = {
                    'total': total,
                    'wins': wins,
                    'losses': row_dict['losses'],
                    'accuracy': (wins / total * 100) if total > 0 else 0,
                    'avg_pnl': row_dict['avg_pnl'] or 0
                }
            return results

    def get_pending_predictions(self) -> List[Dict]:
        """Get predictions that need outcome checking."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM predictions
                WHERE outcome = 'PENDING'
                ORDER BY timestamp ASC
            """)
            return [dict(row) for row in cursor.fetchall()]

    # === TOKEN METADATA CACHE ===

    def get_token_metadata(self, mint: str) -> Optional[Dict]:
        """Get cached token metadata."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM token_metadata WHERE mint = ?", (mint,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def cache_token_metadata(self, mint: str, symbol: str, name: str,
                             decimals: int, logo_url: str = ""):
        """Cache token metadata."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO token_metadata
                (mint, symbol, name, decimals, logo_url, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (mint, symbol, name, decimals, logo_url,
                  datetime.now(timezone.utc).isoformat()))
            conn.commit()

    # === ANALYTICS ===

    def get_top_tokens(self, hours: int = 24, limit: int = 10) -> List[Dict]:
        """Get tokens with most buy activity."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    token_symbol,
                    token_mint,
                    COUNT(*) as buy_count,
                    SUM(amount_usd) as total_usd,
                    COUNT(DISTINCT buyer_wallet) as unique_buyers
                FROM buys
                WHERE datetime(timestamp) > datetime('now', ?)
                GROUP BY token_mint
                ORDER BY buy_count DESC
                LIMIT ?
            """, (f'-{hours} hours', limit))
            return [dict(row) for row in cursor.fetchall()]

    def get_top_buyers(self, hours: int = 24, limit: int = 10) -> List[Dict]:
        """Get most active buyer wallets."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    buyer_wallet,
                    COUNT(*) as buy_count,
                    SUM(amount_usd) as total_usd,
                    COUNT(DISTINCT token_mint) as unique_tokens
                FROM buys
                WHERE datetime(timestamp) > datetime('now', ?)
                GROUP BY buyer_wallet
                ORDER BY total_usd DESC
                LIMIT ?
            """, (f'-{hours} hours', limit))
            return [dict(row) for row in cursor.fetchall()]


# Singleton instance
_db_instance: Optional[BuyTrackerDB] = None

def get_db() -> BuyTrackerDB:
    """Get singleton database instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = BuyTrackerDB()
    return _db_instance
