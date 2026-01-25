---
phase: 07-retain-recall-functions
plan: 05
subsystem: bot-memory
tags: [memory, x-bot, bags-intel, buy-tracker, integration]

requires:
  - 07-01-core-recall-api

provides:
  - X/Twitter post performance tracking and pattern analysis
  - Bags Intel graduation outcome storage and prediction
  - Buy Tracker purchase event tracking and statistics
  - Complete memory integration across all 5 Jarvis bots

affects:
  - Future analytics and reporting features
  - Bot performance optimization based on memory insights

tech-stack:
  added:
    - None (uses existing core.memory API)
  patterns:
    - Fire-and-forget memory operations
    - Non-blocking async storage
    - Context field parsing for metadata retrieval
    - Task tracking for background operations

key-files:
  created:
    - bots/twitter/memory_hooks.py
    - bots/bags_intel/memory_hooks.py
    - bots/buy_tracker/memory_hooks.py
  modified:
    - bots/twitter/autonomous_engine.py
    - bots/bags_intel/intel_service.py
    - bots/buy_tracker/bot.py

decisions:
  - name: "Fire-and-forget storage pattern"
    rationale: "Memory operations must not block bot operations"
    alternatives: ["Synchronous storage", "Queue-based batch processing"]
    chosen: "fire_and_forget() for non-blocking async execution"

  - name: "Context field for metadata"
    rationale: "retain_fact() doesn't accept metadata parameter"
    alternatives: ["Extend retain_fact API", "Store in separate table"]
    chosen: "Encode metadata in context field (e.g., score:{value}|hour:{value})"

  - name: "String parsing for recall"
    rationale: "Metadata stored in context field must be parsed"
    alternatives: ["JSON in context", "Regex extraction"]
    chosen: "Simple string split parsing (score:X, hour:Y)"

metrics:
  duration: "896s (14.9 minutes)"
  completed: "2026-01-25"
---

# Phase 07 Plan 05: X/Twitter + Bags Intel + Buy Tracker Integration Summary

**One-liner:** Fire-and-forget memory hooks for X/Twitter post analytics, Bags Intel graduation predictions, and Buy Tracker purchase statistics

## What Was Built

Completed memory integration for the final 3 Jarvis bot systems with non-blocking storage and pattern analysis.

### 1. X/Twitter Memory Hooks (`bots/twitter/memory_hooks.py`)

**Store Functions:**
- `store_post_performance()` - Stores tweet metrics (likes, retweets, replies, impressions)
  - Context format: `post_performance|{tweet_id}|score:{engagement_score}|hour:{posting_hour}`
  - Fires after successful tweet posting (non-blocking)

**Recall Functions:**
- `recall_engagement_patterns()` - Finds high-performing tweets by topic and engagement threshold
- `get_best_posting_times()` - Analyzes posting hour vs. average engagement
- `suggest_content_patterns()` - Identifies high-engagement topics and best-performing posts

**Integration:**
- Added `fire_and_forget()` call in `autonomous_engine.py` `post_tweet()` after successful post
- Stores initial metrics (0 likes/retweets), ready for later update mechanism
- Controlled by `TWITTER_MEMORY_ENABLED` env var

### 2. Bags Intel Memory Hooks (`bots/bags_intel/memory_hooks.py`)

**Store Functions:**
- `store_graduation_outcome()` - Stores graduation events with scores, prices, and outcomes
  - Context format: `graduation_outcome|{mint[:12]}|score:{score}|tier:{tier}|outcome:{status}`
  - Includes bonding curve data (duration, volume, buyers, buy/sell ratio)
  - Tracks price changes (24h, 7d) when available

**Recall Functions:**
- `recall_similar_graduations()` - Finds graduations in score range or by creator
- `get_graduation_success_rate()` - Calculates historical success rate above score threshold
- `predict_graduation_success()` - Predicts success probability based on similar patterns
  - Weighted: 70% similar score patterns + 30% creator history

**Integration:**
- Added `fire_and_forget()` call in `intel_service.py` `_handle_graduation()` after report sent
- Stores outcome as "pending" initially (can be updated later with actual performance)
- Controlled by `BAGS_INTEL_MEMORY_ENABLED` env var

### 3. Buy Tracker Memory Hooks (`bots/buy_tracker/memory_hooks.py`)

**Store Functions:**
- `store_purchase_event()` - Stores token purchases with buyer, amount, price
  - Context format: `purchase_event|{mint[:12]}|sol:{amount}|source:{source}`
  - Includes market cap, buyer position percentage, USD value

