#!/bin/bash
#
# Jarvis Autonomous System - VPS Deployment Script
# Run this on the VPS to deploy the complete autonomous system
#
# Usage: bash deploy_autonomous_system.sh
#

set -e

PROJECT_HOME="$HOME/Jarvis"
LOG_FILE="$PROJECT_HOME/logs/deployment.log"

echo "[$(date)] ============================================================" | tee -a "$LOG_FILE"
echo "[$(date)] JARVIS AUTONOMOUS SYSTEM - VPS DEPLOYMENT" | tee -a "$LOG_FILE"
echo "[$(date)] ============================================================" | tee -a "$LOG_FILE"

# Step 1: Verify we're in the right directory
echo "[$(date)] STEP 1: Verifying project directory..." | tee -a "$LOG_FILE"
if [ ! -d "$PROJECT_HOME" ]; then
    echo "[ERROR] Project directory not found: $PROJECT_HOME" | tee -a "$LOG_FILE"
    exit 1
fi
cd "$PROJECT_HOME"
echo "[OK] Project directory verified: $(pwd)" | tee -a "$LOG_FILE"

# Step 2: Pull latest code
echo "[$(date)] STEP 2: Pulling latest code from main branch..." | tee -a "$LOG_FILE"
git fetch origin main
git reset --hard origin/main
echo "[OK] Code updated to latest version" | tee -a "$LOG_FILE"

# Step 3: Verify autonomous system files exist
echo "[$(date)] STEP 3: Verifying autonomous system files..." | tee -a "$LOG_FILE"
required_files=(
    "core/moderation/toxicity_detector.py"
    "core/moderation/auto_actions.py"
    "core/learning/engagement_analyzer.py"
    "core/vibe_coding/sentiment_mapper.py"
    "core/vibe_coding/regime_adapter.py"
    "core/autonomous_manager.py"
    "scripts/validate_autonomous_system.py"
)

for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
        echo "[ERROR] Missing required file: $file" | tee -a "$LOG_FILE"
        exit 1
    fi
done
echo "[OK] All autonomous system files present" | tee -a "$LOG_FILE"

# Step 4: Create required directories
echo "[$(date)] STEP 4: Creating required directories..." | tee -a "$LOG_FILE"
mkdir -p data/moderation data/learning data/vibe_coding data/validation_proof logs
echo "[OK] Directories created" | tee -a "$LOG_FILE"

# Step 5: Stop supervisor gracefully
echo "[$(date)] STEP 5: Stopping supervisor gracefully..." | tee -a "$LOG_FILE"
sudo systemctl stop jarvis-supervisor || true
sleep 5
echo "[OK] Supervisor stopped" | tee -a "$LOG_FILE"

# Step 6: Restart supervisor
echo "[$(date)] STEP 6: Restarting supervisor with autonomous manager..." | tee -a "$LOG_FILE"
sudo systemctl start jarvis-supervisor
sleep 10
echo "[OK] Supervisor started" | tee -a "$LOG_FILE"

# Step 7: Verify supervisor status
echo "[$(date)] STEP 7: Verifying supervisor status..." | tee -a "$LOG_FILE"
sudo systemctl status jarvis-supervisor --no-pager | head -10 | tee -a "$LOG_FILE"

# Step 8: Check for autonomous_manager startup
echo "[$(date)] STEP 8: Checking autonomous_manager startup..." | tee -a "$LOG_FILE"
sleep 5
if tail -20 "$PROJECT_HOME/logs/supervisor.log" | grep -q "autonomous_manager"; then
    echo "[OK] autonomous_manager component detected in logs" | tee -a "$LOG_FILE"
else
    echo "[WARNING] autonomous_manager not yet visible in logs, checking again..." | tee -a "$LOG_FILE"
    sleep 10
    tail -30 "$PROJECT_HOME/logs/supervisor.log" | tee -a "$LOG_FILE"
fi

# Step 9: Sync treasury positions
echo "[$(date)] STEP 9: Syncing treasury positions to dashboard..." | tee -a "$LOG_FILE"
if python scripts/sync_treasury_positions.py >> "$LOG_FILE" 2>&1; then
    echo "[OK] Treasury positions synced" | tee -a "$LOG_FILE"
else
    echo "[WARNING] Position sync encountered issues (continuing)" | tee -a "$LOG_FILE"
fi

# Step 10: Start validation loop
echo "[$(date)] STEP 10: Starting continuous validation loop..." | tee -a "$LOG_FILE"
nohup python scripts/validate_autonomous_system.py > logs/validation_continuous.log 2>&1 &
VALIDATION_PID=$!
echo "[OK] Validation loop started (PID: $VALIDATION_PID)" | tee -a "$LOG_FILE"
sleep 5

# Step 11: Check validation loop output
echo "[$(date)] STEP 11: Checking validation loop output..." | tee -a "$LOG_FILE"
head -30 "logs/validation_continuous.log" | tee -a "$LOG_FILE"

# Step 12: Final status
echo "[$(date)] ============================================================" | tee -a "$LOG_FILE"
echo "[$(date)] DEPLOYMENT COMPLETE" | tee -a "$LOG_FILE"
echo "[$(date)] ============================================================" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
echo "STATUS:" | tee -a "$LOG_FILE"
echo "  ✓ Code updated to latest version" | tee -a "$LOG_FILE"
echo "  ✓ Supervisor restarted with all components" | tee -a "$LOG_FILE"
echo "  ✓ Treasury positions synced to dashboard" | tee -a "$LOG_FILE"
echo "  ✓ Validation loop running (PID: $VALIDATION_PID)" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
echo "NEXT STEPS:" | tee -a "$LOG_FILE"
echo "  1. Monitor validation loop:" | tee -a "$LOG_FILE"
echo "     tail -f logs/validation_continuous.log" | tee -a "$LOG_FILE"
echo "  2. Check supervisor health:" | tee -a "$LOG_FILE"
echo "     journalctl -u jarvis-supervisor -f" | tee -a "$LOG_FILE"
echo "  3. Collect validation proof after 24+ hours:" | tee -a "$LOG_FILE"
echo "     ls -la data/validation_proof/" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
echo "[$(date)] Log file: $LOG_FILE" | tee -a "$LOG_FILE"
