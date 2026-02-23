#!/usr/bin/env bash
set -euo pipefail

# Fix Squishy's Clawdbot config schema issues and ensure it's not using Gemini.
# Intended to run on the Squishy Mac host (via SSH).

export PATH="/usr/local/bin:/usr/bin:/bin:${PATH:-}"

CFG="${HOME}/.clawdbot/clawdbot.json"
LOG_DIR="${HOME}/.clawdbot/logs"
RUNTIME_LOG="${LOG_DIR}/gateway.squishy.runtime.log"

# Homebrew on Apple Silicon installs to /opt/homebrew/bin; include it for jq.
export PATH="/opt/homebrew/bin:${PATH}"

if ! command -v clawdbot >/dev/null 2>&1; then
  echo "[fix_squishy] ERROR: clawdbot not found on PATH"
  exit 1
fi

if [ ! -f "$CFG" ]; then
  echo "[fix_squishy] ERROR: missing config: $CFG"
  exit 1
fi

mkdir -p "$LOG_DIR"

ts="$(date -u +%Y%m%dT%H%M%SZ)"
cp -a "$CFG" "${CFG}.bak.${ts}"

# Patch config:
# - remove unsupported key `channels.telegram.allowGroups`
# - switch model to Anthropic (no Gemini)
# - set DM policy to pairing (safe default)
#
# Prefer jq if available; fall back to python3 so we don't hard-depend on jq.
if command -v jq >/dev/null 2>&1; then
  jq '
    del(.channels.telegram.allowGroups)
    | .channels.telegram.dmPolicy = "pairing"
    # Mac is currently on an older Clawdbot build that does not know about 4.6.
    # Use the newest supported Opus alias in that build.
    | .agents.defaults.model.primary = "anthropic/claude-opus-4-5"
  ' "$CFG" > "${CFG}.tmp"
  mv "${CFG}.tmp" "$CFG"
else
  if ! command -v python3 >/dev/null 2>&1; then
    echo "[fix_squishy] ERROR: neither jq nor python3 is available to patch JSON"
    exit 1
  fi
  python3 - <<'PY'
import json
from pathlib import Path

cfg = Path.home() / ".clawdbot" / "clawdbot.json"
d = json.loads(cfg.read_text())

channels = d.setdefault("channels", {})
tg = channels.setdefault("telegram", {})
tg.pop("allowGroups", None)
tg["dmPolicy"] = "pairing"

agents = d.setdefault("agents", {})
defaults = agents.setdefault("defaults", {})
model = defaults.setdefault("model", {})
model["primary"] = "anthropic/claude-opus-4-5"

cfg.write_text(json.dumps(d, indent=2, sort_keys=False) + "\n")
PY
fi

echo "[fix_squishy] Patched config: ${CFG} (backup ${CFG}.bak.${ts})"

# Stop any existing gateway.
pkill -f "clawdbot gateway" >/dev/null 2>&1 || true

# Start gateway in background. This will stay running.
# Bind to loopback to avoid requiring gateway auth tokens.
nohup clawdbot gateway --profile squishy --port 18793 --bind loopback >"$RUNTIME_LOG" 2>&1 &

sleep 2
echo "[fix_squishy] Gateway process:"
pgrep -af "clawdbot gateway" || true

echo "[fix_squishy] Tail log: $RUNTIME_LOG"
tail -n 60 "$RUNTIME_LOG" || true
