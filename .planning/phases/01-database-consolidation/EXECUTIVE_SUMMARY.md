# Database Consolidation - Executive Summary
**Date:** 2026-01-24  
**Phase:** 01 - Database Consolidation  
**Status:** Inventory Complete ✓

---

## The Problem

**Current State:**
- 29 SQLite databases scattered across the project
- ~2 MB total, 5,000+ rows across 120+ tables
- 13 databases are empty or nearly empty
- No connection pooling
- No WAL mode (poor concurrent access)
- 100+ files reference database paths directly

**Pain Points:**
- Difficult to backup (29 separate files)
- No cross-table queries (data siloed)
- File descriptor exhaustion risk
- Maintenance nightmare
- SQLite lock contention

---

## The Solution

**Consolidate from 29 → 7 databases:**

### 3 Consolidated Databases

1. **jarvis_core.db** (600 KB)
   - Operational data: trades, positions, users, config
   - ~700 rows
   - Critical for trading operations

2. **jarvis_analytics.db** (1.2 MB)
   - Analytics: messages, tweets, metrics, memory, sentiment
   - ~3,500 rows  
   - High write volume, medium read priority

3. **jarvis_cache.db** (100 KB)
   - Temporary data: cache, rate limiter logs
   - ~50 rows
   - High churn, can be purged

### 4 Standalone Databases (keep separate)
- engagement.db (Twitter metrics - may grow large)
- jarvis_spam_protection.db (security isolation)
- raid_bot.db (feature-specific)
- achievements.db (community features)

---

## Migration Plan

### Effort: 30-40 hours

| Phase | Duration | Tasks |
|-------|----------|-------|
| **01-02: Schema Design** | 1 week | Create SQL schemas, migration scripts |
| **01-03: Code Updates** | 1 week | Update 100+ file references |
| **01-04: Testing** | 3 days | Staging migration, tests, production deploy |

### Risks & Mitigation

**HIGH RISK:**
- jarvis_memory.db has FTS5 virtual tables with triggers
- **Mitigation:** Special migration script for FTS tables

**MEDIUM RISK:**
- Foreign key constraints in 6 databases
- **Mitigation:** Table-by-table migration with FK verification

**MEDIUM RISK:**
- 100+ code references to update
- **Mitigation:** Centralized config, feature flag rollback

---

## Benefits

### Operational
- 75% fewer database files (29 → 7)
- Centralized backups (3 files instead of 29)
- Connection pooling feasible
- Cross-table JOINs enabled

### Performance
- WAL mode for concurrent access
- Connection pooling (reduce overhead)
- Fewer file descriptors
- Better cache locality

### Maintenance
- Simpler schema management
- Easier migrations
- Consolidated monitoring
- Single source of truth

---

## Rollback Plan

1. **Keep originals** in data/backup/ for 30 days
2. **Feature flag:** `USE_CONSOLIDATED_DBS=false` for instant rollback
3. **Monitor:** Error rates, latency, lock contention
4. **Criteria:** Rollback if error rate >5% or critical failures

---

## Timeline

**Week 1 (Schema & Scripts):**
- Create consolidated SQL schemas
- Write Python migration scripts
- Handle FTS special cases

**Week 2 (Code Updates):**
- Update all 100+ file references
- Create centralized DB config
- Implement connection pooling
- Update tests

**Week 3 (Testing & Deploy):**
- Staging migration
- Integration tests
- Production deployment
- Monitor for 7 days

**Total: 3 weeks**

---

## Success Metrics

### Pre-Migration Baseline
- Database count: 29
- Total size: 2 MB
- File descriptors: 29 max
- No connection pooling
- No WAL mode

### Post-Migration Goals
- Database count: 7 (75% reduction)
- Total size: <2 MB (no bloat)
- File descriptors: 7 max
- Connection pooling: Yes
- WAL mode: Yes
- Error rate: <1% increase
- Query latency: <10% increase

### Monitoring (7 days post-deploy)
- SQLite lock wait times
- Query performance
- Error rates
- Backup/restore times

---

## Recommendation

**PROCEED with consolidation.**

**Justification:**
1. Current sprawl is unsustainable (29 databases)
2. Benefits outweigh risks
3. Rollback plan provides safety net
4. 3-week timeline is reasonable
5. No major blockers identified

**Next Action:**
Begin Phase 01-02 (Schema Design & Migration Scripts)

---

## Appendix: Database List

### Top 10 by Size
1. telegram_memory.db - 312 KB (1,719 rows)
2. jarvis.db - 300 KB (652 rows)
3. jarvis_x_memory.db - 200 KB (299 rows)
4. call_tracking.db - 188 KB (564 rows)
5. jarvis_admin.db - 156 KB (1,087 rows)
6. jarvis_memory.db - 140 KB (~10 rows + FTS)
7. raid_bot.db - 76 KB (6 rows)
8. sentiment.db - 48 KB (1 row)
9. long_term.db - 48 KB (0 rows - EMPTY)
10. tax.db - 44 KB (2 rows)

### Empty/Nearly Empty (13 databases)
- long_term.db, engagement.db, whales.db, achievements.db
- ai_memory.db, bot_health.db, health.db, distributions.db
- file_cache.db, research.db, metrics.db, recycle_test.db
- custom.db

**These should be consolidated or archived.**

