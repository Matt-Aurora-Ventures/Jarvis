# Backtest Strategy Optimization Audit

**Date:** 2026-02-15
**Scope:** 26 trading strategies across 6 optimization rounds
**Objective:** Reduce TPs to realistic levels while maximizing profitability

---

## Executive Summary

| Metric | Value |
|--------|-------|
| Total strategies | 26 |
| Profitable (Exp > 0%) | 15 |
| Borderline (PF 0.91–0.97) | 6 |
| Unprofitable (xstock/index/prestock) | 5 |
| Total trades (final run) | 27,686 |
| Position size | $10 |
| Fixed cost per trade | $0.06 (~1.9% friction) |

---

## 1. Files Modified

### Primary backtest scripts
- **`backtest-data/scripts/05_simulate_trades.ts`** — `ALGO_EXIT_PARAMS` (SL/TP/trail/maxAge per strategy) + `getEntryType()` function (entry signal mapping)
- **`backtest-data/scripts/06_generate_reports.ts`** — Report generation (unchanged, used as-is)

### Results output (auto-generated each run)
- `backtest-data/results/results_{algo_id}.json` — Per-strategy trade details
- `backtest-data/results/results_{algo_id}.csv` — Per-strategy trade CSV
- `backtest-data/results/summary_{algo_id}.json` — Per-strategy summary stats
- `backtest-data/results/master_comparison.csv` — All 26 strategies ranked
- `backtest-data/results/master_comparison.json` — Same as above, JSON format
- `backtest-data/results/master_all_trades.csv` — Every individual trade (27,686 rows)
- `backtest-data/results/data_manifest.json` — Token/candle data inventory

### Live application files (to be updated after final approval)
- `src/stores/useSniperStore.ts` — `STRATEGY_PRESETS`, `getRecommendedSlTp()`
- `src/lib/bags-strategies.ts` — `BAGS_STRATEGY_PRESETS`
- `src/components/strategy-categories.ts` — Category groupings
- `src/components/strategy-info.ts` — Strategy descriptions
- `src/__tests__/strategy-presets.test.ts` — Unit tests
- `src/__tests__/bags-strategies.test.ts` — Bags unit tests

---

## 2. Optimization Rounds (R1–R6)

### Round 1 (Initial realistic TPs)
**Goal:** Cut TPs from v4 sweep values (75–200%) to realistic levels (15–30%)
- Memecoin: SL 8%, TP 15% → **Most strategies lost money** (TP too low for crypto volatility)
- Established: SL 8%, TP 15% → Worked well
- xstock/index: SL 5%, TP 15% → Lost money
- **Result:** ~8/26 profitable

### Round 2 (Fix R:R ratios)
**Goal:** Restore TP > SL with proper R:R per asset class
- Memecoin: SL 10%, TP 20% (2:1 R:R) → Core strategies profitable
- Established: SL 8%, TP 15% (1.9:1 R:R) → 3/5 profitable
- Bluechip: SL 10%, TP 20% (2:1 R:R) → Barely profitable (+0.11%)
- xstock/index: SL 3%, TP 10% (3.3:1 R:R) → Still losing
- Entry type change: xstock/index switched to `mean_reversion` + `dip_buy`
- **Result:** 10/26 profitable

### Round 3 (Targeted entry type experiments)
**Goal:** Try selective entries for xstock/index (pullback_buy, sma_crossover, accumulation)
- xstock: `pullback_buy` / `sma_crossover` entries → Worse than mean_reversion
- index: `accumulation` / `range_breakout` entries → Worse
- Bluechip: `breakout` entry → Much worse (-0.94% vs +0.11%)
- Memecoin: `breakout` / `range_breakout` entries → Worse
- **Result:** Step backward. Reverted all R3 changes.

### Round 4 (Best round — FINAL params) ✅
**Goal:** Consolidate best params from R1-R3, try SL 4% for xstock
- Memecoin wide: mean_reversion, SL 10%, TP 25% (2.5:1 R:R)
- Bluechip: mean_reversion, SL 10%, TP 25% (2.5:1 R:R) → +0.47%
- established_breakout: SL 7%, TP 15% → -0.12% (very close)
- volume_spike: mean_reversion, SL 8%, TP 15%
- xstock/index: mean_reversion, SL 4%, TP 10% → Still losing
- **Result:** 15/26 profitable (best across all rounds)

### Round 5 (Micro-tweaks — failed)
**Goal:** Flip borderline strategies by adjusting SL/TP by 1-2%
- established_breakout SL 6% → Worse (WR dropped more than R:R improved)
- momentum/hybrid_b TP 30% → WR dropped too much
- volume_spike SL 6% → Much worse
- **Lesson:** Lowering SL drops WR faster than R:R improvement compensates
- **Result:** Reverted all R5 changes

