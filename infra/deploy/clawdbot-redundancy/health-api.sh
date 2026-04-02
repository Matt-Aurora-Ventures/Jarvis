#!/bin/bash
# Simple HTTP Health API for ClawdBots
# Runs via socat to provide external health check endpoint
# Install: apt-get install -y socat
# Run: nohup /root/clawd/infra/health-api.sh &

PORT=18888

respond() {
    local status="$1"
    local body="$2"
    printf "HTTP/1.1 %s\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n%s" "$status" "$body"
}

handle_request() {
    read -r request_line
    local path=$(echo "$request_line" | cut -d' ' -f2)

    case "$path" in
        /health|/)
            # Quick health check
            local all_healthy=true
            local status_json=""

            for bot in friday matt jarvis; do
                local port=""
                case "$bot" in
                    friday) port=18789 ;;
                    matt) port=18800 ;;
                    jarvis) port=18801 ;;
                esac

                if curl -s --connect-timeout 2 "http://127.0.0.1:$port/" | grep -q "clawdbot-app"; then
                    status_json="$status_json\"$bot\":\"healthy\","
                else
                    status_json="$status_json\"$bot\":\"unhealthy\","
                    all_healthy=false
                fi
            done

            status_json="${status_json%,}"  # Remove trailing comma

            if $all_healthy; then
                respond "200 OK" "{\"status\":\"healthy\",\"timestamp\":\"$(date -Iseconds)\",\"bots\":{$status_json}}"
            else
                respond "503 Service Unavailable" "{\"status\":\"degraded\",\"timestamp\":\"$(date -Iseconds)\",\"bots\":{$status_json}}"
            fi
            ;;

        /recover/*)
            # Recover a specific bot
            local bot=$(echo "$path" | sed 's|/recover/||')
            if [[ "$bot" =~ ^(friday|matt|jarvis)$ ]]; then
                docker restart "clawdbot-$bot" >/dev/null 2>&1
                respond "200 OK" "{\"action\":\"restart\",\"bot\":\"$bot\",\"status\":\"initiated\"}"
            else
                respond "400 Bad Request" "{\"error\":\"Invalid bot name\"}"
            fi
            ;;

        /state)
            # Return watchdog state
            if [ -f /root/clawd/infra/watchdog-state.json ]; then
                respond "200 OK" "$(cat /root/clawd/infra/watchdog-state.json)"
            else
                respond "404 Not Found" "{\"error\":\"State file not found\"}"
            fi
            ;;

        *)
            respond "404 Not Found" "{\"error\":\"Not found\",\"endpoints\":[\"/health\",\"/state\",\"/recover/{bot}\"]}"
            ;;
    esac
}

echo "Starting ClawdBot Health API on port $PORT..."
while true; do
    socat TCP-LISTEN:$PORT,reuseaddr,fork EXEC:"/root/clawd/infra/health-api.sh handle"
done
