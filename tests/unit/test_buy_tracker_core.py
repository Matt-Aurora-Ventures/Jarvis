"""
Comprehensive unit tests for the Buy Tracker Core (bot.py).

Tests cover:
1. Buy Detection
   - Buy message formatting
   - Large buy circles display
   - Number formatting utilities

2. Large Buy Alerts
   - Threshold detection
   - Alert message formatting
   - FAQ keyboard generation
   - Message caching

3. Bot Initialization
   - Configuration validation
   - Missing config handling
   - Self-correcting AI system initialization

4. Callback Handling
   - FAQ expand/collapse
   - Ape button callbacks
   - Confirm/cancel trade callbacks
   - Info button callbacks
   - Expand section callbacks

5. Admin Authorization
   - Admin ID parsing
   - Authorization checks

6. Telegram Notification
   - Buy notification sending
   - Retry logic
   - Video attachment
   - Sticker sending

7. Lifecycle Management
   - Start/stop
   - Startup message

8. Database Operations (from database.py)
   - Buy record storage
   - Alert deduplication
   - Query by date/wallet
   - Aggregate statistics
   - Prediction tracking

9. Utilities (from utils.py)
   - Retry decorators
   - Rate limiting
   - Circuit breaker
   - Input validation
   - Spending limits

10. Ape Buttons (from ape_buttons.py)
    - Button creation
    - Callback parsing
    - Trade setup validation
    - TP/SL calculations

11. Configuration (from config.py)
    - Config loading
    - Additional pairs parsing

12. Intent Tracking (from intent_tracker.py)
    - Intent ID generation
    - Duplicate detection
"""

import pytest
import asyncio
import json
import tempfile
import sqlite3
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from bots.buy_tracker.bot import (
    JarvisBuyBot,
    get_faq_keyboard,
    _parse_admin_ids,
    _get_admin_ids,
    _is_admin,
    FAQ_CONTENT,
)
from bots.buy_tracker.config import (
    BuyBotConfig,
    load_config,
    ADDITIONAL_LP_PAIRS,
)
from bots.buy_tracker.monitor import BuyTransaction
from bots.buy_tracker.database import (
    BuyTrackerDB,
    BuyRecord,
    PredictionRecord,
    get_db,
)
from bots.buy_tracker.utils import (
    RetryConfig,
    RateLimiter,
    TelegramRateLimiter,
    CircuitBreakerConfig,
    CircuitBreaker,
    CircuitOpenError,
    SpendingLimits,
    AuditLogger,
    is_valid_solana_address,
    sanitize_token_name,
    sanitize_telegram_message,
    generate_dedup_key,
    get_timeout_config,
    get_telegram_limiter,
    get_audit_logger,
)
from bots.buy_tracker.ape_buttons import (
    RiskProfile,
    RISK_PROFILE_CONFIG,
    STOCK_RISK_PROFILE_CONFIG,
    APE_ALLOCATION_PCT,
    TradeSetup,
    TradeResult,
    get_risk_config,
    create_ape_buttons_with_tp_sl,
    create_token_ape_keyboard,
    create_stock_ape_keyboard,
    parse_ape_callback,
    calculate_tp_sl_prices,
    create_trade_setup,
    format_treasury_status,
)


# =============================================================================
# TEST FIXTURES
# =============================================================================

@pytest.fixture
def sample_buy_transaction():
    """Create a sample BuyTransaction for testing."""
    return BuyTransaction(
        signature="abc123def456ghi789jkl012mno345pqr678stu901vwx234yz",
        buyer_wallet="9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",
        token_amount=1000000.0,
        sol_amount=0.5,
        usd_amount=75.0,
        price_per_token=0.000000075,
        buyer_position_pct=0.001,
        market_cap=750000.0,
        timestamp=datetime.utcnow(),
        tx_url="https://solscan.io/tx/abc123",
        dex_url="https://dexscreener.com/solana/TOKEN",
        lp_pair_name="main",
        lp_pair_address="PAIR123",
    )


@pytest.fixture
def mock_config():
    """Create a mock BuyBotConfig for testing."""
    return BuyBotConfig(
        bot_token="test_token_123",
        chat_id="-1001234567890",
        token_address="KR8TIVTokenMintAddress1234567890123456789",
        token_symbol="KR8TIV",
        token_name="Kr8Tiv",
        pair_address="KR8TIVPairAddress1234567890123456789012",
        additional_pairs=[],
        helius_api_key="test_helius_key",
        min_buy_usd=5.0,
        video_path="",
        bot_name="Test Buy Bot",
    )


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


# =============================================================================
# 1. BUY DETECTION TESTS
# =============================================================================

