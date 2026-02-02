# Jarvis Requirements

**Created:** 2026-01-24
**Updated:** 2026-02-01
**Status:** V1 Complete, V2 In Progress

---

## Current Milestone: V2 - Web Trading Dashboard

### V2 Executive Summary

Replicate the Telegram `/demo` bot trading interface as a modern React web application, reusing 85% of existing backend logic.

**Scope:**
- 19 callback handlers (~5,200 lines) to replicate
- 7 existing API endpoints to extend (~15-20 new endpoints)
- ~30-40 new React components
- Real-time WebSocket updates
- Mobile-responsive dark mode UI

---

## V2 P0 Requirements (MVP - Phase 1)

### REQ-V2-001: Portfolio Dashboard
**Priority:** P0 | **Category:** Core
- Display wallet SOL balance and USD equivalent
- Show total portfolio value
- Show unrealized P&L (USD and %)
- Position count indicator
- Market regime indicator (bull/bear/crab)

### REQ-V2-002: Position List View
**Priority:** P0 | **Category:** Core
- List all open positions with:
  - Token symbol + logo
  - Entry price / Current price
  - P&L (USD and %)
  - TP/SL levels
  - Time held
- Sortable by P&L, value, time
- Quick sell buttons (25%, 50%, 100%)

### REQ-V2-003: Buy Token Flow
**Priority:** P0 | **Category:** Trading
- Token address input + validation
- Quick buy amounts: 0.05, 0.1, 0.25, 0.5, 1, 2 SOL
- Custom amount input
- **Mandatory TP/SL selection** (default: TP=50%, SL=20%)
- Pre-buy AI sentiment display
- Execute via bags.fm with Jupiter fallback
- Success confirmation with tx link

### REQ-V2-004: Sell Position Flow
**Priority:** P0 | **Category:** Trading
- Select position to sell
- Partial sell options: 25%, 50%, 100%
- Confirmation dialog with P&L preview
- Execute via bags.fm with Jupiter fallback
- 0.5% success fee on profitable trades
- Post-sell summary

### REQ-V2-005: AI Sentiment Analysis
**Priority:** P0 | **Category:** AI
- Request sentiment for any token
- Display: sentiment (bullish/bearish/neutral), score (0-100), signal
- Show AI reasoning
- Powered by Grok (xAI)

### REQ-V2-006: Real-Time Updates
**Priority:** P0 | **Category:** Infrastructure
- WebSocket connection for live price updates
- Auto-refresh positions every 5 seconds
- Reconnection logic with exponential backoff
- Visual indicator for connection status

---

## V2 P1 Requirements (Phase 2)

### REQ-V2-007: Trending Tokens
**Priority:** P1 | **Category:** Discovery
- Bags.fm top 15 trending tokens
- Quick buy from trending list
- Token details on click

### REQ-V2-008: TP/SL Adjustment
**Priority:** P1 | **Category:** Trading
- Adjust TP/SL on open positions
- Slider or input for new values
- Immediate effect on monitoring

### REQ-V2-009: Trailing Stops
**Priority:** P1 | **Category:** Trading
- Add trailing stop to position
- Configure trail percentage

### REQ-V2-010: Watchlist
**Priority:** P1 | **Category:** Discovery
- Add tokens to watchlist
- Price tracking for watchlist tokens
- Quick buy from watchlist

### REQ-V2-011: Price Alerts
**Priority:** P1 | **Category:** Alerts
- Set price alerts for tokens
- Alert types: above/below price
- Notification via UI toast

---

## V2 P2 Requirements (Phase 3)

### REQ-V2-012: Sniper Configuration
**Priority:** P2 | **Category:** Advanced
- Configure auto-snipe settings
- Token launch detection

### REQ-V2-013: DCA Plans
**Priority:** P2 | **Category:** Advanced
- Create DCA plan for token
- Configure interval and amount

### REQ-V2-014: Bull vs Bear Debate
**Priority:** P2 | **Category:** AI
- Request AI debate for any token
- Display bull vs bear arguments

### REQ-V2-015: Trade History
**Priority:** P2 | **Category:** Analytics
- Complete trade history
- Filter by date, token, P&L

### REQ-V2-016: P&L Reports
**Priority:** P2 | **Category:** Analytics
- Daily/weekly/monthly P&L
- Win rate statistics

