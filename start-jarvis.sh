#!/bin/bash
cd /root/clawd/Jarvis

# Kill any existing instances (carefully)
for pid in $(ps aux | grep "tg_bot.bot" | grep -v grep | awk '{print $2}'); do
    kill -9 $pid 2>/dev/null
done
sleep 2

# Load env vars from secrets (DO NOT commit secrets to git!)
source /root/clawd/Jarvis/.env.local

# Force unbuffered Python output
export PYTHONUNBUFFERED=1

# Start the bot
nohup ./tg_bot/.venv/bin/python -u -m tg_bot.bot > /root/clawd/Jarvis/tg_bot/logs/jarvis.out.log 2> /root/clawd/Jarvis/tg_bot/logs/jarvis.err.log &

echo "Jarvis started. Check logs at tg_bot/logs/"
