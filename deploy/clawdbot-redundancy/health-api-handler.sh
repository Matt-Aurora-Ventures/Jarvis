#!/bin/bash
# Handler script called by socat for each HTTP request

respond() {
    printf "HTTP/1.1 %s\r\nContent-Type: application/json\r\nAccess-Control-Allow-Origin: *\r\nConnection: close\r\n\r\n%s" "$1" "$2"
}

# Read HTTP request
read -r request_line
path=$(echo "$request_line" | cut -d' ' -f2 | cut -d'?' -f1)

case "$path" in
    /health|/)
        all_healthy=true
        friday_status="unhealthy"
        matt_status="unhealthy"
        jarvis_status="unhealthy"

        if curl -s --connect-timeout 2 http://127.0.0.1:18789/ 2>/dev/null | grep -q "clawdbot-app"; then
            friday_status="healthy"
        else
            all_healthy=false
        fi

        if curl -s --connect-timeout 2 http://127.0.0.1:18800/ 2>/dev/null | grep -q "clawdbot-app"; then
            matt_status="healthy"
        else
            all_healthy=false
        fi

        if curl -s --connect-timeout 2 http://127.0.0.1:18801/ 2>/dev/null | grep -q "clawdbot-app"; then
            jarvis_status="healthy"
        else
            all_healthy=false
        fi

        if $all_healthy; then
            respond "200 OK" "{\"status\":\"healthy\",\"timestamp\":\"$(date -Iseconds)\",\"bots\":{\"friday\":\"$friday_status\",\"matt\":\"$matt_status\",\"jarvis\":\"$jarvis_status\"}}"
        else
            respond "503 Service Unavailable" "{\"status\":\"degraded\",\"timestamp\":\"$(date -Iseconds)\",\"bots\":{\"friday\":\"$friday_status\",\"matt\":\"$matt_status\",\"jarvis\":\"$jarvis_status\"}}"
        fi
        ;;

    /recover/friday|/recover/matt|/recover/jarvis)
        bot=$(basename "$path")
        docker restart "clawdbot-$bot" >/dev/null 2>&1 &
        respond "200 OK" "{\"action\":\"restart\",\"bot\":\"$bot\",\"status\":\"initiated\",\"timestamp\":\"$(date -Iseconds)\"}"
        ;;

    /state)
        if [ -f /root/clawd/infra/watchdog-state.json ]; then
            respond "200 OK" "$(cat /root/clawd/infra/watchdog-state.json)"
        else
            respond "404 Not Found" "{\"error\":\"State file not found\"}"
        fi
        ;;

    /recover-all)
        for bot in friday matt jarvis; do
            docker restart "clawdbot-$bot" >/dev/null 2>&1 &
        done
        respond "200 OK" "{\"action\":\"restart-all\",\"status\":\"initiated\",\"timestamp\":\"$(date -Iseconds)\"}"
        ;;

    *)
        respond "404 Not Found" "{\"endpoints\":[\"/health\",\"/state\",\"/recover/{bot}\",\"/recover-all\"]}"
        ;;
esac
