#!/bin/bash
# Ralph Wiggum Telegram Task Compiler & Executor
# Phase 2: Extract all user requests and execute in continuous loop

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 RALPH WIGGUM TASK COMPILER"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

TASK_LIST="/root/clawd/MASTER_TASK_LIST.md"
COMPLETED_TASKS="/root/clawd/COMPLETED_TASKS.md"
CHAT_ARCHIVE="/root/clawd/telegram-chat-archive"

# Initialize task files
initialize_files() {
    echo "📝 Initializing task tracking files..."

    cat > "$TASK_LIST" <<EOF
# MASTER TASK LIST
Generated: $(date)
Source: All Telegram chats with Matt

## Status
- Total Tasks: 0
- Completed: 0
- In Progress: 0
- Pending: 0

## Tasks

EOF

    cat > "$COMPLETED_TASKS" <<EOF
# COMPLETED TASKS
Tracking all completed work

EOF

    mkdir -p "$CHAT_ARCHIVE"
    echo "✅ Task files initialized"
}

# Extract tasks from Telegram chats
extract_telegram_tasks() {
    echo "📥 Extracting tasks from Telegram chats..."

    # Get all chat IDs (Matt, Friday, Jarvis)
    CHAT_IDS=(
        "${MAIN_CHAT_ID:-}"
        "${FRIDAY_CHAT_ID:-}"
        "${JARVIS_CHAT_ID:-}"
    )

    TASK_COUNTER=1

    for CHAT_ID in "${CHAT_IDS[@]}"; do
        if [ -z "$CHAT_ID" ]; then continue; fi

        echo "  📱 Processing chat: $CHAT_ID"

        # Export chat history using Telegram Bot API
        # This assumes you have telegram-cli or similar tool
        CHAT_FILE="$CHAT_ARCHIVE/chat_${CHAT_ID}_$(date +%Y%m%d).json"

        # Use Python script to extract via Telegram Bot API
        python3 - <<PYTHON_SCRIPT
import os
import json
import requests
from datetime import datetime, timedelta

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
CHAT_ID = '$CHAT_ID'

if not TOKEN:
    print("⚠️  No TELEGRAM_BOT_TOKEN - skipping API extraction")
    exit(0)

# Get messages from last 30 days
url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
response = requests.get(url)
messages = response.json().get('result', [])

# Save to file
with open('$CHAT_FILE', 'w') as f:
    json.dump(messages, f, indent=2)

print(f"✅ Exported {len(messages)} messages")
PYTHON_SCRIPT

        # Parse tasks from chat
        if [ -f "$CHAT_FILE" ]; then
            # Extract user messages that look like tasks
            jq -r '.[] | select(.message.from.is_bot == false) | .message.text' "$CHAT_FILE" 2>/dev/null | \
            grep -E "(^(add|fix|create|implement|update|build|make|setup|install|configure|deploy)|please|can you|need to|want to|todo|task)" -i | \
            while IFS= read -r line; do
                echo "## Task $TASK_COUNTER" >> "$TASK_LIST"
                echo "**Source**: Chat $CHAT_ID" >> "$TASK_LIST"
                echo "**Request**: $line" >> "$TASK_LIST"
                echo "**Status**: Pending" >> "$TASK_LIST"
                echo "**Added**: $(date)" >> "$TASK_LIST"
                echo "" >> "$TASK_LIST"
                TASK_COUNTER=$((TASK_COUNTER + 1))
            done
        fi
    done

    # Also check voice transcripts
    if [ -d /root/clawd/voice-transcripts ]; then
        echo "  🎤 Processing voice transcripts..."
        find /root/clawd/voice-transcripts -name "*.txt" -type f | while read -r transcript; do
            grep -E "(add|fix|create|implement|update|build|make|setup|install|configure|deploy|please|can you|need to|want to|todo|task)" -i "$transcript" | \
            while IFS= read -r line; do
                echo "## Task $TASK_COUNTER" >> "$TASK_LIST"
                echo "**Source**: Voice transcript $(basename $transcript)" >> "$TASK_LIST"
                echo "**Request**: $line" >> "$TASK_LIST"
                echo "**Status**: Pending" >> "$TASK_LIST"
                echo "**Added**: $(date)" >> "$TASK_LIST"
                echo "" >> "$TASK_LIST"
                TASK_COUNTER=$((TASK_COUNTER + 1))
            done
        done
    fi

    # Update task count
    TOTAL_TASKS=$((TASK_COUNTER - 1))
    sed -i "s/Total Tasks: 0/Total Tasks: $TOTAL_TASKS/" "$TASK_LIST"

    echo "✅ Extracted $TOTAL_TASKS tasks"
}

