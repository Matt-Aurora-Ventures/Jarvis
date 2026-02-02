# Bot Token Deployment Script
# Deploys all corrected bot tokens to VPS servers
# Date: 2026-01-31

param(
    [switch]$DryRun,
    [switch]$SkipBackup,
    [switch]$VPS1Only,
    [switch]$VPS2Only
)

Write-Host "`n=== BOT TOKEN DEPLOYMENT SCRIPT ===" -ForegroundColor Cyan
Write-Host "Date: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Gray
Write-Host ""

# Token definitions (from ALL_BOT_TOKENS_COMPLETE.txt)
$VPS1_IP = "72.61.7.126"
$VPS1_ENV_PATH = "/home/jarvis/Jarvis/lifeos/config/.env"
$VPS1_TOKENS = @{
    "TREASURY_BOT_TOKEN" = "***TREASURY_BOT_TOKEN_REDACTED***"
    "X_BOT_TELEGRAM_TOKEN" = "7968869100:AAEan4TRjH4eHIOGvssn6BV71ChsuPrz6Hc"
}

$VPS2_IP = "76.13.106.100"
$VPS2_ENV_PATH = "/root/clawdbots/tokens.env"
$VPS2_TOKENS = @{
    "CLAWDMATT_BOT_TOKEN" = "8288059637:AAHbcATe1mgMBGKuf5ceYFpyVpO2rzXYFq4"
    "CLAWDFRIDAY_BOT_TOKEN" = "7864180473:AAHN9ROzOdtHRr5JXw1iTDpMYQitGEh-Bu4"
    "CLAWDJARVIS_BOT_TOKEN" = "8434411668:AAHNGOzjHI-rYwBZ2mIM2c7cbZmLGTjekJ4"
}

function Deploy-ToVPS {
    param(
        [string]$VPS_IP,
        [string]$ENV_PATH,
        [hashtable]$TOKENS,
        [string]$VPS_NAME
    )

    Write-Host "`n--- Deploying to $VPS_NAME ($VPS_IP) ---" -ForegroundColor Yellow

    # Test SSH connection
    Write-Host "Testing SSH connection..." -ForegroundColor Gray
    $testResult = ssh -o ConnectTimeout=5 root@$VPS_IP "echo 'Connected'" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Cannot connect to $VPS_IP via SSH" -ForegroundColor Red
        Write-Host "  Make sure SSH is configured and the VPS is online" -ForegroundColor Red
        return $false
    }
    Write-Host "[OK] SSH connection successful" -ForegroundColor Green

    # Backup current .env
    if (-not $SkipBackup) {
        Write-Host "Creating backup of .env file..." -ForegroundColor Gray
        $backupCmd = "cp $ENV_PATH ${ENV_PATH}.backup-`$(date +%Y%m%d_%H%M%S)"
        if ($DryRun) {
            Write-Host "[DRY RUN] Would run: $backupCmd" -ForegroundColor Yellow
        } else {
            ssh root@$VPS_IP $backupCmd
            if ($LASTEXITCODE -eq 0) {
                Write-Host "[OK] Backup created" -ForegroundColor Green
            } else {
                Write-Host "[WARN] Backup failed (file may not exist yet)" -ForegroundColor Yellow
            }
        }
    }

    # Deploy each token
    foreach ($tokenName in $TOKENS.Keys) {
        $tokenValue = $TOKENS[$tokenName]
        Write-Host "`nDeploying $tokenName..." -ForegroundColor Gray

        # Check if token already exists
        $checkCmd = "grep -q '^${tokenName}=' $ENV_PATH && echo 'EXISTS' || echo 'NEW'"
        $tokenStatus = ssh root@$VPS_IP $checkCmd 2>$null

        if ($tokenStatus -match "EXISTS") {
            Write-Host "  Token exists - updating..." -ForegroundColor Gray
            $deployCmd = "sed -i 's~^${tokenName}=.*~${tokenName}=${tokenValue}~' $ENV_PATH"
        } else {
            Write-Host "  New token - appending..." -ForegroundColor Gray
            $deployCmd = "echo '${tokenName}=${tokenValue}' >> $ENV_PATH"
        }

        if ($DryRun) {
            Write-Host "[DRY RUN] Would run: $deployCmd" -ForegroundColor Yellow
        } else {
            ssh root@$VPS_IP $deployCmd
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  [OK] Token deployed" -ForegroundColor Green
            } else {
                Write-Host "  [ERROR] Token deployment failed" -ForegroundColor Red
                return $false
            }
        }

        # Verify token
        $verifyCmd = "grep '^${tokenName}=' $ENV_PATH"
        $verification = ssh root@$VPS_IP $verifyCmd 2>$null
        if ($verification -match $tokenName) {
            Write-Host "  [VERIFIED] $verification" -ForegroundColor Green
        } else {
            Write-Host "  [ERROR] Verification failed - token not found in .env" -ForegroundColor Red
            return $false
        }
    }

    # Restart supervisor (VPS1 only)
    if ($VPS_NAME -eq "VPS1" -and -not $DryRun) {
        Write-Host "`nRestarting supervisor..." -ForegroundColor Gray
        ssh root@$VPS_IP "pkill -f supervisor.py; sleep 2; cd /home/jarvis/Jarvis && nohup python bots/supervisor.py > logs/supervisor.log 2>&1 &"
        Write-Host "[OK] Supervisor restarted" -ForegroundColor Green
        Write-Host "  Monitor logs: ssh root@$VPS_IP 'tail -f /home/jarvis/Jarvis/logs/supervisor.log'" -ForegroundColor Gray
    }

    # Restart ClawdBots service (VPS2 only)
    if ($VPS_NAME -eq "VPS2" -and -not $DryRun) {
        Write-Host "`nRestarting ClawdBots service..." -ForegroundColor Gray
        # Check if systemd service exists
        $serviceCheck = ssh root@$VPS_IP "systemctl list-units --type=service | grep clawdbot" 2>$null
        if ($serviceCheck) {
            ssh root@$VPS_IP "systemctl restart clawdbot-gateway"
            Write-Host "[OK] ClawdBots service restarted" -ForegroundColor Green
        } else {
            Write-Host "[WARN] No systemd service found - restart manually if needed" -ForegroundColor Yellow
        }
    }

    return $true
}

