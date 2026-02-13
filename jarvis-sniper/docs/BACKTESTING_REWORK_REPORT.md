# Jarvis Sniper Backtesting Rework (Data, Validation, Iteration)

Date: 2026-02-10

This document is a practical blueprint to rebuild Jarvis Sniper strategy validation so it is:

- **Data-backed**: thousands of trades, not dozens.
- **Verifiable**: every trade can be tied to an upstream identifier (Solana signature / exchange trade id).
- **Reproducible**: same inputs produce the same outputs (seeded sims; versioned datasets).
- **Actionable**: strategies get tuned iteratively and promoted/demoted based on out-of-sample results.

## 1) Current State (What’s Broken)

### 1.1 Synthetic data is not acceptable (now removed from Strategy Validation)
**Hard rule:** Strategy Validation must use **zero synthetic data**.

Status as of 2026-02-10:

- `/api/backtest` now runs **memecoin + xStock/index/prestock** strategies using **real OHLCV** (GeckoTerminal pool OHLCV as primary; optional Birdeye fallback when an API key is available).
- `/api/backtest/continuous` now uses **real OHLCV** only (no synthetic candle generation).
- `/api/backtest` can now generate **evidence artifacts** (trade ledger + dataset provenance) and cache them for download:
  - `POST /api/backtest` with `includeEvidence: true` returns `evidence.runId`
  - `GET /api/backtest/evidence?runId=...&format=csv|manifest|report|json`

Remaining gaps are about **evidence** (trade-level ledgers) and **scale** (5,000+ trades), not “synthetic vs real”.

### 1.2 Sample sizes are too small for “truth”
Even when the engine runs many samples, the current validation artifacts are not designed to prove:

- trade timestamps
- trade provenance (where did this trade come from?)
- on-chain id (signature) / exchange id
- consistent slippage/fill assumptions

### 1.3 Strategy metadata is easy to mislead
If you validate a bluechip strategy on multiple tokens, a naive “per-strategy” label can end up reflecting only one token’s result, not the aggregate.

## 2) Goals (Hard Requirements)

1. **Minimum trades**:
   - Each strategy must be tested on **>= 5,000 trades** (aggregate across assets allowed if comparable).
2. **Evidence artifacts per run**:
   - `trades.csv` (or parquet) with `timestamp`, `symbol/mint`, `side`, `entry/exit`, `fees`, `slippage`, and a **verifier id** (signature/trade_id).
   - `summary.json` with metrics.
   - `manifest.json` with dataset hashes + build info.
3. **Out-of-sample validation**:
   - Walk-forward or train/validate splits must be mandatory for any “promoted” strategy.
4. **Multi-source input for the sniper**:
   - Pump-only intake is unacceptable. We must ingest multiple launch venues/pool creations.

## 3) Data Strategy (Real, Cheap, Scalable)

This is the critical piece. Without real data, tuning is just noise.

### 3.1 Track A: Hyperliquid (fast path to 5,000+ clean trades)
Use Hyperliquid historical trade data to:

- validate generic momentum/mean reversion logic on deep markets
- build a robust parameter tuning workflow (TP/SL/trails/hold time)
- establish baseline risk controls

Outputs here can be fully timestamped and verifiable via Hyperliquid trade ids / endpoints.

### 3.2 Track B: Solana (sniper-realistic trade reconstruction)
For sniper strategies, we need **on-chain** verification:

- **Launch discovery**: detect new mints/pool creations across multiple venues.
- **Swap stream**: parse swap transactions to reconstruct trade-level prints.

Preferred approach:

- Use a reliable indexing provider for enriched parsing (e.g. Helius Enhanced Transactions) when available.
- Fallback to Solana RPC parsing (slower) for smaller samples.

Verifier id: `signature` (+ slot / blockTime).

### 3.3 Track C: TradingView / Equities Screener (optional)
For the “xStocks/index” side, TradingView screener data is fine for real-time scoring, but it is not a substitute for historical backtesting unless we also store time-series snapshots.

