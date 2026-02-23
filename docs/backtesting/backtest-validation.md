# Backtest Validation Contract

## Entrypoints

- `scripts/backtesting/run_backtest_validation.ps1`
- `scripts/backtesting/validate_backtest_contract.py`

## Modes

- `Warning mode` (default): command failures are recorded as warnings and artifacts are still emitted.
- `Strict mode`: any contract or command failure returns non-zero exit and should fail CI for main/nightly gates.

Run examples:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/backtesting/run_backtest_validation.ps1
powershell -ExecutionPolicy Bypass -File scripts/backtesting/run_backtest_validation.ps1 -Strict
```

## Artifacts

- `artifacts/backtest_validation/contract_validation_<timestamp>.json`
- `artifacts/backtest_validation/run_summary_<timestamp>.json`
- `artifacts/backtest_compare/latest.json`
- `artifacts/backtest_compare/latest_run.json`

## Pass/Fail Interpretation

- `contract_validation*.json`:
  - `overall_ok=true` means command contract and script governance checks passed.
  - `overall_ok=false` means the test command contract drifted or governance checks failed.
- `run_summary*.json`:
  - `overall_status=pass` means all validation commands completed with `exit_code=0`.
  - `overall_status=warn` means one or more commands failed in warning mode.
- In strict mode:
  - Any failed contract check or command should be treated as release-blocking for main/nightly.
