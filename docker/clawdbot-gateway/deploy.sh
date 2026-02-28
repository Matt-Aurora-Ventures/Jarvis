#!/bin/bash
# ============================================================================
# Deploy 3-Agent ClawdBot Gateway to VPS
# ============================================================================
# Run this ON the VPS after SCP'ing the files over.
# ============================================================================
set -e

DEPLOY_DIR="/docker/clawdbot-gateway"
WORKSPACE_BASE="/root/clawd"

echo "=== ClawdBot 3-Agent Gateway Deployment ==="

# 1. Stop existing single container
echo "[1/6] Stopping existing clawdbot-gateway..."
cd "$DEPLOY_DIR" 2>/dev/null && docker compose down 2>/dev/null || true
docker stop clawdbot-gateway 2>/dev/null || true
docker rm clawdbot-gateway 2>/dev/null || true

# 2. Backup existing config
echo "[2/6] Backing up existing config..."
BACKUP_DIR="/docker/clawdbot-gateway/backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp "$DEPLOY_DIR/docker-compose.yml" "$BACKUP_DIR/" 2>/dev/null || true
cp -r /var/lib/docker/volumes/opt_clawdbot-config/_data/ "$BACKUP_DIR/old-config/" 2>/dev/null || true
cp -r /var/lib/docker/volumes/opt_clawdbot-workspace/_data/ "$BACKUP_DIR/old-workspace/" 2>/dev/null || true
echo "  Backup at: $BACKUP_DIR"

# 3. Generate unique auth tokens
echo "[3/6] Generating auth tokens..."
FRIDAY_TOKEN=$(openssl rand -hex 32)
MATT_TOKEN=$(openssl rand -hex 32)
JARVIS_TOKEN=$(openssl rand -hex 32)

# Update .env with generated tokens
sed -i "s/FRIDAY_AUTH_TOKEN=GENERATE_ME_ON_VPS/FRIDAY_AUTH_TOKEN=$FRIDAY_TOKEN/" "$DEPLOY_DIR/.env"
sed -i "s/MATT_AUTH_TOKEN=GENERATE_ME_ON_VPS/MATT_AUTH_TOKEN=$MATT_TOKEN/" "$DEPLOY_DIR/.env"
sed -i "s/JARVIS_AUTH_TOKEN=GENERATE_ME_ON_VPS/JARVIS_AUTH_TOKEN=$JARVIS_TOKEN/" "$DEPLOY_DIR/.env"

echo "  Friday: ${FRIDAY_TOKEN:0:8}..."
echo "  Matt:   ${MATT_TOKEN:0:8}..."
echo "  Jarvis: ${JARVIS_TOKEN:0:8}..."

# 4. Set up workspace directories
echo "[4/6] Setting up workspaces..."
for agent in friday matt jarvis; do
  mkdir -p "$WORKSPACE_BASE/$agent"
done

# Copy SOUL.md files if they exist alongside this script
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$SCRIPT_DIR/workspace-matt/SOUL.md" ]; then
  cp "$SCRIPT_DIR/workspace-matt/SOUL.md" "$WORKSPACE_BASE/matt/SOUL.md"
  echo "  Copied Matt SOUL.md"
fi
if [ -f "$SCRIPT_DIR/workspace-jarvis/SOUL.md" ]; then
  cp "$SCRIPT_DIR/workspace-jarvis/SOUL.md" "$WORKSPACE_BASE/jarvis/SOUL.md"
  echo "  Copied Jarvis SOUL.md"
fi
# Preserve Friday's existing workspace
if [ -d "$BACKUP_DIR/old-workspace" ]; then
  cp -n "$BACKUP_DIR/old-workspace/"*.md "$WORKSPACE_BASE/friday/" 2>/dev/null || true
  echo "  Preserved Friday workspace files"
fi

# 5. Start all 3 containers
echo "[5/6] Starting 3-agent gateway..."
cd "$DEPLOY_DIR"
docker compose up -d

# 6. Verify
echo "[6/6] Verifying..."
sleep 10
for port in 18789 18790 18791; do
  if ss -tlnp | grep -q ":$port "; then
    echo "  Port $port: LISTENING"
  else
    echo "  Port $port: NOT YET (may still be starting)"
  fi
done

echo ""
echo "=== Deployment Complete ==="
echo "Friday (CMO): http://localhost:18789 - Claude Opus 4.6"
echo "Matt   (COO): http://localhost:18790 - Codex CLI Driver"
echo "Jarvis (CTO): http://localhost:18791 - Grok"
echo ""
echo "Auth tokens saved in: $DEPLOY_DIR/.env"
echo "Logs: docker compose -f $DEPLOY_DIR/docker-compose.yml logs -f"
