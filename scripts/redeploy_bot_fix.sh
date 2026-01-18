#!/bin/bash
# Quick redeployment of Telegram bot with lock fix
# Run on VPS: bash scripts/redeploy_bot_fix.sh

set -e

echo "═════════════════════════════════════════════"
echo "  JARVIS BOT REDEPLOYMENT - LOCK FIX"
echo "═════════════════════════════════════════════"
echo ""

BOT_DIR="/home/jarvis/Jarvis"
LOCK_FILE="/tmp/jarvis_bot.lock"
LOG_FILE="$BOT_DIR/logs/tg_bot.log"

# Step 1: Kill existing bot processes
echo "Step 1: Killing existing bot processes..."
pkill -9 -f "tg_bot.bot" 2>/dev/null || true
pkill -9 -f "bot.py" 2>/dev/null || true
sleep 2
echo "✓ Existing processes killed"
echo ""

# Step 2: Clean lock file
echo "Step 2: Cleaning lock file..."
rm -f "$LOCK_FILE"
echo "✓ Lock file removed"
echo ""

# Step 3: Pull latest code
echo "Step 3: Pulling latest code from GitHub..."
cd "$BOT_DIR"
git pull origin main
echo "✓ Latest code pulled"
echo ""

# Step 4: Verify new code is there
echo "Step 4: Verifying new bot.py has lock fix..."
if grep -q "max_wait_time = 30" tg_bot/bot.py; then
    echo "✓ Lock fix verified in bot.py"
else
    echo "✗ ERROR: Lock fix not found in bot.py!"
    exit 1
fi
echo ""

# Step 5: Start the bot
echo "Step 5: Starting bot with new lock logic..."
mkdir -p "$(dirname "$LOG_FILE")"

# Run bot in background
nohup /home/jarvis/Jarvis/venv/bin/python -m tg_bot.bot >> "$LOG_FILE" 2>&1 &
BOT_PID=$!
sleep 3

echo "✓ Bot started with PID: $BOT_PID"
echo ""

# Step 6: Verify bot acquired lock
echo "Step 6: Verifying bot acquired lock..."
if [ -f "$LOCK_FILE" ]; then
    LOCKED_PID=$(cat "$LOCK_FILE" 2>/dev/null)
    echo "✓ Lock file created with PID: $LOCKED_PID"
else
    echo "⚠ WARNING: Lock file not yet created (may take a moment)"
fi
echo ""

# Step 7: Check for Conflict errors
echo "Step 7: Checking logs for Conflict errors..."
CONFLICT_COUNT=$(grep -c "Conflict:" "$LOG_FILE" 2>/dev/null || echo "0")
if [ "$CONFLICT_COUNT" -gt "0" ]; then
    echo "⚠ WARNING: Found $CONFLICT_COUNT Conflict errors in logs"
    echo "   This may indicate multiple bots still polling"
    echo ""
    echo "Recent log entries:"
    tail -20 "$LOG_FILE"
else
    echo "✓ No Conflict errors found!"
fi
echo ""

# Step 8: Final status
echo "═════════════════════════════════════════════"
echo "  REDEPLOYMENT COMPLETE"
echo "═════════════════════════════════════════════"
echo ""
echo "Bot Status:"
echo "  PID: $BOT_PID"
echo "  Lock: $LOCK_FILE"
echo "  Logs: $LOG_FILE"
echo ""
echo "Next steps:"
echo "  1. Monitor logs: tail -f $LOG_FILE"
echo "  2. Send test message to @Jarviskr8tivbot"
echo "  3. Check for Conflict errors"
echo ""
