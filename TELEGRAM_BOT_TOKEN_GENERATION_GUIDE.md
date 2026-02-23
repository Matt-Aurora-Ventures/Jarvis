# Telegram Bot Token Generation Guide

## CRITICAL: Fixing Polling Conflicts

**Problem**: Multiple Telegram bots are crashing due to polling conflicts - they're all trying to use the same token.

**Solution**: Create separate bot tokens for each bot component.

---

## Manual Steps (via @BotFather on Telegram)

### 1. Open Telegram Web
- Go to https://web.telegram.org/a/
- Already logged in

### 2. Search for BotFather
1. Click on the search box (top left)
2. Type: `@BotFather`
3. Click on "BotFather" with the verified checkmark (3,982,993 monthly users)

### 3. For Each Bot, Generate/Regenerate Token

#### A. Treasury Bot (CRITICAL - Currently Crashing)
```
/mybots
→ Select "Jarvis Trading Bot" or create new bot
→ If creating new: /newbot
   - Name: "Treasury Bot"
   - Username: "jarvis_treasury_bot" (must end in 'bot')
→ If regenerating existing token:
   - Click on bot → "API Token" → "Regenerate Token"
→ Copy the token (format: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz)
→ Save as: TREASURY_BOT_TOKEN=<token>
```

#### B. Buy Tracker Bot
```
/mybots
→ Select existing or create new
/newbot
   - Name: "Buy Tracker Bot"
   - Username: "jarvis_buy_tracker_bot"
→ Copy token
→ Save as: BUY_TRACKER_BOT_TOKEN=<token>
```

#### C. Sentiment Reporter Bot
```
/mybots
→ Select existing or create new
/newbot
   - Name: "Sentiment Reporter Bot"
   - Username: "jarvis_sentiment_bot"
→ Copy token
→ Save as: SENTIMENT_REPORTER_BOT_TOKEN=<token>
```

#### D. Twitter Poster Bot (if needed)
```
/mybots
→ Select existing or create new
/newbot
   - Name: "Twitter Poster Bot"
   - Username: "jarvis_twitter_poster_bot"
→ Copy token
→ Save as: TWITTER_POSTER_BOT_TOKEN=<token>
```

### 4. Save Tokens Securely

Create a temporary file with all tokens:

```bash
# Save to: C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\telegram_bot_tokens.txt

TREASURY_BOT_TOKEN=<your_token_here>
BUY_TRACKER_BOT_TOKEN=<your_token_here>
SENTIMENT_REPORTER_BOT_TOKEN=<your_token_here>
TWITTER_POSTER_BOT_TOKEN=<your_token_here>
```

**DO NOT commit this file to git!**

### 5. Update .env File

Add the new tokens to `lifeos/config/.env`:

```bash
# Telegram Bot Tokens (Separate tokens to avoid polling conflicts)
TELEGRAM_BOT_TOKEN=<main_jarvis_bot_token>
TREASURY_BOT_TOKEN=<treasury_bot_token>
BUY_TRACKER_BOT_TOKEN=<buy_tracker_bot_token>
SENTIMENT_REPORTER_BOT_TOKEN=<sentiment_reporter_bot_token>
```

### 6. Update Bot Code

Each bot component needs to use its specific token:

**File**: `bots/treasury/trading.py` or wherever Treasury bot initializes
```python
# Before
bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))

# After
bot = Bot(token=os.getenv("TREASURY_BOT_TOKEN"))
```

**File**: `bots/buy_tracker/main.py`
```python
bot = Bot(token=os.getenv("BUY_TRACKER_BOT_TOKEN"))
```

**File**: `bots/sentiment_reporter.py`
```python
bot = Bot(token=os.getenv("SENTIMENT_REPORTER_BOT_TOKEN"))
```

---

## Alternative: Use Telegram Bot API Directly

If web interface is problematic, use the Bot API via curl:

### Get Bot Info (verify token works)
```bash
curl https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getMe
```

### List Your Bots
Unfortunately, there's no direct API to list all bots. You must:
1. Check your existing `.env` file for current tokens
2. Use @BotFather web interface
3. Check your Telegram chat history with @BotFather

---

## Verification

After creating tokens, verify each one works:

```bash
# Test treasury bot token
curl https://api.telegram.org/bot<TREASURY_BOT_TOKEN>/getMe

# Test buy tracker bot token
curl https://api.telegram.org/bot<BUY_TRACKER_BOT_TOKEN>/getMe

# Test sentiment reporter bot token
curl https://api.telegram.org/bot<SENTIMENT_REPORTER_BOT_TOKEN>/getMe
```

Each should return JSON with bot info, not an error.

---

## Critical Next Steps

1. Generate the tokens manually via @BotFather
2. Save them to `telegram_bot_tokens.txt`
3. Update `lifeos/config/.env`
4. Update bot initialization code to use the new tokens
5. Restart the supervisor: `python bots/supervisor.py`
6. Monitor logs for polling errors - should be gone

---

## Why This Fixes The Problem

**Root Cause**: Multiple bot instances (treasury_bot, buy_tracker, sentiment_reporter) all using the same `TELEGRAM_BOT_TOKEN`, causing Telegram's "Conflict: terminated by other getUpdates request" error.

**Fix**: Each bot gets its own unique token, eliminating polling conflicts.

**Error Code 429967295**: This is the exit code from the Telegram polling conflict. Separate tokens = no more conflicts.

---

## Reference

- Telegram Bot API Docs: https://core.telegram.org/bots/api
- BotFather Commands: https://core.telegram.org/bots#6-botfather
- Error 409 (Conflict): https://core.telegram.org/bots/api#getupdates

