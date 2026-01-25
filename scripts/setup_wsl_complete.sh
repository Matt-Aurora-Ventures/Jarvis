#!/bin/bash
# Complete WSL Development Environment Setup Script
# Installs: Claude CLI, Clawd Bot, Windsurf IDE, GSD (Get Shit Done)
# Usage: bash setup_wsl_complete.sh

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Progress tracking
TOTAL_STEPS=13
CURRENT_STEP=0

print_step() {
    CURRENT_STEP=$((CURRENT_STEP + 1))
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}[Step $CURRENT_STEP/$TOTAL_STEPS]${NC} $1"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
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

print_info() {
    echo -e "${MAGENTA}ℹ${NC} $1"
}

# ASCII Art Header
echo -e "${BLUE}"
cat << "EOF"
╔══════════════════════════════════════════════════════════════╗
║                WSL Development Environment Setup             ║
║              Claude CLI • Clawd Bot • Windsurf • GSD         ║
╚══════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

# Check if running in WSL
if ! grep -qi microsoft /proc/version; then
    print_error "This script must be run in WSL (Windows Subsystem for Linux)"
    exit 1
fi

print_success "Running in WSL"

# Detect distribution
if [ -f /etc/os-release ]; then
    . /etc/os-release
    print_info "Distribution: $PRETTY_NAME"
    print_info "Version: $VERSION"

    # Check if it's Ubuntu/Debian-based
    if [[ ! "$ID_LIKE" =~ "debian" ]] && [[ "$ID" != "ubuntu" ]] && [[ "$ID" != "debian" ]]; then
        print_warning "This script is optimized for Ubuntu/Debian. Your mileage may vary."
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
fi

# Check for systemd
if [ -d /run/systemd/system ]; then
    print_success "Systemd is enabled"
    SYSTEMD_AVAILABLE=true
else
    print_warning "Systemd is NOT enabled (some auto-start features won't work)"
    print_info "To enable: Add [boot]\\nsystemd=true to /etc/wsl.conf and restart WSL"
    SYSTEMD_AVAILABLE=false
fi

# Step 1: Update system
print_step "Updating system packages"
sudo apt-get update -qq
sudo apt-get upgrade -y -qq
print_success "System updated"

# Step 2: Install prerequisites
print_step "Installing prerequisites"
sudo apt-get install -y \
    curl \
    wget \
    git \
    build-essential \
    ca-certificates \
    gnupg \
    apt-transport-https \
    software-properties-common \
    unzip \
    jq \
    htop \
    nano \
    vim
print_success "Prerequisites installed"

# Step 3: Install Node.js 20.x
print_step "Installing Node.js 20.x"
if command -v node &> /dev/null; then
    NODE_VERSION=$(node -v)
    print_warning "Node.js already installed: $NODE_VERSION"
    if [[ "$NODE_VERSION" < "v20" ]]; then
        print_info "Upgrading to Node.js 20.x..."
        curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
        sudo apt-get install -y nodejs
    fi
else
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y nodejs
fi
print_success "Node.js installed: $(node -v)"
print_success "npm installed: $(npm -v)"

# Step 4: Install Claude CLI
print_step "Installing Claude CLI"
if command -v claude &> /dev/null; then
    print_warning "Claude CLI already installed"
    CLAUDE_VERSION=$(claude --version 2>&1 || echo "unknown")
    print_info "Current version: $CLAUDE_VERSION"
    read -p "Reinstall/Update? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo npm install -g @anthropic-ai/claude-code
    fi
else
    sudo npm install -g @anthropic-ai/claude-code
fi
print_success "Claude CLI ready: $(which claude)"

# Step 5: Install Python & pip
print_step "Installing Python 3 and pip"
sudo apt-get install -y python3 python3-pip python3-venv python3-dev
print_success "Python installed: $(python3 --version)"
print_success "pip installed: $(pip3 --version)"

# Step 6: Install uv (fast Python package installer)
print_step "Installing uv (Python package manager)"
if ! command -v uv &> /dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
    print_success "uv installed: $(uv --version)"
else
    print_warning "uv already installed: $(uv --version)"
fi

# Step 7: Clone and setup Clawd bot
print_step "Setting up Clawd Discord Bot"
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
    print_success "Clawd cloned to $CLAWD_DIR"
fi

# Install Clawd dependencies
cd "$CLAWD_DIR"
if [ -f "package.json" ]; then
    print_info "Installing Clawd Node.js dependencies..."
    npm install
    print_success "Clawd Node.js dependencies installed"
elif [ -f "requirements.txt" ]; then
    print_info "Installing Clawd Python dependencies..."
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    deactivate
    print_success "Clawd Python dependencies installed"
