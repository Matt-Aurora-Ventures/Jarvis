#!/bin/bash
# Trust Ladder Tracking System
# Tracks bot autonomy progression based on successful actions
#
# Levels:
# 1. Assisted (10 successful assists)
# 2. Monitored (50 successful executions)
# 3. Autonomous (200 successful actions, zero major errors)
# 4. Trusted (1000 successful actions, proactive suggestions allowed)
#
# Usage:
#   ./trust-ladder.sh status          - Show current trust levels
#   ./trust-ladder.sh record friday success "completed trade"
#   ./trust-ladder.sh record friday error "API timeout"
#   ./trust-ladder.sh promote friday  - Check and promote if eligible

set -e

TRUST_DB="/root/clawd/data/trust-ladder.json"
mkdir -p "$(dirname $TRUST_DB)"

# Initialize database if not exists
if [ ! -f "$TRUST_DB" ]; then
    cat > "$TRUST_DB" << 'EOF'
{
    "bots": {
        "friday": {
            "level": 1,
            "level_name": "assisted",
            "successful_actions": 0,
            "failed_actions": 0,
            "major_errors": 0,
            "proactive_suggestions": 0,
            "last_promotion": null,
            "history": []
        },
        "matt": {
            "level": 1,
            "level_name": "assisted",
            "successful_actions": 0,
            "failed_actions": 0,
            "major_errors": 0,
            "proactive_suggestions": 0,
            "last_promotion": null,
            "history": []
        },
        "jarvis": {
            "level": 1,
            "level_name": "assisted",
            "successful_actions": 0,
            "failed_actions": 0,
            "major_errors": 0,
            "proactive_suggestions": 0,
            "last_promotion": null,
            "history": []
        }
    },
    "level_requirements": {
        "1": {"name": "assisted", "successes": 0, "max_errors": 999},
        "2": {"name": "monitored", "successes": 10, "max_errors": 5},
        "3": {"name": "autonomous", "successes": 50, "max_errors": 2},
        "4": {"name": "trusted", "successes": 200, "max_errors": 0}
    }
}
EOF
fi

# =============================================================================
# Commands
# =============================================================================

show_status() {
    echo "=========================================="
    echo "Trust Ladder Status"
    echo "=========================================="
    echo ""

    for bot in friday matt jarvis; do
        local LEVEL=$(jq -r ".bots.$bot.level" "$TRUST_DB")
        local LEVEL_NAME=$(jq -r ".bots.$bot.level_name" "$TRUST_DB")
        local SUCCESSES=$(jq -r ".bots.$bot.successful_actions" "$TRUST_DB")
        local ERRORS=$(jq -r ".bots.$bot.major_errors" "$TRUST_DB")

        # Calculate next level requirements
        local NEXT_LEVEL=$((LEVEL + 1))
        local NEXT_REQ=$(jq -r ".level_requirements.\"$NEXT_LEVEL\".successes // \"MAX\"" "$TRUST_DB")

        echo "$bot:"
        echo "  Level: $LEVEL ($LEVEL_NAME)"
        echo "  Successful Actions: $SUCCESSES"
        echo "  Major Errors: $ERRORS"
        if [ "$NEXT_REQ" != "MAX" ]; then
            echo "  Progress to Level $NEXT_LEVEL: $SUCCESSES / $NEXT_REQ"
        else
            echo "  Status: MAX LEVEL ACHIEVED"
        fi
        echo ""
    done
}

record_action() {
    local BOT="$1"
    local TYPE="$2"
    local DESCRIPTION="$3"
    local TIMESTAMP=$(date -Iseconds)

    if [ "$TYPE" = "success" ]; then
        # Increment successful actions
        jq ".bots.$BOT.successful_actions += 1 | .bots.$BOT.history += [{\"type\": \"success\", \"description\": \"$DESCRIPTION\", \"timestamp\": \"$TIMESTAMP\"}]" "$TRUST_DB" > "${TRUST_DB}.tmp"
        mv "${TRUST_DB}.tmp" "$TRUST_DB"
        echo "Recorded success for $BOT: $DESCRIPTION"

    elif [ "$TYPE" = "error" ]; then
        # Increment failed actions
        jq ".bots.$BOT.failed_actions += 1 | .bots.$BOT.history += [{\"type\": \"error\", \"description\": \"$DESCRIPTION\", \"timestamp\": \"$TIMESTAMP\"}]" "$TRUST_DB" > "${TRUST_DB}.tmp"
        mv "${TRUST_DB}.tmp" "$TRUST_DB"
        echo "Recorded error for $BOT: $DESCRIPTION"

    elif [ "$TYPE" = "major_error" ]; then
        # Increment major errors (affects trust level)
        jq ".bots.$BOT.major_errors += 1 | .bots.$BOT.failed_actions += 1 | .bots.$BOT.history += [{\"type\": \"major_error\", \"description\": \"$DESCRIPTION\", \"timestamp\": \"$TIMESTAMP\"}]" "$TRUST_DB" > "${TRUST_DB}.tmp"
        mv "${TRUST_DB}.tmp" "$TRUST_DB"
        echo "Recorded MAJOR ERROR for $BOT: $DESCRIPTION"

        # Check for demotion
        check_demotion "$BOT"

    elif [ "$TYPE" = "proactive" ]; then
        # Record proactive suggestion
        jq ".bots.$BOT.proactive_suggestions += 1 | .bots.$BOT.successful_actions += 1 | .bots.$BOT.history += [{\"type\": \"proactive\", \"description\": \"$DESCRIPTION\", \"timestamp\": \"$TIMESTAMP\"}]" "$TRUST_DB" > "${TRUST_DB}.tmp"
        mv "${TRUST_DB}.tmp" "$TRUST_DB"
        echo "Recorded proactive suggestion for $BOT: $DESCRIPTION"
    fi

    # Check for promotion
    check_promotion "$BOT"
}

