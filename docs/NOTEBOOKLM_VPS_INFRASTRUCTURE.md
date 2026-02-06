# Jarvis VPS Infrastructure - Complete Reference

## VPS Servers

### VPS 1: Main Jarvis (72.61.7.126)
- **Provider**: Hostinger
- **Hostname**: srv1277677.hstgr.cloud
- **OS**: Ubuntu 24.04 LTS
- **Plan**: KVM 8 (400GB disk, 2GB RAM)
- **Location**: United States - Boston
- **SSH**: `ssh root@72.61.7.126`
- **IPv6**: 2a02:4780:2d:7372::1
- **Purpose**: Runs main Jarvis supervisor (Telegram bot, buy tracker, sentiment reporter, treasury bot, X bot sync)

### VPS 2: ClawdBots (76.13.106.100)
- **Purpose**: Runs 3 ClawdBot agents (ClawdMatt, ClawdFriday, ClawdJarvis)
- **Service**: clawdbot-gateway (systemd)
- **Token file**: /root/clawdbots/tokens.env

---

## Systemd Services (VPS 1)

### jarvis-supervisor.service
- **Path**: /etc/systemd/system/jarvis-supervisor.service
- **User**: jarvis
- **WorkingDirectory**: /home/jarvis/Jarvis
- **EnvironmentFile**: /etc/jarvis/jarvis.env
- **ExecStart**: /home/jarvis/Jarvis/start_supervisor.sh
- **Restart**: always (RestartSec=30)
- **Resource Limits**: CPUQuota=50%, MemoryMax=2G
- **IMPORTANT**: StartLimitIntervalSec should be 300 with StartLimitBurst=5 to prevent infinite restart loops

### jarvis-telegram.service
- **Path**: /etc/systemd/system/jarvis-telegram.service

### jarvis-twitter.service
- **Path**: /etc/systemd/system/jarvis-twitter.service

### ClawdBot Services (VPS 2)
- deploy/clawdfriday.service
- deploy/clawdjarvis.service
- deploy/clawdmatt.service
- All use EnvironmentFile=/root/clawdbots/tokens.env

---

## Telegram Bot Token Registry

### Active Tokens (as of Feb 2, 2026)

| Bot Name | Token ID | Variable Name | VPS | Purpose |
|----------|----------|---------------|-----|---------|
| @jarvistrades_bot | 8587062928 | TELEGRAM_BOT_TOKEN | 72.61.7.126 | Main Jarvis Telegram bot |
| @Javistreasury_bot | 8295840687 | TELEGRAM_BUY_BOT_TOKEN | 72.61.7.126 | Buy tracker / sentiment reports |
| @jarvis_treasury_bot | 8504068106 | TREASURY_BOT_TOKEN | 72.61.7.126 | Treasury trading bot |
| @X_TELEGRAM_KR8TIV_BOT | 7968869100 | X_BOT_TELEGRAM_TOKEN | 72.61.7.126 | X/Twitter sync notifications |
| @ClawdMatt_bot | 8288059637 | CLAWDMATT_BOT_TOKEN | 76.13.106.100 | ClawdMatt agent |
| @ClawdFriday_bot | 7864180473 | CLAWDFRIDAY_BOT_TOKEN | 76.13.106.100 | ClawdFriday agent |
| @ClawdJarvis_87772_bot | 8434411668 | CLAWDJARVIS_BOT_TOKEN | 76.13.106.100 | ClawdJarvis agent |

### Revoked Tokens (DO NOT USE)

| Token ID | Reason | Date |
|----------|--------|------|
| 8047602125 | Exposed in git security audit, revoked | Jan 31, 2026 |

### Token Loading Priority

**Main bot** (tg_bot/config.py):
1. `TELEGRAM_BOT_TOKEN` environment variable
2. `secrets/keys.json` file (fallback)

**Buy tracker** (bots/buy_tracker/config.py):
1. `TELEGRAM_BUY_BOT_TOKEN` environment variable
2. Falls back to `TELEGRAM_BOT_TOKEN` (BUG - causes polling conflicts)

