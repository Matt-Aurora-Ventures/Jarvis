# R4 Realistic-TP Optimization — Complete Session Handoff

**Date:** 2026-02-15
**Session Scope:** Reduce all 26 strategy TPs from unrealistic v5 sweep values (75-200%) to realistic levels (9-30%), re-optimize SL/entry types, update all live application files.
**Author:** Cascade AI (session with user)

---

## TABLE OF CONTENTS

1. [Starting State (Before This Session)](#1-starting-state)
2. [User's Request](#2-users-request)
3. [Mathematical Foundation](#3-mathematical-foundation)
4. [Data Sources](#4-data-sources)
5. [Every File Modified](#5-every-file-modified)
6. [Every Strategy Parameter Change (Before → After)](#6-every-strategy-parameter-change)
7. [6 Rounds of Optimization (Detailed)](#7-six-rounds-of-optimization)
8. [Entry Type System Explained](#8-entry-type-system)
9. [Win Rate Change Analysis](#9-win-rate-change-analysis)
10. [Files NOT Updated (Remaining Work)](#10-files-not-updated)
11. [Test Results](#11-test-results)
12. [Verification Checklist](#12-verification-checklist)

---

## 1. STARTING STATE

Before this session, the codebase was at **v5 sweep optimization** (documented in `BACKTEST_V3_CHANGELOG.md`):

### v5 Strategy Parameters (BEFORE this session)

| Strategy | SL% | TP% | Trail% | Entry | WR% | PF | Exp%/trade | Trades |
|----------|-----|-----|--------|-------|-----|-----|-----------|--------|
| elite | 15 | 75 | 5 | momentum | 34.1 | 1.67 | +6.72 | 185 |
| pump_fresh_tight | 15 | 75 | 5 | fresh_pump | 31.1 | 1.54 | +5.86 | 209 |
| micro_cap_surge | 15 | 75 | 5 | aggressive | 32.2 | 1.51 | +5.38 | 289 |
| momentum | 20 | 200 | 5 | mean_reversion | 32.1 | 1.53 | +6.53 | 1176 |
| hybrid_b | 20 | 200 | 5 | mean_reversion | 32.1 | 1.53 | +6.53 | 1176 |
| let_it_ride | 20 | 200 | 5 | mean_reversion | 32.1 | 1.53 | +6.53 | 1176 |
| utility_swing | 25 | 200 | 5 | mean_reversion | 55.2 | 3.12 | +19.78 | 67 |
| meme_classic | 25 | 200 | 5 | mean_reversion | 50.0 | 2.93 | +19.36 | 106 |
| volume_spike | 25 | 200 | 5 | dip_buy | 38.8 | 2.31 | +19.32 | 299 |
| sol_veteran | 25 | 200 | 5 | mean_reversion | 50.0 | 2.68 | +17.12 | 104 |
| established_breakout | 25 | 200 | 5 | mean_reversion | 37.7 | 2.05 | +14.43 | 390 |
| bags_fresh_snipe | 15 | 60 | 5 | fresh_pump | 42.1 | 1.73 | +6.42 | 38 |
| bags_momentum | 15 | 75 | 5 | momentum | 38.0 | 1.82 | +6.56 | 50 |
| bags_value | 7 | 21 | 4 | mean_reversion | 49.2 | 1.93 | +2.59 | 65 |
| bags_dip_buyer | 10 | 50 | 5 | dip_buy | 30.4 | 1.50 | +2.48 | 102 |
| bags_bluechip | 6 | 18 | 4 | mean_reversion | 53.2 | 2.16 | +3.67 | 62 |
| bags_conservative | 7 | 21 | 4 | mean_reversion | 49.3 | 1.76 | +2.74 | 71 |
| bags_aggressive | 15 | 75 | 5 | aggressive | 37.1 | 1.30 | +2.52 | 89 |
| bags_elite | 6 | 18 | 4 | mean_reversion | 48.6 | 2.05 | +3.84 | 37 |
| bluechip_trend_follow | 15 | 120 | 5 | mean_reversion | 29.1 | 1.55 | +6.02 | 667 |
| bluechip_breakout | 15 | 120 | 5 | mean_reversion | 29.1 | 1.55 | +6.02 | 667 |
| xstock_intraday | 10 | 100 | 5 | trend_follow | 21.4 | 1.21 | +1.82 | 3384 |
| xstock_swing | 10 | 100 | 5 | trend_follow | 21.6 | 1.24 | +2.03 | 3156 |
| prestock_speculative | 10 | 100 | 5 | trend_follow | 20.2 | 1.18 | +1.57 | 2781 |
| index_intraday | 10 | 100 | 5 | trend_follow | 21.6 | 1.24 | +2.03 | 3156 |
| index_leveraged | 10 | 100 | 5 | trend_follow | 21.4 | 1.21 | +1.82 | 3384 |

**v5 Overall:** 26/26 profitable, 25.1% WR, +3.62% avg PnL, 22,886 trades

### Why v5 Was Unrealistic
- **200% TP on established tokens** (RAY, JUP, BONK) means waiting for a token to **triple**. This almost never happens on established tokens in real trading.
- **100% TP on tokenized stocks** (xSPY, xAAPL) means waiting for a 100% move. Stocks move 1-4% per day.
- **75% TP on memecoins** requires a token to nearly double. While possible, it's rare.
- The high PFs (2.0-3.0) were driven by the few trades that hit these extreme TPs paying for many losses.

---

## 2. USER'S REQUEST

The user requested:
1. Reduce TPs to realistic levels (10-30%) across all strategies
2. Apply 3:1 Reward:Risk ratio for xstock/index/prestock strategies (researched from stock swing trading articles)
3. Disable trailing stops (proven to be hidden losses at sub-friction levels)
4. Run full backtest pipeline after each change and analyze results
5. Iterate through multiple rounds to maximize profitability
6. Create a comprehensive audit file
7. Update all live application files with final parameters

### External Research Referenced
- **Source:** https://tradethatswing.com/how-to-set-profit-targets-when-swing-trading-stocks/
- **Key finding:** Minimum 3:1 reward:risk ratio for profitable swing trading
- **Application:** For xstock/index, if risking 4% SL → need 10-12% TP minimum

---

## 3. MATHEMATICAL FOUNDATION

### 3.1 Friction Model

Every trade has fixed costs:
```
Position size: $10.00
Buy fee:       ~$0.03 (Solana DEX swap fee)
Sell fee:      ~$0.03
Total friction: ~$0.06 per round-trip = ~0.6% of position
Effective friction on returns: ~1.9% (because it applies to both entry and exit)
```

### 3.2 Breakeven Win Rate Formula

For a given SL% and TP%, the breakeven WR (ignoring friction) is:
```
Breakeven WR = SL / (SL + TP)
```

With friction adjustment (~1.9% drag):
```
Effective Win = TP - 1.9%  (friction reduces each win)
Effective Loss = SL + 1.9%  (friction increases each loss)
Adjusted Breakeven WR = (SL + 1.9%) / ((SL + 1.9%) + (TP - 1.9%))
```

### 3.3 Breakeven WR for Each R:R Ratio Used

| SL% | TP% | R:R | Raw Breakeven WR | Friction-Adjusted Breakeven WR | Achievable? |
|-----|-----|-----|-----------------|-------------------------------|-------------|
| 10 | 20 | 2:1 | 33.3% | ~36% | ✅ Yes (proven 39-41% WR) |
| 10 | 25 | 2.5:1 | 28.6% | ~33% | ⚠️ Barely (achieved 32-33% WR) |
| 8 | 15 | 1.9:1 | 34.8% | ~40% | ✅ Yes for 3/5 (47-53% WR) |
| 5 | 10 | 2:1 | 33.3% | ~40% | ✅ Yes (50-55% WR on bags) |
| 5 | 9 | 1.8:1 | 35.7% | ~42% | ✅ Yes (54-55% WR on bags) |
| 7 | 25 | 3.6:1 | 21.9% | ~27% | ✅ Yes (33% WR) |
| 8 | 25 | 3.1:1 | 24.2% | ~30% | ✅ Yes (36% WR) |
| 10 | 30 | 3:1 | 25.0% | ~31% | ⚠️ Barely (29-37% WR) |
| 4 | 10 | 2.5:1 | 28.6% | ~31% | ❌ No (32% WR but friction kills it) |

### 3.4 Why SL > TP Always Loses (Math Proof)

```
Example: SL 12%, TP 6% (old v3 style)
- Each win: +$0.60 - $0.06 = +$0.54 net
- Each loss: -$1.20 - $0.06 = -$1.26 net
- Breakeven WR: $1.26 / ($0.54 + $1.26) = 70%
- With additional friction: needs ~77% WR
- Crypto achievable WR: 30-55%
- Result: IMPOSSIBLE to profit
```

### 3.5 Why Trailing Stops Are Hidden Losses

```
Scenario: Trail at 5%, position is +3% (sub-friction)
- Trail triggers exit at +3%
- After friction: +3% - 1.9% = +1.1% net
- This looks like a "win" but:
  - Without trail, position might reach TP (+15-25%)
  - Trail cuts winners short while SL takes full losses
  - Net effect: drags average PnL negative
  
Solution: Set trailingStopPct = 99 (effectively disabled)
- Only SL and TP trigger exits
- Each trade is binary: full SL loss or full TP win
- This makes the math clean and predictable
```

---

## 4. DATA SOURCES

### 4.1 Backtest Pipeline

The backtest runs through a 6-phase pipeline:

| Phase | Script | Purpose |
|-------|--------|---------|
| 01 | `01_fetch_data.ts` | Fetch OHLCV candle data from Solana DEXes |
| 02 | `02_build_universe.ts` | Build token universe from fetched data |
| 03 | `03_filter_by_algo.ts` | Filter tokens by strategy-specific criteria |
| 04 | `04_fetch_candles.ts` | Fetch detailed candles for filtered tokens |
| **05** | **`05_simulate_trades.ts`** | **Simulate trades with SL/TP/entry params** |
| **06** | **`06_generate_reports.ts`** | **Generate summary reports and CSVs** |

**Only Phases 05 and 06 were modified and re-run during this session.**

### 4.2 Data Files (Input — NOT Modified)

| File | Contents | Size |
|------|----------|------|
| `backtest-data/data/candles/*.json` | OHLCV candle data per token | ~928 tokens |
| `backtest-data/data/token_universe.csv` | All tokens with metadata | ~928 rows |
| `backtest-data/data/filtered_*.csv` | Pre-filtered tokens per strategy | 26 files |

### 4.3 Results Files (Output — Regenerated Each Run)

| File | Contents |
|------|----------|
| `backtest-data/results/results_{algo_id}.json` | Per-trade details for each strategy |
| `backtest-data/results/results_{algo_id}.csv` | Same in CSV format |
| `backtest-data/results/summary_{algo_id}.json` | Strategy-level summary (WR, PF, Exp, trades) |
| `backtest-data/results/master_comparison.csv` | All 26 strategies ranked side-by-side |
| `backtest-data/results/master_comparison.json` | Same in JSON format |
| `backtest-data/results/master_all_trades.csv` | Every individual trade (27,686 rows) |

### 4.4 How Results Numbers Were Obtained

Each number in the strategy tables came directly from the backtest output files. The pipeline:
1. Reads OHLCV candles for each token assigned to a strategy
2. Scans candles for entry signals matching the strategy's `EntryType`
3. Simulates each trade: enters at signal price, exits at SL/TP/maxAge
4. Calculates per-trade PnL including $0.06 friction
5. Aggregates into WR%, PF, Expectancy, trade count per strategy
6. Writes results to JSON/CSV files

**The numbers cited in STRATEGY_PRESETS descriptions come directly from `master_comparison.csv`.**

---

## 5. EVERY FILE MODIFIED

### 5.1 `backtest-data/scripts/05_simulate_trades.ts`

**What was modified:**
- `ALGO_EXIT_PARAMS` array (lines 53-99): SL, TP, trailingStopPct, maxPositionAgeHours for all 26 strategies
- `getEntryType()` function (lines 129-146): Entry signal mapping for all 26 strategies

**Modification count:** 14 edits across 6 rounds (R1-R6), with R5 and R6 reverted back to R4.

**Final state of ALGO_EXIT_PARAMS:**
```typescript
const ALGO_EXIT_PARAMS: AlgoExitParams[] = [
  // MEMECOIN CORE — 3 strategies (SL 10%, TP 20% = 2:1 R:R)
  { algo_id: 'elite',                stopLossPct: 10,  takeProfitPct: 20,  trailingStopPct: 99, maxPositionAgeHours: 12 },
  { algo_id: 'micro_cap_surge',      stopLossPct: 10,  takeProfitPct: 20,  trailingStopPct: 99, maxPositionAgeHours: 8 },
  { algo_id: 'pump_fresh_tight',     stopLossPct: 10,  takeProfitPct: 20,  trailingStopPct: 99, maxPositionAgeHours: 8 },

  // MEMECOIN WIDE — 3 strategies (SL 10%, TP 25% = 2.5:1 R:R)
  { algo_id: 'momentum',             stopLossPct: 10,  takeProfitPct: 25,  trailingStopPct: 99, maxPositionAgeHours: 24 },
  { algo_id: 'hybrid_b',             stopLossPct: 10,  takeProfitPct: 25,  trailingStopPct: 99, maxPositionAgeHours: 24 },
  { algo_id: 'let_it_ride',          stopLossPct: 10,  takeProfitPct: 25,  trailingStopPct: 99, maxPositionAgeHours: 48 },

  // ESTABLISHED TOKENS — 5 strategies (SL 8%, TP 15%)
  { algo_id: 'sol_veteran',          stopLossPct: 8,   takeProfitPct: 15,  trailingStopPct: 99, maxPositionAgeHours: 168 },
  { algo_id: 'utility_swing',        stopLossPct: 8,   takeProfitPct: 15,  trailingStopPct: 99, maxPositionAgeHours: 168 },
  { algo_id: 'established_breakout', stopLossPct: 8,   takeProfitPct: 15,  trailingStopPct: 99, maxPositionAgeHours: 168 },
  { algo_id: 'meme_classic',         stopLossPct: 8,   takeProfitPct: 15,  trailingStopPct: 99, maxPositionAgeHours: 168 },
  { algo_id: 'volume_spike',         stopLossPct: 8,   takeProfitPct: 15,  trailingStopPct: 99, maxPositionAgeHours: 168 },

  // BAGS.FM — 8 strategies (mixed params)
  { algo_id: 'bags_fresh_snipe',     stopLossPct: 10,  takeProfitPct: 30,  trailingStopPct: 99, maxPositionAgeHours: 8 },
  { algo_id: 'bags_momentum',        stopLossPct: 10,  takeProfitPct: 30,  trailingStopPct: 99, maxPositionAgeHours: 12 },
  { algo_id: 'bags_aggressive',      stopLossPct: 7,   takeProfitPct: 25,  trailingStopPct: 99, maxPositionAgeHours: 12 },
  { algo_id: 'bags_dip_buyer',       stopLossPct: 8,   takeProfitPct: 25,  trailingStopPct: 99, maxPositionAgeHours: 8 },
  { algo_id: 'bags_elite',           stopLossPct: 5,   takeProfitPct: 9,   trailingStopPct: 99, maxPositionAgeHours: 4 },
  { algo_id: 'bags_value',           stopLossPct: 5,   takeProfitPct: 10,  trailingStopPct: 99, maxPositionAgeHours: 4 },
  { algo_id: 'bags_conservative',    stopLossPct: 5,   takeProfitPct: 10,  trailingStopPct: 99, maxPositionAgeHours: 4 },
  { algo_id: 'bags_bluechip',        stopLossPct: 5,   takeProfitPct: 9,   trailingStopPct: 99, maxPositionAgeHours: 4 },

  // BLUE CHIP SOLANA — 2 strategies (SL 10%, TP 25% = 2.5:1 R:R)
  { algo_id: 'bluechip_trend_follow',stopLossPct: 10,  takeProfitPct: 25,  trailingStopPct: 99, maxPositionAgeHours: 48 },
  { algo_id: 'bluechip_breakout',    stopLossPct: 10,  takeProfitPct: 25,  trailingStopPct: 99, maxPositionAgeHours: 48 },

  // xSTOCK & PRESTOCK — SL 4%, TP 10% = 2.5:1 R:R
  { algo_id: 'xstock_intraday',      stopLossPct: 4,   takeProfitPct: 10,  trailingStopPct: 99, maxPositionAgeHours: 96 },
  { algo_id: 'xstock_swing',         stopLossPct: 4,   takeProfitPct: 10,  trailingStopPct: 99, maxPositionAgeHours: 96 },
  { algo_id: 'prestock_speculative', stopLossPct: 4,   takeProfitPct: 10,  trailingStopPct: 99, maxPositionAgeHours: 96 },

  // INDEX — SL 4%, TP 10% = 2.5:1 R:R
  { algo_id: 'index_intraday',       stopLossPct: 4,   takeProfitPct: 10,  trailingStopPct: 99, maxPositionAgeHours: 96 },
  { algo_id: 'index_leveraged',      stopLossPct: 4,   takeProfitPct: 10,  trailingStopPct: 99, maxPositionAgeHours: 96 },
];
```

**Final state of getEntryType():**
```typescript
function getEntryType(algoId: string): EntryType {
  if (['pump_fresh_tight', 'bags_fresh_snipe'].includes(algoId)) return 'fresh_pump';
  if (['micro_cap_surge', 'bags_aggressive'].includes(algoId)) return 'aggressive';
  if (['elite', 'bags_momentum'].includes(algoId)) return 'momentum';
  if (['momentum', 'hybrid_b', 'let_it_ride', 'bluechip_trend_follow', 'bluechip_breakout'].includes(algoId)) return 'mean_reversion';
  if (['bags_value', 'bags_bluechip', 'bags_elite', 'bags_conservative'].includes(algoId)) return 'mean_reversion';
  if (['xstock_swing', 'xstock_intraday', 'index_intraday', 'index_leveraged'].includes(algoId)) return 'mean_reversion';
  if (['prestock_speculative'].includes(algoId)) return 'mean_reversion';
  if (['volume_spike'].includes(algoId)) return 'mean_reversion';
  if (['bags_dip_buyer'].includes(algoId)) return 'dip_buy';
  if (['sol_veteran', 'utility_swing', 'established_breakout', 'meme_classic'].includes(algoId)) return 'mean_reversion';
  return 'momentum';
}
```

---

### 5.2 `src/stores/useSniperStore.ts`

**What was modified:**

#### A. STRATEGY_PRESETS header comment (lines 164-174)
- **Before:** Referenced v5 sweep (27,573 trades, 26/26 profitable)
- **After:** References R4 realistic-TP (27,686 trades, 15/26 profitable, 6 borderline, 5 disabled)

#### B. All 26 STRATEGY_PRESETS entries (lines 175-537)
Every single preset was updated with:
- New `stopLossPct`, `takeProfitPct`, `trailingStopPct` values
- New `description` strings with R4 backtest metrics
- New `winRate` and `trades` values from R4 results
- `disabled: true` added to 5 xstock/index/prestock strategies

#### C. setStrategyMode() function (lines 1226-1235)
- **Before:**
  ```typescript
  aggressive:   { sl: 45, tp: 250, trail: 20 },
  balanced:     { sl: 20, tp: 100, trail: 10 },
  conservative: { sl: 20, tp: 80,  trail: 8  },
  ```
- **After:**
  ```typescript
  aggressive:   { sl: 10, tp: 25, trail: 99 },
  balanced:     { sl: 8,  tp: 15, trail: 99 },
  conservative: { sl: 5,  tp: 10, trail: 99 },
  ```

#### D. NOT MODIFIED (still has old values):
- **`getRecommendedSlTp()` function (lines 751-872)** — This function dynamically recommends SL/TP based on token metrics. It still contains old v5/v7 values (e.g., trail 4-6 for memecoins, SL 1.5/TP 3 for xstocks). This was NOT updated because the STRATEGY_PRESETS now directly set the SL/TP/trail for each strategy, and getRecommendedSlTp is only called when no preset is active.

---

### 5.3 `src/lib/bags-strategies.ts`

**What was modified:** All 8 `BAGS_STRATEGY_PRESETS` entries updated with R4 params.

**Before → After for each bags strategy:**

| Strategy | Before SL/TP/Trail | After SL/TP/Trail | Before WR | After WR | Before Trades | After Trades |
|----------|--------------------|-------------------|-----------|----------|---------------|-------------|
| bags_fresh_snipe | 15/60/5 | **10/30/99** | 42.1% | **37.5%** | 38 | **48** |
| bags_momentum | 15/75/5 | **10/30/99** | 38.0% | **29.5%** | 50 | **61** |
| bags_value | 7/21/4 | **5/10/99** | 49.2% | **50.7%** | 65 | **71** |
| bags_dip_buyer | 10/50/5 | **8/25/99** | 30.4% | **36.4%** | 102 | **110** |
| bags_bluechip | 6/18/4 | **5/9/99** | 53.2% | **54.5%** | 62 | **66** |
| bags_conservative | 7/21/4 | **5/10/99** | 49.3% | **51.3%** | 71 | **78** |
| bags_aggressive | 15/75/5 | **7/25/99** | 37.1% | **33.3%** | 89 | **105** |
| bags_elite | 6/18/4 | **5/9/99** | 48.6% | **55.0%** | 37 | **40** |

---

### 5.4 `src/__tests__/bags-strategies.test.ts`

**What was modified:** 10 test assertions updated to match R4 values.

| Test | Before | After |
|------|--------|-------|
| bags_conservative WR | '49.3%' | '51.3%' |
| bags_conservative trades | 71 | 78 |
| bags_momentum WR | '38.0%' | '29.5%' |
| bags_momentum trades | 50 | 61 |
| bags_value WR | '49.2%' | '50.7%' |
| bags_value trades | 65 | 71 |
| bags_aggressive TP min | ≥50 | ≥20 |
| bags_aggressive WR | '37.1%' | '33.3%' |
| bags_aggressive trades | 89 | 105 |
| bags_elite WR | '48.6%' | '55.0%' |
| bags_elite trades | 37 | 40 |
| bags_fresh_snipe WR | '42.1%' | '37.5%' |
| bags_fresh_snipe trades | 38 | 48 |
| bags_dip_buyer WR | '30.4%' | '36.4%' |
| bags_dip_buyer trades | 102 | 110 |
| bags_bluechip WR | '53.2%' | '54.5%' |
| bags_bluechip trades | 62 | 66 |
| trailingStopPct range | 0-30 | exactly 99 |
| takeProfitPct min | ≥10 | ≥9 |

---

### 5.5 `backtest-data/BACKTEST_OPTIMIZATION_AUDIT.md`

**Created new file** (307 lines) documenting all 6 rounds of optimization, final parameters, xstock deep dive, key learnings, data locations, and parameter change history per strategy.

---

## 6. EVERY STRATEGY PARAMETER CHANGE (Before → After)

### MEMECOIN CORE (3 strategies)

| Strategy | v5 SL | R4 SL | v5 TP | R4 TP | v5 Trail | R4 Trail | v5 Entry | R4 Entry |
|----------|-------|-------|-------|-------|----------|----------|----------|----------|
| elite | 15 | **10** | 75 | **20** | 5 | **99** | momentum | momentum (unchanged) |
| pump_fresh_tight | 15 | **10** | 75 | **20** | 5 | **99** | fresh_pump | fresh_pump (unchanged) |
| micro_cap_surge | 15 | **10** | 75 | **20** | 5 | **99** | aggressive | aggressive (unchanged) |

**Reasoning:** Memecoin core strategies had proven entries (momentum, fresh_pump, aggressive). SL 15→10 reduces max loss per trade. TP 75→20 is realistic (20% moves happen frequently on memecoins). 2:1 R:R requires ~36% WR with friction — achieved 39-41% WR.

### MEMECOIN WIDE (3 strategies)

| Strategy | v5 SL | R4 SL | v5 TP | R4 TP | v5 Trail | R4 Trail | v5 Entry | R4 Entry |
|----------|-------|-------|-------|-------|----------|----------|----------|----------|
| momentum | 20 | **10** | 200 | **25** | 5 | **99** | mean_reversion | mean_reversion (unchanged) |
| hybrid_b | 20 | **10** | 200 | **25** | 5 | **99** | mean_reversion | mean_reversion (unchanged) |
| let_it_ride | 20 | **10** | 200 | **25** | 5 | **99** | mean_reversion | mean_reversion (unchanged) |

**Reasoning:** TP 200→25 is a massive reduction. The 200% TP worked in backtest because rare moonshots paid for everything, but in live trading, waiting for a 200% move means most trades expire at maxAge. TP 25% with SL 10% gives 2.5:1 R:R requiring ~33% WR. Achieved 32-33% WR — borderline (PF 0.97). R6 tested switching to momentum/aggressive entries but they were worse.

### ESTABLISHED TOKENS (5 strategies)

| Strategy | v5 SL | R4 SL | v5 TP | R4 TP | v5 Trail | R4 Trail | v5 Entry | R4 Entry |
|----------|-------|-------|-------|-------|----------|----------|----------|----------|
| utility_swing | 25 | **8** | 200 | **15** | 5 | **99** | mean_reversion | mean_reversion (unchanged) |
| meme_classic | 25 | **8** | 200 | **15** | 5 | **99** | mean_reversion | mean_reversion (unchanged) |
| volume_spike | 25 | **8** | 200 | **15** | 5 | **99** | dip_buy | **mean_reversion** (changed) |
| sol_veteran | 25 | **8** | 200 | **15** | 5 | **99** | mean_reversion | mean_reversion (unchanged) |
| established_breakout | 25 | **8** | 200 | **15** | 5 | **99** | mean_reversion | mean_reversion (unchanged) |

**Reasoning:** Established tokens (RAY, JUP, BONK, WIF) are mature assets. 200% TP is fantasy. 15% TP is achievable on established tokens during dip recoveries. SL 8% gives 1.9:1 R:R requiring ~40% WR — utility_swing (52.8%), meme_classic (50.8%), sol_veteran (47.7%) comfortably clear this. established_breakout (40.2%) and volume_spike (37.2%) fall short — borderline.

**volume_spike entry change:** dip_buy → mean_reversion. dip_buy (price < SMA20 × 0.95) was too deep for volume surges. mean_reversion (price < SMA5 × 0.97) catches shallower dips that recover faster.

### BAGS.FM (8 strategies)

| Strategy | v5 SL | R4 SL | v5 TP | R4 TP | v5 Trail | R4 Trail | v5 Entry | R4 Entry |
|----------|-------|-------|-------|-------|----------|----------|----------|----------|
| bags_fresh_snipe | 15 | **10** | 60 | **30** | 5 | **99** | fresh_pump | fresh_pump (unchanged) |
| bags_momentum | 15 | **10** | 75 | **30** | 5 | **99** | momentum | momentum (unchanged) |
| bags_aggressive | 15 | **7** | 75 | **25** | 5 | **99** | aggressive | aggressive (unchanged) |
| bags_dip_buyer | 10 | **8** | 50 | **25** | 5 | **99** | dip_buy | dip_buy (unchanged) |
| bags_elite | 6 | **5** | 18 | **9** | 4 | **99** | mean_reversion | mean_reversion (unchanged) |
| bags_value | 7 | **5** | 21 | **10** | 4 | **99** | mean_reversion | mean_reversion (unchanged) |
| bags_conservative | 7 | **5** | 21 | **10** | 4 | **99** | mean_reversion | mean_reversion (unchanged) |
| bags_bluechip | 6 | **5** | 18 | **9** | 4 | **99** | mean_reversion | mean_reversion (unchanged) |

**Reasoning:** Bags strategies split into "wide" (fresh_snipe, momentum, aggressive, dip_buyer) and "tight" (elite, value, conservative, bluechip). Wide bags need larger TPs because new bags tokens have high volatility. Tight bags are on established bags tokens where 9-10% moves are more reliable. All entries unchanged — they were already optimized in v4 sweep.

### BLUE CHIP SOLANA (2 strategies)

| Strategy | v5 SL | R4 SL | v5 TP | R4 TP | v5 Trail | R4 Trail | v5 Entry | R4 Entry |
|----------|-------|-------|-------|-------|----------|----------|----------|----------|
| bluechip_trend_follow | 15 | **10** | 120 | **25** | 5 | **99** | mean_reversion | mean_reversion (unchanged) |
| bluechip_breakout | 15 | **10** | 120 | **25** | 5 | **99** | mean_reversion | mean_reversion (unchanged) |

**Reasoning:** Bluechip Solana tokens ($200K+ liquidity) don't regularly make 120% moves. 25% is realistic for multi-day holds. R3 tested `breakout` entry — it was much worse (-0.94% vs +0.11%). Mean_reversion confirmed as best entry.

### xSTOCK / PRESTOCK / INDEX (5 strategies)

| Strategy | v5 SL | R4 SL | v5 TP | R4 TP | v5 Trail | R4 Trail | v5 Entry | R4 Entry |
|----------|-------|-------|-------|-------|----------|----------|----------|----------|
| xstock_intraday | 10 | **4** | 100 | **10** | 5 | **99** | trend_follow | **mean_reversion** |
| xstock_swing | 10 | **4** | 100 | **10** | 5 | **99** | trend_follow | **mean_reversion** |
| prestock_speculative | 10 | **4** | 100 | **10** | 5 | **99** | trend_follow | **mean_reversion** |
| index_intraday | 10 | **4** | 100 | **10** | 5 | **99** | trend_follow | **mean_reversion** |
| index_leveraged | 10 | **4** | 100 | **10** | 5 | **99** | trend_follow | **mean_reversion** |

**Reasoning:** Per user's research on stock swing trading (3:1 R:R). TP 100→10 because tokenized stocks should behave like stocks (5-15% swings, not 100%). SL 10→4 to maintain good R:R. Entry changed from trend_follow to mean_reversion because trend_follow (look for sustained uptrend) doesn't work at 10% TP — mean_reversion (buy dips) gave the best WR of all 8 entry types tested (32.2%). **Still unprofitable at every realistic TP level.**

### setStrategyMode() Defaults

| Mode | v5 SL | R4 SL | v5 TP | R4 TP | v5 Trail | R4 Trail |
|------|-------|-------|-------|-------|----------|----------|
| aggressive | 45 | **10** | 250 | **25** | 20 | **99** |
| balanced | 20 | **8** | 100 | **15** | 10 | **99** |
| conservative | 20 | **5** | 80 | **10** | 8 | **99** |

**Reasoning:** These defaults apply when user switches strategy mode manually (not via preset). Aligned to R4 backtest-proven ranges for each risk level.

---

## 7. SIX ROUNDS OF OPTIMIZATION (Detailed)

### Round 1: Initial Realistic TPs
**Changes to 05_simulate_trades.ts:**
- Cut all TPs by 50-90% from v5 sweep values
- Memecoin: SL 8%, TP 15%
- Established: SL 8%, TP 15%
- xstock/index: SL 5%, TP 15% (3:1 R:R per user's research)
- Bags: TPs halved

**Result:** ~8/26 profitable. TP too low for memecoins (they need 20%+ to be profitable). xstock/index still losing.

### Round 2: Fix R:R Ratios
**Changes:**
- Memecoin core: SL 10%, TP 20% (2:1 R:R) — widened SL for volatility
- Memecoin wide: SL 10%, TP 20% (same)
- Bluechip: SL 10%, TP 20%
- xstock/index: SL 3%, TP 10% (3.3:1 R:R) — tighter SL
- Entry change: xstock/index → mean_reversion, prestock → dip_buy

**Result:** 10/26 profitable. Memecoin core now works. xstock WR too low at 3% SL (28.7%).

### Round 3: Entry Type Experiments
**Changes:**
- xstock: tried pullback_buy, sma_crossover entries
- index: tried accumulation, range_breakout entries
- Bluechip: tried breakout entry
- Some memecoin strategies: tried breakout, range_breakout
- SL tweaks: established_breakout SL 7%, volume_spike SL 8%

**Result:** WORSE than R2. Every alternative entry type produced lower WR. Bluechip breakout entry was -0.94% (vs +0.11% with mean_reversion). **All R3 changes reverted.**

### Round 4: Consolidation (FINAL) ✅
**Changes (from R2 base):**
- Memecoin wide: TP 20→25 (2.5:1 R:R instead of 2:1) — needed more room
- Bluechip: TP 20→25 (same reasoning)
- xstock/index: SL 3→4 (4% SL gives slightly better WR than 3%)
- volume_spike: entry dip_buy → mean_reversion

**Result:** 15/26 profitable — BEST of all rounds.

### Round 5: Micro-Tweaks (Failed)
**Changes:**
- established_breakout: SL 8→6 (trying to tighten)
- momentum/hybrid_b/let_it_ride: TP 25→30
- volume_spike: SL 8→6
- bags_momentum: SL 8→10

**Result:** All worse. Tighter SL drops WR faster than R:R improves. **All R5 changes reverted.**

### Round 6: Entry Type Switch (Failed)
**Changes:**
- momentum/hybrid_b: mean_reversion → momentum entry
- let_it_ride: mean_reversion → aggressive entry
- volume_spike: mean_reversion → aggressive entry

**Result:** All worse. Alternative entries generate MORE trades but LOWER quality signals (more noise trades dilute WR). **All R6 changes reverted.**

**Final conclusion: R4 is the best parameter set.**

---

## 8. ENTRY TYPE SYSTEM

Each strategy uses a specific entry signal type defined in `getEntryType()`. These are algorithmic rules that scan OHLCV candles:

| Entry Type | Logic | Which Strategies Use It |
|------------|-------|------------------------|
| `momentum` | Green candle body > 2× average, close near high, above SMA5 | elite, bags_momentum |
| `fresh_pump` | 3+ consecutive green candles, each close > previous | pump_fresh_tight, bags_fresh_snipe |
| `aggressive` | Volume > 2× average, close > SMA5, any candle color | micro_cap_surge, bags_aggressive |
| `mean_reversion` | Price < SMA5 × 0.97, green candle after red (dip bounce) | momentum, hybrid_b, let_it_ride, bluechip_*, xstock_*, index_*, bags_value, bags_bluechip, bags_elite, bags_conservative, volume_spike, sol_veteran, utility_swing, established_breakout, meme_classic, prestock_speculative |
| `dip_buy` | Price < SMA20 × 0.95, green candle (deeper dip) | bags_dip_buyer |

### Entry types tested but NOT used (proven worse):
- `breakout` — Close above 20-candle high on volume (R3: worse for bluechip)
- `range_breakout` — 10-candle range < 5%, then breakout (R3: worse for index)
- `pullback_buy` — Price pulls back to SMA20 in uptrend (R3: worse for xstock)
- `sma_crossover` — SMA5 crosses above SMA20 (R3: worse for xstock)
- `accumulation` — Volume builds before breakout (R3: worse for index)
- `trend_follow` — v5 default for xstock, replaced by mean_reversion in R2
- `strict_trend` — Stricter trend_follow variant, never tested in R4

---

## 9. WIN RATE CHANGE ANALYSIS

### Why Some WRs Went DOWN (SL tightened more than TP helped)

| Strategy | v5 SL→R4 SL | v5 TP→R4 TP | SL tightened | TP easier | Net WR effect |
|----------|-------------|-------------|-------------|-----------|---------------|
| bags_fresh_snipe | 15→10 | 60→30 | 1.5x tighter | 2x easier | WR down (SL dominated) |
| bags_momentum | 15→10 | 75→30 | 1.5x tighter | 2.5x easier | WR down |
| bags_aggressive | 15→7 | 75→25 | 2.1x tighter | 3x easier | WR down |
| momentum/hybrid_b | 20→10 | 200→25 | 2x tighter | 8x easier | WR barely changed |

### Why Some WRs Went UP (TP dropped more than SL)

| Strategy | v5 SL→R4 SL | v5 TP→R4 TP | SL tightened | TP easier | Net WR effect |
|----------|-------------|-------------|-------------|-----------|---------------|
| bags_value | 7→5 | 21→10 | 1.4x tighter | 2.1x easier | **WR UP** (49.2→50.7%) |
| bags_bluechip | 6→5 | 18→9 | 1.2x tighter | 2x easier | **WR UP** (53.2→54.5%) |
| bags_elite | 6→5 | 18→9 | 1.2x tighter | 2x easier | **WR UP** (48.6→55.0%) |
| bags_conservative | 7→5 | 21→10 | 1.4x tighter | 2.1x easier | **WR UP** (49.3→51.3%) |
| bags_dip_buyer | 10→8 | 50→25 | 1.25x tighter | 2x easier | **WR UP** (30.4→36.4%) |
| elite | 15→10 | 75→20 | 1.5x tighter | 3.75x easier | **WR UP** (34.1→39.8%) |

### Key Insight
When TP drops proportionally MORE than SL tightens, WR goes UP.
When SL tightens proportionally MORE than TP drops, WR goes DOWN.
The WR direction depends on which force dominates.

---

## 10. FILES NOT UPDATED (Remaining Work)

These files still contain **old v5 sweep values** and need to be updated in a future session:

### 10.1 `src/components/strategy-info.ts` (CRITICAL)
**Status:** Still has v5 params in every strategy's `params` and `summary` fields.

Examples of stale data:
```typescript
// Current (WRONG — still v5):
momentum: {
  summary: 'Mean-reversion dip-buy with 200% TP target...',
  params: 'SL 20% | TP 200% | Trail 5% | ...',
}
// Should be (R4):
momentum: {
  summary: 'Mean-reversion dip-buy with 25% TP target...',
  params: 'SL 10% | TP 25% | Trail disabled | ...',
}
```

**All 26 strategy entries need updating in this file.**

### 10.2 `src/components/strategy-categories.ts`
**Status:** Category groupings are correct (no params in this file). However, the TOP PERFORMERS category still lists `volume_spike` which is now borderline (PF 0.91). Consider replacing with `bags_value` or `sol_veteran`.

### 10.3 `src/stores/useSniperStore.ts` — `getRecommendedSlTp()` function
**Status:** Still has old v5/v7 dynamic SL/TP logic with trailing stops enabled (trail 1-6). This function is called when no preset is active. It should be updated to:
- Return trail: 99 everywhere (disabled)
- Align SL/TP ranges with R4 params
- Update xstock/index returns to match 4/10 params

### 10.4 `src/__tests__/strategy-presets.test.ts`
**Status:** 37 tests currently passing. These tests check structural things (26 presets exist, IDs are unique, TP > SL) — they don't hardcode specific WR/trade values like the bags tests do, so they pass without changes.

### 10.5 `StrategyPreset` interface
**Status:** The `disabled` property was added to xstock/index/prestock presets but the `StrategyPreset` TypeScript interface may not include `disabled?: boolean`. This could cause TypeScript errors if strict type checking is enabled. Needs verification.

---

## 11. TEST RESULTS

```
Test Files  2 passed (2)
     Tests  60 passed (60)
  Duration  1.54s

Files tested:
- src/__tests__/strategy-presets.test.ts (37 tests)
- src/__tests__/bags-strategies.test.ts (23 tests)
```

All tests pass with the R4 parameter updates.

---

## 12. VERIFICATION CHECKLIST

For the reviewing LLM to verify:

### Math Checks
- [ ] Verify breakeven WR formula: `SL / (SL + TP)` for each strategy
- [ ] Verify friction-adjusted breakeven adds ~3-6% to raw breakeven WR
- [ ] Confirm TP > SL for all 26 strategies
- [ ] Confirm trailingStopPct = 99 for all 26 strategies

### Parameter Consistency Checks
- [ ] `05_simulate_trades.ts` ALGO_EXIT_PARAMS matches STRATEGY_PRESETS in `useSniperStore.ts`
- [ ] `bags-strategies.ts` BAGS_STRATEGY_PRESETS matches bags entries in STRATEGY_PRESETS
- [ ] WR%, PF, Exp%, Trades in preset descriptions match master_comparison.csv
- [ ] Test assertions in `bags-strategies.test.ts` match `bags-strategies.ts` values

### Logic Checks
- [ ] getEntryType() maps every algo_id in ALGO_EXIT_PARAMS to an entry type
- [ ] No algo_id appears in multiple entry type groups (no duplicates)
- [ ] xstock/index/prestock strategies have `disabled: true`
- [ ] setStrategyMode() trail values are 99 (disabled) for all modes

### Remaining Work
- [ ] Update `strategy-info.ts` with R4 params (26 entries)
- [ ] Update `getRecommendedSlTp()` to disable trailing stops
- [ ] Verify `StrategyPreset` interface includes `disabled?: boolean`
- [ ] Consider updating TOP PERFORMERS category (volume_spike is now borderline)

---

*This document covers every calculation, every file modification, every parameter change, and every reasoning decision made during the R4 realistic-TP optimization session on 2026-02-15.*
