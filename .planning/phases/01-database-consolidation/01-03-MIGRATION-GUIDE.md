# Database Migration Guide: Legacy → Unified Layer

**Phase:** 01-database-consolidation
**Plan:** 03
**Date:** 2026-01-26
**Purpose:** Developer guide for migrating from hardcoded database paths to the unified layer

---

## Overview

The Jarvis codebase has migrated from **28+ fragmented SQLite databases** to **3 consolidated databases** via a unified connection pool layer.

### Benefits
- **Connection pooling**: Automatic connection reuse and management
- **Thread safety**: Safe concurrent access
- **Reduced memory**: 3 databases vs 28+
- **Atomic transactions**: Cross-table operations in single database
- **Simpler code**: No manual connection lifecycle management

### Database Consolidation
```
OLD (28+ databases)                   NEW (3 databases)
├── jarvis.db                         ├── jarvis_core.db
├── llm_costs.db           →          ├── jarvis_analytics.db
├── metrics.db             →          └── jarvis_cache.db
├── rate_limiter.db        →
├── telegram_memory.db     →
└── 23+ other databases    →
```

---

## Migration Patterns

### Pattern 1: Core Operational Data

**Use `get_core_db()` for:**
- Trading positions
- User accounts
- Orders and trades
- Bot configuration
- Token metadata

**Before:**
```python
import sqlite3

conn = sqlite3.connect("data/jarvis.db")
cursor = conn.cursor()

cursor.execute("SELECT * FROM positions WHERE status = 'OPEN'")
positions = cursor.fetchall()

conn.commit()
conn.close()
```

**After:**
```python
from core.database import get_core_db

db = get_core_db()
with db.cursor() as cursor:
    cursor.execute("SELECT * FROM positions WHERE status = 'OPEN'")
    positions = cursor.fetchall()
# Automatic commit and connection return to pool
```

---

### Pattern 2: Analytics and Metrics Data

**Use `get_analytics_db()` for:**
- LLM usage costs
- Performance metrics
- Error rates and latencies
- Sentiment data
- Learnings and insights
- Whale tracking

**Before:**
```python
import sqlite3

conn = sqlite3.connect("data/llm_costs.db")
cursor = conn.cursor()

cursor.execute("""
    INSERT INTO llm_usage (provider, model, cost_usd)
    VALUES (?, ?, ?)
""", ("openai", "gpt-4o", 0.025))

conn.commit()
conn.close()
```

**After:**
```python
from core.database import get_analytics_db

db = get_analytics_db()
with db.cursor() as cursor:
    cursor.execute("""
        INSERT INTO llm_usage (provider, model, cost_usd)
        VALUES (?, ?, ?)
    """, ("openai", "gpt-4o", 0.025))
```

---

### Pattern 3: Cache and Ephemeral Data

**Use `get_cache_db()` for:**
- Rate limit state
- API response cache
- Session data
- Spam protection counters
- Temporary data (can be cleared)

**Before:**
```python
import sqlite3

conn = sqlite3.connect("data/rate_limiter.db")
cursor = conn.cursor()

cursor.execute("""
    UPDATE rate_limits
    SET count = count + 1, last_request = ?
    WHERE user_id = ?
""", (now, user_id))

conn.commit()
conn.close()
```

**After:**
```python
from core.database import get_cache_db

db = get_cache_db()
with db.cursor() as cursor:
    cursor.execute("""
        UPDATE rate_limits
        SET count = count + 1, last_request = ?
        WHERE user_id = ?
    """, (now, user_id))
```

---

## Advanced Patterns

### Pattern 4: Custom Context Manager

**If your code has a `_get_conn()` method:**

**Before:**
```python
import sqlite3
from contextlib import contextmanager

class MyService:
    def __init__(self):
        self.db_path = "data/myservice.db"

    @contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_data(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM data")
            return cursor.fetchall()
```

