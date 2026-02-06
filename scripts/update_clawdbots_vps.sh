#!/bin/bash
# Update ClawdBots to OpenClaw 2026.2.3 on VPS
# Run on VPS: bash update_clawdbots_vps.sh

set -e

echo "====================================="
echo "ClawdBots Update to OpenClaw 2026.2.3"
echo "====================================="

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "ERROR: This script must be run as root"
   echo "Usage: sudo bash update_clawdbots_vps.sh"
   exit 1
fi

# Verify we're in the clawdbots directory
if [[ ! -d "/root/clawdbots" ]]; then
    echo "ERROR: /root/clawdbots not found"
    exit 1
fi

cd /root/clawdbots

echo ""
echo "Step 1: Backing up current configuration..."
mkdir -p /root/clawdbots-backup
docker compose -f deploy/clawdbot-redundancy/docker-compose.clawdbots.yml config > /root/clawdbots-backup/docker-compose-backup-$(date +%Y%m%d-%H%M%S).yml
echo "✓ Configuration backed up"

echo ""
echo "Step 2: Stopping current containers..."
docker compose -f deploy/clawdbot-redundancy/docker-compose.clawdbots.yml down
echo "✓ Containers stopped"

echo ""
echo "Step 3: Building new image with OpenClaw 2026.2.3..."
cd deploy/clawdbot-redundancy
docker build -f Dockerfile.clawdbot-full -t clawdbot-ready:2026.2.3 . --no-cache
docker tag clawdbot-ready:2026.2.3 clawdbot-ready:latest
echo "✓ Image built"

echo ""
echo "Step 4: Starting containers with new image..."
docker compose -f docker-compose.clawdbots.yml up -d
echo "✓ Containers started"

echo ""
echo "Step 5: Waiting for containers to be healthy (60s)..."
sleep 60

echo ""
echo "Step 6: Verifying installation..."
echo ""
echo "Friday version:"
docker exec clawdbot-friday openclaw --version || echo "Warning: Friday not responding"
echo ""
echo "Matt version:"
docker exec clawdbot-matt openclaw --version || echo "Warning: Matt not responding"
echo ""
echo "Jarvis version:"
docker exec clawdbot-jarvis openclaw --version || echo "Warning: Jarvis not responding"

echo ""
echo "Step 7: Checking container health..."
docker compose -f docker-compose.clawdbots.yml ps

echo ""
echo "====================================="
echo "Update Complete!"
echo "====================================="
echo ""
echo "Monitor logs with:"
echo "  docker compose -f deploy/clawdbot-redundancy/docker-compose.clawdbots.yml logs -f"
echo ""
echo "Check individual bot logs:"
echo "  docker logs -f clawdbot-friday"
echo "  docker logs -f clawdbot-matt"
echo "  docker logs -f clawdbot-jarvis"
echo ""
echo "Check health endpoints:"
echo "  curl http://localhost:18789/__clawdbot__/canvas/"
echo "  curl http://localhost:18800/__clawdbot__/canvas/"
echo "  curl http://localhost:18801/__clawdbot__/canvas/"
echo ""
