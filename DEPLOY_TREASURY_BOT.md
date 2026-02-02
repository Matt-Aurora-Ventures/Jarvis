# Deploy TREASURY_BOT_TOKEN - VPS 72.61.7.126

**Created**: 2026-01-31
**Status**: ✅ READY TO DEPLOY

---

## Token Details

**Bot**: @jarvis_treasury_bot
**Token**: `***TREASURY_BOT_TOKEN_REDACTED***`
**Purpose**: Treasury trading operations
**Location**: /home/jarvis/Jarvis/lifeos/config/.env

---

## Deployment Command (COPY-PASTE READY)

```bash
# SSH to VPS
ssh root@72.61.7.126

# Verify .env exists
cat /home/jarvis/Jarvis/lifeos/config/.env | grep TREASURY_BOT_TOKEN

# If not found, add it:
echo '' >> /home/jarvis/Jarvis/lifeos/config/.env
echo '# Treasury Bot' >> /home/jarvis/Jarvis/lifeos/config/.env
echo 'TREASURY_BOT_TOKEN=***TREASURY_BOT_TOKEN_REDACTED***' >> /home/jarvis/Jarvis/lifeos/config/.env

# Verify it was added
tail -5 /home/jarvis/Jarvis/lifeos/config/.env

# Restart supervisor (if X bot deployment didn't already restart it)
pkill -f supervisor.py
sleep 2
cd /home/jarvis/Jarvis
nohup python bots/supervisor.py > logs/supervisor.log 2>&1 &

# Verify supervisor is running
tail -f logs/supervisor.log
```

---

## Success Criteria

After deployment, check logs for:
```
✅ Treasury bot initialized
✅ Connected to Telegram API
✅ Monitoring trading operations
```

---

## What This Enables

**Before**: Treasury bot not connected to Telegram
**After**: Treasury bot can send trade notifications and accept commands via Telegram

---

## Related Services

- Main Jarvis bot: Uses TELEGRAM_BOT_TOKEN
- X bot: Uses X_BOT_TELEGRAM_TOKEN
- Treasury bot: Uses TREASURY_BOT_TOKEN

Each bot has its own token to avoid polling conflicts.
