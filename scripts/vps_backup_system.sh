#!/bin/bash
# VPS Backup System
# Coordinates with local Windows backups

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "☁️  VPS BACKUP SYSTEM"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

BACKUP_ROOT="/root/clawd/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$BACKUP_ROOT/vps_$TIMESTAMP"

# Critical paths on VPS
CRITICAL_PATHS=(
    "/root/clawd/MEMORY.md"
    "/root/clawd/TODO.md"
    "/root/clawd/daily-notes"
    "/root/clawd/voice-transcripts"
    "/root/clawd/scripts"
    "$HOME/.claude/config.json"
    "$HOME/.claude/hooks"
    "$HOME/.claude/commands"
)

# Create backup directory
echo "📦 Creating backup: $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"

# Backup function with error handling
backup_path() {
    local src="$1"
    local dest="$2"

    if [ -e "$src" ]; then
        echo "  📁 Backing up: $(basename $src)"

        if cp -r "$src" "$dest/" 2>/dev/null; then
            echo "    ✅ Success"
            return 0
        else
            echo "    ❌ Failed: $?"
            return 1
        fi
    else
        echo "  ⚠️  Not found: $src"
        return 1
    fi
}

# Perform backups
echo ""
echo "🔄 Starting backup process..."
SUCCESS=0
FAILED=0

for path in "${CRITICAL_PATHS[@]}"; do
    if backup_path "$path" "$BACKUP_DIR"; then
        SUCCESS=$((SUCCESS + 1))
    else
        FAILED=$((FAILED + 1))
    fi
done

# Generate checksums (security)
echo ""
echo "🔒 Generating checksums..."
find "$BACKUP_DIR" -type f -exec sha256sum {} \; > "$BACKUP_DIR/checksums.txt"
echo "✅ Checksums: $BACKUP_DIR/checksums.txt"

# Sync to Windows (if accessible)
echo ""
echo "💻 Attempting Windows sync..."

if [ -n "$WINDOWS_HOST" ] && [ -n "$WINDOWS_USER" ]; then
    WINDOWS_BACKUP="/cygdrive/c/Users/lucid/Backups/from_vps"

    echo "  📡 Syncing to: $WINDOWS_USER@$WINDOWS_HOST"

    if scp -r -o ConnectTimeout=10 "$BACKUP_DIR" "${WINDOWS_USER}@${WINDOWS_HOST}:${WINDOWS_BACKUP}/" 2>/dev/null; then
        echo "  ✅ Windows sync successful"
    else
        echo "  ⚠️  Windows sync failed (may not be accessible)"
    fi
else
    echo "  ⚠️  Windows credentials not set (export WINDOWS_HOST and WINDOWS_USER)"
fi

# Cleanup old backups (keep last 10)
echo ""
echo "🧹 Cleaning old backups..."

ls -dt $BACKUP_ROOT/vps_* 2>/dev/null | tail -n +11 | while read -r old_backup; do
    echo "  🗑️  Deleting: $(basename $old_backup)"
    rm -rf "$old_backup"
done

# Summary
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ BACKUP COMPLETE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📊 Summary:"
echo "  Success: $SUCCESS paths"
echo "  Failed: $FAILED paths"
echo "  Location: $BACKUP_DIR"
echo "  Checksums: $BACKUP_DIR/checksums.txt"
echo ""
echo "⏰ Next backup: Run this script again (or schedule with cron)"
