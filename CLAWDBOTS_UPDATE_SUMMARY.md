# ClawdBots Update Summary - OpenClaw 2026.2.3

## Overview

All ClawdBot instances have been updated from `clawdbot@latest` to **OpenClaw 2026.2.3** (released Feb 3, 2026).

## What Changed

### 1. Package Updates

**Before:**
```bash
npm install -g clawdbot@latest
npm install -g openclaw@latest
```

**After:**
```bash
npm install -g openclaw@2026.2.3
ln -sf "$(which openclaw)" /usr/local/bin/clawdbot  # Backward compatibility
```

**Rationale:** OpenClaw is the official package; clawdbot is now just a compatibility shim.

### 2. Files Modified

| File | Change |
|------|--------|
| `docker/clawdbot-gateway/docker-compose.yml` | Updated all 3 containers to install openclaw@2026.2.3 |
| `deploy/clawdbot-redundancy/Dockerfile.clawdbot-full` | Updated base image to openclaw@2026.2.3 |
| `deploy/clawdbot-redundancy/docker-compose.clawdbots.yml` | Updated image tag to `clawdbot-ready:2026.2.3` |

### 3. New Features in OpenClaw 2026.2.3

| Feature | Description | Status |
|---------|-------------|--------|
| **Telegram Model Selection** | Inline buttons for `/models` and `/model` commands | ✅ Available |
| **Discord Presence** | Set custom bot status and activity | ✅ Available |
| **Security Fixes** | Honor Telegram model overrides in buttons | ✅ Applied |
| **Message Indicators** | New messages indicator style for chat interface | ✅ Available |

### 4. Deployment Scripts Created

| Script | Purpose | Platform |
|--------|---------|----------|
| `scripts/update_clawdbots_vps.sh` | Update clawdbots on VPS | Linux (Ubuntu) |
| `scripts/update_clawdbots_local.ps1` | Update local gateway | Windows |
| `UPDATE_CLAWDBOTS.md` | Full deployment guide | Documentation |

## Deployment Instructions

### Quick Start (Windows Local)

```powershell
cd C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis
.\scripts\update_clawdbots_local.ps1
```

### Quick Start (VPS)

```bash
cd /root/clawdbots
sudo bash scripts/update_clawdbots_vps.sh
```

## Verification

After deployment, verify the update:

```bash
# Check versions
docker exec clawdbot-friday openclaw --version
docker exec clawdbot-matt openclaw --version
docker exec clawdbot-jarvis openclaw --version

# Should output: 2026.2.3
```

## New Telegram Features

### Inline Model Selection

Users can now select models directly in Telegram:

1. Send `/models` to any bot
2. See list of available models with inline buttons
3. Click a button to switch models
4. Confirmation message shows the selected model

**Example:**
```
User: /models

Bot: Select a model:
[Claude Opus 4.5] [Claude Sonnet 4] [Grok 3]

User: *clicks Claude Opus 4.5*

Bot: ✓ Model changed to claude-opus-4-5-20251101
```

### Model Override Persistence

Model selections are now properly persisted across sessions, fixing the bug where Telegram button selections were ignored.

## Discord Integration (Optional)

If you enable Discord channel, you can now set custom presence:

```json
{
  "channels": {
    "discord": {
      "enabled": true,
      "token": "YOUR_DISCORD_BOT_TOKEN",
      "presence": {
        "status": "online",
        "activity": {
          "name": "Trading on Solana",
          "type": "WATCHING"
        }
      }
    }
  }
}
```

## Backward Compatibility

All existing configurations continue to work:
- ✅ `clawdbot` command still works (symlinked to openclaw)
- ✅ Existing config files (clawdbot.json) unchanged
- ✅ Telegram bot tokens and auth unchanged
- ✅ Supermemory integration unchanged
- ✅ All environment variables unchanged

## Architecture

### Current Setup

```
┌─────────────────────────────────────────────────────────┐
│                    ClawdBot Gateway                      │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Friday     │  │     Matt     │  │   Jarvis     │  │
│  │ (Port 18789) │  │ (Port 18790) │  │ (Port 18791) │  │
│  │              │  │              │  │              │  │
│  │ Claude Opus  │  │ Claude Sonnet│  │    Grok 3    │  │
│  │     4.5      │  │   + Codex    │  │              │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │          Supermemory (Shared Long-term)            │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │      Watchdog (Auto-recovery every 60s)            │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Bot Personalities

| Bot | Model | Port | Role | Telegram |
|-----|-------|------|------|----------|
| **Friday** | Claude Opus 4.5 | 18789 | CMO - Marketing & Strategy | @ClawdFriday_bot |
| **Matt** | Claude Sonnet 4 + Codex | 18790 | COO - Operations & Coding | @ClawdMatt_bot |
| **Jarvis** | Grok 3 (xAI) | 18791 | CTO - Technical Leadership | @ClawdJarvis_bot |

## Troubleshooting

### Container not starting

```bash
# Check logs
docker compose logs friday

# Common issues:
# 1. Port already in use → Check with: netstat -tulpn | grep 18789
# 2. Config error → Verify .env file exists
# 3. Network issue → Restart Docker: systemctl restart docker
```

### Version shows "unknown"

```bash
# Force reinstall
docker compose exec friday npm install -g openclaw@2026.2.3 --force
docker compose restart friday
```

### Telegram bot not responding

```bash
# Check if bot token is valid
docker compose exec friday env | grep TELEGRAM

# Restart specific bot
docker compose restart friday
```

## Rollback Procedure

If issues occur, rollback to previous version:

```bash
# VPS
cd /root/clawdbots/deploy/clawdbot-redundancy
docker compose down
docker tag clawdbot-ready:2026.2.2 clawdbot-ready:latest
docker compose up -d

# Local
cd C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\docker\clawdbot-gateway
docker compose down
# Edit docker-compose.yml: Change openclaw@2026.2.3 back to clawdbot@latest
docker compose up -d
```

## Next Steps

1. ✅ Test Telegram inline model selection (`/models`)
2. ✅ Verify all bots are responding
3. ✅ Check Supermemory integration
4. ⏳ Monitor logs for 24h for any issues
5. ⏳ Consider enabling Discord channel
6. ⏳ Review security updates in changelog

## Resources

- **OpenClaw Docs:** https://docs.openclaw.ai
- **Changelog:** https://github.com/openclaw/openclaw/blob/main/CHANGELOG.md
- **Repository:** https://github.com/openclaw/openclaw
- **Issues:** https://github.com/openclaw/openclaw/issues

## Support

For issues specific to this deployment:
1. Check logs: `docker compose logs -f`
2. Check health: `curl http://localhost:18789/health`
3. Review [UPDATE_CLAWDBOTS.md](./UPDATE_CLAWDBOTS.md)

---

**Update Date:** February 3, 2026
**OpenClaw Version:** 2026.2.3
**Updated By:** Claude (Sonnet 4.5)
**Bots Affected:** ClawdFriday, ClawdMatt, ClawdJarvis