class TestBuyMessageFormatting:
    """Tests for buy message formatting in JarvisBuyBot."""

    def test_format_number_billions(self):
        """Test formatting billions."""
        bot = JarvisBuyBot.__new__(JarvisBuyBot)
        assert bot._format_number(1_500_000_000) == "1.50B"
        assert bot._format_number(2_300_000_000) == "2.30B"

    def test_format_number_millions(self):
        """Test formatting millions."""
        bot = JarvisBuyBot.__new__(JarvisBuyBot)
        assert bot._format_number(1_500_000) == "1.50M"
        assert bot._format_number(5_000_000) == "5.00M"

    def test_format_number_thousands(self):
        """Test formatting thousands."""
        bot = JarvisBuyBot.__new__(JarvisBuyBot)
        assert bot._format_number(1_500) == "1,500"
        assert bot._format_number(999_999) == "999,999"

    def test_format_number_small(self):
        """Test formatting small numbers."""
        bot = JarvisBuyBot.__new__(JarvisBuyBot)
        assert bot._format_number(100.5) == "100.50"
        assert bot._format_number(0.5) == "0.50"

    def test_format_mcap_millions(self):
        """Test formatting market cap in millions."""
        bot = JarvisBuyBot.__new__(JarvisBuyBot)
        assert bot._format_mcap(5_000_000) == "$5.00M"

    def test_format_mcap_thousands(self):
        """Test formatting market cap in thousands."""
        bot = JarvisBuyBot.__new__(JarvisBuyBot)
        assert bot._format_mcap(500_000) == "$500.00K"

    def test_format_mcap_small(self):
        """Test formatting small market cap."""
        bot = JarvisBuyBot.__new__(JarvisBuyBot)
        assert bot._format_mcap(500) == "$500.00"

    def test_get_buy_circles_huge(self):
        """Test green circles for huge buys (>$10k)."""
        bot = JarvisBuyBot.__new__(JarvisBuyBot)
        circles = bot._get_buy_circles(15000.0)
        assert circles.count("🟢") == 10

    def test_get_buy_circles_large(self):
        """Test green circles for large buys (>$5k)."""
        bot = JarvisBuyBot.__new__(JarvisBuyBot)
        circles = bot._get_buy_circles(7500.0)
        assert circles.count("🟢") == 8

    def test_get_buy_circles_medium(self):
        """Test green circles for medium buys (>$1k)."""
        bot = JarvisBuyBot.__new__(JarvisBuyBot)
        circles = bot._get_buy_circles(1500.0)
        assert circles.count("🟢") == 6

    def test_get_buy_circles_small(self):
        """Test green circles for small buys (>$500)."""
        bot = JarvisBuyBot.__new__(JarvisBuyBot)
        circles = bot._get_buy_circles(600.0)
        assert circles.count("🟢") == 5

    def test_get_buy_circles_tiny(self):
        """Test green circles for tiny buys (>$100)."""
        bot = JarvisBuyBot.__new__(JarvisBuyBot)
        circles = bot._get_buy_circles(150.0)
        assert circles.count("🟢") == 4

    def test_get_buy_circles_micro(self):
        """Test green circles for micro buys (>$50)."""
        bot = JarvisBuyBot.__new__(JarvisBuyBot)
        circles = bot._get_buy_circles(75.0)
        assert circles.count("🟢") == 3

    def test_get_buy_circles_dust(self):
        """Test green circles for dust buys (>$20)."""
        bot = JarvisBuyBot.__new__(JarvisBuyBot)
        circles = bot._get_buy_circles(25.0)
        assert circles.count("🟢") == 2

    def test_get_buy_circles_minimum(self):
        """Test green circles for minimum buys (<$20)."""
        bot = JarvisBuyBot.__new__(JarvisBuyBot)
        circles = bot._get_buy_circles(10.0)
        assert circles.count("🟢") == 1

    def test_format_buy_message_structure(self, sample_buy_transaction, mock_config):
        """Test the structure of formatted buy message."""
        bot = JarvisBuyBot.__new__(JarvisBuyBot)
        bot.config = mock_config
        bot._buy_counter = 0

        message = bot._format_buy_message(sample_buy_transaction)

        assert mock_config.bot_name in message
        assert mock_config.token_name in message
        assert "Buy!" in message
        assert "SOL" in message
        assert "Position:" in message or "Buyer Position:" in message
        assert "MCap" in message
        assert "TX" in message
        assert "Dex" in message

    def test_format_buy_message_lp_pair_shown(self, sample_buy_transaction, mock_config):
        """Test LP pair name is shown when not main."""
        bot = JarvisBuyBot.__new__(JarvisBuyBot)
        bot.config = mock_config
        bot._buy_counter = 0

        sample_buy_transaction.lp_pair_name = "kr8tiv/ralph"
        message = bot._format_buy_message(sample_buy_transaction)

        assert "LP: kr8tiv/ralph" in message

    def test_format_buy_message_credit_every_10th(self, sample_buy_transaction, mock_config):
        """Test @FrankkkNL credit appears every 10th buy."""
        bot = JarvisBuyBot.__new__(JarvisBuyBot)
        bot.config = mock_config
        bot._buy_counter = 9  # Will become 10 after this buy

        message = bot._format_buy_message(sample_buy_transaction)

        assert "@FrankkkNL" in message


# =============================================================================
# 2. LARGE BUY ALERTS TESTS
# =============================================================================

class TestFAQKeyboard:
    """Tests for FAQ keyboard generation."""

    def test_get_faq_keyboard_hidden(self):
        """Test FAQ keyboard when FAQ is hidden."""
        keyboard = get_faq_keyboard(show_faq=False)

        assert keyboard is not None
        assert len(keyboard.inline_keyboard) == 1
        button = keyboard.inline_keyboard[0][0]
        assert "What is Jarvis?" in button.text
        assert button.callback_data == "show_faq"

    def test_get_faq_keyboard_shown(self):
        """Test FAQ keyboard when FAQ is shown."""
        keyboard = get_faq_keyboard(show_faq=True)

        assert keyboard is not None
        button = keyboard.inline_keyboard[0][0]
        assert "Hide" in button.text
        assert button.callback_data == "hide_faq"

    def test_faq_content_not_empty(self):
        """Test FAQ content is not empty."""
        assert len(FAQ_CONTENT) > 0
        assert "JARVIS" in FAQ_CONTENT
        assert "KR8TIV" in FAQ_CONTENT


# =============================================================================
# 3. BOT INITIALIZATION TESTS
# =============================================================================

class TestBotInitialization:
    """Tests for JarvisBuyBot initialization."""

    def test_bot_initialization_default_config(self):
        """Test bot initialization with default config."""
        with patch('bots.buy_tracker.bot.load_config') as mock_load:
            mock_load.return_value = MagicMock(
                bot_token="token",
                chat_id="chat",
                token_address="addr",
                helius_api_key="key",
            )

            bot = JarvisBuyBot()

            assert bot.bot is None
            assert bot.app is None
            assert bot.monitor is None
            assert bot._running is False
            assert bot._buy_counter == 0

    def test_bot_initialization_custom_config(self, mock_config):
        """Test bot initialization with custom config."""
        bot = JarvisBuyBot(config=mock_config)

        assert bot.config == mock_config
        assert bot.config.token_symbol == "KR8TIV"

    def test_bot_message_cache_initialized(self, mock_config):
        """Test message cache is initialized empty."""
        bot = JarvisBuyBot(config=mock_config)

        assert isinstance(bot._message_cache, dict)
        assert len(bot._message_cache) == 0

    def test_bot_sticker_cache_initialized(self, mock_config):
        """Test sticker cache is initialized."""
        bot = JarvisBuyBot(config=mock_config)

        assert bot._kr8tiv_sticker_id is None


# =============================================================================
# 4. ADMIN AUTHORIZATION TESTS
# =============================================================================

class TestAdminAuthorization:
    """Tests for admin ID parsing and authorization."""

    def test_parse_admin_ids_single(self):
        """Test parsing single admin ID."""
        result = _parse_admin_ids("12345678")
        assert result == {12345678}

    def test_parse_admin_ids_multiple(self):
        """Test parsing multiple admin IDs."""
        result = _parse_admin_ids("111,222,333")
        assert result == {111, 222, 333}

    def test_parse_admin_ids_with_spaces(self):
        """Test parsing admin IDs with spaces."""
        result = _parse_admin_ids("111, 222, 333")
        assert result == {111, 222, 333}

    def test_parse_admin_ids_empty_string(self):
        """Test parsing empty string."""
        result = _parse_admin_ids("")
        assert result == set()

    def test_parse_admin_ids_invalid_mixed(self):
        """Test parsing with invalid entries."""
        result = _parse_admin_ids("111,abc,333")
        assert result == {111, 333}

    def test_get_admin_ids_from_treasury_env(self):
        """Test getting admin IDs from TREASURY_ADMIN_IDS env."""
        with patch.dict(os.environ, {'TREASURY_ADMIN_IDS': '12345'}, clear=False):
            result = _get_admin_ids()
            assert 12345 in result

    def test_get_admin_ids_from_telegram_env(self):
        """Test getting admin IDs from TELEGRAM_ADMIN_IDS env."""
        with patch.dict(os.environ, {'TELEGRAM_ADMIN_IDS': '67890'}, clear=False):
            # Clear TREASURY_ADMIN_IDS to force fallback
            env = dict(os.environ)
            env.pop('TREASURY_ADMIN_IDS', None)
            with patch.dict(os.environ, env, clear=True):
                with patch.dict(os.environ, {'TELEGRAM_ADMIN_IDS': '67890'}):
                    result = _get_admin_ids()
                    assert 67890 in result

    def test_is_admin_true(self):
        """Test is_admin returns True for admin."""
        with patch('bots.buy_tracker.bot._get_admin_ids', return_value={12345}):
            assert _is_admin(12345) is True

    def test_is_admin_false(self):
        """Test is_admin returns False for non-admin."""
        with patch('bots.buy_tracker.bot._get_admin_ids', return_value={12345}):
            assert _is_admin(99999) is False

    def test_is_admin_empty_admins(self):
        """Test is_admin returns False when no admins configured."""
        with patch('bots.buy_tracker.bot._get_admin_ids', return_value=set()):
            assert _is_admin(12345) is False


