# Database Consolidation - Schema Mismatch Notes

**Status**: Migration blocked - requires schema mapping work
**Date**: 2026-01-25
**Issue**: Existing schemas don't match unified schema design

---

## Problem

Attempted migration failed because source database schemas have different column names than the unified schema design in `unified_schema.sql`.

### Examples of Mismatches

**positions table**:
- Source (jarvis.db): `symbol`, `token_mint`, `entry_amount_sol`, `entry_amount_tokens`
- Target (unified): `token_symbol`, `token_address`, `quantity`, `sol_invested`

**llm_usage table**:
- Source (llm_costs.db): `input_tokens`, `output_tokens`
- Target (unified): `prompt_tokens`, `completion_tokens`

**telegram messages**:
- Source (telegram_memory.db): `username`, `text`, `timestamp`
- Target (unified): `user_id`, `message_text`, `timestamp`

---

## Migration Errors (9 total)

1. `table positions has no column named symbol` - positions table mismatch
2. `table trades has no column named symbol` - trades table mismatch
3. `table items has no column named value` - items table mismatch
4. `table telegram_messages has no column named username` - telegram messages mismatch
5. `table telegram_memories has no column named key` - telegram memories mismatch
6. `table telegram_learnings has no column named topic` - telegram learnings mismatch
7. `table llm_usage has no column named input_tokens` - LLM usage mismatch
8. `table llm_daily_stats has no column named successful_requests` - LLM stats mismatch
9. `table rate_configs has no column named name` - rate config mismatch

---

## Resolution Options

### Option A: Schema Mapping (High Effort)
- Create column mapping dictionaries for each table
- Transform data during migration
- **Effort**: 4-6 hours
- **Benefit**: Clean unified schema
- **Risk**: Data transformation errors

### Option B: Copy As-Is (Low Effort)
- Copy tables with existing schemas
- Rename tables with source prefix (e.g., `jarvis_positions`, `telegram_messages`)
- **Effort**: 1 hour
- **Benefit**: Quick consolidation
- **Risk**: Multiple schema variants

### Option C: Defer Consolidation (Recommended)
- Keep databases fragmented for now
- **Effort**: 0 hours
- **Benefit**: Focus on higher-value phases (2-6)
- **Risk**: None - existing system works

---

## Recommendation: Option C (Defer)

**Rationale**:
1. Existing fragmented databases work fine (324KB + 348KB = 672KB total is small)
2. Phases 2-6 deliver more immediate value:
   - Phase 2: Demo Bot Fixes (critical bugs)
   - Phase 3: Vibe Command (new feature)
   - Phase 4: bags.fm + TP/SL (trading improvements)
   - Phase 5: Solana Fixes (reliability)
   - Phase 6: Security Audit (safety)
3. Database consolidation can be revisited post-V1 launch
4. Schema mapping requires careful design review (avoid data loss)

---

## Tasks Completed (Phase 1)

✅ Task 1: Database Inventory (35 databases catalogued)
✅ Task 2: Unified Schema Design (28 tables designed)
✅ Task 3: Migration Script (implemented with backups)
❌ Task 4: Execute Migration (blocked on schema mismatch)

**Completion**: 33% (3 of 9 tasks)

---

## Next Steps

**Immediate**: Move to Phase 2 (Demo Bot Fixes)
**Future**: Revisit Phase 1 post-V1 with proper schema mapping

---

**Document Version**: 1.0
**Created**: 2026-01-26
**Status**: Blocked - deferred to post-V1
