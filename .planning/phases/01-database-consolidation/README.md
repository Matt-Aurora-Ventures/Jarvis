# Phase 01: Database Consolidation

**Status:** Task 01-01 Complete ✓  
**Date:** 2026-01-24  
**Agent:** Scout

---

## Overview

This phase consolidates 29 scattered SQLite databases into 3 consolidated databases + 4 standalone databases, improving maintainability, performance, and enabling cross-table queries.

---

## Quick Links

### Start Here
- **[EXECUTIVE_SUMMARY.md](./EXECUTIVE_SUMMARY.md)** - High-level overview and recommendation

### Detailed Analysis
- **[database_inventory.md](./database_inventory.md)** - Complete catalog of all 29 databases
- **[dependency_graph.md](./dependency_graph.md)** - Foreign keys and code dependencies
- **[code_references.md](./code_references.md)** - Files that need updating
- **[VISUAL_MAP.md](./VISUAL_MAP.md)** - Visual diagrams and flow

### Task Documentation
- **[01-01-PLAN.md](./01-01-PLAN.md)** - Original task plan
- **[TASK_01-01_COMPLETE.md](./TASK_01-01_COMPLETE.md)** - Completion summary

---

## Key Findings

### Current State
- 29 databases (2 MB total, 5,000+ rows)
- 13 databases are empty or nearly empty
- No connection pooling
- No WAL mode
- 100+ scattered code references

### Proposed State
- 7 databases (75% reduction)
- 3 consolidated: core, analytics, cache
- 4 standalone: engagement, spam_protection, raid, achievements
- Connection pooling enabled
- WAL mode for concurrent access

### Migration Effort
- **30-40 hours** total
- 1 week for schema design & scripts
- 1 week for code updates
- 3 days for testing & deployment

---

## Consolidation Plan

### jarvis_core.db (600 KB)
**Operational data - trading, positions, users**
- From jarvis.db: positions, trades, scorecard, etc.
- From treasury_trades.db: treasury_trades
- From tax.db: tax_lots, sales, wash_sales
- From jarvis_admin.db: users → telegram_users
- From rate_limiter.db: rate_configs

### jarvis_analytics.db (1.2 MB)
**Analytics - messages, metrics, memory, sentiment**
- From telegram_memory.db: ALL
- From jarvis_x_memory.db: ALL
- From jarvis_memory.db: ALL (including FTS tables)
- From call_tracking.db: ALL
- From sentiment.db: ALL
- From whales.db: ALL
- From llm_costs.db: ALL
- From metrics.db: ALL
- From bot_health.db: ALL
- From research.db: ALL

### jarvis_cache.db (100 KB)
**Temporary data - cache, rate limiting logs**
- From file_cache.db: cache_entries
- From rate_limiter.db: request_log, limit_stats
- From ai_memory.db: memories
- From long_term.db: ALL
- From distributions.db: distributions

---

## Risks & Mitigation

### HIGH RISK: FTS Tables
**Problem:** jarvis_memory.db has FTS5 virtual tables with triggers  
**Mitigation:** Special migration script preserving FTS structure

### MEDIUM RISK: Foreign Keys
**Problem:** 6 databases have FK constraints  
**Mitigation:** Table-by-table migration with FK verification

### MEDIUM RISK: Code Updates
**Problem:** 100+ files reference database paths  
**Mitigation:** Centralized config, feature flag for rollback

---

## Next Steps

### ✓ DONE: Task 01-01 - Database Inventory
- All 29 databases cataloged
- Schemas extracted
- Dependencies mapped
- Consolidation plan created

### → NEXT: Task 01-02 - Schema Design & Migration Scripts
**Owner:** Kraken (implementation agent)  
**Duration:** 1 week  
**Deliverables:**
1. Consolidated SQL schemas
2. Python migration scripts
3. FTS table migration logic
4. Validation queries

### Future: Task 01-03 - Code Updates
**Owner:** Phoenix (refactoring agent)  
**Duration:** 1 week

### Future: Task 01-04 - Testing & Deployment
**Owner:** Arbiter (testing agent)  
**Duration:** 3 days

---

## Success Metrics

### Before
- 29 databases
- No pooling
- No WAL mode
- Scattered references

### After (Goals)
- 7 databases
- Connection pooling: YES
- WAL mode: YES
- Centralized config: YES
- Error rate increase: <1%
- Query latency increase: <10%

---

## Files in This Directory

```
01-database-consolidation/
├── README.md                    (this file)
├── EXECUTIVE_SUMMARY.md         (start here - high-level overview)
├── database_inventory.md        (complete database catalog)
├── dependency_graph.md          (foreign keys & code dependencies)
├── code_references.md           (files to update)
├── VISUAL_MAP.md                (diagrams and visual flow)
├── 01-01-PLAN.md                (original task plan)
└── TASK_01-01_COMPLETE.md       (task completion summary)
```

---

**Recommendation:** PROCEED with database consolidation.

The benefits (75% reduction in DB count, connection pooling, cross-table queries) outweigh the risks (FTS migration, code updates). A robust rollback plan provides safety.

**Next Action:** Begin Task 01-02 (Schema Design & Migration Scripts)

