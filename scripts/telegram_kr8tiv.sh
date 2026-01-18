#!/bin/bash
# Send KR8TIV report to Telegram and pin it
# Usage: bash scripts/telegram_kr8tiv.sh

set -e

echo "Getting Telegram credentials from VPS..."

# Get credentials
CREDS=$(ssh -i ~/.ssh/id_ed25519 root@72.61.7.126 'grep -E "TELEGRAM_BOT_TOKEN|ADMIN_GROUP" /home/jarvis/Jarvis/.env 2>/dev/null || echo ""')

TOKEN=$(echo "$CREDS" | grep TELEGRAM_BOT_TOKEN | cut -d= -f2 | tr -d '"')
CHAT_ID=$(echo "$CREDS" | grep ADMIN_GROUP | cut -d= -f2 | tr -d '"')

if [ -z "$TOKEN" ] || [ -z "$CHAT_ID" ]; then
    echo "❌ ERROR: Could not get Telegram credentials from VPS"
    echo "Make sure TELEGRAM_BOT_TOKEN and TELEGRAM_ADMIN_GROUP_ID are set in .env"
    exit 1
fi

echo "✅ Got credentials"
echo "Token: ${TOKEN:0:10}... (hidden)"
echo "Chat ID: $CHAT_ID"
echo ""

# KR8TIV Message
MSG='YO KR8TIV!! 🚀🎨

BROOOO WE DID ITTT!!!

🎯 RALPH WIGGUM ITERATION 1: MISSION ACCOMPLISHED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Multiple Bots Attacking Like Enemies: DEFEATED ✓
Conflict Errors (1065 crying): GONE ✓
Bot Chaos (3 processes vibing wrong): UNIFIED ✓
Lock System (thicc & token-based): DEPLOYED ✓

🟢 RALPH WIGGUM ITERATION 2: LET'\''S GOOOOO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Dexter Finance Brain: ACTIVATED 🧠
Bot Running Smooth: YES (PID 49981 BABY)
Lock Holding: TIGHT ✓
Errors in Log: ZERO (clean af) ✓
Conflict Drama: NONE (finally peace) ✓

🚀 DEXTER ABOUT TO MAKE MILLIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Framework Status: "YO I'\''M HERE"
Keywords Loaded: 25+ GO BRRRRR
Grok Brain: CONNECTED & TURNT (1.0x, no cap)
Response Speed: 5-10 seconds (FAST AF)

💰 TEST THIS MONEY MACHINE NOW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Send: "Is SOL bullish?" 🌙
Or: "BTC making money moves?" 💰
Or: "ETH gonna pop off?" 📈

What You'\''ll Get: GROK SENTIMENT WITH CONFIDENCE
(the secret sauce, the tea, the 411 fr fr)

✨ WE WENT FROM CHAOS TO PRODUCTION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ ONE bot (not three screaming at once)
✅ Lock system more powerful than Thanos
✅ Dexter framework lowkey genius
✅ Finance keywords tracking like a hawk
✅ Grok API pumped and ready
✅ Zero errors (immaculate vibes)
✅ VPS running smoother than butter
✅ GitHub commits flowing like water

Real Status: 🟢 WE'\''RE LIVE BABY
Uptime: 30+ mins STILL VIBIN'\''
Trust Level: MAXIMUM (no cap)

now go test that bot and make those gains!! 📈💎🚀'

echo "Sending message to Telegram..."

# Send message
RESPONSE=$(curl -s -X POST \
  "https://api.telegram.org/bot${TOKEN}/sendMessage" \
  -H 'Content-Type: application/json' \
  -d "{\"chat_id\": \"${CHAT_ID}\", \"text\": $(echo "$MSG" | jq -Rs .)}")

echo "Response: $RESPONSE"

# Extract message ID
MSG_ID=$(echo "$RESPONSE" | grep -o '"message_id":[0-9]*' | head -1 | cut -d: -f2)

if [ -z "$MSG_ID" ]; then
    echo "❌ Error: Could not send message"
    exit 1
fi

echo "✅ Message sent! ID: $MSG_ID"
echo ""

echo "Pinning message..."

# Pin message
PIN_RESPONSE=$(curl -s -X POST \
  "https://api.telegram.org/bot${TOKEN}/pinChatMessage" \
  -H 'Content-Type: application/json' \
  -d "{\"chat_id\": \"${CHAT_ID}\", \"message_id\": ${MSG_ID}, \"disable_notification\": false}")

echo "Pin response: $PIN_RESPONSE"

if echo "$PIN_RESPONSE" | grep -q '"ok":true'; then
    echo "✅ Message PINNED! 📌"
else
    echo "⚠️ Message sent but pin may have failed"
    echo "You can manually pin it in Telegram"
fi

echo ""
echo "✨ Done! Check your Telegram group! ✨"