# Main execution
if ($DryRun) {
    Write-Host "[DRY RUN MODE] No changes will be made`n" -ForegroundColor Yellow
}

$success = $true

# Deploy to VPS1 (Main Jarvis)
if (-not $VPS2Only) {
    $result = Deploy-ToVPS -VPS_IP $VPS1_IP -ENV_PATH $VPS1_ENV_PATH -TOKENS $VPS1_TOKENS -VPS_NAME "VPS1"
    $success = $success -and $result
}

# Deploy to VPS2 (ClawdBots)
if (-not $VPS1Only) {
    $result = Deploy-ToVPS -VPS_IP $VPS2_IP -ENV_PATH $VPS2_ENV_PATH -TOKENS $VPS2_TOKENS -VPS_NAME "VPS2"
    $success = $success -and $result
}

# Final summary
Write-Host "`n=== DEPLOYMENT SUMMARY ===" -ForegroundColor Cyan
if ($DryRun) {
    Write-Host "[DRY RUN] No actual changes were made" -ForegroundColor Yellow
    Write-Host "Run without -DryRun to deploy for real" -ForegroundColor Yellow
} elseif ($success) {
    Write-Host "[SUCCESS] All tokens deployed successfully!" -ForegroundColor Green
    Write-Host "`nNext steps:" -ForegroundColor Yellow
    Write-Host "1. Monitor VPS1 logs: ssh root@$VPS1_IP 'tail -f /home/jarvis/Jarvis/logs/supervisor.log'" -ForegroundColor Gray
    Write-Host "2. Check for 'Using unique X bot token' and 'Using unique treasury bot token'" -ForegroundColor Gray
    Write-Host "3. Verify no polling conflicts for 30+ minutes" -ForegroundColor Gray
    Write-Host "4. Test X bot posting to verify Telegram sync works" -ForegroundColor Gray
} else {
    Write-Host "[FAILED] Some deployments failed - check errors above" -ForegroundColor Red
}

Write-Host ""
