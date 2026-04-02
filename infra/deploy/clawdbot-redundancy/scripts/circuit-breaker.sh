#!/bin/bash
# Circuit Breaker for AI Providers
# Implements the circuit breaker pattern to prevent cascade failures
#
# States:
# - CLOSED: Normal operation, requests flow through
# - OPEN: Circuit tripped, requests blocked, using fallback
# - HALF_OPEN: Testing if provider recovered
#
# Usage:
#   ./circuit-breaker.sh status              - Show all provider states
#   ./circuit-breaker.sh check openai        - Check if provider is available
#   ./circuit-breaker.sh record openai success
#   ./circuit-breaker.sh record openai failure
#   ./circuit-breaker.sh reset openai        - Force reset circuit

set -e

CB_DB="/root/clawd/data/circuit-breaker.json"
mkdir -p "$(dirname $CB_DB)"

# Configuration
FAILURE_THRESHOLD=5           # Failures before opening circuit
RECOVERY_TIMEOUT=300          # Seconds before trying half-open (5 min)
HALF_OPEN_SUCCESSES=3         # Successes needed to close circuit
SUCCESS_THRESHOLD=10          # Successes to reset failure count

# Initialize database if not exists
if [ ! -f "$CB_DB" ]; then
    cat > "$CB_DB" << 'EOF'
{
    "providers": {
        "dexter": {
            "state": "CLOSED",
            "failures": 0,
            "successes": 0,
            "last_failure": null,
            "last_success": null,
            "opened_at": null,
            "half_open_successes": 0,
            "description": "Default - Free Claude CLI for Telegram"
        },
        "ollama": {
            "state": "CLOSED",
            "failures": 0,
            "successes": 0,
            "last_failure": null,
            "last_success": null,
            "opened_at": null,
            "half_open_successes": 0,
            "description": "Free local inference - first fallback"
        },
        "xai": {
            "state": "CLOSED",
            "failures": 0,
            "successes": 0,
            "last_failure": null,
            "last_success": null,
            "opened_at": null,
            "half_open_successes": 0,
            "description": "Paid - Grok for sentiment analysis only"
        },
        "groq": {
            "state": "CLOSED",
            "failures": 0,
            "successes": 0,
            "last_failure": null,
            "last_success": null,
            "opened_at": null,
            "half_open_successes": 0,
            "description": "Free tier - Code/chat backup"
        },
        "openrouter": {
            "state": "CLOSED",
            "failures": 0,
            "successes": 0,
            "last_failure": null,
            "last_success": null,
            "opened_at": null,
            "half_open_successes": 0,
            "description": "Paid - Last resort only"
        },
        "anthropic": {
            "state": "CLOSED",
            "failures": 0,
            "successes": 0,
            "last_failure": null,
            "last_success": null,
            "opened_at": null,
            "half_open_successes": 0,
            "description": "Direct API - High priority"
        }
    },
    "fallback_chain": ["dexter", "ollama", "xai", "groq", "openrouter"],
    "config": {
        "failure_threshold": 5,
        "recovery_timeout_seconds": 300,
        "half_open_successes_required": 3
    }
}
EOF
fi

# =============================================================================
# Helper Functions
# =============================================================================

get_state() {
    local PROVIDER="$1"
    jq -r ".providers.$PROVIDER.state // \"UNKNOWN\"" "$CB_DB"
}

get_failures() {
    local PROVIDER="$1"
    jq -r ".providers.$PROVIDER.failures // 0" "$CB_DB"
}

get_opened_at() {
    local PROVIDER="$1"
    jq -r ".providers.$PROVIDER.opened_at // \"\"" "$CB_DB"
}

seconds_since_opened() {
    local PROVIDER="$1"
    local OPENED_AT=$(get_opened_at "$PROVIDER")

    if [ -z "$OPENED_AT" ] || [ "$OPENED_AT" = "null" ]; then
        echo "999999"
        return
    fi

    local OPENED_TS=$(date -d "$OPENED_AT" +%s 2>/dev/null || echo "0")
    local NOW_TS=$(date +%s)
    echo $((NOW_TS - OPENED_TS))
}

# =============================================================================
# Commands
# =============================================================================

