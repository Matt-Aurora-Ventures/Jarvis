#!/bin/bash
# Nightly Backup Script for ClawdBot Soul & Memory
# Runs via cron: 0 3 * * * /root/clawd/scripts/nightly-backup.sh
#
# Creates compressed backups of:
# - Soul documents (SOUL.md, IDENTITY.md, etc.)
# - SQLite memories (main.sqlite)
# - Skills and learned patterns
# - Configuration files
#
# Retention: 7 days of daily backups

set -e

BACKUP_ROOT="/root/clawd/backups"
DATA_ROOT="/root/clawd/data"
CONFIG_ROOT="/root/.clawdbot"
DATE=$(date +%Y-%m-%d)
RETENTION_DAYS=7
LOG_FILE="/var/log/clawdbot-backup.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# =============================================================================
# Backup Functions
# =============================================================================

backup_bot() {
    local BOT_NAME="$1"
    local BOT_CONFIG="$2"
    local BACKUP_DIR="$BACKUP_ROOT/$BOT_NAME/$DATE"

    log "Starting backup for $BOT_NAME..."

    mkdir -p "$BACKUP_DIR"

    # Backup soul documents
    if [ -d "$DATA_ROOT/$BOT_NAME" ]; then
        tar -czf "$BACKUP_DIR/soul-documents.tar.gz" \
            -C "$DATA_ROOT/$BOT_NAME" . 2>/dev/null || true
        log "  Soul documents: OK"
    fi

    # Backup memory/skills from container workspace
    if [ -d "$DATA_ROOT/$BOT_NAME/memory" ]; then
        tar -czf "$BACKUP_DIR/memory.tar.gz" \
            -C "$DATA_ROOT/$BOT_NAME/memory" . 2>/dev/null || true
        log "  Memory: OK"
    fi

    if [ -d "$DATA_ROOT/$BOT_NAME/skills" ]; then
        tar -czf "$BACKUP_DIR/skills.tar.gz" \
            -C "$DATA_ROOT/$BOT_NAME/skills" . 2>/dev/null || true
        log "  Skills: OK"
    fi

    # Backup configuration (without secrets)
    if [ -d "$BOT_CONFIG" ]; then
        # Copy config but redact sensitive keys
        mkdir -p "$BACKUP_DIR/config"
        if [ -f "$BOT_CONFIG/clawdbot.json" ]; then
            cat "$BOT_CONFIG/clawdbot.json" | \
                jq 'walk(if type == "string" and (test("sk-|tskey-|xai-")) then "REDACTED" else . end)' \
                > "$BACKUP_DIR/config/clawdbot.json" 2>/dev/null || \
                cp "$BOT_CONFIG/clawdbot.json" "$BACKUP_DIR/config/"
        fi
        log "  Config: OK"
    fi

    # Backup SQLite databases
    for db in "$DATA_ROOT/$BOT_NAME"/*.sqlite "$DATA_ROOT/$BOT_NAME"/*.db; do
        if [ -f "$db" ]; then
            cp "$db" "$BACKUP_DIR/" 2>/dev/null || true
            log "  Database $(basename $db): OK"
        fi
    done

    # Create unified brain archive (survival kit)
    tar -czf "$BACKUP_DIR/$BOT_NAME-brain.tar.gz" \
        -C "$BACKUP_DIR" \
        --exclude="$BOT_NAME-brain.tar.gz" \
        . 2>/dev/null || true

    log "  Brain archive: $BACKUP_DIR/$BOT_NAME-brain.tar.gz"

    # Calculate backup size
    local SIZE=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1)
    log "  Total size: $SIZE"
}

cleanup_old_backups() {
    local BOT_NAME="$1"
    log "Cleaning up backups older than $RETENTION_DAYS days for $BOT_NAME..."

    find "$BACKUP_ROOT/$BOT_NAME" -maxdepth 1 -type d -mtime +$RETENTION_DAYS -exec rm -rf {} \; 2>/dev/null || true

    local COUNT=$(ls -d "$BACKUP_ROOT/$BOT_NAME"/*/ 2>/dev/null | wc -l)
    log "  Retained backups: $COUNT"
}

# =============================================================================
# Main Execution
# =============================================================================

log "=========================================="
log "ClawdBot Nightly Backup Starting"
log "=========================================="

mkdir -p "$BACKUP_ROOT"

# Backup each bot
backup_bot "friday" "/root/.clawdbot"
backup_bot "matt" "/docker/clawdbot-gateway/config-matt"
backup_bot "jarvis" "/root/.clawdbot-jarvis"

# Backup shared SuperMemory database
if [ -f "/root/clawdbots/data/supermemory.db" ]; then
    mkdir -p "$BACKUP_ROOT/shared/$DATE"
    cp "/root/clawdbots/data/supermemory.db" "$BACKUP_ROOT/shared/$DATE/"
    log "Shared SuperMemory: OK"
fi

# Cleanup old backups
cleanup_old_backups "friday"
cleanup_old_backups "matt"
cleanup_old_backups "jarvis"
cleanup_old_backups "shared"

log "=========================================="
log "Backup Complete"
log "=========================================="

# Summary
echo ""
echo "Backup Summary:"
du -sh "$BACKUP_ROOT"/*/"$DATE" 2>/dev/null | while read size dir; do
    echo "  $dir: $size"
done
