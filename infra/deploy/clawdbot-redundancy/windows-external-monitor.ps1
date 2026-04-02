# ClawdBot External Monitor - Layer 3 Redundancy
# Runs on Windows via Task Scheduler every 5 minutes
# Can SSH into VPS to recover bots if VPS-local watchdog fails

$VPS_IP = "76.13.106.100"
$VPS_TAILSCALE = "100.89.228.71"
$TELEGRAM_BOT_TOKEN = $env:TELEGRAM_BOT_TOKEN
$TELEGRAM_CHAT_ID = $env:TELEGRAM_CHAT_ID
$LOG_FILE = "$env:USERPROFILE\.clawdbot-monitor.log"
$STATE_FILE = "$env:USERPROFILE\.clawdbot-monitor-state.json"

$BOTS = @{
    "friday" = 18789
    "matt" = 18800
    "jarvis" = 18801
}

function Write-Log {
    param($Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$timestamp - $Message" | Add-Content $LOG_FILE
    Write-Host "$timestamp - $Message"
}

function Send-TelegramAlert {
    param(
        [string]$Message,
        [string]$Urgency = "normal"
    )

    $emoji = switch ($Urgency) {
        "critical" { "[CRITICAL]" }
        "warning"  { "[WARNING]" }
        "success"  { "[OK]" }
        default    { "[INFO]" }
    }

    $body = @{
        chat_id = $TELEGRAM_CHAT_ID
        text = "$emoji [Windows Monitor] $Message"
        parse_mode = "HTML"
    }

    try {
        Invoke-RestMethod -Uri "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" -Method Post -Body $body -ErrorAction SilentlyContinue | Out-Null
    } catch {
        Write-Log "Failed to send Telegram alert: $_"
    }
}

function Test-BotHealth {
    param([string]$BotName, [int]$Port)

    try {
        $response = Invoke-WebRequest -Uri "http://${VPS_IP}:${Port}/" -TimeoutSec 10 -ErrorAction Stop
        return $response.Content -match "clawdbot-app"
    } catch {
        Write-Log "${BotName}: HTTP check failed - $_"
        return $false
    }
}

function Test-VPSReachable {
    if (Test-Connection -ComputerName $VPS_IP -Count 1 -Quiet) {
        return $VPS_IP
    }
    if (Test-Connection -ComputerName $VPS_TAILSCALE -Count 1 -Quiet) {
        Write-Log "Direct IP unreachable, using Tailscale"
        return $VPS_TAILSCALE
    }
    return $null
}

function Invoke-SSHRecovery {
    param([string]$BotName, [string]$TargetIP)

    Write-Log "Attempting SSH recovery for $BotName via $TargetIP"
    Send-TelegramAlert "$BotName unresponsive - initiating external SSH recovery..." "warning"

    try {
        $result = ssh root@$TargetIP "docker restart clawdbot-$BotName; sleep 30; docker ps | grep clawdbot-$BotName" 2>&1
        Write-Log "SSH recovery result: $result"

        if ($result -match "clawdbot-$BotName") {
            Send-TelegramAlert "$BotName recovered via external SSH!" "success"
            return $true
        } else {
            Send-TelegramAlert "$BotName SSH recovery may have failed" "critical"
            return $false
        }
    } catch {
        Write-Log "SSH recovery failed: $_"
        Send-TelegramAlert "$BotName SSH recovery failed: $_" "critical"
        return $false
    }
}

function Invoke-FullVPSRecovery {
    param([string]$TargetIP)

    Write-Log "Initiating full VPS recovery"
    Send-TelegramAlert "Multiple bots down - initiating full VPS recovery..." "critical"

    try {
        $result = ssh root@$TargetIP "for bot in friday matt jarvis; do docker restart clawdbot-`$bot 2>/dev/null; done; sleep 45; docker ps --format 'table {{.Names}}\t{{.Status}}' | grep clawdbot" 2>&1
        Write-Log "Full recovery result: $result"
        Send-TelegramAlert "Full recovery completed. Status: $result" "info"
        return $true
    } catch {
        Write-Log "Full recovery failed: $_"
        Send-TelegramAlert "Full VPS recovery FAILED: $_" "critical"
        return $false
    }
}

# Main execution
Write-Log "=== External monitor check started ==="

$targetIP = Test-VPSReachable
if (-not $targetIP) {
    Write-Log "VPS completely unreachable!"
    Send-TelegramAlert "VPS unreachable from Windows monitor! Direct IP and Tailscale both failed." "critical"
    exit 1
}

$unhealthyBots = @()
$healthyBots = @()

foreach ($bot in $BOTS.GetEnumerator()) {
    $healthy = Test-BotHealth -BotName $bot.Key -Port $bot.Value
    if ($healthy) {
        Write-Log "$($bot.Key): Healthy"
        $healthyBots += $bot.Key
    } else {
        Write-Log "$($bot.Key): UNHEALTHY"
        $unhealthyBots += $bot.Key
    }
}

if ($unhealthyBots.Count -eq 0) {
    Write-Log "All bots healthy"
    @{
        timestamp = (Get-Date -Format "o")
        status = "healthy"
        bots = @{
            friday = @{ healthy = $true }
            matt = @{ healthy = $true }
            jarvis = @{ healthy = $true }
        }
    } | ConvertTo-Json | Set-Content $STATE_FILE
    exit 0
}

$cooldownFile = "$env:TEMP\.clawdbot-external-cooldown"
$cooldownMinutes = 2

if (Test-Path $cooldownFile) {
    $lastRun = Get-Content $cooldownFile
    $elapsed = ((Get-Date) - [datetime]$lastRun).TotalMinutes
    if ($elapsed -lt $cooldownMinutes) {
        Write-Log "In cooldown ($([int]$elapsed) min), letting VPS watchdog handle it"
        exit 0
    }
}

(Get-Date -Format "o") | Set-Content $cooldownFile

if ($unhealthyBots.Count -ge 2) {
    Invoke-FullVPSRecovery -TargetIP $targetIP
} else {
    foreach ($bot in $unhealthyBots) {
        Invoke-SSHRecovery -BotName $bot -TargetIP $targetIP
    }
}

Write-Log "=== External monitor check completed ==="
