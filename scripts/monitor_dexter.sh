#!/bin/bash
# Monitor Dexter finance integration on VPS
# Usage: bash scripts/monitor_dexter.sh
# or: bash scripts/monitor_dexter.sh follow (for real-time tail)

set -e

MODE=${1:-check}
VPS="root@72.61.7.126"
LOG_FILE="/home/jarvis/Jarvis/logs/tg_bot.log"

if [ "$MODE" = "follow" ]; then
    echo "═══════════════════════════════════════════════════════════"
    echo "  DEXTER MONITORING - REAL-TIME (Ctrl+C to stop)"
    echo "═══════════════════════════════════════════════════════════"
    echo ""
    echo "Filtering for: DEXTER | FINANCE | GROK | ERROR | WARNING"
    echo ""
    ssh -i ~/.ssh/id_ed25519 "$VPS" "tail -f $LOG_FILE" | grep -iE "dexter|finance|grok|error|warning" || true

elif [ "$MODE" = "recent" ]; then
    echo "═══════════════════════════════════════════════════════════"
    echo "  DEXTER MONITORING - RECENT ACTIVITY (Last 100 lines)"
    echo "═══════════════════════════════════════════════════════════"
    echo ""

    echo "=== Recent Dexter/Finance Activity ==="
    ssh -i ~/.ssh/id_ed25519 "$VPS" "tail -100 $LOG_FILE | grep -iE 'dexter|finance|grok'" || echo "(no activity found)"

    echo ""
    echo "=== Recent Errors ==="
    ssh -i ~/.ssh/id_ed25519 "$VPS" "tail -100 $LOG_FILE | grep -iE 'ERROR|EXCEPTION'" || echo "(no errors found)"

    echo ""
    echo "=== Last 20 Log Lines ==="
    ssh -i ~/.ssh/id_ed25519 "$VPS" "tail -20 $LOG_FILE"

else
    # Default: status check
    echo "═══════════════════════════════════════════════════════════"
    echo "  DEXTER FINANCE INTEGRATION - STATUS CHECK"
    echo "═══════════════════════════════════════════════════════════"
    echo ""

    echo "=== Bot Status ==="
    ssh -i ~/.ssh/id_ed25519 "$VPS" "ps aux | grep 'tg_bot.bot' | grep -v grep" || echo "Bot not running!"

    echo ""
    echo "=== Lock File Status ==="
    ssh -i ~/.ssh/id_ed25519 "$VPS" "ls -lh /home/jarvis/Jarvis/data/locks/telegram_polling_*.lock 2>/dev/null && \
    echo 'PID:' && cat /home/jarvis/Jarvis/data/locks/telegram_polling_*.lock" || echo "Lock file not found!"

    echo ""
    echo "=== Supervisor Status ==="
    ssh -i ~/.ssh/id_ed25519 "$VPS" "ps aux | grep supervisor | grep -v grep | head -1" || echo "Supervisor not running"

    echo ""
    echo "=== Log File Size ==="
    ssh -i ~/.ssh/id_ed25519 "$VPS" "wc -l $LOG_FILE && du -sh $LOG_FILE"

    echo ""
    echo "=== Total Dexter Invocations ==="
    ssh -i ~/.ssh/id_ed25519 "$VPS" "grep -ic 'dexter' $LOG_FILE || echo '0'"

    echo ""
    echo "=== Total Finance Questions ==="
    ssh -i ~/.ssh/id_ed25519 "$VPS" "grep -ic 'finance' $LOG_FILE || echo '0'"

    echo ""
    echo "=== Total Errors ==="
    ssh -i ~/.ssh/id_ed25519 "$VPS" "grep -ic 'ERROR' $LOG_FILE || echo '0'"

    echo ""
    echo "=== Latest Activity (Last 30 seconds) ==="
    ssh -i ~/.ssh/id_ed25519 "$VPS" "tail -50 $LOG_FILE"

    echo ""
    echo "═══════════════════════════════════════════════════════════"
    echo "Usage:"
    echo "  bash scripts/monitor_dexter.sh       - Status check (this)"
    echo "  bash scripts/monitor_dexter.sh recent - Recent activity"
    echo "  bash scripts/monitor_dexter.sh follow - Real-time monitoring"
    echo "═══════════════════════════════════════════════════════════"
fi
