# TOOLS.md - Local Environment Notes

## Infrastructure

### VPS (This Server)
- **Tailscale IP**: 100.66.17.93
- **Workspace**: `/root/clawd/`
- **Jarvis Code**: `/root/clawd/Jarvis/tg_bot/`

### Windows Desktop
- **Tailscale IP**: 100.102.41.120
- **User**: lucid
- **SSH**: `ssh lucid@100.102.41.120`
- **Projects**: `C:\Users\lucid\OneDrive\Desktop\Projects\`

---

## Chrome CDP Browser Control

⚠️ **CRITICAL: Use CDP only. Never ask for browser extensions.**

### Setup SSH Tunnel (if not already running)
```bash
ssh -f -N -L 9222:127.0.0.1:9222 lucid@100.102.41.120
```

### Control Script
```bash
# List open tabs
node /root/clawd/scripts/chrome-control.mjs list

# Navigate to URL
node /root/clawd/scripts/chrome-control.mjs goto "https://example.com"

# Take screenshot
node /root/clawd/scripts/chrome-control.mjs screenshot

# Execute JavaScript
node /root/clawd/scripts/chrome-control.mjs eval "document.title"
```

### Verify Connection
```bash
curl http://127.0.0.1:9222/json/list
```

### Human-Like Automation (CRITICAL)
When automating browsers, avoid bot detection:
- **Delays**: 2-5 seconds between actions (randomize)
- **Typing**: 50-150ms between keystrokes
- **Mouse**: Move to element before clicking
- **Sessions**: Check existing cookies first

---

## Useful Scripts

| Script | Purpose |
|--------|---------|
| `/root/clawd/scripts/chrome-control.mjs` | CDP browser control |
| `/root/clawd/scripts/bags-watcher.mjs` | Monitor bags.fm tokens |
| `/root/clawd/scripts/supermemory-search.mjs` | Search Supermemory |
| `/root/clawd/scripts/supermemory-add.mjs` | Add to Supermemory |
| `/root/clawd/scripts/backup-full.sh` | Full VPS backup |

---

## Telegram Groups

| Group | ID | Topic |
|-------|-----|-------|
| KR8TIV AI - Jarvis Life OS | -1003408655098 | General: 22552 |

---

## Social Accounts (Official)

- **Matt Personal X**: @aurora_ventures
- **KR8TIV AI X**: @kr8tivai
- **Jarvis X**: @jarvis_lifeos

---

## Running Jarvis Bot

### Start
```bash
cd /root/clawd/Jarvis
set -a; . tg_bot/.env; set +a
nohup ./tg_bot/.venv/bin/python -m tg_bot.bot > tg_bot/logs/jarvis.out.log 2>&1 &
echo $! > tg_bot/run/jarvis.pid
```

### Stop
```bash
kill $(cat /root/clawd/Jarvis/tg_bot/run/jarvis.pid)
```

### Logs
```bash
tail -f /root/clawd/Jarvis/tg_bot/logs/jarvis.err.log
```

---

## Environment Setup

Jarvis .env location: `/root/clawd/Jarvis/tg_bot/.env`

Required vars:
- `TELEGRAM_BOT_TOKEN`
- `ANTHROPIC_API_KEY`
- `HELIUS_API_KEY`
- `BIRDEYE_API_KEY`
- `BAGS_API_KEY`
- `TELEGRAM_ADMIN_IDS=8527130908`
- `BROADCAST_CHAT_ID=-1003408655098`

---

## Add your own notes below...

