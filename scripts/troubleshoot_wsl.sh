#!/bin/bash
# WSL Development Environment Troubleshooting Script
# Diagnoses common issues with Claude CLI, Clawd, GSD, and WSL setup

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
NC='\033[0m'

echo -e "${BLUE}"
cat << "EOF"
╔══════════════════════════════════════════════════════════════╗
║                WSL Troubleshooting & Diagnostics             ║
╚══════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

ISSUE_COUNT=0

check_pass() {
    echo -e "${GREEN}✓${NC} $1"
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
    ISSUE_COUNT=$((ISSUE_COUNT + 1))
}

check_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

check_info() {
    echo -e "${MAGENTA}ℹ${NC} $1"
}

print_section() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_fix() {
    echo -e "${YELLOW}Fix:${NC} $1"
}

# ==========================================
# 1. System & WSL Check
# ==========================================
print_section "1. System & WSL Status"

if grep -qi microsoft /proc/version; then
    check_pass "Running in WSL"

    if grep -qi "WSL2" /proc/version; then
        check_pass "WSL version: 2"
    else
        check_warn "WSL version: 1 (WSL2 recommended for better performance)"
        print_fix "Upgrade to WSL2: wsl --set-version <distro> 2"
    fi
else
    check_fail "Not running in WSL!"
    exit 1
fi

if [ -d /run/systemd/system ]; then
    check_pass "Systemd is enabled"
else
    check_warn "Systemd is NOT enabled"
    print_fix "Add to /etc/wsl.conf: [boot]\\nsystemd=true, then restart WSL"
fi

# ==========================================
# 2. Distribution Info
# ==========================================
print_section "2. Distribution Information"

if [ -f /etc/os-release ]; then
    . /etc/os-release
    check_pass "Distribution: $PRETTY_NAME"
    check_info "Version: $VERSION"
    check_info "Codename: $VERSION_CODENAME"
else
    check_fail "Cannot detect distribution"
fi

# ==========================================
# 3. Network Connectivity
# ==========================================
print_section "3. Network Connectivity"

if ping -c 1 8.8.8.8 &> /dev/null; then
    check_pass "Internet connectivity (IPv4)"
else
    check_fail "No internet connectivity"
    print_fix "Check Windows network, try: wsl --shutdown and restart"
fi

if ping -c 1 google.com &> /dev/null; then
    check_pass "DNS resolution working"
else
    check_fail "DNS resolution failed"
    print_fix "Check /etc/resolv.conf, try: echo 'nameserver 8.8.8.8' | sudo tee /etc/resolv.conf"
fi

# Check if can reach key services
if curl -s --max-time 5 https://api.anthropic.com &> /dev/null; then
    check_pass "Can reach Anthropic API"
else
    check_warn "Cannot reach Anthropic API (might be firewall/proxy)"
fi

if curl -s --max-time 5 https://discord.com &> /dev/null; then
    check_pass "Can reach Discord"
else
    check_warn "Cannot reach Discord (might be firewall/proxy)"
fi

# ==========================================
# 4. Node.js & npm
# ==========================================
print_section "4. Node.js & npm"

if command -v node &> /dev/null; then
    NODE_VERSION=$(node -v)
    check_pass "Node.js installed: $NODE_VERSION"

    if [[ "$NODE_VERSION" < "v18" ]]; then
        check_warn "Node.js version is old (< v18)"
        print_fix "Update: curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt-get install -y nodejs"
    fi
else
    check_fail "Node.js not installed"
    print_fix "Install: curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt-get install -y nodejs"
fi

if command -v npm &> /dev/null; then
    NPM_VERSION=$(npm -v)
    check_pass "npm installed: $NPM_VERSION"

    # Check npm permissions
    NPM_PREFIX=$(npm config get prefix)
    check_info "npm prefix: $NPM_PREFIX"

    if [ "$NPM_PREFIX" = "/usr" ] || [ "$NPM_PREFIX" = "/usr/local" ]; then
        check_warn "npm using system prefix (might need sudo for global installs)"
        print_fix "Set user prefix: mkdir -p ~/.npm-global && npm config set prefix ~/.npm-global && echo 'export PATH=~/.npm-global/bin:\$PATH' >> ~/.bashrc"
    fi
else
    check_fail "npm not installed"
    print_fix "Install with Node.js"
fi

# ==========================================
# 5. Python & pip
# ==========================================
print_section "5. Python & pip"

if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    check_pass "Python installed: $PYTHON_VERSION"
else
    check_fail "Python3 not installed"
    print_fix "Install: sudo apt-get install -y python3 python3-pip python3-venv"
fi

if command -v pip3 &> /dev/null; then
    PIP_VERSION=$(pip3 --version)
    check_pass "pip installed: $PIP_VERSION"
else
    check_fail "pip3 not installed"
    print_fix "Install: sudo apt-get install -y python3-pip"
fi

if command -v uv &> /dev/null; then
    UV_VERSION=$(uv --version)
    check_pass "uv installed: $UV_VERSION"
