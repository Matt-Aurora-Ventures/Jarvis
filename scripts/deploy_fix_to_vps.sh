#!/bin/bash
# VPS Deployment Script - Treasury Bot Critical Fix
# Deploys EMERGENCY_FIX_TREASURY_BOT.md solution to production VPS
#
# Usage: ./scripts/deploy_fix_to_vps.sh [vps_hostname] [vps_user]

set -e  # Exit on error

VPS_HOST="${1:-your-vps-hostname}"
VPS_USER="${2:-ubuntu}"
VPS_PATH="/opt/jarvis"  # Adjust to your VPS path

echo "🚀 VPS Deployment Script - Treasury Bot Critical Fix"
echo "=" 80
echo "Target: ${VPS_USER}@${VPS_HOST}:${VPS_PATH}"
echo "=" 80
echo

# Step 1: Verify local changes are committed
echo "📋 Step 1: Verifying local changes are committed..."
if ! git diff-index --quiet HEAD --; then
    echo "❌ ERROR: Uncommitted changes detected!"
    echo "Please commit all changes before deploying."
    exit 1
fi
echo "✅ All changes committed"
echo

# Step 2: Check VPS connectivity
echo "🔍 Step 2: Testing VPS connectivity..."
if ! ssh -o ConnectTimeout=5 "${VPS_USER}@${VPS_HOST}" "echo 'Connection successful'" 2>/dev/null; then
    echo "❌ ERROR: Cannot connect to VPS"
    echo "Please check:"
    echo "  - VPS hostname is correct"
    echo "  - SSH keys are set up"
    echo "  - VPS is online"
    exit 1
fi
echo "✅ VPS connection successful"
echo

# Step 3: Backup current VPS state
echo "💾 Step 3: Backing up current VPS state..."
ssh "${VPS_USER}@${VPS_HOST}" << 'ENDSSH'
cd /opt/jarvis || exit 1
# Create backup directory with timestamp
BACKUP_DIR="backups/pre-treasury-fix-$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Backup critical files
cp bots/treasury/run_treasury.py "$BACKUP_DIR/" 2>/dev/null || echo "run_treasury.py not found"
cp lifeos/config/.env "$BACKUP_DIR/.env.backup" 2>/dev/null || echo ".env not found"
git log -1 > "$BACKUP_DIR/git-commit.txt"

echo "✅ Backup created: $BACKUP_DIR"
ENDSSH
echo

# Step 4: Pull latest code from GitHub
echo "📥 Step 4: Pulling latest code from GitHub..."
ssh "${VPS_USER}@${VPS_HOST}" << 'ENDSSH'
cd /opt/jarvis || exit 1

echo "Current commit:"
git log -1 --oneline

echo "Fetching latest..."
git fetch origin main

echo "Pulling updates..."
git pull origin main

echo "New commit:"
git log -1 --oneline
ENDSSH
echo "✅ Code updated on VPS"
echo

# Step 5: Verify TREASURY_BOT_TOKEN
echo "🔐 Step 5: Checking if TREASURY_BOT_TOKEN is set..."
TOKEN_STATUS=$(ssh "${VPS_USER}@${VPS_HOST}" << 'ENDSSH'
cd /opt/jarvis || exit 1
python3 -c "
import os
from dotenv import load_dotenv
load_dotenv('lifeos/config/.env')
token = os.environ.get('TREASURY_BOT_TOKEN')
if token:
    print(f'SET (first 20 chars: {token[:20]}...)')
else:
    print('NOT_SET')
" 2>/dev/null || echo "ERROR_CHECKING"
ENDSSH
)

if [[ "$TOKEN_STATUS" == "NOT_SET" ]]; then
    echo "⚠️  WARNING: TREASURY_BOT_TOKEN is NOT SET on VPS!"
    echo
    echo "Treasury bot will NOT start until you:"
    echo "1. Create token via @BotFather (see TELEGRAM_BOT_TOKEN_GENERATION_GUIDE.md)"
    echo "2. SSH to VPS: ssh ${VPS_USER}@${VPS_HOST}"
    echo "3. Edit .env: nano ${VPS_PATH}/lifeos/config/.env"
    echo "4. Add line: TREASURY_BOT_TOKEN=<your_token>"
    echo "5. Re-run this script"
    echo
    read -p "Continue anyway? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Deployment aborted. Fix TREASURY_BOT_TOKEN first."
        exit 1
    fi
