# Jarvis VPS Deployment Checklist

**Target Server**: 72.61.7.126 (Ubuntu 24.04 LTS)
**Deployment Date**: 2026-01-17
**Version**: v4.7.1 (Unrestricted Trading + VPS Automation)

---

## Pre-Deployment: API Keys Checklist

Gather these API keys BEFORE deployment. You'll need them immediately after:

### Required API Keys

- [ ] **Anthropic API Key** (`sk-ant-...`)
  - From: https://console.anthropic.com/

- [ ] **XAI API Key** (Grok)
  - From: https://console.x.ai/

- [ ] **Groq API Key** (`gsk_...`)
  - From: https://console.groq.com/

- [ ] **MiniMax API Key**
  - From: https://platform.minimaxi.com/

- [ ] **BirdEye API Key** (Solana token data)
  - From: https://birdeye.so/

- [ ] **Helius API Key** (Solana RPC)
  - From: https://www.helius.dev/

### Twitter/X API Keys (4 required)

- [ ] **API Key** (Consumer Key)
- [ ] **API Secret** (Consumer Secret)
- [ ] **Access Token** (User OAuth Token)
- [ ] **Access Secret** (User OAuth Token Secret)
- Source: https://developer.twitter.com/en/portal/dashboard

### Telegram API Key

- [ ] **Bot Token** (from @BotFather on Telegram)
- Format: `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`

---

## Deployment Steps

### Step 1: SSH into VPS

```bash
ssh root@72.61.7.126
```

Expected output: Ubuntu 24.04 LTS bash prompt

### Step 2: Run Deployment Script

Copy and paste this entire command:

```bash
curl -fsSL https://raw.githubusercontent.com/Matt-Aurora-Ventures/Jarvis/main/vps-deploy-with-keys.sh | bash
```

**What happens** (9 phases, ~10-15 minutes):
1. System update & dependency installation
2. Create non-root `jarvis` user
3. Configure UFW firewall (ports 22, 80, 443)
4. Clone Jarvis repository
5. Create Python 3.12 virtual environment
6. Install Python dependencies
7. Create systemd services (auto-restart enabled)
8. Start all 3 services
9. Configure log rotation

**Monitor progress**: Watch the terminal output. You'll see GREEN checkmarks for each phase.

### Step 3: Update API Keys (IMMEDIATELY after deployment)

When deployment completes, you'll see:
```
✓ DEPLOYMENT COMPLETE! Your bots are running 24/7
```

Edit the secrets file:
```bash
nano /home/jarvis/Jarvis/secrets/keys.json
```

**Find and replace all `REPLACEME` values** with your actual API keys:

```json
{
  "anthropic_api_key": "sk-ant-YOUR_ACTUAL_KEY",
  "xai": {"api_key": "YOUR_XAI_KEY"},
  "groq_api_key": "YOUR_GROQ_KEY",
  "minimax_api_key": "YOUR_MINIMAX_KEY",
  "birdeye_api_key": "YOUR_BIRDEYE_KEY",
  "helius": {"api_key": "YOUR_HELIUS_KEY"},
  "twitter": {
    "api_key": "YOUR_TWITTER_API_KEY",
    "api_secret": "YOUR_TWITTER_API_SECRET",
    "access_token": "YOUR_TWITTER_ACCESS_TOKEN",
    "access_secret": "YOUR_TWITTER_ACCESS_SECRET"
  },
  "telegram": {
    "bot_token": "YOUR_TELEGRAM_BOT_TOKEN"
  }
}
```

**Save and exit nano:**
- Press: `Ctrl+O`, then `Enter` (save)
- Press: `Ctrl+X` (exit)

### Step 4: Restart Services with New Keys

```bash
systemctl restart jarvis-supervisor jarvis-telegram jarvis-twitter
```

Wait 3-5 seconds for services to restart.

### Step 5: Verify Services are Running

```bash
systemctl status jarvis-supervisor
systemctl status jarvis-telegram
systemctl status jarvis-twitter
```

Expected output for each: **`active (running)`** ✓

All three should show GREEN "active (running)" status.

---

## Post-Deployment Verification

### Check Service Logs

```bash
# Supervisor logs (includes trading bot, sentiment reporter)
journalctl -u jarvis-supervisor -n 50

# Telegram bot logs
journalctl -u jarvis-telegram -n 50

# Twitter/X bot logs
journalctl -u jarvis-twitter -n 50
```

### Test Telegram Bot

1. Start a conversation with @Jarviskr8tivbot on Telegram
2. Send `/start`
3. Try `/portfolio` or `/p` for quick portfolio overview
4. Try `/treasury` for full treasury display