## 4) Dataset Design (Versioned + Reproducible)

### 4.1 Canonical event schema
Normalize every source into a single format:

- `event_id` (unique)
- `ts` (ms)
- `asset_id` (ticker or mint)
- `price`, `size`
- `side` (buy/sell)
- `fees`, `slippage_model`
- `verifier`:
  - Solana: `signature`, `slot`, `blockTime`
  - Hyperliquid: `trade_id` (or equivalent) + endpoint provenance

### 4.2 Storage
Use a local, append-only store:

- Parquet (recommended) or sqlite for small-scale
- one file per source + time window, plus a manifest index

### 4.3 Determinism
Strategy Validation uses **real data only**. If synthetic data is ever used for UI prototyping, it must be:

- behind a dev-only flag
- clearly labeled synthetic
- never mixed with verified scorecards

## 5) Backtest Engine (What We Must Change)

### 5.1 Move from candle-only to trade/event simulation where needed
OHLCV backtests can hide:

- spread
- MEV/priority effects
- fill failures
- per-tx fees

For sniper strategies, event-level backtesting is the baseline.

### 5.2 Explicit fill model
Every strategy run must declare:

- slippage model (bps + volume impact)
- fee model (LP + priority fee + tip)
- latency model (N seconds or N slots)
- failure rate model (optional)

### 5.3 Evidence export
Every run must export the full trade ledger with timestamps and verifier ids (no exceptions for “real” runs).

## 6) Iterative Tuning Loop (Your “100 -> 200 -> ... -> 5000” Request)

We implement a staged process:

1. **Stage 1: sanity (100-300 trades)**
   - quickly eliminate obviously losing configs
2. **Stage 2: stability (1,000 trades)**
   - tune TP/SL/trailing/hold windows
   - reject configs with unstable PnL variance
3. **Stage 3: promotion (5,000+ trades out-of-sample)**
   - only then mark a strategy as “validated”

We run parameter search in waves:

- random/grid sampling for breadth
- then a focused search around the winners

### 6.1 Implementation (Real Data, Scripted)

Stage 1 + Stage 2 are implemented for Hyperliquid as a repeatable runner:

- Script: `scripts/hyperliquid-tune.ts`
- Output: `.jarvis-cache/backtest-runs/<runId>/{manifest.json,trades.csv,report.md,evidence.json}`

Example (recommended defaults):

```bash
cd jarvis-sniper
npx tsx scripts/hyperliquid-tune.ts --strategy hl_momentum --interval 5m --days1 7 --days2 30
```

Notes:

- **Zero synthetic**: the script uses only Hyperliquid `candleSnapshot` candles.
- Evidence includes **trade-level timestamps** and **dataset hashes** (SHA-256) so results are reproducible.
- If Stage 2 doesn’t reach `--stage2-min-trades` (default: 1000), increase `--coins` and/or `--days2`.

## 7) Product/UI Implications (What Users Should See)

Strategy Validation UI must show:

- sample size (trades)
- data source (“verified” vs “synthetic”)
- last-run timestamp
- ability to download evidence artifacts

If a strategy is unverified or underperforming out-of-sample:

- label it clearly
- disable “live” toggles by default

## 8) Immediate Work Items (Next Implementation Steps)

1. Implement the **evidence artifact export** (trade ledger + manifest) for every run. (DONE for OHLCV backtests)
2. Add a “Download evidence” button to Strategy Validation UI. (DONE: downloads `trades.csv` from `runId`)
3. Implement the **real-data dataset layer** for deep historical backtesting (Hyperliquid first).
4. Implement Solana **launch discovery + swap parsing** so “sniper-realistic” strategies are event-level verifiable.

## 9) Sources (Requested)

- Awesome systematic trading research list:
  - https://github.com/paperswithbacktest/awesome-systematic-trading
- `tvscreener` repo + docs:
  - https://github.com/deepentropy/tvscreener
  - https://deepentropy.github.io/tvscreener/docs/
