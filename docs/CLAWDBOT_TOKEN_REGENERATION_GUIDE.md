# ClawdBot Token Regeneration Guide

**Created**: 2026-01-31
**Issue**: 4 of 5 ClawdBot tokens are INVALID (corrupted or expired)
**Validation Tool**: `python scripts/validate_bot_tokens.py`

---

## Problem Summary

The token validation script detected the following issues:

| Bot | Token | Issue | Status |
|-----|-------|-------|--------|
| Treasury | 8504068106:... | None | VALID |
| ClawdMatt | 8288859637:... | Unauthorized | NEEDS REGENERATION |
| ClawdFriday | 7864180**H**73:... | 'H' in numeric ID | NEEDS REGENERATION |
| ClawdJarvis | 8434**H**11668:... | 'H' in numeric ID | NEEDS REGENERATION |
| X Bot Sync | 7968869100:... | Unauthorized | NEEDS REGENERATION |

### What Went Wrong

The tokens with 'H' characters in the Bot ID (7864180H73, 8434H11668) are **invalid**.
Telegram Bot IDs are always **numeric only** (e.g., 8504068106).

Possible causes:
1. Copy-paste error when recording tokens
2. OCR misread '4' or '0' as 'H'
3. Token was corrupted during transfer

---

## Step-by-Step Regeneration

### 1. Open @BotFather in Telegram

Search for `@BotFather` and start a chat.

### 2. List Your Bots

Send: `/mybots`

You should see:
- @ClawdMatt_bot
- @ClawdFriday_bot
- @ClawdJarvis_87772_bot
- @X_TELEGRAM_KR8TIV_BOT

### 3. Regenerate Each Token

For EACH invalid bot:

1. **Click the bot name** (e.g., @ClawdMatt_bot)
2. Click **"API Token"**
3. Click **"Revoke current token"** (if compromised/leaked)
4. Click **"Generate new token"** or the token will already show
5. **Copy the ENTIRE token** including the colon

### 4. Verify Token Format

A valid token looks like:
```
***TREASURY_BOT_TOKEN_REDACTED***
^^^^^^^^^^ ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  Bot ID              Token Hash
 (NUMERIC)          (alphanumeric)
```

**Invalid examples:**
```
850H068106:AAHoS...  (H in Bot ID - WRONG)
7864180H73:AAHN9...  (H in Bot ID - WRONG)
```

### 5. Update Token Files

After getting each new token:

**Local file** (secrets/bot_tokens_DEPLOY_ONLY.txt):
```bash
cd "C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis"
notepad secrets/bot_tokens_DEPLOY_ONLY.txt
```

Replace the invalid token line with the new one.

### 6. Validate New Tokens

```bash
python scripts/validate_bot_tokens.py
```

All tokens should show `[OK]` with the correct username.

---

## Bot-Specific Instructions

### ClawdMatt (@ClawdMatt_bot)

**Purpose**: Marketing & PR filter with KR8TIV brand voice
**Token Variable**: `CLAWDMATT_BOT_TOKEN`
**Deploy To**: VPS 76.13.106.100 (/root/clawdbots/tokens.env)

1. Get new token from @BotFather
2. Update: `secrets/bot_tokens_DEPLOY_ONLY.txt`
3. SSH and update: `ssh root@76.13.106.100`
   ```bash
   nano /root/clawdbots/tokens.env
   # Update CLAWDMATT_BOT_TOKEN=<new_token>
   ```

### ClawdFriday (@ClawdFriday_bot)

**Purpose**: Email AI assistant
**Token Variable**: `CLAWDFRIDAY_BOT_TOKEN`
**Deploy To**: VPS 76.13.106.100 (/root/clawdbots/tokens.env)

1. Get new token from @BotFather
2. Update: `secrets/bot_tokens_DEPLOY_ONLY.txt`
3. SSH and update on VPS

### ClawdJarvis (@ClawdJarvis_87772_bot)

**Purpose**: Main orchestrator
**Token Variable**: `CLAWDJARVIS_BOT_TOKEN`
**Deploy To**: VPS 76.13.106.100 (/root/clawdbots/tokens.env)

