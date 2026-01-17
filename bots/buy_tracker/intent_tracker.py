"""
Buy Intent Idempotency Tracker.

Fixes Issue #1: Duplicate trades from button retries.

Provides:
- UUID generation for buy intents
- Deduplication checking before trade execution
- 1-hour idempotency window (allows retries)
- Transaction-safe button handling
"""

import uuid
import logging
from typing import Optional, Tuple
from datetime import datetime, timedelta

from core.memory.dedup_store import (
    MemoryStore,
    MemoryEntry,
    MemoryType,
    get_memory_store,
)

logger = logging.getLogger(__name__)

# Intent ID validity window (how long to deduplicate retries)
INTENT_IDEMPOTENCY_HOURS = 1


def generate_intent_id(
    symbol: str,
    amount_sol: float,
    entry_price: float,
    tp_price: float,
    sl_price: float,
    user_id: Optional[int] = None,
) -> str:
    """
    Generate a deterministic intent ID from trade parameters.

    This ensures that the same trade parameters always generate the same ID,
    allowing deduplication of retries.

    Args:
        symbol: Token symbol (e.g., "KR8TIV")
        amount_sol: Amount in SOL
        entry_price: Entry price
        tp_price: Take profit price
        sl_price: Stop loss price
        user_id: User ID (for Telegram)

    Returns:
        UUID string for this intent
    """
    # Create a deterministic string from key parameters
    intent_str = f"{symbol}:{amount_sol}:{entry_price}:{tp_price}:{sl_price}"
    if user_id:
        intent_str += f":{user_id}"

    # Generate deterministic UUID from string (always same for same params)
    import hashlib
    hash_digest = hashlib.sha256(intent_str.encode()).digest()
    intent_uuid = str(uuid.UUID(bytes=hash_digest[:16]))

    return intent_uuid


async def check_intent_duplicate(
    intent_id: str,
    symbol: str,
) -> Tuple[bool, Optional[str]]:
    """
    Check if this intent was already executed.

    Args:
        intent_id: UUID of the intent
        symbol: Token symbol (for grouping/analytics)

    Returns:
        (is_duplicate, cached_tx_signature or error_message)
    """
    try:
        store = get_memory_store()

        # Use intent_id as entity_id for Layer 1 exact match detection
        # This ensures different intents are not confused (Layer 2 would catch all same-symbol intents)
        is_dup, reason = await store.is_duplicate(
            content=f"buy_intent:{intent_id}",
            entity_id=intent_id,  # Use intent_id to avoid symbol-based grouping
            entity_type="intent",
            memory_type=MemoryType.DUPLICATE_INTENT,
            hours=INTENT_IDEMPOTENCY_HOURS,
            similarity_threshold=0.95  # Exact intent only
        )

        return is_dup, reason
    except Exception as e:
        logger.warning(f"Intent duplicate check failed: {e}")
        return False, None


async def record_intent_execution(
    intent_id: str,
    symbol: str,
    success: bool,
    tx_signature: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    """
    Record that an intent was executed.

    Args:
        intent_id: UUID of the intent
        symbol: Token symbol (for analytics)
        success: Whether execution succeeded
        tx_signature: Transaction signature if successful
        error: Error message if failed
    """
    try:
        store = get_memory_store()

        # Set TTL: entry expires after INTENT_IDEMPOTENCY_HOURS
        expires_at = (datetime.utcnow() + timedelta(hours=INTENT_IDEMPOTENCY_HOURS)).isoformat()

        entry = MemoryEntry(
            content=f"buy_intent:{intent_id}",
            memory_type=MemoryType.DUPLICATE_INTENT,
            entity_id=intent_id,  # Use intent_id for exact dedup
            entity_type="intent",
            expires_at=expires_at,
            metadata={
                "intent_id": intent_id,
                "symbol": symbol,  # Store symbol in metadata for analytics
                "success": success,
                "tx_signature": tx_signature or "",
                "error": error or "",
            }
        )

        entry_id = await store.store(entry)
        logger.info(
            f"Recorded intent: {intent_id} for {symbol} (status={'SUCCESS' if success else 'FAILED'}) "
            f"(entry {entry_id})"
        )
    except Exception as e:
        logger.warning(f"Failed to record intent: {e}")


async def get_intent_result(
    intent_id: str,
    symbol: str,
) -> Optional[dict]:
    """
    Get the cached result of a previously executed intent.

    Args:
        intent_id: UUID of the intent
        symbol: Token symbol (for verification)

    Returns:
        Dictionary with result metadata or None if not found
    """
    try:
        store = get_memory_store()

        # Query by intent_id (exact match)
        memories = await store.get_memories(
            entity_id=intent_id,  # Query by intent_id
            memory_type=MemoryType.DUPLICATE_INTENT,
            limit=1
        )

        if memories and len(memories) > 0:
            # Verify symbol matches (optional sanity check)
            metadata = memories[0].metadata
            if metadata.get("symbol") == symbol:
                return metadata

        return None
    except Exception as e:
        logger.warning(f"Failed to get intent result: {e}")
        return None
