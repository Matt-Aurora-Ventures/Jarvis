# Backtest Data Pipeline - Run All Phases
# Usage: powershell -ExecutionPolicy Bypass -File backtest-data/scripts/run_all.ps1
# Or run individual phases: npx tsx backtest-data/scripts/01_discover_universe.ts

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  BACKTEST DATA PIPELINE" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

function Run-Phase {
    param([string]$Phase, [string]$Script, [string]$Description)
    Write-Host ""
    Write-Host "--- Phase $Phase`: $Description ---" -ForegroundColor Yellow
    $startTime = Get-Date
    npx tsx "backtest-data/scripts/$Script"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAILED: Phase $Phase ($Script) exited with code $LASTEXITCODE" -ForegroundColor Red
        exit $LASTEXITCODE
    }
    $elapsed = (Get-Date) - $startTime
    Write-Host "Phase $Phase completed in $($elapsed.ToString('hh\:mm\:ss'))" -ForegroundColor Green
}

Set-Location $root

# Phase 1: Discover token universe (API-heavy, ~30-60 min)
Run-Phase "1" "01_discover_universe.ts" "Token Universe Discovery"

# Phase 2: Score all tokens (CPU only, ~1 min)
Run-Phase "2" "02_score_universe.ts" "Score Universe"

# Phase 3: Filter through 25 algos (CPU only, ~1 min)
Run-Phase "3" "03_filter_by_algo.ts" "Filter by Algo"

# Phase 4: Fetch OHLCV candles (API-heavy, ~24-48 hours)
# This is the longest phase. It's resumable - safe to interrupt and restart.
Run-Phase "4" "04_fetch_candles.ts" "Fetch OHLCV Candles"

# Phase 5: Simulate trades (CPU only, ~5-10 min)
Run-Phase "5" "05_simulate_trades.ts" "Trade Simulation"

# Phase 6: Generate reports (CPU only, ~1 min)
Run-Phase "6" "06_generate_reports.ts" "Generate Reports"

# Phase 7b: Consistency report (CPU only, ~1 min)
Run-Phase "7b" "07b_consistency_report.ts" "Consistency Report"

# Phase 8: Walk-forward validation (CPU only, ~1 min)
Run-Phase "8" "08_walkforward_validate.ts" "Walk-Forward Validation"

# Optional sweeps
Run-Phase "8e" "05e_equity_sweep.ts" "Equity Sweep"
Run-Phase "8g" "07_gate_sweep.ts" "Gate Sweep"
if (Test-Path "backtest-data/scripts/05f_volume_gate_sweep.ts") {
    Run-Phase "8f" "05f_volume_gate_sweep.ts" "Volume Gate Sweep"
}

# Phase 9: Recommendations + provenance
Run-Phase "9" "09_generate_recommendations_and_provenance.ts" "Recommendations + Provenance"

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  PIPELINE COMPLETE" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "Results: backtest-data/results/" -ForegroundColor Cyan
Write-Host "Reports: backtest-data/results/master_comparison.csv" -ForegroundColor Cyan
Write-Host "Recommendations: backtest-data/results/strategy_recommendations.md" -ForegroundColor Cyan
