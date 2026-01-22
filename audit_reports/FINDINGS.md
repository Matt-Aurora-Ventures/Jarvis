# Audit Findings

Date: 2026-01-22

## 1) Telegram Bot
- Entry points: `tg_bot/bot.py`, `tg_bot/bot_core.py`, `tg_bot/public_trading_bot_integration.py`, `tg_bot/treasury_bot_manager.py`
- Current behavior: polling-based bot; admin gating for privileged commands; demo UI flows in `tg_bot/handlers/demo.py`
- Known failures: occasional polling conflicts when multiple instances run with same token
- Root cause: no single-instance guard across multiple entrypoints and helper scripts
- Fix plan: file lock per token; graceful exit when lock is held
- Risk of regression: low; lock is scoped to polling only
- Tests added: `tests/unit/test_instance_lock.py`, `tests/integration/test_telegram_polling_lock.py`

## 2) Trading Engine (positions/history persistence)
- Entry points: `bots/treasury/trading.py`, `tg_bot/handlers/treasury.py`
- Current behavior: canonical state in `data/trader/` with legacy fallback for hidden files
- Known failures: closed trade history persisted to legacy hidden file, missing from canonical store
- Root cause: split write paths and legacy reads without consolidation
- Fix plan: canonicalize paths, migrate legacy on load, keep legacy read-only
- Risk of regression: medium; touches persistence paths
- Tests added: `tests/unit/test_trade_history_migration.py`

## 3) Sentiment Reporter (cooldowns + restart behavior)
- Entry points: `bots/twitter/sentiment_poster.py`, `core/context_engine.py`
- Current behavior: uses context engine timestamps to prevent restart spam
- Known failures: immediate re-post after restart when last post not persisted
- Root cause: state stored in legacy JSON file only
- Fix plan: use canonical context state and record tweet timestamps
- Risk of regression: low; uses existing context engine
- Tests added: `tests/unit/test_sentiment_poster_restart.py`

## 4) Twitter/X Read Degradation
- Entry points: `bots/twitter/twitter_client.py`
- Current behavior: read endpoints can back off on 401/403 with persisted cooldown
- Known failures: repeated 401s causing log spam and hammering on restart
- Root cause: cooldown state not persisted
- Fix plan: persist read-disable state in context engine
- Risk of regression: low; read-only flow
- Tests added: `tests/unit/test_twitter_read_backoff.py`

## 5) CLI / Vibe Coding (Admin-only)
- Entry points: `tg_bot/bot_core.py`, `tg_bot/services/claude_cli_handler.py`
- Current behavior: admin-only `/code` and `/dev`, now supports API mode via local Anthropic-compatible endpoints
- Known failures: CLI-only requirement blocked VPS usage
- Root cause: hard CLI dependency for coding commands
- Fix plan: allow API mode when `ANTHROPIC_BASE_URL` is set; keep CLI fallback
- Risk of regression: medium; command flow changes
- Tests added: `tests/unit/test_code_command_api_mode.py`

## 6) Error Logging + Deduplication
- Entry points: `core/logging/error_tracker.py`, `tg_bot/bot_core.py`
- Current behavior: error tracker deduplicates and scrubs secrets
- Known failures: secret leakage risk in error logs
- Root cause: log sanitization not using scrubber consistently
- Fix plan: apply scrubber before logging/storing errors
- Risk of regression: low
- Tests added: `tests/unit/test_error_tracker.py`

## 7) Supervisor / Orchestration
- Entry points: `bots/supervisor.py`, `tg_bot/public_trading_bot_integration.py`
- Current behavior: multi-component orchestration with polling lock enforcement
- Known failures: duplicate polling instances
- Root cause: lack of global instance lock
- Fix plan: lock per token at polling startup
- Risk of regression: low
- Tests added: `tests/integration/test_telegram_polling_lock.py`

## 8) State Consistency / Migration
- Entry points: `data_migrations/001_state_consolidation.py`, `core/state_paths.py`
- Current behavior: canonical state in `data/trader/` with legacy merge path
- Known failures: fragmented JSON stores and hidden legacy state
- Root cause: multiple historical persistence locations
- Fix plan: idempotent migration script and canonical read paths
- Risk of regression: medium (data integrity)
- Tests added: `tests/unit/test_state_consolidation_migration.py`
