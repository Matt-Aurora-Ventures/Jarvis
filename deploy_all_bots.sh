#!/bin/bash
# Automated Bot Deployment Script
# Created: 2026-01-31
# Purpose: Deploy all bot tokens to VPS 72.61.7.126

set -e  # Exit on error

VPS="72.61.7.126"
ENV_FILE="/home/jarvis/Jarvis/lifeos/config/.env"

echo "🚀 Starting bot deployment to VPS $VPS..."

# Deploy X_BOT_TELEGRAM_TOKEN
echo ""
echo "📦 Deploying X_BOT_TELEGRAM_TOKEN..."
ssh -i ~/.ssh/jarvis_vps_key root@$VPS << 'EOF'
    # Check if X_BOT_TELEGRAM_TOKEN already exists
    if grep -q "X_BOT_TELEGRAM_TOKEN" /home/jarvis/Jarvis/lifeos/config/.env; then
        echo "⚠️  X_BOT_TELEGRAM_TOKEN already exists, skipping..."
    else
        echo "✅ Adding X_BOT_TELEGRAM_TOKEN..."
        echo '' >> /home/jarvis/Jarvis/lifeos/config/.env
        echo '# X Bot Telegram Sync (separate token to avoid polling conflicts)' >> /home/jarvis/Jarvis/lifeos/config/.env
        echo 'X_BOT_TELEGRAM_TOKEN=8451209415:AAFuXgze9Ekz3_02UIqC0poIK5LKARymoq0' >> /home/jarvis/Jarvis/lifeos/config/.env
    fi
EOF

# Deploy TREASURY_BOT_TOKEN
echo ""
echo "📦 Deploying TREASURY_BOT_TOKEN..."
ssh -i ~/.ssh/jarvis_vps_key root@$VPS << 'EOF'
    # Check if TREASURY_BOT_TOKEN already exists
    if grep -q "TREASURY_BOT_TOKEN" /home/jarvis/Jarvis/lifeos/config/.env; then
        echo "⚠️  TREASURY_BOT_TOKEN already exists, checking value..."
        grep "TREASURY_BOT_TOKEN" /home/jarvis/Jarvis/lifeos/config/.env
    else
        echo "✅ Adding TREASURY_BOT_TOKEN..."
        echo '' >> /home/jarvis/Jarvis/lifeos/config/.env
        echo '# Treasury Bot' >> /home/jarvis/Jarvis/lifeos/config/.env
        echo 'TREASURY_BOT_TOKEN=***TREASURY_BOT_TOKEN_REDACTED***' >> /home/jarvis/Jarvis/lifeos/config/.env
    fi
EOF

# Show current .env tokens
echo ""
echo "📄 Current bot tokens in .env:"
ssh -i ~/.ssh/jarvis_vps_key root@$VPS "grep '_BOT_TOKEN' /home/jarvis/Jarvis/lifeos/config/.env"

# Restart supervisor
echo ""
echo "🔄 Restarting supervisor..."
ssh -i ~/.ssh/jarvis_vps_key root@$VPS << 'EOF'
    pkill -f supervisor.py || echo "No supervisor running"
    sleep 2
    cd /home/jarvis/Jarvis
    nohup python bots/supervisor.py > logs/supervisor.log 2>&1 &
    echo "✅ Supervisor restarted"
    sleep 3
    echo ""
    echo "📊 Recent supervisor logs:"
    tail -20 logs/supervisor.log
EOF

echo ""
echo "✅ Deployment complete!"
echo ""
echo "🔍 To monitor logs:"
echo "   ssh root@$VPS 'tail -f /home/jarvis/Jarvis/logs/supervisor.log'"
echo ""
echo "🎯 Success criteria:"
echo "   - Look for: 'X bot using dedicated Telegram token (X_BOT_TELEGRAM_TOKEN)'"
echo "   - Look for: 'Treasury bot initialized'"
