#!/bin/bash
cd /root/clawd/Jarvis
pkill -f "tg_bot.bot" 2>/dev/null || true
sleep 1
nohup /root/clawd/Jarvis/tg_bot/.venv/bin/python -u -m tg_bot.bot >> /root/clawd/Jarvis/tg_bot/logs/jarvis.log 2>&1 &
echo $! > /root/clawd/Jarvis/tg_bot/jarvis.pid
echo "Started PID: $!"
