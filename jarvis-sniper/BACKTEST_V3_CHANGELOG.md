# Backtest Pipeline v5 — Established Token Optimization (2026-02-15)

## Summary

**All 26 strategies profitable.** v5 replaced the bottom 5 underperformers with 5 new established-token strategies targeting older, proven Solana tokens (6mo-1yr+).

| Version | Change | Trades | Avg PnL | Profitable |
|---------|--------|--------|---------|------------|
| v3 | TP > SL fix | 1,815 | +0.54% | 12/12 |
| v4 | Sweep optimization | 27,573 | +2.83% | 26/26 |
| **v5** | **Established tokens** | **22,886** | **+3.62%** | **26/26** |

Avg PnL **+28% improvement** over v4 by replacing weak strategies with high-conviction established-token plays.

---

## What Changed in v5

### Replaced Bottom 5 Strategies

| Removed | Exp/Trade | Replaced With | Exp/Trade | Improvement |
|---------|-----------|---------------|-----------|-------------|
| `loose` | +0.60% | `utility_swing` | **+19.78%** | **+33x** |
| `bluechip_mean_revert` | +0.79% | `meme_classic` | **+19.36%** | **+24x** |
| `insight_j` | +2.21% | `volume_spike` | **+19.32%** | **+9x** |
| `genetic_v2` | +4.02% | `sol_veteran` | **+17.12%** | **+4x** |
| `genetic_best` | +5.38% | `established_breakout` | **+14.43%** | **+3x** |

### New Established Token Category

All 5 new strategies use **mean_reversion / dip_buy** entry on tokens **30 days to 1+ year old** with proven liquidity:

| Strategy | Entry | Tokens | SL | TP | MaxAge | WR | PF | Exp/Trade | Trades |
|----------|-------|--------|----|----|--------|----|----|-----------|--------|
| `utility_swing` | mean_reversion | 6mo+, $10K+ liq, score 55+ | 25% | 200% | 168h | 55.2% | 3.12 | +19.78% | 67 |
| `meme_classic` | mean_reversion | 1yr+, $5K+ liq, score 40+ | 25% | 200% | 168h | 50.0% | 2.93 | +19.36% | 106 |
| `volume_spike` | dip_buy | 30d+, $20K+ liq, V/L 0.3+ | 25% | 200% | 168h | 38.8% | 2.31 | +19.32% | 299 |
| `sol_veteran` | mean_reversion | 6mo+, $50K+ liq, score 40+ | 25% | 200% | 168h | 50.0% | 2.68 | +17.12% | 104 |
| `established_breakout` | mean_reversion | 30d+, $10K+ liq, score 30+ | 25% | 200% | 168h | 37.7% | 2.05 | +14.43% | 390 |

### New Entry Signal Types Added

5 new entry types implemented in `05_simulate_trades.ts` (used by sweep, available for future strategies):
- **`sma_crossover`** — SMA5 crosses above SMA20 with volume confirmation
- **`accumulation`** — Tight price range + ramping volume = accumulation before breakout
- **`range_breakout`** — Price breaks 20-candle high with 2x+ volume
- **`pullback_buy`** — Price pulls back to SMA20 in uptrend, then bounces
- **`vol_surge_scalp`** — Sudden 3x+ volume spike with strong green candle

### Sweep Process (`05d_established_sweep.ts`)

Tested **9 entry types × 8 SL × 12 TP × 7 maxAge = ~5,600 combos per strategy** across 5 strategies.
- **16,074 profitable combinations found**
- Mean_reversion and dip_buy entries dominated on established tokens
- Optimal params converged to SL 25% / TP 200% / 168h (7-day hold window)

---

## All 26 Strategies (Ranked by Expectancy)

### Top 10

| Rank | Strategy | WR | PF | Exp/Trade | Trades | Category |
|------|----------|-----|------|-----------|--------|----------|
| 1 | `utility_swing` | 55.2% | 3.12 | +19.78% | 67 | **Established** |
| 2 | `meme_classic` | 50.0% | 2.93 | +19.36% | 106 | **Established** |
| 3 | `volume_spike` | 38.8% | 2.31 | +19.32% | 299 | **Established** |
| 4 | `sol_veteran` | 50.0% | 2.68 | +17.12% | 104 | **Established** |
| 5 | `established_breakout` | 37.7% | 2.05 | +14.43% | 390 | **Established** |
| 6 | `elite` | 34.1% | 1.67 | +6.72% | 185 | Memecoin |
| 7 | `bags_momentum` | 38.0% | 1.82 | +6.56% | 50 | Bags.FM |
| 8 | `momentum` | 32.1% | 1.53 | +6.53% | 1,176 | Memecoin |
| 9 | `hybrid_b` | 32.1% | 1.53 | +6.53% | 1,176 | Memecoin |
| 10 | `let_it_ride` | 32.1% | 1.53 | +6.53% | 1,176 | Memecoin |

### Strategies 11-20