elif [ -f "pyproject.toml" ]; then
    print_info "Installing Clawd with uv..."
    uv venv
    source .venv/bin/activate
    uv pip install -e .
    deactivate
    print_success "Clawd installed via uv"
fi

# Step 8: Install GSD (Get Shit Done)
print_step "Installing GSD (Get Shit Done) framework"
GSD_DIR="$HOME/get-shit-done"
if [ -d "$GSD_DIR" ]; then
    print_warning "GSD directory already exists at $GSD_DIR"
    cd "$GSD_DIR"
    git pull
else
    git clone https://github.com/glittercowboy/get-shit-done.git "$GSD_DIR"
    print_success "GSD cloned to $GSD_DIR"
fi

cd "$GSD_DIR"

# Install GSD dependencies
if [ -f "package.json" ]; then
    print_info "Installing GSD Node.js dependencies..."
    npm install
    print_success "GSD dependencies installed"
elif [ -f "requirements.txt" ]; then
    print_info "Installing GSD Python dependencies..."
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    deactivate
    print_success "GSD dependencies installed"
elif [ -f "pyproject.toml" ]; then
    print_info "Installing GSD with uv..."
    uv venv
    source .venv/bin/activate
    uv pip install -e .
    deactivate
    print_success "GSD installed"
fi

# Make GSD CLI available globally if it has one
if [ -f "gsd" ] || [ -f "gsd.py" ]; then
    GSD_EXEC=$(find . -name "gsd*" -type f -executable | head -1)
    if [ ! -z "$GSD_EXEC" ]; then
        sudo ln -sf "$GSD_DIR/$GSD_EXEC" /usr/local/bin/gsd
        print_success "GSD CLI linked to /usr/local/bin/gsd"
    fi
fi

# Step 9: Install VS Code
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

# Step 10: Create environment configuration
print_step "Creating environment configuration"
cat > "$HOME/.wsl_dev_config" <<'EOF'
# WSL Development Environment Configuration
# Auto-generated by setup_wsl_complete.sh

# ==========================================
# Node.js Configuration
# ==========================================
export NODE_OPTIONS="--max-old-space-size=4096"

# ==========================================
# API Keys (FILL THESE IN!)
# ==========================================
export CLAUDE_API_KEY=""              # Get from: https://console.anthropic.com
export DISCORD_BOT_TOKEN=""           # Get from: https://discord.com/developers
export OPENAI_API_KEY=""              # Optional: https://platform.openai.com

# ==========================================
# Tool Paths
# ==========================================
export CLAWD_HOME="$HOME/clawd"
export GSD_HOME="$HOME/get-shit-done"

# ==========================================
# Path Additions
# ==========================================
export PATH="$HOME/.local/bin:$PATH"
export PATH="$HOME/.cargo/bin:$PATH"
export PATH="/usr/local/bin:$PATH"

# ==========================================
# Development Aliases
# ==========================================
alias clawd="cd $CLAWD_HOME"
alias gsd="cd $GSD_HOME"
alias update-dev="sudo apt-get update && sudo apt-get upgrade -y"
alias update-node="sudo npm update -g"
alias update-claude="sudo npm update -g @anthropic-ai/claude-code"

# Clawd bot management
if [ -f "$CLAWD_HOME/venv/bin/activate" ]; then
    alias activate-clawd="source $CLAWD_HOME/venv/bin/activate"
    alias start-clawd="cd $CLAWD_HOME && source venv/bin/activate && python main.py"
elif [ -f "$CLAWD_HOME/.venv/bin/activate" ]; then
    alias activate-clawd="source $CLAWD_HOME/.venv/bin/activate"
fi

# GSD management
if [ -f "$GSD_HOME/venv/bin/activate" ]; then
    alias activate-gsd="source $GSD_HOME/venv/bin/activate"
elif [ -f "$GSD_HOME/.venv/bin/activate" ]; then
    alias activate-gsd="source $GSD_HOME/.venv/bin/activate"
fi

# ==========================================
# Helpful Functions
# ==========================================
# Quick status check
dev-status() {
    echo "=== Development Environment Status ==="
    echo "Node.js: $(node -v 2>/dev/null || echo 'Not installed')"
    echo "Python: $(python3 --version 2>/dev/null || echo 'Not installed')"
    echo "Claude CLI: $(claude --version 2>/dev/null || echo 'Not installed')"
    echo "VS Code: $(code --version 2>/dev/null | head -1 || echo 'Not installed')"
    echo ""
    echo "Projects:"
    [ -d "$CLAWD_HOME" ] && echo "✓ Clawd: $CLAWD_HOME" || echo "✗ Clawd: Not found"
    [ -d "$GSD_HOME" ] && echo "✓ GSD: $GSD_HOME" || echo "✗ GSD: Not found"
}

