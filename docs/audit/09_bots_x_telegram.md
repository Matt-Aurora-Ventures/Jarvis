# X + Telegram Bots Audit (2026-01-12)

## Scope
- X bot stacks: `bots/twitter`, `core/social/twitter_bot.py`, `core/integrations/x_sentiment_bot.py`, `bots/grok_imagine`.
- Telegram bot stacks: `tg_bot`, `bots/buy_tracker`, `core/integrations/telegram_sentiment_bot.py`.
- Treasury buy flow: `bots/treasury/trading.py`, `bots/buy_tracker/ape_buttons.py`.
- Credential sources: `tg_bot/.env`, `bots/twitter/.env`, `.env`, `secrets/keys.json`, `lifeos/config/*.json`.

## Credential + Connectivity Map
### X
- Primary posting path: `bots/twitter/twitter_client.py` (OAuth2 user context for posting; OAuth1 via tweepy for media).
- OAuth2 setup: `bots/twitter/oauth_setup.py` (PKCE, localhost callback).
- Video workflow: `bots/grok_imagine` (Playwright + cookies), then post via `bots/grok_imagine/post_to_x.py` or `bots/twitter/bot.py`.
- Secondary/legacy path: `core/social/twitter_bot.py` (tweepy OAuth1).
- Sentiment poster: `bots/twitter/sentiment_poster.py` (Claude -> TwitterClient).

### Telegram
- Main chat bot: `tg_bot/bot.py` (admin-gated commands + optional auto-replies).
- Buy bot + ape buttons: `bots/buy_tracker/bot.py`, `bots/buy_tracker/ape_buttons.py`.
- Sentiment reporter: `bots/buy_tracker/sentiment_report.py`.
- Legacy sentiment bot: `core/integrations/telegram_sentiment_bot.py` (config + secrets file).

## Current Env State (presence only)
- X credentials are set only in `bots/twitter/.env`.
- Telegram credentials are set only in `tg_bot/.env`.
- `X_EXPECTED_USERNAME` is unset across all env files.
- `X_VIDEO_PATH`/`X_VIDEO_DIR` are unset (no video uploads configured).
- `XAI_API_KEY` differs between `tg_bot/.env` and `bots/twitter/.env` (mismatch).
- `TELEGRAM_BUY_BOT_TOKEN` is unset (buy bot shares the main bot token).
- `lifeos/config/x_bot.json` and `lifeos/config/telegram_bot.json` are missing (legacy bots run on defaults with no chat_ids configured).

## Findings (ordered by severity)
### Critical
1) Multiple X posting pipelines can run concurrently and use different credential sources. This can look like "random posting" from unintended accounts if more than one entrypoint is launched (e.g., `bots/twitter/*` + `core/social/twitter_bot.py`).  
2) `bots/grok_imagine/x_cookies.json` exists in repo and contains live auth cookies. This is a security risk and can be the source of accidental account actions if reused across environments.

### High
3) Media upload requires OAuth1 credentials (tweepy) that must match the OAuth2 account. If OAuth1 belongs to a different account, video uploads will fail or post to the wrong account.  
4) `X_EXPECTED_USERNAME` is unset, so any module not defaulting to `jarvis_lifeos` can post as whichever OAuth1 account is configured.  
5) `XAI_API_KEY` mismatch across env files causes inconsistent Grok outputs and rate limit behavior between Telegram and X workflows.  
6) Buy bot and main bot share the same Telegram token; buy bot disables polling in that case, so callback buttons can silently stop working if only the buy bot is running.

### Medium
7) `TELEGRAM_ADMIN_CHAT_ID` is unset; any module expecting this for push notifications will fail or skip sending.  
8) Grok Imagine automation depends on cookies and a brittle browser UI; cookie expiry or selector changes break video generation.  
9) OAuth2 refresh requires `offline.access` and valid client credentials; expired tokens will hard-fail posting.

### Low
10) `X_VIDEO_PATH`/`X_VIDEO_DIR` are unset; Grok Imagine video will never attach even if generated.

