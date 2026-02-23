# Deploy TREASURY_BOT_TOKEN to VPS

**Generated:** 2026-01-31
**VPS:** 72.61.7.126
**Token:** `TREASURY_BOT_TOKEN=850H068106:AAHoS0GKxl79nPE_2wFjkkmX_T7iXEwOyao`

## Quick Deploy (Copy-Paste Commands)

SSH to VPS and run these commands:

```bash
# 1. SSH to VPS
ssh root@72.61.7.126

# 2. Backup current .env
cp /home/jarvis/Jarvis/lifeos/config/.env /home/jarvis/Jarvis/lifeos/config/.env.backup-$(date +%Y%m%d_%H%M%S)

# 3. Add or update token (choose ONE)

## Option A: If token doesn't exist yet (APPEND)
echo 'TREASURY_BOT_TOKEN=850H068106:AAHoS0GKxl79nPE_2wFjkkmX_T7iXEwOyao' >> /home/jarvis/Jarvis/lifeos/config/.env

## Option B: If token exists (UPDATE)
sed -i 's/^TREASURY_BOT_TOKEN=.*/TREASURY_BOT_TOKEN=850H068106:AAHoS0GKxl79nPE_2wFjkkmX_T7iXEwOyao/' /home/jarvis/Jarvis/lifeos/config/.env

# 4. Verify token was added
grep TREASURY_BOT_TOKEN /home/jarvis/Jarvis/lifeos/config/.env

# 5. Restart supervisor
pkill -f supervisor.py
sleep 2
cd /home/jarvis/Jarvis
nohup python bots/supervisor.py > logs/supervisor.log 2>&1 &

# 6. Monitor logs
tail -f logs/supervisor.log
# Look for: "Using unique treasury bot token"
```

## Manual Editor Method

If you prefer editing manually:

```bash
ssh root@72.61.7.126
nano /home/jarvis/Jarvis/lifeos/config/.env
```

Add this line:
```
TREASURY_BOT_TOKEN=850H068106:AAHoS0GKxl79nPE_2wFjkkmX_T7iXEwOyao
```

Save: `Ctrl+X`, then `Y`, then `Enter`

Restart supervisor:
```bash
pkill -f supervisor.py && cd /home/jarvis/Jarvis && nohup python bots/supervisor.py > logs/supervisor.log 2>&1 &
```

## One-Liner Deployment

Complete deployment in one command:

```bash
ssh root@72.61.7.126 "cp /home/jarvis/Jarvis/lifeos/config/.env /home/jarvis/Jarvis/lifeos/config/.env.backup-\$(date +%Y%m%d_%H%M%S) && echo 'TREASURY_BOT_TOKEN=850H068106:AAHoS0GKxl79nPE_2wFjkkmX_T7iXEwOyao' >> /home/jarvis/Jarvis/lifeos/config/.env && grep TREASURY_BOT_TOKEN /home/jarvis/Jarvis/lifeos/config/.env && pkill -f supervisor.py; sleep 2 && cd /home/jarvis/Jarvis && nohup python bots/supervisor.py > logs/supervisor.log 2>&1 &"
```

Then verify:
```bash
ssh root@72.61.7.126 "tail -50 /home/jarvis/Jarvis/logs/supervisor.log | grep -i treasury"
```

## Verification

After deployment, confirm:

1. **Token in .env:**
   ```bash
   ssh root@72.61.7.126 "grep TREASURY_BOT_TOKEN /home/jarvis/Jarvis/lifeos/config/.env"
   ```
   Expected: `TREASURY_BOT_TOKEN=850H068106:AAHoS0GKxl79nPE_2wFjkkmX_T7iXEwOyao`

2. **Supervisor running:**
   ```bash
   ssh root@72.61.7.126 "ps aux | grep supervisor.py"
   ```

3. **Bot using token:**
   ```bash
   ssh root@72.61.7.126 "tail -100 /home/jarvis/Jarvis/logs/supervisor.log | grep 'Using unique treasury bot token'"
   ```

4. **No crashes:**
   ```bash
   ssh root@72.61.7.126 "tail -100 /home/jarvis/Jarvis/logs/supervisor.log | grep -i 'exit code'"
   ```
   Should NOT show exit code 4294967295 anymore.

## Troubleshooting

**If SSH times out:**
- Check VPS is online
- Verify firewall allows SSH (port 22)
- Try from different network

**If token doesn't appear:**
- Check file permissions: `ls -la /home/jarvis/Jarvis/lifeos/config/.env`
- Verify path is correct
- Use absolute path when editing

**If supervisor won't start:**
- Check Python path: `which python`
- Verify dependencies: `pip list | grep telegram`
- Check for port conflicts: `netstat -tulpn | grep python`

**If bot still crashes:**
- Check logs for actual error: `tail -200 logs/supervisor.log`
- Verify token is valid with Telegram BotFather
- Test bot manually: `python -c "from telegram import Bot; print(Bot('850H068106:AAHoS0GKxl79nPE_2wFjkkmX_T7iXEwOyao').get_me())"`

## Context

This fixes the "exit code 4294967295" error caused by missing TREASURY_BOT_TOKEN.
The @jarvis_treasury_bot token was created via @BotFather and needs to be deployed to VPS.

**Bot:** @jarvis_treasury_bot
**Purpose:** Dedicated Telegram bot for treasury trading operations
**Issue:** 35 consecutive crashes due to missing token
