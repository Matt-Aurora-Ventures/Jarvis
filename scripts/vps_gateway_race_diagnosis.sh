#!/bin/bash
# Gateway Config Race Condition Diagnostic
# Container Environment - PID 1 supervisor, auto-restart gateway

set -e

echo "============================================"
echo "GATEWAY CONFIG RACE CONDITION DIAGNOSTIC"
echo "============================================"
echo ""
echo "Environment: Container with PID 1 supervisor"
echo "Issue: Config stripped during restart"
echo "Goal: Identify what overwrites config file"
echo ""

# Configuration
GATEWAY_URL="ws://100.66.17.93:18789"  # Adjust to actual Tailscale IP
CONFIG_FILE="$HOME/.clawdbot/clawdbot.json"
LOG_DIR="/tmp/gateway_diagnostic_$(date +%Y%m%d_%H%M%S)"

mkdir -p "$LOG_DIR"
echo "Logs: $LOG_DIR"
echo ""

# Phase 1: Setup monitoring
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "PHASE 1: SETUP FILE MONITORING"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if inotifywait is available
if ! command -v inotifywait &> /dev/null; then
    echo "Installing inotify-tools..."
    apt-get update && apt-get install -y inotify-tools
fi

# Start file watcher in background
echo "Starting file watcher..."
inotifywait -m -e modify,create,delete,move,close_write "$CONFIG_FILE" 2>&1 | while read -r event; do
    SIZE=$(wc -c < "$CONFIG_FILE" 2>/dev/null || echo "0")
    echo "$(date +%H:%M:%S.%3N) | Event: $event | Size: $SIZE bytes" | tee -a "$LOG_DIR/file_events.log"
done &
WATCHER_PID=$!

echo "File watcher started (PID: $WATCHER_PID)"
sleep 2

# Phase 2: Baseline measurement
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "PHASE 2: BASELINE MEASUREMENT"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "Current config size: $(wc -c < "$CONFIG_FILE") bytes"
echo "Gateway process: $(pgrep -f clawdbot-gateway || echo 'NOT RUNNING')"
echo "Supervisor (PID 1): $(ps -p 1 -o comm=)"
echo ""

# Get initial hash
echo "Getting current config hash..."
INITIAL_HASH=$(clawdbot gateway call config.get --params '{}' --url "$GATEWAY_URL" 2>/dev/null | jq -r '.hash' || echo "FAILED")

if [ "$INITIAL_HASH" = "FAILED" ]; then
    echo "❌ Cannot connect to gateway at $GATEWAY_URL"
    echo "Check gateway is running and URL is correct"
    kill $WATCHER_PID 2>/dev/null
    exit 1
fi

echo "Initial hash: $INITIAL_HASH"
echo "Initial accounts: $(clawdbot gateway call config.get --params '{}' --url "$GATEWAY_URL" | jq -r '.config.accounts | keys')"
echo ""

# Phase 3: Execute test config.patch
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "PHASE 3: CONFIG.PATCH TEST"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "$(date +%H:%M:%S.%3N) | TIMESTAMP: Config.patch starting" | tee -a "$LOG_DIR/timing.log"

# Backup current config
cp "$CONFIG_FILE" "$LOG_DIR/config_before_patch.json"
echo "Backup saved: $LOG_DIR/config_before_patch.json"

# Apply test patch
echo ""
echo "Applying config.patch with test account..."
PATCH_RESULT=$(clawdbot gateway call config.patch --url "$GATEWAY_URL" --params "{
  \"baseHash\": \"$INITIAL_HASH\",
  \"patch\": {
    \"accounts\": {
      \"diagnostic_test\": {
        \"type\": \"telegram\",
        \"chatId\": \"999999999\",
        \"token\": \"diagnostic_test_token\"
      }
    },
    \"agents\": {
      \"list\": [\"main\", \"diagnostic_test\"]
    }
  }
}" 2>&1)

