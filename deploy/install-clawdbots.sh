#!/bin/bash
# Install ClawdBots systemd services on VPS
# Run on VPS: bash install-clawdbots.sh

set -e

echo "====================================="
echo "ClawdBots Systemd Installation"
echo "====================================="

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "ERROR: This script must be run as root"
   echo "Usage: sudo bash install-clawdbots.sh"
   exit 1
fi

# Verify we're in the clawdbots directory
if [[ ! -d "/root/clawdbots/bots" ]]; then
    echo "ERROR: /root/clawdbots/bots not found"
    echo "Please ensure the clawdbots repository is at /root/clawdbots"
    exit 1
fi

# Verify tokens.env exists
if [[ ! -f "/root/clawdbots/tokens.env" ]]; then
    echo "WARNING: /root/clawdbots/tokens.env not found"
    echo "Please create tokens.env with bot tokens before starting services"
fi

# Verify Python dependencies
echo "Checking Python dependencies..."
python3 -c "import telebot" 2>/dev/null || {
    echo "Installing pyTelegramBotAPI..."
    pip3 install pyTelegramBotAPI
}

# Copy service files to systemd directory
echo ""
echo "Installing systemd service files..."

SERVICE_FILES=(
    "clawdjarvis.service"
    "clawdfriday.service"
    "clawdmatt.service"
    "clawdbots.target"
)

for file in "${SERVICE_FILES[@]}"; do
    if [[ -f "/root/clawdbots/deploy/$file" ]]; then
        echo "  - Installing $file"
        cp "/root/clawdbots/deploy/$file" /etc/systemd/system/
        chmod 644 "/etc/systemd/system/$file"
    else
        echo "  - WARNING: $file not found in /root/clawdbots/deploy/"
    fi
done

# Reload systemd daemon
echo ""
echo "Reloading systemd daemon..."
systemctl daemon-reload

# Enable services
echo ""
echo "Enabling services to start on boot..."
systemctl enable clawdjarvis.service
systemctl enable clawdfriday.service
systemctl enable clawdmatt.service
systemctl enable clawdbots.target

# Show status
echo ""
echo "====================================="
echo "Installation Complete!"
echo "====================================="
echo ""
echo "Service Management Commands:"
echo ""
echo "Start all bots:"
echo "  systemctl start clawdbots.target"
echo ""
echo "Stop all bots:"
echo "  systemctl stop clawdbots.target"
echo ""
echo "Check status:"
echo "  systemctl status clawdbots.target"
echo "  systemctl status clawdjarvis"
echo "  systemctl status clawdfriday"
echo "  systemctl status clawdmatt"
echo ""
echo "View logs:"
echo "  journalctl -u clawdjarvis -f"
echo "  journalctl -u clawdfriday -f"
echo "  journalctl -u clawdmatt -f"
echo ""
echo "Restart individual bot:"
echo "  systemctl restart clawdjarvis"
echo ""
echo "====================================="
echo ""
echo "Ready to start? Run:"
echo "  systemctl start clawdbots.target"
echo ""