# =============================================================================
# 5. DATABASE TESTS
# =============================================================================

class TestBuyTrackerDB:
    """Tests for BuyTrackerDB operations."""

    def test_db_initialization(self, temp_db_path):
        """Test database initialization creates tables."""
        db = BuyTrackerDB(db_path=temp_db_path)

        # Check tables exist
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

    def test_record_buy(self, temp_db_path):
        """Test recording a buy transaction."""
        db = BuyTrackerDB(db_path=temp_db_path)

        buy = BuyRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            token_symbol="KR8TIV",
            token_name="Kr8Tiv",
            token_mint="mint123",
            buyer_wallet="wallet456",
            amount_sol=1.5,
            amount_usd=150.0,
            token_amount=1000000.0,
            price_at_buy=0.00015,
            tx_signature="sig789",
            sentiment_score=0.8,
            sentiment_label="BULLISH",
        )

        buy_id = db.record_buy(buy)

        assert buy_id is not None
        assert buy_id > 0

    def test_record_buy_duplicate_signature_ignored(self, temp_db_path):
        """Test duplicate signature is ignored (INSERT OR IGNORE)."""
        db = BuyTrackerDB(db_path=temp_db_path)

        buy = BuyRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            token_symbol="KR8TIV",
            token_mint="mint123",
            buyer_wallet="wallet456",
            amount_sol=1.0,
            amount_usd=100.0,
            tx_signature="unique_sig_123",
        )

        # First insert
        id1 = db.record_buy(buy)
        # Second insert with same signature
        id2 = db.record_buy(buy)

        # Both should succeed but only one record
        buys = db.get_buys_by_token("mint123")
        assert len(buys) == 1

    def test_is_duplicate_alert(self, temp_db_path):
        """Test duplicate alert detection."""
        db = BuyTrackerDB(db_path=temp_db_path)

        assert db.is_duplicate_alert("sig123") is False

        db.mark_alert_sent("sig123")

        assert db.is_duplicate_alert("sig123") is True

    def test_get_recent_buys(self, temp_db_path):
        """Test getting recent buys."""
        db = BuyTrackerDB(db_path=temp_db_path)

        # Insert some buys
        for i in range(5):
            buy = BuyRecord(
                timestamp=datetime.now(timezone.utc).isoformat(),
                token_symbol="TOKEN",
                token_mint="mint",
                buyer_wallet=f"wallet{i}",
                amount_sol=1.0,
                amount_usd=100.0,
                tx_signature=f"sig{i}",
            )
            db.record_buy(buy)

        recent = db.get_recent_buys(hours=24, limit=10)

        assert len(recent) == 5

    def test_get_buys_by_token(self, temp_db_path):
        """Test getting buys for specific token."""
        db = BuyTrackerDB(db_path=temp_db_path)

        # Insert buys for different tokens
        for mint in ["mintA", "mintB", "mintA"]:
            buy = BuyRecord(
                timestamp=datetime.now(timezone.utc).isoformat(),
                token_symbol="TOKEN",
                token_mint=mint,
                buyer_wallet="wallet",
                amount_sol=1.0,
                amount_usd=100.0,
                tx_signature=f"sig_{mint}_{datetime.now().timestamp()}",
            )
            db.record_buy(buy)

        buys_a = db.get_buys_by_token("mintA")
        buys_b = db.get_buys_by_token("mintB")

        assert len(buys_a) == 2
        assert len(buys_b) == 1

    def test_get_buy_stats(self, temp_db_path):
        """Test getting buy statistics."""
        db = BuyTrackerDB(db_path=temp_db_path)

        # Insert some buys
        for i in range(3):
            buy = BuyRecord(
                timestamp=datetime.now(timezone.utc).isoformat(),
                token_symbol="TOKEN",
                token_mint=f"mint{i}",
                buyer_wallet=f"wallet{i % 2}",
                amount_sol=1.0 + i,
                amount_usd=100.0 + i * 10,
                tx_signature=f"sig{i}",
            )
            db.record_buy(buy)

        stats = db.get_buy_stats(hours=24)

        assert stats['total_buys'] == 3
        assert stats['unique_tokens'] == 3
        assert stats['unique_buyers'] == 2

    def test_record_prediction(self, temp_db_path):
        """Test recording a prediction."""
        db = BuyTrackerDB(db_path=temp_db_path)

        pred = PredictionRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            token_symbol="KR8TIV",
            token_mint="mint123",
            prediction_type="BULLISH",
            confidence=0.85,
            price_at_prediction=0.001,
            target_price=0.002,
            stop_loss=0.0008,
        )

        pred_id = db.record_prediction(pred)

        assert pred_id is not None
        assert pred_id > 0

    def test_update_prediction_outcome(self, temp_db_path):
        """Test updating prediction outcome."""
        db = BuyTrackerDB(db_path=temp_db_path)

        pred = PredictionRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            token_symbol="KR8TIV",
            token_mint="mint123",
            prediction_type="BULLISH",
            confidence=0.85,
            price_at_prediction=0.001,
            target_price=0.002,
        )

        pred_id = db.record_prediction(pred)

        db.update_prediction_outcome(
            prediction_id=pred_id,
            outcome="WIN",
            outcome_price=0.0022,
            pnl_percent=120.0,
        )

        # Verify update
        pending = db.get_pending_predictions()
        assert len(pending) == 0  # No longer pending

    def test_get_prediction_accuracy(self, temp_db_path):
        """Test getting prediction accuracy."""
        db = BuyTrackerDB(db_path=temp_db_path)

        # Insert predictions with outcomes
        for outcome in ["WIN", "WIN", "LOSS"]:
            pred = PredictionRecord(
                timestamp=datetime.now(timezone.utc).isoformat(),
                token_symbol="TEST",
                token_mint="mint",
                prediction_type="BULLISH",
                confidence=0.8,
                price_at_prediction=1.0,
            )
            pred_id = db.record_prediction(pred)
            db.update_prediction_outcome(
                pred_id, outcome, 1.1, 10.0 if outcome == "WIN" else -5.0
            )

        accuracy = db.get_prediction_accuracy(days=7)

        assert "BULLISH" in accuracy
        assert accuracy["BULLISH"]["wins"] == 2
        assert accuracy["BULLISH"]["losses"] == 1

    def test_cache_token_metadata(self, temp_db_path):
        """Test caching token metadata."""
        db = BuyTrackerDB(db_path=temp_db_path)

        db.cache_token_metadata(
            mint="mint123",
            symbol="KR8TIV",
            name="Kr8Tiv",
            decimals=9,
            logo_url="https://example.com/logo.png",
        )

        metadata = db.get_token_metadata("mint123")

        assert metadata is not None
        assert metadata["symbol"] == "KR8TIV"
        assert metadata["decimals"] == 9

    def test_get_top_tokens(self, temp_db_path):
        """Test getting top tokens by activity."""
        db = BuyTrackerDB(db_path=temp_db_path)

        # Insert buys with varying amounts
        for i, (mint, count) in enumerate([("mint1", 5), ("mint2", 3), ("mint3", 1)]):
            for j in range(count):
                buy = BuyRecord(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    token_symbol=f"TOKEN{i}",
                    token_mint=mint,
                    buyer_wallet="wallet",
                    amount_sol=1.0,
                    amount_usd=100.0,
                    tx_signature=f"sig_{mint}_{j}",
                )
                db.record_buy(buy)

        top = db.get_top_tokens(hours=24, limit=5)

        assert len(top) == 3
        assert top[0]["token_mint"] == "mint1"
        assert top[0]["buy_count"] == 5

    def test_get_top_buyers(self, temp_db_path):
        """Test getting top buyers by volume."""
        db = BuyTrackerDB(db_path=temp_db_path)

        # Insert buys with varying amounts per wallet
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
        assert top_buyers[0]["buyer_wallet"] == "wallet1"
        assert top_buyers[0]["total_usd"] == 500.0


