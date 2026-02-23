# Jarvis Sniper — Roadmap

**Created:** 2026-02-09
**Milestone:** v2.0 — Backtesting, Advanced Algorithms, Data Integration
**Phase 1 Status:** ✅ Complete

---

## Phase Summary

| Phase | Name | Goal | Requirements | Status |
|-------|------|------|--------------|--------|
| 1 | Core Trading MVP | Dynamic scoring, presets, auto-snipe | SCORE-*, TRADE-*, UX-* | ✅ Complete |
| 2.1 | Backtesting Pipeline | Validate all strategies with historical data | BACK-01, BACK-02, BACK-03 | Pending |
| 2.2 | Data Integration | tvscreener + market hours for equity scoring | DATA-01, DATA-02, BACK-04 | Pending |
| 2.3 | Wallet Safety & Circuit Breakers | Fund persistence + per-asset risk isolation | WALLET-01, WALLET-02, CIRCUIT-01 | Planned |
| 2.4 | Advanced Algorithms | Research-backed strategies + regime detection | ALGO-01, ALGO-02, ALGO-04 | Pending |
| 2.5 | Power Features | Pairs trading, gradual sizing, on-chain SL/TP | ALGO-03, CIRCUIT-02, EXEC-01 | Pending |

---

## Phase 1: Core Trading MVP ✅ COMPLETE

**Goal:** Multi-asset trading terminal with dynamic scoring, 16 presets, auto-snipe.

**Delivered:**
- Dynamic scoring (`calcBlueChipScore`, `calcEquityScore`)
- 17-token blue chip registry
- Per-asset SL/TP calibration
- 16 strategy presets across 5 asset classes
- Auto-snipe pipeline with budget controls
- Session export
- Asset-type-aware filters
- Strategy switch continuity

---

## Phase 2.1: Backtesting Pipeline

**Goal:** Validate all 16 strategy presets against historical data. Users and operators need confidence that claimed win rates are real.

**Requirements:** BACK-01, BACK-02, BACK-03

**Success Criteria:**
1. Historical OHLCV data collected for all 17 blue chip tokens (6+ months, 1h candles)
2. Memecoin graduation history loaded (5000+ tokens)
3. Backtesting engine simulates entries/exits with realistic slippage and fees
4. All 16 strategies produce validation reports with: Win Rate, Profit Factor, Max Drawdown, Sharpe Ratio
5. Underperforming strategies identified and flagged

**Plans:** 3 plans

Plans:
- [ ] 02.1-01-PLAN.md — Historical data hardening (Birdeye fallback + memecoin graduation data)
- [ ] 02.1-02-PLAN.md — Backtest dashboard UI (hook + panel + main page integration)
- [ ] 02.1-03-PLAN.md — Strategy validation + win rate update (run all 16, flag underperformers)

**Dependencies:** None — can start immediately
**Data needed:** OHLCV candles, graduation history
**Already built:** backtest-engine.ts, historical-data.ts, api/backtest/route.ts

---

## Phase 2.2: Data Integration

**Goal:** Enrich equity scoring with real TradingView stock data and add continuous backtesting.

**Requirements:** DATA-01, DATA-02, BACK-04

**Success Criteria:**
1. tvscreener API integrated — pulling RSI, MACD, volume for mapped symbols
2. `calcEquityScore()` uses both on-chain (DexScreener) and off-chain (tvscreener) data
3. Market hours indicator shows pre/regular/after status
4. Equity scores demonstrably more accurate with cross-referenced data
5. Continuous backtesting runs daily on new data

**Plans:** 3 plans

Plans:
- [ ] 02.2-01-PLAN.md — TradingView API route & symbol mapping (tv-screener.ts + /api/tv-screener)
- [ ] 02.2-02-PLAN.md — Enhanced equity scoring with TV indicators (TDD: tv-scoring.ts + xstocks route update)
- [ ] 02.2-03-PLAN.md — Market hours UI indicator + continuous backtesting endpoint

