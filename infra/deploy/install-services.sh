#!/bin/bash
# JARVIS Systemd Service Installation Script
#
# This script installs systemd service units for all JARVIS bot components.
# Each bot runs as an independent systemd service with auto-restart, resource
# limits, and watchdog monitoring.
#
# Usage:
#   sudo ./deploy/install-services.sh [--supervisor-only|--split-services]
#
# Options:
#   --supervisor-only   Install only the monolithic supervisor service (default)
#   --split-services    Install individual services for each bot component
#
# Prerequisites:
#   - systemd-based Linux system
#   - User 'jarvis' exists
#   - /opt/jarvis directory exists with correct permissions
#   - .env file configured at /opt/jarvis/.env

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_DIR="/etc/systemd/system"
MODE="${1:---supervisor-only}"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}JARVIS Systemd Service Installer${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}ERROR: This script must be run as root${NC}"
    echo "Usage: sudo $0 [--supervisor-only|--split-services]"
    exit 1
fi

# Verify jarvis user exists
if ! id -u jarvis &>/dev/null; then
    echo -e "${RED}ERROR: User 'jarvis' does not exist${NC}"
    echo "Create it with: sudo useradd -r -m -d /opt/jarvis jarvis"
    exit 1
fi

# Verify /opt/jarvis exists
if [ ! -d /opt/jarvis ]; then
    echo -e "${RED}ERROR: /opt/jarvis directory does not exist${NC}"
    exit 1
fi

# Verify .env file exists
if [ ! -f /opt/jarvis/.env ]; then
    echo -e "${YELLOW}WARNING: /opt/jarvis/.env not found${NC}"
    echo "Services will fail to start without environment configuration"
fi

case "$MODE" in
    --supervisor-only)
        echo -e "\n${GREEN}Installing SUPERVISOR MODE (monolithic)${NC}"
        echo "This installs a single service that runs all bots via supervisor.py"
        echo ""

        # Stop and disable split services if they exist
        for service in jarvis-telegram jarvis-sentiment jarvis-twitter jarvis-buytracker jarvis-treasury; do
            if systemctl is-active --quiet "$service" 2>/dev/null; then
                echo "  Stopping $service..."
                systemctl stop "$service"
            fi
            if systemctl is-enabled --quiet "$service" 2>/dev/null; then
                echo "  Disabling $service..."
                systemctl disable "$service"
            fi
        done

        # Install supervisor service
        echo "  Installing jarvis.service..."
        cp "$SCRIPT_DIR/jarvis.service" "$SERVICE_DIR/"
        chmod 644 "$SERVICE_DIR/jarvis.service"

        # Reload and enable
        systemctl daemon-reload
        systemctl enable jarvis.service

        echo -e "\n${GREEN}✓ Supervisor service installed${NC}"
        echo ""
        echo "Start with: sudo systemctl start jarvis"
        echo "Status:     sudo systemctl status jarvis"
        echo "Logs:       sudo journalctl -u jarvis -f"
        ;;

    --split-services)
        echo -e "\n${GREEN}Installing SPLIT SERVICES MODE${NC}"
        echo "This installs separate services for each bot component"
        echo ""

        # Stop and disable supervisor if running
        if systemctl is-active --quiet jarvis 2>/dev/null; then
            echo "  Stopping jarvis (supervisor)..."
            systemctl stop jarvis
        fi
        if systemctl is-enabled --quiet jarvis 2>/dev/null; then
            echo "  Disabling jarvis (supervisor)..."
            systemctl disable jarvis
        fi

        # Install target
        echo "  Installing jarvis.target..."
        cp "$SCRIPT_DIR/jarvis.target" "$SERVICE_DIR/"
        chmod 644 "$SERVICE_DIR/jarvis.target"

        # Install individual services
        for service in telegram sentiment twitter buytracker treasury; do
            echo "  Installing jarvis-$service.service..."
            cp "$SCRIPT_DIR/jarvis-$service.service" "$SERVICE_DIR/"
            chmod 644 "$SERVICE_DIR/jarvis-$service.service"
        done

        # Reload and enable
        systemctl daemon-reload
        systemctl enable jarvis.target
        systemctl enable jarvis-telegram.service
        systemctl enable jarvis-sentiment.service
        systemctl enable jarvis-twitter.service
        systemctl enable jarvis-buytracker.service
        systemctl enable jarvis-treasury.service

        echo -e "\n${GREEN}✓ Split services installed${NC}"
        echo ""
        echo "Start all:  sudo systemctl start jarvis.target"
        echo "Stop all:   sudo systemctl stop jarvis.target"
        echo "Status:     sudo systemctl status 'jarvis-*'"
        echo "Logs:       sudo journalctl -u 'jarvis-*' -f"
        echo ""
        echo "Individual services:"
        echo "  - jarvis-telegram.service   (Telegram bot gateway)"
        echo "  - jarvis-sentiment.service  (Sentiment reporter)"
        echo "  - jarvis-twitter.service    (Twitter/X poster)"
        echo "  - jarvis-buytracker.service (Buy tracker)"
        echo "  - jarvis-treasury.service   (Treasury trading)"
        ;;

    *)
        echo -e "${RED}ERROR: Invalid option${NC}"
        echo "Usage: sudo $0 [--supervisor-only|--split-services]"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}Installation complete!${NC}"
echo ""
echo "Common commands:"
echo "  sudo systemctl daemon-reload       # Reload service definitions"
echo "  sudo systemctl restart jarvis      # Restart services"
echo "  sudo journalctl -u jarvis -f       # Follow logs"
echo "  sudo systemctl status jarvis       # Check status"
echo ""