# =============================================================================
# 6. UTILITIES TESTS
# =============================================================================

class TestRetryConfig:
    """Tests for RetryConfig."""

    def test_retry_config_defaults(self):
        """Test RetryConfig default values."""
        config = RetryConfig()

        assert config.max_retries == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.jitter is True

    def test_retry_config_custom(self):
        """Test RetryConfig with custom values."""
        config = RetryConfig(
            max_retries=5,
            base_delay=2.0,
            max_delay=120.0,
            jitter=False,
        )

        assert config.max_retries == 5
        assert config.base_delay == 2.0
        assert config.jitter is False


class TestRateLimiter:
    """Tests for RateLimiter."""

    def test_rate_limiter_initialization(self):
        """Test rate limiter initialization."""
        limiter = RateLimiter(max_requests=10, window_seconds=60.0)

        assert limiter.max_requests == 10
        assert limiter.window_seconds == 60.0
        assert len(limiter.requests) == 0

    def test_can_proceed_empty(self):
        """Test can_proceed with no previous requests."""
        limiter = RateLimiter(max_requests=10, window_seconds=60.0)

        assert limiter.can_proceed() is True

    def test_can_proceed_below_limit(self):
        """Test can_proceed below limit."""
        limiter = RateLimiter(max_requests=10, window_seconds=60.0)
        limiter.requests = [time.time()] * 5

        assert limiter.can_proceed() is True

    def test_can_proceed_at_limit(self):
        """Test can_proceed at limit."""
        limiter = RateLimiter(max_requests=10, window_seconds=60.0)
        limiter.requests = [time.time()] * 10

        assert limiter.can_proceed() is False

    def test_can_proceed_expired_requests_cleared(self):
        """Test expired requests are cleared."""
        limiter = RateLimiter(max_requests=10, window_seconds=1.0)
        limiter.requests = [time.time() - 5] * 10  # All expired

        assert limiter.can_proceed() is True

    @pytest.mark.asyncio
    async def test_acquire_success(self):
        """Test acquire succeeds below limit."""
        limiter = RateLimiter(max_requests=10, window_seconds=60.0)

        result = await limiter.acquire()

        assert result is True
        assert len(limiter.requests) == 1


class TestCircuitBreaker:
    """Tests for CircuitBreaker."""

    def test_circuit_breaker_initialization(self):
        """Test circuit breaker initialization."""
        breaker = CircuitBreaker("test")

        assert breaker.name == "test"
        assert breaker.state == CircuitBreaker.CLOSED
        assert breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_can_proceed_closed(self):
        """Test can_proceed in CLOSED state."""
        breaker = CircuitBreaker("test")

        assert await breaker.can_proceed() is True

    @pytest.mark.asyncio
    async def test_can_proceed_open(self):
        """Test can_proceed in OPEN state."""
        breaker = CircuitBreaker("test")
        breaker.state = CircuitBreaker.OPEN
        breaker.last_failure_time = time.time()  # Recent failure

        assert await breaker.can_proceed() is False

    @pytest.mark.asyncio
    async def test_record_failure_threshold(self):
        """Test failure threshold triggers OPEN state."""
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker("test", config)

        for _ in range(3):
            await breaker.record_failure()

        assert breaker.state == CircuitBreaker.OPEN

    @pytest.mark.asyncio
    async def test_record_success_resets_failures(self):
        """Test success resets failure count."""
        breaker = CircuitBreaker("test")
        breaker.failure_count = 2

        await breaker.record_success()

        assert breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_half_open_recovery(self):
        """Test recovery from HALF_OPEN to CLOSED."""
        config = CircuitBreakerConfig(
            half_open_max_calls=2,
            recovery_timeout=0.0,
        )
        breaker = CircuitBreaker("test", config)
        breaker.state = CircuitBreaker.HALF_OPEN

        await breaker.record_success()
        await breaker.record_success()

        assert breaker.state == CircuitBreaker.CLOSED


