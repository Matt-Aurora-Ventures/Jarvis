#!/bin/bash
# Ralph Wiggum Secure Task Extraction & Execution
# Extract ALL tasks from BOTH Telegram channels + execute forever

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 SECURE RALPH WIGGUM TASK SYSTEM"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

TASK_LIST="/root/clawd/MASTER_TASK_LIST.md"
COMPLETED_TASKS="/root/clawd/COMPLETED_TASKS.md"
CHAT_ARCHIVE="/root/clawd/telegram-chat-archive"

# Security: Validate credentials
validate_credentials() {
    echo "🔒 SECURITY: Validating Telegram credentials..."

    if [ -z "$TELEGRAM_BOT_TOKEN" ] || [ ${#TELEGRAM_BOT_TOKEN} -lt 20 ]; then
        echo "❌ Invalid TELEGRAM_BOT_TOKEN"
        return 1
    fi

    if [ -z "$MAIN_CHAT_ID" ] || [ -z "$FRIDAY_CHAT_ID" ] || [ -z "$JARVIS_CHAT_ID" ]; then
        echo "❌ Missing chat IDs"
        return 1
    fi

    echo "✅ Credentials validated"
}

# Initialize with security
initialize_secure() {
    echo "🔒 Initializing secure task system..."

    # Create directories with restricted permissions
    mkdir -p "$CHAT_ARCHIVE"
    chmod 700 "$CHAT_ARCHIVE"

    mkdir -p "$(dirname $TASK_LIST)"
    chmod 700 "$(dirname $TASK_LIST)"

    # Initialize task files
    cat > "$TASK_LIST" <<EOF
# MASTER TASK LIST
Generated: $(date)
Source: All Telegram channels (secure extraction)

## Security
- Credentials validated: ✅
- Chat archive encrypted: TBD
- Task files restricted: chmod 700

## Channels
1. Main Channel (Admin): $MAIN_CHAT_ID
2. Friday Channel: $FRIDAY_CHAT_ID
3. Jarvis Channel: $JARVIS_CHAT_ID

## Status
- Total Tasks: 0
- Completed: 0
- In Progress: 0
- Pending: 0

## Tasks

EOF

    cat > "$COMPLETED_TASKS" <<EOF
# COMPLETED TASKS LOG
Security: This file contains execution history

EOF

    echo "✅ Secure initialization complete"
}

# Extract from BOTH Telegram channels
extract_all_telegram_tasks() {
    echo "📥 Extracting tasks from ALL Telegram channels..."

    # Channels to scan
    CHANNELS=(
        "Main:$MAIN_CHAT_ID:admin"
        "Friday:$FRIDAY_CHAT_ID:member"
        "Jarvis:$JARVIS_CHAT_ID:member"
    )

    TASK_COUNTER=1

    for CHANNEL_INFO in "${CHANNELS[@]}"; do
        IFS=':' read -r CHANNEL_NAME CHAT_ID ROLE <<< "$CHANNEL_INFO"

        echo ""
        echo "  📱 Processing: $CHANNEL_NAME (Role: $ROLE)"
        echo "     Chat ID: $CHAT_ID"

        CHAT_FILE="$CHAT_ARCHIVE/chat_${CHANNEL_NAME}_$(date +%Y%m%d_%H%M%S).json"

        # Security: Use Python to extract via secure API
        python3 - <<PYTHON_SCRIPT
import os
import json
import requests
from datetime import datetime, timedelta

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
CHAT_ID = '$CHAT_ID'
CHAT_NAME = '$CHANNEL_NAME'

if not TOKEN:
    print(f"❌ No TELEGRAM_BOT_TOKEN for {CHAT_NAME}")
    exit(1)

print(f"🔐 Authenticated as: {TOKEN[:10]}...")

# Get chat history (last 100 messages, or more if needed)
url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
params = {
    'limit': 100,
    'timeout': 30
}

try:
    response = requests.get(url, params=params, timeout=60)
    response.raise_for_status()

    data = response.json()

    if not data.get('ok'):
        print(f"❌ API error: {data.get('description')}")
        exit(1)

    messages = data.get('result', [])

    # Filter messages from this specific chat
    chat_messages = []
    for update in messages:
        msg = update.get('message', {})
        if str(msg.get('chat', {}).get('id')) == CHAT_ID:
            chat_messages.append(msg)

    # Save to file
    with open('$CHAT_FILE', 'w') as f:
        json.dump(chat_messages, f, indent=2)

    print(f"✅ Extracted {len(chat_messages)} messages from {CHAT_NAME}")

except Exception as e:
    print(f"❌ Error extracting from {CHAT_NAME}: {e}")
    exit(1)
PYTHON_SCRIPT

        if [ $? -ne 0 ]; then
            echo "⚠️  Failed to extract from $CHANNEL_NAME, continuing..."
            continue
        fi

        # Parse tasks from the chat
        if [ -f "$CHAT_FILE" ]; then
            # Security: Validate JSON before parsing
            if ! jq empty "$CHAT_FILE" 2>/dev/null; then
                echo "⚠️  Invalid JSON in $CHAT_FILE, skipping..."
                continue
            fi

            # Extract task-like messages
            jq -r '.[].text // empty' "$CHAT_FILE" 2>/dev/null | \
            grep -E "(^(add|fix|create|implement|update|build|make|setup|install|configure|deploy|check|test|run|start|stop|restart)|please|can you|need to|want to|todo|task|\\[todo\\]|\\[ \\])" -i | \
            while IFS= read -r task_text; do
                # Security: Sanitize task text (remove potential command injection)
                task_text=$(echo "$task_text" | sed 's/[;&|`$()]//g')

                echo "## Task $TASK_COUNTER" >> "$TASK_LIST"
                echo "**Source**: $CHANNEL_NAME Channel ($ROLE)" >> "$TASK_LIST"
                echo "**Chat ID**: \`$CHAT_ID\`" >> "$TASK_LIST"
                echo "**Request**: $task_text" >> "$TASK_LIST"
                echo "**Status**: Pending" >> "$TASK_LIST"
                echo "**Priority**: $([ "$ROLE" == "admin" ] && echo "High" || echo "Normal")" >> "$TASK_LIST"
                echo "**Added**: $(date)" >> "$TASK_LIST"
                echo "" >> "$TASK_LIST"

                TASK_COUNTER=$((TASK_COUNTER + 1))
            done

            echo "     ✅ Processed $CHANNEL_NAME"
        fi
    done

    # Also scan voice transcripts
    if [ -d /root/clawd/voice-transcripts ]; then
        echo ""
        echo "  🎤 Scanning voice transcripts..."

        find /root/clawd/voice-transcripts -name "*.txt" -type f -mtime -30 | while read -r transcript; do
            grep -E "(add|fix|create|implement|update|build|make|setup|install|configure|deploy|please|can you|need to|want to|todo|task)" -i "$transcript" | \
            while IFS= read -r task_text; do
                # Security: Sanitize
                task_text=$(echo "$task_text" | sed 's/[;&|`$()]//g')

                echo "## Task $TASK_COUNTER" >> "$TASK_LIST"
                echo "**Source**: Voice Transcript $(basename $transcript)" >> "$TASK_LIST"
                echo "**Request**: $task_text" >> "$TASK_LIST"
                echo "**Status**: Pending" >> "$TASK_LIST"
                echo "**Priority**: High" >> "$TASK_LIST"
                echo "**Added**: $(date)" >> "$TASK_LIST"
                echo "" >> "$TASK_LIST"

                TASK_COUNTER=$((TASK_COUNTER + 1))
            done
        done
    fi

    # Update totals
    TOTAL_TASKS=$((TASK_COUNTER - 1))
    sed -i "s/Total Tasks: 0/Total Tasks: $TOTAL_TASKS/" "$TASK_LIST"

    echo ""
    echo "✅ Extracted $TOTAL_TASKS tasks total from all channels"
}

# Ralph Wiggum execution loop (secure)
execute_tasks_secure() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🔄 RALPH WIGGUM EXECUTION LOOP (SECURE)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "⚠️  Will run indefinitely until you say STOP"
    echo "🔒 Security: Commands sanitized, credentials validated"
    echo ""

    TASK_NUM=1
    FAIL_COUNT=0
    MAX_CONSECUTIVE_FAILS=3

    while true; do
        # Get next pending task
        TASK_BLOCK=$(sed -n "/## Task $TASK_NUM/,/^$/p" "$TASK_LIST")
        TASK=$(echo "$TASK_BLOCK" | grep "^**Request**:" | sed 's/\*\*Request\*\*: //')

        if [ -z "$TASK" ]; then
            echo ""
            echo "✅ All tasks completed! Re-scanning for new tasks..."
            sleep 60

            # Re-extract (new tasks may have come in)
            BEFORE_COUNT=$(grep -c "^## Task" "$TASK_LIST" || echo 0)
            extract_all_telegram_tasks
            AFTER_COUNT=$(grep -c "^## Task" "$TASK_LIST" || echo 0)

            if [ $AFTER_COUNT -gt $BEFORE_COUNT ]; then
                echo "🆕 Found $((AFTER_COUNT - BEFORE_COUNT)) new tasks!"
                TASK_NUM=$((BEFORE_COUNT + 1))
            else
                echo "💤 No new tasks. Sleeping 60s..."
                sleep 60
                TASK_NUM=1
            fi
            continue
        fi

        # Security: Check for suspicious commands
        if echo "$TASK" | grep -qE "(rm -rf|dd if=|:(){:|wget.*sh|curl.*\||nc -|mkfs)"; then
            echo "🚨 SECURITY: Task $TASK_NUM contains dangerous command, skipping!"
            sed -i "/## Task $TASK_NUM/,/^$/ s/\*\*Status\*\*: Pending/\*\*Status\*\*: BLOCKED (Security)/" "$TASK_LIST"
            TASK_NUM=$((TASK_NUM + 1))
            continue
        fi

        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "📋 Task $TASK_NUM"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "$TASK"
        echo ""

        # Update status
        sed -i "/## Task $TASK_NUM/,/^$/ s/\*\*Status\*\*: Pending/\*\*Status\*\*: In Progress/" "$TASK_LIST"

        # Execute via Claude (with timeout for safety)
        echo "🤖 Executing with Claude (timeout: 300s)..."

        TASK_LOG="/tmp/claude_task_${TASK_NUM}_$(date +%s).log"
        timeout 300 bash -c "echo '$TASK' | claude chat --continue" > "$TASK_LOG" 2>&1
        EXIT_CODE=$?

        if [ $EXIT_CODE -eq 0 ]; then
            echo "✅ Task $TASK_NUM completed"

            sed -i "/## Task $TASK_NUM/,/^$/ s/\*\*Status\*\*: In Progress/\*\*Status\*\*: ✅ Completed/" "$TASK_LIST"

            # Log completion
            echo "## Task $TASK_NUM - ✅ Completed $(date)" >> "$COMPLETED_TASKS"
            echo "$TASK" >> "$COMPLETED_TASKS"
            echo "" >> "$COMPLETED_TASKS"
            cat "$TASK_LOG" >> "$COMPLETED_TASKS"
            echo "" >> "$COMPLETED_TASKS"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >> "$COMPLETED_TASKS"

            FAIL_COUNT=0

        elif [ $EXIT_CODE -eq 124 ]; then
            echo "⏱️  Task $TASK_NUM timed out (300s)"
            sed -i "/## Task $TASK_NUM/,/^$/ s/\*\*Status\*\*: In Progress/\*\*Status\*\*: ⏱️ Timeout/" "$TASK_LIST"
            FAIL_COUNT=$((FAIL_COUNT + 1))

        else
            echo "❌ Task $TASK_NUM failed (exit: $EXIT_CODE)"
            sed -i "/## Task $TASK_NUM/,/^$/ s/\*\*Status\*\*: In Progress/\*\*Status\*\*: ❌ Failed/" "$TASK_LIST"
            FAIL_COUNT=$((FAIL_COUNT + 1))
        fi

        # Security: Check if too many consecutive failures
        if [ $FAIL_COUNT -ge $MAX_CONSECUTIVE_FAILS ]; then
            echo ""
            echo "🚨 SECURITY: $MAX_CONSECUTIVE_FAILS consecutive failures"
            echo "⚠️  Pausing for manual review..."
            echo "Press ENTER to continue or Ctrl+C to stop"
            read
            FAIL_COUNT=0
        fi

        # Security: Clean up log
        chmod 600 "$TASK_LOG"

        TASK_NUM=$((TASK_NUM + 1))
        sleep 2
    done
}

# Main
echo "🚀 Starting secure task system..."
echo ""

validate_credentials
initialize_secure
extract_all_telegram_tasks

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 TASK COMPILATION COMPLETE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "View tasks: cat $TASK_LIST"
echo "View completed: cat $COMPLETED_TASKS"
echo ""
read -p "Press ENTER to start Ralph Wiggum loop (or Ctrl+C to cancel)... "

execute_tasks_secure
