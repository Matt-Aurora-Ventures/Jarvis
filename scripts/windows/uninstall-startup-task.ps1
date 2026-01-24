# Uninstall Jarvis Supervisor Auto-Start Task
# Must be run as Administrator

$ErrorActionPreference = "Stop"

# Check for admin privileges
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator" -ForegroundColor Red
    Write-Host "Right-click PowerShell and select 'Run as Administrator', then run this script again." -ForegroundColor Yellow
    exit 1
}

Write-Host "Uninstalling Jarvis Supervisor startup task..." -ForegroundColor Cyan

# Configuration
$TaskName = "Jarvis Supervisor Daemon"
$TaskPath = "\Jarvis\"

# Check if task exists
$Task = Get-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -ErrorAction SilentlyContinue

if (-not $Task) {
    Write-Host "Task not found. Nothing to uninstall." -ForegroundColor Yellow
    exit 0
}

# Confirm removal
Write-Host "`nFound task: $TaskPath$TaskName" -ForegroundColor Yellow
$Confirm = Read-Host "Are you sure you want to remove this task? (Y/N)"

if ($Confirm -ne 'Y' -and $Confirm -ne 'y') {
    Write-Host "Uninstall cancelled." -ForegroundColor Yellow
    exit 0
}

# Remove the task
try {
    Unregister-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -Confirm:$false
    Write-Host "`nSUCCESS! Task uninstalled successfully." -ForegroundColor Green
    Write-Host "The supervisor will no longer start automatically on boot." -ForegroundColor Yellow
} catch {
    Write-Host "`nERROR: Failed to uninstall task: $_" -ForegroundColor Red
    exit 1
}
