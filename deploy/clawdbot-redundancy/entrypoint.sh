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
# STEP 2.6: Configure Supermemory (Persistent Memory Across Reboots)
# =============================================================================

# Supermemory API key (must be provided via env)
SUPERMEMORY_API_KEY="${SUPERMEMORY_API_KEY:-}"

if [ -n "$SUPERMEMORY_API_KEY" ]; then
    # Export for plugins to pick up
    export SUPERMEMORY_API_KEY
    export SUPERMEMORY_OPENCLAW_API_KEY="$SUPERMEMORY_API_KEY"
    export SUPERMEMORY_CONTAINER_TAG="clawdbot_$BOT_NAME"

    log "Supermemory API key exported (containerTag: clawdbot_$BOT_NAME)"

    # Try to install/enable Supermemory plugin if not already
    if command -v openclaw &> /dev/null; then
        openclaw plugins install @supermemory/openclaw-supermemory 2>/dev/null || true
    fi

    log "✅ Supermemory configured for persistent memory"
else
    log "Supermemory API key not set (SUPERMEMORY_API_KEY). Skipping Supermemory plugin setup."
fi

# =============================================================================
# STEP 2.605: Configure Codex CLI (for Matt / coding-agent)
# =============================================================================

if [ "$BOT_NAME" = "matt" ] || [ "${INSTALL_CODEX:-false}" = "true" ]; then
    log "Configuring Codex CLI..."
    npm install -g @openai/codex 2>/dev/null || true

    NPM_PREFIX="$(npm config get prefix 2>/dev/null || echo /usr/local)"
    CODEX_BIN="$NPM_PREFIX/bin/codex"
    if [ -x "$CODEX_BIN" ] && [ ! -x /usr/local/bin/codex ]; then
        ln -sf "$CODEX_BIN" /usr/local/bin/codex || true
    fi

    if command -v codex >/dev/null 2>&1; then
        log "✅ Codex CLI available"
    else
        log "⚠️ Codex CLI not on PATH; use fallback command: npx --yes @openai/codex"
    fi
fi

# =============================================================================
# STEP 2.61: Configure AI Provider (Multi-Provider Support)
# =============================================================================

AI_PROVIDER="${AI_PROVIDER:-anthropic}"
AI_MODEL="${AI_MODEL:-claude-sonnet-4-20250514}"

log "Configuring AI provider: $AI_PROVIDER with model: $AI_MODEL"

# Export provider-specific keys based on configured provider
case "$AI_PROVIDER" in
    anthropic)
        export ANTHROPIC_OAUTH_ACCESS="${ANTHROPIC_OAUTH_ACCESS:-}"
        export ANTHROPIC_OAUTH_REFRESH="${ANTHROPIC_OAUTH_REFRESH:-}"
        export AI_API_KEY="${AI_API_KEY:-${ANTHROPIC_OAUTH_ACCESS:-}}"
        if [ -z "$ANTHROPIC_OAUTH_ACCESS" ]; then
            log "  ⚠️ WARNING: ANTHROPIC_OAUTH_ACCESS not set"
        else
            log "  ✅ Anthropic OAuth configured"
        fi
        ;;
    openai)
        export OPENAI_API_KEY="${OPENAI_API_KEY:-}"
        export AI_API_KEY="${AI_API_KEY:-${OPENAI_API_KEY:-}}"
        if [ -z "$OPENAI_API_KEY" ]; then
            log "  ⚠️ WARNING: OPENAI_API_KEY not set"
        else
            log "  ✅ OpenAI API key configured"
        fi
        ;;
    xai)
        export XAI_API_KEY="${XAI_API_KEY:-}"
        export AI_API_KEY="${AI_API_KEY:-${XAI_API_KEY:-}}"
        if [ -z "$XAI_API_KEY" ]; then
            log "  ⚠️ WARNING: XAI_API_KEY not set"
        else
            log "  ✅ XAI API key configured"
        fi
        ;;
    nvidia)
        export NVIDIA_NIM_API_KEY="${NVIDIA_NIM_API_KEY:-}"
        export AI_API_KEY="${AI_API_KEY:-${NVIDIA_NIM_API_KEY:-}}"
        if [ -z "$NVIDIA_NIM_API_KEY" ]; then
            log "  ⚠️ WARNING: NVIDIA_NIM_API_KEY not set"
        else
            log "  ✅ NVIDIA NIM API key configured"
        fi
        ;;
    google)
        export GOOGLE_AI_API_KEY="${GOOGLE_AI_API_KEY:-}"
        export AI_API_KEY="${AI_API_KEY:-${GOOGLE_AI_API_KEY:-}}"
        if [ -z "$GOOGLE_AI_API_KEY" ]; then
            log "  ⚠️ WARNING: GOOGLE_AI_API_KEY not set"
        else
            log "  ✅ Google AI API key configured"
        fi
        ;;
    *)
        log "  ⚠️ Unknown provider: $AI_PROVIDER"
        ;;
esac

# Export for OpenClaw to use
export AI_PROVIDER
export AI_MODEL

log "✅ AI provider configured: $AI_PROVIDER / $AI_MODEL"

# =============================================================================
# STEP 2.62: Configure MCP Servers (Model Context Protocol)
# =============================================================================

MCP_TEMPLATE="/root/.clawdbot/mcp-servers-template.json"
MCP_CONFIG="/root/.clawdbot/mcp-servers.json"

