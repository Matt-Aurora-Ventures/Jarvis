#!/bin/bash
# Jarvis Container Startup Script - CTO/CFO (Grok 4.1)

set -e

echo "[Jarvis] Starting ClawdJarvis - CTO/CFO..."

# Install dependencies quietly
apt-get update -qq 2>/dev/null
apt-get install -y -qq git curl procps jq >/dev/null 2>&1

# Clean up stale npm artifacts
rm -rf /usr/local/lib/node_modules/.clawdbot* 2>/dev/null || true

# Install/update clawdbot
echo "[Jarvis] Installing clawdbot..."
npm install -g clawdbot@latest 2>&1 | tail -5

# Ensure clawdbot is in PATH
if ! which clawdbot >/dev/null 2>&1; then
    echo "[Jarvis] Creating clawdbot symlink..."
    ln -sf /usr/local/lib/node_modules/clawdbot/dist/entry.js /usr/local/bin/clawdbot
fi

# Ensure memory directory exists
mkdir -p /root/clawd/memory

# Load shared context if available
if [ -f /root/clawd/shared-context.json ]; then
    echo "[Jarvis] Loaded shared context"
fi

# Write daily memory marker
MEMORY_FILE="/root/clawd/memory/$(date +%Y-%m-%d).md"
if [ ! -f "$MEMORY_FILE" ]; then
    cat > "$MEMORY_FILE" << 'MEMORY'
# Jarvis Daily Memory

## Startup
- Container started fresh
- Will load context from Telegram history (last 300 messages)

## Role
CTO/CFO - Technical decisions and financial analysis

## Team
- Friday (CMO): Marketing via Claude Opus 4.5
- Matt (COO): Operations via Codex/GPT 5.2
- Jarvis (self): CTO/CFO via Grok 4.1

## Notes
(Add important decisions and context here throughout the day)
MEMORY
fi

echo "[Jarvis] Starting gateway on port 18789 (mapped to 18801 externally)..."
exec clawdbot gateway --profile jarvis --bind 0.0.0.0