**Recall Functions:**
- `recall_purchase_history()` - Query purchases by token or buyer wallet
- `get_token_buy_stats()` - Aggregated stats: total purchases, volume, unique buyers, averages

**Integration:**
- Added `fire_and_forget()` call in `bot.py` `_on_buy_detected()` callback
- Stores every detected buy transaction (KR8TIV source)
- Controlled by `BUY_TRACKER_MEMORY_ENABLED` env var

## Technical Implementation

### Fire-and-Forget Pattern

```python
fire_and_forget(
    store_post_performance(...),
    name=f"store_post_performance_{tweet_id}",
)
```

**Benefits:**
- Bot operations never blocked by memory writes
- Background tasks tracked by TaskTracker
- Errors logged but don't affect core functionality

### Async Wrapper for Sync API

```python
fact_id = await asyncio.to_thread(
    retain_fact,
    content=summary,
    context=context_string,
    source="x_posting",
    entities=entities,
    confidence=1.0,
)
```

**Why:** `retain_fact()` is synchronous (SQLite writes), so we run it in thread pool to avoid blocking event loop.

### Context Field Metadata Encoding

Since `retain_fact()` doesn't accept a `metadata` dict parameter:

**Storage:**
```python
context = f"post_performance|{tweet_id}|score:{engagement_score:.1f}|hour:{posting_hour}"
```

**Retrieval:**
```python
score_str = context_str.split("score:")[1].split("|")[0]
engagement_score = float(score_str)
```

**Trade-offs:**
- ✅ Works with existing API
- ✅ Human-readable in memory viewer
- ❌ Requires string parsing (fragile)
- ❌ No type safety

**Future:** Consider adding metadata support to `retain_fact()` or using JSON in context field.

## Verification

All three memory hook modules tested successfully:

**X/Twitter:**
```bash
✓ store_post_performance() → fact_id=95
✓ recall_engagement_patterns() → 2 patterns
```

**Bags Intel:**
```bash
✓ store_graduation_outcome() → fact_id=97
✓ recall_similar_graduations() → 1 similar graduation
```

**Buy Tracker:**
```bash
✓ store_purchase_event() → fact_id=98
✓ recall_purchase_history() → 1 purchase
```

## Deviations from Plan

None - plan executed exactly as written.

## Next Phase Readiness

**Ready for Phase 8 (Session Context):**
- ✅ All bot memory hooks implemented
- ✅ Fire-and-forget pattern proven across 5 systems
- ✅ Context field metadata pattern established

**Potential Improvements:**
1. **Metrics update mechanism** - X/Twitter posts stored with initial 0 likes/retweets
   - Need periodic job to fetch actual engagement metrics
   - Could use Twitter API polling or webhook
2. **Graduation outcome updates** - Bags Intel outcomes stored as "pending"
   - Need price tracking to update with success/failure
   - Could query DexScreener 24h/7d after graduation
3. **Metadata API** - Consider adding `metadata: Dict` parameter to `retain_fact()`
   - Avoid string parsing fragility
   - Enable structured queries on metadata fields

## Commits

| Commit | Message |
|--------|---------|
| 0e11d19 | feat(07-05): add X/Twitter memory hooks for post performance tracking |
| 892f625 | feat(07-05): add Bags Intel memory hooks for graduation tracking |
| fdb3ff1 | feat(07-05): add Buy Tracker memory hooks for purchase tracking |

## Files Changed

**Created (3):**
- `bots/twitter/memory_hooks.py` (356 lines)
- `bots/bags_intel/memory_hooks.py` (383 lines)
- `bots/buy_tracker/memory_hooks.py` (268 lines)

**Modified (3):**
- `bots/twitter/autonomous_engine.py` (+31 lines)
- `bots/bags_intel/intel_service.py` (+24 lines)
- `bots/buy_tracker/bot.py` (+28 lines)

**Total:** +1090 lines

## Success Criteria Met

- [x] X/Twitter bot stores post metrics after posting
- [x] X/Twitter bot can recall high-engagement patterns
- [x] Bags Intel stores graduation outcomes
- [x] Bags Intel can recall similar graduations for predictions
- [x] Buy Tracker stores purchase events
- [x] All memory operations non-blocking (fire-and-forget)
- [x] Integration with respective bot engines complete
- [x] Environment variable controls (TWITTER_MEMORY_ENABLED, etc.)
