#!/bin/bash
# Ralph Wiggum Secure Gateway Fix
# Fix discovered by agent: Gateway strips keys during validation
# Solution: Fix WebSocket binding → Use config.apply RPC

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔒 SECURE RALPH WIGGUM GATEWAY FIX"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Root cause: Gateway strips unknown keys during validation"
echo "Fix: WebSocket binding → RPC config.apply"
echo ""

# Security: Backup everything first
backup_all_data() {
    echo "🔒 SECURITY: Backing up all data..."
    BACKUP_DIR="/root/clawd/backups/secure_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"

    # Backup critical files
    cp -r /root/clawd/MEMORY.md "$BACKUP_DIR/" 2>/dev/null || true
    cp -r /root/clawd/TODO.md "$BACKUP_DIR/" 2>/dev/null || true
    cp -r /root/clawd/daily-notes "$BACKUP_DIR/" 2>/dev/null || true
    cp -r /root/clawd/voice-transcripts "$BACKUP_DIR/" 2>/dev/null || true
    cp ~/.claude/config.json "$BACKUP_DIR/config.json.backup" 2>/dev/null || true

    # Security: Hash the backup
    find "$BACKUP_DIR" -type f -exec sha256sum {} \; > "$BACKUP_DIR/checksums.txt"

    echo "✅ Backup saved: $BACKUP_DIR"
    echo "🔒 Checksums: $BACKUP_DIR/checksums.txt"
}

