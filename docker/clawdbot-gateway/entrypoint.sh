#!/bin/bash
set -e

PROFILE="${CLAWDBOT_PROFILE:-main}"
PORT="${GATEWAY_PORT:-18789}"

echo "[$PROFILE] Installing clawdbot..."
npm install -g clawdbot@latest 2>&1 | tail -3

if [ "$INSTALL_CODEX" = "true" ]; then
  echo "[$PROFILE] Installing codex CLI..."
  npm install -g @openai/codex 2>&1 | tail -3

  # Resolve npm global bin deterministically for slim containers where PATH may drift.
  NPM_PREFIX="$(npm config get prefix)"
  CODEX_BIN="$NPM_PREFIX/bin/codex"
  if [ -x "$CODEX_BIN" ] && [ ! -x /usr/local/bin/codex ]; then
    ln -sf "$CODEX_BIN" /usr/local/bin/codex || true
  fi

  if command -v codex >/dev/null 2>&1; then
    echo "[$PROFILE] codex available: $(codex --version 2>/dev/null || echo installed)"
  else
    echo "[$PROFILE] WARNING: codex not on PATH, runtime should use fallback: npx --yes @openai/codex"
  fi
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
