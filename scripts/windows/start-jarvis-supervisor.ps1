# Jarvis Supervisor Startup Script
# This script safely starts the Jarvis supervisor daemon with safety checks

$ErrorActionPreference = "Stop"

# Configuration
$ProjectRoot = "C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis"
$PythonExe = "C:\Users\lucid\AppData\Local\Programs\Python\Python312\python.exe"
$SupervisorScript = "bots\supervisor.py"
$LockFile = "$env:TEMP\jarvis_supervisor.lock"
$LogFile = "$ProjectRoot\logs\supervisor-startup.log"

# Ensure logs directory exists
$LogDir = Split-Path $LogFile -Parent
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

# Logging function
function Write-Log {
    param($Message)
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $LogMessage = "$Timestamp - $Message"
    Write-Host $LogMessage
    Add-Content -Path $LogFile -Value $LogMessage
}

Write-Log "=== Jarvis Supervisor Startup ==="

# Global automation pause flag (used to temporarily stop scheduled tasks safely)
if (Test-Path (Join-Path $ProjectRoot "PAUSE_AUTOMATIONS")) {
    Write-Log "Automations paused (PAUSE_AUTOMATIONS exists). Not starting supervisor."
    exit 0
}

# Check if already running via lock file
if (Test-Path $LockFile) {
    $PidContent = Get-Content $LockFile -ErrorAction SilentlyContinue
    if ($PidContent) {
        $Pid = [int]$PidContent
        $Process = Get-Process -Id $Pid -ErrorAction SilentlyContinue
        if ($Process -and $Process.ProcessName -eq "python") {
            Write-Log "Supervisor already running (PID: $Pid). Exiting."
            exit 0
        } else {
            Write-Log "Stale lock file found. Removing..."
            Remove-Item $LockFile -Force
        }
    }
}

# Check if supervisor is already running (by process search)
$ExistingProcess = Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*supervisor.py*"
}
if ($ExistingProcess) {
    Write-Log "Supervisor already running via process search (PID: $($ExistingProcess.Id)). Exiting."
    exit 0
}

# Wait for network connectivity (max 60 seconds)
Write-Log "Checking network connectivity..."
$MaxWait = 60
$Waited = 0
while ($Waited -lt $MaxWait) {
    $NetworkReady = Test-Connection -ComputerName "8.8.8.8" -Count 1 -Quiet -ErrorAction SilentlyContinue
    if ($NetworkReady) {
        Write-Log "Network is ready."
        break
    }
    Start-Sleep -Seconds 5
    $Waited += 5
    Write-Log "Waiting for network... ($Waited/$MaxWait seconds)"
}

if ($Waited -ge $MaxWait) {
    Write-Log "WARNING: Network not ready after $MaxWait seconds. Continuing anyway..."
}

# Check Docker is running
Write-Log "Checking Docker..."
$DockerRunning = docker ps 2>$null
if (-not $?) {
    Write-Log "WARNING: Docker is not responding. Supervisor may have issues."
}

# Change to project directory
Write-Log "Changing to project directory: $ProjectRoot"
Set-Location $ProjectRoot

# Start supervisor
Write-Log "Starting supervisor..."
try {
    $Process = Start-Process -FilePath $PythonExe `
        -ArgumentList $SupervisorScript `
        -WorkingDirectory $ProjectRoot `
        -WindowStyle Hidden `
        -PassThru

    Write-Log "Supervisor started successfully (PID: $($Process.Id))"

    # Wait a moment and verify it's still running
    Start-Sleep -Seconds 5
    if ($Process.HasExited) {
        Write-Log "ERROR: Supervisor exited immediately. Check logs for errors."
        exit 1
    }

    Write-Log "Supervisor is running and stable."
    exit 0

} catch {
    Write-Log "ERROR: Failed to start supervisor: $_"
    exit 1
}
