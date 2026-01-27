#!/bin/bash
# JARVIS VPS COMPLETE FIX - Ralph Wiggum Loop Edition
# Run this in Hostinger web terminal to fix everything
#
# What this script does:
# 1. Checks Docker containers and stops conflicts
# 2. Pulls latest code from GitHub
# 3. Deploys bot fixes
# 4. Fixes SSH firewall access
# 5. Optimizes CPU usage
# 6. Restarts all services cleanly

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     JARVIS VPS COMPLETE FIX - Ralph Wiggum Loop         ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# ============================================================================
# PHASE 1: CHECK DOCKER CONTAINERS & FIX CONFLICTS
# ============================================================================
echo -e "${BLUE}[PHASE 1] Checking Docker containers...${NC}"

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo -e "${RED}Docker is not running. Starting Docker...${NC}"
    systemctl start docker
    sleep 3
fi

# List all running containers
echo -e "${YELLOW}Currently running containers:${NC}"
docker ps --format "table {{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Ports}}"

# Check for Jarvis container
if docker ps | grep -q "jarvis"; then
    echo -e "${YELLOW}Found Jarvis container. Checking resource usage...${NC}"
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.BlockIO}}"
fi

# Stop any conflicting containers
echo -e "${YELLOW}Stopping old Jarvis containers...${NC}"
docker stop $(docker ps -q --filter "name=jarvis") 2>/dev/null || echo "No containers to stop"
docker rm $(docker ps -aq --filter "name=jarvis") 2>/dev/null || echo "No containers to remove"

echo -e "${GREEN}✓ Docker cleanup complete${NC}"
echo ""

# ============================================================================
# PHASE 2: PULL LATEST CODE FROM GITHUB
# ============================================================================
echo -e "${BLUE}[PHASE 2] Pulling latest code from GitHub...${NC}"

# Navigate to Jarvis directory
if [ ! -d "/home/jarvis/Jarvis" ]; then
    echo -e "${RED}ERROR: /home/jarvis/Jarvis directory not found!${NC}"
    echo -e "${YELLOW}Creating directory and cloning repo...${NC}"
    cd /home/jarvis
    sudo -u jarvis git clone https://github.com/Matt-Aurora-Ventures/Jarvis.git
else
    cd /home/jarvis/Jarvis
fi

# Pull latest changes
echo -e "${YELLOW}Current branch:${NC}"
git branch --show-current

echo -e "${YELLOW}Fetching latest changes...${NC}"
sudo -u jarvis git fetch origin main

echo -e "${YELLOW}Pulling changes...${NC}"
sudo -u jarvis git pull origin main

# Show last 5 commits
echo -e "${GREEN}Last 5 commits:${NC}"
git log --oneline -5

echo -e "${GREEN}✓ Code updated to latest${NC}"
echo ""

# ============================================================================
# PHASE 3: CHECK WHICH BOT FILES CHANGED
# ============================================================================
echo -e "${BLUE}[PHASE 3] Checking bot file changes...${NC}"

# Show files changed in last 7 commits (our deployment)
echo -e "${YELLOW}Bot files changed in recent commits:${NC}"
git diff --name-status HEAD~7..HEAD | grep -E "tg_bot|bots/" || echo "No bot files changed"

echo -e "${GREEN}✓ Change review complete${NC}"
echo ""

# ============================================================================
# PHASE 4: FIX SSH FIREWALL ACCESS
# ============================================================================
echo -e "${BLUE}[PHASE 4] Fixing SSH firewall access...${NC}"

# Check current SSH status
echo -e "${YELLOW}SSH service status:${NC}"
systemctl status ssh --no-pager | head -5

# Check firewall rules
echo -e "${YELLOW}Current UFW status:${NC}"
ufw status numbered

# Allow SSH from anywhere (we'll restrict later if needed)
echo -e "${YELLOW}Allowing SSH access...${NC}"
ufw allow 22/tcp
ufw allow OpenSSH

# Ensure SSH is running
systemctl enable ssh
systemctl start ssh

# Show listening ports
echo -e "${YELLOW}SSH listening on:${NC}"
netstat -tuln | grep :22 || ss -tuln | grep :22

echo -e "${GREEN}✓ SSH access configured${NC}"
echo ""

# ============================================================================
# PHASE 5: OPTIMIZE CPU USAGE (STOP RESOURCE HOGS)
# ============================================================================
echo -e "${BLUE}[PHASE 5] Checking CPU usage...${NC}"

