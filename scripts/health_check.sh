#!/bin/bash
# JARVIS ClawdBots Health Check Script
# Comprehensive health check for VPS deployment
#
# Usage:
#   ./health_check.sh           # Run all checks, human-readable output
#   ./health_check.sh --json    # Run all checks, JSON output
#   ./health_check.sh --quiet   # Minimal output, exit code only
#
# Exit codes:
#   0 = All healthy
#   1 = Warnings/degraded
#   2 = Critical/unhealthy

set -o pipefail

# Configuration
BOTS_DIR="${BOTS_DIR:-/root/clawdbots}"
LOG_DIR="${LOG_DIR:-$BOTS_DIR/logs}"
MIN_DISK_GB=1
MIN_MEMORY_MB=500

# Output mode
JSON_OUTPUT=false
QUIET_MODE=false

# Colors (disabled for JSON output)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --json|-j)
            JSON_OUTPUT=true
            shift
            ;;
        --quiet|-q)
            QUIET_MODE=true
            shift
            ;;
        *)
            shift
            ;;
    esac
done

# Disable colors for JSON output
if $JSON_OUTPUT; then
    RED=""
    GREEN=""
    YELLOW=""
    BLUE=""
    NC=""
fi

# Results storage
declare -A RESULTS
OVERALL_STATUS="healthy"
WARNINGS=0
ERRORS=0

# Helper functions
log_info() {
    if ! $QUIET_MODE && ! $JSON_OUTPUT; then
        echo -e "${BLUE}[INFO]${NC} $1"
    fi
}

log_ok() {
    if ! $QUIET_MODE && ! $JSON_OUTPUT; then
        echo -e "${GREEN}[OK]${NC} $1"
    fi
    RESULTS["$2"]="ok"
}

log_warn() {
    if ! $QUIET_MODE && ! $JSON_OUTPUT; then
        echo -e "${YELLOW}[WARN]${NC} $1"
    fi
    RESULTS["$2"]="warning"
    ((WARNINGS++))
    if [[ "$OVERALL_STATUS" == "healthy" ]]; then
        OVERALL_STATUS="degraded"
    fi
}

log_error() {
    if ! $QUIET_MODE && ! $JSON_OUTPUT; then
        echo -e "${RED}[ERROR]${NC} $1"
    fi
    RESULTS["$2"]="error"
    ((ERRORS++))
    OVERALL_STATUS="critical"
}

# Check if a bot is running
check_bot() {
    local bot_name=$1
    local pattern=$2

    if pgrep -f "$pattern" > /dev/null 2>&1; then
        local pid=$(pgrep -f "$pattern" | head -n1)
        local uptime=$(ps -p $pid -o etime= 2>/dev/null | tr -d ' ')
        log_ok "$bot_name is running (PID: $pid, Uptime: $uptime)" "bot_$bot_name"
        return 0
    else
        log_warn "$bot_name is NOT running" "bot_$bot_name"
        return 1
    fi
}

# Check all ClawdBots
check_bots() {
    log_info "Checking bot processes..."

    local running=0
    local total=0

    # ClawdMatt
    ((total++))
    if check_bot "clawdmatt" "clawdmatt"; then
        ((running++))
    fi

    # ClawdJarvis
    ((total++))
    if check_bot "clawdjarvis" "clawdjarvis"; then
        ((running++))
    fi

    # ClawdFriday
    ((total++))
    if check_bot "clawdfriday" "clawdfriday"; then
        ((running++))
    fi

    # Store summary
    RESULTS["bots_running"]=$running
    RESULTS["bots_total"]=$total

    if [[ $running -eq $total ]]; then
        log_ok "All $total bots running"
    elif [[ $running -gt 0 ]]; then
        log_warn "Only $running of $total bots running"
    else
        log_error "No bots running!"
    fi
}

# Check disk space
check_disk() {
    log_info "Checking disk space..."

    # Get root partition usage
    local usage=$(df -BG / | awk 'NR==2 {print $5}' | sed 's/%//')
    local free=$(df -BG / | awk 'NR==2 {print $4}' | sed 's/G//')

    RESULTS["disk_usage_percent"]=$usage
    RESULTS["disk_free_gb"]=$free

    if [[ $free -lt $MIN_DISK_GB ]]; then
        log_error "Disk space critical: ${free}GB free (< ${MIN_DISK_GB}GB)" "disk"
    elif [[ $usage -gt 90 ]]; then
        log_warn "Disk space warning: ${usage}% used" "disk"
    elif [[ $usage -gt 80 ]]; then
        log_warn "Disk space elevated: ${usage}% used" "disk"
    else
        log_ok "Disk space healthy: ${usage}% used, ${free}GB free" "disk"
    fi
}

