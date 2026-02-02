# PowerShell Deployment Script for TREASURY_BOT_TOKEN
# VPS: 72.61.7.126
# Target: /home/jarvis/Jarvis/lifeos/config/.env
# Token: TREASURY_BOT_TOKEN=850H068106:AAHoS0GKxl79nPE_2wFjkkmX_T7iXEwOyao

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "TREASURY BOT TOKEN DEPLOYMENT" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

$VPS_IP = "72.61.7.126"
$TOKEN_LINE = "TREASURY_BOT_TOKEN=850H068106:AAHoS0GKxl79nPE_2wFjkkmX_T7iXEwOyao"
$ENV_PATH = "/home/jarvis/Jarvis/lifeos/config/.env"

# Method 1: Try SSH (requires ssh.exe in PATH)
Write-Host "Method 1: Attempting SSH deployment..." -ForegroundColor Yellow

$sshAvailable = Get-Command ssh -ErrorAction SilentlyContinue
if ($sshAvailable) {
    Write-Host "  Testing SSH connection..."

    $testResult = ssh -o ConnectTimeout=5 root@$VPS_IP "echo 'SSH OK'" 2>&1

    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ SSH connection successful" -ForegroundColor Green

        # Create backup
        Write-Host "  Creating backup..."
        ssh root@$VPS_IP "cp $ENV_PATH ${ENV_PATH}.backup-$(Get-Date -Format 'yyyyMMdd_HHmmss')"

        # Check if token exists
        $checkToken = ssh root@$VPS_IP "grep -q 'TREASURY_BOT_TOKEN' $ENV_PATH && echo 'EXISTS' || echo 'NEW'" 2>&1

        if ($checkToken -match "EXISTS") {
            Write-Host "  ⚠ Updating existing TREASURY_BOT_TOKEN..." -ForegroundColor Yellow
            ssh root@$VPS_IP "sed -i 's/^TREASURY_BOT_TOKEN=.*/TREASURY_BOT_TOKEN=850H068106:AAHoS0GKxl79nPE_2wFjkkmX_T7iXEwOyao/' $ENV_PATH"
        } else {
            Write-Host "  Adding new TREASURY_BOT_TOKEN..." -ForegroundColor Green
            ssh root@$VPS_IP "echo '$TOKEN_LINE' >> $ENV_PATH"
        }

        # Restart supervisor
        Write-Host "  Restarting supervisor..."
        ssh root@$VPS_IP "pkill -f supervisor.py || true; sleep 2; cd /home/jarvis/Jarvis && nohup python bots/supervisor.py > logs/supervisor.log 2>&1 &"

        Start-Sleep -Seconds 5

        # Verify
        Write-Host "  Checking logs..."
        $logCheck = ssh root@$VPS_IP "tail -50 /home/jarvis/Jarvis/logs/supervisor.log | grep -q 'Using unique treasury bot token' && echo 'SUCCESS' || echo 'PENDING'" 2>&1

        if ($logCheck -match "SUCCESS") {
            Write-Host ""
            Write-Host "✅ DEPLOYMENT SUCCESSFUL!" -ForegroundColor Green
            Write-Host "   Treasury bot is using the unique token." -ForegroundColor Green
        } else {
            Write-Host ""
            Write-Host "⚠ Token deployed but verification pending." -ForegroundColor Yellow
            Write-Host "   Check logs manually: ssh root@72.61.7.126 'tail -f /home/jarvis/Jarvis/logs/supervisor.log'" -ForegroundColor Yellow
        }

        exit 0
    } else {
        Write-Host "  ❌ SSH connection failed: $testResult" -ForegroundColor Red
    }
} else {
    Write-Host "  ❌ SSH not available in PATH" -ForegroundColor Red
}

# Method 2: Create manual instructions
Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "MANUAL DEPLOYMENT REQUIRED" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Automated deployment failed. Please deploy manually:" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. SSH to VPS:" -ForegroundColor White
Write-Host "   ssh root@72.61.7.126" -ForegroundColor Cyan
Write-Host ""
Write-Host "2. Edit the .env file:" -ForegroundColor White
Write-Host "   nano /home/jarvis/Jarvis/lifeos/config/.env" -ForegroundColor Cyan
Write-Host ""
Write-Host "3. Add or update this line:" -ForegroundColor White
Write-Host "   TREASURY_BOT_TOKEN=850H068106:AAHoS0GKxl79nPE_2wFjkkmX_T7iXEwOyao" -ForegroundColor Green
Write-Host ""
Write-Host "4. Save and exit:" -ForegroundColor White
Write-Host "   Ctrl+X, then Y, then Enter" -ForegroundColor Cyan
Write-Host ""
Write-Host "5. Restart supervisor:" -ForegroundColor White
Write-Host "   pkill -f supervisor.py" -ForegroundColor Cyan
Write-Host "   cd /home/jarvis/Jarvis" -ForegroundColor Cyan
Write-Host "   nohup python bots/supervisor.py > logs/supervisor.log 2>&1 &" -ForegroundColor Cyan
Write-Host ""
Write-Host "6. Verify deployment:" -ForegroundColor White
Write-Host "   tail -f logs/supervisor.log" -ForegroundColor Cyan
Write-Host "   (Look for 'Using unique treasury bot token')" -ForegroundColor Gray
Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# Copy token to clipboard for convenience
$TOKEN_LINE | Set-Clipboard -ErrorAction SilentlyContinue
if ($?) {
    Write-Host "✓ Token copied to clipboard!" -ForegroundColor Green
    Write-Host ""
}

exit 1
