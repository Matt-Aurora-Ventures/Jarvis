# SECURITY ALERT - Exposed API Credentials in Git History

**Status:** ACTION REQUIRED
**Date:** 2026-01-17 04:15 UTC
**Severity:** HIGH

---

## Issue Found

**Exposed Telegram Bot Token** in git commit `bfc8d2d` (v4.6.0):
```
TELEGRAM_BOT_TOKEN=8047602125:AAES1dmr8sSyaxpLTxBJacVxfnLaLaqcLcE
TELEGRAM_ADMIN_IDS=8527130908
```

This token exists in the public git history on GitHub and can be accessed by anyone with repository access.

---

## Immediate Actions Required

### 1. Rotate Telegram Bot Token (URGENT)

```bash
# On Telegram, contact @BotFather and say:
/revoke

# Then select your bot @Jarviskr8tivbot
# This will invalidate the old token immediately

# Get new token:
/newtoken
# Select @Jarviskr8tivbot again
# BotFather will generate a new token
```

### 2. Update Local Secrets

**File:** `tg_bot/.env`
```bash
# Replace old token with new one from BotFather
TELEGRAM_BOT_TOKEN=<NEW_TOKEN_FROM_BOTFATHER>
```

**File:** `secrets/keys.json`
```bash
# Update telegram bot_token with new token
nano secrets/keys.json
```

### 3. Update VPS Deployment

If you've already deployed to VPS, SSH in and update:
```bash
ssh root@72.61.7.126
nano /home/jarvis/Jarvis/secrets/keys.json
# Update bot_token to new one
systemctl restart jarvis-telegram
```

### 4. Regenerate Custom Deployment Script

```bash
cd "C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis"
python scripts/create_deployment_with_keys.py
# When prompted, enter the NEW Telegram bot token from BotFather
```

---

## Other Credentials Checked

✅ **Groq API Key** - NOT exposed (gsk_... key not found in git history)
✅ **Anthropic API Key** - NOT exposed
✅ **XAI API Key** - NOT exposed
✅ **Twitter API Keys** - NOT exposed
✅ **BirdEye API Key** - NOT exposed
✅ **Helius API Key** - NOT exposed

---

## Root Cause

This token was accidentally committed in commit `bfc8d2d` when it was part of a LaunchDarkly configuration file. The `tg_bot/.env` and `secrets/keys.json` files are now properly in `.gitignore` to prevent this in the future.

---

## Prevention Going Forward

**Current Protections:**
- ✅ `.gitignore` includes `tg_bot/.env`
- ✅ `.gitignore` includes `secrets/`
- ✅ `.gitignore` includes `.env*`
- ✅ GitHub Push Protection enabled (blocks commits with API key patterns)

**Best Practices:**
1. Never commit `.env` files
2. Never commit `secrets/keys.json`
3. Use GitHub's secret scanning (already enabled)
4. Regularly rotate API tokens as precaution
5. Review git history quarterly for accidental commits

---

## Timeline

| Time | Action |
|------|--------|
| 2026-01-17 04:15 | Security audit completed - exposed token found |
| 2026-01-17 04:16 | Telegram token requires immediate rotation |
| ASAP | Execute BotFather token rotation |
| ASAP | Update all local and deployed configurations |

---

## Contacts

- **Telegram BotFather:** @BotFather on Telegram
- **GitHub Security:** https://github.com/settings/security
- **Local Review:** Check for other exposed credentials in git history

---

**NEXT STEPS:**
1. ✅ Rotate Telegram bot token NOW
2. Update local .env and secrets/keys.json
3. Regenerate deployment script with new token
4. If already deployed, SSH to VPS and update there
5. Restart Telegram bot service

**Status:** Awaiting Telegram token rotation
