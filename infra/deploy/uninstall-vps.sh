#!/bin/bash
#
# Jarvis VPS Supervisor Uninstallation Script
# Removes the systemd service and cleans up
#
# Usage:
#   sudo bash deploy/uninstall-vps.sh [--keep-data]
#
# Options:
#   --keep-data    Keep logs and data directories

set -e

JARVIS_USER="jarvis"
JARVIS_HOME="/home/jarvis"
JARVIS_DIR="$JARVIS_HOME/Jarvis"
SERVICE_NAME="jarvis-supervisor"
KEEP_DATA=false

# Parse args
for arg in "$@"; do
    case $arg in
        --keep-data) KEEP_DATA=true ;;
    esac
done

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

echo ""
echo "=========================================="
echo "  JARVIS VPS Supervisor Uninstallation"
echo "=========================================="
echo ""

# Check root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}[ERROR]${NC} This script must be run as root"
    exit 1
fi

# Step 1: Stop service if running
log_info "Step 1/4: Stopping service..."
if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    systemctl stop "$SERVICE_NAME"
    log_info "Service stopped"
else
    log_info "Service was not running"
fi

# Step 2: Disable service
log_info "Step 2/4: Disabling service..."
if systemctl is-enabled --quiet "$SERVICE_NAME" 2>/dev/null; then
    systemctl disable "$SERVICE_NAME"
    log_info "Service disabled"
else
    log_info "Service was not enabled"
fi

# Step 3: Remove service file
log_info "Step 3/4: Removing service file..."
if [ -f "/etc/systemd/system/$SERVICE_NAME.service" ]; then
    rm "/etc/systemd/system/$SERVICE_NAME.service"
    log_info "Service file removed"
else
    log_info "Service file not found"
fi

# Remove logrotate config
if [ -f "/etc/logrotate.d/jarvis" ]; then
    rm "/etc/logrotate.d/jarvis"
    log_info "Logrotate config removed"
fi

systemctl daemon-reload

# Step 4: Optionally clean up data
log_info "Step 4/4: Cleanup..."
if [ "$KEEP_DATA" = true ]; then
    log_warn "Keeping data directories (--keep-data specified)"
else
    log_warn "Data directories preserved by default"
    log_warn "To remove logs: rm -rf $JARVIS_DIR/logs/*"
    log_warn "To remove data: rm -rf $JARVIS_DIR/data/*"
    log_warn "To remove user: userdel -r $JARVIS_USER"
fi

echo ""
echo "=========================================="
echo "  Uninstallation Complete!"
echo "=========================================="
echo ""
echo "The jarvis-supervisor service has been removed."
echo ""
echo "To fall back to manual mode:"
echo "  cd $JARVIS_DIR"
echo "  set -a; . .env; set +a"
echo "  nohup python3 bots/supervisor.py > logs/supervisor.out.log 2>&1 &"
echo "  echo \$! > run/supervisor.pid"
echo ""
echo "To reinstall:"
echo "  sudo bash deploy/install-vps.sh"
echo ""
echo "=========================================="
