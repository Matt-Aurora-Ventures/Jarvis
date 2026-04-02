#!/bin/bash
set -e

PROFILE="${CLAWDBOT_PROFILE:-main}"
PORT="${GATEWAY_PORT:-18789}"

echo "[$PROFILE] Installing clawdbot..."
npm install -g clawdbot@latest 2>&1 | tail -3

if [ "$INSTALL_CODEX" = "true" ]; then
  echo "[$PROFILE] Installing codex CLI..."
  npm install -g @openai/codex 2>&1 | tail -3
fi

echo "[$PROFILE] Writing config to /root/.clawdbot/clawdbot.json..."
mkdir -p /root/.clawdbot

# Config is written by the setup script, just verify it exists
if [ ! -f /root/.clawdbot/clawdbot.json ]; then
  echo "[$PROFILE] ERROR: No config found at /root/.clawdbot/clawdbot.json"
  exit 1
fi

echo "[$PROFILE] Starting gateway on port $PORT..."
exec clawdbot gateway --profile "$PROFILE" --bind 0.0.0.0