# Execute tasks in Ralph Wiggum loop
execute_tasks() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🔄 ENTERING RALPH WIGGUM EXECUTION LOOP"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "⚠️  Will continue until user says STOP"
    echo ""

    TASK_NUM=1

    while true; do
        # Get next pending task
        TASK=$(sed -n "/## Task $TASK_NUM/,/## Task $((TASK_NUM + 1))/p" "$TASK_LIST" | grep "^**Request**:" | sed 's/\*\*Request\*\*: //')

        if [ -z "$TASK" ]; then
            echo "✅ All tasks completed! Checking for new tasks..."
            sleep 60
            extract_telegram_tasks  # Re-scan for new tasks
            TASK_NUM=1
            continue
        fi

        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "📋 Task $TASK_NUM"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "$TASK"
        echo ""

        # Update status to In Progress
        sed -i "s/\*\*Status\*\*: Pending/\*\*Status\*\*: In Progress/" "$TASK_LIST"

        # Execute task using Claude
        echo "🤖 Executing with Claude..."

        # Call Claude CLI with the task
        echo "$TASK" | claude chat --continue 2>&1 | tee /tmp/claude_output_task_${TASK_NUM}.log

        EXIT_CODE=${PIPESTATUS[0]}

        if [ $EXIT_CODE -eq 0 ]; then
            echo "✅ Task $TASK_NUM completed"

            # Mark as completed
            sed -i "/## Task $TASK_NUM/,/## Task $((TASK_NUM + 1))/ s/\*\*Status\*\*: In Progress/\*\*Status\*\*: Completed/" "$TASK_LIST"

            # Add to completed log
            echo "## Task $TASK_NUM - Completed $(date)" >> "$COMPLETED_TASKS"
            echo "$TASK" >> "$COMPLETED_TASKS"
            echo "" >> "$COMPLETED_TASKS"
            cat /tmp/claude_output_task_${TASK_NUM}.log >> "$COMPLETED_TASKS"
            echo "" >> "$COMPLETED_TASKS"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >> "$COMPLETED_TASKS"
            echo "" >> "$COMPLETED_TASKS"

        else
            echo "⚠️  Task $TASK_NUM failed or needs attention"
            sed -i "/## Task $TASK_NUM/,/## Task $((TASK_NUM + 1))/ s/\*\*Status\*\*: In Progress/\*\*Status\*\*: Needs Attention/" "$TASK_LIST"
        fi

        TASK_NUM=$((TASK_NUM + 1))

        # Update task counts
        COMPLETED=$(grep -c "\*\*Status\*\*: Completed" "$TASK_LIST" || echo 0)
        IN_PROGRESS=$(grep -c "\*\*Status\*\*: In Progress" "$TASK_LIST" || echo 0)
        PENDING=$(grep -c "\*\*Status\*\*: Pending" "$TASK_LIST" || echo 0)

        echo ""
        echo "📊 Progress: $COMPLETED completed, $IN_PROGRESS in progress, $PENDING pending"
        echo ""

        sleep 2
    done
}

# Main execution
echo "🚀 Starting Ralph Wiggum Task System..."
echo ""

initialize_files
extract_telegram_tasks

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 TASK LIST COMPILED"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "View tasks: cat $TASK_LIST"
echo "View completed: cat $COMPLETED_TASKS"
echo ""
read -p "Press ENTER to start Ralph Wiggum execution loop (will run until stopped)... "

execute_tasks