### Round 6 (Entry type switch — failed)
**Goal:** Switch losing memecoin strategies from mean_reversion to momentum/aggressive entries
- momentum/hybrid_b: `momentum` entry → 3607 trades, WR 36.2%, -0.69% (worse)
- let_it_ride: `aggressive` entry → 3673 trades, WR 37.2%, -0.53% (worse)
- volume_spike: `aggressive` entry → 1298 trades, WR 36.6%, -0.55% (worse)
- **Lesson:** Alternative entries generate more trades but lower quality signals
- **Result:** Reverted all R6 changes. R4 confirmed as best.

---

## 3. Final Strategy Parameters (R4)

### ✅ PROFITABLE (15 strategies)

| # | Strategy | SL% | TP% | R:R | Entry | WR% | Exp% | PF | Trades |
|---|----------|-----|-----|-----|-------|-----|------|----|--------|
| 1 | utility_swing | 8 | 15 | 1.9:1 | mean_reversion | 52.8 | +2.49 | 1.57 | 123 |
| 2 | meme_classic | 8 | 15 | 1.9:1 | mean_reversion | 50.8 | +2.03 | 1.44 | 197 |
| 3 | bags_fresh_snipe | 10 | 30 | 3:1 | fresh_pump | 37.5 | +1.94 | 1.27 | 48 |
| 4 | bags_dip_buyer | 8 | 25 | 3.1:1 | dip_buy | 36.4 | +1.83 | 1.34 | 110 |
| 5 | bags_conservative | 5 | 10 | 2:1 | mean_reversion | 51.3 | +1.43 | 1.51 | 78 |
| 6 | bags_value | 5 | 10 | 2:1 | mean_reversion | 50.7 | +1.41 | 1.50 | 71 |
| 7 | bags_bluechip | 5 | 9 | 1.8:1 | mean_reversion | 54.5 | +1.38 | 1.52 | 66 |
| 8 | sol_veteran | 8 | 15 | 1.9:1 | mean_reversion | 47.7 | +1.30 | 1.26 | 218 |
| 9 | bags_elite | 5 | 9 | 1.8:1 | mean_reversion | 55.0 | +1.25 | 1.45 | 40 |
| 10 | pump_fresh_tight | 10 | 20 | 2:1 | fresh_pump | 41.1 | +0.91 | 1.14 | 246 |
| 11 | bags_aggressive | 7 | 25 | 3.6:1 | aggressive | 33.3 | +0.74 | 1.14 | 105 |
| 12 | bluechip_trend_follow | 10 | 25 | 2.5:1 | mean_reversion | 34.3 | +0.47 | 1.06 | 1075 |
| 13 | bluechip_breakout | 10 | 25 | 2.5:1 | mean_reversion | 34.3 | +0.47 | 1.06 | 1075 |
| 14 | elite | 10 | 20 | 2:1 | momentum | 39.8 | +0.39 | 1.06 | 246 |
| 15 | micro_cap_surge | 10 | 20 | 2:1 | aggressive | 39.2 | +0.22 | 1.03 | 344 |

### ⚠️ BORDERLINE (6 strategies, PF 0.91–0.97)

| # | Strategy | SL% | TP% | R:R | Entry | WR% | Exp% | PF | Trades | Gap to Breakeven |
|---|----------|-----|-----|-----|-------|-----|------|----|--------|-----------------|
| 16 | established_breakout | 8 | 15 | 1.9:1 | mean_reversion | 40.2 | -0.23 | 0.96 | 1047 | 1.1% WR |
| 17 | momentum | 10 | 25 | 2.5:1 | mean_reversion | 33.1 | -0.27 | 0.97 | 1999 | 0.8% WR |
| 18 | hybrid_b | 10 | 25 | 2.5:1 | mean_reversion | 33.1 | -0.27 | 0.97 | 1999 | 0.8% WR |
| 19 | let_it_ride | 10 | 25 | 2.5:1 | mean_reversion | 32.6 | -0.22 | 0.97 | 1981 | 0.7% WR |
| 20 | volume_spike | 8 | 15 | 1.9:1 | mean_reversion | 37.2 | -0.45 | 0.91 | 1358 | 1.6% WR |
| 21 | bags_momentum | 10 | 30 | 3:1 | momentum | 29.5 | -0.60 | 0.88 | 61 | 2.1% WR |

### ❌ UNPROFITABLE — xstock/index/prestock (5 strategies)

