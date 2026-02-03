#!/bin/bash
# Tailscale Auto-Connect Script for ClawdBot Containers
# Runs at container boot to join the Tailscale mesh automatically
#
# Prerequisites:
# - TAILSCALE_AUTHKEY environment variable (reusable auth key from Tailscale admin)
# - Container must have NET_ADMIN and NET_RAW capabilities
# - /dev/net/tun must be available
#
# Usage in docker run:
#   -e TAILSCALE_AUTHKEY=tskey-auth-xxx
#   --cap-add=NET_ADMIN --cap-add=NET_RAW
#   --device /dev/net/tun:/dev/net/tun

set -e

BOT_NAME="${BOT_NAME:-clawdbot}"
LOG_PREFIX="[tailscale-autoconnect]"

log() {
    echo "$LOG_PREFIX $1"
}

# Check if Tailscale is installed
if ! command -v tailscale &> /dev/null; then
    log "ERROR: Tailscale not installed"
    exit 1
fi

# Check for auth key
if [ -z "$TAILSCALE_AUTHKEY" ]; then
    log "WARNING: TAILSCALE_AUTHKEY not set, skipping auto-connect"
    log "To enable: set TAILSCALE_AUTHKEY environment variable"
    exit 0
fi

# Check if already connected
if tailscale status &> /dev/null; then
    CURRENT_STATUS=$(tailscale status --json 2>/dev/null | jq -r '.Self.Online // false')
    if [ "$CURRENT_STATUS" = "true" ]; then
        log "Already connected to Tailscale mesh"
        tailscale status
        exit 0
    fi
fi

# Start tailscaled if not running
if ! pgrep -x tailscaled > /dev/null; then
    log "Starting tailscaled daemon..."
    tailscaled --state=/var/lib/tailscale/tailscaled.state --socket=/var/run/tailscale/tailscaled.sock &
    sleep 2
fi

# Connect to Tailscale
log "Connecting to Tailscale mesh as $BOT_NAME..."
tailscale up \
    --authkey="$TAILSCALE_AUTHKEY" \
    --hostname="clawdbot-$BOT_NAME" \
    --accept-routes \
    --accept-dns=false \
    --reset

# Verify connection
sleep 2
if tailscale status &> /dev/null; then
    log "Successfully connected to Tailscale!"
    tailscale status

    # Get our Tailscale IP
    TS_IP=$(tailscale ip -4 2>/dev/null || echo "unknown")
    log "Tailscale IP: $TS_IP"
else
    log "ERROR: Failed to connect to Tailscale"
    exit 1
fi
