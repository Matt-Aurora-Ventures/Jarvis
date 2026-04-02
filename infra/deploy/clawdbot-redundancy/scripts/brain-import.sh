#!/bin/bash
# Brain Import Script - Restores brain from portable archive
# Usage: ./brain-import.sh friday /path/to/brain.tar.gz

set -e

BOT_NAME="${1:-friday}"
INPUT_FILE="${2}"

if [ -z "$INPUT_FILE" ] || [ ! -f "$INPUT_FILE" ]; then
    echo "Usage: $0 <bot_name> <brain_archive.tar.gz>"
    echo "Example: $0 friday /tmp/friday-brain-20260203.tar.gz"
    exit 1
fi

DATA_ROOT="/root/clawd/data"

echo "=========================================="
echo "ClawdBot Brain Import"
echo "=========================================="
echo "Bot: $BOT_NAME"
echo "Archive: $INPUT_FILE"
echo ""

# Create temp directory for import
IMPORT_DIR=$(mktemp -d)
trap "rm -rf $IMPORT_DIR" EXIT

# Extract archive
tar -xzf "$INPUT_FILE" -C "$IMPORT_DIR"

# Verify manifest
if [ -f "$IMPORT_DIR/MANIFEST.json" ]; then
    echo "Archive manifest:"
    cat "$IMPORT_DIR/MANIFEST.json" | jq '.'
    echo ""
else
    echo "[WARNING] No manifest found, proceeding anyway..."
fi

# Confirm before overwriting
read -p "This will overwrite existing data for $BOT_NAME. Continue? [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
fi

# Stop container if running
echo "Stopping $BOT_NAME container..."
docker stop "clawdbot-$BOT_NAME" 2>/dev/null || true

# Create target directories
mkdir -p "$DATA_ROOT/$BOT_NAME/memory" "$DATA_ROOT/$BOT_NAME/skills"

# Import soul documents
if [ -d "$IMPORT_DIR/soul" ] && [ "$(ls -A $IMPORT_DIR/soul 2>/dev/null)" ]; then
    cp -r "$IMPORT_DIR/soul"/* "$DATA_ROOT/$BOT_NAME/"
    echo "[OK] Soul documents imported"
fi

# Import memory
if [ -d "$IMPORT_DIR/memory" ] && [ "$(ls -A $IMPORT_DIR/memory 2>/dev/null)" ]; then
    cp -r "$IMPORT_DIR/memory"/* "$DATA_ROOT/$BOT_NAME/memory/"
    echo "[OK] Memory imported"
fi

# Import skills
if [ -d "$IMPORT_DIR/skills" ] && [ "$(ls -A $IMPORT_DIR/skills 2>/dev/null)" ]; then
    cp -r "$IMPORT_DIR/skills"/* "$DATA_ROOT/$BOT_NAME/skills/"
    echo "[OK] Skills imported"
fi

# Import databases
for db in "$IMPORT_DIR"/*.sqlite "$IMPORT_DIR"/*.db; do
    if [ -f "$db" ]; then
        cp "$db" "$DATA_ROOT/$BOT_NAME/"
        echo "[OK] Database: $(basename $db)"
    fi
done

# Restart container
echo "Starting $BOT_NAME container..."
docker start "clawdbot-$BOT_NAME" 2>/dev/null || echo "[INFO] Container not found, start manually"

echo ""
echo "=========================================="
echo "Import Complete"
echo "=========================================="
echo "Data restored to: $DATA_ROOT/$BOT_NAME"
echo ""
echo "Verify with: docker logs clawdbot-$BOT_NAME --tail 20"
