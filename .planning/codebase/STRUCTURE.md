# Jarvis Directory Structure
Generated: 2026-01-24

## Top-Level Overview
Jarvis/
├── api/                    FastAPI REST API server
├── bots/                   Bot implementations
├── core/                   Core business logic
├── tg_bot/                 Telegram bot
├── integrations/           External API integrations
├── lifeos/                 LifeOS context, config
├── scripts/                Utility scripts
├── tests/                  Test suite
├── deployment/             Deployment configs
├── .env                    Environment variables
└── pyproject.toml          Python project config

## Key Directories

### bots/ - Bot Implementations
- supervisor.py - Main supervisor (ENTRY POINT)
- treasury/ - Trading bot (Jupiter DEX)
- buy_tracker/ - KR8TIV buy tracking
- twitter/ - X/Twitter bots
- bags_intel/ - Bags.fm monitoring

### core/ - Core Services
- dexter/ - ReAct autonomous agent
- trading/ - Trading logic, signals
- llm/ - Claude, Grok, Ollama
- memory/ - Deduplication, archival
- security/ - Secrets, audit trail
- monitoring/ - Health, heartbeat

### tg_bot/ - Telegram Bot
- bot.py - Main entry point
- handlers/ - Command handlers
- services/ - Chat responder

### integrations/ - External APIs
- birdeye/ - Token data
- dexscreener/ - Trending tokens
- coinglass/ - Liquidations
- helius/ - Solana blockchain

## State Files

~/.lifeos/trading/
- exit_intents.json - Planned exits
- lut_module_state.json - LUT state

bots/treasury/
- .positions.json - Current positions

bots/twitter/
- .grok_state.json - Grok cost tracking

## Key Files

Configuration:
- .env - Environment variables
- pyproject.toml - Python config

Entry Points:
- bots/supervisor.py - Main supervisor
- tg_bot/bot.py - Telegram bot
- api/fastapi_app.py - API server

Core:
- core/context_loader.py - Jarvis capabilities
- core/safe_state.py - Safe state access
- core/dexter/agent.py - ReAct agent
- core/trading/decision_matrix.py - Signal aggregation

## Naming Conventions

Directories: lowercase_with_underscores
Files: lowercase_with_underscores.py
Classes: PascalCase
Functions: lowercase_with_underscores()

## Where to Add New Code

New Bot:
1. Create bots/my_bot/bot.py
2. Register in bots/supervisor.py

New Command:
1. Create tg_bot/handlers/commands/my_command.py
2. Register in tg_bot/bot.py

New Signal:
1. Create core/trading/signals/my_signal.py
2. Add to DecisionMatrix

New API Endpoint:
1. Create api/routes/my_route.py
2. Register in api/fastapi_app.py
