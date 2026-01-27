#!/bin/bash
# Deploy JARVIS Resilience System to VPS
# Run this on the VPS via Hostinger web console or SSH

set -e

echo "=========================================="
echo "JARVIS RESILIENCE SYSTEM DEPLOYMENT"
echo "=========================================="

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}[Step 1/5] Pull latest code from GitHub${NC}"
cd /home/jarvis/Jarvis
sudo -u jarvis git pull origin main

echo -e "${GREEN}✓ Code updated${NC}"
echo ""

echo -e "${BLUE}[Step 2/5] Install any new dependencies${NC}"
sudo -u jarvis bash -c "
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
"

echo -e "${GREEN}✓ Dependencies updated${NC}"
echo ""

echo -e "${BLUE}[Step 3/5] Verify new files exist${NC}"
ls -lh core/resilient_provider.py
ls -lh core/provider_health_monitor.py
ls -lh tg_bot/middleware/resilient_errors.py
ls -lh tg_bot/handlers/commands/health_command.py
ls -lh tg_bot/handlers/commands/vibe_command.py

echo -e "${GREEN}✓ New files present${NC}"
echo ""

echo -e "${BLUE}[Step 4/5] Restart Telegram bot service${NC}"
systemctl restart jarvis-telegram.service

echo -e "${GREEN}✓ Service restarted${NC}"
echo ""

echo -e "${BLUE}[Step 5/5] Verify service status and check logs${NC}"
systemctl status jarvis-telegram.service --no-pager | head -20

echo ""
echo "Recent logs:"
journalctl -u jarvis-telegram.service -n 30 --no-pager

echo ""
echo "=========================================="
echo "DEPLOYMENT COMPLETE!"
echo "=========================================="
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Watch logs for provider initialization:"
echo "   journalctl -u jarvis-telegram -f"
echo ""
echo "2. Look for these success messages:"
echo "   ✅ Dexter provider registered (Priority 1 - FREE)"
echo "   💰 Cost optimization: Dexter (FREE) is priority 1"
echo ""
echo "3. Test in Telegram:"
echo "   /health  - Check provider status"
echo "   /vibe hello  - Test AI chat"
echo ""
echo "=========================================="