**After:**
```python
from contextlib import contextmanager
from core.database import get_core_db  # or get_analytics_db/get_cache_db

class MyService:
    def __init__(self):
        # db_path no longer needed
        pass

    @contextmanager
    def _get_conn(self):
        db = get_core_db()
        with db.connection() as conn:
            yield conn

    def get_data(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM data")
            return cursor.fetchall()
```

---

### Pattern 5: Singleton/Factory Pattern

**If your code has a singleton database instance:**

**Before:**
```python
import sqlite3

_db_instance = None

def get_database():
    global _db_instance
    if _db_instance is None:
        _db_instance = sqlite3.connect("data/jarvis.db")
    return _db_instance
```

**After:**
```python
from core.database import get_core_db

def get_database():
    # Connection pool handles singleton internally
    return get_core_db()
```

---

### Pattern 6: Direct Execute Helper

**If you have simple one-off queries:**

**Before:**
```python
import sqlite3

def record_metric(name, value):
    conn = sqlite3.connect("data/metrics.db")
    conn.execute("INSERT INTO metrics (name, value) VALUES (?, ?)", (name, value))
    conn.commit()
    conn.close()
```

**After:**
```python
from core.database import get_analytics_db

def record_metric(name, value):
    db = get_analytics_db()
    db.execute("INSERT INTO metrics (name, value) VALUES (?, ?)", (name, value))
    # execute() helper handles cursor, commit, and cleanup
```

---

## Database Mapping

| Legacy Database | Unified Database | Tables/Purpose |
|----------------|------------------|----------------|
| `jarvis.db` | `jarvis_core.db` | positions, trades, users, orders, bot_config, token_metadata |
| `llm_costs.db` | `jarvis_analytics.db` | llm_usage, llm_daily_stats, budget_alerts |
| `metrics.db` | `jarvis_analytics.db` | metrics_1m, metrics_1h, alert_history |
| `sentiment.db` | `jarvis_analytics.db` | sentiment_scores, sentiment_history |
| `rate_limiter.db` | `jarvis_cache.db` | rate_limits, rate_limit_state |
| `telegram_memory.db` | `jarvis_core.db` or `jarvis_cache.db` | Depends on retention policy |
| `sessions.db` | `jarvis_cache.db` | session_data, session_state |
| `api_cache.db` | `jarvis_cache.db` | api_responses, cache_metadata |

---

## Breaking Changes

### Removed Functions
- ❌ `get_legacy_db()` - **REMOVED** from `core.database.__init__.py`
  - **Migration:** Use `get_core_db()` instead

### Deprecated Patterns
- ❌ Direct `sqlite3.connect("data/...")` with hardcoded paths
  - **Migration:** Use unified layer functions

### Parameter Compatibility
Some classes kept `db_path` parameters for backward compatibility, but they are **ignored**:

```python
# Still works but db_path is ignored
tracker = LLMCostTracker(db_path="data/old.db")  # Uses unified layer anyway

# Recommended
tracker = LLMCostTracker()  # No db_path needed
```

---

## Connection Pool API

The `ConnectionPool` class (returned by `get_core_db()` etc.) provides:

### Context Managers
```python
db = get_core_db()

# 1. Connection context (manual cursor)
with db.connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM positions")
    results = cursor.fetchall()
    # Auto-commit on success, rollback on exception

# 2. Cursor context (automatic cursor handling)
with db.cursor() as cursor:
    cursor.execute("SELECT * FROM positions")
    results = cursor.fetchall()
    # Auto-commit, cursor cleanup
```

### Helper Methods
```python
# One-shot query (returns all results)
results = db.execute("SELECT * FROM positions WHERE status = ?", ("OPEN",))

# Bulk insert
db.execute_many(
    "INSERT INTO trades (id, symbol, price) VALUES (?, ?, ?)",
    [(1, "SOL", 100.0), (2, "BTC", 50000.0)]
)
```

### Pool Info
```python
print(f"Pool size: {db.size}")
print(f"Available connections: {db.available}")
```

---

## Testing Checklist

After migrating a file:

- [ ] **Imports updated**
  - [ ] Removed `import sqlite3`
  - [ ] Added `from core.database import get_X_db`