else
    check_warn "uv not installed (fast Python package manager)"
    print_fix "Install: curl -LsSf https://astral.sh/uv/install.sh | sh"
fi

# ==========================================
# 6. Claude CLI
# ==========================================
print_section "6. Claude CLI"

if command -v claude &> /dev/null; then
    CLAUDE_VERSION=$(claude --version 2>&1 || echo "unknown")
    check_pass "Claude CLI installed"
    check_info "Version: $CLAUDE_VERSION"
    check_info "Location: $(which claude)"

    # Check if authenticated
    if [ -f "$HOME/.config/claude/config.json" ]; then
        check_pass "Claude config exists"
    else
        check_warn "Claude config not found (not authenticated?)"
        print_fix "Authenticate: claude auth login"
    fi

    # Test Claude CLI
    if claude --version &> /dev/null; then
        check_pass "Claude CLI is functional"
    else
        check_fail "Claude CLI not working properly"
        print_fix "Reinstall: sudo npm install -g @anthropic-ai/claude-code"
    fi
else
    check_fail "Claude CLI not installed"
    print_fix "Install: sudo npm install -g @anthropic-ai/claude-code"
fi

# Check environment variables
if [ ! -z "$CLAUDE_API_KEY" ]; then
    check_pass "CLAUDE_API_KEY is set"
    if [[ "$CLAUDE_API_KEY" =~ ^sk-ant- ]]; then
        check_pass "CLAUDE_API_KEY format looks correct"
    else
        check_warn "CLAUDE_API_KEY doesn't match expected format (should start with sk-ant-)"
    fi
else
    check_warn "CLAUDE_API_KEY not set in environment"
    check_info "Set in ~/.wsl_dev_config or ~/.bashrc"
fi

# ==========================================
# 7. Clawd Bot
# ==========================================
print_section "7. Clawd Discord Bot"

CLAWD_DIR="$HOME/clawd"
if [ -d "$CLAWD_DIR" ]; then
    check_pass "Clawd directory exists: $CLAWD_DIR"

    cd "$CLAWD_DIR"

    # Check if git repo
    if [ -d ".git" ]; then
        check_pass "Clawd is a git repository"
        GIT_STATUS=$(git status --porcelain 2>/dev/null | wc -l)
        if [ "$GIT_STATUS" -gt 0 ]; then
            check_info "Clawd has $GIT_STATUS uncommitted changes"
        fi
    else
        check_warn "Clawd is not a git repository (can't update)"
    fi

    # Check dependencies
    if [ -f "package.json" ]; then
        check_pass "Node.js project detected"
        if [ -d "node_modules" ]; then
            check_pass "node_modules exists"
        else
            check_fail "node_modules missing"
            print_fix "Install: cd ~/clawd && npm install"
        fi
    elif [ -f "requirements.txt" ]; then
        check_pass "Python project detected"
        if [ -d "venv" ]; then
            check_pass "Python venv exists"
        else
            check_fail "Python venv missing"
            print_fix "Create: cd ~/clawd && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
        fi
    elif [ -f "pyproject.toml" ]; then
        check_pass "Python project (pyproject.toml)"
        if [ -d ".venv" ]; then
            check_pass "Python .venv exists"
        else
            check_warn ".venv missing"
            print_fix "Create: cd ~/clawd && uv venv && source .venv/bin/activate && uv pip install -e ."
        fi
    fi

    # Check configuration
    if [ -f ".env" ]; then
        check_pass "Clawd .env file exists"

        if grep -q "DISCORD_BOT_TOKEN=.\+" ".env"; then
            check_pass "DISCORD_BOT_TOKEN is set in .env"
        else
            check_warn "DISCORD_BOT_TOKEN not set in .env"
        fi

        if grep -q "ANTHROPIC_API_KEY=.\+" ".env"; then
            check_pass "ANTHROPIC_API_KEY is set in .env"
        else
            check_warn "ANTHROPIC_API_KEY not set in .env"
        fi
    else
        check_warn "Clawd .env file not found"
        print_fix "Create from template: cp .env.example .env (if available)"
    fi

    # Check logs directory
    if [ -d "logs" ]; then
        check_pass "Logs directory exists"
        LOG_COUNT=$(find logs -type f 2>/dev/null | wc -l)
        check_info "Found $LOG_COUNT log files"
    else
        check_info "Logs directory doesn't exist (will be created on first run)"
    fi

else
    check_fail "Clawd directory not found at $CLAWD_DIR"
    print_fix "Install: git clone https://github.com/chand1012/clawd.git ~/clawd"
fi

# Check Discord bot token from environment
if [ ! -z "$DISCORD_BOT_TOKEN" ]; then
    check_pass "DISCORD_BOT_TOKEN is set in environment"
else
    check_warn "DISCORD_BOT_TOKEN not in environment (check .env or ~/.wsl_dev_config)"
fi

# ==========================================
# 8. GSD (Get Shit Done)
# ==========================================
print_section "8. GSD (Get Shit Done)"

