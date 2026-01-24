# Install Jarvis Supervisor Auto-Start Task
# Must be run as Administrator

$ErrorActionPreference = "Stop"

# Check for admin privileges
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator" -ForegroundColor Red
    Write-Host "Right-click PowerShell and select 'Run as Administrator', then run this script again." -ForegroundColor Yellow
    exit 1
}

Write-Host "Installing Jarvis Supervisor startup task..." -ForegroundColor Cyan

# Configuration
$TaskName = "Jarvis Supervisor Daemon"
$TaskPath = "\Jarvis\"
$ScriptPath = "C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\scripts\windows\start-jarvis-supervisor.ps1"

# Verify script exists
if (-not (Test-Path $ScriptPath)) {
    Write-Host "ERROR: Startup script not found at: $ScriptPath" -ForegroundColor Red
    exit 1
}

# Create scheduled task action
$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$ScriptPath`""

# Create trigger (at startup, delayed 30 seconds)
$Trigger = New-ScheduledTaskTrigger -AtStartup
$Trigger.Delay = "PT30S"  # 30 second delay

# Create settings
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

# Create principal (run as current user)
$Principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType ServiceAccount `
    -RunLevel Highest

# Register the task
try {
    # Remove existing task if it exists
    $ExistingTask = Get-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -ErrorAction SilentlyContinue
    if ($ExistingTask) {
        Write-Host "Removing existing task..." -ForegroundColor Yellow
        Unregister-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -Confirm:$false
    }

    # Register new task
    Register-ScheduledTask `
        -TaskName $TaskName `
        -TaskPath $TaskPath `
        -Action $Action `
        -Trigger $Trigger `
        -Settings $Settings `
        -Principal $Principal `
        -Description "Auto-start Jarvis supervisor daemon on system boot"

    Write-Host "`nSUCCESS! Task installed successfully." -ForegroundColor Green
    Write-Host "`nTask Details:" -ForegroundColor Cyan
    Write-Host "  Name: $TaskName"
    Write-Host "  Path: $TaskPath"
    Write-Host "  Trigger: At startup (30s delay)"
    Write-Host "  Script: $ScriptPath"
    Write-Host "`nThe supervisor will now start automatically on system boot." -ForegroundColor Green

    # Ask if user wants to run it now
    $RunNow = Read-Host "`nDo you want to run the task now to test it? (Y/N)"
    if ($RunNow -eq 'Y' -or $RunNow -eq 'y') {
        Write-Host "Starting task..." -ForegroundColor Cyan
        Start-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath
        Start-Sleep -Seconds 2
        Write-Host "Task started. Check supervisor status." -ForegroundColor Green
    }

} catch {
    Write-Host "`nERROR: Failed to install task: $_" -ForegroundColor Red
    exit 1
}
