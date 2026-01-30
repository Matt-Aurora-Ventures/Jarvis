#!/bin/bash
# TP/SL Monitor Status - Quick health check

echo "=== TP/SL MONITOR STATUS ==="
echo ""

# Check Redis
if redis-cli ping 2>/dev/null | grep -q PONG; then
    echo "✅ Redis: ONLINE"
else
    echo "❌ Redis: OFFLINE"
fi

# Check primary monitor heartbeat
PRIMARY=$(redis-cli GET jarvis:monitor_heartbeat:primary 2>/dev/null)
if [ -n "$PRIMARY" ]; then
    LAST_CHECK=$(echo "$PRIMARY" | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('last_check','N/A'))")
    echo "✅ Primary Monitor: ALIVE (last: $LAST_CHECK)"
else
    echo "⚠️  Primary Monitor: NO HEARTBEAT"
fi

# Check backup monitor heartbeat
BACKUP=$(redis-cli GET jarvis:monitor_heartbeat:backup 2>/dev/null)
if [ -n "$BACKUP" ]; then
    LAST_CHECK=$(echo "$BACKUP" | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('last_check','N/A'))")
    echo "✅ Backup Monitor: ACTIVE (last: $LAST_CHECK)"
else
    echo "⚠️  Backup Monitor: NO HEARTBEAT"
fi

# Count positions (only users with actual positions)
POS_KEYS=$(redis-cli KEYS "jarvis:positions:*" 2>/dev/null)
POS_COUNT=0
if [ -n "$POS_KEYS" ]; then
    for key in $POS_KEYS; do
        DATA=$(redis-cli GET "$key" 2>/dev/null)
        if [ "$DATA" != "[]" ] && [ -n "$DATA" ]; then
            POS_COUNT=$((POS_COUNT + 1))
        fi
    done
fi
echo ""
echo "📊 Active Users with Positions: $POS_COUNT"

# Show any active locks
LOCK_COUNT=$(redis-cli KEYS "jarvis:exec_lock:*" 2>/dev/null | wc -l)
if [ "$LOCK_COUNT" -gt 0 ]; then
    echo "🔒 Active Execution Locks: $LOCK_COUNT"
fi

echo ""
echo "=== END STATUS ==="
