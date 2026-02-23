param(
  [switch]$Prototype
)

Set-Location $PSScriptRoot
if (-not $Prototype) {
  Write-Host "[BLOCKED] Prototype surface is frozen by policy." -ForegroundColor Yellow
  Write-Host "Use START_TRADING.bat to run canonical jarvis-sniper." -ForegroundColor Yellow
  Write-Host "To explicitly run this prototype, execute: .\\start_trading_ui.ps1 -Prototype" -ForegroundColor Yellow
  exit 1
}

Write-Host "[WARNING] Running prototype Flask UI (non-canonical)." -ForegroundColor Yellow
Write-Host "[WARNING] Do not use this surface for production/live operations." -ForegroundColor Yellow

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
  Write-Host "[ERROR] Python not found in PATH. Install Python 3.11+." -ForegroundColor Red
  exit 1
}

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

New-Item -ItemType Directory -Force -Path (Join-Path $PSScriptRoot "logs") | Out-Null
$logPath = Join-Path $PSScriptRoot "logs\trading_web.log"

Write-Host "Starting Jarvis Trading UI on http://127.0.0.1:5001" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host "Writing runtime log to $logPath" -ForegroundColor DarkGray

& python web/trading_web.py *> $logPath
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
  Write-Host "[ERROR] Trading UI exited with code $exitCode. Check $logPath." -ForegroundColor Red
}
exit $exitCode
