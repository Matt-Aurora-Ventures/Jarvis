#!/bin/bash
# ClawdBot Health Watchdog v3 - Fixed Recovery Timing
# Fixes:
# - Uses clawdbot-ready:latest pre-built image (1s startup vs 2min)
# - Increased grace period to 240s
# - Increased post-restart wait to 90s
# - Added Redis hydration on recovery
# - Added exponential backoff
#
# Runs every minute via cron: * * * * * /root/clawd/infra/bot-health-watchdog.sh

set -o pipefail

LOGFILE="/var/log/clawdbot-watchdog.log"
STATE_FILE="/root/clawd/infra/watchdog-state.json"
BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
CHAT_ID="${TELEGRAM_CHAT_ID:-}"

# Recovery settings - UPDATED FOR PRE-BUILT IMAGE
RECOVERY_COOLDOWN=180           # 3 minutes between recovery attempts per bot
MAX_FAILURES_BEFORE_REBUILD=3   # After 3 failed recoveries, do full rebuild
MAX_REBUILDS_BEFORE_PAUSE=2     # After 2 failed rebuilds, pause for manual review
STARTUP_GRACE_PERIOD=240        # 4 minutes grace after start (increased from 120)
POST_RESTART_WAIT=90            # Wait 90s after restart before health check (increased from 45)
HEALTH_CHECK_TIMEOUT=15         # HTTP timeout for health checks
PAUSE_DURATION=3600             # 1 hour pause after max rebuilds (manual intervention expected)

# Pre-built image (instant startup)
PREBUILT_IMAGE="clawdbot-ready:latest"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOGFILE"
}

send_telegram() {
    local urgency="${2:-normal}"
    local emoji="📋"
    case "$urgency" in
        critical) emoji="🚨" ;;
        warning)  emoji="⚠️" ;;
        success)  emoji="✅" ;;
        info)     emoji="ℹ️" ;;
    esac
    curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
        -d "chat_id=${CHAT_ID}" \
        -d "text=${emoji} [Watchdog v3] $1" \
        -d "parse_mode=HTML" > /dev/null 2>&1
}

get_failure_count() {
    local bot="$1"
    local file="/tmp/.clawdbot-${bot}_failures"
    [ -f "$file" ] && cat "$file" || echo 0
}

increment_failure() {
    local bot="$1"
    local file="/tmp/.clawdbot-${bot}_failures"
    local count=$(get_failure_count "$bot")
    echo $((count + 1)) > "$file"
}

reset_failures() {
    local bot="$1"
    rm -f "/tmp/.clawdbot-${bot}_failures"
}

is_in_cooldown() {
    local bot="$1"
    local cooldown_file="/tmp/.clawdbot-${bot}_cooldown"
    if [ -f "$cooldown_file" ]; then
        local last=$(cat "$cooldown_file")
        local now=$(date +%s)
        [ $((now - last)) -lt $RECOVERY_COOLDOWN ]
    else
        return 1  # Not in cooldown
    fi
}

set_cooldown() {
    local bot="$1"
    date +%s > "/tmp/.clawdbot-${bot}_cooldown"
}

get_rebuild_count() {
    local bot="$1"
    local file="/tmp/.clawdbot-${bot}_rebuilds"
    [ -f "$file" ] && cat "$file" || echo 0
}

increment_rebuild() {
    local bot="$1"
    local file="/tmp/.clawdbot-${bot}_rebuilds"
    local count=$(get_rebuild_count "$bot")
    echo $((count + 1)) > "$file"
}

reset_rebuilds() {
    local bot="$1"
    rm -f "/tmp/.clawdbot-${bot}_rebuilds"
}

is_paused() {
    local bot="$1"
    local pause_file="/tmp/.clawdbot-${bot}_paused"
    if [ -f "$pause_file" ]; then
        local paused_at=$(cat "$pause_file")
        local now=$(date +%s)
        if [ $((now - paused_at)) -lt $PAUSE_DURATION ]; then
            return 0  # Still paused
        else
            rm -f "$pause_file"  # Pause expired
            reset_rebuilds "$bot"
            return 1
        fi
    fi
    return 1
}

