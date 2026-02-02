# Deploy ClawdBots to VPS 76.13.106.100

**Created**: 2026-01-31
**Status**: ✅ READY TO DEPLOY
**Target**: VPS 76.13.106.100 (clawdbot-gateway)

---

## Bot Tokens

1. **ClawdMatt** (@ClawdMatt_bot)
   - Token: `8288059637:AAHbcATe1mgMBGKuf5ceYFpyVpO2rzXYFqH`
   - Created: 2026-01-25

2. **ClawdFriday** (@ClawdFriday_bot)
   - Token: `7864180473:AAHN9ROzOdtHRr5JXw1iTDpMYQitGEh-Bu4`
   - Created: 2026-01-27 (token revoked and renewed)

3. **ClawdJarvis** (@ClawdJarvis_87772_bot)
   - Token: `8434411668:AAHNGOzjHI-rYwBZ2mIM2c7cbZmLGTjekJ4`
   - Created: 2026-01-29

---

## Deployment Steps

### Option 1: Direct Environment Variables

```bash
# SSH to ClawdBot gateway
ssh root@76.13.106.100

# Add tokens to environment (systemd service or .env)
cat >> /opt/clawdbot-gateway/.env << 'EOF'
# ClawdBot Tokens (Updated 2026-01-31)
CLAWDMATT_BOT_TOKEN=8288059637:AAHbcATe1mgMBGKuf5ceYFpyVpO2rzXYFqH
CLAWDFRIDAY_BOT_TOKEN=7864180473:AAHN9ROzOdtHRr5JXw1iTDpMYQitGEh-Bu4
CLAWDJARVIS_BOT_TOKEN=8434411668:AAHNGOzjHI-rYwBZ2mIM2c7cbZmLGTjekJ4
EOF

# Restart ClawdBot services
systemctl restart clawdbot-matt
systemctl restart clawdbot-friday
systemctl restart clawdbot-jarvis

# Verify services are running
systemctl status clawdbot-matt clawdbot-friday clawdbot-jarvis

# Check logs
journalctl -u clawdbot-matt -f
```

### Option 2: Docker Environment

```bash
# If using Docker Compose
cd /opt/clawdbot-gateway

# Update docker-compose.yml environment section
nano docker-compose.yml
# Add:
#   environment:
#     - CLAWDMATT_BOT_TOKEN=8288059637:AAHbcATe1mgMBGKuf5ceYFpyVpO2rzXYFqH
#     - CLAWDFRIDAY_BOT_TOKEN=7864180473:AAHN9ROzOdtHRr5JXw1iTDpMYQitGEh-Bu4
#     - CLAWDJARVIS_BOT_TOKEN=8434411668:AAHNGOzjHI-rYwBZ2mIM2c7cbZmLGTjekJ4

# Restart containers
docker-compose down
docker-compose up -d

# Check logs
docker-compose logs -f
```

---

## Success Criteria

After deployment, verify:
- ✅ All 3 bots respond to /start command
- ✅ No "Unauthorized" or token errors in logs
- ✅ Bots show online status in Telegram

---

## Testing

```bash
# Test each bot via Telegram
# 1. Open @ClawdMatt_bot → send /start
# 2. Open @ClawdFriday_bot → send /start
# 3. Open @ClawdJarvis_87772_bot → send /start

# All should respond with greeting/menu
```

---

## Architecture

```
VPS 76.13.106.100 (clawdbot-gateway)
├── ClawdMatt (API gateway + agent orchestration)
├── ClawdFriday (Task automation + scheduling)
└── ClawdJarvis (Core AI + knowledge base)

Each bot runs independently with its own token to avoid polling conflicts.
```

---

## Notes

- All tokens validated from user's BotFather dump (2026-01-31)
- ClawdMatt token was corrected (was 8288859637, now 8288059637)
- Each bot must use its own unique token (no sharing)
