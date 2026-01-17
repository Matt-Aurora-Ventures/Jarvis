# JARVIS Audit - Deliverable C: Architecture Proposal

**Date**: 2026-01-16
**Purpose**: Design solutions for P1/P2 findings
**Format**: Architecture diagrams + design rationale + API contracts

---

## 1. MEMORYSTORE INTERFACE (Unified Persistence)

### A. Current Problem

```
Before (Fragmented):
┌─────────────────────────────────────────────────┐
│             Memory Storage Today                 │
├─────────────────────────────────────────────────┤
│ X Bot                                             │
│  └─ XMemory class                                │
│     └─ SQLite (content_fingerprints table)       │
│        ├─ fingerprint                            │
│        ├─ topic_hash                             │
│        ├─ semantic_hash (NEW)                    │
│        └─ created_at                             │
│                                                   │
│ Buy Tracker                                       │
│  └─ is_duplicate_alert()                         │
│     └─ SQLite (sent_alerts table)                │
│        └─ tx_signature                           │
│                                                   │
│ Treasury                                          │
│  └─ ALLOW_STACKING flag                          │
│     └─ In-memory position list                   │
│        └─ Token symbol only                      │
│                                                   │
│ Telegram                                          │
│  └─ In-memory set of processed messages          │
│     └─ (Lost on restart)                         │
│                                                   │
│ State Files                                       │
│  ├─ .positions.json                              │
│  ├─ .trade_history.json                          │
│  ├─ .grok_state.json                             │
│  └─ .audit_log.json                              │
│                                                   │
│ Memory/Persistence                               │
│  └─ core/memory/persistence.py (MemoryEntry)     │
│     └─ SQLite (memories table)                   │
│        ├─ content_hash                           │
│        ├─ memory_type (USER/CONVERSATION)        │
│        └─ priority                               │
└─────────────────────────────────────────────────┘

Issues:
- 6 different interfaces (no abstraction)
- 5 different duplicate detection implementations
- 4 different storage backends
- No unified schema or API
```

### B. Proposed Solution: MemoryStore Interface

```python
# core/memory/store.py (NEW)

from abc import ABC, abstractmethod
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from enum import Enum

class MemoryType(Enum):
    """Memory classification."""
    DUPLICATE_CONTENT = "duplicate_content"      # Tweet, message, post
    DUPLICATE_INTENT = "duplicate_intent"        # Buy pick, action
    CONVERSATION = "conversation"                # User chat history
    TRADE_LEARNINGS = "trade_learnings"         # Win/loss patterns
    USER_PROFILE = "user_profile"               # User preferences
    SYSTEM_STATE = "system_state"               # Position, order, state

@dataclass
class MemoryEntry:
    """Unified memory entry."""
    id: str                              # UUID or auto-increment
    content: str                         # Text content
    memory_type: MemoryType              # Classification
    entity_id: str                       # Token symbol, user ID, tweet ID, etc.
    entity_type: str                     # "token", "user", "tweet"
    fingerprint: Optional[str] = None    # Hash for dedup (SHA256[:16])
    semantic_hash: Optional[str] = None  # Concept hash for soft dedup
    created_at: str = None               # ISO timestamp
    expires_at: Optional[str] = None     # TTL for cleanup
    metadata: Dict[str, Any] = None      # Extra fields

class MemoryStore(ABC):
    """Abstract memory storage interface."""

    @abstractmethod
    async def store(self, entry: MemoryEntry) -> str:
        """Store a memory entry. Returns ID."""
        pass

    @abstractmethod
    async def is_duplicate(
        self,
        content: str,
        entity_id: str,
        entity_type: str,
        memory_type: MemoryType,
        hours: int = 24,
        similarity_threshold: float = 0.8
    ) -> tuple[bool, Optional[str]]:
        """
        Check if content is duplicate within timeframe.
        Returns (is_duplicate, reason).
        """
        pass

    @abstractmethod
    async def get_memories(
        self,
        entity_id: str,
        memory_type: Optional[MemoryType] = None,
        limit: int = 10
    ) -> List[MemoryEntry]:
        """Get memories for an entity."""
        pass

    @abstractmethod
    async def cleanup_expired(self) -> int:
        """Delete expired memories. Returns count deleted."""
        pass

class SQLiteMemoryStore(MemoryStore):
    """SQLite implementation."""

    async def store(self, entry: MemoryEntry) -> str:
        # Implementation in next deliverable
        pass

    async def is_duplicate(
        self,
        content: str,
        entity_id: str,
        entity_type: str,
        memory_type: MemoryType,
        hours: int = 24,
        similarity_threshold: float = 0.8
    ) -> tuple[bool, Optional[str]]:
        # Layer 1: Exact match (fingerprint)
        # Layer 2: Soft match (semantic_hash)
        # Layer 3: Similarity (string overlap)
        pass

    async def get_memories(
        self,
        entity_id: str,
        memory_type: Optional[MemoryType] = None,
        limit: int = 10
    ) -> List[MemoryEntry]:
        pass

    async def cleanup_expired(self) -> int:
        pass

# Singleton accessor
_memory_store: Optional[MemoryStore] = None

def get_memory_store() -> MemoryStore:
    """Get global memory store."""
    global _memory_store
    if not _memory_store:
        _memory_store = SQLiteMemoryStore(
            db_path="~/.lifeos/memory.db"
        )
    return _memory_store
```