**Dependencies:** Phase 2.1 (backtesting engine)
**Already researched:** `.planning/research/TVSCREENER.md` — full integration plan, symbol mappings, API payload structure

---

## Phase 2.3: Wallet Safety & Circuit Breakers

**Goal:** Ensure user funds are never lost and trading stops don't cascade across asset classes.

**Requirements:** WALLET-01, WALLET-02, CIRCUIT-01

**Success Criteria:**
1. Ephemeral wallet persists across tab closes (localStorage, encrypted)
2. Auto-sweep triggers on `beforeunload` — all funds return to main wallet
3. Fund recovery UI shows warning and one-click sweep
4. Per-asset circuit breakers isolate losses by asset class
5. Memecoin consecutive losses don't disable blue chip trading

**Plans:** 3 plans

Plans:
- [ ] 02.3-01-PLAN.md — Harden auto-sweep (fire-and-forget) + FundRecoveryBanner component
- [ ] 02.3-02-PLAN.md — Per-asset circuit breaker config, cooldowns, and UI controls
- [ ] 02.3-03-PLAN.md — Edge case hardening + integration verification (network timeout, tab crash, visual check)

**Dependencies:** None — can start immediately
**Already built:** session-wallet.ts (localStorage backup, XOR encryption, registerAutoSweep, checkForRecoverableWallet), per-asset breaker counters in store (AssetClassBreaker, perAsset on CircuitBreakerState)
**Gaps addressed:** Unreliable async sweep in beforeunload, no standalone fund recovery UI, no per-class configurable limits, no cooldown auto-reset

---

## Phase 2.4: Advanced Algorithms

**Goal:** Implement research-backed trading strategies from awesome-systematic-trading, with regime detection.

**Requirements:** ALGO-01, ALGO-02, ALGO-04

**Success Criteria:**
1. At least 4 new strategies implemented from research (mean reversion, trend follow, breakout, momentum factor)
2. Each strategy backtested and validated (Phase 2.1 engine)
3. Volatility regime detector identifies trending/mean-reverting/volatile markets
4. Auto-strategy-select matches regime to best strategy
5. Multi-timeframe confirmation reduces false signals by >20%

**Tasks:**
1. Implement mean reversion strategy (Bollinger Bands / RSI)
2. Implement enhanced trend following (ADX + EMA crossover)
3. Implement breakout strategy (range detection + volume confirmation)
4. Implement momentum factor ranking
5. Build regime detector (ATR + Bollinger width + realized vol)
6. Build multi-timeframe confirmation (5m + 1h + 24h alignment)
7. Backtest each new strategy
8. Add as new presets in store

**Dependencies:** Phase 2.1 (backtesting for validation), Phase 2.2 (tvscreener for richer data)

---

## Phase 2.5: Power Features

**Goal:** Advanced trading capabilities for power users.

**Requirements:** ALGO-03, CIRCUIT-02, EXEC-01

**Success Criteria:**
1. Pairs trading identifies correlated tokens and trades spread mean reversion
2. Gradual position sizing reduces risk after consecutive losses
3. Jupiter Trigger Orders provide on-chain SL/TP (positions survive browser close)

**Tasks:**
1. Build correlation matrix for blue chip tokens
2. Implement Z-score spread trading for token pairs
3. Implement Kelly criterion position sizing
4. Integrate Jupiter Trigger Order API for on-chain SL/TP
5. Update position tracking to include on-chain order keys

**Dependencies:** Phase 2.4 (algorithms), Phase 2.3 (circuit breakers)

---

## Phase Ordering Rationale

- **2.1 Backtesting first:** Can't validate algorithms without backtesting infrastructure
- **2.2 Data second:** tvscreener enriches scoring, continuous backtesting monitors drift
- **2.3 Wallet/Circuit parallel:** Independent of algorithm work, can run alongside 2.1/2.2
- **2.4 Algorithms after data:** Better data -> better algorithm validation
- **2.5 Power last:** Advanced features built on solid foundation

---

**Document Version:** 1.1
**Last Updated:** 2026-02-10
