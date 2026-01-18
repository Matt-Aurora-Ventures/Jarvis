# JARVIS Quick Start Guide

Get JARVIS running in 5 minutes.

## Prerequisites

- Python 3.10+
- Git
- Telegram account (for bot interface)
- Optional: X/Twitter developer account

## Step 1: Clone and Setup (2 minutes)

```bash
# Clone the repository
git clone https://github.com/Matt-Aurora-Ventures/Jarvis.git
cd Jarvis

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Step 2: Configure Environment (1 minute)

```bash
# Copy example environment file
cp .env.example .env
```

Edit `.env` with your credentials:

```bash
# REQUIRED: Telegram Bot Token
# Get from @BotFather on Telegram
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
JARVIS_ADMIN_USER_ID=your_telegram_user_id

# OPTIONAL: X/Twitter Integration
X_API_KEY=your_x_api_key
X_API_SECRET=your_x_api_secret
JARVIS_ACCESS_TOKEN=your_access_token

# OPTIONAL: AI Providers
GROQ_API_KEY=your_groq_key         # Free tier available
XAI_API_KEY=your_grok_key          # For Grok sentiment
```

### Get Your Telegram User ID

1. Message @userinfobot on Telegram
2. It will reply with your user ID
3. Use this for `JARVIS_ADMIN_USER_ID`

## Step 3: Start JARVIS (1 minute)

```bash
# Start all bots via supervisor
python bots/supervisor.py
```

You should see:

```
============================================================
  JARVIS BOT SUPERVISOR
  Robust bot management with auto-restart
============================================================

Health endpoint: http://localhost:8080/health

Registered components:
  - buy_bot
  - sentiment_reporter
  - twitter_poster
  - telegram_bot
  - autonomous_x
  - autonomous_manager

Starting supervisor (Ctrl+C to stop)...
```

## Step 4: Verify (1 minute)

### Check Health Endpoint

```bash
curl http://localhost:8080/health
```

Expected response:

```json
{
  "status": "ok",
  "components": {
    "telegram_bot": {"status": "running"},
    "sentiment_reporter": {"status": "running"}
  }
}
```

### Test Telegram Bot

1. Open Telegram
2. Find your bot (search by the name you gave @BotFather)
3. Send `/help`
4. JARVIS should respond with available commands

## Common Commands

| Command | Description |
|---------|-------------|
| `/help` | List all commands |
| `/sentiment` | Get market sentiment report |
| `/trending` | Show trending Solana tokens |
| `/analyze SOL` | Deep analysis of a token |
| `/price SOL` | Get current price |
| `/portfolio` | View open positions |

## Troubleshooting

### Bot Not Responding

1. Check if supervisor is running:
   ```bash
   curl http://localhost:8080/health
   ```

2. Check logs:
   ```bash
   # Windows
   type logs\supervisor.log

   # Linux/macOS
   tail -f logs/supervisor.log
   ```

3. Verify Telegram token:
   ```bash
   # Should not be empty
   echo $TELEGRAM_BOT_TOKEN
   ```

### Import Errors

If you see import errors, ensure dependencies are installed:

```bash
pip install -r requirements.txt
```

### Permission Errors

Ensure you have write access to:
- `~/.lifeos/` (user data directory)
- `logs/` (log files)

### Port Already in Use

If port 8080 is taken:

```bash
# Check what's using the port
netstat -an | grep 8080

# Or use a different port
export HEALTH_PORT=8081
python bots/supervisor.py
```

## Next Steps

### Enable Trading (Optional)

```bash
# In .env, enable live trading
TREASURY_LIVE_MODE=true
```

**WARNING**: Only enable after thorough testing. Start with paper trading.

### Configure X/Twitter Bot (Optional)

```bash
# In .env
X_BOT_ENABLED=true
X_API_KEY=your_key
X_API_SECRET=your_secret
```

### Enable Public Trading Bot (Optional)

```bash
# In .env
PUBLIC_BOT_TELEGRAM_TOKEN=your_public_bot_token
PUBLIC_BOT_LIVE_TRADING=false  # Start with paper trading
```

## Configuration Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | Main Telegram bot token |
| `JARVIS_ADMIN_USER_ID` | Yes | Your Telegram user ID |
| `GROQ_API_KEY` | No | For LLM responses |
| `XAI_API_KEY` | No | For Grok sentiment |
| `X_API_KEY` | No | X/Twitter integration |
| `TREASURY_LIVE_MODE` | No | Enable live trading |

## Architecture Overview

```
JARVIS
  |
  +-- bots/supervisor.py (Process Manager)
        |
        +-- telegram_bot (User Interface)
        +-- sentiment_reporter (Market Analysis)
        +-- twitter_poster (X Integration)
        +-- autonomous_x (Autonomous Posting)
        +-- buy_bot (Token Tracking)
        +-- autonomous_manager (Self-Improvement)
```

## Resources

- [API Documentation](./API_DOCUMENTATION.md)
- [Deployment Guide](./DEPLOYMENT_GUIDE.md)
- [Troubleshooting](./TROUBLESHOOTING.md)
- [Security Guidelines](./SECURITY_GUIDELINES.md)
- [FAQ](./FAQ.md)

## Support

- **GitHub Issues**: For bugs and feature requests
- **Telegram**: Message your bot for help
- **Documentation**: Check `docs/` folder

---

**Estimated Total Time**: 5 minutes

**Last Updated**: 2026-01-18
