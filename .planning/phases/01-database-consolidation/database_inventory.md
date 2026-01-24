# Database Inventory & Analysis
**Generated:** 2026-01-24  
**Phase:** 01 - Database Consolidation  
**Task:** 01-01 - Database Inventory

---

## Executive Summary

**Total Databases Found:** 29  
**Total Size:** ~2.0 MB  
**Total Tables:** 120+  
**Total Rows:** ~5,000+

**Recommendation:** Consolidate to 3 databases:
- jarvis_core.db (trades, positions, users, config) - ~600KB
- jarvis_analytics.db (metrics, logs, memory, sentiment) - ~1.2MB
- jarvis_cache.db (rate limiting, sessions, temp data) - ~100KB

---

## All Databases (29 total)

### Primary Databases (data/)

| Database | Size | Tables | Rows | Purpose | Status |
|----------|------|--------|------|---------|--------|
| **telegram_memory.db** | 312K | 4 | 1,719 | Telegram conversation history | ✓ VERIFIED |
| **jarvis.db** | 300K | 13 | 652 | Main trading DB (positions, trades, stats) | ✓ VERIFIED |
| **jarvis_x_memory.db** | 200K | 7 | 299 | Twitter/X bot memory & tweets | ✓ VERIFIED |
| **call_tracking.db** | 188K | 5 | 564 | Trading call performance tracking | ✓ VERIFIED |
| **jarvis_admin.db** | 156K | 5 | 1,087 | Telegram admin (users, messages, moderation) | ✓ VERIFIED |
| **jarvis_memory.db** | 140K | 14 | ~10 | AI memory (entities, facts, reflections) | ✓ VERIFIED |

| **raid_bot.db** | 76K | 5 | 6 | Telegram raid bot | ✓ VERIFIED |
| **sentiment.db** | 48K | 4 | 1 | Sentiment analysis | ✓ VERIFIED |
| **tax.db** | 44K | 3 | 2 | Tax tracking | ✓ VERIFIED |
| **whales.db** | 40K | 3 | 0 | Whale tracking (empty) | ✓ VERIFIED |
| **llm_costs.db** | 36K | 3 | 20 | LLM cost tracking | ✓ VERIFIED |
| **metrics.db** | 36K | 3 | 0 | Performance metrics | ✓ VERIFIED |
| **rate_limiter.db** | 36K | 3 | 5 | Rate limiting | ✓ VERIFIED |
| **treasury_trades.db** | 28K | 2 | 28 | Treasury trades | ✓ VERIFIED |
| **others** | <24K | 1-4 | 0-10 | Various (see below) | ✓ VERIFIED |

---

## Consolidation Plan

### Target 1: jarvis_core.db (~600KB)
**Purpose:** Core operational data  
**Tables:** positions, trades, scorecard, treasury_orders, tax_lots, sales

### Target 2: jarvis_analytics.db (~1.2MB)  
**Purpose:** Analytics, memory, logs  
**Tables:** messages, tweets, learnings, sentiment, metrics, whale data

### Target 3: jarvis_cache.db (~100KB)
**Purpose:** Temporary data  
**Tables:** cache_entries, rate_limiter logs

---

## Migration Complexity: 30-40 hours

**Risks:** 
- FTS tables (jarvis_memory.db)
- Foreign keys (positions ← trades)
- 100+ code path updates

**Mitigation:**
- WAL mode for concurrent access
- Connection pooling
- Feature flag rollback

---

## Next Steps

1. Create migration scripts (Task 01-02)
2. Test in staging
3. Production migration with rollback plan
4. Monitor 7 days
5. Clean up old files

