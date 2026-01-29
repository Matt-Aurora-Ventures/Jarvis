#!/bin/bash
# CHOKIDAR FILE WATCHER FIX
# Critical Finding: Config reloader watches file, detects config.patch write,
# immediately triggers SIGUSR1 BEFORE patch's restartDelayMs fires

set -e

echo "============================================"
echo "CHOKIDAR FILE WATCHER FIX"
echo "============================================"
echo ""
echo "Issue: Dual restart (reloader + patch delay)"
echo "Solution: Stop gateway, write config, restart"
echo ""

GATEWAY_URL="ws://100.66.17.93:18789"
CONFIG_FILE="$HOME/.clawdbot/clawdbot.json"

# Validate env vars
if [ -z "$FRIDAY_CHAT_ID" ] || [ -z "$JARVIS_CHAT_ID" ] || [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "❌ ERROR: Missing environment variables"
    echo "Required:"
    echo "  export FRIDAY_CHAT_ID=<id>"
    echo "  export JARVIS_CHAT_ID=<id>"
    echo "  export TELEGRAM_BOT_TOKEN=<token>"
    exit 1
fi

echo "Environment variables validated ✓"
echo ""

# Backup current config
echo "Step 1: Backing up current config..."
cp "$CONFIG_FILE" "$CONFIG_FILE.backup_$(date +%s)"
echo "  Backup saved ✓"
echo ""

# Get current config via RPC (while gateway is still running)
echo "Step 2: Getting current config via RPC..."
clawdbot gateway call config.get --params '{}' --url "$GATEWAY_URL" | jq '.config' > /tmp/current_config.json

if [ ! -s /tmp/current_config.json ]; then
    echo "❌ ERROR: Failed to get config from gateway"
    exit 1
fi

echo "  Config retrieved ✓"
echo ""

# Merge accounts into config
echo "Step 3: Merging accounts into config..."
jq --arg friday_id "$FRIDAY_CHAT_ID" \
   --arg jarvis_id "$JARVIS_CHAT_ID" \
   --arg token "$TELEGRAM_BOT_TOKEN" \
   '. + {
  "gateway": {
    "bind": "loopback",
    "trustedProxies": ["100.0.0.0/8"],
    "pluginAutoEnable": false
  },
  "tailscale": {
    "mode": "serve"
  },
  "accounts": {
    "friday": {
      "type": "telegram",
      "chatId": $friday_id,
      "token": $token
    },
    "jarvis": {
      "type": "telegram",
      "chatId": $jarvis_id,
      "token": $token
    }
  },
  "agents": {
    "list": ["main", "friday", "jarvis"]
  },
  "configWrites": false
}' /tmp/current_config.json > /tmp/new_config.json

echo "  Accounts merged ✓"
echo ""

# Show preview
echo "Preview of new accounts:"
jq '.accounts | keys' /tmp/new_config.json
echo ""

# THE FIX: Stop gateway, write, let supervisor restart
echo "Step 4: Applying atomic fix..."
echo "  - Killing gateway process..."

# Kill gateway (supervisor will restart it)
pkill -9 -f clawdbot-gateway

# IMMEDIATELY write new config (before supervisor restarts gateway)
echo "  - Writing new config..."
cat /tmp/new_config.json > "$CONFIG_FILE"

echo "  - Waiting for supervisor to restart gateway..."
sleep 3

# Wait for gateway to be fully up
RETRY=0
while [ $RETRY -lt 10 ]; do
    if clawdbot gateway call config.get --params '{}' --url "$GATEWAY_URL" &>/dev/null; then
        echo "  - Gateway is up ✓"
        break
    fi
    RETRY=$((RETRY + 1))
    sleep 1
done

if [ $RETRY -eq 10 ]; then
    echo "❌ ERROR: Gateway did not come back up"
    echo "Check supervisor logs"
    exit 1
fi

echo ""

# Verify accounts
echo "Step 5: Verifying accounts..."
ACCOUNTS=$(clawdbot gateway call config.get --params '{}' --url "$GATEWAY_URL" | jq -r '.config.accounts | keys | join(", ")')

echo "  Accounts in gateway: $ACCOUNTS"
echo ""

if echo "$ACCOUNTS" | grep -q "friday" && echo "$ACCOUNTS" | grep -q "jarvis"; then
    echo "✅ SUCCESS: Accounts persisted!"
else
    echo "❌ FAILED: Accounts not found"
    echo "Debugging info:"
    echo "  Config file size: $(wc -c < "$CONFIG_FILE") bytes"
    echo "  Gateway response:"
    clawdbot gateway call config.get --params '{}' --url "$GATEWAY_URL" | jq '.config.accounts'
    exit 1
fi

echo ""

# Make config immutable to prevent future overwrites
echo "Step 6: Locking config file..."
chattr +i "$CONFIG_FILE"
echo "  Config is now immutable ✓"
echo ""

echo "============================================"
echo "✅ FIX COMPLETE"
echo "============================================"
echo ""
echo "Accounts configured:"
echo "  - friday (Chat ID: $FRIDAY_CHAT_ID)"
echo "  - jarvis (Chat ID: $JARVIS_CHAT_ID)"
echo ""
echo "Config is locked with chattr +i"
echo "To make changes later: chattr -i $CONFIG_FILE"
echo ""

# Test restart persistence
echo "Step 7: Testing restart persistence..."
echo "  Triggering restart..."
pkill -SIGUSR1 -f clawdbot-gateway
sleep 5

echo "  Checking accounts after restart..."
ACCOUNTS_AFTER=$(clawdbot gateway call config.get --params '{}' --url "$GATEWAY_URL" | jq -r '.config.accounts | keys | join(", ")')
echo "  Accounts: $ACCOUNTS_AFTER"

if echo "$ACCOUNTS_AFTER" | grep -q "friday" && echo "$ACCOUNTS_AFTER" | grep -q "jarvis"; then
    echo "  ✅ Accounts survived restart!"
else
    echo "  ⚠️  Accounts lost after restart"
    echo "  The immutable flag should prevent this - check chattr status"
    lsattr "$CONFIG_FILE"
fi

echo ""
echo "DONE"
