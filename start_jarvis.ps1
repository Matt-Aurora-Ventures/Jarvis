# JARVIS Quick Start - PowerShell
# Starts the unified JARVIS daemon with all components

Write-Host "=======================================" -ForegroundColor Cyan
Write-Host "  JARVIS - Your Personal AI Assistant" -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host ""

# Check Python
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Python: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Python not found. Please install Python 3.9+" -ForegroundColor Red
    exit 1
}

# Change to script directory
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $scriptPath

# Check for virtual environment
if (Test-Path "venv\Scripts\Activate.ps1") {
    Write-Host "Activating virtual environment..." -ForegroundColor Yellow
    & .\venv\Scripts\Activate.ps1
}

# Parse arguments
$daemonArgs = @()

if ($args -contains "--headless" -or $args -contains "--no-tray") {
    $daemonArgs += "--no-tray"
    Write-Host "Mode: Headless (no system tray)" -ForegroundColor Yellow
} else {
    Write-Host "Mode: Full (with system tray)" -ForegroundColor Yellow
}

if ($args -contains "--debug") {
    $daemonArgs += "--debug"
    Write-Host "Debug: Enabled" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Starting JARVIS daemon..." -ForegroundColor Cyan
Write-Host ""

# Start JARVIS
python jarvis_daemon.py @daemonArgs
