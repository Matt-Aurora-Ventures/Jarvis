#!/bin/bash
# Clawdbot Watchdog - Monitors and auto-recovers the gateway
# Run via cron: */5 * * * * /home/lucid/clawd/scripts/watchdog.sh

LOG_FILE="/home/lucid/.clawdbot/logs/watchdog.log"
MAX_LOG_SIZE=1048576  # 1MB

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# Rotate log if too big
if [ -f "$LOG_FILE" ] && [ $(stat -f%z "$LOG_FILE" 2>/dev/null || stat -c%s "$LOG_FILE" 2>/dev/null) -gt $MAX_LOG_SIZE ]; then
    mv "$LOG_FILE" "${LOG_FILE}.old"
fi

# Check if gateway is responding
check_gateway() {
    curl -s --max-time 5 http://127.0.0.1:18789/health > /dev/null 2>&1
    return $?
}

# Check if service is running
check_service() {
    systemctl --user is-active clawdbot.service > /dev/null 2>&1
    return $?
}

# Restart service
restart_service() {
    log "RESTART: Attempting service restart..."
    systemctl --user restart clawdbot.service
    sleep 10
    if check_gateway; then
        log "RESTART: Success - gateway responding"
        return 0
    else
        log "RESTART: Failed - gateway not responding after restart"
        return 1
    fi
}

# Network reset (WSL specific)
reset_network() {
    log "NETWORK: Resetting WSL network..."
    # Force DNS to public servers
    echo -e "nameserver 8.8.8.8\nnameserver 1.1.1.1" | sudo tee /etc/resolv.conf > /dev/null 2>&1
    sleep 2
}

# Main watchdog logic
main() {
    if check_gateway; then
        # All good, silent exit
        exit 0
    fi

    log "ALERT: Gateway not responding"

    if ! check_service; then
        log "ALERT: Service not running"
        restart_service
        exit $?
    fi

    # Service running but gateway not responding
    log "ALERT: Service running but gateway unresponsive"

    # Try network reset first
    reset_network
    sleep 5

    if check_gateway; then
        log "RECOVERY: Network reset fixed the issue"
        exit 0
    fi

    # Full restart
    restart_service
}

main
