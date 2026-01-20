# Twitter Posting Audit - 2026-01-19

## Observations
- `logs/supervisor.log` showed repeated `401 Unauthorized` errors for `get_mentions`, `search_recent`, and `get_tweet` while OAuth1 posting succeeded.
- VPS `jarvis-twitter` service was in a restart loop due to `PermissionError` reading `/home/jarvis/Jarvis/secrets/keys.json`.
- After fixing permissions and restarting, the bot posted successfully: https://x.com/Jarvis_lifeos/status/2013400066145370577.
- `get_mentions` still emits `401 Unauthorized` on VPS (read endpoints failing while posting works).

## Environment checks (local)
- `bots/twitter/.env` exists with expected key names; `CRYPTOPANIC_API_KEY` is empty.
- `bots/supervisor.py` loads env from `tg_bot/.env`, `bots/twitter/.env`, and root `.env`.

## Risk/impact
- Read failures can spam logs and degrade autonomy (mentions, self-learning metrics, spam scan).
- `X_BOT_ENABLED` only gated the X CLI handler; automated posting did not honor the kill switch.

## Actions taken
- Added `X_BOT_ENABLED` gate to the autonomous X posting loop and sentiment poster.
- Fixed VPS permissions: `chown -R jarvis:jarvis /home/jarvis/Jarvis/secrets` and restarted `jarvis-twitter`.
- Added a read-endpoint cooldown in `bots/twitter/twitter_client.py` to suppress repeated 401s.

## Next steps on VPS
- If `401` persists for read endpoints, verify X app access level includes v2 read, or rotate tokens with read permissions.
- Consider suppressing or degrading mention/search calls when X returns `401` to reduce log noise.