set_paused() {
    local bot="$1"
    date +%s > "/tmp/.clawdbot-${bot}_paused"
    send_telegram "<b>$bot PAUSED FOR MANUAL REVIEW</b>
Too many rebuild failures. Bot will remain paused for 1 hour.

To unpause early:
<code>rm /tmp/.clawdbot-${bot}_paused</code>" "critical"
}

# Calculate exponential backoff (5s, 10s, 20s, 40s, 80s, 160s, max 300s)
get_backoff() {
    local failures="$1"
    local base=5
    local backoff=$((base * (2 ** failures)))
    [ "$backoff" -gt 300 ] && backoff=300
    echo "$backoff"
}

# Hydrate Redis context before health check
hydrate_context() {
    local bot="$1"
    if [ -f "/root/clawd/scripts/redis-hydration.sh" ]; then
        /root/clawd/scripts/redis-hydration.sh startup "$bot" 2>/dev/null || true
    fi
}

# Full rebuild: remove container and recreate with PRE-BUILT IMAGE
full_rebuild() {
    local bot="$1"
    local container="clawdbot-$bot"

    # Check if we've exceeded rebuild attempts
    local rebuild_count=$(get_rebuild_count "$bot")
    if [ "$rebuild_count" -ge $MAX_REBUILDS_BEFORE_PAUSE ]; then
        log "$container: MAX REBUILDS EXCEEDED ($rebuild_count) - pausing for manual review"
        set_paused "$bot"
        return 1
    fi

    increment_rebuild "$bot"
    log "$container: FULL REBUILD triggered (attempt $((rebuild_count + 1)) of $MAX_REBUILDS_BEFORE_PAUSE)"
    send_telegram "<b>$container FULL REBUILD</b>
Using pre-built image for fast recovery..." "critical"

    # Stop and remove
    docker stop "$container" >/dev/null 2>&1
    docker rm "$container" >/dev/null 2>&1
    sleep 2

    # Determine port
    local port=""
    case "$bot" in
        friday) port=18789 ;;
        matt)   port=18800 ;;
        jarvis) port=18801 ;;
    esac

    # Recreate with PRE-BUILT IMAGE and all required flags
    case "$bot" in
        friday)
            docker run -d \
                --name clawdbot-friday \
                --hostname clawdbot-friday \
                --restart=always \
                --memory=2g \
                --memory-swap=3g \
                --cap-add=NET_ADMIN \
                --cap-add=NET_RAW \
                --device /dev/net/tun:/dev/net/tun \
                -p 18789:18789 \
                -e BOT_NAME=friday \
                -e PROFILE=friday \
                -e GATEWAY_PORT=18789 \
                -e DOCKER_API_VERSION=1.44 \
                -e NODE_OPTIONS='--max-old-space-size=1536' \
                -v /root/.clawdbot:/root/.clawdbot:ro \
                -v /var/lib/tailscale-friday:/var/lib/tailscale \
                -v /root/clawd/data/friday/memory:/root/.clawdbot/memory \
                -v /root/clawd/data/friday/skills:/root/.clawdbot/skills \
                -v /root/.ssh:/root/.ssh:ro \
                -v /root/clawdbots/data:/root/clawdbots/data \
                "$PREBUILT_IMAGE"
            ;;
        matt)
            docker run -d \
                --name clawdbot-matt \
                --hostname clawdbot-matt \
                --restart=always \
                --memory=2g \
                --memory-swap=3g \
                --cap-add=NET_ADMIN \
                --cap-add=NET_RAW \
                --device /dev/net/tun:/dev/net/tun \
                -p 18800:18800 \
                -e BOT_NAME=matt \
                -e PROFILE=matt \
                -e GATEWAY_PORT=18800 \
                -e DOCKER_API_VERSION=1.44 \
                -e NODE_OPTIONS='--max-old-space-size=1536' \
                -v /docker/clawdbot-gateway/config-matt:/root/.clawdbot:ro \
                -v /var/lib/tailscale-matt:/var/lib/tailscale \
                -v /root/clawd/data/matt/memory:/root/.clawdbot/memory \
                -v /root/clawd/data/matt/skills:/root/.clawdbot/skills \
                -v /root/.ssh:/root/.ssh:ro \
                -v /root/clawdbots/data:/root/clawdbots/data \
                "$PREBUILT_IMAGE"
            ;;
        jarvis)
            docker run -d \
                --name clawdbot-jarvis \
                --hostname clawdbot-jarvis \
                --restart=always \
                --memory=2g \
                --memory-swap=3g \
                --cap-add=NET_ADMIN \
                --cap-add=NET_RAW \
                --device /dev/net/tun:/dev/net/tun \
                -p 18801:18801 \
                -e BOT_NAME=jarvis \
                -e PROFILE=jarvis \
                -e GATEWAY_PORT=18801 \
                -e DOCKER_API_VERSION=1.44 \
                -e NODE_OPTIONS='--max-old-space-size=1536' \
                -e XAI_API_KEY="${XAI_API_KEY}" \
                -v /root/.clawdbot-jarvis:/root/.clawdbot:ro \
                -v /var/lib/tailscale-jarvis:/var/lib/tailscale \
                -v /root/clawd/data/jarvis/memory:/root/.clawdbot/memory \
                -v /root/clawd/data/jarvis/skills:/root/.clawdbot/skills \
                -v /root/.ssh:/root/.ssh:ro \
                -v /root/clawdbots/data:/root/clawdbots/data \
                "$PREBUILT_IMAGE"
            ;;
    esac

    # Hydrate context from Redis (if available)
    hydrate_context "$bot"

    # Wait for startup (much shorter with pre-built image)
    log "$container: Waiting $POST_RESTART_WAIT seconds for startup..."
    sleep $POST_RESTART_WAIT

    # Verify health
    local response=$(curl -s --connect-timeout 10 --max-time $HEALTH_CHECK_TIMEOUT "http://127.0.0.1:${port}/__clawdbot__/canvas/" 2>&1)

    if echo "$response" | grep -qi "clawdbot\|canvas\|gateway"; then
        log "$container: REBUILD SUCCESS"
        send_telegram "$container rebuilt and healthy! (${POST_RESTART_WAIT}s startup)" "success"
        reset_failures "$bot"
        reset_rebuilds "$bot"
        return 0
    else
        log "$container: REBUILD FAILED - gateway not responding"
        send_telegram "<b>$container REBUILD FAILED!</b>
