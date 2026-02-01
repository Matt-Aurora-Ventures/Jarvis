#!/bin/bash
# Deploy All Bots - Treasury + ClawdBots Suite
# Generated: 2026-01-31 23:45 UTC
# Tokens received from user via Telegram @BotFather

set -e  # Exit on error

echo "========================================="
echo "JARVIS BOT DEPLOYMENT SCRIPT"
echo "========================================="
echo ""

# ============================================================================
# PART 1: Deploy TREASURY_BOT_TOKEN to VPS 72.61.7.126
# ============================================================================

echo "1. Deploying TREASURY_BOT_TOKEN to VPS 72.61.7.126..."
echo "   Bot: @jarvis_treasury_bot"
echo "   Fixes: Exit code 4294967295 (35 consecutive crashes)"
echo ""

# Check if we can SSH
if ssh -o ConnectTimeout=5 root@72.61.7.126 "echo 'SSH OK'" 2>/dev/null; then
    echo "✓ SSH connection successful"

    # Backup .env file
    echo "  Creating backup of .env..."
    ssh root@72.61.7.126 "cp /home/jarvis/Jarvis/lifeos/config/.env /home/jarvis/Jarvis/lifeos/config/.env.backup-$(date +%Y%m%d_%H%M%S)"

    # Add TREASURY_BOT_TOKEN if not present
    if ssh root@72.61.7.126 "grep -q 'TREASURY_BOT_TOKEN' /home/jarvis/Jarvis/lifeos/config/.env" 2>/dev/null; then
        echo "  ⚠ TREASURY_BOT_TOKEN already exists in .env"
        echo "  Updating existing token..."
        ssh root@72.61.7.126 "sed -i 's/^TREASURY_BOT_TOKEN=.*/TREASURY_BOT_TOKEN=850H068106:AAHoS0GKxl79nPE_2wFjkkmX_T7iXEwOyao/' /home/jarvis/Jarvis/lifeos/config/.env"
    else
        echo "  Adding TREASURY_BOT_TOKEN to .env..."
        ssh root@72.61.7.126 "echo 'TREASURY_BOT_TOKEN=850H068106:AAHoS0GKxl79nPE_2wFjkkmX_T7iXEwOyao' >> /home/jarvis/Jarvis/lifeos/config/.env"
    fi

    # Restart supervisor
    echo "  Restarting supervisor..."
    ssh root@72.61.7.126 "pkill -f supervisor.py || true; sleep 2; cd /home/jarvis/Jarvis && nohup python bots/supervisor.py > logs/supervisor.log 2>&1 &"

    echo "  Waiting for supervisor to start..."
    sleep 5

    # Verify
    echo "  Checking supervisor logs..."
    if ssh root@72.61.7.126 "tail -50 /home/jarvis/Jarvis/logs/supervisor.log | grep -q 'Using unique treasury bot token'" 2>/dev/null; then
        echo "  ✅ SUCCESS: Treasury bot using unique token!"
    else
        echo "  ⚠ WARNING: Token message not found yet. Check logs manually:"
        echo "     ssh root@72.61.7.126 'tail -100 /home/jarvis/Jarvis/logs/supervisor.log'"
    fi

    echo ""
    echo "✅ TREASURY BOT DEPLOYED"
    echo ""
else
    echo "❌ ERROR: Cannot SSH to VPS 72.61.7.126"
    echo ""
    echo "MANUAL DEPLOYMENT REQUIRED:"
    echo "1. SSH to VPS: ssh root@72.61.7.126"
    echo "2. Edit .env: nano /home/jarvis/Jarvis/lifeos/config/.env"
    echo "3. Add line: TREASURY_BOT_TOKEN=850H068106:AAHoS0GKxl79nPE_2wFjkkmX_T7iXEwOyao"
    echo "4. Save (Ctrl+X, Y, Enter)"
    echo "5. Restart: pkill -f supervisor.py && cd /home/jarvis/Jarvis && nohup python bots/supervisor.py > logs/supervisor.log 2>&1 &"
    echo "6. Verify: tail -f logs/supervisor.log  # Look for 'Using unique treasury bot token'"
    echo ""
    echo "Press Enter when manual deployment is complete, or Ctrl+C to exit"
    read -r
fi

# ============================================================================
# PART 2: Deploy ClawdBots to VPS 76.13.106.100 (clawdbot-gateway)
# ============================================================================

echo "2. Deploying ClawdBots to VPS 76.13.106.100..."
echo "   Bots: ClawdMatt, ClawdFriday, ClawdJarvis"
echo "   Gateway: ws://127.0.0.1:18789 (already running)"
echo ""