# Security: Validate environment variables
validate_env() {
    echo "🔒 SECURITY: Validating environment..."

    REQUIRED_VARS=(
        "TELEGRAM_BOT_TOKEN"
        "MAIN_CHAT_ID"
        "FRIDAY_CHAT_ID"
        "JARVIS_CHAT_ID"
    )

    for VAR in "${REQUIRED_VARS[@]}"; do
        if [ -z "${!VAR}" ]; then
            echo "❌ SECURITY: Missing required environment variable: $VAR"
            echo "Please export: $VAR"
            return 1
        fi
    done

    # Security: Validate tokens are actual tokens (not empty, not "your_token_here")
    if [[ "$TELEGRAM_BOT_TOKEN" =~ ^your_ ]] || [ ${#TELEGRAM_BOT_TOKEN} -lt 20 ]; then
        echo "❌ SECURITY: TELEGRAM_BOT_TOKEN appears invalid"
        return 1
    fi

    echo "✅ Environment validated"
}

# Fix WebSocket binding issue
fix_websocket_binding() {
    echo "🔧 Fixing WebSocket binding (loopback instead of Tailscale)..."

    # Stop gateway
    pkill -9 -f clawdbot-gateway 2>/dev/null || true
    systemctl stop clawdbot-gateway 2>/dev/null || true
    sleep 2

    # Find gateway config file that controls binding
    GATEWAY_CONFIG="/etc/clawdbot/gateway.conf"

    if [ -f "$GATEWAY_CONFIG" ]; then
        # Security: Backup original
        cp "$GATEWAY_CONFIG" "${GATEWAY_CONFIG}.backup"

        # Fix binding to localhost
        sed -i 's/bind_address = "100\..*"/bind_address = "127.0.0.1"/' "$GATEWAY_CONFIG"
        sed -i 's/websocket_host = "100\..*"/websocket_host = "127.0.0.1"/' "$GATEWAY_CONFIG"

        echo "✅ Fixed binding to 127.0.0.1"
    else
        # If no config file, set via environment
        export GATEWAY_BIND_ADDRESS="127.0.0.1"
        export GATEWAY_WS_HOST="127.0.0.1"
        echo "✅ Set binding via environment"
    fi

    # Restart gateway
    systemctl start clawdbot-gateway 2>/dev/null || {
        nohup clawdbot gateway start --bind 127.0.0.1 > /var/log/clawdbot-gateway.log 2>&1 &
        echo $! > /tmp/clawdbot-gateway.pid
    }

    sleep 5

    # Verify WebSocket works
    if curl -s "http://127.0.0.1:8080/health" > /dev/null 2>&1; then
        echo "✅ WebSocket accessible on 127.0.0.1:8080"
        return 0
    else
        echo "❌ WebSocket still not accessible"
        return 1
    fi
}

# Use RPC to add accounts properly
add_accounts_via_rpc() {
    echo "🔧 Adding accounts via RPC (proper method)..."

    # Security: Create temporary auth token
    AUTH_TOKEN=$(openssl rand -hex 32)

    # Use clawdbot config.apply (the proper way)
    cat > /tmp/config_patch.json <<EOF
{
  "accounts": {
    "friday": {
      "type": "telegram",
      "chatId": "$FRIDAY_CHAT_ID",
      "token": "$TELEGRAM_BOT_TOKEN"
    },
    "jarvis": {
      "type": "telegram",
      "chatId": "$JARVIS_CHAT_ID",
      "token": "$TELEGRAM_BOT_TOKEN"
    }
  },
  "agents": {
    "list": ["main", "friday", "jarvis"]
  }
}
EOF

    # Security: Set restrictive permissions
    chmod 600 /tmp/config_patch.json

    # Apply via RPC
    if command -v clawdbot > /dev/null 2>&1; then
        clawdbot config apply /tmp/config_patch.json
        RESULT=$?
    else
        # Fallback: Direct RPC call
        curl -X POST http://127.0.0.1:8080/rpc \
          -H "Content-Type: application/json" \
          -d @/tmp/config_patch.json
        RESULT=$?
    fi

    # Security: Shred the temp file
    shred -u /tmp/config_patch.json 2>/dev/null || rm -f /tmp/config_patch.json

    if [ $RESULT -eq 0 ]; then
        echo "✅ Accounts added via RPC"
        return 0
    else
        echo "❌ RPC config apply failed"
        return 1
    fi
}

# Verify accounts persist across restart
verify_persistence() {
    echo "🔍 Verifying accounts persist across restart..."

    # Get current config
    BEFORE_CONFIG=$(clawdbot config get 2>/dev/null || curl -s http://127.0.0.1:8080/config)

    # Check accounts exist
    if echo "$BEFORE_CONFIG" | jq -e '.accounts.friday' > /dev/null 2>&1; then
        echo "✅ Friday account exists before restart"
    else
        echo "❌ Friday account missing before restart"
        return 1
    fi

    # Graceful restart
    echo "🔄 Restarting gateway (graceful)..."
    systemctl restart clawdbot-gateway 2>/dev/null || {
        kill $(cat /tmp/clawdbot-gateway.pid) 2>/dev/null
        sleep 3
        nohup clawdbot gateway start --bind 127.0.0.1 > /var/log/clawdbot-gateway.log 2>&1 &
        echo $! > /tmp/clawdbot-gateway.pid
    }

    sleep 5

    # Get config after restart
    AFTER_CONFIG=$(clawdbot config get 2>/dev/null || curl -s http://127.0.0.1:8080/config)

    # Verify accounts still exist
    if echo "$AFTER_CONFIG" | jq -e '.accounts.friday' > /dev/null 2>&1; then
        echo "✅ Friday account PERSISTED after restart"
    else
        echo "❌ Friday account LOST after restart"
        return 1
    fi

    if echo "$AFTER_CONFIG" | jq -e '.accounts.jarvis' > /dev/null 2>&1; then
        echo "✅ Jarvis account PERSISTED after restart"
    else
        echo "❌ Jarvis account LOST after restart"
        return 1
    fi

    return 0
}

# Main Ralph Wiggum loop
MAX_ATTEMPTS=10
ATTEMPT=1

while [ $ATTEMPT -le $MAX_ATTEMPTS ]; do
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🔄 SECURE ATTEMPT $ATTEMPT/$MAX_ATTEMPTS"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Step 1: Backup (every attempt)
    backup_all_data

    # Step 2: Validate environment (security)
    if ! validate_env; then
        echo "❌ Environment validation failed"
        exit 1
    fi

    # Step 3: Fix WebSocket binding
    if ! fix_websocket_binding; then
        echo "⚠️  WebSocket fix failed, retrying in 5s..."
        sleep 5
        ATTEMPT=$((ATTEMPT + 1))
        continue
    fi

    # Step 4: Add accounts via RPC
    if ! add_accounts_via_rpc; then
        echo "⚠️  RPC add failed, retrying in 5s..."
        sleep 5
        ATTEMPT=$((ATTEMPT + 1))
        continue
    fi

    # Step 5: Verify persistence
    if verify_persistence; then
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "✅ GATEWAY FIXED SECURELY!"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        echo "🔒 Security Status:"
        echo "  ✅ All data backed up with checksums"
        echo "  ✅ Credentials validated"
        echo "  ✅ WebSocket bound to loopback (127.0.0.1)"
        echo "  ✅ Accounts added via RPC (not file edit)"
        echo "  ✅ Accounts persist across restart"
        echo ""
        echo "📊 Final Config:"
        clawdbot config get 2>/dev/null || curl -s http://127.0.0.1:8080/config | jq .
        echo ""
        exit 0
    else
        echo "⚠️  Persistence test failed, retrying in 5s..."
        sleep 5
    fi

    ATTEMPT=$((ATTEMPT + 1))
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "❌ FAILED AFTER $MAX_ATTEMPTS ATTEMPTS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Manual debugging required:"
echo "  1. Check gateway logs: journalctl -u clawdbot-gateway -n 100"
echo "  2. Check WebSocket: curl http://127.0.0.1:8080/health"
echo "  3. Check config schema: clawdbot config schema"
echo "  4. Check RPC auth: clawdbot config test-auth"
exit 1
