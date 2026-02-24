# Jarvis Roadmap

## Phase 1-4 Algo Delivery Track (2026-02-24)

This track is the current production hardening focus for Jarvis Sniper.

1. Phase 1: PyTorch backtesting foundation
- CoinGecko ingestion and dataset/model/tuning scaffolding under `core/backtest/`.

2. Phase 2: Open Claw + Jupiter perps reliability
- Signal engines and Wilson confidence gating under `core/open_claw/`.
- Perps execution/reconciliation client path under `bots/jupiter_perps/`.

3. Phase 3: Specialized snipers
- TradFi feed + strategy mapper under `core/intel/` and `bots/tradfi_sniper/`.
- Alvara allocator/client scaffolding under `bots/alvara_manager/`.

4. Phase 4: CI/CD and release automation
- Python logic gates in `.github/workflows/python-testing.yml`.
- Deployment flow in `.github/workflows/deploy.yml` with production hardening checks.

See:
- `docs/operations/2026-02-24-phase14-claim-audit.md`
- `docs/operations/2026-02-24-validation-matrix.md`

**Created:** 2026-01-24
**Updated:** 2026-02-02
**Current Milestone:** V2 - Combined Scope (ClawdBot Evolution + Web Trading)
**V1 Status:** Complete (2026-01-26)

---

## V2 Milestone: Combined Scope

**Goal:**
1. Complete ClawdBot team evolution with shared module library
2. Replicate Telegram `/demo` bot trading functionality in a modern React web application

**Completion Criteria:**
- ClawdBot shared modules deployed to VPS
- All REQ-V2-001 through REQ-V2-006 (P0) satisfied
- WebSocket real-time updates working
- Mobile-responsive design
- Zero critical bugs
- <500ms API response time

---

## V2 Phase Status Summary

| Phase | Status | Progress | Requirements |
|-------|--------|----------|--------------|
| Phase 0: ClawdBot Infrastructure | Complete | 100% | Shared module library |
| Phase 1: Core Trading MVP | Pending | 0% | REQ-V2-001 to REQ-V2-006 |
| Phase 2: Discovery Features | Pending | 0% | REQ-V2-007 to REQ-V2-011 |
| Phase 3: Power User Features | Pending | 0% | REQ-V2-012 to REQ-V2-016 |
| Phase 4: Polish & Mobile | Pending | 0% | Mobile optimization |

---

## V2 Phase Breakdown

### Phase 0: ClawdBot Infrastructure
**Status:** In Progress (90%)
**Priority:** P0
**Estimated Duration:** 1 day (agents completing)

**Goal:** Complete shared module library for ClawdBot team (Matt/Friday/Jarvis)

**ClawdBot Team (VPS: 76.13.106.100):**
| Bot | Role | LLM | Status |
|-----|------|-----|--------|
| Matt | COO | GPT-5.2 (Codex CLI) | ✅ Running |
| Friday | CMO | Opus 4.5 (clawdbot CLI) | ✅ Running |
| Jarvis | CTO+CFO | Grok 4 (xAI) | ✅ Running |

**Shared Modules Created (28/28):**
```
bots/shared/
├── __init__.py              # Module exports
├── analytics.py             # Bot analytics & metrics
├── cache.py                 # Shared caching layer
├── campaign_orchestrator.py # Multi-bot campaign coordination
├── command_registry.py      # Centralized command registration
├── computer_capabilities.py # Remote computer control via Tailscale
├── config_loader.py         # Configuration management
├── conversation_memory.py   # Conversation state persistence
├── coordination.py          # Inter-bot coordination protocol
├── cost_tracker.py          # API cost tracking per bot
├── error_handler.py         # Unified error handling
├── heartbeat.py             # Proactive health monitoring
├── life_control_commands.py # Life Control System integration
├── logging_utils.py         # Structured logging
├── observability.py         # MOLT observability integration
├── personality.py           # SOUL personality loader
├── rate_limiter.py          # API rate limiting
├── scheduler.py             # Task scheduling
├── security.py              # Security utilities
├── self_healing.py          # Auto-recovery system
├── sleep_compute.py         # Sleep-time computation
├── state_manager.py         # Bot state persistence
├── user_preferences.py      # User preference storage
└── webhook_handler.py       # Webhook processing
```

