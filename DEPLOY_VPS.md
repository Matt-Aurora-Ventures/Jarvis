# Jarvis VPS Deployment Guide

## Quick Start (Copy & Paste)

### Step 1: SSH into your VPS
```bash
ssh root@72.61.7.126
```

### Step 2: Download and run deployment script
```bash
cd /tmp && curl -O https://raw.githubusercontent.com/Matt-Aurora-Ventures/Jarvis/main/deploy.sh && bash deploy.sh
```

**OR** if you cloned locally, copy the script to VPS first:
```bash
scp deploy.sh root@72.61.7.126:/tmp/
ssh root@72.61.7.126
cd /tmp && bash deploy.sh
```

### Step 3: Add your API keys
After the script completes, edit the secrets file:
```bash
nano /home/jarvis/Jarvis/secrets/keys.json
```

Fill in all the `YOUR_*_KEY` values with your actual keys.

### Step 4: Restart services to load secrets
```bash
systemctl restart jarvis-supervisor jarvis-telegram jarvis-twitter
```

### Step 5: Verify everything is running
```bash
systemctl status jarvis-supervisor
systemctl status jarvis-telegram
systemctl status jarvis-twitter
```

All three should show **active (running)**.

## What Gets Deployed

✅ **Supervisor Service** - Manages all internal bots:
- Buy bot tracker (KR8TIV tracking)
- Sentiment reporter (hourly reports)
- Autonomous X poster
- Health monitor

✅ **Telegram Bot** - Full chat interface
- `/portfolio` or `/p` - Quick overview
- `/balance` or `/b` - Balance summary
- `/treasury` - Full treasury display
- `/pnl` - P&L details
- `/sector` - Sector breakdown
- All other commands

✅ **Twitter/X Bot** - Autonomous posting
- Sentiment reports
- Grok AI analysis
- Market updates
- Autonomous decision-making

## Manage Services

```bash
# View logs (real-time)
journalctl -u jarvis-supervisor -f

# View last 100 lines
journalctl -u jarvis-supervisor -n 100

# Restart all services
systemctl restart jarvis-supervisor jarvis-telegram jarvis-twitter

# Stop all services
systemctl stop jarvis-supervisor jarvis-telegram jarvis-twitter

# Start all services
systemctl start jarvis-supervisor jarvis-telegram jarvis-twitter

# Check status
systemctl status jarvis-*
```

## Troubleshooting

### Service won't start?
```bash
journalctl -u jarvis-supervisor -n 50
```
Look for the error message and fix it.

### Need to update code?
```bash
cd /home/jarvis/Jarvis
sudo -u jarvis git pull
systemctl restart jarvis-supervisor jarvis-telegram jarvis-twitter
```

### Telegram bot not responding?
1. Make sure token is correct in `secrets/keys.json`
2. Restart service: `systemctl restart jarvis-telegram`
3. Check logs: `journalctl -u jarvis-telegram -n 50`

### X bot not posting?
1. Make sure Twitter API keys are correct in `secrets/keys.json`
2. Restart service: `systemctl restart jarvis-twitter`
3. Check logs: `journalctl -u jarvis-twitter -n 50`

## System Details

**Server**: 72.61.7.126
**OS**: Ubuntu 24.04 LTS
**Bot User**: jarvis (non-root, for security)
**Working Directory**: /home/jarvis/Jarvis
**Logs**: `journalctl` (systemd journals)

## Auto-Restart & High Availability

All services are configured with:
- `Restart=always` - Auto-restarts if crashed
- `RestartSec=30` - Waits 30s before restarting
- systemd monitoring 24/7

So if a bot crashes, it automatically restarts. No manual intervention needed!

## Key Features Enabled

✅ Position stacking - ENABLED (unlimited positions per token)
✅ Asset allocation caps - DISABLED (no limits)
✅ Stablecoins - REMOVED (replaced with better assets)
✅ All Solana blue chips - AVAILABLE
✅ Wrapped tokens - AVAILABLE (BTC, ETH, stocks, commodities)

## Support

If something breaks:
1. Check logs: `journalctl -u jarvis-supervisor -n 100`
2. Restart service: `systemctl restart jarvis-supervisor`
3. Check secrets: `cat /home/jarvis/Jarvis/secrets/keys.json`

That's it! Your Jarvis is now running 24/7 on the VPS.