else
    echo "✅ TREASURY_BOT_TOKEN is set: $TOKEN_STATUS"
fi
echo

# Step 6: Stop supervisor
echo "⏹️  Step 6: Stopping supervisor..."
ssh "${VPS_USER}@${VPS_HOST}" << 'ENDSSH'
cd /opt/jarvis || exit 1

# Try multiple stop methods
pkill -f "supervisor.py" 2>/dev/null || true
systemctl stop jarvis-supervisor 2>/dev/null || true

# Wait for processes to stop
sleep 3

# Verify stopped
if pgrep -f "supervisor.py" > /dev/null; then
    echo "⚠️  Supervisor still running, forcing kill..."
    pkill -9 -f "supervisor.py"
    sleep 2
fi

echo "✅ Supervisor stopped"
ENDSSH
echo

# Step 7: Install/update dependencies
echo "📦 Step 7: Updating dependencies..."
ssh "${VPS_USER}@${VPS_HOST}" << 'ENDSSH'
cd /opt/jarvis || exit 1

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
fi

# Update dependencies
pip install -r requirements.txt --quiet

echo "✅ Dependencies updated"
ENDSSH
echo

# Step 8: Start supervisor
echo "▶️  Step 8: Starting supervisor..."
ssh "${VPS_USER}@${VPS_HOST}" << 'ENDSSH'
cd /opt/jarvis || exit 1

# Activate virtual environment
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
fi

# Start supervisor in background
nohup python bots/supervisor.py > logs/supervisor.log 2>&1 &

sleep 5

# Check if running
if pgrep -f "supervisor.py" > /dev/null; then
    echo "✅ Supervisor started successfully"
else
    echo "❌ Supervisor failed to start!"
    echo "Check logs: tail -50 logs/supervisor.log"
    exit 1
fi
ENDSSH
echo

# Step 9: Monitor logs for success/failure
echo "📊 Step 9: Monitoring logs for 30 seconds..."
ssh "${VPS_USER}@${VPS_HOST}" << 'ENDSSH'
cd /opt/jarvis || exit 1

echo "Watching supervisor logs..."
timeout 30 tail -f logs/supervisor.log | while read line; do
    echo "$line"

    # Check for success indicators
    if echo "$line" | grep -q "Using unique treasury bot token"; then
        echo "✅ Treasury bot using unique token!"
    fi

    # Check for failure indicators
    if echo "$line" | grep -q "TREASURY_BOT_TOKEN not set"; then
        echo "❌ Treasury bot token still not set!"
    fi

    if echo "$line" | grep -q "Conflict: terminated by other getUpdates"; then
        echo "❌ Polling conflict still occurring!"
    fi

    if echo "$line" | grep -q "exited with code 4294967295"; then
        echo "❌ Treasury bot crashed with 4294967295!"
    fi
done

echo
echo "Log monitoring complete. Check full logs if needed:"
echo "  ssh ${VPS_USER}@${VPS_HOST} 'tail -100 ${VPS_PATH}/logs/supervisor.log'"
ENDSSH
echo

# Step 10: Deployment summary
echo "=" 80
echo "🎯 DEPLOYMENT SUMMARY"
echo "=" 80
echo "✅ Code deployed to VPS"
echo "✅ Supervisor restarted"
echo
echo "NEXT STEPS:"
echo "1. Monitor logs for 10+ minutes: ssh ${VPS_USER}@${VPS_HOST} 'tail -f ${VPS_PATH}/logs/supervisor.log'"
echo "2. Verify no crashes with exit code 4294967295"
echo "3. Verify no 'Conflict: terminated by other getUpdates' errors"
echo "4. If TREASURY_BOT_TOKEN not set, follow EMERGENCY_FIX_TREASURY_BOT.md"
echo
echo "ROLLBACK (if needed):"
echo "  ssh ${VPS_USER}@${VPS_HOST}"
echo "  cd ${VPS_PATH}"
echo "  git reset --hard HEAD~1  # Revert to previous commit"
echo "  pkill -f supervisor.py && python bots/supervisor.py"
echo
echo "=" 80
echo "Deployment complete!"
echo "=" 80
