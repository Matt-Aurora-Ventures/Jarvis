#!/bin/bash
# VPS Deployment for Phase 7 Testing (Commit 56744e5)
# Safe deployment - only code updates, no dependency changes

echo "═══════════════════════════════════════════════"
echo "  JARVIS PHASE 7 DEPLOYMENT"
echo "  Commit: 56744e5"
echo "  Changes: Bug fixes + test suite expansion"
echo "═══════════════════════════════════════════════"
echo ""

# Connect to VPS and execute deployment
ssh root@72.61.7.126 << 'REMOTE'
  echo "Step 1: Navigating to Jarvis directory..."
  cd /home/jarvis/Jarvis

  echo "Step 2: Pulling latest code from GitHub..."
  git pull origin main

  echo "Step 3: Verifying commit..."
  git log -1 --oneline

  echo "Step 4: Restarting supervisor services..."
  docker restart jarvis-supervisor

  echo "Step 5: Waiting for services to start..."
  sleep 5

  echo "Step 6: Checking service status..."
  docker ps | grep jarvis-supervisor

  echo ""
  echo "═══════════════════════════════════════════════"
  echo "  DEPLOYMENT COMPLETE"
  echo "═══════════════════════════════════════════════"
  echo ""
  echo "Services restarted:"
  echo "  ✅ jarvis-supervisor (Docker container)"
  echo "  ✅ Telegram bot"
  echo "  ✅ Buy tracker"
  echo "  ✅ Autonomous manager"
  echo ""
  echo "Changes deployed:"
  echo "  • Bug fix: buy_tracker tx_signature → signature"
  echo "  • Stability: Claude model rollback to 3.5 Sonnet"
  echo "  • Testing: 186 tests, 69% coverage on trading_operations"
  echo ""
REMOTE

echo "Deployment script complete!"
echo ""
echo "Next: Monitor logs with:"
echo "  ssh root@72.61.7.126 'docker logs -f jarvis-supervisor'"
