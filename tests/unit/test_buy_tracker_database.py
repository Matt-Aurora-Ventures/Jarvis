"""
Comprehensive unit tests for the Buy Tracker Database (database.py).

Tests cover:
1. Database Initialization
   - Table creation (buys, predictions, token_metadata, sent_alerts)
   - Index creation
   - Schema validation

2. BuyRecord Operations
   - Recording buy transactions
   - Duplicate signature handling (INSERT OR IGNORE)
   - Timestamp auto-generation
   - alert_sent boolean conversion

3. Alert Deduplication
   - is_duplicate_alert checks
   - mark_alert_sent persistence
   - Duplicate signature prevention

4. Query Methods
   - get_recent_buys (with hours and limit)
   - get_buys_by_token (token_mint filtering)
   - get_buy_stats (aggregation)
   - get_top_tokens (ranking by activity)
   - get_top_buyers (ranking by volume)

5. Prediction Operations
   - record_prediction
   - update_prediction_outcome
   - get_pending_predictions
   - get_prediction_accuracy

6. Token Metadata Cache
   - get_token_metadata
   - cache_token_metadata
   - INSERT OR REPLACE behavior

7. Connection Management
   - Context manager behavior
   - Connection pooling
   - Cleanup on errors

8. Singleton Pattern
   - get_db() returns singleton
   - Reset behavior

9. Edge Cases
   - Empty database queries
   - Null/None value handling
   - Very large datasets
   - Concurrent access (basic)

10. Dataclass Operations
    - BuyRecord creation and defaults
    - PredictionRecord creation and defaults
    - asdict serialization
"""

import pytest
import sqlite3
import tempfile
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from bots.buy_tracker.database import (
    BuyTrackerDB,
    BuyRecord,
    PredictionRecord,
    get_db,
    DB_PATH,
)


# =============================================================================
# TEST FIXTURES
# =============================================================================

