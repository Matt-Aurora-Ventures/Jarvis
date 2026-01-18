#!/bin/bash
#
# Run Telegram bot with single instance guarantee
# This ensures only ONE bot polls Telegram at a time
#

set -e

BOT_DIR="/home/jarvis/Jarvis"
VENV="$BOT_DIR/venv/bin/python3"
LOCK_DIR="$BOT_DIR/data/locks"
LOG_FILE="$BOT_DIR/logs/tg_bot.log"

TOKEN=""
if [ -f "$BOT_DIR/.env" ]; then
    TOKEN=$(grep -E '^TELEGRAM_BOT_TOKEN=' "$BOT_DIR/.env" | head -n1 | cut -d= -f2-)
fi
TOKEN="${TOKEN%\"}"
TOKEN="${TOKEN#\"}"
TOKEN="${TOKEN%\'}"
TOKEN="${TOKEN#\'}"

if [ -n "$TOKEN" ]; then
    if command -v sha256sum >/dev/null 2>&1; then
        TOKEN_HASH=$(printf "%s" "$TOKEN" | sha256sum | cut -c1-12)
    else
        TOKEN_HASH=$(TOKEN="$TOKEN" "$VENV" - <<'PY'
import hashlib
import os
token = os.environ.get("TOKEN", "")
print(hashlib.sha256(token.encode("utf-8")).hexdigest()[:12] if token else "no-token")
PY
)
    fi
else
    TOKEN_HASH="no-token"
fi

LOCK_FILE="$LOCK_DIR/telegram_polling_${TOKEN_HASH}.lock"

echo "═══════════════════════════════════════"
echo "  JARVIS TELEGRAM BOT - SINGLE INSTANCE"
echo "═══════════════════════════════════════"
echo ""

# Function to cleanup lock file on exit
cleanup() {
    rm -f "$LOCK_FILE"
    echo "Bot stopped. Lock file removed."
}

trap cleanup EXIT

# Check for existing instance
if [ -f "$LOCK_FILE" ]; then
    OLD_PID=$(cat "$LOCK_FILE" 2>/dev/null || echo "")
    if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        echo "ERROR: Bot already running (PID: $OLD_PID)"
        echo "Stop existing instance first: kill -9 $OLD_PID"
        exit 1
    fi
fi

# Kill any stray bot processes
echo "Cleaning up any stray processes..."
pkill -9 -f "tg_bot.bot" 2>/dev/null || true
pkill -9 -f "bot.py" 2>/dev/null || true
sleep 2

# Create lock file with PID of this script
echo "Creating lock file..."
    mkdir -p "$LOCK_DIR"
echo $$ > "$LOCK_FILE"

# Clear old logs and start fresh
echo "Starting bot..."
mkdir -p "$(dirname "$LOG_FILE")"
: > "$LOG_FILE"  # Clear log file

# Run bot (this will block until bot exits)
cd "$BOT_DIR"
$VENV -m tg_bot.bot >> "$LOG_FILE" 2>&1 &
BOT_PID=$!

# Store PID
echo $BOT_PID > "$LOCK_FILE"

echo "Bot started with PID: $BOT_PID"
echo "Logs: $LOG_FILE"
echo ""
echo "Monitoring bot process..."
echo "Press Ctrl+C to stop"
echo ""

# Wait for bot process
wait $BOT_PID || true

echo "Bot process exited"
