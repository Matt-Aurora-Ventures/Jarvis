# Backtest Baseline Snapshot (2026-02-20)

## Scope
Baseline captured before backtesting reliability fixes and pybroker benchmark harness integration.

## Pre-fix Observations
1. Python backtesting command:
   - `pytest -q tests/backtesting tests/unit/test_backtester.py tests/unit/test_core_backtester.py`
   - Result: `204 passed, 2 failed` (out of `206`)
2. Failing tests:
   - `tests/unit/test_core_backtester.py::TestIndicators::test_ema_insufficient_data`
   - `tests/unit/test_core_backtester.py::TestIndicators::test_rsi_returns_50_insufficient_data`
3. Root cause evidence:
   - `core/backtester.py:541` used fixed lookback via `self.close(i)` and included out-of-range zeros.
   - `core/backtester.py:555` used fixed lookback via `self.close(i)` and included out-of-range zeros.
4. Capital accounting defect:
   - `core/backtester.py:433` used `self._capital += value - fee + pnl`, double-counting realized PnL.
5. Statistical validation defect:
   - `core/trading/backtesting/validator.py:204` shuffled returns and recomputed Sharpe.
   - Since Sharpe is order-invariant on the same set of returns, p-values collapsed to non-informative outputs.
6. TS cost model inconsistency:
   - `jarvis-sniper/src/lib/backtest-engine.ts:526` subtracted `slippagePct` from net PnL despite slippage already applied in entry/exit prices.

## Test Surface Snapshot
1. Backtest-focused test LOC sampled: `4398`
2. Core backtesting implementation LOC sampled: `3754`
3. `jarvis-sniper` backtest suite snapshot at baseline:
   - `37/37` passed on targeted cluster.

## Post-fix Target
1. Python backtesting suites: all green.
2. Statistical validation p-values: non-degenerate and deterministic with seed control.
3. Legacy and advanced engine accounting parity on canonical fixture.
4. TS backtest cost model consistent with explicit cost components.