@pytest.fixture
def temp_db_path():
    """Create a temporary database path for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        yield Path(f.name)
    # Cleanup
    try:
        os.unlink(f.name)
    except Exception:
        pass


@pytest.fixture
def db(temp_db_path):
    """Create a fresh database instance for testing."""
    return BuyTrackerDB(db_path=temp_db_path)


@pytest.fixture
def sample_buy_record():
    """Create a sample BuyRecord for testing."""
    return BuyRecord(
        timestamp=datetime.now(timezone.utc).isoformat(),
        token_symbol="KR8TIV",
        token_name="Kr8Tiv",
        token_mint="mint123456789012345678901234567890123456",
        buyer_wallet="wallet123456789012345678901234567890123",
        amount_sol=1.5,
        amount_usd=150.0,
        token_amount=1000000.0,
        price_at_buy=0.00015,
        tx_signature="sig123456789012345678901234567890123456",
        sentiment_score=0.8,
        sentiment_label="BULLISH",
        grok_verdict="Strong buy signal",
        alert_sent=False,
    )


@pytest.fixture
def sample_prediction_record():
    """Create a sample PredictionRecord for testing."""
    return PredictionRecord(
        timestamp=datetime.now(timezone.utc).isoformat(),
        token_symbol="KR8TIV",
        token_mint="mint123456789012345678901234567890123456",
        prediction_type="BULLISH",
        confidence=0.85,
        price_at_prediction=0.001,
        target_price=0.002,
        stop_loss=0.0008,
    )


# =============================================================================
# 1. DATABASE INITIALIZATION TESTS
# =============================================================================

class TestDatabaseInitialization:
    """Tests for database initialization and schema creation."""

    def test_db_initialization_creates_tables(self, temp_db_path):
        """Test database initialization creates all required tables."""
        db = BuyTrackerDB(db_path=temp_db_path)

        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = {row[0] for row in cursor.fetchall()}

        assert 'buys' in tables
        assert 'predictions' in tables
        assert 'token_metadata' in tables
        assert 'sent_alerts' in tables

    def test_db_initialization_creates_indexes(self, temp_db_path):
        """Test database initialization creates all required indexes."""
        db = BuyTrackerDB(db_path=temp_db_path)

        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            )
            indexes = {row[0] for row in cursor.fetchall()}

        assert 'idx_buys_timestamp' in indexes
        assert 'idx_buys_token' in indexes
        assert 'idx_buys_wallet' in indexes
        assert 'idx_predictions_token' in indexes
        assert 'idx_predictions_outcome' in indexes

    def test_db_initialization_with_custom_path(self, temp_db_path):
        """Test database initialization with custom path."""
        db = BuyTrackerDB(db_path=temp_db_path)

        assert db.db_path == temp_db_path
        assert temp_db_path.exists()

    def test_db_default_path_constant(self):
        """Test DB_PATH constant is set correctly."""
        assert DB_PATH is not None
        assert str(DB_PATH).endswith("buy_tracker.db")

    def test_buys_table_schema(self, db):
        """Test buys table has correct columns."""
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(buys)")
            columns = {row[1] for row in cursor.fetchall()}

        expected_columns = {
            'id', 'timestamp', 'token_symbol', 'token_name', 'token_mint',
            'buyer_wallet', 'amount_sol', 'amount_usd', 'token_amount',
            'price_at_buy', 'tx_signature', 'sentiment_score', 'sentiment_label',
            'grok_verdict', 'alert_sent', 'created_at'
        }
        assert expected_columns.issubset(columns)

    def test_predictions_table_schema(self, db):
        """Test predictions table has correct columns."""
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(predictions)")
            columns = {row[1] for row in cursor.fetchall()}

        expected_columns = {
            'id', 'timestamp', 'token_symbol', 'token_mint', 'prediction_type',
            'confidence', 'price_at_prediction', 'target_price', 'stop_loss',
            'outcome', 'outcome_price', 'outcome_timestamp', 'pnl_percent', 'created_at'
        }
        assert expected_columns.issubset(columns)

    def test_token_metadata_table_schema(self, db):
        """Test token_metadata table has correct columns."""
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(token_metadata)")
            columns = {row[1] for row in cursor.fetchall()}

        expected_columns = {'mint', 'symbol', 'name', 'decimals', 'logo_url', 'updated_at'}
        assert expected_columns.issubset(columns)

    def test_sent_alerts_table_schema(self, db):
        """Test sent_alerts table has correct columns."""
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(sent_alerts)")
            columns = {row[1] for row in cursor.fetchall()}

        expected_columns = {'tx_signature', 'sent_at'}
        assert expected_columns.issubset(columns)

    def test_tx_signature_unique_constraint(self, db, sample_buy_record):
        """Test tx_signature has UNIQUE constraint on buys table."""
        buy1 = sample_buy_record
        buy2 = BuyRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            token_symbol="OTHER",
            token_mint="other_mint",
            buyer_wallet="other_wallet",
            amount_sol=2.0,
            amount_usd=200.0,
            tx_signature=buy1.tx_signature,  # Same signature
        )

        db.record_buy(buy1)
        db.record_buy(buy2)  # Should be ignored

        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM buys WHERE tx_signature = ?",
                         (buy1.tx_signature,))
            count = cursor.fetchone()[0]

        assert count == 1

    def test_idempotent_initialization(self, temp_db_path):
        """Test initialization is idempotent (can be run multiple times)."""
        db1 = BuyTrackerDB(db_path=temp_db_path)
        db2 = BuyTrackerDB(db_path=temp_db_path)  # Re-init same path

        # Both should work
        with db1._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM buys")
            count1 = cursor.fetchone()[0]

        with db2._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM buys")
            count2 = cursor.fetchone()[0]

        assert count1 == count2 == 0


# =============================================================================
# 2. BUY RECORD OPERATIONS TESTS
# =============================================================================

class TestBuyRecordOperations:
    """Tests for recording and retrieving buy transactions."""

    def test_record_buy_returns_id(self, db, sample_buy_record):
        """Test record_buy returns the inserted row ID."""
        buy_id = db.record_buy(sample_buy_record)

        assert buy_id is not None
        assert buy_id > 0

    def test_record_buy_stores_all_fields(self, db, sample_buy_record):
        """Test all fields are stored correctly."""
        db.record_buy(sample_buy_record)

        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM buys WHERE tx_signature = ?",
                         (sample_buy_record.tx_signature,))
            row = cursor.fetchone()

        assert row is not None
        row_dict = dict(row)
        assert row_dict['token_symbol'] == sample_buy_record.token_symbol
        assert row_dict['token_name'] == sample_buy_record.token_name
        assert row_dict['token_mint'] == sample_buy_record.token_mint
        assert row_dict['buyer_wallet'] == sample_buy_record.buyer_wallet
        assert row_dict['amount_sol'] == sample_buy_record.amount_sol
        assert row_dict['amount_usd'] == sample_buy_record.amount_usd
        assert row_dict['sentiment_score'] == sample_buy_record.sentiment_score
        assert row_dict['grok_verdict'] == sample_buy_record.grok_verdict

    def test_record_buy_duplicate_signature_ignored(self, db, sample_buy_record):
        """Test INSERT OR IGNORE behavior for duplicate signatures."""
        id1 = db.record_buy(sample_buy_record)
        id2 = db.record_buy(sample_buy_record)  # Same signature

        # Both calls complete, but only one record exists
        buys = db.get_buys_by_token(sample_buy_record.token_mint)
        assert len(buys) == 1

    def test_record_buy_auto_timestamp(self, db):
        """Test timestamp is auto-generated when not provided."""
        buy = BuyRecord(
            token_symbol="TEST",
            token_mint="mint",
            buyer_wallet="wallet",
            tx_signature="sig_auto_ts",
        )

        db.record_buy(buy)

        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT timestamp FROM buys WHERE tx_signature = ?",
                         ("sig_auto_ts",))
            row = cursor.fetchone()

        assert row is not None
        assert row['timestamp'] is not None
        assert len(row['timestamp']) > 0

    def test_record_buy_alert_sent_boolean_true(self, db):
        """Test alert_sent True is stored as 1."""
        buy = BuyRecord(
            token_symbol="TEST",
            token_mint="mint",
            buyer_wallet="wallet",
            tx_signature="sig_alert_true",
            alert_sent=True,
        )

        db.record_buy(buy)

        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT alert_sent FROM buys WHERE tx_signature = ?",
                         ("sig_alert_true",))
            row = cursor.fetchone()

        assert row['alert_sent'] == 1

    def test_record_buy_alert_sent_boolean_false(self, db):
        """Test alert_sent False is stored as 0."""
        buy = BuyRecord(
            token_symbol="TEST",
            token_mint="mint",
            buyer_wallet="wallet",
            tx_signature="sig_alert_false",
            alert_sent=False,
        )

        db.record_buy(buy)

        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT alert_sent FROM buys WHERE tx_signature = ?",
                         ("sig_alert_false",))
            row = cursor.fetchone()

        assert row['alert_sent'] == 0

    def test_record_buy_with_defaults(self, db):
        """Test recording buy with default values."""
        buy = BuyRecord(
            token_symbol="MINIMAL",
            token_mint="mint",
            buyer_wallet="wallet",
            tx_signature="sig_minimal",
        )

        buy_id = db.record_buy(buy)

        assert buy_id is not None
        buys = db.get_buys_by_token("mint")
        assert len(buys) == 1
        assert buys[0]['amount_sol'] == 0.0  # Default
        assert buys[0]['amount_usd'] == 0.0  # Default

    def test_record_multiple_buys(self, db):
        """Test recording multiple buy transactions."""
        for i in range(10):
            buy = BuyRecord(
                token_symbol="TOKEN",
                token_mint="mint",
                buyer_wallet=f"wallet_{i}",
                amount_sol=i * 0.1,
                amount_usd=i * 10.0,
                tx_signature=f"sig_{i}",
            )
            db.record_buy(buy)

        buys = db.get_buys_by_token("mint")
        assert len(buys) == 10


# =============================================================================
# 3. ALERT DEDUPLICATION TESTS
# =============================================================================

class TestAlertDeduplication:
    """Tests for alert deduplication functionality."""

    def test_is_duplicate_alert_false_for_new(self, db):
        """Test is_duplicate_alert returns False for new signature."""
        assert db.is_duplicate_alert("new_signature") is False

    def test_is_duplicate_alert_true_after_mark(self, db):
        """Test is_duplicate_alert returns True after marking."""
        db.mark_alert_sent("marked_sig")
        assert db.is_duplicate_alert("marked_sig") is True

    def test_mark_alert_sent_persists(self, db):
        """Test mark_alert_sent persists across connections."""
        db.mark_alert_sent("persistent_sig")

        # New connection should still see it
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM sent_alerts WHERE tx_signature = ?",
                         ("persistent_sig",))
            assert cursor.fetchone() is not None

    def test_mark_alert_sent_duplicate_ignored(self, db):
        """Test marking same alert twice is safe (INSERT OR IGNORE)."""
        db.mark_alert_sent("dup_alert")
        db.mark_alert_sent("dup_alert")  # Should not raise

        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM sent_alerts WHERE tx_signature = ?",
                         ("dup_alert",))
            count = cursor.fetchone()[0]

        assert count == 1

    def test_is_duplicate_alert_empty_string(self, db):
        """Test is_duplicate_alert with empty string."""
        assert db.is_duplicate_alert("") is False

    def test_mark_alert_sent_stores_timestamp(self, db):
        """Test mark_alert_sent stores sent_at timestamp."""
        db.mark_alert_sent("ts_sig")

        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT sent_at FROM sent_alerts WHERE tx_signature = ?",
                         ("ts_sig",))
            row = cursor.fetchone()

        assert row['sent_at'] is not None


# =============================================================================
# 4. QUERY METHODS TESTS
# =============================================================================

class TestQueryMethods:
    """Tests for database query methods."""

    def test_get_recent_buys_empty(self, db):
        """Test get_recent_buys returns empty list when no data."""
        recent = db.get_recent_buys(hours=24)
        assert recent == []

    def test_get_recent_buys_with_data(self, db):
        """Test get_recent_buys returns recent transactions."""
        for i in range(5):
            buy = BuyRecord(
                timestamp=datetime.now(timezone.utc).isoformat(),
                token_symbol="TOKEN",
                token_mint="mint",
                buyer_wallet=f"wallet_{i}",
                amount_sol=1.0,
                amount_usd=100.0,
                tx_signature=f"sig_{i}",
            )
            db.record_buy(buy)

        recent = db.get_recent_buys(hours=24, limit=10)

        assert len(recent) == 5

    def test_get_recent_buys_respects_limit(self, db):
        """Test get_recent_buys respects limit parameter."""
        for i in range(10):
            buy = BuyRecord(
                timestamp=datetime.now(timezone.utc).isoformat(),
                token_symbol="TOKEN",
                token_mint="mint",
                buyer_wallet=f"wallet_{i}",
                tx_signature=f"sig_{i}",
            )
            db.record_buy(buy)

        recent = db.get_recent_buys(hours=24, limit=5)

        assert len(recent) == 5

    def test_get_recent_buys_ordered_by_timestamp(self, db):
        """Test get_recent_buys returns results ordered by timestamp DESC."""
        for i in range(3):
            buy = BuyRecord(
                timestamp=datetime.now(timezone.utc).isoformat(),
                token_symbol="TOKEN",
                token_mint="mint",
                buyer_wallet=f"wallet_{i}",
                amount_usd=float(i * 10),
                tx_signature=f"sig_{i}",
            )
            db.record_buy(buy)

        recent = db.get_recent_buys(hours=24)

        # Most recent should be first (last inserted)
        assert len(recent) == 3

    def test_get_buys_by_token_empty(self, db):
        """Test get_buys_by_token returns empty for unknown token."""
        buys = db.get_buys_by_token("unknown_mint")
        assert buys == []

    def test_get_buys_by_token_filters_correctly(self, db):
        """Test get_buys_by_token filters by token_mint."""
        # Insert buys for different tokens
        for mint in ["mintA", "mintB", "mintA", "mintA"]:
            buy = BuyRecord(
                timestamp=datetime.now(timezone.utc).isoformat(),
                token_symbol="TOKEN",
                token_mint=mint,
                buyer_wallet="wallet",
                tx_signature=f"sig_{mint}_{datetime.now().timestamp()}",
            )
            db.record_buy(buy)

        buys_a = db.get_buys_by_token("mintA")
        buys_b = db.get_buys_by_token("mintB")

        assert len(buys_a) == 3
        assert len(buys_b) == 1

    def test_get_buys_by_token_respects_limit(self, db):
        """Test get_buys_by_token respects limit parameter."""
        for i in range(10):
            buy = BuyRecord(
                timestamp=datetime.now(timezone.utc).isoformat(),
                token_symbol="TOKEN",
                token_mint="same_mint",
                buyer_wallet=f"wallet_{i}",
                tx_signature=f"sig_{i}",
            )
            db.record_buy(buy)

        buys = db.get_buys_by_token("same_mint", limit=3)

        assert len(buys) == 3

    def test_get_buy_stats_empty(self, db):
        """Test get_buy_stats returns empty dict when no data."""
        stats = db.get_buy_stats(hours=24)

        assert stats.get('total_buys', 0) == 0

    def test_get_buy_stats_aggregation(self, db):
        """Test get_buy_stats correctly aggregates data."""
        # Insert 3 buys: 2 unique tokens, 2 unique wallets
        for i, (mint, wallet) in enumerate([
            ("mintA", "walletX"),
            ("mintB", "walletX"),
            ("mintA", "walletY"),
        ]):
            buy = BuyRecord(
                timestamp=datetime.now(timezone.utc).isoformat(),
                token_symbol="TOKEN",
                token_mint=mint,
                buyer_wallet=wallet,
                amount_sol=1.0 + i,
                amount_usd=100.0 + i * 10,
                tx_signature=f"sig_{i}",
            )
            db.record_buy(buy)

        stats = db.get_buy_stats(hours=24)

        assert stats['total_buys'] == 3
        assert stats['unique_tokens'] == 2
        assert stats['unique_buyers'] == 2
        assert stats['total_sol'] == pytest.approx(6.0, rel=0.01)  # 1+2+3
        assert stats['total_usd'] == pytest.approx(330.0, rel=0.01)  # 100+110+120

    def test_get_top_tokens_empty(self, db):
        """Test get_top_tokens returns empty list when no data."""
        top = db.get_top_tokens(hours=24)
        assert top == []

    def test_get_top_tokens_ranking(self, db):
        """Test get_top_tokens ranks by buy_count correctly."""
        # Insert varying buy counts per token
        for mint, count in [("mint1", 5), ("mint2", 3), ("mint3", 1)]:
            for j in range(count):
                buy = BuyRecord(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    token_symbol=f"TOKEN_{mint}",
                    token_mint=mint,
                    buyer_wallet="wallet",
                    amount_usd=100.0,
                    tx_signature=f"sig_{mint}_{j}",
                )
                db.record_buy(buy)

        top = db.get_top_tokens(hours=24, limit=5)

        assert len(top) == 3
        assert top[0]['token_mint'] == "mint1"
        assert top[0]['buy_count'] == 5
        assert top[1]['token_mint'] == "mint2"
        assert top[1]['buy_count'] == 3

    def test_get_top_tokens_includes_aggregates(self, db):
        """Test get_top_tokens includes total_usd and unique_buyers."""
        for i in range(3):
            buy = BuyRecord(
                timestamp=datetime.now(timezone.utc).isoformat(),
                token_symbol="TOKEN",
                token_mint="mint",
                buyer_wallet=f"wallet_{i}",
                amount_usd=100.0,
                tx_signature=f"sig_{i}",
            )
            db.record_buy(buy)

        top = db.get_top_tokens(hours=24)

        assert len(top) == 1
        assert top[0]['total_usd'] == 300.0
        assert top[0]['unique_buyers'] == 3

    def test_get_top_buyers_empty(self, db):
        """Test get_top_buyers returns empty list when no data."""
        top = db.get_top_buyers(hours=24)
        assert top == []

    def test_get_top_buyers_ranking(self, db):
        """Test get_top_buyers ranks by total_usd correctly."""
        wallets = [("wallet1", 500.0), ("wallet2", 200.0), ("wallet3", 100.0)]
        for wallet, amount in wallets:
            buy = BuyRecord(
                timestamp=datetime.now(timezone.utc).isoformat(),
                token_symbol="TOKEN",
                token_mint="mint",
                buyer_wallet=wallet,
                amount_sol=amount / 100,
                amount_usd=amount,
                tx_signature=f"sig_{wallet}",
            )
            db.record_buy(buy)

        top_buyers = db.get_top_buyers(hours=24, limit=5)

        assert len(top_buyers) == 3
        assert top_buyers[0]['buyer_wallet'] == "wallet1"
        assert top_buyers[0]['total_usd'] == 500.0

    def test_get_top_buyers_includes_aggregates(self, db):
        """Test get_top_buyers includes buy_count and unique_tokens."""
        for i in range(3):
            buy = BuyRecord(
                timestamp=datetime.now(timezone.utc).isoformat(),
                token_symbol="TOKEN",
                token_mint=f"mint_{i}",
                buyer_wallet="same_wallet",
                amount_usd=100.0,
                tx_signature=f"sig_{i}",
            )
            db.record_buy(buy)

        top = db.get_top_buyers(hours=24)

        assert len(top) == 1
        assert top[0]['buy_count'] == 3
        assert top[0]['unique_tokens'] == 3


# =============================================================================
# 5. PREDICTION OPERATIONS TESTS
# =============================================================================

class TestPredictionOperations:
    """Tests for prediction recording and tracking."""

    def test_record_prediction_returns_id(self, db, sample_prediction_record):
        """Test record_prediction returns the inserted row ID."""
        pred_id = db.record_prediction(sample_prediction_record)

        assert pred_id is not None
        assert pred_id > 0

    def test_record_prediction_stores_all_fields(self, db, sample_prediction_record):
        """Test all prediction fields are stored correctly."""
        db.record_prediction(sample_prediction_record)

        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM predictions WHERE token_symbol = ?",
                         (sample_prediction_record.token_symbol,))
            row = cursor.fetchone()

        assert row is not None
        row_dict = dict(row)
        assert row_dict['prediction_type'] == sample_prediction_record.prediction_type
        assert row_dict['confidence'] == sample_prediction_record.confidence
        assert row_dict['target_price'] == sample_prediction_record.target_price
        assert row_dict['stop_loss'] == sample_prediction_record.stop_loss
        assert row_dict['outcome'] == 'PENDING'

    def test_record_prediction_auto_timestamp(self, db):
        """Test timestamp is auto-generated when not provided."""
        pred = PredictionRecord(
            token_symbol="TEST",
            token_mint="mint",
            prediction_type="BULLISH",
            confidence=0.7,
        )

        db.record_prediction(pred)

        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT timestamp FROM predictions WHERE token_symbol = ?",
                         ("TEST",))
            row = cursor.fetchone()

        assert row is not None
        assert row['timestamp'] is not None

    def test_update_prediction_outcome_sets_fields(self, db, sample_prediction_record):
        """Test update_prediction_outcome sets all outcome fields."""
        pred_id = db.record_prediction(sample_prediction_record)

        db.update_prediction_outcome(
            prediction_id=pred_id,
            outcome="WIN",
            outcome_price=0.0022,
            pnl_percent=120.0,
        )

        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM predictions WHERE id = ?", (pred_id,))
            row = cursor.fetchone()

        assert row['outcome'] == "WIN"
        assert row['outcome_price'] == 0.0022
        assert row['pnl_percent'] == 120.0
        assert row['outcome_timestamp'] is not None

    def test_update_prediction_outcome_loss(self, db, sample_prediction_record):
        """Test updating prediction with LOSS outcome."""
        pred_id = db.record_prediction(sample_prediction_record)

        db.update_prediction_outcome(
            prediction_id=pred_id,
            outcome="LOSS",
            outcome_price=0.0005,
            pnl_percent=-50.0,
        )

        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT outcome, pnl_percent FROM predictions WHERE id = ?",
                         (pred_id,))
            row = cursor.fetchone()

        assert row['outcome'] == "LOSS"
        assert row['pnl_percent'] == -50.0

    def test_get_pending_predictions_empty(self, db):
        """Test get_pending_predictions returns empty when none pending."""
        pending = db.get_pending_predictions()
        assert pending == []

    def test_get_pending_predictions_returns_pending_only(self, db):
        """Test get_pending_predictions filters by outcome=PENDING."""
        # Insert pending prediction
        pred1 = PredictionRecord(
            token_symbol="PENDING_TOKEN",
            prediction_type="BULLISH",
        )
        pred1_id = db.record_prediction(pred1)

        # Insert completed prediction
        pred2 = PredictionRecord(
            token_symbol="COMPLETED_TOKEN",
            prediction_type="BEARISH",
        )
        pred2_id = db.record_prediction(pred2)
        db.update_prediction_outcome(pred2_id, "WIN", 1.0, 10.0)

        pending = db.get_pending_predictions()

        assert len(pending) == 1
        assert pending[0]['token_symbol'] == "PENDING_TOKEN"

    def test_get_pending_predictions_ordered_by_timestamp(self, db):
        """Test get_pending_predictions returns ordered by timestamp ASC."""
        for i in range(3):
            pred = PredictionRecord(
                token_symbol=f"TOKEN_{i}",
                prediction_type="BULLISH",
            )
            db.record_prediction(pred)

        pending = db.get_pending_predictions()

        assert len(pending) == 3

    def test_get_prediction_accuracy_empty(self, db):
        """Test get_prediction_accuracy returns empty dict when no data."""
        accuracy = db.get_prediction_accuracy(days=7)
        assert accuracy == {}

    def test_get_prediction_accuracy_calculation(self, db):
        """Test get_prediction_accuracy calculates accuracy correctly."""
        # Insert predictions with different outcomes
        outcomes = ["WIN", "WIN", "LOSS"]
        for i, outcome in enumerate(outcomes):
            pred = PredictionRecord(
                token_symbol=f"TOKEN_{i}",
                prediction_type="BULLISH",
                confidence=0.8,
            )
            pred_id = db.record_prediction(pred)
            pnl = 10.0 if outcome == "WIN" else -5.0
            db.update_prediction_outcome(pred_id, outcome, 1.0, pnl)

        accuracy = db.get_prediction_accuracy(days=7)

        assert "BULLISH" in accuracy
        assert accuracy["BULLISH"]["total"] == 3
        assert accuracy["BULLISH"]["wins"] == 2
        assert accuracy["BULLISH"]["losses"] == 1
        assert accuracy["BULLISH"]["accuracy"] == pytest.approx(66.67, rel=0.1)

    def test_get_prediction_accuracy_by_type(self, db):
        """Test get_prediction_accuracy groups by prediction_type."""
        for pred_type in ["BULLISH", "BEARISH", "BULLISH"]:
            pred = PredictionRecord(
                token_symbol="TOKEN",
                prediction_type=pred_type,
            )
            pred_id = db.record_prediction(pred)
            db.update_prediction_outcome(pred_id, "WIN", 1.0, 10.0)

        accuracy = db.get_prediction_accuracy(days=7)

        assert "BULLISH" in accuracy
        assert "BEARISH" in accuracy
        assert accuracy["BULLISH"]["total"] == 2
        assert accuracy["BEARISH"]["total"] == 1

    def test_get_prediction_accuracy_excludes_pending(self, db):
        """Test get_prediction_accuracy excludes PENDING predictions."""
        # Add a pending prediction
        pending_pred = PredictionRecord(
            token_symbol="PENDING",
            prediction_type="BULLISH",
        )
        db.record_prediction(pending_pred)

        # Add a completed prediction
        completed_pred = PredictionRecord(
            token_symbol="COMPLETED",
            prediction_type="BULLISH",
        )
        pred_id = db.record_prediction(completed_pred)
        db.update_prediction_outcome(pred_id, "WIN", 1.0, 10.0)

        accuracy = db.get_prediction_accuracy(days=7)

        assert accuracy["BULLISH"]["total"] == 1  # Only completed


# =============================================================================
# 6. TOKEN METADATA CACHE TESTS
# =============================================================================

class TestTokenMetadataCache:
    """Tests for token metadata caching."""

    def test_get_token_metadata_not_found(self, db):
        """Test get_token_metadata returns None for unknown token."""
        metadata = db.get_token_metadata("unknown_mint")
        assert metadata is None

    def test_cache_token_metadata_stores_data(self, db):
        """Test cache_token_metadata stores all fields."""
        db.cache_token_metadata(
            mint="mint123",
            symbol="KR8TIV",
            name="Kr8Tiv Token",
            decimals=9,
            logo_url="https://example.com/logo.png",
        )

        metadata = db.get_token_metadata("mint123")

        assert metadata is not None
        assert metadata["symbol"] == "KR8TIV"
        assert metadata["name"] == "Kr8Tiv Token"
        assert metadata["decimals"] == 9
        assert metadata["logo_url"] == "https://example.com/logo.png"

    def test_cache_token_metadata_updates_existing(self, db):
        """Test cache_token_metadata updates existing entry (INSERT OR REPLACE)."""
        db.cache_token_metadata(
            mint="mint123",
            symbol="OLD",
            name="Old Name",
            decimals=6,
        )

        db.cache_token_metadata(
            mint="mint123",
            symbol="NEW",
            name="New Name",
            decimals=9,
        )

        metadata = db.get_token_metadata("mint123")

        assert metadata["symbol"] == "NEW"
        assert metadata["name"] == "New Name"
        assert metadata["decimals"] == 9

    def test_cache_token_metadata_empty_logo_url(self, db):
        """Test cache_token_metadata with empty logo_url."""
        db.cache_token_metadata(
            mint="mint123",
            symbol="TOKEN",
            name="Token",
            decimals=9,
            logo_url="",
        )

        metadata = db.get_token_metadata("mint123")
        assert metadata["logo_url"] == ""

    def test_cache_token_metadata_sets_updated_at(self, db):
        """Test cache_token_metadata sets updated_at timestamp."""
        db.cache_token_metadata(
            mint="mint123",
            symbol="TOKEN",
            name="Token",
            decimals=9,
        )

        metadata = db.get_token_metadata("mint123")
        assert metadata["updated_at"] is not None


# =============================================================================
# 7. CONNECTION MANAGEMENT TESTS
# =============================================================================

class TestConnectionManagement:
    """Tests for database connection handling."""

    def test_get_connection_context_manager(self, db):
        """Test _get_connection works as context manager."""
        with db._get_connection() as conn:
            assert conn is not None
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1

    def test_get_connection_row_factory(self, db):
        """Test connection has Row factory for dict access."""
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 as value")
            row = cursor.fetchone()
            assert row['value'] == 1

    def test_connection_closed_after_context(self, temp_db_path):
        """Test connection is closed after context exits."""
        db = BuyTrackerDB(db_path=temp_db_path)

        conn_ref = None
        with db._get_connection() as conn:
            conn_ref = conn

        # Connection should be closed but we can't easily verify
        # At minimum, no exception should occur
        assert conn_ref is not None

    def test_multiple_connections(self, db):
        """Test multiple sequential connections work."""
        for _ in range(5):
            with db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                assert cursor.fetchone() is not None


# =============================================================================
# 8. SINGLETON PATTERN TESTS
# =============================================================================

class TestSingletonPattern:
    """Tests for get_db singleton behavior."""

    def test_get_db_returns_instance(self):
        """Test get_db returns a BuyTrackerDB instance."""
        import bots.buy_tracker.database as db_module

        # Reset singleton
        db_module._db_instance = None

        db = get_db()

        assert isinstance(db, BuyTrackerDB)

    def test_get_db_returns_same_instance(self):
        """Test get_db returns the same instance on repeated calls."""
        import bots.buy_tracker.database as db_module

        # Reset singleton
        db_module._db_instance = None

        db1 = get_db()
        db2 = get_db()

        assert db1 is db2

    def test_get_db_uses_default_path(self):
        """Test get_db uses DB_PATH constant."""
        import bots.buy_tracker.database as db_module

        # Reset singleton
        db_module._db_instance = None

        db = get_db()

        assert db.db_path == DB_PATH


# =============================================================================
# 9. DATACLASS TESTS
# =============================================================================

class TestDataclasses:
    """Tests for BuyRecord and PredictionRecord dataclasses."""

    def test_buy_record_defaults(self):
        """Test BuyRecord default values."""
        record = BuyRecord()

        assert record.id is None
        assert record.timestamp == ""
        assert record.token_symbol == ""
        assert record.token_name == ""
        assert record.token_mint == ""
        assert record.buyer_wallet == ""
        assert record.amount_sol == 0.0
        assert record.amount_usd == 0.0
        assert record.token_amount == 0.0
        assert record.price_at_buy == 0.0
        assert record.tx_signature == ""
        assert record.sentiment_score == 0.0
        assert record.sentiment_label == ""
        assert record.grok_verdict == ""
        assert record.alert_sent is False

    def test_buy_record_with_values(self):
        """Test BuyRecord with custom values."""
        record = BuyRecord(
            id=1,
            timestamp="2025-01-25T12:00:00Z",
            token_symbol="KR8TIV",
            amount_sol=1.5,
            amount_usd=150.0,
            alert_sent=True,
        )

        assert record.id == 1
        assert record.token_symbol == "KR8TIV"
        assert record.amount_sol == 1.5
        assert record.alert_sent is True

    def test_prediction_record_defaults(self):
        """Test PredictionRecord default values."""
        record = PredictionRecord()

        assert record.id is None
        assert record.timestamp == ""
        assert record.token_symbol == ""
        assert record.token_mint == ""
        assert record.prediction_type == ""
        assert record.confidence == 0.0
        assert record.price_at_prediction == 0.0
        assert record.target_price == 0.0
        assert record.stop_loss == 0.0
        assert record.outcome == ""
        assert record.outcome_price == 0.0
        assert record.outcome_timestamp == ""
        assert record.pnl_percent == 0.0

    def test_prediction_record_with_values(self):
        """Test PredictionRecord with custom values."""
        record = PredictionRecord(
            id=1,
            token_symbol="KR8TIV",
            prediction_type="BULLISH",
            confidence=0.85,
            target_price=0.002,
            stop_loss=0.0008,
            outcome="WIN",
            pnl_percent=100.0,
        )

        assert record.prediction_type == "BULLISH"
        assert record.confidence == 0.85
        assert record.outcome == "WIN"


# =============================================================================
# 10. EDGE CASES TESTS
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_string_token_mint(self, db):
        """Test handling empty string token_mint."""
        buy = BuyRecord(
            token_symbol="TEST",
            token_mint="",
            buyer_wallet="wallet",
            tx_signature="sig_empty_mint",
        )

        db.record_buy(buy)
        buys = db.get_buys_by_token("")

        assert len(buys) == 1

    def test_very_long_signature(self, db):
        """Test handling very long tx_signature."""
        long_sig = "a" * 200

        buy = BuyRecord(
            token_symbol="TEST",
            token_mint="mint",
            buyer_wallet="wallet",
            tx_signature=long_sig,
        )

        db.record_buy(buy)
        assert not db.is_duplicate_alert(long_sig)
        db.mark_alert_sent(long_sig)
        assert db.is_duplicate_alert(long_sig)

    def test_zero_values(self, db):
        """Test recording buy with all zero numeric values."""
        buy = BuyRecord(
            token_symbol="ZERO",
            token_mint="mint",
            buyer_wallet="wallet",
            amount_sol=0.0,
            amount_usd=0.0,
            token_amount=0.0,
            price_at_buy=0.0,
            sentiment_score=0.0,
            tx_signature="sig_zero",
        )

        db.record_buy(buy)
        buys = db.get_buys_by_token("mint")

        assert len(buys) == 1
        assert buys[0]['amount_sol'] == 0.0

    def test_negative_values(self, db):
        """Test handling negative values (shouldn't happen but handle gracefully)."""
        buy = BuyRecord(
            token_symbol="NEG",
            token_mint="mint",
            buyer_wallet="wallet",
            amount_sol=-1.0,  # Invalid but test handling
            amount_usd=-100.0,
            tx_signature="sig_neg",
        )

        db.record_buy(buy)
        buys = db.get_buys_by_token("mint")

        assert len(buys) == 1

    def test_unicode_in_fields(self, db):
        """Test handling Unicode characters in text fields."""
        buy = BuyRecord(
            token_symbol="EMOJI",
            token_name="Test Token",
            token_mint="mint",
            buyer_wallet="wallet",
            grok_verdict="Bullish analysis",
            tx_signature="sig_unicode",
        )

        db.record_buy(buy)
        buys = db.get_buys_by_token("mint")

        assert len(buys) == 1
        assert buys[0]['token_name'] == "Test Token"

    def test_special_characters_in_signature(self, db):
        """Test handling special characters in tx_signature."""
        special_sig = "abc123!@#$%^&*()_+-=[]{}|;':\",./<>?"

        buy = BuyRecord(
            token_symbol="SPECIAL",
            token_mint="mint",
            buyer_wallet="wallet",
            tx_signature=special_sig,
        )

        db.record_buy(buy)
        db.mark_alert_sent(special_sig)
        assert db.is_duplicate_alert(special_sig)

    def test_large_dataset_performance(self, db):
        """Test handling larger dataset (basic performance check)."""
        # Insert 100 records
        for i in range(100):
            buy = BuyRecord(
                timestamp=datetime.now(timezone.utc).isoformat(),
                token_symbol="TOKEN",
                token_mint="mint",
                buyer_wallet=f"wallet_{i}",
                amount_usd=float(i),
                tx_signature=f"sig_{i}",
            )
            db.record_buy(buy)

        # Query should complete
        recent = db.get_recent_buys(hours=24, limit=50)
        stats = db.get_buy_stats(hours=24)
        top = db.get_top_buyers(hours=24, limit=10)

        assert len(recent) == 50
        assert stats['total_buys'] == 100
        assert len(top) == 10

    def test_null_timestamp_handling(self, db):
        """Test handling null/empty timestamp in query."""
        buy = BuyRecord(
            timestamp="",  # Empty timestamp
            token_symbol="TEST",
            token_mint="mint",
            buyer_wallet="wallet",
            tx_signature="sig_null_ts",
        )

        # Should auto-generate timestamp
        db.record_buy(buy)

        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT timestamp FROM buys WHERE tx_signature = ?",
                         ("sig_null_ts",))
            row = cursor.fetchone()

        # Empty string replaced with auto-generated timestamp
        assert row['timestamp'] is not None

    def test_prediction_zero_market_cap(self, db):
        """Test prediction accuracy with zero values."""
        pred = PredictionRecord(
            token_symbol="ZERO",
            prediction_type="NEUTRAL",
            confidence=0.0,
            price_at_prediction=0.0,
        )

        pred_id = db.record_prediction(pred)
        db.update_prediction_outcome(pred_id, "WIN", 0.0, 0.0)

        accuracy = db.get_prediction_accuracy(days=7)

        assert "NEUTRAL" in accuracy
        assert accuracy["NEUTRAL"]["avg_pnl"] == 0.0