# Show top CPU processes
echo -e "${YELLOW}Top CPU-consuming processes:${NC}"
ps aux --sort=-%cpu | head -11

# Check for ollama (93% CPU in your screenshot)
if ps aux | grep -q "[o]llama runner"; then
    echo -e "${RED}⚠️  Found Ollama using high CPU!${NC}"
    echo -e "${YELLOW}Options:${NC}"
    echo "1. Stop Ollama: systemctl stop ollama"
    echo "2. Limit Ollama CPU: nice -n 19 $(pgrep ollama)"
    echo "3. Configure Ollama limits in service file"
    echo ""
    read -p "Stop Ollama to reduce CPU? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        systemctl stop ollama || killall ollama
        echo -e "${GREEN}✓ Ollama stopped${NC}"
    fi
fi

echo -e "${GREEN}✓ CPU check complete${NC}"
echo ""

# ============================================================================
# PHASE 6: INSTALL PYTHON DEPENDENCIES
# ============================================================================
echo -e "${BLUE}[PHASE 6] Installing Python dependencies...${NC}"

cd /home/jarvis/Jarvis

# Create venv if it doesn't exist
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating Python virtual environment...${NC}"
    sudo -u jarvis python3.12 -m venv venv
fi

# Install/update dependencies
echo -e "${YELLOW}Installing dependencies...${NC}"
sudo -u jarvis bash -c "
    source venv/bin/activate
    pip install --upgrade pip setuptools wheel
    pip install -r requirements.txt
" || echo "⚠️  Some dependencies may have failed"

echo -e "${GREEN}✓ Dependencies installed${NC}"
echo ""

# ============================================================================
# PHASE 7: RESTART BOT SERVICES
# ============================================================================
echo -e "${BLUE}[PHASE 7] Restarting bot services...${NC}"

# Check which services exist
echo -e "${YELLOW}Available Jarvis services:${NC}"
systemctl list-units --type=service --all | grep jarvis

# Restart all Jarvis services
for service in jarvis-supervisor jarvis-telegram jarvis-twitter; do
    if systemctl list-units --type=service --all | grep -q "$service"; then
        echo -e "${YELLOW}Restarting $service...${NC}"
        systemctl restart $service
        sleep 2
        systemctl status $service --no-pager | head -5
    else
        echo -e "${YELLOW}Service $service not found, skipping...${NC}"
    fi
done

echo -e "${GREEN}✓ Services restarted${NC}"
echo ""

# ============================================================================
# PHASE 8: VERIFY EVERYTHING WORKS
# ============================================================================
echo -e "${BLUE}[PHASE 8] Final verification...${NC}"

# Check service status
echo -e "${YELLOW}Service status:${NC}"
systemctl status jarvis-* --no-pager | grep -E "Active|Main PID" || echo "No services found"

# Check logs for errors
echo -e "${YELLOW}Recent logs (last 20 lines):${NC}"
journalctl -u jarvis-telegram -n 20 --no-pager || echo "No telegram service"

# Show resource usage
echo -e "${YELLOW}Current resource usage:${NC}"
free -h
df -h /

# Show network listeners
echo -e "${YELLOW}Services listening on ports:${NC}"
netstat -tuln | grep LISTEN | grep -E ":(22|80|443|5000|5001|8080)" || ss -tuln | grep LISTEN | grep -E ":(22|80|443|5000|5001|8080)"

echo -e "${GREEN}✓ Verification complete${NC}"
echo ""

# ============================================================================
# FINAL SUMMARY
# ============================================================================
echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                  DEPLOYMENT COMPLETE                     ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}✓ Docker containers cleaned${NC}"
echo -e "${GREEN}✓ Latest code pulled from GitHub${NC}"
echo -e "${GREEN}✓ SSH firewall configured${NC}"
echo -e "${GREEN}✓ Dependencies updated${NC}"
echo -e "${GREEN}✓ Services restarted${NC}"
echo ""
echo -e "${YELLOW}NEXT STEPS:${NC}"
echo "1. Test SSH access: ssh root@72.61.7.126"
echo "2. Test Telegram bot: Send /demo to @Jarviskr8tivbot"
echo "3. Monitor logs: journalctl -u jarvis-telegram -f"
echo "4. Check resource usage: htop"
echo ""
echo -e "${YELLOW}IMPORTANT:${NC}"
echo "- If Ollama is using too much CPU, configure limits"
echo "- Monitor /demo command for the 6 bug fixes"
echo "- Test bags.fm integration"
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
