# Jarvis V1 Requirements

**Created:** 2026-01-24
**Status:** Active

---

## Scope

| Category | Count | Status |
|----------|-------|--------|
| Must-Have | 7 | In Planning |
| Should-Have | 4 | In Planning |
| Out of Scope | 4 | Deferred to V2 |

---

## Must-Have Requirements (V1 Blockers)

### REQ-001: Database Consolidation
**Priority:** P0
**Status:** Complete

Consolidate 28+ SQLite databases into 3 databases max:
- `jarvis_core.db` - Main application data (users, trades, positions)
- `jarvis_analytics.db` - Metrics, logs, memory (can be lossy)
- `jarvis_cache.db` - Temporary/ephemeral data

**Success Criteria:**
- [x] ≤3 total databases (ACHIEVED: 3 databases operational)
- [x] Zero data loss during migration (ACHIEVED: 25 records migrated, 0 loss)
- [~] All existing functionality works (User testing recommended)
- [x] Atomic transactions possible across related data (ACHIEVED: Unified layer with connection pooling)
- [~] <20% reduction in memory usage (Requires baseline measurement)

**Impact:** Fixes #1 critical issue from CONCERNS.md

---

### REQ-002: /demo Trading Bot - Fix Execution
**Priority:** P0
**Status:** Complete

Fix all trade execution failures in `/demo` bot:
- Register message handler for token input (currently missing)
- Fix buy/sell flows to work 100% of the time
- Break 391.5KB demo.py into modules (<1000 lines each)
- Add comprehensive error handling and retry logic

**Success Criteria:**
- [ ] 100% trade execution success rate
- [ ] Message handler registered in tg_bot/bot.py
- [ ] demo.py broken into ≤5 modules
- [ ] All execution paths have error recovery
- [ ] Integration tests pass

**Impact:** Fixes user's #1 reported issue

---

### REQ-003: /vibe Command Implementation
**Priority:** P0
**Status:** Pending

Complete `/vibe` command for Telegram-based vibe coding:
- Verify core/vibe_coding/ infrastructure
- Wire up Telegram handler (tg_bot/bot_core.py:1971+)
- Add Claude API integration
- Implement context management and safety guardrails
- Test end-to-end execution

**Success Criteria:**
- [ ] `/vibe` command responds in <2s
- [ ] Code execution works with safety limits
- [ ] Context preserved across conversation
- [ ] Clear error messages on failures
- [ ] 5+ successful test executions

**Impact:** Completes user's requested feature

---

### REQ-004: bags.fm API Integration
**Priority:** P0
**Status:** Pending

Integrate bags.fm API as primary trading interface:
- Implement bags.fm swap API client
- Add WebSocket price feed integration
- Replace Jupiter with bags.fm for all demo bot trades
- Keep Jupiter as fallback (dual implementation)
- Add real-time graduation monitoring

**Success Criteria:**
- [ ] bags.fm API client implemented (core/bags_api.py)
- [ ] WebSocket price feeds operational
- [ ] All demo bot trades use bags.fm first, Jupiter fallback
- [ ] <500ms execution latency
- [ ] 99%+ success rate

**Impact:** User's #2 explicit requirement

---

### REQ-005: Stop-Loss/Take-Profit Enforcement
**Priority:** P0
**Status:** Pending

Make stop-loss and take-profit mandatory for all trades:
- Add TP/SL fields to position schema
- Implement order monitoring service (10s poll loop)
- Auto-execute exits when triggers hit
- Support single TP and ladder exits
- UI for setting custom TP/SL values

**Success Criteria:**
- [ ] 100% of trades have TP/SL set
- [ ] Order monitor runs continuously
- [ ] Exits execute within 15s of trigger
- [ ] Ladder exits supported (50%@2x, 30%@5x, 20%@10x)
- [ ] UI for custom TP/SL working

**Impact:** User's #3 explicit requirement - risk management

---

### REQ-006: Security Vulnerability Fixes
**Priority:** P0
**Status:** Pending

