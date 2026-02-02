#!/bin/bash
# Extract New Treasury Wallet from VPS
# Run this when you have access to the main Jarvis VPS (72.61.7.126)

VPS_IP="72.61.7.126"
NEW_TREASURY="57w9GUzRwXim3nh13R7WtFbpHzUcyKHTtjcTv8cuFoqN"

echo "======================================================================="
echo "EXTRACTING NEW TREASURY WALLET FROM VPS"
echo "======================================================================="
echo ""
echo "Connecting to VPS: $VPS_IP"
echo "Target wallet: $NEW_TREASURY"
echo ""

# Test connection
if ! ssh root@$VPS_IP "echo 'Connected'" 2>/dev/null; then
    echo "[ERROR] Cannot connect to VPS"
    echo "Try: ssh root@$VPS_IP"
    exit 1
fi

echo "[OK] Connected to VPS"
echo ""

# Search for wallet files
echo "Searching for wallet files..."
echo ""

# Check common locations
ssh root@$VPS_IP << 'ENDSSH'
    echo "1. Checking /home/jarvis/Jarvis/data/"
    find /home/jarvis/Jarvis/data -name "*treasury*.json" -o -name "*57w9*.json" 2>/dev/null

    echo ""
    echo "2. Checking /home/jarvis/Jarvis/bots/treasury/.wallets/"
    ls -la /home/jarvis/Jarvis/bots/treasury/.wallets/*.json 2>/dev/null
    ls -la /home/jarvis/Jarvis/bots/treasury/.wallets/*.key 2>/dev/null

    echo ""
    echo "3. Checking wallet registry..."
    if [ -f /home/jarvis/Jarvis/bots/treasury/.wallets/registry.json ]; then
        cat /home/jarvis/Jarvis/bots/treasury/.wallets/registry.json
    fi

    echo ""
    echo "4. Searching for wallet by address..."
    find /home/jarvis/Jarvis -name "*57w9*.json" -o -name "*57w9*.key" 2>/dev/null

    echo ""
    echo "5. Checking logs for wallet generation..."
    grep -r "57w9GUzRw\|generated.*wallet\|created.*wallet" /home/jarvis/Jarvis/logs/ 2>/dev/null | tail -20
ENDSSH

echo ""
echo "-----------------------------------------------------------------------"
echo "If wallet files found above, download them:"
echo ""
echo "  scp root@$VPS_IP:/path/to/wallet.json ./new_treasury_wallet.json"
echo ""
echo "Then decrypt using:"
echo "  python scripts/decrypt_treasury_keys.py"
echo ""
echo "======================================================================="
