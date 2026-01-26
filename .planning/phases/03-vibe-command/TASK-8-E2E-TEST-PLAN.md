# Task 8: End-to-End Testing Plan

**Status**: READY FOR EXECUTION
**Date**: 2026-01-26
**Prerequisites**: Bot running, VIBECODING_ANTHROPIC_KEY configured

## Test Scenarios

### Scenario 1: Simple Code Change (Happy Path)

**Test Command**:
```
/vibe add a docstring to the BagsAPIClient class in core/trading/bags_client.py
```

**Expected Behavior**:
1. Animated progress indicator appears (Processing... animation)
2. Response within 30-60 seconds
3. Single message with:
   - ✅ Vibe Complete header
   - Code changes in ```python``` blocks
   - Token count and duration
   - Sanitization status (if applicable)
4. Docstring added without modifying other code

**Verification**:
- Check `core/trading/bags_client.py` for docstring
- Verify no unintended changes
- Check analytics DB: `SELECT * FROM vibe_requests WHERE status='success' ORDER BY id DESC LIMIT 1`

---

### Scenario 2: Multi-File Refactor

**Test Command**:
```
/vibe extract the sentiment logic from tg_bot/handlers/demo/demo_sentiment.py into a new sentiment_analyzer.py module
```

**Expected Behavior**:
1. Progress animation during processing
2. Response showing:
   - New file creation
   - Import updates in original file
   - Code organization
3. Multiple chunks if response >3800 chars:
   - Header: "Vibe Complete (N parts)"
   - Part 1/N, Part 2/N, etc.
   - Code blocks preserved across chunks

**Verification**:
- New file exists
- Original file imports from new file
- All tests still pass
- Check chunk count in analytics: `SELECT chunks_sent FROM vibe_requests ORDER BY id DESC LIMIT 1`

---

### Scenario 3: Bug Fix

**Test Command**:
```
/vibe fix the TypeError in tg_bot/handlers/demo/demo_orders.py line 142
```

**Expected Behavior**:
1. Claude identifies the bug
2. Explains the fix
3. Shows before/after code
4. Suggests related improvements (if any)

**Verification**:
- Bug is fixed
- Error no longer occurs
- Related code improvements are sensible

---

### Scenario 4: Error Handling - No Arguments

**Test Command**:
```
/vibe
```

**Expected Behavior**:
1. Immediate help message (no processing)
2. Shows:
   - Usage instructions
   - Examples
   - Current session stats (if session exists)
3. No analytics entry created

**Verification**:
- Help message displays correctly
- No error in logs

---

### Scenario 5: Timeout Test

**Test Command**:
```
/vibe refactor the entire codebase to use async/await everywhere and add comprehensive type hints to all functions
```

**Expected Behavior**:
1. Progress animation starts
2. After 5 minutes (timeout):
   - Animation stops
   - ⏱️ Timeout message appears
   - Suggests breaking into smaller tasks
3. Analytics logs as "timeout" status

**Verification**:
- Check logs for timeout warning
- Check analytics: `SELECT * FROM vibe_requests WHERE status='timeout'`
- Session lock released (can send new request)

---

### Scenario 6: Large Output (Chunking Test)

**Test Command**:
```
/vibe write a comprehensive test suite for demo_trading.py with tests for all major functions
```

**Expected Behavior**:
1. Response >3800 chars triggers chunking
2. Header message: "Vibe Complete (N parts)"
3. Sequential chunk messages:
   - Part 1/N
   - Part 2/N
   - etc.
4. Code blocks preserved:
   - Chunks end with ```
   - Next chunk starts with ```python
5. 0.3s delay between chunks visible

**Verification**:
- All chunks received
- Code blocks are syntactically valid
- No truncation mid-code
- Check: `SELECT chunks_sent, response_length FROM vibe_requests ORDER BY id DESC LIMIT 1`

---

### Scenario 7: Concurrent Requests (Lock Test)

**Setup**: Requires 2 users or careful timing

**Test Sequence**:

1. **User A**: `/vibe <long task that takes 30s>`
   - Expected: Processing animation starts

2. **User A** (before first completes): `/vibe <another task>`
   - Expected:
     - ⏸️ Error message
     - Shows when first request started
     - Shows preview of running request
     - "Please wait for it to complete"
     - Analytics logs as "concurrent_blocked"

3. **User B** (while User A's task runs): `/vibe <any task>`
   - Expected: Processes normally (different user lock)

4. **User A** (after first completes): `/vibe <another task>`
   - Expected: Processes normally

**Verification**:
- Check: `SELECT user_id, status, started_at FROM vibe_requests WHERE status='concurrent_blocked'`
- Verify lock released after completion
- Verify per-user isolation

---

## Analytics Verification Queries

After running all tests, verify logging:

```sql
-- Overall stats
SELECT status, COUNT(*) as count, AVG(duration_seconds) as avg_duration
FROM vibe_requests
GROUP BY status;

-- Daily aggregation
SELECT * FROM v_vibe_daily_stats WHERE date = DATE('now');

-- Token usage
SELECT SUM(tokens_used) as total_tokens, AVG(tokens_used) as avg_tokens
FROM vibe_requests WHERE status='success';

-- Error breakdown
SELECT error_message, COUNT(*) as count
FROM vibe_requests
WHERE status IN ('error', 'timeout', 'rate_limited')
GROUP BY error_message;
```

---

## Performance Benchmarks

Expected performance (based on implementation):

| Scenario | Expected Duration |
|----------|------------------|
| Simple change | 15-45 seconds |
| Multi-file refactor | 30-90 seconds |
| Bug fix | 20-60 seconds |
| Large output | 60-180 seconds |
| Timeout | Exactly 300 seconds |

**Token Usage**:
- Simple: 500-2000 tokens
- Complex: 3000-8000 tokens
- Maximum per request: 4096 tokens (output limit)

---

## Failure Criteria

Tests fail if:

1. ❌ Unhandled exceptions in logs
2. ❌ Code blocks truncated mid-syntax
3. ❌ Chunks sent out of order
4. ❌ Lock not released after error/timeout
5. ❌ Analytics not logging
6. ❌ Progress animation doesn't stop on completion
7. ❌ Timeout doesn't trigger after 5 minutes
8. ❌ Concurrent requests from same user both execute

---

## Success Criteria

✅ All 7 scenarios complete successfully
✅ No unhandled exceptions
✅ Analytics DB has entries for all requests
✅ Code changes are correct and compilable
✅ Response times within expected ranges
✅ Chunking preserves code block integrity
✅ Concurrent protection works per-user

---

## Manual Test Execution Checklist

- [ ] Start Telegram bot
- [ ] Verify `VIBECODING_ANTHROPIC_KEY` is set
- [ ] Run migration: `sqlite3 data/jarvis_analytics.db < core/database/migrations/add_vibe_requests_table.sql`
- [ ] Execute Scenario 1 (happy path)
- [ ] Execute Scenario 2 (multi-file)
- [ ] Execute Scenario 3 (bug fix)
- [ ] Execute Scenario 4 (no args)
- [ ] Execute Scenario 5 (timeout)
- [ ] Execute Scenario 6 (large output)
- [ ] Execute Scenario 7 (concurrent)
- [ ] Run analytics verification queries
- [ ] Review logs for errors
- [ ] Document any issues found

---

## Automated Test Suite (Future Work)

For automated testing, create:
- `tests/integration/test_vibe_command.py`
- Mock Anthropic API responses
- Mock Telegram message sending
- Verify chunking logic
- Verify analytics logging
- Verify concurrency locks

**Note**: Mocking approach avoids API costs and enables CI/CD integration.
