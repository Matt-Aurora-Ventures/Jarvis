# ClawdBots Update Guide - OpenClaw 2026.2.3

## What's Updated

All clawdbot instances have been updated to use **OpenClaw 2026.2.3** (released Feb 3, 2026).

### Key Changes in OpenClaw 2026.2.3

1. **Telegram Model Selection** - Inline button model selection for `/models` and `/model` commands (#8193)
2. **Discord Presence** - New set-presence action for bot activity and status
3. **Security Fixes** - Honor Telegram model overrides in buttons
4. **Message Indicators** - New messages indicator style for chat interface

### Updated Files

- `docker/clawdbot-gateway/docker-compose.yml` - Updated all 3 containers to install openclaw@2026.2.3
- `deploy/clawdbot-redundancy/Dockerfile.clawdbot-full` - Updated base image to openclaw@2026.2.3
- `deploy/clawdbot-redundancy/docker-compose.clawdbots.yml` - Updated image tag to 2026.2.3

## Deployment Steps

### Local Docker Gateway (Windows)

```powershell
cd C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\docker\clawdbot-gateway

# Stop existing containers
docker compose down

# Pull latest and restart
docker compose pull
docker compose up -d

# Verify updates
docker compose exec friday openclaw --version
docker compose exec matt openclaw --version
docker compose exec jarvis openclaw --version

# Check logs
docker compose logs -f friday
```

### VPS Deployment (Ubuntu)

```bash
cd /root/clawdbots

# Rebuild image with openclaw 2026.2.3
cd deploy/clawdbot-redundancy
docker build -f Dockerfile.clawdbot-full -t clawdbot-ready:2026.2.3 .
docker tag clawdbot-ready:2026.2.3 clawdbot-ready:latest

# Restart containers with new image
docker compose -f docker-compose.clawdbots.yml down
docker compose -f docker-compose.clawdbots.yml up -d

# Verify versions
docker exec clawdbot-friday openclaw --version
docker exec clawdbot-matt openclaw --version
docker exec clawdbot-jarvis openclaw --version

# Monitor health
docker compose -f docker-compose.clawdbots.yml ps
docker compose -f docker-compose.clawdbots.yml logs -f
```

## Configuration Changes

### Backward Compatibility

All containers now create a `clawdbot` symlink pointing to `openclaw` for backward compatibility:

```bash
ln -sf "$(which openclaw)" /usr/local/bin/clawdbot
```

This means both commands work:
- `openclaw gateway --profile friday`
- `clawdbot gateway --profile friday`

### New Features Available

#### Telegram Model Selection
Users can now select models directly in Telegram using inline buttons:
- `/models` - Show available models with selection buttons
- `/model` - Change the current model

#### Discord Presence (if enabled)
Set custom bot status and activity:
```json
{
  "channels": {
    "discord": {
      "presence": {
        "status": "online",
        "activity": {
          "name": "Monitoring Solana",
          "type": "WATCHING"
        }
      }
    }
  }
}
```

## Verification Checklist

After deployment, verify:

- [ ] All 3 containers running (`docker ps`)
- [ ] Health checks passing (`docker compose ps` shows "healthy")
- [ ] Telegram bots responding to commands
- [ ] Memory (Supermemory) integration working
- [ ] Logs show openclaw 2026.2.3 version
- [ ] `/models` command shows inline buttons (Telegram)

## Rollback (if needed)

```bash
# Use previous image
docker compose -f docker-compose.clawdbots.yml down
docker tag clawdbot-ready:2026.2.2 clawdbot-ready:latest
docker compose -f docker-compose.clawdbots.yml up -d
```

## Support

- OpenClaw Docs: https://docs.openclaw.ai
- Changelog: https://github.com/openclaw/openclaw/blob/main/CHANGELOG.md
- Issues: https://github.com/openclaw/openclaw/issues

## Next Steps

Consider enabling these new features:
1. Configure Telegram inline model selection
2. Set up Discord presence (if using Discord channel)
3. Review security updates and apply any additional hardening
4. Test the new message indicator styles in web interface

---

**Updated:** February 3, 2026
**Version:** OpenClaw 2026.2.3
**Bots:** ClawdFriday, ClawdMatt, ClawdJarvis
