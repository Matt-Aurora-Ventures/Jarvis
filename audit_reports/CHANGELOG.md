# Audit Changelog

Date: 2026-01-22

## Telegram
- Added single-instance polling locks across bot entrypoints and helpers.
  - `tg_bot/bot.py`
  - `tg_bot/public_trading_bot_integration.py`
  - `tg_bot/treasury_bot_manager.py`
  - `tg_bot/get_my_id.py`
- Added `/errors` command (admin) and scrubbed error logging.
  - `tg_bot/handlers/admin.py`
  - `tg_bot/bot.py`
  - `tg_bot/bot_core.py`
  - `core/logging/error_tracker.py`

## Trading State + Persistence
- Canonicalized trade history/positions under `data/trader/` and migrated legacy files.
  - `bots/treasury/trading.py`
  - `tg_bot/handlers/treasury.py`
  - `tg_bot/handlers/commands/export_command.py`
  - `core/state_paths.py`
  - `core/backup/disaster_recovery.py`
- Added consolidation migration script and plan.
  - `data_migrations/001_state_consolidation.py`
  - `data_migrations/PLAN.md`
- Added TP/SL remediation: legacy records default TP/SL, invalid TP/SL inputs fall back to defaults.
  - `bots/treasury/trading.py`

## Sentiment + Twitter
- Persisted cooldown state via context engine to prevent restart spam.
  - `core/context_engine.py`
  - `bots/twitter/sentiment_poster.py`
  - `bots/twitter/bot.py`
- Persisted X read-disable cooldown to avoid restart hammering.
  - `bots/twitter/twitter_client.py`
- Added error tracker coverage for sentiment poster and X client error paths.
  - `bots/twitter/sentiment_poster.py`
  - `bots/twitter/twitter_client.py`
- Defaulted tweet length truncation to 4000 chars (Premium-capable) with env override.
  - `bots/twitter/twitter_client.py`

## Claude / Local Models
- Enabled API mode for `/code` and `/dev` when `ANTHROPIC_BASE_URL` is set.
  - `tg_bot/services/claude_cli_handler.py`
  - `tg_bot/bot_core.py`
- Documented local model setup for VPS and local.
  - `RUNBOOK.md`
  - `DEPLOYMENT_GUIDE.md`
  - `DEPLOYMENT_CHECKLIST.md`
  - `env.example`

## Demo Parity (Golden Tests)
- Added demo golden harness and snapshots.
  - `tests/demo_golden/harness.py`
  - `tests/demo_golden/test_demo_golden.py`
  - `tests/demo_golden/README.md`
  - `tests/demo_golden/golden/*.json`

## Tests + Verification
- Instance lock tests.
  - `tests/unit/test_instance_lock.py`
  - `tests/integration/test_telegram_polling_lock.py`
- Error tracker dedup test.
  - `tests/unit/test_error_tracker.py`
- Sentiment restart + duplicate tests.
  - `tests/unit/test_sentiment_poster_restart.py`
- Trade history migration + restart tests.
  - `tests/unit/test_trade_history_migration.py`
- State migration idempotency test.
  - `tests/unit/test_state_consolidation_migration.py`
- Twitter read backoff tests.
  - `tests/unit/test_twitter_read_backoff.py`
- `/code` API-mode tests.
  - `tests/unit/test_code_command_api_mode.py`
- Verification script.
  - `scripts/verify_v1.py`

## Telegram UI + Admin Safety
- Enforced server-side admin checks for quick-command callbacks and aligned callback routing to real handlers.
  - `tg_bot/handlers/commands/quick_command.py`
- Backward-compatible admin checks in handler wrapper.
  - `tg_bot/handlers/__init__.py`

## Security + Test Stability
- Avoided pytest capture breakage by not re-wrapping stdout during tests.
  - `bots/treasury/display.py`
- Fixed secrets manager cache/audit lock deadlock.
  - `core/security/enhanced_secrets_manager.py`
