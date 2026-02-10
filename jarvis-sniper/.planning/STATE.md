# Jarvis Sniper — Project State

**Last Updated:** 2026-02-10
**Current Phase:** 2.1 (Backtesting Pipeline) — Plan 01 complete, Plans 02-03 pending
**Milestone:** v2.0

---

## Active Work

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1 | ✅ Complete | All 8 requirements delivered |
| Phase 2.1 | 🔄 In Progress | Plan 01 done (historical data hardened), Plans 02-03 pending |
| Phase 2.2 | ⏳ Pending | tvscreener — research complete, implementation ready |
| Phase 2.3 | ✅ Complete | Wallet persistence + per-asset circuit breakers done |
| Phase 2.4 | ⏳ Pending | Advanced algorithms — research complete (10 strategies ranked) |
| Phase 2.5 | ⏳ Pending | Power features |

---

## Plan Completion

| Plan | Name | Status | Summary |
|------|------|--------|---------|
| 02.1-01 | Historical Data Pipeline Hardening | ✅ Complete | Birdeye fallback + memecoin graduation calibration |
| 02.1-02 | Backtest Validation Runs | ⏳ Pending | |
| 02.1-03 | Backtest API Integration | ⏳ Pending | |

---

## Research Status

| Topic | Status | Output |
|-------|--------|--------|
| awesome-systematic-trading | ✅ Complete | `.planning/research/STRATEGIES.md` — 10 ranked strategies |
| tvscreener API | ✅ Complete | `.planning/research/TVSCREENER.md` — full integration plan |

---

## Already Built (This Session)

### Backtesting Engine (Phase 2.1 partial)
- `src/lib/backtest-engine.ts` — 5 entry signals, walk-forward, grid search, report generation
- `src/lib/historical-data.ts` — Multi-source OHLCV fetcher (DexScreener + Birdeye + synthetic) + memecoin graduation calibration
- `src/app/api/backtest/route.ts` — POST API with quick/full/grid modes

### Wallet Persistence (Phase 2.3 — DONE)
- `src/lib/session-wallet.ts` — localStorage backup, auto-sweep on beforeunload, fund recovery
- `registerAutoSweep()`, `checkForRecoverableWallet()`, `isLikelyFunded()`

### Per-Asset Circuit Breakers (Phase 2.3 — DONE)
- `AssetClassBreaker` interface + `perAsset` on `CircuitBreakerState`
- `closePosition` updates both global AND per-asset counters
- `snipeToken` checks per-asset breaker before entering
- `assetType` field on Position interface

---

## Key Context

### Build Status
- TypeScript: 0 errors (verified 2026-02-10)
- Dev server: port 3001

### Recent Decisions
- Session wallet stays client-side (no backend)
- Per-asset circuit breakers use Zustand counters per asset class
- All new strategies must be backtested before being added as presets
- tvscreener integration uses direct HTTP (no Python dependency)
- Birdeye public OHLCV API used as Tier 2 fallback when DexScreener returns empty
- Memecoin graduation backtesting uses 100 synthetic patterns (4 archetypes) instead of historical data
- Adaptive rate limiting: 1s for Birdeye API, 500ms for DexScreener

---

## Memory

### What Works
- `calcBlueChipScore()` produces meaningful differentiation (10-90 range)
- `calcEquityScore()` sector bonuses improve ranking quality
- Asset-type-aware snipe filters solved cross-class interference
- 30s DexScreener cache prevents rate limiting
- 3-tier OHLCV fallback ensures real data for backtests

### Watch Out For
- DexScreener sometimes returns 0 for txn counts → need graceful handling
- Bags.fm swap API can hang indefinitely → timeout required
- Google Fonts fetch fails in CI/build environments → non-critical
- Birdeye public API rate limited to ~5 req/min without API key

---

## Session Continuity

Last session: 2026-02-10T07:20Z
Stopped at: Completed 02.1-01-PLAN.md
Resume file: None

---

*Last updated: 2026-02-10*
