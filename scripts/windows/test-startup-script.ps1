# Test Jarvis Supervisor Startup Script (Dry Run)
# This script tests the startup logic without actually starting the supervisor

$ErrorActionPreference = "Stop"

# Configuration
$ProjectRoot = "C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis"
$PythonExe = "C:\Users\lucid\AppData\Local\Programs\Python\Python312\python.exe"
$SupervisorScript = "$ProjectRoot\bots\supervisor.py"
$LockFile = "$ProjectRoot\.supervisor.lock"
$LogDir = "$ProjectRoot\logs"

Write-Host "=== Jarvis Supervisor Startup Test ===" -ForegroundColor Cyan
Write-Host ""

# Check 1: Python executable
Write-Host "[1/6] Checking Python executable..." -ForegroundColor Yellow
if (Test-Path $PythonExe) {
    $pythonVersion = & $PythonExe --version
    Write-Host "  PASS: Python found - $pythonVersion" -ForegroundColor Green
} else {
    Write-Host "  FAIL: Python not found at $PythonExe" -ForegroundColor Red
    exit 1
}

# Check 2: Supervisor script
Write-Host "[2/6] Checking supervisor script..." -ForegroundColor Yellow
if (Test-Path $SupervisorScript) {
    Write-Host "  PASS: Supervisor script found" -ForegroundColor Green
} else {
    Write-Host "  FAIL: Supervisor script not found at $SupervisorScript" -ForegroundColor Red
    exit 1
}

# Check 3: Working directory
Write-Host "[3/6] Checking project directory..." -ForegroundColor Yellow
if (Test-Path $ProjectRoot) {
    Write-Host "  PASS: Project directory exists" -ForegroundColor Green
} else {
    Write-Host "  FAIL: Project directory not found at $ProjectRoot" -ForegroundColor Red
    exit 1
}

# Check 4: Lock file status
Write-Host "[4/6] Checking lock file..." -ForegroundColor Yellow
if (Test-Path $LockFile) {
    try {
        $lockContent = Get-Content $LockFile -Raw | ConvertFrom-Json
        $pid = $lockContent.pid
        $process = Get-Process -Id $pid -ErrorAction SilentlyContinue

        if ($process) {
            Write-Host "  WARNING: Supervisor already running (PID: $pid)" -ForegroundColor Yellow
            Write-Host "  The startup script would exit without starting a new instance." -ForegroundColor Yellow
        } else {
            Write-Host "  INFO: Stale lock file found (PID: $pid not running)" -ForegroundColor Cyan
            Write-Host "  The startup script would clean up and proceed." -ForegroundColor Cyan
        }
    } catch {
        Write-Host "  WARNING: Lock file exists but cannot be read" -ForegroundColor Yellow
    }
} else {
    Write-Host "  PASS: No lock file found (clean state)" -ForegroundColor Green
}

# Check 5: Process check
Write-Host "[5/6] Checking for running supervisor process..." -ForegroundColor Yellow
$existingProcess = Get-Process -Name "python" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*supervisor.py*" } |
    Select-Object -First 1

if ($existingProcess) {
    Write-Host "  WARNING: Supervisor process found (PID: $($existingProcess.Id))" -ForegroundColor Yellow
    Write-Host "  The startup script would exit without starting a new instance." -ForegroundColor Yellow
} else {
    Write-Host "  PASS: No supervisor process running" -ForegroundColor Green
}

# Check 6: Network connectivity
Write-Host "[6/6] Checking network connectivity..." -ForegroundColor Yellow
try {
    $ping = Test-Connection -ComputerName 8.8.8.8 -Count 1 -Quiet -ErrorAction SilentlyContinue
    if ($ping) {
        Write-Host "  PASS: Network is reachable" -ForegroundColor Green
    } else {
        Write-Host "  WARNING: Network may not be ready" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  WARNING: Network check failed" -ForegroundColor Yellow
}

# Summary
Write-Host ""
Write-Host "=== Test Summary ===" -ForegroundColor Cyan
Write-Host "All critical checks passed." -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. To install the scheduled task (requires admin):" -ForegroundColor White
Write-Host "     .\install-startup-task.ps1" -ForegroundColor Cyan
Write-Host ""
Write-Host "  2. To test manual startup (does NOT require admin):" -ForegroundColor White
Write-Host "     .\start-jarvis-supervisor.ps1" -ForegroundColor Cyan
Write-Host ""
Write-Host "  3. To check logs after startup:" -ForegroundColor White
Write-Host "     notepad $LogDir\supervisor-startup.log" -ForegroundColor Cyan
