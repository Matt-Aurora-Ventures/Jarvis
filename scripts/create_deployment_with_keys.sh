#!/bin/bash
# VPS Deployment Script Generator with Key Injection
# This script helps you create a custom deployment script with your API keys baked in
# Usage: bash scripts/create_deployment_with_keys.sh

set -e

echo "========================================"
echo "JARVIS VPS DEPLOYMENT SCRIPT GENERATOR"
echo "========================================"
echo ""
echo "This will create a custom deployment script with your API keys."
echo "Keep this custom script private - never commit it to Git!"
echo ""

# Check if we have the template
if [ ! -f "vps-deploy-with-keys.sh" ]; then
    echo "ERROR: vps-deploy-with-keys.sh not found. Run from Jarvis directory."
    exit 1
fi

# Function to read key with prompts
read_key() {
    local prompt=$1
    local default=$2
    local key=""

    if [ -z "$default" ]; then
        read -p "$prompt: " key
    else
        read -p "$prompt [$default]: " key
        if [ -z "$key" ]; then
            key=$default
        fi
    fi

    echo "$key"
}

echo "========================================"
echo "GATHERING API KEYS"
echo "========================================"
echo ""
echo "Leave blank to use REPLACEME (you'll update on VPS later)"
echo ""

# Read API keys
ANTHROPIC=$(read_key "Anthropic API Key (sk-ant-...)" "sk-ant-REPLACEME")
XAI=$(read_key "XAI/Grok API Key" "REPLACEME")

# Groq key
GROQ=$(read_key "Groq API Key" "REPLACEME")
MINIMAX=$(read_key "MiniMax API Key" "REPLACEME")
BIRDEYE=$(read_key "BirdEye API Key" "REPLACEME")
HELIUS=$(read_key "Helius API Key" "REPLACEME")

echo ""
echo "Twitter/X API Credentials (4 keys required):"
echo ""
TWITTER_API=$(read_key "  API Key (Consumer Key)" "REPLACEME")
TWITTER_SECRET=$(read_key "  API Secret (Consumer Secret)" "REPLACEME")
TWITTER_TOKEN=$(read_key "  Access Token (OAuth Token)" "REPLACEME")
TWITTER_TOKEN_SECRET=$(read_key "  Access Secret (OAuth Token Secret)" "REPLACEME")

echo ""
TELEGRAM=$(read_key "Telegram Bot Token" "REPLACEME")

echo ""
echo "========================================"
echo "SUMMARY"
echo "========================================"
echo ""
echo "API Keys being configured:"
echo "  ✓ Anthropic: $([ "$ANTHROPIC" != "sk-ant-REPLACEME" ] && echo "PROVIDED" || echo "PLACEHOLDER")"
echo "  ✓ XAI: $([ "$XAI" != "REPLACEME" ] && echo "PROVIDED" || echo "PLACEHOLDER")"
echo "  ✓ Groq: $([ "$GROQ" != "REPLACEME" ] && echo "PROVIDED" || echo "PLACEHOLDER")"
echo "  ✓ MiniMax: $([ "$MINIMAX" != "REPLACEME" ] && echo "PROVIDED" || echo "PLACEHOLDER")"
echo "  ✓ BirdEye: $([ "$BIRDEYE" != "REPLACEME" ] && echo "PROVIDED" || echo "PLACEHOLDER")"
echo "  ✓ Helius: $([ "$HELIUS" != "REPLACEME" ] && echo "PROVIDED" || echo "PLACEHOLDER")"
echo "  ✓ Twitter API: $([ "$TWITTER_API" != "REPLACEME" ] && echo "PROVIDED" || echo "PLACEHOLDER")"
echo "  ✓ Telegram: $([ "$TELEGRAM" != "REPLACEME" ] && echo "PROVIDED" || echo "PLACEHOLDER")"
echo ""

read -p "Ready to generate deployment script? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
fi

# Create custom deployment script
OUTPUT_FILE="vps-deploy-custom-$(date +%s).sh"
cp vps-deploy-with-keys.sh "$OUTPUT_FILE"

# Replace placeholders
sed -i 's|"anthropic_api_key": "sk-ant-REPLACEME"|"anthropic_api_key": "'"$ANTHROPIC"'"|g' "$OUTPUT_FILE"
sed -i 's|"api_key": "REPLACEME"|"api_key": "'"$XAI"'"|g' "$OUTPUT_FILE"
sed -i 's|"groq_api_key": "REPLACEME"|"groq_api_key": "'"$GROQ"'"|g' "$OUTPUT_FILE"
sed -i 's|"minimax_api_key": "REPLACEME"|"minimax_api_key": "'"$MINIMAX"'"|g' "$OUTPUT_FILE"
sed -i 's|"birdeye_api_key": "REPLACEME"|"birdeye_api_key": "'"$BIRDEYE"'"|g' "$OUTPUT_FILE"
sed -i 's|"helius": {"api_key": "REPLACEME"}|"helius": {"api_key": "'"$HELIUS"'"}|g' "$OUTPUT_FILE"
sed -i 's|"api_key": "REPLACEME",|"api_key": "'"$TWITTER_API"'",|g' "$OUTPUT_FILE"
sed -i 's|"api_secret": "REPLACEME"|"api_secret": "'"$TWITTER_SECRET"'"|g' "$OUTPUT_FILE"
sed -i 's|"access_token": "REPLACEME"|"access_token": "'"$TWITTER_TOKEN"'"|g' "$OUTPUT_FILE"
sed -i 's|"access_secret": "REPLACEME"|"access_secret": "'"$TWITTER_TOKEN_SECRET"'"|g' "$OUTPUT_FILE"
sed -i 's|"bot_token": "REPLACEME"|"bot_token": "'"$TELEGRAM"'"|g' "$OUTPUT_FILE"

chmod +x "$OUTPUT_FILE"

echo ""
echo "========================================"
echo "✓ DEPLOYMENT SCRIPT GENERATED"
echo "========================================"
echo ""
echo "Custom script: $OUTPUT_FILE"
echo ""
echo "NEXT STEPS:"
echo "1. Copy this script to your VPS:"
echo "   scp $OUTPUT_FILE root@72.61.7.126:~/"
echo ""
echo "2. SSH into VPS and run it:"
echo "   ssh root@72.61.7.126"
echo "   bash $OUTPUT_FILE"
echo ""
echo "3. Keep this script private - DO NOT commit to Git"
echo ""
echo "========================================"
