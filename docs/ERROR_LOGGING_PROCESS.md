# Error Logging & Audit Process

This document captures the new telemetry, auditing, and escalation steps for the Jarvis Telegram + Treasury systems. It applies equally whether you are running locally or on the VPS.

## 1. Centralized Logging

The shared helper `core/logging_utils.configure_component_logger` now ensures every log record from a component is duplicated into:

- `<repo>/logs/telegram_bot.log` / `telegram_bot_errors.log`
- `<repo>/logs/treasury_bot.log` / `treasury_bot_errors.log`

Each entry is rotated at 5 MB with 7 backup files and uses `%(asctime)s %(levelname)s %(name)s %(message)s` so timestamps, severity, and module names are preserved. The handlers are attached to the `tg_bot` and `bots.treasury` logger namespaces, so every handler, callback, and trading event inherits the same disk-backed audit trail. Console output is preserved via the existing `logging.basicConfig` call.

## 2. Telegram CLI-First Safety

- Coding requests (prefixed with `vibe:`, `code:`, etc.) are still routed exclusively through `tg_bot.services.claude_cli_handler`.
- CLI failures now short-circuit the flow and return immediately after sending a failure notice, preventing the fallback `ChatResponder` (which would call the Claude API) from replying to the same update.
- All CLI and handler errors are written to `logs/telegram_bot_errors.log`; this makes `/help`/inline button failures observable across both local development and the VPS supervisor logs.

## 3. Treasury Bot Logging

The treasury runner now configures `bots.treasury` to log to `logs/treasury_bot*.log`. Errors from trading operations, Telegram UI buttons, or the Jupiter client flow are captured with stack traces and persisted without touching stdout.

## 4. Audit Workflow (Last 12 Hours)

1. Run the audit script with `python scripts/audit_recent_errors.py --hours 12`. It scans:
   - `logs/telegram_bot_errors.log`
   - `logs/treasury_bot_errors.log`
   - `logs/supervisor.log`
   - `logs/bots.log`
   Additional logs can be appended with `--files /path/to/extra.log`.
2. The script prints the number of ERROR/CRITICAL lines within the window and shows the 5 most recent entries per file. Use this after deployments or before troubleshooting a failing feature.
3. On the VPS, the same script can be scheduled or hooked into cron/`systemd` to feed alerts into the monitoring channel.

## 5. Troubleshooting Steps

1. If `/help` buttons or treasury trades fail, tail the primary log:
   ```bash
   tail -n 200 logs/telegram_bot_errors.log
   tail -n 200 logs/treasury_bot_errors.log
   ```
2. Correlate with `logs/supervisor.log` if the process crashed (`grep ERROR logs/supervisor.log`).
3. After addressing the root cause (e.g., missing CLI, API rate limit, wallet issue), rerun the audit script to ensure zero recent errors.

## 6. Future Enhancements

- Hook the audit script into alerting (e.g., sending a digest to the private Telegram group) whenever new errors appear.
- Extend the helper to capture structured metadata (callback data, command name, user id) if needed.