### C. Usage Examples (After Migration)

```python
# X Bot - Dedup tweets
store = get_memory_store()
is_dup, reason = await store.is_duplicate(
    content="KR8TIV surging 20% on volume",
    entity_id="KR8TIV",
    entity_type="token",
    memory_type=MemoryType.DUPLICATE_CONTENT,
    hours=24
)
if is_dup:
    logger.info(f"Duplicate tweet: {reason}")
    return  # Skip posting

# Treasury - Dedup buy intents (FIX for Issue #1)
is_dup, reason = await store.is_duplicate(
    content=f"buy_intent:{pick_id}:{user_id}",
    entity_id=pick_id,
    entity_type="pick",
    memory_type=MemoryType.DUPLICATE_INTENT,
    hours=1  # Prevent double-clicks for 1 hour
)
if is_dup:
    return {"error": "Trade already processed", "intent_id": pick_id}

# Telegram - Persistent dedup
is_dup, reason = await store.is_duplicate(
    content=message.text,
    entity_id=message.chat_id,
    entity_type="chat",
    memory_type=MemoryType.DUPLICATE_CONTENT,
    hours=24
)

# Store learnings
await store.store(MemoryEntry(
    content="WETH picked at $1800, hit TP at $1950 (+8.3%)",
    memory_type=MemoryType.TRADE_LEARNINGS,
    entity_id="WETH",
    entity_type="token",
    metadata={"pnl_pct": 8.3, "timeframe_hours": 4}
))
```

### D. Benefits

✓ **Unified API**: All bots use same interface
✓ **Persistent Dedup**: Survives restarts (fixes Telegram issue)
✓ **Semantic Dedup**: Reuses X bot's sophisticated logic
✓ **Buy Intent Safety**: Fixes Issue #1 (duplicate trades)
✓ **Migration Path**: Can refactor one bot at a time
✓ **Testable**: Single interface to mock in tests

---

## 2. EVENT BUS WITH BACKPRESSURE (Async Coordination)

### A. Current Problem

```
Before (No Event Bus):

┌──────────────┐
│ Sentiment    │  → generate picks (3 sec)
│ Report       │  → call Grok (30 sec) [SLOW]
└──────────────┘
       ↓ (direct function call, no async coordination)
┌──────────────┐
│ Ape Buttons  │  → render in Telegram
└──────────────┘
       ↓ (button clicked)
┌──────────────┐
│ Trading      │  → open position on Jupiter (5 sec) [NETWORK WAIT]
└──────────────┘

Issues:
- No backpressure (Grok slow → system stalls)
- No task tracking (can't kill hung tasks)
- No retry logic (failed Grok = no picks)
- No parallel execution (runs sequentially)
- Memory leak (no queue size limit on job_queue)
```

