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

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  PIPELINE COMPLETE" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "Results: backtest-data/results/" -ForegroundColor Cyan
Write-Host "Reports: backtest-data/results/master_comparison.csv" -ForegroundColor Cyan
