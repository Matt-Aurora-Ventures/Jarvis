#!/bin/bash
# Start All WSL Development Services
# Launches Clawd Bot, checks health, and prepares environment

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
cat << "EOF"
╔══════════════════════════════════════════════════════════════╗
║              Starting WSL Development Services               ║
╚══════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

print_step() {
    echo ""
    echo -e "${BLUE}▶${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# ==========================================
# 1. Health Check
# ==========================================
print_step "Running health check..."

if [ -f "$HOME/health_check_wsl.sh" ]; then
    bash "$HOME/health_check_wsl.sh"
    HEALTH_RESULT=$?

    if [ $HEALTH_RESULT -eq 2 ]; then
        echo ""
        print_warning "Critical health issues detected!"
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Aborting. Fix issues first."
            exit 1
        fi
    fi
else
    print_warning "Health check script not found, skipping"
fi

# ==========================================
# 2. Check Configuration
# ==========================================
print_step "Checking configuration..."

if [ -f "$HOME/.wsl_dev_config" ]; then
    source "$HOME/.wsl_dev_config"
    print_success "Configuration loaded"

    if [ -z "$DISCORD_BOT_TOKEN" ]; then
        print_warning "DISCORD_BOT_TOKEN not set - Clawd bot may fail"
    fi

    if [ -z "$CLAUDE_API_KEY" ]; then
        print_warning "CLAUDE_API_KEY not set - Claude features may fail"
    fi
else
    print_warning "Configuration file not found: ~/.wsl_dev_config"
fi

# ==========================================
# 3. Start Clawd Bot
# ==========================================
CLAWD_DIR="$HOME/clawd"

if [ -d "$CLAWD_DIR" ]; then
    print_step "Starting Clawd Discord Bot..."

    # Check if already running
    if pgrep -f "clawd" > /dev/null || pgrep -f "main.py" > /dev/null; then
        print_warning "Clawd appears to be already running"
        read -p "Restart? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            pkill -f "clawd" 2>/dev/null || pkill -f "main.py" 2>/dev/null
            sleep 2
        else
            print_success "Keeping existing Clawd process"
            CLAWD_DIR=""  # Skip starting
        fi
    fi

    if [ ! -z "$CLAWD_DIR" ]; then
        cd "$CLAWD_DIR"

        # Detect project type and start
        if [ -f "package.json" ]; then
            # Node.js version
            print_step "Starting Clawd (Node.js)..."

            if [ -f ".env" ]; then
                print_success ".env file found"
            else
                print_warning ".env file not found (bot may fail to authenticate)"
            fi

            # Start in background
            npm start > logs/clawd.log 2>&1 &
            CLAWD_PID=$!

            sleep 3

            if ps -p $CLAWD_PID > /dev/null; then
                print_success "Clawd started (PID: $CLAWD_PID)"
                echo "  Logs: tail -f ~/clawd/logs/clawd.log"
            else
                print_warning "Clawd failed to start. Check logs: ~/clawd/logs/clawd.log"
            fi

        elif [ -f "requirements.txt" ] || [ -f "pyproject.toml" ]; then
            # Python version
            print_step "Starting Clawd (Python)..."

            if [ -f ".env" ]; then
                print_success ".env file found"
            else
                print_warning ".env file not found"
            fi

            # Create logs directory if it doesn't exist
            mkdir -p logs

            # Activate venv and start
            if [ -d "venv" ]; then
                source venv/bin/activate
            elif [ -d ".venv" ]; then
                source .venv/bin/activate
            else
                print_warning "No virtual environment found"
            fi

            # Find the main script
            MAIN_SCRIPT=""
            if [ -f "main.py" ]; then
                MAIN_SCRIPT="main.py"
            elif [ -f "bot.py" ]; then
                MAIN_SCRIPT="bot.py"
            elif [ -f "run.py" ]; then
                MAIN_SCRIPT="run.py"
            fi

            if [ ! -z "$MAIN_SCRIPT" ]; then
                python "$MAIN_SCRIPT" > logs/clawd.log 2>&1 &
                CLAWD_PID=$!

                sleep 3

                if ps -p $CLAWD_PID > /dev/null; then
                    print_success "Clawd started (PID: $CLAWD_PID)"
                    echo "  Logs: tail -f ~/clawd/logs/clawd.log"
                else
                    print_warning "Clawd failed to start. Check logs: ~/clawd/logs/clawd.log"
                fi
            else
                print_warning "Could not find main script (main.py, bot.py, or run.py)"
            fi

            deactivate 2>/dev/null || true
        fi
    fi
else
    print_warning "Clawd not installed at $CLAWD_DIR"
fi

# ==========================================
# 4. Display Status
# ==========================================
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
print_step "Service Status"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Check Claude CLI
if command -v claude &> /dev/null; then
    print_success "Claude CLI: Available"
else
    print_warning "Claude CLI: Not found"
fi

# Check Clawd
if pgrep -f "clawd" > /dev/null || pgrep -f "main.py" > /dev/null; then
    CLAWD_PID=$(pgrep -f "clawd" || pgrep -f "main.py")
    print_success "Clawd Bot: Running (PID: $CLAWD_PID)"
else
    print_warning "Clawd Bot: Not running"
fi

# Check GSD
if [ -d "$HOME/get-shit-done" ]; then
    print_success "GSD: Installed"
else
    print_warning "GSD: Not installed"
fi

# ==========================================
# 5. Helpful Commands
# ==========================================
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
print_step "Helpful Commands"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

echo "  dev-status              - Check environment status"
echo "  health-check            - Run health check"
echo "  tail -f ~/clawd/logs/clawd.log  - View Clawd logs"
echo "  pkill -f clawd          - Stop Clawd bot"
echo "  update-all              - Update all packages"
echo "  troubleshoot            - Run troubleshooting"

echo ""
echo -e "${GREEN}✓ All services started!${NC}"
echo ""
