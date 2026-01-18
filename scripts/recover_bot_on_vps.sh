#!/bin/bash
# ============================================
# VPS Bot Recovery and Restart Script
# ============================================
# Usage: bash scripts/recover_bot_on_vps.sh
# Prerequisites:
#   - SSH key at ~/.ssh/id_ed25519
#   - Access to root@72.61.7.126
# ============================================

set -e

VPS="root@72.61.7.126"
SSH_KEY="~/.ssh/id_ed25519"
JARVIS_PATH="/home/jarvis/Jarvis"
LOG_FILE="$JARVIS_PATH/logs/tg_bot.log"
LOCK_DIR="$JARVIS_PATH/data/locks"
VENV_BIN="$JARVIS_PATH/venv/bin/python"

echo "============================================"
echo "VPS BOT RECOVERY UTILITY"
echo "============================================"
echo ""

# Check SSH connectivity
echo "[1/5] Checking VPS connectivity..."
if ! ssh -i $SSH_KEY $VPS "echo 'SSH OK'" > /dev/null 2>&1; then
    echo "ERROR: Cannot connect to VPS via SSH"
    exit 1
fi
echo "OK - VPS reachable"
echo ""

# Check current bot status
echo "[2/5] Checking current bot status..."
BOT_STATUS=$(ssh -i $SSH_KEY $VPS "ps aux | grep -i 'tg_bot.bot' | grep -v grep | wc -l" || echo "0")
echo "Bot processes running: $BOT_STATUS"

if [ "$BOT_STATUS" -gt 0 ]; then
    echo "Stopping existing bot processes..."
    ssh -i $SSH_KEY $VPS "pkill -9 -f 'tg_bot.bot' || true"
    sleep 2
fi
echo ""

# Clean lock files
echo "[3/5] Cleaning lock files..."
ssh -i $SSH_KEY $VPS "rm -f $LOCK_DIR/*.lock && echo 'Locks cleaned'"
echo "OK - Lock files cleaned"
echo ""

# Restart bot
echo "[4/5] Starting bot..."
ssh -i $SSH_KEY $VPS "cd $JARVIS_PATH && nohup $VENV_BIN -m tg_bot.bot >> $LOG_FILE 2>&1 &"
sleep 3

# Verify bot started
echo "[5/5] Verifying bot status..."
BOT_PID=$(ssh -i $SSH_KEY $VPS "ps aux | grep -i 'tg_bot.bot' | grep -v grep | awk '{print \$2}'" || echo "")

if [ -z "$BOT_PID" ]; then
    echo "ERROR: Bot failed to start"
    echo "Check logs:"
    ssh -i $SSH_KEY $VPS "tail -20 $LOG_FILE" || true
    exit 1
fi

echo "OK - Bot started (PID: $BOT_PID)"
echo ""

# Show recent logs
echo "============================================"
echo "Recent bot logs:"
echo "============================================"
ssh -i $SSH_KEY $VPS "tail -10 $LOG_FILE"
echo ""

echo "============================================"
echo "SUCCESS - Bot recovery complete!"
echo "============================================"
echo ""
echo "Next steps:"
echo "  1. Check bot in Telegram: @Jarviskr8tivbot"
echo "  2. Send test question: 'Is SOL bullish?'"
echo "  3. Monitor logs: tail -f $LOG_FILE | grep -i dexter"
echo ""
