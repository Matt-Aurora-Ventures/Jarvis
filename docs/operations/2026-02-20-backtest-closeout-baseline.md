# Backtest Closeout Baseline - 2026-02-20

## Command Baseline

1. `powershell -ExecutionPolicy Bypass -File scripts/backtesting/run_backtest_validation.ps1`
2. `python tools/backtesting/pybroker_compare.py --output-root artifacts/backtest_compare`

## Result Snapshot

1. Python contract tests: `170 passed`
2. Sniper backtest suite: `39 passed`
3. PyBroker comparison artifact generated:
   - `artifacts/backtest_compare/20260220T211242Z/comparison.json`

## Known Pending Benchmark Gap

From `artifacts/backtest_compare/20260220T211242Z/comparison.json`:

1. `pybroker.available = true`
2. `pybroker.status = "pending"`
3. all scenario comparisons are `status = "skipped"` with reason:
   - `pybroker scenario unavailable (status=pending)`

## Known Equity/Drawdown Anomaly Reproduction

Reproduction command:

```bash
python -c "from core.backtesting.backtest_engine import AdvancedBacktestEngine, BacktestConfig; import tempfile; from pathlib import Path; candles=[{'timestamp':'2024-01-01T00:00:00Z','open':100,'high':101,'low':99,'close':100,'volume':1000},{'timestamp':'2024-01-01T01:00:00Z','open':100,'high':101,'low':99,'close':100,'volume':1000}];
with tempfile.TemporaryDirectory() as d:
 e=AdvancedBacktestEngine(results_dir=Path(d)); e.load_data('T', candles); cfg=BacktestConfig(symbol='T', start_date='2024-01-01', end_date='2024-01-02', initial_capital=10000, fee_rate=0, slippage_bps=0,max_position_size=1.0,allow_short=False);
 def strat(engine,c):
  if engine._current_idx==0 and engine.is_flat(): engine.buy(1.0,'enter')
  elif engine._current_idx==1 and engine.is_long(): engine.close_position('exit')
 r=e.run(strat,cfg); print('equity_curve', r.equity_curve); print('final_capital',r.final_capital,'maxdd',r.metrics.max_drawdown)"
```

Observed output:

1. `equity_curve` drops to `0.0` during flat-price long hold.
2. `final_capital = 10000.0`
3. `maxdd = 100.0`

This confirms the long equity tracking bug for the baseline.