1. Get new token from @BotFather
2. Update: `secrets/bot_tokens_DEPLOY_ONLY.txt`
3. SSH and update on VPS

### X Bot Sync (@X_TELEGRAM_KR8TIV_BOT)

**Purpose**: Sync @Jarvis_lifeos tweets to Telegram
**Token Variable**: `X_BOT_TELEGRAM_TOKEN`
**Deploy To**: VPS 72.61.7.126 (/home/jarvis/Jarvis/lifeos/config/.env)

1. Get new token from @BotFather
2. Update: `secrets/bot_tokens_DEPLOY_ONLY.txt`
3. Update: `lifeos/config/.env` (local)
4. SSH and update on VPS:
   ```bash
   ssh root@72.61.7.126
   nano /home/jarvis/Jarvis/lifeos/config/.env
   # Add: X_BOT_TELEGRAM_TOKEN=<new_token>
   pkill -f supervisor.py
   cd /home/jarvis/Jarvis && nohup python bots/supervisor.py > logs/supervisor.log 2>&1 &
   ```

---

## Deployment After Regeneration

### For ClawdBots (VPS 76.13.106.100)

```bash
# SSH to VPS
ssh root@76.13.106.100

# Update tokens file
nano /root/clawdbots/tokens.env

# Content should be:
CLAWDMATT_BOT_TOKEN=<new_token>
CLAWDFRIDAY_BOT_TOKEN=<new_token>
CLAWDJARVIS_BOT_TOKEN=<new_token>

# Save and start bots
# (Method depends on clawdbot-gateway or standalone setup)
```

### For X Bot Sync (VPS 72.61.7.126)

```bash
# SSH to VPS
ssh root@72.61.7.126

# Backup and edit .env
cp /home/jarvis/Jarvis/lifeos/config/.env /home/jarvis/Jarvis/lifeos/config/.env.bak
nano /home/jarvis/Jarvis/lifeos/config/.env

# Add line:
X_BOT_TELEGRAM_TOKEN=<new_token>

# Restart supervisor
pkill -f supervisor.py
cd /home/jarvis/Jarvis && nohup python bots/supervisor.py > logs/supervisor.log 2>&1 &

# Verify X bot using dedicated token
tail -f logs/supervisor.log | grep "X bot"
# Should see: "X bot using dedicated Telegram token (X_BOT_TELEGRAM_TOKEN)"
```

---

## Verification Checklist

After regenerating all tokens:

- [ ] Run `python scripts/validate_bot_tokens.py` - all show OK
- [ ] All tokens have numeric-only Bot IDs (no H, O, etc.)
- [ ] Treasury bot token is unchanged (already valid)
- [ ] ClawdMatt responds to Telegram messages
- [ ] ClawdFriday responds to Telegram messages
- [ ] ClawdJarvis responds to Telegram messages
- [ ] X bot sync pushes tweets to Telegram
- [ ] No polling conflicts for 10+ minutes
- [ ] Update MASTER_GSD with success status

---

## Troubleshooting

### "Unauthorized" Error

The token was revoked or never existed. Regenerate via @BotFather.

### "Bot ID contains invalid characters"

The token was copied incorrectly. The Bot ID (before the colon) must be ONLY digits.
Get a fresh copy from @BotFather.

### "Request timeout"

Network issue. Try again in a few seconds.

### Polling Conflicts

If you see "Conflict: terminated by other getUpdates request", multiple processes
are using the same token. Ensure each bot uses a UNIQUE token.

---

## Quick Reference

```bash
# Validate tokens
python scripts/validate_bot_tokens.py

# Local token file
notepad secrets/bot_tokens_DEPLOY_ONLY.txt

# VPS tokens (ClawdBots)
ssh root@76.13.106.100
cat /root/clawdbots/tokens.env

# VPS tokens (Treasury/X)
ssh root@72.61.7.126
grep BOT_TOKEN /home/jarvis/Jarvis/lifeos/config/.env
```

---

**Document Status**: ACTIVE
**Next Action**: User must regenerate 4 tokens via @BotFather
**After Regeneration**: Run validation script, then deploy to VPS
