# Jarvis Sentiment Bots & Voice Setup Guide

Quick setup guide for Morgan Freeman voice, Telegram bot, and X sentiment automation.

---

## Table of Contents

1. [Morgan Freeman Voice](#1-morgan-freeman-voice-setup)
2. [Telegram Sentiment Bot](#2-telegram-sentiment-bot)
3. [X (Twitter) Sentiment Bot](#3-x-twitter-sentiment-bot)
4. [Configuration Reference](#4-configuration-reference)

---

## 1. Morgan Freeman Voice Setup

Jarvis uses **Coqui XTTS-v2** for free, local voice cloning. You need a 6-15 second audio sample.

### Step 1: Get Audio Sample

**Option A: Download from soundboard** (easiest)
```bash
# Create the voices directory
mkdir -p data/voices/clones

# Download from a soundboard (example)
# Get a clean 10-15 second clip from:
# - https://www.voicy.network/official-soundboards/movies/morgan-freeman
# - https://www.101soundboards.com/boards/22055-morgan-freeman-soundboard
```

**Option B: Extract from YouTube**
```bash
# Install yt-dlp if needed
pip install yt-dlp

# Download audio from a Morgan Freeman interview
yt-dlp -x --audio-format wav -o "data/voices/clones/morgan_freeman.wav" "YOUTUBE_URL"

# Trim to 10-15 seconds (use Audacity or ffmpeg)
ffmpeg -i data/voices/clones/morgan_freeman.wav -ss 0 -t 15 data/voices/clones/morgan_freeman_trimmed.wav
mv data/voices/clones/morgan_freeman_trimmed.wav data/voices/clones/morgan_freeman.wav
```

### Step 2: Place the Audio File

```
Jarvis/
  data/
    voices/
      clones/
        morgan_freeman.wav   <-- Your 10-15 second clip here
```

### Step 3: Enable Voice Cloning

Edit `lifeos/config/minimax.config.json`:

```json
{
  "voice_clone_enabled": true,
  "voice_clone_voice": "morgan_freeman",
  "voice_clone_language": "en",
  "tts_engine": "voice_clone"
}
```

### Step 4: Test It

```python
from core import voice_clone

# Speak with Morgan Freeman's voice
voice_clone.speak("Hello, I am Jarvis. How may I assist you today?")
```

**Requirements:**
- Python 3.9-3.12
- ~2GB disk space (XTTS model auto-downloads)
- First run takes 2-3 minutes (model download)

---

## 2. Telegram Sentiment Bot

Automated crypto sentiment readings via Telegram.

### Step 1: Create Telegram Bot

1. Open Telegram, search for `@BotFather`
2. Send `/newbot`
3. Follow prompts to name your bot
4. Copy the **API token** (looks like `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`)

### Step 2: Get Your Chat ID

1. Message `@userinfobot` on Telegram
2. It will reply with your **Chat ID** (a number like `123456789`)

### Step 3: Configure Jarvis

Add to `secrets/keys.json`:

```json
{
  "TELEGRAM_BOT_TOKEN": "YOUR_BOT_TOKEN_HERE"
}
```

Create `lifeos/config/telegram_bot.json`:

```json
{
  "enabled": true,
  "chat_ids": [123456789],
  "schedule": {
    "enabled": true,
    "times": ["09:00", "12:00", "17:00", "21:00"]
  },
  "tokens": ["SOL", "BTC", "ETH"],
  "format": {
    "use_emojis": true,
    "include_price": true
  }
}
```

### Step 4: Start the Bot

```python
from core.integrations import telegram_sentiment_bot

# Start scheduled posting
telegram_sentiment_bot.start()

# Manual push (optional)
telegram_sentiment_bot.push_report()
```

Or via CLI:
```bash
python -c "from core.integrations.telegram_sentiment_bot import start; start()"
```

### Schedule Options

| Time (UTC) | Description |
|------------|-------------|
| `"09:00"` | Morning report |
| `"12:00"` | Midday update |
| `"17:00"` | Afternoon recap |
| `"21:00"` | Evening summary |

**Customize frequency:**
```json
{
  "schedule": {
    "times": ["08:00", "20:00"]  // Twice daily
  }
}
```

---

## 3. X (Twitter) Sentiment Bot

Automated sentiment posts to X/Twitter.

### Step 1: Create X Developer Account

1. Go to [developer.twitter.com](https://developer.twitter.com)
2. Sign up for **Free** tier (allows 1,500 tweets/month)
3. Create a new **Project** and **App**

### Step 2: Generate API Keys

In your X Developer Portal App:

1. Go to **Keys and tokens**
2. Generate:
   - **API Key** (Consumer Key)
   - **API Key Secret** (Consumer Secret)
   - **Access Token**
   - **Access Token Secret**

**Important:** Set app permissions to **Read and Write**

### Step 3: Configure Jarvis

Add to `secrets/keys.json`:

```json
{
  "X_API_KEY": "your_api_key",
  "X_API_SECRET": "your_api_secret",
  "X_ACCESS_TOKEN": "your_access_token",
  "X_ACCESS_TOKEN_SECRET": "your_access_token_secret"
}
```

Create `lifeos/config/x_bot.json`:

```json
{
  "enabled": true,
  "schedule": {
    "enabled": true,
    "times": ["08:00", "14:00", "20:00"]
  },
  "tokens": ["SOL", "BTC", "ETH"],
  "post_format": "single",
  "include_hashtags": true,
  "include_disclaimer": true,
  "dry_run": true,
  "cooldown_minutes": 60
}
```

### Step 4: Install Tweepy

```bash
pip install tweepy
```

### Step 5: Test (Dry Run First!)

```python
from core.integrations import x_sentiment_bot

# Check config
bot = x_sentiment_bot.get_bot()
print(f"Configured: {bot.is_configured()}")
print(f"Dry run: {bot.config.get('dry_run')}")

# Test with dry run (won't actually post)
x_sentiment_bot.post_sentiment("SOL")
```

### Step 6: Go Live

Edit `lifeos/config/x_bot.json`:
```json
{
  "dry_run": false  // Set to false when ready
}
```

Start scheduler:
```python
from core.integrations import x_sentiment_bot
x_sentiment_bot.start()
```

### Post Frequency Recommendations

| Tier | Posts/Day | Schedule |
|------|-----------|----------|
| Conservative | 2 | `["09:00", "21:00"]` |
| Moderate | 3 | `["08:00", "14:00", "20:00"]` |
| Active | 4 | `["06:00", "12:00", "18:00", "22:00"]` |

**X Free Tier Limit:** 1,500 posts/month = ~50 posts/day max

---

## 4. Configuration Reference

### secrets/keys.json

```json
{
  "TELEGRAM_BOT_TOKEN": "123456789:ABC...",
  "X_API_KEY": "...",
  "X_API_SECRET": "...",
  "X_ACCESS_TOKEN": "...",
  "X_ACCESS_TOKEN_SECRET": "...",
  "XAI_API_KEY": "..."
}
```

### Voice Configuration

`lifeos/config/minimax.config.json`:
```json
{
  "tts_engine": "voice_clone",
  "voice_clone_enabled": true,
  "voice_clone_voice": "morgan_freeman",
  "voice_clone_language": "en",
  "speak_responses": true
}
```

### Telegram Bot Configuration

`lifeos/config/telegram_bot.json`:
```json
{
  "enabled": true,
  "chat_ids": [123456789],
  "schedule": {
    "enabled": true,
    "times": ["09:00", "12:00", "17:00", "21:00"],
    "timezone": "UTC"
  },
  "tokens": ["SOL", "BTC", "ETH"],
  "include_trending": true,
  "max_trending": 5,
  "format": {
    "use_emojis": true,
    "include_chart_link": true,
    "include_price": true
  }
}
```

### X Bot Configuration

`lifeos/config/x_bot.json`:
```json
{
  "enabled": true,
  "schedule": {
    "enabled": true,
    "times": ["08:00", "14:00", "20:00"],
    "timezone": "UTC"
  },
  "tokens": ["SOL", "BTC", "ETH"],
  "post_format": "single",
  "include_hashtags": true,
  "include_disclaimer": true,
  "dry_run": false,
  "cooldown_minutes": 60
}
```

---

## Quick Start Commands

```bash
# Start both bots
python -c "
from core.integrations import telegram_sentiment_bot, x_sentiment_bot
telegram_sentiment_bot.start()
x_sentiment_bot.start()
print('Bots started!')
"

# Manual Telegram push
python -c "from core.integrations.telegram_sentiment_bot import push_report; push_report()"

# Manual X post (dry run)
python -c "from core.integrations.x_sentiment_bot import post_sentiment; post_sentiment('SOL')"

# Test voice
python -c "from core.voice_clone import speak; speak('Hello, this is Jarvis.')"
```

---

## Troubleshooting

### Voice Clone Not Working

```bash
# Check Python version (needs 3.9-3.12)
python --version

# Reinstall TTS
pip uninstall TTS -y && pip install TTS

# Check audio file
ls -la data/voices/clones/morgan_freeman.wav
```

### Telegram Bot Not Responding

```python
# Test token
import requests
token = "YOUR_TOKEN"
r = requests.get(f"https://api.telegram.org/bot{token}/getMe")
print(r.json())
```

### X API Errors

```python
# Test credentials
import tweepy
client = tweepy.Client(
    consumer_key="...",
    consumer_secret="...",
    access_token="...",
    access_token_secret="..."
)
print(client.get_me())
```

---

## Cost Summary

| Feature | Cost |
|---------|------|
| Morgan Freeman Voice (XTTS) | **FREE** (local) |
| Telegram Bot | **FREE** |
| X Basic API | **FREE** (1,500 posts/mo) |
| Grok Sentiment | ~$0.05/analysis |

**Monthly estimate:** $0-5 depending on sentiment API usage

---

*Last updated: 2026-01-08*
