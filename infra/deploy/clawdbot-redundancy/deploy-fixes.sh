#!/bin/bash
# ClawdBot Critical Fixes Deployment Script
# Applies fixes identified in error report:
# 1. Removes conflicting cron jobs
# 2. Creates persistent workspace directories
# 3. Updates watchdog to v3
# 4. Recreates containers with proper volume mounts

set -e

VPS_HOST="root@76.13.106.100"
LOCAL_DIR="$(dirname "$0")"

echo "=========================================="
echo "ClawdBot Critical Fixes Deployment"
echo "=========================================="
echo ""

# Step 1: Remove conflicting cron jobs
echo "[1/6] Removing conflicting cron jobs..."
ssh "$VPS_HOST" bash -s << 'EOF'
echo "Current crontab:"
crontab -l 2>/dev/null || echo "(empty)"
echo ""

# Remove ALL old recovery scripts from cron
crontab -l 2>/dev/null | \
    grep -v 'auto-recovery.sh' | \
    grep -v 'jarvis-recovery.sh' | \
    grep -v 'bot-health-watchdog.sh' | \
    grep -v 'watchdog' | \
    crontab - 2>/dev/null || true

echo "After cleanup:"
crontab -l 2>/dev/null || echo "(empty)"
EOF
echo "Done."
echo ""

# Step 2: Create workspace directories
echo "[2/6] Creating persistent workspace directories..."
ssh "$VPS_HOST" bash -s << 'EOF'
mkdir -p /root/clawd/workspaces/friday
mkdir -p /root/clawd/workspaces/matt
mkdir -p /root/clawd/workspaces/jarvis
mkdir -p /root/clawd/infra
mkdir -p /root/clawdbots/data

# Set permissions
chmod 755 /root/clawd/workspaces/friday
chmod 755 /root/clawd/workspaces/matt
chmod 755 /root/clawd/workspaces/jarvis

echo "Workspace directories created:"
ls -la /root/clawd/workspaces/
EOF
echo "Done."
echo ""

# Step 3: Stop any restart loops by pausing all bots
echo "[3/6] Pausing all bots (to stop restart loops)..."
ssh "$VPS_HOST" bash -s << 'EOF'
# Set pause files for all bots
for bot in friday matt jarvis; do
    echo "Pausing $bot..."
    date +%s > "/tmp/.clawdbot-${bot}_paused"
done
echo "All bots paused (1 hour timeout)"
EOF
echo "Done."
echo ""

# Step 4: Copy updated files
echo "[4/6] Copying updated configuration files..."

# Convert line endings to Unix format before copying
echo "Converting line endings..."
if command -v dos2unix &> /dev/null; then
    dos2unix "$LOCAL_DIR/docker-compose.clawdbots.yml" 2>/dev/null || true
    dos2unix "$LOCAL_DIR/vps-watchdog-v3.sh" 2>/dev/null || true
    dos2unix "$LOCAL_DIR/entrypoint.sh" 2>/dev/null || true
    dos2unix "$LOCAL_DIR/tailscale-start.sh" 2>/dev/null || true
    dos2unix "$LOCAL_DIR/scripts/peer-health-monitor.sh" 2>/dev/null || true
    dos2unix "$LOCAL_DIR/scripts/solana-wallet-init.sh" 2>/dev/null || true
else
    # Fallback using sed
    for f in docker-compose.clawdbots.yml vps-watchdog-v3.sh entrypoint.sh tailscale-start.sh; do
        sed -i 's/\r$//' "$LOCAL_DIR/$f" 2>/dev/null || true
    done
    for f in scripts/peer-health-monitor.sh scripts/solana-wallet-init.sh; do
        sed -i 's/\r$//' "$LOCAL_DIR/$f" 2>/dev/null || true
    done
fi

# Copy files to VPS
scp "$LOCAL_DIR/docker-compose.clawdbots.yml" "$VPS_HOST:/root/clawd/infra/"
scp "$LOCAL_DIR/vps-watchdog-v3.sh" "$VPS_HOST:/root/clawd/infra/bot-health-watchdog.sh"
scp "$LOCAL_DIR/entrypoint.sh" "$VPS_HOST:/root/clawd/infra/"
scp "$LOCAL_DIR/tailscale-start.sh" "$VPS_HOST:/root/clawd/infra/"
scp "$LOCAL_DIR/scripts/peer-health-monitor.sh" "$VPS_HOST:/root/clawd/infra/"
scp "$LOCAL_DIR/scripts/solana-wallet-init.sh" "$VPS_HOST:/root/clawd/infra/"

# Make executable
ssh "$VPS_HOST" "chmod +x /root/clawd/infra/*.sh"
echo "Done."
echo ""

# Step 5: Install new watchdog v3 cron job
echo "[5/6] Installing watchdog v3 cron job..."
ssh "$VPS_HOST" bash -s << 'EOF'
# Add single watchdog v3 cron job
(crontab -l 2>/dev/null | grep -v watchdog; echo "* * * * * /root/clawd/infra/bot-health-watchdog.sh >> /var/log/clawdbot-watchdog.log 2>&1") | crontab -

echo "New crontab:"
crontab -l
EOF
echo "Done."
echo ""

# Step 6: Recreate containers one at a time
echo "[6/6] Recreating containers with fixed configuration..."
ssh "$VPS_HOST" bash -s << 'EOF'
cd /root/clawd/infra

# Stop all containers first
echo "Stopping all containers..."
docker stop clawdbot-friday clawdbot-matt clawdbot-jarvis 2>/dev/null || true
docker rm clawdbot-friday clawdbot-matt clawdbot-jarvis 2>/dev/null || true

# Clear pause files
rm -f /tmp/.clawdbot-*_paused /tmp/.clawdbot-*_failures /tmp/.clawdbot-*_rebuilds /tmp/.clawdbot-*_cooldown

# Start with compose
echo "Starting containers with new configuration..."
docker-compose -f docker-compose.clawdbots.yml up -d friday matt jarvis

echo "Waiting 60s for startup..."
sleep 60

# Check health
echo ""
echo "Container status:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep clawdbot

echo ""
echo "Health checks:"
for bot in friday matt jarvis; do
    case "$bot" in
        friday) port=18789 ;;
        matt)   port=18800 ;;
        jarvis) port=18801 ;;
    esac

    response=$(curl -s --connect-timeout 5 --max-time 10 "http://127.0.0.1:${port}/__clawdbot__/canvas/" 2>&1)
    if echo "$response" | grep -qi "clawdbot\|canvas\|gateway"; then
        echo "$bot (port $port): HEALTHY"
    else
        echo "$bot (port $port): STARTING (may need more time)"
    fi
done
EOF

echo ""
echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Monitor logs: ssh root@76.13.106.100 'docker logs -f clawdbot-friday'"
echo "2. Check health: ssh root@76.13.106.100 'docker ps | grep clawdbot'"
echo "3. View watchdog: ssh root@76.13.106.100 'tail -f /var/log/clawdbot-watchdog.log'"
echo ""