## What Works (validated)
- Treasury wallet initializes from `data/treasury_keypair.json` with `JARVIS_WALLET_PASSWORD` loaded from `tg_bot/.env`.  
- Treasury balance fetch now works with CoinGecko fallback if `price.jup.ag` is down.  
- Commodity prices for XAG/XPT now resolve via Yahoo Finance fallback.

## What Fails (root causes)
- X OAuth issues are typically expired OAuth2 tokens or mismatched OAuth1/OAuth2 accounts.  
- Video posts fail if tweepy is unavailable or OAuth1 is missing/mismatched.  
- Telegram buy bot callback handling is disabled when sharing the same token with the main bot and polling is not running.

## Conclusive Troubleshooting Checklist
### X OAuth + Posting
1) Re-run OAuth2 setup via `python bots/twitter/oauth_setup.py` and confirm `https://api.twitter.com/2/users/me` returns `@jarvis_lifeos`.  
2) Ensure `X_EXPECTED_USERNAME=jarvis_lifeos` is set in the environment for all X processes.  
3) Verify OAuth1 (API key/secret + access token/secret) belongs to the same account as OAuth2.  
4) Confirm `tweepy` is installed for media uploads and video chunked upload is enabled.  
5) If tokens expire frequently, validate `offline.access` scope and `X_OAUTH2_REFRESH_TOKEN` presence.

### Grok Imagine Video
1) Refresh cookies using `python bots/grok_imagine/grok_login.py`.  
2) Generate video via `python bots/grok_imagine/generate_video_from_image.py`.  
3) Set `X_VIDEO_DIR=bots/grok_imagine/generated` so `bots/twitter/bot.py` attaches the latest mp4.  
4) If posting fails, verify OAuth1 credentials and X media limits.

### Telegram Automation
1) Ensure `TELEGRAM_BOT_TOKEN` + `TELEGRAM_ADMIN_IDS` are set in `tg_bot/.env`.  
2) For separate buy bot callbacks, set `TELEGRAM_BUY_BOT_TOKEN` and keep `BUY_BOT_ENABLE_POLLING=auto` or `true`.  
3) To fully auto-reply in groups, set `TG_REPLY_MODE=all` and tune `TG_REPLY_COOLDOWN_SECONDS`.  
4) Verify `BUY_BOT_TOKEN_ADDRESS` + `HELIUS_API_KEY` are set for buy notifications.

### Treasury Buy Flow
1) Confirm `data/treasury_keypair.json` exists and `JARVIS_WALLET_PASSWORD` is set.  
2) Set `TREASURY_ADMIN_IDS` to the Telegram user IDs allowed to trade.  
3) Set `TREASURY_LIVE_MODE=true` to enable real swaps (otherwise dry-run).  
4) For status cards, set `TREASURY_WALLET_ADDRESS`.

## Automation Plan (recommended)
1) Choose a single X pipeline: prefer `bots/twitter/bot.py` + `bots/twitter/sentiment_poster.py`; disable legacy `core/social/twitter_bot.py` and `core/integrations/x_sentiment_bot.py` unless needed.  
2) Centralize X credentials to one env file and export into the process environment (avoid mixed `.env` sources).  
3) Run Telegram main bot (`tg_bot/bot.py`) as the always-on chat responder; run buy bot (`bots/buy_tracker/bot.py`) with a separate token to keep callbacks reliable.  
4) Schedule Grok Imagine video generation and set `X_VIDEO_DIR` so the next post automatically attaches video.  
5) Add a small daily health check task that calls `TwitterClient.connect()` and a Telegram `getMe` to verify connectivity.

## Latest Docs (reference)
- X API v2: https://developer.x.com/en/docs/x-api  
- X OAuth 2.0 (user context): https://developer.x.com/en/docs/authentication/oauth-2-0/user-access-token  
- X media upload v1.1: https://developer.x.com/en/docs/twitter-api/v1/media/upload-media/api-reference/post-media-upload  
- Telegram Bot API: https://core.telegram.org/bots/api  
- python-telegram-bot: https://docs.python-telegram-bot.org/
