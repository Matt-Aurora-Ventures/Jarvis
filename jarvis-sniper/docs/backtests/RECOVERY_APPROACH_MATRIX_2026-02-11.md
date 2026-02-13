# Backtest Recovery Approach Matrix (2026-02-11)

## Goal
Reach stable, real-data-only large-scale backtesting without orchestration hangs.

## Approach A: API-Orchestrated Campaign (`scripts/run-gsd-orchestrated-backtests.ps1`)
- Status: **Partially fixed / in progress**
- What worked:
  - End-to-end preflight/smoke runs are now executing.
  - Current fresh campaign running: `gsd-5000-fresh2-20260211-080940`.
- Root failures found and fixed:
  1. **PowerShell resume crash**
     - Error: `ConvertFrom-Json : ... parameter name 'AsHashtable'`
     - Cause: script used `-AsHashtable` unsupported in Windows PowerShell 5.
     - Fix: added PS5-compatible JSON loader + deep hashtable converter.
  2. **False stall detection**
     - Error: repeated `No progress change for 180s` while run was still active.
     - Cause: run progress stays `0` until chunk completion in current API status model.
     - Fix: stall logic now keys on status endpoint reachability (not progress deltas).
  3. **Brittle preflight**
     - Error: startup abort on transient `(422) Unprocessable Entity` / `(404) Not Found`.
     - Cause: preflight depended on external real-data probe every startup.
     - Fix: deterministic local-candle health probe first, then fallback probes.
- Evidence:
  - Campaign log: `.jarvis-cache/backtest-campaign/gsd-5000-fresh2-20260211-080940/campaign.log`
  - State: `.jarvis-cache/backtest-campaign/gsd-5000-fresh2-20260211-080940/campaign-state.json`

## Approach B: Hyperliquid Direct Tuning (`scripts/hyperliquid-tune.ts`)
- Status: **Succeeded (fast), below 5000-trade threshold**
- Run 1:
  - Command: `npx tsx scripts/hyperliquid-tune.ts --strategy hl_momentum --interval 15m --days1 14 --days2 90 --top 30 --stage1-min-trades 300 --stage2-min-trades 5000`
  - Output: `trades=2215`, `datasets=6`
  - Artifacts: `.jarvis-cache/backtest-runs/hl-tune-hl_momentum-mli35h4h-25shszbs/`
- Run 2:
  - Command: `npx tsx scripts/hyperliquid-tune.ts --strategy hl_momentum --interval 5m --days1 14 --days2 90 --top 40 --stage1-min-trades 500 --stage2-min-trades 5000`
  - Output: `trades=1442`, `datasets=6`
  - Artifacts: `.jarvis-cache/backtest-runs/hl-tune-hl_momentum-mli3ksck-4opnw18i/`
- Limitation observed:
  - Trade threshold not met because only 6 assets yielded sufficient candle datasets in stage2 window.

## Approach C: Large Multi-Source Scorer (`scripts/backtest-scorer.ts --quick`)
- Status: **Succeeded technically, rejected as final truth source**
- Output summary:
  - `112` tokens, `92` configs, `203` API calls.
  - Generated `BACKTEST_RESULTS.md` and `scripts/.backtest-results.json`.
- Why rejected as final promotion source:
  - Many top configs had very low decided-trade counts and `PF = Infinity` artifacts.
  - Not a one-to-one mapping with the 26 production strategy families and 5000-trade gate.

## Current Decision
Use **Approach A** as canonical campaign path (real-data production strategy mapping) with fixes applied, and use **Approach B** as acceleration lane for TradFi-style signal tuning.

## Next Actions
1. Let `gsd-5000-fresh2-20260211-080940` continue through baseline/expansion.
2. If any family remains under 5000 trades, run targeted expansion passes with higher token caps and family-specific batching.
3. Keep Hyperliquid lane for rapid parameter narrowing, then validate promoted params through canonical API campaign artifacts.
