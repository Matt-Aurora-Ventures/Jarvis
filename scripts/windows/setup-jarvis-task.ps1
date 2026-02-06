$action = New-ScheduledTaskAction `
    -Execute 'C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\.venv\Scripts\python.exe' `
    -Argument 'bots\supervisor.py' `
    -WorkingDirectory 'C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis'

$trigger = New-ScheduledTaskTrigger -AtStartup

$settings = New-ScheduledTaskSettingsSet `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

Register-ScheduledTask `
    -TaskName 'Jarvis Supervisor' `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description 'Auto-start Jarvis bot supervisor on boot with auto-restart on failure' `
    -Force

Write-Host "Jarvis Supervisor scheduled task created successfully."
Write-Host "It will auto-start on boot and restart up to 3 times on failure (1 min interval)."
