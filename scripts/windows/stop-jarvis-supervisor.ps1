# Stop Jarvis Supervisor Daemon
# This script gracefully stops the running supervisor

$ErrorActionPreference = "Stop"

# Configuration
$ProjectRoot = "C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis"
$LockFile = "$ProjectRoot\.supervisor.lock"
$LogDir = "$ProjectRoot\logs"
$LogFile = "$LogDir\supervisor-startup.log"

# Function to write log messages
function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logMessage = "[$timestamp] $Message"
    Write-Host $logMessage
    if (Test-Path $LogDir) {
        Add-Content -Path $LogFile -Value $logMessage
    }
}

Write-Log "=== Stopping Jarvis Supervisor ==="

# Try to find PID from lock file
$pid = $null
if (Test-Path $LockFile) {
    try {
        $lockContent = Get-Content $LockFile -Raw | ConvertFrom-Json
        $pid = $lockContent.pid
        Write-Log "Found supervisor PID from lock file: $pid"
    } catch {
        Write-Log "Could not read lock file."
    }
}

# Also search for supervisor process
$supervisorProcesses = Get-Process -Name "python" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*supervisor.py*" }

if ($supervisorProcesses) {
    foreach ($proc in $supervisorProcesses) {
        Write-Log "Found supervisor process: PID $($proc.Id)"
        try {
            Stop-Process -Id $proc.Id -Force
            Write-Log "Stopped process $($proc.Id)"
        } catch {
            Write-Log "Failed to stop process $($proc.Id): $_"
        }
    }
} elseif ($pid) {
    # Try to stop using PID from lock file
    try {
        Stop-Process -Id $pid -Force
        Write-Log "Stopped process $pid"
    } catch {
        Write-Log "Failed to stop process $pid: $_"
    }
} else {
    Write-Log "No supervisor process found running."
}

# Clean up lock file
if (Test-Path $LockFile) {
    Remove-Item $LockFile -Force
    Write-Log "Removed lock file."
}

Write-Log "Supervisor stop complete."
