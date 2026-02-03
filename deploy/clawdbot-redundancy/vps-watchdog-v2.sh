#!/bin/bash
# ClawdBot Health Watchdog v2 - Multi-Layer Self-Healing
# Layer 2: VPS-local recovery with escalation
# Runs every minute via cron: * * * * * /root/clawd/infra/bot-health-watchdog.sh

set -o pipefail

LOGFILE="/root/clawd/infra/watchdog.log"
STATE_FILE="/root/clawd/infra/watchdog-state.json"
BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
CHAT_ID="${TELEGRAM_CHAT_ID:-}"

# Recovery settings
RECOVERY_COOLDOWN=180      # 3 minutes between recovery attempts per bot
MAX_FAILURES_BEFORE_REBUILD=3  # After 3 failed recoveries, do full rebuild
STARTUP_GRACE_PERIOD=120   # 2 minutes grace after start

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
        -d "text=${emoji} $1" \
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

# Full rebuild: remove container and recreate from scratch
full_rebuild() {
    local bot="$1"
    local container="clawdbot-$bot"

    log "$container: FULL REBUILD triggered"
    send_telegram "<b>$container FULL REBUILD</b>
Previous recovery attempts failed.
Rebuilding from scratch..." "critical"

    # Get current container config
    local image=$(docker inspect --format '{{.Config.Image}}' "$container" 2>/dev/null || echo "node:22-slim")

    # Stop and remove
    docker stop "$container" >/dev/null 2>&1
    docker rm "$container" >/dev/null 2>&1
    sleep 2

    # Recreate based on bot type
    case "$bot" in
        friday)
            docker run -d \
                --name clawdbot-friday \
                --restart=always \
                -p 18789:18789 \
                -v /root/.clawdbot:/root/.clawdbot \
                -v /root/clawd:/root/clawd \
                -v /var/run/docker.sock:/var/run/docker.sock \
                node:22-slim \
                bash /root/clawd/friday/start.sh
            ;;
        matt)
            docker run -d \
                --name clawdbot-matt \
                --restart=always \
                -p 18800:18789 \
                -v /docker/clawdbot-gateway/config-matt:/root/.clawdbot \
                -v /root/clawd/matt:/root/clawd \
                -v /var/run/docker.sock:/var/run/docker.sock \
                -e INSTALL_CODEX=true \
                node:22-slim \
                bash /root/clawd/start.sh
            ;;
        jarvis)
            docker run -d \
                --name clawdbot-jarvis \
                --restart=always \
                -p 18801:18789 \
                -v /root/.clawdbot-jarvis:/root/.clawdbot \
                -v /root/clawd/jarvis:/root/clawd \
                -e XAI_API_KEY="${XAI_API_KEY}" \
                node:22-slim \
                bash /root/clawd/jarvis/start.sh
            ;;
    esac

    sleep 60  # Wait for container startup

    # Verify
    if docker ps --format "{{.Names}}" | grep -q "^${container}$"; then
        log "$container: REBUILD SUCCESS"
        send_telegram "$container rebuilt and running!" "success"
        reset_failures "$bot"
        return 0
    else
        log "$container: REBUILD FAILED"
        send_telegram "<b>$container REBUILD FAILED!</b>
Manual intervention required.

<code>ssh root@76.13.106.100
docker logs $container --tail 50</code>" "critical"
        return 1
    fi
}

check_and_recover() {
    local bot="$1"
    local container="clawdbot-$bot"

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
        sleep 45

        if docker ps --format "{{.Names}}" | grep -q "^${container}$"; then
            log "$container: Started successfully"
            send_telegram "$container is back online!" "success"
            reset_failures "$bot"
            return 0
        else
            log "$container: Failed to start"
            send_telegram "$container failed to start" "critical"
            return 1
        fi
    fi

    # Container running - check gateway health
    local response=$(curl -s --connect-timeout 5 --max-time 10 "http://127.0.0.1:${port}/" 2>&1)

    if echo "$response" | grep -q "clawdbot-app"; then
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
        log "$container: Recently started ($uptime s), waiting..."
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

    log "$container: Gateway dead, restarting..."
    send_telegram "$container gateway unresponsive - restarting..." "warning"
    set_cooldown "$bot"
    increment_failure "$bot"

    docker restart "$container" >/dev/null 2>&1
    sleep 45

    # Verify
    response=$(curl -s --connect-timeout 5 "http://127.0.0.1:${port}/" 2>&1)
    if echo "$response" | grep -q "clawdbot-app"; then
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
    "bots": {
        "friday": {"running": $(docker ps --format '{{.Names}}' | grep -q clawdbot-friday && echo true || echo false), "failures": $(get_failure_count friday)},
        "matt": {"running": $(docker ps --format '{{.Names}}' | grep -q clawdbot-matt && echo true || echo false), "failures": $(get_failure_count matt)},
        "jarvis": {"running": $(docker ps --format '{{.Names}}' | grep -q clawdbot-jarvis && echo true || echo false), "failures": $(get_failure_count jarvis)}
    }
}
EOF
}

# Main
mkdir -p /root/clawd/infra

log "=== Watchdog run started ==="

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

log "=== Watchdog run completed ==="

# Cleanup old logs (keep last 1000 lines)
if [ -f "$LOGFILE" ]; then
    tail -1000 "$LOGFILE" > "${LOGFILE}.tmp" && mv "${LOGFILE}.tmp" "$LOGFILE"
fi