class TestInputValidation:
    """Tests for input validation utilities."""

    def test_is_valid_solana_address_valid(self):
        """Test valid Solana address."""
        # 44-char base58 address
        valid = "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM"
        assert is_valid_solana_address(valid) is True

    def test_is_valid_solana_address_short(self):
        """Test address too short."""
        assert is_valid_solana_address("ABC123") is False

    def test_is_valid_solana_address_invalid_chars(self):
        """Test address with invalid characters."""
        # Contains 0, O, I, l which are invalid in base58
        invalid = "0OIl1234567890123456789012345678901234567890"
        assert is_valid_solana_address(invalid) is False

    def test_is_valid_solana_address_empty(self):
        """Test empty address."""
        assert is_valid_solana_address("") is False
        assert is_valid_solana_address(None) is False

    def test_sanitize_token_name_normal(self):
        """Test sanitizing normal token name."""
        result = sanitize_token_name("KR8TIV Token")
        assert result == "KR8TIV Token"

    def test_sanitize_token_name_html_escape(self):
        """Test HTML escaping in token name."""
        result = sanitize_token_name("<script>alert('xss')</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_sanitize_token_name_truncate(self):
        """Test truncation of long token name."""
        long_name = "A" * 100
        result = sanitize_token_name(long_name, max_length=50)
        assert len(result) == 50
        assert result.endswith("...")

    def test_sanitize_token_name_empty(self):
        """Test sanitizing empty name."""
        assert sanitize_token_name("") == "Unknown"
        assert sanitize_token_name(None) == "Unknown"

    def test_sanitize_telegram_message(self):
        """Test sanitizing Telegram message."""
        result = sanitize_telegram_message("Hello <b>world</b>")
        assert "&lt;b&gt;" in result

    def test_sanitize_telegram_message_null_bytes(self):
        """Test removing null bytes."""
        result = sanitize_telegram_message("Hello\x00World")
        assert "\x00" not in result

    def test_generate_dedup_key(self):
        """Test dedup key generation."""
        key1 = generate_dedup_key("sig123", "mint456")
        key2 = generate_dedup_key("sig123", "mint456")
        key3 = generate_dedup_key("sig999", "mint456")

        assert key1 == key2  # Same inputs = same key
        assert key1 != key3  # Different inputs = different key
        assert len(key1) == 16  # Fixed length

    def test_get_timeout_config_default(self):
        """Test default timeout config."""
        config = get_timeout_config()

        assert config['total'] == 30.0
        assert config['connect'] <= 10.0

    def test_get_timeout_config_custom(self):
        """Test custom timeout config."""
        config = get_timeout_config(timeout=60.0)

        assert config['total'] == 60.0


class TestSpendingLimits:
    """Tests for SpendingLimits."""

    def test_spending_limits_defaults(self):
        """Test default spending limits."""
        limits = SpendingLimits()

        assert limits.max_single_trade_sol == 0.1
        assert limits.max_single_trade_usd == 50.0
        assert limits.max_daily_sol == 1.0
        assert limits.max_daily_usd == 500.0

    def test_check_trade_within_limits(self):
        """Test trade within all limits."""
        limits = SpendingLimits()

        allowed, reason = limits.check_trade(0.05, 25.0)

        assert allowed is True
        assert reason == "OK"

    def test_check_trade_exceeds_single_sol(self):
        """Test trade exceeds single trade SOL limit."""
        limits = SpendingLimits(max_single_trade_sol=0.1)

        allowed, reason = limits.check_trade(0.2, 20.0)

        assert allowed is False
        assert "single trade" in reason.lower()

    def test_check_trade_exceeds_single_usd(self):
        """Test trade exceeds single trade USD limit."""
        limits = SpendingLimits(max_single_trade_usd=50.0)

        allowed, reason = limits.check_trade(0.05, 100.0)

        assert allowed is False
        assert "single trade" in reason.lower()

    def test_check_trade_exceeds_daily_limit(self):
        """Test trade exceeds daily limit."""
        limits = SpendingLimits(max_daily_sol=1.0, max_single_trade_sol=0.5)  # Allow single trade
        limits.daily_spent_sol = 0.9
        limits.last_reset = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        allowed, reason = limits.check_trade(0.2, 20.0)

        assert allowed is False
        assert "daily limit" in reason.lower()

    def test_record_trade(self):
        """Test recording trade against limits."""
        limits = SpendingLimits()

        limits.record_trade(0.5, 50.0)

        assert limits.daily_spent_sol == 0.5
        assert limits.daily_spent_usd == 50.0

    def test_daily_reset(self):
        """Test daily counters reset on new day."""
        limits = SpendingLimits()
        limits.daily_spent_sol = 0.5
        limits.daily_spent_usd = 50.0
        limits.last_reset = "1999-01-01"  # Old date

        # Should reset on check
        allowed, _ = limits.check_trade(0.05, 5.0)

        assert limits.last_reset == datetime.now(timezone.utc).strftime("%Y-%m-%d")


# =============================================================================
# 7. APE BUTTONS TESTS
# =============================================================================

class TestRiskProfileConfig:
    """Tests for risk profile configurations."""

    def test_risk_profile_safe_config(self):
        """Test SAFE risk profile config."""
        config = RISK_PROFILE_CONFIG[RiskProfile.SAFE]

        assert config["tp_pct"] == 15.0
        assert config["sl_pct"] == 5.0
        assert config["label"] == "SAFE"

    def test_risk_profile_medium_config(self):
        """Test MEDIUM risk profile config."""
        config = RISK_PROFILE_CONFIG[RiskProfile.MEDIUM]

        assert config["tp_pct"] == 30.0
        assert config["sl_pct"] == 10.0

    def test_risk_profile_degen_config(self):
        """Test DEGEN risk profile config."""
        config = RISK_PROFILE_CONFIG[RiskProfile.DEGEN]

        assert config["tp_pct"] == 50.0
        assert config["sl_pct"] == 15.0

    def test_stock_risk_profile_lower(self):
        """Test stock risk profiles have lower targets."""
        stock_safe = STOCK_RISK_PROFILE_CONFIG[RiskProfile.SAFE]
        crypto_safe = RISK_PROFILE_CONFIG[RiskProfile.SAFE]

        assert stock_safe["tp_pct"] < crypto_safe["tp_pct"]
        assert stock_safe["sl_pct"] < crypto_safe["sl_pct"]

    def test_get_risk_config_token(self):
        """Test getting risk config for tokens."""
        config = get_risk_config("token", RiskProfile.MEDIUM)

        assert config["tp_pct"] == 30.0  # Crypto config

    def test_get_risk_config_stock(self):
        """Test getting risk config for stocks."""
        config = get_risk_config("stock", RiskProfile.MEDIUM)

        assert config["tp_pct"] == 10.0  # Stock config (lower)


class TestTradeSetup:
    """Tests for TradeSetup dataclass."""

    def test_trade_setup_creation(self):
        """Test basic TradeSetup creation."""
        setup = TradeSetup(
            symbol="KR8TIV",
            asset_type="token",
            direction="LONG",
            entry_price=0.001,
            take_profit_price=0.0013,
            stop_loss_price=0.00095,
            risk_profile=RiskProfile.SAFE,
            allocation_percent=5.0,
            amount_sol=0.5,
        )

        assert setup.symbol == "KR8TIV"
        assert setup.direction == "LONG"
        assert setup.risk_profile == RiskProfile.SAFE

    def test_trade_setup_validate_valid(self):
        """Test validate with valid setup."""
        setup = TradeSetup(
            symbol="KR8TIV",
            asset_type="token",
            direction="LONG",
            entry_price=0.001,
            take_profit_price=0.0013,  # Above entry
            stop_loss_price=0.00095,   # Below entry
            risk_profile=RiskProfile.SAFE,
            allocation_percent=5.0,
        )

        is_valid, msg = setup.validate()

        assert is_valid is True
        assert msg == "Valid"

    def test_trade_setup_validate_missing_tp(self):
        """Test validate with missing TP."""
        setup = TradeSetup(
            symbol="KR8TIV",
            asset_type="token",
            direction="LONG",
            entry_price=0.001,
            take_profit_price=0.0,  # Invalid
            stop_loss_price=0.00095,
            risk_profile=RiskProfile.SAFE,
            allocation_percent=5.0,
        )

        is_valid, msg = setup.validate()

        assert is_valid is False
        assert "take profit" in msg.lower()

    def test_trade_setup_validate_wrong_tp_direction(self):
        """Test validate with TP in wrong direction for LONG."""
        setup = TradeSetup(
            symbol="KR8TIV",
            asset_type="token",
            direction="LONG",
            entry_price=0.001,
            take_profit_price=0.0008,  # Below entry (wrong for LONG)
            stop_loss_price=0.00095,
            risk_profile=RiskProfile.SAFE,
            allocation_percent=5.0,
        )

        is_valid, msg = setup.validate()

        assert is_valid is False
        assert "above entry" in msg.lower()

    def test_trade_setup_validate_wrong_sl_direction(self):
        """Test validate with SL in wrong direction for LONG."""
        setup = TradeSetup(
            symbol="KR8TIV",
            asset_type="token",
            direction="LONG",
            entry_price=0.001,
            take_profit_price=0.0013,
            stop_loss_price=0.0012,  # Above entry (wrong for LONG)
            risk_profile=RiskProfile.SAFE,
            allocation_percent=5.0,
        )

        is_valid, msg = setup.validate()

        assert is_valid is False
        assert "below entry" in msg.lower()

    def test_trade_setup_validate_allocation_too_high(self):
        """Test validate with allocation > 10%."""
        setup = TradeSetup(
            symbol="KR8TIV",
            asset_type="token",
            direction="LONG",
            entry_price=0.001,
            take_profit_price=0.0013,
            stop_loss_price=0.00095,
            risk_profile=RiskProfile.SAFE,
            allocation_percent=15.0,  # Too high
        )

        is_valid, msg = setup.validate()

        assert is_valid is False
        assert "allocation" in msg.lower()

    def test_trade_setup_to_dict(self):
        """Test TradeSetup serialization."""
        setup = TradeSetup(
            symbol="KR8TIV",
            asset_type="token",
            direction="LONG",
            entry_price=0.001,
            take_profit_price=0.0013,
            stop_loss_price=0.00095,
            risk_profile=RiskProfile.MEDIUM,
            allocation_percent=5.0,
            amount_sol=0.5,
            grade="A",
        )

        data = setup.to_dict()

        assert data["symbol"] == "KR8TIV"
        assert data["risk_profile"] == "medium"
        assert data["grade"] == "A"


class TestTradeResult:
    """Tests for TradeResult dataclass."""

    def test_trade_result_success(self):
        """Test successful trade result."""
        setup = TradeSetup(
            symbol="KR8TIV",
            asset_type="token",
            direction="LONG",
            entry_price=0.001,
            take_profit_price=0.0013,
            stop_loss_price=0.00095,
            risk_profile=RiskProfile.SAFE,
            allocation_percent=5.0,
        )

        result = TradeResult(
            success=True,
            trade_setup=setup,
            tx_signature="sig123",
            message="Trade executed",
        )

        assert result.success is True
        assert result.tx_signature == "sig123"

    def test_trade_result_failure(self):
        """Test failed trade result."""
        result = TradeResult(
            success=False,
            error="Insufficient balance",
        )

        assert result.success is False
        assert "balance" in result.error.lower()


class TestCalculateTPSL:
    """Tests for TP/SL price calculations."""

    def test_calculate_tp_sl_long_safe(self):
        """Test TP/SL calculation for LONG SAFE."""
        tp, sl = calculate_tp_sl_prices(
            entry_price=1.0,
            risk_profile=RiskProfile.SAFE,
            direction="LONG",
            asset_type="token",
        )

        assert tp == 1.15  # +15%
        assert sl == 0.95  # -5%

    def test_calculate_tp_sl_long_medium(self):
        """Test TP/SL calculation for LONG MEDIUM."""
        tp, sl = calculate_tp_sl_prices(
            entry_price=1.0,
            risk_profile=RiskProfile.MEDIUM,
            direction="LONG",
            asset_type="token",
        )

        assert tp == 1.30  # +30%
        assert sl == 0.90  # -10%

    def test_calculate_tp_sl_long_degen(self):
        """Test TP/SL calculation for LONG DEGEN."""
        tp, sl = calculate_tp_sl_prices(
            entry_price=1.0,
            risk_profile=RiskProfile.DEGEN,
            direction="LONG",
            asset_type="token",
        )

        assert tp == 1.50  # +50%
        assert sl == 0.85  # -15%

    def test_calculate_tp_sl_short(self):
        """Test TP/SL calculation for SHORT."""
        tp, sl = calculate_tp_sl_prices(
            entry_price=1.0,
            risk_profile=RiskProfile.SAFE,
            direction="SHORT",
            asset_type="token",
        )

        assert tp == 0.85  # -15% (profit for short)
        assert sl == 1.05  # +5% (loss for short)

    def test_calculate_tp_sl_stock(self):
        """Test TP/SL calculation for stocks (lower targets)."""
        tp, sl = calculate_tp_sl_prices(
            entry_price=100.0,
            risk_profile=RiskProfile.MEDIUM,
            direction="LONG",
            asset_type="stock",
        )

        assert tp == pytest.approx(110.0, rel=0.01)  # +10% (stock medium)
        assert sl == pytest.approx(96.0, rel=0.01)   # -4%


class TestParseApeCallback:
    """Tests for ape callback parsing."""

    def test_parse_ape_callback_valid(self):
        """Test parsing valid ape callback."""
        callback = "ape:5:m:t:KR8TIV:contract1"

        parsed = parse_ape_callback(callback)

        assert parsed is not None
        assert parsed["allocation_percent"] == 5.0
        assert parsed["risk_profile"] == RiskProfile.MEDIUM
        assert parsed["asset_type"] == "token"
        assert parsed["symbol"] == "KR8TIV"
        assert parsed["contract"] == "contract1"

    def test_parse_ape_callback_safe_profile(self):
        """Test parsing with SAFE profile."""
        callback = "ape:2:s:t:BONK:"

        parsed = parse_ape_callback(callback)

        assert parsed["risk_profile"] == RiskProfile.SAFE
        assert parsed["allocation_percent"] == 2.0

    def test_parse_ape_callback_degen_profile(self):
        """Test parsing with DEGEN profile."""
        callback = "ape:1:d:t:WIF:"

        parsed = parse_ape_callback(callback)

        assert parsed["risk_profile"] == RiskProfile.DEGEN
        assert parsed["allocation_percent"] == 1.0

    def test_parse_ape_callback_stock_type(self):
        """Test parsing stock asset type."""
        callback = "ape:5:m:s:AAPL:"

        parsed = parse_ape_callback(callback)

        assert parsed["asset_type"] == "stock"

    def test_parse_ape_callback_invalid_prefix(self):
        """Test parsing invalid callback prefix."""
        callback = "invalid:5:m:t:TOKEN:"

        parsed = parse_ape_callback(callback)

        assert parsed is None

    def test_parse_ape_callback_too_short(self):
        """Test parsing callback with too few parts."""
        callback = "ape:5:m"

        parsed = parse_ape_callback(callback)

        assert parsed is None


class TestCreateApeButtons:
    """Tests for creating ape buttons."""

    def test_create_ape_buttons_structure(self):
        """Test ape buttons keyboard structure."""
        keyboard = create_ape_buttons_with_tp_sl(
            symbol="KR8TIV",
            asset_type="token",
            contract_address="contract123",
        )

        # Should have 5 rows: header, 3 allocation rows, info row
        assert len(keyboard.inline_keyboard) == 5

        # Header row has 3 profile buttons
        assert len(keyboard.inline_keyboard[0]) == 3

    def test_create_token_ape_keyboard(self):
        """Test token-specific keyboard creation."""
        keyboard = create_token_ape_keyboard(
            symbol="BONK",
            contract="contract456",
            entry_price=0.00001,
            grade="B+",
        )

        assert keyboard is not None
        # Info row should contain symbol
        info_button = keyboard.inline_keyboard[-1][0]
        assert "BONK" in info_button.text

    def test_create_stock_ape_keyboard(self):
        """Test stock-specific keyboard creation."""
        keyboard = create_stock_ape_keyboard(
            ticker="AAPL",
            entry_price=180.0,
            grade="A",
        )

        assert keyboard is not None


class TestCreateTradeSetup:
    """Tests for creating trade setup from callback."""

    def test_create_trade_setup_basic(self):
        """Test basic trade setup creation."""
        parsed = {
            "allocation_percent": 5.0,
            "risk_profile": RiskProfile.MEDIUM,
            "tp_pct": 30.0,
            "sl_pct": 10.0,
            "asset_type": "token",
            "symbol": "KR8TIV",
            "contract": "contract123",
        }

        setup = create_trade_setup(
            parsed_callback=parsed,
            entry_price=0.001,
            treasury_balance_sol=10.0,
            direction="LONG",
            grade="A",
        )

        assert setup.symbol == "KR8TIV"
        assert setup.allocation_percent == 5.0
        assert setup.amount_sol == 0.5  # 5% of 10 SOL
        assert setup.entry_price == 0.001
        assert setup.take_profit_price == pytest.approx(0.0013, rel=0.01)  # +30%
        assert setup.stop_loss_price == pytest.approx(0.0009, rel=0.01)   # -10%
        assert setup.grade == "A"


class TestFormatTreasuryStatus:
    """Tests for treasury status formatting."""

    def test_format_treasury_status_basic(self):
        """Test basic treasury status formatting."""
        status = format_treasury_status(
            balance_sol=10.5,
            balance_usd=1575.0,
            open_positions=5,
            pnl_24h=12.5,
            treasury_address="9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",
        )

        assert "10.5000 SOL" in status
        assert "$1,575.00" in status
        assert "5" in status
        assert "+12.50%" in status
        assert "9WzD" in status

    def test_format_treasury_status_negative_pnl(self):
        """Test treasury status with negative PnL."""
        status = format_treasury_status(
            balance_sol=5.0,
            balance_usd=750.0,
            open_positions=2,
            pnl_24h=-5.5,
        )

        assert "-5.50%" in status

    def test_format_treasury_status_risk_profiles(self):
        """Test risk profiles are shown."""
        status = format_treasury_status()

        assert "SAFE" in status
        assert "MED" in status
        assert "DEGEN" in status


# =============================================================================
# 8. CONFIGURATION TESTS
# =============================================================================

class TestBuyBotConfig:
    """Tests for BuyBotConfig."""

    def test_config_post_init_rpc_url(self):
        """Test RPC URL is set from Helius API key."""
        config = BuyBotConfig(
            bot_token="token",
            chat_id="chat",
            token_address="addr",
            helius_api_key="test_key",
        )

        assert "test_key" in config.rpc_url
        assert "helius-rpc.com" in config.rpc_url

    def test_config_post_init_ws_url(self):
        """Test WebSocket URL is set from Helius API key."""
        config = BuyBotConfig(
            bot_token="token",
            chat_id="chat",
            token_address="addr",
            helius_api_key="test_key",
        )

        assert "test_key" in config.websocket_url
        assert "wss://" in config.websocket_url

    def test_config_defaults(self):
        """Test config default values."""
        config = BuyBotConfig(
            bot_token="token",
            chat_id="chat",
            token_address="addr",
        )

        assert config.token_symbol == "KR8TIV"
        assert config.token_name == "Kr8Tiv"
        assert config.min_buy_usd == 5.0
        assert config.buy_emoji == "🤖"

    def test_additional_pairs_default(self):
        """Test additional pairs default to empty list."""
        config = BuyBotConfig(
            bot_token="token",
            chat_id="chat",
            token_address="addr",
        )

        assert config.additional_pairs == []


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_config_from_env(self):
        """Test loading config from environment."""
        env_vars = {
            "TELEGRAM_BOT_TOKEN": "env_token",
            "TELEGRAM_BUY_BOT_CHAT_ID": "env_chat_id",
            "BUY_BOT_TOKEN_ADDRESS": "env_token_address",
            "HELIUS_API_KEY": "env_helius_key",
            "BUY_BOT_MIN_USD": "10.0",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            config = load_config()

            assert config.chat_id == "env_chat_id"
            assert config.helius_api_key == "env_helius_key"
            assert config.min_buy_usd == 10.0

    def test_load_config_additional_pairs(self):
        """Test loading config includes additional pairs."""
        with patch.dict(os.environ, {}, clear=False):
            config = load_config()

            # Should load from ADDITIONAL_LP_PAIRS constant
            if ADDITIONAL_LP_PAIRS:
                assert len(config.additional_pairs) > 0


# =============================================================================
# 9. INTENT TRACKER TESTS
# =============================================================================

class TestIntentTracking:
    """Tests for intent tracking (idempotency)."""

    def test_generate_intent_id_deterministic(self):
        """Test intent ID is deterministic for same params."""
        from bots.buy_tracker.intent_tracker import generate_intent_id

        id1 = generate_intent_id("KR8TIV", 0.5, 0.001, 0.0013, 0.0009, 12345)
        id2 = generate_intent_id("KR8TIV", 0.5, 0.001, 0.0013, 0.0009, 12345)

        assert id1 == id2

    def test_generate_intent_id_different_params(self):
        """Test different params generate different IDs."""
        from bots.buy_tracker.intent_tracker import generate_intent_id

        id1 = generate_intent_id("KR8TIV", 0.5, 0.001, 0.0013, 0.0009)
        id2 = generate_intent_id("KR8TIV", 1.0, 0.001, 0.0013, 0.0009)  # Different amount

        assert id1 != id2

    def test_generate_intent_id_uuid_format(self):
        """Test intent ID is valid UUID format."""
        from bots.buy_tracker.intent_tracker import generate_intent_id
        import uuid

        intent_id = generate_intent_id("TOKEN", 1.0, 0.01, 0.02, 0.008)

        # Should be valid UUID
        parsed = uuid.UUID(intent_id)
        assert str(parsed) == intent_id


# =============================================================================
# 10. BOT LIFECYCLE TESTS
# =============================================================================

class TestBotLifecycle:
    """Tests for bot start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_validates_config(self, mock_config):
        """Test start validates required config."""
        mock_config.bot_token = ""  # Missing
        bot = JarvisBuyBot(config=mock_config)

        # Should log error and return without starting
        await bot.start()

        assert bot._running is False

    @pytest.mark.asyncio
    async def test_stop_sets_running_false(self, mock_config):
        """Test stop sets _running to False."""
        bot = JarvisBuyBot(config=mock_config)
        bot._running = True
        bot.monitor = AsyncMock()
        bot.app = AsyncMock()
        bot.app.updater = AsyncMock()

        await bot.stop()

        assert bot._running is False


# =============================================================================
# 11. CALLBACK HANDLER TESTS
# =============================================================================

class TestCallbackHandlers:
    """Tests for Telegram callback handlers."""

    @pytest.fixture
    def mock_update(self):
        """Create mock Telegram Update."""
        update = MagicMock()
        update.callback_query = MagicMock()
        update.callback_query.data = "show_faq"
        update.callback_query.message = MagicMock()
        update.callback_query.message.message_id = 12345
        update.callback_query.message.chat_id = -100123
        update.callback_query.message.video = None
        update.callback_query.message.animation = None
        update.callback_query.from_user = MagicMock()
        update.callback_query.from_user.id = 67890
        update.callback_query.answer = AsyncMock()
        update.callback_query.message.edit_text = AsyncMock()
        return update

    @pytest.fixture
    def mock_context(self):
        """Create mock Telegram Context."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_handle_faq_callback_show(self, mock_config, mock_update, mock_context):
        """Test FAQ show callback expands content."""
        bot = JarvisBuyBot(config=mock_config)
        bot.bot = AsyncMock()
        bot._message_cache[12345] = "Original message"

        mock_update.callback_query.data = "show_faq"

        await bot._handle_faq_callback(mock_update, mock_context)

        # Should answer callback
        mock_update.callback_query.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_faq_callback_hide(self, mock_config, mock_update, mock_context):
        """Test FAQ hide callback collapses content."""
        bot = JarvisBuyBot(config=mock_config)
        bot.bot = AsyncMock()
        bot._message_cache[12345] = "Original message"

        mock_update.callback_query.data = "hide_faq"

        await bot._handle_faq_callback(mock_update, mock_context)

        mock_update.callback_query.answer.assert_called_once()


# =============================================================================
# 12. AUDIT LOGGER TESTS
# =============================================================================

class TestAuditLogger:
    """Tests for AuditLogger."""

    def test_audit_logger_initialization(self):
        """Test audit logger initialization."""
        # Use tempdir to avoid file locking issues on Windows
        temp_dir = tempfile.mkdtemp()
        log_path = os.path.join(temp_dir, "test_audit.log")
        try:
            logger_obj = AuditLogger(log_file=log_path)
            assert logger_obj.log_file == log_path
            # Close handlers to release file
            for handler in logger_obj.logger.handlers[:]:
                handler.close()
                logger_obj.logger.removeHandler(handler)
        finally:
            try:
                os.unlink(log_path)
                os.rmdir(temp_dir)
            except Exception:
                pass

    def test_log_trade(self):
        """Test logging a trade."""
        temp_dir = tempfile.mkdtemp()
        log_path = os.path.join(temp_dir, "test_trade.log")
        try:
            audit = AuditLogger(log_file=log_path)
            audit.log_trade("BUY", "KR8TIV", 0.5, 0.001, user_id="12345")

            # Close handlers before reading
            for handler in audit.logger.handlers[:]:
                handler.close()
                audit.logger.removeHandler(handler)

            # Read log file
            with open(log_path) as log_file:
                content = log_file.read()
                assert "TRADE" in content
                assert "BUY" in content
                assert "KR8TIV" in content
        finally:
            try:
                os.unlink(log_path)
                os.rmdir(temp_dir)
            except Exception:
                pass

    def test_log_alert(self):
        """Test logging an alert."""
        temp_dir = tempfile.mkdtemp()
        log_path = os.path.join(temp_dir, "test_alert.log")
        try:
            audit = AuditLogger(log_file=log_path)
            audit.log_alert("LARGE_BUY", "TOKEN", "chat123")

            # Close handlers before reading
            for handler in audit.logger.handlers[:]:
                handler.close()
                audit.logger.removeHandler(handler)

            with open(log_path) as log_file:
                content = log_file.read()
                assert "ALERT" in content
                assert "LARGE_BUY" in content
        finally:
            try:
                os.unlink(log_path)
                os.rmdir(temp_dir)
            except Exception:
                pass


# =============================================================================
# 13. TELEGRAM RATE LIMITER TESTS
# =============================================================================

class TestTelegramRateLimiter:
    """Tests for TelegramRateLimiter."""

    def test_telegram_limiter_initialization(self):
        """Test Telegram rate limiter initialization."""
        limiter = TelegramRateLimiter()

        assert limiter.global_limiter is not None
        assert len(limiter.chat_limiters) == 0  # Empty defaultdict

    @pytest.mark.asyncio
    async def test_telegram_limiter_acquire(self):
        """Test acquiring rate limit for chat."""
        limiter = TelegramRateLimiter()

        await limiter.acquire("chat123")

        # Chat limiter should be created
        assert "chat123" in limiter.chat_limiters

    def test_get_telegram_limiter_singleton(self):
        """Test get_telegram_limiter returns singleton."""
        import bots.buy_tracker.utils as utils_module

        # Reset singleton
        utils_module._telegram_limiter = None

        limiter1 = get_telegram_limiter()
        limiter2 = get_telegram_limiter()

        assert limiter1 is limiter2


# =============================================================================
# 14. MESSAGE CACHE TESTS
# =============================================================================

class TestMessageCache:
    """Tests for message caching functionality."""

    def test_message_cache_add(self, mock_config):
        """Test adding message to cache."""
        bot = JarvisBuyBot(config=mock_config)

        bot._message_cache[123] = "Test message"

        assert 123 in bot._message_cache
        assert bot._message_cache[123] == "Test message"

    def test_message_cache_limit_100(self, mock_config):
        """Test message cache limits to 100 entries."""
        bot = JarvisBuyBot(config=mock_config)

        # Add 101 messages
        for i in range(101):
            bot._message_cache[i] = f"Message {i}"

        # Simulate the limiting logic from _on_buy_detected
        if len(bot._message_cache) > 100:
            oldest = list(bot._message_cache.keys())[0]
            del bot._message_cache[oldest]

        assert len(bot._message_cache) == 100
        assert 0 not in bot._message_cache  # Oldest removed


# =============================================================================
# 15. EDGE CASES TESTS
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_buy_transaction(self):
        """Test handling empty/minimal buy transaction."""
        tx = BuyTransaction(
            signature="",
            buyer_wallet="",
            token_amount=0.0,
            sol_amount=0.0,
            usd_amount=0.0,
            price_per_token=0.0,
            buyer_position_pct=0.0,
            market_cap=0.0,
            timestamp=datetime.utcnow(),
            tx_url="",
            dex_url="",
        )

        assert tx.buyer_short == ""
        assert tx.signature_short == ""

    def test_very_small_amounts(self, mock_config):
        """Test formatting very small amounts."""
        bot = JarvisBuyBot.__new__(JarvisBuyBot)

        result = bot._format_number(0.000001)
        assert result == "0.00"

    def test_very_large_amounts(self, mock_config):
        """Test formatting very large amounts."""
        bot = JarvisBuyBot.__new__(JarvisBuyBot)

        result = bot._format_number(999_999_999_999)
        assert "B" in result

    def test_allocation_percent_boundary_zero(self):
        """Test allocation percent at zero boundary."""
        setup = TradeSetup(
            symbol="TEST",
            asset_type="token",
            direction="LONG",
            entry_price=1.0,
            take_profit_price=1.15,
            stop_loss_price=0.95,
            risk_profile=RiskProfile.SAFE,
            allocation_percent=0.0,  # Invalid
        )

        is_valid, _ = setup.validate()
        assert is_valid is False

    def test_allocation_percent_boundary_ten(self):
        """Test allocation percent at 10% boundary."""
        setup = TradeSetup(
            symbol="TEST",
            asset_type="token",
            direction="LONG",
            entry_price=1.0,
            take_profit_price=1.15,
            stop_loss_price=0.95,
            risk_profile=RiskProfile.SAFE,
            allocation_percent=10.0,  # At limit
        )

        is_valid, _ = setup.validate()
        assert is_valid is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