**Completed (28/28 modules):**
- message_queue.py ✅ (2026-02-02)
- feature_flags.py ✅ (2026-02-02)
- response_templates.py ✅ (2026-02-02)
- utils.py ✅ (2026-02-02)

**Success Criteria:**
- [x] 24+ shared modules created
- [x] All 3 ClawdBots running on VPS
- [ ] All modules deployed to VPS
- [ ] Integration tests pass
- [ ] Documentation complete

**Remaining Tasks:**
1. Wait for remaining agents to complete
2. Update bots/shared/__init__.py with all exports
3. Deploy to VPS: `rsync -avz bots/shared/ root@76.13.106.100:/root/clawdbots/bots/shared/`
4. Restart ClawdBot services

**Note:** NO DELETING VPS or infrastructure - only improve/adjust

---

### Phase 1: Core Trading MVP
**Status:** Pending
**Requirements:** REQ-V2-001 to REQ-V2-006
**Priority:** P0
**Estimated Duration:** 2-3 weeks

**Goal:** Minimum viable trading interface with all P0 features

**Deliverables:**
1. **Backend API** (Flask + Flask-SocketIO)
   - `/api/status` - Wallet, balance, position count
   - `/api/positions` - All positions with P&L
   - `/api/token/sentiment` - AI sentiment (Grok)
   - `/api/trade/buy` - Execute buy with mandatory TP/SL
   - `/api/trade/sell` - Execute sell (partial/full)
   - `/api/market/regime` - Market regime indicator
   - WebSocket `/ws/prices` - Real-time price updates

2. **Frontend Components** (React)
   - Portfolio dashboard (balance, P&L, position count)
   - Position list with sort/filter
   - Buy token modal with TP/SL
   - Sell position modal with preview
   - AI sentiment display
   - WebSocket connection indicator

3. **Integration**
   - Import trading logic from `tg_bot/handlers/demo/`
   - Connect to bags.fm (primary) + Jupiter (fallback)
   - Wire TP/SL monitoring service

**Success Criteria:**
- [ ] Portfolio shows accurate balance and P&L
- [ ] Buy flow works with mandatory TP/SL
- [ ] Sell flow works (25%, 50%, 100%)
- [ ] AI sentiment displays for any token
- [ ] Real-time prices update via WebSocket
- [ ] Mobile-responsive layout

**Tasks:**
1. API endpoints implementation
2. WebSocket price feed
3. React components (portfolio, positions, buy, sell)
4. State management (positions, balance)
5. Integration with existing trading logic
6. Testing and verification

**Dependencies:** None
**Blockers:** None

---

### Phase 2: Discovery Features
**Status:** Pending
**Requirements:** REQ-V2-007 to REQ-V2-011
**Priority:** P1
**Estimated Duration:** 1-2 weeks
**Depends On:** Phase 1

**Goal:** Token discovery and position management features

**Deliverables:**
1. **Trending Tokens**
   - Bags.fm top 15 integration
   - Quick buy from trending list
   - Auto-refresh (60s)

2. **TP/SL Adjustment**
   - Adjust TP/SL on existing positions
   - Immediate effect on monitoring

3. **Trailing Stops**
   - Configure trail percentage
   - Visual indicator on position

4. **Watchlist**
   - Add/remove tokens
   - Price tracking
   - Quick buy

5. **Price Alerts**
   - Set above/below alerts
   - Toast notifications

**Success Criteria:**
- [ ] Trending tokens display and update
- [ ] TP/SL adjustment works
- [ ] Trailing stops functional
- [ ] Watchlist persists across sessions
- [ ] Alerts trigger correctly

---

### Phase 3: Power User Features
**Status:** Pending
**Requirements:** REQ-V2-012 to REQ-V2-016
**Priority:** P2
**Estimated Duration:** 1-2 weeks
**Depends On:** Phase 2