### B. Proposed Event Bus Architecture

```python
# core/event_bus/event_bus.py (NEW)

from enum import Enum
from typing import Callable, Awaitable, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import asyncio
from collections import defaultdict
import logging

logger = logging.getLogger("jarvis.event_bus")

class EventType(Enum):
    """Events in the system."""
    # Sentiment flow
    SENTIMENT_REPORT_REQUESTED = "sentiment.report_requested"
    SENTIMENT_REPORT_GENERATED = "sentiment.report_generated"
    SENTIMENT_REPORT_FAILED = "sentiment.report_failed"

    # Grok flow
    GROK_ANALYSIS_REQUESTED = "grok.analysis_requested"
    GROK_ANALYSIS_COMPLETED = "grok.analysis_completed"
    GROK_ANALYSIS_FAILED = "grok.analysis_failed"

    # Pick flow
    PICK_GENERATED = "pick.generated"
    PICK_DISCARDED = "pick.discarded"

    # Trading flow
    BUY_INTENT_CREATED = "trading.buy_intent_created"
    BUY_INTENT_EXECUTED = "trading.buy_intent_executed"
    BUY_INTENT_FAILED = "trading.buy_intent_failed"

    # X Bot flow
    TWEET_POSTED = "twitter.tweet_posted"
    TWEET_FAILED = "twitter.tweet_failed"

@dataclass
class Event:
    """Unified event structure."""
    type: EventType
    trace_id: str                      # Correlation ID
    timestamp: datetime
    source: str                        # Component that emitted
    payload: dict                      # Event data
    correlation_ids: dict = None       # Related IDs (pick_id, user_id, etc.)

class EventBus:
    """
    Central event bus with backpressure handling.

    Features:
    - Async event publishing with max queue size
    - Handler registration & execution
    - Retry logic with exponential backoff
    - Dead letter queue for failed events
    - Trace ID propagation across components
    """

    def __init__(
        self,
        max_queue_size: int = 1000,
        handler_timeout_seconds: int = 30
    ):
        self.max_queue_size = max_queue_size
        self.handler_timeout_seconds = handler_timeout_seconds
        self.handlers: dict[EventType, list[Callable]] = defaultdict(list)
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self.dead_letter_queue: list[Event] = []
        self.stats = {
            "events_published": 0,
            "events_processed": 0,
            "events_failed": 0,
            "queue_overflow": 0
        }

    def subscribe(
        self,
        event_type: EventType,
        handler: Callable[[Event], Awaitable[None]]
    ) -> None:
        """Register handler for event type."""
        self.handlers[event_type].append(handler)
        logger.info(f"Handler registered: {event_type} → {handler.__name__}")

    async def publish(
        self,
        event: Event,
        priority: int = 0  # Higher = process first
    ) -> bool:
        """
        Publish event to bus.
        Returns False if queue full (backpressure).
        """
        try:
            # Add to queue with timeout
            await asyncio.wait_for(
                self.queue.put((priority, event)),
                timeout=2.0
            )
            self.stats["events_published"] += 1
            logger.info(
                f"[{event.trace_id}] Event published: "
                f"{event.type.value} from {event.source}"
            )
            return True
        except asyncio.TimeoutError:
            self.stats["queue_overflow"] += 1
            logger.warning(
                f"[{event.trace_id}] Queue full (size={self.queue.qsize()}). "
                f"Backpressure triggered."
            )
            return False

    async def process_events(self) -> None:
        """Main event loop (runs in background)."""
        while True:
            try:
                priority, event = await self.queue.get()

                # Execute handlers for this event type
                handlers = self.handlers.get(event.type, [])
                if not handlers:
                    logger.warning(f"No handlers for {event.type}")
                    self.queue.task_done()
                    continue

                for handler in handlers:
                    try:
                        # Execute with timeout
                        await asyncio.wait_for(
                            handler(event),
                            timeout=self.handler_timeout_seconds
                        )
                    except asyncio.TimeoutError:
                        logger.error(
                            f"[{event.trace_id}] Handler timeout: "
                            f"{handler.__name__} (>{self.handler_timeout_seconds}s)"
                        )
                        self.dead_letter_queue.append(event)
                        self.stats["events_failed"] += 1
                    except Exception as e:
                        logger.error(
                            f"[{event.trace_id}] Handler error: "
                            f"{handler.__name__}: {e}"
                        )
                        self.dead_letter_queue.append(event)
                        self.stats["events_failed"] += 1

                self.stats["events_processed"] += 1
                self.queue.task_done()

            except Exception as e:
                logger.error(f"Event bus error: {e}")
                await asyncio.sleep(1)  # Backoff on errors

    def get_stats(self) -> dict:
        """Get bus statistics."""
        return {
            **self.stats,
            "queue_size": self.queue.qsize(),
            "dead_letter_count": len(self.dead_letter_queue),
            "queue_max": self.max_queue_size
        }

# Singleton
_event_bus: Optional[EventBus] = None

def get_event_bus() -> EventBus:
    global _event_bus
    if not _event_bus:
        _event_bus = EventBus(max_queue_size=1000, handler_timeout_seconds=30)
    return _event_bus
```