| # | Strategy | SL% | TP% | R:R | Entry | WR% | Exp% | PF | Trades |
|---|----------|-----|-----|-----|-------|-----|------|----|--------|
| 22 | xstock_intraday | 4 | 10 | 2.5:1 | mean_reversion | 32.2 | -0.92 | 0.75 | 3231 |
| 23 | xstock_swing | 4 | 10 | 2.5:1 | mean_reversion | 32.0 | -0.94 | 0.74 | 3047 |
| 24 | prestock_speculative | 4 | 10 | 2.5:1 | mean_reversion | 32.0 | -0.94 | 0.74 | 3301 |
| 25 | index_intraday | 4 | 10 | 2.5:1 | mean_reversion | 32.0 | -0.94 | 0.74 | 3047 |
| 26 | index_leveraged | 4 | 10 | 2.5:1 | mean_reversion | 32.2 | -0.92 | 0.75 | 3231 |

---

## 4. xstock/index/prestock Deep Dive

### What was tested (exhaustive)

| SL% | TP% | R:R | Entry Type | Result |
|-----|-----|-----|------------|--------|
| 10 | 100 | 10:1 | trend_follow | Profitable (v4 sweep) but 100% TP unrealistic |
| 5 | 15 | 3:1 | trend_follow | Losing |
| 5 | 10 | 2:1 | trend_follow | Losing |
| 3 | 10 | 3.3:1 | mean_reversion | Losing (WR 28.7%) |
| 3 | 10 | 3.3:1 | dip_buy | Losing |
| 4 | 10 | 2.5:1 | mean_reversion | Losing (WR 32.2%) — **best** |
| 4 | 10 | 2.5:1 | pullback_buy | Losing (WR 30.9%) |
| 4 | 10 | 2.5:1 | sma_crossover | Losing (WR 31.1%) |
| 4 | 10 | 2.5:1 | accumulation | Losing (WR 30.7%) |
| 4 | 10 | 2.5:1 | range_breakout | Losing (WR 31.6%) |

### Root cause
These tokenized stock/index instruments on Solana DEXes have too much price noise relative to signal. The best WR achieved was 32.2% with mean_reversion at SL 4%/TP 10%, but breakeven requires ~29% WR at this R:R — and after friction (~1.9%), the math doesn't work. The instruments would need either:
1. **Higher TP (50%+)** — which defeats the purpose of realistic stock TPs
2. **Better data** — more granular candles, longer history, or fundamental filters
3. **External signals** — stock market data (pre-market, earnings) as entry filters

### Recommendation
Disable xstock/index/prestock strategies in live trading until better data or entry filters are available. They are the only strategies that lose money at EVERY realistic TP level.

---

## 5. Key Learnings

### What works
- **TP > SL always** — Math proof: with 1.9% friction, SL > TP needs impossible WR
- **Trailing stops disabled** (99%) — Trail exits at sub-friction levels are hidden losses
- **mean_reversion entry** — Best for established tokens and bluechip crypto
- **fresh_pump / aggressive entries** — Best for memecoin rapid plays
- **SL 5–10% range** — Sweet spot for crypto. Too tight = stopped out, too wide = big losses

### What doesn't work
- **Tighter SL doesn't always help** — Drops WR faster than R:R improves
- **Changing entry type** — R3 and R6 proved alternative entries generate more trades but lower quality
- **Mean reversion on memecoins** — Works for slow dips, fails on fast crashes (catching falling knives)
- **Any realistic TP for tokenized stocks** — DEX price action is too noisy

### Mathematical relationships discovered
- Breakeven WR = SL / (SL + TP) + friction_adjustment
- With 1.9% friction: SL 10/TP 20 → breakeven ~36% WR
- With 1.9% friction: SL 8/TP 15 → breakeven ~40% WR
- With 1.9% friction: SL 4/TP 10 → breakeven ~31% WR

---

## 6. Data Locations

| Data | Location |
|------|----------|
| Candle data (OHLCV) | `backtest-data/data/candles/` |
| Token universe | `backtest-data/data/token_universe.csv` |
| Trade simulation script | `backtest-data/scripts/05_simulate_trades.ts` |
| Report generation script | `backtest-data/scripts/06_generate_reports.ts` |
| Per-strategy results (JSON) | `backtest-data/results/results_{algo_id}.json` |
| Per-strategy results (CSV) | `backtest-data/results/results_{algo_id}.csv` |
| Per-strategy summaries | `backtest-data/results/summary_{algo_id}.json` |
| Master comparison | `backtest-data/results/master_comparison.csv` |
| All trades combined | `backtest-data/results/master_all_trades.csv` (27,686 rows) |
| Data manifest | `backtest-data/results/data_manifest.json` |
| This audit file | `backtest-data/BACKTEST_OPTIMIZATION_AUDIT.md` |

---

## 7. Parameter Change History

### ALGO_EXIT_PARAMS changes by strategy

#### elite (memecoin core)
| Round | SL | TP | Entry | Result |
|-------|----|----|-------|--------|
| v4 sweep | 15 | 75 | momentum | +2.14% |
| R1 | 8 | 15 | momentum | ~breakeven |
| R2–R6 (final) | **10** | **20** | **momentum** | **+0.39%** |

