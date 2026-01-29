# Create Scheduled Backup Task

$BACKUP_SCRIPT = "c:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\scripts\local_backup_system.ps1"
$TASK_NAME = "JarvisLocalBackup"

# Remove existing
Unregister-ScheduledTask -TaskName $TASK_NAME -Confirm:$false -ErrorAction SilentlyContinue

# Create action
$Action = New-ScheduledTaskAction -Execute "PowerShell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$BACKUP_SCRIPT`""

# Create trigger (every 6 hours, repeating for 365 days)
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Hours 6) -RepetitionDuration ([TimeSpan]::FromDays(365))

# Settings
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# Register
Register-ScheduledTask -TaskName $TASK_NAME -Action $Action -Trigger $Trigger -Settings $Settings -Description "Jarvis local backup system"

Write-Host "[OK] Scheduled task created: $TASK_NAME" -ForegroundColor Green