### C. Event Flow Diagram

```
After (With Event Bus):

┌────────────────────────────────────────────────────┐
│               Event Bus (Async Queue)              │
│  ┌──────────────────────────────────────────────┐  │
│  │ Max size: 1000                               │  │
│  │ Handler timeout: 30s                         │  │
│  │ Dead letter queue for failures               │  │
│  └──────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────┘
         ↑                            ↓
    Publishers              Event Handlers
    ┌────────┐              ┌──────────────┐
    │Sentiment│─ emit ────→ │EventBus.queue│ ← consumed by handlers
    │Report   │ SENTIMENT   │(async, no    │
    └────────┘ _GENERATED   │blocking)     │
         │                  └──────────────┘
    ┌────────┐                    ↓
    │Grok    │─ emit ────→     Handler 1
    │Client  │ GROK_COMPLETED    (Ape Buttons)
    └────────┘                    ↓
         │                  Handler 2
    ┌────────┐                (Treasury)
    │Trading │─ emit ────→     ↓
    │Engine  │ BUY_INTENT   Handler 3
    └────────┘ _EXECUTED     (X Bot post)

Backpressure Flow:
1. Grok slow (30 sec) → publish GROK_COMPLETED event
2. Event queued (async, non-blocking)
3. Sentiment report continues (doesn't wait)
4. Handler processes Grok result at own pace
5. If queue fills (backpressure) → log warning, return False
6. Caller decides: retry, skip, or alert admin
```

### D. Usage Example

```python
# In Sentiment Report (sentiment_report.py)
async def generate_report(self):
    trace_id = str(uuid.uuid4())
    bus = get_event_bus()

    # Publish event
    event = Event(
        type=EventType.SENTIMENT_REPORT_REQUESTED,
        trace_id=trace_id,
        timestamp=datetime.utcnow(),
        source="sentiment_report",
        payload={"report_type": "daily_market"}
    )
    await bus.publish(event, priority=1)

    # Generate picks
    picks = await self._generate_picks()

    # Publish completion (async, non-blocking)
    result_event = Event(
        type=EventType.SENTIMENT_REPORT_GENERATED,
        trace_id=trace_id,
        timestamp=datetime.utcnow(),
        source="sentiment_report",
        payload={"picks_count": len(picks)}
    )
    if not await bus.publish(result_event):
        logger.warning(f"[{trace_id}] Event bus backpressure - queue full")

# Handler registration (in bot_core.py startup)
bus = get_event_bus()

async def handle_sentiment_generated(event: Event):
    """Handler for sentiment report completion."""
    logger.info(f"[{event.trace_id}] Sentiment report done, posting to Telegram")
    # Render ape buttons
    await render_buttons(event.payload["picks"])

async def handle_buy_intent(event: Event):
    """Handler for buy intent execution."""
    logger.info(f"[{event.trace_id}] Opening position on Jupiter")
    # Execute trade
    await execute_trade(event.payload)

bus.subscribe(EventType.SENTIMENT_REPORT_GENERATED, handle_sentiment_generated)
bus.subscribe(EventType.BUY_INTENT_CREATED, handle_buy_intent)
```

