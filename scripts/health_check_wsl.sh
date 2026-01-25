#!/bin/bash
# WSL Development Environment - Daily Health Check
# Quick status check for Claude CLI, Clawd, GSD, and WSL environment
# Run this daily or before starting work

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

HEALTH_SCORE=100
WARNINGS=0
ERRORS=0

print_header() {
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║            WSL Development Environment Health Check          ║${NC}"
    echo -e "${BLUE}║                     $(date '+%Y-%m-%d %H:%M:%S')                      ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

check_ok() {
    echo -e "${GREEN}●${NC} $1"
}

check_warn() {
    echo -e "${YELLOW}●${NC} $1"
    WARNINGS=$((WARNINGS + 1))
    HEALTH_SCORE=$((HEALTH_SCORE - 5))
}

check_error() {
    echo -e "${RED}●${NC} $1"
    ERRORS=$((ERRORS + 1))
    HEALTH_SCORE=$((HEALTH_SCORE - 15))
}

print_section() {
    echo ""
    echo -e "${BLUE}$1${NC}"
}

# Start
print_header

# ==========================================
# 1. Core Services Status
# ==========================================
print_section "🔧 Core Services"

# Claude CLI
if command -v claude &> /dev/null; then
    if claude --version &> /dev/null; then
        check_ok "Claude CLI: Running"
    else
        check_error "Claude CLI: Installed but not working"
    fi
else
    check_error "Claude CLI: Not installed"
fi

# Clawd Bot (check if process is running)
if pgrep -f "clawd" > /dev/null || pgrep -f "main.py" > /dev/null; then
    check_ok "Clawd Bot: Running"
elif [ -d "$HOME/clawd" ]; then
    check_warn "Clawd Bot: Installed but not running"
else
    check_warn "Clawd Bot: Not installed"
fi

# VS Code
if command -v code &> /dev/null; then
    check_ok "VS Code: Available"
else
    check_warn "VS Code: Not installed"
fi

# ==========================================
# 2. Environment Configuration
# ==========================================
print_section "⚙️  Configuration"

# Config file
if [ -f "$HOME/.wsl_dev_config" ]; then
    check_ok "Config file: Present"

    # Check API keys
    source "$HOME/.wsl_dev_config"
    if [ -z "$CLAUDE_API_KEY" ]; then
        check_warn "CLAUDE_API_KEY: Not configured"
    else
        check_ok "CLAUDE_API_KEY: Configured"
    fi

    if [ -z "$DISCORD_BOT_TOKEN" ]; then
        check_warn "DISCORD_BOT_TOKEN: Not configured"
    else
        check_ok "DISCORD_BOT_TOKEN: Configured"
    fi
else
    check_error "Config file: Missing"
fi

# ==========================================
# 3. Network Status
# ==========================================
print_section "🌐 Network"

# Internet
if ping -c 1 -W 2 8.8.8.8 &> /dev/null; then
    check_ok "Internet: Connected"
else
    check_error "Internet: No connectivity"
fi

# DNS
if ping -c 1 -W 2 google.com &> /dev/null; then
    check_ok "DNS: Resolving"
else
    check_warn "DNS: Not resolving"
fi

# Anthropic API
if timeout 3 curl -s https://api.anthropic.com &> /dev/null; then
    check_ok "Anthropic API: Reachable"
else
    check_warn "Anthropic API: Unreachable"
fi

# ==========================================
# 4. Resource Usage
# ==========================================
print_section "💾 Resources"

# Memory
TOTAL_MEM=$(free -h | awk '/^Mem:/ {print $2}')
USED_MEM=$(free -h | awk '/^Mem:/ {print $3}')
AVAIL_MEM_MB=$(free -m | awk '/^Mem:/ {print $7}')

if [ "$AVAIL_MEM_MB" -gt 1000 ]; then
    check_ok "Memory: ${USED_MEM}/${TOTAL_MEM} used (${AVAIL_MEM_MB}MB available)"
elif [ "$AVAIL_MEM_MB" -gt 500 ]; then
    check_warn "Memory: ${USED_MEM}/${TOTAL_MEM} used (${AVAIL_MEM_MB}MB available - running low)"
else
    check_error "Memory: ${USED_MEM}/${TOTAL_MEM} used (${AVAIL_MEM_MB}MB available - critically low)"
fi

# Disk
DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}')
DISK_USAGE_PCT=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')

if [ "$DISK_USAGE_PCT" -lt 80 ]; then
    check_ok "Disk: ${DISK_USAGE} used"
elif [ "$DISK_USAGE_PCT" -lt 90 ]; then
    check_warn "Disk: ${DISK_USAGE} used (getting high)"
else
    check_error "Disk: ${DISK_USAGE} used (critically high)"
fi

# CPU load
LOAD_AVG=$(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | tr -d ',')
check_ok "CPU Load: ${LOAD_AVG}"

# ==========================================
# 5. Projects Status
# ==========================================
print_section "📁 Projects"

