# JARVIS - Claude Code Context

## Project Overview
Jarvis is an autonomous LifeOS trading and AI assistant system running on Solana.

## Key Directories
- `core/` - Main Python modules (trading, bots, execution, risk management)
- `bots/` - Bot implementations (Telegram, Twitter/X, Treasury, Buy Tracker)
- `tg_bot/` - Telegram bot handlers and services
- `api/` - API server and handlers
- `lifeos/config/` - Configuration files
- `scripts/` - Automation and utility scripts
- `~/.lifeos/trading/` - Runtime state files

## Current State Access
- Position state: `bots/treasury/.positions.json`
- Exit intents: `~/.lifeos/trading/exit_intents.json`
- Grok state: `bots/twitter/.grok_state.json`
- Execution logs: Check supervisor output

## Critical Files
- `bots/supervisor.py` - Main supervisor that orchestrates all components
- `bots/treasury/trading.py` - Treasury trading engine (Jupiter DEX)
- `bots/twitter/x_claude_cli_handler.py` - X/Twitter CLI command handler
- `bots/twitter/autonomous_engine.py` - Autonomous posting engine
- `bots/buy_tracker/sentiment_report.py` - Sentiment analysis and reporting
- `tg_bot/services/chat_responder.py` - Telegram chat handler
- `core/context_loader.py` - Shared Jarvis context/capabilities

## Active Configurations
- Max positions: 50 (treasury/trading.py, position_manager.py)
- Grok daily cost limit: $10 (tg_bot/config.py)
- X Bot circuit breaker: 60s min interval, 30min cooldown after 3 errors

## How to Execute Actions
```python
# Example: Post to X
from bots.twitter.twitter_client import TwitterClient
client = TwitterClient()
await client.post_tweet("Message here")

# Example: Check positions
from bots.treasury.trading import TreasuryTrader
trader = TreasuryTrader()
positions = trader.get_open_positions()

# Example: Get Jarvis capabilities
from core.context_loader import JarvisContext
caps = JarvisContext.get_capabilities()
```

## Environment Variables
- `X_BOT_ENABLED` - Kill switch for X posting (true/false)
- `LIFEOS_KILL_SWITCH` - Emergency trade halt
- `TREASURY_LIVE_MODE` - Enable live trading (vs dry run)
- `TELEGRAM_BOT_TOKEN` - Telegram API token
- `JARVIS_ACCESS_TOKEN` - Twitter OAuth for @Jarvis_lifeos

## Running the System
```bash
# Start all bots via supervisor
python bots/supervisor.py

# Components managed:
# - buy_bot: KR8TIV token tracking
# - sentiment_reporter: Hourly market reports
# - twitter_poster: Grok sentiment tweets
# - telegram_bot: Telegram interface
# - autonomous_x: Autonomous X posting
```

## Key Features
1. **Autonomous Trading**: Jupiter DEX integration for Solana tokens
2. **Sentiment Analysis**: Grok AI for token scoring
3. **X/Twitter Bot**: @Jarvis_lifeos posts market updates
4. **Telegram Integration**: Full admin interface via @Jarviskr8tivbot
5. **CLI Commands**: Admin can execute code via X mentions

## Recent Fixes (2026-01-15)
1. X bot circuit breaker to prevent spam loops
2. Max positions increased to 50
3. Telegram bot context enhanced with capabilities
4. Grok daily cost limit increased to $10