show_status() {
    echo "=========================================="
    echo "Circuit Breaker Status"
    echo "=========================================="
    echo ""

    for provider in openai anthropic xai google ollama; do
        local STATE=$(get_state "$provider")
        local FAILURES=$(get_failures "$provider")
        local SUCCESSES=$(jq -r ".providers.$provider.successes // 0" "$CB_DB")

        local ICON="✅"
        [ "$STATE" = "OPEN" ] && ICON="🔴"
        [ "$STATE" = "HALF_OPEN" ] && ICON="🟡"

        echo "$ICON $provider:"
        echo "   State: $STATE"
        echo "   Failures: $FAILURES / $FAILURE_THRESHOLD"
        echo "   Successes: $SUCCESSES"

        if [ "$STATE" = "OPEN" ]; then
            local ELAPSED=$(seconds_since_opened "$provider")
            local REMAINING=$((RECOVERY_TIMEOUT - ELAPSED))
            if [ "$REMAINING" -gt 0 ]; then
                echo "   Recovery in: ${REMAINING}s"
            else
                echo "   Ready for half-open test"
            fi
        fi
        echo ""
    done

    echo "Fallback chain: $(jq -r '.fallback_chain | join(" -> ")' "$CB_DB")"
}

check_provider() {
    local PROVIDER="$1"
    local STATE=$(get_state "$PROVIDER")

    case "$STATE" in
        CLOSED)
            echo "AVAILABLE"
            return 0
            ;;
        HALF_OPEN)
            echo "TESTING"
            return 0
            ;;
        OPEN)
            local ELAPSED=$(seconds_since_opened "$PROVIDER")
            if [ "$ELAPSED" -ge "$RECOVERY_TIMEOUT" ]; then
                # Transition to half-open
                jq ".providers.$PROVIDER.state = \"HALF_OPEN\" | .providers.$PROVIDER.half_open_successes = 0" "$CB_DB" > "${CB_DB}.tmp"
                mv "${CB_DB}.tmp" "$CB_DB"
                echo "TESTING"
                return 0
            fi
            echo "UNAVAILABLE"
            return 1
            ;;
        *)
            echo "UNKNOWN"
            return 1
            ;;
    esac
}

get_fallback() {
    local FAILED_PROVIDER="$1"

    # Get fallback chain and find first available
    local CHAIN=$(jq -r '.fallback_chain[]' "$CB_DB")

    for provider in $CHAIN; do
        if [ "$provider" != "$FAILED_PROVIDER" ]; then
            local AVAILABLE=$(check_provider "$provider" 2>/dev/null)
            if [ "$AVAILABLE" = "AVAILABLE" ] || [ "$AVAILABLE" = "TESTING" ]; then
                echo "$provider"
                return 0
            fi
        fi
    done

    echo "NONE"
    return 1
}

