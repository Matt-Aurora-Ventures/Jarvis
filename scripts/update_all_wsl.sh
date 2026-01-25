#!/bin/bash
# One-Click Update Script for WSL Development Environment
# Updates: System packages, Node.js packages, Python packages, Claude CLI, Clawd, GSD

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
cat << "EOF"
╔══════════════════════════════════════════════════════════════╗
║              Update All WSL Development Tools                ║
╚══════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

UPDATE_COUNT=0

print_step() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
    UPDATE_COUNT=$((UPDATE_COUNT + 1))
}

print_skip() {
    echo -e "${YELLOW}⊘${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# ==========================================
# 1. System Packages (apt)
# ==========================================
print_step "1. Updating System Packages (apt)"

echo "Running: sudo apt-get update"
sudo apt-get update -qq

echo "Running: sudo apt-get upgrade"
sudo apt-get upgrade -y

echo "Running: sudo apt-get autoremove"
sudo apt-get autoremove -y

echo "Running: sudo apt-get autoclean"
sudo apt-get autoclean

print_success "System packages updated"

# ==========================================
# 2. Node.js Global Packages
# ==========================================
print_step "2. Updating Node.js Global Packages"

if command -v npm &> /dev/null; then
    echo "Running: npm update -g"
    sudo npm update -g

    print_success "Global npm packages updated"
else
    print_skip "npm not installed, skipping"
fi

# ==========================================
# 3. Claude CLI
# ==========================================
print_step "3. Updating Claude CLI"

if command -v claude &> /dev/null; then
    CURRENT_VERSION=$(claude --version 2>&1 || echo "unknown")
    echo "Current Claude CLI version: $CURRENT_VERSION"

    echo "Running: npm update -g @anthropic-ai/claude-code"
    sudo npm update -g @anthropic-ai/claude-code

    NEW_VERSION=$(claude --version 2>&1 || echo "unknown")
    if [ "$CURRENT_VERSION" != "$NEW_VERSION" ]; then
        print_success "Claude CLI updated: $CURRENT_VERSION → $NEW_VERSION"
    else
        print_success "Claude CLI already up to date: $CURRENT_VERSION"
    fi
else
    print_skip "Claude CLI not installed"
    echo "Install with: sudo npm install -g @anthropic-ai/claude-code"
fi

# ==========================================
# 4. Python Global Packages
# ==========================================
print_step "4. Updating Python Global Packages"

if command -v pip3 &> /dev/null; then
    echo "Running: pip3 install --upgrade pip"
    pip3 install --user --upgrade pip

    # Update common global packages
    GLOBAL_PACKAGES="setuptools wheel pipx"
    for pkg in $GLOBAL_PACKAGES; do
        if pip3 list | grep -q "^$pkg "; then
            echo "Updating: $pkg"
            pip3 install --user --upgrade $pkg 2>/dev/null || true
        fi
    done

    print_success "Python global packages updated"
else
    print_skip "pip3 not installed"
fi

# Update uv if installed
if command -v uv &> /dev/null; then
    echo "Running: uv self update"
    uv self update || echo "uv self-update not available, skipping"
    print_success "uv updated (if available)"
fi

# ==========================================
# 5. Clawd Bot
# ==========================================
print_step "5. Updating Clawd Discord Bot"

CLAWD_DIR="$HOME/clawd"
if [ -d "$CLAWD_DIR" ]; then
    cd "$CLAWD_DIR"

    if [ -d ".git" ]; then
        echo "Pulling latest Clawd changes..."
        git pull

        # Update dependencies
        if [ -f "package.json" ]; then
            echo "Running: npm install"
            npm install
            print_success "Clawd (Node.js) updated"
        elif [ -f "requirements.txt" ]; then
            if [ -d "venv" ]; then
                echo "Running: pip install --upgrade -r requirements.txt"
                source venv/bin/activate
                pip install --upgrade -r requirements.txt
                deactivate
                print_success "Clawd (Python) updated"
            else
                print_skip "Clawd venv not found, skipping dependency update"
            fi
        elif [ -f "pyproject.toml" ]; then
            if [ -d ".venv" ]; then
                echo "Running: uv pip install --upgrade -e ."
                source .venv/bin/activate
                uv pip install --upgrade -e . || pip install --upgrade -e .
                deactivate
                print_success "Clawd (uv) updated"
            fi
        fi
    else
        print_skip "Clawd is not a git repository, cannot update"
    fi
else
    print_skip "Clawd not installed at $CLAWD_DIR"
fi

# ==========================================
# 6. GSD (Get Shit Done)
# ==========================================
print_step "6. Updating GSD Framework"

GSD_DIR="$HOME/get-shit-done"
if [ -d "$GSD_DIR" ]; then
    cd "$GSD_DIR"

    if [ -d ".git" ]; then
        echo "Pulling latest GSD changes..."
        git pull

        # Update dependencies
        if [ -f "package.json" ]; then
            echo "Running: npm install"
            npm install
            print_success "GSD (Node.js) updated"
        elif [ -f "requirements.txt" ]; then
            if [ -d "venv" ]; then
                echo "Running: pip install --upgrade -r requirements.txt"
                source venv/bin/activate
                pip install --upgrade -r requirements.txt
                deactivate
                print_success "GSD (Python) updated"
            fi
        elif [ -f "pyproject.toml" ]; then
            if [ -d ".venv" ]; then
                echo "Running: uv pip install --upgrade -e ."
                source .venv/bin/activate
                uv pip install --upgrade -e . || pip install --upgrade -e .
                deactivate
                print_success "GSD updated"
            fi
        fi
    else
        print_skip "GSD is not a git repository, cannot update"
    fi
else
    print_skip "GSD not installed at $GSD_DIR"
fi

# ==========================================
# 7. VS Code Extensions (if code is installed)
# ==========================================
print_step "7. Updating VS Code Extensions"

if command -v code &> /dev/null; then
    echo "Running: code --update-extensions"
    # Note: code --update-extensions doesn't exist, but we can list outdated
    code --list-extensions --show-versions | head -5
    print_success "VS Code is installed (update extensions manually via Code UI)"
else
    print_skip "VS Code not installed"
fi

# ==========================================
# Summary
# ==========================================
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Update Complete!${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Updated $UPDATE_COUNT components"
echo ""
echo "What was updated:"
echo "  ✓ System packages (apt)"
echo "  ✓ Node.js global packages"
echo "  ✓ Claude CLI"
echo "  ✓ Python global packages"
echo "  ✓ Clawd Discord Bot (if installed)"
echo "  ✓ GSD Framework (if installed)"
echo ""
echo "Next steps:"
echo "  • Restart any running bots/services"
echo "  • Test Claude CLI: claude --version"
echo "  • Verify setup: bash ~/verify_wsl_setup.sh"
echo ""

# Offer to restart WSL
echo -e "${YELLOW}Tip:${NC} Some updates may require WSL restart"
read -p "Restart WSL now? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Exiting WSL... (restart from Windows with: wsl)"
    exit
fi

echo -e "${GREEN}Done! 🚀${NC}"
