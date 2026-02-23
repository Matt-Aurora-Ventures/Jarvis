# PyBroker Benchmark Harness

## Objective
Provide an external benchmark scaffold so internal backtesting outputs can be compared against a second framework (`pybroker`) without changing production runtime.

## Files
1. `tools/backtesting/pybroker_adapter.py`
2. `tools/backtesting/pybroker_compare.py`
3. `tests/backtesting/test_pybroker_compare.py`

## Scenarios (Internal Baseline)
1. `buy_and_hold`
2. `sma_crossover`
3. `fixed_sl_tp_trend`

## Usage
Run comparison artifact generation:

```bash
python tools/backtesting/pybroker_compare.py --output-root artifacts/backtest_compare --symbol SOL
```

Or via unified script:

```bash
scripts/backtesting/run_backtest_validation.sh
```

PowerShell:

```powershell
scripts/backtesting/run_backtest_validation.ps1
```

## Artifact
Output path:
`artifacts/backtest_compare/<timestamp>/comparison.json`

Contains:
1. internal scenario metrics,
2. pybroker availability/status,
3. per-scenario comparison results.

## Current status
1. Internal scenarios execute end-to-end and produce deterministic artifacts.
2. When `pybroker` runtime is available, benchmark scenarios execute and artifact emits `pybroker.status = "completed"` with per-scenario metrics.
3. When `pybroker` runtime is unavailable, artifact is still generated with `pybroker.status = "skipped"` to keep CI artifacts stable.
4. Comparison assertions support hybrid policy:
   - PR: warning mode (non-blocking)
   - push to `main` + nightly: strict mode (blocking)
5. Strict mode enforces both:
   - execution health (`pybroker.status` not blocked when runtime is available),
   - scenario parity (no `comparisons[*].status == "fail"` beyond tolerance).
6. `fixed_sl_tp_trend` internal benchmark now uses one-bar staged execution to match pybroker delayed fill semantics.

## Optional dependency
Install with:

```bash
pip install ".[backtesting]"
```