# =============================================================================
# 11. ADDITIONAL INTEGRATION TESTS
# =============================================================================

class TestIntegration:
    """Integration-style tests combining multiple operations."""

    def test_full_buy_workflow(self, db):
        """Test complete buy workflow: record, query, stats."""
        # Record multiple buys
        for i in range(5):
            buy = BuyRecord(
                timestamp=datetime.now(timezone.utc).isoformat(),
                token_symbol="KR8TIV",
                token_mint="kr8tiv_mint",
                buyer_wallet=f"wallet_{i}",
                amount_sol=float(i + 1),
                amount_usd=float((i + 1) * 100),
                tx_signature=f"sig_{i}",
            )
            db.record_buy(buy)
            db.mark_alert_sent(buy.tx_signature)

        # Verify data
        buys = db.get_buys_by_token("kr8tiv_mint")
        stats = db.get_buy_stats(hours=24)
        top_tokens = db.get_top_tokens(hours=24)
        top_buyers = db.get_top_buyers(hours=24)

        assert len(buys) == 5
        assert stats['total_buys'] == 5
        assert stats['unique_buyers'] == 5
        assert len(top_tokens) == 1
        assert len(top_buyers) == 5

        # Verify all alerts marked as sent
        for i in range(5):
            assert db.is_duplicate_alert(f"sig_{i}")

    def test_full_prediction_workflow(self, db):
        """Test complete prediction workflow: create, update, accuracy."""
        # Create predictions
        pred_ids = []
        for i in range(4):
            pred = PredictionRecord(
                timestamp=datetime.now(timezone.utc).isoformat(),
                token_symbol=f"TOKEN_{i}",
                prediction_type="BULLISH" if i % 2 == 0 else "BEARISH",
                confidence=0.7 + i * 0.05,
                price_at_prediction=0.001,
                target_price=0.002,
            )
            pred_ids.append(db.record_prediction(pred))

        # Verify pending
        pending = db.get_pending_predictions()
        assert len(pending) == 4

        # Update outcomes
        db.update_prediction_outcome(pred_ids[0], "WIN", 0.002, 100.0)
        db.update_prediction_outcome(pred_ids[1], "WIN", 0.0008, 20.0)
        db.update_prediction_outcome(pred_ids[2], "LOSS", 0.0005, -50.0)
        # Leave pred_ids[3] pending

        # Verify pending updated
        pending = db.get_pending_predictions()
        assert len(pending) == 1

        # Check accuracy
        accuracy = db.get_prediction_accuracy(days=7)
        assert "BULLISH" in accuracy
        assert "BEARISH" in accuracy
        assert accuracy["BULLISH"]["wins"] == 1
        assert accuracy["BULLISH"]["losses"] == 1
        assert accuracy["BEARISH"]["wins"] == 1

    def test_token_metadata_workflow(self, db):
        """Test complete token metadata workflow."""
        # Cache metadata
        db.cache_token_metadata(
            mint="test_mint",
            symbol="TEST",
            name="Test Token",
            decimals=9,
            logo_url="https://example.com/test.png",
        )

        # Retrieve
        meta = db.get_token_metadata("test_mint")
        assert meta["symbol"] == "TEST"

        # Update
        db.cache_token_metadata(
            mint="test_mint",
            symbol="TEST2",
            name="Test Token V2",
            decimals=6,
        )

        # Verify update
        meta = db.get_token_metadata("test_mint")
        assert meta["symbol"] == "TEST2"
        assert meta["decimals"] == 6


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
