#!/bin/bash
# ClawdBot Container Entrypoint
# 1. Validates environment
# 2. Starts Tailscale (if configured)
# 3. Starts clawdbot gateway

set -e

BOT_NAME="${BOT_NAME:-unknown}"
PROFILE="${PROFILE:-$BOT_NAME}"
GATEWAY_PORT="${GATEWAY_PORT:-18789}"
LOG_PREFIX="[entrypoint:$BOT_NAME]"

log() {
    echo "$LOG_PREFIX $(date '+%H:%M:%S') $1"
}

log "Container starting..."

# =============================================================================
# STEP 1: Environment Validation
# =============================================================================

# Check for auth-profiles.json (required for gateway)
AUTH_PROFILES="/root/.clawdbot/auth-profiles.json"
if [ ! -f "$AUTH_PROFILES" ]; then
    log "WARNING: $AUTH_PROFILES not found"
    log "Gateway may fail without authentication config"
fi

# Check for clawdbot.json (bot config)
BOT_CONFIG="/root/.clawdbot/clawdbot.json"
if [ ! -f "$BOT_CONFIG" ]; then
    log "WARNING: $BOT_CONFIG not found"
fi

# Secure permissions on sensitive files
if [ -f "$AUTH_PROFILES" ]; then
    chmod 600 "$AUTH_PROFILES" 2>/dev/null || true
fi
if [ -f "/root/.clawdbot/.env" ]; then
    chmod 600 "/root/.clawdbot/.env" 2>/dev/null || true
fi

# =============================================================================
# STEP 2: Tailscale (Optional)
# =============================================================================

if [ -n "$TAILSCALE_AUTHKEY" ] || [ -f "/var/lib/tailscale/tailscaled.state" ]; then
    log "Starting Tailscale..."
    /root/scripts/tailscale-start.sh || log "WARNING: Tailscale failed (non-fatal)"
else
    log "Tailscale not configured, skipping"
fi

# =============================================================================
# STEP 2.5: Redis Context Hydration (Fast Recovery)
# =============================================================================

if [ -f "/root/scripts/redis-hydration.sh" ]; then
    log "Checking Redis for cached context..."
    /root/scripts/redis-hydration.sh startup "$BOT_NAME" 2>/dev/null || log "No Redis context available"
elif command -v redis-cli &> /dev/null && redis-cli -h "${REDIS_HOST:-localhost}" ping &> /dev/null; then
    # Inline hydration if script not available but Redis is
    log "Redis available, attempting inline hydration..."
    REDIS_HOST="${REDIS_HOST:-localhost}"
    KEY_PREFIX="clawdbot:$BOT_NAME"

    # Check if we have cached context
    KEY_COUNT=$(redis-cli -h "$REDIS_HOST" KEYS "$KEY_PREFIX:*" 2>/dev/null | wc -l)
    if [ "$KEY_COUNT" -gt 0 ]; then
        log "Found $KEY_COUNT cached keys, context ready"
    fi
else
    log "Redis not available, using disk-based context"
fi

# =============================================================================
# STEP 3: Start Gateway
# =============================================================================

log "Starting clawdbot gateway"
log "  Profile: $PROFILE"
log "  Port: $GATEWAY_PORT"

# Export port for HEALTHCHECK
export GATEWAY_PORT

# Start the gateway (exec replaces shell, so signals propagate correctly)
exec clawdbot gateway --profile "$PROFILE" --bind lan
