#!/bin/bash
# Bot Token Deployment Script (Bash version)
# Deploys all corrected bot tokens to VPS servers
# Date: 2026-01-31

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
GRAY='\033[0;37m'
NC='\033[0m' # No Color

# Parse arguments
DRY_RUN=false
SKIP_BACKUP=false
VPS1_ONLY=false
VPS2_ONLY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run) DRY_RUN=true; shift ;;
        --skip-backup) SKIP_BACKUP=true; shift ;;
        --vps1-only) VPS1_ONLY=true; shift ;;
        --vps2-only) VPS2_ONLY=true; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

echo -e "${CYAN}\n=== BOT TOKEN DEPLOYMENT SCRIPT ===${NC}"
echo -e "${GRAY}Date: $(date '+%Y-%m-%d %H:%M:%S')${NC}"
echo ""

# VPS1 configuration (Main Jarvis)
VPS1_IP="72.61.7.126"
VPS1_ENV_PATH="/home/jarvis/Jarvis/lifeos/config/.env"
declare -A VPS1_TOKENS=(
    ["TREASURY_BOT_TOKEN"]="***TREASURY_BOT_TOKEN_REDACTED***"
    ["X_BOT_TELEGRAM_TOKEN"]="7968869100:AAEan4TRjH4eHIOGvssn6BV71ChsuPrz6Hc"
)

# VPS2 configuration (ClawdBots)
VPS2_IP="76.13.106.100"
VPS2_ENV_PATH="/root/clawdbots/tokens.env"
declare -A VPS2_TOKENS=(
    ["CLAWDMATT_BOT_TOKEN"]="8288059637:AAHbcATe1mgMBGKuf5ceYFpyVpO2rzXYFq4"
    ["CLAWDFRIDAY_BOT_TOKEN"]="7864180473:AAHN9ROzOdtHRr5JXw1iTDpMYQitGEh-Bu4"
    ["CLAWDJARVIS_BOT_TOKEN"]="8434411668:AAHNGOzjHI-rYwBZ2mIM2c7cbZmLGTjekJ4"
)