Gateway not responding after ${POST_RESTART_WAIT}s.

<code>ssh root@76.13.106.100
docker logs $container --tail 50</code>" "critical"
        return 1
    fi
}

check_and_recover() {
    local bot="$1"
    local container="clawdbot-$bot"

    # Check if bot is paused for manual review
    if is_paused "$bot"; then
        log "$container: PAUSED - skipping (manual intervention required)"
        return 1
    fi

    # Determine port
    local port=""
    case "$bot" in
        friday) port=18789 ;;
        matt)   port=18800 ;;
        jarvis) port=18801 ;;
    esac

    # Check if container is running
    if ! docker ps --format "{{.Names}}" | grep -q "^${container}$"; then
        log "$container: Container not running"

        if is_in_cooldown "$bot"; then
            log "$container: In cooldown, skipping"
            return 1
        fi

        local failures=$(get_failure_count "$bot")
        if [ "$failures" -ge $MAX_FAILURES_BEFORE_REBUILD ]; then
            full_rebuild "$bot"
            return $?
        fi

        # Simple recovery: start the container
        log "$container: Starting container..."
        send_telegram "$container down - starting..." "warning"
        set_cooldown "$bot"
        increment_failure "$bot"

        docker start "$container" >/dev/null 2>&1

        # Hydrate context
        hydrate_context "$bot"

        # Wait with exponential backoff
        local backoff=$(get_backoff "$failures")
        log "$container: Waiting ${POST_RESTART_WAIT}s (backoff: ${backoff}s)..."
        sleep $POST_RESTART_WAIT

        if docker ps --format "{{.Names}}" | grep -q "^${container}$"; then
            # Check gateway health
            local response=$(curl -s --connect-timeout 10 --max-time $HEALTH_CHECK_TIMEOUT "http://127.0.0.1:${port}/__clawdbot__/canvas/" 2>&1)
            if echo "$response" | grep -qi "clawdbot\|canvas\|gateway"; then
                log "$container: Started and healthy"
                send_telegram "$container is back online!" "success"
                reset_failures "$bot"
                return 0
            fi
        fi

        log "$container: Failed to start or unhealthy"
        send_telegram "$container failed to start (attempt $((failures + 1)))" "critical"
        return 1
    fi

    # Container running - check gateway health
    local response=$(curl -s --connect-timeout 10 --max-time $HEALTH_CHECK_TIMEOUT "http://127.0.0.1:${port}/__clawdbot__/canvas/" 2>&1)

    if echo "$response" | grep -qi "clawdbot\|canvas\|gateway"; then
        # Healthy - reset failure count
        reset_failures "$bot"
        return 0
    fi

    # Gateway not responding - check how long container has been up
    local started=$(docker inspect --format '{{.State.StartedAt}}' "$container" 2>/dev/null)
    local start_epoch=$(date -d "$started" +%s 2>/dev/null || echo 0)
    local now=$(date +%s)
    local uptime=$((now - start_epoch))

    if [ "$uptime" -lt $STARTUP_GRACE_PERIOD ]; then
        log "$container: Recently started (${uptime}s < ${STARTUP_GRACE_PERIOD}s), waiting..."
        return 0
    fi

    # Container running but gateway dead - restart
    if is_in_cooldown "$bot"; then
        log "$container: Gateway dead but in cooldown"
        return 1
    fi

    local failures=$(get_failure_count "$bot")
    if [ "$failures" -ge $MAX_FAILURES_BEFORE_REBUILD ]; then
        full_rebuild "$bot"
        return $?
    fi

    log "$container: Gateway dead (uptime: ${uptime}s), restarting..."
    send_telegram "$container gateway unresponsive (${uptime}s uptime) - restarting..." "warning"
    set_cooldown "$bot"
    increment_failure "$bot"

    docker restart "$container" >/dev/null 2>&1

    # Hydrate context
    hydrate_context "$bot"

    # Wait for restart
    sleep $POST_RESTART_WAIT

    # Verify
    response=$(curl -s --connect-timeout 10 --max-time $HEALTH_CHECK_TIMEOUT "http://127.0.0.1:${port}/__clawdbot__/canvas/" 2>&1)
    if echo "$response" | grep -qi "clawdbot\|canvas\|gateway"; then
        log "$container: Recovery successful"
        send_telegram "$container recovered!" "success"
        reset_failures "$bot"
        return 0
    else
        log "$container: Recovery failed"
        send_telegram "$container recovery failed (attempt $((failures + 1)))" "critical"
        return 1
    fi
}

