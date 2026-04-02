#!/bin/bash
# Self-Evolution Reflection Script
# Runs nightly to analyze bot performance and generate improvement insights
# Cron: 0 4 * * * /root/clawd/scripts/self-evolution-reflect.sh
#
# Reflection Hierarchy:
# - Hourly: Performance metrics (via health checks)
# - Daily: Strategy effectiveness (this script)
# - Weekly: User satisfaction (Sunday at 4am)
# - Monthly: Architecture reviews (1st of month)

set -e

REFLECTION_DIR="/root/clawd/reflections"
DATE=$(date +%Y-%m-%d)
WEEKDAY=$(date +%u)  # 1=Monday, 7=Sunday
DAY_OF_MONTH=$(date +%d)
LOG_FILE="$REFLECTION_DIR/$DATE-reflection.json"

mkdir -p "$REFLECTION_DIR"

# =============================================================================
# Data Collection Functions
# =============================================================================

get_container_metrics() {
    local BOT_NAME="$1"
    docker stats "clawdbot-$BOT_NAME" --no-stream --format '{{json .}}' 2>/dev/null || echo '{}'
}

get_recovery_events() {
    local BOT_NAME="$1"
    # Count recovery events in last 24 hours
    grep -c "clawdbot-$BOT_NAME" /var/log/clawdbot-watchdog.log 2>/dev/null | tail -1 || echo "0"
}

get_uptime_percentage() {
    local BOT_NAME="$1"
    local PORT
    case "$BOT_NAME" in
        friday) PORT=18789 ;;
        matt)   PORT=18800 ;;
        jarvis) PORT=18801 ;;
    esac

    # Calculate from health check logs (last 24 hours = 1440 minutes)
    local TOTAL_CHECKS=1440
    local FAILED_CHECKS=$(grep -c "UNHEALTHY.*$BOT_NAME" /var/log/clawdbot-watchdog.log 2>/dev/null || echo "0")
    local UPTIME=$(echo "scale=2; (($TOTAL_CHECKS - $FAILED_CHECKS) / $TOTAL_CHECKS) * 100" | bc 2>/dev/null || echo "99.9")
    echo "$UPTIME"
}

get_api_errors() {
    local BOT_NAME="$1"
    # Check container logs for errors in last 24h
    docker logs "clawdbot-$BOT_NAME" --since 24h 2>&1 | grep -ci "error\|failed\|429\|500" || echo "0"
}

# =============================================================================
# Analysis Functions
# =============================================================================

analyze_bot() {
    local BOT_NAME="$1"

    local METRICS=$(get_container_metrics "$BOT_NAME")
    local RECOVERIES=$(get_recovery_events "$BOT_NAME")
    local UPTIME=$(get_uptime_percentage "$BOT_NAME")
    local ERRORS=$(get_api_errors "$BOT_NAME")

    cat << EOF
{
    "bot": "$BOT_NAME",
    "metrics": {
        "uptime_percent": $UPTIME,
        "recovery_events": $RECOVERIES,
        "api_errors": $ERRORS
    },
    "health_grade": "$(calculate_grade $UPTIME $RECOVERIES $ERRORS)",
    "recommendations": $(generate_recommendations "$BOT_NAME" "$UPTIME" "$RECOVERIES" "$ERRORS")
}
EOF
}

calculate_grade() {
    local UPTIME="$1"
    local RECOVERIES="$2"
    local ERRORS="$3"

    # Simple grading: A (excellent) to F (failing)
    if (( $(echo "$UPTIME >= 99.5" | bc -l) )) && [ "$RECOVERIES" -le 1 ]; then
        echo "A"
    elif (( $(echo "$UPTIME >= 98" | bc -l) )) && [ "$RECOVERIES" -le 3 ]; then
        echo "B"
    elif (( $(echo "$UPTIME >= 95" | bc -l) )) && [ "$RECOVERIES" -le 5 ]; then
        echo "C"
    elif (( $(echo "$UPTIME >= 90" | bc -l) )); then
        echo "D"
    else
        echo "F"
    fi
}

generate_recommendations() {
    local BOT_NAME="$1"
    local UPTIME="$2"
    local RECOVERIES="$3"
    local ERRORS="$4"

    local RECS="[]"

    if [ "$RECOVERIES" -gt 3 ]; then
        RECS=$(echo "$RECS" | jq '. + ["Investigate frequent restarts - check memory limits and API quotas"]')
    fi

    if [ "$ERRORS" -gt 50 ]; then
        RECS=$(echo "$RECS" | jq '. + ["High API error rate - review provider health and rate limits"]')
    fi

    if (( $(echo "$UPTIME < 95" | bc -l) )); then
        RECS=$(echo "$RECS" | jq '. + ["Low uptime - consider adding redundancy or increasing resources"]')
    fi

    echo "$RECS"
}