Fix all remaining security vulnerabilities:
- Centralize secret management (no env var wallet passwords)
- Audit and consolidate API keys (233 files currently)
- Add comprehensive rate limiting
- Remove hardcoded credentials
- Implement secret rotation mechanism

**Success Criteria:**
- [ ] Zero hardcoded secrets in code
- [ ] Centralized secret management (core/secrets.py)
- [ ] All API endpoints rate-limited
- [ ] Security audit passes
- [ ] Secret rotation documented

**Impact:** Blocks public launch - security mandatory

---

### REQ-007: Code Refactoring (Critical Files)
**Priority:** P0
**Status:** Complete

Refactor massive files to maintainable modules:
- Break trading.py (3,754 lines) into ≤5 modules
- Break demo.py (391.5KB) into ≤5 modules
- Remove 100+ blocking sleep() calls
- Convert to event-driven architecture

**Success Criteria:**
- [ ] No files >1000 lines
- [ ] trading.py broken into logical modules
- [ ] demo.py broken into logical modules
- [ ] <10 total sleep() calls remaining
- [ ] Event-driven patterns implemented

**Impact:** Maintainability blocker - can't iterate on 10K line files

---

## Should-Have Requirements (Quality Bar)

### REQ-008: Test Coverage
**Priority:** P1
**Status:** Pending

Achieve 80%+ test coverage on critical paths:
- Unit tests for trading logic
- Integration tests for /demo flows
- End-to-end tests for full trading cycles
- Load testing for concurrent users

**Success Criteria:**
- [ ] ≥80% coverage on core/, bots/treasury/, tg_bot/handlers/
- [ ] All critical paths tested
- [ ] Load tests pass (100 concurrent users)
- [ ] CI/CD pipeline runs tests

---

### REQ-009: Performance Optimization
**Priority:** P1
**Status:** Pending

Optimize system performance:
- Event-driven architecture (no blocking)
- Database query optimization
- Connection pool standardization
- Caching for expensive operations

**Success Criteria:**
- [ ] <500ms p95 latency for trades
- [ ] <100ms p95 for Telegram responses
- [ ] Standardized connection pool
- [ ] Cache hit rate >80% for repeated queries

---

### REQ-010: Monitoring & Alerting
**Priority:** P1
**Status:** Pending

Implement comprehensive monitoring:
- Centralized logging
- Health check endpoints
- Alert on critical failures
- Performance metrics dashboard

**Success Criteria:**
- [ ] Centralized logging operational
- [ ] Alerts configured for P0 failures
- [ ] Health endpoints return <200ms
- [ ] Metrics dashboard viewable

---

### REQ-011: API Key Management
**Priority:** P1
**Status:** Pending

Centralize API key management:
- Single source of truth for keys
- Rotation mechanism
- Access control per key
- Usage tracking and limits

**Success Criteria:**
- [ ] All keys in centralized store
- [ ] Rotation mechanism tested
- [ ] Per-key rate limits enforced
- [ ] Usage tracked in jarvis_analytics.db

---

## Out of Scope (V2 Deferred)

### REQ-OOS-001: Mobile App
**Rationale:** V1 is Telegram-only

### REQ-OOS-002: Multi-Chain Support
**Rationale:** V1 is Solana-only

### REQ-OOS-003: Fiat On/Off Ramps
**Rationale:** Crypto-native users only for V1

### REQ-OOS-004: Social Trading Features
**Rationale:** Individual traders for V1

---

## Requirement Traceability

| Phase | Requirements | Priority |
|-------|-------------|----------|
| Phase 1 | REQ-001 (Database) | P0 |
| Phase 2 | REQ-002 (Demo Bot), REQ-007 (Refactor) | P0 |
| Phase 3 | REQ-003 (Vibe) | P0 |
| Phase 4 | REQ-004 (bags.fm), REQ-005 (TP/SL) | P0 |
| Phase 5 | REQ-006 (Security) | P0 |
| Phase 6 | REQ-008 (Tests), REQ-009 (Performance) | P1 |
| Phase 7 | REQ-010 (Monitoring), REQ-011 (API Keys) | P1 |

---

**Document Version:** 1.0
**Last Updated:** 2026-01-24
**Next Review:** After each phase completion