# Write status to state file for external monitors
update_state() {
    local status="$1"
    cat > "$STATE_FILE" << EOF
{
    "timestamp": "$(date -Iseconds)",
    "epoch": $(date +%s),
    "status": "$status",
    "watchdog_version": "v3",
    "bots": {
        "friday": {"running": $(docker ps --format '{{.Names}}' | grep -q clawdbot-friday && echo true || echo false), "failures": $(get_failure_count friday)},
        "matt": {"running": $(docker ps --format '{{.Names}}' | grep -q clawdbot-matt && echo true || echo false), "failures": $(get_failure_count matt)},
        "jarvis": {"running": $(docker ps --format '{{.Names}}' | grep -q clawdbot-jarvis && echo true || echo false), "failures": $(get_failure_count jarvis)}
    },
    "config": {
        "grace_period": $STARTUP_GRACE_PERIOD,
        "restart_wait": $POST_RESTART_WAIT,
        "cooldown": $RECOVERY_COOLDOWN
    }
}
EOF
}

# Main
mkdir -p /root/clawd/infra /var/log

log "=== Watchdog v3 run started ==="

all_healthy=true
for bot in friday matt jarvis; do
    if ! check_and_recover "$bot"; then
        all_healthy=false
    fi
done

if $all_healthy; then
    update_state "healthy"
else
    update_state "degraded"
fi

log "=== Watchdog v3 run completed ==="

# Cleanup old logs (keep last 2000 lines)
if [ -f "$LOGFILE" ]; then
    tail -2000 "$LOGFILE" > "${LOGFILE}.tmp" && mv "${LOGFILE}.tmp" "$LOGFILE"
fi