record_result() {
    local PROVIDER="$1"
    local RESULT="$2"
    local TIMESTAMP=$(date -Iseconds)
    local STATE=$(get_state "$PROVIDER")

    if [ "$RESULT" = "success" ]; then
        # Record success
        jq ".providers.$PROVIDER.successes += 1 | .providers.$PROVIDER.last_success = \"$TIMESTAMP\"" "$CB_DB" > "${CB_DB}.tmp"
        mv "${CB_DB}.tmp" "$CB_DB"

        case "$STATE" in
            HALF_OPEN)
                # Increment half-open successes
                local HO_SUCCESSES=$(jq -r ".providers.$PROVIDER.half_open_successes // 0" "$CB_DB")
                HO_SUCCESSES=$((HO_SUCCESSES + 1))

                if [ "$HO_SUCCESSES" -ge "$HALF_OPEN_SUCCESSES" ]; then
                    # Close circuit
                    jq ".providers.$PROVIDER.state = \"CLOSED\" | .providers.$PROVIDER.failures = 0 | .providers.$PROVIDER.half_open_successes = 0 | .providers.$PROVIDER.opened_at = null" "$CB_DB" > "${CB_DB}.tmp"
                    mv "${CB_DB}.tmp" "$CB_DB"
                    echo "✅ Circuit CLOSED for $PROVIDER (recovered)"
                else
                    jq ".providers.$PROVIDER.half_open_successes = $HO_SUCCESSES" "$CB_DB" > "${CB_DB}.tmp"
                    mv "${CB_DB}.tmp" "$CB_DB"
                    echo "🟡 Half-open success for $PROVIDER ($HO_SUCCESSES/$HALF_OPEN_SUCCESSES)"
                fi
                ;;
            CLOSED)
                # Reset failure count after enough successes
                local SUCCESSES=$(jq -r ".providers.$PROVIDER.successes // 0" "$CB_DB")
                if [ "$((SUCCESSES % SUCCESS_THRESHOLD))" -eq 0 ]; then
                    jq ".providers.$PROVIDER.failures = 0" "$CB_DB" > "${CB_DB}.tmp"
                    mv "${CB_DB}.tmp" "$CB_DB"
                fi
                echo "✅ Success recorded for $PROVIDER"
                ;;
        esac

    elif [ "$RESULT" = "failure" ]; then
        # Record failure
        jq ".providers.$PROVIDER.failures += 1 | .providers.$PROVIDER.last_failure = \"$TIMESTAMP\"" "$CB_DB" > "${CB_DB}.tmp"
        mv "${CB_DB}.tmp" "$CB_DB"

        local FAILURES=$(get_failures "$PROVIDER")

        case "$STATE" in
            CLOSED)
                if [ "$FAILURES" -ge "$FAILURE_THRESHOLD" ]; then
                    # Open circuit
                    jq ".providers.$PROVIDER.state = \"OPEN\" | .providers.$PROVIDER.opened_at = \"$TIMESTAMP\"" "$CB_DB" > "${CB_DB}.tmp"
                    mv "${CB_DB}.tmp" "$CB_DB"
                    echo "🔴 Circuit OPENED for $PROVIDER (threshold reached)"

                    # Suggest fallback
                    local FALLBACK=$(get_fallback "$PROVIDER")
                    if [ "$FALLBACK" != "NONE" ]; then
                        echo "   Fallback: $FALLBACK"
                    fi
                else
                    echo "⚠️ Failure recorded for $PROVIDER ($FAILURES/$FAILURE_THRESHOLD)"
                fi
                ;;
            HALF_OPEN)
                # Re-open circuit
                jq ".providers.$PROVIDER.state = \"OPEN\" | .providers.$PROVIDER.opened_at = \"$TIMESTAMP\" | .providers.$PROVIDER.half_open_successes = 0" "$CB_DB" > "${CB_DB}.tmp"
                mv "${CB_DB}.tmp" "$CB_DB"
                echo "🔴 Circuit RE-OPENED for $PROVIDER (half-open test failed)"
                ;;
            OPEN)
                echo "🔴 Failure recorded for $PROVIDER (circuit already open)"
                ;;
        esac
    fi
}

reset_circuit() {
    local PROVIDER="$1"

    jq ".providers.$PROVIDER = {\"state\": \"CLOSED\", \"failures\": 0, \"successes\": 0, \"last_failure\": null, \"last_success\": null, \"opened_at\": null, \"half_open_successes\": 0}" "$CB_DB" > "${CB_DB}.tmp"
    mv "${CB_DB}.tmp" "$CB_DB"

    echo "✅ Circuit reset for $PROVIDER"
}

# =============================================================================
# Main
# =============================================================================

case "${1:-status}" in
    status)
        show_status
        ;;
    check)
        if [ -z "$2" ]; then
            echo "Usage: $0 check <provider>"
            exit 1
        fi
        check_provider "$2"
        ;;
    fallback)
        if [ -z "$2" ]; then
            echo "Usage: $0 fallback <failed_provider>"
            exit 1
        fi
        get_fallback "$2"
        ;;
    record)
        if [ -z "$2" ] || [ -z "$3" ]; then
            echo "Usage: $0 record <provider> <success|failure>"
            exit 1
        fi
        record_result "$2" "$3"
        ;;
    reset)
        if [ -z "$2" ]; then
            echo "Usage: $0 reset <provider>"
            exit 1
        fi
        reset_circuit "$2"
        ;;
    *)
        echo "Usage: $0 {status|check|fallback|record|reset}"
        echo ""
        echo "Commands:"
        echo "  status                    Show all circuit states"
        echo "  check <provider>          Check if provider is available"
        echo "  fallback <provider>       Get fallback for failed provider"
        echo "  record <provider> <result> Record success/failure"
        echo "  reset <provider>          Force reset circuit"
        ;;
esac
