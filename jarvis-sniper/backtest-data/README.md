# Backtest Data Pipeline

Complete backtesting pipeline that pulls qualifying tokens for all 26 trading algorithms, fetches OHLCV candle data, simulates trades, and generates performance reports.

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
│   ├── master_comparison.csv          # All 26 algos side by side
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
│   ├── 05f_volume_gate_sweep.ts       # Phase 5f: Volume gate optimization
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

# Or run phases individually:
npx tsx backtest-data/scripts/01_discover_universe.ts
npx tsx backtest-data/scripts/02_score_universe.ts
npx tsx backtest-data/scripts/03_filter_by_algo.ts
npx tsx backtest-data/scripts/04_fetch_candles.ts
npx tsx backtest-data/scripts/05_simulate_trades.ts
npx tsx backtest-data/scripts/06_generate_reports.ts
npx tsx backtest-data/scripts/05f_volume_gate_sweep.ts
```

If `tsx` install is blocked in your environment, use local `vite-node`:
```bash
./node_modules/.bin/vite-node backtest-data/scripts/01_discover_universe.ts
./node_modules/.bin/vite-node backtest-data/scripts/02_score_universe.ts
./node_modules/.bin/vite-node backtest-data/scripts/03_filter_by_algo.ts
./node_modules/.bin/vite-node backtest-data/scripts/04_fetch_candles.ts
./node_modules/.bin/vite-node backtest-data/scripts/05_simulate_trades.ts
./node_modules/.bin/vite-node backtest-data/scripts/06_generate_reports.ts
./node_modules/.bin/vite-node backtest-data/scripts/05f_volume_gate_sweep.ts
```

## Scaling / API Key

Set these in `backtest-data/.env` (ignored by git):

- `COINGECKO_API_KEY`: Enables CoinGecko Pro onchain endpoints (higher rate limits).
- `GECKO_MAX_PAGES_NEW_POOLS` (default `200`): Pages to pull from GeckoTerminal `new_pools`.
- `GECKO_MAX_PAGES_TOP_POOLS` (default `200`): Pages to pull from GeckoTerminal top pools (24h volume).
- `GECKO_MAX_PAGES_MISC` (default `10`): Pages for additional endpoints (trending, tx-count sorts).
- `BIRDEYE_API_KEY` (optional): Enables Birdeye token-list and trending ingestion.
- `BIRDEYE_MAX_PAGES` (default `25`): Number of Birdeye token-list pages.
- `BIRDEYE_PAGE_LIMIT` (default `50`): Birdeye page size.

## Phases

| Phase | Script | Time Estimate | API Calls | Description |
|-------|--------|---------------|-----------|-------------|
| 1 | `01_discover_universe.ts` | 30-60 min | ~200 | Pull 50K+ tokens from GeckoTerminal, DexScreener, Jupiter |
| 2 | `02_score_universe.ts` | ~1 min | 0 | Compute local scores (0-100) for all tokens |
| 3 | `03_filter_by_algo.ts` | ~1 min | 0 | Filter through 26 algo criteria, 5000 per algo |
| 4 | `04_fetch_candles.ts` | 24-48 hours | ~90K | Fetch 5m/15m/1h OHLCV candles for all unique mints |
| 5 | `05_simulate_trades.ts` | ~5 min | 0 | Simulate trades with SL/TP/trailing stop rules |
| 6 | `06_generate_reports.ts` | ~1 min | 0 | Generate summaries, comparisons, manifests |

## Resumability

Every script saves progress and can be safely interrupted and restarted:
- **Phase 1**: `discovery_progress.json` tracks which API pages have been fetched
- **Phase 4**: `candle_fetch_progress.json` tracks which mints have been fetched
- All API responses are cached to `cache/` directory

## 26 Trading Algorithms

### Memecoin (6)
`pump_fresh_tight`, `micro_cap_surge`, `elite`, `momentum`, `hybrid_b`, `let_it_ride`

### Bags.fm (8)
`bags_fresh_snipe`, `bags_momentum`, `bags_value`, `bags_dip_buyer`, `bags_bluechip`, `bags_conservative`, `bags_aggressive`, `bags_elite`

### Established + Blue Chip (7)
`sol_veteran`, `utility_swing`, `established_breakout`, `meme_classic`, `volume_spike`, `bluechip_trend_follow`, `bluechip_breakout`

### xStock (3)
`xstock_intraday`, `xstock_swing`, `prestock_speculative`

### Index (2)
`index_intraday`, `index_leveraged`

## Data Sources

- **GeckoTerminal** — New pools, top pools, trending, OHLCV candles (30 req/min)
- **DexScreener** — Token profiles, boosted tokens, pair details (300 req/min)
- **Jupiter Gems** — Graduation feed with scoring data
- **Birdeye** (optional API key) — Token list + trending feed for additional lead discovery

## Re-running Backtests

Once data is collected, Phases 5-6 can be re-run instantly against saved datasets:
```bash
npx tsx backtest-data/scripts/05_simulate_trades.ts
npx tsx backtest-data/scripts/06_generate_reports.ts
```

Modify exit parameters in `05_simulate_trades.ts` to test new SL/TP/trailing stop configurations.
