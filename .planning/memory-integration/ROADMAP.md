# Roadmap: Clawdbot Memory System Integration

## Overview

Integrate Clawdbot's hybrid Markdown + SQLite memory architecture across all Jarvis bot systems (Treasury, Telegram, X, Bags Intel) to enable persistent, personalized intelligence that evolves with evidence. This 3-phase roadmap delivers unified memory foundation, active retain/recall loops, and reflective intelligence synthesis aligned with Jarvis V1 Phases 6-8.

## Phases

**Phase Numbering:**
- Integer phases (6, 7, 8): Aligned with Jarvis V1 parent phases
- This is a brownfield integration into existing production codebase

- [x] **Phase 6: Memory Foundation** - Unified workspace, SQLite schema, PostgreSQL integration
- [ ] **Phase 7: Retain/Recall Functions** - Active memory storage and retrieval across all bots
- [ ] **Phase 8: Reflect & Intelligence** - Daily synthesis, confidence evolution, entity intelligence

## Phase Details

### Phase 6: Memory Foundation
**Goal**: Jarvis has a unified memory workspace with dual-layer storage (Markdown + SQLite) integrated with existing PostgreSQL semantic memory

**Depends on**: Nothing (brownfield integration into existing Jarvis V1)

**Requirements**: MEM-001, MEM-002, MEM-003, MEM-004, MEM-005, SES-001, SES-002, SES-003, SES-004, INT-001, INT-002, INT-003, INT-006

**Success Criteria** (what must be TRUE):
  1. Memory workspace exists at `~/jarvis/memory/` with all subdirectories (memory/, bank/, bank/entities/)
  2. SQLite database `jarvis.db` contains all required tables (facts, entities, entity_mentions, preferences, sessions, facts_fts, fact_embeddings)
  3. Markdown layer auto-creates daily logs at `memory/YYYY-MM-DD.md` when facts are stored
  4. Existing PostgreSQL archival_memory learnings (100+ entries) are accessible via new schema
  5. FTS5 full-text search returns results from stored facts in <100ms

**Plans**: 6 plans in 4 waves

Plans:
- [x] 06-01-PLAN.md — Workspace & Directory Structure (Wave 1)
- [x] 06-02-PLAN.md — SQLite Schema & Database Initialization (Wave 1)
- [x] 06-03-PLAN.md — retain_fact() with Markdown Sync (Wave 2)
- [x] 06-04-PLAN.md — FTS5 Full-Text Search (Wave 2)
- [x] 06-05-PLAN.md — PostgreSQL Integration & Hybrid Search (Wave 3)
- [x] 06-06-PLAN.md — Data Migration (Wave 4)

### Phase 7: Retain/Recall Functions
**Goal**: Every Jarvis bot system (Treasury, Telegram, X, Bags Intel, Buy Tracker) actively stores and retrieves memory to inform decisions

**Depends on**: Phase 6

**Requirements**: RET-001, RET-002, RET-003, RET-004, RET-005, RET-006, RET-007, RET-008, REC-001, REC-002, REC-003, REC-004, REC-005, REC-006, REC-007, REC-008, SES-005, ENT-001, ENT-002, ENT-003, ENT-004, INT-004, INT-005, PERF-001, PERF-004, QUAL-001, QUAL-002, QUAL-003

**Success Criteria** (what must be TRUE):
  1. Treasury bot stores trade outcomes with full context (token, price, sentiment, outcome) after every trade
  2. Treasury bot queries past trade outcomes before entering new positions
  3. Telegram bot stores user preferences from conversations and recalls them to personalize responses
  4. X/Twitter bot stores post performance (likes, retweets) and queries high-engagement patterns before posting
  5. Bags Intel stores graduation patterns and queries historical success rates before scoring new tokens
  6. User can query their preference history and see confidence scores evolving based on evidence
  7. Entity mentions (@tokens, @users, @strategies) are auto-extracted and linked across all stored facts
  8. Recall queries complete in <100ms at p95 with hybrid FTS5 + vector search

**Plans**: TBD (to be planned in Phase 7 planning session)

Plans:
- TBD

### Phase 8: Reflect & Intelligence
**Goal**: Jarvis autonomously synthesizes daily experiences into evolving intelligence with confidence-weighted opinions

**Depends on**: Phase 7

**Requirements**: REF-001, REF-002, REF-003, REF-004, REF-005, REF-006, REF-007, ENT-005, ENT-006, PERF-002, PERF-003

**Success Criteria** (what must be TRUE):
  1. Daily reflect function runs automatically and synthesizes key facts into `memory.md` core memory
  2. Entity summaries auto-update in `bank/entities/` (tokens, users, strategies) based on new facts
  3. User preference confidence scores evolve based on evidence (strengthen with confirmations, weaken with contradictions)
  4. Weekly summary reports generate and show pattern insights (e.g., "bags.fm graduations with dev Twitter presence succeed 70%")
  5. Daily reflect completes in <5 minutes and archives logs older than 30 days
  6. Memory database stays under 500MB with 10K+ facts stored

**Plans**: TBD (to be planned in Phase 8 planning session)

Plans:
- TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 6 → 7 → 8

**Integration with Jarvis V1:**
- Phase 6: Runs alongside Jarvis V1 Phase 6 (Security Fixes)
- Phase 7: Runs alongside Jarvis V1 Phase 7 (Testing & QA)
- Phase 8: Runs alongside Jarvis V1 Phase 8 (Monitoring & Launch)

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 6. Memory Foundation | 6/6 | ✓ Complete | 2026-01-25 |
| 7. Retain/Recall Functions | 0/TBD | Ready for planning | - |
| 8. Reflect & Intelligence | 0/TBD | Pending Phase 7 | - |

---

**Roadmap Version:** 1.2
**Created:** 2026-01-25
**Last Updated:** 2026-01-25 (Phase 6 complete)
