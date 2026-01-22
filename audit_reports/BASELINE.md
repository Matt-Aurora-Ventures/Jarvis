# Baseline (Pre-Audit)

Date: 2026-01-22

## Repo State
- Branch: fix/audit_codex52_fullstack
- Git SHA: c17522d9dc7859467e6810c87953c6bf3d5d7648

## Environment
- OS: Microsoft Windows 11 Home (10.0.26200, Build 26200)
- Python: 3.12.10

## How to Run
### Demo bot
- Start Telegram bot: `python tg_bot/bot.py` (or `python bots/supervisor.py` to run all)
- In Telegram chat, run `/demo` to enter demo UI

### Non-demo bot
- Telegram bot only: `python tg_bot/bot.py`
- Full supervisor stack: `python bots/supervisor.py`
- Windows quick start: `start_jarvis.bat`

## Key Entrypoints
- Telegram bot: `tg_bot/bot.py`
- Demo UI handlers: `tg_bot/handlers/demo.py`
- Public trading bot integration: `tg_bot/public_trading_bot_integration.py`
- Trading engine: `bots/treasury/trading.py`
- Treasury runner: `bots/treasury/run_treasury.py`
- Twitter bot: `bots/twitter/run_autonomous.py`
- Supervisor: `bots/supervisor.py`
- Daemon (desktop): `jarvis_daemon.py`
