# Jarvis - Autonomous Trading & AI Assistant

**Created:** 2026-01-24
**Owner:** @lucid
**Status:** V1 Complete, V2 In Progress

---

## Current Milestone: v2.0 Trading Web Interface

**Goal:** Bring all Telegram `/demo` trading functionality to a production-grade web dashboard.

**Target features:**
- Real-time position monitoring with WebSocket updates
- Buy/sell execution via web UI (mirroring Telegram flows)
- AI sentiment analysis integration (Grok/xAI)
- Portfolio value display and trade history
- Mobile-responsive design with dark mode

**Why:** Telegram is powerful for mobile/on-the-go trading, but web provides better UX for power users, multi-monitor workflows, and public demos. 85% of trading logic can be directly reused from existing `tg_bot/handlers/demo/`.

---

## Previous Milestones

### v1.0 - Production-Ready Infrastructure ✅

**Completed:** 2026-01-26
**Goal:** Transform Jarvis from fragmented experimental system into production-ready platform.

**Delivered:**
- ✅ Database consolidation (28 → 3 databases, 89% reduction)
- ✅ Demo bot fully functional with 240 tests passing
- ✅ bags.fm API integrated with Jupiter fallback
- ✅ Mandatory TP/SL on all trades
- ✅ Zero critical security vulnerabilities
- ✅ 80%+ test coverage on critical paths

---

## Vision

Transform Jarvis from a fragmented experimental system into a **production-ready, public-launch capable** autonomous trading and AI assistant platform on Solana.

**Core Pillars:**
1. **Reliability** - Zero critical bugs, <1% error rate, 99.9% uptime
2. **Intelligence** - AI-powered trading decisions with continuous learning
3. **User Experience** - Seamless Telegram interface, clear feedback, instant responses
4. **Risk Management** - Mandatory stop-loss/take-profit on every trade
5. **Performance** - Consolidated databases, optimized queries, event-driven architecture

---

## Problem Statement

### Current State
Jarvis is a powerful but fragmented system with critical blockers preventing public launch:

**Database Crisis:**
- 28+ separate SQLite databases causing fragmentation
- Data scattered across files and databases
- No atomic cross-DB transactions
- Massive overhead from multiple connection pools

**Broken Core Features:**
- `/demo` trading bot: 391.5KB monolithic file with execution failures
- `/vibe` command: Partially implemented
- Trade execution: Multiple implementations, no consistent error handling

**Missing Critical Features:**
- No stop-loss/take-profit enforcement
- No bags.fm API integration (only Jupiter)
- No unified trading interface
- No AI learning from trade outcomes

**Code Quality Issues:**
- trading.py: 3,754 lines with 65+ functions
- demo.py: ~10,000 lines in single file
- 100+ sleep() calls (blocking patterns)
- <50% test coverage (estimated)

---

## Goals

### V1 Success Criteria

**Must-Have (Blockers for Launch):**
1. ✅ `/demo` bot fully functional - buy/sell flows work 100% of the time
2. ✅ `/vibe` command operational - Telegram-based vibe coding works
3. ✅ bags.fm API integrated - Primary execution with Jupiter fallback
4. ✅ Stop-loss/take-profit mandatory - Every trade has risk management
5. ✅ Database consolidated - 3 DBs max (core, analytics, cache)
6. ✅ Zero critical security vulnerabilities
7. ✅ Core code refactored - No files >1000 lines

**Should-Have (Quality Bar):**
8. ✅ 80%+ test coverage on critical paths
9. ✅ Performance optimized - Event-driven, no blocking sleep() calls
10. ✅ Monitoring & alerting operational
11. ✅ API key management centralized

**Nice-to-Have (Post-V1):**
12. Multi-wallet support
13. Advanced order types (trailing stops, ladder exits)
14. Cross-chain trading

---

## Target Users

**Primary:** Crypto traders who want an AI-powered trading assistant

**User Personas:**
1. **Degen Trader** - High-risk meme coin trading, needs fast execution and risk controls
2. **Conservative Investor** - Wants AI recommendations with strict stop-losses
3. **Developer** - Wants to extend Jarvis via `/vibe` command

---

## Non-Goals (Out of Scope for V1)

- ❌ Mobile app (Telegram only for V1)
- ❌ Multi-chain support (Solana only)
- ❌ Fiat on/off ramps
- ❌ Social trading features
- ❌ Portfolio analytics dashboard (basic only)

---

## Technical Context

### Existing Codebase

**Core Components:**
- **bots/supervisor.py** - Orchestrates all bot components
- **bots/treasury/trading.py** - Treasury trading engine (3,754 lines - NEEDS REFACTOR)
- **tg_bot/handlers/demo.py** - Demo bot (391.5KB - NEEDS REFACTOR)
- **core/dexter/** - AI decision engine
- **core/vibe_coding/** - Vibe command infrastructure (partial)

**External Integrations:**
- Twitter/X API (OAuth)
- Telegram Bot API
- Solana RPC (Helius)
- Jupiter DEX (current primary)
- **bags.fm** (TO BE INTEGRATED)
- Grok AI (xAI)
- PostgreSQL (continuous-claude DB)

**Technical Debt:**
- 28+ SQLite databases
- Massive monolithic files
- 100+ blocking sleep() calls
- API keys scattered across 233 files
- <50% test coverage

---

## Constraints

1. **Must maintain existing functionality** - No breaking changes to live bots
2. **Zero data loss** - Database consolidation must preserve all data
3. **Backward compatible** - Existing configs and state files must work
4. **Security first** - All vulnerabilities fixed before launch
5. **Performance cannot degrade** - Optimizations only

---

## Success Metrics

**Reliability:**
- 99.9% uptime
- <1% trade execution error rate
- Zero critical security vulnerabilities

**Performance:**
- <500ms trade execution latency
- <3 databases total
- <100 total lines of sleep() calls

**Code Quality:**
- 80%+ test coverage
- No files >1000 lines
- All linting errors fixed

**User Experience:**
- 100% trade success rate in /demo bot
- <2s response time for /vibe command
- Clear error messages (no raw exceptions)

---

## References

**Codebase Analysis:**
- `.planning/codebase/CONCERNS.md` - Technical debt report
- `.planning/codebase/ARCHITECTURE.md` - System design
- `.planning/codebase/STACK.md` - Technology stack

**User Requirements:**
- User explicitly wants: Solana fixes, Telegram fixes, bags.fm integration, stop-loss/TP
- User wants: "ralph wiggum loop" - continuous iteration until V1 complete

---

**Document Version:** 2.0
**Last Updated:** 2026-01-27
**Next Review:** After V2 Phase 1 complete
