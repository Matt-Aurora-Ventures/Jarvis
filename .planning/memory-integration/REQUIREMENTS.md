# Requirements: Clawdbot Memory System Integration

**Defined:** 2026-01-25
**Core Value:** Every Jarvis bot remembers everything and evolves intelligence based on evidence

---

## v1 Requirements

Requirements for Clawdbot memory integration into Jarvis Phases 6-8.

### Memory Foundation

- [ ] **MEM-001**: Create unified memory workspace structure at `~/jarvis/memory/`
- [ ] **MEM-002**: Implement SQLite schema (facts, entities, entity_mentions, preferences, sessions, facts_fts, fact_embeddings)
- [ ] **MEM-003**: Create Markdown layer (memory.md, daily logs in memory/YYYY-MM-DD.md, bank/ structure)
- [ ] **MEM-004**: Integrate with existing PostgreSQL archival_memory for vector embeddings
- [ ] **MEM-005**: Implement FTS5 full-text search across all facts

### Retain Functions (Storage)

- [ ] **RET-001**: Implement core `retain_fact(content, context, entities, source)` function
- [ ] **RET-002**: Integrate retain into Treasury trading system (after every trade)
- [ ] **RET-003**: Integrate retain into Telegram bot (user preferences, conversation context)
- [ ] **RET-004**: Integrate retain into X/Twitter bot (post performance, audience reactions)
- [ ] **RET-005**: Integrate retain into Bags Intel (graduation patterns, token outcomes)
- [ ] **RET-006**: Implement `retain_preference(user, key, value, evidence)` with confidence tracking
- [ ] **RET-007**: Implement entity extraction and linking (@tokens, @users, @strategies)
- [ ] **RET-008**: Auto-append facts to daily Markdown logs (memory/YYYY-MM-DD.md)

### Recall Functions (Retrieval)

- [ ] **REC-001**: Implement core `recall(query, k, filters)` with hybrid search (FTS5 + vector)
- [ ] **REC-002**: Integrate recall into Treasury before trade decisions
- [ ] **REC-003**: Integrate recall into Telegram before responses
- [ ] **REC-004**: Integrate recall into X before posting
- [ ] **REC-005**: Integrate recall into Bags Intel for graduation predictions
- [ ] **REC-006**: Implement `get_user_preferences(user)` for personalization
- [ ] **REC-007**: Implement `get_entity_summary(entity_name)` for context
- [ ] **REC-008**: Support temporal filters (last 7 days, last month, all time)

### Reflect Functions (Synthesis)

- [ ] **REF-001**: Implement daily `reflect()` function for memory synthesis
- [ ] **REF-002**: Update core memory.md with key daily facts
- [ ] **REF-003**: Update entity summaries in bank/entities/
- [ ] **REF-004**: Evolve preference confidence scores based on evidence
- [ ] **REF-005**: Archive old daily logs (>30 days)
- [ ] **REF-006**: Generate weekly summary reports
- [ ] **REF-007**: Detect contradictions in facts and flag for review

### Session Management

- [ ] **SES-001**: Implement session tracking (per-user, per-platform)
- [ ] **SES-002**: Link platform identities (Telegram user = X user = API user)
- [ ] **SES-003**: Isolate memory by user (multi-user support)
- [ ] **SES-004**: Store session metadata (conversation context, current task)
- [x] **SES-005**: Support cross-session context (resume conversations)

### Entity System

- [x] **ENT-001**: Implement entity extraction from facts (@mentions)
- [x] **ENT-002**: Create entity profiles for tokens (bank/entities/tokens/)
- [x] **ENT-003**: Create entity profiles for users (bank/entities/users/)
- [x] **ENT-004**: Create entity profiles for strategies (bank/entities/strategies/)
- [ ] **ENT-005**: Auto-update entity summaries during reflect
- [ ] **ENT-006**: Support entity relationships (token → strategy, user → preferences)

### Integration with Existing Jarvis Systems

- [ ] **INT-001**: Migrate existing PostgreSQL archival_memory learnings to new schema
- [ ] **INT-002**: Link SQLite fact_embeddings to PostgreSQL archival_memory.id
- [ ] **INT-003**: Preserve existing semantic search functionality
- [x] **INT-004**: Integrate with Trust Ladder (confidence scores inform autonomy levels)
- [x] **INT-005**: Track 81+ trading strategy performance in memory
- [ ] **INT-006**: Store state in `~/.lifeos/memory/` alongside existing trading state

### Performance & Quality