deploy_to_vps() {
    local VPS_IP=$1
    local ENV_PATH=$2
    local VPS_NAME=$3
    shift 3
    local -n TOKENS=$1

    echo -e "${YELLOW}\n--- Deploying to $VPS_NAME ($VPS_IP) ---${NC}"

    # Test SSH connection
    echo -e "${GRAY}Testing SSH connection...${NC}"
    if ! ssh -o ConnectTimeout=5 root@$VPS_IP "echo 'Connected'" > /dev/null 2>&1; then
        echo -e "${RED}[ERROR] Cannot connect to $VPS_IP via SSH${NC}"
        echo -e "${RED}  Make sure SSH is configured and the VPS is online${NC}"
        return 1
    fi
    echo -e "${GREEN}[OK] SSH connection successful${NC}"

    # Backup current .env
    if [ "$SKIP_BACKUP" = false ]; then
        echo -e "${GRAY}Creating backup of .env file...${NC}"
        local BACKUP_CMD="cp $ENV_PATH ${ENV_PATH}.backup-\$(date +%Y%m%d_%H%M%S)"
        if [ "$DRY_RUN" = true ]; then
            echo -e "${YELLOW}[DRY RUN] Would run: $BACKUP_CMD${NC}"
        else
            if ssh root@$VPS_IP "$BACKUP_CMD" 2>/dev/null; then
                echo -e "${GREEN}[OK] Backup created${NC}"
            else
                echo -e "${YELLOW}[WARN] Backup failed (file may not exist yet)${NC}"
            fi
        fi
    fi

    # Deploy each token
    for TOKEN_NAME in "${!TOKENS[@]}"; do
        local TOKEN_VALUE="${TOKENS[$TOKEN_NAME]}"
        echo -e "\n${GRAY}Deploying $TOKEN_NAME...${NC}"

        # Check if token already exists
        local TOKEN_STATUS=$(ssh root@$VPS_IP "grep -q '^${TOKEN_NAME}=' $ENV_PATH && echo 'EXISTS' || echo 'NEW'" 2>/dev/null)

        if [ "$TOKEN_STATUS" = "EXISTS" ]; then
            echo -e "${GRAY}  Token exists - updating...${NC}"
            local DEPLOY_CMD="sed -i 's~^${TOKEN_NAME}=.*~${TOKEN_NAME}=${TOKEN_VALUE}~' $ENV_PATH"
        else
            echo -e "${GRAY}  New token - appending...${NC}"
            local DEPLOY_CMD="echo '${TOKEN_NAME}=${TOKEN_VALUE}' >> $ENV_PATH"
        fi

        if [ "$DRY_RUN" = true ]; then
            echo -e "${YELLOW}[DRY RUN] Would run: $DEPLOY_CMD${NC}"
        else
            if ssh root@$VPS_IP "$DEPLOY_CMD"; then
                echo -e "${GREEN}  [OK] Token deployed${NC}"
            else
                echo -e "${RED}  [ERROR] Token deployment failed${NC}"
                return 1
            fi
        fi

        # Verify token
        local VERIFICATION=$(ssh root@$VPS_IP "grep '^${TOKEN_NAME}=' $ENV_PATH" 2>/dev/null)
        if [ -n "$VERIFICATION" ]; then
            echo -e "${GREEN}  [VERIFIED] $VERIFICATION${NC}"
        else
            echo -e "${RED}  [ERROR] Verification failed - token not found in .env${NC}"
            return 1
        fi
    done

    # Restart supervisor (VPS1 only)
    if [ "$VPS_NAME" = "VPS1" ] && [ "$DRY_RUN" = false ]; then
        echo -e "\n${GRAY}Restarting supervisor...${NC}"
        ssh root@$VPS_IP "pkill -f supervisor.py; sleep 2; cd /home/jarvis/Jarvis && nohup python bots/supervisor.py > logs/supervisor.log 2>&1 &"
        echo -e "${GREEN}[OK] Supervisor restarted${NC}"
        echo -e "${GRAY}  Monitor logs: ssh root@$VPS_IP 'tail -f /home/jarvis/Jarvis/logs/supervisor.log'${NC}"
    fi

    # Restart ClawdBots service (VPS2 only)
    if [ "$VPS_NAME" = "VPS2" ] && [ "$DRY_RUN" = false ]; then
        echo -e "\n${GRAY}Restarting ClawdBots service...${NC}"
        if ssh root@$VPS_IP "systemctl list-units --type=service | grep -q clawdbot" 2>/dev/null; then
            ssh root@$VPS_IP "systemctl restart clawdbot-gateway"
            echo -e "${GREEN}[OK] ClawdBots service restarted${NC}"
        else
            echo -e "${YELLOW}[WARN] No systemd service found - restart manually if needed${NC}"
        fi
    fi

    return 0
}

# Main execution
if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}[DRY RUN MODE] No changes will be made\n${NC}"
fi

SUCCESS=true

# Deploy to VPS1 (Main Jarvis)
if [ "$VPS2_ONLY" = false ]; then
    if ! deploy_to_vps "$VPS1_IP" "$VPS1_ENV_PATH" "VPS1" VPS1_TOKENS; then
        SUCCESS=false
    fi
fi

# Deploy to VPS2 (ClawdBots)
if [ "$VPS1_ONLY" = false ]; then
    if ! deploy_to_vps "$VPS2_IP" "$VPS2_ENV_PATH" "VPS2" VPS2_TOKENS; then
        SUCCESS=false
    fi
fi

# Final summary
echo -e "${CYAN}\n=== DEPLOYMENT SUMMARY ===${NC}"
if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}[DRY RUN] No actual changes were made${NC}"
    echo -e "${YELLOW}Run without --dry-run to deploy for real${NC}"
elif [ "$SUCCESS" = true ]; then
    echo -e "${GREEN}[SUCCESS] All tokens deployed successfully!${NC}"
    echo -e "\n${YELLOW}Next steps:${NC}"
    echo -e "${GRAY}1. Monitor VPS1 logs: ssh root@$VPS1_IP 'tail -f /home/jarvis/Jarvis/logs/supervisor.log'${NC}"
    echo -e "${GRAY}2. Check for 'Using unique X bot token' and 'Using unique treasury bot token'${NC}"
    echo -e "${GRAY}3. Verify no polling conflicts for 30+ minutes${NC}"
    echo -e "${GRAY}4. Test X bot posting to verify Telegram sync works${NC}"
else
    echo -e "${RED}[FAILED] Some deployments failed - check errors above${NC}"
fi

echo ""