# Clawd
if [ -d "$HOME/clawd" ]; then
    cd "$HOME/clawd"
    if [ -d ".git" ]; then
        GIT_STATUS=$(git status --porcelain 2>/dev/null | wc -l)
        if [ "$GIT_STATUS" -eq 0 ]; then
            check_ok "Clawd: Clean (no uncommitted changes)"
        else
            check_warn "Clawd: ${GIT_STATUS} uncommitted changes"
        fi
    else
        check_warn "Clawd: Not a git repository"
    fi

    # Check if dependencies are installed
    if [ -f "package.json" ] && [ ! -d "node_modules" ]; then
        check_error "Clawd: node_modules missing (run: npm install)"
    elif [ -f "requirements.txt" ] && [ ! -d "venv" ]; then
        check_error "Clawd: venv missing (run: python3 -m venv venv)"
    fi
else
    check_warn "Clawd: Not installed"
fi

# GSD
if [ -d "$HOME/get-shit-done" ]; then
    check_ok "GSD: Installed"
else
    check_warn "GSD: Not installed"
fi

# ==========================================
# 6. Updates Available
# ==========================================
print_section "🔄 Updates"

# Check when last update was run
if command -v npm &> /dev/null; then
    NPM_OUTDATED=$(npm outdated -g 2>/dev/null | wc -l)
    if [ "$NPM_OUTDATED" -gt 1 ]; then
        check_warn "npm: $((NPM_OUTDATED - 1)) global packages have updates"
    else
        check_ok "npm: All global packages up to date"
    fi
fi

# Check system updates
if command -v apt &> /dev/null; then
    APT_UPDATES=$(apt list --upgradable 2>/dev/null | grep -c "upgradable")
    if [ "$APT_UPDATES" -gt 0 ]; then
        check_warn "System: ${APT_UPDATES} packages have updates (run: update-dev)"
    else
        check_ok "System: Up to date"
    fi
fi

# ==========================================
# 7. Systemd Services (if enabled)
# ==========================================
if [ -d /run/systemd/system ]; then
    print_section "⚡ Services"

    if systemctl is-active --quiet clawd 2>/dev/null; then
        check_ok "Clawd Service: Running"
    elif systemctl is-enabled --quiet clawd 2>/dev/null; then
        check_warn "Clawd Service: Enabled but not running"
    else
        check_ok "Clawd Service: Not configured (manual start)"
    fi
fi

# ==========================================
# Health Score & Summary
# ==========================================
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Calculate health score (0-100)
if [ $HEALTH_SCORE -lt 0 ]; then
    HEALTH_SCORE=0
fi

# Determine health status
if [ $HEALTH_SCORE -ge 90 ]; then
    HEALTH_STATUS="${GREEN}Excellent${NC}"
    HEALTH_EMOJI="🟢"
elif [ $HEALTH_SCORE -ge 75 ]; then
    HEALTH_STATUS="${GREEN}Good${NC}"
    HEALTH_EMOJI="🟢"
elif [ $HEALTH_SCORE -ge 60 ]; then
    HEALTH_STATUS="${YELLOW}Fair${NC}"
    HEALTH_EMOJI="🟡"
elif [ $HEALTH_SCORE -ge 40 ]; then
    HEALTH_STATUS="${YELLOW}Poor${NC}"
    HEALTH_EMOJI="🟠"
else
    HEALTH_STATUS="${RED}Critical${NC}"
    HEALTH_EMOJI="🔴"
fi

echo -e "  ${HEALTH_EMOJI} Health Score: ${HEALTH_SCORE}/100 (${HEALTH_STATUS})"
echo ""
echo -e "  ${YELLOW}⚠${NC}  Warnings: ${WARNINGS}"
echo -e "  ${RED}✗${NC}  Errors: ${ERRORS}"
echo ""

# Recommendations
if [ $ERRORS -gt 0 ] || [ $WARNINGS -gt 3 ]; then
    echo -e "${YELLOW}Recommendations:${NC}"

    if [ $ERRORS -gt 0 ]; then
        echo "  • Fix critical errors with: bash ~/troubleshoot_wsl.sh"
    fi

    if [ $WARNINGS -gt 3 ]; then
        echo "  • Review warnings above and address any issues"
    fi

    if [ "$AVAIL_MEM_MB" -lt 500 ]; then
        echo "  • Restart WSL to free memory: wsl --shutdown (from Windows)"
    fi

    if [ "$DISK_USAGE_PCT" -gt 85 ]; then
        echo "  • Clean up disk space: sudo apt-get autoclean"
    fi

    if [ "$APT_UPDATES" -gt 0 ]; then
        echo "  • Update packages: update-all"
    fi
    echo ""
fi

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Exit code based on health
if [ $HEALTH_SCORE -ge 75 ]; then
    exit 0
elif [ $HEALTH_SCORE -ge 50 ]; then
    exit 1
else
    exit 2
fi