echo "$(date +%H:%M:%S.%3N) | TIMESTAMP: Config.patch completed" | tee -a "$LOG_DIR/timing.log"
echo "$PATCH_RESULT" | tee -a "$LOG_DIR/patch_result.log"

# Monitor size changes for 10 seconds
echo ""
echo "Monitoring config file size for 10 seconds..."
for i in {1..20}; do
    SIZE=$(wc -c < "$CONFIG_FILE")
    echo "$(date +%H:%M:%S.%3N) | Size check $i: $SIZE bytes" | tee -a "$LOG_DIR/size_checks.log"

    # Save snapshot if size changed significantly
    if [ $i -eq 1 ]; then
        FIRST_SIZE=$SIZE
    elif [ $((SIZE - FIRST_SIZE)) -gt 100 ] || [ $((FIRST_SIZE - SIZE)) -gt 100 ]; then
        cp "$CONFIG_FILE" "$LOG_DIR/config_snapshot_${i}.json"
        echo "  → Snapshot saved (size change detected)"
    fi

    sleep 0.5
done

# Phase 4: Identify the writer
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "PHASE 4: IDENTIFY THE WRITER"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check current config
FINAL_SIZE=$(wc -c < "$CONFIG_FILE")
cp "$CONFIG_FILE" "$LOG_DIR/config_after_patch.json"

echo "Final config size: $FINAL_SIZE bytes"
echo "Final accounts: $(clawdbot gateway call config.get --params '{}' --url "$GATEWAY_URL" 2>/dev/null | jq -r '.config.accounts | keys' || echo 'GATEWAY OFFLINE')"
echo ""

# Analyze file events
echo "File events detected:"
grep "MODIFY\|CLOSE_WRITE" "$LOG_DIR/file_events.log" | tail -20
echo ""

# Check for multiple writers
echo "Processes accessing config file:"
lsof "$CONFIG_FILE" 2>/dev/null || echo "  (lsof not available or no processes)"
echo ""

# Check supervisor state
echo "Supervisor (PID 1) info:"
echo "  Command: $(cat /proc/1/cmdline | tr '\0' ' ')"
echo "  Open files: $(ls -la /proc/1/fd/ 2>/dev/null | grep -c clawdbot || echo '0') clawdbot-related"
echo ""

# Check gateway process
GATEWAY_PID=$(pgrep -f clawdbot-gateway || echo "")
if [ -n "$GATEWAY_PID" ]; then
    echo "Gateway process (PID $GATEWAY_PID) info:"
    echo "  Started: $(ps -p $GATEWAY_PID -o lstart=)"
    echo "  Open files: $(ls -la /proc/$GATEWAY_PID/fd/ 2>/dev/null | grep -c json || echo '0') json files"
else
    echo "Gateway process: NOT RUNNING"
fi
echo ""

# Phase 5: Analysis & Recommendations
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "PHASE 5: ANALYSIS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Count significant events
MODIFY_COUNT=$(grep -c "MODIFY" "$LOG_DIR/file_events.log" || echo "0")
SIZE_VARIANCE=$((FINAL_SIZE - $(wc -c < "$LOG_DIR/config_before_patch.json")))

echo "Diagnostic Results:"
echo "  - Modify events: $MODIFY_COUNT"
echo "  - Size variance: $SIZE_VARIANCE bytes"
echo "  - Snapshots saved: $(ls -1 "$LOG_DIR"/config_snapshot_*.json 2>/dev/null | wc -l)"
echo ""

# Determine the issue
if [ $MODIFY_COUNT -gt 2 ]; then
    echo "⚠️  FINDING: Multiple config writes detected ($MODIFY_COUNT)"
    echo ""
    echo "Likely cause: Race condition between:"
    echo "  1. config.patch writing updated config"
    echo "  2. Gateway restart signal (SIGUSR1)"
    echo "  3. Something writing old in-memory state"
    echo ""
    echo "RECOMMENDED FIX: See Phase 6 options below"
