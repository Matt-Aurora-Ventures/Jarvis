#!/bin/bash
#
# Nightly Analysis Script for Sleep-Time Compute
#
# Matt's deep knowledge synthesis routine - runs at 3 AM UTC
# Cron: 0 3 * * * /root/clawdbots/scripts/nightly_analysis.sh
#
# What it does:
# 1. Collects last 24h of logs from all agents
# 2. Runs pattern recognition via nightly_routine.py
# 3. Creates Supermemory derives (knowledge graph)
# 4. Updates SOUL files with insights
# 5. Sends summary to Telegram
#
# Author: ClawdMatt (Chief Growth Architect)
# Created: 2026-02-01
#

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================

# Paths (VPS defaults - override with env vars)
CLAWDBOTS_DIR="${CLAWDBOTS_DIR:-/root/clawdbots}"
LOGS_DIR="${LOGS_DIR:-${CLAWDBOTS_DIR}/logs}"
OUTPUT_DIR="${OUTPUT_DIR:-${CLAWDBOTS_DIR}/sleep_compute}"
NIGHTLY_LOG_DIR="${NIGHTLY_LOG_DIR:-${CLAWDBOTS_DIR}/logs/nightly}"

# Date for this run
RUN_DATE=$(date +%Y-%m-%d)
RUN_TIME=$(date +%H:%M:%S)

# Create directories
mkdir -p "${OUTPUT_DIR}/${RUN_DATE}"
mkdir -p "${NIGHTLY_LOG_DIR}"

# Log file for this run
LOG_FILE="${NIGHTLY_LOG_DIR}/nightly_${RUN_DATE}.log"

# =============================================================================
# Logging
# =============================================================================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"
}

log_error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" | tee -a "${LOG_FILE}" >&2
}

# =============================================================================
# Step 1: Collect Logs
# =============================================================================

collect_logs() {
    log "Step 1: Collecting logs from last 24 hours..."

    local analysis_dir="${OUTPUT_DIR}/${RUN_DATE}"

    # Friday logs
    if [[ -f "${LOGS_DIR}/friday_activity.log" ]]; then
        tail -n 5000 "${LOGS_DIR}/friday_activity.log" > "${analysis_dir}/friday.log"
        log "  - Collected friday_activity.log"
    else
        touch "${analysis_dir}/friday.log"
        log "  - friday_activity.log not found (created empty)"
    fi

    # Matt logs
    if [[ -f "${LOGS_DIR}/matt_activity.log" ]]; then
        tail -n 5000 "${LOGS_DIR}/matt_activity.log" > "${analysis_dir}/matt.log"
        log "  - Collected matt_activity.log"
    else
        touch "${analysis_dir}/matt.log"
        log "  - matt_activity.log not found (created empty)"
    fi

    # Jarvis logs
    if [[ -f "${LOGS_DIR}/jarvis_activity.log" ]]; then
        tail -n 5000 "${LOGS_DIR}/jarvis_activity.log" > "${analysis_dir}/jarvis.log"
        log "  - Collected jarvis_activity.log"
    else
        touch "${analysis_dir}/jarvis.log"
        log "  - jarvis_activity.log not found (created empty)"
    fi

    # Optional: Telegram messages (if export script exists)
    if [[ -f "${CLAWDBOTS_DIR}/scripts/export_group_messages.py" ]]; then
        python3 "${CLAWDBOTS_DIR}/scripts/export_group_messages.py" --last-24h > "${analysis_dir}/telegram.json" 2>/dev/null || true
        log "  - Collected telegram messages"
    fi

    log "Log collection complete."
}

# =============================================================================
# Step 2: Run Pattern Recognition
# =============================================================================

run_analysis() {
    log "Step 2: Running pattern recognition..."

    local analysis_dir="${OUTPUT_DIR}/${RUN_DATE}"

    # Activate virtual environment if it exists
    if [[ -f "${CLAWDBOTS_DIR}/.venv/bin/activate" ]]; then
        source "${CLAWDBOTS_DIR}/.venv/bin/activate"
    fi

    # Run the nightly routine
    python3 -m core.sleep_compute.nightly_routine \
        --logs-dir "${LOGS_DIR}" \
        --output-dir "${OUTPUT_DIR}" \
        --soul-dir "${CLAWDBOTS_DIR}" \
        --verbose \
        2>&1 | tee -a "${LOG_FILE}"

    if [[ $? -eq 0 ]]; then
        log "Pattern recognition complete."
    else
        log_error "Pattern recognition failed!"
        return 1
    fi
}

# =============================================================================
# Step 3: Send Telegram Summary (Optional)
# =============================================================================

send_summary() {
    log "Step 3: Sending summary to Telegram..."

    local summary_file="${OUTPUT_DIR}/${RUN_DATE}/summary.json"

    if [[ ! -f "${summary_file}" ]]; then
        log "  - No summary file found, skipping Telegram notification"
        return 0
    fi

    # Check if we have the required env vars
    if [[ -z "${CLAWDMATT_BOT_TOKEN:-}" ]] || [[ -z "${TEAM_CHAT_ID:-}" ]]; then
        log "  - CLAWDMATT_BOT_TOKEN or TEAM_CHAT_ID not set, skipping Telegram"
        return 0
    fi

    # Parse summary and send
    local patterns_found=$(jq -r '.patterns_found' "${summary_file}")
    local high_conf=$(jq -r '.high_confidence_patterns' "${summary_file}")
    local derives=$(jq -r '.derives_created' "${summary_file}")
    local duration=$(jq -r '.duration_seconds' "${summary_file}")

    local message="Sleep-Compute Report - ${RUN_DATE}

Analyzed 24h of activity across Friday, Matt, and Jarvis.

Patterns Detected: ${patterns_found}
High-Confidence Insights: ${high_conf}
Derives Created: ${derives}
Duration: ${duration}s

Full analysis: ${OUTPUT_DIR}/${RUN_DATE}/patterns.json"

    # Send via Telegram API
    curl -s -X POST \
        "https://api.telegram.org/bot${CLAWDMATT_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TEAM_CHAT_ID}" \
        -d "text=${message}" \
        -d "parse_mode=Markdown" > /dev/null

    log "Telegram summary sent."
}

# =============================================================================
# Step 4: Git Commit SOUL Changes (Optional)
# =============================================================================

commit_changes() {
    log "Step 4: Committing SOUL changes..."

    cd "${CLAWDBOTS_DIR}"

    # Check for changes
    if git diff --quiet CLAWD*_SOUL.md 2>/dev/null; then
        log "  - No SOUL changes to commit"
        return 0
    fi

    # Commit changes
    git add CLAWD*_SOUL.md
    git commit -m "Sleep-Compute: ${RUN_DATE} - Auto-derived insights" || true

    # Push if remote exists
    if git remote | grep -q origin; then
        git push origin main 2>/dev/null || log "  - Push failed (not critical)"
    fi

    log "SOUL changes committed."
}

# =============================================================================
# Main
# =============================================================================

main() {
    log "=========================================="
    log "Sleep-Time Compute - Nightly Analysis"
    log "Date: ${RUN_DATE} ${RUN_TIME}"
    log "=========================================="

    # Run all steps
    collect_logs
    run_analysis
    send_summary
    commit_changes

    log "=========================================="
    log "Nightly analysis complete!"
    log "=========================================="
}

# Run main
main "$@"
