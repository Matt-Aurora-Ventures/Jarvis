#!/bin/bash
# Health Check Script for Jarvis VPS
# Verifies all components are running and configured correctly

echo "=== JARVIS VPS HEALTH CHECK ==="
echo "Timestamp: $(date)"
echo ""

# Check systemd services
echo "1. Systemd Services:"
echo "---------------------"
systemctl status jarvis-supervisor --no-pager | head -5
echo ""

# Check process tree under supervisor
echo "2. Supervisor Process Tree:"
echo "----------------------------"
ps aux | grep 'python.*supervisor\|telegram\|treasury\|twitter' | grep -v grep
echo ""

# Check Ollama
echo "3. Ollama Status:"
echo "----------------------------"
curl -s http://localhost:11434/api/tags | python3 -m json.tool | grep 'name\|size' | head -10
echo ""

# Check wallets
echo "4. Wallet Status:"
echo "----------------------------"
if [ -d "/home/jarvis/Jarvis/wallets" ]; then
  echo "✓ Wallets directory exists"
  ls -lah /home/jarvis/Jarvis/wallets/ | tail -5
else
  echo "✗ Wallets directory missing"
fi
echo ""

# Check Telegram bot
echo "5. Telegram Bot:"
echo "----------------------------"
tail -5 /home/jarvis/Jarvis/logs/telegram_bot.log 2>/dev/null || echo "No telegram logs"
echo ""

# Check for errors
echo "6. Recent Errors:"
echo "----------------------------"
grep -i error /home/jarvis/Jarvis/logs/supervisor.log | tail -5 2>/dev/null || echo "No recent errors"
echo ""

# Check AI configuration
echo "7. AI Configuration:"
echo "----------------------------"
grep 'OLLAMA.*MODEL\|ANTHROPIC' /home/jarvis/Jarvis/.env | grep -v '^#' | head -10
echo ""

echo "=== HEALTH CHECK COMPLETE ==="