elif [ $SIZE_VARIANCE -lt -100 ]; then
    echo "⚠️  FINDING: Config size decreased (stripped)"
    echo ""
    echo "Likely cause: Startup validation removing keys"
    echo ""
    echo "RECOMMENDED FIX: Use moltbot doctor --fix + disable auto-enable"
elif [ $SIZE_VARIANCE -gt 100 ]; then
    echo "✅ FINDING: Config size increased (patch applied)"
    echo ""
    echo "Config.patch appears to be working. Verify accounts persist:"
    clawdbot gateway call config.get --params '{}' --url "$GATEWAY_URL" | jq '.config.accounts'
else
    echo "❓ FINDING: Unclear - review event logs"
fi

echo ""

# Phase 6: Fix recommendations
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "PHASE 6: FIX RECOMMENDATIONS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

cat <<'EOF'
Based on the diagnostic, apply the appropriate fix:

╔════════════════════════════════════════════════════════════╗
║ FIX 1: Atomic Write + Kill (Wins the race)                ║
╚════════════════════════════════════════════════════════════╝

# Get current config
clawdbot gateway call config.get --params '{}' --url "$GATEWAY_URL" > /tmp/current.json

# Merge accounts offline
jq '.config + {
  "accounts": {
    "friday": {"type": "telegram", "chatId": "ID", "token": "TOKEN"},
    "jarvis": {"type": "telegram", "chatId": "ID", "token": "TOKEN"}
  },
  "agents": {"list": ["main", "friday", "jarvis"]}
}' /tmp/current.json > /tmp/new_config.json

# Kill gateway + immediately write (race the supervisor)
pkill -9 -f clawdbot-gateway && cat /tmp/new_config.json > ~/.clawdbot/clawdbot.json

# Wait for supervisor restart
sleep 5

# Verify
clawdbot gateway call config.get --params '{}' --url "$GATEWAY_URL" | jq '.config.accounts | keys'

╔════════════════════════════════════════════════════════════╗
║ FIX 2: Config Lock (Prevents overwrites)                  ║
╚════════════════════════════════════════════════════════════╝

# Apply patch first
clawdbot gateway call config.patch --url "$GATEWAY_URL" --params "{...}"

# Lock the file
chattr +i ~/.clawdbot/clawdbot.json

# Trigger restart - it CAN'T overwrite now
pkill -SIGUSR1 -f clawdbot-gateway

# Wait and verify
sleep 5
cat ~/.clawdbot/clawdbot.json | jq '.accounts | keys'

# Remove lock (only if you need to change config later)
chattr -i ~/.clawdbot/clawdbot.json

╔════════════════════════════════════════════════════════════╗
║ FIX 3: Disable Plugin Auto-Enable (Prevents startup write)║
╚════════════════════════════════════════════════════════════╝

# Add to config
jq '. + {"gateway": {"pluginAutoEnable": false}}' ~/.clawdbot/clawdbot.json > /tmp/new.json
cat /tmp/new.json > ~/.clawdbot/clawdbot.json

# Or set environment
export CLAWDBOT_NO_AUTO_ENABLE=1

# Then restart
pkill -SIGUSR1 -f clawdbot-gateway

╔════════════════════════════════════════════════════════════╗
║ FIX 4: Force Loopback Binding (Fixes WebSocket access)    ║
╚════════════════════════════════════════════════════════════╝

jq '. + {
  "gateway": {
    "bind": "loopback",
    "trustedProxies": ["100.0.0.0/8"],
    "pluginAutoEnable": false
  },
  "tailscale": {"mode": "serve"}
}' ~/.clawdbot/clawdbot.json > /tmp/new.json

cat /tmp/new.json > ~/.clawdbot/clawdbot.json
pkill -SIGUSR1 -f clawdbot-gateway

EOF

# Cleanup
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "DIAGNOSTIC COMPLETE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Review logs in: $LOG_DIR"
echo ""
echo "Files saved:"
ls -lh "$LOG_DIR"

# Stop watcher
kill $WATCHER_PID 2>/dev/null || true

echo ""
echo "Next step: Apply the recommended fix from Phase 6"
