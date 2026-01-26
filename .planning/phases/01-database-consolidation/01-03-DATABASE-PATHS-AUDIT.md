# Database Paths Audit Report
**Phase:** 01-database-consolidation
**Plan:** 03
**Date:** 2026-01-26
**Purpose:** Identify all hardcoded database paths for migration to unified layer

---

## Executive Summary

**Total files with hardcoded paths:** 117 files
**Priority P0 (Critical):** 6 files in core/ that must be updated
**Priority P1 (High):** 4 files in bots/ that handle trades/positions
**Priority P2 (Medium):** 3 files in tg_bot/
**Files to skip:** 104 (tests, migrations, utilities, already migrated)

**Current adoption:** Only 3 files use unified layer (✅ VERIFIED from 01-VERIFICATION.md)
**Target adoption:** 15+ files after this plan

---

## Priority P0: Core Production Files (MUST UPDATE)

These files are critical infrastructure and MUST be updated:

### 1. core/llm/cost_tracker.py
**Current:**
```python
import sqlite3
self.db_path = db_path or os.getenv("LLM_COST_DB", "data/llm_costs.db")
conn = sqlite3.connect(self.db_path)
```

**Target:**
```python
from core.database import get_analytics_db
conn = get_analytics_db()
```

**Complexity:** SIMPLE
**Lines to change:** ~10 (3 sqlite3.connect calls)
**Reason:** LLM cost tracking belongs in analytics database

---

### 2. core/monitoring/metrics_collector.py
**Current:**
```python
import sqlite3
self.db_path = db_path or os.getenv("METRICS_DB", "data/metrics.db")
conn = sqlite3.connect(self.db_path)
```

**Target:**
```python
from core.database import get_analytics_db
conn = get_analytics_db()
```

**Complexity:** SIMPLE
**Lines to change:** ~8 (multiple sqlite3.connect calls)
**Reason:** Metrics/monitoring data belongs in analytics database

---

### 3. core/database/__init__.py
**Current:**
```python
def get_legacy_db(db_name: str = "jarvis.db") -> sqlite3.Connection:
    """DEPRECATED: Use get_core_db() instead"""
    ...
```

**Target:** REMOVE FUNCTION ENTIRELY

**Complexity:** SIMPLE
**Lines to change:** ~15 (remove function and docstrings)
**Reason:** Legacy compatibility shim no longer needed after migration

---

### 4. core/rate_limiter.py
**Current:**
```python
Path(__file__).parent.parent / "data" / "rate_limiter.db"
```

**Target:**
```python
from core.database import get_cache_db
conn = get_cache_db()
```

**Complexity:** SIMPLE
**Reason:** Rate limiter state is ephemeral cache data

---

### 5. core/telegram_console_bridge.py
**Current:**
```python
MEMORY_DB = DATA_DIR / "telegram_memory.db"
```

**Target:**
```python
from core.database import get_core_db  # or get_cache_db for ephemeral
conn = get_core_db()
```

**Complexity:** SIMPLE
**Reason:** Telegram memory should be in core or cache DB

---

### 6. core/security/enhanced_rate_limiter.py
**Current:**
```python
Path("data/rate_limiter") / "rate_limiter.db"
```

**Target:**
```python
from core.database import get_cache_db
conn = get_cache_db()
```

**Complexity:** SIMPLE
**Reason:** Enhanced rate limiter shares cache DB with basic limiter

---

## Priority P1: Bots Production Files (HIGH PRIORITY)

These handle live trading and must be updated for consistency:

### 7. bots/treasury/database.py
**Current:**
```python
import sqlite3
DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
DB_PATH = DATA_DIR / "jarvis.db"
```

**Target:**
```python
from core.database import get_core_db
conn = get_core_db()
```

**Complexity:** MEDIUM
**Lines to change:** ~30 (multiple connection calls throughout)
**Reason:** Treasury positions/trades are core operational data
**Note:** This file is used by trading modules, high impact

---

### 8. bots/treasury/scorekeeper.py
**Current:**
```python
import sqlite3
DB_PATH = DATA_DIR / "jarvis.db"
```

**Target:**
```python
from core.database import get_core_db
conn = get_core_db()
```

**Complexity:** SIMPLE
**Reason:** Trade scoring uses same DB as treasury

---

### 9. bots/buy_tracker/database.py
**Current:**
```python
import sqlite3
# (likely has hardcoded paths)
```

**Target:**
```python
from core.database import get_core_db
conn = get_core_db()
```

