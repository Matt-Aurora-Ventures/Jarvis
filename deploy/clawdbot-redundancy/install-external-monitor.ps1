# Install ClawdBot External Monitor as Windows Task
# Run this script as Administrator

$TaskName = "ClawdBot-External-Monitor"
$ScriptPath = "$PSScriptRoot\windows-external-monitor.ps1"

# Check if running as admin
if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Host "Please run this script as Administrator" -ForegroundColor Red
    exit 1
}

# Remove existing task if present
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

# Create the task action
$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$ScriptPath`""

# Create trigger - every 5 minutes
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 5)

# Create settings
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RunOnlyIfNetworkAvailable

# Register the task
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -RunLevel Highest -Description "External health monitor for ClawdBot cluster on VPS"

Write-Host "Task '$TaskName' installed successfully!" -ForegroundColor Green
Write-Host "The monitor will run every 5 minutes and SSH into VPS to recover bots if needed."
Write-Host ""
Write-Host "To view logs: Get-Content ~\.clawdbot-monitor.log -Tail 50"
Write-Host "To run manually: & '$ScriptPath'"
Write-Host "To uninstall: Unregister-ScheduledTask -TaskName '$TaskName'"
