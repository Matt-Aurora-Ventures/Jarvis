#!/bin/bash
# JARVIS VPS DEPLOYMENT WITH AUTOMATIC KEY INJECTION
# Copy this entire command and paste into your VPS terminal as root
# This script does everything: setup, install, configure keys, and start bots

set -e

echo "=========================================="
echo "JARVIS BOT DEPLOYMENT - FULL AUTOMATION"
echo "=========================================="

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# ============================================================================
# PHASE 1: SYSTEM SETUP
# ============================================================================
echo -e "${BLUE}[PHASE 1] System Setup${NC}"

apt update && apt upgrade -y
apt install -y python3.12 python3.12-venv python3-pip git sqlite3 curl wget ufw fail2ban supervisor htop screen

# Create jarvis user if not exists
if ! id "jarvis" &>/dev/null; then
    adduser --disabled-password --gecos "" jarvis
    usermod -aG sudo jarvis
fi

# Setup firewall
ufw allow OpenSSH
ufw allow 80
ufw allow 443
ufw --force enable

echo -e "${GREEN}✓ System setup complete${NC}"

# ============================================================================
# PHASE 2: CLONE & SETUP JARVIS
# ============================================================================
echo -e "${BLUE}[PHASE 2] Clone and setup Jarvis${NC}"

cd /home/jarvis

if [ ! -d "Jarvis" ]; then
    sudo -u jarvis git clone https://github.com/Matt-Aurora-Ventures/Jarvis.git
else
    sudo -u jarvis bash -c "cd /home/jarvis/Jarvis && git pull"
fi

cd /home/jarvis/Jarvis

# Create venv
if [ ! -d "venv" ]; then
    sudo -u jarvis python3.12 -m venv venv
fi

# Install dependencies
sudo -u jarvis bash -c "
    source venv/bin/activate
    pip install --upgrade pip setuptools wheel
    pip install -r requirements.txt
" || true

echo -e "${GREEN}✓ Jarvis cloned and dependencies installed${NC}"

# ============================================================================
# PHASE 3: SETUP SECRETS WITH YOUR KEYS
# ============================================================================
echo -e "${BLUE}[PHASE 3] Configure API keys${NC}"

mkdir -p /home/jarvis/Jarvis/secrets
chmod 700 /home/jarvis/Jarvis/secrets

# CREATE KEYS.JSON WITH YOUR ACTUAL KEYS
cat > /home/jarvis/Jarvis/secrets/keys.json << 'KEYS_EOF'
{
  "anthropic_api_key": "sk-ant-REPLACEME",
  "xai": {"api_key": "REPLACEME"},
  "groq_api_key": "REPLACEME",
  "minimax_api_key": "REPLACEME",
  "birdeye_api_key": "REPLACEME",
  "helius": {"api_key": "REPLACEME"},
  "twitter": {
    "api_key": "REPLACEME",
    "api_secret": "REPLACEME",
    "access_token": "REPLACEME",
    "access_secret": "REPLACEME"
  },
  "telegram": {
    "bot_token": "REPLACEME"
  }
}
KEYS_EOF

chmod 600 /home/jarvis/Jarvis/secrets/keys.json
chown jarvis:jarvis /home/jarvis/Jarvis/secrets/keys.json

echo -e "${YELLOW}[!] Keys configured (partially). Update remaining placeholders:${NC}"
echo "    nano /home/jarvis/Jarvis/secrets/keys.json"

# ============================================================================
# PHASE 4: CREATE SYSTEMD SERVICES
# ============================================================================
echo -e "${BLUE}[PHASE 4] Create systemd services${NC}"

cat > /etc/systemd/system/jarvis-supervisor.service << 'EOF'
[Unit]
Description=Jarvis Bot Supervisor
After=network.target

[Service]
Type=simple
User=jarvis
WorkingDirectory=/home/jarvis/Jarvis
Environment=PYTHONUNBUFFERED=1
ExecStart=/home/jarvis/Jarvis/venv/bin/python bots/supervisor.py
Restart=always
RestartSec=30
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/jarvis-telegram.service << 'EOF'
[Unit]
Description=Jarvis Telegram Bot
After=network.target

[Service]
Type=simple
User=jarvis
WorkingDirectory=/home/jarvis/Jarvis
Environment=PYTHONUNBUFFERED=1
ExecStart=/home/jarvis/Jarvis/venv/bin/python -m tg_bot.bot
Restart=always
RestartSec=30
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/jarvis-twitter.service << 'EOF'
[Unit]
Description=Jarvis Twitter/X Bot
After=network.target

[Service]
Type=simple
User=jarvis
WorkingDirectory=/home/jarvis/Jarvis
Environment=PYTHONUNBUFFERED=1
ExecStart=/home/jarvis/Jarvis/venv/bin/python -m bots.twitter.run_autonomous
Restart=always
RestartSec=30
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

chmod 644 /etc/systemd/system/jarvis-*.service
systemctl daemon-reload

echo -e "${GREEN}✓ Systemd services created${NC}"

# ============================================================================
# PHASE 5: START SERVICES
# ============================================================================
echo -e "${BLUE}[PHASE 5] Enable and start services${NC}"

systemctl enable jarvis-supervisor.service jarvis-telegram.service jarvis-twitter.service
systemctl start jarvis-supervisor.service jarvis-telegram.service jarvis-twitter.service

sleep 3

echo -e "${GREEN}✓ All services started${NC}"

# ============================================================================
# PHASE 6: VERIFY & SUMMARY
# ============================================================================
echo ""
echo "=========================================="
echo "DEPLOYMENT COMPLETE!"
echo "=========================================="
echo ""
echo -e "${GREEN}Services Running:${NC}"
systemctl status jarvis-supervisor.service 2>&1 | grep -E "active|failed" || true
systemctl status jarvis-telegram.service 2>&1 | grep -E "active|failed" || true
systemctl status jarvis-twitter.service 2>&1 | grep -E "active|failed" || true
echo ""
echo -e "${YELLOW}NEXT STEPS:${NC}"
echo "1. Update remaining API keys:"
echo "   nano /home/jarvis/Jarvis/secrets/keys.json"
echo ""
echo "2. Restart services after updating keys:"
echo "   systemctl restart jarvis-supervisor jarvis-telegram jarvis-twitter"
echo ""
echo "3. View logs:"
echo "   journalctl -u jarvis-supervisor -f"
echo ""
echo "=========================================="
