#!/bin/bash
# Verify Sentiment Reporter Status on VPS
# Usage: ./scripts/verify_sentiment_reporter.sh [vps_host]

VPS_HOST="${1:-72.61.7.126}"
VPS_USER="root"

echo "🔍 Checking Sentiment Reporter Status on $VPS_HOST"
echo "=================================================="
echo

# Check if supervisor is running
echo "1. Checking supervisor process..."
ssh "${VPS_USER}@${VPS_HOST}" "pgrep -f supervisor.py > /dev/null && echo '✅ Supervisor is running' || echo '❌ Supervisor is NOT running'"
echo

# Check last 20 lines of supervisor log for sentiment_reporter
echo "2. Checking supervisor logs for sentiment_reporter..."
ssh "${VPS_USER}@${VPS_HOST}" "cd /home/jarvis/Jarvis && tail -50 logs/supervisor.log | grep sentiment_reporter | tail -10"
echo

# Check if sentiment reports are being posted to Telegram
echo "3. Checking when last sentiment report was generated..."
ssh "${VPS_USER}@${VPS_HOST}" "cd /home/jarvis/Jarvis && grep 'Posting sentiment report' logs/supervisor.log | tail -3"
echo

# Check for errors in sentiment reporter
echo "4. Checking for sentiment_reporter errors..."
ssh "${VPS_USER}@${VPS_HOST}" "cd /home/jarvis/Jarvis && grep -i 'sentiment.*error\|sentiment.*failed' logs/supervisor.log | tail -5"
echo

# Check required environment variables
echo "5. Checking required environment variables..."
ssh "${VPS_USER}@${VPS_HOST}" << 'ENDSSH'
cd /home/jarvis/Jarvis || exit 1
python3 -c "
import os
from dotenv import load_dotenv

load_dotenv('lifeos/config/.env')

required = {
    'TELEGRAM_BOT_TOKEN': os.getenv('TELEGRAM_BOT_TOKEN'),
    'TELEGRAM_BUY_BOT_CHAT_ID': os.getenv('TELEGRAM_BUY_BOT_CHAT_ID'),
    'XAI_API_KEY': os.getenv('XAI_API_KEY'),
}

for key, val in required.items():
    if val:
        print(f'✅ {key}: SET (first 20 chars: {val[:20]}...)')
    else:
        print(f'❌ {key}: NOT SET')
"
ENDSSH
echo

echo "=================================================="
echo "✅ Verification complete"
echo
echo "To manually restart sentiment reporter:"
echo "  ssh ${VPS_USER}@${VPS_HOST}"
echo "  cd /home/jarvis/Jarvis"
echo "  pkill -f supervisor.py"
echo "  nohup python3 bots/supervisor.py > logs/supervisor.log 2>&1 &"
