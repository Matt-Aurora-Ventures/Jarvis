#!/bin/bash
# Tailscale Startup Script for ClawdBot Containers
# Uses userspace networking to avoid requiring privileged host-level permissions
#
# Docker run requirements:
#   --cap-add=NET_ADMIN
#   --device /dev/net/tun
#   -v /var/lib/tailscale:/var/lib/tailscale
#
# Environment variables:
#   TAILSCALE_AUTHKEY - Reusable auth key from Tailscale admin console
#   BOT_NAME - Bot name for hostname (friday/matt/jarvis)

set -e

BOT_NAME="${BOT_NAME:-clawdbot}"
LOG_PREFIX="[tailscale:$BOT_NAME]"

log() {
    echo "$LOG_PREFIX $(date '+%H:%M:%S') $1"
}

# Check if Tailscale is installed
if ! command -v tailscale &> /dev/null; then
    log "ERROR: Tailscale not installed"
    exit 1
fi

# Create required directories
# Use persistent path in /root/.clawdbot/tailscale/ for state to survive image updates
STATE_DIR="${TAILSCALE_STATE_DIR:-/root/.clawdbot/tailscale}"
mkdir -p "$STATE_DIR" /var/run/tailscale

# Check if tailscaled is already running
if pgrep -x tailscaled > /dev/null; then
    log "tailscaled already running"
else
    log "Starting tailscaled daemon with userspace networking..."
    log "State dir: $STATE_DIR (persistent)"
    tailscaled \
        --state="$STATE_DIR/tailscaled.state" \
        --socket=/var/run/tailscale/tailscaled.sock \
        --tun=userspace-networking &

    # Wait for daemon to be ready
    sleep 3
fi

# Check for auth key
if [ -z "$TAILSCALE_AUTHKEY" ]; then
    log "WARNING: TAILSCALE_AUTHKEY not set"
    log "To enable auto-connect: set TAILSCALE_AUTHKEY environment variable"

    # Check if already authenticated from persistent state
    if tailscale status &> /dev/null; then
        CURRENT_STATUS=$(tailscale status --json 2>/dev/null | jq -r '.Self.Online // false')
        if [ "$CURRENT_STATUS" = "true" ]; then
            log "Already connected via persistent state"
            tailscale status
            exit 0
        fi
    fi

    log "Not connected - manual 'tailscale up' required"
    exit 0
fi

# Connect to Tailscale mesh
log "Connecting to Tailscale mesh as clawdbot-$BOT_NAME..."
tailscale up \
    --authkey="$TAILSCALE_AUTHKEY" \
    --hostname="clawdbot-$BOT_NAME" \
    --accept-routes \
    --accept-dns=false

# Verify connection
sleep 2
if tailscale status &> /dev/null; then
    TS_IP=$(tailscale ip -4 2>/dev/null || echo "unknown")
    log "SUCCESS: Connected to Tailscale mesh"
    log "Tailscale IP: $TS_IP"
    tailscale status
else
    log "ERROR: Failed to connect to Tailscale"
    exit 1
fi