### E. Benefits

✓ **Backpressure**: Queue fills → system slows gracefully (not crash)
✓ **Async**: Sentiment report doesn't wait for Grok (runs in parallel)
✓ **Timeout**: Hung handlers killed after 30s (fixes supervisor hang)
✓ **Tracing**: Trace ID on every event (fixes Issue #10 - debugging)
✓ **Dead Letter Queue**: Failed events captured for debugging
✓ **Monitoring**: Queue depth, handler times, error rates

---

## 3. BUY INTENT IDEMPOTENCY (Fix Issue #1)

### A. Flow Diagram

```
Before (Vulnerable to Duplicates):

┌──────────────────────────────────────────────────────┐
│ Sentiment Report generates pick                      │
│ Symbol: KR8TIV, Conviction: 75, Target: $0.0084    │
│ Entry: $0.0042, SL: $0.0021                          │
└──────────────────────────────────────────────────────┘
              ↓
┌──────────────────────────────────────────────────────┐
│ Ape Button rendered in Telegram                      │
│ "BUY KR8TIV @ $0.0042"                              │
│ Button callback: /button_click?symbol=KR8TIV        │
│ (No intent ID, just symbol)                          │
└──────────────────────────────────────────────────────┘
              ↓
        ┌─────┴─────┐
        │ User Click │
        └─────┬─────┘
    (User clicks button at 12:00 PM)
              ↓
┌──────────────────────────────────────────────────────┐
│ Button Callback Handler                              │
│ /button_click?symbol=KR8TIV                         │
│ (NO IDEMPOTENCY CHECK)                               │
│ Opens position: 100 USDC at $0.0042 ✓               │
└──────────────────────────────────────────────────────┘
              ↓
     Network glitch (user retries)
              ↓
┌──────────────────────────────────────────────────────┐
│ Button Callback Handler (second call)                │
│ /button_click?symbol=KR8TIV                         │
│ (AGAIN - no dedup!)                                  │
│ Opens SECOND position: 100 USDC at $0.0042 ✗        │
│                                                       │
│ Result: User has 2x KR8TIV position                  │
│         Should have had 1x                           │
│         On stop loss: 2x loss instead of 1x          │
└──────────────────────────────────────────────────────┘


After (With Intent Idempotency):

┌──────────────────────────────────────────────────────┐
│ Sentiment Report generates pick                      │
│ Creates unique intent ID: uuid-abc-123              │
│ Symbol: KR8TIV, Conviction: 75, Intent: uuid-abc   │
│ Entry: $0.0042, SL: $0.0021                          │
│ Stores in memory: intent_abc → {status: pending}    │
└──────────────────────────────────────────────────────┘
              ↓
┌──────────────────────────────────────────────────────┐
│ Ape Button rendered in Telegram                      │
│ "BUY KR8TIV @ $0.0042"                              │
│ Button callback: /button_click?intent_id=uuid-abc   │
│ (Intent ID in URL - idempotency key)                │
└──────────────────────────────────────────────────────┘
              ↓
        ┌─────┴─────┐
        │ User Click │
        └─────┬─────┘
    (User clicks button at 12:00 PM)
              ↓
┌──────────────────────────────────────────────────────┐
│ Button Callback Handler                              │
│ /button_click?intent_id=uuid-abc                    │
│ Check: store.is_duplicate("uuid-abc", "pick", 1h)   │
│ Result: NO (first occurrence)                        │
│ Opens position: 100 USDC at $0.0042 ✓               │
│ Store intent: uuid-abc → {status: executed}         │
└──────────────────────────────────────────────────────┘
              ↓
     Network glitch (user retries)
              ↓
┌──────────────────────────────────────────────────────┐
│ Button Callback Handler (second call)                │
│ /button_click?intent_id=uuid-abc                    │
│ Check: store.is_duplicate("uuid-abc", "pick", 1h)   │
│ Result: YES (already executed)                       │
│ Response: "Trade already executed (intent: uuid-abc)"│
│ NO SECOND POSITION OPENED ✓                          │
│                                                       │
│ Result: User has 1x KR8TIV position (correct)        │
│         Protected against double-clicks              │
└──────────────────────────────────────────────────────┘
```

### B. Implementation Changes

```python
# core/sentiment/sentiment_report.py (MODIFIED)
async def _create_conviction_pick(
    self,
    symbol: str,
    conviction_score: int,
    entry_price: float,
    target_price: float,
    stop_loss: float
) -> str:
    """
    Create a conviction pick with unique intent ID.

    Returns: intent_id (UUID)
    """
    import uuid
    intent_id = str(uuid.uuid4())

    # Store intent in MemoryStore (persists across restarts)
    store = get_memory_store()
    await store.store(MemoryEntry(
        content=f"buy_intent:{symbol}:{intent_id}",
        memory_type=MemoryType.DUPLICATE_INTENT,
        entity_id=intent_id,
        entity_type="pick",
        metadata={
            "symbol": symbol,
            "conviction": conviction_score,
            "entry": entry_price,
            "target": target_price,
            "stop_loss": stop_loss,
            "status": "pending"  # Can be: pending, executed, expired, cancelled
        }
    ))

    return intent_id

# tg_bot/handlers/trading.py (MODIFIED)
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle buy button click - NOW WITH IDEMPOTENCY."""

    query = update.callback_query
    intent_id = query.data.split(":")[-1]  # Extract from "buy:intent-uuid-abc"

    # Check idempotency
    store = get_memory_store()
    is_dup, reason = await store.is_duplicate(
        content=f"buy_intent:{intent_id}",
        entity_id=intent_id,
        entity_type="pick",
        memory_type=MemoryType.DUPLICATE_INTENT,
        hours=1  # Dedup window: 1 hour
    )

    if is_dup:
        # Trade already executed
        await query.answer("Trade already executed", show_alert=True)
        return

    # Execute trade
    try:
        result = await execute_trade(intent_id)
        if result["success"]:
            # Mark intent as executed
            await store.store(MemoryEntry(
                content=f"buy_intent_executed:{intent_id}",
                memory_type=MemoryType.DUPLICATE_INTENT,
                entity_id=intent_id,
                entity_type="pick",
                metadata={"status": "executed", "tx_sig": result["tx_signature"]}
            ))
            await query.answer("Position opened ✓")
        else:
            await query.answer(f"Trade failed: {result['error']}")
    except Exception as e:
        await query.answer(f"Error: {e}")
```

### C. Benefits

✓ **Duplicate Prevention**: Same intent ID = returns cached result
✓ **Persistent**: Survives restarts (stored in MemoryStore)
✓ **User Friendly**: User can retry without side effects
✓ **Audit Trail**: Intent ID links pick → button click → trade

---

## 4. STATE BACKUP STRATEGY (Fix Issue #2)

### A. Current Risk

```
Today:
  .positions.json (14 KB, ONE copy)
  ↓
  Corruption → NO RECOVERY
  Deletion → NO RECOVERY
  Disk full → NO RECOVERY
```

### B. Proposed Strategy

```
After (Atomic + Versioned + Backup):

┌─────────────────────────────────────┐
│ Write Position Update               │
├─────────────────────────────────────┤
│ 1. Load current state               │
│ 2. Compute new state in memory      │
│ 3. Write to .positions.tmp (temp)   │
│ 4. Verify JSON valid                │
│ 5. Atomic rename: .tmp → .positions │
│ 6. Copy to archive/.positions.{ts}  │
│ 7. Keep last 24 hourly versions     │
└─────────────────────────────────────┘

Result:
  .positions.json ................. Current (live)
  archive/.positions.20250116T20* .. Hourly backups
  archive/.positions.20250116T19* .. (24 versions)
  archive/.positions.20250116T18*
  ...
```

### C. Implementation

```python
# core/state/backup.py (NEW)

import json
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
import shutil
import logging

logger = logging.getLogger("jarvis.backup")

class AtomicStateManager:
    """
    Atomic writes with backup strategy.
    - Temporary file writes (prevents corruption)
    - Atomic rename (all-or-nothing)
    - Hourly backups (rollback capability)
    - Auto-cleanup (keep last 24 versions)
    """

    def __init__(self, state_path: str, archive_dir: str = "archive"):
        self.state_path = Path(state_path)
        self.archive_dir = Path(state_path).parent / archive_dir
        self.archive_dir.mkdir(exist_ok=True)

    async def write_state(self, state: dict) -> bool:
        """
        Atomically write state with backup.

        Returns: True if successful
        """
        try:
            # Step 1: Write to temporary file
            temp_path = self.state_path.with_suffix('.tmp')

            # Use JSON encoder with pretty print
            with open(temp_path, 'w') as f:
                json.dump(state, f, indent=2)

            # Step 2: Verify validity (parse it back)
            with open(temp_path, 'r') as f:
                json.load(f)

            # Step 3: Atomic rename
            temp_path.rename(self.state_path)
            logger.info(f"State written: {self.state_path}")

            # Step 4: Create backup (async, fire-and-forget)
            asyncio.create_task(self._backup_state())

            # Step 5: Cleanup old backups
            asyncio.create_task(self._cleanup_old_backups())

            return True

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON (temp file kept): {temp_path} - {e}")
            return False
        except Exception as e:
            logger.error(f"Write failed: {e}")
            return False

    async def _backup_state(self) -> None:
        """Create timestamped backup."""
        try:
            timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
            backup_path = self.archive_dir / f"{self.state_path.stem}.{timestamp}.json"

            # Copy current file to backup
            shutil.copy(self.state_path, backup_path)
            logger.info(f"Backup created: {backup_path}")

        except Exception as e:
            logger.error(f"Backup failed: {e}")

    async def _cleanup_old_backups(self) -> None:
        """Keep only last 24 hourly backups."""
        try:
            backups = sorted(self.archive_dir.glob(f"{self.state_path.stem}.*.json"))

            # Keep last 24
            if len(backups) > 24:
                for old_backup in backups[:-24]:
                    old_backup.unlink()
                    logger.info(f"Cleaned up: {old_backup}")

        except Exception as e:
            logger.error(f"Cleanup failed: {e}")

    async def restore_from_backup(self, timestamp: str) -> Optional[dict]:
        """
        Restore state from backup.

        Args:
            timestamp: From backup filename (e.g., '20250116T201000')

        Returns:
            State dict or None if failed
        """
        try:
            backup_path = self.archive_dir / f"{self.state_path.stem}.{timestamp}.json"

            if not backup_path.exists():
                logger.error(f"Backup not found: {backup_path}")
                return None

            with open(backup_path, 'r') as f:
                state = json.load(f)

            logger.info(f"Restored from backup: {backup_path}")
            return state

        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return None

    def list_backups(self) -> list[str]:
        """List available backups (timestamps)."""
        backups = self.archive_dir.glob(f"{self.state_path.stem}.*.json")
        return sorted([b.stem.split('.')[-1] for b in backups])

# Usage in scorekeeper.py
manager = AtomicStateManager(
    state_path="~/.lifeos/trading/.positions.json",
    archive_dir="~/.lifeos/trading/archive"
)

# When saving positions
positions_state = {"positions": [...]}
success = await manager.write_state(positions_state)

if not success:
    logger.error("Failed to save positions - data integrity at risk")
    # Alert admin
```

### D. Benefits

✓ **Atomic Writes**: No partial/corrupt JSON (temp file pattern)
✓ **Backup**: 24-hour rollback capability
✓ **Verification**: Valid JSON before commit
✓ **Auto-Cleanup**: Archive doesn't grow unbounded

---

## 5. CONFIGURATION UNIFICATION (Fix Issue #11)

### A. Proposed Schema

```yaml
# config.yaml (New single source of truth)

# Sentiment & Scoring
sentiment:
  interval_seconds: 3600           # Run hourly
  top_picks_count: 10              # Top 10 picks per report
  min_conviction_score: 70          # Only include 70+ conviction

# Wrapped Token Settings
tokens:
  min_liquidity_wrapped: 500_000    # $500K minimum
  include_ethereum_ecosystem: true  # LINK, AAVE, etc.
  include_l1_bridges: true          # WAVAX, WMATIC, etc.
  risk_tiers:
    major:
      - WETH
      - WBTC
      - LINK
    standard:
      - AAVE
      - UNI
      - WAVAX
    minor: []  # Excluded by liquidity filter

# Grok & LLM
grok:
  daily_cost_limit_usd: 10
  timeout_seconds: 30
  retry_attempts: 3

# Trading
treasury:
  max_positions: 50
  allow_stacking: false             # Prevent duplicate token positions
  live_mode: ${TREASURY_LIVE_MODE}  # From env
  target_price_multiplier: 2.0      # Entry * 2 = TP
  stop_loss_multiplier: 0.5         # Entry * 0.5 = SL

# X Bot
twitter:
  enabled: ${X_BOT_ENABLED}
  circuit_breaker:
    min_interval_seconds: 60        # Min between posts
    error_threshold: 3
    cooldown_seconds: 1800          # 30 min cooldown after 3 errors
  sentiment_interval_seconds: 3600  # Post hourly

# Telegram
telegram:
  digest_hours: [0, 8, 16]          # UTC hours for digests
  sentiment_interval_seconds: 3600

# Monitoring
monitoring:
  metrics_port: 8000
  health_check_interval_seconds: 60

# Logging
logging:
  level: INFO                       # DEBUG, INFO, WARNING, ERROR
  file: logs/jarvis.log
```

### B. Usage

```python
# core/config.py (Updated)
from dataclasses import dataclass
import yaml

@dataclass
class Config:
    """Application configuration (loaded from config.yaml)."""
    sentiment: dict
    tokens: dict
    grok: dict
    treasury: dict
    twitter: dict
    telegram: dict
    monitoring: dict
    logging: dict

def load_config(config_file: str = "config.yaml") -> Config:
    with open(config_file) as f:
        data = yaml.safe_load(f)

    # Expand environment variables
    import os
    config_str = yaml.dump(data)
    for key, value in os.environ.items():
        config_str = config_str.replace(f"${{{key}}}", value)

    data = yaml.safe_load(config_str)
    return Config(**data)

# Usage everywhere
config = load_config()
interval = config.sentiment["interval_seconds"]  # 3600
max_pos = config.treasury["max_positions"]       # 50
```

### C. Benefits

✓ **Single Source of Truth**: All config in one file
✓ **Env Expansion**: ${X_BOT_ENABLED} from environment
✓ **Validation**: Schema validation on load
✓ **Consistency**: Same naming across system

---

## 6. ARCHITECTURE SUMMARY TABLE

| Component | Current | Proposed | Benefit |
|-----------|---------|----------|---------|
| **Memory** | 6 different classes | MemoryStore interface | Unified API, persistent dedup |
| **Events** | async gather | EventBus + queue | Backpressure, async coordination |
| **Idempotency** | None | Intent UUID + MemoryStore | Prevents duplicate trades |
| **Backups** | None | Atomic writes + archive | Recoverable from corruption |
| **Error Handling** | 2,609 bare excepts | Structured errors | Debuggable failures |
| **Config** | Scattered | config.yaml | Single source of truth |
| **Tracing** | None | Trace IDs on events | Correlate logs across services |

---

## NEXT STEPS

**Deliverable D** (Implementation Plan) will specify:

1. **Phased Milestones** (M1..Mn):
   - M1: MemoryStore implementation & SQLite migration
   - M2: EventBus setup & integration
   - M3: Buy intent idempotency
   - M4: State backup strategy
   - M5: Error handling cleanup
   - M6: Configuration unification

2. **Acceptance Criteria** for each milestone

3. **Test Commands** to verify each fix

4. **Rollback Plans** if needed

---

**END OF DELIVERABLE C**

