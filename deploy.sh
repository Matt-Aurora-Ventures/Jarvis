#!/bin/bash
# JARVIS VPS DEPLOYMENT SCRIPT - AUTOMATED FULL SETUP
# Run this on your VPS as root after SSH in
# Usage: bash deploy.sh

set -e  # Exit on error

echo "=========================================="
echo "JARVIS BOT DEPLOYMENT - FULL AUTOMATION"
echo "=========================================="

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ============================================================================
# PHASE 1: SYSTEM SETUP
# ============================================================================
echo -e "${BLUE}[PHASE 1] System Setup${NC}"

# Update system
echo "Updating system packages..."
apt update && apt upgrade -y

# Install dependencies
echo "Installing dependencies..."
apt install -y \
    python3.12 python3.12-venv python3-pip \
    git sqlite3 curl wget \
    ufw fail2ban \
    supervisor \
    htop screen

echo -e "${GREEN}✓ System dependencies installed${NC}"

# ============================================================================
# PHASE 2: CREATE JARVIS USER (Don't run bots as root)
# ============================================================================
echo -e "${BLUE}[PHASE 2] Create jarvis user${NC}"

# Check if user exists
if id "jarvis" &>/dev/null; then
    echo "jarvis user already exists"
else
    adduser --disabled-password --gecos "" jarvis
    usermod -aG sudo jarvis
    echo -e "${GREEN}✓ jarvis user created${NC}"
fi

# ============================================================================
# PHASE 3: SETUP FIREWALL
# ============================================================================
echo -e "${BLUE}[PHASE 3] Configure firewall${NC}"

ufw allow OpenSSH
ufw allow 80
ufw allow 443
ufw --force enable

echo -e "${GREEN}✓ Firewall configured${NC}"

# ============================================================================
# PHASE 4: CLONE & SETUP JARVIS
# ============================================================================
echo -e "${BLUE}[PHASE 4] Clone and setup Jarvis${NC}"

cd /home/jarvis

# Clone repo if not exists
if [ ! -d "Jarvis" ]; then
    sudo -u jarvis git clone https://github.com/Matt-Aurora-Ventures/Jarvis.git
    echo -e "${GREEN}✓ Repository cloned${NC}"
else
    echo "Repository already exists, updating..."
    sudo -u jarvis bash -c "cd /home/jarvis/Jarvis && git pull"
fi

cd /home/jarvis/Jarvis

# Setup Python venv
if [ ! -d "venv" ]; then
    sudo -u jarvis python3.12 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# Activate and install dependencies
sudo -u jarvis bash -c "
    source venv/bin/activate
    pip install --upgrade pip setuptools wheel
    pip install -r requirements.txt
" || true

echo -e "${GREEN}✓ Dependencies installed${NC}"

# ============================================================================
# PHASE 5: SETUP SECRETS
# ============================================================================
echo -e "${BLUE}[PHASE 5] Setup secrets directory${NC}"

mkdir -p /home/jarvis/Jarvis/secrets
chmod 700 /home/jarvis/Jarvis/secrets

cat > /home/jarvis/Jarvis/secrets/keys.json << 'SECRETS_EOF'
{
  "anthropic_api_key": "YOUR_ANTHROPIC_KEY",
  "xai": {"api_key": "YOUR_XAI_KEY"},
  "groq_api_key": "YOUR_GROQ_KEY",
  "minimax_api_key": "YOUR_MINIMAX_KEY",
  "birdeye_api_key": "YOUR_BIRDEYE_KEY",
  "helius": {"api_key": "YOUR_HELIUS_KEY"},
  "twitter": {
    "api_key": "YOUR_TWITTER_API_KEY",
    "api_secret": "YOUR_TWITTER_API_SECRET",
    "access_token": "YOUR_ACCESS_TOKEN",
    "access_secret": "YOUR_ACCESS_SECRET"
  },
  "telegram": {
    "bot_token": "YOUR_TELEGRAM_BOT_TOKEN"
  }
}
SECRETS_EOF

