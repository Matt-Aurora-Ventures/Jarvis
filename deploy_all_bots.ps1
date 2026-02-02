# Automated Bot Deployment Script (PowerShell)
# Created: 2026-01-31
# Purpose: Deploy all bot tokens to VPS 72.61.7.126

$VPS = "72.61.7.126"
$KEY = "C:\Users\lucid\AppData\Local\Temp\jarvis_vps_key"

Write-Host "🚀 Starting bot deployment to VPS $VPS..." -ForegroundColor Green

# Deploy X_BOT_TELEGRAM_TOKEN
Write-Host "`n📦 Deploying X_BOT_TELEGRAM_TOKEN..." -ForegroundColor Cyan
ssh -i $KEY root@$VPS @"
if grep -q 'X_BOT_TELEGRAM_TOKEN' /home/jarvis/Jarvis/lifeos/config/.env; then
    echo '⚠️  X_BOT_TELEGRAM_TOKEN already exists'
else
    echo '✅ Adding X_BOT_TELEGRAM_TOKEN...'
    echo '' >> /home/jarvis/Jarvis/lifeos/config/.env
    echo '# X Bot Telegram Sync' >> /home/jarvis/Jarvis/lifeos/config/.env
    echo 'X_BOT_TELEGRAM_TOKEN=8451209415:AAFuXgze9Ekz3_02UIqC0poIK5LKARymoq0' >> /home/jarvis/Jarvis/lifeos/config/.env
fi
"@

# Deploy TREASURY_BOT_TOKEN
Write-Host "`n📦 Deploying TREASURY_BOT_TOKEN..." -ForegroundColor Cyan
ssh -i $KEY root@$VPS @"
if grep -q 'TREASURY_BOT_TOKEN' /home/jarvis/Jarvis/lifeos/config/.env; then
    echo '⚠️  TREASURY_BOT_TOKEN already exists'
    grep 'TREASURY_BOT_TOKEN' /home/jarvis/Jarvis/lifeos/config/.env
else
    echo '✅ Adding TREASURY_BOT_TOKEN...'
    echo '' >> /home/jarvis/Jarvis/lifeos/config/.env
    echo '# Treasury Bot' >> /home/jarvis/Jarvis/lifeos/config/.env
    echo 'TREASURY_BOT_TOKEN=***TREASURY_BOT_TOKEN_REDACTED***' >> /home/jarvis/Jarvis/lifeos/config/.env
fi
"@

# Show current tokens
Write-Host "`n📄 Current bot tokens:" -ForegroundColor Yellow
ssh -i $KEY root@$VPS "grep '_BOT_TOKEN' /home/jarvis/Jarvis/lifeos/config/.env"

# Restart supervisor
Write-Host "`n🔄 Restarting supervisor..." -ForegroundColor Cyan
ssh -i $KEY root@$VPS @"
pkill -f supervisor.py || echo 'No supervisor running'
sleep 2
cd /home/jarvis/Jarvis
nohup python bots/supervisor.py > logs/supervisor.log 2>&1 &
sleep 3
tail -20 logs/supervisor.log
"@

Write-Host "`n✅ Deployment complete!" -ForegroundColor Green
Write-Host "`n🎯 Success criteria:" -ForegroundColor Yellow
Write-Host "   - Look for: 'X bot using dedicated Telegram token (X_BOT_TELEGRAM_TOKEN)'"
Write-Host "   - Look for: 'Treasury bot initialized'"