**Treasury bot** (bots/supervisor.py):
1. `TREASURY_BOT_TOKEN` environment variable
2. Falls back to `TREASURY_BOT_TELEGRAM_TOKEN` (legacy name)

**ClawdBots** (bots/clawdXXX/clawdXXX_telegram_bot.py):
1. Loads from `tokens.env` relative to project root
2. Falls back to `/root/clawdbots/tokens.env`
3. Uses `CLAWDXXX_BOT_TOKEN` env var

---

## Environment Files

### Local Development
- `.env` - Root project env (TELEGRAM_BOT_TOKEN)
- `tg_bot/.env` - Main bot + buy bot + treasury tokens
- `docker/clawdbot-gateway/.env` - ClawdBot tokens

### VPS 1 (72.61.7.126)
- `/etc/jarvis/jarvis.env` - All VPS1 tokens loaded by systemd
- `/home/jarvis/Jarvis/tg_bot/.env` - App-level config
- `/home/jarvis/Jarvis/.env` - Root config

### VPS 2 (76.13.106.100)
- `/root/clawdbots/tokens.env` - ClawdBot tokens

---

## Supervisor Architecture

The supervisor (bots/supervisor.py) orchestrates all bot components:

```
supervisor.py
├── create_telegram_bot()     → Spawns tg_bot/bot.py subprocess
│   └── Uses TELEGRAM_BOT_TOKEN (8587062928)
│   └── Acquires polling lock (only one poller per token)
├── create_sentiment_reporter() → Inline SentimentReportGenerator
│   └── BUG: Uses TELEGRAM_BOT_TOKEN instead of TELEGRAM_BUY_BOT_TOKEN
│   └── Posts to TELEGRAM_BUY_BOT_CHAT_ID
├── create_buy_bot()          → Buy tracker component
│   └── Uses TELEGRAM_BUY_BOT_TOKEN (8295840687)
│   └── Dangerous fallback to main token if missing
├── create_treasury_bot()     → Treasury trading bot
│   └── Uses TREASURY_BOT_TOKEN (8504068106)
├── create_twitter_poster()   → X/Twitter posting engine
└── create_autonomous_x()     → Autonomous X posting
```

### Restart Behavior
- Internal: max_retries=100 per component, exponential backoff
- Systemd: Restart=always, RestartSec=30
- Combined: Can create infinite crash loops if a component has a permanent failure (e.g., invalid token)

### Telegram Polling Lock
- Only ONE process can poll per bot token
- Lock file prevents duplicate polling
- If lock is held by supervisor, child skips acquisition
- SKIP_TELEGRAM_LOCK=1 environment variable bypasses lock

---

## Token Deployment Process

### Scripts Available
1. `scripts/deploy_bot_tokens.ps1` - PowerShell (Windows)
2. `scripts/deploy_bot_tokens.sh` - Bash (Linux/Mac)
3. `scripts/deploy_with_password.py` - Interactive Python (password-based SSH)

### Deployment Steps
1. SSH connection test to VPS
2. Backup existing .env file (timestamped)
3. Update tokens via `sed` or `echo >>` if new
4. Verify with `grep` on remote
5. Restart services:
   - VPS1: `pkill -f supervisor.py && nohup python bots/supervisor.py`
   - VPS2: `systemctl restart clawdbot-gateway`

### Manual Token Update (VPS Recovery Mode)
When VPS is in recovery mode, system disk is at /mnt/sda1:
```bash
# View current tokens
cat /mnt/sda1/etc/jarvis/jarvis.env | grep TELEGRAM

# Update a token
sed -i 's/OLD_TOKEN/NEW_TOKEN/' /mnt/sda1/etc/jarvis/jarvis.env

# Verify
cat /mnt/sda1/etc/jarvis/jarvis.env | grep TELEGRAM
```

---

## Known Issues and Bugs

### 1. Sentiment Reporter Token Bug
- **File**: bots/supervisor.py line 615
- **Issue**: Uses TELEGRAM_BOT_TOKEN (main) to post to buy bot chat
- **Fix**: Change to TELEGRAM_BUY_BOT_TOKEN

