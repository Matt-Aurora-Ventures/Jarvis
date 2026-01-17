# JARVIS Audit - Deliverable D: Implementation Plan

**Date**: 2026-01-16
**Purpose**: Phased implementation roadmap with acceptance criteria
**Approach**: 6 sequential milestones, each with tests and rollback plans
**Duration**: ~80-100 hours (estimated)

---

## IMPLEMENTATION STRATEGY

**Phased Approach**:
1. **M1**: MemoryStore interface (foundational - enables M2, M3)
2. **M2**: EventBus implementation (enables M4, M6)
3. **M3**: Buy intent idempotency (uses M1)
4. **M4**: State backup strategy (standalone, but tested with M1)
5. **M5**: Error handling cleanup (quality pass)
6. **M6**: Configuration unification (refactoring, last)

**Why This Order**:
- M1 & M2 are blockers (multiple features depend on them)
- M3 fixes critical Issue #1 (duplicate trades) ASAP
- M4 fixes critical Issue #2 (state loss) early
- M5 & M6 are quality improvements (can defer if needed)

**Testing Approach** (Ralph Wiggum Loop):
```
Milestone N:
  1. Write code ← Implement M1 changes
  2. Run unit tests ← Verify isolated functionality
  3. Run integration tests ← Verify with dependent systems
  4. Manual test ← Reproduce original issue, verify fixed
  5. Check error logs ← Scan for new warnings/errors
  6. Fix any issues ← If tests fail, iterate
  7. Merge to main ← Commit when all tests pass
  → Repeat for M2, M3, ...

"No stop until fully functional" = loop until all 6 milestones pass all tests.
```

---

## M1: MEMORYSTORE INTERFACE & SQLITE MIGRATION

### Scope

**Delivers**:
- Core MemoryStore ABC (abstract base class)
- SQLiteMemoryStore implementation
- Migration: X bot → MemoryStore
- Test coverage

**Files To Create**:
- `core/memory/store.py` ← NEW (interface + SQLite impl)
- `core/memory/__init__.py` ← NEW (export MemoryStore)
- `tests/test_memory_store.py` ← NEW (unit tests)
- `tests/integration/test_x_bot_memory.py` ← NEW (integration)

**Files To Modify**:
- `bots/twitter/autonomous_engine.py` ← Refactor to use MemoryStore
- `bots/twitter/bot.py` ← Update imports

### Implementation Tasks

```
M1.1 Create MemoryStore interface (300 lines)
     - Enum: MemoryType
     - Dataclass: MemoryEntry
     - ABC: MemoryStore
     - Methods: store(), is_duplicate(), get_memories(), cleanup_expired()
     Estimated: 2h

M1.2 Implement SQLiteMemoryStore (500 lines)
     - Database schema migration
     - Fingerprint + semantic_hash (3-layer detection)
     - TTL-based cleanup
     - Indexes for performance
     Estimated: 4h

M1.3 Refactor X bot to use MemoryStore (200 lines changed)
     - Replace XMemory.is_duplicate_fingerprint() → store.is_duplicate()
     - Replace XMemory.record_fingerprint() → store.store()
     - Remove old fingerprint table queries
     Estimated: 2h

M1.4 Unit tests (300 lines)
     - Test store() and retrieve()
     - Test is_duplicate() with exact, topic, semantic matches
     - Test TTL cleanup
     - Test index queries
     Estimated: 3h

M1.5 Integration tests (200 lines)
     - X bot posting with dedup enabled
     - Verify semantic duplicates caught
     - Verify old fingerprints cleaned after 24h
     Estimated: 2h

M1.6 Review & bugfix (iterate)
     Estimated: 1-2h
```

**Total M1**: ~14-16 hours

### Acceptance Criteria

**AC1.1**: MemoryStore interface defined
- [ ] `MemoryStore` ABC exists at `core/memory/store.py`
- [ ] 5 abstract methods: store, is_duplicate, get_memories, cleanup_expired, get_stats
- [ ] MemoryEntry dataclass with 8+ fields
- [ ] MemoryType enum with ≥4 types

