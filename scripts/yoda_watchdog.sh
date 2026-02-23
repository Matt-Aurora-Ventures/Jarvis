#!/usr/bin/env bash
set -euo pipefail

# Yoda Watchdog (Hetzner)
# Purpose: external health monitoring + safe recovery for the KVM4 hub bots.
#
# Non-destructive: only restarts the specific unhealthy container(s).
# Requires:
# - curl
# - SSH key with access to the KVM4 host for docker restarts
#
# Env:
# - HEALTH_URL (default: http://76.13.106.100:18888/health)
# - KVM4_SSH_HOST (default: 76.13.106.100)
# - KVM4_SSH_KEY (default: /root/yoda-watchdog/id_ed25519)
# - TELEGRAM_CHAT_ID (default: -5003286623)
# - YODA_TELEGRAM_TOKEN (required for alerts; if missing, alerts are skipped)
# - RESTART_TARGETS (default: "clawdbot-friday clawdbot-matt clawdbot-jarvis")

LOCK_FILE="${LOCK_FILE:-/var/lock/yoda-watchdog.lock}"
HEALTH_URL="${HEALTH_URL:-http://76.13.106.100:18888/health}"
KVM4_SSH_HOST="${KVM4_SSH_HOST:-76.13.106.100}"
KVM4_SSH_KEY="${KVM4_SSH_KEY:-/root/yoda-watchdog/id_ed25519}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:--5003286623}"
YODA_TELEGRAM_TOKEN="${YODA_TELEGRAM_TOKEN:-}"
RESTART_TARGETS="${RESTART_TARGETS:-clawdbot-friday clawdbot-matt clawdbot-jarvis}"

mkdir -p "$(dirname "$LOCK_FILE")" || true

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  exit 0
fi

ts() { date -Is; }

send_telegram() {
  local text="$1"
  if [[ -z "$YODA_TELEGRAM_TOKEN" ]]; then
    return 0
  fi
  # Best-effort; never fail watchdog because Telegram is down.
  curl -fsS --max-time 10 \
    -X POST "https://api.telegram.org/bot${YODA_TELEGRAM_TOKEN}/sendMessage" \
    -d "chat_id=${TELEGRAM_CHAT_ID}" \
    --data-urlencode "text=${text}" >/dev/null 2>&1 || true
}

health_json="$(curl -fsS --max-time 8 "$HEALTH_URL" 2>/dev/null || true)"

if [[ -z "$health_json" ]]; then
  send_telegram "🧙 Yoda Watchdog: health endpoint DOWN at $(ts). Attempting recovery on ${KVM4_SSH_HOST}."
  ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 -i "$KVM4_SSH_KEY" "root@${KVM4_SSH_HOST}" \
    "docker restart ${RESTART_TARGETS} >/dev/null 2>&1 || true"
  exit 0
fi

# Parse health JSON without jq (keep dependency footprint small).
python3 - <<'PY' "$health_json" "$KVM4_SSH_HOST" "$KVM4_SSH_KEY" "$RESTART_TARGETS" "$HEALTH_URL" "$TELEGRAM_CHAT_ID" "$YODA_TELEGRAM_TOKEN"
import json, os, sys, subprocess, datetime

health_json = sys.argv[1]
kvm4_host = sys.argv[2]
kvm4_key = sys.argv[3]
restart_targets = sys.argv[4].split()
health_url = sys.argv[5]
chat_id = sys.argv[6]
yoda_token = sys.argv[7]

def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")

def send_telegram(msg: str) -> None:
    if not yoda_token:
        return
    try:
        subprocess.run(
            [
                "curl",
                "-fsS",
                "--max-time",
                "10",
                "-X",
                "POST",
                f"https://api.telegram.org/bot{yoda_token}/sendMessage",
                "-d",
                f"chat_id={chat_id}",
                "--data-urlencode",
                f"text={msg}",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except Exception:
        pass

try:
    data = json.loads(health_json)
except Exception:
    send_telegram(f"🧙 Yoda Watchdog: invalid health JSON at {now()} from {health_url}. Restarting {restart_targets}.")
    subprocess.run(
        ["ssh", "-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=10", "-i", kvm4_key, f"root@{kvm4_host}",
         "docker", "restart", *restart_targets],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    sys.exit(0)

status = data.get("status")
bots = data.get("bots") or {}

unhealthy = []
for name in ("friday", "matt", "jarvis"):
    s = bots.get(name)
    if s and s != "healthy":
        unhealthy.append(name)

if status != "healthy" or unhealthy:
    targets = []
    for n in unhealthy:
        targets.append(f"clawdbot-{n}")
    if not targets:
        targets = restart_targets

    send_telegram(f"🧙 Yoda Watchdog: unhealthy={unhealthy or status} at {now()}. Restarting: {targets}")
    subprocess.run(
        ["ssh", "-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=10", "-i", kvm4_key, f"root@{kvm4_host}",
         "docker", "restart", *targets],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
PY
