#!/bin/bash
# Master Ralph Wiggum Script
# Orchestrates: Fix Gateway → Extract Tasks → Execute Forever

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔄 MASTER RALPH WIGGUM ORCHESTRATOR"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "This will:"
echo "  1. Fix gateway config persistence (loop until fixed)"
echo "  2. Extract all tasks from Telegram chats"
echo "  3. Execute all tasks in continuous loop"
echo ""
echo "⚠️  This will run indefinitely until you say STOP"
echo ""

read -p "Press ENTER to begin... "

# Phase 1: Fix Gateway
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "PHASE 1: FIX GATEWAY"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
bash "$SCRIPT_DIR/ralph_wiggum_gateway_fix.sh"

if [ $? -ne 0 ]; then
    echo "❌ Gateway fix failed. Cannot proceed."
    exit 1
fi

# Phase 2: Extract and Execute Tasks
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "PHASE 2: TASK EXTRACTION & EXECUTION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
bash "$SCRIPT_DIR/ralph_wiggum_telegram_tasks.sh"