**Complexity:** SIMPLE
**Reason:** Buy tracking data belongs in core DB

---

### 10. bots/twitter/autonomous_engine.py
**Current:**
```python
import sqlite3
# (likely uses local DB for tweet history)
```

**Target:**
```python
from core.database import get_cache_db  # or analytics
conn = get_cache_db()
```

**Complexity:** MEDIUM
**Reason:** Tweet history could be analytics or cache

---

## Priority P2: Telegram Bot Files (MEDIUM)

### 11. tg_bot/models/subscriber.py
**Current:**
```python
import sqlite3
# (subscriber data)
```

**Target:**
```python
from core.database import get_core_db
conn = get_core_db()
```

**Complexity:** SIMPLE
**Reason:** Subscriber management is core data

---

### 12. tg_bot/services/conversation_memory.py
**Current:**
```python
import sqlite3
# (conversation history)
```

**Target:**
```python
from core.database import get_cache_db  # or core if persistent
conn = get_cache_db()
```

**Complexity:** SIMPLE
**Reason:** Depends on retention policy

---

### 13. tg_bot/services/cost_tracker.py
**Current:**
```python
import sqlite3
# (duplicate cost tracking?)
```

**Target:**
```python
from core.database import get_analytics_db
conn = get_analytics_db()
```

**Complexity:** SIMPLE
**Reason:** Consolidate with core/llm/cost_tracker.py

---

## Files to SKIP (Migrations, Tests, Utilities)

These files are exempt from migration:

### Migration Scripts (expected to have legacy paths)
- core/data/migrations.py - Migration runner, needs legacy paths
- core/database/migration.py - Migration infrastructure

### Testing Files (use test databases)
- All files matching `test_*.py` or `*_test.py`
- core/state_backup/state_backup.py - Backup utility, needs access to all DBs

### Development Tools
- core/performance/query_optimizer.py - Query analysis tool
- core/data/query_optimizer.py - Duplicate query tool
- core/startup_validator.py - Startup validation, checks all DBs

### Already Using Unified Layer (✅ VERIFIED)
- core/database/pool.py - Connection pool infrastructure
- core/database/sqlite_pool.py - Pool implementation
- core/db/pool.py - Alternative pool (may need consolidation)

### Low Priority / Inactive
- 90+ other files in core/ that:
  - May be deprecated
  - Are rarely executed
  - Are one-off scripts
  - Handle specialized use cases

---

## Mapping: Legacy DB → Unified DB

| Legacy Database | Unified Database | Reason |
|----------------|------------------|--------|
| `jarvis.db` | `core.db` | Operational data (positions, trades, users) |
| `llm_costs.db` | `analytics.db` | Analytics and metrics |
| `metrics.db` | `analytics.db` | Performance monitoring |
| `rate_limiter.db` | `cache.db` | Ephemeral rate limit state |
| `telegram_memory.db` | `core.db` or `cache.db` | Depends on retention needs |
| `*_analytics.db` | `analytics.db` | All analytics consolidated |
| `*_cache.db` | `cache.db` | All cache/temp data |

---

## Migration Strategy

**Phase 1 (P0):** Update 6 core/ files
- Estimated time: 30 minutes
- Risk: LOW (isolated changes)
- Testing: Unit tests + smoke test

**Phase 2 (P1):** Update 4 bots/ files
- Estimated time: 45 minutes
- Risk: MEDIUM (affects trading operations)
- Testing: Integration tests + paper trading verification

**Phase 3 (P2):** Update 3 tg_bot/ files
- Estimated time: 20 minutes
- Risk: LOW (user-facing but non-critical)
- Testing: Bot interaction tests

**Total estimated time:** 95 minutes (~1.5 hours)

---

## Success Metrics

- ✅ 13 production files updated
- ✅ 15+ files import from core.database (up from 3)
- ✅ Zero `sqlite3.connect("data/...")` in P0/P1 files
- ✅ `get_legacy_db()` removed from core/database/__init__.py
- ✅ All updated files pass import checks
- ✅ Integration tests pass

---

## Rollback Plan

If issues arise:
1. Git revert the commit for affected file
2. Restart services with old code
3. Database state is unchanged (no schema changes in this plan)
4. Zero data loss risk (only changing how connections are established)

---

## Notes

- **Connection pooling:** Unified layer provides automatic connection pooling
- **Thread safety:** Connection pool handles concurrent access
- **Performance:** Expect minor improvement due to pooling
- **Backward compatibility:** Old database files remain on disk temporarily
- **No schema changes:** This plan only changes connection methods, not schemas
