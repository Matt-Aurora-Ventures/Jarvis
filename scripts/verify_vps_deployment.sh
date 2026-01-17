#!/bin/bash
# VPS Deployment Verification Script
# Run this AFTER deployment and key updates to confirm all services are working
# Usage: bash verify_vps_deployment.sh

set -e

echo "========================================"
echo "JARVIS VPS DEPLOYMENT VERIFICATION"
echo "========================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

CHECKS_PASSED=0
CHECKS_FAILED=0

check_service() {
    local service=$1
    local name=$2

    if systemctl is-active --quiet $service; then
        echo -e "${GREEN}✓${NC} $name is running"
        ((CHECKS_PASSED++))
    else
        echo -e "${RED}✗${NC} $name is NOT running"
        ((CHECKS_FAILED++))
        return 1
    fi
}

check_file() {
    local file=$1
    local name=$2

    if [ -f "$file" ]; then
        echo -e "${GREEN}✓${NC} $name exists"
        ((CHECKS_PASSED++))
    else
        echo -e "${RED}✗${NC} $name MISSING"
        ((CHECKS_FAILED++))
        return 1
    fi
}

check_json() {
    local file=$1
    local name=$2

    if python3 -m json.tool "$file" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} $name JSON is valid"
        ((CHECKS_PASSED++))
    else
        echo -e "${RED}✗${NC} $name JSON is INVALID"
        ((CHECKS_FAILED++))
        return 1
    fi
}

# Phase 1: Check Installation
echo "Phase 1: Installation Check"
echo "================================"
check_file "/home/jarvis/Jarvis/bots/supervisor.py" "Supervisor script"
check_file "/home/jarvis/Jarvis/tg_bot/bot.py" "Telegram bot script"
check_file "/home/jarvis/Jarvis/bots/twitter/run_autonomous.py" "Twitter bot script"
check_file "/home/jarvis/Jarvis/venv/bin/python" "Python venv"
echo ""

# Phase 2: Check Secrets
echo "Phase 2: Secrets Configuration"
echo "================================"
check_file "/home/jarvis/Jarvis/secrets/keys.json" "Secrets file"
check_json "/home/jarvis/Jarvis/secrets/keys.json" "Secrets JSON"

# Check for REPLACEME values
if grep -q "REPLACEME" /home/jarvis/Jarvis/secrets/keys.json; then
    echo -e "${YELLOW}⚠${NC}  WARNING: Found REPLACEME in secrets (not all keys updated)"
    ((CHECKS_FAILED++))
else
    echo -e "${GREEN}✓${NC} All API keys appear to be configured"
    ((CHECKS_PASSED++))
fi
echo ""

# Phase 3: Check Services
echo "Phase 3: Service Status"
echo "================================"
check_service "jarvis-supervisor.service" "Supervisor service"
check_service "jarvis-telegram.service" "Telegram bot service"
check_service "jarvis-twitter.service" "Twitter bot service"
echo ""

# Phase 4: Check Logs (no errors in last few entries)
echo "Phase 4: Recent Log Check"
echo "================================"

# Check supervisor logs for errors
if journalctl -u jarvis-supervisor -n 10 2>/dev/null | grep -i "error\|exception\|traceback" > /dev/null; then
    echo -e "${YELLOW}⚠${NC}  Supervisor logs contain recent errors (check: journalctl -u jarvis-supervisor -n 50)"
    ((CHECKS_FAILED++))
else
    echo -e "${GREEN}✓${NC} Supervisor logs look clean"
    ((CHECKS_PASSED++))
fi

# Check telegram logs for errors
if journalctl -u jarvis-telegram -n 10 2>/dev/null | grep -i "error\|exception\|traceback" > /dev/null; then
    echo -e "${YELLOW}⚠${NC}  Telegram logs contain recent errors (check: journalctl -u jarvis-telegram -n 50)"
    ((CHECKS_FAILED++))
else
    echo -e "${GREEN}✓${NC} Telegram logs look clean"
    ((CHECKS_PASSED++))
fi

# Check twitter logs for errors
if journalctl -u jarvis-twitter -n 10 2>/dev/null | grep -i "error\|exception\|traceback" > /dev/null; then
    echo -e "${YELLOW}⚠${NC}  Twitter logs contain recent errors (check: journalctl -u jarvis-twitter -n 50)"
    ((CHECKS_FAILED++))
else
    echo -e "${GREEN}✓${NC} Twitter logs look clean"
    ((CHECKS_PASSED++))
fi
echo ""

# Phase 5: Resource Usage
echo "Phase 5: Resource Usage"
echo "================================"

# Check disk space
DISK_USAGE=$(df /home/jarvis/Jarvis | tail -1 | awk '{print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -lt 80 ]; then
    echo -e "${GREEN}✓${NC} Disk usage: ${DISK_USAGE}% (OK)"
    ((CHECKS_PASSED++))
else
    echo -e "${RED}✗${NC} Disk usage: ${DISK_USAGE}% (HIGH)"
    ((CHECKS_FAILED++))
fi

# Check memory for python processes
PYTHON_PROCS=$(ps aux | grep -E "python|supervisor|telegram|twitter" | grep -v grep | wc -l)
echo -e "${GREEN}✓${NC} Found $PYTHON_PROCS Python processes"
echo ""

# Summary
echo "========================================"
echo "VERIFICATION SUMMARY"
echo "========================================"
echo -e "${GREEN}Passed: $CHECKS_PASSED${NC}"
echo -e "${RED}Failed: $CHECKS_FAILED${NC}"
echo ""

if [ $CHECKS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed! Your deployment is healthy.${NC}"
    echo ""
    echo "Your Jarvis bots are running 24/7:"
    echo "  - Supervisor: Managing internal bots"
    echo "  - Telegram: @Jarviskr8tivbot (use /start to test)"
    echo "  - Twitter: @Jarvis_lifeos (posts sentiment & grok analysis)"
    echo ""
    echo "Monitor logs anytime:"
    echo "  journalctl -u jarvis-supervisor -f"
    exit 0
else
    echo -e "${RED}✗ Some checks failed. Review errors above and fix before proceeding.${NC}"
    echo ""
    echo "Common issues:"
    echo "  1. REPLACEME values in secrets - run: nano /home/jarvis/Jarvis/secrets/keys.json"
    echo "  2. Service errors - check: journalctl -u <service> -n 100"
    echo "  3. Missing dependencies - run: cd /home/jarvis/Jarvis && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi
