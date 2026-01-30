#!/bin/bash
# Jarvis Bot Supervisor - Container-safe (no systemd, handles clawdbot PID 1)
# Prevents zombie processes by using exec and proper cleanup

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOT_DIR="/root/clawd/Jarvis/tg_bot"
VENV="$BOT_DIR/.venv"
LOG_DIR="$BOT_DIR/logs"
PID_FILE="$BOT_DIR/jarvis.pid"
LOG_FILE="$LOG_DIR/jarvis.log"

mkdir -p "$LOG_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
}

# Kill ALL jarvis-related processes
kill_all_jarvis() {
    log "Stopping all Jarvis processes..."
    
    # Kill by PID file first
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID" 2>/dev/null || true
            sleep 1
            kill -9 "$PID" 2>/dev/null || true
        fi
        rm -f "$PID_FILE"
    fi
    
    # Kill any remaining tg_bot processes
    pkill -f "tg_bot.bot" 2>/dev/null || true
    pkill -f "python.*tg_bot" 2>/dev/null || true
    
    # Give processes time to die
    sleep 2
    
    # Force kill if still running
    pkill -9 -f "tg_bot.bot" 2>/dev/null || true
    
    log "All Jarvis processes stopped"
}

# Check if bot is running
status() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            log "Jarvis bot is running (PID: $PID)"
            return 0
        else
            warn "PID file exists but process $PID is not running"
            rm -f "$PID_FILE"
            return 1
        fi
    fi
    
    # Check for orphan processes
    ORPHAN_PID=$(pgrep -f "tg_bot.bot" | head -1)
    if [ -n "$ORPHAN_PID" ]; then
        warn "Found orphan Jarvis process (PID: $ORPHAN_PID)"
        return 0
    fi
    
    error "Jarvis bot is not running"
    return 1
}

# Start Redis if not running
ensure_redis() {
    if ! redis-cli ping >/dev/null 2>&1; then
        log "Starting Redis..."
        redis-server --daemonize yes
        sleep 1
        if redis-cli ping >/dev/null 2>&1; then
            log "Redis started successfully"
        else
            error "Failed to start Redis"
            return 1
        fi
    else
        log "Redis already running"
    fi
}

# Start the bot
start() {
    # Check if already running
    if status >/dev/null 2>&1; then
        warn "Jarvis bot is already running"
        return 0
    fi
    
    # Ensure Redis is up
    ensure_redis || return 1
    
    # Kill any orphans first
    kill_all_jarvis
    
    log "Starting Jarvis bot..."
    
    # Must run from parent of tg_bot for module resolution
    cd /root/clawd/Jarvis
    
    # Activate venv and start with nohup (not exec, so we can get PID)
    # Using exec would replace this shell, making PID tracking impossible
    source "$VENV/bin/activate"
    
    # Set PYTHONPATH to ensure tg_bot module is found
    export PYTHONPATH="/root/clawd/Jarvis:$PYTHONPATH"
    
    nohup python -u -m tg_bot.bot >> "$LOG_FILE" 2>&1 &
    BOT_PID=$!
    
    echo "$BOT_PID" > "$PID_FILE"
    
    # Wait a moment and verify it's running
    sleep 3
    
    if kill -0 "$BOT_PID" 2>/dev/null; then
        log "Jarvis bot started successfully (PID: $BOT_PID)"
        log "Logs: tail -f $LOG_FILE"
        return 0
    else
        error "Jarvis bot failed to start - check $LOG_FILE"
        rm -f "$PID_FILE"
        return 1
    fi
}

# Stop the bot
stop() {
    kill_all_jarvis
}

# Restart
restart() {
    log "Restarting Jarvis bot..."
    stop
    sleep 2
    start
}

# View logs
logs() {
    LINES=${1:-100}
    tail -n "$LINES" "$LOG_FILE"
}

# Follow logs
follow() {
    tail -f "$LOG_FILE"
}

# Main command router
case "${1:-status}" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    status)
        status
        ;;
    logs)
        logs "${2:-100}"
        ;;
    follow)
        follow
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs [lines]|follow}"
        echo ""
        echo "Commands:"
        echo "  start   - Start Jarvis bot (starts Redis if needed)"
        echo "  stop    - Stop Jarvis bot"
        echo "  restart - Restart Jarvis bot"
        echo "  status  - Check if bot is running"
        echo "  logs    - View last N log lines (default: 100)"
        echo "  follow  - Follow log output in real-time"
        exit 1
        ;;
esac
