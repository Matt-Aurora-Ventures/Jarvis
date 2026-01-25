#!/bin/bash
# WSL Development Environment Setup Script
# Installs: Claude CLI, Clawd Bot, Windsurf IDE
# Usage: bash setup_wsl_dev_environment.sh

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Progress tracking
TOTAL_STEPS=10
CURRENT_STEP=0

print_step() {
    CURRENT_STEP=$((CURRENT_STEP + 1))
    echo -e "\n${BLUE}[Step $CURRENT_STEP/$TOTAL_STEPS]${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Check if running in WSL
if ! grep -qi microsoft /proc/version; then
    print_error "This script must be run in WSL (Windows Subsystem for Linux)"
    exit 1
fi

print_success "Running in WSL"

# Step 1: Update system
print_step "Updating system packages"
sudo apt-get update -qq
sudo apt-get upgrade -y -qq
print_success "System updated"

# Step 2: Install prerequisites
print_step "Installing prerequisites (curl, wget, git, build-essential)"
sudo apt-get install -y curl wget git build-essential ca-certificates gnupg \
    apt-transport-https software-properties-common
print_success "Prerequisites installed"

# Step 3: Install Node.js (required for Claude CLI and Clawd)
print_step "Installing Node.js 20.x"
if command -v node &> /dev/null; then
    NODE_VERSION=$(node -v)
    print_warning "Node.js already installed: $NODE_VERSION"
else
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y nodejs
    print_success "Node.js installed: $(node -v)"
fi

# Step 4: Install Claude CLI
print_step "Installing Claude CLI (@anthropic-ai/claude-code)"
if command -v claude &> /dev/null; then
    print_warning "Claude CLI already installed: $(claude --version 2>/dev/null || echo 'version unknown')"
    read -p "Reinstall? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo npm install -g @anthropic-ai/claude-code
    fi
else
    sudo npm install -g @anthropic-ai/claude-code
    print_success "Claude CLI installed: $(claude --version 2>/dev/null || echo 'installed')"
fi

# Step 5: Install Python (for Clawd bot if it's Python-based)
print_step "Installing Python 3 and pip"
sudo apt-get install -y python3 python3-pip python3-venv
print_success "Python installed: $(python3 --version)"

# Step 6: Clone and setup Clawd bot
print_step "Setting up Clawd bot"
CLAWD_DIR="$HOME/clawd"
if [ -d "$CLAWD_DIR" ]; then
    print_warning "Clawd directory already exists at $CLAWD_DIR"
    read -p "Re-clone? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$CLAWD_DIR"
        git clone https://github.com/chand1012/clawd.git "$CLAWD_DIR"
    fi
else
    git clone https://github.com/chand1012/clawd.git "$CLAWD_DIR"
fi

cd "$CLAWD_DIR"

# Detect project type and install dependencies
if [ -f "package.json" ]; then
    print_step "Installing Clawd Node.js dependencies"
    npm install
    print_success "Clawd Node.js dependencies installed"
elif [ -f "requirements.txt" ]; then
    print_step "Installing Clawd Python dependencies"
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    deactivate
    print_success "Clawd Python dependencies installed"
elif [ -f "pyproject.toml" ]; then
    print_step "Installing Clawd Python dependencies (Poetry/UV)"
    pip install --user pipx
    python3 -m pipx ensurepath
    pipx install poetry
    poetry install
    print_success "Clawd dependencies installed via Poetry"
else
    print_warning "No package.json or requirements.txt found in Clawd repo"
fi

# Step 7: Install VS Code (base for Windsurf)
print_step "Installing Visual Studio Code"
if command -v code &> /dev/null; then
    print_warning "VS Code already installed"
else
    wget -qO- https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > /tmp/packages.microsoft.gpg
    sudo install -D -o root -g root -m 644 /tmp/packages.microsoft.gpg /etc/apt/keyrings/packages.microsoft.gpg
    sudo sh -c 'echo "deb [arch=amd64,arm64,armhf signed-by=/etc/apt/keyrings/packages.microsoft.gpg] https://packages.microsoft.com/repos/code stable main" > /etc/apt/sources.list.d/vscode.list'
    rm /tmp/packages.microsoft.gpg
    sudo apt-get update
    sudo apt-get install -y code
    print_success "VS Code installed"
fi

# Step 8: Install Windsurf
print_step "Installing Windsurf IDE"
# Check if Windsurf has a specific installer or is a VS Code extension
WINDSURF_URL="https://windsurf.com"  # Placeholder - update with actual URL

print_warning "Windsurf installation method needs to be confirmed"
echo "Please visit https://windsurf.com for installation instructions"
echo "If Windsurf is a VS Code extension, install it via: code --install-extension <extension-id>"

# Step 9: Create environment configuration
print_step "Creating environment configuration"
cat > "$HOME/.wsl_dev_config" <<'EOF'
# WSL Development Environment Configuration
# Added by setup_wsl_dev_environment.sh

# Node.js
export NODE_OPTIONS="--max-old-space-size=4096"

# Claude CLI
export CLAUDE_API_KEY=""  # Add your API key here

# Clawd Bot
export CLAWD_HOME="$HOME/clawd"
export DISCORD_BOT_TOKEN=""  # Add your Discord bot token here

# Path additions
export PATH="$HOME/.local/bin:$PATH"

# Aliases
alias clawd="cd $CLAWD_HOME"
alias claude-version="claude --version"
alias update-dev="sudo apt-get update && sudo apt-get upgrade -y"

# Load Clawd environment if it exists
if [ -f "$CLAWD_HOME/venv/bin/activate" ]; then
    alias activate-clawd="source $CLAWD_HOME/venv/bin/activate"
fi
EOF

# Add to .bashrc if not already present
if ! grep -q "wsl_dev_config" "$HOME/.bashrc"; then
    echo "" >> "$HOME/.bashrc"
    echo "# WSL Dev Environment" >> "$HOME/.bashrc"
    echo "[ -f ~/.wsl_dev_config ] && source ~/.wsl_dev_config" >> "$HOME/.bashrc"
    print_success "Configuration added to .bashrc"
else
    print_warning "Configuration already in .bashrc"
fi

# Step 10: Create verification script
print_step "Creating verification script"
cat > "$HOME/verify_wsl_setup.sh" <<'VERIFY_EOF'
#!/bin/bash
echo "=== WSL Development Environment Verification ==="
echo ""

check_command() {
    if command -v $1 &> /dev/null; then
        echo "✓ $1: $(which $1)"
        if [ ! -z "$2" ]; then
            echo "  Version: $($1 $2 2>&1 | head -1)"
        fi
    else
        echo "✗ $1: Not found"
    fi
}

echo "1. System Tools:"
check_command "curl" "--version"
check_command "git" "--version"
check_command "node" "--version"
check_command "npm" "--version"
check_command "python3" "--version"
check_command "pip3" "--version"

echo ""
echo "2. Development Tools:"
check_command "claude" "--version"
check_command "code" "--version"

echo ""
echo "3. Clawd Bot:"
if [ -d "$HOME/clawd" ]; then
    echo "✓ Clawd directory: $HOME/clawd"
    if [ -f "$HOME/clawd/venv/bin/activate" ]; then
        echo "  ✓ Python virtual environment found"
    fi
    if [ -f "$HOME/clawd/package.json" ]; then
        echo "  ✓ Node.js project found"
    fi
else
    echo "✗ Clawd directory not found"
fi

echo ""
echo "4. Configuration:"
if [ -f "$HOME/.wsl_dev_config" ]; then
    echo "✓ WSL dev config: $HOME/.wsl_dev_config"
else
    echo "✗ WSL dev config not found"
fi

echo ""
echo "=== Verification Complete ==="
VERIFY_EOF

chmod +x "$HOME/verify_wsl_setup.sh"
print_success "Verification script created at ~/verify_wsl_setup.sh"

# Final summary
echo ""
echo "========================================="
echo -e "${GREEN}Setup Complete!${NC}"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Add your API keys to ~/.wsl_dev_config:"
echo "   - CLAUDE_API_KEY (get from https://console.anthropic.com)"
echo "   - DISCORD_BOT_TOKEN (for Clawd bot)"
echo ""
echo "2. Reload your shell configuration:"
echo "   source ~/.bashrc"
echo ""
echo "3. Run verification:"
echo "   bash ~/verify_wsl_setup.sh"
echo ""
echo "4. Configure Clawd bot:"
echo "   cd ~/clawd"
echo "   # Follow setup instructions in README"
echo ""
echo "5. For Windsurf IDE:"
echo "   Visit https://windsurf.com for installation"
echo ""
echo "Useful aliases added:"
echo "  - clawd          (cd to Clawd directory)"
echo "  - activate-clawd (activate Clawd Python venv)"
echo "  - update-dev     (update system packages)"
echo ""