### 2. Buy Tracker Fallback Bug
- **File**: bots/buy_tracker/config.py line 95
- **Issue**: Falls back to main bot token, causing polling conflicts
- **Fix**: Remove fallback, require explicit TELEGRAM_BUY_BOT_TOKEN

### 3. Infinite Restart Loop
- **File**: /etc/systemd/system/jarvis-supervisor.service
- **Issue**: StartLimitIntervalSec=0 allows infinite restarts
- **Fix**: Set StartLimitIntervalSec=300, StartLimitBurst=5

### 4. Duplicate Token Variables
- **File**: tg_bot/.env
- **Issue**: PUBLIC_BOT_TELEGRAM_TOKEN duplicates TELEGRAM_BOT_TOKEN
- **Issue**: TREASURY_BOT_TELEGRAM_TOKEN duplicates TELEGRAM_BUY_BOT_TOKEN
- **Fix**: Remove duplicate variable names

### 5. Token Not Deployed After Rotation
- **Issue**: Token 8047602125 was revoked but VPS still had it
- **Root Cause**: Deploy scripts weren't run after token rotation
- **Prevention**: Always run deploy_bot_tokens after changing tokens

---

## Troubleshooting Runbook

### Bot Returns "InvalidToken" / 401 Unauthorized
1. Check which token is being used: `grep TELEGRAM /etc/jarvis/jarvis.env`
2. Verify token with BotFather: Open Telegram → @BotFather → /mybots → select bot → API Token
3. Update token: `sed -i 's/OLD/NEW/' /etc/jarvis/jarvis.env`
4. Restart: `systemctl restart jarvis-supervisor`

### VPS Enters Recovery/Emergency Mode
1. Connect via Hostinger web terminal
2. System disk is at /mnt/sda1
3. Check kernel logs: `cat /mnt/sda1/var/log/kern.log | tail -50`
4. Check fstab: `cat /mnt/sda1/etc/fstab`
5. Check systemd services: `ls /mnt/sda1/etc/systemd/system/ | grep jarvis`
6. Check app logs: `cat /mnt/sda1/var/log/syslog | tail -100`
7. Fix issues, then exit recovery from hPanel dashboard

### Polling Conflicts (Multiple bots on same token)
1. Check if multiple processes use same token
2. Ensure each bot has its OWN unique token
3. Check fallback chains in config files
4. Look for SKIP_TELEGRAM_LOCK usage

### How to Generate New Token
1. Open Telegram → @BotFather
2. Send /mybots → select bot
3. Tap "API Token" (view current) or "Revoke current token" (generate new)
4. Update in: local .env files, VPS env files, deploy scripts
5. Run deploy script to push to VPS
6. Restart services

---

## Recovery Mode Reference (Hostinger)

When VPS boots into recovery mode:
- System disk: /mnt/sda1 (399GB ext4)
- Boot: /mnt/sda16
- EFI: /mnt/sda15
- Recovery OS: sdb1 (9.5GB, mounted at /)
- File browser: http://72.61.7.126/
- Exit: hPanel dashboard → Settings → Emergency mode → Turn off

### Common Recovery Tasks
```bash
# Check fstab
cat /mnt/sda1/etc/fstab

# Check systemd services
ls /mnt/sda1/etc/systemd/system/ | grep jarvis

# Edit service files
vi /mnt/sda1/etc/systemd/system/jarvis-supervisor.service

# Check env files
cat /mnt/sda1/etc/jarvis/jarvis.env

# Check logs
cat /mnt/sda1/var/log/syslog | tail -200
cat /mnt/sda1/var/log/kern.log | tail -50

# Check for kernel panics/OOM
grep -i "panic\|oom\|error\|fail" /mnt/sda1/var/log/kern.log | tail -20
```

---

## Telegram Admin Configuration

- **Admin User ID**: 8527130908 (set in jarvis-supervisor.service and .env)
- **Buy Bot Chat ID**: Set in TELEGRAM_BUY_BOT_CHAT_ID
- **Digest Hours (UTC)**: 8, 14, 20
- **Grok Daily Cost Limit**: $10.00
- **Sentiment Interval**: 3600s (1 hour)
