#!/bin/bash
# Redis Context Hydration Script
# Loads bot context into Redis for millisecond-fast recovery
#
# Benefits:
# - Instant context reload after restart (vs reading files)
# - Shared context across multiple bot instances
# - Real-time context updates without file I/O
#
# Usage:
#   ./redis-hydration.sh hydrate friday    - Load context to Redis
#   ./redis-hydration.sh dehydrate friday  - Save Redis to disk
#   ./redis-hydration.sh status            - Show Redis status

set -e

REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"
REDIS_PREFIX="clawdbot"
DATA_ROOT="/root/clawd/data"

# Check Redis availability
check_redis() {
    if ! redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping > /dev/null 2>&1; then
        echo "ERROR: Redis not available at $REDIS_HOST:$REDIS_PORT"
        exit 1
    fi
}

# =============================================================================
# Hydration Functions
# =============================================================================

hydrate_bot() {
    local BOT_NAME="$1"
    echo "=========================================="
    echo "Hydrating $BOT_NAME context to Redis"
    echo "=========================================="

    local BOT_DIR="$DATA_ROOT/$BOT_NAME"
    local KEY_PREFIX="$REDIS_PREFIX:$BOT_NAME"

    # Hydrate soul documents
    for doc in "$BOT_DIR"/*.md; do
        if [ -f "$doc" ]; then
            local DOC_NAME=$(basename "$doc" .md)
            local CONTENT=$(cat "$doc" | base64 -w 0)
            redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" SET "$KEY_PREFIX:soul:$DOC_NAME" "$CONTENT" > /dev/null
            echo "  [OK] Soul: $DOC_NAME"
        fi
    done

    # Hydrate memory files
    if [ -d "$BOT_DIR/memory" ]; then
        for mem in "$BOT_DIR/memory"/*; do
            if [ -f "$mem" ]; then
                local MEM_NAME=$(basename "$mem")
                local CONTENT=$(cat "$mem" | base64 -w 0)
                redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" SET "$KEY_PREFIX:memory:$MEM_NAME" "$CONTENT" > /dev/null
                echo "  [OK] Memory: $MEM_NAME"
            fi
        done
    fi

    # Hydrate recent conversation context (if exists)
    local CONTEXT_FILE="$BOT_DIR/context.json"
    if [ -f "$CONTEXT_FILE" ]; then
        local CONTEXT=$(cat "$CONTEXT_FILE")
        redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" SET "$KEY_PREFIX:context" "$CONTEXT" > /dev/null
        echo "  [OK] Conversation context"
    fi

    # Set metadata
    redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" HSET "$KEY_PREFIX:meta" \
        "hydrated_at" "$(date -Iseconds)" \
        "source_host" "$(hostname)" \
        "bot_name" "$BOT_NAME" > /dev/null

    # Set TTL (24 hours) to force periodic refresh
    redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" EXPIRE "$KEY_PREFIX:meta" 86400 > /dev/null

    echo ""
    echo "Hydration complete for $BOT_NAME"
    echo "Keys created: $(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" KEYS "$KEY_PREFIX:*" | wc -l)"
}

dehydrate_bot() {
    local BOT_NAME="$1"
    echo "=========================================="
    echo "Dehydrating $BOT_NAME context from Redis"
    echo "=========================================="

    local BOT_DIR="$DATA_ROOT/$BOT_NAME"
    local KEY_PREFIX="$REDIS_PREFIX:$BOT_NAME"

    mkdir -p "$BOT_DIR/memory"

    # Dehydrate soul documents
    for key in $(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" KEYS "$KEY_PREFIX:soul:*"); do
        local DOC_NAME=$(echo "$key" | sed "s|$KEY_PREFIX:soul:||")
        local CONTENT=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" GET "$key" | base64 -d)
        echo "$CONTENT" > "$BOT_DIR/$DOC_NAME.md"
        echo "  [OK] Soul: $DOC_NAME"
    done

    # Dehydrate memory files
    for key in $(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" KEYS "$KEY_PREFIX:memory:*"); do
        local MEM_NAME=$(echo "$key" | sed "s|$KEY_PREFIX:memory:||")
        local CONTENT=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" GET "$key" | base64 -d)
        echo "$CONTENT" > "$BOT_DIR/memory/$MEM_NAME"
        echo "  [OK] Memory: $MEM_NAME"
    done

    # Dehydrate conversation context
    local CONTEXT=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" GET "$KEY_PREFIX:context")
    if [ -n "$CONTEXT" ] && [ "$CONTEXT" != "(nil)" ]; then
        echo "$CONTEXT" > "$BOT_DIR/context.json"
        echo "  [OK] Conversation context"
    fi

    echo ""
    echo "Dehydration complete for $BOT_NAME"
}

show_status() {
    echo "=========================================="
    echo "Redis Hydration Status"
    echo "=========================================="
    echo ""
    echo "Redis: $REDIS_HOST:$REDIS_PORT"
    echo ""

    for bot in friday matt jarvis; do
        local KEY_PREFIX="$REDIS_PREFIX:$bot"
        local KEY_COUNT=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" KEYS "$KEY_PREFIX:*" 2>/dev/null | wc -l)

        if [ "$KEY_COUNT" -gt 0 ]; then
            local HYDRATED_AT=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" HGET "$KEY_PREFIX:meta" "hydrated_at" 2>/dev/null)
            echo "$bot:"
            echo "  Keys: $KEY_COUNT"
            echo "  Hydrated: ${HYDRATED_AT:-unknown}"
        else
            echo "$bot: NOT HYDRATED"
        fi
        echo ""
    done

    # Memory usage
    local MEMORY=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" INFO memory 2>/dev/null | grep "used_memory_human" | cut -d: -f2 | tr -d '\r')
    echo "Redis memory: $MEMORY"
}

hydrate_all() {
    for bot in friday matt jarvis; do
        hydrate_bot "$bot"
        echo ""
    done
}

# =============================================================================
# Startup Integration
# =============================================================================

startup_hydrate() {
    # Called from container entrypoint to load context quickly
    local BOT_NAME="$1"
    local KEY_PREFIX="$REDIS_PREFIX:$BOT_NAME"

    # Check if Redis is available
    if ! redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping > /dev/null 2>&1; then
        echo "[hydration] Redis not available, using disk"
        return 0
    fi

    # Check if context exists in Redis
    local KEY_COUNT=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" KEYS "$KEY_PREFIX:*" 2>/dev/null | wc -l)

    if [ "$KEY_COUNT" -gt 0 ]; then
        echo "[hydration] Loading context from Redis ($KEY_COUNT keys)"
        dehydrate_bot "$BOT_NAME" > /dev/null 2>&1
        echo "[hydration] Context loaded in $(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" DEBUG SLEEP 0 2>&1 | grep -oP '\d+' || echo '0')ms"
    else
        echo "[hydration] No Redis context, using disk"
    fi
}

# =============================================================================
# Main
# =============================================================================

case "${1:-status}" in
    hydrate)
        check_redis
        if [ -z "$2" ]; then
            hydrate_all
        else
            hydrate_bot "$2"
        fi
        ;;
    dehydrate)
        check_redis
        if [ -z "$2" ]; then
            echo "Usage: $0 dehydrate <bot_name>"
            exit 1
        fi
        dehydrate_bot "$2"
        ;;
    startup)
        startup_hydrate "${2:-friday}"
        ;;
    status)
        check_redis
        show_status
        ;;
    *)
        echo "Usage: $0 {hydrate|dehydrate|startup|status} [bot_name]"
        echo ""
        echo "Commands:"
        echo "  hydrate [bot]     Load bot context to Redis"
        echo "  dehydrate <bot>   Save Redis context to disk"
        echo "  startup <bot>     Quick hydration check for container start"
        echo "  status            Show hydration status"
        ;;
esac