check_promotion() {
    local BOT="$1"
    local CURRENT_LEVEL=$(jq -r ".bots.$BOT.level" "$TRUST_DB")
    local SUCCESSES=$(jq -r ".bots.$BOT.successful_actions" "$TRUST_DB")
    local ERRORS=$(jq -r ".bots.$BOT.major_errors" "$TRUST_DB")

    local NEXT_LEVEL=$((CURRENT_LEVEL + 1))
    local REQUIRED_SUCCESSES=$(jq -r ".level_requirements.\"$NEXT_LEVEL\".successes // 999999" "$TRUST_DB")
    local MAX_ERRORS=$(jq -r ".level_requirements.\"$NEXT_LEVEL\".max_errors // 0" "$TRUST_DB")
    local NEXT_NAME=$(jq -r ".level_requirements.\"$NEXT_LEVEL\".name // \"unknown\"" "$TRUST_DB")

    if [ "$SUCCESSES" -ge "$REQUIRED_SUCCESSES" ] && [ "$ERRORS" -le "$MAX_ERRORS" ]; then
        echo ""
        echo "🎉 PROMOTION: $BOT advancing to Level $NEXT_LEVEL ($NEXT_NAME)!"

        jq ".bots.$BOT.level = $NEXT_LEVEL | .bots.$BOT.level_name = \"$NEXT_NAME\" | .bots.$BOT.last_promotion = \"$(date -Iseconds)\"" "$TRUST_DB" > "${TRUST_DB}.tmp"
        mv "${TRUST_DB}.tmp" "$TRUST_DB"

        # Send notification (if Telegram configured)
        if command -v curl &> /dev/null && [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
            curl -s "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
                -d "chat_id=$TELEGRAM_CHAT_ID" \
                -d "text=🎉 Trust Ladder: $BOT promoted to Level $NEXT_LEVEL ($NEXT_NAME)!" \
                > /dev/null 2>&1
        fi
    fi
}

check_demotion() {
    local BOT="$1"
    local CURRENT_LEVEL=$(jq -r ".bots.$BOT.level" "$TRUST_DB")
    local ERRORS=$(jq -r ".bots.$BOT.major_errors" "$TRUST_DB")

    # Demote if too many errors for current level
    local MAX_ERRORS=$(jq -r ".level_requirements.\"$CURRENT_LEVEL\".max_errors // 999" "$TRUST_DB")

    if [ "$ERRORS" -gt "$MAX_ERRORS" ] && [ "$CURRENT_LEVEL" -gt 1 ]; then
        local NEW_LEVEL=$((CURRENT_LEVEL - 1))
        local NEW_NAME=$(jq -r ".level_requirements.\"$NEW_LEVEL\".name" "$TRUST_DB")

        echo ""
        echo "⚠️ DEMOTION: $BOT dropping to Level $NEW_LEVEL ($NEW_NAME) due to errors"

        jq ".bots.$BOT.level = $NEW_LEVEL | .bots.$BOT.level_name = \"$NEW_NAME\"" "$TRUST_DB" > "${TRUST_DB}.tmp"
        mv "${TRUST_DB}.tmp" "$TRUST_DB"
    fi
}

# =============================================================================
# Main
# =============================================================================

case "${1:-status}" in
    status)
        show_status
        ;;
    record)
        if [ -z "$2" ] || [ -z "$3" ]; then
            echo "Usage: $0 record <bot> <success|error|major_error|proactive> [description]"
            exit 1
        fi
        record_action "$2" "$3" "${4:-no description}"
        ;;
    promote)
        check_promotion "${2:-friday}"
        ;;
    *)
        echo "Usage: $0 {status|record|promote}"
        echo ""
        echo "Commands:"
        echo "  status                         Show trust levels for all bots"
        echo "  record <bot> <type> [desc]     Record an action"
        echo "  promote <bot>                  Check and promote if eligible"
        echo ""
        echo "Action types: success, error, major_error, proactive"
        ;;
esac
