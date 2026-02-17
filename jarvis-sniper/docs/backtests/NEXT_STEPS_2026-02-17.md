# Codex Cloud Backtest Runs: Retrieval Notes + Next Actions (2026-02-17)

## What was fetched

I attempted to fetch recent "online Codex Cloud" backtest data in two ways:

1. External web access/search from this environment (blocked by proxy `403 CONNECT tunnel failed`).
2. Local repository run artifacts under `docs/backtests/` (available and reviewed).

## Most recent available run artifacts in-repo

### `gsd-20260211-003847`
- Stage summary shows:
  - Main Backtest: `ERROR`
  - Bags Backtest: `OK`
- Main backtest payload indicates chunked execution with **23/23 strategy failures**.
- Dominant failure mode: **45s request timeout** per strategy.
- One strategy (`prestock_speculative`) failed with HTTP 500 quickly (~1.31s).
- Bags backtest payload is marked `{ "skipped": true }`.

### `gsd-20260211-003256`
- Stage summary shows:
  - Main Backtest: `ERROR`
  - Bags Backtest: `OK`
- Main backtest request timed out at ~240s.
- Bags backtest returned zero-token/zero-result payload.

## Diagnosis

Across both runs, the main failure is orchestration/API timeout rather than strategy logic quality:

- The 45s timeout in the chunked run is too low for deep strategy batches.
- Timeout behavior appears systemic (all strategies timing out), so this is likely infrastructure/request-budget configuration before model/strategy ranking concerns.
- Secondary issue: occasional server-side 500 for specific strategy paths.

## What to do next

1. **Increase orchestrator request timeout defaults** for main backtests:
   - Move chunk timeout from ~45s to at least 180–300s for cloud calls.
   - Keep per-strategy retry with exponential backoff and jitter.
2. **Run smaller strategy cohorts first** (e.g., 4–6 strategies per batch) and fan out only when stable.
3. **Add explicit timeout telemetry** in run summaries:
   - timeout count, p50/p95 latency, upstream endpoint + status family.
4. **Handle HTTP 500 gracefully**:
   - one automatic retry on 5xx with fresh correlation ID.
5. **Gate "result publication" on minimum successful chunk ratio**:
   - e.g., mark run as degraded if <70% chunks complete.
6. **Re-run a focused smoke suite** after timeout increases:
   - `xstock_swing`, `xstock_intraday`, `volume_spike`, `utility_swing`, `bluechip_breakout`.
7. **Only after orchestration stability**, continue with parameter/gate sweeps.

## Proposed immediate operating plan

- Phase A (stability): 1 run, 5 core strategies, elevated timeouts, strict retry logging.
- Phase B (coverage): 2 runs, expanded strategy set, compare timeout and completion rates.
- Phase C (optimization): equity + volume gate sweeps only if completion ratio remains high.

