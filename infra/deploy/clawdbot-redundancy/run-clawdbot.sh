#!/bin/bash
# ClawdBot Container Run Script
# Complete docker run command with all required flags for Tailscale and persistence

# =============================================================================
# Configuration - Set these for your environment
# =============================================================================

BOT_NAME="${1:-friday}"                    # friday, matt, or jarvis
TAILSCALE_AUTHKEY="${TAILSCALE_AUTHKEY:-}" # Optional: Set for auto-connect

# Port mapping
case "$BOT_NAME" in
    friday) GATEWAY_PORT=18789 ;;
    matt)   GATEWAY_PORT=18800 ;;
    jarvis) GATEWAY_PORT=18801 ;;
    *)      GATEWAY_PORT=18789 ;;
esac

# Paths
CONFIG_DIR="/root/.clawdbot"
if [ "$BOT_NAME" = "matt" ]; then
    CONFIG_DIR="/docker/clawdbot-gateway/config-matt"
elif [ "$BOT_NAME" = "jarvis" ]; then
    CONFIG_DIR="/root/.clawdbot-jarvis"
fi

# =============================================================================
# Docker Run Command
# =============================================================================

echo "[run-clawdbot] Starting clawdbot-$BOT_NAME on port $GATEWAY_PORT"

docker run -d \
    --name "clawdbot-$BOT_NAME" \
    --hostname "clawdbot-$BOT_NAME" \
    --restart=always \
    \
    # Network capabilities for Tailscale
    --cap-add=NET_ADMIN \
    --cap-add=NET_RAW \
    --device /dev/net/tun:/dev/net/tun \
    \
    # Resource limits (prevent OOM kills)
    --memory=2g \
    --memory-swap=3g \
    \
    # Port exposure
    -p "$GATEWAY_PORT:$GATEWAY_PORT" \
    \
    # Environment variables
    -e "BOT_NAME=$BOT_NAME" \
    -e "PROFILE=$BOT_NAME" \
    -e "GATEWAY_PORT=$GATEWAY_PORT" \
    -e "DOCKER_API_VERSION=1.44" \
    ${TAILSCALE_AUTHKEY:+-e "TAILSCALE_AUTHKEY=$TAILSCALE_AUTHKEY"} \
    \
    # Volume mounts - PERSISTENT DATA
    # Config (read-only for security)
    -v "$CONFIG_DIR:/root/.clawdbot:ro" \
    # Tailscale state (survives restarts)
    -v "/var/lib/tailscale-$BOT_NAME:/var/lib/tailscale" \
    # Memory/soul persistence
    -v "/root/clawd/data/$BOT_NAME/memory:/root/.clawdbot/memory" \
    -v "/root/clawd/data/$BOT_NAME/skills:/root/.clawdbot/skills" \
    # SSH keys (for GitHub sync)
    -v "/root/.ssh:/root/.ssh:ro" \
    # Shared memory database
    -v "/root/clawdbots/data:/root/clawdbots/data" \
    \
    # Use pre-built image
    clawdbot-ready:latest

echo "[run-clawdbot] Container started: clawdbot-$BOT_NAME"
docker ps --filter "name=clawdbot-$BOT_NAME" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
