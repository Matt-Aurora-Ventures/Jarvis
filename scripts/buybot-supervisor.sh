#!/bin/bash
# Buy Bot Supervisor (ClawdJarvis) - container-safe

set -e

ROOT_DIR="/root/clawd/Jarvis"
BOT_DIR="$ROOT_DIR/bots/buy_tracker"
TG_VENV="$ROOT_DIR/tg_bot/.venv"
LOG_DIR="$BOT_DIR/logs"
PID_FILE="$BOT_DIR/buybot.pid"
OUT_LOG="$LOG_DIR/buybot.out.log"
ERR_LOG="$LOG_DIR/buybot.err.log"

mkdir -p "$LOG_DIR"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"; }

status() {
  if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
      log "Buy bot running (PID: $PID)"
      return 0
    fi
  fi
  return 1
}

stop() {
  log "Stopping buy bot..."
  if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    kill "$PID" 2>/dev/null || true
    sleep 2
    kill -9 "$PID" 2>/dev/null || true
    rm -f "$PID_FILE"
  fi
  pkill -f "bots.buy_tracker.bot" 2>/dev/null || true
  pkill -f "buy_tracker/bot.py" 2>/dev/null || true
  log "Buy bot stopped"
}

start() {
  if status >/dev/null 2>&1; then
    log "Buy bot already running"
    return 0
  fi

  stop || true

  # Load ClawdJarvis token from local secrets (DO NOT print)
  # Prefer jarvis-keys.json -> telegram_bots.clawdjarvis (known-good)
  if [ -f "/root/clawd/secrets/jarvis-keys.json" ]; then
    TELEGRAM_BUY_BOT_TOKEN=$(jq -r '.telegram_bots.clawdjarvis // empty' /root/clawd/secrets/jarvis-keys.json 2>/dev/null || true)
    export TELEGRAM_BUY_BOT_TOKEN
  fi

  # Fallback: keys.json -> telegram.clawdjarvis_token
  if [ -z "$TELEGRAM_BUY_BOT_TOKEN" ] && [ -f "/root/clawd/secrets/keys.json" ]; then
    TELEGRAM_BUY_BOT_TOKEN=$(jq -r '.telegram.clawdjarvis_token // empty' /root/clawd/secrets/keys.json 2>/dev/null || true)
    export TELEGRAM_BUY_BOT_TOKEN
  fi

  if [ -z "$TELEGRAM_BUY_BOT_TOKEN" ]; then
    log "ERROR: TELEGRAM_BUY_BOT_TOKEN not configured (secrets/keys.json telegram.clawdjarvis_token missing)"
    return 1
  fi

  export BUY_BOT_ENABLE_POLLING=auto

  log "Starting buy bot (ClawdJarvis)..."
  cd "$ROOT_DIR"

  "$TG_VENV/bin/python" -u -m bots.buy_tracker.bot >>"$OUT_LOG" 2>>"$ERR_LOG" &
  echo $! > "$PID_FILE"
  sleep 1
  log "Buy bot started (PID: $(cat "$PID_FILE"))"
}

case "${1:-status}" in
  start) start ;;
  stop) stop ;;
  restart) stop; start ;;
  status) if status; then exit 0; else log "Buy bot not running"; exit 1; fi ;;
  *) echo "Usage: $0 {start|stop|restart|status}"; exit 2 ;;
esac
