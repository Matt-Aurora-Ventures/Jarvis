#!/bin/bash
#
# Jarvis VPS Supervisor Installation Script
# Deploys supervisor.py as a systemd service
#
# Usage:
#   scp -r deploy/ jarvis@VPS_HOST:~/
#   ssh jarvis@VPS_HOST 'sudo bash ~/deploy/install-vps.sh'
#
# Or remotely:
#   ssh root@VPS_HOST 'bash -s' < deploy/install-vps.sh

set -e

# Configuration
JARVIS_USER="jarvis"
JARVIS_HOME="/home/jarvis"
JARVIS_DIR="$JARVIS_HOME/Jarvis"
SERVICE_NAME="jarvis-supervisor"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo ""
echo "=========================================="
echo "  JARVIS VPS Supervisor Installation"
echo "=========================================="
echo ""

# Check root
if [ "$EUID" -ne 0 ]; then
    log_error "This script must be run as root"
    echo "Usage: sudo $0"
    exit 1
fi

# Check if systemd is available
if ! command -v systemctl &> /dev/null; then
    log_error "systemd not available on this system"
    echo "Use the nohup fallback method instead:"
    echo "  nohup python3 bots/supervisor.py > logs/supervisor.log 2>&1 &"
    exit 1
fi

# Step 1: Create jarvis user if missing
log_info "Step 1/7: Checking user '$JARVIS_USER'..."
if ! id "$JARVIS_USER" &>/dev/null; then
    log_info "Creating user $JARVIS_USER..."
    useradd -r -m -d "$JARVIS_HOME" -s /bin/bash "$JARVIS_USER"
    log_info "User created: $JARVIS_USER"
else
    log_info "User already exists: $JARVIS_USER"
fi

# Step 2: Create directory structure
log_info "Step 2/7: Creating directory structure..."
mkdir -p "$JARVIS_DIR/logs"
mkdir -p "$JARVIS_DIR/data"
mkdir -p "$JARVIS_DIR/.lifeos/trading"
mkdir -p "$JARVIS_DIR/run"
mkdir -p /var/log/jarvis

# Step 3: Install Python dependencies (if requirements.txt exists)
log_info "Step 3/7: Checking Python environment..."
if [ -f "$JARVIS_DIR/requirements.txt" ]; then
    log_info "Installing Python dependencies..."
    su - "$JARVIS_USER" -c "cd $JARVIS_DIR && pip3 install --user -r requirements.txt" || {
        log_warn "pip install failed - you may need to run manually"
    }
else
    log_warn "requirements.txt not found - ensure dependencies are installed"
fi

# Step 4: Install systemd service
log_info "Step 4/7: Installing systemd service..."
if [ -f "$SCRIPT_DIR/jarvis-supervisor.service" ]; then
    cp "$SCRIPT_DIR/jarvis-supervisor.service" /etc/systemd/system/
else
    # Create inline if script is running standalone
    cat > /etc/systemd/system/jarvis-supervisor.service << 'SERVICE_EOF'
[Unit]
Description=Jarvis LifeOS Supervisor - Autonomous Trading & Social AI
After=network-online.target
Wants=network-online.target

[Service]
Type=notify
NotifyAccess=all
User=jarvis
Group=jarvis
WorkingDirectory=/home/jarvis/Jarvis
EnvironmentFile=/home/jarvis/Jarvis/.env
ExecStart=/usr/bin/python3 bots/supervisor.py
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=10
StartLimitIntervalSec=600
StartLimitBurst=10
TimeoutStartSec=60
TimeoutStopSec=30
WatchdogSec=300
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
PrivateTmp=true
ReadWritePaths=/home/jarvis/Jarvis/logs /home/jarvis/Jarvis/data /home/jarvis/Jarvis/.lifeos /tmp
MemoryMax=4G
CPUQuota=90%
StandardOutput=journal
StandardError=journal
SyslogIdentifier=jarvis-supervisor

[Install]
WantedBy=multi-user.target
SERVICE_EOF
fi
chmod 644 /etc/systemd/system/jarvis-supervisor.service
log_info "Service file installed: /etc/systemd/system/jarvis-supervisor.service"

# Step 5: Install logrotate configuration
log_info "Step 5/7: Installing logrotate configuration..."
cat > /etc/logrotate.d/jarvis << 'LOGROTATE_EOF'
/home/jarvis/Jarvis/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 640 jarvis jarvis
    sharedscripts
    postrotate
        systemctl kill -s HUP jarvis-supervisor.service 2>/dev/null || true
    endscript
}

/var/log/jarvis/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 640 jarvis jarvis
}
LOGROTATE_EOF
chmod 644 /etc/logrotate.d/jarvis
log_info "Logrotate config installed: /etc/logrotate.d/jarvis"

# Step 6: Set permissions
log_info "Step 6/7: Setting permissions..."
chown -R "$JARVIS_USER:$JARVIS_USER" "$JARVIS_DIR"
chown -R "$JARVIS_USER:$JARVIS_USER" /var/log/jarvis
chmod 750 "$JARVIS_DIR"
chmod 750 "$JARVIS_DIR/logs"
chmod 750 /var/log/jarvis

# Check for .env file
if [ ! -f "$JARVIS_DIR/.env" ]; then
    log_warn ".env file not found at $JARVIS_DIR/.env"
    log_warn "Service will fail to start without environment configuration!"
    echo ""
    echo "Required environment variables:"
    echo "  TELEGRAM_BOT_TOKEN"
    echo "  TELEGRAM_ADMIN_IDS"
    echo "  JARVIS_ACCESS_TOKEN (Twitter OAuth)"
    echo "  SOLANA_RPC_URL"
    echo "  XAI_API_KEY (for Grok)"
    echo "  X_BOT_ENABLED=true"
    echo "  TREASURY_LIVE_MODE=true"
    echo ""
else
    chmod 600 "$JARVIS_DIR/.env"
    chown "$JARVIS_USER:$JARVIS_USER" "$JARVIS_DIR/.env"
    log_info ".env file found and secured"
fi

# Step 7: Enable and reload systemd
log_info "Step 7/7: Enabling service..."
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

# Verify service file
log_info "Verifying service configuration..."
if systemd-analyze verify /etc/systemd/system/jarvis-supervisor.service 2>&1 | grep -q "error"; then
    log_warn "Service file has warnings - check with: systemd-analyze verify jarvis-supervisor.service"
else
    log_info "Service file verified OK"
fi

echo ""
echo "=========================================="
echo "  Installation Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo ""
echo "  1. Ensure code is deployed to $JARVIS_DIR:"
echo "     rsync -avz --exclude '.git' ./ $JARVIS_DIR/"
echo ""
echo "  2. Create/update .env file:"
echo "     nano $JARVIS_DIR/.env"
echo ""
echo "  3. Start the service:"
echo "     sudo systemctl start $SERVICE_NAME"
echo ""
echo "  4. Check status:"
echo "     sudo systemctl status $SERVICE_NAME"
echo ""
echo "  5. View logs:"
echo "     sudo journalctl -u $SERVICE_NAME -f"
echo ""
echo "  6. Test restart behavior:"
echo "     sudo systemctl restart $SERVICE_NAME"
echo ""
echo "=========================================="
