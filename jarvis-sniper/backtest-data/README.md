# Backtest Data Pipeline

Complete backtesting pipeline that pulls qualifying tokens for all 25 trading algorithms, fetches OHLCV candle data, simulates trades, and generates performance reports.

## Directory Structure

```
backtest-data/
├── universe/                          # Phase 1-2 outputs
│   ├── universe_raw.json              # All discovered tokens
│   ├── universe_raw.csv
│   ├── universe_scored.json           # Tokens with computed scores
│   └── universe_scored.csv
├── qualified/                         # Phase 3 outputs
│   ├── qualified_{algo_id}.json       # 5,000 qualifying tokens per algo
│   ├── qualified_{algo_id}.csv
│   └── filter_summary.json
├── candles/                           # Phase 4 outputs
│   ├── {mint}_5m.json                 # 5-minute OHLCV candles
│   ├── {mint}_15m.json                # 15-minute OHLCV candles
│   ├── {mint}_1h.json                 # 1-hour OHLCV candles
│   └── candles_index.json             # Index of available candle data
├── results/                           # Phase 5-6 outputs
│   ├── results_{algo_id}.json         # All simulated trades per algo
│   ├── results_{algo_id}.csv
│   ├── summary_{algo_id}.json         # Aggregate stats per algo
│   ├── master_comparison.csv          # All 25 algos side by side
│   ├── master_all_trades.csv          # Every trade from every algo
│   └── data_manifest.json             # Checksums & metadata
├── cache/                             # API response cache (resumability)
├── scripts/
│   ├── shared/
│   │   ├── types.ts                   # TypeScript type definitions
│   │   └── utils.ts                   # Shared utilities (rate limiter, IO, etc.)
│   ├── 01_discover_universe.ts        # Phase 1: Token discovery
│   ├── 02_score_universe.ts           # Phase 2: Score computation
│   ├── 03_filter_by_algo.ts           # Phase 3: Algo filtering
│   ├── 04_fetch_candles.ts            # Phase 4: OHLCV fetch
│   ├── 05_simulate_trades.ts          # Phase 5: Trade simulation
│   ├── 06_generate_reports.ts         # Phase 6: Report generation
│   └── run_all.ps1                    # Run entire pipeline
├── discovery_progress.json            # Phase 1 resume checkpoint
├── candle_fetch_progress.json         # Phase 4 resume checkpoint
├── pipeline.log                       # Full execution log
└── README.md
```

## Quick Start

```bash
cd jarvis-sniper

# Run the full pipeline (24-48 hours total, mostly Phase 4)
powershell -ExecutionPolicy Bypass -File backtest-data/scripts/run_all.ps1

# CI/cloud runner (deterministic order + run log)
bash backtest-data/scripts/run_pipeline_ci.sh

# Or run phases individually:
npx tsx backtest-data/scripts/01_discover_universe.ts
npx tsx backtest-data/scripts/02_score_universe.ts
npx tsx backtest-data/scripts/03_filter_by_algo.ts
npx tsx backtest-data/scripts/04_fetch_candles.ts
npx tsx backtest-data/scripts/05_simulate_trades.ts
npx tsx backtest-data/scripts/06_generate_reports.ts
npx tsx backtest-data/scripts/07b_consistency_report.ts
npx tsx backtest-data/scripts/08_walkforward_validate.ts
npx tsx backtest-data/scripts/09_generate_recommendations_and_provenance.ts
```

## Scaling / API Key

Set these in `backtest-data/.env` (ignored by git):

- `COINGECKO_API_KEY`: Enables CoinGecko Pro onchain endpoints (higher rate limits).
- `HELIUS_API_KEY`: Enables Helius DAS enrichment (`getAssetBatch`).
- `BIRDEYE_API_KEY`: Enables Birdeye token-list expansion.
- `PUMPFUN_API_KEY`: Optional auth header for Pump.fun feed.
- `GECKO_MAX_PAGES_NEW_POOLS` (default `200`): Pages to pull from GeckoTerminal `new_pools`.
- `GECKO_MAX_PAGES_TOP_POOLS` (default `200`): Pages to pull from GeckoTerminal top pools (24h volume).
- `GECKO_MAX_PAGES_MISC` (default `25`): Pages for additional endpoints (trending, tx-count sorts).
- `BIRDEYE_MAX_PAGES` (default `20`), `PUMPFUN_MAX_PAGES` (default `20`): Source intake expansion.
- `WALKFORWARD_FOLDS` (default `5`), `WALKFORWARD_MIN_VALIDATE_TRADES` (default `10`): Robustness settings.

## Phases

| Phase | Script | Time Estimate | API Calls | Description |
|-------|--------|---------------|-----------|-------------|
| 1 | `01_discover_universe.ts` | 45-90 min | variable | Pull tokens from GeckoTerminal, DexScreener, Jupiter, Birdeye, Pump.fun + Helius enrichment |
| 2 | `02_score_universe.ts` | ~1 min | 0 | Compute local scores (0-100) for all tokens |
| 3 | `03_filter_by_algo.ts` | ~1 min | 0 | Filter through 25 algo criteria, 5000 per algo |
| 4 | `04_fetch_candles.ts` | 24-48 hours | ~90K | Fetch 5m/15m/1h OHLCV candles for all unique mints |
| 5 | `05_simulate_trades.ts` | ~5 min | 0 | Simulate trades with SL/TP/trailing stop rules |
| 6 | `06_generate_reports.ts` | ~1 min | 0 | Generate summaries, comparisons, manifests |
| 7 | `07b_consistency_report.ts` | ~1 min | 0 | Rolling-window consistency and status labeling |
| 8 | `08_walkforward_validate.ts` | ~1 min | 0 | Chronological fold validation (out-of-sample robustness) |
| 9 | `09_generate_recommendations_and_provenance.ts` | ~1 min | 0 | Strict-gate recommendations + provenance artifacts |

## Resumability

Every script saves progress and can be safely interrupted and restarted:
- **Phase 1**: `discovery_progress.json` tracks which API pages have been fetched
- **Phase 4**: `candle_fetch_progress.json` tracks which mints have been fetched
- All API responses are cached to `cache/` directory

## 25 Trading Algorithms

### Memecoin (10)
`pump_fresh_tight`, `micro_cap_surge`, `elite`, `momentum`, `insight_j`, `hybrid_b`, `let_it_ride`, `loose`, `genetic_best`, `genetic_v2`

### Bags.fm (8)
`bags_fresh_snipe`, `bags_momentum`, `bags_value`, `bags_dip_buyer`, `bags_bluechip`, `bags_conservative`, `bags_aggressive`, `bags_elite`

### Blue Chip (3)
`bluechip_mean_revert`, `bluechip_trend_follow`, `bluechip_breakout`

### xStock (3)
`xstock_intraday`, `xstock_swing`, `prestock_speculative`

### Index (2)
`index_intraday`, `index_leveraged`

## Data Sources

- **GeckoTerminal** — New pools, top pools, trending, OHLCV candles (30 req/min)
- **DexScreener** — Token profiles, boosted tokens, pair details (300 req/min)
- **Jupiter Gems** — Graduation feed with scoring data
- **Birdeye** — Solana token list expansion
- **Pump.fun** — Launch feed expansion
- **Helius DAS** — Metadata enrichment for discovered mints

## Re-running Backtests

Once data is collected, Phases 5-6 can be re-run instantly against saved datasets:
```bash
npx tsx backtest-data/scripts/05_simulate_trades.ts
npx tsx backtest-data/scripts/06_generate_reports.ts
```

Modify exit parameters in `05_simulate_trades.ts` to test new SL/TP/trailing stop configurations.
