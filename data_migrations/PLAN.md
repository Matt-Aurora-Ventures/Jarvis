# State Migration Plan

## Goals
- Preserve all existing data (no deletions)
- Define one canonical store per domain
- Make migrations idempotent and safe to re-run
- Stop writing to deprecated stores after migration

## Hidden / Legacy Files
- `bots/treasury/.trade_history.json` → migrate into `data/trader/trade_history.json` (canonical)
- `bots/treasury/.positions.json` → migrate into `data/trader/open_positions.json` (canonical)
- `bots/treasury/.daily_volume.json` → migrate into `data/trader/daily_volume.json` (canonical)
- Keep legacy files, mark as deprecated (rename to `*.migrated` or leave read-only)

## Duplicate Databases
- `data/jarvis.db` is the canonical error log + metrics DB (verify table usage)
- `data/jarvis_x_memory.db` remains canonical for X/Twitter dedupe
- Identify any duplicate sqlite dbs (e.g., `database.db`, `custom.db`) used for overlapping domains; consolidate reads to canonical and stop writes to secondary DBs

## Fragmented JSON Stores
- `data/context_state.json`, `data/cooldown_state.json`, `data/jarvis_state.json` -> consolidate into a single canonical state record (choose `data/context_state.json` as canonical)
- `data/treasury_scorekeeper.json`, `data/treasury_orders.json`, `data/limit_orders.json` -> map into trading domain canonical storage

## Migration Script (data_migrations/001_state_consolidation.py)
- Detect existing stores and merge data safely
- De-duplicate by stable IDs (trade_id, position_id, tweet_id)
- Write canonical outputs
- Emit a migration report to `data_migrations/migration_001_report.json`
- Idempotent: running twice yields the same canonical store

## Rollback
- Do not delete or overwrite legacy files; only create new canonical stores and leave legacy as read-only or renamed
- Keep a timestamped backup copy of canonical before writing if it already exists
