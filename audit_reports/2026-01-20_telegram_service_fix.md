# Telegram Service Fix - 2026-01-20

## Observations
- `jarvis-telegram` crashed on VPS with `ModuleNotFoundError: No module named 'tg_bot.sessions'`.
- After syncing `tg_bot/sessions`, the next failure was `Permission denied` opening `/home/jarvis/Jarvis/data/locks/telegram_polling_*.lock`.
- Chart generation warning (`matplotlib not available`) is non-fatal.

## Actions taken (VPS)
- Copied `tg_bot/sessions` to `/home/jarvis/Jarvis/tg_bot/` and set ownership to `jarvis:jarvis`.
- Fixed lock permissions: `chown -R jarvis:jarvis /home/jarvis/Jarvis/data/locks`.
- Removed stale polling lock file and restarted `jarvis-telegram`.
- Normalized repo ownership: `sudo chown -R jarvis:jarvis /home/jarvis/Jarvis` to prevent future deploy permission errors.

## Result
- `jarvis-telegram` is running normally after restart.

## Follow-ups
- Ensure future deploys include `tg_bot/sessions` to avoid missing-module crashes.
- If chart uploads are required, install `matplotlib` in the venv.
