param(
    [switch]$SkipJs,
    [switch]$SkipPyBroker,
    [switch]$StrictPyBroker
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repoRoot
$strictPyBrokerMode = $StrictPyBroker -or ($env:STRICT_PYBROKER -eq "1")

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$artifactDir = Join-Path $repoRoot "artifacts\backtest_validation\$timestamp"
New-Item -ItemType Directory -Force -Path $artifactDir | Out-Null

Write-Host "Running Python backtest contract tests..."
python -m pytest -q `
  tests/backtesting `
  tests/unit/test_backtester.py `
  tests/unit/test_core_backtester.py `
  tests/backtesting/test_strategy_validator.py
if ($LASTEXITCODE -ne 0) {
    throw "Python backtest validation failed."
}

if (-not $SkipJs) {
    Write-Host "Running jarvis-sniper backtest test suite..."
    Push-Location (Join-Path $repoRoot "jarvis-sniper")
    npm run -s test -- `
      src/__tests__/bags-backtest.test.ts `
      src/__tests__/bags-backtest-api.test.ts `
      src/__tests__/backtest-route-execution-realism.test.ts `
      src/__tests__/backtest-campaign-orchestrator.test.ts `
      src/__tests__/backtest-artifact-integrity.test.ts `
      src/__tests__/rpc-and-backtest-regressions.test.ts `
      src/__tests__/backtest-cost-accounting.test.ts
    $jsExit = $LASTEXITCODE
    Pop-Location

    if ($jsExit -ne 0) {
        throw "jarvis-sniper backtest validation failed."
    }
}

if (-not $SkipPyBroker) {
    Write-Host "Running pybroker comparison harness..."
    python tools/backtesting/pybroker_compare.py --output-root artifacts/backtest_compare
    if ($LASTEXITCODE -ne 0) {
        throw "pybroker comparison harness failed."
    }

    if ($strictPyBrokerMode) {
        Write-Host "Running strict pybroker comparison assertion..."
        python scripts/backtesting/assert_pybroker_comparison.py --artifact-root artifacts/backtest_compare --strict --enforce-parity
        if ($LASTEXITCODE -ne 0) {
            throw "strict pybroker comparison assertion failed."
        }
    } else {
        Write-Host "Running warning-mode pybroker comparison assertion..."
        python scripts/backtesting/assert_pybroker_comparison.py --artifact-root artifacts/backtest_compare
    }
}

Write-Host "Backtest validation complete. Artifacts dir: $artifactDir"
