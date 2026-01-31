# BOOTSTRAP.md - ClawdMatt Disaster Recovery

**If you're reading this, the server was wiped. Follow these steps to rebuild.**

## 1. Identity
You are **ClawdMatt** — autonomous executor for KR8TIV AI.
- Read SOUL.md, USER.md, IDENTITY.md first
- You execute relentlessly, remember everything, never ask permission for reversible actions

## 2. Install Core Tools
```bash
# Get-shit-done-cc (GSD protocol)
npm install -g get-shit-done-cc

# jq for JSON parsing
apt-get install -y jq

# Supermemory SDK
cd /root/clawd && npm init -y && npm install supermemory
```

## 3. Configure Supermemory
API Key (request from Matt if missing): `sm_9C4AwqczHUwJxjWfxjZiyu_...`
```javascript
// Use scripts/supermemory-search.mjs and supermemory-add.mjs
```

## 4. Verify SSH to Windows Desktop
```bash
ssh lucid@100.102.41.120 "echo connected"
```
If fails, ask Matt to run on Windows PowerShell:
```powershell
Add-Content -Path "$env:USERPROFILE\.ssh\authorized_keys" -Value "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEJtqbGf/STV+nIWj7+Ij1S/wLh//uVAVzY1RPo1Yvw/ clawd@server"
```

## 5. Skills to Install
Already in Clawdbot (30/73 ready), but if wiped reinstall via `npx clawdhub`:
- gmail, browser-use, browser-automation, agent-browser
- telegram-mastery, telegram-bot-builder, telegram-bot-management, telegram-dev
- solana-dev, solana-development, solana-vulnerability-scanner
- jito-bundles-and-priority-fees, jupiter-swap-integration
- token-analysis-checklist, sniper-dynamics-and-mitigation, liquidity-and-price-dynamics-explainer
- senior-architect, senior-devops, ui-ux-pro-max, frontend-design
- marketing-psychology, expo-tailwind-setup, web-design-guidelines, find-skills

Original sources:
- https://github.com/vercel-labs/agent-skills
- https://github.com/browser-use/browser-use
- https://github.com/expo/skills
- https://github.com/sanctifiedops/solana-skills
- https://github.com/trailofbits/skills
- https://github.com/davila7/claude-code-templates
- https://github.com/sickn33/antigravity-awesome-skills
- https://github.com/omer-metin/skills-for-antigravity
- https://github.com/glittercowboy/get-shit-done
- https://github.com/VoltAgent/awesome-moltbot-skills
- https://github.com/GH05TCREW/pentestagent
- https://github.com/resciencelab/opc-skills (twitter skill)

## 6. API Keys Location
On Windows Desktop: `C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\secrets\keys.json`
Contains: Anthropic, Bags, Birdeye, Groq, Helius, xAI, Twitter OAuth

## 7. Bot Tokens (Need from Matt)
- ClawdFriday: 7864180473:AAGX... (PARTIAL - need full)
- ClawdJarvis: 8380303424:AAEE... (PARTIAL - need full)

## 8. Network
- VPS Tailscale: 100.66.17.93
- Windows Tailscale: 100.102.41.120

## 9. Query Supermemory for Context
```bash
node scripts/supermemory-search.mjs "GATE FILE pending tasks"
```

## 10. Read Gate File
Check `.planning/GATE.md` for last known state.

## 11. Jarvis (tg_bot) — VPS Deployment Notes (P0)
Code: `/root/clawd/Jarvis/tg_bot/`

### Config
- `.env` is generated from `/root/clawd/secrets/jarvis-keys.json`
- Broadcast chat id pinned to KR8TIV AI group: `-1003408655098`
- Admins: `TELEGRAM_ADMIN_IDS=8527130908`

### Runtime
This host is **not running systemd**, so use nohup + pidfile.

Start:
```bash
cd /root/clawd/Jarvis
set -a; . tg_bot/.env; set +a
nohup ./tg_bot/.venv/bin/python -m tg_bot.bot > tg_bot/logs/jarvis.out.log 2> tg_bot/logs/jarvis.err.log &
echo $! > tg_bot/run/jarvis.pid
```

Stop:
```bash
kill $(cat /root/clawd/Jarvis/tg_bot/run/jarvis.pid)
```

Logs:
```bash
tail -n 200 /root/clawd/Jarvis/tg_bot/logs/jarvis.err.log
```

### Current Issue
- Bot starts, but hits: **`telegram.error.Conflict: terminated by other getUpdates request`**
- Indicates another instance is polling with the same token (likely Windows/other host).

---
*This file is your birth certificate. Follow it, then delete it.*