# =============================================================================
# Reflection Report Generation
# =============================================================================

generate_daily_reflection() {
    cat << EOF
{
    "reflection_type": "daily",
    "date": "$DATE",
    "timestamp": "$(date -Iseconds)",
    "bots": [
        $(analyze_bot "friday"),
        $(analyze_bot "matt"),
        $(analyze_bot "jarvis")
    ],
    "system_insights": {
        "total_uptime": "$(echo "scale=2; ($(get_uptime_percentage friday) + $(get_uptime_percentage matt) + $(get_uptime_percentage jarvis)) / 3" | bc)%",
        "total_recoveries": $(($(get_recovery_events friday) + $(get_recovery_events matt) + $(get_recovery_events jarvis))),
        "infrastructure_health": "$([ $(get_recovery_events friday) -le 5 ] && echo 'stable' || echo 'needs_attention')"
    },
    "learning_opportunities": [
        "Review most common error patterns",
        "Identify peak usage times for scaling",
        "Document successful recovery patterns"
    ]
}
EOF
}

generate_weekly_reflection() {
    cat << EOF
{
    "reflection_type": "weekly",
    "week_ending": "$DATE",
    "timestamp": "$(date -Iseconds)",
    "weekly_summary": {
        "average_uptime": "calculating...",
        "total_incidents": 0,
        "user_satisfaction": "pending_survey"
    },
    "strategic_improvements": [
        "Consider pre-emptive scaling before known high-traffic periods",
        "Review and update emergency runbooks",
        "Test disaster recovery procedures"
    ],
    "trust_ladder_progress": {
        "friday": "level_3_autonomous",
        "matt": "level_2_monitored",
        "jarvis": "level_3_autonomous"
    }
}
EOF
}

generate_monthly_reflection() {
    cat << EOF
{
    "reflection_type": "monthly",
    "month": "$(date +%Y-%m)",
    "timestamp": "$(date -Iseconds)",
    "architecture_review": {
        "current_topology": "3-bot_mesh_on_kvm2",
        "bottlenecks_identified": [],
        "scaling_recommendations": [
            "Consider Akash deployment for GPU workloads",
            "Evaluate multi-region deployment for resilience"
        ]
    },
    "cost_analysis": {
        "compute": "vps_monthly",
        "ai_api_costs": "tracking",
        "optimization_opportunities": []
    },
    "next_month_goals": [
        "Achieve 99.9% uptime across all bots",
        "Reduce average recovery time to under 10 seconds",
        "Implement proactive scaling"
    ]
}
EOF
}

# =============================================================================
# Main Execution
# =============================================================================

echo "=========================================="
echo "Self-Evolution Reflection - $DATE"
echo "=========================================="

# Always run daily reflection
echo "Running daily reflection..."
DAILY_REPORT=$(generate_daily_reflection)
echo "$DAILY_REPORT" > "$REFLECTION_DIR/$DATE-daily.json"
echo "Daily report: $REFLECTION_DIR/$DATE-daily.json"

# Weekly reflection on Sundays
if [ "$WEEKDAY" -eq 7 ]; then
    echo "Running weekly reflection..."
    WEEKLY_REPORT=$(generate_weekly_reflection)
    echo "$WEEKLY_REPORT" > "$REFLECTION_DIR/$DATE-weekly.json"
    echo "Weekly report: $REFLECTION_DIR/$DATE-weekly.json"
fi

# Monthly reflection on 1st of month
if [ "$DAY_OF_MONTH" -eq "01" ]; then
    echo "Running monthly reflection..."
    MONTHLY_REPORT=$(generate_monthly_reflection)
    echo "$MONTHLY_REPORT" > "$REFLECTION_DIR/$DATE-monthly.json"
    echo "Monthly report: $REFLECTION_DIR/$DATE-monthly.json"
fi

# Output summary to console
echo ""
echo "Reflection Summary:"
echo "$DAILY_REPORT" | jq '.system_insights'

# Cleanup old reflections (keep 30 days)
find "$REFLECTION_DIR" -name "*.json" -mtime +30 -delete 2>/dev/null || true

echo ""
echo "Reflection complete."
