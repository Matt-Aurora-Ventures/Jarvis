#!/bin/bash
# VPS Deployment Script for Jarvis
# Run this on the VPS after pulling the latest code

echo "=== Jarvis VPS Deployment ==="
echo ""

# 1. Pull latest code
echo "1️⃣  Pulling latest code from GitHub..."
cd /home/ubuntu/Jarvis
git pull origin main
echo "✅ Code updated"
echo ""

# 2. Verify Python dependencies
echo "2️⃣  Checking Python dependencies..."
pip install -r requirements.txt 2>/dev/null || pip3 install -r requirements.txt
echo "✅ Dependencies checked"
echo ""

# 3. Restart Telegram bot
echo "3️⃣  Restarting Telegram bot service..."
supervisorctl restart tg_bot
sleep 3
supervisorctl status tg_bot
echo "✅ Telegram bot restarted"
echo ""

# 4. Verify services
echo "4️⃣  Checking supervisor services..."
supervisorctl status | grep -E "tg_bot|buy_bot|sentiment|twitter"
echo ""

echo "=== Deployment Complete ==="
echo ""
echo "Next steps:"
echo "1. Test treasury commands in Telegram: /portfolio, /balance, /pnl"
echo "2. Check sentiment report for blue chip trading buttons"
echo "3. Verify both fixes are working"