# Update everything
update-all() {
    echo "Updating system packages..."
    sudo apt-get update && sudo apt-get upgrade -y
    echo "Updating global npm packages..."
    sudo npm update -g
    echo "Updating Python packages..."
    pip3 install --upgrade pip
    echo "Done!"
}

EOF

# Add to .bashrc if not already present
if ! grep -q "wsl_dev_config" "$HOME/.bashrc"; then
    echo "" >> "$HOME/.bashrc"
    echo "# WSL Development Environment" >> "$HOME/.bashrc"
    echo "[ -f ~/.wsl_dev_config ] && source ~/.wsl_dev_config" >> "$HOME/.bashrc"
    print_success "Configuration added to .bashrc"
else
    print_warning "Configuration already in .bashrc"
fi

# Step 11: Create systemd services (if available)
if [ "$SYSTEMD_AVAILABLE" = true ]; then
    print_step "Creating systemd service templates"

    # Clawd service
    cat > "/tmp/clawd.service" <<CLAWD_SERVICE
[Unit]
Description=Clawd Discord Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$HOME/clawd
ExecStart=$HOME/clawd/venv/bin/python main.py
Restart=on-failure
RestartSec=10
EnvironmentFile=$HOME/clawd/.env

[Install]
WantedBy=multi-user.target
CLAWD_SERVICE

    print_info "Clawd service template created at /tmp/clawd.service"
    print_info "To install: sudo mv /tmp/clawd.service /etc/systemd/system/"
    print_info "Then: sudo systemctl enable clawd && sudo systemctl start clawd"
else
    print_step "Skipping systemd services (systemd not available)"
fi

# Step 12: Create verification script
print_step "Creating verification script"
cat > "$HOME/verify_wsl_setup.sh" <<'VERIFY_EOF'
#!/bin/bash

echo -e "\033[0;34m"
cat << "EOF"
╔══════════════════════════════════════════════════════════════╗
║          WSL Development Environment Verification            ║
╚══════════════════════════════════════════════════════════════╝
EOF
echo -e "\033[0m"

check_command() {
    if command -v $1 &> /dev/null; then
        echo -e "\033[0;32m✓\033[0m $1: $(which $1)"
        if [ ! -z "$2" ]; then
            VERSION=$($1 $2 2>&1 | head -1)
            echo "  Version: $VERSION"
        fi
        return 0
    else
        echo -e "\033[0;31m✗\033[0m $1: Not found"
        return 1
    fi
}

check_dir() {
    if [ -d "$1" ]; then
        echo -e "\033[0;32m✓\033[0m $2: $1"
        return 0
    else
        echo -e "\033[0;31m✗\033[0m $2: Not found"
        return 1
    fi
}

echo "1. System Tools:"
check_command "curl" "--version"
check_command "git" "--version"
check_command "node" "--version"
check_command "npm" "--version"
check_command "python3" "--version"
check_command "pip3" "--version"
check_command "uv" "--version"

echo ""
echo "2. Development Tools:"
check_command "claude" "--version"
check_command "code" "--version"

echo ""
echo "3. Projects:"
check_dir "$HOME/clawd" "Clawd Bot"
check_dir "$HOME/get-shit-done" "GSD Framework"

echo ""
echo "4. Configuration:"
if [ -f "$HOME/.wsl_dev_config" ]; then
    echo -e "\033[0;32m✓\033[0m WSL dev config found"

    # Check if API keys are set
    source "$HOME/.wsl_dev_config"
    if [ -z "$CLAUDE_API_KEY" ]; then
        echo -e "\033[0;33m  ⚠\033[0m CLAUDE_API_KEY not set"
    else
        echo -e "\033[0;32m  ✓\033[0m CLAUDE_API_KEY set"
    fi

    if [ -z "$DISCORD_BOT_TOKEN" ]; then
        echo -e "\033[0;33m  ⚠\033[0m DISCORD_BOT_TOKEN not set"
    else
        echo -e "\033[0;32m  ✓\033[0m DISCORD_BOT_TOKEN set"
    fi
else
    echo -e "\033[0;31m✗\033[0m WSL dev config not found"
fi

echo ""
echo "5. Systemd Status:"
if [ -d /run/systemd/system ]; then
    echo -e "\033[0;32m✓\033[0m Systemd enabled"
else
    echo -e "\033[0;33m⚠\033[0m Systemd not enabled"
fi

