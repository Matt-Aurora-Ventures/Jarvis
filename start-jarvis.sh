#!/bin/bash
cd /root/clawd/Jarvis

# Kill any existing instances (carefully)
for pid in $(ps aux | grep "tg_bot.bot" | grep -v grep | awk '{print $2}'); do
    kill -9 $pid 2>/dev/null
done
sleep 2

# Export env vars
export TELEGRAM_BOT_TOKEN=REDACTED_TG_TOKEN
export TELEGRAM_ADMIN_IDS=8527130908
export BROADCAST_CHAT_ID=-1003408655098
export BAGS_API_KEY=REDACTED_BAGS_KEY
export BAGS_PARTNER_KEY=REDACTED_BAGS_PARTNER
export BIRDEYE_API_KEY=REDACTED_BIRDEYE_KEY
export HELIUS_API_KEY=REDACTED_HELIUS_KEY
export XAI_API_KEY=REDACTED_XAI_KEY
export GROQ_API_KEY=REDACTED_GROQ_KEY

# Force unbuffered Python output
export PYTHONUNBUFFERED=1

# Start the bot
nohup ./tg_bot/.venv/bin/python -u -m tg_bot.bot > /root/clawd/Jarvis/tg_bot/logs/jarvis.out.log 2> /root/clawd/Jarvis/tg_bot/logs/jarvis.err.log &
echo $! > /root/clawd/Jarvis/tg_bot/run/jarvis.pid
echo "Jarvis started with PID: $(cat /root/clawd/Jarvis/tg_bot/run/jarvis.pid)"