**Goal:** Advanced features for power traders

**Deliverables:**
1. Sniper configuration
2. DCA plans
3. Bull vs Bear AI debate
4. Complete trade history
5. P&L reports and analytics

**Success Criteria:**
- [ ] Sniper config works
- [ ] DCA plans execute correctly
- [ ] AI debate displays both sides
- [ ] Trade history with filters
- [ ] P&L reports accurate

---

### Phase 4: Polish & Mobile
**Status:** Pending
**Priority:** P1
**Estimated Duration:** 1 week
**Depends On:** Phase 3

**Goal:** Mobile optimization and final polish

**Deliverables:**
1. Mobile-responsive breakpoints (640px, 768px, 1024px)
2. Touch-friendly interactions
3. Dark mode (default)
4. Performance optimization
5. Error state handling
6. Loading state polish

**Success Criteria:**
- [ ] Works on mobile devices
- [ ] Dark mode looks good
- [ ] All loading states handled
- [ ] All error states have friendly messages
- [ ] Performance <500ms for all operations

---

## V2 Technical Stack

| Layer | Technology | Notes |
|-------|------------|-------|
| Backend | Flask + Flask-SocketIO | Matches existing `web/task_web.py` |
| Frontend | React | Matches existing `frontend/` |
| State | React Context/Zustand | TBD during Phase 1 |
| Styling | TailwindCSS | Mobile-first, dark mode |
| WebSocket | Socket.IO | Real-time prices |
| Trading | bags.fm + Jupiter | Existing integration |
| AI | Grok (xAI) | Existing integration |

---

## V2 Timeline Estimate

```
Phase 1: Core Trading MVP       [████████████████████] 2-3 weeks
Phase 2: Discovery Features     [████████████] 1-2 weeks
Phase 3: Power User Features    [████████████] 1-2 weeks
Phase 4: Polish & Mobile        [████████] 1 week
---
Total: 5-8 weeks
```

---

## V2 Risk Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| WebSocket instability | Medium | High | Reconnection logic with exponential backoff |
| Port conflicts | Low | Medium | Use 5001 (task_web uses 5000) |
| Mobile responsiveness | Medium | Low | TailwindCSS responsive design |
| Real-time P&L overhead | Medium | Medium | Cache prices (5s TTL) |

---

---

# V1 Milestone: Production Ready (COMPLETE)

**Status:** ✅ COMPLETE
**Completed:** 2026-01-26
**Duration:** 4 days (vs. 10-13 weeks estimated)

---

## V1 Phase Summary (All Complete)

| Phase | Status | Completion Date |
|-------|--------|-----------------|
| Phase 1: Database Consolidation | ✅ Complete | 2026-01-26 |
| Phase 2: Demo Bot & Refactoring | ✅ Complete | 2026-01-26 |
| Phase 3: Vibe Command | ✅ Complete | 2026-01-26 |
| Phase 4: bags.fm + TP/SL | ✅ Complete | 2026-01-26 |
| Phase 5: Solana Integration | ✅ Complete | 2026-01-24 |
| Phase 6: Security | ✅ Complete | 2026-01-24 |
| Phase 7: Testing & QA | ✅ Complete | 2026-01-25 |
| Phase 8: Launch Prep | ✅ Complete | 2026-01-25 |

---

## V1 Key Achievements

- Database consolidation: 28 -> 3 databases (89% reduction)
- Demo bot fully functional with 240 tests passing
- bags.fm API integrated with Jupiter fallback
- Mandatory TP/SL on 100% of trades
- Zero critical security vulnerabilities
- 80%+ test coverage on critical paths
- 13,621 total tests in 438 files
- Production-grade Solana stack (v0.36.11 + Jito MEV)
- Comprehensive monitoring (200+ exports)
- 50+ documentation files

---

**Document Version:** 3.0
**Last Updated:** 2026-02-01
**Next Review:** After V2 Phase 1 completion
