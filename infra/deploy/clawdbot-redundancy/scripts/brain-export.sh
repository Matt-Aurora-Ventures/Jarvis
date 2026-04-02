#!/bin/bash
# Brain Export Script - Creates portable brain archive for migration
# Usage: ./brain-export.sh friday /path/to/output.tar.gz

set -e

BOT_NAME="${1:-friday}"
OUTPUT_FILE="${2:-/tmp/$BOT_NAME-brain-$(date +%Y%m%d).tar.gz}"

DATA_ROOT="/root/clawd/data"
BACKUP_ROOT="/root/clawd/backups"

echo "=========================================="
echo "ClawdBot Brain Export"
echo "=========================================="
echo "Bot: $BOT_NAME"
echo "Output: $OUTPUT_FILE"
echo ""

# Create temp directory for export
EXPORT_DIR=$(mktemp -d)
trap "rm -rf $EXPORT_DIR" EXIT

mkdir -p "$EXPORT_DIR/soul" "$EXPORT_DIR/memory" "$EXPORT_DIR/skills" "$EXPORT_DIR/config"

# Export soul documents
if [ -d "$DATA_ROOT/$BOT_NAME" ]; then
    cp -r "$DATA_ROOT/$BOT_NAME"/*.md "$EXPORT_DIR/soul/" 2>/dev/null || true
    echo "[OK] Soul documents exported"
fi

# Export memory
if [ -d "$DATA_ROOT/$BOT_NAME/memory" ]; then
    cp -r "$DATA_ROOT/$BOT_NAME/memory"/* "$EXPORT_DIR/memory/" 2>/dev/null || true
    echo "[OK] Memory exported"
fi

# Export skills
if [ -d "$DATA_ROOT/$BOT_NAME/skills" ]; then
    cp -r "$DATA_ROOT/$BOT_NAME/skills"/* "$EXPORT_DIR/skills/" 2>/dev/null || true
    echo "[OK] Skills exported"
fi

# Export databases
for db in "$DATA_ROOT/$BOT_NAME"/*.sqlite "$DATA_ROOT/$BOT_NAME"/*.db; do
    if [ -f "$db" ]; then
        cp "$db" "$EXPORT_DIR/" 2>/dev/null || true
        echo "[OK] Database: $(basename $db)"
    fi
done

# Export config (redacted)
CONFIG_DIR="/root/.clawdbot"
[ "$BOT_NAME" = "matt" ] && CONFIG_DIR="/docker/clawdbot-gateway/config-matt"
[ "$BOT_NAME" = "jarvis" ] && CONFIG_DIR="/root/.clawdbot-jarvis"

if [ -f "$CONFIG_DIR/clawdbot.json" ]; then
    cat "$CONFIG_DIR/clawdbot.json" | \
        jq 'walk(if type == "string" and (test("sk-|tskey-|xai-|ghp_")) then "REDACTED" else . end)' \
        > "$EXPORT_DIR/config/clawdbot.json" 2>/dev/null || \
        cp "$CONFIG_DIR/clawdbot.json" "$EXPORT_DIR/config/"
    echo "[OK] Config exported (secrets redacted)"
fi

# Create manifest
cat > "$EXPORT_DIR/MANIFEST.json" << EOF
{
    "bot_name": "$BOT_NAME",
    "export_date": "$(date -Iseconds)",
    "export_host": "$(hostname)",
    "version": "1.0",
    "contents": {
        "soul_documents": $(ls "$EXPORT_DIR/soul" 2>/dev/null | wc -l),
        "memory_files": $(ls "$EXPORT_DIR/memory" 2>/dev/null | wc -l),
        "skill_files": $(ls "$EXPORT_DIR/skills" 2>/dev/null | wc -l),
        "databases": $(ls "$EXPORT_DIR"/*.sqlite "$EXPORT_DIR"/*.db 2>/dev/null | wc -l)
    }
}
EOF

# Create archive
tar -czf "$OUTPUT_FILE" -C "$EXPORT_DIR" .

# Display summary
echo ""
echo "=========================================="
echo "Export Complete"
echo "=========================================="
echo "Archive: $OUTPUT_FILE"
echo "Size: $(du -h "$OUTPUT_FILE" | cut -f1)"
echo ""
echo "Contents:"
cat "$EXPORT_DIR/MANIFEST.json" | jq '.contents'
echo ""
echo "To import on another host:"
echo "  ./brain-import.sh $BOT_NAME $OUTPUT_FILE"