echo ""
echo -e "\033[0;34m══════════════════════════════════════════════════════════════\033[0m"
echo "Verification complete!"
echo ""
echo "Next steps:"
echo "1. Edit ~/.wsl_dev_config and add your API keys"
echo "2. Run: source ~/.bashrc"
echo "3. Test Claude CLI: claude --version"
echo "4. Configure Clawd: cd ~/clawd && nano .env"
echo "5. Check out GSD: cd ~/get-shit-done"
VERIFY_EOF

chmod +x "$HOME/verify_wsl_setup.sh"
print_success "Verification script created: ~/verify_wsl_setup.sh"

# Step 13: Create quick start guide
print_step "Creating quick start guide"
cat > "$HOME/WSL_QUICK_START.md" <<'QUICKSTART_EOF'
# WSL Development Environment - Quick Start

## What's Installed

✓ **Claude CLI** - Anthropic's official CLI tool
✓ **Clawd Bot** - Discord bot framework with Claude AI
✓ **GSD** - Get Shit Done productivity framework
✓ **VS Code** - Code editor with WSL support
✓ **Node.js 20** - JavaScript runtime
✓ **Python 3** - Python with pip and uv
✓ **Dev Tools** - git, curl, wget, build tools

## First Steps

### 1. Configure API Keys

```bash
nano ~/.wsl_dev_config
```

Add your keys:
- `CLAUDE_API_KEY` - Get from https://console.anthropic.com
- `DISCORD_BOT_TOKEN` - Get from https://discord.com/developers

### 2. Reload Environment

```bash
source ~/.bashrc
```

### 3. Verify Installation

```bash
bash ~/verify_wsl_setup.sh
```

## Quick Commands

### Claude CLI
```bash
claude --version          # Check version
claude auth login         # Authenticate
claude "Hello world"      # Run a query
```

### Clawd Discord Bot
```bash
clawd                     # Go to Clawd directory
activate-clawd            # Activate Python env
nano .env                 # Configure bot
python main.py            # Start bot
```

### GSD (Get Shit Done)
```bash
gsd                       # Go to GSD directory
activate-gsd              # Activate environment
# Follow GSD documentation for usage
```

### General
```bash
dev-status                # Check environment status
update-all                # Update everything
update-dev                # Update system packages
update-claude             # Update Claude CLI
```

## File Locations

- Clawd: `~/clawd`
- GSD: `~/get-shit-done`
- Config: `~/.wsl_dev_config`
- Logs: `~/clawd/logs/`

## Troubleshooting

### Claude CLI not found
```bash
sudo npm install -g @anthropic-ai/claude-code
source ~/.bashrc
```

### Python virtual env issues
```bash
cd ~/clawd  # or ~/get-shit-done
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Discord bot won't start
1. Check `DISCORD_BOT_TOKEN` in `~/.wsl_dev_config` or `~/clawd/.env`
2. Verify bot token is valid at https://discord.com/developers
3. Check bot has correct permissions in Discord server

## Resources

- Claude CLI: https://github.com/anthropics/claude-code
- Clawd: https://clawd.bot
- GSD: https://github.com/glittercowboy/get-shit-done
- Anthropic Console: https://console.anthropic.com
- Discord Developers: https://discord.com/developers

## Getting Help

Run any of these:
```bash
claude --help
dev-status
bash ~/verify_wsl_setup.sh
```
QUICKSTART_EOF

print_success "Quick start guide created: ~/WSL_QUICK_START.md"

# Final summary
echo ""
echo -e "${GREEN}"
cat << "EOF"
╔══════════════════════════════════════════════════════════════╗
║                     🎉 Setup Complete! 🎉                    ║
╚══════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

echo -e "${BLUE}Installed Tools:${NC}"
echo "  ✓ Claude CLI"
echo "  ✓ Clawd Discord Bot"
echo "  ✓ GSD (Get Shit Done)"
echo "  ✓ VS Code"
echo "  ✓ Node.js & Python"
echo ""

echo -e "${YELLOW}Next Steps:${NC}"
echo "1. ${MAGENTA}Configure API keys:${NC}"
echo "   nano ~/.wsl_dev_config"
echo ""
echo "2. ${MAGENTA}Reload environment:${NC}"
echo "   source ~/.bashrc"
echo ""
echo "3. ${MAGENTA}Verify installation:${NC}"
echo "   bash ~/verify_wsl_setup.sh"
echo ""
echo "4. ${MAGENTA}Read quick start guide:${NC}"
echo "   cat ~/WSL_QUICK_START.md"
echo ""

echo -e "${BLUE}Useful Commands:${NC}"
echo "  dev-status     - Check environment status"
echo "  update-all     - Update everything"
echo "  clawd          - Go to Clawd directory"
echo "  gsd            - Go to GSD directory"
echo ""

echo -e "${GREEN}Happy coding! 🚀${NC}"
echo ""