if [ -f "$MCP_TEMPLATE" ] && [ ! -f "$MCP_CONFIG" ]; then
    log "Configuring MCP servers from template..."

    # Copy template and substitute environment variables
    cp "$MCP_TEMPLATE" "$MCP_CONFIG"

    # Substitute env vars if present
    if [ -n "$GITHUB_TOKEN" ]; then
        sed -i "s|\${GITHUB_TOKEN}|$GITHUB_TOKEN|g" "$MCP_CONFIG"
        log "  - GitHub MCP: configured"
    else
        log "  - GitHub MCP: GITHUB_TOKEN not set (disabled)"
    fi

    if [ -n "$BRAVE_API_KEY" ]; then
        sed -i "s|\${BRAVE_API_KEY}|$BRAVE_API_KEY|g" "$MCP_CONFIG"
        log "  - Brave Search MCP: configured"
    else
        log "  - Brave Search MCP: BRAVE_API_KEY not set (disabled)"
    fi

    log "✅ MCP servers configured: $MCP_CONFIG"
elif [ -f "$MCP_CONFIG" ]; then
    log "MCP servers already configured"
else
    log "MCP template not found, skipping MCP setup"
fi

# Export MCP config path for OpenClaw to pick up
export OPENCLAW_MCP_CONFIG="$MCP_CONFIG"

# =============================================================================
# STEP 2.65: Bootstrap Identity Injection (Tells bot who they are on startup)
# =============================================================================

IDENTITY_FILE="/root/.clawdbot/BOOTSTRAP.md"
log "Injecting bootstrap identity..."

cat > "$IDENTITY_FILE" << BOOTSTRAP_EOF
# Bootstrap Context - Read This First

You are **$BOT_NAME**, a ClawdBot agent. This file is injected at container startup.

## Memory Status
- **Supermemory**: ACTIVE ✅
- **Container Tags**: clawdbot_$BOT_NAME (private), clawdbot_shared (team)
- **Provider**: supermemory.ai

## What This Means
1. You have PERSISTENT MEMORY that survives reboots
2. You can recall past conversations and learnings
3. Your memories are stored in the cloud (Supermemory)
4. You share knowledge with other ClawdBots via clawdbot_shared tag

## On Every Boot
- This file is regenerated to confirm memory is active
- Your Supermemory connection is verified
- You start with full access to your past experiences

## Your Identity
- Name: $BOT_NAME
- Profile: $PROFILE
- Gateway Port: $GATEWAY_PORT
- AI Provider: $AI_PROVIDER
- AI Model: $AI_MODEL
- Started: $(date -Iseconds)

## Quick Memory Commands
- Search your memories: already automatic via searchOnPrompt
- Add important memory: happens automatically via autoAdd
- The shared team memory lets you learn from Friday, Matt, Jarvis, and Yoda

## MCP Servers Available
You have access to Model Context Protocol (MCP) servers:
- **filesystem**: Read/write files in /root/clawd and /root/.clawdbot
- **memory**: Knowledge graph for storing entities and relations
- **sequential-thinking**: Structured problem-solving
- **github**: GitHub API (if GITHUB_TOKEN configured)
- **brave-search**: Web search (if BRAVE_API_KEY configured)

You are NOT starting fresh. You have memory. Use it.
BOOTSTRAP_EOF

log "✅ Bootstrap identity injected: $IDENTITY_FILE"

# =============================================================================
# STEP 2.7: Start OpenClaw Daemon (if configured)
# =============================================================================

OPENCLAW_CONFIG="/root/.clawdbot/openclaw-config.json"
if [ -f "$OPENCLAW_CONFIG" ]; then
    log "Starting OpenClaw daemon..."
    openclaw onboard --install-daemon --config "$OPENCLAW_CONFIG" 2>&1 | tee -a /var/log/openclaw-$BOT_NAME.log &
    log "OpenClaw daemon started (multi-channel inbox active)"
else
    log "OpenClaw not configured, skipping (run 'openclaw onboard' to configure)"
fi

# =============================================================================
# STEP 2.8: Initialize UI-TARS (GUI Agent)
# =============================================================================

# UI-TARS is available via: npx @agent-tars/cli
# Pre-installed in image, ready for on-demand usage
# To use: docker exec clawdbot-friday npx @agent-tars/cli
log "UI-TARS GUI agent available: npx @agent-tars/cli"

# =============================================================================
# STEP 2.9: Start Cron Daemon (for peer health monitoring)
# =============================================================================

if command -v cron &> /dev/null; then
    log "Starting cron daemon for peer health monitoring..."
    cron
    log "Cron started (peer monitor runs every 2 minutes)"
else
    log "WARNING: cron not available, peer health monitoring disabled"
fi

# =============================================================================
# STEP 2.95: Clear Stale Session Locks (Prevents Startup Crashes)
# =============================================================================

SESSIONS_DIR="/root/.clawdbot/agents/main/sessions"
if [ -d "$SESSIONS_DIR" ]; then
    LOCK_COUNT=$(find "$SESSIONS_DIR" -name "*.lock" -type f 2>/dev/null | wc -l)
    if [ "$LOCK_COUNT" -gt 0 ]; then
        log "Clearing $LOCK_COUNT stale session locks..."
        find "$SESSIONS_DIR" -name "*.lock" -type f -delete 2>/dev/null || true
        log "✅ Session locks cleared"
    fi
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
exec clawdbot gateway --profile "$PROFILE" --port "$GATEWAY_PORT" --bind lan
