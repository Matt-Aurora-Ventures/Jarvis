#!/bin/bash
# Jarvis Bot Supervisor
# Manages single-instance execution with proper cleanup and restart

set -euo pipefail

BOT_DIR="/root/clawd/Jarvis/tg_bot"
RUN_DIR="$BOT_DIR/run"
LOG_DIR="$BOT_DIR/logs"
PID_FILE="$RUN_DIR/jarvis.pid"
LOCK_FILE="$RUN_DIR/supervisor.lock"
VENV="$BOT_DIR/.venv/bin/python"

# Create directories
mkdir -p "$RUN_DIR" "$LOG_DIR"

# Exclusive lock on supervisor itself (prevents multiple supervisors)
exec 200>"$LOCK_FILE"
if ! flock -n 200; then
    echo "ERROR: Another supervisor is already running"
    exit 1
fi

# Cleanup function
cleanup() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Supervisor shutting down..."
    if [[ -f "$PID_FILE" ]]; then
        BOT_PID=$(cat "$PID_FILE")
        if kill -0 "$BOT_PID" 2>/dev/null; then
            echo "Stopping bot (PID $BOT_PID)..."
            kill -TERM "$BOT_PID" 2>/dev/null || true
            sleep 2
            kill -KILL "$BOT_PID" 2>/dev/null || true
        fi
        rm -f "$PID_FILE"
    fi
    rm -f /root/.local/state/jarvis/locks/*.lock 2>/dev/null || true
    exit 0
}

trap cleanup SIGTERM SIGINT SIGHUP EXIT

# Load environment
if [[ -f "$BOT_DIR/.env" ]]; then
    set -a
    source "$BOT_DIR/.env"
    set +a
fi

# IMPORTANT: Do NOT set SKIP_TELEGRAM_LOCK - let the bot acquire its own lock!
unset SKIP_TELEGRAM_LOCK

export PYTHONUNBUFFERED=1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Jarvis Supervisor started"
echo "Bot directory: $BOT_DIR"
echo "Log file: $LOG_DIR/jarvis.log"

# Main loop - restart on crash
RESTART_COUNT=0
MAX_RESTARTS_PER_HOUR=5
LAST_RESTART_HOUR=""

while true; do
    CURRENT_HOUR=$(date '+%Y-%m-%d-%H')
    
    # Reset counter on new hour
    if [[ "$CURRENT_HOUR" != "$LAST_RESTART_HOUR" ]]; then
        RESTART_COUNT=0
        LAST_RESTART_HOUR="$CURRENT_HOUR"
    fi
    
    # Check restart limit
    if [[ $RESTART_COUNT -ge $MAX_RESTARTS_PER_HOUR ]]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: Too many restarts ($RESTART_COUNT) this hour. Backing off..."
        sleep 300  # 5 minute cooldown
        RESTART_COUNT=0
    fi
    
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting Jarvis bot (restart #$RESTART_COUNT this hour)..."
    
    cd /root/clawd/Jarvis
    
    # Start bot in background
    $VENV -u -m tg_bot.bot >> "$LOG_DIR/jarvis.log" 2>&1 &
    BOT_PID=$!
    echo $BOT_PID > "$PID_FILE"
    
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Bot started with PID $BOT_PID"
    
    # Wait for bot to exit
    wait $BOT_PID || true
    EXIT_CODE=$?
    
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Bot exited with code $EXIT_CODE"
    rm -f "$PID_FILE"
    
    # Clean up lock files for clean restart
    rm -f /root/.local/state/jarvis/locks/*.lock 2>/dev/null || true
    
    RESTART_COUNT=$((RESTART_COUNT + 1))
    
    # Brief pause before restart
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Waiting 5 seconds before restart..."
    sleep 5
done