---

## V2 Technical Requirements

### API Endpoints Required

**Phase 1 (P0):**
```
GET  /api/status          # Wallet, balance, position count
GET  /api/positions       # All positions with P&L
POST /api/token/sentiment # AI sentiment
POST /api/trade/buy       # Execute buy with TP/SL
POST /api/trade/sell      # Execute sell
GET  /api/market/regime   # Market regime
WS   /ws/prices           # Real-time price updates
```

**Phase 2 (P1):**
```
GET  /api/trending        # Bags.fm trending
GET  /api/watchlist       # User watchlist
POST /api/watchlist       # Add to watchlist
PATCH /api/positions/:id/tpsl # Update TP/SL
POST /api/alerts          # Create alert
```

**Phase 3 (P2):**
```
GET  /api/sniper/config   # Sniper settings
GET  /api/dca/plans       # DCA plans
POST /api/analysis/debate # Bull vs Bear
GET  /api/portfolio/history # Trade history
```

### Data Structures

**Position Object:**
```typescript
interface Position {
  id: string
  symbol: string
  address: string
  entryPrice: number
  currentPrice: number
  amount: number
  amountSol: number
  currentValue: number
  unrealizedPnl: number
  unrealizedPnlPct: number
  tpPrice: number
  slPrice: number
  timestamp: string
  txHash: string
  source: 'bags_fm' | 'jupiter'
}
```

### Business Rules

1. **Mandatory TP/SL**: All buys MUST have TP/SL set (default: TP=50%, SL=20%)
2. **Success Fee**: 0.5% fee on profitable trade exits
3. **Trading Source**: bags.fm primary, Jupiter DEX fallback
4. **Price Caching**: 5-second TTL for Jupiter prices

---

## V2 Implementation Phases

| Phase | Requirements | Duration |
|-------|--------------|----------|
| Phase 1 | REQ-V2-001 to REQ-V2-006 | 2-3 weeks |
| Phase 2 | REQ-V2-007 to REQ-V2-011 | 1-2 weeks |
| Phase 3 | REQ-V2-012 to REQ-V2-016 | 1-2 weeks |
| Phase 4 | Mobile optimization, polish | 1 week |

---

## V2 Success Criteria

- All P0 requirements implemented and tested
- <500ms response time for API calls
- WebSocket reconnection works reliably
- Mobile responsive on all breakpoints
- Zero critical security vulnerabilities

---

---

# V1 Requirements (COMPLETED 2026-01-26)

## V1 Summary

| Category | Count | Status |
|----------|-------|--------|
| Must-Have | 7 | Complete |
| Should-Have | 4 | Complete |

### V1 Key Achievements
- Database consolidation (28 -> 3 databases)
- Demo bot fully functional with 240 tests passing
- bags.fm API integrated with Jupiter fallback
- Mandatory TP/SL on all trades
- Zero critical security vulnerabilities
- 80%+ test coverage on critical paths

---

## V1 Must-Have Requirements (All Complete)

### REQ-001: Database Consolidation
**Status:** Complete
- Consolidated 28+ SQLite databases into 3 databases

### REQ-002: /demo Trading Bot - Fix Execution
**Status:** Complete
- 100% trade execution success rate

### REQ-003: /vibe Command Implementation
**Status:** Complete
- Verified working

### REQ-004: bags.fm API Integration
**Status:** Complete
- Primary trading interface with Jupiter fallback

### REQ-005: Stop-Loss/Take-Profit Enforcement
**Status:** Complete
- 100% of trades have mandatory TP/SL

### REQ-006: Security Vulnerability Fixes
**Status:** Complete
- Zero critical vulnerabilities

### REQ-007: Code Refactoring
**Status:** Complete
- No files >1000 lines

---

## V1 Should-Have Requirements (All Complete)

### REQ-008: Test Coverage
**Status:** Complete - 80%+ coverage

### REQ-009: Performance Optimization
**Status:** Complete - <500ms p95 latency

### REQ-010: Monitoring & Alerting
**Status:** Complete

### REQ-011: API Key Management
**Status:** Complete

---

**Document Version:** 2.0
**Author:** Claude Code
**Next:** Create ROADMAP.md with V2 phase breakdown