Expected response: Formatted portfolio with holdings, P&L, sector breakdown

### Test Twitter Bot

Check @Jarvis_lifeos feed for recent posts about market sentiment or grok analysis.

### Check Systemd Auto-Restart

Services are configured to auto-restart if they crash:
- Restart delay: 30 seconds
- Restart policy: `always`

To test:
```bash
systemctl stop jarvis-supervisor
sleep 5
systemctl status jarvis-supervisor
```

Should show "active (running)" - it auto-restarted.

---

## Key Features Enabled

✅ **Unrestricted Trading**
- Position stacking: ENABLED (unlimited positions per token)
- Asset allocation caps: DISABLED (no per-token limits)
- Blue chips trading: ALL SOLANA TOKENS AVAILABLE

✅ **Available Assets** (45+ tokens)
- **Solana Native (5)**: SOL, BTC, ETH, BONK, JUP
- **xStocks (7)**: xNVDA, xTSLA, xAAPL, xGOOG, xAMZN, xMSFT, xMETA
- **PreStocks (5)**: pSPACEX, pOPENAI, pANTHROPIC, pXAI, pANDURIL
- **Commodities (3)**: GOLD, SILVER, OIL
- **Plus 25+ wrapped tokens**

✅ **3 Production Services**
- **Supervisor** - Orchestrates buy_bot, sentiment_reporter, health monitor
- **Telegram Bot** - Full admin interface (@Jarviskr8tivbot)
- **Twitter Bot** - Autonomous posting (@Jarvis_lifeos)

---

## Important Commands

```bash
# View real-time logs (supervisor)
journalctl -u jarvis-supervisor -f

# View all service status
systemctl status jarvis-*

# Restart all services
systemctl restart jarvis-supervisor jarvis-telegram jarvis-twitter

# Stop all services (emergency)
systemctl stop jarvis-supervisor jarvis-telegram jarvis-twitter

# Start all services
systemctl start jarvis-supervisor jarvis-telegram jarvis-twitter

# Check disk space (monitor log growth)
df -h

# Check Python process memory usage
ps aux | grep python
```

---

## Troubleshooting

### Service won't start after key update?

```bash
# Check logs for the error
journalctl -u jarvis-supervisor -n 100

# Verify JSON syntax in keys.json
cat /home/jarvis/Jarvis/secrets/keys.json | python3 -m json.tool
```

### Telegram bot not responding?

1. Verify token in `/home/jarvis/Jarvis/secrets/keys.json` is correct
2. Restart service: `systemctl restart jarvis-telegram`
3. Check logs: `journalctl -u jarvis-telegram -n 50`

### Twitter/X bot not posting?

1. Verify all 4 Twitter keys are correct (not partial)
2. Check API keys have correct permissions on https://developer.twitter.com
3. Restart service: `systemctl restart jarvis-twitter`
4. Check logs: `journalctl -u jarvis-twitter -n 50`

### Supervisor crashes repeatedly?

Check for Python import errors:
```bash
journalctl -u jarvis-supervisor -n 200 | grep -i error
```

Common causes:
- Missing dependency (check requirements.txt)
- Invalid API key format
- File permission issue in `/home/jarvis/Jarvis/secrets/`

### Need to update code?

```bash
cd /home/jarvis/Jarvis
sudo -u jarvis git pull origin main
systemctl restart jarvis-supervisor jarvis-telegram jarvis-twitter
```

---

## System Details

| Property | Value |
|----------|-------|
| **Server** | 72.61.7.126 |
| **OS** | Ubuntu 24.04 LTS |
| **Python** | 3.12 |
| **Bot User** | jarvis (non-root) |
| **Working Dir** | /home/jarvis/Jarvis |
| **Log Location** | systemd journal (journalctl) |
| **Service Restart** | Auto (30s delay after crash) |

---

## Version Summary

**v4.7.1** - Deployment & Trading Constraints Removal
- ✅ Unrestricted position stacking enabled
- ✅ Per-token allocation caps disabled
- ✅ VPS deployment automation (systemd services)
- ✅ Treasury display system fully integrated
- ✅ Sentiment engine self-tuning enabled

**Previous**: v4.7.0 - Treasury Display & Telegram Integration

---

## Support

If something breaks:
1. Check logs: `journalctl -u <service-name> -n 100`
2. Restart service: `systemctl restart <service-name>`
3. Update code: `cd /home/jarvis/Jarvis && sudo -u jarvis git pull`
4. Verify secrets: `cat /home/jarvis/Jarvis/secrets/keys.json` (check JSON syntax)

Your Jarvis is now running 24/7 on the VPS! 🚀