GSD_DIR="$HOME/get-shit-done"
if [ -d "$GSD_DIR" ]; then
    check_pass "GSD directory exists: $GSD_DIR"

    cd "$GSD_DIR"

    if [ -d ".git" ]; then
        check_pass "GSD is a git repository"
    fi

    # Check project type
    if [ -f "package.json" ]; then
        check_pass "GSD Node.js project"
        if [ -d "node_modules" ]; then
            check_pass "node_modules exists"
        else
            check_warn "node_modules missing"
            print_fix "Install: cd ~/get-shit-done && npm install"
        fi
    elif [ -f "requirements.txt" ] || [ -f "pyproject.toml" ]; then
        check_pass "GSD Python project"
        if [ -d "venv" ] || [ -d ".venv" ]; then
            check_pass "Virtual environment exists"
        else
            check_warn "Virtual environment missing"
            print_fix "Create: cd ~/get-shit-done && python3 -m venv venv"
        fi
    fi

    # Check if GSD CLI is available
    if command -v gsd &> /dev/null; then
        check_pass "GSD CLI is available globally"
        check_info "Location: $(which gsd)"
    else
        check_info "GSD CLI not in PATH (might need to run from directory)"
    fi
else
    check_fail "GSD directory not found at $GSD_DIR"
    print_fix "Install: git clone https://github.com/glittercowboy/get-shit-done.git ~/get-shit-done"
fi

# ==========================================
# 9. Configuration Files
# ==========================================
print_section "9. Configuration Files"

if [ -f "$HOME/.wsl_dev_config" ]; then
    check_pass "~/.wsl_dev_config exists"
else
    check_warn "~/.wsl_dev_config not found"
    print_fix "Run setup script or create manually"
fi

if grep -q "wsl_dev_config" "$HOME/.bashrc"; then
    check_pass "~/.wsl_dev_config is loaded in .bashrc"
else
    check_warn "~/.wsl_dev_config not loaded in .bashrc"
    print_fix "Add: echo '[ -f ~/.wsl_dev_config ] && source ~/.wsl_dev_config' >> ~/.bashrc"
fi

# ==========================================
# 10. Resources & Performance
# ==========================================
print_section "10. Resources & Performance"

TOTAL_MEM=$(free -h | awk '/^Mem:/ {print $2}')
AVAIL_MEM=$(free -h | awk '/^Mem:/ {print $7}')
USED_MEM=$(free -h | awk '/^Mem:/ {print $3}')

check_info "Total Memory: $TOTAL_MEM"
check_info "Used Memory: $USED_MEM"
check_info "Available Memory: $AVAIL_MEM"

# Check if low on memory
AVAIL_MEM_MB=$(free -m | awk '/^Mem:/ {print $7}')
if [ "$AVAIL_MEM_MB" -lt 500 ]; then
    check_warn "Low available memory (< 500MB)"
    print_fix "Consider increasing WSL memory in .wslconfig or closing other apps"
fi

check_info "CPU Cores: $(nproc)"

DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}')
check_info "Disk Usage: $DISK_USAGE"

# Check if running low on disk
DISK_USAGE_PCT=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$DISK_USAGE_PCT" -gt 90 ]; then
    check_warn "Disk usage is high (> 90%)"
    print_fix "Clean up: sudo apt-get autoclean, docker system prune (if using Docker)"
fi

# ==========================================
# 11. Common Issues Quick Check
# ==========================================
print_section "11. Common Issues Quick Check"

# Check PATH
if echo $PATH | grep -q ".local/bin"; then
    check_pass "~/.local/bin is in PATH"
else
    check_warn "~/.local/bin not in PATH"
    print_fix "Add to .bashrc: export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

# Check for common permission issues
NPM_GLOBAL=$(npm root -g 2>/dev/null)
if [ ! -z "$NPM_GLOBAL" ]; then
    if [ -w "$NPM_GLOBAL" ]; then
        check_pass "npm global directory is writable"
    else
        check_warn "npm global directory is not writable"
        print_fix "Fix permissions or use user-local npm prefix"
    fi
fi

# Check for proxy issues (common in corporate networks)
if [ ! -z "$HTTP_PROXY" ] || [ ! -z "$HTTPS_PROXY" ]; then
    check_info "Proxy detected: HTTP_PROXY=$HTTP_PROXY, HTTPS_PROXY=$HTTPS_PROXY"
    check_warn "Proxy might cause issues with some tools"
fi

# ==========================================
# Summary
# ==========================================
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Summary${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

if [ "$ISSUE_COUNT" -eq 0 ]; then
    echo -e "${GREEN}✓ No critical issues found!${NC}"
    echo "Your WSL development environment looks good."
else
    echo -e "${YELLOW}⚠ Found $ISSUE_COUNT potential issues${NC}"
    echo "Review the output above and apply suggested fixes."
fi

echo ""
echo "For more help:"
echo "  • View quick start: cat ~/WSL_QUICK_START.md"
echo "  • Run verification: bash ~/verify_wsl_setup.sh"
echo "  • Check environment: dev-status"
echo ""