# Check memory
check_memory() {
    log_info "Checking memory..."

    local total=$(free -m | awk 'NR==2 {print $2}')
    local used=$(free -m | awk 'NR==2 {print $3}')
    local available=$(free -m | awk 'NR==2 {print $7}')
    local usage=$((used * 100 / total))

    RESULTS["memory_total_mb"]=$total
    RESULTS["memory_used_mb"]=$used
    RESULTS["memory_available_mb"]=$available
    RESULTS["memory_usage_percent"]=$usage

    if [[ $available -lt $MIN_MEMORY_MB ]]; then
        log_error "Memory critical: ${available}MB available (< ${MIN_MEMORY_MB}MB)" "memory"
    elif [[ $usage -gt 90 ]]; then
        log_warn "Memory warning: ${usage}% used" "memory"
    elif [[ $usage -gt 80 ]]; then
        log_warn "Memory elevated: ${usage}% used" "memory"
    else
        log_ok "Memory healthy: ${usage}% used, ${available}MB available" "memory"
    fi
}

# Check API connectivity
check_api() {
    local name=$1
    local url=$2
    local timeout=${3:-5}

    if command -v curl &> /dev/null; then
        local start=$(date +%s%N)
        local status=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout $timeout "$url" 2>/dev/null)
        local end=$(date +%s%N)
        local duration=$(( (end - start) / 1000000 ))

        RESULTS["api_${name}_latency_ms"]=$duration
        RESULTS["api_${name}_status"]=$status

        if [[ "$status" == "200" ]]; then
            log_ok "$name API reachable (${duration}ms)" "api_$name"
            return 0
        elif [[ "$status" == "429" ]]; then
            log_warn "$name API rate limited" "api_$name"
            return 1
        else
            log_warn "$name API returned $status" "api_$name"
            return 1
        fi
    else
        log_warn "curl not available, skipping API check" "api_$name"
        return 1
    fi
}

# Check API connectivity
check_apis() {
    log_info "Checking API connectivity..."

    # Check Jupiter API
    check_api "jupiter" "https://quote-api.jup.ag/v6/health"

    # Check Telegram API (if token is available)
    if [[ -n "$TELEGRAM_BOT_TOKEN" ]]; then
        check_api "telegram" "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe"
    else
        log_info "Telegram token not set, skipping API check"
        RESULTS["api_telegram"]="not_configured"
    fi
}

# Check log files for errors
check_logs() {
    log_info "Checking logs for recent errors..."

    if [[ ! -d "$LOG_DIR" ]]; then
        log_warn "Log directory not found: $LOG_DIR" "logs"
        return
    fi

    local total_errors=0

    for logfile in "$LOG_DIR"/*.log; do
        if [[ -f "$logfile" ]]; then
            local name=$(basename "$logfile" .log)
            # Count errors in last 100 lines
            local errors=$(tail -n 100 "$logfile" 2>/dev/null | grep -ci "error" || echo "0")
            total_errors=$((total_errors + errors))

            RESULTS["log_${name}_errors"]=$errors

            if [[ $errors -gt 10 ]]; then
                log_warn "$name: $errors errors in recent log" "log_$name"
            fi
        fi
    done

    RESULTS["logs_total_errors"]=$total_errors

    if [[ $total_errors -gt 50 ]]; then
        log_warn "High error count in logs: $total_errors"
    elif [[ $total_errors -gt 0 ]]; then
        log_ok "Logs checked: $total_errors errors found"
    else
        log_ok "Logs clean: no recent errors"
    fi
}

# Generate JSON output
output_json() {
    echo "{"
    echo "  \"status\": \"$OVERALL_STATUS\","
    echo "  \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\","
    echo "  \"hostname\": \"$(hostname)\","
    echo "  \"warnings\": $WARNINGS,"
    echo "  \"errors\": $ERRORS,"
    echo "  \"checks\": {"

    local first=true
    for key in "${!RESULTS[@]}"; do
        if $first; then
            first=false
        else
            echo ","
        fi
        echo -n "    \"$key\": \"${RESULTS[$key]}\""
    done

    echo ""
    echo "  }"
    echo "}"
}

# Main execution
main() {
    if ! $QUIET_MODE && ! $JSON_OUTPUT; then
        echo ""
        echo "========================================"
        echo "  ClawdBots Health Check"
        echo "  $(date)"
        echo "========================================"
        echo ""
    fi

    # Run all checks
    check_bots
    check_disk
    check_memory
    check_apis
    check_logs

    # Output results
    if $JSON_OUTPUT; then
        output_json
    elif ! $QUIET_MODE; then
        echo ""
        echo "========================================"
        echo "  Summary"
        echo "========================================"
        echo ""
        echo "Status: $OVERALL_STATUS"
        echo "Warnings: $WARNINGS"
        echo "Errors: $ERRORS"
        echo ""
    fi

    # Return appropriate exit code
    case $OVERALL_STATUS in
        "healthy")
            exit 0
            ;;
        "degraded")
            exit 1
            ;;
        "critical"|"unhealthy")
            exit 2
            ;;
        *)
            exit 3
            ;;
    esac
}

# Run main
main