#### micro_cap_surge (memecoin core)
| Round | SL | TP | Entry | Result |
|-------|----|----|-------|--------|
| v4 sweep | 15 | 75 | aggressive | +3.82% |
| R2–R6 (final) | **10** | **20** | **aggressive** | **+0.22%** |

#### pump_fresh_tight (memecoin core)
| Round | SL | TP | Entry | Result |
|-------|----|----|-------|--------|
| v4 sweep | 15 | 75 | fresh_pump | +5.74% |
| R2–R6 (final) | **10** | **20** | **fresh_pump** | **+0.91%** |

#### momentum, hybrid_b, let_it_ride (memecoin wide)
| Round | SL | TP | Entry | Result |
|-------|----|----|-------|--------|
| v4 sweep | 20 | 200 | mean_reversion | +2–3% |
| R2 | 10 | 20 | mean_reversion | -0.65% |
| R4 (final) | **10** | **25** | **mean_reversion** | **-0.27%** (PF 0.97) |
| R5 | 10 | 30 | mean_reversion | -0.25% (WR dropped) |
| R6 | 10 | 20 | momentum/aggressive | -0.69% (much worse) |

#### sol_veteran, utility_swing, meme_classic (established)
| Round | SL | TP | Entry | Result |
|-------|----|----|-------|--------|
| R2–R6 (final) | **8** | **15** | **mean_reversion** | **+1.3 to +2.5%** |

#### established_breakout
| Round | SL | TP | Entry | Result |
|-------|----|----|-------|--------|
| R2 | 8 | 15 | mean_reversion | -0.23% |
| R4 | 7 | 15 | mean_reversion | -0.12% (closest) |
| R5 | 6 | 15 | mean_reversion | -0.19% (worse) |
| Final | **8** | **15** | **mean_reversion** | **-0.23%** (PF 0.96) |

#### volume_spike
| Round | SL | TP | Entry | Result |
|-------|----|----|-------|--------|
| R2 | 10 | 20 | dip_buy | -0.45% |
| R4 | 8 | 15 | mean_reversion | -0.45% |
| R5 | 6 | 15 | mean_reversion | -0.58% (worse) |
| R6 | 10 | 20 | aggressive | -0.55% (worse) |
| Final | **8** | **15** | **mean_reversion** | **-0.45%** (PF 0.91) |

#### bluechip_trend_follow, bluechip_breakout
| Round | SL | TP | Entry | Result |
|-------|----|----|-------|--------|
| R2 | 10 | 20 | mean_reversion | +0.11% |
| R3 | 8 | 20 | breakout | -0.94% (much worse) |
| R4 (final) | **10** | **25** | **mean_reversion** | **+0.47%** |

#### xstock_intraday, xstock_swing, prestock_speculative, index_intraday, index_leveraged
| Round | SL | TP | Entry | Result |
|-------|----|----|-------|--------|
| v4 sweep | 10 | 100 | trend_follow | +1.5–2% |
| R1 | 5 | 15 | trend_follow | losing |
| R2 | 3 | 10 | mean_reversion/dip_buy | -0.69 to -0.92% |
| R3 | 4 | 10 | pullback/sma/accum/range | -1.04 to -1.13% |
| R4 (final) | **4** | **10** | **mean_reversion** | **-0.92 to -0.94%** |

#### All bags strategies — see Section 3 table above for final params.

---

## 8. Entry Type Reference

| Entry Type | Logic | Best For |
|------------|-------|----------|
| `momentum` | Green candle > 2× avg body, close near high, above SMA5 | Memecoin core (elite) |
| `fresh_pump` | 3+ consecutive green candles, each close > previous close | Pump plays (pump_fresh_tight) |
| `aggressive` | Volume > 2× avg, close > SMA5, any candle color | High-vol memecoins (micro_cap_surge) |
| `mean_reversion` | Price < SMA5 × 0.97, green after red (dip bounce) | Established, bluechip, bags |
| `dip_buy` | Price < SMA20 × 0.95, green candle (deeper dip) | bags_dip_buyer |
| `breakout` | Close above 20-candle high on volume | Tested, worse for all strategies |
| `range_breakout` | 10-candle range < 5%, then breakout | Tested, worse for all strategies |
| `pullback_buy` | Price pulls back to SMA20 in uptrend | Tested on xstock, not effective |
| `sma_crossover` | SMA5 crosses above SMA20 | Tested on xstock, not effective |
| `accumulation` | Volume builds up before breakout | Tested on index, not effective |

---

*This audit covers all code changes, parameter adjustments, test results, and data locations from the realistic-TP optimization effort across 6 rounds of testing on 26 strategies.*