- [ ] **PERF-001**: Recall queries execute in <100ms p95
- [ ] **PERF-002**: Daily reflect completes in <5 minutes
- [ ] **PERF-003**: Memory database size stays <500MB for 10K facts
- [ ] **PERF-004**: Concurrent access from multiple bots without conflicts
- [ ] **QUAL-001**: 100% of trade outcomes stored with full context
- [ ] **QUAL-002**: User preferences tracked with confidence evolution
- [ ] **QUAL-003**: Entity mentions correctly extracted and linked

---

## v2 Requirements

Deferred to future releases.

### Advanced Memory Features

- **MEM-V2-001**: Memory export/import for backups
- **MEM-V2-002**: Memory visualization dashboard
- **MEM-V2-003**: Distributed memory across multiple instances
- **MEM-V2-004**: Memory compression for old facts

### Intelligence Enhancements

- **INT-V2-001**: Automatic pattern detection from facts
- **INT-V2-002**: Anomaly detection in preferences (confidence drops)
- **INT-V2-003**: Predictive analytics based on historical memory
- **INT-V2-004**: Cross-entity correlation discovery

### Multi-User

- **USER-V2-001**: Multi-tenant memory isolation
- **USER-V2-002**: Shared memory pools (public facts)
- **USER-V2-003**: User permission system for memory access

---

## Out of Scope

| Feature | Reason |
|---------|--------|
| Replace PostgreSQL | Extend existing system, don't replace |
| Real-time collaboration | Single user for V1 |
| Memory versioning (git-like) | Overkill for V1 |
| Natural language queries | RRF search sufficient for V1 |
| Mobile app for memory | Web/CLI only for V1 |

---

## Traceability

Which phases cover which requirements. Maps to Jarvis V1 Phases 6-8.

| Requirement | Phase | Status |
|-------------|-------|--------|
| MEM-001 | Phase 6 | Complete |
| MEM-002 | Phase 6 | Complete |
| MEM-003 | Phase 6 | Complete |
| MEM-004 | Phase 6 | Complete |
| MEM-005 | Phase 6 | Complete |
| RET-001 | Phase 7 | Complete |
| RET-002 | Phase 7 | Complete |
| RET-003 | Phase 7 | Complete |
| RET-004 | Phase 7 | Complete |
| RET-005 | Phase 7 | Complete |
| RET-006 | Phase 7 | Complete |
| RET-007 | Phase 7 | Complete |
| RET-008 | Phase 7 | Complete |
| REC-001 | Phase 7 | Complete |
| REC-002 | Phase 7 | Complete |
| REC-003 | Phase 7 | Complete |
| REC-004 | Phase 7 | Complete |
| REC-005 | Phase 7 | Complete |
| REC-006 | Phase 7 | Complete |
| REC-007 | Phase 7 | Complete |
| REC-008 | Phase 7 | Complete |
| REF-001 | Phase 8 | Pending |
| REF-002 | Phase 8 | Pending |
| REF-003 | Phase 8 | Pending |
| REF-004 | Phase 8 | Pending |
| REF-005 | Phase 8 | Pending |
| REF-006 | Phase 8 | Pending |
| REF-007 | Phase 8 | Pending |
| SES-001 | Phase 6 | Complete |
| SES-002 | Phase 6 | Complete |
| SES-003 | Phase 6 | Complete |
| SES-004 | Phase 6 | Complete |
| SES-005 | Phase 7 | Pending |
| ENT-001 | Phase 7 | Pending |
| ENT-002 | Phase 7 | Pending |
| ENT-003 | Phase 7 | Pending |
| ENT-004 | Phase 7 | Pending |
| ENT-005 | Phase 8 | Pending |
| ENT-006 | Phase 8 | Pending |
| INT-001 | Phase 6 | Complete |
| INT-002 | Phase 6 | Complete |
| INT-003 | Phase 6 | Complete |
| INT-004 | Phase 7 | Pending |
| INT-005 | Phase 7 | Pending |
| INT-006 | Phase 6 | Complete |
| PERF-001 | Phase 7 | Complete |
| PERF-002 | Phase 8 | Pending |
| PERF-003 | Phase 8 | Pending |
| PERF-004 | Phase 7 | Complete |
| QUAL-001 | Phase 7 | Complete |
| QUAL-002 | Phase 7 | Complete |
| QUAL-003 | Phase 7 | Complete |

**Coverage:**
- v1 requirements: 50 total
- Mapped to phases: 50
- Unmapped: 0 ✓

---

*Requirements defined: 2026-01-25*
*Last updated: 2026-01-25 after initial definition*