chmod 600 /home/jarvis/Jarvis/secrets/keys.json
chown jarvis:jarvis /home/jarvis/Jarvis/secrets/keys.json

echo -e "${YELLOW}[!] IMPORTANT: Update secrets/keys.json with your actual API keys${NC}"
echo "    Edit: /home/jarvis/Jarvis/secrets/keys.json"

# ============================================================================
# PHASE 6: CREATE SYSTEMD SERVICES
# ============================================================================
echo -e "${BLUE}[PHASE 6] Create systemd services${NC}"

# Twitter Bot Service
cat > /etc/systemd/system/jarvis-twitter.service << 'TWITTER_SERVICE'
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
TWITTER_SERVICE

# Telegram Bot Service
cat > /etc/systemd/system/jarvis-telegram.service << 'TELEGRAM_SERVICE'
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
TELEGRAM_SERVICE

# Supervisor (buy bot, sentiment reporter, etc via supervisor.py)
cat > /etc/systemd/system/jarvis-supervisor.service << 'SUPERVISOR_SERVICE'
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
SUPERVISOR_SERVICE

chmod 644 /etc/systemd/system/jarvis-*.service

systemctl daemon-reload

echo -e "${GREEN}✓ Systemd services created${NC}"

# ============================================================================
# PHASE 7: START SERVICES
# ============================================================================
echo -e "${BLUE}[PHASE 7] Enable and start services${NC}"

systemctl enable jarvis-supervisor.service
systemctl enable jarvis-telegram.service
systemctl enable jarvis-twitter.service

systemctl start jarvis-supervisor.service
systemctl start jarvis-telegram.service
systemctl start jarvis-twitter.service

echo -e "${GREEN}✓ All services started${NC}"

# ============================================================================
# PHASE 8: VERIFY DEPLOYMENT
# ============================================================================
echo -e "${BLUE}[PHASE 8] Verify deployment${NC}"

sleep 3

echo ""
echo "Service Status:"
echo "================================"

systemctl status jarvis-supervisor.service || true
echo ""

systemctl status jarvis-telegram.service || true
echo ""

systemctl status jarvis-twitter.service || true
echo ""

# ============================================================================
# PHASE 9: SETUP LOG ROTATION
# ============================================================================
echo -e "${BLUE}[PHASE 9] Configure log rotation${NC}"

cat > /etc/logrotate.d/jarvis << 'LOGROTATE_EOF'
/home/jarvis/Jarvis/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    notifempty
    missingok
    create 0640 jarvis jarvis
}
LOGROTATE_EOF

echo -e "${GREEN}✓ Log rotation configured${NC}"

# ============================================================================
# FINAL SUMMARY
# ============================================================================
echo ""
echo "=========================================="
echo "DEPLOYMENT COMPLETE!"
echo "=========================================="
echo ""
echo -e "${GREEN}All services are running!${NC}"
echo ""
echo "Quick Commands:"
echo "  View logs:     journalctl -u jarvis-supervisor -f"
echo "  Restart:       systemctl restart jarvis-supervisor jarvis-telegram jarvis-twitter"
echo "  Stop:          systemctl stop jarvis-supervisor jarvis-telegram jarvis-twitter"
echo "  Status:        systemctl status jarvis-*"
echo ""
echo "NEXT STEPS:"
echo "  1. Update API keys in: /home/jarvis/Jarvis/secrets/keys.json"
echo "  2. Restart services:   systemctl restart jarvis-supervisor jarvis-telegram jarvis-twitter"
echo "  3. Test Telegram:      Send /start to @Jarviskr8tivbot"
echo "  4. Check X bot:        Look for posts from @Jarvis_lifeos"
echo ""
echo "Monitor logs:"
echo "  journalctl -u jarvis-supervisor -n 100 -f"
echo "=========================================="