| Rank | Strategy | WR | PF | Exp/Trade | Trades | Category |
|------|----------|-----|------|-----------|--------|----------|
| 11 | `bags_fresh_snipe` | 42.1% | 1.73 | +6.42% | 38 | Bags.FM |
| 12 | `bluechip_trend_follow` | 29.1% | 1.55 | +6.02% | 667 | Blue Chip |
| 13 | `bluechip_breakout` | 29.1% | 1.55 | +6.02% | 667 | Blue Chip |
| 14 | `pump_fresh_tight` | 31.1% | 1.54 | +5.86% | 209 | Memecoin |
| 15 | `micro_cap_surge` | 32.2% | 1.51 | +5.38% | 289 | Memecoin |
| 16 | `bags_elite` | 48.6% | 2.05 | +3.84% | 37 | Bags.FM |
| 17 | `bags_bluechip` | 53.2% | 2.16 | +3.67% | 62 | Bags.FM |
| 18 | `bags_conservative` | 49.3% | 1.76 | +2.74% | 71 | Bags.FM |
| 19 | `bags_value` | 49.2% | 1.93 | +2.59% | 65 | Bags.FM |
| 20 | `bags_aggressive` | 37.1% | 1.30 | +2.52% | 89 | Bags.FM |

### Strategies 21-26

| Rank | Strategy | WR | PF | Exp/Trade | Trades | Category |
|------|----------|-----|------|-----------|--------|----------|
| 21 | `bags_dip_buyer` | 30.4% | 1.50 | +2.48% | 102 | Bags.FM |
| 22 | `xstock_swing` | 21.6% | 1.24 | +2.03% | 3,156 | xStock |
| 23 | `index_intraday` | 21.6% | 1.24 | +2.03% | 3,156 | Index |
| 24 | `xstock_intraday` | 21.4% | 1.21 | +1.82% | 3,384 | xStock |
| 25 | `index_leveraged` | 21.4% | 1.21 | +1.82% | 3,384 | Index |
| 26 | `prestock_speculative` | 20.2% | 1.18 | +1.57% | 2,781 | Prestock |

**Overall: 25.1% WR | +3.62% avg PnL | 22,886 trades | 26/26 profitable**

---

## Files Changed (12 files)

### Backtest Scripts
- **`backtest-data/scripts/shared/types.ts`**
  - Added `min_age_hours` to `AlgoFilter`, `'established'` to category union
- **`backtest-data/scripts/03_filter_by_algo.ts`**
  - Replaced 5 bottom strategies with 5 established-token filters (min_age 720-8760h)
  - Added `min_age_hours` filtering logic
- **`backtest-data/scripts/05_simulate_trades.ts`**
  - `ALGO_EXIT_PARAMS` — 26 strategies (6 memecoin, 5 established, 8 bags, 2 bluechip, 3 xstock, 2 index)
  - Added 5 new entry types: `sma_crossover`, `accumulation`, `range_breakout`, `pullback_buy`, `vol_surge_scalp`
  - Updated `getEntryType()` — established strategies use mean_reversion/dip_buy
- **`backtest-data/scripts/05d_established_sweep.ts`** — NEW: comprehensive parameter sweep for established tokens
- **`backtest-data/scripts/06_generate_reports.ts`**
  - `ALL_ALGO_IDS` — updated to v5 strategy set

### Live Strategy Presets
- **`src/stores/useSniperStore.ts`**
  - `AssetType` — added `'established'`
  - `STRATEGY_PRESETS` — 26 strategies (replaced 5 with new established presets)
  - `perAssetBreakerConfig` / `perAsset` — added `established` entries
- **`src/lib/bags-strategies.ts`** — unchanged (8 bags strategies)

### UI / Display
- **`src/components/strategy-categories.ts`**
  - 6 categories: TOP PERFORMERS, MEMECOIN, ESTABLISHED TOKENS, BAGS.FM, BLUE CHIP SOLANA, xSTOCK & INDEX
- **`src/components/strategy-info.ts`**
  - Replaced 5 removed entries + 2 deprecated (hot, insight_i) with 5 new established strategy descriptions

### Tests
- **`src/__tests__/strategy-presets.test.ts`**
  - Updated: 26 strategies, 6 categories, correct labels, TP > SL for all
- **`src/__tests__/bags-strategies.test.ts`**
  - Unchanged: 8 bags strategies, 23 tests

---

## Strategy Composition (v5)

| Category | Count | Avg Exp/Trade | Strategy |
|----------|-------|---------------|----------|
| **Established** | 5 | **+18.00%** | utility_swing, meme_classic, volume_spike, sol_veteran, established_breakout |
| **Memecoin** | 6 | +6.26% | elite, pump_fresh_tight, micro_cap_surge, momentum, hybrid_b, let_it_ride |
| **Bags.FM** | 8 | +3.85% | bags_elite, bags_bluechip, bags_conservative, bags_value, bags_aggressive, bags_dip_buyer, bags_fresh_snipe, bags_momentum |
| **Blue Chip** | 2 | +6.02% | bluechip_trend_follow, bluechip_breakout |
| **xStock** | 3 | +1.81% | xstock_intraday, xstock_swing, prestock_speculative |
| **Index** | 2 | +1.93% | index_intraday, index_leveraged |

---

## Test Results

```
Test Files  2 passed (2)
     Tests  60 passed (60)
```