**AC1.2**: SQLiteMemoryStore implementation complete
- [ ] Database at `~/.lifeos/memory.db` created on startup
- [ ] Table `memories` with columns: id, content, content_hash, memory_type, entity_id, entity_type, fingerprint, semantic_hash, created_at, expires_at, metadata
- [ ] Indexes on: fingerprint, semantic_hash, entity_id, created_at
- [ ] `store()` creates MemoryEntry (returns ID)
- [ ] `is_duplicate()` implements 3-layer detection (exact → topic → semantic)
- [ ] `cleanup_expired()` removes entries where expires_at < now

**AC1.3**: X bot successfully migrated
- [ ] No more direct SQLite queries to `content_fingerprints`
- [ ] All dedup calls via `store.is_duplicate()`
- [ ] All recording via `store.store()`
- [ ] Tests pass: X bot still catches exact and semantic duplicates

**AC1.4**: No regressions
- [ ] Duplicate detection sensitivity same as before (not stricter/looser)
- [ ] Performance ≥ same (added indexes compensate for abstraction)
- [ ] Backward compatible: old tweets in content_fingerprints table still loaded

### Test Commands

```bash
# Unit tests
python -m pytest tests/test_memory_store.py -v

# Expected output:
#   test_memory_store.py::test_store_creates_entry PASSED
#   test_memory_store.py::test_is_duplicate_exact_match PASSED
#   test_memory_store.py::test_is_duplicate_semantic_match PASSED
#   test_memory_store.py::test_cleanup_expired PASSED
#   ===== 4 passed in 0.45s =====

# Integration tests
python -m pytest tests/integration/test_x_bot_memory.py -v

# Manual test: Post duplicates, verify filtered
python -c "
from bots.twitter.autonomous_engine import XMemory
from core.memory.store import get_memory_store, MemoryType

store = get_memory_store()

# Simulate X bot dedup
content1 = 'KR8TIV surging 20% on volume'
is_dup1, reason1 = await store.is_duplicate(
    content=content1,
    entity_id='KR8TIV',
    entity_type='token',
    memory_type=MemoryType.DUPLICATE_CONTENT,
    hours=24
)
print(f'First post: is_dup={is_dup1}')  # Should be False

# Record it
await store.store(MemoryEntry(
    content=content1,
    memory_type=MemoryType.DUPLICATE_CONTENT,
    entity_id='KR8TIV',
    entity_type='token',
    fingerprint='abc123',
    semantic_hash='def456'
))

# Try to post same content (different wording)
content2 = 'KR8TIV spiking hard 20% volume wave'
is_dup2, reason2 = await store.is_duplicate(
    content=content2,
    entity_id='KR8TIV',
    entity_type='token',
    memory_type=MemoryType.DUPLICATE_CONTENT,
    hours=24
)
print(f'Semantic duplicate: is_dup={is_dup2}, reason={reason2}')  # Should be True
"

# Error log check
grep -i "error\|warning" ~/.lifeos/memory.db.log 2>/dev/null
# Should show: 0 errors during migration
```

### Rollback Plan

```bash
# If M1 breaks X bot:

Step 1: Restore old code
  git checkout HEAD -- bots/twitter/autonomous_engine.py

Step 2: Keep MemoryStore (used by M2, M3)
  # Don't revert core/memory/store.py

Step 3: Test
  python -m pytest tests/twitter/ -v
  # Verify X bot works with old dedup code

Step 4: Investigate failure
  # Review git diff core/memory/store.py bots/twitter/autonomous_engine.py
  # Find breaking change
  # Fix and re-apply
```

---

## M2: EVENT BUS IMPLEMENTATION

### Scope

**Delivers**:
- EventBus class with async queue
- Handler registration system
- Dead letter queue for failed events
- Integration with bots/supervisor.py

**Files To Create**:
- `core/event_bus/event_bus.py` ← NEW (EventBus class)
- `core/event_bus/__init__.py` ← NEW (exports)
- `tests/test_event_bus.py` ← NEW (unit tests)

**Files To Modify**:
- `bots/supervisor.py` ← Remove bare `asyncio.gather()`, use EventBus
- `bots/sentiment_report.py` ← Publish events instead of direct calls
- `tg_bot/bot.py` ← Register event handlers

### Implementation Tasks

