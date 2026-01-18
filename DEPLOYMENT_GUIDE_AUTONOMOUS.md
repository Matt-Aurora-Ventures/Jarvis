# Jarvis Autonomous System - Deployment Guide

**Date**: January 17, 2026
**Version**: 4.8.0 - Complete Autonomous System Integration
**Status**: Ready for VPS deployment

## Summary

This deployment guide covers the integration and deployment of Jarvis's complete autonomous system:
- **Auto-Moderation**: Toxicity detection + auto-actions (warn/mute/ban)
- **Self-Improvement**: Engagement analyzer → optimization recommendations
- **Vibe Coding**: Sentiment-driven parameter adaptation
- **Unified Logic Bus**: Central orchestrator for all components

All components are integrated into `bots/supervisor.py` and run continuously without human intervention.

---

## Local Testing

### 1. Quick Import Test

```bash
cd ~/Jarvis
python -c "
from core.moderation.toxicity_detector import ToxicityDetector
from core.moderation.auto_actions import AutoActions
from core.learning.engagement_analyzer import EngagementAnalyzer
from core.vibe_coding.sentiment_mapper import SentimentMapper
from core.vibe_coding.regime_adapter import RegimeAdapter
from core.autonomous_manager import get_autonomous_manager
print('[OK] All autonomous components import successfully')
"
```

### 2. Run Full Validation Suite (Local)

Run all 6 validation tests on your machine:

```bash
cd ~/Jarvis
python scripts/validate_autonomous_system.py
# Runs until Ctrl+C
# Press Ctrl+C after seeing 1-2 iterations
```

Expected output:
```
Iteration 1 Results: 6/6 tests passed
  [PASS] Position Sync
  [PASS] Moderation
  [PASS] Learning
  [PASS] Vibe Coding
  [PASS] Autonomous Loops
  [PASS] State Persistence
```

---

## VPS Deployment

### Step 1: SSH to VPS

```bash
ssh jarvis@165.232.123.6
cd ~/Jarvis
```

### Step 2: Pull Latest Code

```bash
git pull origin main

# Verify commits present
git log --oneline | head -5
```

### Step 3: Restart Supervisor

```bash
sudo systemctl restart jarvis-supervisor

# Wait 10 seconds
sleep 10

# Check status
sudo systemctl status jarvis-supervisor
```

### Step 4: Verify Autonomous Manager Started

```bash
# Check logs for autonomous_manager startup
tail -30 ~/Jarvis/logs/supervisor.log | grep autonomous_manager

# Should show:
# [autonomous_manager] Initializing autonomous system components...
# [autonomous_manager] Moderation initialized
# [autonomous_manager] Learning analyzer initialized
# [autonomous_manager] All components initialized, starting loops...
```

---

## Continuous Validation Loop

### Run Ralph Wiggum Loop

After deployment, run continuous tests:

```bash
ssh jarvis@165.232.123.6
cd ~/Jarvis

# Start validation loop
nohup python scripts/validate_autonomous_system.py > validation.log 2>&1 &

# Monitor
tail -f validation.log

# Check proof files (one per iteration)
ls -la data/validation_proof/
```

---

## Components Working

All 6 validation tests should pass:

1. **Position Sync** - Treasury → Scorekeeper → Dashboard
2. **Moderation** - Toxicity detection + auto-actions
3. **Learning** - Engagement analyzer recommendations
4. **Vibe Coding** - Sentiment-driven regime adaptation
5. **Autonomous Loops** - All components running
6. **State Persistence** - Data survives operations

---

## Troubleshooting

### Check Component Startup

```bash
tail -100 ~/Jarvis/logs/supervisor.log | grep -E "autonomous|STARTING|RUNNING"
```

### Verify Imports

```bash
python -c "from core.autonomous_manager import get_autonomous_manager; print('OK')"
```

### Check Supervisor Health

```bash
sudo systemctl status jarvis-supervisor
journalctl -u jarvis-supervisor -n 50
```

---

## Rollback

```bash
git log --oneline | head -10
git checkout <previous_commit_hash>
sudo systemctl restart jarvis-supervisor
```

---

## Next Steps

1. Deploy to VPS using steps above
2. Run validation loop for 24+ hours
3. Collect proof from `data/validation_proof/`
4. Monitor component health via logs
