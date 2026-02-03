#!/bin/bash
# ClawdBot Full Infrastructure Installation
# Deploys all components to VPS in correct order
#
# Usage:
#   Local:  ./install-full.sh              (deploys to remote VPS)
#   Remote: ./install-full.sh --local      (runs on VPS directly)

set -e

VPS_HOST="${VPS_HOST:-root@76.13.106.100}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REMOTE_DIR="/root/clawd"

# =============================================================================
# Installation Steps
# =============================================================================

install_local() {
    echo "=========================================="
    echo "ClawdBot Full Infrastructure Installation"
    echo "=========================================="
    echo "Target: $VPS_HOST"
    echo ""

    # Step 1: Copy all files
    echo "[1/7] Copying deployment files..."
    ssh $VPS_HOST "mkdir -p $REMOTE_DIR/{scripts,infra,build,data/{friday,matt,jarvis}/{memory,skills},backups,reflections}"

    scp -r "$SCRIPT_DIR/scripts/"* $VPS_HOST:$REMOTE_DIR/scripts/
    scp -r "$SCRIPT_DIR/monitoring/" $VPS_HOST:$REMOTE_DIR/monitoring/
    scp "$SCRIPT_DIR/Dockerfile.clawdbot-full" $VPS_HOST:$REMOTE_DIR/build/Dockerfile
    scp "$SCRIPT_DIR/tailscale-start.sh" $VPS_HOST:$REMOTE_DIR/build/
    scp "$SCRIPT_DIR/entrypoint.sh" $VPS_HOST:$REMOTE_DIR/build/
    scp "$SCRIPT_DIR/docker-compose.clawdbots.yml" $VPS_HOST:$REMOTE_DIR/
    scp "$SCRIPT_DIR/firewall-rules.sh" $VPS_HOST:$REMOTE_DIR/infra/
    echo "   Files copied"

    # Step 2: Make scripts executable
    echo "[2/7] Setting permissions..."
    ssh $VPS_HOST "chmod +x $REMOTE_DIR/scripts/*.sh $REMOTE_DIR/infra/*.sh $REMOTE_DIR/build/*.sh"
    echo "   Permissions set"

    # Step 3: Build Docker image
    echo "[3/7] Building Docker image..."
    ssh $VPS_HOST "cd $REMOTE_DIR/build && docker build -t clawdbot-ready:latest -f Dockerfile ."
    echo "   Image built"

    # Step 4: Setup cron jobs
    echo "[4/7] Setting up cron jobs..."
    ssh $VPS_HOST "$REMOTE_DIR/scripts/setup-cron.sh"
    echo "   Cron installed"

    # Step 5: Deploy containers
    echo "[5/7] Deploying containers..."
    ssh $VPS_HOST "cd $REMOTE_DIR && docker-compose -f docker-compose.clawdbots.yml down 2>/dev/null || true"
    ssh $VPS_HOST "cd $REMOTE_DIR && docker-compose -f docker-compose.clawdbots.yml up -d"
    echo "   Containers started"

    # Step 6: Apply firewall rules
    echo "[6/7] Applying firewall rules..."
    ssh $VPS_HOST "$REMOTE_DIR/infra/firewall-rules.sh" || echo "   Firewall skipped (may need manual setup)"

    # Step 7: Initialize systems
    echo "[7/7] Initializing systems..."
    ssh $VPS_HOST "$REMOTE_DIR/scripts/trust-ladder.sh status" || true
    ssh $VPS_HOST "$REMOTE_DIR/scripts/circuit-breaker.sh status" || true
    echo "   Systems initialized"

    echo ""
    echo "=========================================="
    echo "Installation Complete!"
    echo "=========================================="
    print_summary
}

install_remote() {
    echo "=========================================="
    echo "ClawdBot Local Installation"
    echo "=========================================="

    # Assuming scripts are already in place
    REMOTE_DIR="/root/clawd"

    echo "[1/5] Building Docker image..."
    cd $REMOTE_DIR/build && docker build -t clawdbot-ready:latest -f Dockerfile .

    echo "[2/5] Setting up cron jobs..."
    $REMOTE_DIR/scripts/setup-cron.sh

    echo "[3/5] Deploying containers..."
    cd $REMOTE_DIR && docker-compose -f docker-compose.clawdbots.yml down 2>/dev/null || true
    cd $REMOTE_DIR && docker-compose -f docker-compose.clawdbots.yml up -d

    echo "[4/5] Applying firewall rules..."
    $REMOTE_DIR/infra/firewall-rules.sh || echo "Firewall skipped"

    echo "[5/5] Initializing systems..."
    $REMOTE_DIR/scripts/trust-ladder.sh status || true
    $REMOTE_DIR/scripts/circuit-breaker.sh status || true

    echo ""
    echo "=========================================="
    echo "Installation Complete!"
    echo "=========================================="
    print_summary
}

print_summary() {
    echo ""
    echo "Endpoints:"
    echo "  Friday Gateway:  http://76.13.106.100:18789"
    echo "  Matt Gateway:    http://76.13.106.100:18800"
    echo "  Jarvis Gateway:  http://76.13.106.100:18801"
    echo "  Health API:      http://76.13.106.100:18888/health"
    echo ""
    echo "Automated Tasks:"
    echo "  - Watchdog:     Every minute"
    echo "  - Backup:       3:00 AM UTC daily"
    echo "  - Reflection:   4:00 AM UTC daily"
    echo "  - Hydration:    Every 6 hours"
    echo ""
    echo "Management Commands:"
    echo "  Trust Ladder:    /root/clawd/scripts/trust-ladder.sh status"
    echo "  Circuit Breaker: /root/clawd/scripts/circuit-breaker.sh status"
    echo "  Brain Export:    /root/clawd/scripts/brain-export.sh friday /tmp/brain.tar.gz"
    echo ""
    echo "Logs:"
    echo "  docker logs -f clawdbot-friday"
    echo "  tail -f /var/log/clawdbot-watchdog.log"
}

# =============================================================================
# Main
# =============================================================================

if [ "$1" = "--local" ]; then
    install_remote
else
    install_local
fi