```
M2.1 Define EventType enum (100 lines)
     - SENTIMENT_REPORT_REQUESTED
     - SENTIMENT_REPORT_GENERATED
     - GROK_ANALYSIS_COMPLETED
     - BUY_INTENT_CREATED
     - BUY_INTENT_EXECUTED
     - TWEET_POSTED
     - And 5+ more event types
     Estimated: 1h

M2.2 Implement EventBus (400 lines)
     - Async queue with max size
     - Handler registration
     - Timeout wrapping
     - Dead letter queue
     - Statistics tracking
     Estimated: 4h

M2.3 Integrate with supervisor (100 lines changed)
     - Create event loop in supervisor startup
     - Replace gather() with event publishing
     - Monitor queue depth
     Estimated: 2h

M2.4 Register handlers (200 lines)
     - Sentiment report publishes SENTIMENT_REPORT_GENERATED
     - Ape buttons subscribe to generate event
     - Treasury subscribes to BUY_INTENT_CREATED
     Estimated: 2h

M2.5 Unit tests (250 lines)
     - Test publish/subscribe
     - Test backpressure (queue full)
     - Test handler timeout
     - Test dead letter queue
     Estimated: 3h

M2.6 Integration test with bots (200 lines)
     - Sentiment report → Ape buttons → Trading (async chain)
     - Verify no blocking
     - Verify events in dead letter if handler timeout
     Estimated: 2h

M2.7 Iterate & debug
     Estimated: 2-3h
```

**Total M2**: ~16-18 hours

### Acceptance Criteria

**AC2.1**: EventType enum complete
- [ ] ≥15 event types defined
- [ ] Covers: Sentiment → Grok → Pick → Trading → X → Telegram flows

**AC2.2**: EventBus functional
- [ ] `publish()` method works (returns True on success)
- [ ] `subscribe()` registers handlers
- [ ] `process_events()` runs in background
- [ ] Queue size configurable (default 1000)
- [ ] Handler timeout configurable (default 30s)
- [ ] Dead letter queue populated on failures

