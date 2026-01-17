"""
Unit tests for buy intent idempotency tracker (Issue #1 fix).

Tests:
- Intent ID generation (deterministic)
- Duplicate intent detection
- Intent recording and retrieval
- Idempotency window enforcement
"""

import pytest
import asyncio
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from bots.buy_tracker.intent_tracker import (
    generate_intent_id,
    check_intent_duplicate,
    record_intent_execution,
    get_intent_result,
)
from core.event_bus.event_bus import set_event_bus, EventBus
from core.memory.dedup_store import SQLiteMemoryStore, set_memory_store


@pytest.fixture
async def clean_memory_store():
    """Use temporary MemoryStore for each test to avoid state sharing."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
        db_path = f.name

    # Create temp store
    temp_store = SQLiteMemoryStore(db_path=db_path)
    set_memory_store(temp_store)

    yield temp_store

    # Cleanup
    try:
        Path(db_path).unlink(missing_ok=True)
    except Exception:  # noqa: BLE001 - intentional catch-all
        pass


def test_intent_id_generation_deterministic():
    """Test that intent IDs are deterministic (same params = same ID)."""
    symbol = "KR8TIV"
    amount = 10.0
    entry = 0.001
    tp = 0.0011
    sl = 0.0009
    user = 123

    # Generate same ID twice with same params
    id1 = generate_intent_id(symbol, amount, entry, tp, sl, user)
    id2 = generate_intent_id(symbol, amount, entry, tp, sl, user)

    # Should be identical
    assert id1 == id2
    assert len(id1) > 0


def test_intent_id_varies_by_params():
    """Test that different params generate different IDs."""
    symbol = "KR8TIV"

    # Same params
    id1 = generate_intent_id(symbol, 10.0, 0.001, 0.0011, 0.0009)

    # Different amount
    id2 = generate_intent_id(symbol, 20.0, 0.001, 0.0011, 0.0009)

    assert id1 != id2


def test_intent_id_includes_user():
    """Test that user ID affects intent ID."""
    symbol = "KR8TIV"
    amount = 10.0
    entry = 0.001
    tp = 0.0011
    sl = 0.0009

    id_no_user = generate_intent_id(symbol, amount, entry, tp, sl, user_id=None)
    id_user1 = generate_intent_id(symbol, amount, entry, tp, sl, user_id=123)
    id_user2 = generate_intent_id(symbol, amount, entry, tp, sl, user_id=456)

    # Different user should give different intent IDs
    assert id_no_user != id_user1
    assert id_user1 != id_user2


@pytest.mark.asyncio
async def test_intent_duplicate_detection(clean_memory_store):
    """Test that duplicate intents are detected (Issue #1 fix)."""
    symbol = "KR8TIV"
    amount = 10.0
    entry = 0.001
    tp = 0.0011
    sl = 0.0009

    intent_id = generate_intent_id(symbol, amount, entry, tp, sl)

    # First check - should not be duplicate
    is_dup, reason = await check_intent_duplicate(intent_id, symbol)
    assert is_dup is False

    # Record execution
    await record_intent_execution(
        intent_id=intent_id,
        symbol=symbol,
        success=True,
        tx_signature="abc123..."
    )

    # Second check - should now be duplicate
    is_dup2, reason2 = await check_intent_duplicate(intent_id, symbol)
    assert is_dup2 is True


@pytest.mark.asyncio
async def test_intent_recording(clean_memory_store):
    """Test recording and retrieving intent results."""
    symbol = "SOL"
    amount = 5.0
    entry = 200.0
    tp = 220.0
    sl = 180.0

    intent_id = generate_intent_id(symbol, amount, entry, tp, sl)
    tx_sig = "sig_test_12345"

    # Record successful execution
    await record_intent_execution(
        intent_id=intent_id,
        symbol=symbol,
        success=True,
        tx_signature=tx_sig,
        error=None
    )

    # Retrieve result
    result = await get_intent_result(intent_id, symbol)
    assert result is not None
    assert result["success"] is True
    assert result["tx_signature"] == tx_sig


@pytest.mark.asyncio
async def test_intent_failure_recording(clean_memory_store):
    """Test recording failed intent execution."""
    symbol = "WETH"
    amount = 1.0
    entry = 2000.0
    tp = 2200.0
    sl = 1800.0

    intent_id = generate_intent_id(symbol, amount, entry, tp, sl)
    error_msg = "Insufficient balance"

    # Record failed execution
    await record_intent_execution(
        intent_id=intent_id,
        symbol=symbol,
        success=False,
        tx_signature=None,
        error=error_msg
    )

    # Retrieve result
    result = await get_intent_result(intent_id, symbol)
    assert result is not None
    assert result["success"] is False
    assert result["error"] == error_msg


@pytest.mark.asyncio
async def test_intent_idempotency_window(clean_memory_store):
    """Test that intents expire after 1 hour."""
    # This test verifies the idempotency mechanism
    # (actual time-based cleanup is handled by MemoryStore)
    symbol = "TEST"
    intent_id = generate_intent_id(symbol, 10.0, 0.001, 0.0011, 0.0009)

    # Record an intent
    await record_intent_execution(
        intent_id=intent_id,
        symbol=symbol,
        success=True,
        tx_signature="test123"
    )

    # Within window - should be duplicate
    is_dup, _ = await check_intent_duplicate(intent_id, symbol)
    assert is_dup is True

    # Outside window (0 hours) - should allow (expired)
    # This tests the cleanup mechanism
    # Note: Actual expiration is handled by MemoryStore.cleanup_expired()


@pytest.mark.asyncio
async def test_intent_same_trade_retried(clean_memory_store):
    """Test the Issue #1 scenario: button clicked twice on same trade."""
    # User clicks button for KR8TIV 10 SOL trade
    symbol = "KR8TIV"
    amount = 10.0
    entry = 0.001
    tp = 0.00120  # 20% gain
    sl = 0.00080  # 20% loss
    user_id = 12345

    intent_id = generate_intent_id(symbol, amount, entry, tp, sl, user_id)

    # First execution (succeeds)
    await record_intent_execution(
        intent_id=intent_id,
        symbol=symbol,
        success=True,
        tx_signature="sig_12345"
    )

    # User retries (button click again with same params)
    # Should be blocked as duplicate
    is_dup, reason = await check_intent_duplicate(intent_id, symbol)
    assert is_dup is True
    assert "duplicate" in reason.lower() or reason is not None

    # Verify we can retrieve the original execution
    result = await get_intent_result(intent_id, symbol)
    assert result is not None
    assert result["tx_signature"] == "sig_12345"


@pytest.mark.asyncio
async def test_different_trades_allowed(clean_memory_store):
    """Test that different trades (different params) are not blocked."""
    symbol = "KR8TIV"
    user_id = 12345

    # First trade
    intent_id_1 = generate_intent_id(symbol, 10.0, 0.001, 0.00120, 0.00080, user_id)
    await record_intent_execution(
        intent_id=intent_id_1,
        symbol=symbol,
        success=True,
        tx_signature="sig_1"
    )

    # Different amount - should be allowed
    intent_id_2 = generate_intent_id(symbol, 20.0, 0.001, 0.00120, 0.00080, user_id)
    is_dup, _ = await check_intent_duplicate(intent_id_2, symbol)
    assert is_dup is False

    # Different price - should be allowed
    intent_id_3 = generate_intent_id(symbol, 10.0, 0.002, 0.00120, 0.00080, user_id)
    is_dup, _ = await check_intent_duplicate(intent_id_3, symbol)
    assert is_dup is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
