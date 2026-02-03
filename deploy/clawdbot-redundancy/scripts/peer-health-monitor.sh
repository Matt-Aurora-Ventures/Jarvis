#!/bin/bash
# ClawdBot Peer Health Monitor
# Allows each bot to monitor and restart peers
# Deployed inside each container to create mesh healing network

set -e

BOT_NAME="${BOT_NAME:-unknown}"
LOG_PREFIX="[peer-monitor:$BOT_NAME]"

# Bot configuration
declare -A BOT_PORTS=(
    ["friday"]=18789
    ["matt"]=18800
    ["jarvis"]=18801
)

# Docker host access (requires /var/run/docker.sock mounted)
DOCKER_HOST="${DOCKER_HOST:-unix:///var/run/docker.sock}"

# Telegram notifications
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-}"

log() {
    echo "$LOG_PREFIX $(date '+%H:%M:%S') $1"
}

send_telegram() {
    local message="$1"
    local urgency="${2:-normal}"

    if [ -z "$TELEGRAM_BOT_TOKEN" ] || [ -z "$TELEGRAM_CHAT_ID" ]; then
        return
    fi

    local emoji="ℹ️"
    case "$urgency" in
        critical) emoji="🚨" ;;
        warning)  emoji="⚠️" ;;
        success)  emoji="✅" ;;
    esac

    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_CHAT_ID}" \
        -d "text=${emoji} [${BOT_NAME}→Peer] ${message}" \
        -d "parse_mode=HTML" > /dev/null 2>&1 || true
}

check_peer_health() {
    local peer="$1"
    local port="${BOT_PORTS[$peer]}"

    if [ -z "$port" ]; then
        log "Unknown peer: $peer"
        return 1
    fi

    # Check via Docker network (container-to-container)
    local response
    response=$(curl -s --connect-timeout 5 --max-time 10 \
        "http://clawdbot-${peer}:${port}/__clawdbot__/canvas/" 2>&1) || true

    if echo "$response" | grep -qi "clawdbot\|canvas\|gateway"; then
        return 0  # Healthy
    fi

    return 1  # Unhealthy
}

restart_peer() {
    local peer="$1"
    local container="clawdbot-$peer"

    log "Attempting to restart $container..."

    # Check if we have docker access
    if ! command -v docker &> /dev/null; then
        log "Docker CLI not available"
        return 1
    fi

    # Try to restart via docker
    if docker restart "$container" 2>/dev/null; then
        log "$container restarted successfully"
        send_telegram "<b>$container</b> restarted by $BOT_NAME (peer recovery)" "success"
        return 0
    else
        log "Failed to restart $container"
        return 1
    fi
}

diagnose_peer() {
    local peer="$1"
    local container="clawdbot-$peer"

    log "Diagnosing $container..."

    # Check if container exists
    if ! docker ps -a --format '{{.Names}}' | grep -q "^${container}$"; then
        echo "CONTAINER_NOT_FOUND"
        return
    fi

    # Check if container is running
    if ! docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
        echo "CONTAINER_STOPPED"
        return
    fi

    # Check container health status
    local health
    health=$(docker inspect --format '{{.State.Health.Status}}' "$container" 2>/dev/null || echo "unknown")

    case "$health" in
        "healthy")
            echo "HEALTHY_BUT_UNRESPONSIVE"
            ;;
        "unhealthy")
            echo "UNHEALTHY"
            ;;
        "starting")
            echo "STARTING"
            ;;
        *)
            echo "UNKNOWN_STATE"
            ;;
    esac
}

monitor_peers() {
    log "Starting peer health check..."

    for peer in "${!BOT_PORTS[@]}"; do
        # Skip self
        if [ "$peer" = "$BOT_NAME" ]; then
            continue
        fi

        if check_peer_health "$peer"; then
            log "$peer: healthy"
        else
            log "$peer: UNHEALTHY"

            # Diagnose before acting
            local diagnosis
            diagnosis=$(diagnose_peer "$peer")
            log "$peer diagnosis: $diagnosis"

            case "$diagnosis" in
                "STARTING")
                    log "$peer is still starting, skipping"
                    ;;
                "CONTAINER_NOT_FOUND"|"CONTAINER_STOPPED"|"UNHEALTHY")
                    send_telegram "Detected $peer is down ($diagnosis). Attempting recovery..." "warning"
                    if restart_peer "$peer"; then
                        log "$peer recovery initiated"
                    else
                        send_telegram "Failed to restart $peer automatically. Manual intervention may be needed." "critical"
                    fi
                    ;;
                *)
                    log "$peer in unknown state, monitoring only"
                    ;;
            esac
        fi
    done

    log "Peer health check complete"
}

# Run monitor
monitor_peers