**AC2.3**: No blocking in publish
- [ ] `await bus.publish(event)` returns immediately (doesn't wait for handler)
- [ ] Handler runs async in background
- [ ] Sentiment report doesn't wait for Grok result (parallel execution)

**AC2.4**: Backpressure handling
- [ ] Queue fills to max size
- [ ] Further `publish()` calls return False (or raise exception)
- [ ] Caller can decide: retry, skip, or alert

**AC2.5**: Trace ID propagation
- [ ] Every event has trace_id
- [ ] Trace ID logged on every handler execution
- [ ] Enables correlation across services

### Test Commands

```bash
# Unit tests
python -m pytest tests/test_event_bus.py -v

# Expected: All tests pass, backpressure working
#   test_event_bus.py::test_publish_subscribe PASSED
#   test_event_bus.py::test_backpressure_queue_full PASSED
#   test_event_bus.py::test_handler_timeout PASSED
#   test_event_bus.py::test_dead_letter_queue PASSED

# Integration: Test sentiment report with events
python -c "
import asyncio
from core.event_bus import get_event_bus, EventType, Event
from bots.buy_tracker.sentiment_report import SentimentReport

async def test():
    bus = get_event_bus()
    sr = SentimentReport()

    # Subscribe to sentiment completion
    async def on_sentiment_done(event: Event):
        print(f'[{event.trace_id}] Sentiment done: {event.payload}')

    bus.subscribe(EventType.SENTIMENT_REPORT_GENERATED, on_sentiment_done)

    # Run sentiment report (publishes event on completion)
    await sr.generate_report()

    # Give event bus time to process
    await asyncio.sleep(2)

    # Check stats
    stats = bus.get_stats()
    print(f'Events processed: {stats[\"events_processed\"]}')
    print(f'Queue depth: {stats[\"queue_size\"]}')

    assert stats['events_processed'] > 0, 'No events processed'
    print('✓ EventBus integration test passed')

asyncio.run(test())
"

# Stress test: Queue behavior under load
python -c "
import asyncio
from core.event_bus import get_event_bus, EventType, Event

async def stress():
    bus = get_event_bus()

    # Slow handler (5 sec each)
    async def slow_handler(event: Event):
        await asyncio.sleep(5)

    bus.subscribe(EventType.TEST, slow_handler)

    # Publish 100 events rapidly
    success = 0
    failed = 0
    for i in range(100):
        event = Event(
            type=EventType.TEST,
            trace_id=f'test-{i}',
            timestamp=datetime.utcnow(),
            source='test',
            payload={}
        )
        if await bus.publish(event):
            success += 1
        else:
            failed += 1

    print(f'Published: success={success}, backpressure={failed}')
    stats = bus.get_stats()
    print(f'Queue depth: {stats[\"queue_size\"]} (max={stats[\"queue_max\"]})')
    assert stats['queue_overflow'] > 0, 'Backpressure not triggered'
    print('✓ Backpressure working')

asyncio.run(stress())
"

# Check logs for no errors
grep -i "error\|exception" logs/*.log | wc -l
# Should be 0 new errors
```

### Rollback Plan

```bash
# If EventBus causes hangs or regressions:

Step 1: Disable event bus
  # Remove event bus startup from supervisor.py
  # Keep old asyncio.gather() logic temporarily

Step 2: Restore sentiment report
  git checkout HEAD -- bots/buy_tracker/sentiment_report.py

Step 3: Test
  python bots/supervisor.py
  # Verify all bots still run

Step 4: Debug
  # Check if issue is in EventBus itself or integration
  # Review dead_letter_queue for failed events
  tail -100 logs/event_bus.log
```

---

## M3: BUY INTENT IDEMPOTENCY (Using M1)

### Scope

**Depends On**: M1 (MemoryStore)
**Delivers**:
- Intent UUID generation on pick creation
- Intent idempotency check on button click
- Protection against duplicate trades

**Files To Modify**:
- `bots/buy_tracker/sentiment_report.py` ← Generate intent_id
- `tg_bot/handlers/trading.py` ← Check idempotency before trade
- `bots/treasury/trading.py` ← Log intent_id with position

**Files To Create**:
- `tests/test_buy_intent_idempotency.py` ← NEW (test duplicate clicks)

### Implementation Tasks

```
M3.1 Generate intent_id in pick creation (50 lines)
     - Import uuid
     - Create UUID for each pick
     - Store in MemoryStore with status: pending
     Estimated: 1h

M3.2 Pass intent_id to Telegram button (30 lines)
     - Modify button callback data: "buy:intent-{uuid}"
     - Extract intent_id from callback
     Estimated: 0.5h

M3.3 Check idempotency before trade (50 lines)
     - Call store.is_duplicate(intent_id)
     - If duplicate → return cached result
     - If new → execute trade, store result
     Estimated: 1h

M3.4 Link intent_id to position (30 lines)
     - Save intent_id in position metadata
     - Enable audit trail
     Estimated: 0.5h

M3.5 Unit tests (150 lines)
     - Test single click → one position
     - Test double click → error on second
     - Test after timeout (1h) → allows new click
     Estimated: 2h

M3.6 Integration test (100 lines)
     - Simulate user clicking button twice rapidly
     - Verify only one position opened
     - Verify audit log shows both attempts
     Estimated: 1.5h

M3.7 Manual test (simulate network retry)
     Estimated: 1h
```

**Total M3**: ~7-8 hours

### Acceptance Criteria

**AC3.1**: Intent UUID generated
- [ ] Each pick has unique intent_id
- [ ] Intent_id stored in MemoryStore with status: pending
- [ ] Intent_id visible to user (in button callback data)

**AC3.2**: Idempotency check working
- [ ] First button click → executes trade, updates intent status to "executed"
- [ ] Second click (within 1h) → returns "already processed" error
- [ ] After 1h → allows new trade (intent expires)

**AC3.3**: No duplicate positions
- [ ] User clicks twice → only 1 position opened
- [ ] Audit log shows both clicks (both recorded)
- [ ] Second attempt logs: "duplicate intent, already executed"

**AC3.4**: Rollback on error
- [ ] Trade fails (e.g., Jupiter down) → intent marked "failed"
- [ ] User can retry (not stuck in "executed" state)

### Test Commands

```bash
# Unit tests
python -m pytest tests/test_buy_intent_idempotency.py -v

# Expected:
#   test_buy_intent_idempotency.py::test_single_click_opens_position PASSED
#   test_buy_intent_idempotency.py::test_double_click_prevented PASSED
#   test_buy_intent_idempotency.py::test_intent_expires_after_timeout PASSED

# Simulation: Double-click scenario
python -c "
import asyncio
import uuid
from tg_bot.handlers.trading import button_callback
from core.memory.store import get_memory_store, MemoryType

async def test_double_click():
    store = get_memory_store()
    intent_id = str(uuid.uuid4())

    # Simulate first click
    print(f'Click 1: intent_id={intent_id}')
    result1 = await execute_buy_intent(intent_id)
    print(f'Result 1: {result1}')
    assert result1['success'] == True

    # Simulate retry/double-click
    print(f'Click 2: intent_id={intent_id} (retry)')
    result2 = await execute_buy_intent(intent_id)
    print(f'Result 2: {result2}')
    assert result2['success'] == False
    assert 'already' in result2['error'].lower()

    print('✓ Double-click protection working')

# Check audit log
from bots.treasury.scorekeeper import get_scorekeeper
sk = get_scorekeeper()
learnings = sk.get_learnings_for_context(limit=5)
print(f'Audit trail: {learnings}')
# Should show: 2 BUY_INTENT entries (one executed, one rejected)
"

# Manual integration test
python -c "
# Start bot with intent tracking
import logging
logging.basicConfig(level=logging.INFO)

# Simulate user journey
print('1. Sentiment report generates pick...')
# ... generates intent_id=abc-123

print('2. Button rendered in Telegram')
# ... button callback includes intent_id

print('3. User clicks (first time)')
# ... executes trade, records intent

print('4. User clicks again (network glitch)')
# ... checks intent, returns 'already executed'

print('5. Check .audit_log.json')
import json
with open('bots/treasury/.audit_log.json') as f:
    logs = json.load(f)
    recent = [l for l in logs if 'BUY_INTENT' in l.get('action', '')]
    print(f'Recent intents: {len(recent)}')
    # Should show 2 entries, second with success=False
"
```

### Rollback Plan

```bash
# If idempotency breaks trading:

Step 1: Disable idempotency check
  # Comment out store.is_duplicate() call in button_callback()

Step 2: Restore old behavior
  git checkout HEAD -- tg_bot/handlers/trading.py

Step 3: Test
  # Manual trade to verify it works

Step 4: Debug
  # Check if issue is with MemoryStore or logic
  # Verify MemoryStore.is_duplicate() actually returns results
```

---

## M4: STATE BACKUP STRATEGY (Using M1)

### Scope

**Depends On**: M1 (MemoryStore for consistency checks)
**Delivers**:
- Atomic writes with temp files
- Hourly backups
- Auto-cleanup (24-hour retention)
- Restore mechanism

**Files To Create**:
- `core/state/backup.py` ← NEW (AtomicStateManager)
- `core/state/__init__.py` ← NEW (exports)

**Files To Modify**:
- `bots/treasury/scorekeeper.py` ← Use AtomicStateManager for writes
- `scripts/` ← Add backup management scripts

### Implementation Tasks

```
M4.1 Create AtomicStateManager (250 lines)
     - write_state() with temp file + atomic rename
     - Backup creation (async)
     - Cleanup old backups (keep 24)
     - Restore from backup()
     Estimated: 3h

M4.2 Integrate with scorekeeper (50 lines)
     - Replace direct JSON writes with AtomicStateManager
     - Initialize manager on startup
     Estimated: 1h

M4.3 Create restore script (100 lines)
     - List available backups
     - Restore from timestamp
     - Verify integrity
     Estimated: 1.5h

M4.4 Unit tests (150 lines)
     - Test atomic write
     - Test backup creation
     - Test cleanup
     - Test restore
     Estimated: 2h

M4.5 Integration test (100 lines)
     - Simulate file corruption
     - Test restore process
     - Verify recovered state matches DB
     Estimated: 1.5h

M4.6 Manual test (corruption scenario)
     Estimated: 1h
```

**Total M4**: ~10 hours

### Acceptance Criteria

**AC4.1**: Atomic writes working
- [ ] Writes to .positions.tmp first
- [ ] Verifies JSON valid before rename
- [ ] Atomic rename (no partial writes)
- [ ] No corruption even if process crashes mid-write

**AC4.2**: Backups created hourly
- [ ] Backup file created in archive/ on each write
- [ ] Filename includes timestamp: `.positions.20250116T201234.json`
- [ ] Backup is valid JSON (can parse)

**AC4.3**: Auto-cleanup working
- [ ] Only last 24 backups retained
- [ ] Older backups deleted
- [ ] Archive directory doesn't grow unbounded

**AC4.4**: Restore mechanism working
- [ ] `restore_from_backup(timestamp)` returns state dict
- [ ] Restored state is valid
- [ ] Positions can be re-loaded from restored file

**AC4.5**: No false positives
- [ ] Normal write → writes .positions.json AND archive (no error)
- [ ] Corrupt JSON → detected, temp file kept for investigation
- [ ] Disk full → logged as warning, recovery possible

### Test Commands

```bash
# Unit tests
python -m pytest tests/test_state_backup.py -v

# Expected:
#   test_state_backup.py::test_atomic_write PASSED
#   test_state_backup.py::test_backup_creation PASSED
#   test_state_backup.py::test_cleanup_old_backups PASSED
#   test_state_backup.py::test_restore_from_backup PASSED

# Manual test: Corruption scenario
python -c "
from core.state.backup import AtomicStateManager
import os

manager = AtomicStateManager('.positions.json', 'archive')

# Write initial state
state1 = {'positions': [{'token': 'KR8TIV', 'amount': 100}]}
success = await manager.write_state(state1)
print(f'Write 1: success={success}')
assert success == True

# Verify backup created
backups = manager.list_backups()
print(f'Backups: {len(backups)}')
assert len(backups) == 1

# Simulate corruption (truncate .positions.json)
with open('.positions.json', 'w') as f:
    f.write('{invalid json')

# Try to restore from backup
restored = await manager.restore_from_backup(backups[0])
print(f'Restored positions: {len(restored[\"positions\"])}')
assert restored['positions'][0]['token'] == 'KR8TIV'
print('✓ Backup recovery working')
"

# Stress test: Multiple writes
python -c "
import asyncio
from core.state.backup import AtomicStateManager

async def stress():
    manager = AtomicStateManager('.positions.json', 'archive')

    # Write 30 times (simulate 30 hours of trading)
    for i in range(30):
        state = {'positions': [{'token': f'TOKEN_{i}', 'amount': 100}]}
        success = await manager.write_state(state)
        assert success == True

    # Check backups
    backups = manager.list_backups()
    print(f'Total backups: {len(backups)}')
    assert len(backups) == 24, f'Expected 24, got {len(backups)}'
    print('✓ Cleanup working (kept 24 most recent)')

asyncio.run(stress())
"

# Verify integrity
python -c "
from core.state.backup import AtomicStateManager
import json

manager = AtomicStateManager('.positions.json', 'archive')

# Verify .positions.json is valid JSON
with open('.positions.json') as f:
    state = json.load(f)
    print(f'Current positions: {len(state.get(\"positions\", []))}')

# Verify all backups are valid
for ts in manager.list_backups():
    backup = await manager.restore_from_backup(ts)
    assert backup is not None, f'Backup {ts} corrupt'

print('✓ All state files valid')
"
```

### Rollback Plan

```bash
# If backup interferes with trading:

Step 1: Disable async backup creation
  # Comment out asyncio.create_task(self._backup_state())

Step 2: Use direct writes temporarily
  # Revert to old write_state() call

Step 3: Test
  python bots/supervisor.py
  # Verify trading works

Step 4: Debug
  # Check if backup() or cleanup() causing slowness
  # Review logs for backup errors
```

---

## M5: ERROR HANDLING CLEANUP

### Scope

**Delivers**:
- Remove 2,609 bare `except:` blocks
- Add structured error logging
- Create exception types hierarchy

**Files To Modify**:
- `bots/grok_imagine/*.py` ← Remove bare excepts (6+ files)
- `core/errors/exceptions.py` ← Add custom exception types
- All components ← Replace bare except with specific handlers

### Implementation Tasks

```
M5.1 Create exception hierarchy (100 lines)
     - JarvisError (base)
     - NetworkError
     - DatabaseError
     - TradeExecutionError
     - GrokError
     - etc.
     Estimated: 1h

M5.2 Audit codebase (0 lines)
     - Find all bare excepts
     - Document context for each
     Estimated: 1h (already done in Deliverable A)

M5.3 Fix grok_imagine module (200 lines)
     - Replace 6+ bare excepts with structured logging
     - Add context about what failed
     Estimated: 2h

M5.4 Fix other modules (200 lines)
     - sentiment_report.py
     - ape_buttons.py
     - Others with bare excepts
     Estimated: 1.5h

M5.5 Add error recovery (100 lines)
     - Retry logic for transient errors
     - Graceful degradation
     Estimated: 1.5h

M5.6 Test coverage (150 lines)
     - Verify no silent failures
     - Check logs have useful messages
     Estimated: 1.5h
```

**Total M5**: ~8-9 hours

### Acceptance Criteria

**AC5.1**: No bare `except:` blocks
- [ ] `grep -r "except:" bots/ core/ tg_bot/ | grep -v "except Exception" | wc -l` = 0

**AC5.2**: Structured error logging
- [ ] Every except block logs: error type, message, context
- [ ] Log format: `[ERROR] Component.method: {exception_type}: {message} - Context: {details}`

**AC5.3**: Custom exception types in use
- [ ] `raise TradeExecutionError("Jupiter down")` instead of generic Exception
- [ ] Caller can distinguish error types for recovery

### Test Commands

```bash
# Audit for remaining bare excepts
grep -rn "except:" bots/ core/ tg_bot/ --include="*.py" | \
  grep -v "except Exception" | \
  grep -v "except.*Error" | \
  grep -v "#" | \
  wc -l
# Should be 0

# Check error logging
grep -r "logger.error\|logger.exception" bots/grok_imagine/*.py | wc -l
# Should be ≥6 (one per former bare except)

# Test error recovery
python -c "
import logging
logging.basicConfig(level=logging.ERROR)

# Simulate grok failure
from bots.grok_imagine import grok_login

try:
    # Intentionally fail
    result = await grok_login.login_to_grok('invalid_creds')
except Exception as e:
    print(f'Caught: {type(e).__name__}: {e}')
    # Should be specific exception, not generic

# Check logs
print('Log should show error context...')
"
```

---

## M6: CONFIGURATION UNIFICATION

### Scope

**Delivers**:
- Single `config.yaml` file
- Environment variable expansion
- Schema validation
- Config hot-reload

**Files To Create**:
- `config.yaml` ← NEW (master config)
- `core/config.py` ← NEW (config loader + validator)
- `tests/test_config.py` ← NEW (schema validation tests)

**Files To Modify**:
- All components ← Read from config instead of hardcoded values
- `bots/supervisor.py` ← Load config on startup

### Implementation Tasks

```
M6.1 Create config.yaml (100 lines)
     - All timing intervals
     - All thresholds
     - All limits
     - Environment variable refs
     Estimated: 1.5h

M6.2 Create config loader (200 lines)
     - YAML parsing
     - Env var expansion
     - Schema validation
     - Type checking
     Estimated: 2h

M6.3 Refactor components (300 lines)
     - Replace hardcoded values with config reads
     - tg_bot/config.py
     - treasury/trading.py
     - twitter/autonomous_engine.py
     - enhanced_market_data.py
     Estimated: 3h

M6.4 Hot reload (100 lines)
     - Watch config.yaml for changes
     - Reload without restart
     Estimated: 1.5h

M6.5 Tests (150 lines)
     - Validate schema
     - Test env var expansion
     - Test type coercion
     Estimated: 1.5h

M6.6 Documentation (100 lines)
     - Document all config options
     - Explain defaults
     - Examples
     Estimated: 1h
```

**Total M6**: ~11 hours

### Acceptance Criteria

**AC6.1**: config.yaml created
- [ ] Covers all tunable parameters from Deliverable C
- [ ] Environment variables can override (e.g., ${X_BOT_ENABLED})
- [ ] Comments explain each option

**AC6.2**: Config loader working
- [ ] `from core.config import load_config`
- [ ] `config = load_config("config.yaml")`
- [ ] Returns Config object with all settings

**AC6.3**: All hardcoded values replaced
- [ ] No `hours=24` directly in code
- [ ] All timing values read from config
- [ ] All thresholds read from config

**AC6.4**: Validation working
- [ ] Invalid config → error on startup
- [ ] Missing required keys → error with hint
- [ ] Type coercion works (string "10" → int 10)

### Test Commands

```bash
# Validate config schema
python -m pytest tests/test_config.py::test_schema_validation -v

# Load config
python -c "
from core.config import load_config
config = load_config('config.yaml')
print(f'Max positions: {config.treasury[\"max_positions\"]}')
print(f'Grok cost limit: ${config.grok[\"daily_cost_limit_usd\"]}')
print(f'Digest hours (UTC): {config.telegram[\"digest_hours\"]}')
"

# Test env var expansion
export X_BOT_ENABLED=false
python -c "
from core.config import load_config
config = load_config('config.yaml')
assert config.twitter['enabled'] == False
print('✓ Env var expansion working')
"
```

---

## SUMMARY: ALL MILESTONES

| Milestone | Focus | Hours | Depends | Blocks |
|-----------|-------|-------|---------|--------|
| M1 | MemoryStore interface | 14-16h | — | M3, M4, M6 |
| M2 | EventBus + backpressure | 16-18h | — | M6 |
| M3 | Buy intent idempotency | 7-8h | M1 | — |
| M4 | State backup strategy | 10h | M1 | — |
| M5 | Error handling cleanup | 8-9h | — | — |
| M6 | Config unification | 11h | M1, M2 | — |
| **TOTAL** | **6 phases** | **~80-100h** | — | — |

---

## TESTING & VALIDATION APPROACH (Ralph Wiggum Loop)

### Per-Milestone Validation

```
For each Milestone M:

PHASE 1: Code Review
  [ ] Read all changes (git diff)
  [ ] Verify against Acceptance Criteria
  [ ] Check no breaking changes

PHASE 2: Unit Tests
  [ ] Run pytest tests/test_M*.py -v
  [ ] Expect: 100% pass rate
  [ ] Coverage: ≥80%

PHASE 3: Integration Tests
  [ ] Run pytest tests/integration/test_M*.py -v
  [ ] Test with dependent systems
  [ ] Verify no side effects

PHASE 4: Manual Testing
  [ ] Execute manual test commands (from above)
  [ ] Verify original issue fixed
  [ ] Check error logs: 0 new errors/warnings

PHASE 5: Error Log Review
  [ ] grep -i "error\|exception\|traceback" logs/*
  [ ] Each error must be expected/known
  [ ] Fix any unexpected errors → ITERATE

PHASE 6: Commit
  [ ] All tests pass
  [ ] All errors explained
  [ ] No TODOs or FIXMEs left
  [ ] Git commit with message
```

### Cross-Milestone Integration

```
After all M1..M6 complete:

FULL SYSTEM TEST:

1. Start supervisor
   python bots/supervisor.py &

2. Generate sentiment report (triggers M1, M2, M3, M4)
   python -m bots.buy_tracker.sentiment_report

3. Verify event flow
   [ ] Sentiment generated event published (M2)
   [ ] Picks stored in MemoryStore (M1)
   [ ] Ape buttons rendered (M2 event handler)
   [ ] Button clicks check idempotency (M3)
   [ ] Positions backed up atomically (M4)

4. Simulate failure scenarios
   [ ] Network timeout → event bus backpressure (M2)
   [ ] Double-click → dedup prevents duplicate (M3)
   [ ] Crash during write → restore from backup (M4)
   [ ] Bare except triggered → structured error logged (M5)

5. Check all logs
   tail -100 logs/*.log
   [ ] No ERRORs except expected ones
   [ ] All components reporting health
   [ ] Metrics updated (M2 bus stats)

6. Verify config working (M6)
   # Change config.yaml
   # Restart bot
   # Verify new settings applied
```

---

## KNOWN RISKS & MITIGATIONS

| Risk | Impact | Mitigation |
|------|--------|-----------|
| M1 migration breaks X bot | Medium | Rollback plan ready; can disable M1 without breaking M2+ |
| M2 EventBus hangs | High | Timeout on handlers, dead letter queue, monitoring |
| M3 intent tracking overhead | Low | Minimal DB queries; MemoryStore indexed on intent_id |
| M4 backup disk space | Low | Auto-cleanup keeps only 24 versions |
| M5 error handling incomplete | Low | Audit script to find remaining bare excepts |
| M6 config loading fails | Medium | Fallback to defaults if config.yaml not found |

---

## ROLLBACK STRATEGY

**Per Milestone**:
- If any test fails or crashes detected → rollback immediately
- Don't proceed to next milestone until current one fully passes

**Full System**:
- If integration test fails → identify which milestone broke it
- Rollback that milestone (git revert)
- Fix issue → re-test → retry

**Command**:
```bash
# Rollback to last working milestone
git log --oneline | head -5
# Find last M{n} commit

git revert {hash}
# Creates new commit that undoes changes

# Test
python -m pytest tests/ -v
```

---

**END OF DELIVERABLE D**

Complete Implementation Plan with:
- 6 phased milestones
- ~80-100 hour estimate
- Detailed acceptance criteria
- Test commands for each
- Rollback procedures
- Ralph Wiggum loop validation approach

**Ready for approval. Upon user approval, proceed to Deliverable E (Implementation).**

