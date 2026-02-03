#!/bin/bash
# Deploy ClawdBot Full Image to VPS
# Copies files, builds image, and redeploys all containers

set -e

VPS_HOST="${VPS_HOST:-root@76.13.106.100}"
VPS_DIR="/root/clawd"

echo "=========================================="
echo "ClawdBot Full Image Deployment"
echo "=========================================="
echo "Target: $VPS_HOST"
echo ""

# =============================================================================
# Step 1: Copy files to VPS
# =============================================================================

echo "[1/5] Copying deployment files to VPS..."

# Create directories on VPS
ssh $VPS_HOST "mkdir -p $VPS_DIR/build $VPS_DIR/data/{friday,matt,jarvis}/{memory,skills}"

# Copy Dockerfile and scripts
scp Dockerfile.clawdbot-full $VPS_HOST:$VPS_DIR/build/Dockerfile
scp tailscale-start.sh $VPS_HOST:$VPS_DIR/build/
scp entrypoint.sh $VPS_HOST:$VPS_DIR/build/
scp docker-compose.clawdbots.yml $VPS_HOST:$VPS_DIR/

echo "   Files copied successfully"

# =============================================================================
# Step 2: Build new image on VPS
# =============================================================================

echo "[2/5] Building clawdbot-ready:latest image..."

ssh $VPS_HOST "cd $VPS_DIR/build && docker build -t clawdbot-ready:latest -f Dockerfile ."

echo "   Image built successfully"

# =============================================================================
# Step 3: Stop existing containers
# =============================================================================

echo "[3/5] Stopping existing containers..."

ssh $VPS_HOST "docker stop clawdbot-friday clawdbot-matt clawdbot-jarvis 2>/dev/null || true"
ssh $VPS_HOST "docker rm clawdbot-friday clawdbot-matt clawdbot-jarvis 2>/dev/null || true"

echo "   Old containers removed"

# =============================================================================
# Step 4: Start new containers
# =============================================================================

echo "[4/5] Starting new containers with docker-compose..."

# Check if XAI_API_KEY exists in environment
ssh $VPS_HOST "cd $VPS_DIR && docker-compose -f docker-compose.clawdbots.yml up -d"

echo "   Containers started"

# =============================================================================
# Step 5: Verify health
# =============================================================================

echo "[5/5] Waiting for containers to become healthy..."
sleep 30

ssh $VPS_HOST "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep clawdbot"

echo ""
echo "=========================================="
echo "Deployment complete!"
echo "=========================================="
echo ""
echo "Health check endpoints:"
echo "  Friday:  http://76.13.106.100:18789"
echo "  Matt:    http://76.13.106.100:18800"
echo "  Jarvis:  http://76.13.106.100:18801"
echo "  Health:  http://76.13.106.100:18888/health"
echo ""
echo "To check logs:"
echo "  ssh $VPS_HOST 'docker logs -f clawdbot-friday'"