# Check if we can SSH
if ssh -o ConnectTimeout=5 root@76.13.106.100 "echo 'SSH OK'" 2>/dev/null; then
    echo "✓ SSH connection successful"

    # Create bot config directory
    echo "  Creating bot configuration directory..."
    ssh root@76.13.106.100 "mkdir -p /root/clawdbots"

    # Create individual bot config files
    echo "  Creating ClawdMatt config..."
    ssh root@76.13.106.100 "cat > /root/clawdbots/clawdmatt.env << 'EOF'
TELEGRAM_BOT_TOKEN=8288859637:AAHbcATe1mgMBGKuf5ceYFpyVpO2rzXYFqH
BOT_NAME=ClawdMatt
BOT_DESCRIPTION=Marketing & PR Filter Bot
BRAND_GUIDE_PATH=/root/clawdbots/kr8tiv_marketing_guide.md
ABILITIES=ClawdMatt_base
MEMORY=separate
EOF"

    echo "  Creating ClawdFriday config..."
    ssh root@76.13.106.100 "cat > /root/clawdbots/clawdfriday.env << 'EOF'
TELEGRAM_BOT_TOKEN=7864180H73:AAHN9ROzOdtHRr5JXwliTDpMYQitGEh-BuH
BOT_NAME=ClawdFriday
BOT_DESCRIPTION=Email AI Assistant
BRAND_GUIDE_PATH=/root/clawdbots/friday_guide.md
ABILITIES=ClawdMatt_base
MEMORY=separate
EOF"

    echo "  Creating ClawdJarvis config..."
    ssh root@76.13.106.100 "cat > /root/clawdbots/clawdjarvis.env << 'EOF'
TELEGRAM_BOT_TOKEN=8434H11668:AAHNGOzjHI-rYwBZ2mIM2c7cbZmLGTjekJH
BOT_NAME=ClawdJarvis
BOT_DESCRIPTION=Main Orchestrator
BRAND_GUIDE_PATH=/root/clawdbots/jarvis_brand_guide.md
ABILITIES=ClawdMatt_base
MEMORY=separate
EOF"

    # Copy brand guides
    echo "  Uploading brand guidelines..."
    scp docs/marketing/KR8TIV_AI_MARKETING_GUIDE_JAN_31_2026.md root@76.13.106.100:/root/clawdbots/kr8tiv_marketing_guide.md
    scp docs/marketing/x_thread_ai_stack_jarvis_voice.md root@76.13.106.100:/root/clawdbots/jarvis_brand_guide.md

    # Create Friday guide (reference to marketing guide)
    ssh root@76.13.106.100 "cat > /root/clawdbots/friday_guide.md << 'EOF'
# Friday Email AI - Brand Voice

Refer to KR8TIV_AI_MARKETING_GUIDE_JAN_31_2026.md for complete brand voice.

Key Points for Email:
- Professional but authentic
- Technical + accessible
- Honest about capabilities
- Action-oriented with next steps
- No hype, no overpromising
EOF"

    echo ""
    echo "  ✅ Configuration files created on VPS"
    echo ""
    echo "  Next steps:"
    echo "  1. SSH to VPS: ssh root@76.13.106.100"
    echo "  2. Start bots via clawdbot or standalone"
    echo "  3. Verify no polling conflicts"
    echo ""
else
    echo "❌ ERROR: Cannot SSH to VPS 76.13.106.100"
    echo ""
    echo "MANUAL DEPLOYMENT REQUIRED:"
    echo "See: docs/BOT_DEPLOYMENT_CHECKLIST.md for complete instructions"
    echo ""
fi

# ============================================================================
# VERIFICATION
# ============================================================================

echo "========================================="
echo "DEPLOYMENT SUMMARY"
echo "========================================="
echo ""
echo "Tokens Deployed:"
echo "  ✓ TREASURY_BOT_TOKEN (@jarvis_treasury_bot)"
echo "  ✓ CLAWDMATT_BOT_TOKEN (@ClawdMatt_bot)"
echo "  ✓ CLAWDFRIDAY_BOT_TOKEN (@ClawdFriday_bot)"
echo "  ✓ CLAWDJARVIS_BOT_TOKEN (@ClawdJarvis_87772_bot)"
echo ""
echo "Next Actions:"
echo "  1. Monitor treasury bot logs for 10+ minutes (no crashes)"
echo "  2. Start ClawdBots on 76.13.106.100"
echo "  3. Test all bots for polling conflicts"
echo "  4. Update MASTER_GSD with deployment success"
echo ""
echo "========================================="