- [ ] **Connections replaced**
  - [ ] No `sqlite3.connect("data/...")` calls
  - [ ] Using `db = get_X_db()` instead
  - [ ] Using context managers: `with db.connection() as conn:`

- [ ] **Manual lifecycle removed**
  - [ ] No manual `conn.commit()`
  - [ ] No manual `conn.close()`
  - [ ] No manual `conn.rollback()` (auto on exception)

- [ ] **Imports work**
  - [ ] File imports without errors
  - [ ] No circular import issues

- [ ] **Functionality works**
  - [ ] Queries return correct results
  - [ ] Writes persist to database
  - [ ] Transactions work correctly

- [ ] **Performance acceptable**
  - [ ] No noticeable slowdown
  - [ ] Connection pool reuse working

---

## Rollback Procedure

If issues arise after migration:

### 1. Identify the Problem
```bash
# Check database connectivity
python -c "from core.database import health_check; print(health_check())"

# Check for connection leaks
python -c "from core.database import get_core_db; db = get_core_db(); print(f'Available: {db.available}/{db.size}')"
```

### 2. Revert File Changes
```bash
# Revert a single file
git checkout HEAD^ -- path/to/file.py

# Restart affected services
python bots/supervisor.py
```

### 3. Restore Legacy Database
```bash
# If needed, restore from backup
cp data/backups/jarvis.db.backup data/jarvis.db
```

### 4. Report Issue
Document the issue with:
- File that failed
- Error message
- Steps to reproduce
- Expected vs actual behavior

---

## Migration Statistics

**Files migrated in this plan:**
- ✅ core/llm/cost_tracker.py - 6 connection calls updated
- ✅ core/database/__init__.py - get_legacy_db() removed
- ✅ bots/treasury/database.py - Context manager updated
- ✅ bots/treasury/scorekeeper.py - 2 methods updated

**Current adoption:**
- 7 production files using unified layer
- Target: 15+ files (53% of goal met)

**Remaining files:**
- 4 P0 core/ files (metrics_collector, rate_limiter, etc.)
- 2 P1 bots/ files (buy_tracker, twitter)
- 3 P2 tg_bot/ files

---

## FAQs

### Q: Why three databases instead of one?
**A:** Separation of concerns and performance:
- **Core:** Frequent transactional updates (positions, trades)
- **Analytics:** Write-heavy, read-rarely (metrics, logs)
- **Cache:** High churn, can be cleared without data loss

### Q: Can I still use raw sqlite3 for tests?
**A:** Yes, test files are exempt. Use in-memory databases:
```python
import sqlite3
conn = sqlite3.connect(":memory:")
```

### Q: What happens if the pool is exhausted?
**A:** Requests wait (default 30s timeout). Increase `max_connections` if needed:
```python
from core.database.pool import get_pool
pool = get_pool("data/jarvis_core.db", max_connections=20)
```

### Q: How do I debug connection leaks?
**A:** Check pool stats:
```python
from core.database import get_core_db
db = get_core_db()
print(f"Size: {db.size}, Available: {db.available}")
# If available stays low, connections aren't being returned
```

### Q: Does this work with async code?
**A:** For async, use the PostgreSQL client:
```python
from core.database import get_postgres_client
client = get_postgres_client()
results = await client.fetch("SELECT * FROM positions")
```

---

## Reference

**Files:**
- Unified layer: `core/database/__init__.py`
- Connection pool: `core/database/pool.py`
- Audit report: `.planning/phases/01-database-consolidation/01-03-DATABASE-PATHS-AUDIT.md`

**Verification commands:**
```bash
# Count unified layer adoption
grep -r "from core.database import get_" --include="*.py" core/ bots/ tg_bot/ | wc -l

# Find remaining hardcoded paths
grep -r "sqlite3.connect.*data/" --include="*.py" core/ bots/ tg_bot/

# Verify no legacy function usage
grep -r "get_legacy_db" --include="*.py" .
```

---

**Last Updated:** 2026-01-26
**Version:** 1.0
**Status:** Active
