#!/bin/bash
# JARVIS Systemd Service Setup Script
# Run as root on the deployment server

set -e

JARVIS_USER="jarvis"
JARVIS_DIR="/opt/jarvis"
SERVICE_NAME="jarvis"

echo "=========================================="
echo "JARVIS Systemd Service Setup"
echo "=========================================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo)"
    exit 1
fi

# Create jarvis user if doesn't exist
if ! id "$JARVIS_USER" &>/dev/null; then
    echo "[1/6] Creating user: $JARVIS_USER"
    useradd --system --home-dir "$JARVIS_DIR" --shell /bin/false "$JARVIS_USER"
else
    echo "[1/6] User $JARVIS_USER already exists"
fi

# Create directory structure
echo "[2/6] Setting up directories"
mkdir -p "$JARVIS_DIR"
mkdir -p "$JARVIS_DIR/logs"
mkdir -p "$JARVIS_DIR/.lifeos/trading"

# Copy service file
echo "[3/6] Installing systemd service"
cp "$(dirname "$0")/jarvis.service" /etc/systemd/system/
systemctl daemon-reload

# Set permissions
echo "[4/6] Setting permissions"
chown -R "$JARVIS_USER:$JARVIS_USER" "$JARVIS_DIR"
chmod 750 "$JARVIS_DIR"

# Check for .env file
if [ ! -f "$JARVIS_DIR/.env" ]; then
    echo ""
    echo "WARNING: $JARVIS_DIR/.env not found!"
    echo "Please create it with required environment variables:"
    echo "  - TELEGRAM_BOT_TOKEN"
    echo "  - JARVIS_ACCESS_TOKEN (Twitter OAuth)"
    echo "  - SOLANA_RPC_URL"
    echo "  - WALLET_PRIVATE_KEY"
    echo "  - GROK_API_KEY"
    echo "  - X_BOT_ENABLED=true"
    echo "  - TREASURY_LIVE_MODE=true"
    echo ""
fi

# Enable service
echo "[5/6] Enabling service for boot"
systemctl enable "$SERVICE_NAME"

echo "[6/6] Setup complete!"
echo ""
echo "=========================================="
echo "Next steps:"
echo "=========================================="
echo ""
echo "1. Deploy code to $JARVIS_DIR:"
echo "   rsync -avz --exclude '.git' ./ $JARVIS_DIR/"
echo ""
echo "2. Install Python dependencies:"
echo "   cd $JARVIS_DIR && pip3 install -r requirements.txt"
echo ""
echo "3. Create .env file with credentials:"
echo "   nano $JARVIS_DIR/.env"
echo ""
echo "4. Start the service:"
echo "   systemctl start $SERVICE_NAME"
echo ""
echo "5. Check status:"
echo "   systemctl status $SERVICE_NAME"
echo "   journalctl -u $SERVICE_NAME -f"
echo ""
echo "=========================================="
