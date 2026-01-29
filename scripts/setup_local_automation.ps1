# Setup Full Local Automation
# Gives agent complete access to local machine

$ErrorActionPreference = "Stop"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "SETUP FULL LOCAL AUTOMATION" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "This grants the agent:" -ForegroundColor Yellow
Write-Host "  [OK] Full file system access" -ForegroundColor Green
Write-Host "  [OK] Browser automation (Puppeteer)" -ForegroundColor Green
Write-Host "  [OK] C++ libraries for automation" -ForegroundColor Green
Write-Host "  [OK] Download permissions" -ForegroundColor Green
Write-Host "  [OK] Python/Node.js execution" -ForegroundColor Green
Write-Host ""

# Create authorization file
$AUTH_FILE = "$env:USERPROFILE\.claude\local_automation_auth.json"
$AUTH_DATA = @{
    authorized = $true
    timestamp = Get-Date -Format "o"
    permissions = @{
        file_system = "full"
        browser = "full"
        downloads = "full"
        execution = "full"
        cpp_libs = "full"
        network = "full"
    }
    restrictions = @{
        requires_confirmation = @()  # Empty = nothing requires confirmation
        blocked_commands = @()        # Empty = nothing blocked
    }
} | ConvertTo-Json -Depth 10

New-Item -ItemType Directory -Force -Path (Split-Path $AUTH_FILE) | Out-Null
$AUTH_DATA | Out-File -FilePath $AUTH_FILE -Encoding utf8

Write-Host "[OK] Authorization file created: $AUTH_FILE" -ForegroundColor Green

# Install required automation tools
Write-Host ""
Write-Host "Installing automation tools..." -ForegroundColor Cyan

# Check/install Puppeteer
Write-Host "  Checking Puppeteer..." -ForegroundColor Yellow
if (!(Test-Path "$env:APPDATA\npm\node_modules\puppeteer")) {
    npm install -g puppeteer
    Write-Host "    [OK] Installed Puppeteer" -ForegroundColor Green
} else {
    Write-Host "    [OK] Puppeteer already installed" -ForegroundColor Green
}

# Check/install Python automation libs
Write-Host "  Checking Python automation libs..." -ForegroundColor Yellow
$PYTHON_LIBS = @("pyautogui", "selenium", "requests", "beautifulsoup4")

foreach ($lib in $PYTHON_LIBS) {
    try {
        python -c "import $($lib.Replace('-', '_'))" 2>$null
        Write-Host "    [OK] $lib already installed" -ForegroundColor Green
    }
    catch {
        pip install $lib
        Write-Host "    [OK] Installed $lib" -ForegroundColor Green
    }
}

# Check C++ build tools
Write-Host "  Checking C++ build tools..." -ForegroundColor Yellow
if (Get-Command cl.exe -ErrorAction SilentlyContinue) {
    Write-Host "    [OK] MSVC already installed" -ForegroundColor Green
} else {
    Write-Host "    [WARNING] MSVC not found - install Visual Studio Build Tools manually" -ForegroundColor Yellow
    Write-Host "       Download: https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022" -ForegroundColor Gray
}

# Setup scheduled backup task
Write-Host ""
Write-Host "Setting up scheduled backups..." -ForegroundColor Cyan

$BACKUP_SCRIPT = "$PSScriptRoot\local_backup_system.ps1"
$TASK_NAME = "JarvisLocalBackup"

# Remove existing task if present
Unregister-ScheduledTask -TaskName $TASK_NAME -Confirm:$false -ErrorAction SilentlyContinue

# Create new task (run every 6 hours)
$Action = New-ScheduledTaskAction -Execute "PowerShell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$BACKUP_SCRIPT`""
$Trigger = New-ScheduledTaskTrigger -Daily -At "12:00AM"
$Trigger.Repetition = (New-ScheduledTaskTrigger -Once -At "12:00AM" -RepetitionInterval (New-TimeSpan -Hours 6) -RepetitionDuration ([TimeSpan]::FromDays(9999))).Repetition
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName $TASK_NAME -Action $Action -Trigger $Trigger -Settings $Settings -Description "Jarvis local backup system" | Out-Null

Write-Host "[OK] Scheduled task created: $TASK_NAME (runs every 6 hours)" -ForegroundColor Green

# Test backup immediately
Write-Host ""
Write-Host "Running test backup..." -ForegroundColor Cyan
& $BACKUP_SCRIPT

# Environment variables for VPS coordination
Write-Host ""
Write-Host "VPS Coordination Setup..." -ForegroundColor Cyan
Write-Host ""
Write-Host "To enable VPS sync, set these environment variables:" -ForegroundColor Yellow
Write-Host '  $env:VPS_HOST = "your_vps_ip"' -ForegroundColor Gray
Write-Host '  $env:VPS_USER = "root"' -ForegroundColor Gray
Write-Host ""
Write-Host "Then run:" -ForegroundColor Yellow
Write-Host '  ssh-copy-id $env:VPS_USER@$env:VPS_HOST' -ForegroundColor Gray
Write-Host ""

# Create agent status file
$STATUS_FILE = "$env:USERPROFILE\.claude\agent_status.json"
$STATUS_DATA = @{
    local_automation = "enabled"
    last_backup = Get-Date -Format "o"
    scheduled_task = $TASK_NAME
    permissions = "full"
    vps_sync = if ($env:VPS_HOST) { "enabled" } else { "disabled" }
} | ConvertTo-Json

$STATUS_DATA | Out-File -FilePath $STATUS_FILE -Encoding utf8

# Summary
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "[OK] LOCAL AUTOMATION SETUP COMPLETE" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Summary:" -ForegroundColor White
Write-Host "  Authorization: [OK] Full access granted" -ForegroundColor Green
Write-Host "  Puppeteer: [OK] Installed" -ForegroundColor Green
Write-Host "  Python automation: [OK] Installed" -ForegroundColor Green
Write-Host "  Scheduled backups: [OK] Every 6 hours" -ForegroundColor Green
Write-Host "  Status file: $STATUS_FILE" -ForegroundColor Cyan
Write-Host ""
Write-Host "Agent now has full automation capabilities!" -ForegroundColor Green
