#!/bin/bash
# Deploy ClawdBot Shared Modules to VPS
# Syncs bots/shared/, bot directories, and SOUL files to VPS and restarts services
#
# Usage: ./scripts/deploy_shared_modules.sh [--dry-run]

set -euo pipefail

# Configuration
VPS_HOST="root@76.13.106.100"
VPS_DIR="/root/clawdbots"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse arguments
DRY_RUN=""
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN="--dry-run"
    echo -e "${YELLOW}DRY RUN MODE - No changes will be made${NC}"
    echo
fi

cd "$PROJECT_DIR"

echo "========================================="
echo "CLAWDBOT SHARED MODULES DEPLOYMENT"
echo "========================================="
echo "Source:      ${PROJECT_DIR}"
echo "Destination: ${VPS_HOST}:${VPS_DIR}"
echo "========================================="
echo

# Step 1: Verify local files exist
echo "Step 1: Verifying local shared modules..."
if [ ! -d "bots/shared" ]; then
    echo -e "${RED}ERROR: bots/shared/ directory not found!${NC}"
    exit 1
fi

LOCAL_COUNT=$(find "bots/shared" -name "*.py" -type f | wc -l)
echo -e "${GREEN}Found ${LOCAL_COUNT} Python files in bots/shared/${NC}"
echo

# Step 2: Test VPS connectivity
echo "Step 2: Testing VPS connectivity..."
if ! ssh -o ConnectTimeout=10 -o BatchMode=yes "${VPS_HOST}" "echo 'SSH OK'" 2>/dev/null; then
    echo -e "${RED}ERROR: Cannot connect to VPS${NC}"
    echo "  Verify SSH key: ssh-add -l"
    echo "  Test manually: ssh ${VPS_HOST}"
    exit 1
fi
echo -e "${GREEN}VPS connection successful${NC}"
echo

# Step 3: Backup existing files on VPS
echo "Step 3: Backing up existing shared modules on VPS..."
if [[ -z "$DRY_RUN" ]]; then
    ssh "${VPS_HOST}" "
        BACKUP_DIR='${VPS_DIR}/backups/shared-\$(date +%Y%m%d_%H%M%S)'
        if [ -d '${VPS_DIR}/bots/shared' ] && ls ${VPS_DIR}/bots/shared/*.py 1>/dev/null 2>&1; then
            mkdir -p \"\$BACKUP_DIR\"
            cp -r ${VPS_DIR}/bots/shared/ \"\$BACKUP_DIR/\"
            echo \"Backup created: \$BACKUP_DIR\"
        else
            echo 'No existing files to backup'
        fi
    "
else
    echo "  [DRY RUN] Would backup existing files"
fi
echo

# Step 4: Deploy shared modules
echo "Step 4: Syncing bots/shared/ ..."
rsync -avz $DRY_RUN \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    bots/shared/ "$VPS_HOST:$VPS_DIR/bots/shared/"
echo

# Step 5: Deploy bot directories
echo "Step 5: Syncing bot files ..."
for bot in clawdjarvis clawdfriday clawdmatt; do
    if [ -d "bots/$bot" ]; then
        echo -e "  ${GREEN}Syncing bots/$bot/${NC}"
        rsync -avz $DRY_RUN \
            --exclude='__pycache__' \
            --exclude='*.pyc' \
            --exclude='.env' \
            --exclude='*.log' \
            "bots/$bot/" "$VPS_HOST:$VPS_DIR/bots/$bot/"
    else
        echo -e "  ${YELLOW}Skipping bots/$bot/ (not found locally)${NC}"
    fi
done
echo

# Step 6: Deploy SOUL/IDENTITY/BOOTSTRAP files
echo "Step 6: Syncing SOUL files ..."
for bot in clawdjarvis clawdfriday clawdmatt; do
    for file in SOUL.md IDENTITY.md BOOTSTRAP.md personality.json; do
        if [ -f "bots/$bot/$file" ]; then
            echo "  $bot/$file"
            rsync -avz $DRY_RUN "bots/$bot/$file" "$VPS_HOST:$VPS_DIR/bots/$bot/$file"
        fi
    done
done
echo

# Step 7: Restart services
echo "Step 7: Restarting bot services ..."
if [[ -z "$DRY_RUN" ]]; then
    ssh "${VPS_HOST}" "
        # Try systemd first
        if systemctl list-units --type=service 2>/dev/null | grep -qE '(clawdjarvis|clawdfriday|clawdmatt)'; then
            echo 'Restarting via systemd...'
            systemctl restart clawdjarvis clawdfriday clawdmatt 2>/dev/null || echo 'Some services failed to restart'
            sleep 3
        elif [ -f '${VPS_DIR}/stop_all_bots.sh' ] && [ -f '${VPS_DIR}/start_all_bots.sh' ]; then
            echo 'Restarting via control scripts...'
            cd ${VPS_DIR}
            ./stop_all_bots.sh 2>&1 || true
            sleep 3
            ./start_all_bots.sh 2>&1 || true
            sleep 2
        else
            echo 'WARNING: No restart mechanism found - restart bots manually'
        fi
    "
    echo -e "${GREEN}Restart commands sent${NC}"
else
    echo "  [DRY RUN] Would restart clawdjarvis, clawdfriday, clawdmatt"
fi
echo

# Step 8: Verify services are running
echo "Step 8: Checking service status ..."
if [[ -z "$DRY_RUN" ]]; then
    ssh "${VPS_HOST}" "
        echo '--- Service Status ---'
        for svc in clawdjarvis clawdfriday clawdmatt; do
            if systemctl is-active \$svc 2>/dev/null; then
                echo \"  \$svc: ACTIVE\"
            else
                # Fallback: check process
                if ps aux | grep -v grep | grep -q \$svc; then
                    echo \"  \$svc: RUNNING (process)\"
                else
                    echo \"  \$svc: NOT RUNNING\"
                fi
            fi
        done
        echo ''
        echo '--- File counts ---'
        echo \"  bots/shared/: \$(ls ${VPS_DIR}/bots/shared/*.py 2>/dev/null | wc -l) Python files\"
    "
else
    echo "  [DRY RUN] Would verify services"
fi
echo

# Summary
echo "========================================="
echo "DEPLOYMENT SUMMARY"
echo "========================================="
if [[ -n "$DRY_RUN" ]]; then
    echo -e "${YELLOW}DRY RUN - No changes were made${NC}"
else
    echo -e "${GREEN}Deployment Complete${NC}"
fi
echo
echo "New modules deployed:"
echo "  - allowlist.py (auth middleware)"
echo "  - command_blocklist.py (dangerous command filtering)"
echo "  - bot_lifecycle.py (startup/shutdown hooks)"
echo "  - action_confirmation.py (Telegram approval workflow)"
echo "  - knowledge_graph.py (SQLite PKG)"
echo "  - memory_tags.py (tag-based access control)"
echo "  - morning_brief.py (daily intelligence brief)"
echo "  - scheduled_tasks.py (lightweight scheduler)"
echo "  - memory_management.py (log rotation/compaction)"
echo "  - kaizen.py (self-improvement loops)"
echo
echo "Rollback (if needed):"
echo "  ssh ${VPS_HOST} 'ls ${VPS_DIR}/backups/'"
echo "========================================="
